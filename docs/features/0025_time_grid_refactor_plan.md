# Time Ruler and Grid Rendering Refactoring Plan

## 1. User Stories and Requirements Analysis

### Core Requirement
Refactor the time ruler and grid rendering logic from the WaveformCanvas class into a separate, reusable module to improve code organization, maintainability, and enable independent testing.

### Specific Requirements
1. **Separation of Concerns**: Extract all time ruler and grid rendering logic from WaveformCanvas into a dedicated module
2. **Clean Interface**: Define a clear, type-safe interface between WaveformCanvas and the new module
3. **Performance Preservation**: Maintain current rendering performance characteristics
4. **Reusability**: Design the module to be reusable by other components if needed
5. **Type Safety**: Follow project guidelines with strict typing (no Any types, use TypedDict, explicit Optional)
6. **Testing**: Make the module independently testable without Qt dependencies where possible

### Current Functionality to Preserve
- Time ruler with automatic tick spacing based on viewport and density settings
- Smart time label formatting with appropriate units (ps, ns, μs, ms, s)
- Optional vertical grid lines aligned with ruler ticks
- Grid line styling (solid, dashed, dotted) with configurable opacity
- Efficient calculation reuse between ruler and grid rendering
- Font metrics-based label spacing to prevent overlap
- Support for different timescales from waveform files

## 2. Codebase Research

### Current Implementation Analysis

#### WaveformCanvas Methods Related to Time Ruler/Grid
Located in `wavescout/waveform_canvas.py`:

1. **State Management** (lines 97-99):
   - `_last_tick_positions: List[Tuple[float, int]]` - Cached tick positions
   - `_last_ruler_config: Optional[TimeRulerConfig]` - Cached configuration

2. **Core Calculation Methods**:
   - `_calculate_and_store_ruler_info()` (lines 967-982): Calculates and caches ruler info
   - `_calculate_time_ruler_ticks()` (lines 1046-1123): Core tick calculation algorithm
   - `_format_time_label()` (lines 1145-1226): Time value formatting with unit conversion

3. **Rendering Methods**:
   - `_draw_time_ruler()` (lines 983-1044): Draws ruler background, ticks, and labels
   - `_draw_grid_lines()` (lines 1125-1143): Draws vertical grid lines
   - `_draw_time_ruler_simple()` (lines 901-928): Simplified ruler for thread context

4. **Integration Points**:
   - Called from `_paint_grid()` (lines 426-434): Grid drawing in paint pipeline
   - Called from `_paint_overlays()` (lines 457-477): Ruler drawing as overlay
   - Coordinates with `_time_to_x()` and `_x_to_time()` for pixel conversions

#### Data Structures Used

From `wavescout/data_model.py`:
- `TimeRulerConfig`: Configuration dataclass with fields:
  - `tick_density: float`
  - `text_size: int`
  - `time_unit: TimeUnit`
  - `show_grid_lines: bool`
  - `grid_color: str`
  - `grid_style: str`
  - `grid_opacity: float`
  - `nice_numbers: List[float]`
- `Timescale`: Waveform timescale with factor and unit
- `TimeUnit`: Enum for time units (ZEPTOSECONDS to SECONDS)

From `wavescout/config.py`:
- `RENDERING`: RenderingConfig with constants
- `COLORS`: ColorScheme with color definitions
- Font and dimension constants

#### Dependencies and Coupling
- Direct Qt dependencies: QPainter, QPen, QColor, QFont, QFontMetrics
- Access to WaveformCanvas state: width, height, viewport times, model/session
- Pixel conversion methods tied to canvas dimensions

## 3. Implementation Planning

### Module Architecture

#### New Module: `wavescout/time_grid_renderer.py`

This module will encapsulate all time ruler and grid rendering logic with a clean, type-safe interface.

### Data Model Design

No changes to existing data models required. The module will use existing:
- `TimeRulerConfig` from `data_model.py`
- `Timescale` and `TimeUnit` from `data_model.py`
- Color and rendering constants from `config.py`

### File-by-File Changes

#### 1. Create New File: `wavescout/time_grid_renderer.py`

**Classes to Create**:
- `TimeGridRenderer`: Main renderer class
- `TickInfo`: TypedDict for tick position data
- `ViewportParams`: TypedDict for viewport parameters
- `RenderContext`: TypedDict for rendering context

**Functions to Implement**:
- `calculate_tick_positions()`: Extract tick calculation logic
- `format_time_label()`: Extract time formatting logic
- `render_time_ruler()`: Render ruler to QPainter
- `render_grid_lines()`: Render grid lines to QPainter
- `calculate_nice_step_size()`: Helper for tick spacing

**Integration Points**:
- Accept QPainter for rendering
- Return structured data for tick positions
- Use dependency injection for configuration

#### 2. Modify: `wavescout/waveform_canvas.py`

**Instance Variables to Add**:
- `_time_grid_renderer: Optional[TimeGridRenderer]` - Renderer instance

**Methods to Modify**:
- `__init__()`: Initialize TimeGridRenderer instance
- `_calculate_and_store_ruler_info()`: Delegate to renderer
- `_draw_time_ruler()`: Delegate to renderer
- `_draw_grid_lines()`: Delegate to renderer
- `_calculate_time_ruler_ticks()`: Remove (moved to renderer)
- `_format_time_label()`: Remove (moved to renderer)

