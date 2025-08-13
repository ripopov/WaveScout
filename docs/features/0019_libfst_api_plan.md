# Feature Plan: LibFST API Compatible with PyWellen (Rust Implementation)

## Requirements

Create libfst Rust interface matching pywellen API exactly, allowing interchangeable use for FST file reading.
**The current Python pylibfst.py implementation will be removed completely and replaced with this Rust-based solution.**

### Scope
- **Remove existing pylibfst.py** (current ctypes-based implementation)
- Implement Rust wrapper around libfst C API using FFI
- Python bindings via PyO3/maturin matching pywellen.pyi interface  
- Support all pywellen classes: Waveform, Hierarchy, Scope, Var, Signal, TimeTable, Timescale
- Lazy signal loading
- Memory-efficient handling of large FST files

## Architecture Overview

### Approach: Rust + PyO3 (like pywellen)
We will create a Rust crate that:
1. Uses Rust FFI to call libfst C functions
2. Implements the same Rust structs/traits as wellen
3. Exposes Python bindings via PyO3 with identical API to pywellen

This ensures:
- Proper memory management with Rust's ownership system
- Native Python iterators and object model
- Type safety and performance
- Direct compatibility with existing pywellen code

## Implementation Design

### File Structure
```
libfst_rust/
├── Cargo.toml           # Rust package configuration
├── build.rs             # Build script to link libfst
├── pyproject.toml       # Python package configuration  
├── src/
│   ├── lib.rs           # PyO3 Python bindings (mirrors pywellen/src/lib.rs)
│   ├── ffi.rs           # FFI bindings to libfst C API
│   ├── hierarchy.rs     # Hierarchy, Scope, Var implementations
│   ├── signal.rs        # Signal data structures
│   └── waveform.rs      # Main waveform reader
└── tests/
    └── test_compat.py   # API compatibility tests
```

### Rust FFI Layer (src/ffi.rs)

```rust
use std::ffi::{CStr, CString};
use std::os::raw::{c_char, c_void, c_int, c_uint};

// FFI type definitions matching fstapi.h
pub type FstHandle = u32;
pub type FstReaderContext = *mut c_void;

#[repr(C)]
pub struct FstHier {
    pub htyp: u8,
    pub u: FstHierUnion,
}

#[repr(C)]
pub union FstHierUnion {
    pub scope: FstHierScope,
    pub var: FstHierVar,
}

// FFI function declarations
extern "C" {
    pub fn fstReaderOpen(filename: *const c_char) -> FstReaderContext;
    pub fn fstReaderClose(ctx: FstReaderContext);
    pub fn fstReaderIterateHier(ctx: FstReaderContext) -> *mut FstHier;
    pub fn fstReaderIterateHierRewind(ctx: FstReaderContext) -> c_int;
    pub fn fstReaderSetFacProcessMask(ctx: FstReaderContext, facidx: FstHandle);
    pub fn fstReaderIterBlocks(
        ctx: FstReaderContext,
        callback: Option<FstValueChangeCb>,
        user_data: *mut c_void,
        vcd_handle: *mut c_void
    ) -> c_int;
}

// Safe Rust wrapper
pub struct FstReader {
    ctx: FstReaderContext,
}

impl FstReader {
    /// Safe wrapper for opening FST files
    pub fn open(path: &str) -> Result<Self, String> { /* ... */ }
}

impl Drop for FstReader {
    /// Automatically close FST reader on drop
    fn drop(&mut self) { /* ... */ }
}
```

### Core Rust Types (src/hierarchy.rs)

