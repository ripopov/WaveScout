#!/usr/bin/env python3
"""
Wavescout: An interactive Python application designed for waveform visualization and analysis.
This version refactors the code to separate concerns (MVC/MVP) and decouple components via signals.
It also fixes the search window so that it remains visible until closed.
"""

import sys
import re
import fnmatch
import json
from math import ceil
from datetime import datetime  # used for date stamp in dumped file
from vcd_parser import *  # assumes that the VCDParser and signal classes are defined here

from PySide6.QtCore import Qt, QRectF, QPoint, QEvent, Signal, QObject
from PySide6.QtGui import (QPainter, QPen, QBrush, QColor, QFont, QFontMetrics, QAction,
                           QGuiApplication, QKeySequence, QShortcut)
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                               QPushButton, QLabel, QLineEdit, QSplitter, QMenu, QAbstractItemView,
                               QTreeWidget, QTreeWidgetItem, QFileDialog, QScrollArea)

# -----------------------------------------------------------------------------
# StateManager: handles saving/loading (file I/O) for application state.
# -----------------------------------------------------------------------------
class StateManager(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)

    def save_state(self, state, filename):
        try:
            with open(filename, "w") as f:
                json.dump(state, f, indent=4)
        except Exception as e:
            print("Error saving state:", e)

    def load_state(self, filename):
        try:
            with open(filename, "r") as f:
                return json.load(f)
        except Exception as e:
            print("Error loading state:", e)
            return None

# -----------------------------------------------------------------------------
# WaveformModel: encapsulates the domain data (VCD file, timescale, signals, hierarchy)
# -----------------------------------------------------------------------------
class WaveformModel(QObject):
    def __init__(self, vcd_filename, parent=None):
        super().__init__(parent)
        self.vcd_filename = vcd_filename
        self.vcd_parser = VCDParser(self.vcd_filename)
        timescale = self.vcd_parser.parse()
        self.timescale = timescale if timescale else "unknown"
        self.signals = list(self.vcd_parser.signals.values())
        self.hierarchy = self.vcd_parser.hierarchy

