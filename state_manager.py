#!/usr/bin/env python3
"""
state_manager.py

This module defines the StateManager class which is responsible for
saving and loading the application state to/from a JSON file.
"""

import json
from PySide6.QtCore import QObject

class StateManager(QObject):
    """
    Handles saving and loading of the application state to and from a JSON file.
    """
    def __init__(self, parent=None):
        super().__init__(parent)

    def save_state(self, state, filename):
        """Save the given state dictionary as a JSON file."""
        try:
            with open(filename, "w") as f:
                json.dump(state, f, indent=4)
        except Exception as e:
            print("Error saving state:", e)

    def load_state(self, filename):
        """Load and return the application state from a JSON file."""
        try:
            with open(filename, "r") as f:
                return json.load(f)
        except Exception as e:
            print("Error loading state:", e)
            return None
