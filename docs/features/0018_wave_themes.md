# Waveform Themes: Technical Specification

This document specifies a theming feature to make colors in the waveform canvas and signal renderer configurable at runtime via the main application menu. Three color themes are included: Default, DarkOne, and Dracula.

Date: 2025-08-11
Owner: WaveScout maintainers


## 1. Scope and Goals

- Allow users to switch between predefined color themes through the application UI (menu item in the main window).
- Apply theme colors consistently across waveform rendering (wavescout/waveform_canvas.py and wavescout/signal_renderer.py) and related UI surfaces that consume ColorScheme from wavescout/config.py.
- Persist the user’s theme choice across runs using QSettings.
- Maintain strict typing and avoid Any, following project typing guidelines.
- Minimize runtime overhead; switching themes should be O(1) updates plus repaint.

Non-goals (for this iteration):
- Arbitrary user-defined palettes (custom editor) — out of scope.
- Per-signal automatic color cycling — keep existing behavior; only the default signal color changes with theme.


## 2. Current State Summary

- Colors are centralized in wavescout/config.py dataclass ColorScheme, referenced widely by waveform_canvas.py, signal_renderer.py, markers_window.py, and others via `from .config import COLORS`.
- Many color roles used already:
  - BACKGROUND, BACKGROUND_DARK, BACKGROUND_INVALID
  - HEADER_BACKGROUND
  - ALTERNATE_ROW
  - BORDER, GRID, RULER_LINE, BOUNDARY_LINE
  - TEXT, TEXT_MUTED
  - CURSOR
  - MARKER_DEFAULT_COLOR
  - ROI_SELECTION_COLOR, ROI_GUIDE_LINE_COLOR, ROI_SELECTION_OPACITY
  - DEBUG_TEXT, DEBUG_BACKGROUND
  - DEFAULT_SIGNAL
- Some colors are currently hard-coded (e.g., analog undefined/high-Z overlays in signal_renderer.py).
- The main menu (scout.py) has a View menu; no theme submenu exists yet.

Implication: We can introduce a theme registry and runtime update mechanism to replace the global `COLORS` instance and trigger repaint of widgets.


## 3. Requirements

Functional:
1. Provide three selectable themes via menu: Default, DarkOne, Dracula.
2. Persist selected theme to QSettings under e.g. key `theme_name`.
3. On switch, immediately update colors used by:
   - Waveform canvas backgrounds, grid, ruler, boundary lines, text, cursor.
   - Signal renderer text and overlays (and adopt themed defaults for undefined/high-Z fills).
   - Marker default color (for new markers only; existing markers keep their chosen color).
   - ROI selection overlay and guide line.
4. Switching themes should repaint the canvas and any dependent widgets without requiring restart.
5. Maintain strict typing: `TypedDict` for theme maps where appropriate, or dataclasses with explicit fields.

Non-functional:
- No significant regression in paint performance.
- mypy strict passes: `make typecheck`.
- Unit tests added for persistence and runtime switching behavior hooks.


## 4. Theme Model and Roles

Introduce explicit color roles covering all currently used entries and a few missing ones to remove hard-coded colors:

- Backgrounds
  - BACKGROUND: canvas background for valid time range
  - BACKGROUND_DARK: canvas background for invalid/time-outside range
  - BACKGROUND_INVALID: off-range initial image background (kept for compatibility)
  - HEADER_BACKGROUND: time ruler background
  - ALTERNATE_ROW: alternating row fill
- Lines
  - BORDER: row borders
  - GRID: grid/tick minor lines if used
  - RULER_LINE: ruler ticks and axis line
  - BOUNDARY_LINE: lines at waveform min and max time bounds
- Text
  - TEXT: primary text
  - TEXT_MUTED: secondary text (e.g., analog min/max labels)
- Interaction/Overlays
  - CURSOR: cursor vertical line color
  - ROI_SELECTION_COLOR: ROI fill color (alpha applied separately)
  - ROI_SELECTION_OPACITY: float 0..1
  - ROI_GUIDE_LINE_COLOR: ROI guide line
  - MARKER_DEFAULT_COLOR: default color for new markers
- Debug
  - DEBUG_TEXT: overlay text color
  - DEBUG_BACKGROUND: RGBA tuple for overlay background box
