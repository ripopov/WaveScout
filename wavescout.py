#!/usr/bin/env python3
import sys
import re
import fnmatch
import json
from math import ceil
from datetime import datetime  # used for date stamp in dumped file

from PySide6.QtCore import Qt, QRectF, QPoint, QEvent, Signal
from PySide6.QtGui import QPainter, QPen, QBrush, QColor, QFont, QFontMetrics, QAction, QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                               QPushButton, QLabel, QLineEdit, QSplitter, QMenu, QAbstractItemView,
                               QTreeWidget, QTreeWidgetItem, QFileDialog, QScrollArea)

# ---------------------------
# VCD Data Classes and Parser
# ---------------------------
class VCDSignal:
    def __init__(self, identifier, name, hierarchy, width=1):
        self.id = identifier               # VCD signal identifier (e.g. "!")
        self.name = name                   # The declared signal name (e.g. "BinCount" or "ext.COPY_ENGINE_READ_REQUEST")
        self.hierarchy = hierarchy[:]      # List of scopes leading to the signal
        self.fullname = '.'.join(hierarchy + [name])
        self.width = width                 # Bit width of the signal
        self.transitions = []              # List of (time, value) tuples
        self.aliases = [self.fullname]     # List of full names (aliases)
        # Custom attributes:
        self.height_factor = 1             # Per-signal height factor (1 = normal, 2 = twice, etc.)
        self.rep_mode = "hex"              # Representation mode used for value pane: "hex", "bin", "decimal"
        # New toggle for wave pane drawing: if True, draw using Analog Step method.
        self.analog_render = False

class VCDParser:
    def __init__(self, filename):
        self.filename = filename
        self.signals = {}      # Mapping from var-id to VCDSignal
        self.hierarchy = {}    # Nested dictionary for design explorer
        self.timescale = None
        self.metadata = {}     # Optionally store $date, $version, etc.

    def parse(self):
        # Helper to normalize dumped values: replace any 'x' or 'X' with '0'.
        def normalize_value(val):
            return ''.join('0' if c in 'xX' else c for c in val)

        try:
            with open(self.filename, "r") as f:
                current_scope = []
                in_header = True
                current_time = 0
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    if in_header:
                        if line.startswith("$timescale"):
                            tokens = []
                            parts = line.split()
                            if len(parts) > 1:
                                tokens.extend(parts[1:])
                            while "$end" not in line:
                                line = f.readline().strip()
                                if "$end" in line:
                                    break
                                tokens.extend(line.split())
                            self.timescale = tokens[0] if tokens else "unknown"
                        elif line.startswith("$date"):
                            date_info = []
                            while "$end" not in line:
                                line = f.readline().strip()
                                if "$end" in line:
                                    break
                                date_info.append(line)
                            self.metadata["date"] = ' '.join(date_info)
                        elif line.startswith("$version"):
                            version_info = []
                            while "$end" not in line:
                                line = f.readline().strip()
                                if "$end" in line:
                                    break
                                version_info.append(line)
                            self.metadata["version"] = ' '.join(version_info)
                        elif line.startswith("$scope"):
                            parts = line.split()
                            if len(parts) >= 3:
                                current_scope.append(parts[2])
                        elif line.startswith("$upscope"):
                            if current_scope:
                                current_scope.pop()
                        elif line.startswith("$var"):
                            parts = line.split()
                            if len(parts) >= 6:
                                var_id = parts[3]
                                try:
                                    end_index = parts.index("$end")
                                except ValueError:
                                    end_index = len(parts)
                                var_name = ' '.join(parts[4:end_index])
                                try:
                                    width = int(parts[2])
                                except ValueError:
                                    width = 1
                                # --- If the variable name contains a dot and there is a scope,
                                #     use only the top-level scope and leave the var_name intact.
                                if current_scope and '.' in var_name:
                                    new_fullname = current_scope[0] + '.' + var_name
                                elif current_scope:
                                    new_fullname = '.'.join(current_scope + [var_name])
                                else:
                                    new_fullname = var_name
                                # Create or update the signal.
                                if var_id in self.signals:
                                    existing_signal = self.signals[var_id]
                                    if new_fullname not in existing_signal.aliases:
                                        existing_signal.aliases.append(new_fullname)
                                    self._insert_into_hierarchy(new_fullname, existing_signal)
                                else:
                                    signal = VCDSignal(var_id, var_name, current_scope, width)
                                    # Overwrite fullname if modified.
                                    signal.fullname = new_fullname
                                    self.signals[var_id] = signal
                                    self._insert_into_hierarchy(signal.fullname, signal)
                        elif line.startswith("$enddefinitions"):
                            in_header = False
                    else:
                        if line.startswith("#"):
                            try:
                                current_time = int(line[1:])
                            except ValueError:
                                current_time = 0
                        else:
                            if line.startswith("b"):
                                m = re.match(r"b([01xz]+)\s+(\S+)", line)
                                if m:
                                    value, sig_id = m.groups()
                                    # Normalize the value (replace any x/X with 0)
                                    value = normalize_value(value)
                                    if sig_id in self.signals:
                                        self.signals[sig_id].transitions.append((current_time, value))
                            else:
                                sig_id = line[1:]
                                value = line[0]
                                # Normalize the single-character value.
                                value = '0' if value in 'xX' else value
                                if sig_id in self.signals:
                                    self.signals[sig_id].transitions.append((current_time, value))
            for sig in self.signals.values():
                sig.transitions.sort(key=lambda t: t[0])
            return self.timescale
        except FileNotFoundError:
            print(f"VCD file not found: {self.filename}. Running without loading any signals.")
            self.hierarchy = {}
            return None

    def _insert_into_hierarchy(self, fullname, signal):
        # If the signal's declared name contains a dot (and there is a scope),
        # then do not split the var_name further.
        if signal.hierarchy and '.' in signal.name:
            parts = [signal.hierarchy[0], signal.name]
        else:
            parts = fullname.split(".")
        subtree = self.hierarchy
        for part in parts:
            if part not in subtree:
                subtree[part] = {}
            subtree = subtree[part]
        subtree["_signal"] = signal

def convert_vector(value, width, mode):
    """Convert a binary string value into a string using the given mode.
       For value display, mode is one of 'hex', 'bin', or 'decimal'."""
    if set(value) <= {'0', '1'}:
        if mode == "hex":
            digits = ceil(width / 4)
            return f"0x{int(value, 2):0{digits}X}"
        elif mode == "bin":
            return "0b" + value
        elif mode == "decimal":
            return str(int(value, 2))
    return value.upper()

def numeric_value(v):
    try:
        if set(v) <= {'0', '1'}:
            return int(v, 2)
        elif v.startswith("0x"):
            return int(v, 16)
        else:
            return float(v)
    except (ValueError, TypeError):
        return 0.0