# -----------------------------------------------------------------------------
# SearchWindow (View): a window for searching for a timestamp where selected signals match.
# Now it emits a timestampFound signal. Also, its window flags are set so that it shows
# as a top-level window and remains visible until explicitly closed.
# -----------------------------------------------------------------------------
class SearchWindow(QWidget):
    timestampFound = Signal(float)  # Emits a found timestamp

    def __init__(self, signals, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Search Window")
        # Force this widget to be a top-level window so it remains visible.
        self.setWindowFlags(self.windowFlags() | Qt.Window)
        self.signals = signals
        self.signal_edits = {}  # Mapping: signal -> QLineEdit

        layout = QVBoxLayout(self)
        # Create one row per selected signal.
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
        desired = {}
        for sig, edit in self.signal_edits.items():
            txt = edit.text().strip()
            if txt != "":
                desired[sig] = numeric_value(txt)
        if not desired:
            self.result_label.setText("Please enter a value for at least one signal.")
            return

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

# -----------------------------------------------------------------------------
# DesignTree (View): a QTreeWidget with a custom key handler. (Signals are used to add signals.)
# -----------------------------------------------------------------------------
class DesignTree(QTreeWidget):
    signalsToAdd = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
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

# -----------------------------------------------------------------------------
# WaveformView (View): a custom drawing widget. Now it emits signals when the time window,
# cursor or markers change instead of “climbing up” the widget hierarchy.
# -----------------------------------------------------------------------------
class WaveformView(QWidget):
    timeWindowChanged = Signal(float, float)  # start_time, end_time
    cursorChanged = Signal(float)             # new cursor time
    markersChanged = Signal()                 # marker A or B changed

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.signals = []
        self.start_time = 0
        self.end_time = 200
        self.zoom_factor = 1.0

        self.signal_height = 30
        self.left_margin = 0
        self.top_margin = 30  # Reserved for timeline header.
        self.text_font = QFont("Courier", 10)
        self.value_font = QFont("Courier", 10, QFont.Bold)
        self.cursor_time = None
        self.highlighted_signal = None

        self.marker_A = None
        self.marker_B = None

        self.selection_start_x = None
        self.selection_end_x = None
        self.selection_threshold = 10

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing, True)
        painter.fillRect(self.rect(), QColor("black"))
        drawing_width = self.width()
        drawing_height = self.height()

        # Draw timeline header.
        painter.setPen(QPen(Qt.white))
        painter.drawLine(0, self.top_margin, drawing_width, self.top_margin)
        start_str = f"{self.start_time:.2f}"
        end_str = f"{self.end_time:.2f}"
        painter.drawText(5, self.top_margin - 5, start_str)
        fm = QFontMetrics(self.text_font)
        end_text_width = fm.horizontalAdvance(end_str)
        painter.drawText(drawing_width - end_text_width - 5, self.top_margin - 5, end_str)

        time_span = self.end_time - self.start_time
        pixels_per_time = drawing_width / time_span if time_span else 1

        # Draw selection rectangle (if any).
        if self.selection_start_x is not None and self.selection_end_x is not None:
            x1 = min(self.selection_start_x, self.selection_end_x)
            x2 = max(self.selection_start_x, self.selection_end_x)
            selection_rect = QRectF(x1, self.top_margin, x2 - x1, drawing_height - self.top_margin)
            painter.fillRect(selection_rect, QBrush(QColor(0, 0, 255, 100)))

        # Draw each signal.
        y = self.top_margin + 20
        for signal in self.signals:
            effective_height = self.signal_height * signal.height_factor
            if self.highlighted_signal == signal:
                painter.setPen(QPen(QColor("darkblue"), 1))
                painter.drawRect(0, y, drawing_width, effective_height)
            if signal.width > 1:
                if signal.analog_render:
                    self._draw_analog_step(painter, signal, y, effective_height, drawing_width, pixels_per_time)
                else:
                    self._draw_vector_signal_custom(painter, signal, y, effective_height, drawing_width, pixels_per_time)
            else:
                self._draw_signal_custom(painter, signal, y, effective_height, drawing_width, pixels_per_time)
            y += effective_height

        # Draw cursor (if any).
        if self.cursor_time is not None:
            cursor_x = (self.cursor_time - self.start_time) * pixels_per_time
            pen = QPen(Qt.red, 1, Qt.DashLine)
            painter.setPen(pen)
            painter.drawLine(cursor_x, self.top_margin, cursor_x, drawing_height)

        # Draw markers A and B.
        if self.marker_A is not None and self.start_time <= self.marker_A <= self.end_time:
            xA = (self.marker_A - self.start_time) * pixels_per_time
            painter.setPen(QPen(Qt.yellow, 1))
            painter.drawLine(xA, self.top_margin, xA, drawing_height)
            label_rect = QRectF(xA - 15, 0, 30, self.top_margin)
            painter.drawText(label_rect, Qt.AlignCenter, "A")
        if self.marker_B is not None and self.start_time <= self.marker_B <= self.end_time:
            xB = (self.marker_B - self.start_time) * pixels_per_time
            painter.setPen(QPen(Qt.yellow, 1))
            painter.drawLine(xB, self.top_margin, xB, drawing_height)
            label_rect = QRectF(xB - 15, 0, 30, self.top_margin)
            painter.drawText(label_rect, Qt.AlignCenter, "B")

        # Draw global start and end markers.
        global_min, global_max = self._get_global_range()
        if global_min is not None and global_max is not None:
            if self.start_time == global_min:
                painter.setPen(QPen(Qt.red, 3))
                painter.drawLine(0, self.top_margin, 0, drawing_height)
            elif self.start_time < global_min < self.end_time:
                x_global_min = (global_min - self.start_time) * pixels_per_time
                painter.setPen(QPen(Qt.red, 1))
                painter.drawLine(x_global_min, self.top_margin, x_global_min, drawing_height)
            if self.end_time == global_max:
                painter.setPen(QPen(Qt.red, 3))
                painter.drawLine(drawing_width, self.top_margin, drawing_width, drawing_height)
            elif self.start_time < global_max < self.end_time:
                x_global_max = (global_max - self.start_time) * pixels_per_time
                painter.setPen(QPen(Qt.red, 1))
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
                painter.drawText(QRectF(segment_start, y_top, block_width, effective_height - 10), Qt.AlignCenter, full_text)
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
            painter.drawText(QRectF(segment_start, y_top, block_width, effective_height - 10), Qt.AlignCenter, full_text)

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
            painter.setPen(QPen(Qt.yellow, 1))
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
        painter.setPen(QPen(Qt.yellow, 1))
        text_rect = QRectF(segment_start, y_value, drawing_width - segment_start, base_y + effective_height - y_value)
        painter.setPen(QPen(Qt.white, 1))
        painter.drawText(text_rect, Qt.AlignCenter, last_disp)

    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            self.cursor_time = None
            self.update()
            self.cursorChanged.emit(0)
        elif event.button() == Qt.LeftButton:
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
                self.timeWindowChanged.emit(self.start_time, self.end_time)
            else:
                self.set_cursor(event)
            self.selection_start_x = None
            self.selection_end_x = None
            self.update()

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if event.modifiers() & Qt.ControlModifier:
            if delta > 0:
                self.zoom(1.1)
            else:
                self.zoom(0.9)
        else:
            pan_amount = -delta / 10
            self.pan(pan_amount)

    def set_cursor(self, event):
        drawing_width = self.width()
        time_span = self.end_time - self.start_time
        pixels_per_time = drawing_width / time_span if time_span else 1
        self.cursor_time = self.start_time + event.position().x() / pixels_per_time
        self.cursorChanged.emit(self.cursor_time)
        self.update()

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
        self.timeWindowChanged.emit(start, end)
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
        self.timeWindowChanged.emit(self.start_time, self.end_time)
        self.update()

    def pan(self, delta):
        if delta < 0 and self.start_time == 0:
            return
        self.start_time += delta
        self.end_time += delta
        if self.start_time < 0:
            self.start_time = 0
        self.timeWindowChanged.emit(self.start_time, self.end_time)
        self.update()

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
        self.timeWindowChanged.emit(self.start_time, self.end_time)
        self.update()

    def keyPressEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            if event.key() == Qt.Key_A:
                if self.cursor_time is not None:
                    self.marker_A = self.cursor_time
                    self.markersChanged.emit()
                    self.update()
            elif event.key() == Qt.Key_B:
                if self.cursor_time is not None:
                    self.marker_B = self.cursor_time
                    self.markersChanged.emit()
                    self.update()
        else:
            super().keyPressEvent(event)

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

