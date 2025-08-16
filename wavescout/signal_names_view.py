"""Signal names tree view for the WaveScout widget."""

from PySide6.QtWidgets import QTreeView, QAbstractItemView, QMenu, QStyledItemDelegate, QWidget, QStyleOptionViewItem, QInputDialog, QColorDialog
from PySide6.QtCore import Qt, Signal, QModelIndex, QAbstractItemModel, QPoint, QSize
from PySide6.QtGui import QAction, QActionGroup, QKeyEvent, QColor
from typing import List, Optional, Callable, Union, TYPE_CHECKING
from PySide6.QtCore import QPersistentModelIndex
from .data_model import SignalNode, RenderType, AnalogScalingMode, DataFormat
from .config import RENDERING, UI

if TYPE_CHECKING:
    from .waveform_controller import WaveformController


class ScaledHeightDelegate(QStyledItemDelegate):
    """Custom delegate that scales row height based on SignalNode.height_scaling."""
    
    def __init__(self, base_height: int = RENDERING.DEFAULT_ROW_HEIGHT, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._base_height = base_height
        
    def sizeHint(self, option: QStyleOptionViewItem, index: Union[QModelIndex, QPersistentModelIndex]) -> QSize:
        """Return size hint with scaled height based on node's height_scaling."""
        # Get the default size hint
        size = super().sizeHint(option, index)
        
        # Get the signal node from the model
        node = index.data(Qt.ItemDataRole.UserRole)
        if isinstance(node, SignalNode):
            # Scale the height based on height_scaling
            scaled_height = self._base_height * node.height_scaling
            size.setHeight(scaled_height)
        else:
            size.setHeight(self._base_height)
            
        return size


class BaseColumnView(QTreeView):
    """Base class for column-specific tree views."""
    
    def __init__(self, visible_column: int, allow_expansion: bool = True, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._visible_column = visible_column
        self.setRootIsDecorated(True)
        self.setAlternatingRowColors(UI.TREE_ALTERNATING_ROWS)
        self.setUniformRowHeights(UI.TREE_UNIFORM_ROW_HEIGHTS)  # Changed to False to allow variable row heights
        self.setHeaderHidden(False)
        self.setItemsExpandable(allow_expansion)
        # Enable multi-selection
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        
        # Set custom delegate for height scaling
        self._delegate = ScaledHeightDelegate(base_height=RENDERING.DEFAULT_ROW_HEIGHT, parent=self)
        self.setItemDelegate(self._delegate)
        
    def setModel(self, model: Optional[QAbstractItemModel]) -> None:
        super().setModel(model)
        # Hide all columns except the specified one
        if model:
            for col in range(model.columnCount()):
                if col != self._visible_column:
                    self.setColumnHidden(col, True)
                    
    def expandAll(self) -> None:
        # Override in subclasses that don't allow expansion
        if not self.itemsExpandable():
            pass
        else:
            super().expandAll()


class SignalNamesView(BaseColumnView):
    """Tree view for signal names (column 0)."""
    
    # Signals
    navigate_to_scope_requested = Signal(str, str)  # Emits (scope_path, signal_name)
    
    def __init__(self, controller: 'WaveformController', parent: Optional[QWidget] = None) -> None:
        super().__init__(visible_column=0, allow_expansion=True, parent=parent)
        self._controller = controller
        
        # Enable context menu
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        
        # Enable drag and drop
        if UI.DRAG_DROP_ENABLED:
            self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
            self.setDefaultDropAction(Qt.DropAction.MoveAction)
            self.setDragDropOverwriteMode(False)
            self.setDropIndicatorShown(True)
            self.setDragEnabled(True)

    def _get_selected_signal_nodes(self) -> List[SignalNode]:
        """Return a list of selected SignalNode items (excluding groups)."""
        nodes: List[SignalNode] = []
        sel_model = self.selectionModel()
        if not sel_model:
            return nodes
        for idx in sel_model.selectedRows(0):
            n = self.model().data(idx, Qt.ItemDataRole.UserRole)
            if isinstance(n, SignalNode) and not n.is_group:
                nodes.append(n)
        return nodes

    def _get_all_selected_nodes(self) -> List[SignalNode]:
        """Return a list of all selected SignalNode items (including groups)."""
        nodes: List[SignalNode] = []
        sel_model = self.selectionModel()
        if not sel_model:
            return nodes
        for idx in sel_model.selectedRows(0):
            n = self.model().data(idx, Qt.ItemDataRole.UserRole)
            if isinstance(n, SignalNode):
                nodes.append(n)
        return nodes

    def _apply_to_selected_signals(self, apply_fn: Callable[[SignalNode], None], predicate: Optional[Callable[[SignalNode], bool]] = None) -> None:
        """Apply a function to all selected signal nodes.
        - apply_fn: callable taking a SignalNode
        - predicate: optional callable taking a SignalNode and returning bool
        """
        for n in self._get_selected_signal_nodes():
            if predicate is None or predicate(n):
                apply_fn(n)

    def _show_context_menu(self, position: QPoint) -> None:
        """Show context menu at the given position."""
        # Get the index at the position
        index = self.indexAt(position)
        if not index.isValid():
            return
            
        # Get the signal node
        node = self.model().data(index, Qt.ItemDataRole.UserRole)
        if not isinstance(node, SignalNode):
            return
            
        # Create context menu
        menu = QMenu(self)
        
        # For groups, only show rename action
        if node.is_group:
            rename_action = QAction("Rename", self)
            rename_action.triggered.connect(self._rename_selected_signal)
            menu.addAction(rename_action)
            
            # Show the menu at the cursor position
            menu.exec(self.viewport().mapToGlobal(position))
            return
        
        # For signals, show all options
        # Add data format submenu
        format_menu = menu.addMenu("Data Format")
        
        # Create action group for data format options (only one can be selected)
        format_group = QActionGroup(self)
        format_group.setExclusive(True)
        
        # Define data format options
        format_options = [
            ("Unsigned", DataFormat.UNSIGNED),
            ("Signed", DataFormat.SIGNED),
            ("Hex", DataFormat.HEX),
            ("Binary", DataFormat.BIN),
            ("Float32", DataFormat.FLOAT)
        ]
        
        # Create actions for each data format option
        for display_name, format_value in format_options:
            action = QAction(display_name, self)
            action.setCheckable(True)
            action.setChecked(node.format.data_format == format_value)
            action.setData(format_value)
            action.triggered.connect(lambda checked, f=format_value: self._apply_to_selected_signals(lambda n: self._set_data_format(n, f)))
            format_group.addAction(action)
            format_menu.addAction(action)
        
        # Add color selection action
        color_action = QAction("Set Color...", self)
        color_action.triggered.connect(self._set_signal_color)
        menu.addAction(color_action)
        menu.addSeparator()
        
        # Add render type submenu for multi-bit signals
        if node.is_multi_bit:
            render_menu = menu.addMenu("Set Render Type")
            
            # Create action group for render type options
            render_group = QActionGroup(self)
            render_group.setExclusive(True)
            
            # Bus option
            bus_action = QAction("Bus", self)
            bus_action.setCheckable(True)
            bus_action.setChecked(node.format.render_type == RenderType.BUS)
            bus_action.triggered.connect(lambda: self._apply_to_selected_signals(
                lambda n: self._set_render_type(n, RenderType.BUS), 
                predicate=lambda n: getattr(n, 'is_multi_bit', False)
            ))
            render_group.addAction(bus_action)
            render_menu.addAction(bus_action)
            
            # Analog Scale All option
            analog_all_action = QAction("Analog Scale All", self)
            analog_all_action.setCheckable(True)
            analog_all_action.setChecked(
                node.format.render_type == RenderType.ANALOG and 
                node.format.analog_scaling_mode == AnalogScalingMode.SCALE_TO_ALL_DATA
            )
            analog_all_action.triggered.connect(lambda: self._apply_to_selected_signals(
                lambda n: self._set_render_type_with_scaling(n, RenderType.ANALOG, AnalogScalingMode.SCALE_TO_ALL_DATA),
                predicate=lambda n: getattr(n, 'is_multi_bit', False)
            ))
            render_group.addAction(analog_all_action)
            render_menu.addAction(analog_all_action)
            
            # Analog Scale Visible option
            analog_visible_action = QAction("Analog Scale Visible", self)
            analog_visible_action.setCheckable(True)
            analog_visible_action.setChecked(
                node.format.render_type == RenderType.ANALOG and 
                node.format.analog_scaling_mode == AnalogScalingMode.SCALE_TO_VISIBLE_DATA
            )
            analog_visible_action.triggered.connect(lambda: self._apply_to_selected_signals(
                lambda n: self._set_render_type_with_scaling(n, RenderType.ANALOG, AnalogScalingMode.SCALE_TO_VISIBLE_DATA),
                predicate=lambda n: getattr(n, 'is_multi_bit', False)
            ))
            render_group.addAction(analog_visible_action)
            render_menu.addAction(analog_visible_action)
        
        # Add separator before rename action
        menu.addSeparator()
        
        # Add rename action
        rename_action = QAction("Rename", self)
        rename_action.triggered.connect(self._rename_selected_signal)
        menu.addAction(rename_action)
        
        # Add separator before navigation action
        menu.addSeparator()
        
        # Add navigate to scope action (only for signals, not groups)
        if not node.is_group:
            navigate_action = QAction("Navigate to scope", self)
            navigate_action.triggered.connect(self._navigate_to_scope)
            menu.addAction(navigate_action)
        
        # Add height scaling submenu
        height_menu = menu.addMenu("Set Height Scaling")
        
        # Create action group for height options (only one can be selected)
        height_group = QActionGroup(self)
        height_group.setExclusive(True)
        
        # Define height scaling options
        height_options = [1, 2, 3, 4, 8]
        
        # Create actions for each height option
        for height_value in height_options:
            action = QAction(f"{height_value}x", self)
            action.setCheckable(True)
            action.setChecked(node.height_scaling == height_value)
            action.setData(height_value)
            action.triggered.connect(lambda checked, h=height_value: self._apply_to_selected_signals(lambda n: self._set_height_scaling(n, h)))
            height_group.addAction(action)
            height_menu.addAction(action)
        
        # Show the menu at the cursor position
        menu.exec(self.viewport().mapToGlobal(position))
        
    def _set_data_format(self, node: SignalNode, data_format: DataFormat) -> None:
        """Set the data format for the given signal node."""
        self._controller.set_node_format(node.instance_id, data_format=data_format)
    
    def _set_signal_color(self) -> None:
        """Open color dialog and apply selected color to all selected signals."""
        # Get first selected signal's current color
        selected = self._get_selected_signal_nodes()
        if not selected:
            return
        
        current_color = QColor(selected[0].format.color)
        
        # Open color dialog
        new_color = QColorDialog.getColor(
            current_color, 
            self, 
            "Select Signal Color"
        )
        
        if new_color.isValid():
            # Apply to all selected signals
            color_str = new_color.name()  # Returns hex format "#RRGGBB"
            for node in selected:
                self._controller.set_node_format(
                    node.instance_id,
                    color=color_str
                )
                    
    def _set_height_scaling(self, node: SignalNode, height_scaling: int) -> None:
        """Set the height scaling for the given signal node."""
        self._controller.set_node_format(node.instance_id, height_scaling=height_scaling)
                    
    def _set_render_type(self, node: SignalNode, render_type: RenderType) -> None:
        """Set the render type for the given signal node."""
        self._controller.set_node_format(node.instance_id, render_type=render_type)
                    
    def _set_render_type_with_scaling(self, node: SignalNode, render_type: RenderType, scaling_mode: AnalogScalingMode) -> None:
        """Set both render type and analog scaling mode for the given signal node.
        Additionally, when switching into Analog mode via this context action,
        set the row height scaling to 3 by default for better analog visibility.
        This auto-adjustment happens only when transitioning from a non-Analog
        render type to Analog; users can still change height scaling later.
        """
        # Check if we're transitioning into Analog from a different mode
        # We must check BEFORE calling set_node_format since it updates the node
        old_render_type = node.format.render_type
        entering_analog = (render_type == RenderType.ANALOG and old_render_type != RenderType.ANALOG)
        
        # Use controller to set render type and analog scaling mode
        self._controller.set_node_format(
            node.instance_id, 
            render_type=render_type,
            analog_scaling_mode=scaling_mode
        )
        
        # If entering analog mode and height is still 1, set it to 3
        if entering_analog and node.height_scaling == 1:
            self._controller.set_node_format(node.instance_id, height_scaling=3)
                    
    def _find_node_index(self, target_node: SignalNode, parent: QModelIndex = QModelIndex()) -> QModelIndex:
        """Find the model index for the given node."""
        model = self.model()
        if not model:
            return QModelIndex()
            
        for row in range(model.rowCount(parent)):
            index = model.index(row, 0, parent)
            node = model.data(index, Qt.ItemDataRole.UserRole)
            
            if node == target_node:
                return index
                
            # Recursively search children
            if model.hasChildren(index):
                child_index = self._find_node_index(target_node, index)
                if child_index.isValid():
                    return child_index
                    
        return QModelIndex()
    
    def _navigate_to_scope(self) -> None:
        """Navigate to the parent scope of the selected signal."""
        # Get all selected nodes
        nodes = self._get_all_selected_nodes()
        if not nodes:
            return
        
        # Take the first selected node (skip groups)
        node = None
        for n in nodes:
            if not n.is_group:
                node = n
                break
        
        if not node:
            return
        
        # Extract scope path from signal path
        scope_path = self._extract_scope_path(node.name)
        if scope_path:
            # Emit signal to request navigation with both scope and full signal name
            self.navigate_to_scope_requested.emit(scope_path, node.name)
    
    def _extract_scope_path(self, signal_path: str) -> str:
        """Extract parent scope from signal path.
        
        Examples:
            'top.cpu.alu.result' -> 'top.cpu.alu'
            'signal' -> '' (no scope)
        """
        parts = signal_path.split('.')
        if len(parts) <= 1:
            return ''  # Top-level signal has no parent scope
        return '.'.join(parts[:-1])
    
    def _rename_selected_signal(self) -> None:
        """Rename the first selected signal or group with a user-defined nickname."""
        # Get all selected nodes (including groups)
        nodes = self._get_all_selected_nodes()
        if not nodes:
            return
        
        # Take the first selected node
        node = nodes[0]
        
        # Prepare dialog
        current_nickname = node.nickname if node.nickname else ""
        signal_name = node.name
        
        # Show input dialog
        new_nickname, ok = QInputDialog.getText(
            self,
            "Rename Signal",
            f"Enter nickname for '{signal_name}':",
            text=current_nickname
        )
        
        if ok:
            self._controller.rename_node(node.instance_id, new_nickname if new_nickname else "")
    
    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Handle key press events."""
        # Check for 'R' or 'r' key
        if event.key() == Qt.Key.Key_R and not event.modifiers():
            # Trigger rename for selected signal
            self._rename_selected_signal()
            event.accept()
        else:
            # Pass to parent for default handling
            super().keyPressEvent(event)