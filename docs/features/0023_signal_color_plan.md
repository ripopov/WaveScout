# Signal Color Customization Feature Specification

## 1. User Stories and Requirements Analysis

### 1.1 Feature Overview
Enable users to customize the display color of individual signals in the waveform viewer through a context menu option that opens a quick color picker modal popup.

### 1.2 User Stories

**Story 1: As a user, I want to customize signal colors to visually distinguish between related signals**
- Right-click on a signal in the signal names tree view
- Select "Set Color..." from the context menu
- Choose a color from a quick color picker
- See the signal immediately update with the new color in the waveform canvas

**Story 2: As a user, I want color customization to work for all signal types**
- Digital signals should render with custom colors
- Analog waveforms should use custom colors for their traces
- Bus signals should display with custom colors for their outlines and text
- Event markers should render with custom colors

**Story 3: As a user, I want my color choices to be persistent**
- Custom colors should be saved when I save a session
- Custom colors should be restored when I load a session
- Default theme color should be used for new signals

### 1.3 Functional Requirements

1. **Context Menu Integration**
   - Add "Set Color..." menu item to signal context menu (not for groups)
   - Position after "Data Format" submenu, before "Render Type" submenu
   - Show current color as a small icon/preview next to menu item (optional enhancement)

2. **Color Picker Dialog**
   - Use Qt's QColorDialog for color selection
   - Show current signal color as initial selection
   - Support standard color palette and custom colors
   - Allow hex color input for precise color specification

3. **Rendering Support**
   - All signal renderers must respect the custom color setting
   - Color should override theme default but maintain proper opacity/alpha handling
   - Ensure good contrast against background for visibility

4. **Persistence**
   - Color field already exists in DisplayFormat dataclass
   - Ensure YAML serialization/deserialization preserves color values
   - Default to theme color for signals without explicit color

5. **Multi-Selection Support**
   - When multiple signals are selected, apply color to all selected signals
   - Consistent with existing multi-selection behavior for format changes

### 1.4 Non-Functional Requirements

1. **Performance**
   - Color changes should trigger immediate canvas repaint
   - No significant performance impact on rendering
   - Efficient cache invalidation (only affected signals)

2. **User Experience**
   - Color picker should open near cursor position
   - Immediate visual feedback upon color selection
   - Undo/redo support through existing session state management

3. **Compatibility**
   - Backward compatible with existing session files
   - Forward compatible (older versions ignore color field)
   - Theme integration (respect theme when no custom color set)

## 2. Codebase Research

### 2.1 Current Implementation Analysis

**DisplayFormat Color Field** (`wavescout/data_model.py`)
- `DisplayFormat.color` field already exists with default factory using theme color
- Type: `str` (hex color format)
- Default: `get_default_signal_color()` returns current theme's default signal color

**Signal Renderers** (`wavescout/signal_renderer.py`)
- All renderers (`draw_digital_signal`, `draw_bus_signal`, `draw_analog_signal`, `draw_event_signal`) already use `node_info['format'].color`
- Color extraction: `color = QColor(node_info['format'].color)`
- Alpha handling: Forces full opacity (255) for crisp rendering

**Context Menu** (`wavescout/signal_names_view.py`)
- `SignalNamesView._show_context_menu()` builds the context menu
- Current structure: Data Format → Render Type → Height → Analog Scaling → Navigate to Scope → Rename
- Multi-selection support via `_apply_to_selected_signals()`

**Controller Format Updates** (`wavescout/waveform_controller.py`)
- `set_node_format()` method handles format property updates
- Already supports color updates: checks for 'color' in kwargs
- Triggers format change events via EventBus

**Persistence** (`wavescout/persistence.py`)
- `_serialize_node()` includes format dict with color field
- `_deserialize_node()` reconstructs DisplayFormat with color
- YAML serialization handles string color values automatically

### 2.2 Key Components Affected

1. **SignalNamesView** - Add color picker menu action
2. **WaveformController** - Already supports color updates via `set_node_format()`
3. **Signal Renderers** - Already respect color field
4. **Persistence** - Already handles color serialization
5. **WaveformCanvas** - Will repaint automatically on format change events

## 3. Implementation Planning

### 3.1 File-by-File Changes

#### `wavescout/signal_names_view.py`

**Function to Modify:** `_show_context_menu()`

**Nature of Changes:**
1. Add "Set Color..." action after Data Format submenu
2. Connect action to new `_set_signal_color()` method
3. Implement `_set_signal_color()` method to:
   - Get current color from first selected signal
   - Open QColorDialog with current color
   - Apply new color to all selected signals via controller

