# Feature Plan: Controller-Centric Mutations with Typed Event Bus

## Requirements Analysis

Goal: Centralize all domain mutations behind a pure-Python controller API and propagate UI updates through a typed, lightweight Event Bus. Tighten type safety at the backend boundary using Protocols.

Key requirements:
- UI (WaveScoutWidget, SignalNamesView) and the Qt model (WaveformItemModel) must not mutate domain objects directly; they express intent via controller methods only.
- Introduce a small, typed Event Bus and explicit event dataclasses; UI and models subscribe and react to events.
- Strengthen typing at the session/backend boundary by replacing Any with a Protocol.
- Preserve existing behaviors (delete/group/move/rename/format changes, drag-and-drop) with no regressions.
- Keep code strictly typed per project guidelines (no Any; explicit Optional/TypeAlias/TypedDict as needed).

Non-functional:
- Maintain or improve responsiveness; allow a minimal, reset-based update path initially, optimizing later.
- Keep controller methods UI-free (no Qt types, no dialogs).

## Codebase Research

Essential Files to Examine:
- wavescout/data_model.py: Session and node structures, typing of waveform_db (boundary to backend)
- wavescout/waveform_controller.py: Central place to own mutation APIs
- wavescout/waveform_item_model.py: Drag-and-drop and structure changes in Qt model
- wavescout/signal_names_view.py: Context menu actions and edits (format, render type, rename)
- wavescout/wave_scout_widget.py: High-level widget wiring and structural actions
- wavescout/waveform_canvas.py: Redraw triggers (for event-driven updates)

Architecture Patterns to Consider:
- Command-like controller methods emitting events
- Event Bus with dataclass payloads; type-safe publish/subscribe
- Normalized viewport model and cache invalidation triggers

## Data Model Design

Changes within data_model.py:
- Strengthen the backend boundary type on WaveformSession:
  - Replace Optional[Any] waveform_db with Optional[WaveformDBProtocol].
  - Define/import WaveformDBProtocol in wavescout/protocols.py (only methods actually used by the app, e.g., get_signal, get_var_bitwidth, iter_handles, timescale/time range access).

Persistence:
- No new persisted fields. The change is purely typing for the session boundary (YAML unaffected).

Types and Aliases:
- Introduce precise payload types for events (TypeAlias, Literal) in events module.

## Implementation Planning

File-by-File Changes (no code here; nature of changes only):

1) wavescout/data_model.py
- Change field type: WaveformSession.waveform_db: Optional[WaveformDBProtocol]
- Update imports to use local protocols module

2) wavescout/application/events.py (new)
- Define dataclass events used by the app initially:
  - StructureChangedEvent: change_kind (Literal['move','delete','insert','group']), changed_ids (list[int]), optional parent_id, insert_row
  - FormatChangedEvent: id (int), fields (dict[str, str] or a stricter TypedDict if stable)
  - ViewportChangedEvent: old/new viewport bounds (float or Time type if available)
  - CursorMovedEvent: old_pos/new_pos (float or Time)
- Centralize shared type aliases if helpful

3) wavescout/application/event_bus.py (new)
- Minimal, type-safe publish/subscribe mechanism:
  - Subscribe by event type; enforce callable signature via Protocol or generic constraints
  - Publish validates payload type; logs or raises in debug on subscriber exceptions

4) wavescout/waveform_controller.py
- Add pure-Python mutation APIs (no Qt):
  - delete_nodes_by_ids(ids: Iterable[int]) -> None
  - group_nodes(ids: Iterable[int], name: str, mode: GroupRenderMode) -> None
  - move_nodes(order: list[int], new_parent_id: Optional[int], insert_row: int) -> None
  - set_data_format(id: int, fmt: DataFormat) -> None
  - set_height_scaling(id: int, value: int) -> None
  - set_render_type(id: int, render_type: RenderType, scaling: Optional[AnalogScalingMode] = None) -> None
  - rename_node(id: int, nickname: str) -> None
- Emit StructureChangedEvent or FormatChangedEvent as appropriate
- Keep any legacy callbacks temporarily but implement them via the Event Bus internally

5) wavescout/wave_scout_widget.py
- Replace direct structural mutations (e.g., delete/group) with controller calls
- Subscribe to typed events to trigger UI updates (e.g., repaint, model refresh)
- Ensure viewport/cursor handlers route through controller methods that emit Viewport/Cursor events

6) wavescout/signal_names_view.py
- Replace direct domain mutations in context menu handlers with controller calls:
  - set_data_format, set_height_scaling, set_render_type (and analog scaling), rename
- Remove ad-hoc model updates where the controller+events now drive refresh; temporarily allow model resets for correctness during transition

7) wavescout/waveform_item_model.py
- In dropMimeData and related helpers:
  - Parse DnD payload; call controller.move_nodes(...) instead of mutating the tree
  - Subscribe to StructureChangedEvent; initially perform beginResetModel/endResetModel on changes
  - Optionally, later optimize to fine-grained beginMoveRows/insert/remove based on event payload

8) wavescout/waveform_canvas.py
- Ensure relevant events (structure/format/viewport) trigger appropriate redraw requests

## Algorithm Descriptions

Event Bus:
- Maintain a dict[type, list[Subscriber]] where Subscriber is a callable with a specific signature per event type
- publish(event):
  1) Lookup list of subscribers for type(event)
  2) Invoke each safely; log exceptions; fail fast in debug
  3) No return aggregation; side-effect system

Controller Operations (examples):
- delete_nodes_by_ids(ids):
  - Validate ids exist; remove nodes from session tree; update parent/children arrays
  - Emit StructureChangedEvent(change_kind='delete', changed_ids=sorted(ids))
- move_nodes(order, new_parent_id, insert_row):
  - Compute source positions; detach nodes; insert into new parent at insert_row in provided order
  - Emit StructureChangedEvent(change_kind='move', changed_ids=order, parent_id=new_parent_id, insert_row=insert_row)
- set_data_format(id, fmt) / set_render_type(...):
  - Update node display format/render metadata
  - Emit FormatChangedEvent(id=id, fields={'format': str(fmt)}) or include more fields as needed

## UI Integration

Subscriptions:
- WaveScoutWidget subscribes to StructureChangedEvent and FormatChangedEvent to trigger canvas/model refresh and to Viewport/Cursor events to adjust rulers/cursors
- WaveformItemModel subscribes to StructureChangedEvent to refresh rows (reset initially)
- SignalNamesView triggers controller calls from context menu and keyboard shortcuts; let model refresh via events

Context Menu Integration (SignalNamesView._show_context_menu):
- Keep existing structure; actions now delegate to controller APIs; remove direct domain mutation

Visual Updates:
- WaveformCanvas.paintEvent remains; ensure event-driven repaint is requested when events are received

## Performance Considerations
- Initial approach: use beginResetModel/endResetModel on structural events for correctness
- Optimization path: switch to fine-grained insert/remove/move model signals when event payload provides sufficient context
- Cache invalidation: when formats change, invalidate only affected nodes/ranges; ensure no full redraw if unnecessary
- Memory: small overhead for subscriber lists and short-lived event objects

## Phase Planning
- Phase 1: Type boundary and Event Bus foundations (data_model Protocol change; events module; event bus module)
- Phase 2: Controller APIs and migration of widget/view handlers to controller calls
- Phase 3: WaveformItemModel DnD refactor and event-driven refresh (reset first, optimize later)
- Phase 4: Types, tests, and documentation updates across the touched modules

