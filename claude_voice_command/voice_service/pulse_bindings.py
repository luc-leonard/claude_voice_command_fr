"""Bindings ctypes pour libpulse-simple."""

import ctypes
import logging
import os
from ctypes import POINTER, c_char_p, c_int, c_size_t, c_uint32, c_void_p
from enum import IntEnum

logger = logging.getLogger(__name__)

# Configurer PULSE_SERVER pour WSLg si disponible
if os.path.exists("/mnt/wslg/PulseServer"):
    os.environ.setdefault("PULSE_SERVER", "/mnt/wslg/PulseServer")


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
_libpulse = None
PULSE_AVAILABLE = False

try:
    _libpulse = ctypes.CDLL("libpulse-simple.so.0")

    # pa_simple_new
    _libpulse.pa_simple_new.argtypes = [
        c_char_p,  # server
        c_char_p,  # name
        c_int,  # dir
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


def get_libpulse():
    """Retourne la bibliothèque libpulse-simple."""
    if not PULSE_AVAILABLE:
        raise RuntimeError("libpulse-simple non disponible")
    return _libpulse


def pa_error_string(error_code: int) -> str:
    """Retourne le message d'erreur PulseAudio."""
    if PULSE_AVAILABLE:
        return _libpulse.pa_strerror(error_code).decode()
    return f"Error {error_code}"
