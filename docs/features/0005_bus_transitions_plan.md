# Enhanced Bus Waveform Rendering Plan

## 1. Requirements Analysis

### Core Requirement
Eliminate the abrupt mode switch between low transition density (boxed regions with <=> style transitions) and high density (solid boxes/lines) in bus waveform rendering. Instead, all transitions should be visualized consistently as "><"-shaped sloped transitions that become progressively steeper as transition density increases, collapsing to a single vertical line "|" when transitions occur on every pixel.

### Specific Details from User
- All transitions rendered as "><" style across all zoom levels
- Slopes steepen smoothly as transition density increases
- When transitions occur on every pixel, they collapse into a single vertical line "|"
- No abrupt visual switch between two disparate styles
- Behavior changes continuously with density
- Value text placement/visibility conforms to interior width rules
- Rendering performance remains O(N) in sampled regions
- No data model changes required

### Performance Requirements
- Must maintain O(N) complexity relative to number of sampled regions
- No noticeable performance regressions from current implementation

## 2. Codebase Research

### Current Implementation Analysis
The bus rendering logic is in `wavescout/signal_renderer.py::draw_bus_signal()` (lines 177-299).

Current behavior:
- **Low density mode** (< RENDERING.HIGH_DENSITY_THRESHOLD regions):
  - Draws boxes with diagonal transitions: `<=>` style
  - Transition width controlled by `RENDERING.BUS_TRANSITION_WIDTH`
  - Shows value text when region width > `RENDERING.MIN_BUS_TEXT_WIDTH`
  
- **High density mode** (> RENDERING.HIGH_DENSITY_THRESHOLD regions):
  - Falls back to simple vertical lines at transitions
  - Connects with horizontal lines at top and bottom
  - No value text displayed

### Key Variables and Constants
- `RENDERING.HIGH_DENSITY_THRESHOLD`: Threshold for mode switch (needs to be eliminated)
- `RENDERING.BUS_TRANSITION_WIDTH`: Fixed width for diagonal transitions (currently static)
- `RENDERING.MIN_BUS_TEXT_WIDTH`: Minimum region width for text display

## 3. Data Model Design
No data model changes required. The enhancement works entirely within the rendering layer.

## 4. Implementation Planning

### Algorithm Description

#### Dynamic Transition Width Calculation
1. **Calculate transition density**:
   - Measure average pixels per transition in current viewport
   - `density = viewport_width_px / num_transitions`

2. **Compute dynamic transition width**:
   - Maximum width: `RENDERING.BUS_TRANSITION_WIDTH` (e.g., 8 pixels)
   - Minimum width: 0.5 pixels (essentially vertical)
   - Formula: `transition_width = min(max_width, density * slope_factor)`
   - Where `slope_factor` controls how quickly transitions steepen (e.g., 0.25)

3. **Handle edge cases**:
   - When `transition_width < 1.0`: Draw vertical line
   - When regions overlap due to transition width: Clip or merge transitions

#### Unified Rendering Loop
Replace the current dual-mode approach with a single rendering loop that:
1. Iterates through all sampled regions
2. Calculates dynamic transition width based on local density
3. Draws each region with appropriate transition slopes
4. Handles text rendering based on available interior width

### File-by-File Changes

#### `wavescout/signal_renderer.py`
**Function to Modify**: `draw_bus_signal()`

**Nature of Changes**:
1. Remove the `is_high_density` check and dual-mode rendering paths
2. Implement dynamic transition width calculation
3. Create unified rendering loop that handles all density levels
4. Add smooth transition slope calculation based on:
   - Local transition density
   - Available pixel width between transitions
5. Implement collision detection for overlapping transitions
6. Ensure text rendering respects dynamic interior widths

**Integration Points**:
- Maintains same function signature and interface
- Uses existing `SignalDrawingData` structure
- Respects existing clipping boundaries (`min_valid_pixel`, `max_valid_pixel`)
- Preserves text rendering logic with dynamic width calculation

#### `wavescout/config.py` (if exists) or inline constants
**Constants to Add/Modify**:
- `BUS_TRANSITION_MAX_WIDTH`: Maximum transition width (renamed from `BUS_TRANSITION_WIDTH`)
- `BUS_TRANSITION_SLOPE_FACTOR`: Controls steepening rate (new)
- Remove or deprecate `HIGH_DENSITY_THRESHOLD`

### Key Implementation Details
1. The transition from sloped to vertical should be gradual and visually smooth
2. Consider using anti-aliasing for sub-pixel transition widths
3. May need to adjust `MIN_BUS_TEXT_WIDTH` constant for narrower regions
4. Test with both light and dark themes to ensure visibility

### Future Enhancements (Not in Scope)
- Configurable slope factor per signal
- Different transition styles (curved vs. linear)
- Adaptive text abbreviation for narrow regions