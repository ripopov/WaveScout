#!/usr/bin/env python3
"""
VCD Viewer: An interactive waveform visualization and analysis tool.

This application follows an MVC/MVP design to decouple components using signals.
It supports VCD file parsing, waveform display (with customizable digital/analog views),
signal search by timestamp, and state saving/loading.

Modules:
    - vcd_parser: Provides VCDParser and related signal classes.
    - PySide6: Supplies the GUI components.
    - search_window: Provides the SearchWindow view for timestamp searching.
"""

import sys
import fnmatch
from vcd_parser import VCDParser, VCDSignal, dump_signals, numeric_value, convert_vector

from PySide6.QtCore import Qt, QRectF, QPoint, QEvent, Signal, QObject
from PySide6.QtGui import (QPainter, QPen, QBrush, QColor, QFont, QFontMetrics, QAction,
                           QGuiApplication, QKeySequence, QShortcut)
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                               QPushButton, QLabel, QLineEdit, QSplitter, QMenu, QAbstractItemView,
                               QTreeWidget, QTreeWidgetItem, QFileDialog, QScrollArea)

from search_window import SearchWindow
from state_manager import StateManager

# -----------------------------------------------------------------------------
# Helper drawing functions (used in multiple widgets)
# -----------------------------------------------------------------------------
def draw_timeline_header(painter, start_time, end_time, top_margin, text_font, width):
    painter.setPen(Qt.white)
    painter.drawLine(0, top_margin, width, top_margin)
    start_str, end_str = f"{start_time:.2f}", f"{end_time:.2f}"
    painter.drawText(5, top_margin - 5, start_str)
    fm = QFontMetrics(text_font)
    painter.drawText(width - fm.horizontalAdvance(end_str) - 5, top_margin - 5, end_str)

def draw_marker(painter, marker, label, start_time, end_time, top_margin, width):
    if marker is None or not (start_time <= marker <= end_time):
        return
    pixels_per_time = width / (end_time - start_time) if (end_time - start_time) else 1
    x = (marker - start_time) * pixels_per_time
    painter.setPen(QPen(Qt.yellow, 1))
    painter.drawLine(x, top_margin, x, painter.viewport().height())
    painter.drawText(QRectF(x - 15, 0, 30, top_margin), Qt.AlignCenter, label)

def draw_cursor(painter, cursor_time, start_time, end_time, top_margin, height, width):
    if cursor_time is None:
        return
    pixels_per_time = width / (end_time - start_time) if (end_time - start_time) else 1
    x = (cursor_time - start_time) * pixels_per_time
    painter.setPen(QPen(Qt.red, 1, Qt.DashLine))
    painter.drawLine(x, top_margin, x, height)

def draw_selection_rect(painter, sel_start, sel_end, top_margin, width, height):
    if sel_start is not None and sel_end is not None:
        x1, x2 = min(sel_start, sel_end), max(sel_start, sel_end)
        painter.fillRect(QRectF(x1, top_margin, x2 - x1, height - top_margin),
                         QBrush(QColor(0, 0, 255, 100)))


# =============================================================================
# WAVEFORM MODEL
# =============================================================================
class WaveformModel(QObject):
    """Encapsulates VCD file data: timescale, signals, and hierarchy."""
    def __init__(self, vcd_filename, parent=None):
        super().__init__(parent)
        self.vcd_filename = vcd_filename
        self.vcd_parser = VCDParser(vcd_filename)
        self.timescale = self.vcd_parser.parse() or "unknown"
        self.signals = list(self.vcd_parser.signals.values())
        self.hierarchy = self.vcd_parser.hierarchy