# ---------------------------
# SearchWindow: a new window to search for a timestamp where all selected signals have desired values.
# ---------------------------
class SearchWindow(QWidget):
    def __init__(self, signals, main_window):
        super().__init__()
        self.setWindowTitle("Search Window")
        self.signals = signals
        self.main_window = main_window  # Expected to have a 'wave_panel'
        self.signal_edits = {}  # Mapping: signal -> QLineEdit for search value

        layout = QVBoxLayout(self)
        # Create one row per selected signal.
        for sig in self.signals:
            row = QHBoxLayout()
            # Compute min and max numeric values for the signal.
            min_val, max_val = self.get_min_max(sig)
            if min_val is not None and max_val is not None:
                info_text = f" (min: {min_val}, max: {max_val})"
            else:
                info_text = ""
            # Append min/max info to the signal's fullname.
            label = QLabel(sig.fullname + info_text)
            edit = QLineEdit()
            edit.setPlaceholderText("Enter value (bin, hex, or dec) or leave blank")
            self.signal_edits[sig] = edit
            row.addWidget(label)
            row.addWidget(edit)
            layout.addLayout(row)
        # Button row:
        btn = QPushButton("Find")
        btn.clicked.connect(self.find_timestamp)
        layout.addWidget(btn)
        # Label to display result (e.g. "Not found")
        self.result_label = QLabel("")
        layout.addWidget(self.result_label)

    @staticmethod
    def get_min_max(signal):
        """Compute the minimum and maximum numeric values among the signal's transitions.
           Returns a tuple (min_val, max_val) or (None, None) if there are no transitions."""
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
        # Build a dictionary mapping signals to the desired numeric value,
        # but ignore those signals with empty input.
        desired = {}
        for sig, edit in self.signal_edits.items():
            txt = edit.text().strip()
            if txt != "":
                desired[sig] = numeric_value(txt)
        if not desired:
            self.result_label.setText("Please enter a value for at least one signal.")
            return

        # Get global start and end times (from all selected signals)
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

        # Build a sorted set of candidate timestamps (the union of all transitions)
        candidate_times = set()
        for sig in self.signals:
            for t, _ in sig.transitions:
                if global_start <= t <= global_end:
                    candidate_times.add(t)
        candidate_times.add(global_start)
        candidate_list = sorted(candidate_times)

        # Search for a timestamp where each signal with a specified desired value matches.
        found_time = None
        for t in candidate_list:
            all_match = True
            for sig, desired_val in desired.items():
                # Get the last transition value at time t.
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
            # Adjust the main window’s WaveformPanel so that the found time is visible.
            wave_view = self.main_window.wave_panel.wave_view
            current_window = wave_view.end_time - wave_view.start_time
            # Set new start_time so that found_time is at the left edge.
            wave_view.start_time = found_time
            wave_view.end_time = found_time + current_window
            wave_view.cursor_time = found_time  # Place red cursor at found timestamp.
            wave_view.update()
            self.main_window.wave_panel.update_values()
        else:
            self.result_label.setText("Not found")

# ---------------------------
# DesignTree: subclass of QTreeWidget with multi-selection and custom key handler.
# ---------------------------
class DesignTree(QTreeWidget):
    signalsToAdd = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.signal_map = {}

    def keyPressEvent(self, event):
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

