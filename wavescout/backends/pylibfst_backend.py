"""Pylibfst backend implementation with adapters for protocol types."""

from typing import Optional, List, Tuple, cast
from pathlib import Path

try:
    import pylibfst
except ImportError:
    raise ImportError("pylibfst is required for the pylibfst backend. Install it with: poetry run build-pylibfst")

from .base import WaveformBackend, BackendType, BackendFactory
from ..backend_types import (
    WWaveform, WHierarchy, WSignal, WVar, WTimeTable, WTimescale,
    WScope, WScopeIter, WVarIter, WVarIndex, WSignalChangeIter, WQueryResult
)


class TimeTableAdapter:
    """Adapter to make pylibfst's time_range compatible with WTimeTable protocol.
    
    Since pylibfst doesn't provide a full time table (only start/end times),
    this adapter provides a minimal implementation that satisfies the protocol.
    """
    
    def __init__(self, time_range: Optional[Tuple[int, int]]):
        """Initialize with time range from pylibfst.
        
        Args:
            time_range: Tuple of (start_time, end_time) or None
        """
        self.time_range = time_range
        
    def __getitem__(self, idx: int) -> int:
        """Get time value at index.
        
        For pylibfst, we only have start (idx=0) and end (idx=1) times.
        Supports negative indexing (-1 for last element, -2 for first).
        """
        if self.time_range is None:
            raise IndexError("No time range available")
        
        # Handle negative indices
        if idx < 0:
            idx = 2 + idx  # Convert negative index to positive
        
        if idx == 0:
            return self.time_range[0]
        elif idx == 1:
            return self.time_range[1]
        else:
            raise IndexError(f"Time table index {idx} out of range (valid indices: 0, 1, -1, -2)")
    
    def __len__(self) -> int:
        """Get number of time points.
        
        For pylibfst, we only have 2 points: start and end.
        """
        return 2 if self.time_range else 0


class WaveformAdapter:
    """Adapter to make pylibfst.Waveform compatible with WWaveform protocol.
    
    This adapter handles the difference between pylibfst's time_range
    and the expected time_table attribute.
    """
    
    def __init__(self, waveform: 'pylibfst.Waveform'):
        """Initialize with a pylibfst Waveform.
        
        Args:
            waveform: The pylibfst Waveform object to wrap
        """
        self._waveform = waveform
        self.hierarchy = cast(WHierarchy, waveform.hierarchy)
        # Adapt time_range to time_table
        time_range = getattr(waveform, 'time_range', None)
        self.time_table = TimeTableAdapter(time_range) if time_range else None
    
    def load_body(self) -> None:
        """Load the waveform body if not already loaded."""
        self._waveform.load_body()
    
    def body_loaded(self) -> bool:
        """Check if waveform body is loaded."""
        return self._waveform.body_loaded()
    
    def get_signal(self, var: WVar) -> WSignal:
        """Get signal data for a variable."""
        signal = self._waveform.get_signal(var)  # type: ignore
        return cast(WSignal, signal)
    
    def get_signal_from_path(self, abs_hierarchy_path: str) -> WSignal:
        """Get signal data by hierarchical path."""
        signal = self._waveform.get_signal_from_path(abs_hierarchy_path)
        return cast(WSignal, signal)
    
    def load_signals(self, vars: List[WVar]) -> List[WSignal]:
        """Load multiple signals."""
        signals = self._waveform.load_signals(vars)  # type: ignore
        return [cast(WSignal, sig) for sig in signals]
    
    def load_signals_multithreaded(self, vars: List[WVar]) -> List[WSignal]:
        """Load multiple signals using multiple threads."""
        signals = self._waveform.load_signals_multithreaded(vars)  # type: ignore
        return [cast(WSignal, sig) for sig in signals]
    
    def unload_signals(self, signals: List[WSignal]) -> None:
        """Unload signals to free memory."""
        self._waveform.unload_signals(signals)  # type: ignore


