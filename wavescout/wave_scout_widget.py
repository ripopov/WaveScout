"""Main WaveScout widget with four synchronized panels."""

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QTreeView, 
                              QScrollBar, QSplitter,
                              QLabel, QFrame, QAbstractItemView, QMenu,
                              QStyledItemDelegate, QStyleOptionViewItem, QApplication)
from PySide6.QtCore import Qt, Signal, QModelIndex, QItemSelectionModel, QItemSelection, QEvent, QTimer, QSize
from PySide6.QtGui import QColor, QAction, QActionGroup
from typing import Optional, Any
from .waveform_item_model import WaveformItemModel
from .waveform_canvas import WaveformCanvas
from .data_model import WaveformSession, SignalNode, GroupRenderMode
from .waveform_controller import WaveformController
from .signal_names_view import SignalNamesView, BaseColumnView
from .config import RENDERING, UI




class SignalValuesView(BaseColumnView):
    """Tree view for signal values at cursor (column 1)."""
    
    def __init__(self, parent=None):
        super().__init__(visible_column=1, allow_expansion=False, parent=parent)


class AnalysisView(BaseColumnView):
    """Tree view for analysis values (column 3)."""
    
    def __init__(self, parent=None):
        super().__init__(visible_column=3, allow_expansion=False, parent=parent)


