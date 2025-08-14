mod ffi;
mod hierarchy;
mod signal;
mod waveform;

use pyo3::prelude::*;
use pyo3::types::PyString;
use pyo3::Bound;
use std::sync::Arc;

use hierarchy::{ScopeRef, SignalRef, VarRef};
use signal::SignalValue;

/// Python wrapper for VarIndex
#[pyclass(name = "VarIndex")]
#[derive(Clone)]
struct PyVarIndex {
    inner: hierarchy::VarIndex,
}

#[pymethods]
impl PyVarIndex {
    fn msb(&self) -> i32 {
        self.inner.msb
    }
    
    fn lsb(&self) -> i32 {
        self.inner.lsb
    }
}

/// Python wrapper for TimescaleUnit
#[pyclass(name = "TimescaleUnit")]
#[derive(Clone)]
struct PyTimescaleUnit {
    inner: hierarchy::TimescaleUnit,
}

#[pymethods]
impl PyTimescaleUnit {
    fn __str__(&self) -> &str {
        match self.inner {
            hierarchy::TimescaleUnit::Zeptoseconds => "zs",
            hierarchy::TimescaleUnit::Attoseconds => "as",
            hierarchy::TimescaleUnit::Femtoseconds => "fs",
            hierarchy::TimescaleUnit::Picoseconds => "ps",
            hierarchy::TimescaleUnit::Nanoseconds => "ns",
            hierarchy::TimescaleUnit::Microseconds => "us",
            hierarchy::TimescaleUnit::Milliseconds => "ms",
            hierarchy::TimescaleUnit::Seconds => "s",
            hierarchy::TimescaleUnit::Unknown => "unknown",
        }
    }
    
    fn __repr__(&self) -> String {
        format!("TimescaleUnit({})", self.__str__())
    }
    
    fn to_exponent(&self) -> Option<i8> {
        self.inner.to_exponent()
    }
}

/// Python wrapper for Timescale
#[pyclass(name = "Timescale")]
#[derive(Clone)]
struct PyTimescale {
    #[pyo3(get)]
    factor: u32,
    #[pyo3(get)]
    unit: PyTimescaleUnit,
}

#[pymethods]
impl PyTimescale {
    fn __str__(&self) -> String {
        format!("{}{}", self.factor, self.unit.__str__())
    }
    
    fn __repr__(&self) -> String {
        format!("Timescale(factor={}, unit={})", self.factor, self.unit.__str__())
    }
}

/// Python wrapper for Hierarchy
#[pyclass(name = "Hierarchy")]
#[derive(Clone)]
struct PyHierarchy {
    inner: Arc<hierarchy::Hierarchy>,
}

#[pymethods]
impl PyHierarchy {
    fn all_vars(&self) -> PyVarIter {
        let vars: Vec<PyVar> = self.inner
            .all_vars()
            .map(|v| PyVar {
                inner: v.clone(),
                hierarchy: self.inner.clone(),
            })
            .collect();
        PyVarIter { vars, index: 0 }
    }
    
    fn top_scopes(&self) -> PyScopeIter {
        let scopes: Vec<PyScope> = self.inner
            .top_scopes()
            .map(|s| PyScope {
                inner: s.clone(),
                hierarchy: self.inner.clone(),
            })
            .collect();
        PyScopeIter { scopes, index: 0 }
    }
    
    fn date(&self) -> &str {
        &self.inner.date
    }
    
    fn version(&self) -> &str {
        &self.inner.version
    }
    
    fn timescale(&self) -> Option<PyTimescale> {
        self.inner.timescale.as_ref().map(|ts| PyTimescale {
            factor: ts.factor,
            unit: PyTimescaleUnit { inner: ts.unit },
        })
    }
    
    fn file_format(&self) -> &str {
        &self.inner.file_format
    }
}

/// Python wrapper for Scope
#[pyclass(name = "Scope")]
#[derive(Clone)]
struct PyScope {
    inner: hierarchy::Scope,
    hierarchy: Arc<hierarchy::Hierarchy>,
}

#[pymethods]
impl PyScope {
    fn name(&self, _hier: &PyHierarchy) -> &str {
        &self.inner.name
    }
    
    fn full_name(&self, _hier: &PyHierarchy) -> String {
        // Build full path from parent scopes
        let mut path = Vec::new();
        let mut current = Some(&self.inner);
        
        while let Some(scope) = current {
            path.push(scope.name.clone());
            current = scope.parent.and_then(|p| self.hierarchy.get_scope(p));
        }
        
        path.reverse();
        path.join(".")
    }
    
