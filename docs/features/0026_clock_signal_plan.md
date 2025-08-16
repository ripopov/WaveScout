# Clock Signal Support Feature Plan

## 1. User Stories and Requirements Analysis

### Core Functionality
The user wants to add clock signal support to WaveScout that fundamentally changes how the time grid is rendered. 
Instead of purely time-based grid lines and labels, when a clock signal is selected, the grid will display both clock cycle counts and time values, with grid lines aligned to clock edges.

### Specific Requirements

#### Data Model Requirements
- **Storage**: Clock signal stored as `Optional[tuple[Time, SignalNode]]` in `WaveformSession`
  - `Time` component: Calculated clock period in Timescale units
  - `SignalNode` component: Reference to the clock signal node for session persistence
- **Persistence**: Clock signal selection must be saved and restored from YAML session files
- **State Management**: Clock signal changes flow through WaveformController

#### Clock Signal Selection
- **UI Access**: Context menu option "Set as Clock" in Signal Names Panel
- **Valid Signal Types** (based on `var_type()` from WVar):
  - 1-bit signals: Wire, Reg, Logic, Bit, etc. (width = 1)
  - Event type signals
  - Multi-bit buses: Wire, Reg, Integer (treated as clock counters)
- **Invalid Signal Types**:
  - String type variables
  - Real/Float type variables

#### Clock Period Calculation Algorithms

1. **Event Type Signals**:
   - Iterate through first 2 signal changes using `all_changes()` iterator
   - Calculate time difference between consecutive changes
   - Use this difference as clock period

2. **1-bit Clock Signals** (Wire/Reg/Logic with width=1):
   - Iterate through signal changes to find first 4 positive edges (0→1 transitions)
   - Calculate intervals between consecutive positive edges
   - Use shortest interval as clock period (handles gated clocks)
   - If fewer than 2 edges found, fall back to any 2 transitions

3. **Bus/Counter Signals** (Multi-bit Wire/Reg/Integer):
   - Get first 2 signal changes using `all_changes()` iterator
   - Calculate: `value_diff = value2 - value1`, `time_diff = time2 - time1`
   - Clock period = `time_diff / value_diff` (assumes monotonic counter)
   - Validate result is positive integer

#### Ruler Display Modifications
- **Dual-row Display**: When clock is active, ruler shows:
  - Row 1: Clock cycle counts (e.g., "0", "100", "200", "300")
  - Row 2: Time values in configured units (e.g., "0ns", "10ns", "20ns")
- **Visual Differentiation**: 
  - Clock row background: Slightly darker/lighter shade than base ruler color
  - Time row background: Different subtle shade for clear visual separation
  - Use theme-aware colors that work in both light and dark modes
- **Font Adjustment**: Reduce font size to fit both rows in same ruler height
- **Layout**: Vertically stack labels with clock count above time value

#### Grid and Tick Behavior
- **Tick Alignment**: All ticks and grid lines align to clock edges only
- **Step Calculation**: 
  - Calculate visible clock cycles in viewport
  - Choose step sizes in powers of 10 (1, 10, 100, 1000, etc.)
  - Ensure readable spacing based on canvas width
- **Label Format**: Clock counts as integers, times with appropriate units

### Performance Requirements
- Clock period calculation should be fast (use only first few transitions)
- Grid rendering must remain smooth during zoom/pan operations
- Cache clock period to avoid recalculation

### UI/UX Requirements
- Clear visual indication when clock mode is active through differentiated backgrounds
- Background colors should be subtle (5-10% brightness difference from base ruler)
- Smooth transition between time-only and clock+time display
- Context menu option visible only for valid signal types
- Clear feedback if clock calculation fails
- Theme-aware coloring that adapts to light/dark mode settings

## 2. Codebase Research

### Key Files Analyzed

#### Data Model (`wavescout/data_model.py`)
- `WaveformSession` class (line 271): Central session state container
- `SignalNode` class (line 105): Signal representation with handle and format
- `Viewport` class (line 198): Viewport state with time conversion methods
- `TimeRulerConfig` class (line 186): Ruler configuration settings

#### Time Grid Renderer (`wavescout/time_grid_renderer.py`)
- `TimeGridRenderer` class: Encapsulates all grid/ruler rendering logic
- `calculate_ticks()` method: Computes tick positions and labels
- `render_ruler()` method: Draws the ruler header
- `render_grid()` method: Draws vertical grid lines
- Uses normalized step calculation with "nice numbers" for readable intervals

