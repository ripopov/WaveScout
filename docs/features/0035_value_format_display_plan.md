# Feature Plan: Display Value and Data Format in SignalValuesView

## 1. Use Cases and Requirements Analysis

### User Request
The user wants to see both the signal value and its data format in the SignalValuesView column. The display should follow the pattern: `"value : data_format"`

### Specific Requirements
- Display current signal value at cursor position (existing functionality)
- Append the data format type after the value, separated by " : "
- Data format comes from `SignalNode.format.data_format` enum
- Format should be shown as a string representation of the DataFormat enum value (e.g., "hex", "bin", "unsigned", "signed", "float")

### Example Display
- Previous: `0x1234`
- New: `0x1234 : hex`
- Previous: `1010`
- New: `1010 : bin`
- Previous: `42`
- New: `42 : unsigned`

## 2. Codebase Research

### Core Components Analysis

#### data_model.py (Lines 65-71)
```python
class DataFormat(Enum):
    UNSIGNED = "unsigned"
    SIGNED = "signed"
    HEX = "hex"
    BIN = "bin"
    FLOAT = "float"
```
- DataFormat enum defines all possible data format types
- Each enum has a string value that can be accessed via `.value`

#### SignalNode Structure (Lines 96-109)
```python
@dataclass
class SignalNode:
    name: str
    handle: Optional[SignalHandle] = None
    format: DisplayFormat = field(default_factory=DisplayFormat)
    # ... other fields
```
- SignalNode contains a `format` field of type DisplayFormat
- DisplayFormat includes `data_format: DataFormat` field

#### DisplayFormat Structure (Lines 89-94)
```python
@dataclass
class DisplayFormat:
    render_type: RenderType = RenderType.BOOL
    data_format: DataFormat = DataFormat.UNSIGNED
    color: Optional[str] = None
    analog_scaling_mode: AnalogScalingMode = AnalogScalingMode.SCALE_TO_ALL_DATA
```
- DisplayFormat contains the data_format field we need to display

#### WaveformItemModel._value_at_cursor() (Lines 185-206)
Current implementation in `waveform_item_model.py`:
- Queries the waveform database for signal value at cursor time
- Uses `parse_signal_value()` to format the value according to data_format
- Returns formatted string for display
- This is where we need to append the format information

#### SignalValuesView Class (wave_scout_widget.py Lines 19-24)
```python
class SignalValuesView(BaseColumnView):
    """Tree view for signal values at cursor (column 1)."""
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(visible_column=1, allow_expansion=False, parent=parent)
```
- SignalValuesView displays column 1 of the WaveformItemModel
- It's a simple view that relies on the model's data() method

### Current Data Flow
1. SignalValuesView requests data from WaveformItemModel for column 1
2. WaveformItemModel.data() checks column == 1 and calls `_value_at_cursor()`
3. `_value_at_cursor()` queries the database and formats the value
4. The formatted value string is returned to the view for display

## 3. Implementation Planning

### File-by-File Changes

#### File: `wavescout/waveform_item_model.py`

**Function to Modify:** `_value_at_cursor()`

**Nature of Changes:**
- After getting the formatted value string from `parse_signal_value()`
- Append the data format to the string in the format: `"{value} : {format}"`
- Get the format string from `node.format.data_format.value`
- Handle empty values appropriately (don't append format if value is empty)

**Integration Points:**
- No changes to other methods needed
- The change is isolated to value formatting
- SignalValuesView will automatically display the updated format

### Algorithm Description

1. In `_value_at_cursor()` method:
   - Get the formatted value string (existing logic)
   - Check if value string is not empty
   - If not empty:
     - Get format string: `format_str = node.format.data_format.value`
     - Append to value: `return f"{value_str} : {format_str}"`
   - If empty, return empty string as before

### Edge Cases to Consider
- Empty/invalid signal values should not display format
- Groups don't have values, so they continue returning empty string
- Ensure consistency across all data format types

### Testing Considerations
- Verify display for all DataFormat enum values (unsigned, signed, hex, bin, float)
- Test with empty/invalid signals
- Ensure groups show no value/format
- Verify cursor movement updates both value and format display