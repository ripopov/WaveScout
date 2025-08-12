"""Optimized waveform canvas widget with offline rendering pipeline."""

from PySide6.QtWidgets import QWidget, QScrollBar
from PySide6.QtCore import Qt, Signal, QModelIndex, QTimer, QRectF, QRect
from PySide6.QtGui import QPainter, QPen, QColor, QFont, QFontMetrics, QImage, QResizeEvent, QPaintEvent, QShowEvent, QMouseEvent, QCloseEvent, QKeyEvent
from typing import List, Tuple, Dict, Optional, Union
from .waveform_item_model import WaveformItemModel
from dataclasses import dataclass, field
from .data_model import SignalNode, SignalHandle, SignalNodeID, Time, TimeUnit, TimeRulerConfig, RenderType, Marker
from .signal_sampling import (
    SignalDrawingData,
    generate_signal_draw_commands
)
from .signal_renderer import (
    draw_digital_signal, draw_bus_signal, draw_analog_signal, draw_event_signal,
    NodeInfo, RenderParams
)
from . import config
RENDERING = config.RENDERING
MARKER_LABELS = config.MARKER_LABELS
import time as time_module
import math
from .protocols import WaveformDBProtocol
from .data_model import SignalRangeCache

@dataclass
class CachedWaveDrawData:
    """Cached drawing data for all visible signals."""
    draw_commands: Dict[SignalNodeID, SignalDrawingData] = field(default_factory=dict)  # instance_id -> commands
    viewport_hash: str = ""  # To check if cache is valid


class TransitionCache:
    """Cache for signal transitions to avoid repeated database queries."""

    def __init__(self, max_entries: int = RENDERING.TRANSITION_CACHE_MAX_ENTRIES):
        self.cache: Dict[Tuple[int, Time, Time], List[Tuple[Time, str]]] = {}
        self.access_times: Dict[Tuple[int, Time, Time], float] = {}
        self.max_entries = max_entries

    def get(self, handle: SignalHandle, start_time: Time, end_time: Time) -> Optional[List[Tuple[Time, str]]]:
        """Get transitions from cache if available."""
        key = (handle, start_time, end_time)
        if key in self.cache:
            self.access_times[key] = time_module.time()
            return self.cache[key]
        return None

    def put(self, handle: SignalHandle, start_time: Time, end_time: Time, transitions: List[Tuple[Time, str]]) -> None:
        """Store transitions in cache."""
        # Evict old entries if cache is full
        if len(self.cache) >= self.max_entries:
            self._evict_lru()

        key = (handle, start_time, end_time)
        self.cache[key] = transitions
        self.access_times[key] = time_module.time()

    def _evict_lru(self) -> None:
        """Evict least recently used entry."""
        if not self.access_times:
            return

        lru_key = min(self.access_times, key=lambda k: self.access_times.get(k, 0))
        del self.cache[lru_key]
        del self.access_times[lru_key]

    def clear(self) -> None:
        """Clear the cache."""
        self.cache.clear()
        self.access_times.clear()