```rust
use std::sync::Arc;
use std::collections::HashMap;

/// Mirrors wellen::Hierarchy structure
pub struct Hierarchy {
    scopes: Vec<Scope>,
    vars: Vec<Var>,
    path_to_var: HashMap<String, usize>,
    signal_ref_map: HashMap<u32, SignalRef>,  // Maps FST handles to SignalRefs
}

/// Mirrors wellen::Scope
#[derive(Clone)]
pub struct Scope {
    name: String,
    scope_type: ScopeType,
    parent: Option<ScopeRef>,
    children: Vec<ScopeRef>,
    vars: Vec<VarRef>,
}

/// Mirrors wellen::Var
#[derive(Clone)]
pub struct Var {
    name: String,
    var_type: VarType,
    direction: VarDirection,
    length: Option<u32>,
    signal_ref: SignalRef,
    index: Option<VarIndex>,
}

/// Reference types for efficient indexing
#[derive(Copy, Clone, Hash, Eq, PartialEq)]
pub struct SignalRef(pub usize);

#[derive(Copy, Clone)]
pub struct ScopeRef(pub usize);

#[derive(Copy, Clone)]
pub struct VarRef(pub usize);

impl Hierarchy {
    /// Build hierarchy from FST reader
    /// Algorithm:
    /// 1. Use fstReaderIterateHier() to traverse FST hierarchy
    /// 2. Maintain scope stack for tracking current position
    /// 3. Build parent-child relationships between scopes
    /// 4. Strip bit ranges from signal names (e.g., "sig[7:0]" -> "sig")
    /// 5. Map FST handles to SignalRef for alias detection
    /// 6. Create path-to-variable mapping for fast lookups
    pub fn from_fst(reader: &FstReader) -> Result<Self, String> { /* ... */ }
    
    pub fn all_vars(&self) -> impl Iterator<Item = &Var> { /* ... */ }
    
    pub fn top_scopes(&self) -> impl Iterator<Item = &Scope> { /* ... */ }
}
```

### Signal Loading (src/signal.rs)

```rust
use std::sync::Arc;

/// Mirrors wellen::Signal
pub struct Signal {
    changes: Vec<(u64, SignalValue)>,
}

/// Mirrors wellen::SignalValue
pub enum SignalValue {
    Binary(Vec<u8>),
    FourValue(Vec<u8>),
    Real(f64),
    String(String),
}

impl Signal {
    /// Load signal data from FST using callback mechanism
    /// Algorithm:
    /// 1. Clear all facility masks with fstReaderClrFacProcessMaskAll()
    /// 2. Set mask for specific signal with fstReaderSetFacProcessMask()
    /// 3. Use fstReaderIterBlocks() with C callback to collect changes
    /// 4. Callback receives time and value for each transition
    /// 5. Parse FST value strings into appropriate SignalValue enum
    pub fn load_from_fst(reader: &FstReader, handle: FstHandle) -> Result<Self, String> { /* ... */ }
    
    /// Binary search to find value at specific time
    pub fn value_at_time(&self, time: u64) -> Option<&SignalValue> { /* ... */ }
    
    /// Iterator over all signal transitions
    pub fn all_changes(&self) -> impl Iterator<Item = (u64, &SignalValue)> { /* ... */ }
}

/// Parse FST string values into typed SignalValue
/// Logic:
/// - Pure binary (0/1) -> Binary vector (convertible to integer)
/// - Contains x/z/X/Z -> Four-value logic string
/// - Parseable as float -> Real value
/// - Otherwise -> String value
fn parse_signal_value(s: &str) -> SignalValue { /* ... */ }
```

### Main Waveform Reader (src/waveform.rs)

```rust
use std::sync::{Arc, Mutex};
use std::collections::HashMap;

pub struct SignalSource {
    reader: Arc<Mutex<FstReader>>,
    signal_cache: Arc<Mutex<HashMap<SignalRef, Arc<Signal>>>>,
}

impl SignalSource {
    /// Load multiple signals with caching
    /// Algorithm:
    /// 1. Check cache for each requested signal
    /// 2. For cache miss, load signal from FST file
    /// 3. Store loaded signals in Arc for reference counting
    /// 4. Cache signals to avoid redundant I/O
    /// 5. If multi_threaded, use rayon for parallel loading
    pub fn load_signals(
        &mut self,
        refs: &[SignalRef],
        hierarchy: &Hierarchy,
        multi_threaded: bool,
    ) -> Vec<(SignalRef, Signal)> { /* ... */ }
}
```

### PyO3 Python Bindings (src/lib.rs)

