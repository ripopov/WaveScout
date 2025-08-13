# Feature Plan: LibFST API Compatible with PyWellen

## Requirements

Create libfst Python interface matching pywellen API exactly, allowing interchangeable use for FST file reading.

### Scope
- Implement C++20 wrapper around libfst with extern "C" API
- Python bindings via ctypes matching pywellen.pyi interface
- Support all pywellen classes: Waveform, Hierarchy, Scope, Var, Signal, TimeTable, Timescale
- Lazy signal loading
- Memory-efficient handling of large FST files

## API Analysis

### PyWellen Interface (from pywellen.pyi)

**Core Classes:**
- `Waveform(path, multi_threaded=True, load_body=True)` - Main entry point
- `Hierarchy` - File metadata and scope/variable iteration
- `Scope` - Design hierarchy nodes
- `Var` - Signal definitions with type, width, direction
- `Signal` - Waveform data with value queries
- `TimeTable` - Timestamp array
- `Timescale` - Time unit and factor

**Key Methods to Implement:**
- `Waveform.get_signal(var) -> Signal`
- `Hierarchy.all_vars() -> VarIter`
- `Hierarchy.top_scopes() -> ScopeIter`
- `Signal.value_at_time(time) -> value`
- `Signal.all_changes() -> SignalChangeIter`
- `Var.signal_ref() -> int` (for alias detection)

## Implementation Design

### File Structure
```
libfst/
├── pylibfst.cpp          # C++20 implementation
├── pylibfst.h           # extern "C" API
├── pylibfst_internal.hpp # Internal C++ classes
└── CMakeLists.txt       # Build configuration
```

### C++ Internal Structure (pylibfst_internal.hpp)

```cpp
namespace pylibfst {

class Waveform {
    std::unique_ptr<void, decltype(&fstReaderClose)> reader_;
    std::shared_ptr<Hierarchy> hierarchy_;
    std::shared_ptr<TimeTable> time_table_;
    std::unordered_map<fstHandle, std::shared_ptr<Signal>> signal_cache_;
};

class Hierarchy {
    std::vector<Scope> scopes_;
    std::vector<Var> vars_;
    std::unordered_map<std::string, size_t> path_to_var_;
};

class Signal {
    std::vector<std::pair<uint64_t, std::variant<uint64_t, std::string, double>>> changes_;
};

}
```

### extern "C" API (pylibfst.h)

```c
typedef void* pylibfst_waveform_t;
typedef void* pylibfst_hierarchy_t;
typedef void* pylibfst_signal_t;
typedef void* pylibfst_var_t;
typedef void* pylibfst_iterator_t;

pylibfst_waveform_t pylibfst_waveform_new(const char* path, int load_body);
void pylibfst_waveform_delete(pylibfst_waveform_t waveform);
pylibfst_signal_t pylibfst_waveform_get_signal(pylibfst_waveform_t waveform, pylibfst_var_t var);

pylibfst_iterator_t pylibfst_hierarchy_all_vars(pylibfst_hierarchy_t hierarchy);
const char* pylibfst_var_full_name(pylibfst_var_t var, pylibfst_hierarchy_t hierarchy);
uint32_t pylibfst_var_signal_ref(pylibfst_var_t var);

// Iterator functions
pylibfst_var_t pylibfst_var_iter_next(pylibfst_iterator_t iter);
void pylibfst_iterator_delete(pylibfst_iterator_t iter);
```

### Python Binding Structure (pylibfst.py)

```python
class Waveform:
    def __init__(self, path: str, multi_threaded: bool = True, load_body: bool = True):
        self._handle = _lib.pylibfst_waveform_new(path.encode(), load_body)
        self.hierarchy = Hierarchy(self._handle)
        
    def get_signal(self, var: Var) -> Signal:
        signal_handle = _lib.pylibfst_waveform_get_signal(self._handle, var._handle)
        return Signal(signal_handle)

class Var:
    def signal_ref(self) -> int:
        return _lib.pylibfst_var_signal_ref(self._handle)
        
    def full_name(self, hier: Hierarchy) -> str:
        return _lib.pylibfst_var_full_name(self._handle, hier._handle).decode()
```

## Key Implementation Details

### Hierarchy Parsing
1. Use `fstReaderIterateHier()` to traverse FST hierarchy
2. Strip bit ranges from signal names to match pywellen behavior
3. Build scope tree and variable list
4. Create path-to-variable mapping for fast lookups

### Signal Loading
1. Check cache before loading
2. Use `fstReaderSetFacProcessMask()` for specific signal
3. Collect changes via `fstReaderIterBlocks()` callback
4. Store as vector of (time, value) pairs
5. Parse FST bit strings to match pywellen's integer/string representation

### Time Table Construction
1. Collect all unique timestamps during hierarchy traversal
2. Store as sorted vector for binary search
3. Share single instance across all signals

### Value Representation
Match pywellen's approach:
- Binary vectors → integers (when possible) or bit strings
- Real values → doubles
- String values → strings
- Unknown/high-Z → bit strings with 'x', 'z' characters

## File Changes

### Modified Files
- `libfst/CMakeLists.txt` - Add C++20 flags, build shared library
- `Makefile` - Update build-libfst target

### New Files
- `libfst/pylibfst.cpp` - Implementation
- `libfst/pylibfst.h` - C API
- `libfst/pylibfst_internal.hpp` - C++ classes
- `pylibfst.py` - Complete rewrite with ctypes
- `tests/test_libfst_api.py` - API compatibility tests

## Testing Strategy

### API Compatibility Tests
```python
def test_api_compatibility():
    # Load same file with both libraries
    pw_wave = pywellen.Waveform("test.fst")
    lf_wave = pylibfst.Waveform("test.fst")
    
    # Verify identical hierarchies
    pw_vars = list(pw_wave.hierarchy.all_vars())
    lf_vars = list(lf_wave.hierarchy.all_vars())
    assert len(pw_vars) == len(lf_vars)
    
    # Verify signal data matches
    for pw_var, lf_var in zip(pw_vars, lf_vars):
        pw_sig = pw_wave.get_signal(pw_var)
        lf_sig = lf_wave.get_signal(lf_var)
        # Compare transitions...
```

### Performance Tests
- Measure load time for large FST files
- Compare memory usage
- Test signal access patterns

## Build Configuration

### CMakeLists.txt additions
```cmake
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_library(pylibfst SHARED 
    pylibfst.cpp
    fstapi.c 
    fastlz.c 
    lz4.c)
    
target_compile_options(pylibfst PRIVATE -fPIC)
target_link_libraries(pylibfst PRIVATE z)
```

## Success Criteria

1. All pywellen public methods available with identical signatures
2. Same data returned when reading identical FST files
3. Performance within 20% of pywellen
4. Pass all API compatibility tests
5. Handle FST files >1GB efficiently