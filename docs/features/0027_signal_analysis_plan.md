# Signal Analysis Feature Specification

## 1. User Stories and Requirements Analysis

### 1.1 Feature Overview
The Signal Analysis feature enables users to compute statistical measurements (Minimum, Maximum, Sum, Average) for selected signals. Analysis can be performed either using a fixed sampling period or synchronized with a sampling signal's transitions. The analysis scope can be global (entire waveform) or constrained between the first two markers.

### 1.2 Core User Stories

#### Story 1: Sampling Signal Selection
**As a** digital design engineer  
**I want to** designate a specific signal as my sampling clock  
**So that** I can analyze other signals synchronized to my system clock or control signal

**Acceptance Criteria:**
- Right-click context menu in Signal Names panel shows "Set as Sampling Signal" option
- Only one sampling signal can be active at a time
- Selecting a new sampling signal replaces the previous one
- Sampling signal selection persists across session save/restore
- Visual indicator shows which signal is the current sampling signal (optional enhancement)
- Sampling behavior depends on signal type:
  - 1-bit wire signals: Sample on positive edges only (clock-like behavior)
  - Bus signals: Sample on any value change
  - Event signals: Sample on every event occurrence

#### Story 2: Analysis Interval Selection
**As a** waveform analyst  
**I want to** analyze signals either globally or between specific markers  
**So that** I can focus on regions of interest in my waveform

**Acceptance Criteria:**
- If 0 or 1 markers exist: Analysis uses full waveform time range
- If 2+ markers exist: Analysis can use interval between Marker 1 and Marker 2
- User can choose between "Global" and "Marker A-B" modes in the analysis window

#### Story 3: Triggering Analysis
**As a** user  
**I want to** quickly start signal analysis on selected signals  
**So that** I can get measurements without disrupting my workflow

**Acceptance Criteria:**
- Context menu "Analyze" option appears for selected signals
- Keyboard shortcut 'A'/'a' triggers analysis for selected signals
- Analysis window opens as a modal dialog
- Multiple signals can be analyzed simultaneously

#### Story 4: Configuring Analysis Parameters
**As a** user  
**I want to** choose between sampling signal or fixed period sampling  
**So that** I can analyze signals in the most appropriate way for my use case

**Acceptance Criteria:**
- Radio buttons allow switching between "Sampling Signal" and "Sampling Period" modes
- Sampling Signal mode shows dropdown with all available signals
- Sampling Period mode shows text input for numeric period value
- Previously selected sampling signal (if any) appears as default in dropdown
- Input validation ensures period is positive number

#### Story 5: Viewing Analysis Results
**As a** user  
**I want to** see analysis results in a clear tabular format  
**So that** I can quickly understand signal characteristics

**Acceptance Criteria:**
- Table displays: Signal Name, Min, Max, Sum, Average columns
- One row per selected signal
- Values initially empty, populated after analysis completes
- Table rows are selectable and copyable (for paste to external tools)
- Table is read-only (no editing allowed)

#### Story 6: Non-blocking Analysis
**As a** user  
**I want to** continue using the application while analysis runs  
**So that** I don't have to wait for long computations

**Acceptance Criteria:**
- Analysis runs asynchronously without freezing UI
- Progress bar shows analysis progress
- "Start Analysis" button initiates computation
- Results update table as they complete
- Cancel option available during analysis (enhancement)

### 1.3 Detailed Requirements

#### Functional Requirements
1. **Sampling Signal Management**
   - Add `sampling_signal: Optional[SignalNode] = None` to WaveformSession
   - Ensure sampling_signal persists in YAML session files
   - Validate sampling signal is still valid after session restore

