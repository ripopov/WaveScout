# Feature: System Theme Support (Lean Plan)

## Introduction
WaveScout should respect the system theme (light/dark and platform styling) by relying on Qt's native palette and styles. Custom drawing inside WaveformCanvas remains as-is for optimal waveform clarity, but its time ruler must align in height with other panel headers to keep names, values, and waveforms perfectly aligned.

## Requirements
- Respect system theme for colors and widget styles (use Qt system palette and style).
- Keep WaveformCanvas custom drawing colors unchanged; only its time ruler height must align with other headers.
- Ensure all panel headers in WaveScoutWidget have the same height so names, values, and waveforms align.

## Data Model Changes
### Modified Classes
None.

### New Classes/Enums
None. Theme is handled by removing custom stylesheets and using the system palette; no ThemeManager infrastructure is introduced.

## Implementation

### 1. Use System Palette (remove hardcoded styles)
**File**: `wavescout/wave_scout_widget.py`
**Function**: `_apply_theme()`
**Changes**:
- Clear any custom (dark) stylesheet, letting Qt's system palette/style apply.
- Do not introduce or use ThemeManager/ThemeMode.
- Do not alter WaveformCanvas drawing colors.

### 2. Unify Header Heights Across Panels
**File**: `wavescout/wave_scout_widget.py`
**Function**: `_sync_header_heights()` (new)
**Changes**:
- Implement `_sync_header_heights()` to set a single fixed height on all QTreeView headers. Use `RENDERING.DEFAULT_HEADER_HEIGHT` as the unified value.
- Call `_sync_header_heights()` during UI setup and whenever layout/state is restored or content sizes change (e.g., from `_update_scrollbar_range()`).
- Pass the resolved header height to the canvas via `self._canvas.setHeaderHeight(height)`.

### 3. Make Time Ruler Honor the Header Height
**File**: `wavescout/waveform_canvas.py`
**Function**: `_draw_time_ruler`
**Changes**:
- Replace uses of `RENDERING.DEFAULT_HEADER_HEIGHT` with `self._header_height` for the ruler background rectangle, baseline, and tick positions, so the canvas time ruler height matches the headers set by the widget.

### 4. Tree View Styling (respect system theme)
**File**: `wavescout/signal_names_view.py`
**Classes**: `SignalNamesView`, `BaseColumnView`
**Changes**:
- Remove any hardcoded stylesheets if present.
- Ensure `setAlternatingRowColors(True)` relies on the system palette.
- Use system default selection colors (no custom overrides).

### 5. Main Window Setup
**File**: `scout.py`
**Functions**: `main()`, `WaveScoutMainWindow.__init__()`
**Changes**:
- Remove `app.setStyle("Fusion")` if present to use the native system style.
- Remove any custom tree view theming helpers (e.g., `_apply_design_tree_theme()`).
- Do not introduce ThemeManager; rely on Qt's palette propagation.

### 6. Optional: Lightweight live theme-change hook
- If desired later, implement `changeEvent` in `WaveScoutWidget` to detect `QEvent.PaletteChange` or `QEvent.StyleChange` and call `_sync_header_heights()` and/or `_apply_theme()` to re-apply alignment after theme switches.
- Avoid adding a ThemeManager or custom color scheme classes unless user-selectable themes are introduced in the future.

## Algorithms and Behaviors
- Theme use: No explicit detection is required; clearing stylesheets allows Qt to apply the current system theme automatically. Live changes can be picked up via `changeEvent` optionally.
- Header height: Use `RENDERING.DEFAULT_HEADER_HEIGHT` as the canonical height across headers and the canvas time ruler, synchronized by the widget.

## UI Integration
- Application matches system theme on startup using the platform's native style and palette.
- WaveformCanvas continues to use its custom COLORS for drawing; only the time ruler height is synchronized.
- All panel headers (names, values, analysis, and canvas time ruler) share the same height, ensuring alignment.

## Testing Approach
1. Platform coverage
   - Windows 11: Personalization > Colors (Light/Dark)
   - macOS: System Settings > Appearance (Light/Dark/Auto)
   - Linux KDE/GNOME: Theme switchers
2. Live theme switching (optional)
   - Start in light, switch to dark (and vice versa); verify widgets adopt system palette without artifacts.
3. Alignment verification
   - Confirm all panel headers, including the time ruler, have equal height.
   - Verify names/values align with waveform rows under different font sizes and DPI.
4. Canvas isolation
   - Ensure waveform colors are unchanged across themes; only header height synchronization affects the ruler.

## Performance Impact
- Minimal. Relying on system palette avoids heavy stylesheet processing; optional changeEvent handling is inexpensive and user-initiated.

## Implementation Notes
- Prefer native platform style over Fusion to match OS look-and-feel.
- Keep the plan small and focused: no ThemeManager, no alternate color scheme classes.
- The critical fix is making `_draw_time_ruler` read `self._header_height`, since the widget already passes the header height to the canvas.