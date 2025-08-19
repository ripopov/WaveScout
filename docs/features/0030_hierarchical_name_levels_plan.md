# Hierarchical Name Display Levels Feature Specification

## 1. User Stories and Requirements Analysis

### 1.1 Feature Overview
Users need the ability to configure how many hierarchical levels are displayed for signal names in the SignalNamesView. This allows users to reduce visual clutter by showing only the relevant portions of deeply nested signal paths.

### 1.2 Detailed Requirements

#### Core Functionality
- **Configurable Display Levels**: Users can set the number of hierarchical levels to display (0 = full path, N = last N levels)
- **Persistent Settings**: The configuration is saved in QSettings and persists across application sessions
- **Immediate Visual Update**: Changes take effect immediately, repainting signal names without requiring application restart
- **Non-Session Setting**: This is a user preference, NOT part of the WaveformSession data model

#### User Interface Requirements
- **Menu Access**: View → "Hier Name Levels" menu item opens configuration dialog
- **Configuration Dialog**:
  - Title: "Set Hierarchical Name Levels"
  - Input field accepting only numeric digits (validated)
  - Three buttons: "Max", "Ok", "Cancel"
  - Enter key triggers "Ok" action
  - Escape key triggers "Cancel" action
- **Button Behaviors**:
  - "Ok": Apply the entered value and close dialog
  - "Cancel": Close dialog without changes
  - "Max": Set value to 0 (display full hierarchy) and apply

#### Display Behavior Examples
Given signal: `dut.cpu.alu.adder0`
- Setting = 0: `dut.cpu.alu.adder0` (full path)
- Setting = 1: `adder0`
- Setting = 2: `alu.adder0`
- Setting = 3: `cpu.alu.adder0`
- Setting = 4: `dut.cpu.alu.adder0`
- Setting > 4: `dut.cpu.alu.adder0` (capped at actual levels)

#### Edge Cases
- Signals with fewer levels than the setting display their full name
- Setting of 0 always shows the full hierarchical path
- Nicknames always take precedence over hierarchical display
- Groups show their full name (not affected by this setting)

### 1.3 Acceptance Criteria
1. ✓ Menu item "View → Hier Name Levels" is accessible
2. ✓ Dialog accepts only numeric input (0-999)
3. ✓ Setting persists across application restarts via QSettings
4. ✓ Signal names update immediately upon configuration change
5. ✓ Setting of 0 displays full hierarchical paths
6. ✓ Setting of N displays last N levels of hierarchy
7. ✓ "Max" button sets value to 0 and applies
8. ✓ Enter key and "Ok" button apply changes
9. ✓ Escape key and "Cancel" button discard changes
10. ✓ Nicknames are unaffected by this setting

## 2. Codebase Research

### 2.1 Current Implementation Analysis

#### Signal Name Display Logic
**File**: `wavescout/waveform_item_model.py`
- Method `_format_signal_name()` (lines 158-173) currently handles signal name formatting
- Already supports `SignalNameDisplayMode.LAST_N_LEVELS` mode
- Uses `self._session.signal_name_hierarchy_levels` (default: 2)
- Nicknames take precedence over hierarchical display

#### Data Model
**File**: `wavescout/data_model.py`
- `SignalNameDisplayMode` enum (line 243-245) defines display modes
- `WaveformSession` contains:
  - `signal_name_display_mode: SignalNameDisplayMode` (line 269)
  - `signal_name_hierarchy_levels: int = 2` (line 270)
- Currently part of session (saved in YAML), needs to move to QSettings

#### Signal Names View
**File**: `wavescout/signal_names_view.py`
- `SignalNamesView` class handles the tree view for signal names
- Uses `WaveformItemModel` for data display
- Context menu handled in `_show_context_menu()` method

#### Main Application Window
**File**: `scout.py`
- View menu created in `_create_actions()` method (lines 668-762)
- QSettings already imported but not currently used for preferences
- Theme settings use QSettings (via theme_manager)

### 2.2 Key Findings
1. **Existing Infrastructure**: The logic for displaying N levels already exists in `WaveformItemModel._format_signal_name()`
2. **Migration Required**: Need to move setting from WaveformSession to QSettings
3. **No QSettings Manager**: Project doesn't have a centralized settings manager yet
4. **Model Updates**: WaveformItemModel needs notification when setting changes

## 3. Implementation Planning

### 3.1 Architecture Design

#### Settings Management Strategy
- Create a simple settings manager for application-level preferences
- Use QSettings with organization="WaveScout" and application="WaveScout"
- Setting key: "SignalDisplay/HierarchyLevels" (integer, default: 0)
- Setting of 0 = show full path (changed from current default of 2)

#### Data Flow
1. User opens dialog via View menu
2. Dialog reads current value from QSettings
3. User modifies value and confirms
4. Dialog writes to QSettings
5. Dialog emits signal to notify views
6. WaveformItemModel reads new value and triggers repaint

