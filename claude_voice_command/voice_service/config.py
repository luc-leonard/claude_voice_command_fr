"""Configuration du service vocal."""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class TTSVoice(Enum):
    """Voix TTS disponibles (Kyutai DSM-TTS, voix cml-tts/fr CC-BY-4.0)."""
    FEMININE_1 = "cml-tts/fr/2216_1745_000007-0001.wav"
    FEMININE_2 = "cml-tts/fr/10087_11650_000028-0002.wav"
    MASCULINE_1 = "cml-tts/fr/296_1028_000022-0001.wav"
    MASCULINE_2 = "cml-tts/fr/1406_1028_000009-0003.wav"


@dataclass
class VoiceConfig:
    """Configuration du service vocal."""

    # Audio
    sample_rate: int = 16000
    channels: int = 1
    chunk_duration_ms: int = 32  # Durée des chunks audio en ms (exactement 32ms / 512 samples pour Silero VAD)

    # VAD (Voice Activity Detection)
    vad_threshold: float = 0.5
    min_speech_duration_ms: int = 250
    min_silence_duration_ms: int = 500
    speech_pad_ms: int = 100

    # Whisper STT
    whisper_model: str = "large-v3"
    whisper_device: str = "cuda"
    whisper_compute_type: str = "float16"
    whisper_language: str = "fr"
    whisper_beam_size: int = 5
    whisper_vad_filter: bool = True

    # Kyutai DSM-TTS
    tts_voice: TTSVoice = field(default=TTSVoice.FEMININE_1)
    tts_device: str = "cuda"
    tts_temp: float = 0.6
    tts_cfg_coef: float = 2.0

    # Chemins
    models_dir: Path = field(default_factory=lambda: Path.home() / ".cache" / "voice_models")

    def __post_init__(self):
        """Crée les répertoires nécessaires."""
        self.models_dir.mkdir(parents=True, exist_ok=True)

    @property
    def chunk_size(self) -> int:
        """Taille des chunks audio en échantillons."""
        return int(self.sample_rate * self.chunk_duration_ms / 1000)