# =============================================================================
# WAVEFORM VIEW (VIEW)
# =============================================================================
class WaveformView(QWidget):
    """
    Custom widget to display waveform data.
    Handles panning, zooming, cursor and marker updates.
    """
    timeWindowChanged = Signal(float, float)
    cursorChanged = Signal(float)
    markersChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.signals = []
        self.start_time, self.end_time = 0, 200
        self.zoom_factor = 1.0

        self.signal_height = 30
        self.left_margin = 0
        self.top_margin = 30
        self.text_font = QFont("Courier", 10)
        self.value_font = QFont("Courier", 10, QFont.Bold)
        self.cursor_time = None
        self.highlighted_signal = None
        self.marker_A = None
        self.marker_B = None
        self.selection_start_x = self.selection_end_x = None
        self.selection_threshold = 10

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)
        painter.fillRect(self.rect(), QColor("black"))
        drawing_width, drawing_height = self.width(), self.height()
        time_span = self.end_time - self.start_time
        pixels_per_time = drawing_width / time_span if time_span else 1

        # Draw timeline header, selection, signals, cursor, markers, boundaries:
        draw_timeline_header(painter, self.start_time, self.end_time, self.top_margin, self.text_font, drawing_width)
        draw_selection_rect(painter, self.selection_start_x, self.selection_end_x, self.top_margin, drawing_width, drawing_height)
        self._draw_signals(painter, drawing_width, drawing_height, pixels_per_time)
        draw_cursor(painter, self.cursor_time, self.start_time, self.end_time, self.top_margin, drawing_height, drawing_width)
        draw_marker(painter, self.marker_A, "A", self.start_time, self.end_time, self.top_margin, drawing_width)
        draw_marker(painter, self.marker_B, "B", self.start_time, self.end_time, self.top_margin, drawing_width)
        self._draw_global_boundaries(painter, drawing_width, drawing_height, pixels_per_time)
        painter.end()

    def _draw_signals(self, painter, drawing_width, drawing_height, pixels_per_time):
        y = self.top_margin + 20
        for signal in self.signals:
            effective_height = self.signal_height * signal.height_factor
            if self.highlighted_signal == signal:
                painter.setPen(QPen(QColor("darkblue"), 1))
                painter.drawRect(0, y, drawing_width, effective_height)
            if signal.width > 1:
                (self._draw_analog_step(painter, signal, y, effective_height, drawing_width, pixels_per_time)
                 if signal.analog_render else
                 self._draw_vector_signal(painter, signal, y, effective_height, drawing_width, pixels_per_time))
            else:
                self._draw_digital_signal(painter, signal, y, effective_height, drawing_width, pixels_per_time)
            y += effective_height

    def _draw_global_boundaries(self, painter, width, height, pixels_per_time):
        global_min, global_max = self._get_global_range()
        if global_min is not None:
            if self.start_time >= global_min:
                x = 0 if self.start_time == global_min else (global_min - self.start_time) * pixels_per_time
                painter.setPen(QPen(Qt.red, 3 if self.start_time == global_min else 1))
                painter.drawLine(x, self.top_margin, x, height)
        if global_max is not None:
            if self.end_time <= global_max:
                x = width if self.end_time == global_max else (global_max - self.start_time) * pixels_per_time
                painter.setPen(QPen(Qt.red, 3 if self.end_time == global_max else 1))
                painter.drawLine(x, self.top_margin, x, height)

    def _get_global_range(self):
        global_min = global_max = None
        for s in self.signals:
            if s.transitions:
                t0, t1 = s.transitions[0][0], s.transitions[-1][0]
                global_min = t0 if global_min is None or t0 < global_min else global_min
                global_max = t1 if global_max is None or t1 > global_max else global_max
        return global_min, global_max

    def _value_to_y(self, val, base_y, effective_height):
        return base_y + 5 if val in ("1", "b1", "true") else base_y + effective_height - 5

    def _draw_digital_signal(self, painter, signal, base_y, effective_height, drawing_width, pixels_per_time):
        transitions = signal.transitions
        if not transitions:
            return
        last_val = next((v for t, v in transitions if t < self.start_time), "0")
        prev_x = 0
        prev_y = self._value_to_y(last_val, base_y, effective_height)
        for t, val in transitions:
            if not (self.start_time <= t <= self.end_time):
                continue
            x = (t - self.start_time) * pixels_per_time
            painter.setPen(QPen(QColor("cyan" if last_val == "1" else "lime"), 1))
            painter.drawLine(prev_x, prev_y, x, prev_y)
            new_y = self._value_to_y(val, base_y, effective_height)
            painter.setPen(QPen(QColor("lime"), 1))
            painter.drawLine(x, prev_y, x, new_y)
            prev_x, prev_y, last_val = x, new_y, val
        painter.setPen(QPen(QColor("cyan" if last_val == "1" else "lime"), 1))
        painter.drawLine(prev_x, prev_y, drawing_width, prev_y)

    def _draw_vector_signal(self, painter, signal, base_y, effective_height, drawing_width, pixels_per_time):
        transitions = signal.transitions
        if not transitions:
            return
        y_top, y_bottom = base_y + 5, base_y + effective_height - 5
        delta = 2
        last_val = next((v for t, v in transitions if t < self.start_time), "0")
        last_disp = convert_vector(last_val, signal.width, signal.rep_mode)
        segment_start = 0
        fm = QFontMetrics(self.text_font)
        char_width = fm.horizontalAdvance("0")
        for t, val in transitions:
            if not (self.start_time <= t <= self.end_time):
                continue
            x = (t - self.start_time) * pixels_per_time
            if val == last_val:
                continue
            rect_end = max(segment_start, x - delta)
            painter.setPen(QPen(QColor("cyan"), 1))
            painter.drawLine(segment_start, y_top, rect_end, y_top)
            painter.setPen(QPen(QColor("lime"), 1))
            painter.drawLine(segment_start, y_bottom, rect_end, y_bottom)
            if (block_width := rect_end - segment_start) >= char_width:
                text = last_disp if fm.horizontalAdvance(last_disp) <= block_width else last_disp[:max(1, int(block_width / char_width))]
                painter.drawText(QRectF(segment_start, y_top, block_width, effective_height - 10), Qt.AlignCenter, text)
            painter.drawLine(x - delta, y_top, x + delta, y_bottom)
            painter.drawLine(x - delta, y_bottom, x + delta, y_top)
            segment_start, last_val, last_disp = x + delta, val, convert_vector(val, signal.width, signal.rep_mode)
        rect_end = drawing_width
        painter.setPen(QPen(QColor("cyan"), 1))
        painter.drawLine(segment_start, y_top, rect_end, y_top)
        painter.setPen(QPen(QColor("lime"), 1))
        painter.drawLine(segment_start, y_bottom, rect_end, y_bottom)
        if (block_width := rect_end - segment_start) >= char_width:
            text = last_disp if fm.horizontalAdvance(last_disp) <= block_width else last_disp[:max(1, int(block_width / char_width))]
            painter.drawText(QRectF(segment_start, y_top, block_width, effective_height - 10), Qt.AlignCenter, text)

    def _draw_analog_step(self, painter, signal, base_y, effective_height, drawing_width, pixels_per_time):
        # Determine numeric range:
        nums = []
        for t, v in signal.transitions:
            try:
                nums.append(int(v, 2))
            except Exception:
                continue
        if not nums or (min_val := min(nums)) == (max_val := max(nums)):
            self._draw_digital_signal(painter, signal, base_y, effective_height, drawing_width, pixels_per_time)
            return

        def map_value(num):
            norm = (num - min_val) / (max_val - min_val)
            return base_y + effective_height - norm * effective_height

        segment_start = 0
        last_val = next((v for t, v in signal.transitions if t < self.start_time), "0")
        try:
            last_num = int(last_val, 2)
        except Exception:
            last_num = 0
        last_disp = convert_vector(last_val, signal.width, signal.rep_mode)
        painter.setFont(self.text_font)
        for t, v in signal.transitions:
            if not (self.start_time <= t <= self.end_time):
                continue
            x = (t - self.start_time) * pixels_per_time
            y_value = map_value(last_num)
            norm = (last_num - min_val) / (max_val - min_val)
            heat_color = QColor(int(norm * 255), 0, int((1 - norm) * 255))
            rect = QRectF(segment_start, base_y + effective_height, x - segment_start, - (base_y + effective_height - y_value))
            painter.fillRect(rect, heat_color)
            painter.setPen(QPen(Qt.yellow, 1))
            painter.drawLine(segment_start, y_value, x, y_value)
            segment_start = x + 1
            last_val = v
            try:
                last_num = int(last_val, 2)
            except Exception:
                last_num = 0
            last_disp = convert_vector(last_val, signal.width, signal.rep_mode)
        y_value = map_value(last_num)
        rect = QRectF(segment_start, base_y + effective_height, drawing_width - segment_start, - (base_y + effective_height - y_value))
        norm = (last_num - min_val) / (max_val - min_val)
        painter.fillRect(rect, QColor(int(norm * 255), 0, int((1 - norm) * 255)))
        text_rect = QRectF(segment_start, y_value, drawing_width - segment_start, base_y + effective_height - y_value)
        painter.setPen(QPen(Qt.white, 1))
        painter.drawText(text_rect, Qt.AlignCenter, last_disp)

    # --- Mouse & Wheel event handling ---
    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            self.cursor_time = None
            self.update()
            self.cursorChanged.emit(0)
        elif event.button() == Qt.LeftButton:
            self.selection_start_x = self.selection_end_x = event.position().x()
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
                x1, x2 = min(self.selection_start_x, self.selection_end_x), max(self.selection_start_x, self.selection_end_x)
                self.set_time_window(self.start_time + (x1 / pixels_per_time),
                                     self.start_time + (x2 / pixels_per_time))
            else:
                self._set_cursor_from_event(event)
            self.selection_start_x = self.selection_end_x = None
            self.update()

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if event.modifiers() & Qt.ControlModifier:
            self.zoom(1.1 if delta > 0 else 0.9)
        else:
            self.pan(-delta / 10)

    def _set_cursor_from_event(self, event):
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
        self.start_time, self.end_time = start, end
        self.timeWindowChanged.emit(start, end)
        self.update()

    def zoom(self, factor):
        window = self.end_time - self.start_time
        new_window = window / factor
        if self.cursor_time is not None:
            offset = self.cursor_time - self.start_time
            self.start_time = self.cursor_time - offset / factor
        self.end_time = self.start_time + new_window
        self.timeWindowChanged.emit(self.start_time, self.end_time)
        self.update()

    def pan(self, delta):
        if delta < 0 and self.start_time <= 0:
            return
        self.start_time = max(0, self.start_time + delta)
        self.end_time += delta
        self.timeWindowChanged.emit(self.start_time, self.end_time)
        self.update()

    def zoom_to_fit(self):
        if not self.signals:
            return
        min_time = min((s.transitions[0][0] for s in self.signals if s.transitions), default=self.start_time)
        max_time = max((s.transitions[-1][0] for s in self.signals if s.transitions), default=self.end_time)
        if min_time != max_time:
            self.set_time_window(min_time, max_time)

    def keyPressEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            if event.key() == Qt.Key_A and self.cursor_time is not None:
                self.marker_A = self.cursor_time
                self.markersChanged.emit()
                self.update()
            elif event.key() == Qt.Key_B and self.cursor_time is not None:
                self.marker_B = self.cursor_time
                self.markersChanged.emit()
                self.update()
        else:
            super().keyPressEvent(event)

    def get_value_at_time(self, signal, time):
        val = "0"
        for t, v in signal.transitions:
            if t <= time:
                val = v
            else:
                break
        return convert_vector(val, signal.width, signal.rep_mode) if signal.width > 1 else val