class WaveScoutWidget(QWidget):
    """Main WaveScout widget with four synchronized panels."""
    
    cursorChanged = Signal(object)  # Using object to handle large time values
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.session: Optional[WaveformSession] = None
        self.model: Optional[WaveformItemModel] = None
        self.controller: WaveformController = WaveformController()
        self._shared_scrollbar: Optional[QScrollBar] = None
        self._selection_model: Optional[QItemSelectionModel] = None
        self._updating_selection = False
        self._setup_ui()
        # Bind controller events to view updates
        self.controller.on("viewport_changed", self._update_canvas_time_range)
        self.controller.on("cursor_changed", self._on_controller_cursor_changed)
        self.controller.on("benchmark_changed", self._on_controller_benchmark_changed)
        
    def _setup_ui(self):
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
        
        # Create splitter for the four panels
        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Create the four views
        self._names_view = SignalNamesView()
        self._values_view = SignalValuesView()
        self._canvas = WaveformCanvas(None)
        self._analysis_view = AnalysisView()
        
        # Install event filter on child views to handle keyboard shortcuts
        self._names_view.installEventFilter(self)
        self._values_view.installEventFilter(self)
        self._canvas.installEventFilter(self)
        self._analysis_view.installEventFilter(self)
        
        # Add views to splitter
        self._splitter.addWidget(self._names_view)
        self._splitter.addWidget(self._values_view)
        self._splitter.addWidget(self._canvas)
        self._splitter.addWidget(self._analysis_view)
        
        # Set initial splitter sizes
        if UI.SPLITTER_INITIAL_SIZES is not None:
            self._splitter.setSizes(UI.SPLITTER_INITIAL_SIZES)
        
        layout.addWidget(self._splitter)
        
        # Create shared scrollbar
        self._setup_shared_scrollbar()
        
        # Connect signals
        self._canvas.cursorMoved.connect(self._on_cursor_moved)
        
        # Sync header heights across panels
        self._sync_header_heights()
        
    def _setup_shared_scrollbar(self):
        """Set up the shared vertical scrollbar for row locking."""
        # Create a single scrollbar
        self._shared_scrollbar = QScrollBar(Qt.Orientation.Vertical)
        
        # Assign it to all views
        self._names_view.setVerticalScrollBar(self._shared_scrollbar)
        self._values_view.setVerticalScrollBar(self._shared_scrollbar)
        self._analysis_view.setVerticalScrollBar(self._shared_scrollbar)
        
        # Canvas will use the scrollbar for painting
        self._canvas.setSharedScrollBar(self._shared_scrollbar)
        self._shared_scrollbar.valueChanged.connect(self._canvas.update)
        
    def setSession(self, session: WaveformSession):
        """Set the waveform session and create the model."""
        self._cleanup_previous_session()
        self._initialize_new_session(session)
        # Inform controller last so it can emit events after canvas is ready
        self.controller.set_session(session)
        self._setup_model_connections()
        self._restore_ui_state()
    
    def _cleanup_previous_session(self):
        """Clean up the previous session resources."""
        # Disconnect signals from old model
        if hasattr(self, 'model') and self.model:
            try:
                self.model.layoutChanged.disconnect(self._update_scrollbar_range)
                self.model.rowsInserted.disconnect(self._update_scrollbar_range)
                self.model.rowsRemoved.disconnect(self._update_scrollbar_range)
            except:
                pass  # Signals might not be connected
        
        # Disconnect selection model signals
        if hasattr(self, '_selection_model') and self._selection_model:
            try:
                self._selection_model.selectionChanged.disconnect(self._on_selection_changed)
            except:
                pass
        
        # Disconnect view signals
        if hasattr(self, '_names_view') and self._names_view.model():
            try:
                self._names_view.expanded.disconnect(self._sync_expansion)
                self._names_view.collapsed.disconnect(self._sync_expansion)
            except:
                pass
        
        # Clear models from all views
        for view_name in ['_names_view', '_values_view', '_analysis_view', '_canvas']:
            if hasattr(self, view_name):
                view = getattr(self, view_name)
                if view:
                    view.setModel(None)
        
        # Delete old objects
        if hasattr(self, '_selection_model') and self._selection_model:
            self._selection_model.deleteLater()
            self._selection_model = None
        if hasattr(self, 'model') and self.model:
            self.model.deleteLater()
            self.model = None
    
    def _initialize_new_session(self, session: WaveformSession):
        """Initialize the new session and create models."""
        # Set new session
        self.session = session
        self.model = WaveformItemModel(session, self)
        
        # Create shared selection model
        self._selection_model = QItemSelectionModel(self.model)
        
        # Set model and selection model on all views
        self._names_view.setModel(self.model)
        self._names_view.setSelectionModel(self._selection_model)
        self._values_view.setModel(self.model)
        self._values_view.setSelectionModel(self._selection_model)
        self._analysis_view.setModel(self.model)
        self._analysis_view.setSelectionModel(self._selection_model)
        self._canvas.setModel(self.model)
        
        # Set canvas time range from viewport
        self._canvas.setTimeRange(session.viewport.start_time, session.viewport.end_time)
        self._canvas.setCursorTime(session.cursor_time)
    
    def _setup_model_connections(self):
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
    
    def _sync_header_heights(self):
        """Ensure all panel headers have the same height using system theme value."""
        try:
            height = RENDERING.DEFAULT_HEADER_HEIGHT
            for view in [self._names_view, self._values_view, self._analysis_view]:
                if view and view.header():
                    view.header().setFixedHeight(height)
        except Exception:
            # Fail-safe: ignore if headers are not yet available
            pass
    
    def _restore_ui_state(self):
        """Restore UI state including scrollbar and expansion states."""
        # Force the tree view to calculate sizes by processing events
        QApplication.processEvents()

        # Make sure headers are in sync before computing ranges
        self._sync_header_heights()
        
        # Update scrollbar range (this also sets header height)
        self._update_scrollbar_range()
        
        # Expand all groups initially based on their is_expanded state
        self._restore_expansion_state()
        
    def _update_scrollbar_range(self):
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
        

    def _calculate_total_rows(self, parent=QModelIndex()):
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
        
    def _sync_expansion(self, index):
        """Synchronize expansion state across all tree views."""
        is_expanded = self._names_view.isExpanded(index)
        
        # Update the data model
        if self.model is not None:
            node = self.model.data(index, Qt.ItemDataRole.UserRole)
            if isinstance(node, SignalNode) and node.is_group:
                node.is_expanded = is_expanded
        
        # Sync to other views
        if is_expanded:
            self._values_view.expand(index)
            self._analysis_view.expand(index)
        else:
            self._values_view.collapse(index)
            self._analysis_view.collapse(index)
            
        # Update scrollbar
        self._update_scrollbar_range()
        
        # Notify model that layout has changed to update canvas
        if self.model:
            self.model.layoutChanged.emit()
        
    def _restore_expansion_state(self, parent_index=QModelIndex()):
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
                    self._analysis_view.expand(index)
                else:
                    self._names_view.collapse(index)
                    self._values_view.collapse(index)
                    self._analysis_view.collapse(index)
                
                # Recurse into children
                self._restore_expansion_state(index)
    
    def _on_model_reset(self):
        """Handle model reset by restoring expansion state."""
        # Schedule restoration for next event loop iteration to ensure views are updated
        QTimer.singleShot(0, self._restore_expansion_state)
        self._update_scrollbar_range()
                
    def _on_cursor_moved(self, time):
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
            if self.session.time_ruler_config and hasattr(self, '_canvas'):
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
            
    def _on_controller_cursor_changed(self):
        """Controller signaled cursor change: refresh info bar and canvas."""
        if not self.session:
            return
        # Reuse existing on-canvas cursor formatting by calling canvas setter
        self._canvas.setCursorTime(self.session.cursor_time)
        # Update info bar text similar to _on_cursor_moved
        time = self.session.cursor_time
        if self.session.time_ruler_config and hasattr(self, '_canvas'):
            formatted_time = self._canvas._format_time_label(time, self.session.time_ruler_config.time_unit, None)
            self._info_bar.setText(f"Cursor: {formatted_time}")
        else:
            if self.session.timescale:
                unit_suffix = self.session.timescale.unit.value
                self._info_bar.setText(f"Cursor: {time} {unit_suffix}")
            else:
                self._info_bar.setText(f"Cursor: {time}")
        self.cursorChanged.emit(time)

    def _on_controller_benchmark_changed(self):
        if self._canvas:
            self._canvas.update()
            
    def _on_selection_changed(self, selected: QItemSelection, deselected: QItemSelection):
        """Handle selection changes and update the data model."""
        if self._updating_selection or not self.session or not self._selection_model or not self.model:
            return
            
        # Clear previous selection
        self.session.selected_nodes.clear()
        
        # Get all selected indexes
        selected_indexes = self._selection_model.selectedIndexes()
        
        # Filter to only column 0 (to avoid duplicates) and extract nodes
        processed_node_ids = set()
        for index in selected_indexes:
            if index.column() == 0:
                node = self.model.data(index, Qt.ItemDataRole.UserRole)
                node_id = id(node) if node else None
                if node and node_id not in processed_node_ids:
                    self.session.selected_nodes.append(node)
                    processed_node_ids.add(node_id)
        
        # Update canvas to highlight selected signals
        self._canvas.update()
        
    def _select_all(self):
        """Select all items in the model."""
        if not self._selection_model or not self.model:
            return
            
        # Create selection for all items
        selection = QItemSelection()
        
        def add_to_selection(parent_index=QModelIndex()):
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
        
    def eventFilter(self, watched, event):
        """Filter events from child widgets to handle keyboard shortcuts."""
        if event.type() == QEvent.Type.KeyPress:
            # Check if this is one of our shortcut keys
            key = event.key()
            modifiers = event.modifiers()
            
            # Zoom and navigation keys should be handled by parent
            if (key in [Qt.Key.Key_Plus, Qt.Key.Key_Equal, Qt.Key.Key_Minus] or
                (key == Qt.Key.Key_F and modifiers == Qt.KeyboardModifier.NoModifier) or
                (key == Qt.Key.Key_S and modifiers == Qt.KeyboardModifier.NoModifier) or
                (key == Qt.Key.Key_E and modifiers == Qt.KeyboardModifier.NoModifier) or
                (key == Qt.Key.Key_G and modifiers == Qt.KeyboardModifier.NoModifier) or
                key in [Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_PageUp, Qt.Key.Key_PageDown]):
                # Send the event to our keyPressEvent
                self.keyPressEvent(event)
                return True
        
        return super().eventFilter(watched, event)
    
    def keyPressEvent(self, event):
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
        else:
            super().keyPressEvent(event)
            
    def _delete_selected_nodes(self):
        """Delete all selected nodes from the data model."""
        if not self.session or not self.session.selected_nodes:
            return
            
        # Get selected nodes to delete (make a copy)
        nodes_to_delete = list(self.session.selected_nodes)
        
        # Clear selection in UI first to avoid accessing deleted nodes
        if self._selection_model:
            self._updating_selection = True  # Prevent selection change handler
            self._selection_model.clearSelection()
            self._updating_selection = False
        
        # Clear selection in data model
        self.session.selected_nodes.clear()
        
        # Begin model reset to prevent view updates during deletion
        if self.model:
            self.model.beginResetModel()
        
        try:
            # Create a set of node IDs for O(1) lookup
            nodes_to_delete_ids = {id(node) for node in nodes_to_delete}
            
            # Process deletions in a single pass
            # First, handle root nodes
            new_root_nodes = []
            for node in self.session.root_nodes:
                if id(node) not in nodes_to_delete_ids:
                    new_root_nodes.append(node)
                else:
                    # Clear parent reference for deleted nodes
                    node.parent = None
            self.session.root_nodes = new_root_nodes
            
            # Then handle children of non-deleted nodes
            for node in nodes_to_delete:
                if node.parent and id(node.parent) not in nodes_to_delete_ids:
                    # Remove from parent's children
                    parent = node.parent
                    parent.children = [child for child in parent.children if id(child) != id(node)]
                    node.parent = None
            
            # End model reset - this will refresh all views
            if self.model:
                self.model.endResetModel()
                
            # Restore expansion state after model reset
            self._restore_expansion_state()
            
        except Exception as e:
            print(f"Error during node deletion: {e}")
            # End model reset even on error
            if self.model:
                self.model.endResetModel()
                
    def _create_group_from_selected(self):
        """Create a new group containing the selected nodes."""
        if not self.session or not self.session.selected_nodes:
            return
            
        # Create a new group node
        group_name = f"Group {len([n for n in self.session.root_nodes if n.is_group]) + 1}"
        group_node = SignalNode(
            name=group_name,
            is_group=True,
            group_render_mode=GroupRenderMode.SEPARATE_ROWS,
            is_expanded=True
        )
        
        # Get selected nodes (make a copy to avoid modification during iteration)
        selected_nodes = list(self.session.selected_nodes)
        
        # Filter out nodes whose parent is also selected
        # This prevents flattening when grouping groups
        nodes_to_group = []
        
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
                nodes_to_group.append(node)
        
        # Clear selection in UI
        if self._selection_model:
            self._updating_selection = True
            self._selection_model.clearSelection()
            self._updating_selection = False
        
        # Clear selection in data model
        self.session.selected_nodes.clear()
        
        # Begin model reset
        if self.model:
            self.model.beginResetModel()
        
        try:
            # Find the position where to insert the new group
            # (position of the first node being grouped)
            insert_position = None
            insert_parent = None
            
            for node in nodes_to_group:
                if node.parent:
                    # Node is in a parent's children list
                    parent = node.parent
                    try:
                        idx = parent.children.index(node)
                        if insert_position is None or (insert_parent == parent and idx < insert_position):
                            insert_position = idx
                            insert_parent = parent
                    except ValueError:
                        pass
                else:
                    # Node is in root_nodes
                    try:
                        idx = self.session.root_nodes.index(node)
                        if insert_position is None or (insert_parent is None and idx < insert_position):
                            insert_position = idx
                            insert_parent = None
                    except ValueError:
                        pass
            
            # Remove selected nodes from their current parents and add to group
            for node in nodes_to_group:
                # Remove from root nodes if present
                if node in self.session.root_nodes:
                    self.session.root_nodes.remove(node)
                
                # Remove from parent's children if it has a parent
                if node.parent:
                    node.parent.children.remove(node)
                
                # Add to new group
                node.parent = group_node
                group_node.children.append(node)
            
            # Insert the group at the determined position
            if insert_parent is not None:
                # Insert into a parent's children
                group_node.parent = insert_parent
                if insert_position is not None and insert_position <= len(insert_parent.children):
                    insert_parent.children.insert(insert_position, group_node)
                else:
                    insert_parent.children.append(group_node)
            else:
                # Insert into root nodes
                if insert_position is not None and insert_position <= len(self.session.root_nodes):
                    self.session.root_nodes.insert(insert_position, group_node)
                else:
                    self.session.root_nodes.append(group_node)
            
            # End model reset
            if self.model:
                self.model.endResetModel()
                
            # Restore expansion state
            self._restore_expansion_state()
            
        except Exception as e:
            print(f"Error creating group: {e}")
            # End model reset even on error
            if self.model:
                self.model.endResetModel()
                
    def _zoom_in(self):
        """Zoom in by 2x (delta = 0.5)."""
        if self.session and self.session.viewport:
            self._zoom_viewport(0.5)
            
    def _zoom_out(self):
        """Zoom out by 2x (delta = 2.0)."""
        if self.session and self.session.viewport:
            self._zoom_viewport(2.0)
            
    def _zoom_to_fit(self):
        """Fit entire waveform in view (delegated to controller)."""
        self.controller.zoom_to_fit()
    
    def toggleBenchmarkMode(self):
        """Toggle benchmark mode on/off (delegated to controller)."""
        self.controller.toggle_benchmark_mode()
            
    def _zoom_viewport(self, zoom_factor: float, mouse_x: Optional[int] = None):
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
        
    def _pan_left(self):
        """Pan left by 10% of viewport width."""
        if self.session and self.session.viewport:
            viewport = self.session.viewport
            pan_distance = viewport.width * UI.PAN_PERCENTAGE
            self._pan_viewport(-pan_distance)
            
    def _pan_right(self):
        """Pan right by 10% of viewport width."""
        if self.session and self.session.viewport:
            viewport = self.session.viewport
            pan_distance = viewport.width * UI.PAN_PERCENTAGE
            self._pan_viewport(pan_distance)
            
    def _pan_viewport(self, pan_distance: float):
        """Pan viewport by given distance in relative coordinates.
        
        Args:
            pan_distance: Distance to pan (positive = right, negative = left)
        """
        if not self.session or not self.session.viewport:
            return
            
        # Delegate pan to controller; it will handle constraints and emit viewport_changed
        self.controller.pan_viewport(pan_distance)
        
    def _go_to_start(self):
        """Go to start of waveform (delegated to controller)."""
        if self.session and self.session.viewport:
            self.controller.go_to_start()
            
    def _go_to_end(self):
        """Go to end of waveform (delegated to controller)."""
        if self.session and self.session.viewport:
            self.controller.go_to_end()
            
    def _update_canvas_time_range(self):
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
            
    def wheelEvent(self, event):
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