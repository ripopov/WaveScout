"""
Variables view widget for split mode in DesignTreeView.

This widget displays variables in a table format with filtering support.
"""

from typing import Optional, List, Dict, Any, Union
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTableView, QLineEdit,
    QAbstractItemView, QHeaderView
)
from PySide6.QtCore import (
    Qt, QAbstractTableModel, QModelIndex, QPersistentModelIndex,
    QSortFilterProxyModel, Signal, QTimer
)
from PySide6.QtGui import QKeySequence


class VarsModel(QAbstractTableModel):
    """Table model for displaying variables with Name, Type, and Bit Range columns."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.variables: List[Dict[str, Any]] = []
        self.columns = ["Name", "Type", "Bit Range"]
    
    def set_variables(self, variables: List[Dict[str, Any]]):
        """Set the list of variables to display."""
        self.beginResetModel()
        self.variables = variables
        self.endResetModel()
    
    def rowCount(self, parent: Union[QModelIndex, QPersistentModelIndex] = QModelIndex()) -> int:
        """Return the number of variables."""
        if parent.isValid():
            return 0
        return len(self.variables)
    
    def columnCount(self, parent: Union[QModelIndex, QPersistentModelIndex] = QModelIndex()) -> int:
        """Return the number of columns."""
        if parent.isValid():
            return 0
        return len(self.columns)
    
    def data(self, index: Union[QModelIndex, QPersistentModelIndex], role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        """Get data for the given index and role."""
        if not index.isValid() or index.row() >= len(self.variables):
            return None
        
        var = self.variables[index.row()]
        col = index.column()
        
        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:  # Name
                return var.get('name', '')
            elif col == 1:  # Type
                return var.get('var_type', '')
            elif col == 2:  # Bit Range
                return var.get('bit_range', '')
        elif role == Qt.ItemDataRole.ToolTipRole:
            # Show full path in tooltip
            return var.get('full_path', var.get('name', ''))
        elif role == Qt.ItemDataRole.UserRole:
            # Return the full variable info for signal creation
            return var
        
        return None
    
    def headerData(self, section: int, orientation: Qt.Orientation,
                   role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        """Get header data."""
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            if 0 <= section < len(self.columns):
                return self.columns[section]
        return None
    
    def flags(self, index: Union[QModelIndex, QPersistentModelIndex]) -> Qt.ItemFlag:
        """Get item flags."""
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable


class FuzzyFilterProxyModel(QSortFilterProxyModel):
    """Proxy model implementing fuzzy filtering for variables using rapidfuzz."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.filter_text = ""
        self.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.score_threshold = 50  # Minimum score to show results (lowered for partial_ratio)
        
        # Import rapidfuzz (mandatory dependency)
        from rapidfuzz import fuzz
        self.fuzz = fuzz
    
    def set_filter_text(self, text: str):
        """Set the filter text and invalidate the filter."""
        self.filter_text = text.lower()
        self.invalidateFilter()
    
    def filterAcceptsRow(self, source_row: int, source_parent: Union[QModelIndex, QPersistentModelIndex]) -> bool:
        """Determine if a row should be shown based on fuzzy filter."""
        if not self.filter_text:
            return True
        
        # Get the variable name from the source model
        source_model = self.sourceModel()
        if not source_model:
            return True
            
        name_index = source_model.index(source_row, 0, source_parent)
        name = source_model.data(name_index, Qt.ItemDataRole.DisplayRole)
        
        if not name:
            return False
        
        # First check if all characters in filter appear in order (subsequence matching)
        name_lower = name.lower()
        filter_chars = list(self.filter_text)
        
        pos = 0
        for char in filter_chars:
            pos = name_lower.find(char, pos)
            if pos == -1:
                return False
            pos += 1
        
        # If subsequence check passes, use rapidfuzz for scoring/ranking
        # This ensures we only show results where characters appear in order
        # but still get good fuzzy scoring for ranking
        score = self.fuzz.partial_ratio(self.filter_text, name_lower)
        return score >= self.score_threshold


class VarsView(QWidget):
    """Widget containing the variables table and filter input."""
    
    # Signal emitted when variables are selected for addition
    variables_selected = Signal(list)  # List of variable dictionaries
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self._setup_ui()
        self._setup_connections()
        
        # Debounce timer for filter input
        self.filter_timer = QTimer()
        self.filter_timer.setSingleShot(True)
        self.filter_timer.timeout.connect(self._apply_filter)
    
    def _setup_ui(self):
        """Create the UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Filter input
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Filter variables... (Ctrl+F)")
        layout.addWidget(self.filter_input)
        
        # Variables table
        self.table_view = QTableView()
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_view.setSortingEnabled(False)
        
        # Create models
        self.vars_model = VarsModel()
        self.filter_proxy = FuzzyFilterProxyModel()
        self.filter_proxy.setSourceModel(self.vars_model)
        
        # Set model
        self.table_view.setModel(self.filter_proxy)
        
        # Configure column widths
        header = self.table_view.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)  # Name column stretches
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # Type column
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)  # Bit Range column
        
        layout.addWidget(self.table_view)
    
    def _setup_connections(self):
        """Connect signals and slots."""
        self.filter_input.textChanged.connect(self._on_filter_changed)
        self.table_view.doubleClicked.connect(self._on_double_click)
    
    def _on_filter_changed(self, text: str):
        """Handle filter text change with debouncing."""
        self.filter_timer.stop()
        self.filter_timer.start(200)  # 200ms debounce
    
    def _apply_filter(self):
        """Apply the filter to the proxy model."""
        self.filter_proxy.set_filter_text(self.filter_input.text())
    
    def _on_double_click(self, index: QModelIndex):
        """Handle double-click on a variable."""
        if not index.isValid():
            return
        
        # Get the source index
        source_index = self.filter_proxy.mapToSource(index)
        if not source_index.isValid():
            return
        
        # Get variable data
        var_data = self.vars_model.data(
            self.vars_model.index(source_index.row(), 0),
            Qt.ItemDataRole.UserRole
        )
        
        if var_data:
            self.variables_selected.emit([var_data])
    
    def set_variables(self, variables: List[Dict[str, Any]]):
        """Set the variables to display."""
        self.vars_model.set_variables(variables)
        self.filter_input.clear()
    
    def get_selected_variables(self) -> List[Dict[str, Any]]:
        """Get the currently selected variables."""
        selected: List[Dict[str, Any]] = []
        selection = self.table_view.selectionModel()
        
        if not selection:
            return selected
        
        for proxy_index in selection.selectedRows():
            source_index = self.filter_proxy.mapToSource(proxy_index)
            if source_index.isValid():
                var_data = self.vars_model.data(
                    self.vars_model.index(source_index.row(), 0),
                    Qt.ItemDataRole.UserRole
                )
                if var_data:
                    selected.append(var_data)
        
        return selected
    
    def clear_filter(self):
        """Clear the filter input."""
        self.filter_input.clear()
    
    def focus_filter(self):
        """Set focus to the filter input."""
        self.filter_input.setFocus()
        self.filter_input.selectAll()