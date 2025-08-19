# pyside6_native_frame_custom_header_win11.py
import sys, ctypes
from ctypes import wintypes
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLineEdit, QLabel,
    QHBoxLayout, QVBoxLayout, QStyle, QFrame
)

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QLineEdit, QLabel, QHBoxLayout, QVBoxLayout, QStyle, QFrame
from PySide6.QtGui import QMouseEvent

IS_WIN = sys.platform.startswith("win")

# --- Win32 bits we need (Windows 10/11) ---
if IS_WIN:
    user32 = ctypes.windll.user32
    SetWindowLongPtrW = user32.SetWindowLongPtrW
    GetWindowLongPtrW = user32.GetWindowLongPtrW
    SetWindowPos = user32.SetWindowPos

    GWL_STYLE = -16
    SWP_NOSIZE = 0x0001
    SWP_NOMOVE = 0x0002
    SWP_NOZORDER = 0x0004
    SWP_FRAMECHANGED = 0x0020

    # Base styles we care about
    WS_CAPTION      = 0x00C00000  # WS_BORDER|WS_DLGFRAME
    WS_SYSMENU      = 0x00080000
    WS_MINIMIZEBOX  = 0x00020000
    WS_MAXIMIZEBOX  = 0x00010000
    WS_THICKFRAME   = 0x00040000  # resizing border (keeps snap/resize native)

def remove_win_caption(hwnd):
    """Remove only WS_CAPTION, keep thickframe + sys menu + buttons (native frame preserved)."""
    style = GetWindowLongPtrW(hwnd, GWL_STYLE)
    new_style = style & ~WS_CAPTION
    # Ensure we still have the bits that keep native behaviors
    new_style |= (WS_THICKFRAME | WS_SYSMENU | WS_MINIMIZEBOX | WS_MAXIMIZEBOX)
    if new_style != style:
        SetWindowLongPtrW(hwnd, GWL_STYLE, new_style)
        # Tell DWM/WM to recompute non-client metrics
        SetWindowPos(hwnd, 0, 0, 0, 0, 0,
                     SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED)

class Header(QWidget):
    """Custom in-client header with a search bar.
       Drag empty header area to move the window.
       Double-click empty header to toggle maximize/restore.
    """
    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName("Header")
        self.setAttribute(Qt.WA_StyledBackground, True)

        title_h = self.style().pixelMetric(QStyle.PM_TitleBarHeight)
        self.setFixedHeight(max(36, title_h))

        self.icon = QLabel()
        if not parent.windowIcon().isNull():
            self.icon.setPixmap(parent.windowIcon().pixmap(16, 16))

        self.title = QLabel(parent.windowTitle())
        self.title.setObjectName("HeaderTitle")
        self.search = QLineEdit(placeholderText="Search…")
        self.search.setClearButtonEnabled(True)
        self.search.returnPressed.connect(self._do_search)

        row = QHBoxLayout(self)
        row.setContentsMargins(10, 4, 10, 4)
        row.setSpacing(8)
        row.addWidget(self.icon)
        row.addWidget(self.title)
        row.addSpacing(12)
        row.addWidget(self.search, 1)

        self.setStyleSheet("""
        #Header { background: palette(window); border-bottom: 1px solid palette(mid); }
        #HeaderTitle { font-weight: 600; }
        QLineEdit { padding: 4px 8px; border-radius: 6px; }
        """)

    def _w(self):
        return self.window()  # QMainWindow

    def _winhandle(self):
        w = self._w()
        return w.windowHandle() if w is not None else None

    def mousePressEvent(self, ev: QMouseEvent):
        # Use ev.position() (QPointF) instead of deprecated ev.pos()
        if ev.button() == Qt.LeftButton and not self.search.geometry().contains(ev.position().toPoint()):
            win = self._winhandle()
            if win:
                win.startSystemMove()
                return
        super().mousePressEvent(ev)

    def mouseDoubleClickEvent(self, ev: QMouseEvent):
        if ev.button() == Qt.LeftButton and not self.search.geometry().contains(ev.position().toPoint()):
            w = self._w()
            w.showNormal() if w.isMaximized() else w.showMaximized()
            return
        super().mouseDoubleClickEvent(ev)

    def _do_search(self):
        text = self.search.text().strip()
        self._w().statusBar().showMessage(f"Search: {text}", 2500)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Native frame, no caption — custom header (PySide6, Win11)")
        self.setWindowIcon(QIcon.fromTheme("system-search") or QIcon())

        # Keep native frame & buttons, but we’ll strip the caption via Win32
        self.setWindowFlags(
            Qt.Window
            | Qt.CustomizeWindowHint
            | Qt.WindowSystemMenuHint
            | Qt.WindowMinimizeButtonHint
            | Qt.WindowMaximizeButtonHint
            | Qt.WindowCloseButtonHint
        )

        container = QWidget()
        v = QVBoxLayout(container)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        v.addWidget(Header(self))
        body = QFrame(); body.setFrameShape(QFrame.StyledPanel)
        v.addWidget(body, 1)
        self.setCentralWidget(container)
        self.statusBar().showMessage("Ready")

    def showEvent(self, ev):
        super().showEvent(ev)
        # IMPORTANT: only after the native window exists
        if IS_WIN:
            hwnd = int(self.winId())  # HWND
            remove_win_caption(hwnd)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = MainWindow()
    w.resize(1000, 650)
    w.show()
    sys.exit(app.exec())