class WaveformCanvas(QWidget):
    """Optimized widget for drawing waveforms with caching."""

    cursorMoved = Signal(object)  # Emitted when cursor is moved (using object to handle large integers)
    roiSelected = Signal(object, object)  # Emitted on ROI selection release: (start_time, end_time)

    def __init__(self, model: Optional[WaveformItemModel], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._model = model
        self._row_height = RENDERING.DEFAULT_ROW_HEIGHT  # Default/base row height
        self._header_height = RENDERING.DEFAULT_HEADER_HEIGHT  # Default header height - standard QTreeView header height
        self._time_scale = 1.0  # pixels per time unit
        self._row_heights: Dict[int, int] = {}  # Dictionary to store row heights by row index
        self._start_time = 0
        self._end_time = 1000000
        self._cursor_time = 0
        self._shared_scrollbar: Optional[QScrollBar] = None
        self._visible_nodes: List[SignalNode] = []  # Flattened list of visible nodes
        self._row_to_node: Dict[int, SignalNode] = {}   # Map row index to node
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self.setMinimumWidth(RENDERING.MIN_CANVAS_WIDTH)
        
        # Grid drawing state
        self._last_tick_positions: List[Tuple[float, int]] = []
        self._last_ruler_config: Optional[TimeRulerConfig] = None

        # Caching
        self._transition_cache = TransitionCache()
        self._last_viewport = (0, 0)  # Track viewport changes
        self._signal_range_cache: Dict[SignalNodeID, SignalRangeCache] = {}  # Cache for analog signal ranges
        
        # Single-threaded rendering - no thread pool needed

        # Deferred updates
        self._update_timer = QTimer()
        self._update_timer.setSingleShot(True)
        self._update_timer.timeout.connect(self._do_update)
        self._pending_update = False
        
        # Rendered image cache
        self._rendered_image: Optional[QImage] = None
        self._render_generation = 0  # Track render requests
        self._last_render_params_hash: Optional[int] = None  # Track last rendered params
        
        # Waveform time boundaries
        self._waveform_min_time: Time = 0
        self._waveform_max_time: Optional[Time] = None
        
        
        # Debug counters and timing
        self._paint_frame_counter = 0  # Incremented on every paintEvent
        self._render_complete_counter = 0  # Incremented when render completes
        self._last_paint_time_ms = 0.0  # Time taken by last paintEvent
        self._last_render_time_ms = 0.0  # Time taken by last render

        # ROI selection state
        self._roi_selection_active: bool = False
        self._roi_start_x: Optional[int] = None
        self._roi_current_x: Optional[int] = None
    
    def __del__(self) -> None:
        """Clean up on destruction."""
        pass

    def setSharedScrollBar(self, scrollbar: QScrollBar) -> None:
        """Set the shared vertical scrollbar."""
        self._shared_scrollbar = scrollbar
        if scrollbar:
            scrollbar.valueChanged.connect(self.update)

    def setHeaderHeight(self, height: int) -> None:
        """Set the header height to match the tree view's header."""
        # Ensure minimum header height
        height = max(height, RENDERING.DEFAULT_HEADER_HEIGHT)
        if self._header_height != height:
            self._header_height = height
            self.update()  # Trigger a repaint if header height changes

    def setRowHeight(self, height: int) -> None:
        """Set the row height to match other views."""
        self._row_height = height
        self.update()
        
    

    def setTimeRange(self, start_time: Time, end_time: Time) -> None:
        """Set the visible time range."""
        
        # Check if viewport changed significantly
        viewport_changed = (abs(self._start_time - start_time) > 1 or
                          abs(self._end_time - end_time) > 1)

        self._start_time = start_time
        self._end_time = end_time
        self._update_time_scale()

        # Clear cache if viewport changed significantly
        if viewport_changed:
            self._transition_cache.clear()
            # Don't clear rendered image - keep showing old one until new render completes

        self.update()

    def setCursorTime(self, time: Time) -> None:
        """Set the cursor position."""
        old_time = self._cursor_time
        self._cursor_time = time
        
        # If we have a rendered image and cursor is just moving within visible range,
        # do a minimal update by just repainting the cursor areas
        if (self._rendered_image and not self._rendered_image.isNull() and
            old_time >= self._start_time and old_time <= self._end_time and
            time >= self._start_time and time <= self._end_time):
            # Calculate the rectangles that need updating (old and new cursor positions)
            old_x = int((old_time - self._start_time) * self.width() / (self._end_time - self._start_time))
            new_x = int((time - self._start_time) * self.width() / (self._end_time - self._start_time))
            
            # Update regions around both cursor positions (with some padding)
            padding = RENDERING.CURSOR_PADDING
            width = RENDERING.CURSOR_WIDTH + 2 * padding + 1
            self.update(old_x - padding, 0, width, self.height())
            self.update(new_x - padding, 0, width, self.height())
        else:
            # Full update needed
            self.update()
        
    def setModel(self, model: WaveformItemModel) -> None:
        """Set the data model and connect to its signals."""
        # Disconnect from old model if exists
        if self._model:
            try:
                self._model.layoutChanged.disconnect(self._on_model_layout_changed)
                self._model.rowsInserted.disconnect(self._on_model_rows_changed)
                self._model.rowsRemoved.disconnect(self._on_model_rows_changed)
                self._model.dataChanged.disconnect(self._on_model_data_changed)
                self._model.modelReset.disconnect(self._on_model_reset)
            except:
                pass
        
        self._model = model
        
        # Connect to new model
        if self._model:
            self._model.layoutChanged.connect(self._on_model_layout_changed)
            self._model.rowsInserted.connect(self._on_model_rows_changed)
            self._model.rowsRemoved.connect(self._on_model_rows_changed)
            self._model.dataChanged.connect(self._on_model_data_changed)
            self._model.modelReset.connect(self._on_model_reset)
            
            # Update visible nodes
            self.updateVisibleNodes()
    
    def _on_model_layout_changed(self) -> None:
        """Handle model layout changes."""
        
        # Update visible nodes (this will also update row heights)
        self.updateVisibleNodes()
        
        # Always invalidate and update when layout changes
        # This ensures changes like height scaling are properly reflected
        self._rendered_image = None  # Invalidate rendered image
        self._last_render_params_hash = None  # Force re-render
        self.update()
    
    def _on_model_rows_changed(self, parent: QModelIndex, first: int, last: int) -> None:
        """Handle model row insertion/removal."""
        self.updateVisibleNodes()
        self._rendered_image = None  # Invalidate rendered image
        self._last_render_params_hash = None  # Force re-render
        self.update()
    
    def _on_model_data_changed(self, topLeft: QModelIndex, bottomRight: QModelIndex, roles: Optional[List[int]] = None) -> None:
        """Handle model data changes."""
        # Update if display data changed or if no roles specified (assume all changed)
        if roles is None or not roles or Qt.ItemDataRole.DisplayRole in roles or Qt.ItemDataRole.UserRole in roles:
            self._rendered_image = None  # Invalidate rendered image
            self._last_render_params_hash = None  # Force re-render
            self.update()
    
    def _on_model_reset(self) -> None:
        """Handle model reset (typically after beginResetModel/endResetModel)."""
        self.updateVisibleNodes()
        self._rendered_image = None  # Invalidate rendered image
        self._last_render_params_hash = None  # Force re-render
        self.update()

    def updateVisibleNodes(self) -> None:
        """Update the list of visible nodes based on expansion state."""
        self._visible_nodes = []
        self._row_to_node = {}
        self._row_heights = {}  # Reset row heights

        if not self._model:
            return
        
        # Update waveform time boundaries
        self._update_waveform_bounds()
        
        # Store model in local variable for type narrowing
        model = self._model

        def add_visible_nodes(parent_index: QModelIndex = QModelIndex(), row_offset: int = 0) -> int:
            """Recursively add visible nodes."""
            rows = model.rowCount(parent_index)
            current_row = row_offset

            for row in range(rows):
                index = model.index(row, 0, parent_index)
                node = model.data(index, Qt.ItemDataRole.UserRole)

                if node:
                    self._visible_nodes.append(node)
                    self._row_to_node[current_row] = node
                    # Store the scaled row height for this row
                    self._row_heights[current_row] = self._row_height * node.height_scaling
                    current_row += 1

                    # Add children if expanded
                    if model.hasChildren(index):
                        # Check if node is expanded (from data model)
                        is_expanded = node.is_group and node.is_expanded

                        if is_expanded:
                            current_row = add_visible_nodes(index, current_row)

            return current_row

        add_visible_nodes()
        
        
        # Don't automatically generate draw commands here - let paintEvent handle it
        # This prevents generating commands with wrong viewport before setTimeRange is called
    
    def _update_waveform_bounds(self) -> None:
        """Update the waveform time boundaries from the database."""
        if not self._model or not self._model._session or not self._model._session.waveform_db:
            self._waveform_max_time = None
            return
        
        try:
            # Get time table from waveform database
            time_table = self._model._session.waveform_db.get_time_table()
            if time_table and len(time_table) > 0:
                # The last time in the time table is the maximum time
                self._waveform_max_time = time_table[-1]
            else:
                self._waveform_max_time = None
        except:
            self._waveform_max_time = None

    def _update_time_scale(self) -> None:
        """Update time scale based on widget width and time range."""
        if self._end_time > self._start_time and self.width() > 0:
            self._time_scale = self.width() / (self._end_time - self._start_time)
        else:
            self._time_scale = 1.0

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Handle widget resize with deferred update."""
        super().resizeEvent(event)
        old_width = event.oldSize().width()
        new_width = event.size().width()
        
        self._update_time_scale()
        
        # Don't clear rendered image - it will be stretched but that's better than flickering

        # Defer update to avoid multiple repaints during resize
        self._pending_update = True
        self._update_timer.stop()
        self._update_timer.start(RENDERING.UPDATE_TIMER_DELAY)  # delay for smoother resize
        
    def showEvent(self, event: QShowEvent) -> None:
        """Handle widget show event."""
        super().showEvent(event)
        # Trigger initial render when widget is shown
        if self.width() > 0 and self.height() > 0:
            self.update()

    def _do_update(self) -> None:
        """Perform the actual update after timer expires."""
        if self._pending_update:
            self._pending_update = False
            self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        """Paint the waveforms with caching."""
        # Start timing
        paint_start_time = time_module.time()
        
        # Increment frame counter
        self._paint_frame_counter += 1
        
        painter = QPainter(self)
        # Enable high-quality text rendering; disable geometry antialiasing for crisp 1px lines
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        
        # Check if this is a partial update
        is_partial_update = self._should_do_partial_update(event)
        
        if is_partial_update:
            self._paint_partial_update(painter, event.rect())
        else:
            self._paint_full_update(painter)
        
        # Draw overlays (cursor, etc.)
        self._paint_overlays(painter, event.rect(), is_partial_update)
        
        # Calculate paint time
        self._last_paint_time_ms = (time_module.time() - paint_start_time) * 1000
        
        # Draw debug info if enabled
        self._paint_debug_info(painter, is_partial_update)
    
    def _should_do_partial_update(self, event: QPaintEvent) -> bool:
        """Determine if this is a partial update (cursor only)."""
        update_rect = event.rect()
        cursor_region_width = RENDERING.CURSOR_WIDTH + 2 * RENDERING.CURSOR_PADDING + 1
        return bool(update_rect.width() < cursor_region_width * 2 and 
                    self._rendered_image and 
                    not self._rendered_image.isNull())
    
    def _paint_partial_update(self, painter: QPainter, update_rect: QRect) -> None:
        """Handle partial update by redrawing only the affected region."""
        if self._rendered_image is not None:
            painter.drawImage(update_rect, self._rendered_image, update_rect)
    
    def _paint_full_update(self, painter: QPainter) -> None:
        """Handle full update by redrawing everything."""
        # Paint background
        self._paint_background(painter)
        
        # Draw grid if enabled
        self._paint_grid(painter)
        
        # Render and draw waveforms
        self._paint_waveforms(painter)
    
    def _paint_background(self, painter: QPainter) -> None:
        """Paint the background with different colors for valid/invalid time ranges."""
        self._paint_background_with_boundaries(painter)
    
    def _paint_grid(self, painter: QPainter) -> None:
        """Draw grid lines behind waveforms."""
        # Calculate time ruler positions first (needed for grid)
        self._calculate_and_store_ruler_info()
        
        # Draw grid lines if enabled
        if self._last_ruler_config is not None:
            if self._last_ruler_config.show_grid_lines and self._last_tick_positions:
                self._draw_grid_lines(painter, self._last_tick_positions, self._last_ruler_config)
    
    def _paint_waveforms(self, painter: QPainter) -> None:
        """Render and paint the waveforms."""
        # Check if we need to render
        render_params = self._collect_render_params()
        param_hash = self._hash_render_params(render_params)
        
        if param_hash != self._last_render_params_hash:
            # Parameters changed, need to re-render
            self._last_render_params_hash = param_hash
            self._render_generation += 1
            
            # Render synchronously
            image, generation, render_time_ms = self._render_to_image(render_params, self._render_generation)
            self._rendered_image = image
            self._render_complete_counter += 1
            self._last_render_time_ms = render_time_ms
        
        # Draw the rendered image if available
        if self._rendered_image and not self._rendered_image.isNull():
            painter.drawImage(0, 0, self._rendered_image)
    
    def _paint_overlays(self, painter: QPainter, update_rect: QRect, is_partial_update: bool) -> None:
        """Paint overlays on top of waveforms (boundary lines, ruler, markers, cursor, ROI)."""
        # Draw boundary lines
        if not is_partial_update:
            self._draw_boundary_lines(painter)
        
        # Draw time ruler
        if not is_partial_update:
            self._draw_time_ruler(painter)
        
        # Draw ROI overlay before markers and cursor for proper layering
        self._paint_roi_overlay(painter)
        
        # Draw markers (before cursor so cursor is always on top)
        self._paint_markers(painter, update_rect, is_partial_update)
        
        # Draw cursor
        self._paint_cursor(painter, update_rect, is_partial_update)
    
    def _paint_markers(self, painter: QPainter, update_rect: QRect, is_partial_update: bool) -> None:
        """Draw markers if they're visible."""
        if not self._model or not self._model._session:
            return
            
        markers = self._model._session.markers
        if not markers:
            return
            
        for i, marker in enumerate(markers):
            # Skip placeholder markers (time < 0)
            if marker and marker.time >= 0 and marker.time >= self._start_time and marker.time <= self._end_time:
                x = int((marker.time - self._start_time) * self.width() / 
                       (self._end_time - self._start_time))
                
                # Only draw marker if it's in the update region (or full update)
                marker_padding = RENDERING.MARKER_WIDTH + 2
                if not is_partial_update or (x >= update_rect.left() - marker_padding and 
                                            x <= update_rect.right() + marker_padding):
                    # Draw the vertical line
                    pen = QPen(QColor(marker.color))
                    pen.setWidth(RENDERING.MARKER_WIDTH)
                    painter.setPen(pen)
                    painter.drawLine(x, 0, x, self.height())
                    
                    # Draw the label at the top
                    if i < len(MARKER_LABELS):
                        label = MARKER_LABELS[i]
                        font = QFont(RENDERING.FONT_FAMILY, RENDERING.FONT_SIZE_SMALL)
                        painter.setFont(font)
                        
                        # Draw label background for readability
                        fm = QFontMetrics(font)
                        text_rect = fm.boundingRect(label)
                        text_rect.moveTopLeft(QRect(x - text_rect.width() // 2, 2, 0, 0).topLeft())
                        
                        # Semi-transparent background
                        painter.fillRect(text_rect.adjusted(-2, -1, 2, 1), 
                                       QColor(0, 0, 0, 180))
                        
                        # Draw the label text
                        painter.setPen(QColor(marker.color))
                        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, label)
    
    def _paint_cursor(self, painter: QPainter, update_rect: QRect, is_partial_update: bool) -> None:
        """Draw the cursor if it's visible."""
        if self._cursor_time >= self._start_time and self._cursor_time <= self._end_time:
            x = int((self._cursor_time - self._start_time) * self.width() / 
                   (self._end_time - self._start_time))
            
            # Only draw cursor if it's in the update region (or full update)
            if not is_partial_update or (x >= update_rect.left() - RENDERING.CURSOR_PADDING and 
                                        x <= update_rect.right() + RENDERING.CURSOR_PADDING):
                pen = QPen(QColor(config.COLORS.CURSOR))
                pen.setWidth(0)  # cosmetic 1 device-pixel
                painter.setPen(pen)
                painter.drawLine(x, 0, x, self.height())
    
    def _paint_debug_info(self, painter: QPainter, is_partial_update: bool) -> None:
        """Draw debug information if not a partial update."""
        if not is_partial_update:
            self._draw_debug_counters(painter)
    
    
    def _hash_render_params(self, params: RenderParams) -> int:
        """Create a hash of render parameters for quick comparison."""
        # Build key params list
        key_params: List[Union[float, int, bool, tuple[object, ...]]] = [
            params['width'],
            params['height'],
            params.get('dpr', 1.0),
            params['start_time'],
            params['end_time'],
            # Don't include cursor_time - cursor is drawn separately
            params['scroll_value'],
            params.get('header_height', 35),  # Include header height
        ]
        
        # Add visible nodes info
        key_params.append(len(params['visible_nodes_info']))
        # Include node handles, height scaling, data format, and COLOR to detect changes
        if 'visible_nodes' in params:
            key_params.append(
                tuple((node.handle, node.name, node.height_scaling, 
                       node.format.data_format if not node.is_group else None,
                       node.format.color if not node.is_group else None)  # Include color for theme changes
                      for node in params['visible_nodes'])
            )
        # Include row heights to detect layout changes
        if 'row_heights' in params:
            key_params.append(tuple(params['row_heights'].items()))
        
        return hash(tuple(key_params))
    
    def _collect_render_params(self) -> RenderParams:
        """Collect all parameters needed for rendering."""
        # Get scroll position
        scroll_value = 0
        if self._shared_scrollbar:
            scroll_value = self._shared_scrollbar.value()
        
        
        # Only copy visible nodes info, not the actual nodes
        visible_nodes_info: List[NodeInfo] = []
        for i, node in enumerate(self._visible_nodes):
            node_info: NodeInfo = NodeInfo(
                name=node.name,
                handle=node.handle,
                is_group=node.is_group,
                format=node.format,
                render_type=node.format.render_type,
                height_scaling=node.height_scaling,
                instance_id=node.instance_id
            )
            visible_nodes_info.append(node_info)
        
        # Get waveform_db reference if available
        waveform_db = None
        if self._model and self._model._session and self._model._session.waveform_db:
            waveform_db = self._model._session.waveform_db
        
        return RenderParams(
            width=self.width(),
            height=self.height(),
            dpr=float(self.devicePixelRatioF()),
            start_time=self._start_time,
            end_time=self._end_time,
            cursor_time=self._cursor_time,
            scroll_value=scroll_value,
            visible_nodes_info=visible_nodes_info,
            visible_nodes=self._visible_nodes.copy(),  # Pass full nodes for draw command generation
            waveform_db=waveform_db,
            generation=self._render_generation,
            row_heights=self._row_heights.copy(),  # Pass row heights for rendering
            base_row_height=self._row_height,
            header_height=self._header_height,  # Include header height for proper rendering
            waveform_max_time=self._waveform_max_time,  # Add waveform max time for renderer
            signal_range_cache=self._signal_range_cache  # Pass signal range cache for analog rendering
        )
    
    def _render_to_image(self, params: RenderParams, generation: int) -> Tuple[QImage, int, float]:
        """Render waveforms to an image (runs in thread pool)."""
        # Start timing
        render_start_time = time_module.time()
        
        # Timing for draw command generation
        draw_cmd_start = time_module.time()
        
        # Generate draw commands
        if params['waveform_db']:
            visible_signal_node = [node for node in params['visible_nodes'] if not node.is_group and node.handle is not None]
            draw_commands = self._generate_all_draw_commands(
                visible_signal_node,
                params['start_time'],
                params['end_time'],
                params['width'],
                params['waveform_db']
            )
            params['draw_commands'] = draw_commands.draw_commands
        else:
            params['draw_commands'] = {}
        
        draw_cmd_time = (time_module.time() - draw_cmd_start) * 1000
        
        
        # Timing for image creation and painting
        paint_start = time_module.time()
        
        # Create image at device-pixel resolution
        dpr = float(params.get('dpr', 1.0))
        w_px = max(1, int(math.ceil(params['width'] * dpr)))
        h_px = max(1, int(math.ceil(params['height'] * dpr)))
        image = QImage(w_px, h_px, QImage.Format.Format_ARGB32_Premultiplied)
        image.setDevicePixelRatio(dpr)
        # Use darker background color by default (for invalid ranges)
        image.fill(QColor(config.COLORS.BACKGROUND_INVALID))
        
        # Create painter; disable geometry antialiasing for crisp lines, keep text AA
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        
        try:
            # First paint the valid time range background
                if self._waveform_max_time is not None and params['width'] > 0:
                    # Calculate pixel positions for time boundaries
                    x_min = int((self._waveform_min_time - params['start_time']) * params['width'] / 
                               (params['end_time'] - params['start_time']))
                    x_max = int((self._waveform_max_time + 1 - params['start_time']) * params['width'] / 
                               (params['end_time'] - params['start_time']))
                    
                    # Clip to image bounds
                    x_min = max(0, x_min)
                    x_max = min(params['width'], x_max)
                    
                    # Paint the valid time range with lighter background
                    if x_max > x_min:
                        painter.fillRect(x_min, 0, x_max - x_min, params['height'], QColor(config.COLORS.BACKGROUND))
                
                # Render normal waveforms
                self._render_waveforms(painter, params)
        finally:
            painter.end()
        
        paint_time = (time_module.time() - paint_start) * 1000
        
        # Calculate render time
        render_time_ms = (time_module.time() - render_start_time) * 1000
        
        
        
        return image, generation, render_time_ms
    
    
    def _render_waveforms(self, painter: QPainter, params: RenderParams) -> None:
        """Render waveforms (thread-safe version)."""
        import time as time_module

        # Don't draw ruler here - it's drawn separately in paintEvent to ensure it's always on top
        
        # Check if we have draw commands
        draw_commands = params.get('draw_commands', {})
        if not draw_commands:
            # Show loading message
            painter.setPen(QColor(config.COLORS.TEXT_MUTED))
            painter.setFont(QFont("Arial", RENDERING.FONT_SIZE_LARGE))
            painter.drawText(params['width'] // 2 - 50, params['height'] // 2, "Loading waveforms...")
            return

        # Waveforms need to be offset by header height even in cached image
        y_offset = params.get('header_height', RENDERING.DEFAULT_HEADER_HEIGHT)  # Use header height from params

        painter.save()
        # Set clipping to prevent drawing outside the waveform area
        painter.setClipRect(0, y_offset, params['width'], params['height'] - y_offset)

        # Draw each visible row
        cumulative_y = y_offset
        row_heights = params.get('row_heights', {})
        base_row_height = params.get('base_row_height', 20)
        
        for row, node_info in enumerate(params['visible_nodes_info']):
            # Get the height for this row
            row_height = row_heights.get(row, base_row_height)
            
            # Calculate y position: cumulative position minus scroll offset
            y = cumulative_y - params['scroll_value']
            
            # The painter's clipping will handle not drawing rows outside the viewport.
            self._draw_row(painter, node_info, draw_commands, row, y, row_height, params)
            
            # Update cumulative y for next row
            cumulative_y += row_height

        painter.restore()
        
    
    
    def _draw_time_ruler_simple(self, painter: QPainter, params: RenderParams) -> None:
        """Simple version of time ruler drawing."""
        # Use default ruler config since we can't access model from thread
        ruler_config = TimeRulerConfig()
        
        # Draw ruler background
        painter.fillRect(0, 0, params['width'], RENDERING.DEFAULT_HEADER_HEIGHT, QColor(config.COLORS.HEADER_BACKGROUND))
        pen = QPen(QColor(config.COLORS.RULER_LINE))
        pen.setWidth(0)
        painter.setPen(pen)
        painter.drawLine(0, RENDERING.DEFAULT_HEADER_HEIGHT - 1, params['width'], RENDERING.DEFAULT_HEADER_HEIGHT - 1)
        
        # Simple time labels
        painter.setPen(QColor(config.COLORS.TEXT))
        painter.setFont(QFont(RENDERING.FONT_FAMILY, RENDERING.FONT_SIZE_NORMAL))
        
        # Draw some time markers
        num_ticks = 10
        for i in range(num_ticks + 1):
            x = i * params['width'] // num_ticks
            time = params['start_time'] + (params['end_time'] - params['start_time']) * i // num_ticks
            
            # Draw tick
            painter.drawLine(x, 30, x, 34)
            
            # Draw label
            label = f"{time}"
            painter.drawText(x - 20, 5, 40, 20, Qt.AlignmentFlag.AlignCenter, label)
    
    def _draw_row(self, painter: QPainter, node_info: NodeInfo, draw_commands: Dict[SignalHandle, SignalDrawingData], row: int, y: int, row_height: int, params: RenderParams) -> None:
        """Thread-safe version of row drawing."""
        # Draw background
        if row % 2 == 0:
            painter.fillRect(0, y, params['width'], row_height, QColor(config.COLORS.ALTERNATE_ROW))
        
        # Draw border
        border_pen = QPen(QColor(config.COLORS.BORDER))
        border_pen.setWidth(0)  # cosmetic 1 device-pixel
        painter.setPen(border_pen)
        painter.drawLine(0, y + row_height - 1, params['width'], y + row_height - 1)
        
        
        # Draw signal if it has drawing commands
        if node_info['handle'] is not None and node_info['handle'] in draw_commands:
            drawing_data = draw_commands[node_info['handle']]
            # Use render_type from node_info, not from drawing_data
            render_type = node_info.get('render_type') or node_info['format'].render_type
            if render_type == RenderType.BOOL:
                draw_digital_signal(painter, node_info, drawing_data, y, row_height, params)
            elif render_type == RenderType.BUS:
                draw_bus_signal(painter, node_info, drawing_data, y, row_height, params)
            elif render_type == RenderType.ANALOG:
                draw_analog_signal(painter, node_info, drawing_data, y, row_height, params)
            elif render_type == RenderType.EVENT:
                draw_event_signal(painter, node_info, drawing_data, y, row_height, params)
    
    def _draw_cursor(self, painter: QPainter, params: RenderParams) -> None:
        """Thread-safe version of cursor drawing."""
        if params['cursor_time'] >= params['start_time'] and params['cursor_time'] <= params['end_time']:
            x = int((params['cursor_time'] - params['start_time']) * params['width'] / 
                   (params['end_time'] - params['start_time']))
            
            painter.setPen(QPen(QColor(config.COLORS.CURSOR), RENDERING.CURSOR_WIDTH))
            painter.drawLine(x, 0, x, params['height'])


    def _calculate_and_store_ruler_info(self) -> None:
        """Calculate and store ruler information for grid drawing."""
        # Get configuration from session if available
        if self._model and self._model._session:
            ruler_config = self._model._session.time_ruler_config
        else:
            # Default configuration
            ruler_config = TimeRulerConfig()
        
        # Calculate tick positions and step size
        tick_positions, step_size = self._calculate_time_ruler_ticks(ruler_config)
        
        # Store tick positions for grid drawing
        self._last_tick_positions = tick_positions
        self._last_ruler_config = ruler_config
        
    def _draw_time_ruler(self, painter: QPainter) -> None:
        """Draw the time ruler according to spec 4.11."""

        # If model not loaded, don't draw ruler
        if not self._model:
            return

        # Use stored configuration if available
        if self._last_ruler_config is not None:
            ruler_config = self._last_ruler_config
            tick_positions = self._last_tick_positions
            _, step_size = self._calculate_time_ruler_ticks(ruler_config)
        else:
            # Fallback: calculate now
            self._calculate_and_store_ruler_info()
            if self._last_ruler_config is None:
                return  # Cannot proceed without config
            ruler_config = self._last_ruler_config
            tick_positions = self._last_tick_positions
            _, step_size = self._calculate_time_ruler_ticks(ruler_config)
        
        # Draw ruler background
        painter.fillRect(0, 0, self.width(), self._header_height, QColor(config.COLORS.HEADER_BACKGROUND))
        pen = QPen(QColor(config.COLORS.RULER_LINE))
        pen.setWidth(0)  # cosmetic 1 device-pixel
        painter.setPen(pen)
        painter.drawLine(0, self._header_height - 1, self.width(), self._header_height - 1)
        
        # Draw ticks and labels
        font = QFont(RENDERING.FONT_FAMILY_MONO, ruler_config.text_size)
        painter.setFont(font)
        
        # Get font metrics for accurate text measurement
        fm = QFontMetrics(font)
        
        for time_value, pixel_x in tick_positions:
            if 0 <= pixel_x <= self.width():
                # Draw tick mark with cosmetic pen
                tick_pen = QPen(QColor(config.COLORS.RULER_LINE))
                tick_pen.setWidth(0)
                painter.setPen(tick_pen)
                painter.drawLine(int(pixel_x), self._header_height - 6, int(pixel_x), self._header_height - 1)
                
                # Format and draw label
                # Use the session's timescale unit if available, otherwise fall back to config
                display_unit = ruler_config.time_unit
                if self._model and self._model._session and self._model._session.timescale:
                    display_unit = self._model._session.timescale.unit
                label = self._format_time_label(time_value, display_unit, step_size)
                
                # Get actual text dimensions
                text_rect = fm.boundingRect(label)
                text_width = text_rect.width()
                text_height = text_rect.height()
                
                # Calculate position to center text above tick
                text_x = int(pixel_x) - text_width // 2
                text_y = 5  # Increased margin from top for better spacing
                
                # Draw text using simpler drawText overload
                painter.setPen(QColor(config.COLORS.TEXT))
                painter.drawText(text_x, text_y + fm.ascent(), label)
    
    def _calculate_time_ruler_ticks(self, config: TimeRulerConfig) -> Tuple[List[Tuple[float, int]], float]:
        """Calculate optimal tick positions according to spec 4.11.2.
        
        Returns:
            Tuple of (tick_positions, step_size) where tick_positions is a list of (time, pixel_x) tuples
        """
        if self._end_time <= self._start_time or self.width() <= 0:
            return [], 0
        
        # Step 1: Estimate label width requirements
        viewport_left = self._start_time
        viewport_right = self._end_time
        
        # Create a sample label to estimate width
        # Use the larger of start/end time for estimation
        sample_time = max(abs(viewport_left), abs(viewport_right))
        # For estimation, use a reasonable step size guess
        estimated_step = (viewport_right - viewport_left) / 10
        # Use the session's timescale unit if available, otherwise fall back to config
        display_unit = config.time_unit
        if self._model and self._model._session and self._model._session.timescale:
            display_unit = self._model._session.timescale.unit
        sample_label = self._format_time_label(sample_time, display_unit, estimated_step)
        
        # Get font metrics for accurate width calculation
        font = QFont(RENDERING.FONT_FAMILY_MONO, config.text_size)
        fm = QFontMetrics(font)
        
        # Add some padding between labels
        label_width = fm.horizontalAdvance(sample_label) + RENDERING.DEBUG_TEXT_PADDING
        
        # Step 2: Calculate maximum number of labels that fit
        available_space = self.width() * config.tick_density
        max_labels = int(available_space / label_width) + 2
        
        # Step 3: Determine base scale
        viewport_duration = viewport_right - viewport_left
        if max_labels > 0:
            raw_step = viewport_duration / max_labels
        else:
            raw_step = viewport_duration
            
        if raw_step > 0:
            scale = 10 ** math.floor(math.log10(raw_step))
        else:
            scale = 1
        
        # Step 4: Find optimal step multiplier
        nice_multipliers = [1, 2, 2.5, 5, 10, 20, 25, 50]
        step_size = scale  # Default
        
        for multiplier in nice_multipliers:
            test_step = scale * multiplier
            
            # Calculate first tick position (aligned to step)
            first_tick = math.floor(viewport_left / test_step) * test_step
            
            # Count how many ticks would be generated
            num_ticks = math.ceil((viewport_right - first_tick) / test_step) + 1
            
            if num_ticks <= max_labels:
                step_size = test_step
                break
        
        # Step 5: Generate tick positions
        tick_positions = []
        first_tick = math.floor(viewport_left / step_size) * step_size
        
        tick_time = first_tick
        while tick_time <= viewport_right:
            # Keep full precision for time values
            pixel_x = self._time_to_x(tick_time)
            tick_positions.append((tick_time, pixel_x))
            
            
            tick_time += step_size
            
        return tick_positions, step_size
    
    def _draw_grid_lines(self, painter: QPainter, tick_positions: List[Tuple[float, int]], config: TimeRulerConfig) -> None:
        """Draw vertical grid lines at tick positions."""
        # Set up grid line style (cosmetic for crispness)
        pen = QPen(QColor(config.grid_color))
        pen.setWidth(0)  # cosmetic 1 device-pixel
        if config.grid_style == "dashed":
            pen.setStyle(Qt.PenStyle.DashLine)
        elif config.grid_style == "dotted":
            pen.setStyle(Qt.PenStyle.DotLine)
        painter.setPen(pen)
        
        # Draw vertical lines from below ruler to bottom
        for _, pixel_x in tick_positions:
            if 0 <= pixel_x <= self.width():
                painter.drawLine(int(pixel_x), RENDERING.DEFAULT_HEADER_HEIGHT, int(pixel_x), self.height())
    
    def _format_time_label(self, time: float, unit: TimeUnit, step_size: Optional[float] = None) -> str:
        """Format time value according to preferred unit.
        
        Args:
            time: Time value in Timescale units
            unit: The preferred time unit for display
            step_size: The step size between ticks (used to determine decimal places)
        """
        # Get the current timescale
        if self._model and self._model._session and self._model._session.timescale:
            timescale = self._model._session.timescale
        else:
            # Default to 1ps if not available
            from .data_model import Timescale, TimeUnit as TU
            timescale = Timescale(1, TU.PICOSECONDS)
        
        # Convert from timescale units to seconds first
        time_in_seconds = time * timescale.factor * (10 ** timescale.unit.to_exponent())
        
        # Convert seconds to the target unit
        conversions = {
            TimeUnit.ZEPTOSECONDS: (time_in_seconds * 1e21, "zs"),    # s to zs
            TimeUnit.ATTOSECONDS: (time_in_seconds * 1e18, "as"),     # s to as
            TimeUnit.FEMTOSECONDS: (time_in_seconds * 1e15, "fs"),    # s to fs
            TimeUnit.PICOSECONDS: (time_in_seconds * 1e12, "ps"),     # s to ps
            TimeUnit.NANOSECONDS: (time_in_seconds * 1e9, "ns"),      # s to ns
            TimeUnit.MICROSECONDS: (time_in_seconds * 1e6, "μs"),     # s to μs
            TimeUnit.MILLISECONDS: (time_in_seconds * 1e3, "ms"),     # s to ms
            TimeUnit.SECONDS: (time_in_seconds, "s")                  # s to s
        }
        
        value, suffix = conversions[unit]
        
        # Determine decimal places based on step size
        if step_size is not None:
            # Convert step size from timescale units to seconds
            step_in_seconds = step_size * timescale.factor * (10 ** timescale.unit.to_exponent())
            
            # Convert step size to the current display unit
            step_in_unit = step_in_seconds * (10 ** -unit.to_exponent())
            
            # Special handling for units with different factors
            if unit == TimeUnit.MICROSECONDS:
                step_in_unit = step_in_seconds * 1e6
            elif unit == TimeUnit.MILLISECONDS:
                step_in_unit = step_in_seconds * 1e3
            
            # Determine decimal places needed
            if step_in_unit >= 1:
                decimal_places = 0
            elif step_in_unit >= 0.1:
                decimal_places = 1
            elif step_in_unit >= 0.01:
                decimal_places = 2
            elif step_in_unit >= 0.001:
                decimal_places = 3
            else:
                decimal_places = 4  # Maximum precision
        else:
            # Default decimal places when step size is not provided
            decimal_places = 0
        
        # Format with appropriate decimal places
        if decimal_places == 0:
            formatted_value = f"{value:.0f}"
        else:
            formatted_value = f"{value:.{decimal_places}f}"
            # Remove trailing zeros after decimal point
            if '.' in formatted_value:
                formatted_value = formatted_value.rstrip('0').rstrip('.')
        
        # Handle unit upgrades for readability
        if unit == TimeUnit.PICOSECONDS and value >= 1000:
            return self._format_time_label(time, TimeUnit.NANOSECONDS, step_size)
        elif unit == TimeUnit.NANOSECONDS and value >= 1000:
            return self._format_time_label(time, TimeUnit.MICROSECONDS, step_size)
        elif unit == TimeUnit.MICROSECONDS and value >= 1000:
            return self._format_time_label(time, TimeUnit.MILLISECONDS, step_size)
        elif unit == TimeUnit.MILLISECONDS and value >= 1000:
            return self._format_time_label(time, TimeUnit.SECONDS, step_size)
        
        return f"{formatted_value} {suffix}"


    
    def _generate_all_draw_commands(self, signal_nodes: List[SignalNode], start_time: Time, end_time: Time, canvas_width: int, waveform_db: WaveformDBProtocol) -> CachedWaveDrawData:
        """Generate drawing commands for all signals (runs in thread pool)."""
        result = CachedWaveDrawData()
        result.viewport_hash = f"{start_time}_{end_time}_{canvas_width}"
        
        # Debug timing
        total_start = time_module.time()
        signal_times = []
        
        # Process each signal
        for node in signal_nodes:
            if node.handle is not None:
                sig_start = time_module.time()
                drawing_data = generate_signal_draw_commands(
                    node, start_time, end_time, canvas_width, waveform_db, 
                    self._waveform_max_time
                )
                sig_time = (time_module.time() - sig_start) * 1000
                signal_times.append((node.name, sig_time))
                
                if drawing_data:
                    result.draw_commands[node.handle] = drawing_data
        
        total_time = (time_module.time() - total_start) * 1000
        
        
        return result
    
    def _time_to_x(self, time: Time) -> int:
        """Convert time to x coordinate."""
        return int((time - self._start_time) * self._time_scale)
        
    def _x_to_time(self, x: int) -> Time:
        """Convert x coordinate to time."""
        return int(x / self._time_scale + self._start_time)
        
    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Handle mouse presses: left sets cursor, right starts ROI selection."""
        if event.button() == Qt.MouseButton.LeftButton:
            time = self._x_to_time(int(event.position().x()))
            self._cursor_time = max(self._start_time, min(time, self._end_time))
            self.cursorMoved.emit(self._cursor_time)
            self.update()
        elif event.button() == Qt.MouseButton.RightButton:
            x = int(event.position().x())
            self._start_roi_selection(x)
    
    def _paint_background_with_boundaries(self, painter: QPainter) -> None:
        """Paint background with different colors for valid/invalid time ranges."""
        # Default background color for entire canvas
        painter.fillRect(self.rect(), QColor(config.COLORS.BACKGROUND_DARK))  # Darker for invalid ranges
        
        # If we have valid waveform bounds, paint the valid range differently
        if self._waveform_max_time is not None and self.width() > 0:
            # Calculate pixel positions for time boundaries
            x_min = self._time_to_x(self._waveform_min_time)
            x_max = self._time_to_x(self._waveform_max_time + 1)  # +1 to include the last timestamp
            
            # Clip to widget bounds
            x_min = max(0, x_min)
            x_max = min(self.width(), x_max)
            
            # Paint the valid time range with a lighter background
            if x_max > x_min:
                painter.fillRect(x_min, 0, x_max - x_min, self.height(), QColor(config.COLORS.BACKGROUND))
    
    def _draw_boundary_lines(self, painter: QPainter) -> None:
        """Draw vertical lines at waveform time boundaries."""
        if self._waveform_max_time is None:
            return
        
        # Set up pen for boundary lines (cosmetic for HiDPI)
        pen = QPen(QColor(config.COLORS.BOUNDARY_LINE))
        pen.setWidth(0)  # 1 device pixel
        painter.setPen(pen)
        
        # Draw line at time 0 if visible
        if self._waveform_min_time >= self._start_time and self._waveform_min_time <= self._end_time:
            x_min = self._time_to_x(self._waveform_min_time)
            painter.drawLine(x_min, 0, x_min, self.height())
        
        # Draw line at max_time + 1 if visible
        boundary_time = self._waveform_max_time + 1
        if boundary_time >= self._start_time and boundary_time <= self._end_time:
            x_max = self._time_to_x(boundary_time)
            painter.drawLine(x_max, 0, x_max, self.height())
    
    def _draw_debug_counters(self, painter: QPainter) -> None:
        """Draw debug counters in bottom right corner."""
        # Save painter state
        painter.save()
        
        # Set up font and colors
        font = QFont(RENDERING.DEBUG_FONT_FAMILY, RENDERING.DEBUG_FONT_SIZE)
        font.setBold(True)
        painter.setFont(font)
        
        # Format times to 1 decimal place
        paint_time_ms = self._last_paint_time_ms
        render_time_ms = self._last_render_time_ms
        
        # Create text in requested format
        debug_text = f"PaintEvent # {self._paint_frame_counter} ({paint_time_ms:.1f} ms), RenderedFrame # {self._render_complete_counter} ({render_time_ms:.1f} ms)"
        # Calculate text position
        metrics = QFontMetrics(font)
        text_rect = metrics.boundingRect(debug_text)
        x = self.width() - text_rect.width() - RENDERING.DEBUG_TEXT_MARGIN
        y = self.height() - RENDERING.DEBUG_TEXT_MARGIN
        
        # Draw background
        padding = RENDERING.DEBUG_TEXT_PADDING // 2
        bg_rect = QRectF(x - padding, y - text_rect.height() - padding, 
                        text_rect.width() + 2 * padding, text_rect.height() + 2 * padding)
        painter.fillRect(bg_rect, QColor(*config.COLORS.DEBUG_BACKGROUND))
        
        # Draw text
        painter.setPen(QColor(config.COLORS.DEBUG_TEXT))
        painter.drawText(x, y, debug_text)
        
        # Restore painter state
        painter.restore()
    
    # ---- ROI selection helpers ----
    def _start_roi_selection(self, x: int) -> None:
        self._roi_selection_active = True
        self._roi_start_x = max(0, min(x, self.width()))
        self._roi_current_x = self._roi_start_x
        # Force overlay-only update
        self.update()
    
    def _update_roi_selection(self, x: int) -> None:
        if not self._roi_selection_active:
            return
        self._roi_current_x = max(0, min(int(x), self.width()))
        # Trigger overlay repaint for smooth feedback
        self.update()
    
    def _finish_roi_selection(self) -> None:
        if not self._roi_selection_active or self._roi_start_x is None or self._roi_current_x is None:
            self._clear_roi_selection()
            return
        x0 = self._roi_start_x
        x1 = self._roi_current_x
        if x0 == x1:
            # No selection; clear and return
            self._clear_roi_selection()
            return
        left_x = min(x0, x1)
        right_x = max(x0, x1)
        start_time = self._x_to_time(left_x)
        end_time = self._x_to_time(right_x)
        # Emit signal; controller will enforce min width and clamp
        self.roiSelected.emit(start_time, end_time)
        self._clear_roi_selection()
    
    def _clear_roi_selection(self) -> None:
        self._roi_selection_active = False
        self._roi_start_x = None
        self._roi_current_x = None
        self.update()
    
    def _paint_roi_overlay(self, painter: QPainter) -> None:
        if not self._roi_selection_active or self._roi_start_x is None or self._roi_current_x is None:
            return
        x0 = self._roi_start_x
        x1 = self._roi_current_x
        left_x = min(x0, x1)
        right_x = max(x0, x1)
        # Draw semi-transparent fill
        color = QColor(config.COLORS.ROI_SELECTION_COLOR)
        # Apply opacity
        alpha = int(max(0.0, min(1.0, config.COLORS.ROI_SELECTION_OPACITY)) * 255)
        fill_color = QColor(color.red(), color.green(), color.blue(), alpha)
        painter.fillRect(left_x, 0, right_x - left_x, self.height(), fill_color)
        # Draw guide lines
        pen = QPen(QColor(config.COLORS.ROI_GUIDE_LINE_COLOR))
        pen.setWidth(RENDERING.ROI_GUIDE_LINE_WIDTH)
        pen.setCosmetic(True)
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.drawLine(left_x, 0, left_x, self.height())
        painter.drawLine(right_x, 0, right_x, self.height())
    
    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._roi_selection_active:
            self._update_roi_selection(int(event.position().x()))
        else:
            super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.RightButton and self._roi_selection_active:
            self._finish_roi_selection()
            event.accept()
        else:
            super().mouseReleaseEvent(event)
    
    def keyPressEvent(self, event: QKeyEvent) -> None:
        # Escape cancels ROI selection if active
        if event.key() == Qt.Key.Key_Escape and self._roi_selection_active:
            self._clear_roi_selection()
            event.accept()
            return
        super().keyPressEvent(event)
    
    def closeEvent(self, event: QCloseEvent) -> None:
        """Clean up resources when closing."""
        super().closeEvent(event)