    fn scope_type(&self) -> &str {
        match self.inner.scope_type {
            hierarchy::ScopeType::Module => "module",
            hierarchy::ScopeType::Task => "task",
            hierarchy::ScopeType::Function => "function",
            hierarchy::ScopeType::Begin => "begin",
            hierarchy::ScopeType::Fork => "fork",
            hierarchy::ScopeType::Generate => "generate",
            hierarchy::ScopeType::Struct => "struct",
            hierarchy::ScopeType::Union => "union",
            hierarchy::ScopeType::Class => "class",
            hierarchy::ScopeType::Interface => "interface",
            hierarchy::ScopeType::Package => "package",
            hierarchy::ScopeType::Program => "program",
            _ => "unknown",
        }
    }
    
    fn vars(&self, _hier: &PyHierarchy) -> PyVarIter {
        let vars: Vec<PyVar> = self.inner.vars
            .iter()
            .filter_map(|&var_ref| self.hierarchy.get_var(var_ref))
            .map(|v| PyVar {
                inner: v.clone(),
                hierarchy: self.hierarchy.clone(),
            })
            .collect();
        PyVarIter { vars, index: 0 }
    }
    
    fn scopes(&self, _hier: &PyHierarchy) -> PyScopeIter {
        let scopes: Vec<PyScope> = self.inner.children
            .iter()
            .filter_map(|&scope_ref| self.hierarchy.get_scope(scope_ref))
            .map(|s| PyScope {
                inner: s.clone(),
                hierarchy: self.hierarchy.clone(),
            })
            .collect();
        PyScopeIter { scopes, index: 0 }
    }
}

/// Python wrapper for Var
#[pyclass(name = "Var")]
#[derive(Clone)]
struct PyVar {
    inner: hierarchy::Var,
    hierarchy: Arc<hierarchy::Hierarchy>,
}

#[pymethods]
impl PyVar {
    fn name(&self, _hier: &PyHierarchy) -> &str {
        &self.inner.name
    }
    
    fn full_name(&self, _hier: &PyHierarchy) -> String {
        self.hierarchy.var_full_name(&self.inner)
    }
    
    fn bitwidth(&self) -> Option<u32> {
        self.inner.bitwidth()
    }
    
    fn var_type(&self) -> &str {
        match self.inner.var_type {
            hierarchy::VarType::Event => "Event",
            hierarchy::VarType::Integer => "Integer",
            hierarchy::VarType::Parameter => "Parameter",
            hierarchy::VarType::Real => "Real",
            hierarchy::VarType::Reg => "Reg",
            hierarchy::VarType::Supply0 => "Supply0",
            hierarchy::VarType::Supply1 => "Supply1",
            hierarchy::VarType::Time => "Time",
            hierarchy::VarType::Tri => "Tri",
            hierarchy::VarType::TriAnd => "TriAnd",
            hierarchy::VarType::TriOr => "TriOr",
            hierarchy::VarType::TriReg => "TriReg",
            hierarchy::VarType::Tri0 => "Tri0",
            hierarchy::VarType::Tri1 => "Tri1",
            hierarchy::VarType::WAnd => "WAnd",
            hierarchy::VarType::Wire => "Wire",
            hierarchy::VarType::WOr => "WOr",
            hierarchy::VarType::String => "String",
            hierarchy::VarType::Port => "Port",
            hierarchy::VarType::SparseArray => "SparseArray",
            hierarchy::VarType::RealTime => "RealTime",
            // SystemVerilog types
            hierarchy::VarType::Bit => "Bit",
            hierarchy::VarType::Logic => "Logic",
            hierarchy::VarType::Int => "Int",
            hierarchy::VarType::ShortInt => "ShortInt",
            hierarchy::VarType::LongInt => "LongInt",
            hierarchy::VarType::Byte => "Byte",
            hierarchy::VarType::Enum => "Enum",
            hierarchy::VarType::ShortReal => "ShortReal",
            // VHDL types (though FST may not use these)
            hierarchy::VarType::Boolean => "Boolean",
            hierarchy::VarType::BitVector => "BitVector",
            hierarchy::VarType::StdLogic => "StdLogic",
            hierarchy::VarType::StdLogicVector => "StdLogicVector",
            hierarchy::VarType::StdULogic => "StdULogic",
            hierarchy::VarType::StdULogicVector => "StdULogicVector",
        }
    }
    
