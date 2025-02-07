#!/usr/bin/env python3
"""
design_tree.py

This module defines the DesignTree class, a custom QTreeWidget
that displays the signal hierarchy and emits a signal when the 'i'
key is pressed on a selection.
"""

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