```rust
use pyo3::prelude::*;
use std::sync::Arc;

/// Python module matching pywellen exactly
#[pymodule]
fn pylibfst(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_class::<Waveform>()?;
    m.add_class::<Hierarchy>()?;
    m.add_class::<Scope>()?;
    m.add_class::<Var>()?;
    m.add_class::<Signal>()?;
    m.add_class::<TimeTable>()?;
    m.add_class::<Timescale>()?;
    m.add_class::<TimescaleUnit>()?;
    m.add_class::<VarIter>()?;
    m.add_class::<ScopeIter>()?;
    m.add_class::<SignalChangeIter>()?;
    m.add_class::<QueryResult>()?;
    Ok(())
}

#[pyclass]
struct Waveform {
    #[pyo3(get)]
    hierarchy: Hierarchy,
    
    wave_source: Option<SignalSource>,
    time_table: Option<TimeTable>,
    body_continuation: Option<Box<dyn FnOnce() -> Result<Body, String>>>,
}

#[pymethods]
impl Waveform {
    #[new]
    #[pyo3(signature = (path, multi_threaded = true, remove_scopes_with_empty_name = false, load_body = true))]
    /// Constructor matching pywellen signature exactly
    /// Logic:
    /// 1. Open FST file with FstReader
    /// 2. Parse hierarchy structure
    /// 3. If load_body=true, immediately load time table and prepare signal source
    /// 4. If load_body=false, store continuation closure for lazy loading
    fn new(...) -> PyResult<Self> { /* ... */ }
    
    /// Lazy loading implementation
    /// Executes stored continuation to load body on first signal access
    fn load_body(&mut self) -> PyResult<()> { /* ... */ }
    
    fn body_loaded(&self) -> bool { /* ... */ }
    
    /// Get signal with GIL release for I/O operations
    /// Algorithm:
    /// 1. Ensure body is loaded
    /// 2. Extract signal_ref from Var
    /// 3. Release Python GIL during signal loading (heavy I/O)
    /// 4. Return Signal wrapped in Arc for reference counting
    fn get_signal(&mut self, var: &Var, py: Python) -> PyResult<Signal> { /* ... */ }
    
    // Implement remaining methods: get_signal_from_path, load_signals, 
    // load_signals_multithreaded, unload_signals - all matching pywellen API
}

#[pyclass]
#[derive(Clone)]
struct Hierarchy(Arc<crate::hierarchy::Hierarchy>);

#[pymethods]
impl Hierarchy {
    /// Return Python iterator over all variables
    /// Note: Collects into Vec due to Python lifetime requirements
    fn all_vars(&self) -> VarIter { /* ... */ }
    
    /// Return Python iterator over top-level scopes
    fn top_scopes(&self) -> ScopeIter { /* ... */ }
    
    // Additional methods: date(), version(), timescale(), file_format()
    // All matching pywellen API exactly
}

// Python iterator wrappers implementing Python iterator protocol
#[pyclass]
struct VarIter(Box<dyn Iterator<Item = Var> + Send + Sync>);

#[pymethods]
impl VarIter {
    fn __iter__(slf: PyRef<'_, Self>) -> PyRef<'_, Self> { /* ... */ }
    fn __next__(mut slf: PyRefMut<'_, Self>) -> Option<Var> { /* ... */ }
}

// Similar implementations for:
// - ScopeIter: Iterator over Scope objects
// - SignalChangeIter: Iterator over (time, value) tuples
// - Additional classes: Var, Scope, Signal, TimeTable, Timescale, TimescaleUnit, QueryResult
```

## Build Configuration

### Cargo.toml
```toml
[package]
name = "pylibfst"
version = "0.1.0"
edition = "2021"

[lib]
name = "pylibfst"
crate-type = ["cdylib"]

[dependencies]
pyo3 = { version = "0.22", features = ["extension-module"] }
num-bigint = "0.4"

[build-dependencies]
cc = "1.0"

[profile.release]
lto = true
```

### build.rs
```rust
fn main() {
    // Build script to compile and link libfst C library
    // - Compiles fstapi.c, fastlz.c, lz4.c
    // - Links against zlib for compression support
    // - Generates static library for linking
}
```

### pyproject.toml
```toml
[build-system]
requires = ["maturin>=1.0,<2.0"]
build-backend = "maturin"

[project]
name = "pylibfst"
version = "0.1.0"
requires-python = ">=3.8"

[tool.maturin]
features = ["pyo3/extension-module"]
python-source = "python"
```

