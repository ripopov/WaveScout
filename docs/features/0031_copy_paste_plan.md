# Copy-Paste Support for SignalNamesView

## User Stories and Requirements Analysis

### Core Functionality
The feature implements standard Copy-Paste keyboard shortcuts (Ctrl+C/Ctrl+V) for signal management in the SignalNamesView widget, enabling users to:
1. Copy selected signal nodes to clipboard
2. Paste copied signals at a specific insertion point within the same application
3. Paste signal names as plain text into external applications

### Detailed Requirements

#### Copy Operation (Ctrl+C)
- **Trigger**: User presses Ctrl+C while SignalNamesView has focus
- **Selection Support**: Support both single and multiple signal node selection
- **Data Storage**: Store two representations in clipboard:
  - Internal format: Serialized SignalNode data for internal paste operations
  - Plain text format: Signal names (one per line) for external paste operations
- **Selection Types**: Copy both regular signals and groups (preserving hierarchy)

#### Internal Paste Operation (Ctrl+V in SignalNamesView)
- **Trigger**: User presses Ctrl+V while SignalNamesView has focus
- **Insertion Point**: Insert copied nodes AFTER the first currently selected SignalNode
- **Insertion Logic**: Match existing 'I' shortcut behavior from DesignTreeView
- **Hierarchy Preservation**: When pasting groups, preserve their internal structure
- **Instance IDs**: Generate new instance_ids for pasted nodes (deep copy behavior)
- **Workflow Example**:
  1. User selects 3 nodes: `clk`, `reset`, `data[7:0]`
  2. User presses Ctrl+C to copy
  3. User selects node `addr[15:0]` as insertion point
  4. User presses Ctrl+V to paste
  5. The 3 copied nodes appear after `addr[15:0]` in the signal list

#### External Paste Operation (Ctrl+V in text editor)
- **Format**: Plain text with one signal name per line
- **Content**: Use SignalNode.nickname if available, otherwise SignalNode.name
- **Groups**: For group nodes, paste the group name followed by its children (indented)
- **Example Output**:
  ```
  top.cpu.clk
  top.cpu.reset
  top.cpu.data[7:0]
  ```

### Edge Cases and Error Handling
1. **Empty Selection on Copy**: Do nothing, no clipboard update
2. **No Selection on Paste**: Insert at end of root_nodes list
3. **Invalid Clipboard Data**: Silently ignore if clipboard doesn't contain valid SignalNode data
4. **Cross-Session Paste**: Validate signal handles exist in current WaveformDB before pasting
5. **Duplicate Signals**: Allow duplicate signal instances (same handle, different instance_id)

### User Feedback
- Status bar messages for successful copy/paste operations
- No error dialogs for invalid operations (fail silently)
- Visual selection update after paste to show newly inserted nodes

## Codebase Research

### Current Signal Insertion Implementation

#### Design Tree 'I' Shortcut
Location: `wavescout/design_tree_view.py` lines 477-489
- Handles 'I' key press in eventFilter
- Calls `add_selected_signals()` which emits `signals_selected` signal
- Signal handled by `scout.py::_on_signals_selected()` 

#### Signal Addition Flow
1. `design_tree_view.py` emits `signals_selected` with List[SignalNode]
2. `scout.py::_on_signals_selected()` receives signal nodes
3. `scout.py::_add_node_to_session()` inserts nodes after last selected node:
   - If selected node has parent: insert into parent.children after selected
   - If selected node is root: insert into session.root_nodes after selected
   - If no selection: append to session.root_nodes
4. Model emits `layoutChanged` to update views

### Key Components

#### SignalNamesView (`wavescout/signal_names_view.py`)
- Already has `keyPressEvent` override (lines 508-522)
- Has methods to get selected nodes:
  - `_get_selected_signal_nodes()`: Returns non-group nodes
  - `_get_all_selected_nodes()`: Returns all nodes including groups
- Uses WaveformController for state management

#### SignalNode (`wavescout/data_model.py`)
- Dataclass with fields:
  - `name`: Full hierarchical path
  - `handle`: Optional[SignalHandle] for signal reference
  - `format`: DisplayFormat with render settings
  - `nickname`: User-defined display name
  - `children`: List["SignalNode"] for groups
  - `parent`: Optional["SignalNode"] reference
  - `is_group`: Boolean flag
  - `instance_id`: Unique identifier (auto-generated)

#### WaveformController (`wavescout/waveform_controller.py`)
- Central controller for session state
- Manages selection by instance IDs
- Provides event callbacks for state changes
- No existing methods for node insertion (handled in scout.py)

### Qt Clipboard System
- `QApplication.clipboard()`: Access system clipboard
- `QMimeData`: Container for clipboard data with multiple formats
- Custom MIME type for internal SignalNode data
- Plain text format for external compatibility

## Implementation Planning

### File-by-File Changes

#### 1. `wavescout/signal_names_view.py`

**Modifications to `keyPressEvent` method**:
- Add Ctrl+C handler to trigger copy operation
- Add Ctrl+V handler to trigger paste operation
- Check for modifier keys using `event.modifiers() & Qt.KeyboardModifier.ControlModifier`

**New Methods to Add**:
- `_copy_selected_nodes()`: 
  - Get selected nodes using `_get_all_selected_nodes()`
  - Serialize nodes to YAML for internal format
  - Extract names for plain text format
  - Set both formats on clipboard using QMimeData
  
- `_paste_nodes()`:
  - Check clipboard for custom MIME type first
  - Deserialize SignalNode data if available
  - Validate nodes against current WaveformDB
  - Get insertion point from current selection
  - Call `_insert_nodes_after()` to add nodes
  
