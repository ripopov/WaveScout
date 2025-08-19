# JSON Serialization Format Migration Plan

## User Stories and Requirements Analysis

### Overview
Replace the current YAML-based session serialization format with standard JSON throughout the WaveScout application. JSON provides a universally supported, standardized format with excellent performance and tooling support.

### Core Requirements

1. **Format Migration**
   - Replace all YAML serialization with standard JSON format
   - Maintain exact same data structure and field names
   - File extension changes to `.json` exclusively
   - Use Python's built-in `json` module (no external dependencies)

2. **Clean Implementation**
   - Complete removal of YAML dependencies (pyyaml)
   - No legacy YAML loading or format detection needed
   - Single format approach for simplicity
   - All existing YAML files must be manually converted before use

3. **User Experience**
   - File dialogs only show JSON format (*.json)
   - Clear error messages if attempting to load non-JSON files
   - Clean, minified JSON for smaller file sizes with optional pretty-printing

4. **Performance Requirements**
   - JSON parsing should be very fast (native Python implementation)
   - Smaller file sizes than YAML due to more compact format
   - Efficient handling of large session files

### Rationale for JSON

1. **Industry Standard**: JSON is the most widely supported data format
2. **Native Support**: Built into Python standard library - no dependencies
3. **Better Tooling**: Extensive ecosystem of parsers, validators, and tools
4. **Type Safety**: Easier to validate and type-check JSON structures
5. **Performance**: Fastest parsing among text-based formats
6. **Simpler Spec**: JSON has minimal syntax and no ambiguities

## Codebase Research

### Current YAML Usage Analysis

#### Primary Implementation Files

1. **`wavescout/persistence.py`**
   - Core serialization/deserialization logic
   - Uses `yaml.safe_dump()` and `yaml.safe_load()`
   - Functions: `save_session()`, `load_session()`, `_serialize_node()`, `_deserialize_node()`
   - Handles complex nested structures (SignalNode trees, DisplayFormat, etc.)

2. **`wavescout/signal_names_view.py`**
   - Copy/paste functionality uses YAML for clipboard serialization
   - Lines 617, 622: `yaml.safe_dump()` and `yaml.safe_load()`
   - Used for temporary data exchange, not file persistence

3. **`scout.py`**
   - Main application file dialogs
   - Lines 987, 1008: File filter strings "YAML Files (*.yaml *.yml)"
   - Line 796: Temporary reload file with `.yaml` extension

#### Test Files Using YAML

- `tests/test_persistence.py`: Core persistence tests with `.yaml` temp files
- `tests/test_scout_integration.py`: Integration tests creating `.yaml` files
- `tests/test_session_alias_loading.py`: Session loading tests
- `tests/test_signals_copy_paste.py`: Copy/paste serialization tests
- `tests/test_clock_signal.py`: Clock signal persistence tests
- `tests/test_marker_integration.py`: Marker persistence tests
- `tests/test_fst_loading.py`: FST backend session tests
- `tests/test_vcd_aliases.py`: VCD alias session tests

#### Utility Scripts

- `take_snapshot.py`: Command-line tool accepting `.yaml` session files
  - Auto-detects session files by `.yaml`/`.yml` extension
  - Lines 77-82: File discovery logic

#### Dependencies

- `pyproject.toml`: 
  - Line 12: `pyyaml = "^6.0.2"`
  - Line 23: `types-PyYAML = "^6.0"` (dev dependency)

### Current Session File Structure

Based on `wave.yaml` example:
```yaml
db_uri: /path/to/waveform.vcd
root_nodes:
  - name: signal.path.name
    handle: 0
    format:
      render_type: bus
      data_format: unsigned
      color: '#00e676'
      analog_scaling_mode: scale_to_all
    nickname: ''
    is_group: false
    # ... more fields
viewport:
  left: 0.0
  right: 1.0
  # ... viewport settings
markers:
  - time: 1000
    label: "Marker A"
    color: "#FF0000"
cursor_time: 5000
analysis_mode:
  mode: "max"
  range_start: 0
  range_end: 10000
```

## Implementation Planning

### Dependencies Update

Update `pyproject.toml`:
```toml
# No new dependencies needed - JSON is built into Python!

# Remove YAML dependencies completely:
# DELETE: pyyaml = "^6.0.2"
# DELETE: types-PyYAML = "^6.0"
```

### File-by-File Changes

#### 1. `wavescout/persistence.py`

**Changes Required:**
- Replace yaml import with json from standard library
- Modify `save_session()`:
  - Change serialization to JSON format using json.dump()
  - Use `.json` extension exclusively
  - Add indent parameter for readability
- Modify `load_session()`:
  - Remove all YAML-related code
  - Use json.load() for JSON parsing
  - Simplified implementation with single format
- Remove obsolete functions:
  - No format detection needed
  - No migration helpers needed
  - Clean, single-format implementation

#### 2. `scout.py`

**Changes Required:**
- Update file dialog filters (lines 987, 1008):
  - Single filter: "Session Files (*.json)"
  - Remove all YAML file filters
- Update temporary reload file extension (line 796):
  - Change from `.yaml` to `.json`