# ---------------------------
# WaveformView: custom drawing area for waveforms.
# ---------------------------
class WaveformView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.signals = []
        self.start_time = 0
        self.end_time = 200
        self.zoom_factor = 1.0

        self.signal_height = 30
        self.left_margin = 0
        self.top_margin = 30  # Reserved for timeline header.
        self.text_font = QFont("Courier", 10)
        self.value_font = QFont("Courier", 10, QFont.Weight.Bold)
        self.cursor_time = None
        self.highlighted_signal = None

        self.marker_A = None
        self.marker_B = None

        self.selection_start_x = None
        self.selection_end_x = None
        self.selection_threshold = 10

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        painter.fillRect(self.rect(), QColor("black"))
        drawing_width = self.width()
        drawing_height = self.height()

        # Draw timeline header.
        painter.setPen(QPen(Qt.GlobalColor.white))
        painter.drawLine(0, self.top_margin, drawing_width, self.top_margin)
        start_str = f"{self.start_time:.2f}"
        end_str = f"{self.end_time:.2f}"
        painter.drawText(5, self.top_margin - 5, start_str)
        fm = QFontMetrics(self.text_font)
        end_text_width = fm.horizontalAdvance(end_str)
        painter.drawText(drawing_width - end_text_width - 5, self.top_margin - 5, end_str)

        time_span = self.end_time - self.start_time
        pixels_per_time = drawing_width / time_span if time_span else 1

        if self.selection_start_x is not None and self.selection_end_x is not None:
            x1 = min(self.selection_start_x, self.selection_end_x)
            x2 = max(self.selection_start_x, self.selection_end_x)
            selection_rect = QRectF(x1, self.top_margin, x2 - x1, drawing_height - self.top_margin)
            painter.fillRect(selection_rect, QBrush(QColor(0, 0, 255, 100)))

        y = self.top_margin + 20
        for signal in self.signals:
            effective_height = self.signal_height * signal.height_factor
            if self.highlighted_signal == signal:
                painter.setPen(QPen(QColor("darkblue"), 1))
                painter.drawRect(0, y, drawing_width, effective_height)
            # For signals wider than one bit, use analog step drawing if analog_render is True.
            if signal.width > 1:
                if signal.analog_render:
                    self._draw_analog_step(painter, signal, y, effective_height, drawing_width, pixels_per_time)
                else:
                    self._draw_vector_signal_custom(painter, signal, y, effective_height, drawing_width, pixels_per_time)
            else:
                self._draw_signal_custom(painter, signal, y, effective_height, drawing_width, pixels_per_time)
            y += effective_height

        if self.cursor_time is not None:
            cursor_x = (self.cursor_time - self.start_time) * pixels_per_time
            pen = QPen(Qt.GlobalColor.red, 1, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.drawLine(cursor_x, self.top_margin, cursor_x, drawing_height)

        if self.marker_A is not None and self.start_time <= self.marker_A <= self.end_time:
            xA = (self.marker_A - self.start_time) * pixels_per_time
            painter.setPen(QPen(Qt.GlobalColor.yellow, 1))
            painter.drawLine(xA, self.top_margin, xA, drawing_height)
            label_rect = QRectF(xA - 15, 0, 30, self.top_margin)
            painter.drawText(label_rect, Qt.AlignmentFlag.AlignCenter, "A")

        if self.marker_B is not None and self.start_time <= self.marker_B <= self.end_time:
            xB = (self.marker_B - self.start_time) * pixels_per_time
            painter.setPen(QPen(Qt.GlobalColor.yellow, 1))
            painter.drawLine(xB, self.top_margin, xB, drawing_height)
            label_rect = QRectF(xB - 15, 0, 30, self.top_margin)
            painter.drawText(label_rect, Qt.AlignmentFlag.AlignCenter, "B")

        # Draw global start and end markers thicker if we are at the border.
        global_min, global_max = self._get_global_range()
        if global_min is not None and global_max is not None:
            # If the view is at the start of the waveform, draw a thick marker at x=0.
            if self.start_time == global_min:
                painter.setPen(QPen(Qt.GlobalColor.red, 3))
                painter.drawLine(0, self.top_margin, 0, drawing_height)
            elif self.start_time < global_min < self.end_time:
                x_global_min = (global_min - self.start_time) * pixels_per_time
                painter.setPen(QPen(Qt.GlobalColor.red, 1))
                painter.drawLine(x_global_min, self.top_margin, x_global_min, drawing_height)
            # Similarly, if the view is at the end of the waveform, draw a thick marker at the right edge.
            if self.end_time == global_max:
                painter.setPen(QPen(Qt.GlobalColor.red, 3))
                painter.drawLine(drawing_width, self.top_margin, drawing_width, drawing_height)
            elif self.start_time < global_max < self.end_time:
                x_global_max = (global_max - self.start_time) * pixels_per_time
                painter.setPen(QPen(Qt.GlobalColor.red, 1))
                painter.drawLine(x_global_max, self.top_margin, x_global_max, drawing_height)
        painter.end()

    def _get_global_range(self):
        global_min = None
        global_max = None
        for s in self.signals:
            if s.transitions:
                t0 = s.transitions[0][0]
                t1 = s.transitions[-1][0]
                if global_min is None or t0 < global_min:
                    global_min = t0
                if global_max is None or t1 > global_max:
                    global_max = t1
        return global_min, global_max

    def _value_to_y(self, val, base_y, effective_height):
        if val in ("1", "b1", "true"):
            return base_y + 5
        else:
            return base_y + effective_height - 5

    def _draw_signal_custom(self, painter, signal, base_y, effective_height, drawing_width, pixels_per_time):
        transitions = signal.transitions
        if not transitions:
            return
        last_val = None
        for t, v in transitions:
            if t < self.start_time:
                last_val = v
            else:
                break
        if last_val is None:
            last_val = "0"
        prev_x = 0
        prev_y = self._value_to_y(last_val, base_y, effective_height)
        for t, val in transitions:
            if t < self.start_time or t > self.end_time:
                continue
            x = (t - self.start_time) * pixels_per_time
            if last_val == "1":
                painter.setPen(QPen(QColor("cyan"), 1))
            else:
                painter.setPen(QPen(QColor("lime"), 1))
            painter.drawLine(prev_x, prev_y, x, prev_y)
            painter.setPen(QPen(QColor("lime"), 1))
            new_y = self._value_to_y(val, base_y, effective_height)
            painter.drawLine(x, prev_y, x, new_y)
            prev_x = x
            prev_y = new_y
            last_val = val
        if last_val == "1":
            painter.setPen(QPen(QColor("cyan"), 1))
        else:
            painter.setPen(QPen(QColor("lime"), 1))
        painter.drawLine(prev_x, prev_y, drawing_width, prev_y)

    def _draw_vector_signal_custom(self, painter, signal, base_y, effective_height, drawing_width, pixels_per_time):
        transitions = signal.transitions
        if not transitions:
            return
        y_top = base_y + 5
        y_bottom = base_y + effective_height - 5
        delta = 2
        last_val = None
        for t, v in transitions:
            if t < self.start_time:
                last_val = v
            else:
                break
        if last_val is None:
            last_val = "0"
        last_disp = convert_vector(last_val, signal.width, signal.rep_mode)
        segment_start = 0
        fm = QFontMetrics(self.text_font)
        char_width = fm.horizontalAdvance("0")
        for t, val in transitions:
            if t < self.start_time or t > self.end_time:
                continue
            x = (t - self.start_time) * pixels_per_time
            if val == last_val:
                continue
            rect_end = max(segment_start, x - delta)
            painter.setPen(QPen(QColor("cyan"), 1))
            painter.drawLine(segment_start, y_top, rect_end, y_top)
            painter.setPen(QPen(QColor("lime"), 1))
            painter.drawLine(segment_start, y_bottom, rect_end, y_bottom)
            block_width = rect_end - segment_start
            if block_width >= char_width:
                full_text = last_disp
                text_width = fm.horizontalAdvance(full_text)
                if text_width > block_width:
                    max_chars = max(1, int(block_width / char_width))
                    full_text = full_text[:max_chars]
                painter.drawText(QRectF(segment_start, y_top, block_width, effective_height - 10), Qt.AlignmentFlag.AlignCenter, full_text)
            painter.setPen(QPen(QColor("lime"), 1))
            painter.drawLine(x - delta, y_top, x + delta, y_bottom)
            painter.drawLine(x - delta, y_bottom, x + delta, y_top)
            segment_start = x + delta
            last_val = val
            last_disp = convert_vector(val, signal.width, signal.rep_mode)
        rect_end = drawing_width
        painter.setPen(QPen(QColor("cyan"), 1))
        painter.drawLine(segment_start, y_top, rect_end, y_top)
        painter.setPen(QPen(QColor("lime"), 1))
        painter.drawLine(segment_start, y_bottom, rect_end, y_bottom)
        block_width = rect_end - segment_start
        if block_width >= char_width:
            full_text = last_disp
            text_width = fm.horizontalAdvance(full_text)
            if text_width > block_width:
                max_chars = max(1, int(block_width / char_width))
                full_text = full_text[:max_chars]
            painter.drawText(QRectF(segment_start, y_top, block_width, effective_height - 10), Qt.AlignmentFlag.AlignCenter, full_text)

    def _draw_analog_step(self, painter, signal, base_y, effective_height, drawing_width, pixels_per_time):
        min_val = None
        max_val = None
        for t, v in signal.transitions:
            try:
                num = int(v, 2)
            except:
                continue
            if min_val is None or num < min_val:
                min_val = num
            if max_val is None or num > max_val:
                max_val = num
        if min_val is None or max_val is None or max_val == min_val:
            self._draw_signal_custom(painter, signal, base_y, effective_height, drawing_width, pixels_per_time)
            return

        def map_value_to_y(num):
            norm = (num - min_val) / (max_val - min_val)
            return base_y + effective_height - norm * effective_height

        segment_start = 0
        last_val = None
        last_num = None
        for t, v in signal.transitions:
            if t < self.start_time:
                last_val = v
                try:
                    last_num = int(v, 2)
                except:
                    last_num = 0
            else:
                break
        if last_val is None:
            last_val = "0"
            last_num = 0

        last_disp = convert_vector(last_val, signal.width, signal.rep_mode)
        pen = QPen(QColor("yellow"), 1)
        painter.setPen(pen)
        painter.setFont(self.text_font)
        for t, v in signal.transitions:
            if t < self.start_time or t > self.end_time:
                continue
            try:
                y_value = map_value_to_y(last_num)
            except:
                y_value = base_y + effective_height - 5
            x = (t - self.start_time) * pixels_per_time
            norm = (last_num - min_val) / (max_val - min_val) if (max_val - min_val) != 0 else 0
            heat_color = QColor(int(norm * 255), 0, int((1 - norm) * 255))
            rect = QRectF(segment_start, base_y + effective_height, x - segment_start,
                          - (base_y + effective_height - y_value))
            painter.fillRect(rect, heat_color)
            painter.setPen(QPen(Qt.GlobalColor.yellow, 1))
            painter.drawLine(segment_start, y_value, x, y_value)
            segment_start = x + 1
            last_val = v
            try:
                last_num = int(last_val, 2)
            except:
                last_num = 0
            last_disp = convert_vector(last_val, signal.width, signal.rep_mode)
        try:
            y_value = map_value_to_y(last_num)
        except:
            y_value = base_y + effective_height - 5
        rect = QRectF(segment_start, base_y + effective_height, drawing_width - segment_start,
                      - (base_y + effective_height - y_value))
        try:
            norm = (last_num - min_val) / (max_val - min_val)
        except:
            norm = 0
        heat_color = QColor(int(norm * 255), 0, int((1 - norm) * 255))
        painter.fillRect(rect, heat_color)
        painter.setPen(QPen(Qt.GlobalColor.yellow, 1))
        text_rect = QRectF(segment_start, y_value, drawing_width - segment_start, base_y + effective_height - y_value)
        painter.setPen(QPen(Qt.GlobalColor.white, 1))
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, last_disp)

    def _draw_clock_custom(self, painter, signal, base_y, effective_height, drawing_width, pixels_per_time):
        high_y = base_y + 5
        low_y = base_y + effective_height - 5
        transitions = signal.transitions
        if not transitions:
            painter.setPen(QPen(QColor("lime"), 1))
            painter.drawLine(0, low_y, drawing_width, low_y)
            return
        last_val = "0"
        for t, val in transitions:
            if t < self.start_time:
                last_val = val
            else:
                break
        prev_x = 0
        prev_y = high_y if last_val == "1" else low_y
        for t, val in transitions:
            if t < self.start_time or t > self.end_time:
                continue
            x = (t - self.start_time) * pixels_per_time
            new_y = high_y if val == "1" else low_y
            if last_val == "1":
                painter.setPen(QPen(QColor("cyan"), 1))
            else:
                painter.setPen(QPen(QColor("lime"), 1))
            painter.drawLine(prev_x, prev_y, x, prev_y)
            painter.setPen(QPen(QColor("lime"), 1))
            painter.drawLine(x, prev_y, x, new_y)
            prev_x = x
            prev_y = new_y
            last_val = val
        if last_val == "1":
            painter.setPen(QPen(QColor("cyan"), 1))
        else:
            painter.setPen(QPen(QColor("lime"), 1))
        painter.drawLine(prev_x, prev_y, drawing_width, prev_y)

    def get_value_at_time(self, signal, time):
        val = None
        for t, v in signal.transitions:
            if t <= time:
                val = v
            else:
                break
        if val is None:
            val = "0"
        if signal.width > 1:
            return convert_vector(val, signal.width, signal.rep_mode)
        else:
            return val

    # --- Mouse Events ---
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self.cursor_time = None
            self.update()
            parent_panel = self.parent()
            while parent_panel is not None and not hasattr(parent_panel, "update_values"):
                parent_panel = parent_panel.parent()
            if parent_panel is not None:
                parent_panel.update_values()
        elif event.button() == Qt.MouseButton.LeftButton:
            self.selection_start_x = event.position().x()
            self.selection_end_x = event.position().x()
            self.update()

    def mouseMoveEvent(self, event):
        if self.selection_start_x is not None:
            self.selection_end_x = event.position().x()
            self.update()

    def mouseReleaseEvent(self, event):
        if self.selection_start_x is not None and self.selection_end_x is not None:
            if abs(self.selection_end_x - self.selection_start_x) > self.selection_threshold:
                drawing_width = self.width()
                time_span = self.end_time - self.start_time
                pixels_per_time = drawing_width / time_span if time_span else 1
                x1 = min(self.selection_start_x, self.selection_end_x)
                x2 = max(self.selection_start_x, self.selection_end_x)
                new_start = self.start_time + (x1 / pixels_per_time)
                new_end = self.start_time + (x2 / pixels_per_time)
                self.start_time = new_start
                self.end_time = new_end
            else:
                self.set_cursor(event)
            self.selection_start_x = None
            self.selection_end_x = None
            self.update()

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            # Ctrl+Scroll: Zoom (current behavior)
            if delta > 0:
                self.zoom(1.1)
            else:
                self.zoom(0.9)
        else:
            # Regular Scroll: Pan slowly left/right.
            pan_amount = -delta / 10  # Adjust divisor to change pan speed
            self.pan(pan_amount)

    def set_cursor(self, event):
        drawing_width = self.width()
        time_span = self.end_time - self.start_time
        pixels_per_time = drawing_width / time_span if time_span else 1
        self.cursor_time = self.start_time + event.position().x() / pixels_per_time
        self.update()
        parent_panel = self.parent()
        while parent_panel is not None and not hasattr(parent_panel, "update_values"):
            parent_panel = parent_panel.parent()
        if parent_panel is not None:
            parent_panel.update_values()

    def add_signal(self, signal):
        if signal not in self.signals:
            self.signals.append(signal)
            self.update()

    def clear(self):
        self.signals = []
        self.update()

    def set_time_window(self, start, end):
        self.start_time = start
        self.end_time = end
        self.update()

    def zoom(self, factor):
        window = self.end_time - self.start_time
        new_window = window / factor
        if self.cursor_time is not None:
            offset = self.cursor_time - self.start_time
            new_offset = offset / factor
            self.start_time = self.cursor_time - new_offset
            self.end_time = self.start_time + new_window
        else:
            self.end_time = self.start_time + new_window
        self.update()
        parent_panel = self.parent()
        while parent_panel is not None and not hasattr(parent_panel, "update_values"):
            parent_panel = parent_panel.parent()
        if parent_panel is not None:
            parent_panel.update_values()

    def pan(self, delta):
        # If panning left (delta negative) and already at the start, do nothing.
        if delta < 0 and self.start_time == 0:
            return
        self.start_time += delta
        self.end_time += delta
        if self.start_time < 0:
            self.start_time = 0
        self.update()
        parent_panel = self.parent()
        while parent_panel is not None and not hasattr(parent_panel, "update_values"):
            parent_panel = parent_panel.parent()
        if parent_panel is not None:
            parent_panel.update_values()

    def zoom_to_fit(self):
        if not self.signals:
            return
        min_time = None
        max_time = None
        for s in self.signals:
            if s.transitions:
                t0 = s.transitions[0][0]
                t1 = s.transitions[-1][0]
                if min_time is None or t0 < min_time:
                    min_time = t0
                if max_time is None or t1 > max_time:
                    max_time = t1
        if min_time is None or max_time is None or min_time == max_time:
            return
        self.start_time = min_time
        self.end_time = max_time
        self.update()
        parent_panel = self.parent()
        while parent_panel is not None and not hasattr(parent_panel, "update_values"):
            parent_panel = parent_panel.parent()
        if parent_panel is not None:
            parent_panel.update_values()

    def keyPressEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if event.key() == Qt.Key.Key_A:
                if self.cursor_time is not None:
                    self.marker_A = self.cursor_time
                    self.update()
                    parent_panel = self.parent()
                    while parent_panel is not None and not hasattr(parent_panel, "update_averages"):
                        parent_panel = parent_panel.parent()
                    if parent_panel is not None:
                        parent_panel.update_averages()
            elif event.key() == Qt.Key.Key_B:
                if self.cursor_time is not None:
                    self.marker_B = self.cursor_time
                    self.update()
                    parent_panel = self.parent()
                    while parent_panel is not None and not hasattr(parent_panel, "update_averages"):
                        parent_panel = parent_panel.parent()
                    if parent_panel is not None:
                        parent_panel.update_averages()
        else:
            super().keyPressEvent(event)
        # Note: We have removed the F key handling here so that the global shortcut in the main window is used.