# -----------------------------------------------------------------------------
# WaveformAverages (View): displays marker info and computed averages.
# -----------------------------------------------------------------------------
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
        painter.setFont(QFont("Courier", 10, QFont.Bold))
        fm = QFontMetrics(painter.font())
        painter.setPen(QColor("yellow"))
        painter.drawText(5, fm.ascent()+2, self.header)
        for (y, avg_str) in self.avg_data:
            text_width = fm.horizontalAdvance(avg_str)
            painter.setPen(QColor("yellow"))
            painter.drawText(self.width() - text_width - 5, y + fm.ascent() / 2, avg_str)
        painter.end()

# -----------------------------------------------------------------------------
# WaveformHeaderOverlay and AveragesHeaderOverlay (View): fixed headers drawn over scrollable areas.
# -----------------------------------------------------------------------------
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
        painter.setPen(QPen(Qt.white))
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
                pen = QPen(Qt.red, 1, Qt.DashLine)
                painter.setPen(pen)
                painter.drawLine(cursor_x, 0, cursor_x, top_margin)
        if (self.waveform_view.marker_A is not None and
                self.waveform_view.start_time <= self.waveform_view.marker_A <= self.waveform_view.end_time):
            if self.waveform_view.end_time != self.waveform_view.start_time:
                pixels_per_time = drawing_width / (self.waveform_view.end_time - self.waveform_view.start_time)
                xA = (self.waveform_view.marker_A - self.waveform_view.start_time) * pixels_per_time
                painter.setPen(QPen(Qt.yellow, 1))
                painter.drawLine(xA, 0, xA, top_margin)
                labelRect = QRectF(xA - 15, 0, 30, top_margin)
                painter.drawText(labelRect, Qt.AlignCenter, "A")
        if (self.waveform_view.marker_B is not None and
                self.waveform_view.start_time <= self.waveform_view.marker_B <= self.waveform_view.end_time):
            if self.waveform_view.end_time != self.waveform_view.start_time:
                pixels_per_time = drawing_width / (self.waveform_view.end_time - self.waveform_view.start_time)
                xB = (self.waveform_view.marker_B - self.waveform_view.start_time) * pixels_per_time
                painter.setPen(QPen(Qt.yellow, 1))
                painter.drawLine(xB, 0, xB, top_margin)
                labelRect = QRectF(xB - 15, 0, 30, top_margin)
                painter.drawText(labelRect, Qt.AlignCenter, "B")
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
        painter.setFont(QFont("Courier", 10, QFont.Bold))
        fm = QFontMetrics(painter.font())
        header_text = self.avg_panel.header
        painter.setPen(QColor("yellow"))
        painter.drawText(5, fm.ascent()+2, header_text)
        painter.end()

