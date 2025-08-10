# Feature Plan: Renaming SignalNodes

## Requirements Summary
Add the ability to rename signals and groups in the SignalNames view with a user-defined nickname:
- Add "Rename" action to context menu in SignalNames view
- Support keyboard shortcut 'R'/'r' to trigger rename
- Show modal dialog to input nickname
- If multiple items selected, rename only the first selected item
- Store nickname in data_model (field already exists)
- Display nickname in SignalNames view (already implemented)
- Persist nicknames in session YAML (already implemented)

## Research Findings

### Existing Infrastructure
The codebase already has substantial support for nicknames:

1. **Data Model**: `SignalNode.nickname` field exists in `wavescout/data_model.py:107`
2. **Display Logic**: `WaveformItemModel._format_signal_name()` already prioritizes nicknames
3. **Persistence**: Session serialization/deserialization already handles nicknames
4. **Context Menu**: Established pattern in `SignalNamesView._show_context_menu()`

### Key Discovery
The nickname infrastructure is fully implemented at the data and display layers. This feature only requires adding the UI interaction layer to set nickname values.

## Implementation Plan

### 1. File-by-File Changes

#### `wavescout/signal_names_view.py`
**Functions to Modify:**
- `_show_context_menu()`: Add "Rename" action after existing menu items
- `keyPressEvent()`: Add handler for 'R'/'r' key
- **New method**: `_rename_selected_signal()`: Handle rename logic

**Nature of Changes:**
- Insert "Rename" QAction in context menu (around line 135, after format options)
- Add separator before rename action for visual grouping
- Connect action to new `_rename_selected_signal()` method
- Override or enhance `keyPressEvent()` to capture 'R'/'r' key
- Implement rename logic using `QInputDialog.getText()`
- Handle first selected item when multiple selected
- Emit proper model update signals after nickname change

**Integration Points:**
- Use existing `_get_selected_signal_nodes()` to get selected items
- Follow pattern from `_apply_display_format_to_selected()` for model updates
- Ensure both signals and groups can be renamed (no `is_group` filtering)

### 2. UI Interaction Flow

#### Rename Dialog
Use Qt's built-in `QInputDialog.getText()` for simplicity:
```
Dialog Title: "Rename Signal"
Label: "Enter nickname for '{signal_name}':"
Default Text: Current nickname (if exists) or empty string
Buttons: OK/Cancel
```

#### Multiple Selection Behavior
When multiple items are selected:
1. Get all selected nodes using `_get_selected_signal_nodes()`
2. Take the first node from the selection
3. Show dialog with first node's current nickname
4. Apply rename only to the first node
5. Update model to reflect the change

### 3. Keyboard Shortcut Implementation

#### Approach
Add key handling in `SignalNamesView.keyPressEvent()`:
- Check for `event.key() == Qt.Key.Key_R`
- No modifier keys required (plain 'R' or 'r')
- Call `_rename_selected_signal()` when triggered
- Call `event.accept()` to mark as handled

### 4. Model Update Pattern

After setting nickname:
```
# Get the index for the renamed node
index = self.model().mapFromSource(source_index)

# Emit dataChanged for all columns
self.model().dataChanged.emit(
    self.model().index(index.row(), 0, index.parent()),
    self.model().index(index.row(), self.model().columnCount() - 1, index.parent()),
    [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.UserRole]
)
```

## Test Scenario

Add to `tests/test_scout_integration.py`:

### Test: `test_signal_rename_and_persistence`
1. **Setup**: Start app, load VCD file (use existing test VCD)
2. **Add Signals**: Add 2 signals to wave widget
3. **Rename Signals**: 
   - Select first signal, trigger rename, set nickname to "SignalA"
   - Select second signal, trigger rename, set nickname to "SignalB"
4. **Save Session**: Save session to temporary YAML file
5. **Verify YAML**: 
   - Load YAML and verify nicknames are present
   - Check that `nickname: "SignalA"` and `nickname: "SignalB"` exist in saved data
6. **Reload Session**: Load saved session
7. **Verify Display**: Check that nicknames are displayed in SignalNames view

### Test Implementation Details
- Use `qtbot` to simulate user interactions
- Use `QTest.keyClick()` to test keyboard shortcut
- Mock or directly call `QInputDialog.getText()` return value for automated testing
- Verify both context menu and keyboard shortcut paths

## Edge Cases to Handle

1. **Empty Nickname**: Allow clearing nickname (empty string reverts to default name)
2. **Cancel Dialog**: No changes if user cancels
3. **No Selection**: Do nothing if no items selected
4. **Group Nodes**: Ensure groups can also be renamed
5. **Invalid Characters**: No validation needed - allow any text as nickname

## Performance Considerations
- Minimal impact: Only updating display text
- No cache invalidation needed
- No rendering performance impact

## Success Criteria
- [ ] Context menu shows "Rename" action
- [ ] 'R'/'r' keyboard shortcut triggers rename
- [ ] Modal dialog appears with current nickname pre-filled
- [ ] Nickname updates immediately in SignalNames view
- [ ] Nicknames persist in session YAML
- [ ] Nicknames restore correctly from saved sessions
- [ ] Test passes in `test_scout_integration.py`