### 3.2 File-by-File Changes

#### New File: `wavescout/settings_manager.py`
**Purpose**: Centralized application settings management
**Classes/Functions to Add**:
- `SettingsManager` class (singleton pattern)
- Methods: `get_hierarchy_levels()`, `set_hierarchy_levels()`, `hierarchy_levels_changed` signal
- Initialize QSettings with proper organization/application names
- Provide type-safe accessors for settings

#### New File: `wavescout/hierarchy_levels_dialog.py`
**Purpose**: Dialog for configuring hierarchy levels
**Classes/Functions to Add**:
- `HierarchyLevelsDialog(QDialog)` class
- Input validation for numeric-only entry
- "Max", "Ok", "Cancel" buttons
- Keyboard shortcuts (Enter for Ok, Escape for Cancel)
- Integration with SettingsManager

#### Modified File: `scout.py`
**Functions/Classes to Modify**:
- `_create_actions()`: Add action for "Hier Name Levels" menu item
- Add menu item to View menu after UI Scaling submenu
- Connect action to show HierarchyLevelsDialog
- Initialize SettingsManager on application startup

#### Modified File: `wavescout/waveform_item_model.py`
**Functions/Classes to Modify**:
- `__init__()`: Connect to SettingsManager.hierarchy_levels_changed signal
- `_format_signal_name()`: Read from SettingsManager instead of session
- Add slot `_on_hierarchy_levels_changed()` to handle setting changes and emit dataChanged

#### Modified File: `wavescout/data_model.py`
**Functions/Classes to Modify**:
- Remove or deprecate `signal_name_hierarchy_levels` from WaveformSession
- Keep `signal_name_display_mode` but default to LAST_N_LEVELS

#### Modified File: `wavescout/persistence.py`
**Functions/Classes to Modify**:
- Update session loading to ignore legacy `signal_name_hierarchy_levels` field
- Ensure backward compatibility when loading old sessions

### 3.3 Dialog Implementation Details

#### Dialog Layout
```
┌─────────────────────────────────┐
│ Set Hierarchical Name Levels    │
├─────────────────────────────────┤
│                                  │
│ Number of levels to display:    │
│ ┌──────────────────────────┐    │
│ │ 0                        │    │
│ └──────────────────────────┘    │
│                                  │
│ 0 = Show full hierarchy         │
│                                  │
│ ┌─────────┬────────┬────────┐  │
│ │   Max   │   Ok   │ Cancel │  │
│ └─────────┴────────┴────────┘  │
└─────────────────────────────────┘
```

#### Input Validation
- QLineEdit with QIntValidator(0, 999)
- Real-time validation feedback
- Clear error handling for invalid input

### 3.4 Performance Considerations

#### Repaint Optimization
- Use `dataChanged` signal with appropriate index ranges
- Only update column 0 (signal names column)
- Qt's view will handle efficient repainting

#### Settings Access
- Cache the setting value in WaveformItemModel to avoid repeated QSettings reads
- Update cache only when setting changes via signal

## 4. Testing Strategy

### 4.1 Unit Tests

#### Test: `test_settings_manager.py`
- Test default value retrieval
- Test setting persistence
- Test signal emission on change
- Test QSettings initialization

#### Test: `test_hierarchy_levels_dialog.py`
- Test input validation (numeric only)
- Test button behaviors
- Test keyboard shortcuts
- Test value persistence

#### Test: `test_signal_name_formatting.py`
- Test various hierarchy level settings
- Test edge cases (0 levels, more levels than path depth)
- Test nickname precedence
- Test group name handling

### 4.2 Integration Tests
- Test dialog opening from menu
- Test immediate UI update on setting change
- Test persistence across application restart
- Test interaction with session loading/saving

### 4.3 Manual Testing Checklist
1. Open dialog via View → Hier Name Levels
2. Enter various values (0, 1, 2, 10, invalid text)
3. Test Max button sets to 0
4. Test Enter key applies changes
5. Test Escape key cancels
6. Verify signal names update immediately
7. Restart application and verify persistence
8. Load different waveform files and verify setting remains

## 5. Migration and Compatibility

### 5.1 Backward Compatibility
- Old sessions with `signal_name_hierarchy_levels` field will be ignored
- Default to 0 (full path) for new installations
- Existing users will get default on first run after update

### 5.2 Future Enhancements
- Per-signal override for hierarchy display
- Smart abbreviation (e.g., `d.c.a.adder0` instead of just `adder0`)
- Tooltip showing full path on hover
- Quick toggle in toolbar for common values (1, 2, full)

## 6. Documentation Updates

### 6.1 User Documentation
- Add section to user manual about signal name display options
- Include screenshots of dialog and examples
- Document keyboard shortcuts

### 6.2 Developer Documentation
- Document SettingsManager API
- Add notes about QSettings usage patterns
- Document signal/slot connections for setting changes