# -----------------------------------------------------------------------------
# WaveformPanel (Controller/View container): a composite widget that arranges
# the waveform view, signal names, values and averages. It connects signals from
# child widgets to update the view.
# -----------------------------------------------------------------------------
class WaveformPanel(QWidget):
    def __init__(self, parent=None, name_panel_width=150, value_panel_width=100, avg_panel_width=100):
        super().__init__(parent)
        self.name_panel = WaveformNames(self)
        self.wave_view = WaveformView(self)
        self.value_panel = WaveformValues(self)
        self.avg_panel = WaveformAverages(self)

        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.addWidget(self.name_panel)
        self.splitter.addWidget(self.wave_view)
        self.splitter.addWidget(self.value_panel)
        self.splitter.addWidget(self.avg_panel)
        self.splitter.setSizes([name_panel_width, 600, value_panel_width, avg_panel_width])

        self.content_widget = QWidget()
        content_layout = QVBoxLayout(self.content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.addWidget(self.splitter)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setWidget(self.content_widget)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.scroll_area)
        self.setLayout(layout)

        self.wave_header_overlay = WaveformHeaderOverlay(self.scroll_area.viewport(), self.wave_view)
        self.avg_header_overlay = AveragesHeaderOverlay(self.scroll_area.viewport(), self.avg_panel)

        self.scroll_area.viewport().installEventFilter(self)
        self.scroll_area.verticalScrollBar().valueChanged.connect(self.update_overlays)
        self.scroll_area.horizontalScrollBar().valueChanged.connect(self.update_overlays)

        self.signals = []
        self.start_time = 0
        self.end_time = 200
        self.signal_height = 30
        self.top_margin = 30
        self.timescale_unit = ""
        self.highlighted_signal = None

        # Connect signals from child widgets.
        self.wave_view.cursorChanged.connect(self.update_values)
        self.wave_view.timeWindowChanged.connect(lambda s, e: self.update_values())
        self.wave_view.markersChanged.connect(self.update_averages)
        self.name_panel.representationChanged.connect(self.redraw)

    def eventFilter(self, obj, event):
        if obj == self.scroll_area.viewport() and event.type() in (QEvent.Resize, QEvent.Paint):
            self.update_overlays()
        return super().eventFilter(obj, event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_overlays()

    def update_overlays(self):
        pos = self.wave_view.mapTo(self.scroll_area.viewport(), QPoint(0, 0))
        self.wave_header_overlay.setGeometry(pos.x(), 0, self.wave_view.width(), self.wave_view.top_margin)
        fm = QFontMetrics(QFont("Courier", 10, QFont.Bold))
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

    def update_values(self, *args):
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

# -----------------------------------------------------------------------------
# WaveformNames (View): displays signal names and handles selection.
# -----------------------------------------------------------------------------
class WaveformNames(QWidget):
    representationChanged = Signal()

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
        if event.button() == Qt.LeftButton:
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
                if modifiers & Qt.ShiftModifier and self.last_clicked_index is not None:
                    start = min(self.last_clicked_index, index)
                    end = max(self.last_clicked_index, index)
                    for i in range(start, end + 1):
                        self.selected_signals.add(self.signals[i])
                elif modifiers & Qt.ControlModifier:
                    if clicked_signal in self.selected_signals:
                        self.selected_signals.remove(clicked_signal)
                    else:
                        self.selected_signals.add(clicked_signal)
                    self.last_clicked_index = index
                else:
                    self.selected_signals = {clicked_signal}
                    self.last_clicked_index = index
                self.update()
        elif event.button() == Qt.RightButton:
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
        self.representationChanged.emit()

    def _set_signal_height(self, factor, clicked_signal):
        targets = self.selected_signals if self.selected_signals else {clicked_signal}
        for s in targets:
            s.height_factor = factor
        self.representationChanged.emit()

    def _toggle_analog_render(self, clicked_signal):
        targets = self.selected_signals if self.selected_signals else {clicked_signal}
        for s in targets:
            s.analog_render = not s.analog_render
        self.representationChanged.emit()

    def _dump_signals(self, clicked_signal):
        targets = self.selected_signals if self.selected_signals else {clicked_signal}
        main_window = self.window()
        if hasattr(main_window, "dump_signals"):
            main_window.dump_signals(list(targets))

# -----------------------------------------------------------------------------
# WaveformValues (View): shows the current value for each signal.
# -----------------------------------------------------------------------------
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
        painter.setFont(QFont("Courier", 10, QFont.Bold))
        fm = QFontMetrics(painter.font())
        for (y, text) in self.values:
            text_width = fm.horizontalAdvance(text)
            painter.setPen(QColor("yellow"))
            painter.drawText(self.width() - text_width - 5, y + fm.ascent() / 2, text)
        painter.end()

# -----------------------------------------------------------------------------
# VCDViewer (Main Controller): creates the model, view and coordinates events.
# -----------------------------------------------------------------------------
class VCDViewer(QMainWindow):
    def __init__(self, vcd_filename):
        super().__init__()
        self.setWindowTitle("VCD Waveform Viewer")
        self.resize(1200, 600)
        self.state_manager = StateManager(self)
        self.model = WaveformModel(vcd_filename, self)
        self.vcd_filename = vcd_filename
        self.timescale = self.model.timescale
        self.timescale_unit = ''.join(c for c in self.timescale if not c.isdigit()).strip()
        self.tree_signal_map = {}
        self._create_menu()
        self._create_main_ui()
        # Global shortcut for search: use ApplicationShortcut so it works regardless of focus.
        self.search_shortcut = QShortcut(QKeySequence("F"), self)
        self.search_shortcut.setContext(Qt.ApplicationShortcut)
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
        main_splitter = QSplitter(Qt.Horizontal, self)
        self.setCentralWidget(main_splitter)
        left_frame = QWidget()
        left_layout = QVBoxLayout(left_frame)
        label = QLabel("DesignTree")
        label.setFont(QFont("Arial", 12, QFont.Bold))
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
        selected = self.wave_panel.name_panel.selected_signals
        if not selected:
            print("No signals selected for search.")
            return
        if self.search_window is not None:
            self.search_window.close()
        self.search_window = SearchWindow(list(selected), self)
        self.search_window.timestampFound.connect(self.on_timestamp_found)
        self.search_window.show()

    def on_timestamp_found(self, found_time):
        wave_view = self.wave_panel.wave_view
        current_window = wave_view.end_time - wave_view.start_time
        wave_view.set_time_window(found_time, found_time + current_window)
        wave_view.cursor_time = found_time
        wave_view.update()
        self.wave_panel.update_values()

    def add_signals_from_tree(self, signals):
        for sig in signals:
            self.wave_panel.add_signal(sig)

    def open_file(self):
        new_file, _ = QFileDialog.getOpenFileName(self, "Open VCD File", "", "VCD files (*.vcd);;All files (*)")
        if new_file:
            self.vcd_filename = new_file
            self.model = WaveformModel(self.vcd_filename, self)
            self.timescale = self.model.timescale
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
        self._build_filtered_tree(None, self.model.hierarchy, pattern)

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
            for sig in self.model.vcd_parser.signals.values():
                if sig.fullname == full_name:
                    self.wave_panel.add_signal(sig)
                    return

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Delete:
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
            self.state_manager.save_state(state, save_file)

    def load_state(self):
        load_file, _ = QFileDialog.getOpenFileName(self, "Load Application State", "", "JSON Files (*.json);;All Files (*)")
        if not load_file:
            return
        state = self.state_manager.load_state(load_file)
        if not state:
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
            for sig in self.model.vcd_parser.signals.values():
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
