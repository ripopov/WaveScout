use std::ffi::{CStr, CString};
use std::os::raw::{c_char, c_int, c_uint, c_void};
use std::ptr;

// FFI type definitions matching fstapi.h
pub type FstHandle = u32;
pub type FstReaderContext = *mut c_void;
pub type FstWriterContext = *mut c_void;

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

#[repr(C)]
#[derive(Copy, Clone)]
pub struct FstHierScope {
    pub typ: u8,                      // FST_ST_MIN ... FST_ST_MAX
    pub name: *const c_char,
    pub component: *const c_char,
    pub name_length: u32,             // strlen(u.scope.name)
    pub component_length: u32,        // strlen(u.scope.component)
}

#[repr(C)]
#[derive(Copy, Clone)]
pub struct FstHierVar {
    pub typ: u8,                      // FST_VT_MIN ... FST_VT_MAX
    pub direction: u8,                // FST_VD_MIN ... FST_VD_MAX
    pub svt_workspace: u8,            // zeroed out by FST reader
    pub sdt_workspace: u8,            // zeroed out by FST reader
    pub sxt_workspace: u32,           // zeroed out by FST reader
    pub name: *const c_char,
    pub length: u32,
    pub handle: FstHandle,
    pub name_length: u32,             // strlen(u.var.name)
    pub is_alias: u32,                // Using u32 for bitfield
}

// Hierarchy types
pub const FST_HT_SCOPE: u8 = 0;
pub const FST_HT_UPSCOPE: u8 = 1;
pub const FST_HT_VAR: u8 = 2;
pub const FST_HT_ATTRBEGIN: u8 = 3;
pub const FST_HT_ATTREND: u8 = 4;
pub const FST_HT_TREEBEGIN: u8 = 5;
pub const FST_HT_TREEEND: u8 = 6;

// Scope types
pub const FST_ST_VCD_MODULE: u8 = 0;
pub const FST_ST_VCD_TASK: u8 = 1;
pub const FST_ST_VCD_FUNCTION: u8 = 2;
pub const FST_ST_VCD_BEGIN: u8 = 3;
pub const FST_ST_VCD_FORK: u8 = 4;
pub const FST_ST_VCD_GENERATE: u8 = 5;

// Variable types (from fstapi.h)
pub const FST_VT_VCD_EVENT: u8 = 0;
pub const FST_VT_VCD_INTEGER: u8 = 1;
pub const FST_VT_VCD_PARAMETER: u8 = 2;
pub const FST_VT_VCD_REAL: u8 = 3;
pub const FST_VT_VCD_REG: u8 = 5;  // Note: 4 is FST_VT_VCD_REALTIME in some versions
pub const FST_VT_VCD_SUPPLY0: u8 = 6;
pub const FST_VT_VCD_SUPPLY1: u8 = 7;
pub const FST_VT_VCD_TIME: u8 = 8;
pub const FST_VT_VCD_TRI: u8 = 9;
pub const FST_VT_VCD_TRIAND: u8 = 10;
pub const FST_VT_VCD_TRIOR: u8 = 11;
pub const FST_VT_VCD_TRIREG: u8 = 12;
pub const FST_VT_VCD_TRI0: u8 = 13;
pub const FST_VT_VCD_TRI1: u8 = 14;
pub const FST_VT_VCD_WAND: u8 = 15;
pub const FST_VT_VCD_WIRE: u8 = 16;
pub const FST_VT_VCD_WOR: u8 = 17;
pub const FST_VT_VCD_PORT: u8 = 18;
pub const FST_VT_VCD_SPARRAY: u8 = 19;
pub const FST_VT_VCD_REALTIME: u8 = 20;
pub const FST_VT_GEN_STRING: u8 = 21;
pub const FST_VT_SV_BIT: u8 = 22;
pub const FST_VT_SV_LOGIC: u8 = 23;
pub const FST_VT_SV_INT: u8 = 24;
pub const FST_VT_SV_SHORTINT: u8 = 25;
pub const FST_VT_SV_LONGINT: u8 = 26;
pub const FST_VT_SV_BYTE: u8 = 27;
pub const FST_VT_SV_ENUM: u8 = 28;
pub const FST_VT_SV_SHORTREAL: u8 = 29;
pub const FST_VT_VCD_STRING: u8 = 253;
pub const FST_VT_VCD_REAL_PARAMETER: u8 = 254;  // Not sure about this one

