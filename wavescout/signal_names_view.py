"""Signal names tree view for the WaveScout widget."""

from PySide6.QtWidgets import QTreeView, QAbstractItemView, QMenu, QStyledItemDelegate
from PySide6.QtCore import Qt, Signal, QModelIndex
from PySide6.QtGui import QAction, QActionGroup
from .data_model import SignalNode, RenderType, AnalogScalingMode, DataFormat
from .config import RENDERING, UI


class ScaledHeightDelegate(QStyledItemDelegate):
    """Custom delegate that scales row height based on SignalNode.height_scaling."""
    
    def __init__(self, base_height=RENDERING.DEFAULT_ROW_HEIGHT, parent=None):
        super().__init__(parent)
        self._base_height = base_height
        
    def sizeHint(self, option, index):
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
    
    def __init__(self, visible_column: int, allow_expansion: bool = True, parent=None):
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
        
    def setModel(self, model):
        super().setModel(model)
        # Hide all columns except the specified one
        if model:
            for col in range(model.columnCount()):
                if col != self._visible_column:
                    self.setColumnHidden(col, True)
                    
    def expandAll(self):
        # Override in subclasses that don't allow expansion
        if not self.itemsExpandable():
            pass
        else:
            super().expandAll()


class SignalNamesView(BaseColumnView):
    """Tree view for signal names (column 0)."""
    
    def __init__(self, parent=None):
        super().__init__(visible_column=0, allow_expansion=True, parent=parent)
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

    def _get_selected_signal_nodes(self):
        """Return a list of selected SignalNode items (excluding groups)."""
        nodes = []
        sel_model = self.selectionModel()
        if not sel_model:
            return nodes
        for idx in sel_model.selectedRows(0):
            n = self.model().data(idx, Qt.ItemDataRole.UserRole)
            if isinstance(n, SignalNode) and not n.is_group:
                nodes.append(n)
        return nodes

    def _apply_to_selected_signals(self, apply_fn, predicate=None):
        """Apply a function to all selected signal nodes.
        - apply_fn: callable taking a SignalNode
        - predicate: optional callable taking a SignalNode and returning bool
        """
        for n in self._get_selected_signal_nodes():
            if predicate is None or predicate(n):
                apply_fn(n)

    def _show_context_menu(self, position):
        """Show context menu at the given position."""
        # Get the index at the position
        index = self.indexAt(position)
        if not index.isValid():
            return
            
        # Get the signal node
        node = self.model().data(index, Qt.ItemDataRole.UserRole)
        if not isinstance(node, SignalNode) or node.is_group:
            return
            
        # Create context menu
        menu = QMenu(self)
        
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
        
        # Add render type submenu for multi-bit signals
        if node.is_multi_bit:
            render_menu = menu.addMenu("Set Render Type")
            
            # Create action group for render type options
            render_group = QActionGroup(self)
            render_group.setExclusive(True)
            
            # Define render type options
            render_options = [
                ("Bus", RenderType.BUS),
                ("Analog", RenderType.ANALOG)
            ]
            
            # Create actions for each render type
            for display_name, render_value in render_options:
                action = QAction(display_name, self)
                action.setCheckable(True)
                action.setChecked(node.format.render_type == render_value)
                action.setData(render_value)
                action.triggered.connect(lambda checked, r=render_value: self._apply_to_selected_signals(lambda n: self._set_render_type(n, r), predicate=lambda n: getattr(n, 'is_multi_bit', False)))
                render_group.addAction(action)
                render_menu.addAction(action)
            
            # Add analog scaling submenu if render type is analog
            if node.format.render_type == RenderType.ANALOG:
                analog_menu = menu.addMenu("Analog Scaling")
                
                # Create action group for analog scaling options
                analog_group = QActionGroup(self)
                analog_group.setExclusive(True)
                
                # Define analog scaling options
                analog_options = [
                    ("Scale to All Data", AnalogScalingMode.SCALE_TO_ALL_DATA),
                    ("Scale to Visible Data", AnalogScalingMode.SCALE_TO_VISIBLE_DATA)
                ]
                
                # Create actions for each analog scaling option
                for display_name, scaling_value in analog_options:
                    action = QAction(display_name, self)
                    action.setCheckable(True)
                    action.setChecked(node.format.analog_scaling_mode == scaling_value)
                    action.setData(scaling_value)
                    action.triggered.connect(lambda checked, s=scaling_value: self._apply_to_selected_signals(lambda n: self._set_analog_scaling(n, s), predicate=lambda n: getattr(n, 'format', None) and n.format.render_type == RenderType.ANALOG))
                    analog_group.addAction(action)
                    analog_menu.addAction(action)
        
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
        
    def _set_data_format(self, node: SignalNode, data_format: DataFormat):
        """Set the data format for the given signal node."""
        if node.format.data_format != data_format:
            node.format.data_format = data_format
            
            # Notify the model that the data has changed
            if self.model():
                # Find the index for this node
                index = self._find_node_index(node)
                if index.isValid():
                    # Emit dataChanged for all columns to update all views
                    # Include both DisplayRole and UserRole to ensure canvas updates
                    self.model().dataChanged.emit(
                        self.model().index(index.row(), 0, index.parent()),
                        self.model().index(index.row(), self.model().columnCount() - 1, index.parent()),
                        [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.UserRole]
                    )
                    
    def _set_height_scaling(self, node: SignalNode, height_scaling: int):
        """Set the height scaling for the given signal node."""
        if node.height_scaling != height_scaling:
            node.height_scaling = height_scaling
            
            # Notify the model that the data has changed
            if self.model():
                # Find the index for this node
                index = self._find_node_index(node)
                if index.isValid():
                    # Emit dataChanged for all columns to update all views
                    self.model().dataChanged.emit(
                        self.model().index(index.row(), 0, index.parent()),
                        self.model().index(index.row(), self.model().columnCount() - 1, index.parent()),
                        [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.UserRole]
                    )
                    
                    # Also need to trigger a layout change since row heights will change
                    self.model().layoutChanged.emit()
                    
    def _set_render_type(self, node: SignalNode, render_type: RenderType):
        """Set the render type for the given signal node."""
        if node.format.render_type != render_type:
            node.format.render_type = render_type
            
            # Clear any cached range data when switching modes
            # This will be handled by the canvas when it detects the change
            
            # Notify the model that the data has changed
            if self.model():
                # Find the index for this node
                index = self._find_node_index(node)
                if index.isValid():
                    # Emit dataChanged for all columns to update all views
                    self.model().dataChanged.emit(
                        self.model().index(index.row(), 0, index.parent()),
                        self.model().index(index.row(), self.model().columnCount() - 1, index.parent()),
                        [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.UserRole]
                    )
                    # Trigger layout change to refresh rendering
                    self.model().layoutChanged.emit()
                    
    def _set_analog_scaling(self, node: SignalNode, scaling_mode: AnalogScalingMode):
        """Set the analog scaling mode for the given signal node."""
        if node.format.analog_scaling_mode != scaling_mode:
            node.format.analog_scaling_mode = scaling_mode
            
            # Clear viewport range cache if switching to/from SCALE_TO_VISIBLE_DATA
            # This will be handled by the canvas when it detects the change
            
            # Notify the model that the data has changed
            if self.model():
                # Find the index for this node
                index = self._find_node_index(node)
                if index.isValid():
                    # Emit dataChanged for all columns to update all views
                    self.model().dataChanged.emit(
                        self.model().index(index.row(), 0, index.parent()),
                        self.model().index(index.row(), self.model().columnCount() - 1, index.parent()),
                        [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.UserRole]
                    )
                    
    def _find_node_index(self, target_node: SignalNode, parent=QModelIndex()):
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