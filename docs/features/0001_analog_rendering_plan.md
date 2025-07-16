# Analog Signal Rendering Support - Technical Plan

## Feature Description

Enable multi-bit signals to be displayed as analog waveforms with amplitude-based visualization instead of digital bus values. The amplitude of the signal changes at each SignalSample and stays constant until the next pixel in SignalDrawingData. Amplitude is proportional to the signal value relative to the signal's value range. The signal range (min, max) can be computed globally for the whole duration of the signal or per viewport (only for the visible portion of the signal).

## Data Model Changes

### 1. SignalSample Structure (`wavescout/signal_sampling.py`)

**Current Structure:**
```python
@dataclass
class SignalSample:
    value_kind: ValueKind
    value: Optional[Union[str, float, bool]]  # Single value field
    has_multiple_transitions: bool = False
```

**Modified Structure:**
```python
@dataclass
class SignalSample:
    value_kind: ValueKind
    value_str: Optional[str]    # For BUS rendering mode
    value_float: Optional[float] # For ANALOG rendering mode  
    value_bool: Optional[bool]   # For BOOL rendering mode
    has_multiple_transitions: bool = False
```

**Value Conversion Rules:**
- If pywellen Signal value is None: `value_str = "UNDEFINED"`, `value_float = NaN`, `value_bool = False`
- If pywellen Signal value is str: `value_float = NaN`, `value_bool = False`
- For numeric values: convert int to float for `value_float`

### 2. Analog Scaling Mode (`wavescout/data_model.py`)

**Add New Enum:**
```python
class AnalogScalingMode(Enum):
    SCALE_TO_ALL_DATA = "scale_to_all"      # Use global min/max
    SCALE_TO_VISIBLE_DATA = "scale_to_visible"  # Use viewport min/max
```

**Extend DisplayFormat:**
```python
@dataclass
class DisplayFormat:
    render_type: RenderType = RenderType.BOOL
    radix: str = "hex"
    data_format: DataFormat = DataFormat.UNSIGNED  
    color: str = "#33C3F0"
    analog_scaling_mode: AnalogScalingMode = AnalogScalingMode.SCALE_TO_ALL_DATA  # New field
```

### 3. Signal Range Cache (`wavescout/waveform_canvas.py` or new module)

**Add Cache Structure:**
```python
@dataclass
class SignalRangeCache:
    min: float  # Min value across all time
    max: float  # Max value across all time
    viewport_ranges: Dict[Tuple[Time, Time], Tuple[float, float]]  # Cached viewport ranges
```

## Implementation Changes

### 1. Signal Sampling (`wavescout/signal_sampling.py`)

**Function: `generate_signal_draw_commands()`**
- **Remove lines 76-78** that skip analog signals
- **Implement analog sampling logic:**
  1. Query signal transitions like digital signals
  2. Parse signal values to float where possible
  3. Create SignalSample with separated value fields

**Function: `_parse_signal_value()` (new)**
- Parse pywellen signal value to appropriate types
- see pywellen.pyi for reference

### 2. Context Menu (`wavescout/signal_names_view.py`)

**Function: `_show_context_menu()`**
- **Add "Set Render Type" submenu after line 104:**
  - Options:  "Bus", "Analog"
  - Use QActionGroup for exclusive selection
  - Only show for multi-bit signals (check signal properties)
- **Add "Analog Scaling" submenu (conditional):**
  - Only visible when render_type is ANALOG
  - Options: "Scale to All Data", "Scale to Visible Data"
  - Updates `node.format.analog_scaling_mode`

**Function: `_set_render_type()` (new)**
- Update `node.format.render_type`
- Clear any cached range data when switching modes
- Emit dataChanged and layoutChanged signals

**Function: `_set_analog_scaling()` (new)**
- Update `node.format.analog_scaling_mode`
- Clear viewport range cache if switching to/from SCALE_TO_VISIBLE_DATA
- Trigger re-render

### 3. Analog Rendering (`wavescout/signal_renderer.py`)

**Function: `draw_analog_signal()` (lines 265-339)**
- **Already implemented but needs enhancements:**
  1. Use `sample.value_float` instead of `float(sample.value)`
  2. Handle NaN values properly
  3. Use cached min/max values based on scaling mode
  4. Draw min/max value labels at top/bottom of signal row ( at beginning of row)
  5. Highlight samples with `has_multiple_transitions` using different background color

**Function: `_get_signal_range()` (new)**
- Check cache for existing range data
- If SCALE_TO_ALL_DATA: compute once and cache forever
- If SCALE_TO_VISIBLE_DATA: compute for viewport and cache
- Return (min_val, max_val) tuple

### 4. Range Computation (`wavescout/signal_renderer.py`)

**Function: `compute_signal_range()` (new)**
- Parameters: signal_handle, waveform_db, start_time, end_time
- Query all transitions in time range
- Parse values to float
- Track min/max values
- Return (min, max) 

### 5. Waveform Canvas (`wavescout/waveform_canvas.py`)

**Function: `_draw_row()`**
- Already correctly routes to `draw_analog_signal()` for ANALOG render type
- No changes needed

## Files to Modify

1. **`wavescout/data_model.py`**
   - Add AnalogScalingMode enum
   - Extend DisplayFormat with analog_scaling_mode field

2. **`wavescout/signal_sampling.py`**
   - Modify SignalSample to use separate value fields
   - Remove analog skip (lines 76-78)
   - Add analog value parsing logic

3. **`wavescout/signal_names_view.py`**
   - Add render type selection to context menu
   - Add analog scaling mode selection
   - Add handler functions for new menu items

4. **`wavescout/signal_renderer.py`**
   - Enhance draw_analog_signal() to use new value fields
   - Add min/max value label rendering
   - Add aliasing indication for has_multiple_transitions
   - Add compute_signal_range() function
   - Add _get_signal_range() function for cache management

5. **`wavescout/waveform_canvas.py`**
   - Add SignalRangeCache class


## Algorithm Details

### Range Computation Algorithm
1. Query signal transitions for time range
2. Parse each value to float
3. Track min/max, ignoring NaN values
4. Cache result with appropriate key

### Viewport Range Caching Strategy
1. Use viewport boundaries as cache key
2. Invalidate cache when:
   - Switching scaling modes
   - Signal data changes (rare)

## UI Interaction Flow

1. **User right-clicks on multi-bit signal**
2. **Context menu shows:**
   - Set Radix → [Binary, Decimal, Hexadecimal, Octal]
   - Set Render Type → [Bus, Analog]
   - Set Height Scaling → [1x, 2x, 3x, 4x, 8x]
   - (If Analog) Analog Scaling → [Scale to All Data, Scale to Visible Data]
3. **User selects "Analog"**
4. **Signal re-renders as analog waveform**
5. **User can then select scaling mode**
6. **Viewport changes trigger range recalculation if needed**
