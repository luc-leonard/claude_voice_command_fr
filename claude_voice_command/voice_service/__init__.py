"""Service vocal pour Claude Code - écoute continue et synthèse vocale."""

from .audio_capture import AudioCapture
from .vad import VoiceActivityDetector
from .transcriber import WhisperTranscriber
from .synthesizer import PiperSynthesizer
from .config import VoiceConfig

__all__ = [
    "AudioCapture",
    "VoiceActivityDetector",
    "WhisperTranscriber",
    "PiperSynthesizer",
    "VoiceConfig",
]