class PylibfstBackend(WaveformBackend):
    """Backend implementation using pylibfst library.
    
    This backend supports only FST file format using a C-based
    libfst library through Python bindings.
    """
    
    def __init__(self, file_path: str):
        """Initialize the pylibfst backend.
        
        Args:
            file_path: Path to the waveform file
        """
        super().__init__(file_path)
        self._backend_type = BackendType.PYLIBFST
        self._adapted_waveform: Optional[WaveformAdapter] = None
        
    def load_waveform(
        self,
        multi_threaded: bool = True,
        remove_scopes_with_empty_name: bool = False,
        load_body: bool = True
    ) -> WWaveform:
        """Load the waveform file using pylibfst.
        
        Args:
            multi_threaded: Whether to use multi-threading for signal loading
            remove_scopes_with_empty_name: Whether to filter out unnamed scopes
            load_body: Whether to immediately load the waveform body
            
        Returns:
            Loaded waveform object wrapped in adapter
        """
        # Load using pylibfst
        pylibfst_waveform = pylibfst.Waveform(
            self.file_path,
            multi_threaded=multi_threaded,
            remove_scopes_with_empty_name=remove_scopes_with_empty_name,
            load_body=load_body
        )
        
        # Wrap in adapter to handle time_range vs time_table difference
        self._adapted_waveform = WaveformAdapter(pylibfst_waveform)
        self._waveform = cast(WWaveform, self._adapted_waveform)
        return self._waveform
    
    def get_hierarchy(self) -> Optional[WHierarchy]:
        """Get the hierarchy from the loaded waveform.
        
        Returns:
            Hierarchy object (pylibfst.Hierarchy implements WHierarchy protocol)
        """
        if self._adapted_waveform is None:
            return None
        # pylibfst.Hierarchy directly implements our WHierarchy protocol
        return self._adapted_waveform.hierarchy
    
    def get_time_table(self) -> Optional[WTimeTable]:
        """Get the time table from the loaded waveform.
        
        Returns:
            TimeTable adapter object that implements WTimeTable protocol
        """
        if self._adapted_waveform is None:
            return None
        # Return our TimeTableAdapter that wraps pylibfst's time_range
        return cast(WTimeTable, self._adapted_waveform.time_table)
    
    def get_signal(self, var: WVar) -> Optional[WSignal]:
        """Get signal data for a variable.
        
        Args:
            var: Variable to get signal for (must be a pylibfst.Var)
            
        Returns:
            Signal object (pylibfst.Signal implements WSignal protocol)
        """
        if self._adapted_waveform is None:
            return None
        try:
            # var should be a pylibfst.Var object that implements WVar protocol
            signal = self._adapted_waveform.get_signal(var)
            return signal
        except Exception:
            return None
    
    def load_signals(self, vars: List[WVar]) -> List[WSignal]:
        """Load multiple signals.
        
        Args:
            vars: List of variables to load signals for
            
        Returns:
            List of Signal objects (pylibfst.Signal implements WSignal protocol)
        """
        if self._adapted_waveform is None:
            return []
        return self._adapted_waveform.load_signals(vars)
    
    def load_signals_multithreaded(self, vars: List[WVar]) -> List[WSignal]:
        """Load multiple signals using multiple threads.
        
        Args:
            vars: List of variables to load signals for
            
        Returns:
            List of Signal objects (pylibfst.Signal implements WSignal protocol)
        """
        if self._adapted_waveform is None:
            return []
        return self._adapted_waveform.load_signals_multithreaded(vars)
    
    def supports_file_format(self, file_path: str) -> bool:
        """Check if pylibfst supports the given file format.
        
        Args:
            file_path: Path to the waveform file
            
        Returns:
            True for FST files only, False otherwise
        """
        path = Path(file_path)
        ext = path.suffix.lower()
        # pylibfst only supports FST files
        return ext == '.fst'


# Register the pylibfst backend with the factory
BackendFactory.register_backend(BackendType.PYLIBFST, PylibfstBackend)