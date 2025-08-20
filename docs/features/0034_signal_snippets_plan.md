# SignalNode Tree Snippets Feature Plan

## 1. Use Cases and Requirements Analysis

### Core Problem
In hardware design, the same module is often instantiated multiple times (e.g., multiple CPU cores, memory controllers). Currently, users must manually:
- Navigate through the design tree to find the same signals in each module instance
- Add signals from each instance separately
- Apply identical formatting and color preferences to each instance
- Repeat this process every time they debug the same design

### Solution: Reusable Signal Snippets
Create a snippet system that allows users to:
1. **Create snippets**: Save a configured group of signals as a reusable template
2. **Store snippets**: Maintain a persistent library of snippets across sessions
3. **Instantiate snippets**: Apply saved snippets to different module instances with scope remapping

### Detailed Requirements

#### Snippet Creation
1. User creates a group (`SignalNode.is_group = true`) containing formatted signals
2. Right-click on group → "Save as snippet" menu option
3. Dialog appears with:
   - Snippet name field (pre-filled with group name)
   - Save and Cancel buttons
4. System automatically determines common parent scope (e.g., "TOP.tb_top.imem")
5. Snippet saved as JSON file with:
   - Parent scope name
   - Signal tree structure (relative names)
   - All formatting/color/display properties
   - Support for nested groups (arbitrary depth)

#### Snippet Storage
- JSON files stored in `QStandardPaths.AppDataLocation / snippets` directory
- Persistent across application sessions
- Shareable between users (import/export capability)

#### Snippet Instantiation
1. Display all snippets in right sidebar (currently empty)
2. Table view with columns: "Snippet Name", "Parent Name", "Number of Nodes"
3. Double-click to instantiate:
   - Dialog for parent scope modification
   - Validation:
     - Parent scope exists in current waveform
     - All signals exist in target scope
   - Insert after selected node in SignalNamesView
   - Error dialog if validation fails

### JSON Format Specification

**Important**: All signal handles in snippet JSON files must be set to `-1` (invalid). Valid handles are waveform-specific and must be resolved during snippet instantiation when the target scope and waveform database are known.

```json
{
  "parent_name": "TOP.tb_top.imem",
  "num_nodes": 4,
  "nodes": [
    {
      "name": "awvalid",
      "handle": -1,  // Always -1 in snippets, resolved during instantiation
      "format": "Binary",
      "nickname": null,
      "children": [],
      "is_group": false,
      "is_expanded": false,
      "height_scaling": 1.0,
      "is_multi_bit": false,
      "color": "#00FF00",
      "render_type": "Digital"
    },
    {
      "name": "awsize",
      "handle": -1,  // Always -1 in snippets
      "format": "Hexadecimal",
      // ... other properties
    }
  ]
}
```

## 2. Codebase Research

### Core Components Analysis

#### Data Model (`wavescout/data_model.py`)
- `SignalNode` dataclass with hierarchical structure via `children` list and `parent` reference
- `is_group` flag identifies group nodes
- `deep_copy()` method generates new instance IDs for copied trees
- All formatting properties preserved: `format`, `nickname`, `color`, `render_type`, `height_scaling`

#### Persistence (`wavescout/persistence.py`)
- Existing `_serialize_node()` and `_deserialize_node()` handle recursive tree serialization
- JSON format with nested structure
- Enum conversions for `DataFormat`, `RenderType`
- Can reuse for snippet serialization with modifications

#### Signal Names View (`wavescout/signal_names_view.py`)
- Context menu in `_show_context_menu()` method (line 136)
- Existing group operations provide pattern for snippet actions
- Uses `QAction` with lambda callbacks

#### Main Window (`scout.py`)
- Right panel exists as `self.right_panel` (QFrame, line 456)
- Currently placeholder content
- Toggle functionality via `toggle_right_sidebar()`
- Splitter-based layout with state persistence

#### Controller (`wavescout/waveform_controller.py`)
- `insert_nodes()` for adding nodes at specific positions
- `group_nodes()` for creating groups
- Event bus notifications for state changes
- Selection management by instance IDs

#### Design Tree (`wavescout/design_tree_view.py`, `wavescout/design_tree_model.py`)
- `navigate_to_scope()` validates scope paths
- `_find_scope_by_path()` for hierarchical path resolution
- Can validate signal existence in waveform database

### Key Findings
1. **Reusable Components**: Existing serialization can be adapted for snippets
2. **UI Integration Points**: Context menu and right panel ready for extension
3. **Validation Infrastructure**: Design tree provides scope validation
4. **Controller Pattern**: Established patterns for tree manipulation

## 3. Implementation Planning

### New Files Required

#### `wavescout/snippet_manager.py`
- **Classes**:
  - `Snippet`: Dataclass for snippet metadata and content
  - `SnippetManager`: Singleton for snippet CRUD operations
- **Functions**:
  - `load_snippets()`: Load all snippets from disk
  - `save_snippet()`: Persist snippet to JSON
  - `delete_snippet()`: Remove snippet file
  - `get_snippets_dir()`: Return snippets directory path
  - `validate_snippet()`: Check snippet compatibility with current waveform

#### `wavescout/snippet_browser_widget.py`
- **Classes**:
  - `SnippetBrowserWidget`: QWidget for right sidebar
  - `SnippetTableModel`: QAbstractTableModel for snippet list
- **Functions**:
  - `_on_double_click()`: Handle snippet instantiation
  - `_refresh_snippets()`: Update display from manager
  - `_show_context_menu()`: Edit/delete operations

#### `wavescout/snippet_dialogs.py`
- **Classes**:
  - `SaveSnippetDialog`: Dialog for saving snippets
  - `InstantiateSnippetDialog`: Dialog for scope remapping
