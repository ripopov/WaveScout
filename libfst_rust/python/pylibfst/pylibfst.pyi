"""Type stubs for pylibfst - FST waveform reader with pywellen-compatible API"""

from typing import Optional, Tuple, Union, List, Literal, Iterator

class VarIndex:
    """Represents bit range indices for a variable"""
    def msb(self) -> int: ...
    def lsb(self) -> int: ...

class Hierarchy:
    """Represents the design hierarchy from an FST file"""
    def all_vars(self) -> VarIter: ...
    def top_scopes(self) -> ScopeIter: ...
    def date(self) -> str: ...
    def version(self) -> str: ...
    def timescale(self) -> Optional[Timescale]: ...
    def file_format(self) -> Literal["FST", "VCD", "GHW", "Unknown"]: ...

class Scope:
    """Represents a scope (module, task, function, etc.) in the hierarchy"""
    def name(self, hier: Hierarchy) -> str: ...
    def full_name(self, hier: Hierarchy) -> str: ...
    def scope_type(self) -> Literal[
        "module", "task", "function", "begin", "fork", "generate", "struct", "union", 
        "class", "interface", "package", "program", "vhdl_architecture", "vhdl_procedure", 
        "vhdl_function", "vhdl_record", "vhdl_process", "vhdl_block", "vhdl_for_generate", 
        "vhdl_if_generate", "vhdl_generate", "vhdl_package", "ghw_generic", "vhdl_array", 
        "unknown"
    ]: ...
    def vars(self, hier: Hierarchy) -> VarIter: ...
    def scopes(self, hier: Hierarchy) -> ScopeIter: ...

class ScopeIter:
    """Iterator over Scope objects"""
    def __iter__(self) -> ScopeIter: ...
    def __next__(self) -> Scope: ...

class Var:
    """Represents a variable/signal in the hierarchy"""
    def name(self, hier: Hierarchy) -> str: ...
    def full_name(self, hier: Hierarchy) -> str: ...
    def bitwidth(self) -> Optional[int]: ...
    def var_type(self) -> Literal[
        "Event", "Integer", "Parameter", "Real", "Reg", "Supply0", "Supply1", "Time", 
        "Tri", "TriAnd", "TriOr", "TriReg", "Tri0", "Tri1", "WAnd", "Wire", "WOr", 
        "String", "Port", "SparseArray", "RealTime", "Bit", "Logic", "Int", "ShortInt", 
        "LongInt", "Byte", "Enum", "ShortReal", "Boolean", "BitVector", "StdLogic", 
        "StdLogicVector", "StdULogic", "StdULogicVector"
    ]: ...
    def enum_type(self, hier: Hierarchy) -> Optional[Tuple[str, List[Tuple[str, str]]]]: ...
    def vhdl_type_name(self, hier: Hierarchy) -> Optional[str]: ...
    def direction(self) -> Literal["Unknown", "Implicit", "Input", "Output", "InOut", "Buffer", "Linkage"]: ...
    def length(self) -> Optional[int]: ...
    def is_real(self) -> bool: ...
    def is_string(self) -> bool: ...
    def is_bit_vector(self) -> bool: ...
    def is_1bit(self) -> bool: ...
    def index(self) -> Optional[VarIndex]: ...
    def signal_ref(self) -> int: ...

class VarIter:
    """Iterator over Var objects"""
    def __iter__(self) -> VarIter: ...
    def __next__(self) -> Var: ...

class TimeTable:
    """Time table for compressed time representation"""
    def __getitem__(self, idx: int) -> int: ...
    def __len__(self) -> int: ...

