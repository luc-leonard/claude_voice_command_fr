"""Synthèse vocale avec Kyutai DSM-TTS 1.6B."""

import asyncio
import contextlib
import logging
import re
import sys

import numpy as np
import torch

from .audio_player import AudioPlayer
from .config import TTSVoice, VoiceConfig

logger = logging.getLogger(__name__)

# Dictionnaire de prononciations pour le TTS
# Clé = mot/abréviation, Valeur = prononciation phonétique
PRONUNCIATIONS = {
    # Abréviations dev
    "PR": "pé-air",
    "MR": "aime-air",
    "CI": "cé-i",
    "CD": "cé-dé",
    "CI/CD": "cé-i cé-dé",
    "API": "a-pé-i",
    "URL": "u-erre-elle",
    "SQL": "esse-cu-elle",
    "NoSQL": "no esse-cu-elle",
    "JSON": "jay-sonne",
    "YAML": "ya-meul",
    "HTML": "ache-té-aime-elle",
    "CSS": "cé-esse-esse",
    "JS": "ji-esse",
    "TS": "té-esse",
    "JWT": "ji-wote",
    "SSH": "esse-esse-ache",
    "HTTP": "ache-té-té-pé",
    "HTTPS": "ache-té-té-pé-esse",
    "GPU": "ji-pé-u",
    "CPU": "cé-pé-u",
    "RAM": "rame",
    "SSD": "esse-esse-dé",
    "IDE": "i-dé-euh",
    "CLI": "cé-elle-i",
    "GUI": "ji-u-i",
    "UI": "u-i",
    "UX": "u-ixe",
    "npm": "aime-pé-aime",
    "pip": "pipe",
    "git": "guite",
    "GitHub": "guite-eube",
    "GitLab": "guite-labe",
    # Claude
    "MCP": "aime-cé-pé",
    "LLM": "elle-elle-aime",
    "GPT": "ji-pé-té",
    # Outils
    "VS Code": "vi-esse code",
    "VSCode": "vi-esse code",
    "tmux": "té-muxe",
}


def _prepare_text_for_tts(text: str) -> str:
    """Prépare le texte pour le TTS en appliquant les prononciations."""
    result = text

    # Trier par longueur décroissante pour éviter les remplacements partiels
    sorted_words = sorted(PRONUNCIATIONS.keys(), key=len, reverse=True)

    for word in sorted_words:
        pronunciation = PRONUNCIATIONS[word]
        # Remplacement avec respect des limites de mots
        pattern = re.compile(r'\b' + re.escape(word) + r'\b', re.IGNORECASE)
        result = pattern.sub(pronunciation, result)

    return result


@contextlib.contextmanager
def _redirect_stdout_to_stderr():
    """Redirige sys.stdout vers stderr pour éviter de polluer le protocole MCP stdio.

    Note: on ne redirige PAS le fd 1 natif (os.dup2) car le transport MCP stdio
    l'utilise pour ses réponses JSON-RPC.
    """
    old_stdout = sys.stdout
    sys.stdout = sys.stderr
    try:
        yield
    finally:
        sys.stdout = old_stdout


class KyutaiSynthesizer:
    """Synthétiseur vocal utilisant Kyutai DSM-TTS 1.6B."""

    def __init__(self, config: VoiceConfig):
        self.config = config
        self._tts_model = None
        self._voice_cache: dict[str, object] = {}
        self._sample_rate: int = 24000

    def _load_model(self) -> None:
        """Charge le modèle Kyutai (lazy loading)."""
        if self._tts_model is not None:
            return

        with _redirect_stdout_to_stderr():
            from moshi.models.loaders import CheckpointInfo
            from moshi.models.tts import TTSModel

            logger.info("Chargement du modèle Kyutai DSM-TTS 1.6B...")
            checkpoint_info = CheckpointInfo.from_hf_repo("kyutai/tts-1.6b-en_fr")
            self._tts_model = TTSModel.from_checkpoint_info(
                checkpoint_info,
                n_q=32,
                temp=self.config.tts_temp,
                device=self.config.tts_device,
            )
            self._sample_rate = self._tts_model.mimi.sample_rate
            logger.info(
                f"Modèle Kyutai chargé (device={self.config.tts_device}, "
                f"sample_rate={self._sample_rate})"
            )

    def _get_condition_attributes(self, voice: TTSVoice):
        """Retourne les condition_attributes pour une voix, avec cache."""
        voice_key = voice.value
        if voice_key not in self._voice_cache:
            self._load_model()
            voice_path = self._tts_model.get_voice_path(voice.value)
            self._voice_cache[voice_key] = self._tts_model.make_condition_attributes(
                [voice_path], cfg_coef=self.config.tts_cfg_coef
            )
            logger.info(f"Voice state cachée: {voice_key}")
        return self._voice_cache[voice_key]

    def set_voice(self, voice: TTSVoice) -> None:
        """Change la voix TTS."""
        self.config.tts_voice = voice
        logger.info(f"Voix TTS changée: {voice.value}")

    def synthesize(self, text: str) -> np.ndarray | None:
        """
        Synthétise du texte en audio.

        Args:
            text: Texte à synthétiser

        Returns:
            Audio float32 normalisé [-1, 1] ou None si échec
        """
        if not text.strip():
            return None

        self._load_model()

        # Préparer le texte avec les prononciations correctes
        prepared_text = _prepare_text_for_tts(text)
        logger.debug(f"Texte préparé: '{prepared_text[:100]}'")

        try:
            with _redirect_stdout_to_stderr():
                voice = self.config.tts_voice
                condition_attributes = self._get_condition_attributes(voice)

                entries = self._tts_model.prepare_script([prepared_text], padding_between=1)
                result = self._tts_model.generate([entries], [condition_attributes])

                # Décodage frames → PCM float32
                pcms = []
                with self._tts_model.mimi.streaming(1), torch.no_grad():
                    for frame in result.frames[self._tts_model.delay_steps:]:
                        pcm = self._tts_model.mimi.decode(frame[:, 1:, :]).cpu().numpy()
                        pcms.append(np.clip(pcm[0, 0], -1, 1))

                if not pcms:
                    return None

                audio = np.concatenate(pcms).astype(np.float32)

            logger.debug(f"Synthèse: '{text[:50]}...' ({len(audio)} samples)")
            return audio

        except Exception as e:
            logger.error(f"Erreur de synthèse: {e}")
            return None

    @property
    def sample_rate(self) -> int:
        """Retourne le sample rate du modèle (24000 Hz)."""
        return self._sample_rate

    def speak(self, text: str) -> bool:
        """
        Synthétise et joue le texte.

        Args:
            text: Texte à dire

        Returns:
            True si succès
        """
        audio = self.synthesize(text)
        if audio is None:
            return False

        try:
            player = AudioPlayer(sample_rate=self.sample_rate)
            return player.play(audio)
        except Exception as e:
            logger.error(f"Erreur de lecture audio: {e}")
            return False

    async def speak_async(self, text: str) -> bool:
        """
        Version asynchrone de speak.

        Args:
            text: Texte à dire

        Returns:
            True si succès
        """
        loop = asyncio.get_running_loop()
        audio = await loop.run_in_executor(None, self.synthesize, text)
        if audio is None:
            return False

        try:
            player = AudioPlayer(sample_rate=self.sample_rate)
            return await player.play_async(audio)
        except Exception as e:
            logger.error(f"Erreur de lecture audio: {e}")
            return False
