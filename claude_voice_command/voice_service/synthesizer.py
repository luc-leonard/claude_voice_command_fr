"""Synthèse vocale avec Piper TTS."""

import logging
import re
import subprocess
from pathlib import Path

import numpy as np

from .audio_capture import AudioPlayer
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

# URLs des modèles Piper
PIPER_MODEL_URLS = {
    TTSVoice.SIWIS: {
        "model": "https://huggingface.co/rhasspy/piper-voices/resolve/main/fr/fr_FR/siwis/medium/fr_FR-siwis-medium.onnx",
        "config": "https://huggingface.co/rhasspy/piper-voices/resolve/main/fr/fr_FR/siwis/medium/fr_FR-siwis-medium.onnx.json",
    },
    TTSVoice.GILLES: {
        "model": "https://huggingface.co/rhasspy/piper-voices/resolve/main/fr/fr_FR/gilles/low/fr_FR-gilles-low.onnx",
        "config": "https://huggingface.co/rhasspy/piper-voices/resolve/main/fr/fr_FR/gilles/low/fr_FR-gilles-low.onnx.json",
    },
}


class PiperSynthesizer:
    """Synthétiseur vocal utilisant Piper TTS."""

    def __init__(self, config: VoiceConfig):
        self.config = config
        self._models_dir = config.models_dir / "piper"
        self._models_dir.mkdir(parents=True, exist_ok=True)
        self._voice: "PiperVoice | None" = None
        self._current_voice_type: TTSVoice | None = None

    def _get_model_paths(self, voice: TTSVoice) -> tuple[Path, Path]:
        """Retourne les chemins du modèle et de sa config."""
        model_path = self._models_dir / f"{voice.value}.onnx"
        config_path = self._models_dir / f"{voice.value}.onnx.json"
        return model_path, config_path

    def _download_model(self, voice: TTSVoice) -> None:
        """Télécharge le modèle Piper si nécessaire."""
        model_path, config_path = self._get_model_paths(voice)

        if model_path.exists() and config_path.exists():
            return

        logger.info(f"Téléchargement du modèle Piper {voice.value}...")

        urls = PIPER_MODEL_URLS[voice]

        # Télécharger le modèle
        if not model_path.exists():
            subprocess.run(
                ["curl", "-L", "-o", str(model_path), urls["model"]],
                check=True,
                capture_output=True,
            )

        # Télécharger la config
        if not config_path.exists():
            subprocess.run(
                ["curl", "-L", "-o", str(config_path), urls["config"]],
                check=True,
                capture_output=True,
            )

        logger.info(f"Modèle Piper {voice.value} téléchargé")

    def _load_voice(self, voice: TTSVoice) -> None:
        """Charge le modèle de voix."""
        if self._current_voice_type == voice and self._voice is not None:
            return

        self._download_model(voice)
        model_path, _ = self._get_model_paths(voice)

        from piper import PiperVoice

        logger.info(f"Chargement du modèle Piper {voice.value}...")
        self._voice = PiperVoice.load(str(model_path), use_cuda=False)
        self._current_voice_type = voice
        logger.info(f"Modèle Piper {voice.value} chargé")

    def set_voice(self, voice: TTSVoice) -> None:
        """Change la voix TTS."""
        self._load_voice(voice)
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

        voice = self.config.tts_voice
        self._load_voice(voice)

        # Préparer le texte avec les prononciations correctes
        prepared_text = _prepare_text_for_tts(text)
        logger.debug(f"Texte préparé: '{prepared_text[:100]}'")

        try:
            # Synthétiser avec Piper
            audio_chunks = []
            for chunk in self._voice.synthesize(prepared_text):
                # Convertir int16 en float32
                audio_int16 = chunk.audio_int16_array
                audio_float32 = audio_int16.astype(np.float32) / 32768.0
                audio_chunks.append(audio_float32)

            if not audio_chunks:
                return None

            # Concaténer tous les chunks
            audio = np.concatenate(audio_chunks)

            logger.debug(f"Synthèse: '{text[:50]}...' ({len(audio)} samples)")

            return audio

        except Exception as e:
            logger.error(f"Erreur de synthèse: {e}")
            return None

    @property
    def sample_rate(self) -> int:
        """Retourne le sample rate de la voix chargée."""
        if self._voice is not None:
            return self._voice.config.sample_rate
        return 22050  # Défaut Piper

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
        audio = self.synthesize(text)
        if audio is None:
            return False

        try:
            player = AudioPlayer(sample_rate=self.sample_rate)
            return await player.play_async(audio)
        except Exception as e:
            logger.error(f"Erreur de lecture audio: {e}")
            return False