**Methods to Keep**:
- `_time_to_x()`: Keep in canvas (viewport-specific)
- `_x_to_time()`: Keep in canvas (viewport-specific)

**Integration Points**:
- Pass viewport parameters to renderer
- Provide pixel conversion callbacks
- Handle renderer results for caching

### Algorithm Descriptions

#### Tick Position Calculation Algorithm
The existing algorithm in `_calculate_time_ruler_ticks()` will be preserved:

1. **Estimate Label Width Requirements**:
   - Sample the larger of viewport start/end times
   - Format sample label with current units
   - Measure pixel width using font metrics
   - Add padding between labels

2. **Calculate Maximum Labels**:
   - Available space = canvas_width × tick_density
   - Max labels = available_space / label_width

3. **Determine Base Scale**:
   - Raw step = viewport_duration / max_labels
   - Scale = 10^floor(log10(raw_step))

4. **Find Optimal Step Multiplier**:
   - Test nice multipliers [1, 2, 2.5, 5, 10, 20, 25, 50]
   - Select first multiplier where tick_count ≤ max_labels

5. **Generate Tick Positions**:
   - First tick = floor(viewport_left / step_size) × step_size
   - Generate ticks at step_size intervals until viewport_right

#### Time Label Formatting Algorithm
The existing algorithm in `_format_time_label()` will be preserved:

1. **Convert to Seconds**:
   - Apply timescale factor and unit exponent
   - time_in_seconds = time × timescale.factor × 10^exponent

2. **Convert to Target Unit**:
   - Apply unit-specific conversion factor
   - Handle special cases (μs, ms)

3. **Determine Decimal Places**:
   - Based on step_size relative to display unit
   - Range from 0 to 4 decimal places

4. **Format and Upgrade Units**:
   - Format with appropriate precision
   - Upgrade units for readability (e.g., 1000ps → 1ns)

### Interface Design

#### TimeGridRenderer Public Interface

```python
class TimeGridRenderer:
    def __init__(self, config: TimeRulerConfig, timescale: Optional[Timescale] = None):
        """Initialize with configuration and optional timescale."""
    
    def calculate_ticks(
        self,
        viewport_start: Time,
        viewport_end: Time,
        canvas_width: int,
        time_to_pixel: Callable[[Time], int]
    ) -> Tuple[List[TickInfo], float]:
        """Calculate optimal tick positions for the viewport."""
    
    def render_ruler(
        self,
        painter: QPainter,
        tick_positions: List[TickInfo],
        canvas_width: int,
        header_height: int,
        colors: ColorScheme
    ) -> None:
        """Render the time ruler."""
    
    def render_grid(
        self,
        painter: QPainter,
        tick_positions: List[TickInfo],
        canvas_height: int,
        header_height: int
    ) -> None:
        """Render vertical grid lines."""
    
    def update_config(self, config: TimeRulerConfig) -> None:
        """Update the configuration."""
    
    def update_timescale(self, timescale: Timescale) -> None:
        """Update the timescale."""
```

### Performance Considerations

1. **Caching Strategy**:
   - Maintain tick position caching in WaveformCanvas
   - Renderer is stateless except for configuration
   - Avoid redundant calculations on paint events

2. **Memory Efficiency**:
   - Use lightweight TypedDict for data transfer
   - Avoid copying large data structures
   - Reuse calculation results between ruler and grid

3. **Rendering Optimization**:
   - Use cosmetic pens (width=0) for crisp lines
   - Batch similar drawing operations
   - Minimize QPainter state changes

### Testing Strategy

#### Unit Tests for TimeGridRenderer

1. **Tick Calculation Tests**:
   - Test various viewport ranges and widths
   - Verify tick spacing with different densities
   - Test edge cases (zero width, negative ranges)
   - Validate nice number selection

2. **Label Formatting Tests**:
   - Test all time units
   - Verify decimal place calculation
   - Test unit upgrades
   - Handle extreme values

3. **Configuration Tests**:
   - Test all configuration parameters
   - Verify grid style application
   - Test opacity settings

#### Integration Tests

1. **WaveformCanvas Integration**:
   - Verify renderer initialization
   - Test delegation of rendering calls
   - Validate caching behavior
   - Test configuration updates

2. **Performance Tests**:
   - Measure tick calculation time
   - Profile rendering performance
   - Test with large time ranges

### Migration Plan

#### Phase 1: Create Module (No Breaking Changes)
1. Create `time_grid_renderer.py` with all logic
2. Implement comprehensive unit tests
3. Ensure module is self-contained and documented

#### Phase 2: Integration
1. Add TimeGridRenderer instance to WaveformCanvas
2. Delegate calculations to renderer
3. Maintain backward compatibility
4. Run existing tests to verify no regression

#### Phase 3: Cleanup
1. Remove duplicated methods from WaveformCanvas
2. Update documentation
3. Add integration tests

### Benefits of This Refactoring

1. **Improved Maintainability**: Time/grid logic isolated in dedicated module
2. **Better Testability**: Can test ruler/grid logic without Qt widget
3. **Reusability**: Other components can use the renderer
4. **Cleaner Architecture**: WaveformCanvas focuses on orchestration
5. **Type Safety**: Clear, typed interfaces between components
6. **Documentation**: Self-documenting module with clear purpose