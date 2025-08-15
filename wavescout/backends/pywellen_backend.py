"""Pywellen backend implementation with adapters for protocol types."""

from typing import Optional, List, cast
from pathlib import Path

try:
    import pywellen
except ImportError:
    raise ImportError("pywellen is required for the pywellen backend. Install it with: poetry run build-pywellen")

from .base import WaveformBackend, BackendType, BackendFactory
from ..backend_types import (
    WWaveform, WHierarchy, WSignal, WVar, WTimeTable, WTimescale,
    WScope, WScopeIter, WVarIter, WVarIndex, WSignalChangeIter, WQueryResult
)


# Since pywellen types already match our protocol interfaces exactly,
# we can use them directly without adapter wrappers. The protocol types
# will structurally match at runtime due to Python's duck typing.
# This avoids unnecessary overhead while maintaining type safety.

class PywellenBackend(WaveformBackend):
    """Backend implementation using pywellen library.
    
    This backend supports both VCD and FST file formats using the
    Rust-based wellen library through Python bindings.
    """
    
    def __init__(self, file_path: str):
        """Initialize the pywellen backend.
        
        Args:
            file_path: Path to the waveform file
        """
        super().__init__(file_path)
        self._backend_type = BackendType.PYWELLEN
        
    def load_waveform(
        self,
        multi_threaded: bool = True,
        remove_scopes_with_empty_name: bool = False,
        load_body: bool = True
    ) -> WWaveform:
        """Load the waveform file using pywellen.
        
        Args:
            multi_threaded: Whether to use multi-threading for signal loading
            remove_scopes_with_empty_name: Whether to filter out unnamed scopes
            load_body: Whether to immediately load the waveform body
            
        Returns:
            Loaded waveform object (pywellen.Waveform implements WWaveform protocol)
        """
        self._waveform = pywellen.Waveform(
            self.file_path,
            multi_threaded=multi_threaded,
            remove_scopes_with_empty_name=remove_scopes_with_empty_name,
            load_body=load_body
        )
        # pywellen.Waveform directly implements our WWaveform protocol
        return cast(WWaveform, self._waveform)
    
    def get_hierarchy(self) -> Optional[WHierarchy]:
        """Get the hierarchy from the loaded waveform.
        
        Returns:
            Hierarchy object (pywellen.Hierarchy implements WHierarchy protocol)
        """
        if self._waveform is None:
            return None
        # pywellen.Hierarchy directly implements our WHierarchy protocol
        return cast(WHierarchy, self._waveform.hierarchy)
    
    def get_time_table(self) -> Optional[WTimeTable]:
        """Get the time table from the loaded waveform.
        
        Returns:
            TimeTable object (pywellen.TimeTable implements WTimeTable protocol)
        """
        if self._waveform is None:
            return None
        # pywellen.TimeTable directly implements our WTimeTable protocol
        time_table = self._waveform.time_table
        return cast(WTimeTable, time_table) if time_table else None
    
    def get_signal(self, var: WVar) -> Optional[WSignal]:
        """Get signal data for a variable.
        
        Args:
            var: Variable to get signal for (must be a pywellen.Var)
            
        Returns:
            Signal object (pywellen.Signal implements WSignal protocol)
        """
        if self._waveform is None:
            return None
        try:
            # var should be a pywellen.Var object that implements WVar protocol
            signal = self._waveform.get_signal(var)  # type: ignore
            # pywellen.Signal directly implements our WSignal protocol
            return cast(WSignal, signal)
        except Exception:
            return None
    
    def load_signals(self, vars: List[WVar]) -> List[WSignal]:
        """Load multiple signals.
        
        Args:
            vars: List of variables to load signals for
            
        Returns:
            List of Signal objects (pywellen.Signal implements WSignal protocol)
        """
        if self._waveform is None:
            return []
        # vars should be pywellen.Var objects that implement WVar protocol
        signals = self._waveform.load_signals(vars)  # type: ignore
        # pywellen.Signal objects directly implement our WSignal protocol
        return [cast(WSignal, sig) for sig in signals]
    
    def load_signals_multithreaded(self, vars: List[WVar]) -> List[WSignal]:
        """Load multiple signals using multiple threads.
        
        Args:
            vars: List of variables to load signals for
            
        Returns:
            List of Signal objects (pywellen.Signal implements WSignal protocol)
        """
        if self._waveform is None:
            return []
        # vars should be pywellen.Var objects that implement WVar protocol  
        signals = self._waveform.load_signals_multithreaded(vars)  # type: ignore
        # pywellen.Signal objects directly implement our WSignal protocol
        return [cast(WSignal, sig) for sig in signals]
    
    def supports_file_format(self, file_path: str) -> bool:
        """Check if pywellen supports the given file format.
        
        Args:
            file_path: Path to the waveform file
            
        Returns:
            True for VCD and FST files, False otherwise
        """
        path = Path(file_path)
        ext = path.suffix.lower()
        return ext in ['.vcd', '.fst']


# Register the pywellen backend with the factory
BackendFactory.register_backend(BackendType.PYWELLEN, PywellenBackend)