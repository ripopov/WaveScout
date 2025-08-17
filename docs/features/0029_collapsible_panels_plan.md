# WaveScout Collapsible Panel Redesign Feature Specification

## 1. User Stories and Requirements Analysis

### 1.1 Feature Overview
Redesign the WaveScout main window to use a modern, flexible panel layout with collapsible sidebars and bottom panel, similar to modern IDE interfaces like Visual Studio Code. The redesign will integrate the menu bar into the title bar and provide toggle buttons for panel visibility management.

### 1.2 User Stories

**As a WaveScout user:**
- I want to maximize waveform viewing area by hiding panels I'm not currently using
- I want quick toggle buttons to show/hide sidebars and bottom panel without using menus
- I want the interface to remember my panel visibility preferences between sessions
- I want a more modern, streamlined interface with the menu integrated into the title bar
- I want smooth transitions when panels are shown/hidden
- I want the main waveform view to always remain visible and resize appropriately

### 1.3 Detailed Requirements

#### 1.3.1 Window Layout Structure
- **Main Content Area**: WaveScoutWidget (always visible, central widget)
- **Left Sidebar**: DesignTreeView (collapsible, default width: 420px)
- **Right Sidebar**: New panel with placeholder content "Right Sidebar Content" (collapsible, default width: 250px)
- **Bottom Panel**: New panel with placeholder content "Bottom Panel Content" (collapsible, default height: 200px)