#### Signal Names View (`wavescout/signal_names_view.py`)
- `SignalNamesView._show_context_menu()`: Context menu implementation
- Already has infrastructure for signal-specific context actions
- Uses WaveformController for state changes

#### Waveform Controller (`wavescout/waveform_controller.py`)
- Central state management with callback notification system
- Owns `WaveformSession` instance
- Provides high-level operations for state changes
- Event bus for complex state change notifications

#### Backend Types (`wavescout/backend_types.py`)
- `WVar.var_type()`: Returns signal type string
- `WSignal.all_changes()`: Iterator for signal transitions
- `WSignal.value_at_time()`: Get value at specific time

#### Persistence (`wavescout/persistence.py`)
- `save_session()`: Serializes session to YAML
- `load_session()`: Deserializes and reconnects to waveform DB
- Already handles SignalNode serialization

### Architecture Patterns
- **Model-View Separation**: Data model is pure dataclasses, UI reads from it
- **Controller Pattern**: WaveformController manages all state mutations
- **Protocol-based Abstraction**: WaveformDBProtocol decouples UI from backend
- **Normalized Coordinates**: Viewport uses 0.0-1.0 relative coordinates
- **Type Safety**: Strict typing with no Any types allowed

## 3. Implementation Planning

### Data Model Changes

#### File: `wavescout/data_model.py`

**WaveformSession class modifications**:
- Add field: `clock_signal: Optional[tuple[Time, SignalNode]] = None`
- This stores both the calculated period and the signal reference

### Controller Changes

#### File: `wavescout/waveform_controller.py`

**WaveformController class additions**:
- Add method: `set_clock_signal(node: Optional[SignalNode]) -> None`
  - Calculate clock period based on signal type
  - Update session.clock_signal
  - Emit "viewport_changed" to trigger grid redraw
- Add method: `clear_clock_signal() -> None`
  - Set session.clock_signal to None
  - Emit "viewport_changed"
- Add method: `_calculate_clock_period(node: SignalNode) -> Optional[Time]`
  - Implement the three calculation algorithms
  - Return None if calculation fails

### Clock Period Calculation Module

#### New File: `wavescout/clock_utils.py`

**Functions to implement**:
- `calculate_event_clock_period(signal: WSignal) -> Optional[Time]`
  - For Event type signals
- `calculate_digital_clock_period(signal: WSignal) -> Optional[Time]`
  - For 1-bit digital signals
- `calculate_counter_clock_period(signal: WSignal, bit_width: int) -> Optional[Time]`
  - For bus/counter signals
- `is_valid_clock_signal(var: WVar) -> bool`
  - Check if signal type is valid for clock

### Time Grid Renderer Modifications

#### File: `wavescout/time_grid_renderer.py`

**TimeGridRenderer class modifications**:

1. **Add clock mode support**:
   - Add field: `_clock_period: Optional[Time] = None`
   - Add field: `_clock_offset: Time = 0`
   - Add method: `set_clock_signal(period: Optional[Time], offset: Time = 0) -> None`

2. **Modify `calculate_ticks()` method**:
   - Add parameter: `clock_mode: bool = False`
   - When clock_mode is True:
     - Calculate tick positions at clock edges
     - Generate dual labels (clock count, time)
     - Use power-of-10 steps for clock counts

3. **Modify `render_ruler()` method**:
   - Add parameter: `clock_mode: bool = False`
   - When clock_mode is True:
     - Reduce font size for dual-row display
     - Render clock count above time value with distinct background
     - Render time value below with different background shade
     - Use `painter.fillRect()` to draw background rectangles for each row
     - Calculate background colors based on current theme (light/dark mode)
     - Adjust vertical spacing

4. **Add helper methods**:
   - `_calculate_clock_ticks(viewport_start: Time, viewport_end: Time, canvas_width: int) -> Tuple[List[TickInfo], float]`
     - Calculate tick positions aligned to clock edges
     - Return tick infos with dual labels
   - `_get_ruler_background_colors(base_color: QColor) -> Tuple[QColor, QColor]`
     - Calculate clock row and time row background colors
     - Apply subtle brightness adjustment (±5-10%)
     - Return (clock_bg_color, time_bg_color)

### UI Integration

#### File: `wavescout/signal_names_view.py`

