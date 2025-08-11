# Signal Loading Refactoring Plan

## Requirements Analysis

### Core Requirements
- Move signal loading from lazy loading (on-demand during rendering) to eager loading with progress indication
- Use thread pool worker thread for signal loading to avoid blocking Qt main thread
- Show modal progress dialog with "Loading signals..." message before loading starts
- Start loading immediately after showing dialog
- Auto-close dialog when loading completes
- Cache loaded signals in `waveform_db` for instant access during rendering
- Use most efficient pywellen API: `load_signals_multithreaded()`

### Performance Requirements
- `get_signal()` is expensive and can take significant time for large waveforms
- Must not block Qt event loop/main thread
- Batch loading of multiple signals should use multithreaded API
- Loading should happen once per signal, then be cached

### User Experience Requirements
- User double-clicks signal in design tree or presses 'i' shortcut
- Modal popup appears immediately showing loading progress
- UI remains responsive during loading
- User cannot interact with other UI elements until loading completes

## Codebase Research

### Current Signal Loading Flow
1. User double-clicks or presses 'i' in `DesignTreeView`
2. `_on_tree_double_click()` or keyboard handler emits `signals_selected` signal
3. `scout.py::_on_signals_selected()` receives signal nodes
4. `_add_node_to_session()` adds nodes to session
5. Signal rendering happens later, calling `waveform_db.get_signal()` lazily
6. `get_signal()` loads signal on first access (blocking operation)

### Key Components
- **`wavescout/waveform_db.py`**: Contains `get_signal()` method with lazy loading and caching
- **`wavescout/design_tree_view.py`**: Emits `signals_selected` signal
- **`scout.py`**: Handles `_on_signals_selected()` connection
- **`wavescout/signal_renderer.py`**: Calls `get_signal()` during rendering
- **`LoaderRunnable` class in `scout.py`**: Existing pattern for background loading

## Implementation Planning

### File-by-File Changes

#### 1. `wavescout/waveform_db.py`
- **New Methods to Add**:
  - `preload_signals(handles: List[SignalHandle]) -> None`: Loads multiple signals using thread-safe batch API
  - `preload_signals_for_vars(vars: List[Var]) -> None`: Wrapper for pywellen's `load_signals_multithreaded`
  - `are_signals_cached(handles: List[SignalHandle]) -> bool`: Check if all signals are already cached
  
- **Modifications**:
  - Keep existing `get_signal()` method unchanged for backward compatibility
  - Ensure `_signal_cache` is accessed thread-safely

#### 2. `scout.py`
- **Class: `SignalLoaderRunnable(QRunnable)`**:
  - New runnable class similar to existing `LoaderRunnable`
  - Takes waveform_db and list of signal handles
  - Calls `waveform_db.preload_signals()` in background thread
  
- **Method: `_on_signals_selected()`**:
  - Extract signal handles from nodes
  - Check if signals are already cached
  - If not cached:
    - Create and show QProgressDialog
    - Create SignalLoaderRunnable
    - Connect completion signal to dialog close and actual node addition
  - If cached:
    - Add nodes immediately as before

- **Method: `_load_signals_async(signal_nodes)`**:
  - New method to handle async signal loading
  - Shows progress dialog
  - Runs SignalLoaderRunnable
  - On completion, adds nodes to session

#### 3. `wavescout/design_tree_view.py`
- **No changes needed** - Keep existing signal emission as-is

#### 4. `wavescout/signal_renderer.py`
- **No changes needed** - Will benefit from pre-cached signals automatically

## Algorithm Description

### Signal Loading Algorithm
```
1. User triggers signal addition (double-click or 'i' key)
2. Extract handles from selected signal nodes
3. Check cache status:
   if all_signals_cached:
       add_nodes_to_session()
       return
4. Show modal progress dialog immediately
5. Process Qt events to ensure dialog renders
6. Create runnable with:
   - waveform_db reference
   - list of signal handles needing load
7. In background thread:
   - Convert handles to Var objects
   - Call waveform.load_signals_multithreaded(vars)
   - Store results in _signal_cache
8. On completion (main thread):
   - Close progress dialog
   - Add nodes to session
   - Emit layout changed signal
9. On error:
   - Close progress dialog
   - Show error message
   - Don't add nodes
```

### Cache Management
- Signals remain cached for session lifetime
- Cache cleared only on waveform close/reload
- Thread-safe access using existing cache dictionary

## UI Integration

### Progress Dialog
- Modal dialog with indeterminate progress bar
- Title: "Loading Signals"
- Message: "Loading N signal(s)..."
- No cancel button (operation is atomic)
- Auto-close on completion

### Error Handling
- If loading fails, show QMessageBox with error details
- Status bar shows "Failed to load signals"
- Nodes not added to session on failure

## Performance Considerations

### Batch Loading Optimization
- Collect all handles before loading
- Single call to `load_signals_multithreaded()` for all signals
- Avoids multiple thread pool submissions

### Cache Hit Optimization
- Check cache before showing dialog
- Skip entire async flow if signals already loaded
- Instant response for cached signals

### Memory Management
- Signals stay cached until waveform close
- No automatic cache eviction (signals are needed for rendering)
- Cache size bounded by number of unique signals in design

### Large File Handling
- Progress dialog prevents UI freeze perception
- Multithreaded loading utilizes multiple CPU cores
- No timeout on loading (some signals can be very large)