2. **Analysis Computation**
   - Support two sampling modes:
     - Fixed period: Sample at regular time intervals
     - Signal-based: Sample based on sampling signal transitions
       * For buses: Sample on every value change
       * For event signals: Sample on every event occurrence
       * For 1-bit wire signals: Sample only on positive edges (0→1 transitions)
   - Compute four metrics:
     - Minimum value across all samples
     - Maximum value across all samples
     - Sum of all sampled values
       - Average (arithmetic mean) of sampled values
   - Handle different signal types using parse_signal_value():
     - Digital signals: Returns 0.0 or 1.0 in value_float
     - Multi-bit buses: Converted to float based on data format (signed/unsigned/hex/binary)
     - Analog signals: Direct float values
     - All analysis uses parse_signal_value() from signal_sampling module
     - Ensures consistency with waveform rendering pipeline

3. **Interval Selection**
   - Use existing marker system (no changes needed)
   - If markers.length >= 2: Use markers[0].time to markers[1].time
   - Otherwise: Use 0 to waveform.total_duration

4. **UI Components**
   - Modal dialog window (QDialog)
   - Two-option radio button group for sampling mode
   - Dropdown (QComboBox) for signal selection
   - Line edit (QLineEdit) for period input
   - Table widget (QTableWidget) for results
   - Progress bar (QProgressBar) for status
   - Start button (QPushButton) to initiate

#### Non-Functional Requirements
1. **Performance**
   - Analysis must not block main UI thread
   - Support cancellation of long-running analysis
   - Efficient sampling for large waveforms (millions of samples)

2. **Usability**
   - Clear visual feedback during analysis
   - Intuitive mode selection
   - Copy-paste support for results

3. **Error Handling**
   - Invalid period input validation
   - Handle missing sampling signal gracefully
   - Warn if selected signals cannot be analyzed

## 2. Codebase Research

### 2.1 Key Files Analyzed

#### Data Model (`wavescout/data_model.py`)
- **WaveformSession** class (line 271): Central session state holder
  - Already has `markers: List[Marker]` field for marker storage
  - Need to add `sampling_signal: Optional[SignalNode] = None`
- **SignalNode** class (line 105): Represents signals in the tree
  - Has `handle` for waveform database lookups
  - Has `format` for display configuration
  - Has `instance_id` for unique identification

#### Signal Names View (`wavescout/signal_names_view.py`)
- **SignalNamesView** class (line 76): Tree view for signal names
  - `_show_context_menu()` method (line 131): Context menu creation
  - Already has pattern for multi-signal operations via `_apply_to_selected_signals()`
  - `_get_selected_signal_nodes()` (line 98): Returns selected non-group signals

#### Waveform Controller (`wavescout/waveform_controller.py`)
- Central coordinator for UI state changes
- Manages session state and notifications
- Event bus for complex state changes
- Will need methods for sampling signal management

#### Markers Window (`wavescout/markers_window.py`)
- Example of modal dialog implementation
- Shows QDialog usage pattern with controller integration
- Table-based UI with QTableWidget

#### Waveform Database (`wavescout/waveform_db.py`)
- Provides signal data access via handles
- Methods for getting signal values and transitions

### 2.2 Architecture Patterns Identified

1. **Modal Dialog Pattern**
   - Use QDialog as base class
   - Set modal with `setModal(True)` for blocking interaction
   - Connect to controller for state management

2. **Async Operation Pattern**
   - Qt uses QThread for background operations
   - Signals/slots for thread communication
   - Progress updates via signals

3. **Table Widget Pattern**
   - QTableWidget for simple tabular data
   - Custom item flags for read-only behavior
   - Selection behavior configuration

4. **Controller Integration**
   - Controller owns session state
   - UI components observe controller changes
   - Operations go through controller methods

## 3. Implementation Planning

### 3.1 Data Model Changes

#### File: `wavescout/data_model.py`
**Modifications to WaveformSession class:**
- Add field: `sampling_signal: Optional[SignalNode] = None`
- This field will store the currently selected sampling signal
- Automatically serialized/deserialized via existing persistence

### 3.2 Controller Extensions

#### File: `wavescout/waveform_controller.py`
**New methods to add:**
- `set_sampling_signal(node: Optional[SignalNode]) -> None`
  - Updates session.sampling_signal
  - Emits "sampling_signal_changed" event
