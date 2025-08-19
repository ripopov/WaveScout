# Navigate to Time/Clock Feature Specification

## 1. User Stories and Requirements Analysis

### User Story 1: Quick Navigation to Specific Timestamp
**As a** waveform viewer user  
**I want to** navigate directly to a specific timestamp  
**So that** I can quickly jump to known points of interest without manual scrolling

**Acceptance Criteria:**
- User can access navigation via Edit menu → Navigate to Time/Clk
- Shortcut keys 'T' or 't' open the dialog
- Dialog shows a single text field labeled "Timestamp" when no clock is set
- User can enter timestamp value and press Ok to navigate
- View centers on the specified timestamp with proper margin

### User Story 2: Clock-Based Navigation
**As a** digital design engineer  
**I want to** navigate by clock cycle number  
**So that** I can quickly jump to specific clock cycles during debugging

**Acceptance Criteria:**
- When `WaveformSession.clock_signal` is set, dialog shows two text fields
- Fields are labeled "Timestamp" and "Clock"
- Default focus is on Clock field for quick entry
- User can enter value in either field and press Ok
- Navigation converts clock cycles to timestamp using clock period and phase
- View centers on calculated position with proper margin

### User Story 3: Consistent Navigation Experience
**As a** user familiar with marker navigation  
**I want to** have consistent navigation behavior  
**So that** time/clock navigation feels familiar and predictable

**Acceptance Criteria:**
- Navigation uses same pixel offset as marker navigation (MARKER_NAVIGATION_OFFSET)
- Viewport adjusts smoothly with edge space boundaries respected
- Cancel button or Escape key closes dialog without changes
- Invalid input shows appropriate error message

## 2. Codebase Research

### Essential Components Analyzed

#### Data Model (`wavescout/data_model.py`)
- `WaveformSession.clock_signal`: Optional tuple of (period, phase_offset, SignalNode)
- `Time` type alias for int (simulation units)
- `Viewport` class with normalized coordinates (0.0-1.0)
- `Timescale` for unit conversion

#### Controller (`wavescout/waveform_controller.py`)
- `navigate_to_marker()`: Reference implementation for navigation logic
  - Uses `RENDERING.MARKER_NAVIGATION_OFFSET` (10 pixels default)
  - Converts pixel offset to normalized viewport units
  - Respects viewport edge space boundaries
  - Updates viewport through controller methods
- `set_clock_signal()` and `clear_clock_signal()` methods
- `is_clock_signal()` to check if node is current clock

#### Clock Utilities (`wavescout/clock_utils.py`)
- `calculate_clock_period()`: Returns (period, phase_offset) tuple
- Clock cycle calculation: `time = phase_offset + (cycle * period)`
- Supports various clock signal types (digital, event, counter)

#### Configuration (`wavescout/config.py`)
- `RENDERING.MARKER_NAVIGATION_OFFSET = 10` pixels

#### UI Patterns
- Dialog implementation pattern from `hierarchy_levels_dialog.py`:
  - QDialog with modal behavior
  - QLineEdit with validators for input
  - Ok/Cancel buttons with proper signal connections
  - Keyboard event handling for Enter/Escape

#### Menu Structure (`scout.py`)
- Edit menu contains marker-related actions
- Menu actions use QKeySequence for shortcuts
- Actions connected to methods via signals

### Architecture Patterns
- WaveformController owns navigation logic
- Normalized viewport system (0.0-1.0)
- Callback-based UI updates
- Modal dialogs for user input
- Validation before applying changes

## 3. Implementation Planning

### New Files to Create

#### `wavescout/navigate_time_dialog.py`
**Purpose:** Modal dialog for time/clock navigation input

**Classes:**
- `NavigateTimeDialog(QDialog)`: Main dialog class

**Key Methods:**
- `__init__(controller, parent)`: Initialize with controller reference
- `_setup_ui()`: Create UI layout based on clock signal state
- `_validate_and_navigate()`: Parse input and call controller navigation
- `_format_time_input(text)`: Parse various time formats
- `_format_clock_input(text)`: Parse clock cycle numbers

**UI Structure:**
- Single field mode: "Timestamp" QLineEdit
- Dual field mode: "Timestamp" and "Clock" QLineEdit fields
- Ok and Cancel buttons
- Input validation with error messages

### Files to Modify

#### `wavescout/waveform_controller.py`
**Functions to Add:**
- `navigate_to_time(time: Time, pixel_offset: Optional[int] = None, canvas_width: Optional[int] = None)`
  - Similar to `navigate_to_marker()` but takes absolute time
  - Convert time to normalized position
  - Calculate viewport adjustment with pixel offset
  - Respect edge space boundaries
  - Emit viewport_changed event