    fn enum_type(&self, _hier: &PyHierarchy) -> Option<(String, Vec<(String, String)>)> {
        None // FST doesn't support enum types
    }
    
    fn vhdl_type_name(&self, _hier: &PyHierarchy) -> Option<String> {
        None // FST doesn't store VHDL type names
    }
    
    fn direction(&self) -> &str {
        match self.inner.direction {
            hierarchy::VarDirection::Unknown => "Unknown",
            hierarchy::VarDirection::Implicit => "Implicit",
            hierarchy::VarDirection::Input => "Input",
            hierarchy::VarDirection::Output => "Output",
            hierarchy::VarDirection::InOut => "InOut",
            hierarchy::VarDirection::Buffer => "Buffer",
            hierarchy::VarDirection::Linkage => "Linkage",
        }
    }
    
    fn length(&self) -> Option<u32> {
        self.inner.length
    }
    
    fn is_real(&self) -> bool {
        self.inner.is_real()
    }
    
    fn is_string(&self) -> bool {
        self.inner.is_string()
    }
    
    fn is_1bit(&self) -> bool {
        self.inner.is_1bit()
    }
    
    fn index(&self) -> Option<PyVarIndex> {
        self.inner.index.as_ref().map(|idx| PyVarIndex {
            inner: idx.clone(),
        })
    }
    
    fn signal_ref(&self) -> usize {
        self.inner.signal_ref.0
    }
}

/// Python iterator for variables
#[pyclass(name = "VarIter")]
struct PyVarIter {
    vars: Vec<PyVar>,
    index: usize,
}

#[pymethods]
impl PyVarIter {
    fn __iter__(slf: PyRef<'_, Self>) -> PyRef<'_, Self> {
        slf
    }
    
    fn __next__(mut slf: PyRefMut<'_, Self>) -> Option<PyVar> {
        if slf.index < slf.vars.len() {
            let var = slf.vars[slf.index].clone();
            slf.index += 1;
            Some(var)
        } else {
            None
        }
    }
}

/// Python iterator for scopes
#[pyclass(name = "ScopeIter")]
struct PyScopeIter {
    scopes: Vec<PyScope>,
    index: usize,
}

#[pymethods]
impl PyScopeIter {
    fn __iter__(slf: PyRef<'_, Self>) -> PyRef<'_, Self> {
        slf
    }
    
    fn __next__(mut slf: PyRefMut<'_, Self>) -> Option<PyScope> {
        if slf.index < slf.scopes.len() {
            let scope = slf.scopes[slf.index].clone();
            slf.index += 1;
            Some(scope)
        } else {
            None
        }
    }
}

/// Python wrapper for Signal
#[pyclass(name = "Signal")]
#[derive(Clone)]
struct PySignal {
    inner: Arc<signal::Signal>,
}

#[pymethods]
impl PySignal {
    fn value_at_time(&self, time: u64) -> PyObject {
        Python::with_gil(|py| {
            match self.inner.value_at_time(time) {
                Some(SignalValue::Binary(ref bits)) => {
                    // Convert to integer
                    if let Some(val) = SignalValue::Binary(bits.clone()).to_int() {
                        val.into_py(py)
                    } else {
                        // Too large for u64, return as string
                        SignalValue::Binary(bits.clone()).to_string_repr().into_py(py)
                    }
                }
                Some(SignalValue::FourValue(ref s)) => s.clone().into_py(py),
                Some(SignalValue::Real(r)) => r.into_py(py),
                Some(SignalValue::String(ref s)) => s.clone().into_py(py),
                None => py.None(),
            }
        })
    }
    
    fn value_at_idx(&self, idx: usize) -> PyObject {
        Python::with_gil(|py| {
            match self.inner.value_at_idx(idx) {
                Some(SignalValue::Binary(ref bits)) => {
                    if let Some(val) = SignalValue::Binary(bits.clone()).to_int() {
                        val.into_py(py)
                    } else {
                        SignalValue::Binary(bits.clone()).to_string_repr().into_py(py)
                    }
                }
                Some(SignalValue::FourValue(ref s)) => s.clone().into_py(py),
                Some(SignalValue::Real(r)) => r.into_py(py),
                Some(SignalValue::String(ref s)) => s.clone().into_py(py),
                None => py.None(),
            }
        })
    }
    
