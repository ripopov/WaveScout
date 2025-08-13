use std::sync::Arc;

use crate::ffi::FstReader;
use crate::hierarchy::{Hierarchy, Var};
use crate::signal::{Signal, SignalSource, TimeTable};

/// Main waveform structure
pub struct Waveform {
    pub hierarchy: Arc<Hierarchy>,
    pub wave_source: Option<Arc<SignalSource>>,
    pub time_range: Option<(u64, u64)>,  // (start_time, end_time)
    reader: Option<Arc<FstReader>>,
    multi_threaded: bool,
}

impl Waveform {
    /// Create new waveform from FST file
    pub fn new(
        path: &str,
        multi_threaded: bool,
        _remove_scopes_with_empty_name: bool,
        load_body: bool,
    ) -> Result<Self, String> {
        // Open FST file
        let reader = FstReader::open(path)?;
        let reader_arc = Arc::new(reader);
        
        // Parse hierarchy
        let hierarchy = Hierarchy::from_fst(&reader_arc)?;
        let hierarchy_arc = Arc::new(hierarchy);
        
        let mut waveform = Waveform {
            hierarchy: hierarchy_arc,
            wave_source: None,
            time_range: None,
            reader: Some(reader_arc.clone()),
            multi_threaded,
        };
        
        // Load body if requested
        if load_body {
            waveform.load_body()?;
        }
        
        Ok(waveform)
    }
    
    /// Load waveform body (time range and signal source)
    pub fn load_body(&mut self) -> Result<(), String> {
        if self.wave_source.is_some() {
            return Ok(()); // Already loaded
        }
        
        let reader = self.reader.as_ref()
            .ok_or_else(|| "No reader available".to_string())?;
        
        // Store time range from FST
        let start_time = reader.start_time();
        let end_time = reader.end_time();
        self.time_range = Some((start_time, end_time));
        
        // Create signal source
        let signal_source = SignalSource::new(reader.clone());
        self.wave_source = Some(Arc::new(signal_source));
        
        Ok(())
    }
    
    /// Check if body is loaded
    pub fn body_loaded(&self) -> bool {
        self.wave_source.is_some()
    }
    
    /// Get signal for a variable
    pub fn get_signal(&mut self, var: &Var) -> Result<Arc<Signal>, String> {
        // Ensure body is loaded
        if !self.body_loaded() {
            self.load_body()?;
        }
        
        let wave_source = self.wave_source.as_ref()
            .ok_or_else(|| "Wave source not available".to_string())?;
        
        // Load signal using the variable's FST handle
        wave_source.load_signal(
            var.signal_ref,
            var.fst_handle,
            var.is_real(),
            var.is_string(),
        )
    }
    
    /// Get signal from absolute hierarchy path
    pub fn get_signal_from_path(&mut self, abs_hierarchy_path: &str) -> Result<Arc<Signal>, String> {
        // Clone the variable to avoid borrow issues
        let var = self.hierarchy.var_by_path(abs_hierarchy_path)
            .ok_or_else(|| format!("Variable not found: {}", abs_hierarchy_path))?
            .clone();
        
        self.get_signal(&var)
    }
    
    /// Load multiple signals
    pub fn load_signals(&mut self, vars: &[Var]) -> Result<Vec<Arc<Signal>>, String> {
        // Ensure body is loaded
        if !self.body_loaded() {
            self.load_body()?;
        }
        
        let wave_source = self.wave_source.as_ref()
            .ok_or_else(|| "Wave source not available".to_string())?;
        
        // Prepare load requests
        let requests: Vec<_> = vars.iter()
            .map(|var| (var.signal_ref, var.fst_handle, var.is_real(), var.is_string()))
            .collect();
        
        // Load signals
        let loaded = wave_source.load_signals(requests, false);
        
        // Extract signals in order
        let mut result = Vec::new();
        for var in vars {
            if let Some((_, signal)) = loaded.iter().find(|(ref_id, _)| *ref_id == var.signal_ref) {
                result.push(signal.clone());
            } else {
                return Err(format!("Failed to load signal for {}", var.name));
            }
        }
        
        Ok(result)
    }
    
    /// Load multiple signals with multi-threading
    pub fn load_signals_multithreaded(&mut self, vars: &[Var]) -> Result<Vec<Arc<Signal>>, String> {
        // Ensure body is loaded
        if !self.body_loaded() {
            self.load_body()?;
        }
        
        let wave_source = self.wave_source.as_ref()
            .ok_or_else(|| "Wave source not available".to_string())?;
        
        // Prepare load requests
        let requests: Vec<_> = vars.iter()
            .map(|var| (var.signal_ref, var.fst_handle, var.is_real(), var.is_string()))
            .collect();
        
        // Load signals with multi-threading
        let loaded = wave_source.load_signals(requests, true);
        
        // Extract signals in order
        let mut result = Vec::new();
        for var in vars {
            if let Some((_, signal)) = loaded.iter().find(|(ref_id, _)| *ref_id == var.signal_ref) {
                result.push(signal.clone());
            } else {
                return Err(format!("Failed to load signal for {}", var.name));
            }
        }
        
        Ok(result)
    }
    
    /// Unload signals from cache
    pub fn unload_signals(&self, signal_refs: &[crate::hierarchy::SignalRef]) {
        if let Some(ref wave_source) = self.wave_source {
            wave_source.unload_signals(signal_refs);
        }
    }
}