#### 1.3.2 Custom Title Bar
- Frameless window with custom title bar implementation
- Title bar height: 35px
- Background color: Follows current theme (dark: #252526, light: theme-appropriate)
- Integrated menu bar on the left side of title bar
- Application title centered in title bar
- Panel toggle buttons positioned before window controls (minimize, maximize, close)

#### 1.3.3 Panel Toggle Buttons
- Three toggle buttons in title bar for Left, Right, and Bottom panels
- Visual indicators:
  - Icon design: Simple geometric representations (sidebar rectangles with arrows, horizontal bar with arrow for bottom)
  - Checked state: Highlighted background color (#007ACC or theme accent)
  - Unchecked state: Transparent background
  - Hover effect: Subtle background highlight
- Button size: 30x30 pixels
- Positioned between title and minimize button

#### 1.3.4 Panel Behavior
- Panels hide/show with immediate effect (no animation initially)
- Main content area automatically resizes to fill available space
- Splitter handles remain functional when panels are visible
- Panel sizes preserved when toggling visibility
- Default sizes restored if panel size becomes invalid

#### 1.3.5 Menu Integration
- All existing menus preserved with same functionality
- Menu bar styled to match title bar theme
- Menu items remain fully accessible
- Keyboard shortcuts unchanged

#### 1.3.6 Persistence
- Panel visibility states saved to QSettings
- Panel sizes saved to QSettings  
- Restored on application startup
- Settings keys:
  - `panels/left_visible` (bool)
  - `panels/right_visible` (bool)
  - `panels/bottom_visible` (bool)
  - `panels/left_width` (int)
  - `panels/right_width` (int)
  - `panels/bottom_height` (int)

### 1.4 Technical Constraints
- Must maintain full compatibility with existing WaveScoutWidget
- Must preserve all existing menu functionality and shortcuts
- Must use PySide6/Qt6 components only
- Must follow project's strict typing requirements (no `Any` types)
- Must handle window dragging and resizing properly with frameless window
- Must support all existing themes and styles

### 1.5 Out of Scope
- Animation/transition effects (can be added in future iteration)
- Docking/undocking of panels
- Floating panels
- Panel content customization (using placeholders for now)
- Toolbar integration (remains as separate toolbar widget)

## 2. Codebase Research

### 2.1 Current Architecture Analysis

#### scout.py Structure
The current implementation uses:
- Standard QMainWindow with native title bar
- QSplitter (horizontal) containing DesignTreeView and WaveScoutWidget
- Traditional menu bar and toolbar
- No bottom or right panels
- Splitter sizes: [420, 980]

Key components:
- `WaveScoutMainWindow`: Main window class
- `DesignTreeView`: Left panel tree view (already exists)
- `WaveScoutWidget`: Main waveform viewing widget
- Menu creation in `_create_menus()`
- Toolbar creation in `_create_toolbar()`

#### MockUI.py Reference Implementation
Provides working example of:
- `CustomTitleBar` class with integrated menu
- Frameless window setup
- Panel toggle button implementation with custom icons
- Nested splitter architecture (horizontal inside vertical)
- Toggle methods for each panel
- Mouse event handling for window dragging

### 2.2 Key Integration Points

#### WaveScoutWidget (wavescout/wave_scout_widget.py)
- Self-contained widget with three synchronized panels
- Uses internal QSplitter for signal names, values, and canvas
- No modifications needed - will be placed in central area

#### DesignTreeView (wavescout/design_tree_view.py)
- Already designed as standalone widget
- Has signals for communication: `signals_selected`, `status_message`
- Event filter installation for keyboard handling
- No modifications needed - will be moved to left sidebar

## 3. Implementation Planning

### 3.1 New Components

#### CustomTitleBar Class
**Location**: `scout.py` (inline class, similar to LoaderSignals)
**Purpose**: Custom title bar with integrated menu and panel toggle buttons
**Key Methods**:
- `__init__`: Setup layout, create buttons, integrate menu bar
- `create_sidebar_icon`: Generate left/right sidebar toggle icons
- `create_bottom_panel_icon`: Generate bottom panel toggle icon
- `mousePressEvent`, `mouseMoveEvent`, `mouseReleaseEvent`: Handle window dragging
- `mouseDoubleClickEvent`: Toggle maximize on double-click

#### Panel Placeholder Widgets
**Location**: Created inline in `WaveScoutMainWindow.__init__`
**Purpose**: Temporary content for right sidebar and bottom panel
- Right sidebar: QFrame with QLabel("Right Sidebar Content")
- Bottom panel: QFrame with QLabel("Bottom Panel Content")

### 3.2 File Modifications

#### scout.py - Major Refactoring

**Class: WaveScoutMainWindow**

**Modifications to `__init__`**:
1. Add frameless window flag: `self.setWindowFlags(Qt.FramelessWindowHint)`
2. Create main vertical layout for title bar integration
3. Create and add CustomTitleBar instance
4. Restructure splitter architecture:
   - Create vertical splitter as primary container
   - Create horizontal splitter for left/center/right
   - Nest horizontal splitter inside vertical splitter
5. Create right sidebar widget (placeholder QFrame)
6. Create bottom panel widget (placeholder QFrame)
7. Reorganize widget addition order:
   - Add DesignTreeView to horizontal splitter (left)
   - Add WaveScoutWidget to horizontal splitter (center)
   - Add right sidebar to horizontal splitter (right)
   - Add bottom panel to vertical splitter (bottom)
8. Set default splitter sizes: horizontal [420, 730, 250], vertical [600, 200]
9. Store panel references as instance variables

**Modifications to `_create_menus`**:
- Change from `self.menuBar()` to `self.title_bar.menu_bar`
- Keep all menu structure and actions unchanged

**New Methods**:
- `toggle_left_sidebar`: Show/hide left panel, adjust splitter sizes
- `toggle_right_sidebar`: Show/hide right panel, adjust splitter sizes  
- `toggle_bottom_panel`: Show/hide bottom panel, adjust splitter sizes
- `_save_panel_states`: Save visibility and sizes to QSettings
- `_restore_panel_states`: Load visibility and sizes from QSettings
- `_connect_panel_toggles`: Connect toggle buttons to methods

**Modified Methods**:
- `_create_toolbar`: Ensure toolbar remains below title bar in layout
- `closeEvent`: Add call to `_save_panel_states`

### 3.3 Implementation Algorithm

#### Panel Toggle Logic
For each panel toggle method:
```
1. Check current visibility state
2. If visible:
   - Hide the panel widget
   - Get current splitter sizes
   - Set panel size to 0 in sizes array
   - Redistribute space to remaining visible widgets
   - Apply new sizes to splitter
3. If hidden:
   - Show the panel widget
   - Get current splitter sizes
   - Calculate space for panel (use saved size or default)
   - Reduce other widget sizes proportionally
   - Apply new sizes to splitter
4. Update toggle button checked state
5. Save state to QSettings
```

#### Window Dragging Implementation
```
1. On mouse press in title bar:
   - Check if not maximized
   - Store mouse position as drag start point
2. On mouse move with drag active:
   - Calculate position delta
   - Move window by delta
   - Update drag start point
3. On mouse release:
   - Clear drag start point
```

### 3.4 State Management

#### QSettings Keys
```
panels/left_visible: bool (default: True)
panels/right_visible: bool (default: True)  
panels/bottom_visible: bool (default: True)
panels/left_width: int (default: 420)
panels/right_width: int (default: 250)
panels/bottom_height: int (default: 200)
panels/horizontal_sizes: list[int] (for splitter state)
panels/vertical_sizes: list[int] (for splitter state)
```

#### Initialization Sequence
```
1. Create frameless main window
2. Setup custom title bar with menu
3. Create splitter structure
4. Create all panel widgets
5. Add widgets to splitters
6. Restore panel states from settings
7. Connect toggle button signals
8. Apply initial visibility states
```

## 4. Migration Strategy

### 4.1 Backward Compatibility
- All existing functionality preserved
- Menu items and shortcuts unchanged
- WaveScoutWidget operates identically
- DesignTreeView behavior unchanged
- Session loading/saving unaffected

### 4.2 Migration Steps
1. Add CustomTitleBar class to scout.py
2. Modify window initialization for frameless mode
3. Restructure splitter hierarchy
4. Add placeholder panels
5. Implement toggle methods
6. Add state persistence
7. Test all existing functionality

### 4.3 Rollback Plan
- Implementation is contained to scout.py
- Can revert to standard window by removing frameless flag
- Original splitter structure easily restored
- No changes to core waveform functionality

## 5. Testing Strategy

### 5.1 Functional Testing
- **Panel Toggles**: Each button hides/shows correct panel
- **Splitter Behavior**: Resizing works with all panel combinations
- **Menu Access**: All menu items remain functional
- **Keyboard Shortcuts**: All shortcuts work as before
- **Window Controls**: Minimize, maximize, close work properly
- **Window Dragging**: Can drag window by title bar
- **Double-click Maximize**: Title bar double-click toggles maximize

### 5.2 State Persistence Testing
- Panel visibility saved and restored correctly
- Panel sizes preserved across sessions
- Settings migration from old format handled
- Invalid settings handled gracefully

### 5.3 Integration Testing
- Waveform loading works normally
- Design tree interaction unchanged
- Signal selection and display correct
- All view synchronization maintained
- Theme changes applied to all components

### 5.4 Visual Testing
- Panels align properly without gaps
- Splitter handles visible and functional
- Title bar styling consistent with theme
- Toggle button states clearly visible
- No visual artifacts during toggle

## 6. Acceptance Criteria

### 6.1 Core Functionality
- [ ] Application starts with new panel layout
- [ ] Left sidebar shows DesignTreeView
- [ ] Center area shows WaveScoutWidget  
- [ ] Right sidebar shows placeholder content
- [ ] Bottom panel shows placeholder content
- [ ] All three toggle buttons present in title bar

### 6.2 Panel Management
- [ ] Left panel toggle hides/shows DesignTreeView
- [ ] Right panel toggle hides/shows right sidebar
- [ ] Bottom panel toggle hides/shows bottom panel
- [ ] Main content resizes appropriately
- [ ] Splitters remain functional when panels visible

### 6.3 Window Chrome
- [ ] Menu bar integrated into title bar
- [ ] All menus accessible and functional
- [ ] Window can be dragged by title bar
- [ ] Minimize, maximize, close buttons work
- [ ] Double-click title bar toggles maximize

### 6.4 Persistence
- [ ] Panel states saved on application close
- [ ] Panel states restored on application start
- [ ] Panel sizes preserved correctly
- [ ] Settings stored in appropriate format

### 6.5 Compatibility
- [ ] All existing waveform features work
- [ ] File loading/saving unchanged
- [ ] Keyboard shortcuts functional
- [ ] Theme switching works properly
- [ ] No regression in core functionality

