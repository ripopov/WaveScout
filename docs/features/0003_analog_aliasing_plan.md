# Feature: Analog Signal Aliasing Visualization

## Introduction
This feature improves how analog signals display aliasing when multiple signal transitions occur within a single visible pixel. Currently, aliasing is indicated with a background color change, which can be confusing. The improvement will use the same approach as digital signals: drawing vertical lines to clearly indicate that the exact value cannot be visualized and the user needs to zoom in.

## Requirements
- When multiple signal transitions happen in the same visible pixel for analog signals, draw a vertical line at that pixel instead of changing the background color
- Make it clear to users that the exact value is not possible to visualize using an analog plot at the current zoom level
- Follow the same visual pattern as digital signals use for aliasing (vertical lines)
- Users need to zoom in to understand how the signal changes in aliased regions

## Data Model Changes
No data model changes required. The existing `SignalSample.has_multiple_transitions` field already tracks aliasing information.

## Implementation

### 1. Signal Renderer Changes
**File**: `wavescout/signal_renderer.py`
**Functions**: `draw_analog_signal()`
**Changes**:
- Remove the current aliasing background color rendering (lines 541-548)
- Replace with vertical line rendering similar to digital signals
- Draw vertical lines at pixels where `sample.has_multiple_transitions` is True
- Use a distinct color or style to differentiate from normal waveform lines
- Ensure vertical lines span the full signal height (from y_top to y_bottom)

## Algorithms

### Aliasing Visualization Algorithm
1. During waveform rendering loop (lines 504-532):
   - Track pixels with `has_multiple_transitions = True`
   - Continue accumulating normal waveform points as usual
   
2. After drawing the main waveform polyline:
   - Iterate through tracked aliasing pixels
   - For each aliased pixel:
     a. Set pen to aliasing indicator style (e.g., dashed or different color)
     b. Draw vertical line from `y_top` to `y_bottom` at pixel x-coordinate
     c. Optionally draw at x+1 for better visibility (like digital signals do)

3. Visual style options:
   - Option A: Use same color as signal but with dashed/dotted pen style
   - Option B: Use a slightly darker/lighter shade of the signal color
   - Option C: Use a semi-transparent overlay line

## UI Integration
- No UI controls needed - this is a rendering improvement only
- The vertical lines will appear automatically when aliasing is detected
- Users can zoom in to resolve aliased regions and see actual signal transitions

## Testing Approach
1. Create test waveforms with high-frequency analog signals that alias at default zoom
2. Verify vertical lines appear at aliased pixels
3. Verify zooming in resolves aliasing and shows actual waveform
4. Test with different analog signal types (sine waves, ramps, noise)
5. Compare visual consistency with digital signal aliasing indicators
6. Performance test with heavily aliased signals (thousands of transitions per pixel)

## Performance Impact
- Minimal performance impact - replaces background fill with line drawing
- Actually may improve performance by removing the fillRect operation
- Line drawing is typically faster than area fills in Qt
- No additional data processing required - uses existing `has_multiple_transitions` flag

## Implementation Details

### Current Implementation to Remove
```python
# Lines 541-548 in draw_analog_signal()
# Highlight aliasing regions with different background color
if aliasing_regions:
    aliasing_color = QColor(255, 200, 200, 50)  # Light red with transparency
    painter.fillRect(0, y_top, params['width'], signal_height, aliasing_color)
    
    # Draw vertical lines at aliasing points for clarity
    painter.setPen(QPen(QColor(255, 100, 100, 100), 1))
    for x_pos in aliasing_regions:
        painter.drawLine(int(x_pos), y_top, int(x_pos), y_bottom)
```

### New Implementation Approach
```python
# After drawing the main waveform (around line 540)
# Draw aliasing indicators as vertical lines
if aliasing_regions:
    # Use a distinct pen style for aliasing
    aliasing_pen = QPen(color, 1, Qt.PenStyle.DotLine)
    painter.setPen(aliasing_pen)
    
    for x_pos in aliasing_regions:
        x_int = int(x_pos)
        # Draw primary vertical line
        painter.drawLine(x_int, y_top, x_int, y_bottom)
        # Draw secondary line for better visibility (like digital signals)
        if x_int + 1 < params['width']:
            painter.drawLine(x_int + 1, y_top, x_int + 1, y_bottom)
```

## Visual Consistency
The new approach will provide visual consistency across signal types:
- Digital signals: Vertical lines for aliasing (already implemented)
- Analog signals: Vertical lines for aliasing (this feature)
- Bus signals: Already handles high-density with vertical lines

This creates a unified visual language where vertical lines always indicate "more detail available when zoomed in".