- `get_sampling_signal() -> Optional[SignalNode]`
  - Returns current sampling signal
- `clear_sampling_signal() -> None`
  - Sets sampling_signal to None

### 3.3 Context Menu Integration

#### File: `wavescout/signal_names_view.py`
**Modifications to `_show_context_menu()` method:**
- Add new menu section after clock signal options (around line 278)
- Add "Set as Sampling Signal" action for valid signals
- Add "Clear Sampling Signal" if signal is already selected
- Add separator before "Analyze" action
- Add "Analyze" action that triggers analysis window

**New method to add:**
- `_trigger_analysis() -> None`
  - Gets selected signals
  - Creates and shows SignalAnalysisWindow

### 3.4 Signal Analysis Window Implementation

#### New File: `wavescout/signal_analysis_window.py`
**Main Components:**

1. **SignalAnalysisWindow(QDialog)**
   - Modal dialog for analysis configuration and results
   - Constructor parameters: `controller`, `selected_signals`, `parent`

2. **UI Layout:**
   - Top section: Sampling mode selection
     - QRadioButton: "Sampling Signal"
     - QRadioButton: "Sampling Period"
     - QComboBox: Signal selector (enabled for signal mode)
     - QLineEdit: Period input (enabled for period mode)
   - Middle section: Interval selection
     - QComboBox: "Global" or "Marker A-B" (if markers available)
   - Center section: Results table
     - QTableWidget with columns: Signal Name, Min, Max, Sum, Average
     - Rows for each selected signal
   - Bottom section: Controls
     - QProgressBar: Shows analysis progress
     - QPushButton: "Start Analysis"
     - QPushButton: "Close"

3. **Analysis Worker Thread:**
   - `SignalAnalysisWorker(QThread)`
   - Performs actual computation in background
   - Emits progress updates and results

4. **Core Analysis Algorithm:**
   ```
   For each selected signal:
     1. Determine analysis interval (global or markers)
     2. Get sampling points:
        - If period mode: Generate regular intervals
        - If signal mode: 
          * Check sampling signal type (bus/event/1-bit wire)
          * For bus/event: Get all transitions of sampling signal
          * For 1-bit wire: Get only positive edges (0→1 transitions)
     3. For each sampling point:
        - Get signal value at that time
        - Parse using parse_signal_value(value, signal.format.data_format, bit_width)
        - Extract value_float from returned tuple
        - Skip NaN values (undefined/high-impedance)
        - Update min/max/sum/count with valid values
     4. Calculate average = sum / count
     5. Emit result for this signal
   ```

### 3.5 Analysis Engine

#### New File: `wavescout/analysis_engine.py`
**Core Analysis Functions:**

1. **compute_signal_statistics()**
   - Parameters: `waveform_db`, `signal_node`, `sampling_times`, `start_time`, `end_time`
   - Returns: Dict with min, max, sum, average
   - Uses `parse_signal_value()` from `wavescout.signal_sampling`:
     * Reuses existing value parsing logic from rendering pipeline
     * Calls with signal's data_format and bit_width parameters
     * Extracts value_float from returned tuple for statistics
     * Ensures consistency with how values are displayed in waveform viewer
     * Returns float values for all statistics

2. **generate_sampling_times()**
   - For period mode: Generate regular intervals
   - For signal mode: 
     * Determine signal type via waveform_db.var_from_handle()
     * For buses (bitwidth > 1): Extract all transition times
     * For event signals: Extract all event occurrence times
     * For 1-bit wires: Extract only positive edge times (filter transitions where value changes from '0' to '1')
   - Filters times within analysis interval

3. **sample_signal_value()**
   - Gets signal value at specific time
   - Uses `parse_signal_value()` from `wavescout.signal_sampling` module:
     * Same function used for signal rendering - ensures consistency
     * Returns tuple of (value_str, value_float, value_bool)
     * Uses the value_float component for all statistical calculations
     * Handles all data formats (UNSIGNED, SIGNED, HEX, BIN, FLOAT)
     * Returns NaN for undefined/high-impedance values
   - Statistics computation skips NaN values

