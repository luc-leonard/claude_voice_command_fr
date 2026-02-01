"""Capture audio depuis le microphone via PulseAudio."""

import asyncio
import ctypes
import logging
from collections.abc import AsyncIterator
from ctypes import byref, c_int, c_uint32, c_void_p

import numpy as np

from .config import VoiceConfig
from .pulse_bindings import (
    PULSE_AVAILABLE,
    PaBufferAttr,
    PaSampleFormat,
    PaSampleSpec,
    PaStreamDirection,
    get_libpulse,
    pa_error_string,
)

logger = logging.getLogger(__name__)


class AudioCapture:
    """Capture audio continue depuis le microphone via PulseAudio."""

    def __init__(self, config: VoiceConfig):
        self.config = config
        self._running = False
        self._pa_handle: c_void_p | None = None
        self._queue: asyncio.Queue[np.ndarray] = asyncio.Queue(maxsize=100)
        self._capture_task: asyncio.Task | None = None

    def _open_pulse(self) -> None:
        """Ouvre la connexion PulseAudio."""
        if not PULSE_AVAILABLE:
            raise RuntimeError("libpulse-simple non disponible")

        libpulse = get_libpulse()

        spec = PaSampleSpec()
        spec.format = PaSampleFormat.PA_SAMPLE_FLOAT32LE
        spec.rate = self.config.sample_rate
        spec.channels = self.config.channels

        # Buffer pour faible latence
        attr = PaBufferAttr()
        fragment_size = self.config.chunk_size * 4  # float32 = 4 bytes
        attr.maxlength = c_uint32(-1)  # -1 = default
        attr.fragsize = fragment_size

        error = c_int(0)

        self._pa_handle = libpulse.pa_simple_new(
            None,  # server par défaut
            b"claude-voice",  # nom application
            PaStreamDirection.PA_STREAM_RECORD,
            None,  # device par défaut
            b"voice-capture",  # nom du flux
            byref(spec),
            None,  # channel map par défaut
            byref(attr),
            byref(error),
        )

        if not self._pa_handle:
            raise RuntimeError(f"Erreur PulseAudio: {pa_error_string(error.value)}")

        logger.info(f"PulseAudio ouvert (sample_rate={self.config.sample_rate})")

    def _close_pulse(self) -> None:
        """Ferme la connexion PulseAudio."""
        if self._pa_handle:
            libpulse = get_libpulse()
            libpulse.pa_simple_free(self._pa_handle)
            self._pa_handle = None

    def _read_chunk_sync(self) -> np.ndarray | None:
        """Lit un chunk audio de manière synchrone."""
        if not self._pa_handle:
            return None

        libpulse = get_libpulse()

        # Créer un buffer pour les échantillons
        n_samples = self.config.chunk_size
        buffer = (ctypes.c_float * n_samples)()
        buffer_size = n_samples * ctypes.sizeof(ctypes.c_float)

        error = c_int(0)
        result = libpulse.pa_simple_read(
            self._pa_handle,
            buffer,
            buffer_size,
            byref(error),
        )

        if result < 0:
            logger.error(f"Erreur lecture PulseAudio: {pa_error_string(error.value)}")
            return None

        return np.array(buffer, dtype=np.float32)

    async def _capture_loop(self) -> None:
        """Boucle de capture audio en arrière-plan."""
        loop = asyncio.get_running_loop()

        while self._running:
            try:
                # Lire dans un thread pour ne pas bloquer
                chunk = await loop.run_in_executor(None, self._read_chunk_sync)

                if chunk is not None and self._running:
                    try:
                        self._queue.put_nowait(chunk)
                    except asyncio.QueueFull:
                        # Supprimer le plus ancien si plein
                        try:
                            self._queue.get_nowait()
                            self._queue.put_nowait(chunk)
                        except asyncio.QueueEmpty:
                            pass

            except Exception as e:
                if self._running:
                    logger.error(f"Erreur capture: {e}")
                    await asyncio.sleep(0.1)

    async def start(self) -> None:
        """Démarre la capture audio."""
        if self._running:
            return

        self._open_pulse()
        self._running = True
        self._capture_task = asyncio.create_task(self._capture_loop())

        logger.info("Capture audio démarrée")

    async def stop(self) -> None:
        """Arrête la capture audio."""
        self._running = False

        if self._capture_task:
            self._capture_task.cancel()
            try:
                await self._capture_task
            except asyncio.CancelledError:
                pass
            self._capture_task = None

        self._close_pulse()

        # Vider la queue
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break

        logger.info("Capture audio arrêtée")

    async def read_chunk(self) -> np.ndarray | None:
        """Lit un chunk audio depuis la queue."""
        if not self._running:
            return None

        try:
            return await asyncio.wait_for(self._queue.get(), timeout=1.0)
        except asyncio.TimeoutError:
            return None

    async def stream(self) -> AsyncIterator[np.ndarray]:
        """Génère un flux continu de chunks audio."""
        while self._running:
            chunk = await self.read_chunk()
            if chunk is not None:
                yield chunk

    @property
    def is_running(self) -> bool:
        """Indique si la capture est en cours."""
        return self._running
