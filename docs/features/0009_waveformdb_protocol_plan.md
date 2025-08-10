# WaveformDB Protocol – Minimal, Clear Implementation Plan

## Objective
Decouple UI from WaveformDB internals by introducing a small typed protocol and refactoring the few remaining direct `_var_map` usages. Limit behavior discovery to the protocol and avoid risky changes around hierarchy/persistence.

## Protocol
- File: wavescout/protocols.py (NEW)
- Type: typing.Protocol named WaveformDBProtocol
- Methods (exact signatures):
  - find_handle_by_path(name: str) -> Optional[int]
  - find_handle_by_name(name: str) -> Optional[int]
  - get_handle_for_var(var: Any) -> Optional[int]
  - get_var(handle: int) -> Any
  - get_all_vars_for_handle(handle: int) -> list[Any]
  - iter_handles_and_vars() -> Iterable[tuple[int, list[Any]]]
  - get_var_bitwidth(handle: int) -> int
  - get_time_table() -> Any
  - get_timescale() -> Timescale

Notes:
- Iteration return type is Iterable[...] so existing List return conforms.
- Optionally expose has_handle(handle: int) -> bool if needed later; not required for this refactor.

## Minimal WaveformDB additions
- File: wavescout/waveform_db.py
- Add helpers that wrap existing mappings (O(1)):
  - find_handle_by_path(path: str) -> Optional[int]
    - Implementation: try find_handle_by_name(path); if None and no dot in path, try "TOP." + path; return Optional[int].
  - get_var_bitwidth(handle: int) -> int
    - Implementation: use first var from get_all_vars_for_handle(handle); if var has bitwidth(), return it; else 32.
  - (Optional) has_handle(handle: int) -> bool: return handle in _var_map.

## Refactors (direct and limited)
- wavescout/design_tree_view.py
  - _find_signal_handle: replace private lookups with waveform_db.find_handle_by_path(full_path).
  - Where handle-by-var is needed, call waveform_db.get_handle_for_var(var) (the protocol guarantees it). Remove hasattr guards for these protocol methods only.

- wavescout/waveform_item_model.py
  - _value_at_cursor: replace `_var_map` bitwidth logic with db.get_var_bitwidth(node.handle).

- wavescout/signal_sampling.py
  - generate_signal_draw_commands: replace `_var_map` bitwidth logic with waveform_db.get_var_bitwidth(signal.handle).

- wavescout/design_tree_model.py
  - _build_hierarchy: rely on iter_handles_and_vars() without hasattr guard; it is required by the protocol. Do not change hierarchy-related logic.

## Do NOT change (explicitly out of scope)
- Do not remove hasattr checks that protect hierarchy traversal or optional persistence helpers (e.g., add_var_with_handle) in persistence.py, scope_tree_model.py, or elsewhere. These concerns are not part of this UI-facing protocol.

## Type hints
- Where UI components accept a DB, type them as WaveformDBProtocol (import from wavescout.protocols). Concrete WaveformDB will conform.

## Algorithms (concise)
- find_handle_by_path
  - First try _var_name_to_handle via find_handle_by_name(path).
  - If not found and path lacks a dot, try "TOP." + path.
  - Return Optional[int].
- get_var_bitwidth
  - vars = get_all_vars_for_handle(handle); if vars and hasattr(vars[0], "bitwidth"), return vars[0].bitwidth(); else 32.

## Tests
- Update tests/test_data_format.py: stop reading db._var_map; instead iterate via db.iter_handles_and_vars() and use db.get_var_bitwidth(handle).
- Add tests/test_waveformdb_protocol.py to cover:
  - WaveformDB provides all protocol methods.
  - find_handle_by_path behavior with and without TOP prefix.
  - get_var_bitwidth defaults and normal cases.

## Performance
- All helpers delegate to existing O(1) maps and caches. No extra data structures. Overhead is a single method call.

## Rollout steps
1) Add wavescout/protocols.py with WaveformDBProtocol.  
2) Implement find_handle_by_path and get_var_bitwidth in WaveformDB (plus optional has_handle).  
3) Refactor the three direct `_var_map` usages and limited hasattr checks as listed above.  
4) Update type hints to WaveformDBProtocol in UI entry points.  
5) Fix tests to use public API and add protocol coverage.