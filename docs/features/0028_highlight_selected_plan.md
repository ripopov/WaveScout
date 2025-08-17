# Highlight Selected Waves Feature Specification

## 1. User Stories and Requirements Analysis

### 1.1 Feature Overview
The Highlight Selected Waves feature provides visual emphasis for selected signals in the waveform canvas, making it easier to track and focus on specific signals of interest. When enabled, selected signals in the SignalNamesView will have their background highlighted in the WaveformCanvas with a theme-aware color. This feature can be toggled via a menu option and persists across application sessions.

### 1.2 Core User Stories

#### Story 1: Toggle Highlight Mode

**Acceptance Criteria:**
- Menu item "View → Highlight Selected" toggles the feature
- Menu item shows checkmark when feature is enabled
- Toggling immediately triggers canvas repaint with updated highlighting
- Feature state persists across application restarts via QSettings

#### Story 2: Visual Signal Highlighting

**Acceptance Criteria:**
- Selected signals have their row background highlighted with theme-specific color
- Highlighting spans entire row width in canvas
- Highlighting renders behind signal waveforms (background layer)
- Non-selected signals maintain standard alternating row backgrounds
- Highlighting updates immediately when selection changes

#### Story 3: Theme-Aware Highlighting
**As a** user who switches between themes  
**I want** the selection highlight color to adapt to my chosen theme  
**So that** highlighted signals remain visible and aesthetically consistent

**Acceptance Criteria:**
- Each theme defines its own SELECTION_BACKGROUND color
- Selection highlight uses appropriate color for current theme
- Color provides sufficient contrast with waveform lines
- Theme changes immediately update highlight colors

#### Story 4: Multi-Signal Selection Support

**Acceptance Criteria:**
- All selected signals are highlighted when feature is enabled
- Supports both contiguous and non-contiguous selections
- Highlighting updates correctly as selection changes
- Performance remains smooth with many selected signals

### 1.3 Detailed Requirements

#### Functional Requirements
1. **Menu Integration**
   - Add "Highlight Selected" toggle item to View menu
   - Position after existing view options (grid, tooltips, etc.)
   - Show checkmark (✓) when enabled
   - Default state: disabled

2. **Settings Persistence**
   - Store toggle state in QSettings under key "view/highlight_selected"
   - Load saved state on application startup
   - Apply loaded state before first canvas render

3. **Canvas Rendering**
   - Modify row background rendering to check if signal is selected
   - Apply highlight color only when feature is enabled AND signal is selected
   - Preserve existing alternating row backgrounds for non-selected signals
   - Ensure highlight renders before signal waveforms (background layer)

4. **Theme Integration**
   - Add SELECTION_BACKGROUND field to ColorScheme dataclass
   - Define appropriate colors for each theme:
     - Default: Semi-transparent blue overlay
     - DarkOne: Accent color with low opacity
     - Dracula: Purple-tinted selection color
   - Colors should complement existing SELECTION color (used in tree view)

5. **Selection Tracking**
   - Use WaveformController's selection state (selected_ids)
   - Check node.instance_id against selected_ids for highlight decision
   - React to "selection_changed" events from controller

#### Non-Functional Requirements
1. **Performance**
   - Highlighting check must not impact rendering performance
   - Use efficient set lookup for selection checking (O(1))
   - Cache highlighting state per render cycle if needed

2. **Visual Design**
   - Highlight color must provide sufficient contrast
   - Should not obscure waveform details
   - Maintain visual hierarchy (signals remain primary focus)

3. **Compatibility**
   - Works with all signal types (BOOL, BUS, ANALOG, EVENT)
   - Compatible with all rendering modes and zoom levels
   - Functions correctly with row height scaling

## 2. Codebase Research

### 2.1 Key Files Analyzed

#### Theme System (`wavescout/theme.py`)
- **ColorScheme** class: Defines color palette for themes
- **ThemeManager** class: Manages theme switching and persistence
- Each theme defined in THEMES dictionary with complete ColorScheme
- Need to add SELECTION_BACKGROUND field to ColorScheme

#### Signal Names View (`wavescout/signal_names_view.py`)
- **SignalNamesView** class: Tree view showing signal hierarchy
- `_get_selected_signal_nodes()` method: Returns selected SignalNode objects
- Already integrates with WaveformController for selection management
- Selection changes trigger controller notifications

#### Waveform Canvas (`wavescout/waveform_canvas.py`)
- **WaveformCanvas** class: Main rendering widget
- `_draw_row()` method (line 934): Renders individual signal rows
  - Currently draws alternating backgrounds based on row index
  - Draws at y position with row_height
  - Background drawn before signal rendering
