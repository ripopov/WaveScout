"""WaveformDB implementation using Wellen library."""

from typing import List, Tuple, Optional, Dict
from .data_model import Time, SignalHandle, Timescale, TimeUnit

try:
    from pywellen import Waveform, Var, Hierarchy, Signal, TimeTable
except ImportError:
    raise ImportError(
        "Failed to import pywellen. Please build it first:\n"
        "poetry run build-pywellen"
    )


class WaveformDB:
    """Waveform database using Wellen library for reading VCD/FST files."""
    
    def __init__(self) -> None:
        self.waveform: Optional[Waveform] = None
        self.hierarchy: Optional[Hierarchy] = None
        self.uri: Optional[str] = None
        self._var_map: Dict[SignalHandle, List[Var]] = {}  # Map handles to list of variables (for aliases)
        self._signal_cache: Dict[SignalHandle, Signal] = {}  # Cache loaded signals
        self._timescale: Optional[Timescale] = None  # Store parsed timescale
        self._var_name_to_handle: Dict[str, SignalHandle] = {}  # Map var full name to handle
        self._signal_ref_to_handle: Dict[int, SignalHandle] = {}  # Map SignalRef to our handle (for O(1) alias detection)
        self._handle_to_signal_ref: Dict[SignalHandle, int] = {}  # Map our handle to SignalRef
        
    @property
    def file_path(self) -> Optional[str]:
        """Get the file path of the opened waveform."""
        return self.uri
        
    def open(self, uri: str) -> None:
        """Open a waveform file using Wellen."""
        import time
        import os
        
        start_time = time.time()
        self.uri = uri
        
        # Get file size for reporting
        file_size = os.path.getsize(uri)
        file_size_mb = file_size / (1024 * 1024)
        file_name = os.path.basename(uri)
        
        print(f"Loading {file_name} ({file_size_mb:.1f} MB)...")
        
        # Load waveform
        load_start = time.time()
        self.waveform = Waveform(path=uri)
        self.hierarchy = self.waveform.hierarchy
        load_end = time.time()
        
        print(f"  - Waveform loaded in {load_end - load_start:.2f} seconds")
        
        # Extract and store timescale
        self._extract_timescale()
        
        # Build variable mapping with lazy loading and alias detection
        mapping_start = time.time()
        handle = 0
        
        # Collect all variables to process
        all_variables = []
        seen_vars = set()
        
        # Recursively collect all variables from the hierarchy
        def collect_vars_recursive(scope: Hierarchy) -> None:
            # Add direct variables from this scope
            for var in scope.vars(self.hierarchy):
                var_id = id(var)
                if var_id not in seen_vars:
                    all_variables.append(var)
                    seen_vars.add(var_id)
            # Recurse into child scopes
            for child_scope in scope.scopes(self.hierarchy):
                collect_vars_recursive(child_scope)
        
        # Start from all top scopes
        for top_scope in self.hierarchy.top_scopes():
            collect_vars_recursive(top_scope)
        
        # Process variables with alias detection using signal_ref() for O(1) lookups
        for var in all_variables:
            signal_ref = var.signal_ref()
            
            # Check if we've already seen this signal_ref
            if signal_ref in self._signal_ref_to_handle:
                # This is an alias - add to the existing handle's list
                existing_handle = self._signal_ref_to_handle[signal_ref]
                self._var_map[existing_handle].append(var)
                
                # Map var name to handle for lookup
                var_full_name = var.full_name(self.hierarchy)
                self._var_name_to_handle[var_full_name] = existing_handle
            else:
                # New signal - create new handle
                self._var_map[handle] = [var]
                self._signal_ref_to_handle[signal_ref] = handle
                self._handle_to_signal_ref[handle] = signal_ref
                
                # Map var name to handle for lookup
                var_full_name = var.full_name(self.hierarchy)
                self._var_name_to_handle[var_full_name] = handle
                handle += 1
        
        mapping_end = time.time()
        total_time = time.time() - start_time
        
        print(f"  - Variable mapping built in {mapping_end - mapping_start:.2f} seconds")
        print(f"  - Total load time: {total_time:.2f} seconds")
        print(f"  - Number of unique signals: {len(self._var_map)}")
        print(f"  - Number of variables: {self.num_vars()}")
            
    def top_signals(self) -> List[SignalHandle]:
        """Get handles for top-level signals."""
        if not self.waveform or not self.hierarchy:
            return []
            
        handles = []
        # Get variables from all top scopes recursively
        def collect_vars_recursive(scope: Hierarchy) -> None:
            # Add direct variables
            for var in scope.vars(self.hierarchy):
                for handle, mapped_vars in self._var_map.items():
                    if var in mapped_vars:
                        handles.append(handle)
                        break
            # Recurse into child scopes
            for child_scope in scope.scopes(self.hierarchy):
                collect_vars_recursive(child_scope)
        
        for scope in self.hierarchy.top_scopes():
            collect_vars_recursive(scope)
            
        return handles[:10]  # Return first 10 for testing
        
    def transitions(self, handle: SignalHandle, t0: Time, t1: Time) -> List[Tuple[Time, str]]:
        """Get signal transitions in time range."""
        signal = self.get_signal(handle)
        if not signal:
            return []
        
        transitions = []
        for change_time, value in signal.all_changes():
            if t0 <= change_time <= t1:
                transitions.append((change_time, str(value)))
                
        return transitions
        
    def sample(self, handle: SignalHandle, t: Time) -> str:
        """Get signal value at specific time."""
        signal = self.get_signal(handle)
        if not signal:
            return ""
        
        # Use query_signal for efficient lookup
        query_result = signal.query_signal(max(0, t))
        if query_result.value is not None:
            return str(query_result.value)
        
        return ""
    
    def sample_with_next_change(self, handle: SignalHandle, t: Time) -> Tuple[str, Optional[Time]]:
        """Get signal value at specific time and the time of next change.
        
        Returns:
            Tuple of (value_string, next_change_time)
            next_change_time is None if there are no more changes
        """
        signal = self.get_signal(handle)
        if not signal:
            return ("", None)
        
        # Use query_signal for efficient lookup
        query_result = signal.query_signal(max(0, t))
        
        value_str = ""
        if query_result.value is not None:
            value_str = str(query_result.value)
        
        return (value_str, query_result.next_time)
        
    def close(self) -> None:
        """Close the waveform file."""
        self.waveform = None
        self.hierarchy = None
        self._var_map.clear()
        self._signal_cache.clear()
        self._timescale = None
        self._var_name_to_handle.clear()
        self._signal_ref_to_handle.clear()
        self._handle_to_signal_ref.clear()
        
    def _extract_timescale(self) -> None:
        """Extract timescale from the hierarchy."""
        if not self.hierarchy:
            return
            
        pywellen_timescale = self.hierarchy.timescale()
        if pywellen_timescale:
            # Import our TimeUnit and Timescale classes
            from .data_model import TimeUnit, Timescale
            
            # Convert pywellen unit string to our TimeUnit
            unit_str = str(pywellen_timescale.unit)
            time_unit = TimeUnit.from_string(unit_str)
            
            if time_unit:
                self._timescale = Timescale(
                    factor=pywellen_timescale.factor,
                    unit=time_unit
                )
    
    def get_timescale(self) -> Optional[Timescale]:
        """Get the timescale of the waveform file."""
        return self._timescale
    
    def get_metadata(self) -> Dict[str, Optional[object]]:
        """Get metadata about the waveform file."""
        if not self.hierarchy:
            return {}
            
        return {
            'date': self.hierarchy.date(),
            'version': self.hierarchy.version(),
            'file_format': self.hierarchy.file_format(),
            'timescale': self._timescale
        }
        
    def num_vars(self) -> int:
        """Get total number of unique variables (counting all aliases)."""
        total = 0
        for vars_list in self._var_map.values():
            total += len(vars_list)
        return total
        
    def get_var(self, handle: SignalHandle) -> Optional[Var]:
        """Get variable by handle. Returns pywellen Var object."""
        vars_list = self._var_map.get(handle, [])
        return vars_list[0] if vars_list else None
    
    def get_all_vars_for_handle(self, handle: SignalHandle) -> List[Var]:
        """Get all variables (including aliases) for a handle."""
        return self._var_map.get(handle, [])
    
    def get_time_table(self) -> Optional[TimeTable]:
        """Get the time table from the waveform. Returns pywellen TimeTable object."""
        if self.waveform:
            return self.waveform.time_table
        return None
    
    def get_signal(self, handle: SignalHandle) -> Optional[Signal]:
        """Get the signal object for the given handle. Returns pywellen Signal object.
        
        This method implements lazy loading - signals are only loaded when first requested.
        """
        if handle not in self._var_map:
            return None
            
        # Get the first variable for this handle (all aliases have same signal)
        vars_list = self._var_map[handle]
        if not vars_list:
            return None
        
        # Load signal lazily if not cached
        if handle not in self._signal_cache:
            if self.waveform is not None:
                var = vars_list[0]
                self._signal_cache[handle] = self.waveform.get_signal(var)
            
        return self._signal_cache.get(handle)
    
    def are_signals_cached(self, handles: List[SignalHandle]) -> bool:
        """Check if all specified signals are already cached.
        
        Args:
            handles: List of signal handles to check
            
        Returns:
            True if all signals are cached, False otherwise
        """
        return all(handle in self._signal_cache for handle in handles)
    
    def preload_signals(self, handles: List[SignalHandle]) -> None:
        """Preload multiple signals using efficient batch loading.
        
        This method uses pywellen's load_signals_multithreaded for optimal performance.
        Should be called from a background thread to avoid blocking the UI.
        
        Args:
            handles: List of signal handles to preload
        """
        if not self.waveform:
            return
            
        # Filter out already cached signals and invalid handles
        handles_to_load = [
            h for h in handles 
            if h not in self._signal_cache and h in self._var_map
        ]
        
        if not handles_to_load:
            return  # All signals already cached
            
        # Convert handles to Var objects
        vars_to_load = []
        handle_to_var_map = {}
        for handle in handles_to_load:
            vars_list = self._var_map.get(handle, [])
            if vars_list:
                var = vars_list[0]  # Use first var for each handle
                vars_to_load.append(var)
                handle_to_var_map[id(var)] = handle
        
        if not vars_to_load:
            return
            
        # Batch load signals using multithreaded API
        try:
            loaded_signals = self.waveform.load_signals_multithreaded(vars_to_load)
            
            # Cache the loaded signals
            for var, signal in zip(vars_to_load, loaded_signals):
                handle_or_none = handle_to_var_map.get(id(var))
                if handle_or_none is not None and signal is not None:
                    self._signal_cache[handle_or_none] = signal
                    
        except Exception as e:
            # Re-raise the exception to be handled by the caller
            raise RuntimeError(f"Failed to load signals: {str(e)}")
    
    # Public APIs for accessing protected members
    
    def get_all_handles(self) -> List[SignalHandle]:
        """Get all handle IDs in the database."""
        return list(self._var_map.keys())
    
    def get_handle_for_var(self, var: Var) -> Optional[SignalHandle]:
        """Get handle for a specific variable object.
        
        Args:
            var: Pywellen variable object
            
        Returns:
            Handle ID if found, None otherwise
        """
        # Get the full name of the var and look it up
        var_full_name = var.full_name(self.hierarchy)
        return self._var_name_to_handle.get(var_full_name)
    
    def find_handle_by_name(self, name: str) -> Optional[SignalHandle]:
        """Find handle by variable name.
        
        Args:
            name: Variable name to search for (full hierarchical name)
            
        Returns:
            Handle ID if found, None otherwise
        """
        return self._var_name_to_handle.get(name)
    
    def get_var_to_handle_mapping(self) -> Dict[Var, int]:
        """Get complete variable-to-handle mapping.
        
        Returns:
            Dictionary mapping pywellen variable objects to handle IDs
        """
        var_to_handle = {}
        for handle, vars_list in self._var_map.items():
            for var in vars_list:
                var_to_handle[var] = handle
        return var_to_handle
    
    def get_next_available_handle(self) -> int:
        """Get the next available handle ID."""
        return len(self._var_map) if self._var_map else 0
    
    def clear_signal_cache(self) -> None:
        """Clear the signal cache. Primarily for testing."""
        self._signal_cache.clear()
    
    def is_signal_cached(self, handle: SignalHandle) -> bool:
        """Check if signal is cached for the given handle.
        
        Used in tests to verify caching behavior.
        
        Args:
            handle: Handle ID to check
            
        Returns:
            True if signal is cached, False otherwise
        """
        return handle in self._signal_cache
    
    def iter_handles_and_vars(self) -> List[Tuple[int, List[Var]]]:
        """Iterate over all handles and their associated variables.
        
        Returns:
            List of tuples (handle, vars_list)
        """
        return list(self._var_map.items())
    
    def find_handle_by_path(self, path: str) -> Optional[SignalHandle]:
        """Find handle by hierarchical path.
        
        First tries to find by exact name. If not found and path doesn't
        contain a dot, tries with 'TOP.' prefix.
        
        Args:
            path: Signal path (e.g., "signal" or "TOP.module.signal")
            
        Returns:
            Handle ID if found, None otherwise
        """
        # First try exact match
        handle = self.find_handle_by_name(path)
        if handle is not None:
            return handle
        
        # If not found and no dot in path, try with TOP prefix
        if '.' not in path:
            return self.find_handle_by_name(f"TOP.{path}")
        
        return None
    
    def get_var_bitwidth(self, handle: SignalHandle) -> int:
        """Get bit width for a signal.
        
        Args:
            handle: Signal handle
            
        Returns:
            Bit width of the signal (defaults to 32 if unknown)
        """
        vars_list = self.get_all_vars_for_handle(handle)
        if vars_list:
            width = vars_list[0].bitwidth()
            if width is not None:
                return int(width)
        return 32  # Default bit width