- Signals
  - DEFAULT_SIGNAL: default signal stroke color when node format not set
  - ANALOG_UNDEFINED_FILL: RGBA for undefined region overlay (new)
  - ANALOG_HIGHZ_FILL: RGBA for high-impedance region overlay (new)

Data structure
- Continue using a frozen dataclass ColorScheme in config.py with explicit fields above.
- Add TypeAlias `RGBA = tuple[int, int, int, int]` for 32-bit color tuples.
- For string colors, keep CSS hex `#RRGGBB`.


## 5. Theme Palettes

Sources referenced:
- DarkOne (based on One Dark Notepad++): https://raw.githubusercontent.com/60ss/Npp-1-Dark/refs/heads/master/Npp-1-Dark.xml
- Dracula (Notepad++): https://raw.githubusercontent.com/dracula/notepad-plus-plus/master/Dracula.xml

The following colors are selected to best fit waveform rendering (clear contrast, distinct accents, readable text):

A) Default (existing) — keep current values from config.py
- BACKGROUND: #1e1e1e
- BACKGROUND_DARK: #1a1a1a
- BACKGROUND_INVALID: #1a1a1a
- HEADER_BACKGROUND: #2d2d30
- ALTERNATE_ROW: #2d2d30
- BORDER: #3e3e42
- GRID: #3e3e42
- RULER_LINE: #808080
- BOUNDARY_LINE: #606060
- TEXT: #cccccc
- TEXT_MUTED: #808080
- CURSOR: #ff0000
- ROI_SELECTION_COLOR: #4A90E2
- ROI_SELECTION_OPACITY: 0.20
- ROI_GUIDE_LINE_COLOR: #4A90E2
- MARKER_DEFAULT_COLOR: #00ff00
- DEBUG_TEXT: #ffff00
- DEBUG_BACKGROUND: (0, 0, 0, 200)
- DEFAULT_SIGNAL: #33C3F0
- ANALOG_UNDEFINED_FILL: (255, 0, 0, 100)
- ANALOG_HIGHZ_FILL: (255, 255, 0, 100)

B) DarkOne
- Base palette reference (Atom One Dark / NPP One Dark):
  - Background: #282C34, Foreground: #ABB2BF, Comments/Muted: #5C6370
  - Accents: Blue #61AFEF, Green #98C379, Purple #C678DD, Red #E06C75, Yellow #E5C07B, Orange #D19A66, Cyan #56B6C2
- Selected roles:
  - BACKGROUND: #282C34
  - BACKGROUND_DARK: #1F2329
  - BACKGROUND_INVALID: #1F2329
  - HEADER_BACKGROUND: #21252B
  - ALTERNATE_ROW: #2F333D
  - BORDER: #3E4451
  - GRID: #3E4451
  - RULER_LINE: #5C6370
  - BOUNDARY_LINE: #5A5F6A
  - TEXT: #ABB2BF
  - TEXT_MUTED: #5C6370
  - CURSOR: #E06C75  (red accent for clear visibility)
  - ROI_SELECTION_COLOR: #61AFEF (blue accent)
  - ROI_SELECTION_OPACITY: 0.22
  - ROI_GUIDE_LINE_COLOR: #61AFEF
  - MARKER_DEFAULT_COLOR: #98C379 (green accent)
  - DEBUG_TEXT: #E5C07B (yellow/orange for legibility)
  - DEBUG_BACKGROUND: (0, 0, 0, 200)
  - DEFAULT_SIGNAL: #56B6C2 (cyan, distinct on dark)
  - ANALOG_UNDEFINED_FILL: (224, 108, 117, 100)  # E06C75 at ~40% alpha
  - ANALOG_HIGHZ_FILL: (229, 192, 123, 100)     # E5C07B at ~40% alpha

C) Dracula
- Base palette reference (Dracula NPP):
  - Background: #282A36, CurrentLine: #44475A, Foreground: #F8F8F2, Comment: #6272A4
  - Accents: Cyan #8BE9FD, Green #50FA7B, Orange #FFB86C, Pink #FF79C6, Purple #BD93F9, Red #FF5555, Yellow #F1FA8C