- `navigate_to_clock_cycle(cycle: int, pixel_offset: Optional[int] = None, canvas_width: Optional[int] = None)`
  - Check if clock_signal is set
  - Calculate time from cycle: `time = phase_offset + (cycle * period)`
  - Call `navigate_to_time()` with calculated time

- `get_clock_info() -> Optional[tuple[Time, Time, SignalNode]]`
  - Return current clock_signal tuple if set
  - Used by dialog to determine UI mode

#### `wavescout/wave_scout_widget.py`
**Functions to Add:**
- `_show_navigate_time_dialog()`: 
  - Create and show NavigateTimeDialog
  - Pass controller reference
  - Handle dialog result

**Functions to Modify:**
- `keyPressEvent()`: Add handling for 'T' and 't' keys
  ```python
  elif event.key() == Qt.Key.Key_T and event.modifiers() == Qt.KeyboardModifier.NoModifier:
      self._show_navigate_time_dialog()
      event.accept()
  ```

#### `scout.py` (Main Application)
**Functions to Modify:**
- `_setup_menus()`: Add new menu item in Edit menu
  - Create QAction "Navigate to Time/Clk"
  - Set shortcut with QKeySequence("T")
  - Connect to WaveScoutWidget._show_navigate_time_dialog
  - Add after markers section with separator

### Algorithm Descriptions

#### Time Navigation Algorithm
1. Get current viewport state (left, right, total_duration)
2. Calculate viewport width in normalized units
3. Convert pixel offset to normalized offset using canvas width
4. Convert absolute time to normalized position (0-1)
5. Calculate new viewport left = time_normalized - offset_normalized
6. Calculate new viewport right = left + viewport_width
7. Apply edge space clamping if needed
8. Update viewport through controller

#### Clock Cycle to Time Conversion
1. Get clock_signal tuple (period, phase_offset, node)
2. Validate cycle number is non-negative integer
3. Calculate: time = phase_offset + (cycle * period)
4. Return calculated time for navigation

## 4. UI Integration

### Dialog Layout
```
Navigate to Time/Clock
─────────────────────
[When clock not set:]
Timestamp: [___________]

[When clock is set:]
Timestamp: [___________]
Clock:     [___________]

     [Cancel] [Ok]
```

### Input Validation
- **Timestamp field**: Accept integers, optionally with time unit suffix
- **Clock field**: Accept non-negative integers only
- Show error dialog for invalid input
- Empty fields are treated as cancelled operation

### Keyboard Shortcuts
- **T** or **t**: Open navigation dialog (from main widget)
- **Enter**: Confirm and navigate (in dialog)
- **Escape**: Cancel dialog
- **Tab**: Switch between fields (dual mode)

## 5. Performance Considerations

### Caching
- No additional caching required
- Navigation only updates viewport bounds
- Existing rendering cache handles redraw

### Edge Cases
- Very large time values: Clamp to waveform bounds
- Negative clock cycles: Show error message
- No clock signal set: Hide clock field
- Invalid clock signal: Fall back to timestamp only

## 6. Testing Strategy

### Unit Tests
1. Test time parsing for various formats
2. Test clock cycle to time conversion
3. Test viewport calculation with pixel offset
4. Test edge space boundary clamping
5. Test dialog creation with/without clock

### Integration Tests
1. Test menu action triggers dialog
2. Test keyboard shortcut opens dialog
3. Test navigation updates viewport correctly
4. Test dialog focus behavior
5. Test cancel operation leaves viewport unchanged

### Manual Testing Checklist
- [ ] Menu item appears in Edit menu
- [ ] Shortcuts T and t open dialog
- [ ] Dialog shows single field when no clock
- [ ] Dialog shows dual fields when clock is set
- [ ] Clock field has default focus in dual mode
- [ ] Enter key navigates to specified time/clock
- [ ] Cancel/Escape closes without changes
- [ ] Invalid input shows error message
- [ ] Navigation respects viewport boundaries
- [ ] Navigation uses correct pixel offset

## 7. Acceptance Criteria

### Functional Requirements
- ✓ Edit menu contains "Navigate to Time/Clk" item
- ✓ Shortcuts 'T' and 't' open navigation dialog
- ✓ Dialog adapts UI based on clock signal state
- ✓ Default focus on Clock field when available
- ✓ Navigation uses same offset as marker navigation
- ✓ Viewport updates smoothly with boundaries respected

### Non-Functional Requirements
- ✓ Dialog opens instantly (<100ms)
- ✓ Navigation completes immediately (<50ms)
- ✓ No memory leaks from dialog creation/destruction
- ✓ Consistent with existing UI patterns
- ✓ Keyboard-friendly for power users

### Error Handling
- ✓ Invalid timestamp shows clear error message
- ✓ Negative clock cycles rejected with error
- ✓ Out-of-bounds navigation clamped gracefully
- ✓ Missing clock signal handled by UI adaptation

