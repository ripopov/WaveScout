# WaveformCanvas HiDPI/UIScaling Rendering Plan

## 1. Requirements Analysis

### Core Requirement
Fix blurry or pixelated fonts and lines in WaveformCanvas when UI scaling (e.g., 125%, 150%, 200%) is enabled. Other panels render text crisply under the same scaling; WaveformCanvas must match their visual quality.

### Specific Details from User
- Blurry/pixelated fonts and lines occur in WaveformCanvas when UI scaling is enabled (e.g., 150%).
- Other panels’ fonts look smooth and nice under the same conditions.
- The fix should target WaveformCanvas rendering path.

### Acceptance Criteria
- Text labels (time ruler, values, debug text) and lines (grid, waveforms, cursor, boundaries) appear crisp at 100%, 125%, 150%, 175%, and 200% scaling.
- No regression in appearance at 100% scaling.
- No significant performance degradation (±10%) compared to current rendering on the same machine and viewport.
- Screenshot comparison at 150% shows parity in sharpness between WaveformCanvas and adjacent Qt widgets (e.g., SignalNamesView tree).

## 2. Codebase Research

### Current Implementation Highlights
- WaveformCanvas renders into a cached QImage in `_render_to_image()` then blits via `painter.drawImage(0,0, image)`.
- The backing QImage is created using logical widget width/height: `QImage(params['width'], params['height'], ...)`. No device pixel ratio (DPR) handling is present.
- Render hints: `painter.setRenderHint(QPainter.Antialiasing, False)` for performance.
- Text and lines are drawn directly to the QImage; ruler and overlays are drawn in widget paint pass using the widget’s QPainter.
- Partial update path copies sub-rects from the low-DPI QImage.

### Likely Root Causes
- Using a 1x QImage on a HiDPI display leads Qt to scale it up for display, causing blur.
- Pens and text metrics computed in logical pixels without pixel snapping lead to half-pixel positioning under scaled transforms.
- Cache keys and invalidation do not consider DPR; the same low-res cache is reused after scale changes.

### Files to Consider (per guide)
- wavescout/waveform_canvas.py (primary)
- wavescout/signal_renderer.py (line and text drawing specifics per signal type)
- wavescout/config.py (rendering constants; may add DPR-aware toggles)
- wavescout/data_model.py (no expected changes)
- wavescout/signal_names_view.py (reference for crisp text; no changes planned)

## 3. Data Model Design
No data model changes are required. DPR is a runtime, environment-specific parameter. We will not persist it.

## 4. Implementation Planning

### Design Overview
Adopt a HiDPI-aware rendering pipeline:
- Use a device-pixel backing store (QImage) sized in physical pixels (width_px = ceil(width * dpr), height_px = ceil(height * dpr)).
- Set `image.setDevicePixelRatio(dpr)` and paint at device resolution, then draw the image at logical size (Qt will downscale accurately for non-integer DPR rendering paths while keeping text crisp when rendered at device scale).
- Compute and include DPR in render parameter hashing and caching to prevent reuse across scale changes.
- Ensure overlay/ruler drawing performed with the widget QPainter also accounts for DPR (primarily via integer alignment and avoiding fractional coordinates).
- Snap 1-pixel lines to pixel boundaries accounting for DPR to avoid blurry half-pixel strokes.
- Enable QPainter Antialiasing and TextAntialiasing globally (including overlays and all signal renderers). HighQualityAntialiasing may also be enabled to maximize visual quality.

### File-by-File Changes

#### File Path: wavescout/waveform_canvas.py
- Functions/Classes to Modify:
  - WaveformCanvas.paintEvent()
  - WaveformCanvas._collect_render_params()
  - WaveformCanvas._hash_render_params()
  - WaveformCanvas._render_to_image()
  - WaveformCanvas._paint_partial_update()
  - WaveformCanvas._draw_time_ruler(), _draw_grid_lines(), _paint_cursor(), _draw_boundary_lines(), _draw_debug_counters() (alignment tweaks)