- `paintEvent()`: Main paint handler that triggers rendering
- Uses cached rendering with RenderParams for thread-safe drawing

#### Waveform Controller (`wavescout/waveform_controller.py`)
- Manages selection state via `_selected_ids` set
- Provides `set_selection_by_ids()` for updating selection
- Emits "selection_changed" events
- Selection stored as SignalNodeID (instance_id) values

#### Data Model (`wavescout/data_model.py`)
- **SignalNode** class: Has `instance_id` field for unique identification
- **WaveformSession**: Already has `selected_nodes` list
- Controller synchronizes selected_ids with session.selected_nodes

#### Main Widget (`wavescout/wave_scout_widget.py`)
- **WaveScoutWidget**: Top-level widget composition
- Coordinates between SignalNamesView, ValuesView, and Canvas
- Handles controller event subscriptions
- No direct QSettings usage (handled at application level)

### 2.2 Architecture Patterns Identified

1. **Rendering Pipeline**
   - Canvas uses cached rendering with worker threads
   - RenderParams passed to drawing functions
   - Background drawn in `_draw_row()` before signal content
   - Row-based rendering with viewport culling

2. **Selection Management**
   - Controller maintains canonical selection state
   - Selection tracked by instance IDs (decoupled from objects)
   - Event-based notification for selection changes
   - Views observe controller for updates

3. **Theme System**
   - ColorScheme dataclass defines all colors
   - Global COLORS reference updated on theme change
   - Theme changes broadcast via signals
   - Colors accessed via config.COLORS

4. **Settings Persistence**
   - QSettings used for application preferences
   - Theme preferences already saved/loaded
   - Settings managed at application level (scout.py)

## 3. Implementation Planning

### 3.1 Data Model Changes

#### File: `wavescout/config.py`
**Modifications to ColorScheme class:**
- Add field: `SELECTION_BACKGROUND: str = "#0000FF20"`  # Semi-transparent blue
- This provides default selection background color

### 3.2 Theme Updates

#### File: `wavescout/theme.py`
**Modifications to THEMES dictionary:**
- Add SELECTION_BACKGROUND to each theme's ColorScheme:
  - Default theme: `SELECTION_BACKGROUND="#09477140"` (matches SELECTION with ~25% opacity)
  - DarkOne theme: `SELECTION_BACKGROUND="#2C313C60"` (selection color with ~38% opacity)  
  - Dracula theme: `SELECTION_BACKGROUND="#44475A50"` (selection color with ~31% opacity)

### 3.3 Canvas Rendering Updates

#### File: `wavescout/waveform_canvas.py`
**Modifications to WaveformCanvas class:**

1. **Add instance variable:**
   - `_highlight_selected: bool = False` - Toggle state for highlighting
   - Initialize in `__init__` method

2. **Add toggle method:**
   - `set_highlight_selected(enabled: bool) -> None`
     - Sets `_highlight_selected = enabled`
     - Calls `self.update()` to trigger repaint
     - Invalidates cache if needed

3. **Modify `_draw_row()` method:**
   - Before current background drawing (line 936-938)
   - Check if highlighting is enabled and node is selected:
     ```
     # Determine background color
     if self._highlight_selected and node_info.get('is_selected', False):
         # Use selection background color
         bg_color = QColor(config.COLORS.SELECTION_BACKGROUND)
     elif row % 2 == 0:
         # Use alternating row color
         bg_color = QColor(config.COLORS.ALTERNATE_ROW)
     else:
         # Use default background
         bg_color = QColor(config.COLORS.BACKGROUND)
     
     # Draw background
     painter.fillRect(0, y, params['width'], row_height, bg_color)
     ```

4. **Modify render parameter generation:**
   - In method that creates RenderParams (before calling `_render_waveforms`)
   - Add selection state to node_info dictionaries:
     - Check if node.instance_id is in controller's selected_ids
     - Add 'is_selected' boolean to each node_info

5. **Connect to selection changes:**
   - In `set_model()` method, connect to controller's selection_changed event
   - On selection change, invalidate cache and update if highlighting enabled

### 3.4 Menu Integration

#### File: `scout.py` (main application)
**Modifications to MainWindow class:**

1. **Add instance variable:**
   - `_highlight_selected_action: QAction` - Menu action for toggle

2. **Create menu action in `_setup_menus()` method:**
   - Add to View menu after existing view options
   - Create QAction with text "Highlight Selected"
   - Set checkable=True
   - Connect triggered signal to toggle handler
   - Load initial state from QSettings

