"""WaveformController: A thin non-Qt view-model/controller for UI coordination.

This controller owns the current WaveformSession and exposes basic operations
for viewport manipulation, selection updates, cursor updates, and benchmark mode.

It uses a simple callback-based notification mechanism (no Qt dependencies) so
it can be unit-tested easily. UI widgets (like WaveScoutWidget) can subscribe to
these callbacks and update their views accordingly.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Iterable, Set

from .data_model import WaveformSession, Viewport, SignalNode, Marker, Time
from .config import COLORS, MARKER_LABELS


Callback = Callable[[], None]


@dataclass
class WaveformController:
    """Non-Qt controller for coordinating waveform UI state.

    Responsibilities:
    - Own and expose current session reference.
    - Own and manipulate viewport through operations (zoom/pan/fit/start/end).
    - Track selection (by SignalNode instance IDs) and benchmark mode flag.
    - Provide simple callback hooks to notify views of state changes.

    Notes:
    - Selection is stored as a set of node instance IDs to decouple the view
      from holding object references. The Session still maintains selected_nodes
      (List[SignalNode]) for backward compatibility; this controller will
      synchronize it when set_selection_by_ids is used.
    """

    session: Optional[WaveformSession] = None
    _selected_ids: Set[int] = field(default_factory=set)

    # Simple event callbacks registry
    _callbacks: Dict[str, List[Callback]] = field(default_factory=lambda: {
        "session_changed": [],
        "viewport_changed": [],
        "selection_changed": [],
        "cursor_changed": [],
        "benchmark_changed": [],
        "markers_changed": [],
    })

    # ---- Subscription API ----
    def on(self, event_name: str, callback: Callback) -> None:
        if event_name not in self._callbacks:
            self._callbacks[event_name] = []
        self._callbacks[event_name].append(callback)

    def off(self, event_name: str, callback: Callback) -> None:
        if event_name in self._callbacks:
            try:
                self._callbacks[event_name].remove(callback)
            except ValueError:
                pass

    def _emit(self, event_name: str) -> None:
        for cb in self._callbacks.get(event_name, []):
            try:
                cb()
            except Exception:
                # Fail-safe: do not propagate exceptions from UI callbacks
                pass

    # ---- Session / selection ----
    def set_session(self, session: WaveformSession) -> None:
        self.session = session
        # Sync selected IDs from session.selected_nodes
        self._selected_ids = {n.instance_id for n in session.selected_nodes}
        self._emit("session_changed")
        # Also emit viewport and cursor to allow immediate refresh
        self._emit("viewport_changed")
        self._emit("cursor_changed")
        self._emit("benchmark_changed")

    def set_selection_by_ids(self, ids: Iterable[int]) -> None:
        """Set selection given node instance IDs; sync Session.selected_nodes."""
        if not self.session:
            return
        new_ids = set(ids)
        if new_ids == self._selected_ids:
            return
        self._selected_ids = new_ids
        # Rebuild session.selected_nodes in document order
        selected: List[SignalNode] = []
        for node in self._iter_all_nodes():
            if node.instance_id in self._selected_ids:
                selected.append(node)
        self.session.selected_nodes = selected
        self._emit("selection_changed")

    def get_selected_ids(self) -> Set[int]:
        return set(self._selected_ids)

    # ---- Cursor / benchmark ----
    def set_cursor_time(self, time_value: int) -> None:
        if not self.session:
            return
        if self.session.cursor_time != time_value:
            self.session.cursor_time = int(time_value)
            self._emit("cursor_changed")

    def toggle_benchmark_mode(self) -> None:
        if not self.session:
            return
        self.session.canvas_benchmark_mode = not self.session.canvas_benchmark_mode
        self._emit("benchmark_changed")

    # ---- Marker operations ----
    def add_marker(self, index: int, time: Time, color: Optional[str] = None) -> None:
        """Add or update a marker at the specified index (0-8)."""
        if not self.session or index < 0 or index >= len(MARKER_LABELS):
            return
        
        # Ensure markers list is large enough
        while len(self.session.markers) <= index:
            # Extend with placeholder markers
            self.session.markers.append(Marker(time=0, label="", color=""))
        
        # Use default color if not specified
        if color is None:
            # Use existing marker color if updating, otherwise use default
            existing = self.session.markers[index]
            if existing and existing.color:
                color = existing.color
            else:
                color = COLORS.MARKER_DEFAULT_COLOR
        
        # Create or update marker
        label = MARKER_LABELS[index]
        self.session.markers[index] = Marker(time=time, label=label, color=color)
        self._emit("markers_changed")
    
    def remove_marker(self, index: int) -> None:
        """Remove marker at the specified index."""
        if not self.session or index < 0 or index >= len(self.session.markers):
            return
        
        if index < len(self.session.markers):
            # Replace with placeholder instead of None
            self.session.markers[index] = Marker(time=-1, label="", color="")
            self._emit("markers_changed")
    
    def update_marker_time(self, index: int, time: Time) -> None:
        """Update the timestamp of a marker."""
        if not self.session or index < 0 or index >= len(self.session.markers):
            return
        
        if index < len(self.session.markers):
            marker = self.session.markers[index]
            if marker and marker.time >= 0:  # Check if it's a valid marker
                marker.time = time
                self._emit("markers_changed")
    
    def update_marker_color(self, index: int, color: str) -> None:
        """Update the color of a marker."""
        if not self.session or index < 0 or index >= len(self.session.markers):
            return
        
        if index < len(self.session.markers):
            marker = self.session.markers[index]
            if marker and marker.time >= 0:  # Check if it's a valid marker
                marker.color = color
                self._emit("markers_changed")
    
    def get_marker(self, index: int) -> Optional[Marker]:
        """Get marker at the specified index."""
        if not self.session or index < 0 or index >= len(MARKER_LABELS):
            return None
        
        if index < len(self.session.markers):
            marker = self.session.markers[index]
            # Return None for placeholder markers
            if marker and marker.time >= 0:
                return marker
        return None
    
    def toggle_marker_at_cursor(self, index: int) -> None:
        """Toggle a marker at the current cursor position."""
        if not self.session or index < 0 or index >= len(MARKER_LABELS):
            return
        
        cursor_time = self.session.cursor_time
        existing_marker = self.get_marker(index)
        
        # Toggle behavior: remove if exists at same time, otherwise add/update
        if existing_marker and existing_marker.time == cursor_time:
            self.remove_marker(index)
        else:
            self.add_marker(index, cursor_time)
    
    def navigate_to_marker(self, index: int, pixel_offset: int = 10, canvas_width: int = 1000) -> None:
        """Navigate viewport to show marker at specified pixel offset from left edge.
        
        Args:
            index: Marker index (0-8)
            pixel_offset: Distance in pixels from left edge of viewport (default 10)
            canvas_width: Current canvas width in pixels for accurate offset calculation
        """
        if not self.session or index < 0 or index >= len(MARKER_LABELS):
            return
        
        marker = self.get_marker(index)
        if not marker:
            return  # No marker at this index
        
        vp = self.session.viewport
        if not vp or vp.total_duration <= 0:
            return
        
        # Get current viewport width in normalized units
        viewport_width = vp.right - vp.left
        
        # Convert pixel offset to normalized time units
        # Use actual canvas width for accurate conversion
        offset_normalized = (pixel_offset / float(canvas_width)) * viewport_width
        
        # Convert marker time to normalized position (0-1)
        marker_normalized = marker.time / vp.total_duration
        
        # Calculate new viewport position
        new_left = marker_normalized - offset_normalized
        new_right = new_left + viewport_width
        
        # Clamp to valid bounds with edge space
        edge_space = vp.config.edge_space
        min_allowed_left = -(viewport_width * edge_space)
        max_allowed_right = 1.0 + (viewport_width * edge_space)
        
        if new_left < min_allowed_left:
            offset = min_allowed_left - new_left
            new_left = min_allowed_left
            new_right = new_right + offset
        elif new_right > max_allowed_right:
            offset = new_right - max_allowed_right
            new_left = new_left - offset
            new_right = max_allowed_right
        
        # Update viewport
        vp.left, vp.right = new_left, new_right
        self._emit("viewport_changed")

    # ---- Viewport operations ----
    def zoom_to_fit(self) -> None:
        if not self.session:
            return
        vp = self.session.viewport
        vp.left, vp.right = 0.0, 1.0
        self._emit("viewport_changed")

    def go_to_start(self) -> None:
        if not self.session:
            return
        vp = self.session.viewport
        width = vp.width
        vp.left = 0.0
        vp.right = width
        self._emit("viewport_changed")

    def go_to_end(self) -> None:
        if not self.session:
            return
        vp = self.session.viewport
        width = vp.width
        vp.left = 1.0 - width
        vp.right = 1.0
        self._emit("viewport_changed")

    def pan_viewport(self, pan_distance: float) -> None:
        if not self.session:
            return
        vp = self.session.viewport
        new_left = vp.left + pan_distance
        new_right = vp.right + pan_distance
        width = vp.width
        edge_space = vp.config.edge_space
        min_allowed_left = -(width * edge_space)
        max_allowed_right = 1.0 + (width * edge_space)
        if new_left < min_allowed_left:
            offset = min_allowed_left - new_left
            new_left = min_allowed_left
            new_right = new_right + offset
        elif new_right > max_allowed_right:
            offset = new_right - max_allowed_right
            new_left = new_left - offset
            new_right = max_allowed_right
        vp.left, vp.right = new_left, new_right
        self._emit("viewport_changed")

    def zoom_viewport(self, zoom_factor: float, mouse_relative: Optional[float] = None) -> None:
        """Zoom viewport around a relative position (0..1), or center if None.
        zoom_factor < 1.0 zooms in, > 1.0 zooms out.
        """
        if not self.session:
            return
        vp = self.session.viewport
        center = mouse_relative if mouse_relative is not None else (vp.left + vp.right) / 2.0
        left_distance = center - vp.left
        right_distance = vp.right - center
        new_left = center - (left_distance * zoom_factor)
        new_right = center + (right_distance * zoom_factor)
        # Minimum zoom width
        min_width = self._get_minimum_zoom_width()
        if new_right - new_left < min_width:
            half = min_width / 2.0
            new_left = center - half
            new_right = center + half
        # Maximum width with edge space
        max_width = 1.0 + 2 * vp.config.edge_space
        if new_right - new_left > max_width:
            new_left = -vp.config.edge_space
            new_right = 1.0 + vp.config.edge_space
        vp.left, vp.right = new_left, new_right
        self._emit("viewport_changed")

    # ---- Helpers ----
    def _iter_all_nodes(self) -> Iterable[SignalNode]:
        if not self.session:
            return
        def walk(node: SignalNode) -> Iterable[SignalNode]:
            yield node
            for ch in node.children:
                yield from walk(ch)
        for root in list(self.session.root_nodes):
            yield from walk(root)

    def _get_minimum_zoom_width(self) -> float:
        if not self.session:
            return 1e-4
        vp = self.session.viewport
        if vp.total_duration <= 0:
            return 1e-4
        min_width = vp.config.minimum_width_time / vp.total_duration
        # timescale-based limit: 1 time unit -> half viewport
        timescale_min_width = (1.0 / vp.total_duration) * 2
        return max(min_width, timescale_min_width)
