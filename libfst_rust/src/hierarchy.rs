use std::collections::HashMap;
use std::sync::Arc;

use crate::ffi::{
    self, FstHandle, FstReader, FST_HT_SCOPE, FST_HT_UPSCOPE, FST_HT_VAR,
    FST_HT_ATTRBEGIN, FST_HT_ATTREND, FST_HT_TREEBEGIN, FST_HT_TREEEND,
    FST_ST_VCD_BEGIN, FST_ST_VCD_FORK, FST_ST_VCD_FUNCTION, FST_ST_VCD_GENERATE,
    FST_ST_VCD_MODULE, FST_ST_VCD_TASK, FST_VD_IMPLICIT, FST_VD_INOUT, FST_VD_INPUT,
    FST_VD_OUTPUT, FST_VT_VCD_EVENT, FST_VT_VCD_INTEGER, FST_VT_VCD_PARAMETER,
    FST_VT_VCD_PORT, FST_VT_VCD_REAL, FST_VT_VCD_REAL_PARAMETER, FST_VT_VCD_REG,
    FST_VT_VCD_REALTIME, FST_VT_VCD_SPARRAY, FST_VT_VCD_STRING, FST_VT_GEN_STRING,
    FST_VT_VCD_SUPPLY0, FST_VT_VCD_SUPPLY1, FST_VT_VCD_TIME,
    FST_VT_VCD_TRI, FST_VT_VCD_TRI0, FST_VT_VCD_TRI1, FST_VT_VCD_TRIAND,
    FST_VT_VCD_TRIOR, FST_VT_VCD_TRIREG, FST_VT_VCD_WAND, FST_VT_VCD_WIRE,
    FST_VT_VCD_WOR, FST_VT_SV_BIT, FST_VT_SV_LOGIC, FST_VT_SV_INT, FST_VT_SV_SHORTINT,
    FST_VT_SV_LONGINT, FST_VT_SV_BYTE, FST_VT_SV_ENUM, FST_VT_SV_SHORTREAL,
};

/// Reference types for efficient indexing
#[derive(Debug, Copy, Clone, Hash, Eq, PartialEq, Ord, PartialOrd)]
pub struct SignalRef(pub usize);

#[derive(Debug, Copy, Clone, Hash, Eq, PartialEq, Ord, PartialOrd)]
pub struct ScopeRef(pub usize);

#[derive(Debug, Copy, Clone, Hash, Eq, PartialEq, Ord, PartialOrd)]
pub struct VarRef(pub usize);

/// Variable index for bit ranges
#[derive(Debug, Clone)]
pub struct VarIndex {
    pub msb: i32,
    pub lsb: i32,
}

impl VarIndex {
    pub fn new(msb: i32, lsb: i32) -> Self {
        VarIndex { msb, lsb }
    }
}

/// Scope type enumeration
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ScopeType {
    Module,
    Task,
    Function,
    Begin,
    Fork,
    Generate,
    Struct,
    Union,
    Class,
    Interface,
    Package,
    Program,
    VhdlArchitecture,
    VhdlProcedure,
    VhdlFunction,
    VhdlRecord,
    VhdlProcess,
    VhdlBlock,
    VhdlForGenerate,
    VhdlIfGenerate,
    VhdlGenerate,
    VhdlPackage,
    GhwGeneric,
    VhdlArray,
    Unknown,
}

impl ScopeType {
    fn from_fst(typ: u8) -> Self {
        match typ {
            FST_ST_VCD_MODULE => ScopeType::Module,
            FST_ST_VCD_TASK => ScopeType::Task,
            FST_ST_VCD_FUNCTION => ScopeType::Function,
            FST_ST_VCD_BEGIN => ScopeType::Begin,
            FST_ST_VCD_FORK => ScopeType::Fork,
            FST_ST_VCD_GENERATE => ScopeType::Generate,
            _ => ScopeType::Unknown,
        }
    }
}

/// Variable type enumeration
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum VarType {
    Event,
    Integer,
    Parameter,
    Real,
    Reg,
    Supply0,
    Supply1,
    Time,
    Tri,
    TriAnd,
    TriOr,
    TriReg,
    Tri0,
    Tri1,
    WAnd,
    Wire,
    WOr,
    String,
    Port,
    SparseArray,
    RealTime,
    Bit,
    Logic,
    Int,
    ShortInt,
    LongInt,
    Byte,
    Enum,
    ShortReal,
    Boolean,
    BitVector,
    StdLogic,
    StdLogicVector,
    StdULogic,
    StdULogicVector,
}

