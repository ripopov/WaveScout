"""
Dialogs for snippet save and instantiation operations.
"""

from typing import Optional
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QTextEdit, QLabel, QPushButton,
    QDialogButtonBox, QMessageBox, QWidget
)
from PySide6.QtCore import Qt

from wavescout.data_model import SignalNode
from wavescout.snippet_manager import Snippet, SnippetManager
from wavescout.waveform_db import WaveformDB


class SaveSnippetDialog(QDialog):
    """Dialog for saving a signal group as a snippet."""
    
    def __init__(self, group_node: SignalNode, parent_scope: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.group_node = group_node
        self.parent_scope = parent_scope
        self.snippet_manager = SnippetManager()
        
        self.setWindowTitle("Save as Snippet")
        self.setModal(True)
        self.setMinimumWidth(400)
        
        self._setup_ui()
        self._setup_connections()
    
    def _setup_ui(self) -> None:
        """Setup the dialog UI."""
        layout = QVBoxLayout(self)
        
        # Form layout for fields
        form_layout = QFormLayout()
        
        # Name field
        self.name_edit = QLineEdit(self.group_node.name)
        self.name_edit.selectAll()
        form_layout.addRow("Snippet Name:", self.name_edit)
        
        # Parent scope (read-only)
        self.parent_label = QLabel(self.parent_scope)
        form_layout.addRow("Parent Scope:", self.parent_label)
        
        # Node count (read-only)
        node_count = self._count_nodes(self.group_node)
        self.count_label = QLabel(str(node_count))
        form_layout.addRow("Signal Count:", self.count_label)
        
        # Description field
        self.description_edit = QTextEdit()
        self.description_edit.setPlaceholderText("Optional description...")
        self.description_edit.setMaximumHeight(80)
        form_layout.addRow("Description:", self.description_edit)
        
        layout.addLayout(form_layout)
        
        # Buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | 
            QDialogButtonBox.StandardButton.Cancel
        )
        layout.addWidget(self.button_box)
    
    def _setup_connections(self) -> None:
        """Setup signal connections."""
        self.button_box.accepted.connect(self._on_save)
        self.button_box.rejected.connect(self.reject)
        self.name_edit.textChanged.connect(self._validate_name)
    
    def _count_nodes(self, node: SignalNode) -> int:
        """Count total nodes in tree."""
        count = 0 if node.is_group else 1
        for child in node.children:
            count += self._count_nodes(child)
        return count
    
    def _validate_name(self, text: str) -> None:
        """Validate snippet name."""
        save_button = self.button_box.button(QDialogButtonBox.StandardButton.Save)
        
        if not text:
            save_button.setEnabled(False)
            return
        
        # Check for invalid characters
        invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
        if any(char in text for char in invalid_chars):
            save_button.setEnabled(False)
            self.name_edit.setStyleSheet("QLineEdit { color: red; }")
            return
        
        # Check if name already exists
        if self.snippet_manager.snippet_exists(text):
            save_button.setEnabled(False)
            self.name_edit.setStyleSheet("QLineEdit { color: orange; }")
            self.name_edit.setToolTip("A snippet with this name already exists")
        else:
            save_button.setEnabled(True)
            self.name_edit.setStyleSheet("")
            self.name_edit.setToolTip("")
    
    def _on_save(self) -> None:
        """Handle save button click."""
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Invalid Name", "Please enter a snippet name.")
            return
        
        # Create snippet
        snippet = Snippet(
            name=name,
            parent_name=self.parent_scope,
            num_nodes=self._count_nodes(self.group_node),
            nodes=self.group_node.children,  # Save children, not the group itself
            description=self.description_edit.toPlainText()
        )
        
        # Save snippet
        if self.snippet_manager.save_snippet(snippet):
            self.accept()
        else:
            QMessageBox.critical(self, "Save Failed", "Failed to save snippet.")