- Remove any YAML-related logic:
  - No migration prompts
  - No dual-format support

#### 3. `wavescout/signal_names_view.py`

**Changes Required:**
- Replace yaml import with json
- Line 617: Change `yaml.safe_dump()` to `json.dumps()`
- Line 622: Change `yaml.safe_load()` to `json.loads()`
- Note: Plain JSON is sufficient for clipboard (no comments needed)

#### 4. `take_snapshot.py`

**Changes Required:**
- Update file detection logic (lines 77-82):
  - Look for `.json` files only
  - Remove `.yaml`/`.yml` file detection
- Update help text to reference `.json` format only

#### 5. Test Files

**Changes Required for each test file:**
- Update all temporary file extensions from `.yaml` to `.json`
- Remove any YAML-specific test cases
- Update serialization/deserialization assertions for JSON format
- No backwards compatibility tests needed

### Data Structure Mapping

YAML to JSONC conversion is straightforward as both support the same data types:

| YAML Type | JSONC Type | Notes |
|-----------|------------|-------|
| Scalar string | String | Quote all strings |
| Number | Number | Direct mapping |
| Boolean | Boolean | true/false (lowercase) |
| null | null | Direct mapping |
| List | Array | Direct mapping |
| Dictionary | Object | Direct mapping |
| Comments (#) | Not supported | Use _metadata field for info |

### Implementation Approach

Since we're removing all YAML support, the implementation becomes much simpler:

1. **Replace all YAML imports with json**
2. **Update all file extensions to .json**
3. **Remove any format detection or migration code**
4. **Single, clean implementation path**

### Simplified Implementation

```python
import json
from pathlib import Path
from typing import Optional
from datetime import datetime

def load_session(path: Path, backend_preference: Optional[str] = None) -> WaveformSession:
    """Load session from JSON file."""
    
    if not path.suffix.lower() == '.json':
        raise ValueError(f"Expected .json file, got {path.suffix}")
    
    with open(path, 'r') as f:
        data = json.load(f)
    
    # Deserialize session data
    return _deserialize_session(data, backend_preference)

def save_session(session: WaveformSession, path: Path) -> None:
    """Save session to JSON file."""
    
    # Ensure .json extension
    if not path.suffix.lower() == '.json':
        path = path.with_suffix('.json')
    
    # Serialize session data
    data = _serialize_session(session)
    
    # Add metadata as part of the data structure
    data['_metadata'] = {
        'version': '2.0',
        'generated': datetime.now().isoformat()
    }
    
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)
```

### JSON Structure Example

```json
{
  "_metadata": {
    "version": "2.0",
    "generated": "2025-08-19T10:30:00Z"
  },
  "db_uri": "/path/to/waveform.vcd",
  "root_nodes": [
    {
      "name": "TOP.cpu.clk",
      "handle": 0,
      "format": {
        "render_type": "bool",
        "data_format": "unsigned",
        "color": "#00e676"
      }
    }
  ],
  "viewport": {
    "left": 0.0,
    "right": 1.0,
    "total_duration": 10000
  }
}
```

## Testing Strategy

### Unit Tests

1. **Serialization Tests**
   - Test JSON writing with proper formatting
   - Test complex nested structures
   - Test special characters and escaping
   - Test large session files

2. **Deserialization Tests**
   - Test JSON loading
   - Test invalid file extension rejection
   - Test corrupt file handling
   - Test malformed JSON handling

3. **Data Integrity Tests**
   - Test round-trip preservation
   - Test all data types
   - Test empty sessions
   - Test edge cases

### Integration Tests

1. **File Dialog Tests**
   - Test JSON filter only
   - Test default .json extension
   - Test rejection of non-JSON files

2. **Session Round-Trip Tests**
   - Save as JSON, load, verify
   - Test with real waveform databases
   - Test session state preservation

3. **Clipboard Tests**
   - Test JSON serialization for copy/paste
   - Verify plain JSON format for clipboard

### Performance Tests

1. **Benchmark Loading Speed**
   - Test JSON parsing performance (should be very fast)
   - Test with various file sizes
   - Profile memory usage

2. **File Size Analysis**
   - Measure typical JSON file sizes
   - Test with complex sessions

## Acceptance Criteria

1. **Functional Requirements**
   - [ ] All session data preserved in JSON format
   - [ ] Sessions saved and loaded as JSON exclusively
   - [ ] Metadata stored within JSON structure
   - [ ] File dialogs show only JSON filter

2. **Implementation Requirements**
   - [ ] All YAML dependencies removed from codebase
   - [ ] No YAML imports remaining
   - [ ] Uses Python's built-in json module
   - [ ] All test files updated to use JSON

3. **Performance Requirements**
   - [ ] JSON loading very fast (native implementation)
   - [ ] File sizes smaller than YAML
   - [ ] No UI freezing during load/save

4. **Quality Requirements**
   - [ ] All tests pass with JSON format
   - [ ] Type checking passes (mypy strict)
   - [ ] Documentation updated to reference JSON

5. **User Experience**
   - [ ] Clear .json file extension in dialogs
   - [ ] Helpful error messages for invalid files
   - [ ] Clean, single-format experience