impl VarType {
    fn from_fst(typ: u8) -> Self {
        match typ {
            FST_VT_VCD_EVENT => VarType::Event,
            FST_VT_VCD_INTEGER => VarType::Integer,
            FST_VT_VCD_PARAMETER => VarType::Parameter,
            FST_VT_VCD_REAL | FST_VT_VCD_REAL_PARAMETER => VarType::Real,
            FST_VT_VCD_REG => VarType::Reg,
            FST_VT_VCD_SUPPLY0 => VarType::Supply0,
            FST_VT_VCD_SUPPLY1 => VarType::Supply1,
            FST_VT_VCD_TIME => VarType::Time,
            FST_VT_VCD_TRI => VarType::Tri,
            FST_VT_VCD_TRIAND => VarType::TriAnd,
            FST_VT_VCD_TRIOR => VarType::TriOr,
            FST_VT_VCD_TRIREG => VarType::TriReg,
            FST_VT_VCD_TRI0 => VarType::Tri0,
            FST_VT_VCD_TRI1 => VarType::Tri1,
            FST_VT_VCD_WAND => VarType::WAnd,
            FST_VT_VCD_WIRE => VarType::Wire,
            FST_VT_VCD_WOR => VarType::WOr,
            FST_VT_VCD_STRING | FST_VT_GEN_STRING => VarType::String,
            FST_VT_VCD_PORT => VarType::Port,
            FST_VT_VCD_SPARRAY => VarType::SparseArray,
            FST_VT_VCD_REALTIME => VarType::RealTime,
            FST_VT_SV_BIT => VarType::Bit,
            FST_VT_SV_LOGIC => VarType::Logic,
            FST_VT_SV_INT => VarType::Int,
            FST_VT_SV_SHORTINT => VarType::ShortInt,
            FST_VT_SV_LONGINT => VarType::LongInt,
            FST_VT_SV_BYTE => VarType::Byte,
            FST_VT_SV_ENUM => VarType::Enum,
            FST_VT_SV_SHORTREAL => VarType::ShortReal,
            _ => VarType::Wire, // Default to wire for unknown types
        }
    }
    
    pub fn is_real(&self) -> bool {
        matches!(self, VarType::Real | VarType::RealTime | VarType::ShortReal)
    }
    
    pub fn is_string(&self) -> bool {
        matches!(self, VarType::String)
    }
}

/// Variable direction
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum VarDirection {
    Unknown,
    Implicit,
    Input,
    Output,
    InOut,
    Buffer,
    Linkage,
}

impl VarDirection {
    fn from_fst(dir: u8) -> Self {
        match dir {
            FST_VD_IMPLICIT => VarDirection::Implicit,
            FST_VD_INPUT => VarDirection::Input,
            FST_VD_OUTPUT => VarDirection::Output,
            FST_VD_INOUT => VarDirection::InOut,
            _ => VarDirection::Unknown,
        }
    }
}

/// Scope structure
#[derive(Debug, Clone)]
pub struct Scope {
    pub name: String,
    pub scope_type: ScopeType,
    pub parent: Option<ScopeRef>,
    pub children: Vec<ScopeRef>,
    pub vars: Vec<VarRef>,
}

impl Scope {
    fn new(name: String, scope_type: ScopeType, parent: Option<ScopeRef>) -> Self {
        Scope {
            name,
            scope_type,
            parent,
            children: Vec::new(),
            vars: Vec::new(),
        }
    }
}

/// Variable structure
#[derive(Debug, Clone)]
pub struct Var {
    pub name: String,
    pub var_type: VarType,
    pub direction: VarDirection,
    pub length: Option<u32>,
    pub signal_ref: SignalRef,
    pub index: Option<VarIndex>,
    pub scope: Option<ScopeRef>,
    pub fst_handle: FstHandle,
}

impl Var {
    fn new(
        name: String,
        var_type: VarType,
        direction: VarDirection,
        length: Option<u32>,
        signal_ref: SignalRef,
        fst_handle: FstHandle,
        scope: Option<ScopeRef>,
    ) -> Self {
        // Parse bit range from name if present
        let (clean_name, index) = parse_bit_range(&name);
        
        Var {
            name: clean_name,
            var_type,
            direction,
            length,
            signal_ref,
            index,
            scope,
            fst_handle,
        }
    }
    
    pub fn is_real(&self) -> bool {
        self.var_type.is_real()
    }
    
    pub fn is_string(&self) -> bool {
        self.var_type.is_string()
    }
    
    pub fn is_1bit(&self) -> bool {
        // Strings and real values are never 1-bit wires
        if self.is_string() || self.is_real() {
            return false;
        }
        self.length.unwrap_or(1) == 1
    }
    