- Selected roles:
  - BACKGROUND: #282A36
  - BACKGROUND_DARK: #1E2029
  - BACKGROUND_INVALID: #1E2029
  - HEADER_BACKGROUND: #343746
  - ALTERNATE_ROW: #2F3140
  - BORDER: #44475A
  - GRID: #44475A
  - RULER_LINE: #6272A4
  - BOUNDARY_LINE: #6C7391
  - TEXT: #F8F8F2
  - TEXT_MUTED: #6272A4
  - CURSOR: #FF79C6 (pink accent for high contrast)
  - ROI_SELECTION_COLOR: #BD93F9 (purple accent)
  - ROI_SELECTION_OPACITY: 0.22
  - ROI_GUIDE_LINE_COLOR: #BD93F9
  - MARKER_DEFAULT_COLOR: #50FA7B (green)
  - DEBUG_TEXT: #F1FA8C (yellow)
  - DEBUG_BACKGROUND: (0, 0, 0, 200)
  - DEFAULT_SIGNAL: #8BE9FD (cyan)
  - ANALOG_UNDEFINED_FILL: (255, 85, 85, 100)    # FF5555
  - ANALOG_HIGHZ_FILL: (241, 250, 140, 100)      # F1FA8C


## 6. Architecture and Integration

Introduce a lightweight ThemeManager to own the current ColorScheme and broadcast changes:

- Module: wavescout/theme.py
  - Enum ThemeName = { "Default", "DarkOne", "Dracula" }
  - Dataclass ColorScheme (reuse existing, extended roles) — or retain in config.py.
  - Registry: THEMES: dict[ThemeName, ColorScheme]
  - Signal source: a QObject subclass ThemeManager with `themeChanged` Signal(ColorScheme)
  - Methods:
    - current_theme_name() -> ThemeName
    - current() -> ColorScheme
    - set_theme(name: ThemeName) -> None: sets internal, emits themeChanged
    - load_from_settings(settings: QSettings) -> ThemeName
    - save_to_settings(settings: QSettings, name: ThemeName) -> None

- config.py
  - Extend ColorScheme with new roles ANALOG_UNDEFINED_FILL and ANALOG_HIGHZ_FILL and type alias RGBA.
  - Replace global `COLORS = ColorScheme()` with a function or proxy to ThemeManager, or keep a mutable module-level reference that ThemeManager updates on switch. Example:
    - Keep `COLORS: ColorScheme = THEMES[ThemeName.DEFAULT]` and update in ThemeManager.set_theme.
    - Ensure all users import COLORS at runtime, not bind at import-time constant? Python imports bind the object reference. We’ll rebind config.COLORS on theme switch. Callers should access `COLORS` at use-time (they do currently).

- scout.py (main window)
  - Add View -> Theme submenu with radio actions for each theme.
  - On selection: ThemeManager.set_theme(name); persist to QSettings; trigger UI updates.
  - At startup: read saved theme and apply before creating WaveScoutWidget.

- Waveform repainting
  - On themeChanged: wave_widget and any open dialogs (markers window) should repaint. For minimal change:
    - Connect ThemeManager.themeChanged to a handler in WaveScoutMainWindow that calls:
      - self.wave_widget.update(); and request internal sub-widgets to update if needed (canvas, names/values views). Canvas uses COLORS at paint time, so a simple update() is enough.
      - Optionally set application palette for splitter handle/other surfaces if desired (non-blocking).

- Remove hard-coded analog overlay RGBA in signal_renderer.py and replace with COLORS.ANALOG_UNDEFINED_FILL and COLORS.ANALOG_HIGHZ_FILL.


## 7. UI Design: Theme Menu

- Location: MenuBar -> View -> Theme
- Control: QActionGroup with three checkable QAction entries, mutually exclusive.
- Labels: "Default", "DarkOne", "Dracula"
- Behavior:
  - On select, call ThemeManager.set_theme(theme_name) and persist to QSettings under key `theme_name`.
  - Immediately repaint canvas and related widgets.
  - The selected item is checked based on current theme from settings at startup.


## 8. File-Level Changes

- wavescout/config.py
  - Add roles: ANALOG_UNDEFINED_FILL, ANALOG_HIGHZ_FILL, with types RGBA.
  - Consider moving themes into a separate module; however, to minimize changes, retain ColorScheme here and add a small ThemeName Literal or Enum (import-light).