# =============================================================================
# WAVEFORM AVERAGES (VIEW)
# =============================================================================
class WaveformAverages(QWidget):
    """Displays marker information and computed signal averages."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.avg_data = []
        self.header = ""

    def set_data(self, header, data):
        self.header, self.avg_data = header, data
        self.update()

    def clear(self):
        self.header, self.avg_data = "", []
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("black"))
        painter.setFont(QFont("Courier", 10, QFont.Bold))
        fm = QFontMetrics(painter.font())
        painter.setPen(QColor("yellow"))
        painter.drawText(5, fm.ascent() + 2, self.header)
        for (y, avg_str) in self.avg_data:
            painter.drawText(self.width() - fm.horizontalAdvance(avg_str) - 5,
                             y + fm.ascent() / 2, avg_str)
        painter.end()


# =============================================================================
# OVERLAY HEADERS (VIEW)
# =============================================================================
class WaveformHeaderOverlay(QWidget):
    """Fixed overlay that draws the timeline header over the waveform view."""
    def __init__(self, parent, waveform_view):
        super().__init__(parent)
        self.waveform_view = waveform_view
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("black"))
        draw_timeline_header(painter,
                             self.waveform_view.start_time,
                             self.waveform_view.end_time,
                             self.waveform_view.top_margin,
                             self.waveform_view.text_font,
                             self.width())
        if self.waveform_view.cursor_time is not None:
            draw_cursor(painter, self.waveform_view.cursor_time,
                        self.waveform_view.start_time,
                        self.waveform_view.end_time,
                        self.waveform_view.top_margin,
                        self.height(), self.width())
        draw_marker(painter, self.waveform_view.marker_A, "A",
                    self.waveform_view.start_time,
                    self.waveform_view.end_time,
                    self.waveform_view.top_margin, self.width())
        draw_marker(painter, self.waveform_view.marker_B, "B",
                    self.waveform_view.start_time,
                    self.waveform_view.end_time,
                    self.waveform_view.top_margin, self.width())
        painter.end()


class AveragesHeaderOverlay(QWidget):
    """Fixed overlay that draws a header over the averages panel."""
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
        painter.setPen(QColor("yellow"))
        painter.drawText(5, fm.ascent() + 2, self.avg_panel.header)
        painter.end()


# =============================================================================
# WAVEFORM PANEL (CONTROLLER/VIEW CONTAINER)
# =============================================================================
class WaveformPanel(QWidget):
    """
    Composite widget that arranges the waveform view, names, values and averages.
    Connects child widget signals to coordinate view updates.
    """
    def __init__(self, parent=None, name_panel_width=150, value_panel_width=100, avg_panel_width=100):
        super().__init__(parent)
        self.name_panel = WaveformNames(self)
        self.wave_view = WaveformView(self)
        self.value_panel = WaveformValues(self)
        self.avg_panel = WaveformAverages(self)

        self.splitter = QSplitter(Qt.Horizontal)
        for widget, size in ((self.name_panel, name_panel_width),
                             (self.wave_view, 600),
                             (self.value_panel, value_panel_width),
                             (self.avg_panel, avg_panel_width)):
            self.splitter.addWidget(widget)
        self.splitter.setSizes([name_panel_width, 600, value_panel_width, avg_panel_width])

        self.content_widget = QWidget()
        clayout = QVBoxLayout(self.content_widget)
        clayout.setContentsMargins(0, 0, 0, 0)
        clayout.addWidget(self.splitter)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setWidget(self.content_widget)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.scroll_area)

        self.wave_header_overlay = WaveformHeaderOverlay(self.scroll_area.viewport(), self.wave_view)
        self.avg_header_overlay = AveragesHeaderOverlay(self.scroll_area.viewport(), self.avg_panel)
        self.scroll_area.viewport().installEventFilter(self)
        self.scroll_area.verticalScrollBar().valueChanged.connect(self.update_overlays)
        self.scroll_area.horizontalScrollBar().valueChanged.connect(self.update_overlays)

        self.signals = []
        self.top_margin = 30
        self.signal_height = 30
        self.highlighted_signal = None

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
        y = self.wave_view.top_margin + 20
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
        cursor = self.wave_view.cursor_time or self.wave_view.start_time
        for (signal, y, effective_height) in positions:
            val = self.wave_view.get_value_at_time(signal, cursor)
            self.value_panel.add_value(y + effective_height / 2, val)

    def update_averages(self):
        if self.wave_view.marker_A is None or self.wave_view.marker_B is None:
            self.avg_panel.clear()
            return
        A, B = sorted((self.wave_view.marker_A, self.wave_view.marker_B))
        header = f"A: {A:.2f} B: {B:.2f}"
        avg_data = []
        for (signal, y, effective_height) in self.get_signal_positions():
            avg_val = self.compute_average(signal, A, B)
            avg_data.append((y + effective_height / 2, f"{avg_val:.2f}"))
        self.avg_panel.set_data(header, avg_data)

    def compute_average(self, signal, A, B):
        total, duration = 0.0, B - A
        if duration <= 0:
            return 0.0
        transitions = signal.transitions
        current_val = next((v for t, v in transitions if t <= A), "0")
        current_time = A
        for t, v in transitions:
            if t < A:
                continue
            if t > B:
                break
            total += (t - current_time) * numeric_value(current_val)
            current_time, current_val = t, v
        if current_time < B:
            total += (B - current_time) * numeric_value(current_val)
        return total / duration

    def redraw(self):
        self.wave_view.top_margin = self.top_margin
        self.wave_view.highlighted_signal = self.highlighted_signal
        self.wave_view.update()
        self.name_panel.set_signals(self.signals, self.top_margin, self.signal_height, self.highlighted_signal)
        self.update_values()
        self.update_averages()
        total_height = self.wave_view.top_margin + 20 + sum(self.signal_height * s.height_factor for s in self.signals)
        self.content_widget.setMinimumHeight(total_height)
        self.update_overlays()


# =============================================================================
# WAVEFORM NAMES (VIEW)
# =============================================================================
class WaveformNames(QWidget):
    """
    Displays signal names and manages selection.
    Supports a context menu for changing representation, height, analog mode, and dumping data.
    """
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
        self.top_margin, self.signal_height = top_margin, signal_height
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

    def _signal_index_at(self, y_pos):
        y_acc = self.top_margin + 20
        for i, signal in enumerate(self.signals):
            if y_acc <= y_pos < y_acc + self.signal_height * signal.height_factor:
                return i
            y_acc += self.signal_height * signal.height_factor
        return None

    def mousePressEvent(self, event):
        index = self._signal_index_at(event.position().y())
        if index is None:
            return super().mousePressEvent(event)
        clicked_signal = self.signals[index]
        if event.button() == Qt.LeftButton:
            mods = event.modifiers()
            if mods & Qt.ShiftModifier and self.last_clicked_index is not None:
                start, end = sorted((self.last_clicked_index, index))
                for i in range(start, end + 1):
                    self.selected_signals.add(self.signals[i])
            elif mods & Qt.ControlModifier:
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
        for mode in [("Hex", "hex"), ("Bin", "bin"), ("Decimal", "decimal")]:
            action = QAction(mode[0], self)
            action.setCheckable(True)
            action.setChecked(signal.rep_mode == mode[1])
            action.triggered.connect(lambda checked, m=mode[1], s=signal: self._set_signal_representation(m, s))
            menu.addAction(action)
        action_toggle = QAction("Analog Step", self)
        action_toggle.setCheckable(True)
        action_toggle.setChecked(signal.analog_render)
        action_toggle.triggered.connect(lambda checked, s=signal: self._toggle_analog_render(s))
        menu.addAction(action_toggle)
        height_menu = QMenu("Set Height", self)
        for factor in [1, 2, 3, 4]:
            act = QAction(str(factor), self)
            act.setCheckable(True)
            act.setChecked(signal.height_factor == factor)
            act.triggered.connect(lambda checked, f=factor, s=signal: self._set_signal_height(f, s))
            height_menu.addAction(act)
        menu.addMenu(height_menu)
        action_dump = menu.addAction("Dump")
        action_dump.triggered.connect(lambda: self._dump_signals(signal))
        return menu

    def _set_signal_representation(self, mode, clicked_signal):
        targets = self.selected_signals or {clicked_signal}
        for s in targets:
            s.rep_mode = mode
        self.representationChanged.emit()

    def _set_signal_height(self, factor, clicked_signal):
        targets = self.selected_signals or {clicked_signal}
        for s in targets:
            s.height_factor = factor
        self.representationChanged.emit()

    def _toggle_analog_render(self, clicked_signal):
        targets = self.selected_signals or {clicked_signal}
        for s in targets:
            s.analog_render = not s.analog_render
        self.representationChanged.emit()

    def _dump_signals(self, clicked_signal):
        targets = self.selected_signals or {clicked_signal}
        main_window = self.window()
        if hasattr(main_window, "dump_signals"):
            main_window.dump_signals(list(targets))


# =============================================================================
# WAVEFORM VALUES (VIEW)
# =============================================================================
class WaveformValues(QWidget):
    """Displays the current value of each signal at the cursor time."""
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
            painter.setPen(QColor("yellow"))
            painter.drawText(self.width() - fm.horizontalAdvance(text) - 5, y + fm.ascent() / 2, text)
        painter.end()


# =============================================================================
# VCD VIEWER (MAIN CONTROLLER)
# =============================================================================
class VCDViewer(QMainWindow):
    """
    Main application window that creates the model and integrates all views.
    Manages file operations, state saving/loading, and user interactions.
    """
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

        self.search_shortcut = QShortcut(QKeySequence("F"), self)
        self.search_shortcut.setContext(Qt.ApplicationShortcut)
        self.search_shortcut.activated.connect(self.open_search_window)
        self.search_window = None

    def _create_menu(self):
        menubar = self.menuBar()
        filemenu = menubar.addMenu("File")
        for label, handler in (("Open...", self.open_file),
                               ("Save State", self.save_state),
                               ("Load State", self.load_state),
                               ("Exit", self.close)):
            action = QAction(label, self)
            action.triggered.connect(handler)
            filemenu.addAction(action)
        filemenu.addSeparator()

    def _create_main_ui(self):
        main_splitter = QSplitter(Qt.Horizontal, self)
        self.setCentralWidget(main_splitter)

        from design_explorer import DesignExplorer
        self.design_explorer = DesignExplorer(self)
        self.design_explorer.set_hierarchy(self.model.hierarchy)
        self.design_explorer.signalsToAdd.connect(self.add_signals_from_tree)
        self.design_explorer.tree.itemDoubleClicked.connect(self.on_tree_double_click)
        main_splitter.addWidget(self.design_explorer)

        right_frame = QWidget()
        rlayout = QVBoxLayout(right_frame)
        self.wave_panel = WaveformPanel(name_panel_width=150, value_panel_width=100, avg_panel_width=100)
        rlayout.addWidget(self.wave_panel, 1)
        control_frame = QWidget()
        ctrl_layout = QHBoxLayout(control_frame)
        for label, handler in (("<< Pan Left", lambda: self.wave_panel.wave_view.pan(-50)),
                               ("Pan Right >>", lambda: self.wave_panel.wave_view.pan(50)),
                               ("Zoom In", lambda: self.wave_panel.wave_view.zoom(1.5)),
                               ("Zoom Out", lambda: self.wave_panel.wave_view.zoom(1 / 1.5)),
                               ("Zoom to Fit", self.wave_panel.wave_view.zoom_to_fit)):
            btn = QPushButton(label)
            btn.clicked.connect(handler)
            ctrl_layout.addWidget(btn)
        ctrl_layout.addStretch()
        ctrl_layout.addWidget(QLabel(f"Timescale: {self.timescale}"))
        rlayout.addWidget(control_frame)
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
            self.tree_signal_map.clear()
            self.rebuild_tree()
            self.wave_panel.wave_view.clear()
            self.wave_panel.signals = []
            self.wave_panel.redraw()

    def rebuild_tree(self):
        pattern = self.filter_entry.text().strip() if hasattr(self, "filter_entry") else ""
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
                    leaf = QTreeWidgetItem(parent_item if parent_item else self.tree, [signal.name])
                    self.tree.signal_map[leaf] = signal
                    self.tree_signal_map[leaf] = signal
                    leaf.setForeground(0, QColor("red" if self._is_dynamic(signal) else "gray"))
            else:
                node = QTreeWidgetItem(parent_item if parent_item else self.tree, [key])
                node.setExpanded(True)
                self._build_filtered_tree(node, subtree, pattern)

    def _is_dynamic(self, signal):
        return bool(signal.transitions and len({v for _, v in signal.transitions}) > 1)

    def on_tree_double_click(self, item, column):
        if item.childCount() > 0:
            return
        if item in self.design_explorer.tree.signal_map:
            self.wave_panel.add_signal(self.design_explorer.tree.signal_map[item])
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
            selected = self.wave_panel.name_panel.selected_signals
            if selected:
                for sig in list(selected):
                    if sig in self.wave_panel.signals:
                        self.wave_panel.remove_signal(sig)
                self.wave_panel.name_panel.selected_signals.clear()
                self.wave_panel.highlighted_signal = None
                self.wave_panel.redraw()
            elif self.wave_panel.highlighted_signal in self.wave_panel.signals:
                self.wave_panel.remove_signal(self.wave_panel.highlighted_signal)
                self.wave_panel.highlighted_signal = None
                self.wave_panel.redraw()
        else:
            super().keyPressEvent(event)

    def save_state(self):
        state = {
            "vcd_filename": self.vcd_filename,
            "signals": [{
                "fullname": sig.fullname,
                "rep_mode": sig.rep_mode,
                "height_factor": sig.height_factor,
                "analog_render": sig.analog_render
            } for sig in self.wave_panel.signals],
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
        if saved_vcd and saved_vcd != self.vcd_filename:
            print("Warning: saved state is from a different VCD file. Only signals with matching names will be restored.")
        self.wave_panel.signals = []
        self.wave_panel.wave_view.clear()
        for sig_data in state.get("signals", []):
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
        self.wave_panel.wave_view.cursor_time = state.get("cursor_time")
        self.wave_panel.wave_view.marker_A = state.get("marker_A")
        self.wave_panel.wave_view.marker_B = state.get("marker_B")
        self.wave_panel.redraw()

    def dump_signals(self, signals):
        dump_signals(signals, self.timescale)


if __name__ == "__main__":
    vcd_filename = "jtag.vcd"
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    viewer = VCDViewer(vcd_filename)
    viewer.show()
    sys.exit(app.exec())