// Variable directions
pub const FST_VD_IMPLICIT: u8 = 0;
pub const FST_VD_INPUT: u8 = 1;
pub const FST_VD_OUTPUT: u8 = 2;
pub const FST_VD_INOUT: u8 = 3;

// Callback type for value changes (matches fstReaderIterBlocks callback)
pub type FstValueChangeCb = unsafe extern "C" fn(
    user_data: *mut c_void,
    time: u64,
    handle: FstHandle,
    value: *const u8,  // const unsigned char *
);

// FFI function declarations
extern "C" {
    // Reader functions
    pub fn fstReaderOpen(filename: *const c_char) -> FstReaderContext;
    pub fn fstReaderOpenForUtilitiesOnly() -> FstReaderContext;
    pub fn fstReaderClose(ctx: FstReaderContext);
    
    // Hierarchy iteration
    pub fn fstReaderIterateHier(ctx: FstReaderContext) -> *mut FstHier;
    pub fn fstReaderIterateHierRewind(ctx: FstReaderContext) -> c_int;
    
    // Signal selection
    pub fn fstReaderSetFacProcessMask(ctx: FstReaderContext, facidx: FstHandle);
    pub fn fstReaderClrFacProcessMask(ctx: FstReaderContext, facidx: FstHandle);
    pub fn fstReaderSetFacProcessMaskAll(ctx: FstReaderContext);
    pub fn fstReaderClrFacProcessMaskAll(ctx: FstReaderContext);
    
    // Value iteration
    pub fn fstReaderIterBlocks(
        ctx: FstReaderContext,
        callback: Option<FstValueChangeCb>,
        user_data: *mut c_void,
        vcd_handle: *mut c_void,
    ) -> c_int;
    
    // Metadata
    pub fn fstReaderGetTimescale(ctx: FstReaderContext) -> i8;
    pub fn fstReaderGetStartTime(ctx: FstReaderContext) -> u64;
    pub fn fstReaderGetEndTime(ctx: FstReaderContext) -> u64;
    pub fn fstReaderGetVarCount(ctx: FstReaderContext) -> u32;
    pub fn fstReaderGetMaxHandle(ctx: FstReaderContext) -> FstHandle;
    pub fn fstReaderGetAliasCount(ctx: FstReaderContext) -> u32;
    pub fn fstReaderGetVersionString(ctx: FstReaderContext) -> *const c_char;
    pub fn fstReaderGetDateString(ctx: FstReaderContext) -> *const c_char;
    pub fn fstReaderGetFileType(ctx: FstReaderContext) -> u8;
}

// Safe Rust wrapper
pub struct FstReader {
    ctx: FstReaderContext,
}

// Mark FstReader as Send and Sync since we know the underlying C library
// is thread-safe for read operations
unsafe impl Send for FstReader {}
unsafe impl Sync for FstReader {}

impl FstReader {
    /// Open FST file
    pub fn open(path: &str) -> Result<Self, String> {
        // Validate that file exists
        if !std::path::Path::new(path).exists() {
            return Err(format!("File not found: {}", path));
        }
        
        // Convert to absolute path
        let abs_path = std::path::Path::new(path)
            .canonicalize()
            .map_err(|e| format!("Failed to canonicalize path: {}", e))?;
        
        // On Windows, strip the \\?\ prefix if present
        let path_str = abs_path.to_str()
            .ok_or_else(|| "Path contains invalid UTF-8".to_string())?;
        
        let path_str = if cfg!(windows) && path_str.starts_with(r"\\?\") {
            &path_str[4..]
        } else {
            path_str
        };
        
        
        let c_path = CString::new(path_str).map_err(|e| format!("Invalid path: {}", e))?;
        
        let ctx = unsafe { fstReaderOpen(c_path.as_ptr()) };
        
        if ctx.is_null() {
            Err(format!("Failed to open FST file: {}", path_str))
        } else {
            Ok(FstReader { ctx })
        }
    }
    
