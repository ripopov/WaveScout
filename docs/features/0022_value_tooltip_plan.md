# Value at Cursor Tooltips - Feature Specification

## 1. User Stories and Requirements Analysis

### 1.1 Feature Overview
The "Value at Cursor" tooltips feature displays signal values as semi-transparent tooltips positioned adjacent to the cursor line on each signal row. This provides users with immediate visual feedback of signal values at the cursor position without needing to look at the separate Values panel.

**Keyboard Shortcut**: Holding the 'V' or 'v' key temporarily force-enables value tooltips regardless of the menu setting. This allows quick value inspection without permanently enabling tooltips that might clutter the viewport.

### 1.2 User Value Proposition
- **Immediate Visual Feedback**: Users can see signal values directly in the waveform area without shifting focus
- **Improved Workflow**: Eliminates the need to constantly look between waveform and Values panel
- **Space Efficiency**: Values panel can be collapsed to save screen space when tooltips are enabled
- **Context Preservation**: Values appear exactly where the user is looking at the waveform

### 1.3 Functional Requirements
1. **Display**: Show signal value as tooltip next to cursor on each visible signal row
2. **Formatting**: Use same value formatting as Values panel (hex, binary, decimal, signed, float)
3. **Visibility**: 
   - Semi-transparent dark background with rounded corners
   - Bright text for maximum contrast and readability
   - Colors configurable via theme system
4. **Positioning**: Tooltip appears to the right of cursor line, aligned with signal row
5. **Toggle**: Enable/disable via View menu -> "Value Tooltip at Cursor"
6. **Persistence**: Setting saved in QSettings and restored on application restart
7. **Performance**: Tooltips rendered in real-time with cursor, not cached
8. **Keyboard Override**: 
   - Holding 'V' or 'v' key temporarily force-enables tooltips
   - Force-enable works even when tooltips disabled in menu
   - Releasing 'V' key removes force-enable and returns to menu setting
   - Force-enable state is view-only, not persisted to settings

### 1.4 Non-Functional Requirements
- **Theme Integration**: Tooltip colors must adapt to current theme
- **Rendering Performance**: No noticeable lag when moving cursor
- **Visual Clarity**: Tooltips must not obscure important waveform details
- **Accessibility**: High contrast text ensures readability for all users

### 1.5 Constraints
- Tooltips rendered on top of everything else (highest z-order)
- Not part of cached rendering pipeline (drawn fresh each paint event)
- Must handle edge cases: tooltips near canvas edges, overlapping tooltips
- Must work with all signal types (digital, bus, analog, event)
- 'V' key force-enable is a temporary view state, not saved to configuration

## 2. Codebase Research

### 2.1 Current Cursor Implementation
- **Location**: `wavescout/waveform_canvas.py`
- **Current Behavior**:
  - Cursor position stored in `_cursor_time`
  - Rendered in `_paint_cursor()` method
  - Cursor is drawn as part of overlays in `_paint_overlays()`
  - Uses optimized partial update when cursor moves within visible range

### 2.2 Theme System
- **Location**: `wavescout/theme.py`
- **Key Components**:
  - `ColorScheme` dataclass defines all colors
  - Three themes: DEFAULT, DARKONE, DRACULA
  - `theme_manager` singleton manages current theme
  - Colors accessible via `config.COLORS` after theme applied

### 2.3 Value Formatting
- **Location**: `wavescout/waveform_item_model.py`, `_value_at_cursor()` method
- **Process**:
  1. Query signal value at cursor time from WaveformDB
  2. Use `parse_signal_value()` from `signal_sampling.py` to format
  3. Formatting respects `node.format.data_format` (hex, binary, etc.)
  4. Returns formatted string for display

### 2.4 Existing Overlay Rendering
- **Pattern**: Overlays drawn in `_paint_overlays()` after main waveform render
- **Current overlays**: Grid, boundaries, ruler, markers, ROI selection, cursor
- **Drawing order**: Background → Waveforms → Grid → Overlays → Cursor (last)

### 2.5 QSettings Usage
- **Location**: `scout.py`, main window manages QSettings
- **Pattern**: 
  - Settings stored under "WaveScout"/"Scout" organization/app names
  - View preferences like theme, UI scale already persisted
  - Settings loaded in constructor, saved when changed

### 2.6 Visible Nodes and Row Mapping
- **Canvas maintains**:
  - `_visible_nodes`: List of currently visible SignalNode objects
  - `_row_to_node`: Maps row index to SignalNode
  - `_row_heights`: Scaled heights for each row
- **Row calculation**: Accounts for scrollbar position and header height

## 3. Implementation Planning

### 3.1 Data Model Design

#### New Theme Colors (in ColorScheme dataclass)
```python
# Add to wavescout/config.py ColorScheme
VALUE_TOOLTIP_BACKGROUND: RGBA  # Semi-transparent dark background
VALUE_TOOLTIP_TEXT: str         # Bright text color
VALUE_TOOLTIP_BORDER: str       # Optional border color
```

Theme-specific values:
- DEFAULT: Background (20, 20, 20, 200), Text "#FFFFFF"
- DARKONE: Background (40, 44, 52, 200), Text "#E5C07B" 
- DRACULA: Background (40, 42, 54, 200), Text "#F1FA8C"

