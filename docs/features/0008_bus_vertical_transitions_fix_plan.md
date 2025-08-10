# Bus Vertical Transitions Fix Plan

## 1. Requirements Analysis

- Problem: When rendering a bus, the transition from a region where the signal changes on every pixel (high-frequency toggling) to a stable region is drawn with a left-only slope ("<"), producing a pattern like `|||<====`.
- Desired behavior: All transitions should be drawn as vertical lines by default; only draw symmetrical slopes like `><` for transitions within sufficiently wide regions. Specifically, when a high-density region (vertical-only rendering) is followed by a stable region, the boundary at the start of the stable region must be a vertical line, not a left slope.
- Reproduction: Run `.venv/bin/python take_snapshot.py wave.yaml` and inspect the produced `snapshot.png`.
- Non-goals: No changes to data model, file formats, or UI controls.
- Performance: Maintain O(N) rendering; no noticeable regressions.

## 2. Codebase Research

Essential files:
- wavescout/signal_renderer.py — contains `draw_bus_signal()` responsible for bus rendering.
- wavescout/signal_sampling.py — defines `SignalDrawingData` and value fields used for bus captions.
- docs/features/0005_bus_transitions_plan.md — describes unified transition rendering approach already implemented.

Findings:
- `draw_bus_signal()` already implements a unified approach where transitions have symmetric slopes that collapse to vertical lines for narrow regions. It forces a vertical right transition when the next region is vertical-only (`next_is_vertical`) or when overall transition width is tiny (`force_vertical_close`).
- However, the left transition does not consider whether the previous region was vertical-only. This can result in a left-only slope at the start of a wide stable region when the previous region toggled every pixel, visually forming `|||<====`.

## 3. Data Model Design

- No changes required. The fix is purely in rendering logic.

## 4. Implementation Planning

File-by-File Changes:
- File Path: wavescout/signal_renderer.py
  - Function to Modify: `draw_bus_signal`
  - Nature of Changes:
    - Detect whether the previous region is "vertical-only" (very narrow) similar to how `next_is_vertical` is computed for the right edge.
    - If the previous region was vertical-only, render the left transition as a vertical line instead of symmetric slopes. This guarantees the transition between a high-frequency region and a stable region is vertical.
    - Keep existing logic for right transition (`force_vertical_close`) unchanged.
  - Integration Points:
    - Reuses existing constants (`RENDERING.BUS_TRANSITION_MAX_WIDTH`, `RENDERING.BUS_TRANSITION_SLOPE_FACTOR`).
    - No changes to `SignalDrawingData` or callers.

Algorithm Description:
1. For each region, compute `region_width`, `x_start`, `x_end`, and `actual_trans_width` (existing logic).
2. Determine `prev_is_vertical`:
   - If `i > 0`, compute `prev_region_width = current_x - prev_x`.
   - Consider vertical-only if `prev_region_width < 2` or `(transition_width < 1.0 and prev_region_width < 4)`.
3. When drawing the left transition:
   - If `skip_left_transition` (i == 0) OR `prev_is_vertical`, draw a vertical line at `x_start` and set `x_left_trans = x_start`.
   - Else draw symmetric slopes from `(x_start, y_middle)` to `(x_left_trans, y_top)` and `(x_left_trans, y_bottom)`.
4. The right transition logic remains as before, using `force_vertical_close` to ensure vertical closure when appropriate.

## 5. Performance Considerations
- The additional checks are O(1) per region and do not change overall O(N) complexity.
- No extra allocations or large computations are introduced.

## 6. Verification Plan
- Re-run `.venv/bin/python take_snapshot.py wave.yaml` to regenerate `snapshot.png`.
- Visually confirm that transitions from a high-frequency toggling region to a stable region are vertical (no left-only slope).
- Confirm that symmetric `><` transitions are still used when both adjacent regions are sufficiently wide.
- Run `pytest` to ensure no regressions.

## 7. Risks and Edge Cases
- Extremely narrow sequence of regions (e.g., alternating 1-pixel regions) should continue to render as vertical lines as before.
- When overall `transition_width` is very small due to density, both sides are already forced vertical; the new condition aligns the left side behavior with the right side.

## 8. Rollback Plan
- If visual regressions are observed, revert changes in `draw_bus_signal()` and re-evaluate the threshold values for detecting vertical-only previous regions.
