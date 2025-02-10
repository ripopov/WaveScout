#!/usr/bin/env python3
"""
wavescout.py
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
from contextlib import contextmanager
from typing import List, Tuple, Optional, Dict, Any

from vcd_parser import VCDParser, VCDSignal, dump_signals, numeric_value, convert_vector

from PySide6.QtCore import Qt, QRectF, QPoint, QEvent, Signal, QObject, QThread
from PySide6.QtGui import (QPainter, QPen, QBrush, QColor, QFont, QFontMetrics,
                           QAction, QGuiApplication, QKeySequence, QShortcut, QImage)
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                               QPushButton, QLabel, QSplitter, QMenu, QTreeWidget, QTreeWidgetItem,
                               QFileDialog, QScrollArea, QProgressBar)

from search_window import SearchWindow
from state_manager import StateManager

# ---------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------
DEFAULT_TOP_MARGIN = 30
DEFAULT_TEXT_FONT = QFont("Courier", 10)
DEFAULT_SIGNAL_HEIGHT = 30
NAME_PANEL_WIDTH = 150
VALUE_PANEL_WIDTH = 100
AVG_PANEL_WIDTH = 100
DEFAULT_WAVE_VIEW_WIDTH = 600

# ---------------------------------------------------------------------
# A context manager for QPainter to simplify cleanup.
# ---------------------------------------------------------------------
@contextmanager
def qpainter(widget_or_device) -> QPainter:
    painter = QPainter(widget_or_device)
    try:
        yield painter
    finally:
        painter.end()

# ---------------------------------------------------------------------
# Helper drawing functions (interactive elements drawn online)
# ---------------------------------------------------------------------
def draw_timeline_header(painter: QPainter, start_time: float, end_time: float, width: float) -> None:
    painter.setPen(Qt.GlobalColor.white)
    painter.drawLine(0, DEFAULT_TOP_MARGIN, width, DEFAULT_TOP_MARGIN)
    start_str, end_str = f"{start_time:.2f}", f"{end_time:.2f}"
    painter.drawText(5, DEFAULT_TOP_MARGIN - 5, start_str)
    fm = QFontMetrics(DEFAULT_TEXT_FONT)
    painter.drawText(width - fm.horizontalAdvance(end_str) - 5, DEFAULT_TOP_MARGIN - 5, end_str)

def draw_marker(painter: QPainter, marker: Optional[float], label: str,
                start_time: float, end_time: float, width: float) -> None:
    if marker is None or not (start_time <= marker <= end_time):
        return
    time_span = end_time - start_time
    pixels_per_time = width / time_span if time_span else 1
    x = (marker - start_time) * pixels_per_time
    painter.setPen(QPen(Qt.GlobalColor.yellow, 1))
    painter.drawLine(x, DEFAULT_TOP_MARGIN, x, painter.viewport().height())
    painter.drawText(QRectF(x - 15, 0, 30, DEFAULT_TOP_MARGIN), Qt.AlignmentFlag.AlignCenter, label)

def draw_cursor(painter: QPainter, cursor_time: Optional[float],
                start_time: float, end_time: float, height: float, width: float) -> None:
    if cursor_time is None:
        return
    time_span = end_time - start_time
    pixels_per_time = width / time_span if time_span else 1
    x = (cursor_time - start_time) * pixels_per_time
    painter.setPen(QPen(Qt.GlobalColor.red, 1, Qt.PenStyle.DashLine))
    painter.drawLine(x, DEFAULT_TOP_MARGIN, x, height)

def draw_selection_rect(painter: QPainter, sel_start: Optional[float],
                        sel_end: Optional[float], width: float, height: float) -> None:
    if sel_start is not None and sel_end is not None:
        x1, x2 = min(sel_start, sel_end), max(sel_start, sel_end)
        rect = QRectF(x1, DEFAULT_TOP_MARGIN, x2 - x1, height - DEFAULT_TOP_MARGIN)
        # Fill with semi-transparent blue.
        painter.fillRect(rect, QBrush(QColor(0, 0, 255, 100)))
        # Draw a yellow dashed border.
        painter.setPen(QPen(QColor("yellow"), 2, Qt.DashLine))
        painter.drawRect(rect)

# =============================================================================
# VCD LOADER WORKER (asynchronous parsing)
# =============================================================================
class VCDLoaderWorker(QObject):
    finished = Signal(object)  # Emits the loaded WaveformModel instance

    def __init__(self, vcd_filename: str) -> None:
        super().__init__()
        self.vcd_filename = vcd_filename

    def run(self) -> None:
        model = WaveformModel(self.vcd_filename)
        self.finished.emit(model)

# =============================================================================
# WAVEFORM MODEL
# =============================================================================
class WaveformModel(QObject):
    """Encapsulates VCD file data: timescale, signals, and hierarchy."""
    def __init__(self, vcd_filename: str, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self.vcd_filename: str = vcd_filename
        self.vcd_parser = VCDParser(vcd_filename)
        self.timescale: str = self.vcd_parser.parse() or "unknown"
        self.signals: List[VCDSignal] = list(self.vcd_parser.signals.values())
        self.hierarchy: Dict[str, Any] = self.vcd_parser.hierarchy

# =============================================================================
# WAVEFORM RENDER WORKER (offline rendering of signal traces only)
# =============================================================================
class WaveformRenderWorker(QObject):
    """
    Renders only the signal traces (expensive to compute) into an off-screen QImage.
    Interactive elements (timeline header, cursor, markers, selection) are drawn online.
    """
    finished = Signal(QImage, dict)  # Emits the QImage and the render parameters used

    def __init__(self, params: dict, signals: List[VCDSignal], top_margin: int, signal_height: int) -> None:
        super().__init__()
        self.params = params  # Contains: width, height, start_time, end_time
        self.signals = signals
        self.top_margin = top_margin
        self.signal_height = signal_height
        self._canceled = False

    def cancel(self):
        self._canceled = True

    def run(self):
        width = self.params.get('width', 600)
        height = self.params.get('height', 400)
        start_time = self.params.get('start_time', 0)
        end_time = self.params.get('end_time', 200)
        # Create an off-screen QImage and paint only the signal traces.
        image = QImage(width, height, QImage.Format.Format_ARGB32)
        image.fill(QColor("black"))
        with qpainter(image) as painter:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
            time_span = end_time - start_time
            pixels_per_time = width / time_span if time_span else 1
            y = self.top_margin + 20
            for signal in self.signals:
                if self._canceled:
                    return  # Cancel early if requested.
                effective_height = self.signal_height * signal.height_factor
                if signal.width > 1:
                    if signal.analog_render:
                        self._draw_analog_step(painter, signal, y, effective_height, width, pixels_per_time, start_time)
                    else:
                        self._draw_vector_signal(painter, signal, y, effective_height, width, pixels_per_time, start_time)
                else:
                    self._draw_digital_signal(painter, signal, y, effective_height, width, pixels_per_time, start_time)
                y += effective_height
        self.finished.emit(image, self.params)

    def _value_to_y(self, val: str, base_y: float, effective_height: float) -> float:
        return base_y + 5 if val in ("1", "b1", "true") else base_y + effective_height - 5

    def _draw_digital_signal(self, painter: QPainter, signal: VCDSignal, base_y: float,
                               effective_height: float, drawing_width: float,
                               pixels_per_time: float, start_time: float) -> None:
        transitions = signal.transitions
        if not transitions:
            return
        last_val = next((v for t, v in reversed(transitions) if t <= start_time),
                        transitions[0][1])
        prev_x = 0
        prev_y = self._value_to_y(last_val, base_y, effective_height)
        high_brush = QBrush(QColor(0, 100, 0, 128))
        for t, val in transitions:
            if not (start_time <= t <= self.params.get('end_time')):
                continue
            x = (t - start_time) * pixels_per_time
            if last_val in ("1", "b1", "true"):
                rect = QRectF(prev_x, base_y + 5, x - prev_x, effective_height - 10)
                painter.fillRect(rect, high_brush)
            painter.setPen(QPen(QColor("cyan") if last_val == "1" else QColor("lime"), 1))
            painter.drawLine(prev_x, prev_y, x, prev_y)
            new_y = self._value_to_y(val, base_y, effective_height)
            painter.setPen(QPen(QColor("lime"), 1))
            painter.drawLine(x, prev_y, x, new_y)
            prev_x, prev_y, last_val = x, new_y, val
        if last_val in ("1", "b1", "true"):
            rect = QRectF(prev_x, base_y + 5, drawing_width - prev_x, effective_height - 10)
            painter.fillRect(rect, high_brush)
        painter.setPen(QPen(QColor("cyan") if last_val == "1" else QColor("lime"), 1))
        painter.drawLine(prev_x, prev_y, drawing_width, prev_y)

    def _draw_vector_signal(self, painter: QPainter, signal: VCDSignal, base_y: float,
                              effective_height: float, drawing_width: float,
                              pixels_per_time: float, start_time: float) -> None:
        transitions = signal.transitions
        if not transitions:
            return
        y_top, y_bottom = base_y + 5, base_y + effective_height - 5
        delta = 2
        last_val = next((v for t, v in reversed(transitions) if t <= start_time),
                        transitions[0][1])
        last_disp = convert_vector(last_val, signal.width, signal.rep_mode)
        segment_start = 0
        painter.save()
        painter.setFont(DEFAULT_TEXT_FONT)
        fm = QFontMetrics(DEFAULT_TEXT_FONT)
        char_width = fm.horizontalAdvance("0")
        for t, val in transitions:
            if not (start_time <= t <= self.params.get('end_time')):
                continue
            x = (t - start_time) * pixels_per_time
            if val == last_val:
                continue
            rect_end = max(segment_start, x - delta)
            painter.setPen(QPen(QColor("cyan"), 1))
            painter.drawLine(segment_start, y_top, rect_end, y_top)
            painter.setPen(QPen(QColor("lime"), 1))
            painter.drawLine(segment_start, y_bottom, rect_end, y_bottom)
            block_width = rect_end - segment_start
            if block_width >= char_width:
                text = (last_disp if fm.horizontalAdvance(last_disp) <= block_width
                        else last_disp[:max(1, int(block_width / char_width))])
                painter.drawText(QRectF(segment_start, y_top, block_width, effective_height - 10),
                                 Qt.AlignmentFlag.AlignCenter, text)
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
            text = (last_disp if fm.horizontalAdvance(last_disp) <= block_width
                    else last_disp[:max(1, int(block_width / char_width))])
            painter.drawText(QRectF(segment_start, y_top, block_width, effective_height - 10),
                             Qt.AlignmentFlag.AlignCenter, text)
        painter.restore()

    def _draw_analog_step(self, painter: QPainter, signal: VCDSignal, base_y: float,
                           effective_height: float, drawing_width: float,
                           pixels_per_time: float, start_time: float) -> None:
        nums = []
        for t, v in signal.transitions:
            try:
                nums.append(int(v, 2))
            except Exception:
                continue
        if not nums or ((min_val := min(nums)) == (max_val := max(nums))):
            self._draw_digital_signal(painter, signal, base_y, effective_height, drawing_width, pixels_per_time, start_time)
            return

        def map_value(num: int) -> float:
            norm = (num - min_val) / (max_val - min_val)
            return base_y + effective_height - norm * effective_height

        last_val = next((v for t, v in reversed(signal.transitions) if t <= start_time),
                        signal.transitions[0][1] if signal.transitions else "0")
        try:
            last_num = int(last_val, 2)
        except Exception:
            last_num = 0
        last_disp = convert_vector(last_val, signal.width, signal.rep_mode)
        segment_start = 0
        y_old = map_value(last_num)
        epsilon = 1.0
        painter.save()
        painter.setFont(DEFAULT_TEXT_FONT)
        for t, v in signal.transitions:
            if not (start_time <= t <= self.params.get('end_time')):
                continue
            x = (t - start_time) * pixels_per_time
            norm = (last_num - min_val) / (max_val - min_val)
            heat_color = QColor(int(norm * 255), 0, int((1 - norm) * 255))
            rect = QRectF(segment_start, base_y + effective_height, x - segment_start + epsilon, - (base_y + effective_height - y_old))
            painter.fillRect(rect, heat_color)
            painter.setPen(QPen(Qt.GlobalColor.yellow, 1))
            painter.drawLine(segment_start, y_old, x, y_old)
            try:
                new_num = int(v, 2)
            except Exception:
                new_num = 0
            y_new = map_value(new_num)
            painter.drawLine(x, y_old, x, y_new)
            segment_start = x
            last_num = new_num
            last_disp = convert_vector(v, signal.width, signal.rep_mode)
            y_old = y_new
        norm = (last_num - min_val) / (max_val - min_val)
        heat_color = QColor(int(norm * 255), 0, int((1 - norm) * 255))
        rect = QRectF(segment_start, base_y + effective_height, drawing_width - segment_start + epsilon, - (base_y + effective_height - y_old))
        painter.fillRect(rect, heat_color)
        painter.drawLine(segment_start, y_old, drawing_width, y_old)
        text_rect = QRectF(segment_start, y_old, drawing_width - segment_start, base_y + effective_height - y_old)
        painter.setPen(QPen(Qt.GlobalColor.white, 1))
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, last_disp)
        painter.restore()

# =============================================================================
# WAVEFORM VIEW (online drawing of interactive elements)
# =============================================================================
class WaveformView(QWidget):
    """
    Custom widget to display waveform data.
    Interactive elements (timeline header, cursor, markers, selection, global boundaries)
    are drawn online. Only signal traces are rendered offline.
    """
    timeWindowChanged = Signal(float, float)
    cursorChanged = Signal(float)
    markersChanged = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.signals: List[VCDSignal] = []
        self.start_time: float = 0
        self.end_time: float = 200
        self.signal_height: int = DEFAULT_SIGNAL_HEIGHT
        self.top_margin: int = DEFAULT_TOP_MARGIN
        self.text_font: QFont = DEFAULT_TEXT_FONT
        self.cursor_time: Optional[float] = None
        self.marker_A: Optional[float] = None
        self.marker_B: Optional[float] = None
        self.selection_start_x: Optional[float] = None
        self.selection_end_x: Optional[float] = None
        self.selection_threshold: int = 10

        # Offline rendering of signal traces.
        self._offscreen_image: Optional[QImage] = None
        self._render_params: dict = {}
        self._render_thread: Optional[QThread] = None
        self._render_worker: Optional[WaveformRenderWorker] = None

    def paintEvent(self, event) -> None:
        with qpainter(self) as painter:
            # Draw the offline image (signal traces) if available.
            if self._offscreen_image is not None:
                painter.drawImage(0, 0, self._offscreen_image)
            else:
                painter.fillRect(self.rect(), QColor("black"))
            # Overlay interactive elements drawn live.
            draw_timeline_header(painter, self.start_time, self.end_time, self.width())
            draw_selection_rect(painter, self.selection_start_x, self.selection_end_x, self.width(), self.height())
            draw_cursor(painter, self.cursor_time, self.start_time, self.end_time, self.height(), self.width())
            draw_marker(painter, self.marker_A, "A", self.start_time, self.end_time, self.width())
            draw_marker(painter, self.marker_B, "B", self.start_time, self.end_time, self.width())
            # Draw global boundaries online.
            global_min, global_max = self._get_global_range_online()
            time_span = self.end_time - self.start_time
            pixels_per_time = self.width() / time_span if time_span else 1
            if global_min is not None and self.start_time <= global_min <= self.end_time:
                x = 0 if self.start_time == global_min else (global_min - self.start_time) * pixels_per_time
                pen_width = 3 if self.start_time == global_min else 1
                painter.setPen(QPen(Qt.GlobalColor.red, pen_width))
                painter.drawLine(x, self.top_margin, x, self.height())
            if global_max is not None and self.start_time <= global_max <= self.end_time:
                x = self.width() if self.end_time == global_max else (global_max - self.start_time) * pixels_per_time
                pen_width = 3 if self.end_time == global_max else 1
                painter.setPen(QPen(Qt.GlobalColor.red, pen_width))
                painter.drawLine(x, self.top_margin, x, self.height())

    def _get_global_range_online(self) -> Tuple[Optional[float], Optional[float]]:
        global_min: Optional[float] = None
        global_max: Optional[float] = None
        for s in self.signals:
            if s.transitions:
                t0, t1 = s.transitions[0][0], s.transitions[-1][0]
                global_min = t0 if global_min is None or t0 < global_min else global_min
                global_max = t1 if global_max is None or t1 > global_max else global_max
        return global_min, global_max

    def _current_render_params(self) -> dict:
        return {
            'width': self.width(),
            'height': self.height(),
            'start_time': self.start_time,
            'end_time': self.end_time,
        }

    def schedule_rendering(self) -> None:
        if self._render_worker is not None:
            self._render_worker.cancel()
        if self._render_thread is not None:
            try:
                self._render_thread.quit()
                self._render_thread.wait()
            except RuntimeError:
                pass
            self._render_thread = None
        cur_params = self._current_render_params()
        self._render_params = cur_params
        main_window = self.window()
        if hasattr(main_window, 'progressBar'):
            main_window.progressBar.setRange(0, 0)
            main_window.progressBar.setVisible(True)
        self._render_thread = QThread()
        self._render_worker = WaveformRenderWorker(cur_params, self.signals, self.top_margin, self.signal_height)
        self._render_worker.moveToThread(self._render_thread)
        self._render_thread.started.connect(self._render_worker.run)
        self._render_worker.finished.connect(self._on_render_finished)
        self._render_worker.finished.connect(self._render_thread.quit)
        self._render_worker.finished.connect(self._render_worker.deleteLater)
        self._render_thread.finished.connect(lambda: setattr(self, "_render_thread", None))
        self._render_thread.start()

    def _on_render_finished(self, image: QImage, params: dict) -> None:
        if params == self._current_render_params():
            self._offscreen_image = image
            self._render_params = params
            self.update()
        main_window = self.window()
        if hasattr(main_window, 'progressBar'):
            main_window.progressBar.setRange(0, 100)
            main_window.progressBar.setValue(100)
            main_window.progressBar.setVisible(False)

    def set_time_window(self, start: float, end: float) -> None:
        self.start_time, self.end_time = start, end
        self.timeWindowChanged.emit(start, end)
        self.schedule_rendering()

    def zoom(self, factor: float) -> None:
        window = self.end_time - self.start_time
        new_window = window / factor
        if self.cursor_time is not None:
            offset = self.cursor_time - self.start_time
            self.start_time = self.cursor_time - offset / factor
        self.end_time = self.start_time + new_window
        self.timeWindowChanged.emit(self.start_time, self.end_time)
        self.schedule_rendering()

    def pan(self, delta: float) -> None:
        if delta < 0 and self.start_time <= 0:
            return
        self.start_time = max(0, self.start_time + delta)
        self.end_time += delta
        self.timeWindowChanged.emit(self.start_time, self.end_time)
        self.schedule_rendering()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.schedule_rendering()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.RightButton:
            self.cursor_time = None
            self.schedule_rendering()
            self.cursorChanged.emit(0)
        elif event.button() == Qt.MouseButton.LeftButton:
            # Start selection drag; update interactive overlay but do not schedule offline rendering yet.
            self.selection_start_x = self.selection_end_x = event.position().x()
            self.update()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self.selection_start_x is not None:
            # While dragging, update selection rectangle and call update() to refresh overlay.
            self.selection_end_x = event.position().x()
            self.update()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
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
            # Now that selection is finalized, schedule an offline render.
            self.schedule_rendering()
        else:
            super().mouseReleaseEvent(event)

    def wheelEvent(self, event) -> None:
        delta = event.angleDelta().y()
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.zoom(1.1 if delta > 0 else 0.9)
        else:
            self.pan(-delta / 10)

    def _set_cursor_from_event(self, event) -> None:
        drawing_width = self.width()
        time_span = self.end_time - self.start_time
        pixels_per_time = drawing_width / time_span if time_span else 1
        self.cursor_time = self.start_time + event.position().x() / pixels_per_time
        self.cursorChanged.emit(self.cursor_time)
        self.schedule_rendering()

    def add_signal(self, signal: VCDSignal) -> None:
        if signal not in self.signals:
            self.signals.append(signal)
            self.schedule_rendering()

    def clear(self) -> None:
        self.signals = []
        self._offscreen_image = None
        self.schedule_rendering()

    def keyPressEvent(self, event) -> None:
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if event.key() == Qt.Key.Key_A and self.cursor_time is not None:
                self.marker_A = self.cursor_time
                self.markersChanged.emit()
                self.schedule_rendering()
            elif event.key() == Qt.Key.Key_B and self.cursor_time is not None:
                self.marker_B = self.cursor_time
                self.markersChanged.emit()
                self.schedule_rendering()
        else:
            super().keyPressEvent(event)

    def get_value_at_time(self, signal: VCDSignal, time: float) -> str:
        val = "0"
        for t, v in signal.transitions:
            if t <= time:
                val = v
            else:
                break
        return convert_vector(val, signal.width, signal.rep_mode) if signal.width > 1 else val

    def zoom_to_fit(self) -> None:
        if not self.signals:
            return
        min_time = min((s.transitions[0][0] for s in self.signals if s.transitions), default=self.start_time)
        max_time = max((s.transitions[-1][0] for s in self.signals if s.transitions), default=self.end_time)
        if min_time != max_time:
            self.set_time_window(min_time, max_time)

# =============================================================================
# WAVEFORM AVERAGES (VIEW)
# =============================================================================
class WaveformAverages(QWidget):
    """Displays marker information and computed signal averages."""
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.avg_data: List[Tuple[float, str]] = []
        self.header: str = ""

    def set_data(self, header: str, data: List[Tuple[float, str]]) -> None:
        self.header, self.avg_data = header, data
        self.update()

    def clear(self) -> None:
        self.header, self.avg_data = "", []
        self.update()

    def paintEvent(self, event) -> None:
        with qpainter(self) as painter:
            painter.fillRect(self.rect(), QColor("black"))
            painter.setFont(QFont("Courier", 10, QFont.Weight.Bold))
            fm = QFontMetrics(painter.font())
            painter.setPen(QColor("yellow"))
            painter.drawText(5, fm.ascent() + 2, self.header)
            for (y, avg_str) in self.avg_data:
                painter.drawText(self.width() - fm.horizontalAdvance(avg_str) - 5,
                                 y + fm.ascent() / 2, avg_str)

# =============================================================================
# OVERLAY HEADERS (VIEW)
# =============================================================================
class WaveformHeaderOverlay(QWidget):
    """Fixed overlay that draws the timeline header over the waveform view."""
    def __init__(self, parent: QWidget, waveform_view: WaveformView) -> None:
        super().__init__(parent)
        self.waveform_view = waveform_view
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def paintEvent(self, event) -> None:
        with qpainter(self) as painter:
            painter.fillRect(self.rect(), QColor("black"))
            draw_timeline_header(painter,
                                 self.waveform_view.start_time,
                                 self.waveform_view.end_time,
                                 self.width())

class AveragesHeaderOverlay(QWidget):
    """Fixed overlay that draws a header over the averages panel."""
    def __init__(self, parent: QWidget, avg_panel: WaveformAverages) -> None:
        super().__init__(parent)
        self.avg_panel = avg_panel
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def paintEvent(self, event) -> None:
        with qpainter(self) as painter:
            painter.fillRect(self.rect(), QColor("black"))
            painter.setFont(QFont("Courier", 10, QFont.Weight.Bold))
            fm = QFontMetrics(painter.font())
            painter.setPen(QColor("yellow"))
            painter.drawText(5, fm.ascent() + 2, self.avg_panel.header)

# =============================================================================
# WAVEFORM PANEL (VIEW CONTAINER)
# =============================================================================
class WaveformPanel(QWidget):
    """
    Composite widget that arranges the waveform view, names, values, and averages.
    Connects child widget signals to coordinate view updates.
    """
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        from design_explorer import DesignExplorer  # local import

        self.name_panel = WaveformNames(self)
        self.wave_view = WaveformView(self)
        self.value_panel = WaveformValues(self)
        self.avg_panel = WaveformAverages(self)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        for widget, size in ((self.name_panel, NAME_PANEL_WIDTH),
                             (self.value_panel, VALUE_PANEL_WIDTH),
                             (self.wave_view, DEFAULT_WAVE_VIEW_WIDTH),
                             (self.avg_panel, AVG_PANEL_WIDTH)):
            self.splitter.addWidget(widget)
        self.splitter.setSizes([NAME_PANEL_WIDTH, VALUE_PANEL_WIDTH, DEFAULT_WAVE_VIEW_WIDTH, AVG_PANEL_WIDTH])

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

        self.signals: List[VCDSignal] = []
        self.top_margin: int = DEFAULT_TOP_MARGIN
        self.signal_height: int = DEFAULT_SIGNAL_HEIGHT

        self.wave_view.cursorChanged.connect(self.update_values)
        self.wave_view.timeWindowChanged.connect(lambda s, e: self.update_values())
        self.wave_view.markersChanged.connect(self.update_averages)
        self.name_panel.representationChanged.connect(self.redraw)

    def eventFilter(self, obj, event) -> bool:
        if obj == self.scroll_area.viewport() and event.type() in (QEvent.Type.Resize, QEvent.Type.Paint):
            self.update_overlays()
        return super().eventFilter(obj, event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.update_overlays()

    def update_overlays(self) -> None:
        pos = self.wave_view.mapTo(self.scroll_area.viewport(), QPoint(0, 0))
        self.wave_header_overlay.setGeometry(pos.x(), 0, self.wave_view.width(), self.wave_view.top_margin)
        fm = QFontMetrics(QFont("Courier", 10, QFont.Weight.Bold))
        avg_header_height = fm.height() + 4
        pos2 = self.avg_panel.mapTo(self.scroll_area.viewport(), QPoint(0, 0))
        self.avg_header_overlay.setGeometry(pos2.x(), 0, self.avg_panel.width(), avg_header_height)
        self.wave_header_overlay.update()
        self.avg_header_overlay.update()

    def get_signal_positions(self) -> List[Tuple[VCDSignal, float, float]]:
        positions: List[Tuple[VCDSignal, float, float]] = []
        y = self.wave_view.top_margin + 20
        for signal in self.signals:
            effective_height = self.signal_height * signal.height_factor
            positions.append((signal, y, effective_height))
            y += effective_height
        return positions

    def add_signal(self, signal: VCDSignal) -> None:
        if signal not in self.signals:
            self.signals.append(signal)
            self.wave_view.add_signal(signal)
            self.redraw()

    def remove_signal(self, signal: VCDSignal) -> None:
        if signal in self.signals:
            self.signals.remove(signal)
            if signal in self.wave_view.signals:
                self.wave_view.signals.remove(signal)
            self.redraw()

    def update_values(self, *args) -> None:
        self.value_panel.clear()
        for signal, y, effective_height in self.get_signal_positions():
            cursor = self.wave_view.cursor_time or self.wave_view.start_time
            val = self.wave_view.get_value_at_time(signal, cursor)
            self.value_panel.add_value(y + effective_height / 2, val)

    def update_averages(self) -> None:
        if self.wave_view.marker_A is None or self.wave_view.marker_B is None:
            self.avg_panel.clear()
            return
        A, B = sorted((self.wave_view.marker_A, self.wave_view.marker_B))
        header = f"A: {A:.2f} B: {B:.2f}"
        avg_data: List[Tuple[float, str]] = []
        for signal, y, effective_height in self.get_signal_positions():
            avg, min_val, max_val = self.compute_stats(signal, A, B)
            avg_str = f"Avg: {avg:.2f} Min: {min_val:.2f} Max: {max_val:.2f}"
            avg_data.append((y + effective_height / 2, avg_str))
        self.avg_panel.set_data(header, avg_data)

    def compute_stats(self, signal: VCDSignal, A: float, B: float) -> Tuple[float, float, float]:
        total, duration = 0.0, B - A
        if duration <= 0:
            return 0.0, 0.0, 0.0
        transitions = signal.transitions
        current_val = next((v for t, v in transitions if t <= A), "0")
        current_time = A
        current_num = numeric_value(current_val)
        min_val = current_num
        max_val = current_num

        for t, v in transitions:
            if t < A:
                continue
            if t > B:
                break
            dt = t - current_time
            total += dt * numeric_value(current_val)
            current_time = t
            current_val = v
            current_num = numeric_value(current_val)
            min_val = min(min_val, current_num)
            max_val = max(max_val, current_num)
        if current_time < B:
            dt = B - current_time
            total += dt * numeric_value(current_val)
            current_num = numeric_value(current_val)
            min_val = min(min_val, current_num)
            max_val = max(max_val, current_num)
        avg = total / duration
        return avg, min_val, max_val

    def redraw(self) -> None:
        self.wave_view.top_margin = DEFAULT_TOP_MARGIN
        self.wave_view.schedule_rendering()
        self.name_panel.set_signals(self.signals, DEFAULT_TOP_MARGIN, DEFAULT_SIGNAL_HEIGHT)
        self.update_values()
        self.update_averages()
        total_height = self.wave_view.top_margin + 20 + sum(DEFAULT_SIGNAL_HEIGHT * s.height_factor for s in self.signals)
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

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.signals: List[VCDSignal] = []
        self.top_margin: int = DEFAULT_TOP_MARGIN
        self.signal_height: int = DEFAULT_SIGNAL_HEIGHT
        self.selected_signals: set = set()
        self.last_clicked_index: Optional[int] = None

    def set_signals(self, signals: List[VCDSignal], top_margin: int,
                    signal_height: int) -> None:
        self.signals = signals
        self.top_margin, self.signal_height = top_margin, signal_height
        self.selected_signals.clear()
        self.last_clicked_index = None
        self.update()

    def paintEvent(self, event) -> None:
        with qpainter(self) as painter:
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

    def _signal_index_at(self, y_pos: float) -> Optional[int]:
        y_acc = self.top_margin + 20
        for i, signal in enumerate(self.signals):
            if y_acc <= y_pos < y_acc + self.signal_height * signal.height_factor:
                return i
            y_acc += self.signal_height * signal.height_factor
        return None

    def mousePressEvent(self, event) -> None:
        index = self._signal_index_at(event.position().y())
        if index is None:
            return super().mousePressEvent(event)
        clicked_signal = self.signals[index]
        if event.button() == Qt.MouseButton.LeftButton:
            mods = event.modifiers()
            if mods & Qt.KeyboardModifier.ShiftModifier and self.last_clicked_index is not None:
                start, end = sorted((self.last_clicked_index, index))
                for i in range(start, end + 1):
                    self.selected_signals.add(self.signals[i])
            elif mods & Qt.KeyboardModifier.ControlModifier:
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
            if clicked_signal not in self.selected_signals:
                self.selected_signals = {clicked_signal}
                self.last_clicked_index = index
                self.update()
            menu = self._create_context_menu(clicked_signal)
            menu.exec(event.globalPosition().toPoint())
        else:
            super().mousePressEvent(event)

    def _create_context_menu(self, signal: VCDSignal) -> QMenu:
        menu = QMenu(self)
        for label, mode in [("Hex", "hex"), ("Bin", "bin"), ("Decimal", "decimal")]:
            action = QAction(label, self)
            action.setCheckable(True)
            action.setChecked(signal.rep_mode == mode)
            action.triggered.connect(lambda checked, m=mode, s=signal: self._set_signal_representation(m, s))
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

    def _set_signal_representation(self, mode: str, clicked_signal: VCDSignal) -> None:
        targets = self.selected_signals or {clicked_signal}
        for s in targets:
            s.rep_mode = mode
        self.representationChanged.emit()

    def _set_signal_height(self, factor: int, clicked_signal: VCDSignal) -> None:
        targets = self.selected_signals or {clicked_signal}
        for s in targets:
            s.height_factor = factor
        self.representationChanged.emit()

    def _toggle_analog_render(self, clicked_signal: VCDSignal) -> None:
        targets = self.selected_signals or {clicked_signal}
        for s in targets:
            s.analog_render = not s.analog_render
        self.representationChanged.emit()

    def _dump_signals(self, clicked_signal: VCDSignal) -> None:
        targets = self.selected_signals or {clicked_signal}
        main_window = self.window()
        if hasattr(main_window, "dump_signals"):
            main_window.dump_signals(list(targets))

# =============================================================================
# WAVEFORM VALUES (VIEW)
# =============================================================================
class WaveformValues(QWidget):
    """Displays the current value of each signal at the cursor time."""
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.values: List[Tuple[float, str]] = []

    def clear(self) -> None:
        self.values = []
        self.update()

    def add_value(self, y: float, text: str) -> None:
        self.values.append((y, text))
        self.update()

    def paintEvent(self, event) -> None:
        with qpainter(self) as painter:
            painter.fillRect(self.rect(), QColor("black"))
            painter.setFont(QFont("Courier", 10, QFont.Weight.Bold))
            fm = QFontMetrics(painter.font())
            for (y, text) in self.values:
                painter.setPen(QColor("yellow"))
                painter.drawText(self.width() - fm.horizontalAdvance(text) - 5, y + fm.ascent() / 2, text)

# =============================================================================
# VCD VIEWER (MAIN CONTROLLER)
# =============================================================================
class VCDViewer(QMainWindow):
    """
    Main application window that creates the model and integrates all views.
    Manages file operations, state saving/loading, and user interactions.
    """
    def __init__(self, vcd_filename: str) -> None:
        super().__init__()
        self.setWindowTitle("VCD Waveform Viewer")
        self.resize(1200, 600)
        self.state_manager = StateManager(self)
        self.vcd_filename: str = vcd_filename
        self.model = None
        self.timescale: str = "unknown"

        self.progressBar = QProgressBar()
        self.progressBar.setVisible(False)
        self.statusBar().addPermanentWidget(self.progressBar)

        self._create_menu()
        self._create_main_ui()

        self.load_vcd_model(self.vcd_filename)

        self.search_shortcut = QShortcut(QKeySequence("F"), self)
        self.search_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self.search_shortcut.activated.connect(self.open_search_window)
        self.search_window: Optional[SearchWindow] = None

    def _create_menu(self) -> None:
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

    def _create_main_ui(self) -> None:
        main_splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self.setCentralWidget(main_splitter)

        from design_explorer import DesignExplorer
        self.design_explorer = DesignExplorer(self)
        self.design_explorer.set_hierarchy(self.model.hierarchy if self.model else {})
        self.design_explorer.signalsToAdd.connect(self.add_signals_from_tree)
        self.design_explorer.tree.itemDoubleClicked.connect(self.on_tree_double_click)
        main_splitter.addWidget(self.design_explorer)

        right_frame = QWidget()
        rlayout = QVBoxLayout(right_frame)
        self.wave_panel = WaveformPanel()
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

    def load_vcd_model(self, filename: str) -> None:
        self.progressBar.setVisible(True)
        self.progressBar.setRange(0, 0)
        self.statusBar().showMessage("Loading VCD file...")

        self.loader_thread = QThread()
        self.loader = VCDLoaderWorker(filename)
        self.loader.moveToThread(self.loader_thread)
        self.loader_thread.started.connect(self.loader.run)
        self.loader.finished.connect(self.on_vcd_loaded)
        self.loader.finished.connect(self.loader_thread.quit)
        self.loader.finished.connect(self.loader.deleteLater)
        self.loader_thread.finished.connect(self.loader_thread.deleteLater)
        self.loader_thread.start()

    def on_vcd_loaded(self, model: WaveformModel) -> None:
        self.model = model
        self.timescale = self.model.timescale
        self.design_explorer.set_hierarchy(self.model.hierarchy)
        self.rebuild_tree()
        self.wave_panel.wave_view.clear()
        self.wave_panel.signals = []
        self.wave_panel.redraw()
        self.progressBar.setRange(0, 100)
        self.progressBar.setValue(100)
        self.progressBar.setVisible(False)
        self.statusBar().showMessage("VCD file loaded", 2000)

    def open_search_window(self) -> None:
        selected = self.wave_panel.name_panel.selected_signals
        if not selected:
            print("No signals selected for search.")
            return
        if self.search_window is not None:
            self.search_window.close()
        # Create an ordered list of selected signals using the order in the names panel.
        ordered_signals = [sig for sig in self.wave_panel.name_panel.signals if sig in selected]
        self.search_window = SearchWindow(ordered_signals, self)
        self.search_window.timestampFound.connect(self.on_timestamp_found)
        self.search_window.show()

    def on_timestamp_found(self, found_time: float) -> None:
        wave_view = self.wave_panel.wave_view
        current_window = wave_view.end_time - wave_view.start_time
        wave_view.set_time_window(found_time, found_time + current_window)
        wave_view.cursor_time = found_time
        wave_view.schedule_rendering()
        self.wave_panel.update_values()

    def add_signals_from_tree(self, signals: List[VCDSignal]) -> None:
        for sig in signals:
            self.wave_panel.add_signal(sig)

    def open_file(self) -> None:
        new_file, _ = QFileDialog.getOpenFileName(self, "Open VCD File", "", "VCD files (*.vcd);;All files (*)")
        if new_file:
            self.vcd_filename = new_file
            self.load_vcd_model(self.vcd_filename)

    def rebuild_tree(self) -> None:
        pattern = (self.design_explorer.filter_entry.text().strip()
                   if hasattr(self.design_explorer, "filter_entry") else "")
        self.design_explorer.tree.clear()
        self.design_explorer.tree.signal_map.clear()
        self._build_filtered_tree(self.design_explorer.tree, self.model.hierarchy, pattern)

    def _build_filtered_tree(self, parent_item, tree_dict: Dict[str, Any], pattern: str) -> None:
        for key, subtree in tree_dict.items():
            if key == "_signal":
                continue
            if set(subtree.keys()) == {"_signal"}:
                signal = subtree["_signal"]
                if not pattern or fnmatch.fnmatch(signal.name, f"*{pattern}*"):
                    leaf = QTreeWidgetItem(parent_item, [signal.name])
                    self.design_explorer.tree.signal_map[leaf] = signal
                    leaf.setForeground(0, QColor("red" if self._is_dynamic(signal) else "gray"))
            else:
                node = QTreeWidgetItem(parent_item, [key])
                node.setExpanded(True)
                self._build_filtered_tree(node, subtree, pattern)

    def _is_dynamic(self, signal: VCDSignal) -> bool:
        return bool(signal.transitions and len({v for _, v in signal.transitions}) > 1)

    def on_tree_double_click(self, item, column: int) -> None:
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

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Delete:
            selected = self.wave_panel.name_panel.selected_signals
            if selected:
                for sig in list(selected):
                    if sig in self.wave_panel.signals:
                        self.wave_panel.remove_signal(sig)
                self.wave_panel.name_panel.selected_signals.clear()
                self.wave_panel.redraw()
        else:
            super().keyPressEvent(event)

    def save_state(self) -> None:
        state = {
            "vcd_filename": self.vcd_filename,
            "signals": [ {
                "fullname": sig.fullname,
                "rep_mode": sig.rep_mode,
                "height_factor": sig.height_factor,
                "analog_render": sig.analog_render
            } for sig in self.wave_panel.signals ],
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

    def load_state(self) -> None:
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

    def dump_signals(self, signals: List[VCDSignal]) -> None:
        dump_signals(signals, self.timescale)

if __name__ == "__main__":
    vcd_filename = "jtag.vcd"
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    viewer = VCDViewer(vcd_filename)
    viewer.show()
    sys.exit(app.exec())