class Waveform:
    """Main waveform reader for FST files"""
    hierarchy: Hierarchy
    time_range: Optional[Tuple[int, int]]  # (start_time, end_time) - FST time boundaries

    def __init__(
        self,
        path: str,
        multi_threaded: bool = True,
        remove_scopes_with_empty_name: bool = False,
        load_body: bool = True,
    ) -> None: 
        """
        Create a new Waveform reader for an FST file.
        
        Args:
            path: Path to the FST file
            multi_threaded: Whether to use multi-threading for signal loading
            remove_scopes_with_empty_name: Whether to filter out unnamed scopes
            load_body: Whether to immediately load the waveform body (time range and signals)
        
        Note:
            libfst doesn't support efficient full time table access. This implementation
            provides time_range (start, end) and a compatibility time_table with just those values.
        """
        ...
    
    def load_body(self) -> None: 
        """Load the waveform body if it wasn't loaded during initialization"""
        ...
    
    def body_loaded(self) -> bool: 
        """Check if the waveform body has been loaded"""
        ...
    
    def get_signal(self, var: Var) -> Signal: 
        """
        Load and return the signal data for a variable.
        
        Args:
            var: The variable to get signal data for
            
        Returns:
            Signal object containing all transitions
        """
        ...
    
    def get_signal_from_path(self, abs_hierarchy_path: str) -> Signal: 
        """
        Load and return signal data by absolute hierarchy path.
        
        Args:
            abs_hierarchy_path: Full path to the signal (e.g., "top.module.signal")
            
        Returns:
            Signal object containing all transitions
        """
        ...
    
    def load_signals(self, vars: List[Var]) -> List[Signal]: 
        """
        Load multiple signals at once.
        
        Args:
            vars: List of variables to load signals for
            
        Returns:
            List of Signal objects in the same order as input
        """
        ...
    
    def load_signals_multithreaded(self, vars: List[Var]) -> List[Signal]: 
        """
        Load multiple signals using multi-threading.
        
        Args:
            vars: List of variables to load signals for
            
        Returns:
            List of Signal objects in the same order as input
        """
        ...
    
    def unload_signals(self, signals: List[Signal]) -> None: 
        """
        Unload signals from cache to free memory.
        
        Args:
            signals: List of signals to unload
        """
        ...

class Signal:
    """Represents signal data with all value transitions"""
    
    def value_at_time(self, time: int) -> Union[int, str, float, None]: 
        """
        Get signal value at a specific time.
        
        Args:
            time: Simulation time to query
            
        Returns:
            Signal value at the given time, or None if before first transition
        """
        ...
    
    def value_at_idx(self, idx: int) -> Union[int, str, float, None]: 
        """
        Get signal value at a specific transition index.
        
        Args:
            idx: Index of the transition
            
        Returns:
            Signal value at the given index, or None if index out of range
        """
        ...
    
    def all_changes(self) -> SignalChangeIter: 
        """
        Get iterator over all signal transitions.
        
        Returns:
            Iterator yielding (time, value) tuples
        """
        ...
    
    def all_changes_after(self, start_time: int) -> SignalChangeIter: 
        """
        Get iterator over signal transitions after a specific time.
        
        Args:
            start_time: Time to start iteration from
            
        Returns:
            Iterator yielding (time, value) tuples
        """
        ...
    
    def query_signal(self, query_time: int) -> QueryResult: 
        """
        Query signal state at a specific time with additional info.
        
        Args:
            query_time: Time to query
            
        Returns:
            QueryResult with value, actual time, and next transition info
        """
        ...

class SignalChangeIter:
    """Iterator over signal changes (time, value) pairs"""
    def __iter__(self) -> SignalChangeIter: ...
    def __len__(self) -> int: ...
    def __next__(self) -> Tuple[int, Union[int, str, float]]: ...

class QueryResult:
    """Result of a signal query operation"""
    value: Optional[Union[int, str, float]]
    actual_time: Optional[int]
    next_idx: Optional[int]
    next_time: Optional[int]

class TimescaleUnit:
    """Represents timescale units (ps, ns, us, ms, s, etc.)"""
    def __str__(self) -> Literal["zs", "as", "fs", "ps", "ns", "us", "ms", "s", "unknown"]: ...
    def __repr__(self) -> str: ...
    def to_exponent(self) -> Optional[int]: ...

class Timescale:
    """Represents timescale with factor and unit"""
    factor: int
    unit: TimescaleUnit
    def __str__(self) -> str: ...
    def __repr__(self) -> str: ...