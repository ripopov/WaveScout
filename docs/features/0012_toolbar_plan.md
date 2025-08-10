# WaveScout Toolbar Implementation Plan

## Feature Overview
Add a toolbar to the main application window with buttons for common waveform navigation actions: Zoom In, Zoom Out, Pan Left, Pan Right, and Reload Waveform. These actions should also be available in the menu bar if not already present.

## Requirements Analysis
- **Core Functionality**: Toolbar with 5 action buttons for common waveform operations
- **Actions Required**:
  1. Zoom In - Zoom into the waveform (already exists with `+` shortcut)
  2. Zoom Out - Zoom out of the waveform (already exists with `-` shortcut)  
  3. Pan Left - Shift viewport left (already exists with `Left Arrow` shortcut)
  4. Pan Right - Shift viewport right (already exists with `Right Arrow` shortcut)
  5. Reload Waveform - Reload the current waveform file (new functionality)
- **UI Requirements**: 
  - Toolbar should be docked below the menu bar
  - Buttons should have icons and tooltips
  - Actions should be synchronized between toolbar and menu bar
- **Menu Integration**: Ensure all toolbar actions are also accessible from the View menu

## Codebase Research Summary

### Current State
- **Main Window**: `scout.py` contains `WaveScoutMainWindow` (QMainWindow)
- **Menu Bar**: Already implemented with File and View menus
  - View menu has Zoom In/Out/Fit but lacks Pan Left/Right actions
  - File menu has Open but lacks Reload action
- **Actions**: Zoom and pan functionality already implemented in `WaveScoutWidget`
  - `_zoom_in()`, `_zoom_out()` - 2x zoom factor
  - `_pan_left()`, `_pan_right()` - 10% viewport width pan
  - Controller-based architecture with `WaveformController` handling operations
- **No Toolbar**: Currently no QToolBar implementation exists

### Key Integration Points
- Menu creation in `WaveScoutMainWindow._create_menus()`
- Action handlers in `WaveScoutWidget` class
- Keyboard shortcuts in `WaveScoutWidget.keyPressEvent()`
- Current waveform file path stored in `WaveScoutMainWindow.current_wave_file`

## Implementation Planning

### File-by-File Changes

#### 1. `/home/ripopov/PycharmProjects/WaveScout/scout.py`

**Class: `WaveScoutMainWindow`**

**New Methods to Add:**
- `_create_toolbar()` - Create and configure the main toolbar
- `_create_actions()` - Create QAction objects for toolbar/menu sharing
- `reload_waveform()` - Handle waveform reload functionality

**Methods to Modify:**
- `__init__()` - Call `_create_actions()` and `_create_toolbar()` after menu creation
- `_create_menus()` - Refactor to use shared QAction objects, add Pan Left/Right to View menu, add Reload to File menu
- `load_wave_file()` - Store the loaded file path for reload functionality

**New Instance Variables:**
- `self.zoom_in_action: QAction` - Shared action for zoom in
- `self.zoom_out_action: QAction` - Shared action for zoom out  
- `self.zoom_fit_action: QAction` - Shared action for zoom to fit
- `self.pan_left_action: QAction` - Shared action for pan left
- `self.pan_right_action: QAction` - Shared action for pan right
- `self.reload_action: QAction` - Shared action for reload waveform
- `self.toolbar: QToolBar` - Main application toolbar

**Integration Points:**
- Connect toolbar actions to existing `WaveScoutWidget` methods
- Maintain consistency between toolbar, menu, and keyboard shortcuts
- Update action enabled/disabled states based on waveform loading status

### Algorithm Descriptions

#### Reload Waveform Logic
1. Check if `current_wave_file` is set
2. If not set, show message that no file is loaded
3. If set:
   - Show progress dialog
   - Save current viewport state (optional, for better UX)
   - Call existing `load_wave_file()` with stored path
   - Restore viewport state if saved
   - Update status bar with reload completion message

#### Action State Management
1. On application start: Disable all waveform actions
2. After successful waveform load: Enable zoom/pan/reload actions
3. During file loading: Disable all actions to prevent conflicts
4. On load error: Keep actions in appropriate state

### UI Integration

#### Toolbar Configuration
- **Position**: Below menu bar, above main content area
- **Style**: Use standard Qt toolbar with icon+text or icon-only buttons
- **Button Layout**: 
  1. Zoom In
  2. Zoom Out
  3. Separator
  4. Pan Left
  5. Pan Right
  6. Separator
  7. Reload Waveform

#### Icon Requirements
- Use Qt standard icons where available (QStyle.StandardPixmap)
- Icons needed:
  - Zoom In: `SP_ArrowUp` or custom zoom-in icon
  - Zoom Out: `SP_ArrowDown` or custom zoom-out icon
  - Pan Left: `SP_ArrowLeft`
  - Pan Right: `SP_ArrowRight`
  - Reload: `SP_BrowserReload` or `SP_FileDialogDetailedView`

#### Tooltips and Status Tips
- Each action should have:
  - Tooltip: Brief description (e.g., "Zoom In (Plus)")
  - Status tip: Longer description shown in status bar
  - Keyboard shortcut displayed in tooltip

#### Menu Bar Updates
**View Menu Structure:**
```
View
├── Zoom In          (Plus)
├── Zoom Out         (Minus)
├── Zoom to Fit      (F)
├── ─────────────────
├── Pan Left         (Left)
├── Pan Right        (Right)
├── ─────────────────
├── UI Scaling       ►
└── Canvas Mode      ►
```

**File Menu Addition:**
```
File
├── Open...          (Ctrl+O)
├── Reload           (Ctrl+R)
├── ─────────────────
├── Save Session...
└── Load Session...
```

## Testing Considerations
- Verify toolbar buttons trigger correct actions
- Test keyboard shortcuts still work with toolbar present
- Ensure menu items and toolbar buttons stay synchronized
- Test reload with different file types (VCD, FST)
- Verify proper error handling for reload failures
- Test action enable/disable states during file operations

## Implementation Notes
- Follow strict typing requirements (no `Any` types)
- Use Qt's action sharing mechanism for toolbar/menu consistency
- Maintain existing keyboard shortcuts
- Preserve current zoom/pan behavior and factors
- Consider adding action group for mutually exclusive options in future