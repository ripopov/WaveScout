# Dual FST Backend Support - Refactoring Plan

## User Stories and Requirements Analysis

### Core Requirement
Enable WaveScout to support two different FST waveform reader backends (pywellen and pylibfst) with runtime switching capability, 
while maintaining a clean abstraction layer that prevents backend-specific types from leaking into the GUI and data model layers.

### User Stories
1. As a user, I want to select between Wellen and libfst backends via Edit menu -> FST Loader -> Wellen/libfst
2. As a user, I understand that backend changes take effect only after reloading the waveform file
3. As a user, I expect the same functionality regardless of which backend is selected
4. As a developer, I want to work with library-agnostic interfaces in all GUI and model code
5. As a user, VCD files should always use pywellen backend (no selection needed)

### Key Requirements
- **Runtime Backend Selection**: Users can switch between backends without restarting the application
- **Deferred Application**: Backend changes take effect only when the next waveform file is loaded
- **Type Safety**: No pywellen or pylibfst types should leak outside the backend implementations
- **Protocol-Based Abstraction**: All components interact through the WaveformDBProtocol interface
- **Backward Compatibility**: Existing functionality must continue to work seamlessly
- **Performance**: Backend switching should not impact performance

## Codebase Research

### Current Architecture Analysis

#### Direct pywellen Dependencies Found
The following modules directly import pywellen types:
1. **wavescout/protocols.py**: Imports Var, Hierarchy, Signal, Waveform, TimeTable, Timescale
2. **wavescout/waveform_db.py**: Core implementation using pywellen
3. **wavescout/persistence.py**: Imports Var, Hierarchy for signal resolution
4. **wavescout/waveform_loader.py**: Imports Var, Hierarchy for node creation
5. **wavescout/design_tree_model.py**: Imports Hierarchy, Var for tree building
6. **wavescout/scope_tree_model.py**: Imports Hierarchy, Var for scope filtering

#### Backend API Comparison

Both pywellen and pylibfst share nearly identical APIs with these key differences:

**pylibfst specific**:
- `time_range: Optional[Tuple[int, int]]` instead of `time_table: TimeTable`
- FST-only support (no VCD)

**pywellen specific**:
- `time_table: Optional[TimeTable]` for full time access
- Supports both VCD and FST formats

Common interfaces:
- Hierarchy, Scope, Var, Signal classes with identical methods
- Same signal loading APIs (get_signal, load_signals_multithreaded)
- Same query interfaces (query_signal, all_changes)

### Type Leakage Analysis

The main issue is that pywellen types (Var, Hierarchy, Signal) are exposed in:
1. **protocols.py**: Protocol definition itself imports concrete types
2. **Public interfaces**: Methods return pywellen-specific objects
3. **Tree models**: Directly store and use Var objects
4. **Persistence**: Relies on Var objects for handle mapping

## Implementation Planning

### Phase 1: Create Backend-Agnostic Type System

#### File: wavescout/backend_types.py (NEW)
Create abstract base classes and protocols for all waveform types with "W" prefix (for Waveform):
- WVar (Protocol)
- WHierarchy (Protocol)  
- WSignal (Protocol)
- WScope (Protocol)
- WWaveform (Protocol)
- WTimeTable (Protocol)
- WTimescale (Protocol)

These protocols will define the interface contract without importing any backend.
The "W" prefix is concise and clearly indicates these are waveform-related protocol types.

#### File: wavescout/protocols.py
- Remove all pywellen imports
- Update WaveformDBProtocol to use W-prefixed protocol types
- Change method signatures to return WVar, WSignal, etc. instead of concrete types
- Add backend selection capability to protocol

### Phase 2: Create Backend Adapter Layer

#### File: wavescout/backends/base.py (NEW)
Define the backend adapter interface:
- WaveformBackend (ABC) - base class for all backends
- BackendFactory - factory for creating backend instances

#### File: wavescout/backends/pywellen_backend.py (NEW)
- PywellenBackend class implementing WaveformBackend
- Adapters wrapping pywellen types to implement W-prefixed protocols
- Handle VCD and FST file loading

#### File: wavescout/backends/pylibfst_backend.py (NEW)
- PylibfstBackend class implementing WaveformBackend  
- Adapters wrapping pylibfst types to implement W-prefixed protocols
- Handle FST file loading only

### Phase 3: Refactor WaveformDB

#### File: wavescout/waveform_db.py
- Remove direct pywellen imports
- Add backend selection parameter to __init__
- Use BackendFactory to instantiate appropriate backend
- Update all methods to work with W-prefixed protocol types
- Delegate actual waveform operations to backend adapter

