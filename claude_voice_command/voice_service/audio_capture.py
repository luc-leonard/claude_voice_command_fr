"""Capture audio depuis le microphone via PulseAudio."""

import asyncio
import ctypes
import logging
import os
from collections.abc import AsyncIterator
from ctypes import POINTER, byref, c_char_p, c_int, c_size_t, c_uint32, c_void_p
from enum import IntEnum

import numpy as np

from .config import VoiceConfig

logger = logging.getLogger(__name__)

# Configurer PULSE_SERVER pour WSLg si disponible
if os.path.exists("/mnt/wslg/PulseServer"):
    os.environ.setdefault("PULSE_SERVER", "/mnt/wslg/PulseServer")


# === Bindings ctypes pour libpulse-simple ===

class PaSampleFormat(IntEnum):
    """Formats d'échantillons PulseAudio."""
    PA_SAMPLE_FLOAT32LE = 5
    PA_SAMPLE_S16LE = 3


class PaStreamDirection(IntEnum):
    """Direction du flux."""
    PA_STREAM_RECORD = 2
    PA_STREAM_PLAYBACK = 1


class PaSampleSpec(ctypes.Structure):
    """Spécification d'échantillonnage."""
    _fields_ = [
        ("format", c_int),
        ("rate", c_uint32),
        ("channels", ctypes.c_uint8),
    ]


class PaBufferAttr(ctypes.Structure):
    """Attributs de buffer."""
    _fields_ = [
        ("maxlength", c_uint32),
        ("tlength", c_uint32),
        ("prebuf", c_uint32),
        ("minreq", c_uint32),
        ("fragsize", c_uint32),
    ]


# Charger libpulse-simple
try:
    _libpulse = ctypes.CDLL("libpulse-simple.so.0")

    # pa_simple_new
    _libpulse.pa_simple_new.argtypes = [
        c_char_p,  # server
        c_char_p,  # name
        c_int,     # dir
        c_char_p,  # dev
        c_char_p,  # stream_name
        POINTER(PaSampleSpec),  # ss
        c_void_p,  # channel_map
        POINTER(PaBufferAttr),  # attr
        POINTER(c_int),  # error
    ]
    _libpulse.pa_simple_new.restype = c_void_p

    # pa_simple_read
    _libpulse.pa_simple_read.argtypes = [c_void_p, c_void_p, c_size_t, POINTER(c_int)]
    _libpulse.pa_simple_read.restype = c_int

    # pa_simple_write
    _libpulse.pa_simple_write.argtypes = [c_void_p, c_void_p, c_size_t, POINTER(c_int)]
    _libpulse.pa_simple_write.restype = c_int

    # pa_simple_drain
    _libpulse.pa_simple_drain.argtypes = [c_void_p, POINTER(c_int)]
    _libpulse.pa_simple_drain.restype = c_int

    # pa_simple_free
    _libpulse.pa_simple_free.argtypes = [c_void_p]
    _libpulse.pa_simple_free.restype = None

    # pa_strerror
    _libpulse.pa_strerror.argtypes = [c_int]
    _libpulse.pa_strerror.restype = c_char_p

    PULSE_AVAILABLE = True
except OSError as e:
    logger.warning(f"libpulse-simple non disponible: {e}")
    PULSE_AVAILABLE = False


def _pa_error_string(error_code: int) -> str:
    """Retourne le message d'erreur PulseAudio."""
    if PULSE_AVAILABLE:
        return _libpulse.pa_strerror(error_code).decode()
    return f"Error {error_code}"


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

        self._pa_handle = _libpulse.pa_simple_new(
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
            raise RuntimeError(f"Erreur PulseAudio: {_pa_error_string(error.value)}")

        logger.info(f"PulseAudio ouvert (sample_rate={self.config.sample_rate})")

    def _close_pulse(self) -> None:
        """Ferme la connexion PulseAudio."""
        if self._pa_handle:
            _libpulse.pa_simple_free(self._pa_handle)
            self._pa_handle = None

    def _read_chunk_sync(self) -> np.ndarray | None:
        """Lit un chunk audio de manière synchrone."""
        if not self._pa_handle:
            return None

        # Créer un buffer pour les échantillons
        n_samples = self.config.chunk_size
        buffer = (ctypes.c_float * n_samples)()
        buffer_size = n_samples * ctypes.sizeof(ctypes.c_float)

        error = c_int(0)
        result = _libpulse.pa_simple_read(
            self._pa_handle,
            buffer,
            buffer_size,
            byref(error),
        )

        if result < 0:
            logger.error(f"Erreur lecture PulseAudio: {_pa_error_string(error.value)}")
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


class AudioPlayer:
    """Lecteur audio via PulseAudio."""

    def __init__(self, sample_rate: int = 22050):
        self.sample_rate = sample_rate
        self._pa_handle: c_void_p | None = None

    def _open_pulse(self) -> None:
        """Ouvre la connexion PulseAudio pour la lecture."""
        if not PULSE_AVAILABLE:
            raise RuntimeError("libpulse-simple non disponible")

        spec = PaSampleSpec()
        spec.format = PaSampleFormat.PA_SAMPLE_FLOAT32LE
        spec.rate = self.sample_rate
        spec.channels = 1

        error = c_int(0)

        self._pa_handle = _libpulse.pa_simple_new(
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
            raise RuntimeError(f"Erreur PulseAudio: {_pa_error_string(error.value)}")

    def _close_pulse(self) -> None:
        """Ferme la connexion PulseAudio."""
        if self._pa_handle:
            _libpulse.pa_simple_free(self._pa_handle)
            self._pa_handle = None

    def play(self, audio: np.ndarray) -> bool:
        """Joue l'audio."""
        try:
            self._open_pulse()

            # Convertir en float32 si nécessaire
            if audio.dtype != np.float32:
                audio = audio.astype(np.float32)

            # Écrire l'audio
            buffer = audio.ctypes.data_as(ctypes.c_void_p)
            buffer_size = audio.nbytes

            error = c_int(0)
            result = _libpulse.pa_simple_write(
                self._pa_handle,
                buffer,
                buffer_size,
                byref(error),
            )

            if result < 0:
                logger.error(f"Erreur écriture PulseAudio: {_pa_error_string(error.value)}")
                return False

            # Attendre que tout soit joué
            _libpulse.pa_simple_drain(self._pa_handle, byref(error))

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
