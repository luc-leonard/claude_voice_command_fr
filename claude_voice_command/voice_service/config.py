"""Configuration du service vocal."""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class TTSVoice(Enum):
    """Voix TTS disponibles."""
    SIWIS = "fr_FR-siwis-medium"      # Voix féminine
    GILLES = "fr_FR-gilles-low"       # Voix masculine


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

    # Piper TTS
    tts_voice: TTSVoice = field(default=TTSVoice.SIWIS)
    tts_speaker_id: int = 0
    tts_length_scale: float = 1.0  # Vitesse (< 1 = plus rapide)
    tts_noise_scale: float = 0.667
    tts_noise_w: float = 0.8

    # Chemins
    models_dir: Path = field(default_factory=lambda: Path.home() / ".cache" / "voice_models")

    def __post_init__(self):
        """Crée les répertoires nécessaires."""
        self.models_dir.mkdir(parents=True, exist_ok=True)

    @property
    def chunk_size(self) -> int:
        """Taille des chunks audio en échantillons."""
        return int(self.sample_rate * self.chunk_duration_ms / 1000)