- wavescout/theme.py (new)
  - Define ThemeName enum.
  - Define palette data for the three themes as ColorScheme instances.
  - Implement ThemeManager (QObject with Signal[ColorScheme]) and a `theme_manager` singleton.
  - Provide helper `apply_saved_theme(settings: QSettings) -> None`.

- wavescout/signal_renderer.py
  - Replace hard-coded analog undefined/high-Z fills with COLORS.ANALOG_UNDEFINED_FILL and COLORS.ANALOG_HIGHZ_FILL.

- wavescout/waveform_canvas.py
  - No logic change required; relies on COLORS at paint-time. Ensure any initial QImage fill uses COLORS.BACKGROUND_INVALID (already does). Repaint on theme change.

- wavescout/markers_window.py
  - Continues using COLORS.MARKER_DEFAULT_COLOR when creating new markers. No change beyond repaint when theme changes.

- scout.py
  - Add Theme submenu under View, with QActionGroup for theme selection.
  - Wire actions: on trigger -> ThemeManager.set_theme + save QSettings + trigger repaint.
  - During startup, read saved theme and apply before creating WaveScoutWidget (or immediately after, then repaint).
  - Connect themeChanged signal to a slot that calls `self.wave_widget.update()` and possibly repaint design_tree_view.


## 9. Persistence

- QSettings organization is already WaveScout/Scout.
- Key: `theme_name` value: one of "Default", "DarkOne", "Dracula".
- On first run: default to "Default".


## 10. Type Safety

- No Any. Use Enum for ThemeName.
- ColorScheme remains a @dataclass(frozen=True) with explicit typed fields.
- RGBA TypeAlias = tuple[int, int, int, int].
- ThemeManager signals typed via PySide6 Signal(ColorScheme) and methods fully annotated.


## 11. Testing Plan

- Unit tests (pytest):
  1. Theme registry provides three themes with all roles populated and valid formats (#RRGGBB strings, RGBA tuples).
  2. ThemeManager switching updates config.COLORS reference and emits themeChanged exactly once.
  3. signal_renderer uses theme analog overlay fields (monkeypatch COLORS to known overlay RGBA and verify they are used by inspecting painter operations via a stub or by indirect assertions where feasible).
  4. Persistence: mock QSettings in memory, verify load/save roundtrip.

- Integration tests:
  - Launch app in headless/offscreen, switch theme via ThemeManager programmatically, and assert no exceptions and that WaveformCanvas repaints (track a counter via temporary hook if available).


## 12. Backward Compatibility and Migration

- Existing imports `from .config import COLORS` remain valid; they get new fields but keep old names.
- Default theme reproduces current visuals.
- Existing sessions unaffected; only default marker color for newly created markers changes according to the active theme.


## 13. Performance Considerations

- Theme switching only rebinds a dataclass instance and triggers repaint; no heavy recomputation.
- Paint paths already query COLORS during paint, so no additional branching or caching is needed.


## 14. Implementation Steps (Checklist)

1. Extend ColorScheme with ANALOG_UNDEFINED_FILL and ANALOG_HIGHZ_FILL; add RGBA alias. ✓
2. Create wavescout/theme.py with ThemeName enum, theme palettes (Default, DarkOne, Dracula), ThemeManager singleton, and settings helpers. 
3. Update signal_renderer.py to use theme overlay colors instead of hard-coded RGBA. 
4. Add View -> Theme menu in scout.py; wire actions to ThemeManager and QSettings; connect themeChanged to repaint. 
5. On app start, apply saved theme. 
6. Add tests per Testing Plan. 
7. Run make test and make typecheck. 


## 15. Theme Palette Definitions (canonical)

The following constants should be used to construct ColorScheme instances in wavescout/theme.py.

- Default: use current config.py values exactly (see Section 5A).
- DarkOne: use Section 5B.
- Dracula: use Section 5C.


## 16. Open Questions / Future Work

- Consider theming of design tree view selection colors via Qt palette for deeper integration.
- Provide a user palette editor in a future release.
- Offer per-signal palette cycling or named color sets for improved multi-signal distinction.