**SignalNamesView._show_context_menu() modifications**:
- Add "Set as Clock" action for valid signal types
- Add "Clear Clock" action if signal is current clock
- Connect to controller methods:
  ```
  set_clock_action.triggered.connect(lambda: self._controller.set_clock_signal(node))
  clear_clock_action.triggered.connect(self._controller.clear_clock_signal)
  ```

#### File: `wavescout/waveform_canvas.py`

**WaveformCanvas.paintEvent() modifications**:
- Check if `session.clock_signal` is set
- Pass clock period to TimeGridRenderer if active
- Use clock_mode parameter when calling renderer methods

### Session Persistence

#### File: `wavescout/persistence.py`

**Modifications needed**:
- `_dataclass_to_dict()`: Handle clock_signal tuple serialization
  - Serialize as: `{"period": period, "signal_node": node_dict}`
- `_dict_to_dataclass()`: Handle clock_signal deserialization
  - Reconstruct tuple from dictionary
  - Find SignalNode by instance_id after loading nodes

### Validation and Error Handling

#### Key validation points:
1. **Signal Type Validation**: Check var_type before allowing clock selection
2. **Period Calculation**: Handle cases with insufficient transitions
3. **Counter Validation**: Ensure counter increments are consistent
4. **Session Loading**: Gracefully handle missing clock signal on reload

### Algorithm Descriptions

#### Event Clock Period Calculation
1. Get signal from waveform DB using handle
2. Create iterator with `signal.all_changes()`
3. Collect first 2 changes as (time, value) tuples
4. Return time2 - time1 as period
5. Return None if fewer than 2 changes

#### Digital Clock Period Calculation
1. Get signal from waveform DB
2. Iterate through changes to find positive edges (0→1)
3. Store times of first 4 positive edges
4. Calculate intervals between consecutive edges
5. Return minimum interval (handles gated clocks)
6. Fall back to any 2 transitions if insufficient edges

#### Counter Clock Period Calculation
1. Get signal and bit width from waveform DB
2. Get first 2 changes with values
3. Calculate value difference (handle wraparound if needed)
4. Calculate time difference
5. Compute period = time_diff / value_diff
6. Validate result is positive and reasonable
7. Return None if calculation fails

### Performance Considerations

#### Caching Strategy
- Cache calculated clock period in WaveformSession
- Only recalculate when clock signal changes
- Clock period calculation uses only first few transitions (fast)

#### Rendering Optimization
- Pre-calculate clock-aligned tick positions
- Reuse existing grid rendering infrastructure
- Minimize font metrics calculations

## Phase Planning

### Phase 1: Core Implementation
- Data model changes
- Clock period calculation algorithms
- Controller integration
- Basic testing with different signal types

### Phase 2: UI Integration
- Context menu additions
- Grid renderer modifications
- Dual-row ruler display
- Visual feedback

### Phase 3: Polish and Optimization
- Session persistence
- Error handling improvements
- Performance optimization
- Edge case handling

## Testing Strategy

### Unit Tests
- Clock period calculation for each signal type
- Edge cases (single transition, no transitions)
- Controller state management
- Persistence round-trip

### Integration Tests
- Context menu → controller → session flow
- Grid rendering with clock mode
- Session save/load with clock signal
- Backend compatibility (pywellen and pylibfst)

## Acceptance Criteria

1. **Clock Selection**: User can right-click valid signals and select "Set as Clock"
2. **Period Calculation**: System correctly calculates period for Event, 1-bit, and bus signals
3. **Grid Display**: Ruler shows both clock counts and time values when clock is active
4. **Visual Differentiation**: Clock and time rows have distinct, subtle background colors
5. **Theme Compatibility**: Background colors adapt appropriately to light/dark themes
6. **Grid Alignment**: Grid lines and ticks align to clock edges
7. **Persistence**: Clock selection survives session save/reload
8. **Clear Operation**: User can clear clock selection via context menu
9. **Invalid Signals**: String/Real signals don't show clock option
10. **Performance**: No noticeable lag when enabling clock mode
11. **Error Handling**: Graceful handling of signals with insufficient transitions

## Migration and Compatibility

### Backward Compatibility
- Older session files without clock_signal field load normally (defaults to None)
- No changes to existing grid behavior when clock not selected

### Forward Compatibility
- New clock_signal field ignored by older versions (won't cause load failures)
- YAML structure remains compatible