class InstantiateSnippetDialog(QDialog):
    """Dialog for instantiating a snippet with scope remapping."""
    
    def __init__(self, snippet: Snippet, waveform_db: Optional[WaveformDB], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.snippet = snippet
        self.waveform_db = waveform_db
        self.remapped_nodes: Optional[list[SignalNode]] = None
        self.group_name: str = snippet.name  # Default to snippet name
        
        self.setWindowTitle(f"Instantiate Snippet: {snippet.name}")
        self.setModal(True)
        self.setMinimumWidth(500)
        
        self._setup_ui()
        self._setup_connections()
        self._validate_scope()
    
    def _setup_ui(self) -> None:
        """Setup the dialog UI."""
        layout = QVBoxLayout(self)
        
        # Info section
        info_layout = QFormLayout()
        info_layout.addRow("Snippet:", QLabel(self.snippet.name))
        info_layout.addRow("Original Scope:", QLabel(self.snippet.parent_name))
        info_layout.addRow("Signal Count:", QLabel(str(self.snippet.num_nodes)))
        
        if self.snippet.description:
            desc_label = QLabel(self.snippet.description)
            desc_label.setWordWrap(True)
            info_layout.addRow("Description:", desc_label)
        
        layout.addLayout(info_layout)
        
        # Separator
        layout.addSpacing(10)
        
        # Instantiation options
        form_layout = QFormLayout()
        
        # Group name input (editable)
        self.group_name_edit = QLineEdit(self.snippet.name)
        self.group_name_edit.setToolTip("Name for the group that will contain the instantiated signals")
        form_layout.addRow("Group Name:", self.group_name_edit)
        
        # Target scope input
        self.scope_edit = QLineEdit(self.snippet.parent_name)
        self.scope_edit.selectAll()
        form_layout.addRow("Target Scope:", self.scope_edit)
        
        # Validation feedback
        self.validation_label = QLabel()
        self.validation_label.setWordWrap(True)
        form_layout.addRow("", self.validation_label)
        
        layout.addLayout(form_layout)
        
        # Preview section
        self.preview_label = QLabel("Signals to be created:")
        layout.addWidget(self.preview_label)
        
        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setMaximumHeight(150)
        layout.addWidget(self.preview_text)
        
        # Buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | 
            QDialogButtonBox.StandardButton.Cancel
        )
        self.ok_button = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
        layout.addWidget(self.button_box)
    
    def _setup_connections(self) -> None:
        """Setup signal connections."""
        self.button_box.accepted.connect(self._on_accept)
        self.button_box.rejected.connect(self.reject)
        self.scope_edit.textChanged.connect(self._on_scope_changed)
        self.group_name_edit.textChanged.connect(self._on_group_name_changed)
    
    def _on_scope_changed(self) -> None:
        """Handle scope text change."""
        self._validate_scope()
    
    def _on_group_name_changed(self, text: str) -> None:
        """Handle group name change."""
        self.group_name = text.strip()
        # Validate that group name is not empty
        if not self.group_name:
            self.ok_button.setEnabled(False)
        else:
            # Re-validate scope to update OK button state
            self._validate_scope()
    
    def _on_accept(self) -> None:
        """Handle accept button - store the group name before accepting."""
        self.group_name = self.group_name_edit.text().strip()
        if not self.group_name:
            QMessageBox.warning(self, "Invalid Group Name", "Please enter a group name.")
            return
        self.accept()
    
    def _validate_scope(self) -> None:
        """Validate the target scope and preview remapped signals."""
        target_scope = self.scope_edit.text().strip()
        group_name = self.group_name_edit.text().strip()
        
        # Check group name first
        if not group_name:
            self.validation_label.setText("❌ Please enter a group name")
            self.validation_label.setStyleSheet("QLabel { color: red; }")
            self.ok_button.setEnabled(False)
            return
        
        if not self.waveform_db:
            self.validation_label.setText("⚠ No waveform loaded")
            self.validation_label.setStyleSheet("QLabel { color: orange; }")
            self.ok_button.setEnabled(False)
            return
        
        if not target_scope:
            self.validation_label.setText("❌ Please enter a target scope")
            self.validation_label.setStyleSheet("QLabel { color: red; }")
            self.ok_button.setEnabled(False)
            return
        
        # Try to remap and validate
        try:
            self.remapped_nodes = self._remap_and_validate(target_scope)
            
            # Update preview
            preview_lines = []
            for node in self._get_all_signals(self.remapped_nodes):
                preview_lines.append(f"  {node.name}")
            
            self.preview_text.setPlainText("\n".join(preview_lines[:20]))  # Limit preview
            if len(preview_lines) > 20:
                self.preview_text.append(f"\n  ... and {len(preview_lines) - 20} more")
            
            self.validation_label.setText("✓ All signals found in target scope")
            self.validation_label.setStyleSheet("QLabel { color: green; }")
            self.ok_button.setEnabled(True)
            
        except Exception as e:
            self.validation_label.setText(f"❌ {str(e)}")
            self.validation_label.setStyleSheet("QLabel { color: red; }")
            self.preview_text.clear()
            self.ok_button.setEnabled(False)
            self.remapped_nodes = None
    
    def _remap_and_validate(self, new_parent_scope: str) -> list[SignalNode]:
        """Remap snippet nodes to new scope and validate they exist."""
        if not self.waveform_db:
            raise ValueError("No waveform database available")
        
        old_parent = self.snippet.parent_name
        remapped_nodes: list[SignalNode] = []
        
        def remap_node(node: SignalNode) -> SignalNode:
            new_node = node.deep_copy()
            
            if not node.is_group:
                # Calculate relative name
                if old_parent and node.name.startswith(old_parent + "."):
                    relative_name = node.name[len(old_parent) + 1:]
                elif not old_parent:
                    relative_name = node.name
                else:
                    # Handle case where node name doesn't start with parent
                    relative_name = node.name.split('.')[-1]
                
                # Build new name
                if new_parent_scope:
                    new_name = f"{new_parent_scope}.{relative_name}"
                else:
                    new_name = relative_name
                
                # Resolve handle from waveform database
                if self.waveform_db:
                    handle = self.waveform_db.find_handle_by_path(new_name)
                    if handle is None:
                        raise ValueError(f"Signal '{new_name}' not found in waveform")
                else:
                    raise ValueError("No waveform database available")
                
                new_node.name = new_name
                new_node.handle = handle
            
            # Recursively remap children
            new_node.children = [remap_node(child) for child in node.children]
            for child in new_node.children:
                child.parent = new_node
            
            return new_node
        
        for node in self.snippet.nodes:
            remapped_nodes.append(remap_node(node))
        
        return remapped_nodes
    
    def _get_all_signals(self, nodes: list[SignalNode]) -> list[SignalNode]:
        """Get all non-group signals from node list."""
        signals: list[SignalNode] = []
        
        def collect_signals(node: SignalNode) -> None:
            if not node.is_group:
                signals.append(node)
            for child in node.children:
                collect_signals(child)
        
        for node in nodes:
            collect_signals(node)
        
        return signals
    
    def get_remapped_nodes(self) -> Optional[list[SignalNode]]:
        """Get the remapped nodes if validation succeeded."""
        return self.remapped_nodes
    
    def get_group_name(self) -> str:
        """Get the user-specified group name."""
        return self.group_name