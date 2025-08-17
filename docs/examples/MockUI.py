import sys
from PySide6.QtCore import Qt, QPoint, QSize, QEvent
from PySide6.QtGui import QPainter, QColor, QPen, QIcon, QAction, QKeySequence, QPixmap
from PySide6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout,
                               QWidget, QPushButton, QLabel, QFrame, QSizeGrip, QSplitter, QMenuBar, QToolBar)


class CustomTitleBar(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.setFixedHeight(35)
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(self.backgroundRole(), QColor("#252526"))
        self.setPalette(palette)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.menu_bar = QMenuBar(self)
        self.menu_bar.setStyleSheet("""
            QMenuBar {
                background-color: transparent;
                color: #CCCCCC;
            }
            QMenuBar::item {
                background-color: transparent;
                padding: 5px 10px;
            }
            QMenuBar::item:selected {
                background-color: #3E3E42;
            }
            QMenu {
                background-color: #252526;
                color: #CCCCCC;
                border: 1px solid #3E3E42;
            }
            QMenu::item:selected {
                background-color: #007ACC;
            }
        """)
        layout.addWidget(self.menu_bar)

        layout.addStretch()

        self.title = QLabel("VS Code Style App", self)
        self.title.setStyleSheet("color: #CCCCCC;")
        layout.addWidget(self.title)

        layout.addStretch()

        # Toggle left sidebar button
        self.left_button = QPushButton()
        self.left_button.setCheckable(True)
        self.left_button.setChecked(True)
        self.left_button.setIcon(self.create_sidebar_icon(Qt.LeftArrow))
        self.left_button.setFixedSize(30, 30)
        self.left_button.setStyleSheet(
            "QPushButton { background-color: transparent; border: none; } QPushButton:checked { background-color: #007ACC; }")
        layout.addWidget(self.left_button)

        # Toggle right sidebar button
        self.right_button = QPushButton()
        self.right_button.setCheckable(True)
        self.right_button.setChecked(True)
        self.right_button.setIcon(self.create_sidebar_icon(Qt.RightArrow))
        self.right_button.setFixedSize(30, 30)
        self.right_button.setStyleSheet(
            "QPushButton { background-color: transparent; border: none; } QPushButton:checked { background-color: #007ACC; }")
        layout.addWidget(self.right_button)

        # Toggle bottom panel button
        self.bottom_button = QPushButton()
        self.bottom_button.setCheckable(True)
        self.bottom_button.setChecked(True)
        self.bottom_button.setIcon(self.create_bottombar_icon(Qt.DownArrow))
        self.bottom_button.setFixedSize(30, 30)
        self.bottom_button.setStyleSheet(
            "QPushButton { background-color: transparent; border: none; } QPushButton:checked { background-color: #007ACC; }")
        layout.addWidget(self.bottom_button)

        self.minimize_button = QPushButton("_")
        self.minimize_button.setFixedSize(30, 30)
        self.minimize_button.setStyleSheet(
            "QPushButton { background-color: transparent; border: none; color: #CCCCCC; } QPushButton:hover { background-color: #3E3E42; }")
        self.minimize_button.clicked.connect(self.parent.showMinimized)
        layout.addWidget(self.minimize_button)

        self.maximize_button = QPushButton("[]")
        self.maximize_button.setFixedSize(30, 30)
        self.maximize_button.setStyleSheet(
            "QPushButton { background-color: transparent; border: none; color: #CCCCCC; } QPushButton:hover { background-color: #3E3E42; }")
        self.maximize_button.clicked.connect(self.toggle_maximize)
        layout.addWidget(self.maximize_button)

        self.close_button = QPushButton("X")
        self.close_button.setFixedSize(30, 30)
        self.close_button.setStyleSheet(
            "QPushButton { background-color: transparent; border: none; color: #CCCCCC; } QPushButton:hover { background-color: #C42B1C; }")
        self.close_button.clicked.connect(self.parent.close)
        layout.addWidget(self.close_button)

        self.old_pos = None
        self._system_move_active = False

        # Allow dragging when clicking on menu bar and title label as well
        self.menu_bar.installEventFilter(self)
        self.title.installEventFilter(self)

    def create_sidebar_icon(self, arrow_direction):
        pixmap = QPixmap(16, 16)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        pen = QPen(QColor("#CCCCCC"))
        pen.setWidth(2)
        painter.setPen(pen)
        if arrow_direction == Qt.LeftArrow:
            painter.drawRect(1, 1, 6, 14)
            painter.drawLine(10, 4, 14, 8)
            painter.drawLine(10, 12, 14, 8)
        else:
            painter.drawRect(9, 1, 6, 14)
            painter.drawLine(6, 4, 2, 8)
            painter.drawLine(6, 12, 2, 8)
        painter.end()
        return QIcon(pixmap)

    def create_bottombar_icon(self, arrow_direction):
        pixmap = QPixmap(16, 16)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        pen = QPen(QColor("#CCCCCC"))
        pen.setWidth(2)
        painter.setPen(pen)
        # Draw a horizontal bar (like the sidebar bar but horizontal)
        painter.drawRect(1, 9, 14, 6)
        if arrow_direction == Qt.UpArrow:
            painter.drawLine(4, 10, 8, 6)
            painter.drawLine(12, 10, 8, 6)
        else:  # DownArrow (default)
            painter.drawLine(4, 12, 8, 14)
            painter.drawLine(12, 12, 8, 14)
        painter.end()
        return QIcon(pixmap)

    def toggle_maximize(self):
        if self.parent.isMaximized():
            self.parent.showNormal()
        else:
            self.parent.showMaximized()

    def _start_system_move(self, event) -> bool:
        # Try to use native system move (needed on Wayland); fall back to manual move if not available
        wh = self.parent.windowHandle() if hasattr(self.parent, 'windowHandle') else None
        if wh is None:
            return False
        if not hasattr(wh, 'startSystemMove'):
            return False
        try:
            # Try common signatures across PySide6/PyQt versions
            try:
                return bool(wh.startSystemMove(event.globalPosition().toPoint()))
            except TypeError:
                try:
                    # Older APIs might accept QPoint from globalPos
                    return bool(wh.startSystemMove(event.globalPos()))
                except Exception:
                    # Some versions take no args
                    return bool(wh.startSystemMove())
        except Exception:
            return False

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and not self.parent.isMaximized():
            # Prefer system move where available (e.g., Wayland)
            if self._start_system_move(event):
                self._system_move_active = True
                self.old_pos = None
            else:
                self._system_move_active = False
                self.old_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if self._system_move_active:
            # System move is handled by the window system; nothing to do here
            return
        if self.old_pos:
            delta = QPoint(event.globalPosition().toPoint() - self.old_pos)
            self.parent.move(self.parent.x() + delta.x(), self.parent.y() + delta.y())
            self.old_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        self._system_move_active = False
        self.old_pos = None

    def mouseDoubleClickEvent(self, event):
        self.toggle_maximize()

    def eventFilter(self, obj, event):
        # Forward mouse events from child widgets (menu bar and title label) to enable window dragging
        if obj in (self.menu_bar, self.title):
            if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton and not self.parent.isMaximized():
                # Prefer system move for Wayland and compatible platforms
                if self._start_system_move(event):
                    self._system_move_active = True
                    self.old_pos = None
                else:
                    self._system_move_active = False
                    self.old_pos = event.globalPosition().toPoint()
                return False  # do not consume; allow normal behavior too (e.g., menus)
            elif event.type() == QEvent.MouseMove:
                if self._system_move_active:
                    return False
                if self.old_pos is not None:
                    delta = event.globalPosition().toPoint() - self.old_pos
                    self.parent.move(self.parent.x() + delta.x(), self.parent.y() + delta.y())
                    self.old_pos = event.globalPosition().toPoint()
                    return True  # we handled the drag
            elif event.type() == QEvent.MouseButtonRelease:
                self._system_move_active = False
                self.old_pos = None
                return False
        return super().eventFilter(obj, event)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("VS Code Style App")
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setGeometry(100, 100, 1200, 800)
        self.setStyleSheet("background-color: #1E1E1E;")

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        self.v_layout = QVBoxLayout(self.central_widget)
        self.v_layout.setContentsMargins(0, 0, 0, 0)
        self.v_layout.setSpacing(0)

        self.title_bar = CustomTitleBar(self)
        self.v_layout.addWidget(self.title_bar)

        # Horizontal splitter for main area and right sidebar
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #3E3E42;
                width: 1px;
            }
            QSplitter::handle:hover {
                background-color: #007ACC;
            }
        """)

        # Vertical splitter to host (main+right) above and bottom panel below
        self.v_splitter = QSplitter(Qt.Vertical)
        self.v_splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #3E3E42;
                height: 1px;
            }
            QSplitter::handle:hover {
                background-color: #007ACC;
            }
        """)
        self.v_layout.addWidget(self.v_splitter)

        # Compose splitters
        self.v_splitter.addWidget(self.splitter)

        # Left Sidebar
        self.left_sidebar = QFrame()
        self.left_sidebar.setFrameShape(QFrame.NoFrame)
        self.left_sidebar.setStyleSheet("background-color: #252526;")
        self.left_sidebar_layout = QVBoxLayout(self.left_sidebar)
        self.left_sidebar_layout.addWidget(QLabel("Left Sidebar Content", styleSheet="color: #CCCCCC"))
        self.splitter.addWidget(self.left_sidebar)

        # Central content
        self.content_area = QFrame()
        self.content_area.setFrameShape(QFrame.NoFrame)
        self.content_layout = QVBoxLayout(self.content_area)
        self.content_layout.addWidget(QLabel("Main Content Area", styleSheet="color: #CCCCCC"))
        self.splitter.addWidget(self.content_area)

        # Right Sidebar
        self.right_sidebar = QFrame()
        self.right_sidebar.setFrameShape(QFrame.NoFrame)
        self.right_sidebar.setStyleSheet("background-color: #252526;")
        self.right_sidebar_layout = QVBoxLayout(self.right_sidebar)
        self.right_sidebar_layout.addWidget(QLabel("Right Sidebar Content", styleSheet="color: #CCCCCC"))
        self.splitter.addWidget(self.right_sidebar)

        # Default sizes: left, center, right
        self.splitter.setSizes([250, 700, 250])

        # Bottom Panel
        self.bottom_panel = QFrame()
        self.bottom_panel.setFrameShape(QFrame.NoFrame)
        self.bottom_panel.setStyleSheet("background-color: #252526;")
        self.bottom_panel_layout = QVBoxLayout(self.bottom_panel)
        self.bottom_panel_layout.setContentsMargins(8, 8, 8, 8)
        self.bottom_panel_layout.addWidget(QLabel("Bottom Panel Content", styleSheet="color: #CCCCCC"))
        self.v_splitter.addWidget(self.bottom_panel)

        # Default sizes: main area majority, bottom panel smaller
        self.v_splitter.setSizes([600, 200])

        self.grip = QSizeGrip(self)
        self.v_layout.addWidget(self.grip, 0, Qt.AlignBottom | Qt.AlignRight)

        self._setup_actions()
        self._setup_menu()
        self._setup_toolbar()

    def _setup_actions(self):
        self.title_bar.left_button.clicked.connect(self.toggle_left_sidebar)
        self.title_bar.right_button.clicked.connect(self.toggle_right_sidebar)
        self.title_bar.bottom_button.clicked.connect(self.toggle_bottom_panel)

        self.fullscreen_action = QAction("Toggle Fullscreen", self)
        self.fullscreen_action.setShortcut(QKeySequence(Qt.Key_F11))
        self.fullscreen_action.triggered.connect(self.toggle_fullscreen)
        self.addAction(self.fullscreen_action)

    def _setup_menu(self):
        file_menu = self.title_bar.menu_bar.addMenu("File")
        file_menu.addAction("New File")
        file_menu.addAction("Open File")
        file_menu.addAction("Save")
        file_menu.addSeparator()
        file_menu.addAction("Exit", self.close)

        # Edit menu and actions (keep references for toolbar)
        self.edit_menu = self.title_bar.menu_bar.addMenu("Edit")
        self.undo_action = self.edit_menu.addAction("Undo")
        self.undo_action.setShortcut(QKeySequence.Undo)
        self.redo_action = self.edit_menu.addAction("Redo")
        # Use common redo shortcuts (platform may map accordingly)
        self.redo_action.setShortcuts([QKeySequence.Redo])
        self.edit_menu.addSeparator()
        self.cut_action = self.edit_menu.addAction("Cut")
        self.cut_action.setShortcut(QKeySequence.Cut)
        self.copy_action = self.edit_menu.addAction("Copy")
        self.copy_action.setShortcut(QKeySequence.Copy)
        self.paste_action = self.edit_menu.addAction("Paste")
        self.paste_action.setShortcut(QKeySequence.Paste)

        view_menu = self.title_bar.menu_bar.addMenu("View")
        view_menu.addAction("Zoom In")
        view_menu.addAction("Zoom Out")
        view_menu.addSeparator()
        view_menu.addAction(self.fullscreen_action)

    def _setup_toolbar(self):
        # Create a mock toolbar and populate it with actions from the Edit menu
        self.toolbar = QToolBar("Edit Toolbar", self)
        self.toolbar.setMovable(False)
        self.toolbar.setFloatable(False)
        self.toolbar.setIconSize(QSize(16, 16))
        # Text-only to match the mock style; could be changed to icons if available
        self.toolbar.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.toolbar.setStyleSheet(
            "QToolBar { background-color: #2D2D30; border: none; spacing: 4px; padding: 2px 4px; }"
            "QToolButton { color: #CCCCCC; padding: 4px 8px; }"
            "QToolButton:hover { background-color: #3E3E42; }"
        )

        # Insert the toolbar below the custom title bar
        self.v_layout.insertWidget(1, self.toolbar)

        # Add actions from the Edit menu (skip separators)
        if hasattr(self, 'edit_menu') and self.edit_menu is not None:
            for act in self.edit_menu.actions():
                if act.isSeparator():
                    self.toolbar.addSeparator()
                else:
                    self.toolbar.addAction(act)

    def toggle_right_sidebar(self):
        if self.right_sidebar.isVisible():
            self.right_sidebar.hide()
            # left + center + right(hidden)
            left = 250 if self.left_sidebar.isVisible() else 0
            right = 0
            center = max(0, self.width() - left - right)
            self.splitter.setSizes([left, center, right])
        else:
            self.right_sidebar.show()
            # left + center + right
            left = 250 if self.left_sidebar.isVisible() else 0
            right = 250
            center = max(0, self.width() - left - right)
            self.splitter.setSizes([left, center, right])

    def toggle_bottom_panel(self):
        if self.bottom_panel.isVisible():
            self.bottom_panel.hide()
        else:
            self.bottom_panel.show()
            # Allocate 200px height to bottom panel by default
            h = max(0, self.height() - 200)
            self.v_splitter.setSizes([h, 200])

    def toggle_left_sidebar(self):
        if self.left_sidebar.isVisible():
            self.left_sidebar.hide()
            # left(hidden) + center + right
            left = 0
            right = 250 if self.right_sidebar.isVisible() else 0
            center = max(0, self.width() - left - right)
            self.splitter.setSizes([left, center, right])
        else:
            self.left_sidebar.show()
            # left + center + right
            left = 250
            right = 250 if self.right_sidebar.isVisible() else 0
            center = max(0, self.width() - left - right)
            self.splitter.setSizes([left, center, right])

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
            self.title_bar.show()
            if hasattr(self, 'toolbar'):
                self.toolbar.show()
            self.grip.show()
        else:
            self.showFullScreen()
            self.title_bar.hide()
            if hasattr(self, 'toolbar'):
                self.toolbar.hide()
            self.grip.hide()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
