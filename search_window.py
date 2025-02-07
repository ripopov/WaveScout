#!/usr/bin/env python3
"""
search_window.py

This module defines the SearchWindow class that provides an interface to search
for a timestamp where user-specified signal values match.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton
from vcd_parser import numeric_value, convert_vector

class SearchWindow(QWidget):
    """
    Provides an interface to search for a timestamp where user-defined signal values match.
    Emits a 'timestampFound' signal when a match is located.
    """
    timestampFound = Signal(float)  # Emitted with the found timestamp

    def __init__(self, signals, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Search Window")
        # Ensure this widget remains a top-level window so it stays visible.
        self.setWindowFlags(self.windowFlags() | Qt.Window)
        self.signals = signals
        self.signal_edits = {}  # Map each signal to its input field

        layout = QVBoxLayout(self)
        # Create a row for each signal
        for sig in self.signals:
            row = QHBoxLayout()
            min_val, max_val = self.get_min_max(sig)
            info_text = f" (min: {min_val}, max: {max_val})" if (min_val is not None and max_val is not None) else ""
            label = QLabel(sig.fullname + info_text)
            edit = QLineEdit()
            edit.setPlaceholderText("Enter value (bin, hex, or dec) or leave blank")
            self.signal_edits[sig] = edit
            row.addWidget(label)
            row.addWidget(edit)
            layout.addLayout(row)
        btn = QPushButton("Find")
        btn.clicked.connect(self.find_timestamp)
        layout.addWidget(btn)
        self.result_label = QLabel("")
        layout.addWidget(self.result_label)

    @staticmethod
    def get_min_max(signal):
        """
        Compute the minimum and maximum numeric values from a signal's transitions.
        Returns (min, max) or (None, None) if no transitions exist.
        """
        if not signal.transitions:
            return None, None
        min_val = None
        max_val = None
        for t, v in signal.transitions:
            try:
                num = numeric_value(v)
            except Exception:
                num = 0
            if min_val is None or num < min_val:
                min_val = num
            if max_val is None or num > max_val:
                max_val = num
        return min_val, max_val

    def find_timestamp(self):
        """
        Search for the earliest timestamp where the specified signals match the entered values.
        If a match is found, emit the timestampFound signal; otherwise, update the result label.
        """
        desired = {}
        for sig, edit in self.signal_edits.items():
            txt = edit.text().strip()
            if txt != "":
                desired[sig] = numeric_value(txt)
        if not desired:
            self.result_label.setText("Please enter a value for at least one signal.")
            return

        # Determine the global time range from the signals.
        global_start = None
        global_end = None
        for sig in self.signals:
            if sig.transitions:
                first = sig.transitions[0][0]
                last = sig.transitions[-1][0]
            else:
                first = 0
                last = 0
            if global_start is None or first < global_start:
                global_start = first
            if global_end is None or last > global_end:
                global_end = last
        if global_start is None:
            self.result_label.setText("No transitions to search.")
            return

        # Build candidate timestamps within the global range.
        candidate_times = set()
        for sig in self.signals:
            for t, _ in sig.transitions:
                if global_start <= t <= global_end:
                    candidate_times.add(t)
        candidate_times.add(global_start)
        candidate_list = sorted(candidate_times)

        found_time = None
        for t in candidate_list:
            all_match = True
            for sig, desired_val in desired.items():
                last_val = "0"
                for time_stamp, v in sig.transitions:
                    if time_stamp <= t:
                        last_val = v
                    else:
                        break
                if numeric_value(last_val) != desired_val:
                    all_match = False
                    break
            if all_match:
                found_time = t
                break

        if found_time is not None:
            self.result_label.setText(f"Found at time {found_time}")
            self.timestampFound.emit(found_time)
        else:
            self.result_label.setText("Not found")

