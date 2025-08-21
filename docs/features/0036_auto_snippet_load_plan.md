# Feature 0036: Automatic Snippet Loading via Command Line

## 1. Use Cases and Requirements Analysis

### Core Requirements
The user wants to automatically load snippets when launching WaveScout with a waveform file:
```bash
scout.py --load_wave swerv1.vcd DBG_DEC.json IMEM_LMEM.json
```

### Specific Requirements
1. **Command-line arguments**: After `--load_wave <wave_file>`, accept additional arguments as snippet filenames
2. **Snippet location**: JSON files are located in `QStandardPaths.StandardLocation.AppDataLocation/snippets` directory
3. **Loading order**: Snippets must be loaded in the order specified on the command line
4. **Error handling**: If any snippet fails to load, the application must terminate with an error exit code
5. **Sequential processing**: Load waveform first, then apply snippets in order
6. **No remapping**: Use exact signal names from JSON files - no remapping or scope searching
7. **Predictable behavior**: Signals must exist with exact names as stored in snippet or loading fails

### Acceptance Criteria
- `scout.py --load_wave file.vcd snippet1.json snippet2.json` loads the waveform then instantiates snippets
- Snippets are loaded from the AppDataLocation/snippets directory automatically
- If a snippet file doesn't exist or fails to load, the application exits with non-zero code
- If snippet instantiation fails (e.g., signals not found), the application exits with error
- The order of snippet instantiation matches the command-line order

## 2. Codebase Research

### Current Command-Line Argument Handling
**File: `scout.py`** (lines 1915-1920)
- Uses `argparse` for command-line parsing
- Currently supports:
  - `--load_session`: Load a session file
  - `--load_wave`: Load a waveform file
  - `--exit_after_load`: Exit after loading (for testing)

### Snippet Management System
**File: `wavescout/snippet_manager.py`**
- `SnippetManager` class:
  - `_get_snippets_dir()`: Returns `Path(app_data) / "snippets"` using `QStandardPaths.writableLocation`
  - `load_snippets()`: Loads all snippets from disk
  - `get_snippet(name)`: Retrieves a specific snippet by name
  - `Snippet.from_dict(data)`: Creates snippet from JSON dictionary

**File: `wavescout/snippet_dialogs.py`**
- `InstantiateSnippetDialog`: Dialog for remapping and instantiating snippets
  - `_remap_and_validate(new_parent_scope)`: Remaps snippet nodes to target scope
  - `get_remapped_nodes()`: Returns remapped SignalNode objects

### Snippet Instantiation Flow
**File: `scout.py` (lines 1658-1707)**
- `_on_snippet_instantiate()` method:
  1. Shows `InstantiateSnippetDialog` for user interaction
  2. Gets remapped nodes and group name
  3. Wraps nodes in a group
  4. Calls `controller.instantiate_snippet()`

**File: `wavescout/waveform_controller.py`**
- `instantiate_snippet(snippet_nodes, after_id)`: Adds snippet nodes to session

### Loading State Management
**File: `scout.py`**
- `LoadingState` dataclass (lines 59-81): Manages loading-related temporary state
- `_finalize_waveform_load()` (lines 1224-1269): Completes waveform loading
- `exit_after_load` flag: Used for test automation

## 3. Implementation Planning (DRY-Focused)

### Key Principle: Maximum Code Reuse
The implementation will reuse existing components wherever possible to avoid duplicating logic.

### File-by-File Changes

#### **File: `scout.py`**

**1. Modify Command-Line Argument Parsing** (lines 1915-1920)
- **Function**: `main()`
- **Changes**: 
  - Change `--load_wave` to accept wave file and optional snippets:
    ```python
    parser.add_argument("--load_wave", nargs='+', metavar=('WAVE_FILE', 'SNIPPET'), 
                       help="Load waveform file followed by optional snippet files")
    ```
  - Extract wave file (first arg) and snippets (remaining args)

