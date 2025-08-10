# Markers Feature Implementation Plan

## Overview
Implement persistent timestamp markers in WaveScout waveform viewer, allowing users to place up to 9 named markers (A-I) at specific timestamps with customizable colors. Markers persist across sessions and provide visual reference points for waveform analysis.

## Requirements Analysis

### Core Functionality
- Support up to 9 persistent timestamp markers labeled A through I
- Each marker has customizable color (default: same color for new markers)
- Markers persist in session files (YAML format)
- Markers render as vertical lines similar to cursor but with different colors
- Markers render on top of everything except cursor (cursor always front)
- Marker rendering does not invalidate cached waveform pictures

### User Interaction
- **Keyboard shortcuts**: Ctrl+1 through Ctrl+9 to place/toggle markers
- **Menu option**: Edit → Drop Marker to place marker at cursor position
- **Marker management window**: View → Markers showing table with editable properties
- **Table features**:
  - 3 columns: Marker Name, Color, Timestamp
  - Editable timestamp with immediate canvas update
  - Selectable rows with Delete key support
  - Color cell shows actual color with click-to-edit color picker

## Codebase Research Findings

### Existing Infrastructure
- **Data Model**: `Marker` dataclass already exists in `wavescout/data_model.py`:
  ```python
  @dataclass
  class Marker:
      time: Time
      label: str = ""
      color: str = "#FF0000"
  ```
- **Session Support**: `WaveformSession.markers: List[Marker]` already defined
- **Persistence**: Markers already serialized/deserialized in `persistence.py`
- **Cursor Pattern**: `WaveformCanvas._paint_cursor()` provides rendering template
- **Color System**: Centralized in `config.py` with hex string format

### Key Architectural Patterns
- Time-to-pixel conversion: `(time - start_time) * width / (end_time - start_time)`
- Controller pattern for state management via `WaveformController`
- Event system for component communication
- Qt Model/View for data display

## Data Model Design

### Modifications to `wavescout/data_model.py`
- Add default marker color constant:
  ```python
  DEFAULT_MARKER_COLOR = "#00FF00"  # Green by default
  ```
- No structural changes needed (Marker class already complete)

### Session State Extension
- Markers already in `WaveformSession.markers` list
- Consider adding `selected_marker_index: Optional[int]` for UI selection tracking

## Implementation Planning

### File-by-File Changes

#### 1. `wavescout/config.py`
- **Add Constants**:
  - `MARKER_WIDTH = 1` (thinner than cursor)
  - `MARKER_DEFAULT_COLOR = "#00FF00"`
  - `MARKER_LABELS = ["A", "B", "C", "D", "E", "F", "G", "H", "I"]`
  - `MAX_MARKERS = 9`

#### 2. `wavescout/waveform_canvas.py`
- **New Methods**:
  - `_paint_markers()`: Render all markers as vertical lines
  - `_get_marker_at_position(x: int) -> Optional[Marker]`: Hit detection
- **Modify Methods**:
  - `paintEvent()`: Call `_paint_markers()` after signals, before cursor
  - `_partial_update()`: Exclude marker regions from partial updates
- **Rendering Logic**:
  - Convert marker time to x-coordinate using existing conversion
  - Draw vertical line with marker color
  - Add text label at top of line

#### 3. `wavescout/waveform_controller.py`
- **New Methods**:
  - `add_marker(index: int, time: Time, color: str = None)`: Add/update marker
  - `remove_marker(index: int)`: Remove marker by index
  - `update_marker_time(index: int, time: Time)`: Update timestamp
  - `update_marker_color(index: int, color: str)`: Update color
  - `get_marker(index: int) -> Optional[Marker]`: Get marker by index
- **New Events**:
  - `"markers_changed"`: Emitted when markers modified
- **Integration**:
  - Maintain markers list in session
  - Emit events for UI synchronization

