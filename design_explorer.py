#!/usr/bin/env python3
"""
design_explorer.py

Compound widget that groups the design tree and signal filter controls.
Provides an isolated signal–slot interface for design tree exploration.
"""

import fnmatch

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QTreeWidgetItem
)
from PySide6.QtGui import QFont, QColor
from PySide6.QtWidgets import QTreeWidget, QAbstractItemView
from PySide6.QtCore import Signal


class DesignTree(QTreeWidget):
    signalsToAdd = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.signal_map = {}  # Map tree items to their corresponding signals

    def keyPressEvent(self, event):
        """
        Intercept key presses: if the 'i' key is pressed, emit the selected signals.
        Otherwise, proceed with default behavior.
        """
        if event.text().lower() == "i":
            selected = self.selectedItems()
            sigs = []
            for item in selected:
                if item in self.signal_map:
                    sigs.append(self.signal_map[item])
            if sigs:
                self.signalsToAdd.emit(sigs)
        else:
            super().keyPressEvent(event)


class DesignExplorer(QWidget):
    """
    DesignExplorer groups the signal filter and design tree into a single widget.
    It exposes a signalsToAdd signal (forwarded from its DesignTree) so that when
    the user selects (or double-clicks) signals, the parent can add them to the waveform panel.

    All selection (including shift/ctrl-click and double-click) remains handled
    by the DesignTree.
    """
    signalsToAdd = Signal(list)  # Emitted with a list of signals to add

    def __init__(self, parent=None):
        super().__init__(parent)
        self.hierarchy = None  # This will be set later using set_hierarchy()
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # Top label
        label = QLabel("DesignTree")
        label.setFont(QFont("Arial", 12, QFont.Bold))
        layout.addWidget(label)

        # Signal filter: label and QLineEdit in a horizontal layout
        filter_layout = QHBoxLayout()
        filter_label = QLabel("Signal Filter:")
        self.filter_entry = QLineEdit()
        filter_layout.addWidget(filter_label)
        filter_layout.addWidget(self.filter_entry)
        layout.addLayout(filter_layout)

        # Create the DesignTree widget (which already implements selection, hotkeys, etc.)
        self.tree = DesignTree()
        layout.addWidget(self.tree)

        # Rebuild the tree whenever the filter text changes.
        self.filter_entry.textChanged.connect(self.rebuild_tree)

        # Forward the inner tree’s signalsToAdd signal.
        self.tree.signalsToAdd.connect(self.signalsToAdd.emit)

    def set_hierarchy(self, hierarchy):
        """
        Set the signal hierarchy (as produced by your VCD parser) and rebuild the tree.
        """
        self.hierarchy = hierarchy
        self.rebuild_tree()

    def rebuild_tree(self):
        """
        Rebuild the design tree based on the current filter text and the hierarchy.
        """
        if self.hierarchy is None:
            return
        pattern = self.filter_entry.text().strip()
        self.tree.clear()
        if hasattr(self.tree, 'signal_map'):
            self.tree.signal_map.clear()
        self._build_filtered_tree(None, self.hierarchy, pattern)

    def _build_filtered_tree(self, parent_item, tree_dict, pattern):
        """
        Recursively build the design tree.
        (This code is largely adapted from your original _build_filtered_tree method.)
        """
        for key, subtree in tree_dict.items():
            if key == "_signal":
                continue

            # Leaf node: a node with only a '_signal' key.
            if set(subtree.keys()) == {"_signal"}:
                signal = subtree["_signal"]
                if not pattern or fnmatch.fnmatch(signal.name, f"*{pattern}*"):
                    if parent_item is None:
                        leaf = QTreeWidgetItem(self.tree, [signal.name])
                    else:
                        leaf = QTreeWidgetItem(parent_item, [signal.name])
                    if hasattr(self.tree, 'signal_map'):
                        self.tree.signal_map[leaf] = signal
                    # Colorize based on dynamic behavior
                    if self._is_dynamic(signal):
                        leaf.setForeground(0, QColor("red"))
                    else:
                        leaf.setForeground(0, QColor("gray"))
            else:
                # Internal node: create a branch.
                if parent_item is None:
                    node = QTreeWidgetItem(self.tree, [key])
                else:
                    node = QTreeWidgetItem(parent_item, [key])
                node.setExpanded(True)
                self._build_filtered_tree(node, subtree, pattern)

    def _is_dynamic(self, signal):
        """
        Returns True if the signal has multiple transition values.
        """
        if not signal.transitions:
            return False
        return len({v for _, v in signal.transitions}) > 1