**2. Add CLI Snippet Loading Method**
- **New Method**: `_load_cli_snippets(self, snippet_names: list[str]) -> None`
- **Purpose**: Load and instantiate snippets, reusing existing instantiation logic
- **Location**: Add after `_on_snippet_instantiate()` method
- **Reuses**:
  - `SnippetManager.load_snippet_file()` for loading
  - `InstantiateSnippetDialog._remap_and_validate()` logic (extracted to utility)
  - Existing `controller.instantiate_snippet()` for adding to session
  - Existing group wrapping logic from `_on_snippet_instantiate()`

**3. Modify Waveform Load Finalization** (lines 1224-1269)
- **Function**: `_finalize_waveform_load()`
- **Changes**:
  - After design tree update (line 1269), add:
    ```python
    if self._loading_state.cli_snippets:
        QTimer.singleShot(100, lambda: self._load_cli_snippets(self._loading_state.cli_snippets))
    ```

**4. Update LoadingState** (lines 59-81)
- **Class**: `LoadingState`
- **Changes**: Add field `cli_snippets: List[str] = field(default_factory=list)`

**5. Store CLI Snippets During Initialization** (line 518)
- **Method**: `__init__()`
- **Changes**: 
  ```python
  if isinstance(wave_file, list):
      actual_wave_file = wave_file[0]
      self._loading_state.cli_snippets = wave_file[1:]
      wave_file = actual_wave_file
  ```

#### **File: `wavescout/snippet_manager.py`**

**1. Add Single File Loading Method** (Reuses existing loading logic)
- **New Method**:
  ```python
  def load_snippet_file(self, filename: str) -> Optional[Snippet]:
      """Load a specific snippet file from the snippets directory."""
      json_file = self._snippets_dir / filename
      if not json_file.exists():
          return None
      try:
          with open(json_file, 'r') as f:
              data = json.load(f)
              return Snippet.from_dict(data)
      except Exception as e:
          print(f"Error loading snippet {json_file}: {e}")
          return None
  ```
- **Reuses**: Existing JSON loading and `Snippet.from_dict()` logic

#### **File: `wavescout/snippet_dialogs.py`**

**1. Extract Validation Logic for Reuse**
- **New Static Method** (extract from existing `remap_node` inner function):
  ```python
  @staticmethod
  def validate_and_resolve_nodes(nodes: list[SignalNode], 
                                 waveform_db: WaveformDB) -> list[SignalNode]:
      """Validate signal nodes exist and resolve their handles.
      
      This extracts the validation logic from _remap_and_validate's inner function.
      No remapping - uses exact signal names.
      """
      def validate_node(node: SignalNode) -> SignalNode:
          new_node = node.deep_copy()
          
          if not node.is_group:
              # Resolve handle from waveform database (reuse lines 311-319)
              handle = waveform_db.find_handle_by_path(node.name)
              if handle is None:
                  raise ValueError(f"Signal '{node.name}' not found in waveform")
              new_node.handle = handle
          
          # Recursively validate children (reuse lines 322-324)
          new_node.children = [validate_node(child) for child in node.children]
          for child in new_node.children:
              child.parent = new_node
          
          return new_node
      
      return [validate_node(node) for node in nodes]
  ```
- **Reuses**: Validation and handle resolution logic from lines 311-324 of existing `remap_node`

**2. Refactor Existing Method to Use Extracted Logic**
- **Change** `_remap_and_validate` to separate remapping from validation:
  ```python
  def _remap_and_validate(self, new_parent_scope: str) -> list[SignalNode]:
      """Remap snippet nodes to new scope and validate they exist."""
      if not self.waveform_db:
          raise ValueError("No waveform database available")
      
      old_parent = self.snippet.parent_name
      
      # First remap the names
      remapped_nodes = []
      for node in self.snippet.nodes:
          remapped_nodes.append(self._remap_node_names(node, old_parent, new_parent_scope))
      
      # Then validate and resolve handles using the extracted method
      return self.validate_and_resolve_nodes(remapped_nodes, self.waveform_db)
  
  def _remap_node_names(self, node: SignalNode, old_parent: str, new_parent: str) -> SignalNode:
      """Just remap names without validation."""
      # Lines 292-308 of current implementation, but return without handle resolution
  ```

