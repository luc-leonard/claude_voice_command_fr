"""Lecteur audio via PulseAudio."""

import asyncio
import ctypes
import logging
from ctypes import byref, c_int, c_void_p

import numpy as np

from .pulse_bindings import (
    PULSE_AVAILABLE,
    PaSampleFormat,
    PaSampleSpec,
    PaStreamDirection,
    get_libpulse,
    pa_error_string,
)

logger = logging.getLogger(__name__)


class AudioPlayer:
    """Lecteur audio via PulseAudio."""

    def __init__(self, sample_rate: int = 22050):
        self.sample_rate = sample_rate
        self._pa_handle: c_void_p | None = None

    def _open_pulse(self) -> None:
        """Ouvre la connexion PulseAudio pour la lecture."""
        if not PULSE_AVAILABLE:
            raise RuntimeError("libpulse-simple non disponible")

        libpulse = get_libpulse()

        spec = PaSampleSpec()
        spec.format = PaSampleFormat.PA_SAMPLE_FLOAT32LE
        spec.rate = self.sample_rate
        spec.channels = 1

        error = c_int(0)

        self._pa_handle = libpulse.pa_simple_new(
            None,
            b"claude-voice",
            PaStreamDirection.PA_STREAM_PLAYBACK,
            None,
            b"voice-output",
            byref(spec),
            None,
            None,
            byref(error),
        )

        if not self._pa_handle:
            raise RuntimeError(f"Erreur PulseAudio: {pa_error_string(error.value)}")

    def _close_pulse(self) -> None:
        """Ferme la connexion PulseAudio."""
        if self._pa_handle:
            libpulse = get_libpulse()
            libpulse.pa_simple_free(self._pa_handle)
            self._pa_handle = None

    def play(self, audio: np.ndarray) -> bool:
        """Joue l'audio."""
        try:
            self._open_pulse()
            libpulse = get_libpulse()

            # Convertir en float32 si nécessaire
            if audio.dtype != np.float32:
                audio = audio.astype(np.float32)

            # Écrire l'audio
            buffer = audio.ctypes.data_as(ctypes.c_void_p)
            buffer_size = audio.nbytes

            error = c_int(0)
            result = libpulse.pa_simple_write(
                self._pa_handle,
                buffer,
                buffer_size,
                byref(error),
            )

            if result < 0:
                logger.error(f"Erreur écriture PulseAudio: {pa_error_string(error.value)}")
                return False

            # Attendre que tout soit joué
            libpulse.pa_simple_drain(self._pa_handle, byref(error))

            return True

        except Exception as e:
            logger.error(f"Erreur lecture audio: {e}")
            return False
        finally:
            self._close_pulse()

    async def play_async(self, audio: np.ndarray) -> bool:
        """Version asynchrone de play."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.play, audio)
