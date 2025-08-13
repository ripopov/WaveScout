use std::collections::BTreeMap;
use std::sync::{Arc, Mutex};

use crate::ffi::{FstHandle, FstReader, FstValueChangeCb};
use crate::hierarchy::SignalRef;

/// Signal value enumeration
#[derive(Debug, Clone, PartialEq)]
pub enum SignalValue {
    Binary(Vec<u8>),    // Binary values (0/1)
    FourValue(String),  // Four-value logic (0/1/x/z)
    Real(f64),          // Real numbers
    String(String),     // String values
}

impl SignalValue {
    /// Parse FST string value into typed SignalValue
    pub fn from_fst_string(s: &str, is_real: bool, is_string: bool) -> Self {
        if is_real {
            // Try to parse as float
            if let Ok(val) = s.parse::<f64>() {
                return SignalValue::Real(val);
            }
        }
        
        if is_string {
            return SignalValue::String(s.to_string());
        }
        
        // Check if it's pure binary
        if s.chars().all(|c| c == '0' || c == '1') {
            let bytes: Vec<u8> = s.chars().map(|c| if c == '1' { 1 } else { 0 }).collect();
            SignalValue::Binary(bytes)
        } else {
            // Contains x/z/X/Z or other values - treat as four-value
            SignalValue::FourValue(s.to_string())
        }
    }
    
    /// Convert to integer if possible
    pub fn to_int(&self) -> Option<u64> {
        match self {
            SignalValue::Binary(bits) => {
                if bits.len() > 64 {
                    return None; // Too large for u64
                }
                let mut val = 0u64;
                for (i, &bit) in bits.iter().rev().enumerate() {
                    if bit == 1 {
                        val |= 1u64 << i;
                    }
                }
                Some(val)
            }
            _ => None,
        }
    }
    
    /// Convert to string representation
    pub fn to_string_repr(&self) -> String {
        match self {
            SignalValue::Binary(bits) => {
                bits.iter().map(|&b| if b == 1 { '1' } else { '0' }).collect()
            }
            SignalValue::FourValue(s) => s.clone(),
            SignalValue::Real(r) => r.to_string(),
            SignalValue::String(s) => s.clone(),
        }
    }
}

/// Signal change (time, value) pair
#[derive(Debug, Clone)]
pub struct SignalChange {
    pub time: u64,
    pub value: SignalValue,
}

/// Signal structure containing all transitions
#[derive(Debug, Clone)]
pub struct Signal {
    pub changes: Vec<SignalChange>,
}

impl Signal {
    pub fn new() -> Self {
        Signal {
            changes: Vec::new(),
        }
    }
    
    /// Add a change to the signal
    pub fn add_change(&mut self, time: u64, value: SignalValue) {
        self.changes.push(SignalChange { time, value });
    }
    
    /// Get value at specific time using binary search
    pub fn value_at_time(&self, time: u64) -> Option<&SignalValue> {
        if self.changes.is_empty() {
            return None;
        }
        
        // Binary search for the last change at or before the given time
        let idx = match self.changes.binary_search_by_key(&time, |c| c.time) {
            Ok(idx) => idx,
            Err(idx) => {
                if idx == 0 {
                    return None; // Time is before first change
                }
                idx - 1
            }
        };
        
        Some(&self.changes[idx].value)
    }
    
    /// Get value at specific index
    pub fn value_at_idx(&self, idx: usize) -> Option<&SignalValue> {
        self.changes.get(idx).map(|c| &c.value)
    }
    
    /// Iterator over all signal transitions
    pub fn all_changes(&self) -> impl Iterator<Item = (u64, &SignalValue)> {
        self.changes.iter().map(|c| (c.time, &c.value))
    }
    
    /// Iterator over changes after a specific time
    pub fn all_changes_after(&self, start_time: u64) -> impl Iterator<Item = (u64, &SignalValue)> {
        let start_idx = self.changes.binary_search_by_key(&start_time, |c| c.time)
            .unwrap_or_else(|idx| idx);
        
        self.changes[start_idx..].iter().map(|c| (c.time, &c.value))
    }
    
    /// Query signal at specific time
    pub fn query_signal(&self, query_time: u64) -> QueryResult {
        if self.changes.is_empty() {
            return QueryResult {
                value: None,
                actual_time: None,
                next_idx: None,
                next_time: None,
            };
        }
        
        let idx = match self.changes.binary_search_by_key(&query_time, |c| c.time) {
            Ok(idx) => {
                // Exact match
                let next_idx = if idx + 1 < self.changes.len() {
                    Some(idx + 1)
                } else {
                    None
                };
                let next_time = next_idx.map(|i| self.changes[i].time);
                
                return QueryResult {
                    value: Some(self.changes[idx].value.clone()),
                    actual_time: Some(self.changes[idx].time),
                    next_idx,
                    next_time,
                };
            }
            Err(idx) => idx,
        };
        
        if idx == 0 {
            // Query time is before first change
            QueryResult {
                value: None,
                actual_time: None,
                next_idx: Some(0),
                next_time: Some(self.changes[0].time),
            }
        } else {
            // Return the last change before query time
            let prev_idx = idx - 1;
            let next_idx = if idx < self.changes.len() {
                Some(idx)
            } else {
                None
            };
            let next_time = next_idx.map(|i| self.changes[i].time);
            
            QueryResult {
                value: Some(self.changes[prev_idx].value.clone()),
                actual_time: Some(self.changes[prev_idx].time),
                next_idx,
                next_time,
            }
        }
    }
}

