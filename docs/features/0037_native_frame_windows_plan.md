# Native Window Frame Support for Windows 11

## 1. Use Cases and Requirements Analysis

### Core Requirement
Support Windows 11 Snap Layouts and native window management features while keeping the custom window decorations on Linux where they work well.

### Specific Requirements from User Prompt
- Use native window frame on Windows 11 for Snap Layouts support
- Keep frameless window with custom decorations on Linux
- Reference implementation exists in `docs/examples/NativeFrame.py`

### Platform-Specific Behavior
- **Windows 11**: Use native frame with custom in-client title bar (removes caption but keeps frame)
- **Linux/Wayland**: Keep existing frameless window with custom decorations
- **Windows 10**: Same as Windows 11 (native frame approach works on Win10 too)
- **macOS**: Continue using frameless (not specifically mentioned, maintain current behavior)

### Technical Benefits
- Windows 11 Snap Layouts work natively (hover over maximize button)
- Native window resize/move behaviors preserved
- Better integration with Windows window management
- Consistent appearance across platforms while leveraging native features

## 2. Codebase Research

### Current Implementation Analysis

#### scout.py (Lines 85-358, 360-366)
- **CustomTitleBar class**: Custom title bar widget with menu bar integration
- **Frameless window**: Set via `Qt.FramelessWindowHint` at line 366
- **Window dragging**: Handled via `mousePressEvent`, `mouseMoveEvent` with system move support
- **Panel toggle buttons**: Left, right, bottom panel visibility controls
- **Window control buttons**: Minimize, maximize, close buttons
- **Menu bar integration**: Menu bar embedded in custom title bar

#### Key Components to Modify
1. **Window flags initialization** (line 366): Conditional based on platform
2. **CustomTitleBar class**: Keep for Linux, modify/replace for Windows
3. **Win32 API integration**: Add for Windows caption removal
4. **Platform detection**: Already has `platform` import (line 8)

### NativeFrame.py Example Analysis

#### Key Implementation Details
- **Win32 API usage**: Uses ctypes to call Windows APIs for caption removal
- **remove_win_caption function**: Removes WS_CAPTION while keeping frame
- **Platform detection**: `sys.platform.startswith("win")`
- **Header widget**: Custom header with search bar and window controls
- **ResizeHelper**: For Linux/Wayland resize support
- **Conditional window flags**: Different flags for Windows vs Linux

#### Critical Code Patterns
```python
# Windows: Keep native frame, remove caption
if IS_WIN:
    self.setWindowFlags(Qt.Window | Qt.CustomizeWindowHint | ...)
    # After show: remove_win_caption(hwnd)
else:
    # Linux: Frameless
    self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
```

## 3. Implementation Planning

### File-by-File Changes

#### **scout.py**
**Functions/Classes to Modify**:
- `WaveScoutMainWindow.__init__`: Add platform detection and conditional window flags
- `WaveScoutMainWindow.showEvent`: Add new method for Windows caption removal
- `CustomTitleBar`: Conditionally use based on platform
- Add new `NativeTitleBar` class for Windows
- Add Win32 API functions module-level

**Nature of Changes**:
1. Add Win32 API declarations using ctypes (before CustomTitleBar class)
2. Create NativeTitleBar class (simplified version of CustomTitleBar for Windows)
3. Modify window initialization to check platform
4. Add showEvent override to remove caption on Windows after window creation
5. Conditionally create title bar based on platform

**Integration Points**:
- Title bar creation in `__init__` (around line 412)
- Window flags setting (line 366)
- Menu bar integration needs to work with both title bar types

### Algorithm Descriptions

#### Platform Detection and Initialization
1. Check if running on Windows using `sys.platform.startswith("win")`
2. If Windows:
   - Set window flags with native frame options (no FramelessWindowHint)
   - Create NativeTitleBar instead of CustomTitleBar
   - Store flag to remove caption in showEvent
3. If Linux/Other:
   - Keep existing FramelessWindowHint
   - Use existing CustomTitleBar
   - No changes to current behavior

#### Win32 Caption Removal (Windows Only)
1. In showEvent (first show only):
   - Get window handle via `self.winId()`
   - Call `remove_win_caption(hwnd)` to strip caption
   - This preserves native frame for Snap Layouts

#### NativeTitleBar Design (Windows)
1. Simplified header without window dragging code
2. Keep menu bar integration
3. Keep panel toggle buttons
4. Remove window control buttons (use native ones)
5. No mouse event handlers for dragging (native handles it)

### Key Design Decisions

#### Conditional Title Bar Classes
- **CustomTitleBar**: Keep for Linux, includes all dragging/window control logic
- **NativeTitleBar**: New for Windows, simplified without window controls
- Both inherit from QWidget and share similar layout structure

#### Menu Bar Handling
- On Windows: Menu bar in NativeTitleBar, positioned normally
- On Linux: Menu bar in CustomTitleBar as currently implemented
- Ensure `self.title_bar.menu_bar` works for both

#### Panel Toggle Buttons
- Keep same functionality on both platforms
- Position consistently in both title bar implementations
- Share button creation/styling code if possible

### Testing Considerations
- Test on Windows 11 for Snap Layouts functionality
- Test on Windows 10 for compatibility
- Test on Linux to ensure no regression
- Verify menu functionality on both platforms
- Test window state changes (minimize, maximize, restore)
- Verify panel toggle buttons work correctly