#### New Configuration (in RenderingConfig)
```python
# Add to wavescout/config.py RenderingConfig
VALUE_TOOLTIP_PADDING: int = 4          # Internal padding
VALUE_TOOLTIP_MARGIN: int = 8           # Distance from cursor
VALUE_TOOLTIP_BORDER_RADIUS: int = 4    # Rounded corner radius
VALUE_TOOLTIP_MIN_WIDTH: int = 40       # Minimum tooltip width
VALUE_TOOLTIP_FONT_SIZE: int = 9        # Font size for values
```

#### Canvas State
```python
# Add to WaveformCanvas.__init__()
self._value_tooltips_enabled: bool = False  # Toggle state from menu/settings
self._value_tooltips_force_enabled: bool = False  # Temporary V key override
```

### 3.2 File-by-File Changes

#### 1. **wavescout/config.py**
- **Modifications**: Add tooltip color fields to ColorScheme
- **New fields**: VALUE_TOOLTIP_BACKGROUND, VALUE_TOOLTIP_TEXT, VALUE_TOOLTIP_BORDER
- **Configuration**: Add tooltip rendering parameters to RenderingConfig

#### 2. **wavescout/theme.py**
- **Modifications**: Update all three theme definitions (DEFAULT, DARKONE, DRACULA)
- **Add tooltip colors**: Appropriate colors for each theme's aesthetic

#### 3. **wavescout/waveform_canvas.py**
- **New method**: `_paint_value_tooltips(painter: QPainter)`
  - Check if tooltips should render (menu enabled OR force enabled)
  - Iterate through visible nodes
  - Calculate row positions accounting for scroll
  - Query value at cursor for each node
  - Draw tooltip with background and text
- **Modify**: `_paint_overlays()` to call `_paint_value_tooltips()` after cursor
- **New method**: `set_value_tooltips_enabled(enabled: bool)`
- **State**: Add `_value_tooltips_enabled` and `_value_tooltips_force_enabled` flags
- **Override**: `keyPressEvent(event: QKeyEvent)`
  - If event.key() == Qt.Key_V: set `_value_tooltips_force_enabled = True`
  - Call update() to trigger repaint
  - Call parent implementation
- **Override**: `keyReleaseEvent(event: QKeyEvent)`
  - If event.key() == Qt.Key_V: set `_value_tooltips_force_enabled = False`
  - Call update() to trigger repaint
  - Call parent implementation

#### 4. **scout.py** (Main Window)
- **New action**: `self.value_tooltip_action` in `_create_actions()`
  - Checkable QAction for View menu
  - Connected to toggle slot
- **Modify**: `_create_menus()` to add action to View menu
- **New method**: `_toggle_value_tooltips(checked: bool)`
  - Update canvas setting
  - Save to QSettings
- **Modify**: Constructor to load saved preference from QSettings

#### 5. **wavescout/wave_scout_widget.py**
- **New method**: `set_value_tooltips_enabled(enabled: bool)`
  - Forward to canvas widget

### 3.3 Algorithm Description

#### Tooltip Rendering Algorithm
1. **Check enabled state**: Render if `_value_tooltips_enabled` OR `_value_tooltips_force_enabled`
2. **Get cursor pixel position**: Convert cursor time to x coordinate
3. **Iterate visible nodes**:
   - Calculate row Y position (header + row_index * row_height - scroll_offset)
   - Skip if row outside visible area
   - Query signal value at cursor time (reuse `_value_at_cursor` logic)
   - Skip empty values or groups
   - Calculate tooltip position (cursor_x + margin, row_center_y)
   - Measure text size for tooltip dimensions
   - Draw rounded rectangle with semi-transparent fill
   - Draw text with bright color
4. **Handle edge cases**:
   - If tooltip would extend past right edge, position on left of cursor
   - Ensure minimum tooltip width for very short values
   - Clip tooltips that would extend past canvas boundaries

#### Value Retrieval
- Reuse existing `WaveformItemModel._value_at_cursor()` logic
- Direct query to WaveformDB for efficiency
- Format according to signal's DisplayFormat settings

### 3.4 UI Integration

#### Menu Integration
**Location**: View menu in `scout.py`
```
View
├── Zoom In
├── Zoom Out  
├── Zoom to Fit
├── ─────────
├── Pan Left
├── Pan Right
├── ─────────
├── [✓] Value Tooltip at Cursor  <-- New checkbox item
├── ─────────
├── UI Scaling ►
├── Theme ►
└── Style ►
```

#### Keyboard Interaction
- **'V' Key Behavior**:
  - Press and hold 'V' or 'v' to temporarily show tooltips
  - Works regardless of menu checkbox state
  - Release 'V' to return to menu-configured state
  - Provides quick "peek" at values without permanent UI change
  - Not saved to settings - purely temporary view state

#### Visual Design
- **Background**: Semi-transparent dark rectangle with 4px rounded corners
- **Text**: High contrast bright color from theme
- **Position**: 8px to the right of cursor line, vertically centered on row
- **Size**: Dynamic based on text, minimum 40px width, 4px padding