## Testing Strategy

### API Compatibility Test (tests/test_compat.py)
```python
import pylibfst
import pywellen
import pytest

def test_api_compatibility():
    """Verify pylibfst matches pywellen API exactly"""
    
    # Load same FST file with both libraries
    pw_wave = pywellen.Waveform("test.fst")
    lf_wave = pylibfst.Waveform("test.fst")
    
    # Test hierarchy navigation
    pw_vars = list(pw_wave.hierarchy.all_vars())
    lf_vars = list(lf_wave.hierarchy.all_vars())
    assert len(pw_vars) == len(lf_vars)
    
    # Test signal_ref for alias detection
    for pw_var, lf_var in zip(pw_vars, lf_vars):
        assert pw_var.signal_ref() == lf_var.signal_ref()
        assert pw_var.full_name(pw_wave.hierarchy) == lf_var.full_name(lf_wave.hierarchy)
    
    # Test signal loading and data
    for i in range(min(10, len(pw_vars))):
        pw_sig = pw_wave.get_signal(pw_vars[i])
        lf_sig = lf_wave.get_signal(lf_vars[i])
        
        # Compare all transitions
        pw_changes = list(pw_sig.all_changes())
        lf_changes = list(lf_sig.all_changes())
        assert len(pw_changes) == len(lf_changes)
        
        for (pw_time, pw_val), (lf_time, lf_val) in zip(pw_changes, lf_changes):
            assert pw_time == lf_time
            assert pw_val == lf_val

def test_lazy_loading():
    """Test lazy body loading"""
    wave = pylibfst.Waveform("test.fst", load_body=False)
    assert not wave.body_loaded()
    
    # Body should load on first signal access
    var = next(wave.hierarchy.all_vars())
    signal = wave.get_signal(var)
    assert wave.body_loaded()

def test_iterators():
    """Test Python iterator protocol"""
    wave = pylibfst.Waveform("test.fst")
    
    # Test VarIter
    vars_list = list(wave.hierarchy.all_vars())
    assert len(vars_list) > 0
    
    # Test ScopeIter
    scopes = list(wave.hierarchy.top_scopes())
    assert len(scopes) > 0
    
    # Test SignalChangeIter
    var = vars_list[0]
    signal = wave.get_signal(var)
    changes = list(signal.all_changes())
    assert len(changes) > 0
```

## Implementation Steps

1. **Setup Rust project structure**
   - Create libfst_rust directory
   - Initialize Cargo project
   - Configure maturin for Python packaging

2. **Implement FFI layer**
   - Define FFI types matching fstapi.h
   - Create safe Rust wrappers for C functions
   - Test basic FST file opening

3. **Build core data structures**
   - Implement Hierarchy, Scope, Var, Signal
   - Parse FST hierarchy into Rust structures
   - Handle signal references and aliases

4. **Implement signal loading**
   - Create callback mechanism for fstReaderIterBlocks
   - Parse signal values (binary, 4-state, real, string)
   - Build time table from timestamps

5. **Add PyO3 bindings**
   - Mirror pywellen's Python API exactly
   - Implement Python iterators
   - Handle GIL release for I/O operations

6. **Testing and validation**
   - Run compatibility tests against pywellen
   - Performance benchmarking
   - Memory usage analysis

## Success Criteria

1. ✅ All pywellen public methods available with identical signatures
2. ✅ Same data returned when reading identical FST files
3. ✅ Performance within 20% of pywellen
4. ✅ Pass all API compatibility tests
5. ✅ Handle FST files >1GB efficiently
6. ✅ Python iterators work correctly
7. ✅ Proper memory management (no leaks)
8. ✅ Thread-safe signal loading

## Advantages of Rust Approach

- **Memory Safety**: Rust's ownership system prevents memory leaks and use-after-free
- **Performance**: Zero-cost abstractions and efficient FFI
- **Type Safety**: Strong typing catches errors at compile time
- **Python Integration**: PyO3 provides seamless Python/Rust interop
- **Maintainability**: Same toolchain as pywellen (maturin, PyO3)
- **Compatibility**: Can perfectly mirror pywellen's API and behavior