### NO NEW FILES NEEDED
The implementation will only modify existing files and reuse existing components:
1. Extract validation logic from `_remap_and_validate` for reuse
2. CLI uses `validate_and_resolve_nodes` directly (no remapping)
3. GUI continues using full `_remap_and_validate` (remap + validate)

### Algorithm Simplification

#### CLI Snippet Loading (in `scout.py::_load_cli_snippets`)
```python
def _load_cli_snippets(self, snippet_names: list[str]) -> None:
    """Load and instantiate CLI snippets using exact signal names from JSON."""
    from wavescout.snippet_dialogs import InstantiateSnippetDialog
    
    manager = SnippetManager()
    waveform_db = self.wave_widget.session.waveform_db
    
    for name in snippet_names:
        # Load snippet from file (reuse existing loading)
        snippet = manager.load_snippet_file(name)
        if not snippet:
            print(f"Error: Snippet file not found: {name}", file=sys.stderr)
            sys.exit(1)
        
        # Validate and resolve handles using extracted static method
        try:
            validated_nodes = InstantiateSnippetDialog.validate_and_resolve_nodes(
                snippet.nodes, waveform_db
            )
        except ValueError as e:
            # Enhance error message to include snippet name
            print(f"Error in snippet '{name}': {e}", file=sys.stderr)
            sys.exit(1)
        
        # Create group to wrap snippet (reuse logic from _on_snippet_instantiate)
        group_node = SignalNode(
            name=snippet.name,
            is_group=True,
            children=validated_nodes,
            is_expanded=True
        )
        for child in validated_nodes:
            child.parent = group_node
        
        # Instantiate using existing controller method
        if not self.wave_widget.controller.instantiate_snippet([group_node]):
            print(f"Error: Failed to instantiate snippet: {name}", file=sys.stderr)
            sys.exit(1)
        
        print(f"Successfully loaded snippet: {name}")
```

### Code Reuse Summary
1. **Loading**: Reuses `SnippetManager.load_snippet_file()` (new method using existing logic)
2. **Validation**: Reuses extracted `InstantiateSnippetDialog.validate_and_resolve_nodes()` 
3. **Group Creation**: Reuses exact logic from `_on_snippet_instantiate()`
4. **Instantiation**: Reuses `controller.instantiate_snippet()`
5. **Handle Resolution**: Uses existing `waveform_db.find_handle_by_path()` (inside validation)

### Maximum DRY Achievement
- **Extracted validation logic** from `_remap_and_validate` into a static method
- **Both GUI and CLI** use the same validation/handle resolution code
- **GUI path**: remap names → validate with extracted method
- **CLI path**: skip remapping → validate with extracted method
- **Zero duplicate validation code** between GUI and CLI paths

### Benefits of This Refactoring
1. **Single source of truth** for validation logic
2. **Cleaner separation** between remapping (GUI-only) and validation (shared)
3. **Easier maintenance**: Changes to validation logic automatically apply to both paths
4. **Better testability**: Static method can be unit tested independently
5. **Clearer code**: `_remap_and_validate` now clearly shows two steps: remap then validate

### Error Handling Strategy

1. **Missing Snippet File**: Print `"Error: Snippet file not found: <filename>"`, exit(1)
2. **Invalid Snippet JSON**: Print `"Error: Failed to parse snippet: <filename>"`, exit(1)
3. **Signal Not Found**: Print `"Error: Signal '<signal_name>' from snippet '<snippet_name>' not found in waveform"`, exit(1)
4. **Instantiation Failure**: Print `"Error: Failed to instantiate snippet: <name>"`, exit(1)

### Exit Code Convention
- 0: Success
- 1: General error (snippet not found, parse error, mapping failure)
- 2: Waveform load error (existing behavior)

### Performance Considerations

- Snippet loading is I/O bound but files are small (< 100KB typically)
- Signal validation requires checking existence in waveform database
- Use existing `waveform_db.find_handle_by_path()` for validation
- No significant performance impact expected

### Testing Approach

1. Create test snippets in test fixtures
2. Test successful multi-snippet loading
3. Test error cases (missing file, invalid signals)
4. Test exit codes for various failure modes
5. Verify snippet instantiation order matches command-line order