### Phase 4: Update Dependent Modules

#### File: wavescout/persistence.py
- Remove pywellen imports
- Work with W-prefixed types from backend_types
- Update _resolve_signal_handles to use protocol methods

#### File: wavescout/waveform_loader.py
- Remove pywellen imports
- Update create_signal_node_from_wellen to accept WVar
- Rename function to create_signal_node_from_var

#### File: wavescout/design_tree_model.py
- Remove pywellen imports
- Store WVar references instead of concrete Var
- Update all hierarchy traversal to use protocol methods

#### File: wavescout/scope_tree_model.py
- Remove pywellen imports
- Work with WHierarchy through protocol

### Phase 5: Add Backend Selection UI

#### File: scout.py
- Add FST backend preference to application settings
- Create Edit menu -> FST Loader submenu with radio buttons
- Add action handlers to switch backends
- Store preference in QSettings

#### File: wavescout/waveform_controller.py
- Add method to handle backend preference switching
- Store the new backend preference in settings
- Display notification that change will take effect on next file load
- Do NOT reload current file automatically

### Phase 6: Testing Infrastructure

#### File: tests/test_backend_abstraction.py (NEW)
- Test both backends produce identical results
- Verify no type leakage
- Test backend switching functionality

#### File: tests/test_dual_backend.py (NEW)  
- Integration tests with both backends
- Performance comparison tests
- Edge case handling

## File-by-File Changes

### New Files
1. **wavescout/backend_types.py**
   - Define all W-prefixed protocols (WVar, WSignal, WHierarchy, etc.)
   - No imports from pywellen or pylibfst

2. **wavescout/backends/__init__.py**
   - Export backend factory and enums

3. **wavescout/backends/base.py**
   - WaveformBackend ABC
   - BackendFactory implementation
   - Backend selection enum

4. **wavescout/backends/pywellen_backend.py**
   - PywellenBackend implementation
   - Type adapters for pywellen objects

5. **wavescout/backends/pylibfst_backend.py**
   - PylibfstBackend implementation
   - Type adapters for pylibfst objects

### Modified Files

1. **wavescout/protocols.py**
   - Remove: All pywellen imports
   - Add: Import W-prefixed types from backend_types
   - Modify: All method signatures to use WVar, WSignal, WHierarchy, etc.

2. **wavescout/waveform_db.py**
   - Remove: pywellen imports
   - Add: Backend selection logic
   - Modify: Work through backend adapter

3. **wavescout/persistence.py**
   - Remove: pywellen imports
   - Modify: Use WVar type

4. **wavescout/waveform_loader.py**
   - Remove: pywellen imports
   - Modify: Use W-prefixed types

5. **wavescout/design_tree_model.py**
   - Remove: pywellen imports
   - Modify: Store and use WVar instances

6. **wavescout/scope_tree_model.py**
   - Remove: pywellen imports
   - Modify: Use WHierarchy

7. **scout.py**
   - Add: FST Loader menu in Edit menu
   - Add: Backend selection actions
   - Add: Settings persistence

## Algorithm Descriptions

### Backend Selection Algorithm
1. Check file extension (.vcd always uses pywellen, .fst uses selected backend)
2. If FST file:
   - Read user preference from QSettings
   - Create appropriate backend instance via factory
3. Pass backend to WaveformDB constructor
4. WaveformDB delegates all operations to backend
5. Backend preference changes are stored immediately but applied only on next file load

### Type Adapter Pattern
1. Each backend provides adapters that wrap native types
2. Adapters implement abstract protocols
3. All wavescout code works with protocol types
4. No instanceof checks needed - duck typing through protocols

## Performance Considerations

- Backend adapters should be thin wrappers with minimal overhead
- Signal caching remains in WaveformDB, not duplicated in backends
- Lazy loading strategies preserved across both backends
- Multi-threaded signal loading supported by both backends

## Phase Planning

### Phase 1: Core Abstraction (Priority: High)
- Create backend_types.py with all protocols
- Update protocols.py to use abstract types
- No functional changes yet

### Phase 2: Backend Implementation (Priority: High)
- Implement backend adapter layer
- Create pywellen and pylibfst backends
- Update WaveformDB to use backends

### Phase 3: UI Integration (Priority: Medium)
- Add FST Loader menu
- Implement backend switching
- Add settings persistence

### Phase 4: Testing & Validation (Priority: High)
- Comprehensive testing of both backends
- Verify identical behavior
- Performance benchmarking

Each phase is independently testable and maintains backward compatibility throughout the refactoring process.