# ---------------------------
# WaveformAverages: pane for marker info and averages.
# ---------------------------
class WaveformAverages(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.avg_data = []
        self.header = ""

    def set_data(self, header, data):
        self.header = header
        self.avg_data = data
        self.update()

    def clear(self):
        self.header = ""
        self.avg_data = []
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("black"))
        painter.setFont(QFont("Courier", 10, QFont.Weight.Bold))
        fm = QFontMetrics(painter.font())
        painter.setPen(QColor("yellow"))
        painter.drawText(5, fm.ascent()+2, self.header)
        for (y, avg_str) in self.avg_data:
            text_width = fm.horizontalAdvance(avg_str)
            painter.setPen(QColor("yellow"))
            painter.drawText(self.width() - text_width - 5, y + fm.ascent() / 2, avg_str)
        painter.end()

# ---------------------------
# Overlay widgets for fixed headers.
# ---------------------------
class WaveformHeaderOverlay(QWidget):
    def __init__(self, parent, waveform_view):
        super().__init__(parent)
        self.waveform_view = waveform_view
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("black"))
        drawing_width = self.width()
        top_margin = self.waveform_view.top_margin
        painter.setPen(QPen(Qt.GlobalColor.white))
        painter.drawLine(0, top_margin - 1, drawing_width, top_margin - 1)
        start_str = f"{self.waveform_view.start_time:.2f}"
        end_str = f"{self.waveform_view.end_time:.2f}"
        painter.drawText(5, top_margin - 5, start_str)
        fm = QFontMetrics(self.waveform_view.text_font)
        end_text_width = fm.horizontalAdvance(end_str)
        painter.drawText(drawing_width - end_text_width - 5, top_margin - 5, end_str)
        if self.waveform_view.cursor_time is not None:
            if self.waveform_view.end_time != self.waveform_view.start_time:
                pixels_per_time = drawing_width / (self.waveform_view.end_time - self.waveform_view.start_time)
                cursor_x = (self.waveform_view.cursor_time - self.waveform_view.start_time) * pixels_per_time
                pen = QPen(Qt.GlobalColor.red, 1, Qt.PenStyle.DashLine)
                painter.setPen(pen)
                painter.drawLine(cursor_x, 0, cursor_x, top_margin)
        if (self.waveform_view.marker_A is not None and
                self.waveform_view.start_time <= self.waveform_view.marker_A <= self.waveform_view.end_time):
            if self.waveform_view.end_time != self.waveform_view.start_time:
                pixels_per_time = drawing_width / (self.waveform_view.end_time - self.waveform_view.start_time)
                xA = (self.waveform_view.marker_A - self.waveform_view.start_time) * pixels_per_time
                painter.setPen(QPen(Qt.GlobalColor.yellow, 1))
                painter.drawLine(xA, 0, xA, top_margin)
                labelRect = QRectF(xA - 15, 0, 30, top_margin)
                painter.drawText(labelRect, Qt.AlignmentFlag.AlignCenter, "A")
        if (self.waveform_view.marker_B is not None and
                self.waveform_view.start_time <= self.waveform_view.marker_B <= self.waveform_view.end_time):
            if self.waveform_view.end_time != self.waveform_view.start_time:
                pixels_per_time = drawing_width / (self.waveform_view.end_time - self.waveform_view.start_time)
                xB = (self.waveform_view.marker_B - self.waveform_view.start_time) * pixels_per_time
                painter.setPen(QPen(Qt.GlobalColor.yellow, 1))
                painter.drawLine(xB, 0, xB, top_margin)
                labelRect = QRectF(xB - 15, 0, 30, top_margin)
                painter.drawText(labelRect, Qt.AlignmentFlag.AlignCenter, "B")
        painter.end()

