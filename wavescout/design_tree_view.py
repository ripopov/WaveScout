"""
Design Tree View Widget

A standalone widget providing two viewing modes for the design hierarchy:
- Unified Mode: Shows scopes and variables in a single tree
- Split Mode: Shows scopes in top panel and filtered variables in bottom panel
"""

from enum import Enum
from typing import Optional, List, Any, cast
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeView, QPushButton,
    QLabel, QStackedWidget, QSplitter, QLineEdit, QTableView,
    QHeaderView, QProgressDialog, QApplication, QAbstractItemView
)
from PySide6.QtCore import Qt, Signal, QSettings, QModelIndex, QSortFilterProxyModel, QEvent
from PySide6.QtGui import QKeyEvent

from .design_tree_model import DesignTreeModel, DesignTreeNode
from .data_model import SignalNode, RenderType, DisplayFormat, SignalHandle
from .scope_tree_model import ScopeTreeModel
from .vars_view import VarsView


class DesignTreeViewMode(Enum):
    """Viewing modes for the design tree"""
    UNIFIED = "unified"
    SPLIT = "split"


class DesignTreeView(QWidget):
    """
    Main design tree widget supporting unified and split viewing modes
    """
    
    # Signals
    signals_selected = Signal(list)  # List of SignalNode objects
    status_message = Signal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.waveform_db: Optional[Any] = None
        self.design_tree_model: Optional[DesignTreeModel] = None
        self.scope_tree_model: Optional[ScopeTreeModel] = None
        self.vars_view: Optional[VarsView] = None
        self.current_mode = DesignTreeViewMode.UNIFIED
        
        # Settings
        self.settings = QSettings("WaveScout", "Demo")
        
        # Setup UI
        self._setup_ui()
        
        # Load saved mode
        saved_mode = self.settings.value("design_tree_view_mode", "unified")
        self.set_mode(DesignTreeViewMode(saved_mode))
    
    def _setup_ui(self):
        """Create the UI structure"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Header with mode toggle
        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(5, 5, 5, 5)
        
        title_label = QLabel("Design Hierarchy")
        title_label.setStyleSheet("font-weight: bold;")
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        
        self.mode_button = QPushButton("Split View")
        self.mode_button.setToolTip("Toggle between Unified and Split view modes")
        self.mode_button.setCheckable(True)
        self.mode_button.toggled.connect(self._on_mode_toggled)
        header_layout.addWidget(self.mode_button)
        
        layout.addWidget(header_widget)
        
        # Content area with stacked widget for different modes
        self.content_stack = QStackedWidget()
        layout.addWidget(self.content_stack)
        
        # Unified mode widget
        self.unified_tree = QTreeView()
        self.unified_tree.setAlternatingRowColors(True)
        self.unified_tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.unified_tree.doubleClicked.connect(self._on_tree_double_click)
        self.content_stack.addWidget(self.unified_tree)
        
        # Split mode widget (placeholder for now)
        self.split_widget = QSplitter(Qt.Orientation.Vertical)
        
        # Top panel: Scope tree
        self.scope_tree = QTreeView()
        self.scope_tree.setAlternatingRowColors(True)
        self.scope_tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        # Let QTreeView handle expansion by default - don't override
        self.scope_tree.setExpandsOnDoubleClick(True)
        self.split_widget.addWidget(self.scope_tree)
        
        # Bottom panel: Variables view
        self.vars_view = VarsView()
        self.vars_view.variables_selected.connect(self._on_variables_selected)
        self.split_widget.addWidget(self.vars_view)
        
        # Set initial splitter sizes (30% top, 70% bottom)
        self.split_widget.setSizes([300, 700])
        
        self.content_stack.addWidget(self.split_widget)
    
    def set_waveform_db(self, waveform_db: Any):
        """Set the waveform database and initialize models"""
        self.waveform_db = waveform_db
        
        if waveform_db is None:
            self.design_tree_model = None
            self.unified_tree.setModel(None)
            return
        
        # Create and set the design tree model
        self.design_tree_model = DesignTreeModel(waveform_db)
        self.unified_tree.setModel(self.design_tree_model)
        
        # Optimize: Expand only first scope instead of all
        self.unified_tree.expandToDepth(1)
        
        # Update split mode models if needed
        if self.current_mode == DesignTreeViewMode.SPLIT:
            self._update_split_mode_models()
    
    def set_mode(self, mode: DesignTreeViewMode):
        """Switch between unified and split viewing modes"""
        self.current_mode = mode
        
        if mode == DesignTreeViewMode.UNIFIED:
            self.content_stack.setCurrentIndex(0)
            self.mode_button.setText("Split View")
            self.mode_button.setChecked(False)
        else:
            self.content_stack.setCurrentIndex(1)
            self.mode_button.setText("Unified View")
            self.mode_button.setChecked(True)
            self._update_split_mode_models()
        
        # Save preference
        self.settings.setValue("design_tree_view_mode", mode.value)
    
    def _on_mode_toggled(self, checked: bool):
        """Handle mode toggle button click"""
        if checked:
            self.set_mode(DesignTreeViewMode.SPLIT)
        else:
            self.set_mode(DesignTreeViewMode.UNIFIED)
    
    def _update_split_mode_models(self):
        """Update models for split mode."""
        if not self.waveform_db:
            return
        
        # Create scope tree model if needed
        if not self.scope_tree_model:
            self.scope_tree_model = ScopeTreeModel(self.waveform_db)
            self.scope_tree.setModel(self.scope_tree_model)
            self.scope_tree.selectionModel().currentChanged.connect(self._on_scope_selection_changed)
            self.scope_tree.expandToDepth(1)  # Expand first level
        else:
            self.scope_tree_model.load_hierarchy(self.waveform_db)
        
        # Clear variables view
        if self.vars_view:
            self.vars_view.set_variables([])
    
    def _on_tree_double_click(self, index: QModelIndex):
        """Handle double-click on tree item in unified mode"""
        if not index.isValid() or not self.design_tree_model:
            return
        
        node = index.internalPointer()
        if node and not node.is_scope:
            signal_node = self._create_signal_node(node)
            if signal_node:
                self.signals_selected.emit([signal_node])
    
    def _create_signal_node(self, node: DesignTreeNode) -> Optional[SignalNode]:
        """Create a SignalNode from a tree node"""
        if node.is_scope or not self.waveform_db:
            return None
        
        # Build full path
        path_parts = []
        current = node
        while current and current.parent:
            path_parts.append(current.name)
            current = current.parent
        
        if not path_parts:
            return None
        
        path_parts.reverse()
        full_path = ".".join(path_parts)
        
        # Get handle from node if available
        handle = None
        if hasattr(node, 'var_handle') and node.var_handle is not None:
            handle = node.var_handle
        elif hasattr(node, 'var') and node.var and self.waveform_db:
            # Try to get handle from var object
            if hasattr(self.waveform_db, 'get_handle_for_var'):
                handle = self.waveform_db.get_handle_for_var(node.var)
            elif hasattr(self.waveform_db, 'iter_handles_and_vars'):
                # Find handle by iterating (less efficient but works)
                for h, vars_list in self.waveform_db.iter_handles_and_vars():
                    if node.var in vars_list:
                        handle = h
                        break
        
        # If not, try to find signal handle by path
        if handle is None:
            handle = self._find_signal_handle(full_path)
            
        if handle is None:
            return None
        
        # Determine render type using helper and var_type if available
        var_obj = node.var if hasattr(node, 'var') else None
        is_single_bit = self._is_single_bit(var_obj, handle)
        var_type_str = None
        if var_obj is None and hasattr(self.waveform_db, 'get_var') and handle is not None:
            try:
                var_obj = self.waveform_db.get_var(handle)
            except Exception:
                var_obj = None
        if var_obj is not None and hasattr(var_obj, 'var_type'):
            try:
                var_type_str = str(var_obj.var_type())
            except Exception:
                var_type_str = None
        if var_type_str == "Event":
            render_type = RenderType.EVENT
        else:
            render_type = RenderType.BOOL if is_single_bit else RenderType.BUS
        format = DisplayFormat(render_type=render_type)
        
        return SignalNode(
            name=full_path,
            handle=handle,
            format=format,
            is_multi_bit=not is_single_bit
        )
    
    def _find_signal_handle(self, full_path: str) -> Optional[SignalHandle]:
        """Find signal handle in waveform database"""
        if not self.waveform_db:
            return None
        
        # Try direct lookup
        if full_path in self.waveform_db._var_map:
            handle: SignalHandle = self.waveform_db._var_map[full_path]
            return handle
        
        # Try with TOP prefix
        top_path = f"TOP.{full_path}"
        if top_path in self.waveform_db._var_map:
            top_handle: SignalHandle = self.waveform_db._var_map[top_path]
            return top_handle
        
        return None
    
    def add_selected_signals(self):
        """Add currently selected signals to waveform (called by 'I' shortcut)"""
        signal_nodes: List[SignalNode] = []
        
        if self.current_mode == DesignTreeViewMode.UNIFIED:
            # Get selected items from unified tree
            selection = self.unified_tree.selectionModel()
            if not selection:
                return
            
            for index in selection.selectedIndexes():
                if index.column() == 0:  # Only process first column
                    node = index.internalPointer()
                    if node and not node.is_scope:
                        signal_node = self._create_signal_node(node)
                        if signal_node:
                            signal_nodes.append(signal_node)
        else:
            # Handle split mode - get selected variables from VarsView
            if self.vars_view:
                selected_vars = self.vars_view.get_selected_variables()
                for var_data in selected_vars:
                    signal_node = self._create_signal_node_from_var(var_data)
                    if signal_node:
                        signal_nodes.append(signal_node)
        
        if signal_nodes:
            # Show progress dialog for batch operations
            if len(signal_nodes) > 10:
                progress = QProgressDialog(
                    "Adding signals...", "Cancel", 0, len(signal_nodes), self
                )
                progress.setWindowModality(Qt.WindowModality.WindowModal)
                progress.show()
                
                for i, signal_node in enumerate(signal_nodes):
                    if progress.wasCanceled():
                        break
                    progress.setValue(i)
                    QApplication.processEvents()
                
                progress.setValue(len(signal_nodes))
            
            self.signals_selected.emit(signal_nodes)
            self.status_message.emit(f"Added {len(signal_nodes)} signal(s)")
    
    def eventFilter(self, obj: Any, event: QEvent) -> bool:
        """Event filter to handle keyboard shortcuts"""
        if event.type() == QEvent.Type.KeyPress:
            key_event = cast(QKeyEvent, event)
            
            # Check if the event is from one of our monitored widgets
            is_from_unified = obj == self.unified_tree
            is_from_scope = obj == self.scope_tree
            is_from_vars = self.vars_view and obj == self.vars_view.table_view
            
            # 'i', 'I' or Insert key - add selected signals
            if key_event.key() == Qt.Key.Key_I:
                # Accept both lowercase 'i' (no modifiers) and uppercase 'I' (with Shift)
                if (key_event.modifiers() == Qt.KeyboardModifier.NoModifier or 
                    key_event.modifiers() == Qt.KeyboardModifier.ShiftModifier):
                    # Only process if from a relevant widget
                    if is_from_unified or is_from_vars:
                        self.add_selected_signals()
                        return True
            elif key_event.key() == Qt.Key.Key_Insert:
                if is_from_unified or is_from_vars:
                    self.add_selected_signals()
                    return True
            
            # Ctrl+F - focus filter in split mode
            elif (key_event.key() == Qt.Key.Key_F and 
                  key_event.modifiers() == Qt.KeyboardModifier.ControlModifier):
                if self.current_mode == DesignTreeViewMode.SPLIT and self.vars_view:
                    self.vars_view.focus_filter()
                    return True
            
            # Escape - clear filter in split mode
            elif key_event.key() == Qt.Key.Key_Escape:
                if self.current_mode == DesignTreeViewMode.SPLIT and self.vars_view:
                    self.vars_view.clear_filter()
                    return True
        
        return super().eventFilter(obj, event)
    
    def install_event_filters(self):
        """Install event filters on tree views"""
        self.unified_tree.installEventFilter(self)
        self.scope_tree.installEventFilter(self)
        if self.vars_view:
            self.vars_view.table_view.installEventFilter(self)
    
    def _on_scope_selection_changed(self, current: QModelIndex, previous: QModelIndex):
        """Handle scope selection change in split mode."""
        if not current.isValid() or not self.scope_tree_model:
            return
        
        # Get the selected scope node
        scope_node = current.internalPointer()
        if not scope_node:
            return
        
        # Get variables for this scope
        variables = self.scope_tree_model.get_variables_for_scope(scope_node)
        
        # Update vars view
        if self.vars_view:
            self.vars_view.set_variables(variables)
    
    def _on_variables_selected(self, var_data_list):
        """Handle variables selected from VarsView."""
        signal_nodes = []
        for var_data in var_data_list:
            signal_node = self._create_signal_node_from_var(var_data)
            if signal_node:
                signal_nodes.append(signal_node)
        
        if signal_nodes:
            self.signals_selected.emit(signal_nodes)
            self.status_message.emit(f"Added {len(signal_nodes)} signal(s)")
    
    def _is_single_bit(self, var_obj: Any, handle: Optional[SignalHandle]) -> bool:
        """Determine if a variable/signal is single-bit using pywellen API.
        
        Tries the provided var object first; if not available, attempts to fetch
        it from the waveform_db using the handle. Falls back to True on errors
        to keep behavior safe by default.
        """
        is_single_bit = True
        # Ensure we have a var object
        if var_obj is None and hasattr(self.waveform_db, 'get_var') and handle is not None:
            try:
                var_obj = self.waveform_db.get_var(handle)
            except Exception:
                var_obj = None
        # Use pywellen is_1bit if available
        if var_obj is not None and hasattr(var_obj, 'is_1bit'):
            try:
                is_single_bit = bool(var_obj.is_1bit())
            except Exception:
                is_single_bit = True
        return is_single_bit
    
    def _create_signal_node_from_var(self, var_data: dict) -> Optional[SignalNode]:
        """Create a SignalNode from variable data."""
        if not var_data or not self.waveform_db:
            return None
        
        full_path = var_data.get('full_path', var_data.get('name'))
        if not full_path:
            return None
        
        # Check if we have a var object directly in the data
        var = var_data.get('var')
        handle = None
        
        if var and hasattr(self.waveform_db, 'get_handle_for_var'):
            # Try to get handle from var object
            handle = self.waveform_db.get_handle_for_var(var)
        
        if handle is None:
            # Fallback to path-based lookup
            handle = self._find_signal_handle(full_path)
        
        if handle is None:
            return None
        
        # Determine render type using the helper and var_type if available
        is_single_bit = self._is_single_bit(var, handle)
        var_type_str = None
        # Try get var_type from var_data first
        vt = var_data.get('var_type')
        if vt is not None:
            var_type_str = str(vt)
        elif var is not None and hasattr(var, 'var_type'):
            try:
                var_type_str = str(var.var_type())
            except Exception:
                var_type_str = None
        if var_type_str == "Event":
            render_type = RenderType.EVENT
        else:
            render_type = RenderType.BOOL if is_single_bit else RenderType.BUS
        format = DisplayFormat(render_type=render_type)
        
        return SignalNode(
            name=full_path,
            handle=handle,
            format=format,
            is_multi_bit=not is_single_bit
        )