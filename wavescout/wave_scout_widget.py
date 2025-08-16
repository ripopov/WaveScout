"""Main WaveScout widget with three synchronized panels."""

from PySide6.QtWidgets import (QWidget, QVBoxLayout,
                               QScrollBar, QSplitter,
                               QLabel, QFrame, QApplication)
from PySide6.QtCore import Qt, Signal, QModelIndex, QItemSelectionModel, QItemSelection, QEvent, QTimer, QObject
from PySide6.QtGui import QKeyEvent, QWheelEvent
from typing import Optional, cast, List
from .waveform_item_model import WaveformItemModel
from .waveform_canvas import WaveformCanvas
from .data_model import WaveformSession, SignalNode, GroupRenderMode
from .waveform_controller import WaveformController
from .signal_names_view import SignalNamesView, BaseColumnView
from .config import RENDERING, UI




class SignalValuesView(BaseColumnView):
    """Tree view for signal values at cursor (column 1)."""
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(visible_column=1, allow_expansion=False, parent=parent)


class WaveScoutWidget(QWidget):
    """Main WaveScout widget with three synchronized panels."""
    
    cursorChanged = Signal(object)  # Using object to handle large time values
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        # Initialize ALL attributes upfront
        self.session: Optional[WaveformSession] = None
        self.model: Optional[WaveformItemModel] = None
        self.controller: WaveformController = WaveformController()
        self._shared_scrollbar: Optional[QScrollBar] = None
        self._selection_model: Optional[QItemSelectionModel] = None
        self._updating_selection: bool = False
        self._initialized: bool = False
        
        # Initialize UI components - will be set in _setup_ui
        # Using cast to satisfy mypy while allowing initialization check
        self._info_bar: QLabel = cast(QLabel, None)
        self._splitter: QSplitter = cast(QSplitter, None)
        self._names_view: SignalNamesView = cast(SignalNamesView, None)
        self._values_view: SignalValuesView = cast(SignalValuesView, None)
        self._canvas: WaveformCanvas = cast(WaveformCanvas, None)
        
        # Now setup UI (which will assign real objects)
        self._setup_ui()
        self._initialized = True
        
        # Bind controller events to view updates
        self.controller.on("viewport_changed", self._update_canvas_time_range)
        self.controller.on("cursor_changed", self._on_controller_cursor_changed)
        self.controller.on("markers_changed", self._on_controller_markers_changed)
        
    def _setup_ui(self) -> None:
        """Set up the user interface."""
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Enable keyboard focus
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        
        # Top info bar
        self._info_bar = QLabel("Cursor: 0 ps")
        self._info_bar.setFrameStyle(QFrame.Shape.Box)
        self._info_bar.setMaximumHeight(UI.INFO_BAR_HEIGHT)
        layout.addWidget(self._info_bar)
        
        # Create splitter for the three panels
        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Create the three views
        self._names_view = SignalNamesView(controller=self.controller)
        self._values_view = SignalValuesView()
        self._canvas = WaveformCanvas(None)
        
        # Install event filter on child views to handle keyboard shortcuts
        self._names_view.installEventFilter(self)
        self._values_view.installEventFilter(self)
        self._canvas.installEventFilter(self)
        
        # Add views to splitter
        self._splitter.addWidget(self._names_view)
        self._splitter.addWidget(self._values_view)
        self._splitter.addWidget(self._canvas)
        
        # Set initial splitter sizes
        if UI.SPLITTER_INITIAL_SIZES is not None:
            self._splitter.setSizes(UI.SPLITTER_INITIAL_SIZES)
        
        layout.addWidget(self._splitter)
        
        # Create shared scrollbar
        self._setup_shared_scrollbar()
        
        # Connect signals
        self._canvas.cursorMoved.connect(self._on_cursor_moved)
        # ROI zoom wiring: when canvas emits selection, delegate zoom to controller
        self._canvas.roiSelected.connect(lambda s, e: self.controller.zoom_to_roi(s, e))
        
        # Sync header heights across panels
        self._sync_header_heights()
        
    def _setup_shared_scrollbar(self) -> None:
        """Set up the shared vertical scrollbar for row locking."""
        # Create a single scrollbar
        self._shared_scrollbar = QScrollBar(Qt.Orientation.Vertical)
        
        # Assign it to all views
        self._names_view.setVerticalScrollBar(self._shared_scrollbar)
        self._values_view.setVerticalScrollBar(self._shared_scrollbar)
        
        # Canvas will use the scrollbar for painting
        self._canvas.setSharedScrollBar(self._shared_scrollbar)
        self._shared_scrollbar.valueChanged.connect(self._canvas.update)
        
    def setSession(self, session: WaveformSession) -> None:
        """Set the waveform session and create the model."""
        self._cleanup_previous_session()
        self._initialize_new_session(session)
        # Inform controller last so it can emit events after canvas is ready
        self.controller.set_session(session)
        self._setup_model_connections()
        self._restore_ui_state()
    
    def _cleanup_previous_session(self) -> None:
        """Clean up the previous session resources."""
        # If not fully initialized, there's nothing to clean up
        if not self._initialized:
            return
        
        # Disconnect signals from old model
        if self.model is not None:
            try:
                self.model.layoutChanged.disconnect(self._update_scrollbar_range)
                self.model.rowsInserted.disconnect(self._update_scrollbar_range)
                self.model.rowsRemoved.disconnect(self._update_scrollbar_range)
            except:
                pass  # Signals might not be connected
        
        # Disconnect selection model signals
        if self._selection_model is not None:
            try:
                self._selection_model.selectionChanged.disconnect(self._on_selection_changed)
            except:
                pass
        
        # Disconnect view signals
        if self._names_view is not None and self._names_view.model():
            try:
                self._names_view.expanded.disconnect(self._sync_expansion)
                self._names_view.collapsed.disconnect(self._sync_expansion)
            except:
                pass
        
        # Clear models from all views
        self._names_view.setModel(None)
        self._values_view.setModel(None)
        self._canvas.setModel(None)
        
        # Delete old objects
        if self._selection_model is not None:
            self._selection_model.deleteLater()
            self._selection_model = None
        if self.model is not None:
            # Call cleanup explicitly before deletion
            if hasattr(self.model, '_cleanup'):
                self.model._cleanup()
            self.model.deleteLater()
            self.model = None
    
    def _initialize_new_session(self, session: WaveformSession) -> None:
        """Initialize the new session and create models."""
        # Set new session
        self.session = session
        self.model = WaveformItemModel(session, controller=self.controller, parent=self)
        
        # Create shared selection model
        self._selection_model = QItemSelectionModel(self.model)
        
        # Set model and selection model on all views
        self._names_view.setModel(self.model)
        self._names_view.setSelectionModel(self._selection_model)
        self._values_view.setModel(self.model)
        self._values_view.setSelectionModel(self._selection_model)
        self._canvas.setModel(self.model)
        
        # Set canvas time range from viewport
        self._canvas.setTimeRange(session.viewport.start_time, session.viewport.end_time)
        self._canvas.setCursorTime(session.cursor_time)
    
    def set_value_tooltips_enabled(self, enabled: bool) -> None:
        """Enable or disable value tooltips at cursor."""
        self._canvas.set_value_tooltips_enabled(enabled)
    
    def _setup_model_connections(self) -> None:
        """Set up all signal-slot connections for the model."""
        if not self.model:
            return
            
        # Connect model signals
        self.model.layoutChanged.connect(self._update_scrollbar_range)
        self.model.rowsInserted.connect(self._update_scrollbar_range)
        self.model.rowsRemoved.connect(self._update_scrollbar_range)
        self.model.modelReset.connect(self._on_model_reset)
        
        # Connect view expansion signals
        self._names_view.expanded.connect(self._sync_expansion)
        self._names_view.collapsed.connect(self._sync_expansion)
        
        # Connect selection changed signal
        if self._selection_model:
            self._selection_model.selectionChanged.connect(self._on_selection_changed)
    
    def _sync_header_heights(self) -> None:
        """Ensure all panel headers have the same height using system theme value."""
        try:
            height = RENDERING.DEFAULT_HEADER_HEIGHT
            for view in [self._names_view, self._values_view]:
                if view and view.header():
                    view.header().setFixedHeight(height)
        except Exception:
            # Fail-safe: ignore if headers are not yet available
            pass
    
    def _restore_ui_state(self) -> None:
        """Restore UI state including scrollbar and expansion states."""
        # Force the tree view to calculate sizes by processing events
        QApplication.processEvents()

        # Make sure headers are in sync before computing ranges
        self._sync_header_heights()
        
        # Update scrollbar range (this also sets header height)
        self._update_scrollbar_range()
        
        # Expand all groups initially based on their is_expanded state
        self._restore_expansion_state()
        
    def _update_scrollbar_range(self) -> None:
        """Update the shared scrollbar range based on total rows."""
        if not self.model or not self._names_view.model():
            return

        total_rows = self._calculate_total_rows()
        row_height = self._names_view.sizeHintForRow(0)
        if row_height <= 0:
            row_height = RENDERING.DEFAULT_ROW_HEIGHT  # Fallback

        # Total height of all items
        total_content_height = total_rows * row_height

        # Get the viewport height (the visible area for items)
        viewport_height = self._names_view.viewport().height()

        # Set scrollbar range
        # The maximum is the total content height minus the viewport height
        if self._shared_scrollbar is not None:
            self._shared_scrollbar.setRange(0, max(0, total_content_height - viewport_height))
            self._shared_scrollbar.setPageStep(viewport_height)
            self._shared_scrollbar.setSingleStep(row_height)

        # Ensure consistent header heights across panels
        self._sync_header_heights()

        # Synchronize header and row heights with the canvas
        header_height = self._names_view.header().height()
        self._canvas.setHeaderHeight(header_height)
        # Important: pass the base (unscaled) row height to the canvas.
        # The canvas will apply per-node height_scaling itself. Using a scaled
        # row height from the tree view would cause double scaling and misalignment.
        self._canvas.setRowHeight(RENDERING.DEFAULT_ROW_HEIGHT)
        

    def _calculate_total_rows(self, parent: QModelIndex = QModelIndex()) -> int:
        """Calculate total number of visible rows in the tree."""
        if not self.model:
            return 0
            
        count = 0
        rows = self.model.rowCount(parent)
        
        for row in range(rows):
            count += 1
            index = self.model.index(row, 0, parent)
            if self._names_view.isExpanded(index):
                count += self._calculate_total_rows(index)
                
        return count
        
    def _sync_expansion(self, index: QModelIndex) -> None:
        """Synchronize expansion state across all tree views."""
        is_expanded = self._names_view.isExpanded(index)
        
        # Update the data model
        if self.model is not None:
            node = self.model.data(index, Qt.ItemDataRole.UserRole)
            if isinstance(node, SignalNode) and node.is_group:
                self.controller.set_node_expanded(node.instance_id, is_expanded)
        
        # Sync to other views
        if is_expanded:
            self._values_view.expand(index)
        else:
            self._values_view.collapse(index)
            
        # Update scrollbar
        self._update_scrollbar_range()
        
        # Notify model that layout has changed to update canvas
        if self.model:
            self.model.layoutChanged.emit()
    
    def _iter_all_nodes(self) -> List[SignalNode]:
        """Iterate through all nodes in the session."""
        if not self.session:
            return []
        
        nodes = []
        def walk(node: SignalNode) -> None:
            nodes.append(node)
            for child in node.children:
                walk(child)
        
        for root in self.session.root_nodes:
            walk(root)
        
        return nodes
        
    def _restore_expansion_state(self, parent_index: QModelIndex = QModelIndex()) -> None:
        """Restore expansion state from data model."""
        if not self.model:
            return
            
        row_count = self.model.rowCount(parent_index)
        
        for row in range(row_count):
            index = self.model.index(row, 0, parent_index)
            node = self.model.data(index, Qt.ItemDataRole.UserRole)
            
            if isinstance(node, SignalNode) and node.is_group:
                if node.is_expanded:
                    self._names_view.expand(index)
                    self._values_view.expand(index)
                else:
                    self._names_view.collapse(index)
                    self._values_view.collapse(index)
                
                # Recurse into children
                self._restore_expansion_state(index)
    
    def _on_model_reset(self) -> None:
        """Handle model reset by restoring expansion state."""
        # Schedule restoration for next event loop iteration to ensure views are updated
        QTimer.singleShot(0, self._restore_expansion_state)
        self._update_scrollbar_range()
                
    def _on_cursor_moved(self, time: int) -> None:
        """Handle cursor movement from canvas."""
        if self.session and self.model:
            self.session.cursor_time = time
            row_count = self.model.rowCount()
            if row_count > 0:
                self.model.dataChanged.emit(
                    self.model.index(0, 1),
                    self.model.index(row_count - 1, 1)
                )
            
            # Format cursor time using appropriate unit
            if self.session.time_ruler_config:
                formatted_time = self._canvas._format_time_label(time, self.session.time_ruler_config.time_unit, None)
                self._info_bar.setText(f"Cursor: {formatted_time}")
            else:
                # Display with timescale unit suffix
                if self.session.timescale:
                    unit_suffix = self.session.timescale.unit.value
                    self._info_bar.setText(f"Cursor: {time} {unit_suffix}")
                else:
                    self._info_bar.setText(f"Cursor: {time}")
            
            self.cursorChanged.emit(time)
            
    def _on_controller_cursor_changed(self) -> None:
        """Controller signaled cursor change: refresh info bar and canvas."""
        if not self.session:
            return
        # Reuse existing on-canvas cursor formatting by calling canvas setter
        self._canvas.setCursorTime(self.session.cursor_time)
        # Update info bar text similar to _on_cursor_moved
        time = self.session.cursor_time
        if self.session.time_ruler_config:
            formatted_time = self._canvas._format_time_label(time, self.session.time_ruler_config.time_unit, None)
            self._info_bar.setText(f"Cursor: {formatted_time}")
        else:
            if self.session.timescale:
                unit_suffix = self.session.timescale.unit.value
                self._info_bar.setText(f"Cursor: {time} {unit_suffix}")
            else:
                self._info_bar.setText(f"Cursor: {time}")
        self.cursorChanged.emit(time)

    def _on_controller_markers_changed(self) -> None:
        """Handle markers change from controller."""
        if self._canvas:
            self._canvas.update()
            
    def _on_selection_changed(self, selected: QItemSelection, deselected: QItemSelection) -> None:
        """Handle selection changes and update the data model."""
        if self._updating_selection or not self.session or not self._selection_model or not self.model:
            return
            
        # Get selected nodes from the selection model
        selected_nodes: List[SignalNode] = []
        selected_indexes = self._selection_model.selectedIndexes()
        
        # Filter to only column 0 (to avoid duplicates) and extract nodes
        processed_node_ids = set()
        for index in selected_indexes:
            if index.column() == 0:
                node = self.model.data(index, Qt.ItemDataRole.UserRole)
                if isinstance(node, SignalNode):
                    node_id = node.instance_id
                    if node_id not in processed_node_ids:
                        selected_nodes.append(node)
                        processed_node_ids.add(node_id)
        
        # Use controller to update selection (it will update session)
        self.controller.set_selection_by_ids([n.instance_id for n in selected_nodes])
        
        # Update canvas to highlight selected signals
        self._canvas.update()
        
    def _select_all(self) -> None:
        """Select all items in the model."""
        if not self._selection_model or not self.model:
            return
            
        # Create selection for all items
        selection = QItemSelection()
        
        def add_to_selection(parent_index: QModelIndex = QModelIndex()) -> None:
            """Recursively add all items to selection."""
            assert self.model is not None  # For mypy
            rows = self.model.rowCount(parent_index)
            for row in range(rows):
                index = self.model.index(row, 0, parent_index)
                # Add this index to selection
                selection.select(index, index)
                # Recurse into children
                if self.model.hasChildren(index):
                    add_to_selection(index)
        
        # Add all items
        add_to_selection()
        
        # Apply selection
        self._updating_selection = True
        self._selection_model.select(selection, QItemSelectionModel.SelectionFlag.ClearAndSelect)
        self._updating_selection = False
        
        # Manually trigger selection changed to update data model
        self._on_selection_changed(selection, QItemSelection())
        
    def update_all_views(self) -> None:
        """Update all child views. Public method for external callers."""
        self.update()
        if self._initialized:
            self._canvas.update()
            # Update the viewports of tree views
            self._names_view.viewport().update()
            self._values_view.viewport().update()
    
    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Filter events from child widgets to handle keyboard shortcuts."""
        if event.type() == QEvent.Type.KeyPress:
            # Check if this is one of our shortcut keys
            key_event = cast(QKeyEvent, event)
            key = key_event.key()
            modifiers = key_event.modifiers()
            
            # Zoom and navigation keys should be handled by parent
            if (key in [Qt.Key.Key_Plus, Qt.Key.Key_Equal, Qt.Key.Key_Minus] or
                (key == Qt.Key.Key_F and modifiers == Qt.KeyboardModifier.NoModifier) or
                (key == Qt.Key.Key_S and modifiers == Qt.KeyboardModifier.NoModifier) or
                (key == Qt.Key.Key_E and modifiers == Qt.KeyboardModifier.NoModifier) or
                (key == Qt.Key.Key_G and modifiers == Qt.KeyboardModifier.NoModifier) or
                (key == Qt.Key.Key_V and modifiers == Qt.KeyboardModifier.NoModifier) or
                key in [Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_PageUp, Qt.Key.Key_PageDown]):
                # Send the event to our keyPressEvent
                self.keyPressEvent(key_event)
                return True
        elif event.type() == QEvent.Type.KeyRelease:
            # Handle V key release for tooltips
            key_event = cast(QKeyEvent, event)
            if key_event.key() == Qt.Key.Key_V and key_event.modifiers() == Qt.KeyboardModifier.NoModifier:
                self.keyReleaseEvent(key_event)
                return True
        
        return super().eventFilter(watched, event)
    
    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Handle key press events."""
        # Handle delete key
        if event.key() == Qt.Key.Key_Delete:
            self._delete_selected_nodes()
            event.accept()
        # Handle Ctrl+A for select all
        elif event.key() == Qt.Key.Key_A and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            self._select_all()
            event.accept()
        # Handle zoom shortcuts
        elif event.key() == Qt.Key.Key_Plus or event.key() == Qt.Key.Key_Equal:
            self._zoom_in()
            event.accept()
        elif event.key() == Qt.Key.Key_Minus:
            self._zoom_out()
            event.accept()
        elif event.key() == Qt.Key.Key_F and event.modifiers() == Qt.KeyboardModifier.NoModifier:
            self._zoom_to_fit()
            event.accept()
        # Handle navigation shortcuts
        elif event.key() == Qt.Key.Key_S and event.modifiers() == Qt.KeyboardModifier.NoModifier:
            self._go_to_start()
            event.accept()
        elif event.key() == Qt.Key.Key_E and event.modifiers() == Qt.KeyboardModifier.NoModifier:
            self._go_to_end()
            event.accept()
        elif event.key() == Qt.Key.Key_G and event.modifiers() == Qt.KeyboardModifier.NoModifier:
            self._create_group_from_selected()
            event.accept()
        # Handle arrow keys for panning
        elif event.key() == Qt.Key.Key_Left:
            self._pan_left()
            event.accept()
        elif event.key() == Qt.Key.Key_Right:
            self._pan_right()
            event.accept()
        elif event.key() == Qt.Key.Key_PageUp:
            self._pan_left()
            event.accept()
        elif event.key() == Qt.Key.Key_PageDown:
            self._pan_right()
            event.accept()
        # Handle marker shortcuts (Ctrl+1 through Ctrl+9)
        elif (event.modifiers() == Qt.KeyboardModifier.ControlModifier and 
              event.key() >= Qt.Key.Key_1 and event.key() <= Qt.Key.Key_9):
            marker_index = event.key() - Qt.Key.Key_1  # Convert to 0-based index
            self.controller.toggle_marker_at_cursor(marker_index)
            event.accept()
        # Handle marker navigation (1 through 9 without modifiers)
        elif (event.modifiers() == Qt.KeyboardModifier.NoModifier and 
              event.key() >= Qt.Key.Key_1 and event.key() <= Qt.Key.Key_9):
            marker_index = event.key() - Qt.Key.Key_1  # Convert to 0-based index
            # Get actual canvas width for accurate pixel offset calculation
            canvas_width = self._canvas.width() if self._canvas else RENDERING.DEFAULT_CANVAS_WIDTH
            # Navigate with default pixel offset from left edge
            self.controller.navigate_to_marker(marker_index, None, canvas_width)
            event.accept()
        # Handle V key for value tooltips (forward to canvas)
        elif event.key() == Qt.Key.Key_V and event.modifiers() == Qt.KeyboardModifier.NoModifier:
            # Forward the key press to canvas for tooltip handling
            self._canvas.keyPressEvent(event)
            # Don't accept the event so key release also gets forwarded
        else:
            super().keyPressEvent(event)
    
    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        """Handle key release events."""
        # Handle V key release for value tooltips
        if event.key() == Qt.Key.Key_V and event.modifiers() == Qt.KeyboardModifier.NoModifier:
            # Forward the key release to canvas for tooltip handling
            self._canvas.keyReleaseEvent(event)
            # Don't accept the event so it propagates normally
        else:
            super().keyReleaseEvent(event)
            
    def _delete_selected_nodes(self) -> None:
        """Delete all selected nodes from the data model."""
        if not self.session or not self.session.selected_nodes:
            return
            
        # Get selected node IDs
        node_ids = [node.instance_id for node in self.session.selected_nodes]
        
        # Clear selection in UI first to avoid accessing deleted nodes
        if self._selection_model:
            self._updating_selection = True  # Prevent selection change handler
            self._selection_model.clearSelection()
            self._updating_selection = False
        
        # Use controller to delete nodes
        self.controller.delete_nodes_by_ids(node_ids)
        # Restore expansion state after deletion
        self._restore_expansion_state()
                
    def _create_group_from_selected(self) -> None:
        """Create a new group containing the selected nodes."""
        if not self.session or not self.session.selected_nodes:
            return
        
        from PySide6.QtWidgets import QInputDialog
            
        # Use controller to create group
        # Get selected node IDs
        selected_ids = [node.instance_id for node in self.session.selected_nodes]
        
        # Filter out nodes whose parent is also selected
        # This prevents flattening when grouping groups
        nodes_to_group_ids = []
        selected_nodes = list(self.session.selected_nodes)
        
        for node in selected_nodes:
            # Check if any ancestor is in the selected list
            has_selected_ancestor = False
            current = node.parent
            while current:
                if current in selected_nodes:
                    has_selected_ancestor = True
                    break
                current = current.parent
            
            # Only include nodes that don't have a selected ancestor
            if not has_selected_ancestor:
                nodes_to_group_ids.append(node.instance_id)
        
        if nodes_to_group_ids:
            # Get group name from user
            group_name, ok = QInputDialog.getText(
                self,
                "Create Group",
                "Enter name for the new group:",
                text=""
            )
            
            # If user cancelled, don't create the group
            if not ok:
                return
            
            # If user provided no name, use default
            if not group_name:
                group_name = f"Group {len([n for n in self.session.root_nodes if n.is_group]) + 1}"
            
            # Clear selection in UI
            if self._selection_model:
                self._updating_selection = True
                self._selection_model.clearSelection()
                self._updating_selection = False
            
            # Create the group using controller
            group_id = self.controller.group_nodes(
                nodes_to_group_ids,
                group_name,
                GroupRenderMode.SEPARATE_ROWS
            )
            
            # Restore expansion state after grouping
            self._restore_expansion_state()
            
            # Select the new group
            if group_id != -1 and self.model:
                # Find the group node and select it
                for node in self._iter_all_nodes():
                    if node.instance_id == group_id:
                        # Find index for the node in the model
                        parent_index = QModelIndex()
                        model_index = None
                        for i in range(self.model.rowCount(parent_index)):
                            temp_idx = self.model.index(i, 0, parent_index)
                            if self.model.data(temp_idx, Qt.ItemDataRole.UserRole) == node:
                                model_index = temp_idx
                                break
                        
                        if model_index and model_index.isValid() and self._selection_model:
                            self._selection_model.select(
                                model_index,
                                QItemSelectionModel.SelectionFlag.ClearAndSelect | 
                                QItemSelectionModel.SelectionFlag.Rows
                            )
                        break
        return
                
    def _zoom_in(self) -> None:
        """Zoom in by 2x (delta = 0.5)."""
        if self.session and self.session.viewport:
            self._zoom_viewport(0.5)
            
    def _zoom_out(self) -> None:
        """Zoom out by 2x (delta = 2.0)."""
        if self.session and self.session.viewport:
            self._zoom_viewport(2.0)
            
    def _zoom_to_fit(self) -> None:
        """Fit entire waveform in view (delegated to controller)."""
        self.controller.zoom_to_fit()
    
    def _zoom_viewport(self, zoom_factor: float, mouse_x: Optional[int] = None) -> None:
        """Apply zoom to viewport around mouse position or center.
        
        Args:
            zoom_factor: < 1.0 zooms in, > 1.0 zooms out
            mouse_x: Mouse x position in canvas coordinates (None for center zoom)
        """
        if not self.session or not self.session.viewport:
            return
        viewport = self.session.viewport
        # Compute mouse-relative position if provided
        if mouse_x is not None and self._canvas:
            canvas_width = self._canvas.width()
            if canvas_width > 0:
                mouse_relative = viewport.left + (mouse_x / canvas_width) * viewport.width
            else:
                mouse_relative = (viewport.left + viewport.right) / 2
        else:
            mouse_relative = (viewport.left + viewport.right) / 2
        # Delegate zoom to controller; controller will emit viewport_changed
        self.controller.zoom_viewport(zoom_factor, mouse_relative)
        
    def _pan_left(self) -> None:
        """Pan left by 10% of viewport width."""
        if self.session and self.session.viewport:
            viewport = self.session.viewport
            pan_distance = viewport.width * UI.PAN_PERCENTAGE
            self._pan_viewport(-pan_distance)
            
    def _pan_right(self) -> None:
        """Pan right by 10% of viewport width."""
        if self.session and self.session.viewport:
            viewport = self.session.viewport
            pan_distance = viewport.width * UI.PAN_PERCENTAGE
            self._pan_viewport(pan_distance)
            
    def _pan_viewport(self, pan_distance: float) -> None:
        """Pan viewport by given distance in relative coordinates.
        
        Args:
            pan_distance: Distance to pan (positive = right, negative = left)
        """
        if not self.session or not self.session.viewport:
            return
            
        # Delegate pan to controller; it will handle constraints and emit viewport_changed
        self.controller.pan_viewport(pan_distance)
        
    def _go_to_start(self) -> None:
        """Go to start of waveform (delegated to controller)."""
        if self.session and self.session.viewport:
            self.controller.go_to_start()
            
    def _go_to_end(self) -> None:
        """Go to end of waveform (delegated to controller)."""
        if self.session and self.session.viewport:
            self.controller.go_to_end()
            
    def _update_canvas_time_range(self) -> None:
        """Update canvas with current viewport time range."""
        if self.session and self._canvas:
            viewport = self.session.viewport
            self._canvas.setTimeRange(viewport.start_time, viewport.end_time)
            self._canvas.update()
            
    def _get_minimum_zoom_width(self) -> float:
        """Calculate the minimum allowed zoom width based on constraints.
        
        Returns:
            Minimum viewport width as a fraction of total duration
        """
        if not self.session or not self.session.viewport:
            return 0.0001  # Default to 0.01%
            
        viewport = self.session.viewport
        
        # Start with the configured minimum
        min_width = viewport.config.minimum_width_time / viewport.total_duration
        
        # Apply timescale-based limit if available
        if self.session.timescale and viewport.total_duration > 0:
            # Maximum zoom is when 1 timescale unit takes up half the viewport
            timescale_min_width = (1.0 / viewport.total_duration) * 2
            # Use the larger of the two constraints
            min_width = max(min_width, timescale_min_width)
            
        return min_width
            
    def wheelEvent(self, event: QWheelEvent) -> None:
        """Handle mouse wheel events for zoom and pan."""
        if not self.session or not self.session.viewport:
            return super().wheelEvent(event)
            
        # Get wheel delta
        delta = event.angleDelta().y()
        if delta == 0:
            return super().wheelEvent(event)
            
        # Check modifiers
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            # Ctrl+Wheel = Zoom
            zoom_factor = UI.ZOOM_WHEEL_FACTOR
            if delta > 0:
                # Wheel up = zoom in
                zoom_factor = 1.0 / zoom_factor
            
            # Get mouse position relative to canvas
            canvas_pos = self._canvas.mapFromGlobal(event.globalPosition().toPoint())
            if self._canvas.rect().contains(canvas_pos):
                self._zoom_viewport(zoom_factor, canvas_pos.x())
            else:
                self._zoom_viewport(zoom_factor)
        else:
            # No modifier = Pan
            # Calculate pan distance based on viewport width and scroll sensitivity
            viewport = self.session.viewport
            pan_distance = viewport.width * UI.SCROLL_SENSITIVITY
            
            if delta > 0:
                # Wheel up = pan left
                self._pan_viewport(-pan_distance)
            else:
                # Wheel down = pan right
                self._pan_viewport(pan_distance)
                
        event.accept()