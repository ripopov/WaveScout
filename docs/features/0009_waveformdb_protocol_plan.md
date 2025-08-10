# WaveformDB Protocol Implementation Plan

## Requirements Analysis

### Core Problem
The codebase violates encapsulation principles with 8 locations directly accessing the private `_var_map` attribute of WaveformDB. Additionally, 17+ locations use fragile `hasattr` checks to discover database behavior at runtime, creating tight coupling between UI components and the database implementation.

### Specific Requirements
1. Define a typed Protocol interface for WaveformDB operations
2. Replace all `_var_map` direct access with proper API calls  
3. Remove `hasattr` branches throughout the codebase
4. Maintain backward compatibility during migration
5. Enable proper unit testing with mockable interfaces

### Performance Requirements
- No performance degradation from additional abstraction layer
- Maintain O(1) lookup performance for handle-based operations
- Preserve existing caching mechanisms

## Codebase Research

### Files Requiring Direct Refactoring
- **`wavescout/design_tree_view.py`** (lines 261-269): Direct `_var_map` access for signal lookup
- **`wavescout/waveform_item_model.py`** (lines 168-169): Direct `_var_map` access for bitwidth
- **`wavescout/signal_sampling.py`** (lines 180-181): Direct `_var_map` access for bitwidth
- **`tests/test_data_format.py`** (line 210): Test accessing private `_var_map`

### Files with hasattr Checks
- **`wavescout/persistence.py`**: 6 hasattr checks
- **`wavescout/design_tree_view.py`**: 5 hasattr checks  
- **`wavescout/scope_tree_model.py`**: 3 hasattr checks
- **`wavescout/design_tree_model.py`**: 2 hasattr checks
- **`scout.py`**: 1 hasattr check

### Current WaveformDB Public API
Already provides most needed methods:
- `find_handle_by_name(name)` - Find handle by signal name
- `get_handle_for_var(var)` - Get handle for a variable
- `get_var(handle)` - Get first variable for handle
- `get_all_vars_for_handle(handle)` - Get all variables (aliases)
- `iter_handles_and_vars()` - Iterate handle/var pairs
- `get_time_table()` - Get time table
- `get_timescale()` - Get timescale information

## Data Model Design

No changes required to `data_model.py` - this feature focuses on the database interface layer, not the view model.

## Implementation Planning

### File-by-File Changes

#### 1. Create Protocol Definition
**File Path**: `wavescout/protocols.py` (NEW)
- **Classes to Add**: `WaveformDBProtocol` 
- **Nature of Changes**: Define Protocol class with all required method signatures
- **Integration Points**: Will be imported by all components that accept WaveformDB

#### 2. Enhance WaveformDB Public API
**File Path**: `wavescout/waveform_db.py`
- **Functions to Add**:
  - `has_handle(handle) -> bool` - Check if handle exists
  - `find_handle_by_path(path) -> Optional[SignalHandle]` - Find by full path with TOP prefix handling
  - `get_var_bitwidth(handle) -> int` - Get signal bitwidth with default
- **Nature of Changes**: Add public methods that encapsulate `_var_map` access patterns
- **Integration Points**: Used by UI components to replace direct access

#### 3. Refactor Direct Access Points
**File Path**: `wavescout/design_tree_view.py`
- **Functions to Modify**: `_find_signal_handle()`
- **Nature of Changes**: Replace `self.waveform_db._var_map[path]` with `self.waveform_db.find_handle_by_path(path)`
- **Integration Points**: Called during signal selection and drag-drop operations

**File Path**: `wavescout/waveform_item_model.py`  
- **Functions to Modify**: `data()` method in Qt model
- **Nature of Changes**: Replace `db._var_map[node.handle]` with `db.get_var_bitwidth(node.handle)`
- **Integration Points**: Used for displaying signal values in the waveform view

**File Path**: `wavescout/signal_sampling.py`
- **Functions to Modify**: `sample_analog_signal()`
- **Nature of Changes**: Replace `waveform_db._var_map[signal.handle]` with `waveform_db.get_var_bitwidth(signal.handle)`
- **Integration Points**: Used during analog signal rendering

#### 4. Remove hasattr Checks
**File Path**: `wavescout/persistence.py`
- **Functions to Modify**: `save_session()`, `load_session()`
- **Nature of Changes**: Remove all hasattr checks, rely on protocol methods existing
- **Integration Points**: Session save/load functionality

**File Path**: `wavescout/design_tree_view.py`
- **Functions to Modify**: `_create_signal_from_node()`, `_drop_selected_items()`
- **Nature of Changes**: Remove hasattr checks for `get_handle_for_var`, `iter_handles_and_vars`, `get_var`
- **Integration Points**: Signal creation and drag-drop operations

**File Path**: `wavescout/scope_tree_model.py`
- **Functions to Modify**: `set_waveform_db()`, `rowCount()`, `_rebuild_cache()`
- **Nature of Changes**: Remove hasattr checks for `hierarchy` attribute
- **Integration Points**: Scope tree population

**File Path**: `wavescout/design_tree_model.py`
- **Functions to Modify**: `_rebuild_model()`
- **Nature of Changes**: Remove hasattr checks for `hierarchy` and `iter_handles_and_vars`
- **Integration Points**: Design tree model population

#### 5. Update Type Hints
**File Path**: Multiple files using WaveformDB
- **Nature of Changes**: Update type hints from `WaveformDB` to `WaveformDBProtocol` where appropriate
- **Integration Points**: Improves type checking and IDE support

### Algorithm Descriptions

#### Handle Lookup Algorithm (find_handle_by_path)
1. Check if the path exists directly in `_var_map`
2. If not found, prepend "TOP." and check again
3. Return the handle if found, None otherwise
4. This preserves existing behavior while encapsulating the implementation

#### Bitwidth Extraction Algorithm (get_var_bitwidth)
1. Get all variables for the given handle
2. If variables exist and first has bitwidth() method, call it
3. Otherwise return default value of 32
4. This standardizes bitwidth retrieval across the codebase

## Performance Considerations

### Cache Preservation
- All existing caching mechanisms remain unchanged
- Protocol adds no overhead beyond a virtual function call
- Direct dictionary lookups in `_var_map` replaced with method calls that do the same lookup

### Memory Usage
- Protocol definition adds minimal memory overhead (class definition only)
- No additional data structures or caching layers introduced

## Testing Strategy

### Unit Tests
1. Create `tests/test_waveformdb_protocol.py`:
   - Test WaveformDB implements all protocol methods
   - Test new public methods with edge cases
   - Test handle lookup with and without TOP prefix

2. Create mock implementation:
   - `tests/mocks/mock_waveformdb.py` implementing protocol
   - Use for testing UI components in isolation

### Integration Tests
1. Update existing tests to use public API:
   - `tests/test_data_format.py` - Remove `_var_map` access
   - Add tests for refactored components

2. Edge case testing:
   - Missing signals
   - Invalid handles  
   - Empty database
   - Aliased signals