3. **Add toggle handler method:**
   - `_toggle_highlight_selected(checked: bool) -> None`
     - Save state to QSettings
     - Call canvas.set_highlight_selected(checked)

4. **Load settings on startup:**
   - In initialization or settings loading method
   - Read "view/highlight_selected" from QSettings (default: False)
   - Apply to action and canvas

### 3.5 Integration Points

1. **Settings Management**
   - Settings key: "view/highlight_selected"
   - Type: bool
   - Default: False
   - Load on application start
   - Save on toggle

2. **Controller Integration**
   - Canvas observes "selection_changed" events
   - Retrieves selected_ids from controller
   - Passes selection info through RenderParams

3. **Theme Changes**
   - Canvas already observes theme changes
   - New SELECTION_BACKGROUND color automatically applied
   - Existing theme change handling sufficient

## 4. Testing Strategy

### 4.1 Unit Tests

1. **Test Theme Colors**
   - Verify SELECTION_BACKGROUND defined for all themes
   - Check color format validity
   - Ensure sufficient contrast with backgrounds

2. **Test Canvas Highlighting**
   - Mock selection state
   - Verify correct background color applied
   - Test with highlighting enabled/disabled
   - Check alternating rows preserved when disabled

3. **Test Settings Persistence**
   - Save and load toggle state
   - Verify default value when not set
   - Test settings isolation from other preferences

### 4.2 Integration Tests

1. **Test Selection Synchronization**
   - Select signals in SignalNamesView
   - Verify canvas updates with highlighting
   - Test selection changes (add/remove/clear)
   - Check multi-selection scenarios

2. **Test Theme Switching**
   - Change theme with highlighting enabled
   - Verify new colors applied immediately
   - Test all theme combinations

3. **Test Performance**
   - Large number of signals (1000+)
   - Many selected signals (100+)
   - Rapid selection changes
   - Verify smooth scrolling and rendering

### 4.3 Manual Testing

1. **Visual Verification**
   - Highlight visibility in all themes
   - Contrast with signal waveforms
   - Behavior with different signal types
   - Row height scaling compatibility

2. **User Workflow**
   - Toggle via menu
   - Settings persistence across restarts
   - Selection methods (click, Ctrl+click, Shift+click)
   - Keyboard navigation with highlighting

## 5. Acceptance Criteria

### 5.1 Functional Acceptance
- [ ] "View → Highlight Selected" menu item present and functional
- [ ] Menu item shows checkmark when enabled
- [ ] Toggle state persists across application restarts
- [ ] Selected signals show background highlighting when enabled
- [ ] Highlighting updates immediately on selection changes
- [ ] Non-selected signals maintain standard backgrounds
- [ ] Feature works with all signal types
- [ ] Multi-selection highlighting works correctly

### 5.2 Visual Acceptance
- [ ] Highlight color appropriate for each theme
- [ ] Sufficient contrast between highlight and waveforms
- [ ] Highlighting doesn't obscure signal details
- [ ] Smooth visual transitions when toggling
- [ ] Consistent appearance across zoom levels

### 5.3 Performance Acceptance
- [ ] No noticeable rendering slowdown with highlighting
- [ ] Smooth scrolling maintained with many selections
- [ ] Quick response to selection changes
- [ ] Memory usage remains reasonable

## 6. Risk Assessment

### 6.1 Technical Risks
1. **Rendering Performance**
   - Risk: Selection checking could slow row rendering
   - Mitigation: Use efficient set lookup (O(1))
   - Consider caching selection state per render cycle

2. **Cache Invalidation**
   - Risk: Cached images may not update on selection change
   - Mitigation: Properly invalidate cache on selection events
   - Test cache behavior thoroughly

### 6.2 Visual Risks
1. **Color Contrast**
   - Risk: Highlight may not be visible in some themes
   - Mitigation: Carefully choose colors with testing
   - Consider accessibility guidelines

2. **Visual Noise**
   - Risk: Too many highlights could be distracting
   - Mitigation: Keep highlighting subtle
   - Provide easy toggle for users

## 7. Future Enhancements

1. **Customizable Colors**
   - Allow users to customize highlight color
   - Per-theme color preferences
   - Color picker in preferences dialog

2. **Highlight Modes**
   - Different highlight styles (border, gradient, pattern)
   - Intensity adjustment slider
   - Animated highlight for newly selected signals

3. **Advanced Selection Features**
   - Highlight related signals (same bus, clock domain)
   - Temporary highlight on hover
   - Selection groups with different colors

4. **Integration Features**
   - Export highlighted signals to separate file
   - Print/screenshot with highlighting preserved
   - Highlight persistence in session files