    pub fn bitwidth(&self) -> Option<u32> {
        self.length
    }
}

/// Parse bit range from signal name
fn parse_bit_range(name: &str) -> (String, Option<VarIndex>) {
    if let Some(idx) = name.rfind('[') {
        if let Some(end_idx) = name.rfind(']') {
            if end_idx > idx {
                let base = name[..idx].to_string();
                let range = &name[idx + 1..end_idx];
                
                // Parse range like "7:0" or "15:8"
                if let Some(colon_idx) = range.find(':') {
                    let msb_str = &range[..colon_idx];
                    let lsb_str = &range[colon_idx + 1..];
                    
                    if let (Ok(msb), Ok(lsb)) = (msb_str.parse::<i32>(), lsb_str.parse::<i32>()) {
                        return (base, Some(VarIndex::new(msb, lsb)));
                    }
                }
                
                // Parse single index like "[0]"
                if let Ok(idx) = range.parse::<i32>() {
                    return (base, Some(VarIndex::new(idx, idx)));
                }
            }
        }
    }
    
    (name.to_string(), None)
}

/// Timescale unit
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TimescaleUnit {
    Zeptoseconds,
    Attoseconds,
    Femtoseconds,
    Picoseconds,
    Nanoseconds,
    Microseconds,
    Milliseconds,
    Seconds,
    Unknown,
}

impl TimescaleUnit {
    pub fn from_exponent(exp: i8) -> Self {
        match exp {
            -21 => TimescaleUnit::Zeptoseconds,
            -18 => TimescaleUnit::Attoseconds,
            -15 => TimescaleUnit::Femtoseconds,
            -12 => TimescaleUnit::Picoseconds,
            -9 => TimescaleUnit::Nanoseconds,
            -6 => TimescaleUnit::Microseconds,
            -3 => TimescaleUnit::Milliseconds,
            0 => TimescaleUnit::Seconds,
            _ => TimescaleUnit::Unknown,
        }
    }
    
    pub fn to_exponent(&self) -> Option<i8> {
        match self {
            TimescaleUnit::Zeptoseconds => Some(-21),
            TimescaleUnit::Attoseconds => Some(-18),
            TimescaleUnit::Femtoseconds => Some(-15),
            TimescaleUnit::Picoseconds => Some(-12),
            TimescaleUnit::Nanoseconds => Some(-9),
            TimescaleUnit::Microseconds => Some(-6),
            TimescaleUnit::Milliseconds => Some(-3),
            TimescaleUnit::Seconds => Some(0),
            TimescaleUnit::Unknown => None,
        }
    }
}

/// Timescale structure
#[derive(Debug, Clone)]
pub struct Timescale {
    pub factor: u32,
    pub unit: TimescaleUnit,
}

impl Timescale {
    pub fn new(factor: u32, unit: TimescaleUnit) -> Self {
        Timescale { factor, unit }
    }
    
    pub fn from_fst_exponent(exp: i8) -> Self {
        // FST stores timescale as power of 10
        // e.g., -9 = nanoseconds, -12 = picoseconds
        let unit = TimescaleUnit::from_exponent(exp);
        Timescale { factor: 1, unit }
    }
}

/// Main hierarchy structure
pub struct Hierarchy {
    pub scopes: Vec<Scope>,
    pub vars: Vec<Var>,
    pub path_to_var: HashMap<String, VarRef>,
    pub signal_ref_map: HashMap<FstHandle, SignalRef>,
    pub timescale: Option<Timescale>,
    pub date: String,
    pub version: String,
    pub file_format: String,
}

