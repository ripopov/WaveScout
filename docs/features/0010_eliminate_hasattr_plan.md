# Plan: Eliminate hasattr Calls Using WaveformDBProtocol

## Requirements Analysis

The codebase currently uses numerous `hasattr()` checks to dynamically discover available methods on `waveform_db` objects. This creates several issues:
- Tight coupling between UI code and implementation details
- Runtime behavior discovery instead of static type checking
- Reduced code clarity and IDE support
- Fragile code that breaks encapsulation

The goal is to replace all `hasattr()` checks with proper protocol usage, ensuring:
- All waveform_db interactions go through the `WaveformDBProtocol` interface
- Static type checking can verify correctness
- Clear contracts between components
- Better IDE support and documentation

## Codebase Research

### Current hasattr Usage Patterns

1. **Protocol method checks** (15 occurrences):
   - `hasattr(waveform_db, 'hierarchy')` - checking for hierarchy attribute
   - `hasattr(waveform_db, 'get_handle_for_var')` - checking for method existence
   - `hasattr(waveform_db, 'get_var')` - checking for method existence
   - `hasattr(waveform_db, 'iter_handles_and_vars')` - checking for method existence
   - `hasattr(waveform_db, 'get_timescale')` - checking for method existence

2. **Extended methods not in protocol** (4 occurrences):
   - `hasattr(waveform_db, 'file_path')` - property for file location
   - `hasattr(waveform_db, 'get_var_to_handle_mapping')` - for persistence
   - `hasattr(waveform_db, 'get_next_available_handle')` - for persistence
   - `hasattr(waveform_db, 'add_var_with_handle')` - for persistence (not implemented)

3. **Node attribute checks** (multiple occurrences):
   - `hasattr(node, 'var_handle')` - checking design node attributes
   - `hasattr(node, 'var')` - checking design node attributes
   - `hasattr(var, 'var_type')` - checking pywellen Var attributes
   - `hasattr(var, 'is_1bit')` - checking pywellen Var attributes

### Files Requiring Updates

Main files with hasattr usage on waveform_db:
- `wavescout/design_tree_model.py` - 1 occurrence
- `wavescout/design_tree_view.py` - 6 occurrences  
- `wavescout/persistence.py` - 6 occurrences
- `wavescout/scope_tree_model.py` - 3 occurrences
- `scout.py` - 1 occurrence

## Data Model Design

### Protocol Extensions

The `WaveformDBProtocol` needs additional optional methods:

```python
@dataclass
class WaveformDBProtocol(Protocol):
    # Existing required attributes/methods...
    
    # Optional property for file path
    @property
    def file_path(self) -> Optional[str]:
        """Path to the loaded waveform file."""
        ...
    
    # Optional persistence support methods
    def get_var_to_handle_mapping(self) -> Optional[Dict[Var, SignalHandle]]:
        """Get mapping from Var objects to handles for persistence."""
        return None
    
    def get_next_available_handle(self) -> Optional[SignalHandle]:
        """Get next available handle for new signals."""
        return None
```

## Implementation Planning

### File-by-File Changes

#### 1. **wavescout/protocols.py**
- **Functions/Classes to Modify**: `WaveformDBProtocol`
- **Nature of Changes**: 
  - Add `file_path` as an optional property
  - Add `get_var_to_handle_mapping()` as optional method returning None by default
  - Add `get_next_available_handle()` as optional method returning None by default
  - Import Dict type for type hints
- **Integration Points**: Used by all components interacting with waveform_db

#### 2. **wavescout/design_tree_model.py**
- **Functions/Classes to Modify**: `DesignTreeModel.set_waveform_db()`
- **Nature of Changes**:
  - Replace `if not self.waveform_db or not hasattr(self.waveform_db, 'hierarchy'):` 
  - With: `if not self.waveform_db or not self.waveform_db.hierarchy:`
- **Integration Points**: Hierarchy tree building

#### 3. **wavescout/design_tree_view.py**
- **Functions/Classes to Modify**: 
  - `DesignTreeView._handle_double_click()`
  - `DesignTreeView._show_context_menu()`
  - `DesignTreeView._get_signal_display_name()`
- **Nature of Changes**:
  - Remove all `hasattr(self.waveform_db, 'get_handle_for_var')` checks
  - Remove all `hasattr(self.waveform_db, 'get_var')` checks
  - Replace with direct method calls (methods are required by protocol)
  - For node attributes like `var_handle` and `var`, use `getattr()` with defaults
- **Integration Points**: Signal addition and context menu actions

#### 4. **wavescout/persistence.py**
- **Functions/Classes to Modify**:
  - `_resolve_signal_handles()`
  - `save_session_to_file()`
  - `load_session_from_file()`
- **Nature of Changes**:
  - Replace `hasattr(waveform_db, 'hierarchy')` with `waveform_db.hierarchy is not None`
  - Replace `hasattr(waveform_db, 'file_path')` with check for None result
  - Replace optional method checks with None checks on return values
  - Remove `add_var_with_handle` usage (not implemented anyway)
- **Integration Points**: Session saving/loading

#### 5. **wavescout/scope_tree_model.py**
- **Functions/Classes to Modify**:
  - `ScopeTreeModel.set_waveform_db()`
  - `ScopeTreeModel._build_tree()`
  - `ScopeTreeModel._find_scope_by_path()`
- **Nature of Changes**:
  - Replace `hasattr(waveform_db, 'hierarchy')` with `waveform_db.hierarchy is not None`
  - Use direct attribute access since hierarchy is required by protocol
- **Integration Points**: Scope tree building

#### 6. **scout.py**
- **Functions/Classes to Modify**: `MainWindow._update_title()`
- **Nature of Changes**:
  - Replace `hasattr(session.waveform_db, 'file_path')` with None check
  - Use `getattr(session.waveform_db, 'file_path', None)` for safe access
- **Integration Points**: Window title updates

### Algorithm for Safe Migration

For each hasattr check replacement:
1. If checking required protocol method/attribute: Remove check, use directly
2. If checking optional method: Call method and check for None return
3. If checking node attributes: Use `getattr()` with appropriate default
4. For pywellen object attributes: Keep hasattr or use try/except (external API)

## Performance Considerations

- No significant performance impact expected
- Removing dynamic attribute lookups may slightly improve performance
- Protocol conformance checks happen at development time, not runtime

## Testing Strategy

1. Ensure all existing tests pass after changes
2. Verify protocol conformance with existing test_waveformdb_protocol.py
3. Test with files that have and don't have hierarchy
4. Test persistence with various waveform file types
5. Verify type checking with mypy catches any protocol violations