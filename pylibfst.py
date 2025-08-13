"""Python wrapper for libfst C library using ctypes."""

import ctypes
import os
import platform
from pathlib import Path
from typing import Optional, List, Tuple, Callable, Any
from dataclasses import dataclass
from enum import IntEnum


class FstScopeType(IntEnum):
    """FST scope types."""
    VCD_MODULE = 0
    VCD_TASK = 1
    VCD_FUNCTION = 2
    VCD_BEGIN = 3
    VCD_FORK = 4
    VCD_GENERATE = 5
    VCD_STRUCT = 6
    VCD_UNION = 7
    VCD_CLASS = 8
    VCD_INTERFACE = 9
    VCD_PACKAGE = 10
    VCD_PROGRAM = 11
    VHDL_ARCHITECTURE = 12
    VHDL_PROCEDURE = 13
    VHDL_FUNCTION = 14
    VHDL_RECORD = 15
    VHDL_PROCESS = 16
    VHDL_BLOCK = 17
    VHDL_FOR_GENERATE = 18
    VHDL_IF_GENERATE = 19
    VHDL_GENERATE = 20
    VHDL_PACKAGE = 21


class FstVarType(IntEnum):
    """FST variable types."""
    VCD_EVENT = 0
    VCD_INTEGER = 1
    VCD_PARAMETER = 2
    VCD_REAL = 3
    VCD_REAL_PARAMETER = 4
    VCD_REG = 5
    VCD_SUPPLY0 = 6
    VCD_SUPPLY1 = 7
    VCD_TIME = 8
    VCD_TRI = 9
    VCD_TRIAND = 10
    VCD_TRIOR = 11
    VCD_TRIREG = 12
    VCD_TRI0 = 13
    VCD_TRI1 = 14
    VCD_WAND = 15
    VCD_WIRE = 16
    VCD_WOR = 17
    VCD_PORT = 18
    VCD_SPARRAY = 19
    VCD_REALTIME = 20
    GEN_STRING = 21
    SV_BIT = 22
    SV_LOGIC = 23
    SV_INT = 24
    SV_SHORTINT = 25
    SV_LONGINT = 26
    SV_BYTE = 27
    SV_ENUM = 28
    SV_SHORTREAL = 29


class FstVarDir(IntEnum):
    """FST variable direction."""
    IMPLICIT = 0
    INPUT = 1
    OUTPUT = 2
    INOUT = 3
    BUFFER = 4
    LINKAGE = 5


class FstHierType(IntEnum):
    """FST hierarchy types."""
    SCOPE = 0
    UPSCOPE = 1
    VAR = 2
    ATTRBEGIN = 3
    ATTREND = 4
    TREEBEGIN = 5
    TREEEND = 6


class FstHierScope(ctypes.Structure):
    """FST hierarchy scope structure."""
    _fields_ = [
        ("typ", ctypes.c_ubyte),
        ("name", ctypes.c_char_p),
        ("component", ctypes.c_char_p),
        ("name_length", ctypes.c_uint32),
        ("component_length", ctypes.c_uint32),
    ]


class FstHierVar(ctypes.Structure):
    """FST hierarchy variable structure."""
    _fields_ = [
        ("typ", ctypes.c_ubyte),
        ("direction", ctypes.c_ubyte),
        ("svt_workspace", ctypes.c_ubyte),
        ("sdt_workspace", ctypes.c_ubyte),
        ("sxt_workspace", ctypes.c_uint),
        ("name", ctypes.c_char_p),
        ("length", ctypes.c_uint32),
        ("handle", ctypes.c_uint32),
        ("name_length", ctypes.c_uint32),
        ("is_alias", ctypes.c_uint, 1),
    ]


class FstHierAttr(ctypes.Structure):
    """FST hierarchy attribute structure."""
    _fields_ = [
        ("typ", ctypes.c_ubyte),
        ("subtype", ctypes.c_ubyte),
        ("name", ctypes.c_char_p),
        ("arg", ctypes.c_uint64),
        ("arg_from_name", ctypes.c_uint64),
        ("name_length", ctypes.c_uint32),
    ]


class FstHierUnion(ctypes.Union):
    """FST hierarchy union."""
    _fields_ = [
        ("scope", FstHierScope),
        ("var", FstHierVar),
        ("attr", FstHierAttr),
    ]


class FstHier(ctypes.Structure):
    """FST hierarchy structure."""
    _fields_ = [
        ("htyp", ctypes.c_ubyte),
        ("u", FstHierUnion),
    ]


@dataclass
class HierNode:
    """Python representation of hierarchy node."""
    type: FstHierType
    name: str
    full_path: str
    
    # For scopes
    scope_type: Optional[FstScopeType] = None
    component: Optional[str] = None
    
    # For variables
    var_type: Optional[FstVarType] = None
    var_dir: Optional[FstVarDir] = None
    length: Optional[int] = None
    handle: Optional[int] = None
    is_alias: bool = False


@dataclass
class SignalValue:
    """Signal value at a specific time."""
    time: int
    value: str