impl Hierarchy {
    /// Build hierarchy from FST reader
    pub fn from_fst(reader: &FstReader) -> Result<Self, String> {
        let mut hierarchy = Hierarchy {
            scopes: Vec::new(),
            vars: Vec::new(),
            path_to_var: HashMap::new(),
            signal_ref_map: HashMap::new(),
            timescale: None,
            date: reader.date(),
            version: reader.version(),
            file_format: "FST".to_string(),
        };
        
        // Set timescale
        let ts_exp = reader.timescale();
        if ts_exp != 0 {
            hierarchy.timescale = Some(Timescale::from_fst_exponent(ts_exp));
        }
        
        // Build hierarchy by iterating FST structure
        let mut scope_stack: Vec<ScopeRef> = Vec::new();
        let mut current_path = Vec::new();
        let mut signal_counter = 0usize;
        
        // Rewind to start
        reader.rewind_hier();
        loop {
            let hier_ptr = reader.iterate_hier()?;
            if hier_ptr.is_null() {
                break;
            }
            
            let hier = unsafe { &*hier_ptr };
            
            match hier.htyp {
                FST_HT_SCOPE => {
                    // Enter new scope - access union safely
                    let scope_data = unsafe { hier.u.scope };
                    
                    // Check for null pointers before dereferencing
                    if scope_data.name.is_null() {
                        // Skip null scope names
                        continue;
                    }
                    
                    let name = unsafe { ffi::c_str_to_string(scope_data.name, scope_data.name_length) };
                    let scope_type = ScopeType::from_fst(scope_data.typ);
                    
                    let parent = scope_stack.last().copied();
                    let scope_ref = ScopeRef(hierarchy.scopes.len());
                    
                    hierarchy.scopes.push(Scope::new(name.clone(), scope_type, parent));
                    
                    // Update parent's children
                    if let Some(parent_ref) = parent {
                        hierarchy.scopes[parent_ref.0].children.push(scope_ref);
                    }
                    
                    scope_stack.push(scope_ref);
                    current_path.push(name);
                }
                
                FST_HT_UPSCOPE => {
                    // Exit current scope
                    scope_stack.pop();
                    current_path.pop();
                }
                
                FST_HT_VAR => {
                    // Add variable
                    let var_data = unsafe { hier.u.var };
                    let name = unsafe { ffi::c_str_to_string(var_data.name, var_data.name_length) };
                    let var_type = VarType::from_fst(var_data.typ);
                    let direction = VarDirection::from_fst(var_data.direction);
                    let length = if var_data.length > 0 {
                        Some(var_data.length)
                    } else {
                        None
                    };
                    
                    // Check if this is an alias
                    let signal_ref = if let Some(&existing_ref) = hierarchy.signal_ref_map.get(&var_data.handle) {
                        existing_ref
                    } else {
                        let new_ref = SignalRef(signal_counter);
                        hierarchy.signal_ref_map.insert(var_data.handle, new_ref);
                        signal_counter += 1;
                        new_ref
                    };
                    
                    let scope = scope_stack.last().copied();
                    let var_ref = VarRef(hierarchy.vars.len());
                    
                    // Create the variable (which will parse and clean the name)
                    let var = Var::new(
                        name.clone(),
                        var_type,
                        direction,
                        length,
                        signal_ref,
                        var_data.handle,
                        scope,
                    );
                    
                    // Build full path for lookup using the cleaned name
                    let mut full_path = current_path.clone();
                    full_path.push(var.name.clone());
                    let path_str = full_path.join(".");
                    
                    hierarchy.vars.push(var);
                    hierarchy.path_to_var.insert(path_str, var_ref);
                    
                    // Update scope's vars
                    if let Some(scope_ref) = scope {
                        hierarchy.scopes[scope_ref.0].vars.push(var_ref);
                    }
                }
                
                FST_HT_ATTRBEGIN => {
                    // Skip attributes for now
                }
                
                FST_HT_ATTREND => {
                    // Skip attributes for now
                }
                
                FST_HT_TREEBEGIN => {
                    // Skip tree markers for now
                }
                
                FST_HT_TREEEND => {
                    // Skip tree markers for now
                }
                
                _ => {
                    // Unknown hierarchy type - skip
                }
            }
        }
        
        Ok(hierarchy)
    }
    
    pub fn all_vars(&self) -> impl Iterator<Item = &Var> {
        self.vars.iter()
    }
    
    pub fn top_scopes(&self) -> impl Iterator<Item = &Scope> {
        self.scopes.iter().filter(|s| s.parent.is_none())
    }
    
    pub fn get_var(&self, var_ref: VarRef) -> Option<&Var> {
        self.vars.get(var_ref.0)
    }
    
    pub fn get_scope(&self, scope_ref: ScopeRef) -> Option<&Scope> {
        self.scopes.get(scope_ref.0)
    }
    
    pub fn var_by_path(&self, path: &str) -> Option<&Var> {
        self.path_to_var.get(path).and_then(|&var_ref| self.get_var(var_ref))
    }
    
    pub fn var_full_name(&self, var: &Var) -> String {
        let mut path = Vec::new();
        
        // Build path from variable's scope
        if let Some(scope_ref) = var.scope {
            let mut current_scope = Some(scope_ref);
            while let Some(sr) = current_scope {
                if let Some(scope) = self.get_scope(sr) {
                    path.push(scope.name.clone());
                    current_scope = scope.parent;
                } else {
                    break;
                }
            }
            path.reverse();
        }
        
        // Add variable name (without bit range - it's stored separately in index)
        path.push(var.name.clone());
        
        // Don't add bit range to match pywellen behavior
        path.join(".")
    }
}