/// Query result structure
#[derive(Debug, Clone)]
pub struct QueryResult {
    pub value: Option<SignalValue>,
    pub actual_time: Option<u64>,
    pub next_idx: Option<usize>,
    pub next_time: Option<u64>,
}

/// Time table for compressed time representation
#[derive(Debug, Clone)]
pub struct TimeTable {
    times: Vec<u64>,
}

impl TimeTable {
    pub fn new() -> Self {
        TimeTable { times: Vec::new() }
    }
    
    pub fn from_times(times: Vec<u64>) -> Self {
        TimeTable { times }
    }
    
    pub fn get(&self, idx: usize) -> Option<u64> {
        self.times.get(idx).copied()
    }
    
    pub fn len(&self) -> usize {
        self.times.len()
    }
    
    pub fn is_empty(&self) -> bool {
        self.times.is_empty()
    }
}

// C callback context for signal loading
struct SignalLoadContext {
    signal: Arc<Mutex<Signal>>,
    is_real: bool,
    is_string: bool,
}

// C callback function for FST value changes
unsafe extern "C" fn signal_callback(
    user_data: *mut std::os::raw::c_void,
    time: u64,
    _handle: FstHandle,
    value: *const u8,  // const unsigned char *
) {
    let ctx = &*(user_data as *const SignalLoadContext);
    
    // Convert value to string - FST uses null-terminated strings
    let value_str = if value.is_null() {
        String::new()
    } else {
        // Find the null terminator
        let mut len = 0;
        while *value.add(len) != 0 {
            len += 1;
        }
        
        // Convert to string
        let slice = std::slice::from_raw_parts(value, len);
        String::from_utf8_lossy(slice).to_string()
    };
    
    let signal_value = SignalValue::from_fst_string(&value_str, ctx.is_real, ctx.is_string);
    
    let mut signal = ctx.signal.lock().unwrap();
    signal.add_change(time, signal_value);
}

/// Load signal from FST file
pub fn load_signal_from_fst(
    reader: &FstReader,
    handle: FstHandle,
    is_real: bool,
    is_string: bool,
) -> Result<Signal, String> {
    let signal = Arc::new(Mutex::new(Signal::new()));
    
    // Create context without cloning the Arc
    {
        let ctx = SignalLoadContext {
            signal: signal.clone(),
            is_real,
            is_string,
        };
        
        // Clear all masks and set only the one we want
        reader.clear_fac_process_mask_all();
        reader.set_fac_process_mask(handle);
        
        // Load signal data
        let ctx_ptr = &ctx as *const _ as *mut std::os::raw::c_void;
        if !reader.iterate_blocks(Some(signal_callback), ctx_ptr) {
            return Err("Failed to iterate blocks".to_string());
        }
    } // ctx is dropped here, releasing the clone
    
    // Now we can extract signal from Arc<Mutex>
    let signal = Arc::try_unwrap(signal)
        .map_err(|_| "Failed to unwrap signal Arc")?
        .into_inner()
        .map_err(|_| "Failed to unwrap signal Mutex")?;
    
    Ok(signal)
}

/// Signal source for loading and caching signals
pub struct SignalSource {
    reader: Arc<FstReader>,
    signal_cache: Arc<Mutex<BTreeMap<SignalRef, Arc<Signal>>>>,
}

impl SignalSource {
    pub fn new(reader: Arc<FstReader>) -> Self {
        SignalSource {
            reader,
            signal_cache: Arc::new(Mutex::new(BTreeMap::new())),
        }
    }
    
    /// Load a single signal
    pub fn load_signal(
        &self,
        signal_ref: SignalRef,
        handle: FstHandle,
        is_real: bool,
        is_string: bool,
    ) -> Result<Arc<Signal>, String> {
        // Check cache first
        {
            let cache = self.signal_cache.lock().unwrap();
            if let Some(signal) = cache.get(&signal_ref) {
                return Ok(signal.clone());
            }
        }
        
        // Load signal from FST
        let signal = load_signal_from_fst(&self.reader, handle, is_real, is_string)?;
        let signal_arc = Arc::new(signal);
        
        // Store in cache
        {
            let mut cache = self.signal_cache.lock().unwrap();
            cache.insert(signal_ref, signal_arc.clone());
        }
        
        Ok(signal_arc)
    }
    
    /// Load multiple signals
    pub fn load_signals(
        &self,
        requests: Vec<(SignalRef, FstHandle, bool, bool)>,
        multi_threaded: bool,
    ) -> Vec<(SignalRef, Arc<Signal>)> {
        if multi_threaded {
            use rayon::prelude::*;
            
            requests
                .par_iter()
                .filter_map(|&(ref_id, handle, is_real, is_string)| {
                    self.load_signal(ref_id, handle, is_real, is_string)
                        .ok()
                        .map(|signal| (ref_id, signal))
                })
                .collect()
        } else {
            requests
                .iter()
                .filter_map(|&(ref_id, handle, is_real, is_string)| {
                    self.load_signal(ref_id, handle, is_real, is_string)
                        .ok()
                        .map(|signal| (ref_id, signal))
                })
                .collect()
        }
    }
    
    /// Clear signal cache
    pub fn clear_cache(&self) {
        let mut cache = self.signal_cache.lock().unwrap();
        cache.clear();
    }
    
    /// Unload specific signals from cache
    pub fn unload_signals(&self, refs: &[SignalRef]) {
        let mut cache = self.signal_cache.lock().unwrap();
        for signal_ref in refs {
            cache.remove(signal_ref);
        }
    }
}