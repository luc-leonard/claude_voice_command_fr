"""Service vocal pour Claude Code - écoute continue et synthèse vocale."""

from .audio_capture import AudioCapture
from .audio_player import AudioPlayer
from .config import VoiceConfig
from .synthesizer import KyutaiSynthesizer
from .transcriber import WhisperTranscriber
from .vad import VoiceActivityDetector

__all__ = [
    "AudioCapture",
    "AudioPlayer",
    "KyutaiSynthesizer",
    "VoiceActivityDetector",
    "VoiceConfig",
    "WhisperTranscriber",
]