    fn all_changes(&self) -> PySignalChangeIter {
        let changes: Vec<(u64, PyObject)> = Python::with_gil(|py| {
            self.inner.all_changes()
                .map(|(time, value)| {
                    let py_value = match value {
                        SignalValue::Binary(ref bits) => {
                            if let Some(val) = SignalValue::Binary(bits.clone()).to_int() {
                                val.into_py(py)
                            } else {
                                SignalValue::Binary(bits.clone()).to_string_repr().into_py(py)
                            }
                        }
                        SignalValue::FourValue(ref s) => s.clone().into_py(py),
                        SignalValue::Real(r) => r.into_py(py),
                        SignalValue::String(ref s) => s.clone().into_py(py),
                    };
                    (time, py_value)
                })
                .collect()
        });
        
        PySignalChangeIter { changes, index: 0 }
    }
    
    fn all_changes_after(&self, start_time: u64) -> PySignalChangeIter {
        let changes: Vec<(u64, PyObject)> = Python::with_gil(|py| {
            self.inner.all_changes_after(start_time)
                .map(|(time, value)| {
                    let py_value = match value {
                        SignalValue::Binary(ref bits) => {
                            if let Some(val) = SignalValue::Binary(bits.clone()).to_int() {
                                val.into_py(py)
                            } else {
                                SignalValue::Binary(bits.clone()).to_string_repr().into_py(py)
                            }
                        }
                        SignalValue::FourValue(ref s) => s.clone().into_py(py),
                        SignalValue::Real(r) => r.into_py(py),
                        SignalValue::String(ref s) => s.clone().into_py(py),
                    };
                    (time, py_value)
                })
                .collect()
        });
        
        PySignalChangeIter { changes, index: 0 }
    }
    
    fn query_signal(&self, query_time: u64) -> PyQueryResult {
        let result = self.inner.query_signal(query_time);
        
        let value = Python::with_gil(|py| {
            result.value.map(|v| match v {
                SignalValue::Binary(ref bits) => {
                    if let Some(val) = SignalValue::Binary(bits.clone()).to_int() {
                        val.into_py(py)
                    } else {
                        SignalValue::Binary(bits.clone()).to_string_repr().into_py(py)
                    }
                }
                SignalValue::FourValue(ref s) => s.clone().into_py(py),
                SignalValue::Real(r) => r.into_py(py),
                SignalValue::String(ref s) => s.clone().into_py(py),
            })
        });
        
        PyQueryResult {
            value,
            actual_time: result.actual_time,
            next_idx: result.next_idx,
            next_time: result.next_time,
        }
    }
}

/// Python iterator for signal changes
#[pyclass(name = "SignalChangeIter")]
struct PySignalChangeIter {
    changes: Vec<(u64, PyObject)>,
    index: usize,
}

#[pymethods]
impl PySignalChangeIter {
    fn __iter__(slf: PyRef<'_, Self>) -> PyRef<'_, Self> {
        slf
    }
    
    fn __len__(&self) -> usize {
        self.changes.len()
    }
    
    fn __next__(mut slf: PyRefMut<'_, Self>, py: Python) -> Option<(u64, PyObject)> {
        if slf.index < slf.changes.len() {
            let (time, ref obj) = slf.changes[slf.index];
            let cloned_obj = obj.clone_ref(py);
            slf.index += 1;
            Some((time, cloned_obj))
        } else {
            None
        }
    }
}

/// Python wrapper for QueryResult
#[pyclass(name = "QueryResult")]
struct PyQueryResult {
    #[pyo3(get)]
    value: Option<PyObject>,
    #[pyo3(get)]
    actual_time: Option<u64>,
    #[pyo3(get)]
    next_idx: Option<usize>,
    #[pyo3(get)]
    next_time: Option<u64>,
}

/// Python wrapper for TimeTable
#[pyclass(name = "TimeTable")]
#[derive(Clone)]
struct PyTimeTable {
    inner: signal::TimeTable,
}

#[pymethods]
impl PyTimeTable {
    fn __getitem__(&self, idx: usize) -> PyResult<u64> {
        self.inner.get(idx)
            .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyIndexError, _>("Index out of range"))
    }
    