- **Functions**:
  - `validate_name()`: Check snippet name validity
  - `validate_scope()`: Verify scope exists in waveform

### File Modifications

#### `wavescout/signal_names_view.py`
- **Function**: `_show_context_menu()`
  - Add "Save as Snippet" action for groups
  - Connect to new `_save_as_snippet()` handler
- **New Function**: `_save_as_snippet()`
  - Extract selected group
  - Find common parent scope
  - Launch SaveSnippetDialog
  - Call SnippetManager to save

#### `scout.py`
- **Function**: `__init__()`
  - Replace right panel placeholder with SnippetBrowserWidget
  - Connect snippet instantiation signals
- **New Function**: `_instantiate_snippet(snippet)`
  - Launch InstantiateSnippetDialog
  - Validate and remap scope
  - Insert nodes via controller

#### `wavescout/waveform_controller.py`
- **New Function**: `instantiate_snippet(snippet, parent_scope, position)`
  - Remap signal names to new scope
  - Create deep copies with new IDs
  - Validate signals exist in database
  - Call `insert_nodes()` with remapped tree
  - Emit appropriate events

#### `wavescout/persistence.py`
- **New Function**: `serialize_snippet_nodes(nodes)`
  - Adapt `_serialize_node()` for snippet format
  - Strip absolute paths, keep relative names
  - **Set all handles to -1** (snippets are waveform-agnostic)
  - Exclude runtime properties (instance_id)
- **New Function**: `deserialize_snippet_nodes(data, parent_scope, waveform_db)`
  - Reconstruct tree with new scope prefix
  - Generate new instance IDs
  - **Resolve signal handles from waveform_db** based on remapped paths
  - Return None for signals that don't exist in target waveform

### Algorithm: Finding Common Parent Scope

```
function find_common_parent(group_node):
    all_paths = []
    
    function collect_paths(node, paths):
        if not node.is_group:
            paths.append(node.name)
        for child in node.children:
            collect_paths(child, paths)
    
    collect_paths(group_node, all_paths)
    
    if all_paths is empty:
        return ""
    
    # Split all paths by '.'
    split_paths = [path.split('.') for path in all_paths]
    
    # Find common prefix
    common = []
    for i in range(min(len(p) for p in split_paths)):
        if all(p[i] == split_paths[0][i] for p in split_paths):
            common.append(split_paths[0][i])
        else:
            break
    
    return '.'.join(common)
```

### Algorithm: Scope Remapping and Handle Resolution

```
function remap_and_validate(snippet, new_parent_scope, waveform_db):
    old_parent = snippet.parent_name
    remapped_nodes = []
    
    function remap_node(node):
        new_node = node.deep_copy()
        
        if not node.is_group:
            # Replace old parent with new parent in signal name
            relative_name = node.name[len(old_parent)+1:]
            new_name = f"{new_parent_scope}.{relative_name}"
            
            # Resolve handle from waveform database
            # Note: handle is -1 in snippet, must be resolved here
            handle = waveform_db.find_handle_by_path(new_name)
            if handle is None:
                raise ValidationError(f"Signal {new_name} not found")
            
            new_node.name = new_name
            new_node.handle = handle  # Assign valid handle from current waveform
        
        # Recursively remap children
        new_node.children = [remap_node(child) for child in node.children]
        
        return new_node
    
    for node in snippet.nodes:
        remapped_nodes.append(remap_node(node))
    
    return remapped_nodes
```

### UI Integration

#### Context Menu Extension
Location: `SignalNamesView._show_context_menu()`
- Add separator after existing group operations
- Add "Save as Snippet" action (enabled only for groups)
- Icon: Use existing save icon or create snippet-specific icon
- Shortcut: Consider Ctrl+Shift+S for save snippet

#### Right Sidebar Snippet Browser
- Replace placeholder QLabel with SnippetBrowserWidget
- QTableView with custom model showing:
  - Snippet name (editable)
  - Parent scope (display only)
  - Node count (display only)
  - Creation date (sortable)
- Context menu for:
  - Rename
  - Delete
  - Export
  - Preview (show tree structure)
- Double-click to instantiate
- Drag-and-drop support for reordering

#### Dialogs
1. **Save Snippet Dialog**:
   - QLineEdit for name (pre-filled with group name)
   - QLabel showing detected parent scope
   - QTextEdit for optional description
   - Validation: name uniqueness, valid characters

2. **Instantiate Snippet Dialog**:
   - QLineEdit for target scope (pre-filled with original)
   - QPushButton for scope browser (optional)
   - Preview of signals to be created
   - Validation feedback in real-time

### Performance Considerations

#### Caching Strategy
- Cache snippet list in SnippetManager (reload on file system changes)
- Lazy load snippet content (only when needed for instantiation)
- Use QFileSystemWatcher for automatic refresh

#### Large Snippet Handling
- Limit preview to first N signals for performance
- Batch validation for large signal sets
- Progress dialog for instantiating large snippets

#### Validation Optimization
- Cache scope validation results during session
- Use bulk handle resolution from waveform_db
- Validate incrementally as user types in dialog

### Error Handling

1. **Missing Signals**: Clear error message listing missing signals
2. **Invalid Scope**: Suggest similar valid scopes
3. **File System Errors**: Graceful fallback if snippets directory unavailable
4. **Corrupt Snippets**: Skip loading, log error, allow deletion
5. **Name Conflicts**: Prompt for overwrite or rename

### Testing Approach

1. **Unit Tests**:
   - Snippet serialization/deserialization
   - Common parent finding algorithm
   - Scope remapping logic

2. **Integration Tests**:
   - Save and load snippet round-trip
   - Validation with mock waveform_db
   - UI interaction flows

3. **Edge Cases**:
   - Empty groups
   - Deeply nested groups
   - Signals with special characters
   - Very long scope paths