    /// Get reader context for FFI calls
    pub fn context(&self) -> FstReaderContext {
        self.ctx
    }
    
    /// Get timescale
    pub fn timescale(&self) -> i8 {
        unsafe { fstReaderGetTimescale(self.ctx) }
    }
    
    /// Get start time
    pub fn start_time(&self) -> u64 {
        unsafe { fstReaderGetStartTime(self.ctx) }
    }
    
    /// Get end time
    pub fn end_time(&self) -> u64 {
        unsafe { fstReaderGetEndTime(self.ctx) }
    }
    
    /// Get variable count
    pub fn var_count(&self) -> u32 {
        unsafe { fstReaderGetVarCount(self.ctx) }
    }
    
    /// Get maximum handle
    pub fn max_handle(&self) -> FstHandle {
        unsafe { fstReaderGetMaxHandle(self.ctx) }
    }
    
    /// Get alias count
    pub fn alias_count(&self) -> u32 {
        unsafe { fstReaderGetAliasCount(self.ctx) }
    }
    
    /// Get version string
    pub fn version(&self) -> String {
        unsafe {
            let ptr = fstReaderGetVersionString(self.ctx);
            if ptr.is_null() {
                String::new()
            } else {
                CStr::from_ptr(ptr).to_string_lossy().trim().to_string()
            }
        }
    }
    
    /// Get date string
    pub fn date(&self) -> String {
        unsafe {
            let ptr = fstReaderGetDateString(self.ctx);
            if ptr.is_null() {
                String::new()
            } else {
                CStr::from_ptr(ptr).to_string_lossy().trim().to_string()
            }
        }
    }
    
    /// Get file type
    pub fn file_type(&self) -> u8 {
        unsafe { fstReaderGetFileType(self.ctx) }
    }
    
    /// Iterate hierarchy
    pub fn iterate_hier(&self) -> Result<*mut FstHier, String> {
        let hier = unsafe { fstReaderIterateHier(self.ctx) };
        Ok(hier)  // Return even if null, let caller handle it
    }
    
    /// Rewind hierarchy iterator
    pub fn rewind_hier(&self) -> bool {
        let result = unsafe { fstReaderIterateHierRewind(self.ctx) };
        result != 0
    }
    
    /// Set facility process mask
    pub fn set_fac_process_mask(&self, handle: FstHandle) {
        unsafe { fstReaderSetFacProcessMask(self.ctx, handle) }
    }
    
    /// Clear all facility process masks
    pub fn clear_fac_process_mask_all(&self) {
        unsafe { fstReaderClrFacProcessMaskAll(self.ctx) }
    }
    
    /// Iterate blocks with callback
    pub fn iterate_blocks(
        &self,
        callback: Option<FstValueChangeCb>,
        user_data: *mut c_void,
    ) -> bool {
        unsafe { fstReaderIterBlocks(self.ctx, callback, user_data, ptr::null_mut()) != 0 }
    }
}

impl Drop for FstReader {
    fn drop(&mut self) {
        if !self.ctx.is_null() {
            unsafe { fstReaderClose(self.ctx) }
        }
    }
}

// Helper to convert C string to Rust string
pub unsafe fn c_str_to_string(ptr: *const c_char, len: u32) -> String {
    if ptr.is_null() {
        String::new()
    } else if len > 0 {
        // Create slice with given length
        let slice = std::slice::from_raw_parts(ptr as *const u8, len as usize);
        // Find actual string end (null terminator or full length)
        let actual_len = slice.iter().position(|&b| b == 0).unwrap_or(len as usize);
        String::from_utf8_lossy(&slice[..actual_len]).trim().to_string()
    } else {
        CStr::from_ptr(ptr).to_string_lossy().to_string()
    }
}