- `_insert_nodes_after(nodes: List[SignalNode], after_node: Optional[SignalNode])`:
  - Logic similar to `scout.py::_add_node_to_session()`
  - Update parent/children relationships
  - Generate new instance_ids for pasted nodes
  - Emit signal for model update
  
- `_serialize_nodes(nodes: List[SignalNode]) -> str`:
  - Use `_serialize_node()` from persistence.py for each node
  - Return YAML string using yaml.safe_dump()
  - Leverage existing serialization that handles all fields properly
  
- `_deserialize_nodes(yaml_str: str) -> List[SignalNode]`:
  - Parse YAML using yaml.safe_load()
  - Use `_deserialize_node()` from persistence.py for each node
  - Automatically generates new instance_ids via deep_copy()

**Constants to Add**:
- `SIGNAL_NODE_MIME_TYPE = "application/x-wavescout-signalnodes"`

#### 2. `wavescout/data_model.py`

**New Methods for SignalNode class**:
- `deep_copy() -> SignalNode`:
  - Create deep copy with new instance_id
  - Recursively copy children for groups
  - Clear parent reference (set by insertion logic)
  
**Note**: The `to_dict()` and `from_dict()` methods are NOT needed since `persistence.py` already provides `_serialize_node()` and `_deserialize_node()` functions that handle all serialization requirements including enum conversions, optional fields, and nested children.

#### 3. `wavescout/waveform_controller.py`

**New Methods to Add**:
- `insert_nodes(nodes: List[SignalNode], after_id: Optional[SignalNodeID])`:
  - Insert nodes after specified node ID
  - Update session.root_nodes or parent.children
  - Emit "session_changed" callback
  - Update selection to newly inserted nodes

#### 4. Import persistence functions

**In `signal_names_view.py`**:
- Import `_serialize_node` and `_deserialize_node` from `persistence.py`
- Import `yaml` module for safe_dump and safe_load operations
- These functions handle all the complex serialization logic including:
  - Enum value conversions (RenderType, DataFormat, etc.)
  - Optional field handling with proper defaults
  - Recursive children serialization
  - Backward compatibility for missing fields

### Data Serialization Format

The internal clipboard format will use YAML (consistent with session persistence) with the following structure:
```yaml
version: 1
nodes:
  - name: top.cpu.clk
    handle: 42
    nickname: CPU Clock
    is_group: false
    format:
      render_type: bool
      data_format: unsigned
      color: null
      analog_scaling_mode: scale_to_all
    height_scaling: 1
    is_multi_bit: false
    instance_id: 12345
    is_expanded: true
    group_render_mode: null
    children: []
```

**Benefits of using YAML**:
- Consistency with existing codebase (session persistence already uses YAML)
- Reuse of tested serialization code from `persistence.py`
- Same format for clipboard and file persistence
- Human-readable clipboard content for debugging
- Handles all SignalNode fields including enums automatically

### Integration with Existing Insertion Logic

The paste operation will reuse the insertion pattern from `scout.py::_add_node_to_session()`:
1. Determine insertion point from selection
2. Find parent and index for insertion
3. Insert nodes maintaining order
4. Update parent references
5. Emit model update signal

The key difference is that paste operates on multiple nodes at once and generates new instance IDs to avoid conflicts.

### Validation During Paste

When pasting nodes with signal handles:
1. Check if handle exists in current WaveformDB
2. Skip nodes with invalid handles (different waveform file)
3. Allow duplicate handles (same signal, different instance)
4. Preserve groups even if some children are invalid

## UI Integration

### Keyboard Shortcuts
- **Ctrl+C**: Trigger copy when SignalNamesView has focus
- **Ctrl+V**: Trigger paste when SignalNamesView has focus
- No menu items or toolbar buttons (keyboard-only feature)

### Visual Feedback
- Selection automatically updates to show pasted nodes
- Status bar shows count of copied/pasted nodes
- Tree view scrolls to make first pasted node visible

## Performance Considerations

### Memory Usage
- Clipboard data is transient and cleared on application exit
- Deep copy of nodes ensures no reference leaks
- YAML serialization keeps memory footprint small

### Large Selections
- No practical limit on number of nodes copied
- Paste operation updates model once after all insertions
- Use beginInsertRows/endInsertRows for efficient Qt model updates

## Testing Strategy

### Unit Tests
1. Test serialization/deserialization of SignalNode objects
2. Test deep_copy preserves all fields except instance_id
3. Test insertion logic with various selection states
4. Test clipboard MIME type handling

### Integration Tests
1. Copy single signal and paste at different positions
2. Copy multiple signals and verify order preservation  
3. Copy group with children and verify hierarchy
4. Copy from one session, load different waveform, attempt paste
5. External paste to text editor verification

### Edge Case Tests
1. Copy with no selection (should do nothing)
2. Paste with empty clipboard
3. Paste with corrupted YAML data
4. Copy and paste signals with special characters in names
5. Paste when no waveform is loaded

## Acceptance Criteria

1. **Copy Operation**
   - ✓ Ctrl+C copies selected nodes to clipboard
   - ✓ Multiple selection is supported
   - ✓ Groups and their children are copied
   - ✓ Plain text format works in external editors

2. **Paste Operation** 
   - ✓ Ctrl+V pastes at correct insertion point
   - ✓ Order of pasted nodes is preserved
   - ✓ New instance IDs are generated
   - ✓ Groups maintain their structure
   - ✓ Invalid handles are filtered out

3. **User Experience**
   - ✓ Status messages provide feedback
   - ✓ Selection updates to show new nodes
   - ✓ No error dialogs for invalid operations
   - ✓ Feature works consistently with existing UI patterns