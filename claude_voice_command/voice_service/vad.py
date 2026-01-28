"""Voice Activity Detection avec Silero VAD."""

import logging
from collections import deque
from dataclasses import dataclass
from enum import Enum

import numpy as np
import torch

from .config import VoiceConfig

logger = logging.getLogger(__name__)


class SpeechState(Enum):
    """État de la détection vocale."""
    SILENCE = "silence"
    SPEECH_START = "speech_start"
    SPEECH = "speech"
    SPEECH_END = "speech_end"


@dataclass
class VADResult:
    """Résultat de la détection VAD."""
    state: SpeechState
    probability: float
    audio_segment: np.ndarray | None = None


class VoiceActivityDetector:
    """Détecteur d'activité vocale basé sur Silero VAD."""

    def __init__(self, config: VoiceConfig):
        self.config = config
        self._model = None
        self._state: SpeechState = SpeechState.SILENCE

        # Buffers pour accumuler l'audio
        self._speech_buffer: list[np.ndarray] = []
        self._silence_buffer: list[np.ndarray] = []

        # Compteurs de durée
        self._speech_duration_ms = 0
        self._silence_duration_ms = 0

        # Padding pour capturer le début de la parole
        samples_to_keep = int(config.sample_rate * config.speech_pad_ms / 1000)
        max_chunks = max(1, samples_to_keep // config.chunk_size + 1)
        self._pre_speech_buffer: deque[np.ndarray] = deque(maxlen=max_chunks)

    def _load_model(self) -> None:
        """Charge le modèle Silero VAD."""
        if self._model is not None:
            return

        logger.info("Chargement du modèle Silero VAD...")
        self._model, _ = torch.hub.load(
            repo_or_dir="snakers4/silero-vad",
            model="silero_vad",
            force_reload=False,
            trust_repo=True,
        )
        self._model.eval()
        logger.info("Modèle Silero VAD chargé")

    def reset(self) -> None:
        """Réinitialise l'état du détecteur."""
        self._state = SpeechState.SILENCE
        self._speech_buffer.clear()
        self._silence_buffer.clear()
        self._pre_speech_buffer.clear()
        self._speech_duration_ms = 0
        self._silence_duration_ms = 0

        if self._model is not None:
            self._model.reset_states()

    def process(self, audio_chunk: np.ndarray) -> VADResult:
        """
        Traite un chunk audio et retourne le résultat VAD.

        Args:
            audio_chunk: Chunk audio float32 normalisé [-1, 1]

        Returns:
            VADResult avec l'état et éventuellement le segment audio complet
        """
        self._load_model()

        # Convertir en tensor
        audio_tensor = torch.from_numpy(audio_chunk).float()

        # Obtenir la probabilité de parole
        with torch.no_grad():
            prob = self._model(audio_tensor, self.config.sample_rate).item()

        is_speech = prob >= self.config.vad_threshold
        chunk_duration_ms = len(audio_chunk) * 1000 // self.config.sample_rate

        # Machine à états
        if self._state == SpeechState.SILENCE:
            self._pre_speech_buffer.append(audio_chunk)

            if is_speech:
                self._speech_duration_ms = chunk_duration_ms
                self._state = SpeechState.SPEECH_START
                # Inclure le padding pré-parole
                self._speech_buffer = list(self._pre_speech_buffer)
                self._speech_buffer.append(audio_chunk)

            return VADResult(state=SpeechState.SILENCE, probability=prob)

        elif self._state in (SpeechState.SPEECH_START, SpeechState.SPEECH):
            self._speech_buffer.append(audio_chunk)

            if is_speech:
                self._speech_duration_ms += chunk_duration_ms
                self._silence_duration_ms = 0
                self._silence_buffer.clear()

                if (self._state == SpeechState.SPEECH_START and
                    self._speech_duration_ms >= self.config.min_speech_duration_ms):
                    self._state = SpeechState.SPEECH
                    return VADResult(state=SpeechState.SPEECH, probability=prob)

                return VADResult(state=self._state, probability=prob)
            else:
                # Silence détecté pendant la parole
                self._silence_duration_ms += chunk_duration_ms
                self._silence_buffer.append(audio_chunk)

                if self._silence_duration_ms >= self.config.min_silence_duration_ms:
                    # Fin de parole confirmée
                    if self._speech_duration_ms >= self.config.min_speech_duration_ms:
                        # Retirer le silence final du buffer de parole
                        for _ in range(len(self._silence_buffer)):
                            if self._speech_buffer:
                                self._speech_buffer.pop()

                        # Concaténer l'audio
                        audio_segment = np.concatenate(self._speech_buffer)

                        # Réinitialiser
                        self._state = SpeechState.SILENCE
                        self._speech_buffer.clear()
                        self._silence_buffer.clear()
                        self._pre_speech_buffer.clear()
                        self._speech_duration_ms = 0
                        self._silence_duration_ms = 0

                        return VADResult(
                            state=SpeechState.SPEECH_END,
                            probability=prob,
                            audio_segment=audio_segment,
                        )
                    else:
                        # Parole trop courte, ignorer
                        self._state = SpeechState.SILENCE
                        self._speech_buffer.clear()
                        self._silence_buffer.clear()
                        self._speech_duration_ms = 0
                        self._silence_duration_ms = 0

                return VADResult(state=self._state, probability=prob)

        return VADResult(state=self._state, probability=prob)