### 3.5 Settings Persistence

#### QSettings Keys
- **Key**: "view/value_tooltips_enabled"
- **Type**: bool
- **Default**: false (disabled by default)

#### Load/Save Pattern
```python
# In scout.py constructor
value_tooltips = self.settings.value("view/value_tooltips_enabled", False, type=bool)
self.wave_widget.set_value_tooltips_enabled(value_tooltips)
self.value_tooltip_action.setChecked(value_tooltips)

# In toggle handler
self.settings.setValue("view/value_tooltips_enabled", enabled)
```

## 4. Performance Considerations

### 4.1 Rendering Optimization
- **No caching**: Tooltips drawn fresh each paint event when cursor visible
- **Partial updates**: Leverage existing cursor partial update mechanism
- **Early exit**: Skip tooltip rendering if cursor outside visible range
- **Batch text measurement**: Measure all tooltip texts once if possible

### 4.2 Memory Impact
- **Minimal**: No additional caching or persistent data structures
- **Transient**: Tooltip data calculated on-demand during paint

### 4.3 Query Optimization  
- **Reuse existing queries**: Values already queried for Values panel
- **Single pass**: Query all visible signal values in one iteration
- **Skip groups**: Don't query values for group nodes

## 5. Testing Strategy

### 5.1 Unit Tests
- Test tooltip enable/disable state persistence
- Test value formatting matches Values panel exactly
- Test edge case positioning (canvas boundaries)
- Test V key force-enable behavior:
  - Tooltips appear when V pressed (menu disabled)
  - Tooltips remain when V pressed (menu enabled)
  - Tooltips disappear when V released (menu disabled)
  - Force-enable state not saved to settings

### 5.2 Integration Tests
- Verify tooltips appear/disappear with menu toggle
- Verify theme changes update tooltip colors
- Verify scrolling updates tooltip positions correctly
- Test with all signal types (bool, bus, analog, event)
- Test V key interaction:
  - Key press triggers immediate tooltip display
  - Key release triggers immediate tooltip removal (if menu disabled)
  - V key override works during cursor movement
  - V key state properly isolated from menu setting

### 5.3 Visual Tests
- Tooltip visibility against different waveform backgrounds
- Readability with all three themes
- Positioning with different row heights (height scaling)
- Behavior at canvas edges

### 5.4 Performance Tests
- Cursor movement responsiveness with tooltips enabled
- Paint event timing with many visible signals
- Memory usage comparison (enabled vs disabled)

## 6. Acceptance Criteria

1. ✓ Tooltips display signal values next to cursor on each row
2. ✓ Values formatted identically to Values panel
3. ✓ Semi-transparent dark background with rounded corners
4. ✓ Text uses theme-appropriate high-contrast color
5. ✓ View menu checkbox enables/disables feature
6. ✓ Setting persists across application restarts
7. ✓ No performance degradation when moving cursor
8. ✓ Tooltips render on top of all other elements
9. ✓ Edge cases handled (canvas boundaries, empty values)
10. ✓ Works with all signal types and display formats
11. ✓ 'V' key temporarily force-enables tooltips when held
12. ✓ 'V' key override works regardless of menu setting
13. ✓ Releasing 'V' returns to menu-configured state
14. ✓ 'V' key state is temporary and not persisted

## 7. User Experience Benefits

### 7.1 Quick Value Inspection Workflow
The 'V' key hold functionality enhances the user workflow by:
- **Reduced Clutter**: Users can keep tooltips disabled for a clean viewport during normal navigation
- **On-Demand Information**: Quickly peek at values by holding 'V' when needed
- **Seamless Interaction**: No need to navigate menus or change settings for quick checks
- **Context Switching**: Easily compare values at different time points without permanent UI changes
- **Muscle Memory**: Simple keyboard shortcut becomes second nature for power users

### 7.2 Use Cases
1. **Debugging**: Quickly check signal values while stepping through time
2. **Analysis**: Compare values across multiple signals without visual clutter
3. **Documentation**: Clean screenshots without tooltips, then hold V to show values when explaining
4. **Teaching**: Demonstrate signal behavior with on-demand value display

## 8. Technical Requirements Summary

### 8.1 Keyboard Event Handling
- **Event Propagation**: Key events handled in WaveformCanvas, not consumed
- **State Management**: Separate force-enable flag from menu setting
- **Update Trigger**: Immediate repaint on key press/release
- **Focus Handling**: Canvas must have focus to receive key events
- **Case Insensitive**: Both 'V' and 'v' trigger force-enable

### 8.2 Rendering Logic
```python
def should_show_tooltips(self) -> bool:
    return self._value_tooltips_enabled or self._value_tooltips_force_enabled
```

## 9. Future Enhancements (Out of Scope)

- Configurable tooltip opacity level
- Option to show tooltips only for selected signals
- Tooltip animation/fade effects
- Multi-line tooltips for complex values
- Hovering tooltips (show on mouse hover without cursor)
- Copying values from tooltips to clipboard
- Configurable keyboard shortcut (not just 'V')
- Different force-enable modes (e.g., show only selected signals)