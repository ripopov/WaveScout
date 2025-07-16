# Data Format Feature Implementation Plan

## Introduction
This feature consolidates data format interpretation in WaveScout by removing the separate `radix` field and using only `DataFormat` for all display format options. When pywellen returns an `int` value (unsigned BitInt representing raw data), users will be able to select how this raw data is interpreted and displayed through a context menu option. This allows viewing the same signal data as unsigned decimal, signed decimal (2's complement), hexadecimal, binary, or IEEE float32 format.

## Data Model Changes

### 1. DisplayFormat in data_model.py
- **Remove** the `radix` field from `DisplayFormat` class
- The `data_format` field of type `DataFormat` enum will handle all formatting:
  - `DataFormat.UNSIGNED` - Display as unsigned decimal integer
  - `DataFormat.SIGNED` - Display as signed decimal (2's complement) integer  
  - `DataFormat.HEX` - Display as hexadecimal (e.g., "0x1A3F")
  - `DataFormat.BIN` - Display as binary (e.g., "0b11010011")
  - `DataFormat.FLOAT` - Interpret as IEEE float32

### 2. Default DataFormat Assignment
Modify `wavescout/waveform_loader.py:create_signal_node_from_wellen()`:
- When `var_type()` returns "Integer", "Int", or "ShortInt" → set `DataFormat.SIGNED`
- For multi-bit signals (not 1-bit) → set `DataFormat.HEX` (default for buses)
- For 1-bit signals → set `DataFormat.BIN`
- For all other types → set `DataFormat.UNSIGNED`
- Note: Some types like "Real", "String", "ShortReal" return float/string from pywellen, so DataFormat is ignored

## Signal Sampling Changes

### 1. parse_signal_value() in signal_sampling.py
Enhance the `parse_signal_value()` function to accept a `data_format` parameter and interpret int values accordingly:

**When pywellen returns int (raw data):**
- `value_str` assignment:
  - For `DataFormat.UNSIGNED`: Convert int to decimal string
  - For `DataFormat.SIGNED`: Apply 2's complement conversion, then to decimal string
  - For `DataFormat.HEX`: Format as hexadecimal string (e.g., "0x1A3F")  
  - For `DataFormat.BIN`: Format as binary string (e.g., "0b11010011")
  - For `DataFormat.FLOAT`: Format the interpreted float value as string

- `value_float` assignment:
  - For `DataFormat.UNSIGNED`: Cast int directly to float
  - For `DataFormat.SIGNED`: Apply 2's complement conversion, then cast to float
  - For `DataFormat.HEX`: Cast int directly to float (same as unsigned)
  - For `DataFormat.BIN`: Cast int directly to float (same as unsigned)
  - For `DataFormat.FLOAT`: Interpret raw bits as IEEE 754 float32

- `value_bool` assignment:
  - For all formats: True if non-zero, False if zero

**When pywellen returns float:**
- `value_str`: Convert float to string
- `value_float`: Use float directly
- `value_bool`: True if non-zero
- DataFormat is ignored

**When pywellen returns string:**
- `value_str`: Use string directly
- `value_float`: NaN
- `value_bool`: Parse if "0" or "1", otherwise False
- DataFormat is ignored

### 2. generate_signal_draw_commands() in signal_sampling.py
- Pass the signal's `data_format` from `signal.format.data_format` to `parse_signal_value()` when processing int values from pywellen
- Also need to pass bit width information for proper signed/float conversion

## UI Changes - Context Menu

### 1. signal_names_view.py:_show_context_menu()
**Replace** the existing "Set Radix" submenu with a new "Data Format" submenu:
- Remove the old radix menu and `_set_radix()` method
- Create QActionGroup for mutually exclusive radio button behavior
- Add options: "Unsigned", "Signed", "Hex", "Bin", "Float32"
- Only show this menu for signals that can have different data formats (non-group, non-event signals)
- Set checkmark on current `node.format.data_format` value

### 2. New Method: _set_data_format()
Create a new method to replace `_set_radix()`:
- Updates `node.format.data_format` with the selected value
- Emits `dataChanged` signal to trigger re-rendering
- This will invalidate cached samples and force recalculation

### 3. Code Cleanup
- Remove all references to `radix` field throughout the codebase
- Update any code that checks `format.radix` to use `format.data_format` instead

## Cache Invalidation

### 1. WaveformCanvas Cache
When data format changes, the signal's cached drawing data must be invalidated:
- The existing `_set_data_format()` method's `dataChanged` signal should trigger cache invalidation
- `WaveformCanvas` should detect the change and clear the affected signal from `_signal_cache`
- On next paint, new samples will be generated with the updated format

## Algorithm for Data Format Conversion

### Signed Integer (2's Complement)
```
if value >= 2^(bitwidth-1):
    signed_value = value - 2^bitwidth
else:
    signed_value = value
```

### IEEE Float32
```
1. Ensure value fits in 32 bits (mask with 0xFFFFFFFF)
2. Interpret the 32-bit pattern as IEEE 754 single-precision:
   - Bit 31: Sign bit
   - Bits 30-23: Exponent (biased by 127)
   - Bits 22-0: Mantissa/Significand
3. Convert to float value
```

### Hexadecimal/Binary Formatting
- Hex: Format with appropriate width based on bit count (e.g., 8-bit → "0xFF", 32-bit → "0xFFFFFFFF")
- Binary: Format with appropriate width, optionally group by 4 bits for readability

## Test Plan

### Test File: tests/test_data_format.py
Create a comprehensive test that uses `test_inputs/analog_signals_short.vcd` to verify data format conversions.

**Test Structure:**
1. Load the VCD file using WaveformDB
2. For each signal in the file:
   - Get signal metadata (bit width, var_type)
   - Sample values at multiple time points
   - For each DataFormat option (UNSIGNED, SIGNED, HEX, BIN, FLOAT):
     - Call `parse_signal_value()` with the format
     - Verify `value_str`, `value_float`, and `value_bool` are correctly set
     - Check edge cases (zero, max value, negative for signed)

**Specific Test Cases:**
1. **Integer signals (var_type "integer")**:
   - Test signed interpretation with negative values
   - Verify 2's complement conversion
   
2. **Multi-bit signals (8, 16, 32 bit)**:
   - Test hex formatting (proper width, uppercase)
   - Test binary formatting (proper width, leading zeros)
   - Test float32 interpretation for 32-bit signals
   
3. **Single-bit signals**:
   - Verify binary format is default
   - Test boolean interpretation
   
4. **Real signals (var_type "real")**:
   - Verify DataFormat is ignored
   - Float values pass through unchanged
   
5. **Edge Cases**:
   - Zero values in all formats
   - Maximum unsigned values
   - Minimum signed values (most negative)
   - NaN and infinity for float interpretation

**Validation Points:**
- Ensure `value_float` is numeric for UNSIGNED/SIGNED/FLOAT formats
- Ensure `value_float` matches unsigned interpretation for HEX/BIN
- Verify `value_str` formatting matches expected patterns
- Check `value_bool` is consistent across all formats

## Additional Testing Considerations
- Test with signals of various bit widths (1, 8, 16, 32, 64 bits)
- Verify signed conversion works correctly for negative values
- Test IEEE float32 conversion with normal, denormal, infinity, and NaN values
- Ensure cache is properly invalidated when format changes
- Verify that format changes persist in the session
- Test UI interaction: changing format via context menu updates display immediately