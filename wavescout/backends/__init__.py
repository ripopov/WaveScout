"""Backend implementations for waveform reading.

This package provides adapter implementations for different waveform file readers
(pywellen and pylibfst) that conform to the backend-agnostic protocol types defined
in wavescout.backend_types.
"""

from .base import WaveformBackend, BackendFactory, BackendType

# Import backend implementations to trigger their registration
from . import pywellen_backend
from . import pylibfst_backend

__all__ = [
    'WaveformBackend',
    'BackendFactory', 
    'BackendType',
]