### 3.6 Integration Points

1. **Persistence (wavescout/persistence.py)**
   - No changes needed - sampling_signal automatically saved
   - Validate on restore that signal still exists

2. **Event System**
   - Add "sampling_signal_changed" event type
   - Emit when sampling signal changes

3. **Keyboard Shortcuts**
   - Add 'A'/'a' key handler in SignalNamesView
   - Trigger analysis when pressed with signals selected

## 4. Testing Strategy

### 4.1 Unit Tests

1. **Test Sampling Signal Management**
   - Set/clear sampling signal via controller
   - Verify persistence in session
   - Test replacement behavior

2. **Test Analysis Computations**
   - Test parse_signal_value() integration:
     * Verify correct import from wavescout.signal_sampling
     * Test with various data formats (UNSIGNED, SIGNED, HEX, BIN, FLOAT)
     * Verify value_float extraction from returned tuple
     * Digital signals: Verify 0.0/1.0 conversion
     * Bus signals: Verify correct float conversion based on data format
     * Analog signals: Verify direct float values
   - Test NaN handling for undefined/high-impedance values
   - Test edge cases (empty signals, single value)
   - Test sampling signal type detection:
     * 1-bit wire: Verify only positive edges used
     * Bus signal: Verify all transitions used
     * Event signal: Verify all events used

3. **Test Interval Selection**
   - Global analysis (no markers)
   - Marker-based analysis (2+ markers)
   - Verify correct time range used

### 4.2 Integration Tests

1. **Test UI Flow**
   - Open analysis window
   - Configure parameters
   - Start analysis
   - Verify results displayed

2. **Test Async Behavior**
   - UI remains responsive during analysis
   - Progress updates correctly
   - Results update table

### 4.3 Manual Testing

1. **Large Waveform Performance**
   - Test with waveforms > 1M transitions
   - Verify reasonable completion time
   - Check memory usage

2. **Copy/Paste Functionality**
   - Select table rows
   - Copy to clipboard
   - Paste in external application

## 5. Acceptance Criteria

### 5.1 Functional Acceptance
- [ ] Sampling signal can be selected via context menu
- [ ] Only one sampling signal active at a time
- [ ] Sampling signal persists in saved sessions
- [ ] Analysis window opens via context menu or shortcut
- [ ] Both sampling modes (signal/period) work correctly
- [ ] Interval selection (global/markers) works
- [ ] Statistics computed correctly for all signal types
- [ ] Results displayed in table format
- [ ] Table rows can be copied to clipboard

### 5.2 Non-Functional Acceptance
- [ ] Analysis runs without blocking UI
- [ ] Progress bar updates during analysis
- [ ] Large waveforms analyzed in reasonable time
- [ ] Error messages for invalid inputs
- [ ] Clean UI layout and intuitive workflow

## 6. Risk Assessment

### 6.1 Technical Risks
1. **Performance with Large Datasets**
   - Mitigation: Implement efficient sampling algorithms
   - Consider chunked processing for very large signals

2. **Thread Safety**
   - Mitigation: Use Qt's signal/slot mechanism for thread communication
   - Ensure waveform database access is thread-safe

### 6.2 Usability Risks
1. **Complex UI Flow**
   - Mitigation: Clear labeling and logical grouping
   - Provide tooltips for guidance

2. **Ambiguous Results**
   - Mitigation: Clear column headers
   - Include units where applicable

## 7. Future Enhancements

1. **Export Functionality**
   - Save results to CSV/Excel
   - Generate analysis reports

2. **Advanced Statistics**
   - Standard deviation
   - Percentiles (25th, 50th, 75th)
   - RMS for analog signals

3. **Visualization**
   - Histogram of values
   - Time-series plot of samples

4. **Batch Analysis**
   - Analyze multiple signal groups
   - Compare results across runs

5. **Custom Sampling**
   - User-defined sampling expressions
   - Conditional sampling based on signal states