class PyLibFst:
    """Python wrapper for libfst library."""
    
    def __init__(self):
        """Initialize the FST library wrapper."""
        self._lib: Optional[ctypes.CDLL] = None
        self._ctx: Optional[ctypes.c_void_p] = None
        self._load_library()
        self._setup_functions()
        
    def _load_library(self) -> None:
        """Load the compiled FST library."""
        system = platform.system()
        lib_dir = Path(__file__).parent / "libfst" / "build"
        
        if system == "Windows":
            lib_name = "fstapi.dll"
        elif system == "Darwin":
            lib_name = "libfstapi.dylib"
        else:  # Linux
            lib_name = "libfstapi.so"
        
        lib_path = lib_dir / lib_name
        if not lib_path.exists():
            # Try without build directory for system-installed library
            lib_path = Path(__file__).parent / "libfst" / lib_name
            
        if not lib_path.exists():
            raise FileNotFoundError(
                f"FST library not found at {lib_path}. "
                "Please build libfst first using 'make build-libfst'"
            )
        
        self._lib = ctypes.CDLL(str(lib_path))
        
    def _setup_functions(self) -> None:
        """Setup function signatures for FST API."""
        if not self._lib:
            return
            
        # Reader functions
        self._lib.fstReaderOpen.argtypes = [ctypes.c_char_p]
        self._lib.fstReaderOpen.restype = ctypes.c_void_p
        
        self._lib.fstReaderClose.argtypes = [ctypes.c_void_p]
        self._lib.fstReaderClose.restype = None
        
        self._lib.fstReaderIterateHier.argtypes = [ctypes.c_void_p]
        self._lib.fstReaderIterateHier.restype = ctypes.POINTER(FstHier)
        
        self._lib.fstReaderIterateHierRewind.argtypes = [ctypes.c_void_p]
        self._lib.fstReaderIterateHierRewind.restype = ctypes.c_int
        
        self._lib.fstReaderGetStartTime.argtypes = [ctypes.c_void_p]
        self._lib.fstReaderGetStartTime.restype = ctypes.c_uint64
        
        self._lib.fstReaderGetEndTime.argtypes = [ctypes.c_void_p]
        self._lib.fstReaderGetEndTime.restype = ctypes.c_uint64
        
        self._lib.fstReaderGetTimescale.argtypes = [ctypes.c_void_p]
        self._lib.fstReaderGetTimescale.restype = ctypes.c_byte
        
        self._lib.fstReaderGetVarCount.argtypes = [ctypes.c_void_p]
        self._lib.fstReaderGetVarCount.restype = ctypes.c_uint64
        
        self._lib.fstReaderGetScopeCount.argtypes = [ctypes.c_void_p]
        self._lib.fstReaderGetScopeCount.restype = ctypes.c_uint64
        
        self._lib.fstReaderGetMaxHandle.argtypes = [ctypes.c_void_p]
        self._lib.fstReaderGetMaxHandle.restype = ctypes.c_uint32
        
        self._lib.fstReaderSetFacProcessMask.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        self._lib.fstReaderSetFacProcessMask.restype = None
        
        self._lib.fstReaderClrFacProcessMaskAll.argtypes = [ctypes.c_void_p]
        self._lib.fstReaderClrFacProcessMaskAll.restype = None
        
        self._lib.fstReaderGetValueFromHandleAtTime.argtypes = [
            ctypes.c_void_p, ctypes.c_uint64, ctypes.c_uint32, ctypes.c_char_p
        ]
        self._lib.fstReaderGetValueFromHandleAtTime.restype = ctypes.c_char_p
        
        # Define callback type for value changes
        self._value_change_callback_type = ctypes.CFUNCTYPE(
            None, ctypes.c_void_p, ctypes.c_uint64, ctypes.c_uint32, ctypes.POINTER(ctypes.c_ubyte)
        )
        
        self._lib.fstReaderIterBlocks.argtypes = [
            ctypes.c_void_p,
            self._value_change_callback_type,
            ctypes.c_void_p,
            ctypes.c_void_p
        ]
        self._lib.fstReaderIterBlocks.restype = ctypes.c_int
        
    def open(self, filename: str) -> bool:
        """Open an FST file for reading.
        
        Args:
            filename: Path to the FST file
            
        Returns:
            True if file was opened successfully
        """
        if self._ctx:
            self.close()
            
        if not self._lib:
            return False
            
        self._ctx = self._lib.fstReaderOpen(filename.encode('utf-8'))
        return self._ctx is not None
        
    def close(self) -> None:
        """Close the currently open FST file."""
        if self._ctx and self._lib:
            self._lib.fstReaderClose(self._ctx)
            self._ctx = None
            
    def get_hierarchy(self) -> List[HierNode]:
        """Get the complete hierarchy from the FST file.
        
        Returns:
            List of hierarchy nodes
        """
        if not self._ctx or not self._lib:
            return []
            
        nodes: List[HierNode] = []
        scope_stack: List[str] = []
        
        # Rewind hierarchy iterator
        self._lib.fstReaderIterateHierRewind(self._ctx)
        
        while True:
            hier_ptr = self._lib.fstReaderIterateHier(self._ctx)
            if not hier_ptr:
                break
                
            hier = hier_ptr.contents
            htyp = FstHierType(hier.htyp)
            
            if htyp == FstHierType.SCOPE:
                scope = hier.u.scope
                name = scope.name.decode('utf-8') if scope.name else ""
                component = scope.component.decode('utf-8') if scope.component else None
                scope_stack.append(name)
                full_path = ".".join(scope_stack)
                
                node = HierNode(
                    type=htyp,
                    name=name,
                    full_path=full_path,
                    scope_type=FstScopeType(scope.typ),
                    component=component
                )
                nodes.append(node)
                
            elif htyp == FstHierType.UPSCOPE:
                if scope_stack:
                    scope_stack.pop()
                    
            elif htyp == FstHierType.VAR:
                var = hier.u.var
                raw_name = var.name.decode('utf-8') if var.name else ""
                
                # Strip bit range from name if present (e.g., "signal [1:64]" -> "signal")
                # This matches how WaveformDB handles names
                import re
                match = re.match(r'^(.*?)\s*\[\d+:\d+\]$', raw_name)
                if match:
                    name = match.group(1)
                else:
                    name = raw_name
                
                full_path = ".".join(scope_stack + [name]) if scope_stack else name
                
                node = HierNode(
                    type=htyp,
                    name=name,
                    full_path=full_path,
                    var_type=FstVarType(var.typ),
                    var_dir=FstVarDir(var.direction),
                    length=var.length,
                    handle=var.handle,
                    is_alias=bool(var.is_alias)
                )
                nodes.append(node)
                
        return nodes
        
    def get_signal_values(self, handle: int, start_time: Optional[int] = None, 
                         end_time: Optional[int] = None) -> List[SignalValue]:
        """Get all value changes for a signal.
        
        Args:
            handle: Signal handle
            start_time: Optional start time
            end_time: Optional end time
            
        Returns:
            List of signal values with timestamps
        """
        if not self._ctx or not self._lib:
            return []
            
        values: List[SignalValue] = []
        
        # Storage for callback
        class CallbackData(ctypes.Structure):
            _fields_ = [("values", ctypes.py_object)]
            
        cb_data = CallbackData()
        cb_data.values = values
        
        # Clear all masks first
        self._lib.fstReaderClrFacProcessMaskAll(self._ctx)
        
        # Set mask for specific handle
        self._lib.fstReaderSetFacProcessMask(self._ctx, handle)
        
        # Define callback function
        def value_callback(user_data: ctypes.c_void_p, time: int, 
                          facidx: int, value_ptr: ctypes.POINTER(ctypes.c_ubyte)) -> None:
            if facidx == handle:
                # Convert value bytes to string
                value_bytes = []
                i = 0
                while value_ptr[i] != 0:
                    value_bytes.append(value_ptr[i])
                    i += 1
                value_str = bytes(value_bytes).decode('ascii', errors='ignore')
                
                cb_values = ctypes.cast(user_data, ctypes.POINTER(CallbackData)).contents.values
                cb_values.append(SignalValue(time=time, value=value_str))
        
        # Create callback
        cb_func = self._value_change_callback_type(value_callback)
        
        # Iterate through blocks
        self._lib.fstReaderIterBlocks(
            self._ctx, 
            cb_func,
            ctypes.cast(ctypes.pointer(cb_data), ctypes.c_void_p),
            None  # No VCD file handle
        )
        
        # Filter by time range if specified
        if start_time is not None or end_time is not None:
            filtered = []
            for sv in values:
                if start_time is not None and sv.time < start_time:
                    continue
                if end_time is not None and sv.time > end_time:
                    continue
                filtered.append(sv)
            values = filtered
            
        return values
        
    def get_time_range(self) -> Tuple[int, int]:
        """Get the time range of the FST file.
        
        Returns:
            Tuple of (start_time, end_time)
        """
        if not self._ctx or not self._lib:
            return (0, 0)
            
        start = self._lib.fstReaderGetStartTime(self._ctx)
        end = self._lib.fstReaderGetEndTime(self._ctx)
        return (start, end)
        
    def get_timescale(self) -> int:
        """Get the timescale exponent.
        
        Returns:
            Timescale exponent (e.g., -9 for nanoseconds)
        """
        if not self._ctx or not self._lib:
            return 0
            
        return self._lib.fstReaderGetTimescale(self._ctx)
        
    def get_var_count(self) -> int:
        """Get the number of variables in the FST file.
        
        Returns:
            Number of variables
        """
        if not self._ctx or not self._lib:
            return 0
            
        return self._lib.fstReaderGetVarCount(self._ctx)
        
    def get_scope_count(self) -> int:
        """Get the number of scopes in the FST file.
        
        Returns:
            Number of scopes
        """
        if not self._ctx or not self._lib:
            return 0
            
        return self._lib.fstReaderGetScopeCount(self._ctx)