**Integration Points:**
- Uses existing `_apply_to_selected_signals()` for multi-selection
- Calls `self._controller.set_node_format()` with color parameter
- QColorDialog integration similar to markers_window.py implementation

#### `wavescout/waveform_canvas.py`

**No changes required** - Canvas already responds to format change events and triggers repaint

#### `wavescout/signal_renderer.py`

**No changes required** - All renderers already use `node_info['format'].color`

#### `wavescout/waveform_controller.py`

**No changes required** - `set_node_format()` already handles color updates

#### `wavescout/persistence.py`

**No changes required** - Color field already serialized/deserialized

### 3.2 UI Integration

#### Context Menu Structure
```
Signal Context Menu:
├── Data Format ►
├── Set Color...        <- NEW
├── Render Type ►
├── Height ►
├── Analog Scaling Mode ►
├── Navigate to Scope ►
└── Rename
```

#### Implementation Details

**Location in `SignalNamesView._show_context_menu()`:**
- Insert after `format_menu` creation (around line 190)
- Before "Render Type" submenu creation

**Menu Action Creation:**
```python
# Add after Data Format submenu
color_action = QAction("Set Color...", self)
color_action.triggered.connect(self._set_signal_color)
menu.addAction(color_action)
menu.addSeparator()
```

**Color Picker Method:**
```python
def _set_signal_color(self) -> None:
    """Open color dialog and apply selected color to all selected signals."""
    # Get first selected signal's current color
    selected = self._get_selected_signal_nodes()
    if not selected:
        return
    
    current_color = QColor(selected[0].format.color)
    
    # Open color dialog
    new_color = QColorDialog.getColor(
        current_color, 
        self, 
        "Select Signal Color"
    )
    
    if new_color.isValid():
        # Apply to all selected signals
        color_str = new_color.name()  # Returns hex format "#RRGGBB"
        for node in selected:
            self._controller.set_node_format(
                node.instance_id,
                color=color_str
            )
```

### 3.3 Testing Considerations

#### Manual Testing Scenarios

1. **Single Signal Color Change**
   - Right-click single signal → Set Color → Verify immediate update
   - Check all render types (digital, analog, bus, event)

2. **Multi-Selection Color Change**
   - Select multiple signals → Set Color → Verify all update
   - Mix of different signal types

3. **Session Persistence**
   - Set custom colors → Save session → Reload → Verify colors preserved
   - Load session without colors → Verify defaults applied

4. **Theme Integration**
   - New signals use theme default color
   - Existing custom colors preserved on theme change

#### Unit Test Coverage

1. **Controller Tests**
   - Verify `set_node_format()` with color parameter
   - Check event emission on color change

2. **Persistence Tests**
   - Serialize/deserialize with custom colors
   - Backward compatibility with sessions lacking color

3. **Renderer Tests**
   - Verify color application in each renderer type
   - Alpha channel handling (forced to 255)

### 3.4 Risk Assessment

#### Low Risk
- Color field already exists in data model
- Renderers already use color field
- Controller already supports color updates
- Persistence already handles color field

#### Potential Issues
1. **Color Visibility**: Some colors may have poor contrast against background
   - Mitigation: User responsibility, can change if not visible
   
2. **Performance**: Frequent color changes trigger repaints
   - Mitigation: Existing optimization handles this well

3. **Dialog Blocking**: QColorDialog is modal
   - Mitigation: Standard Qt behavior, users expect this

## 4. Acceptance Criteria

1. ✓ "Set Color..." menu item appears in signal context menu
2. ✓ QColorDialog opens with current signal color pre-selected
3. ✓ Selected color immediately updates signal rendering
4. ✓ Color change works for all signal types (digital, analog, bus, event)
5. ✓ Multi-selection applies color to all selected signals
6. ✓ Custom colors persist in saved sessions
7. ✓ Custom colors restore from loaded sessions
8. ✓ New signals use theme default color
9. ✓ No performance degradation with color changes
10. ✓ Color updates trigger appropriate repaint events

## 5. Implementation Effort Estimate

**Estimated effort: 2-3 hours**

- Context menu integration: 30 minutes
- Color picker implementation: 30 minutes
- Testing and verification: 1-2 hours
- Documentation updates: 30 minutes

The implementation is straightforward because the infrastructure already exists. The main work is adding the UI entry point and ensuring proper integration with the existing format change system.