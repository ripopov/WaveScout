"""Qt Model/View bridge for waveform data."""

from PySide6.QtCore import Qt, QModelIndex, QAbstractItemModel, QPersistentModelIndex, QObject, QMimeData, QByteArray
from typing import overload, Any, List, Optional, Union, Tuple
import json
from .data_model import WaveformSession, SignalNode, SignalNameDisplayMode, RenderType, DataFormat


class WaveformItemModel(QAbstractItemModel):
    """Exposes SignalNode tree to Qt views while keeping dataclass purity."""

    def __init__(self, session: WaveformSession, parent=None):
        super().__init__(parent)
        self._session = session
        self._headers = ["Signal", "Value", "Waveform", "Analysis"]

    # -- overriding row/column API --
    def columnCount(self, _parent=QModelIndex()):
        return 4  # One column for each panel: Signal, Value, Waveform, Analysis

    def rowCount(self, parent=QModelIndex()):
        # Return number of children for given parent (or root nodes)
        if not parent.isValid():
            return len(self._session.root_nodes)
        
        node = parent.internalPointer()
        if node and isinstance(node, SignalNode):
            return len(node.children)
        return 0

    def index(self, row: int, col: int, parent: Union[QModelIndex, QPersistentModelIndex] = QModelIndex()) -> QModelIndex:
        # Create QModelIndex for child at (row, col) under parent
        if not self.hasIndex(row, col, parent):
            return QModelIndex()
        
        if not parent.isValid():
            # Top level
            if 0 <= row < len(self._session.root_nodes):
                return self.createIndex(row, col, self._session.root_nodes[row])
        else:
            parent_node = parent.internalPointer()
            if parent_node and 0 <= row < len(parent_node.children):
                return self.createIndex(row, col, parent_node.children[row])
        
        return QModelIndex()

    @overload
    def parent(self) -> QObject: ...
    
    @overload
    def parent(self, child_idx: QModelIndex | QPersistentModelIndex) -> QModelIndex: ...
    
    def parent(self, child_idx: QModelIndex | QPersistentModelIndex | None = None) -> QModelIndex | QObject:
        # Handle overloaded parent() method
        if child_idx is None:
            return super().parent()
        
        # Return parent index of given child, navigating the tree structure
        if not child_idx.isValid():
            return QModelIndex()
        
        node = child_idx.internalPointer()
        if not node or not node.parent:
            return QModelIndex()
        
        parent_node = node.parent
        
        # Find row of parent within its siblings
        if parent_node.parent:
            # Parent has a grandparent
            row = parent_node.parent.children.index(parent_node)
        else:
            # Parent is a root node
            try:
                row = self._session.root_nodes.index(parent_node)
            except ValueError:
                return QModelIndex()
        
        return self.createIndex(row, 0, parent_node)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        # Return appropriate data based on column and role
        if not index.isValid():
            return None
        
        node = index.internalPointer()
        if not isinstance(node, SignalNode):
            return None

        if role == Qt.ItemDataRole.DisplayRole:
            col = index.column()
            if col == 0:
                return self._format_signal_name(node)
            elif col == 1:
                # Value at cursor position
                return self._value_at_cursor(node)
            elif col == 2:
                return ""  # Waveform painted by canvas
            elif col == 3:
                return self._analysis_value(node)
        elif role == Qt.ItemDataRole.ForegroundRole:
            return node.format.color
        elif role == Qt.ItemDataRole.UserRole:
            return node  # For delegates to access full node data
        
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            if 0 <= section < len(self._headers):
                return self._headers[section]
        return None

    def flags(self, index):
        if not index.isValid():
            return Qt.ItemFlag.ItemIsDropEnabled
        
        default_flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        
        # Enable drag for valid items
        node = index.internalPointer()
        if node and isinstance(node, SignalNode):
            return default_flags | Qt.ItemFlag.ItemIsDragEnabled | Qt.ItemFlag.ItemIsDropEnabled
        
        return default_flags

    def hasChildren(self, parent=QModelIndex()):
        if not parent.isValid():
            return len(self._session.root_nodes) > 0
        
        node = parent.internalPointer()
        return node and len(node.children) > 0

    def _format_signal_name(self, node: SignalNode) -> str:
        # Nickname takes precedence, else use hierarchical display mode
        if node.nickname:
            return node.nickname
        
        mode = self._session.signal_name_display_mode
        
        if mode == SignalNameDisplayMode.FULL_PATH:
            return node.name
        elif mode == SignalNameDisplayMode.LAST_N_LEVELS:
            # Split hierarchical name and take last N levels
            parts = node.name.split('.')
            n = self._session.signal_name_hierarchy_levels
            return '.'.join(parts[-n:]) if len(parts) > n else node.name
        
        return node.name  # fallback
    
    def _value_at_cursor(self, node: SignalNode) -> str:
        # Query WaveformDB for signal value at cursor time
        if node.is_group or not self._session.waveform_db or node.handle is None:
            return ""
        
        try:
            value = self._session.waveform_db.sample(node.handle, self._session.cursor_time)
            
            # Format value based on display format
            if node.format.render_type == RenderType.ANALOG:
                # For analog, just return the value
                return str(value)
            # For digital signals, the value should already be formatted by signal_sampling
            # based on the data_format, so just return it as-is
            
            return str(value)
        except:
            return ""
    
    def _analysis_value(self, node: SignalNode) -> str:
        # Calculate min/max/avg based on analysis mode and range
        if node.is_group or not self._session.waveform_db:
            return ""
        
        mode = self._session.analysis_mode
        if mode.mode == "none":
            return ""
        
        # TODO: Implement analysis calculations
        # For now, return placeholder
        if mode.mode == "max":
            return "1"
        elif mode.mode == "min":
            return "0"
        
        return ""
    
    # -- Drag and Drop Support --
    def supportedDropActions(self):
        return Qt.DropAction.MoveAction
    
    def mimeTypes(self):
        return ["application/x-wavescout-signalnodes"]
    
    def mimeData(self, indexes):
        if not indexes:
            return None
        
        # Collect unique nodes (avoid duplicates from multiple columns)
        nodes_data = []
        seen_nodes = []
        
        for index in indexes:
            if index.column() == 0:  # Only process first column
                node = index.internalPointer()
                if node and node not in seen_nodes:
                    seen_nodes.append(node)
                    # Store node path for reconstruction
                    node_path = self._get_node_path(node)
                    nodes_data.append({
                        'path': node_path,
                        'row': index.row(),
                        'is_group': node.is_group
                    })
        
        if not nodes_data:
            return None
        
        mime_data = QMimeData()
        data = json.dumps(nodes_data).encode('utf-8')
        mime_data.setData("application/x-wavescout-signalnodes", QByteArray(data))
        return mime_data
    
    def canDropMimeData(self, data, action, row, column, parent):
        if not data.hasFormat("application/x-wavescout-signalnodes"):
            return False
        
        if action != Qt.DropAction.MoveAction:
            return False
        
        # Always allow drops - we'll handle the logic in dropMimeData
        return True
    
    def dropMimeData(self, data, action, row, column, parent):
        if not self.canDropMimeData(data, action, row, column, parent):
            return False

        # Parse the drag data
        byte_data = data.data("application/x-wavescout-signalnodes")
        nodes_data = json.loads(byte_data.data().decode('utf-8'))
        
        # Determine drop target and insertion position
        if row == -1 and parent.isValid():
            # Dropped directly on an item
            target_node = parent.internalPointer()
            
            if target_node.is_group:
                # Dropped on a group - insert at the beginning of the group
                parent_node = target_node
                target_list = target_node.children
                insert_row = 0
            else:
                # Dropped on a non-group item - insert after it in the same parent
                parent_node = target_node.parent
                
                if parent_node:
                    target_list = parent_node.children
                    # Find the position of the target item and insert after it
                    try:
                        target_index = target_list.index(target_node)
                        insert_row = target_index + 1
                    except ValueError:
                        insert_row = len(target_list)
                else:
                    # Target is a root node
                    target_list = self._session.root_nodes
                    try:
                        target_index = target_list.index(target_node)
                        insert_row = target_index + 1
                    except ValueError:
                        insert_row = len(target_list)
        elif parent.isValid():
            # Dropped between items in a group
            parent_node = parent.internalPointer()
            target_list = parent_node.children
            insert_row = row if row != -1 else len(target_list)
        else:
            # Dropped at root level
            parent_node = None
            target_list = self._session.root_nodes
            insert_row = row if row != -1 else len(target_list)
        
        # Collect nodes to move
        nodes_to_move = []
        for node_data in nodes_data:
            node = self._find_node_by_path(node_data['path'])
            if node:
                nodes_to_move.append(node)
        
        if not nodes_to_move:
            return False
        
        # Perform the move
        try:
            return self._move_nodes(nodes_to_move, parent_node, insert_row)
        except Exception as e:
            print(f"Drop failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _get_node_path(self, node: SignalNode) -> List[str]:
        """Get the path from root to this node."""
        path = []
        current: Optional[SignalNode] = node
        while current:
            path.append(current.name)
            current = current.parent
        return list(reversed(path))
    
    def _find_node_by_path(self, path: List[str]) -> Optional[SignalNode]:
        """Find a node by its path from root."""
        if not path:
            return None
        
        # Start from root nodes
        current_list = self._session.root_nodes
        current_node = None
        
        for name in path:
            found = False
            for node in current_list:
                if node.name == name:
                    current_node = node
                    current_list = node.children
                    found = True
                    break
            if not found:
                return None
        
        return current_node
    
    def _move_nodes(self, nodes: List[SignalNode], new_parent: Optional[SignalNode], insert_row: int) -> bool:
        """Move nodes to a new parent at the specified position."""
        # Validate the move operation
        if not self._validate_move(nodes, new_parent):
            return False
        
        # Collect nodes with their current positions
        nodes_with_info = self._collect_nodes_with_positions(nodes)
        if not nodes_with_info:
            return False
        
        # Perform the move operation
        return self._perform_move_operation(nodes_with_info, new_parent, insert_row)
    
    def _validate_move(self, nodes: List[SignalNode], new_parent: Optional[SignalNode]) -> bool:
        """Validate that the move operation is allowed."""
        # Prevent moving a node into itself or its descendants
        for node in nodes:
            if new_parent:
                ancestor: Optional[SignalNode] = new_parent
                while ancestor:
                    if ancestor == node:
                        return False
                    ancestor = ancestor.parent
        return True
    
    def _collect_nodes_with_positions(self, nodes: List[SignalNode]) -> List[Tuple[int, Optional[SignalNode], SignalNode]]:
        """Collect nodes with their current positions and parent information."""
        nodes_with_info = []
        for node in nodes:
            if node.parent:
                source_list = node.parent.children
            else:
                source_list = self._session.root_nodes
            
            try:
                current_row = source_list.index(node)
                nodes_with_info.append((current_row, node.parent, node))
            except ValueError:
                continue
        
        # Sort by parent and row to maintain order
        nodes_with_info.sort(key=lambda x: (id(x[1]) if x[1] else 0, x[0]))
        return nodes_with_info
    
    def _perform_move_operation(self, nodes_info: List[Tuple[int, Optional[SignalNode], SignalNode]], 
                               new_parent: Optional[SignalNode], insert_row: int) -> bool:
        """Perform the actual move operation."""
        # Use beginResetModel/endResetModel for simplicity and reliability
        self.beginResetModel()
        
        try:
            # Remove nodes from their current positions
            for _, parent, node in nodes_info:
                if parent:
                    parent.children.remove(node)
                else:
                    self._session.root_nodes.remove(node)
            
            # Get target list
            if new_parent:
                target_list = new_parent.children
            else:
                target_list = self._session.root_nodes
            
            # Insert nodes at new position
            for i, (_, _, node) in enumerate(nodes_info):
                node.parent = new_parent
                if insert_row + i <= len(target_list):
                    target_list.insert(insert_row + i, node)
                else:
                    target_list.append(node)
            
            return True
        except Exception as e:
            print(f"Error in _perform_move_operation: {e}")
            return False
        finally:
            self.endResetModel()
    
    def _find_index_for_node(self, node: SignalNode) -> QModelIndex:
        """Find the QModelIndex for a given node."""
        if not node.parent:
            # Root node
            try:
                row = self._session.root_nodes.index(node)
                return self.createIndex(row, 0, node)
            except ValueError:
                return QModelIndex()
        else:
            # Non-root node
            try:
                row = node.parent.children.index(node)
                parent_index = self._find_index_for_node(node.parent)
                return self.index(row, 0, parent_index)
            except ValueError:
                return QModelIndex()