    fn __len__(&self) -> usize {
        self.inner.len()
    }
}

/// Main Waveform class
#[pyclass(name = "Waveform")]
struct PyWaveform {
    inner: waveform::Waveform,
}

#[pymethods]
impl PyWaveform {
    #[new]
    #[pyo3(signature = (path, multi_threaded = true, remove_scopes_with_empty_name = false, load_body = true))]
    fn new(
        path: &str,
        multi_threaded: bool,
        remove_scopes_with_empty_name: bool,
        load_body: bool,
    ) -> PyResult<Self> {
        let waveform = waveform::Waveform::new(
            path,
            multi_threaded,
            remove_scopes_with_empty_name,
            load_body,
        ).map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(e))?;
        
        Ok(PyWaveform { inner: waveform })
    }
    
    #[getter]
    fn hierarchy(&self) -> PyHierarchy {
        PyHierarchy {
            inner: self.inner.hierarchy.clone(),
        }
    }
    
    #[getter]
    fn time_range(&self) -> Option<(u64, u64)> {
        self.inner.time_range
    }
    
    fn load_body(&mut self) -> PyResult<()> {
        self.inner.load_body()
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e))
    }
    
    fn body_loaded(&self) -> bool {
        self.inner.body_loaded()
    }
    
    fn get_signal(&mut self, var: &PyVar, py: Python) -> PyResult<PySignal> {
        // Release GIL for I/O operation
        py.allow_threads(|| {
            self.inner.get_signal(&var.inner)
                .map(|signal| PySignal { inner: signal })
                .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e))
        })
    }
    
    fn get_signal_from_path(&mut self, abs_hierarchy_path: &str, py: Python) -> PyResult<PySignal> {
        py.allow_threads(|| {
            self.inner.get_signal_from_path(abs_hierarchy_path)
                .map(|signal| PySignal { inner: signal })
                .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e))
        })
    }
    
    fn load_signals(&mut self, vars: Vec<PyVar>, py: Python) -> PyResult<Vec<PySignal>> {
        let rust_vars: Vec<_> = vars.iter().map(|v| v.inner.clone()).collect();
        
        py.allow_threads(|| {
            self.inner.load_signals(&rust_vars)
                .map(|signals| {
                    signals.into_iter()
                        .map(|s| PySignal { inner: s })
                        .collect()
                })
                .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e))
        })
    }
    
    fn load_signals_multithreaded(&mut self, vars: Vec<PyVar>, py: Python) -> PyResult<Vec<PySignal>> {
        let rust_vars: Vec<_> = vars.iter().map(|v| v.inner.clone()).collect();
        
        py.allow_threads(|| {
            self.inner.load_signals_multithreaded(&rust_vars)
                .map(|signals| {
                    signals.into_iter()
                        .map(|s| PySignal { inner: s })
                        .collect()
                })
                .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e))
        })
    }
    
    fn unload_signals(&self, signals: Vec<PySignal>) {
        let refs: Vec<_> = signals.iter()
            .map(|_| SignalRef(0)) // Would need proper tracking of signal refs
            .collect();
        self.inner.unload_signals(&refs);
    }
}

/// Python module definition
#[pymodule]
fn pylibfst(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<PyWaveform>()?;
    m.add_class::<PyHierarchy>()?;
    m.add_class::<PyScope>()?;
    m.add_class::<PyVar>()?;
    m.add_class::<PySignal>()?;
    m.add_class::<PyTimeTable>()?;
    m.add_class::<PyTimescale>()?;
    m.add_class::<PyTimescaleUnit>()?;
    m.add_class::<PyVarIndex>()?;
    m.add_class::<PyVarIter>()?;
    m.add_class::<PyScopeIter>()?;
    m.add_class::<PySignalChangeIter>()?;
    m.add_class::<PyQueryResult>()?;
    
    // Alias classes to match pywellen naming
    m.add("Waveform", m.getattr("Waveform")?)?;
    m.add("Hierarchy", m.getattr("Hierarchy")?)?;
    m.add("Scope", m.getattr("Scope")?)?;
    m.add("Var", m.getattr("Var")?)?;
    m.add("Signal", m.getattr("Signal")?)?;
    m.add("TimeTable", m.getattr("TimeTable")?)?;
    m.add("Timescale", m.getattr("Timescale")?)?;
    m.add("TimescaleUnit", m.getattr("TimescaleUnit")?)?;
    m.add("VarIndex", m.getattr("VarIndex")?)?;
    m.add("VarIter", m.getattr("VarIter")?)?;
    m.add("ScopeIter", m.getattr("ScopeIter")?)?;
    m.add("SignalChangeIter", m.getattr("SignalChangeIter")?)?;
    m.add("QueryResult", m.getattr("QueryResult")?)?;
    
    Ok(())
}