- Nature of Changes:
  1. Determine devicePixelRatioF for the widget’s screen in paintEvent or via self.devicePixelRatioF(). Pass it in render params (e.g., params['dpr']).
  2. In _render_to_image():
     - Create QImage with size in physical pixels: w_px = ceil(width * dpr), h_px = ceil(height * dpr).
     - Call image.setDevicePixelRatio(dpr).
     - Create QPainter(image), set render hints: Antialiasing True, TextAntialiasing True, HighQualityAntialiasing True.
     - Scale logical drawing to device pixels by painter.scale(dpr, dpr) OR alternatively draw in device pixels consistently while converting all logical coordinates; prefer painter.scale(dpr, dpr) to avoid touching all draw math.
  3. Ensure all logical coordinates (start_time->x, row heights, y, font sizes) are computed in logical space before scale; painter scale will map to physical.
  4. Update _paint_partial_update(): draw sub-rects using source rect also multiplied by dpr-aware device logical mapping automatically handled because image has devicePixelRatio set; use painter.drawImage(update_rect, image, update_rect) still works if DPR set, but verify with tests; if not, compute source rect as update_rect adjusted by dpr.
  5. Include 'dpr' in _hash_render_params() to invalidate caches when scaling changes.
  6. When drawing overlays directly on the widget (cursor, boundaries, ruler):
     - Align 1px lines to integer logical coordinates so that after device transform they sit on pixel centers: e.g., use 0.5 offset technique only if Antialiasing is enabled; otherwise prefer cosmetic pens (width=0) to auto-scale to 1 device pixel lines regardless of DPR.
     - Use QPen with cosmetic set (default for width=0) where appropriate (grid, cursor, boundary) to ensure crisp 1-device-pixel lines.
  7. Fonts: create QFont with point size (default) rather than pixel size so Qt scales appropriately with DPR. Avoid manual pixelSize overrides.

- Integration Points:
  - Render param hashing and cache invalidation gains a new dimension (DPR).
  - Partial update path remains compatible but must use DPR-corrected image regions.

#### File Path: wavescout/signal_renderer.py
- Functions to Modify:
  - draw_digital_signal(), draw_bus_signal(), draw_analog_signal(), draw_event_signal()
- Nature of Changes:
  1. Ensure pens used for 1px lines are cosmetic (width=0) so they map to 1 device pixel across DPRs; for thicker lines, choose integer logical widths that scale cleanly.
  2. Avoid fractional pixel positions for crisp edges; while Antialiasing is enabled globally, integer alignment for key edges (grid, cursor, boundaries) still improves sharpness. Round x positions and y baselines to integers in logical space.
  3. For text rendering inside waveforms, keep using point-sized QFont; optionally use QStaticText for repeated labels to improve text rendering performance at higher DPR.
  4. Enable Antialiasing for all renderers (digital, bus, analog, event) to allow sub-pixel smoothing everywhere.

- Integration Points:
  - Use params['dpr'] if needed for specialized snapping or thresholds, but prefer painter scale + cosmetic pens to abstract DPR away.

#### File Path: wavescout/config.py
- Nature of Changes:
  - Add optional constants/toggles:
    - RENDERING.ENABLE_ANALOG_AA_HIDPI: bool = False (enable high-quality AA only for analog waveforms under HiDPI).
    - RENDERING.TEXT_RENDER_HINTS: tuple or keep hardcoded; likely unnecessary to persist.
  - No breaking changes; defaults keep current performance-first behavior.

### Algorithm/Procedure Notes
- Backing store creation:
  1. dpr = self.devicePixelRatioF() or self.window().devicePixelRatioF() if available.
  2. w_px = max(1, int(math.ceil(width * dpr)))
  3. h_px = max(1, int(math.ceil(height * dpr)))
  4. image = QImage(w_px, h_px, Format_ARGB32_Premultiplied)
  5. image.setDevicePixelRatio(dpr)
  6. painter = QPainter(image); painter.setRenderHint(QPainter.RenderHint.Antialiasing, True); painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True); painter.setRenderHint(QPainter.RenderHint.HighQualityAntialiasing, True); painter.scale(dpr, dpr) OR rely on Qt mapping if painting in logical when DPR set (with scale recommended for consistency).
- Pixel snapping for crisp lines:
  - Use cosmetic pens for 1px lines: pen.setWidth(0)
  - When using non-cosmetic pens, align to integers in logical coordinates.
- Cache invalidation:
  - Include dpr and font key (family, point size) in hash; at minimum include dpr and dimensions.

## 5. UI Integration
No menu or new UI controls. Visual updates only:
- Time ruler text and ticks should be crisp.
- Cursor line and grid should remain crisp and 1 device pixel wide.
- Maintain synchronization with other panels; no API changes required.

## 7. Performance Considerations
- Creating larger images at high DPR increases memory and paint time. Notes:
  - Antialiasing (including HighQualityAntialiasing and TextAntialiasing) is enabled globally by requirement; minor performance costs are acceptable.
  - Continue to render only when params hash changes.
  - Limit per-frame allocations; reuse QImage only if dimensions and DPR match; otherwise allocate new.
- Cache invalidation triggers:
  - DPR changes (monitor move, system scaling change, window moved to different screen)
  - Size changes, time range changes, visible rows changes, scroll changes.

## 8. Phase Planning
- Phase 1: DPR-aware backing store and cache invalidation (crispness fix) — Core functionality.
- Phase 2: Cosmetic pens and ruler/overlay alignment tweaks — Visual refinements.