class AveragesHeaderOverlay(QWidget):
    def __init__(self, parent, avg_panel):
        super().__init__(parent)
        self.avg_panel = avg_panel
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("black"))
        painter.setFont(QFont("Courier", 10, QFont.Weight.Bold))
        fm = QFontMetrics(painter.font())
        header_text = self.avg_panel.header
        painter.setPen(QColor("yellow"))
        painter.drawText(5, fm.ascent()+2, header_text)
        painter.end()

# ---------------------------
# WaveformPanel: composite widget containing all subwidgets.
# ---------------------------
class WaveformPanel(QWidget):
    def __init__(self, parent=None, name_panel_width=150, value_panel_width=100, avg_panel_width=100):
        super().__init__(parent)
        # Create the four sub-widgets.
        self.name_panel = WaveformNames(self)
        self.wave_view = WaveformView(self)
        self.value_panel = WaveformValues(self)
        self.avg_panel = WaveformAverages(self)

        # Create a QSplitter to hold them side by side.
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.addWidget(self.name_panel)
        self.splitter.addWidget(self.wave_view)
        self.splitter.addWidget(self.value_panel)
        self.splitter.addWidget(self.avg_panel)
        self.splitter.setSizes([name_panel_width, 600, value_panel_width, avg_panel_width])

        # Create a container widget for the splitter.
        self.content_widget = QWidget()
        content_layout = QVBoxLayout(self.content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.addWidget(self.splitter)

        # Create a scroll area for vertical scrolling.
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setWidget(self.content_widget)

        # Set the main layout.
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.scroll_area)
        self.setLayout(layout)

        # Create header overlays (children of the scroll area's viewport).
        self.wave_header_overlay = WaveformHeaderOverlay(self.scroll_area.viewport(), self.wave_view)
        self.avg_header_overlay = AveragesHeaderOverlay(self.scroll_area.viewport(), self.avg_panel)

        # Install an event filter on the viewport.
        self.scroll_area.viewport().installEventFilter(self)
        # Connect scroll bars signals to update overlays.
        self.scroll_area.verticalScrollBar().valueChanged.connect(self.update_overlays)
        self.scroll_area.horizontalScrollBar().valueChanged.connect(self.update_overlays)

        self.signals = []
        self.start_time = 0
        self.end_time = 200
        self.signal_height = 30
        self.top_margin = 30
        self.timescale_unit = ""
        self.highlighted_signal = None

    def eventFilter(self, obj, event):
        if obj == self.scroll_area.viewport() and event.type() in (QEvent.Type.Resize, QEvent.Type.Paint):
            self.update_overlays()
        return super().eventFilter(obj, event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_overlays()

    def update_overlays(self):
        # For the waveform header overlay, keep the y coordinate fixed at 0.
        pos = self.wave_view.mapTo(self.scroll_area.viewport(), QPoint(0, 0))
        # Use pos.x() so that horizontal scrolling still applies, but force y to 0.
        self.wave_header_overlay.setGeometry(pos.x(), 0, self.wave_view.width(), self.wave_view.top_margin)

        # For the averages header overlay, do the same.
        fm = QFontMetrics(QFont("Courier", 10, QFont.Weight.Bold))
        avg_header_height = fm.height() + 4
        pos2 = self.avg_panel.mapTo(self.scroll_area.viewport(), QPoint(0, 0))
        self.avg_header_overlay.setGeometry(pos2.x(), 0, self.avg_panel.width(), avg_header_height)

        self.wave_header_overlay.update()
        self.avg_header_overlay.update()

    def get_signal_positions(self):
        positions = []
        y = self.top_margin + 20
        for signal in self.signals:
            effective_height = self.signal_height * signal.height_factor
            positions.append((signal, y, effective_height))
            y += effective_height
        return positions

    def add_signal(self, signal):
        if signal not in self.signals:
            self.signals.append(signal)
            self.wave_view.add_signal(signal)
            self.redraw()

    def remove_signal(self, signal):
        if signal in self.signals:
            self.signals.remove(signal)
            if signal in self.wave_view.signals:
                self.wave_view.signals.remove(signal)
            self.redraw()

    def set_cursor(self, time):
        self.wave_view.cursor_time = time
        self.redraw()

    def update_values(self):
        self.value_panel.clear()
        positions = self.get_signal_positions()
        cursor = self.wave_view.cursor_time if self.wave_view.cursor_time is not None else self.wave_view.start_time
        for (signal, y, effective_height) in positions:
            val = self.wave_view.get_value_at_time(signal, cursor)
            self.value_panel.add_value(y + effective_height / 2, val)

    def update_averages(self):
        if self.wave_view.marker_A is None or self.wave_view.marker_B is None:
            self.avg_panel.clear()
            return
        A = self.wave_view.marker_A
        B = self.wave_view.marker_B
        if A > B:
            A, B = B, A
        header = f"A: {A:.2f} B: {B:.2f}"
        avg_data = []
        for (signal, y, effective_height) in self.get_signal_positions():
            avg_val = self.compute_average(signal, A, B)
            avg_data.append((y + effective_height/2, f"{avg_val:.2f}"))
        self.avg_panel.set_data(header, avg_data)

    def compute_average(self, signal, A, B):
        total = 0.0
        duration = B - A
        if duration <= 0:
            return 0.0
        transitions = signal.transitions
        current_val = None
        for t, v in transitions:
            if t <= A:
                current_val = v
            else:
                break
        if current_val is None:
            current_val = "0"
        current_time = A
        for t, v in transitions:
            if t < A:
                continue
            if t > B:
                break
            seg_duration = t - current_time
            total += seg_duration * numeric_value(current_val)
            current_time = t
            current_val = v
        if current_time < B:
            seg_duration = B - current_time
            total += seg_duration * numeric_value(current_val)
        return total / duration

    def redraw(self):
        self.wave_view.top_margin = self.top_margin
        self.wave_view.highlighted_signal = self.highlighted_signal
        self.wave_view.update()
        self.name_panel.set_signals(self.signals, self.top_margin, self.signal_height, self.highlighted_signal)
        self.update_values()
        self.update_averages()
        total_height = self.top_margin + 20
        for signal in self.signals:
            total_height += self.signal_height * signal.height_factor
        self.content_widget.setMinimumHeight(total_height)
        self.update_overlays()

# ---------------------------
# WaveformNames
# ---------------------------
class WaveformNames(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.signals = []
        self.top_margin = 30
        self.signal_height = 30
        self.selected_signals = set()
        self.last_clicked_index = None

    def set_signals(self, signals, top_margin, signal_height, highlighted_signal=None):
        self.signals = signals
        self.top_margin = top_margin
        self.signal_height = signal_height
        self.selected_signals.clear()
        self.last_clicked_index = None
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("black"))
        painter.setFont(QFont("Arial", 10))
        fm = QFontMetrics(painter.font())
        y = self.top_margin + 20
        for signal in self.signals:
            effective_height = self.signal_height * signal.height_factor
            if signal in self.selected_signals:
                painter.fillRect(0, y, self.width(), effective_height, QColor("darkblue"))
            painter.setPen(QColor("white"))
            painter.drawText(5, y + effective_height / 2 + fm.ascent() / 2, signal.fullname)
            y += effective_height
        painter.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            y_click = event.position().y()
            index = None
            y_acc = self.top_margin + 20
            for i, signal in enumerate(self.signals):
                effective_height = self.signal_height * signal.height_factor
                if y_acc <= y_click < y_acc + effective_height:
                    index = i
                    break
                y_acc += effective_height
            if index is not None:
                clicked_signal = self.signals[index]
                modifiers = event.modifiers()
                if modifiers & Qt.KeyboardModifier.ShiftModifier and self.last_clicked_index is not None:
                    start = min(self.last_clicked_index, index)
                    end = max(self.last_clicked_index, index)
                    for i in range(start, end + 1):
                        self.selected_signals.add(self.signals[i])
                elif modifiers & Qt.KeyboardModifier.ControlModifier:
                    if clicked_signal in self.selected_signals:
                        self.selected_signals.remove(clicked_signal)
                    else:
                        self.selected_signals.add(clicked_signal)
                    self.last_clicked_index = index
                else:
                    self.selected_signals = {clicked_signal}
                    self.last_clicked_index = index
                self.update()
        elif event.button() == Qt.MouseButton.RightButton:
            y_click = event.position().y()
            index = None
            y_acc = self.top_margin + 20
            for i, signal in enumerate(self.signals):
                effective_height = self.signal_height * signal.height_factor
                if y_acc <= y_click < y_acc + effective_height:
                    index = i
                    break
                y_acc += effective_height
            if index is not None:
                clicked_signal = self.signals[index]
                if clicked_signal not in self.selected_signals:
                    self.selected_signals = {clicked_signal}
                    self.last_clicked_index = index
                    self.update()
                menu = self._create_context_menu(clicked_signal)
                menu.exec(event.globalPosition().toPoint())
        else:
            super().mousePressEvent(event)

    def _create_context_menu(self, signal):
        menu = QMenu(self)
        action_hex = QAction("Hex", self)
        action_hex.setCheckable(True)
        action_bin = QAction("Bin", self)
        action_bin.setCheckable(True)
        action_dec = QAction("Decimal", self)
        action_dec.setCheckable(True)
        rep = signal.rep_mode
        if rep == "hex":
            action_hex.setChecked(True)
        elif rep == "bin":
            action_bin.setChecked(True)
        elif rep == "decimal":
            action_dec.setChecked(True)
        menu.addAction(action_hex)
        menu.addAction(action_bin)
        menu.addAction(action_dec)
        action_hex.triggered.connect(lambda: self._set_signal_representation("hex", signal))
        action_bin.triggered.connect(lambda: self._set_signal_representation("bin", signal))
        action_dec.triggered.connect(lambda: self._set_signal_representation("decimal", signal))
        action_toggle = QAction("Analog Step", self)
        action_toggle.setCheckable(True)
        action_toggle.setChecked(signal.analog_render)
        action_toggle.triggered.connect(lambda checked, s=signal: self._toggle_analog_render(s))
        menu.addAction(action_toggle)
        height_menu = QMenu("Set Height", self)
        for factor in [1, 2, 3, 4]:
            action_height = QAction(str(factor), self)
            action_height.setCheckable(True)
            action_height.setChecked(signal.height_factor == factor)
            action_height.triggered.connect(lambda checked, f=factor, s=signal: self._set_signal_height(f, s))
            height_menu.addAction(action_height)
        menu.addMenu(height_menu)
        action_dump = menu.addAction("Dump")
        action_dump.triggered.connect(lambda: self._dump_signals(signal))
        return menu

    def _set_signal_representation(self, mode, clicked_signal):
        targets = self.selected_signals if self.selected_signals else {clicked_signal}
        for s in targets:
            s.rep_mode = mode
        parent_panel = self.parent()
        while parent_panel is not None and not hasattr(parent_panel, "redraw"):
            parent_panel = parent_panel.parent()
        if parent_panel is not None:
            parent_panel.redraw()

    def _set_signal_height(self, factor, clicked_signal):
        targets = self.selected_signals if self.selected_signals else {clicked_signal}
        for s in targets:
            s.height_factor = factor
        parent_panel = self.parent()
        while parent_panel is not None and not hasattr(parent_panel, "redraw"):
            parent_panel = parent_panel.parent()
        if parent_panel is not None:
            parent_panel.redraw()

    def _toggle_analog_render(self, clicked_signal):
        targets = self.selected_signals if self.selected_signals else {clicked_signal}
        for s in targets:
            s.analog_render = not s.analog_render
        parent_panel = self.parent()
        while parent_panel is not None and not hasattr(parent_panel, "redraw"):
            parent_panel = parent_panel.parent()
        if parent_panel is not None:
            parent_panel.redraw()

    def _dump_signals(self, clicked_signal):
        targets = self.selected_signals if self.selected_signals else {clicked_signal}
        main_window = self.window()
        if hasattr(main_window, "dump_signals"):
            main_window.dump_signals(list(targets))

class WaveformValues(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.values = []

    def clear(self):
        self.values = []
        self.update()

    def add_value(self, y, text):
        self.values.append((y, text))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("black"))
        painter.setFont(QFont("Courier", 10, QFont.Weight.Bold))
        fm = QFontMetrics(painter.font())
        for (y, text) in self.values:
            text_width = fm.horizontalAdvance(text)
            painter.setPen(QColor("yellow"))
            painter.drawText(self.width() - text_width - 5, y + fm.ascent() / 2, text)
        painter.end()

# ---------------------------
# VCDViewer: Main Application
# ---------------------------
class VCDViewer(QMainWindow):
    def __init__(self, vcd_filename):
        super().__init__()
        self.setWindowTitle("VCD Waveform Viewer")
        self.resize(1200, 600)
        self.vcd_filename = vcd_filename
        self.vcd_parser = VCDParser(self.vcd_filename)
        timescale = self.vcd_parser.parse()
        self.timescale = timescale if timescale else "unknown"
        self.timescale_unit = ''.join(c for c in self.timescale if not c.isdigit()).strip()
        self.tree_signal_map = {}
        self._create_menu()
        self._create_main_ui()
        # NEW: Create a global QShortcut for "F" and store search_window reference.
        self.search_shortcut = QShortcut(QKeySequence("F"), self)
        self.search_shortcut.activated.connect(self.open_search_window)
        self.search_window = None

    def _create_menu(self):
        menubar = self.menuBar()
        filemenu = menubar.addMenu("File")
        open_action = QAction("Open...", self)
        open_action.triggered.connect(self.open_file)
        filemenu.addAction(open_action)
        save_state_action = QAction("Save State", self)
        save_state_action.triggered.connect(self.save_state)
        filemenu.addAction(save_state_action)
        load_state_action = QAction("Load State", self)
        load_state_action.triggered.connect(self.load_state)
        filemenu.addAction(load_state_action)
        filemenu.addSeparator()
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        filemenu.addAction(exit_action)

    def _create_main_ui(self):
        main_splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self.setCentralWidget(main_splitter)
        left_frame = QWidget()
        left_layout = QVBoxLayout(left_frame)
        label = QLabel("DesignTree")
        label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        left_layout.addWidget(label)
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Signal Filter:"))
        self.filter_entry = QLineEdit()
        filter_layout.addWidget(self.filter_entry)
        self.filter_entry.textChanged.connect(self.rebuild_tree)
        left_layout.addLayout(filter_layout)
        self.tree = DesignTree()
        left_layout.addWidget(self.tree)
        self.tree.signalsToAdd.connect(self.add_signals_from_tree)
        self.tree.itemDoubleClicked.connect(self.on_tree_double_click)
        self.rebuild_tree()
        main_splitter.addWidget(left_frame)
        right_frame = QWidget()
        right_layout = QVBoxLayout(right_frame)
        self.wave_panel = WaveformPanel(name_panel_width=150, value_panel_width=100, avg_panel_width=100)
        right_layout.addWidget(self.wave_panel, 1)
        control_frame = QWidget()
        ctrl_layout = QHBoxLayout(control_frame)
        btn_pan_left = QPushButton("<< Pan Left")
        btn_pan_left.clicked.connect(lambda: self.wave_panel.wave_view.pan(-50))
        ctrl_layout.addWidget(btn_pan_left)
        btn_pan_right = QPushButton("Pan Right >>")
        btn_pan_right.clicked.connect(lambda: self.wave_panel.wave_view.pan(50))
        ctrl_layout.addWidget(btn_pan_right)
        btn_zoom_in = QPushButton("Zoom In")
        btn_zoom_in.clicked.connect(lambda: self.wave_panel.wave_view.zoom(1.5))
        ctrl_layout.addWidget(btn_zoom_in)
        btn_zoom_out = QPushButton("Zoom Out")
        btn_zoom_out.clicked.connect(lambda: self.wave_panel.wave_view.zoom(1/1.5))
        ctrl_layout.addWidget(btn_zoom_out)
        btn_zoom_fit = QPushButton("Zoom to Fit")
        btn_zoom_fit.clicked.connect(self.wave_panel.wave_view.zoom_to_fit)
        ctrl_layout.addWidget(btn_zoom_fit)
        ctrl_layout.addStretch()
        timescale_label = QLabel(f"Timescale: {self.timescale}")
        ctrl_layout.addWidget(timescale_label)
        right_layout.addWidget(control_frame)
        main_splitter.addWidget(right_frame)

    def open_search_window(self):
        # NEW: Use the selected signals from the WaveformNames panel.
        selected = self.wave_panel.name_panel.selected_signals
        if not selected:
            print("No signals selected for search.")
            return
        # If a SearchWindow already exists, close it first.
        if self.search_window is not None:
            self.search_window.close()
        self.search_window = SearchWindow(list(selected), self)
        self.search_window.show()

    def add_signals_from_tree(self, signals):
        for sig in signals:
            self.wave_panel.add_signal(sig)

    def open_file(self):
        new_file, _ = QFileDialog.getOpenFileName(self, "Open VCD File", "", "VCD files (*.vcd);;All files (*)")
        if new_file:
            self.vcd_filename = new_file
            self.vcd_parser = VCDParser(self.vcd_filename)
            timescale = self.vcd_parser.parse()
            self.timescale = timescale if timescale else "unknown"
            self.timescale_unit = ''.join(c for c in self.timescale if not c.isdigit()).strip()
            self.tree_signal_map = {}
            self.rebuild_tree()
            self.wave_panel.wave_view.clear()
            self.wave_panel.signals = []
            self.wave_panel.redraw()

    def rebuild_tree(self):
        pattern = self.filter_entry.text().strip()
        self.tree.clear()
        self.tree.signal_map.clear()
        self.tree_signal_map.clear()
        self._build_filtered_tree(None, self.vcd_parser.hierarchy, pattern)

    def _build_filtered_tree(self, parent_item, tree_dict, pattern):
        for key, subtree in tree_dict.items():
            if key == "_signal":
                continue
            if set(subtree.keys()) == {"_signal"}:
                signal = subtree["_signal"]
                if not pattern or fnmatch.fnmatch(signal.name, f"*{pattern}*"):
                    if parent_item is None:
                        leaf = QTreeWidgetItem(self.tree, [signal.name])
                    else:
                        leaf = QTreeWidgetItem(parent_item, [signal.name])
                    self.tree.signal_map[leaf] = signal
                    self.tree_signal_map[leaf] = signal
                    if self._is_dynamic(signal):
                        leaf.setForeground(0, QColor("red"))
                    else:
                        leaf.setForeground(0, QColor("gray"))
            else:
                if parent_item is None:
                    node = QTreeWidgetItem(self.tree, [key])
                else:
                    node = QTreeWidgetItem(parent_item, [key])
                node.setExpanded(True)
                self._build_filtered_tree(node, subtree, pattern)

    def _is_dynamic(self, signal):
        if not signal.transitions:
            return False
        return len({v for _, v in signal.transitions}) > 1

    def on_tree_double_click(self, item, column):
        if item.childCount() > 0:
            return
        if item in self.tree.signal_map:
            signal = self.tree.signal_map[item]
            self.wave_panel.add_signal(signal)
        else:
            full_name = item.text(0)
            parent = item.parent()
            while parent:
                full_name = parent.text(0) + "." + full_name
                parent = parent.parent()
            for sig in self.vcd_parser.signals.values():
                if sig.fullname == full_name:
                    self.wave_panel.add_signal(sig)
                    return

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Delete:
            selected_signals = self.wave_panel.name_panel.selected_signals
            if selected_signals:
                for sig in list(selected_signals):
                    if sig in self.wave_panel.signals:
                        self.wave_panel.remove_signal(sig)
                self.wave_panel.name_panel.selected_signals.clear()
                self.wave_panel.highlighted_signal = None
                self.wave_panel.redraw()
            else:
                if self.wave_panel.highlighted_signal in self.wave_panel.signals:
                    self.wave_panel.remove_signal(self.wave_panel.highlighted_signal)
                    self.wave_panel.highlighted_signal = None
                    self.wave_panel.redraw()
        else:
            super().keyPressEvent(event)

    def save_state(self):
        state = {
            "vcd_filename": self.vcd_filename,
            "signals": [
                {
                    "fullname": sig.fullname,
                    "rep_mode": sig.rep_mode,
                    "height_factor": sig.height_factor,
                    "analog_render": sig.analog_render
                }
                for sig in self.wave_panel.signals
            ],
            "zoom": {
                "start_time": self.wave_panel.wave_view.start_time,
                "end_time": self.wave_panel.wave_view.end_time
            },
            "cursor_time": self.wave_panel.wave_view.cursor_time,
            "marker_A": self.wave_panel.wave_view.marker_A,
            "marker_B": self.wave_panel.wave_view.marker_B
        }
        save_file, _ = QFileDialog.getSaveFileName(self, "Save Application State", "", "JSON Files (*.json);;All Files (*)")
        if save_file:
            try:
                with open(save_file, "w") as f:
                    json.dump(state, f, indent=4)
            except Exception as e:
                print("Error saving state:", e)

    def load_state(self):
        load_file, _ = QFileDialog.getOpenFileName(self, "Load Application State", "", "JSON Files (*.json);;All Files (*)")
        if not load_file:
            return
        try:
            with open(load_file, "r") as f:
                state = json.load(f)
        except Exception as e:
            print("Error loading state:", e)
            return
        if not hasattr(self, "vcd_parser") or not self.vcd_parser:
            print("No VCD file loaded; cannot load state.")
            return
        saved_vcd = state.get("vcd_filename", "")
        current_vcd = self.vcd_filename
        if saved_vcd and saved_vcd != current_vcd:
            print("Warning: saved state is from a different VCD file. Only signals with matching names will be restored.")
        self.wave_panel.signals = []
        self.wave_panel.wave_view.clear()
        saved_signals = state.get("signals", [])
        for sig_data in saved_signals:
            fullname = sig_data.get("fullname")
            for sig in self.vcd_parser.signals.values():
                if sig.fullname == fullname:
                    sig.rep_mode = sig_data.get("rep_mode", "hex")
                    sig.height_factor = sig_data.get("height_factor", 1)
                    sig.analog_render = sig_data.get("analog_render", False)
                    self.wave_panel.add_signal(sig)
                    break
        zoom = state.get("zoom", {})
        self.wave_panel.wave_view.start_time = zoom.get("start_time", self.wave_panel.wave_view.start_time)
        self.wave_panel.wave_view.end_time = zoom.get("end_time", self.wave_panel.wave_view.end_time)
        self.wave_panel.wave_view.cursor_time = state.get("cursor_time", None)
        self.wave_panel.wave_view.marker_A = state.get("marker_A", None)
        self.wave_panel.wave_view.marker_B = state.get("marker_B", None)
        self.wave_panel.redraw()

    def dump_signals(self, signals):
        if not signals:
            return
        global_start = None
        global_end = None
        for sig in signals:
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
            global_start = 0
        if global_end is None:
            global_end = 0

        time_points = set()
        for sig in signals:
            for t, _ in sig.transitions:
                if global_start <= t <= global_end:
                    time_points.add(t)
        time_points.add(global_start)
        time_points = sorted(time_points)

        def get_val_at(sig, ts):
            sval = None
            for time_stamp, v in sig.transitions:
                if time_stamp <= ts:
                    sval = v
                else:
                    break
            if sval is None:
                sval = "0"
            return sval

        dump_filename = "signal_dump.vcd"
        try:
            with open(dump_filename, "w") as f:
                f.write("$date\n")
                f.write(f"    {datetime.now().ctime()}\n")
                f.write("$end\n")
                f.write("$version\n")
                f.write("    VCD dump generated by VCDViewer\n")
                f.write("$end\n")
                f.write(f"$timescale {self.timescale} $end\n")
                f.write("$scope module dump $end\n")
                for sig in signals:
                    f.write(f"$var wire {sig.width} {sig.id} {sig.fullname} $end\n")
                f.write("$upscope $end\n")
                f.write("$enddefinitions $end\n")
                f.write("$dumpvars\n")
                last_values = {}
                for sig in signals:
                    val = get_val_at(sig, global_start)
                    last_values[sig.id] = val
                    if sig.width == 1:
                        f.write(f"{val}{sig.id}\n")
                    else:
                        f.write(f"b{val} {sig.id}\n")
                f.write("$end\n")
                for t in time_points:
                    if t == global_start:
                        continue
                    changes = []
                    for sig in signals:
                        new_val = get_val_at(sig, t)
                        if new_val != last_values.get(sig.id):
                            if sig.width == 1:
                                changes.append(f"{new_val}{sig.id}")
                            else:
                                changes.append(f"b{new_val} {sig.id}")
                            last_values[sig.id] = new_val
                    if changes:
                        f.write(f"#{t}\n")
                        for change in changes:
                            f.write(f"{change}\n")
            print(f"Dumped {len(signals)} signal(s) to {dump_filename}.")
        except Exception as e:
            print("Error dumping signals:", e)

if __name__ == "__main__":
    vcd_filename = "jtag.vcd"  # Default file; choose another via File > Open.
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    viewer = VCDViewer(vcd_filename)
    viewer.show()
    sys.exit(app.exec())
