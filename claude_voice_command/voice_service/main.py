"""Point d'entrée du service vocal."""

import asyncio
import logging
import os
from dataclasses import dataclass
from enum import Enum
from typing import Callable

# Configurer PULSE_SERVER pour WSLg si disponible
if os.path.exists("/mnt/wslg/PulseServer"):
    os.environ.setdefault("PULSE_SERVER", "/mnt/wslg/PulseServer")

from .audio_capture import AudioCapture
from .config import TTSVoice, VoiceConfig
from .synthesizer import KyutaiSynthesizer
from .transcriber import TranscriptionResult, WhisperTranscriber
from .vad import SpeechState, VoiceActivityDetector

logger = logging.getLogger(__name__)


class ServiceState(Enum):
    """État du service vocal."""
    STOPPED = "stopped"
    STARTING = "starting"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"


@dataclass
class VoiceServiceStatus:
    """Statut du service vocal."""
    state: ServiceState
    is_listening: bool
    current_voice: str
    last_transcription: str | None = None


class VoiceService:
    """Service vocal principal avec écoute continue."""

    def __init__(self, config: VoiceConfig | None = None):
        self.config = config or VoiceConfig()
        self._audio = AudioCapture(self.config)
        self._vad = VoiceActivityDetector(self.config)
        self._transcriber = WhisperTranscriber(self.config)
        self._synthesizer = KyutaiSynthesizer(self.config)

        self._state = ServiceState.STOPPED
        self._last_transcription: str | None = None
        self._on_transcription: Callable[[str], None] | None = None
        self._listen_task: asyncio.Task | None = None

    @property
    def state(self) -> ServiceState:
        """État actuel du service."""
        return self._state

    @property
    def is_listening(self) -> bool:
        """Indique si le service écoute."""
        return self._state in (ServiceState.LISTENING, ServiceState.PROCESSING)

    def get_status(self) -> VoiceServiceStatus:
        """Retourne le statut complet du service."""
        return VoiceServiceStatus(
            state=self._state,
            is_listening=self.is_listening,
            current_voice=self.config.tts_voice.value,
            last_transcription=self._last_transcription,
        )

    def set_transcription_callback(self, callback: Callable[[str], None]) -> None:
        """Définit le callback appelé lors d'une transcription."""
        self._on_transcription = callback

    def set_voice(self, voice: TTSVoice | str) -> None:
        """Change la voix TTS."""
        if isinstance(voice, str):
            voice = TTSVoice(voice)
        self._synthesizer.set_voice(voice)

    async def start_listening(self) -> None:
        """Démarre l'écoute continue."""
        if self._state != ServiceState.STOPPED:
            logger.warning("Service déjà en cours d'exécution")
            return

        self._state = ServiceState.STARTING
        logger.info("Démarrage du service vocal...")

        # Démarrer la capture audio
        await self._audio.start()

        # Lancer la boucle d'écoute
        self._state = ServiceState.LISTENING
        self._listen_task = asyncio.create_task(self._listen_loop())

        logger.info("Service vocal démarré - en écoute")

    async def stop_listening(self) -> None:
        """Arrête l'écoute."""
        if self._state == ServiceState.STOPPED:
            return

        logger.info("Arrêt du service vocal...")

        # Arrêter la tâche d'écoute
        if self._listen_task:
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass
            self._listen_task = None

        # Arrêter la capture audio
        await self._audio.stop()

        # Réinitialiser le VAD
        self._vad.reset()

        self._state = ServiceState.STOPPED
        logger.info("Service vocal arrêté")

    async def _listen_loop(self) -> None:
        """Boucle principale d'écoute."""
        try:
            async for audio_chunk in self._audio.stream():
                if self._state == ServiceState.STOPPED:
                    break

                # Traiter avec VAD
                vad_result = self._vad.process(audio_chunk)

                if vad_result.state == SpeechState.SPEECH_END and vad_result.audio_segment is not None:
                    # Fin de parole détectée, transcrire
                    self._state = ServiceState.PROCESSING
                    await self._process_speech(vad_result.audio_segment)
                    self._state = ServiceState.LISTENING

        except asyncio.CancelledError:
            logger.debug("Boucle d'écoute annulée")
        except Exception as e:
            logger.error(f"Erreur dans la boucle d'écoute: {e}")
            self._state = ServiceState.STOPPED

    async def _process_speech(self, audio: any) -> None:
        """Traite un segment de parole."""
        # Transcrire
        result = self._transcriber.transcribe(audio)

        if result and result.text:
            self._last_transcription = result.text
            logger.info(f"Transcription: '{result.text}'")

            # Appeler le callback si défini
            if self._on_transcription:
                try:
                    self._on_transcription(result.text)
                except Exception as e:
                    logger.error(f"Erreur dans le callback de transcription: {e}")

    async def speak(self, text: str) -> bool:
        """
        Synthétise et joue du texte.

        Args:
            text: Texte à dire

        Returns:
            True si succès
        """
        if not text.strip():
            return False

        previous_state = self._state
        self._state = ServiceState.SPEAKING

        try:
            success = await self._synthesizer.speak_async(text)
            return success
        finally:
            self._state = previous_state if previous_state != ServiceState.SPEAKING else ServiceState.LISTENING


async def main():
    """Service vocal avec injection dans tmux."""
    import argparse

    parser = argparse.ArgumentParser(description="Service vocal pour Claude Code")
    parser.add_argument(
        "-t", "--target",
        default="claude",
        help="Session tmux cible (défaut: claude)",
    )
    parser.add_argument(
        "--no-inject",
        action="store_true",
        help="Ne pas injecter le texte (afficher seulement)",
    )
    parser.add_argument(
        "--no-enter",
        action="store_true",
        help="Ne pas appuyer sur Entrée après l'injection",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Activer les logs de debug",
    )
    args = parser.parse_args()

    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    from .keyboard_inject import check_tmux, inject_text, list_tmux_sessions

    if not args.no_inject:
        if not check_tmux(args.target):
            sessions = list_tmux_sessions()
            print()
            print("=" * 50)
            print("ERREUR: Session tmux non trouvée")
            print("=" * 50)
            if sessions:
                print(f"Sessions disponibles: {', '.join(sessions)}")
                print(f"Utilisez: python -m ... -t {sessions[0]}")
            else:
                print("Aucune session tmux active.")
            print()
            print("Pour créer une session et lancer Claude Code:")
            print(f"  tmux new -s {args.target}")
            print("  claude")
            print()
            return

    config = VoiceConfig()
    service = VoiceService(config)

    # Callback d'injection
    def on_transcription(text: str):
        print(f"\n🎤 {text}\n")

        if not args.no_inject:
            success = inject_text(text, press_enter=not args.no_enter, target=args.target)
            if not success:
                print("⚠️  Échec de l'injection")

    service.set_transcription_callback(on_transcription)

    print("=" * 50)
    print("SERVICE VOCAL CLAUDE CODE")
    print("=" * 50)
    print(f"Session tmux: {args.target}")
    print(f"Mode: {'Affichage seul' if args.no_inject else 'Injection tmux'}")
    print(f"Entrée auto: {'Non' if args.no_enter else 'Oui'}")
    print("=" * 50)
    print("Parlez en français. Ctrl+C pour arrêter.")
    print("=" * 50)
    print()

    await service.start_listening()

    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\n\nArrêt du service...")
    finally:
        await service.stop_listening()
        print("Service arrêté.")


if __name__ == "__main__":
    asyncio.run(main())
