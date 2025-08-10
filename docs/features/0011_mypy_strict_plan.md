# Mypy Strict Type Checking Refactoring Plan

## Requirements Analysis

The codebase needs to be refactored to pass `mypy --strict` type checking. Currently there are 306 type errors across 15 files:
- 178 `no-untyped-def` errors (functions missing type annotations)
- 117 `no-untyped-call` errors (calls to untyped functions)
- 11 `type-arg` errors (missing type parameters for generics)

The goal is to add comprehensive type annotations throughout the codebase and enable strict type checking in the Makefile to ensure type safety going forward.

## Codebase Research

### Current Type Checking Configuration
- Uses mypy with Python 3.12
- Has basic mypy.ini configuration with some checks enabled
- Ignores missing imports for pywellen (Rust bindings)
- Current Makefile uses `mypy.ini` config file (not strict mode)

### Error Distribution by File
Major files needing attention:
- `wavescout/waveform_db.py` - Core database interface
- `wavescout/waveform_item_model.py` - Qt model/view  
- `wavescout/signal_names_view.py` - UI components
- `wavescout/persistence.py` - Session management
- `wavescout/vars_view.py` - Variable viewing
- `wavescout/design_tree_view.py` - Design hierarchy

## Implementation Planning

### Phase 1: Fix Core Data Structures and Models

#### File-by-File Changes:

**wavescout/config.py**
- Functions to annotate: `__init__`, `_load_config` 
- Fix generic type parameters for `tuple` type hints
- Add return type annotations (mostly `-> None`)

**wavescout/waveform_db.py**
- Functions to annotate: `__init__`, `_extract_timescale`, `get_timescale`, `get_time_range`
- Add type annotations to nested function `collect_vars_recursive`
- Fix method signatures for `open`, `close`, `is_real`
- Add proper type hints for all public API methods

**wavescout/data_model.py**
- Review and ensure all dataclasses have proper field type annotations
- No errors reported but verify completeness for strict mode

### Phase 2: Fix UI Components and Controllers

**wavescout/waveform_controller.py**
- Add return type annotation to `_setup_shortcuts`

**wavescout/waveform_item_model.py**
- Functions to annotate: `__init__`, `_is_group`, `_is_divider`, `_handle_drop_move`, `_handle_drop_copy`
- Add type annotations for Qt override methods: `canDropMimeData`, `dropMimeData`
- Fix method signatures for drag and drop operations

**wavescout/signal_names_view.py**
- Functions to annotate: `__init__`, `_setup_shortcut`, `_find_items_recursive`, `_select_next`, `_select_previous`
- Add return type annotations for event handlers
- Fix context menu related methods

**wavescout/vars_view.py**
- Classes to annotate: `VarsModel.__init__`, `FuzzyFilterProxyModel.__init__`
- Functions to annotate: `_setup_ui`, `_setup_connections`, `focus_filter`, `clear_filter`
- Add proper type hints for Qt model methods

**wavescout/design_tree_view.py**
- Classes to annotate: `DesignTreeModel.__init__`, `ScopeTreeModel.__init__`
- Functions to annotate: `_setup_ui`, `_update_split_mode_models`, `load_hierarchy`
- Fix generic type parameters for `dict` type hints

### Phase 3: Fix Supporting Modules

**wavescout/waveform_loader.py**
- Add type annotations to `load_wavescout_file` function parameters
- Fix calls to untyped `WaveformDB` methods

**wavescout/signal_sampling.py**
- Add type annotations to `transitions` function parameters

**wavescout/persistence.py**
- Functions to annotate: `save_session`, `load_session`, `collect_vars_from_scope`
- Fix nested function type annotations
- Add return type annotations for helper methods

**wavescout/signal_renderer.py**
- Add return type annotations to rendering methods
- Fix any untyped helper functions

**wavescout/waveform_canvas.py**
- Add type annotations to event handlers and helper methods
- Ensure Qt override methods have proper signatures

### Phase 4: Update Build Configuration

**Makefile**
- Change typecheck target to use `--strict` flag
- Remove dependency on mypy.ini for strict checking
- Keep mypy.ini for pywellen import ignores

**mypy.ini**
- Update to be compatible with strict mode
- Keep pywellen import ignores
- Consider adding strict mode equivalents as fallback

## File Modification Summary

### Files to Modify (15 files):
1. `wavescout/config.py` - 3 errors
2. `wavescout/waveform_db.py` - 17 errors  
3. `wavescout/waveform_controller.py` - 1 error
4. `wavescout/waveform_loader.py` - 3 errors
5. `wavescout/signal_sampling.py` - 1 error
6. `wavescout/waveform_item_model.py` - 11 errors
7. `wavescout/persistence.py` - 10 errors
8. `wavescout/signal_names_view.py` - 100+ errors
9. `wavescout/signal_renderer.py` - 40+ errors
10. `wavescout/waveform_canvas.py` - 50+ errors
11. `wavescout/value_format.py` - 4 errors
12. `wavescout/markers.py` - 8 errors
13. `wavescout/vars_view.py` - 20+ errors
14. `wavescout/design_tree_view.py` - 20+ errors
15. `Makefile` - Update typecheck target

### Type Annotation Patterns to Apply:

1. **Constructor methods**: Add `-> None` annotation
2. **Qt override methods**: Match parent class signatures exactly
3. **Event handlers**: Typically `-> None` or `-> bool`
4. **Generic types**: Add type parameters like `tuple[str, ...]`, `dict[str, Any]`
5. **Nested functions**: Add full type annotations including parameters and return
6. **Property methods**: Add appropriate return type annotations

## Testing Strategy

1. Run `mypy --strict wavescout/` after each file is fixed
2. Verify error count decreases progressively
3. Run existing tests to ensure no runtime regressions
4. Test UI functionality manually for Qt-related changes

## Notes

- Priority should be given to public API methods and core data structures
- Qt method signatures must match parent class exactly to avoid runtime issues
- Use `Any` sparingly - prefer specific types where possible
- Consider using `Protocol` for pywellen types if needed