#### 4. `wavescout/wave_scout_widget.py`
- **Keyboard Shortcuts**:
  - Add Ctrl+1 through Ctrl+9 handling in `keyPressEvent()`
  - Toggle behavior: add marker if none at index, remove if exists
- **Menu Integration**:
  - Add "Drop Marker" action to Edit menu
  - Add "Markers..." action to View menu to open marker window

#### 5. `wavescout/markers_window.py` (New File)
- **Class**: `MarkersWindow(QDialog)`
- **Components**:
  - `QTableWidget` with 3 columns
  - Custom delegate for color cell rendering
  - Editable timestamp cells with validation
- **Functionality**:
  - Load markers from controller
  - Handle timestamp edits with immediate canvas update
  - Delete key support for removing selected marker
  - Color picker dialog on color cell click
- **Signals**:
  - Connect to controller's `markers_changed` event
  - Emit updates when user modifies values

#### 6. `scout.py`
- **Menu Actions**:
  - Add "Drop Marker" to Edit menu
  - Add "Markers..." to View menu
- **Action Handlers**:
  - `_drop_marker()`: Add marker at current cursor position
  - `_show_markers_window()`: Open markers management dialog

## UI Integration

### Menu Structure
```
Edit Menu:
  ...
  --------
  Drop Marker (Ctrl+M)

View Menu:
  ...
  --------
  Markers...
```

### Markers Window Design
- Modal dialog with table widget
- Columns: Name (read-only), Color (custom delegate), Timestamp (editable)
- Buttons: Close, Delete Selected
- Real-time updates to canvas on edit
- Validation for timestamp values

### Visual Rendering
- Vertical lines with 1px width (thinner than cursor)
- Label text positioned at top of viewport
- Semi-transparent background for label readability
- Z-order: signals < markers < cursor

## Algorithm Descriptions

### Marker Placement Algorithm
1. Get current cursor time from session
2. Check if marker exists at target index
3. If exists and at same time, remove marker (toggle behavior)
4. Otherwise, create/update marker with cursor time
5. Use default or existing color
6. Emit `markers_changed` event
7. Trigger canvas repaint

### Marker Rendering Algorithm
1. For each marker in session.markers:
   - Convert marker.time to x-coordinate
   - Skip if outside visible viewport
   - Draw vertical line from top to bottom
   - Draw label text at top with background
2. Ensure rendering order: signals → markers → cursor

## Performance Considerations

### Rendering Optimization
- Markers drawn directly in `paintEvent()`, not cached
- No invalidation of cached signal pixmaps
- Partial updates exclude marker regions
- Only repaint affected regions on marker changes

### Memory Impact
- Minimal: 9 markers maximum, each ~50 bytes
- No caching required for marker visuals
- Reuse existing time-to-pixel calculations

## Testing Considerations

### Unit Tests
- Marker CRUD operations in controller
- Session save/load with markers
- Time-to-pixel conversion accuracy
- Keyboard shortcut handling

### Integration Tests
- Marker persistence across session reload
- Canvas rendering with multiple markers
- Marker window synchronization
- Color picker integration

### Manual Testing
- Verify all 9 shortcuts work correctly
- Test marker visibility at different zoom levels
- Confirm markers don't affect performance
- Validate color changes apply immediately
- Test edge cases (markers at viewport boundaries)

## Implementation Notes

### Phase 1: Core Implementation
1. Add marker rendering to canvas
2. Implement controller methods
3. Add keyboard shortcuts
4. Test basic functionality

### Phase 2: UI Integration
1. Add menu items
2. Create markers window
3. Implement color picker
4. Add delete functionality

### Phase 3: Polish
1. Optimize rendering
2. Add visual feedback
3. Improve label positioning
4. Final testing

## Summary
The Markers feature leverages existing WaveScout infrastructure, particularly the cursor implementation pattern and session persistence system. The data model already supports markers, requiring only UI integration and rendering logic. Implementation follows established patterns for controller events, canvas rendering, and Qt model/view architecture.