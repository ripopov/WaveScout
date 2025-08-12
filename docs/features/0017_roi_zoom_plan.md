# ROI Zoom Feature Plan

## Requirements Analysis

### Core Functionality
Allow users to zoom the waveform viewport to a time interval selected via a right-mouse drag, with smooth overlay feedback that does not trigger waveform re-rendering during the drag.

### Interaction Requirements
- **Press**: User positions mouse at desired start/end of ROI
- **Drag**: Press and hold right mouse button, move to other ROI corner (left→right or right→left)
- **Release**: On right-button release, canvas zooms so ROI exactly becomes visible viewport

### Visual Feedback Requirements
- Two vertical guide lines (one at drag start, one at current mouse position)
- Semi-transparent shaded rectangle between the two positions
- Style matching existing cursor/marker lines for visual consistency
- Overlay drawn above all canvas elements

### Performance Requirements
- Overlay-only drawing without invalidating cached waveform image
- High FPS smooth feedback during mouse movement
- Waveform re-render only after viewport changes on mouse release

## Data Model Design

No changes to data model are needed. The ROI selection is a temporary interactive state that should not be persisted in the session.

### Configuration Addition
```python
# In wavescout/config.py, add to WaveformConfig:
roi_selection_color: str = "#4A90E2"  # Semi-transparent blue
roi_selection_opacity: float = 0.2
roi_guide_line_color: str = "#4A90E2"
roi_guide_line_width: int = 1
roi_guide_line_style: Qt.PenStyle = Qt.PenStyle.DashLine
```

## Implementation Planning

### File-by-File Changes

#### 1. wavescout/config.py
- **Modifications**: Add ROI visual configuration parameters to `WaveformConfig`
- **Purpose**: Centralize ROI appearance settings

#### 2. wavescout/waveform_canvas.py
- **New Member Variables**:
  - `_roi_selection_active: bool = False`
  - `_roi_start_x: Optional[int] = None`
  - `_roi_current_x: Optional[int] = None`
- **Functions to Modify**:
  - `mousePressEvent()`: Add right-click detection and ROI drag start
  - `mouseMoveEvent()`: Add ROI drag tracking (currently not implemented)
  - `mouseReleaseEvent()`: Add ROI zoom trigger (currently not implemented)
  - `_paint_overlays()`: Add ROI overlay drawing
- **New Methods**:
  - `_start_roi_selection(x: int)`: Initialize ROI selection
  - `_update_roi_selection(x: int)`: Update current ROI position
  - `_finish_roi_selection()`: Complete ROI and trigger zoom
  - `_paint_roi_overlay(painter: QPainter)`: Draw ROI visualization
  - `_clear_roi_selection()`: Reset ROI state
- **Integration**: Connect to existing viewport and overlay systems

#### 3. wavescout/waveform_controller.py
- **New Method**:
  - `zoom_to_roi(start_time: Time, end_time: Time)`: Zoom viewport to ROI bounds
- **Integration**: Use existing viewport manipulation infrastructure

### Algorithm Descriptions

#### ROI Selection State Machine
1. **Idle State**: `_roi_selection_active = False`
2. **Right-Press**: Set `_roi_selection_active = True`, store `_roi_start_x`
3. **Mouse Move (while selecting)**: Update `_roi_current_x`, request overlay repaint
4. **Right-Release**: 
   - Convert pixel positions to times
   - Swap if needed (ensure start < end)
   - Trigger zoom operation
   - Clear ROI state variables
5. **Escape/Cancel**: Clear selection variables, return to idle

#### Overlay Drawing Algorithm
1. Skip if `_roi_selection_active` is False
2. Calculate min/max X coordinates from start and current positions
3. Draw vertical guide lines at both X positions
4. Fill semi-transparent rectangle between the lines
5. Use QPainter composition mode for proper transparency

#### Zoom Calculation
1. Convert ROI pixel bounds to time coordinates using `_x_to_time()`
2. Handle edge cases (reversed drag, minimum zoom width)
3. Create new viewport with exact ROI bounds
4. Apply through controller's viewport update mechanism

## UI Integration

### Mouse Event Flow
1. **Right-Press**: Set `_roi_selection_active = True`, store `_roi_start_x`
2. **Mouse Move**: Update `_roi_current_x`, call `update()` for overlay only
3. **Right-Release**: Calculate times, call controller zoom, clear ROI variables

### Visual Rendering
- Overlay drawing in `_paint_roi_overlay()` called from `_paint_overlays()`
- Uses existing painter with proper composition mode for transparency
- Draws after waveforms but before cursor/markers for proper layering

## Performance Considerations

### Overlay-Only Updates
- Use `update()` instead of full repaint during drag
- Check for `_roi_selection_active` early in paint path
- No waveform regeneration during selection

### Cached Image Preservation
- ROI overlay draws on top of cached waveform pixmap
- Only viewport change triggers waveform re-render
- Mouse tracking updates only affect overlay layer

## Testing Strategy

### Manual Test Cases
1. Basic ROI zoom (left to right drag)
2. Reversed ROI zoom (right to left drag)
3. Cancel ROI with Escape key
4. ROI zoom near viewport edges
5. ROI zoom with minimum width enforcement
6. Visual feedback smoothness during drag

### Edge Cases
- Very small ROI selections (enforce minimum width)
- ROI extending beyond data bounds
- Rapid mouse movements during selection
- Window resize during active selection