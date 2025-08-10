#!/usr/bin/env python3
"""WaveScout Main Application Window"""

import sys
import argparse
import os
from pathlib import Path
from PySide6.QtWidgets import (QApplication, QMainWindow, 
                              QSplitter, QTreeView, QFileDialog,
                              QMessageBox, QProgressDialog, QAbstractItemView,
                              QToolBar, QStyle)
from PySide6.QtCore import Qt, QThreadPool, QRunnable, Signal, QObject, QSettings, QEvent
from PySide6.QtGui import QAction, QActionGroup, QKeySequence
# QtAsyncio and asyncio removed - using single-threaded execution
from wavescout import WaveScoutWidget, create_sample_session, save_session, load_session
from wavescout.design_tree_view import DesignTreeView
from wavescout.config import RENDERING


class LoaderSignals(QObject):
    """Signals for loader runnable."""
    finished = Signal(object)
    error = Signal(str)


class LoaderRunnable(QRunnable):
    """Runnable for loading files in thread pool."""
    
    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self.signals = LoaderSignals()
        
    def run(self):
        """Execute the loading function."""
        try:
            result = self.func(*self.args, **self.kwargs)
            self.signals.finished.emit(result)
        except Exception as e:
            import traceback
            error_msg = f"{str(e)}\n\nTraceback:\n{traceback.format_exc()}"
            self.signals.error.emit(error_msg)


class WaveScoutMainWindow(QMainWindow):
    """Main window for WaveScout App."""
    
    def __init__(self, session_file=None, wave_file: str | None = None, exit_after_load: bool = False):
        super().__init__()
        self.setWindowTitle("WaveScout - Waveform Viewer")
        self.resize(1400, 800)
        
        # Initialize thread pool and progress dialog
        self.thread_pool = QThreadPool()
        self.progress_dialog = None
        
        # Initialize settings
        self.settings = QSettings("WaveScout", "Scout")
        
        # Store current UI scale
        self.current_ui_scale = self.settings.value("ui_scale", 1.0, type=float)
        
        # Store current waveform file for reload
        self.current_wave_file: str | None = None
        
        # Create main splitter
        self.main_splitter = QSplitter(Qt.Horizontal)
        
        # Create design tree view (left pane)
        self.design_tree_view = DesignTreeView()
        self.design_tree_view.signals_selected.connect(self._on_signals_selected)
        self.design_tree_view.status_message.connect(self.statusBar().showMessage)
        self.design_tree_view.install_event_filters()
        
        # Add design tree view to splitter first to place it on the left
        self.main_splitter.addWidget(self.design_tree_view)
        
        # Create wave view widget (right pane)
        self.wave_widget = WaveScoutWidget()
        self.main_splitter.addWidget(self.wave_widget)
        
        # Set splitter sizes (design tree: 30%, wave widget: 70%)
        self.main_splitter.setSizes([420, 980])
        
        self.setCentralWidget(self.main_splitter)
        
        # Create actions first (shared between menu and toolbar)
        self._create_actions()
        
        # Create menu bar
        self._create_menus()
        
        # Create toolbar
        self._create_toolbar()
        
        # Initialize status bar
        self.statusBar().showMessage("Ready")
        
        # Schedule initial load after event loop starts
        from PySide6.QtCore import QTimer

        # Store exit-after-load flag
        self.exit_after_load = exit_after_load

        if session_file:
            # Load the provided session file
            QTimer.singleShot(100, lambda: self.load_session_file(session_file))
        elif wave_file:
            # Load the provided waveform file (vcd/fst)
            QTimer.singleShot(100, lambda: self.load_file(wave_file))
        else:
            # Load default VCD file
            vcd_path = Path(__file__).parent / "test_inputs" / "swerv1.vcd"
            if vcd_path.exists():
                QTimer.singleShot(100, lambda: self.load_vcd(str(vcd_path)))
            else:
                # No default file, ensure actions are disabled
                self._set_waveform_actions_enabled(False)
        
    def _create_actions(self):
        """Create shared QAction objects for toolbar and menu."""
        # File actions
        self.open_action = QAction("&Open...", self)
        self.open_action.setShortcut(QKeySequence.Open)
        self.open_action.setStatusTip("Open a waveform file")
        self.open_action.triggered.connect(self.open_file)
        
        self.reload_action = QAction("&Reload", self)
        self.reload_action.setShortcut(QKeySequence("Ctrl+R"))
        self.reload_action.setStatusTip("Reload the current waveform file")
        self.reload_action.setEnabled(False)  # Disabled until a file is loaded
        self.reload_action.triggered.connect(self.reload_waveform)
        
        # View actions
        self.zoom_in_action = QAction("Zoom &In", self)
        self.zoom_in_action.setShortcut(QKeySequence("+"))
        self.zoom_in_action.setStatusTip("Zoom in on the waveform")
        self.zoom_in_action.setEnabled(False)  # Disabled until a file is loaded
        self.zoom_in_action.triggered.connect(self.wave_widget._zoom_in)
        
        self.zoom_out_action = QAction("Zoom &Out", self)
        self.zoom_out_action.setShortcut(QKeySequence("-"))
        self.zoom_out_action.setStatusTip("Zoom out of the waveform")
        self.zoom_out_action.setEnabled(False)  # Disabled until a file is loaded
        self.zoom_out_action.triggered.connect(self.wave_widget._zoom_out)
        
        self.zoom_fit_action = QAction("Zoom to &Fit", self)
        self.zoom_fit_action.setShortcut(QKeySequence("F"))
        self.zoom_fit_action.setStatusTip("Fit the entire waveform in view")
        self.zoom_fit_action.setEnabled(False)  # Disabled until a file is loaded
        self.zoom_fit_action.triggered.connect(self.wave_widget._zoom_to_fit)
        
        self.pan_left_action = QAction("Pan &Left", self)
        self.pan_left_action.setShortcut(QKeySequence("Left"))
        self.pan_left_action.setStatusTip("Pan the view left")
        self.pan_left_action.setEnabled(False)  # Disabled until a file is loaded
        self.pan_left_action.triggered.connect(self.wave_widget._pan_left)
        
        self.pan_right_action = QAction("Pan &Right", self)
        self.pan_right_action.setShortcut(QKeySequence("Right"))
        self.pan_right_action.setStatusTip("Pan the view right")
        self.pan_right_action.setEnabled(False)  # Disabled until a file is loaded
        self.pan_right_action.triggered.connect(self.wave_widget._pan_right)
        
        # Set icons for toolbar
        style = self.style()
        if style:
            self.open_action.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon))
            self.reload_action.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
            self.zoom_in_action.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_ArrowUp))
            self.zoom_out_action.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_ArrowDown))
            self.pan_left_action.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_ArrowLeft))
            self.pan_right_action.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_ArrowRight))
            self.zoom_fit_action.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_DialogResetButton))
    
    def _create_toolbar(self):
        """Create the main toolbar."""
        self.toolbar = QToolBar("Main Toolbar", self)
        self.toolbar.setObjectName("MainToolbar")  # For saving/restoring state
        self.addToolBar(self.toolbar)
        
        # Add actions to toolbar
        self.toolbar.addAction(self.open_action)
        self.toolbar.addAction(self.reload_action)
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.zoom_in_action)
        self.toolbar.addAction(self.zoom_out_action)
        self.toolbar.addAction(self.zoom_fit_action)
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.pan_left_action)
        self.toolbar.addAction(self.pan_right_action)
    
    def _create_menus(self):
        """Create application menus."""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("&File")
        file_menu.addAction(self.open_action)
        file_menu.addAction(self.reload_action)
        file_menu.addSeparator()
        file_menu.addAction("&Save Session...", self.save_session)
        file_menu.addAction("&Load Session...", self.load_session)
        file_menu.addSeparator()
        file_menu.addAction("E&xit", self.close)
        
        # Edit menu
        edit_menu = menubar.addMenu("&Edit")
        edit_menu.addSeparator()
        self.drop_marker_action = QAction("&Drop Marker", self)
        self.drop_marker_action.setShortcut(QKeySequence("Ctrl+M"))
        self.drop_marker_action.triggered.connect(self._drop_marker)
        edit_menu.addAction(self.drop_marker_action)
        
        # View menu
        view_menu = menubar.addMenu("&View")
        view_menu.addAction(self.zoom_in_action)
        view_menu.addAction(self.zoom_out_action)
        view_menu.addAction(self.zoom_fit_action)
        view_menu.addSeparator()
        view_menu.addAction(self.pan_left_action)
        view_menu.addAction(self.pan_right_action)
        view_menu.addSeparator()
        
        # UI Scaling submenu
        ui_scaling_menu = view_menu.addMenu("&UI Scaling")
        ui_scaling_group = QActionGroup(self)
        
        # Add scaling options
        scaling_options = [
            ("75%", 0.75),
            ("90%", 0.9),
            ("100%", 1.0),
            ("110%", 1.1),
            ("125%", 1.25),
            ("150%", 1.5),
            ("175%", 1.75),
            ("200%", 2.0)
        ]
        
        for label, scale in scaling_options:
            action = QAction(label, self)
            action.setCheckable(True)
            action.setChecked(abs(scale - self.current_ui_scale) < 0.01)
            action.triggered.connect(lambda checked, s=scale: self._set_ui_scale(s))
            ui_scaling_group.addAction(action)
            ui_scaling_menu.addAction(action)
        
        view_menu.addSeparator()
        
        # Markers window action
        self.markers_window_action = QAction("&Markers...", self)
        self.markers_window_action.triggered.connect(self._show_markers_window)
        view_menu.addAction(self.markers_window_action)
        
        view_menu.addSeparator()
        
    def reload_waveform(self):
        """Reload the current waveform file."""
        if not self.current_wave_file:
            QMessageBox.information(self, "No File Loaded", "No waveform file is currently loaded.")
            return
            
        # Check if file still exists
        if not os.path.exists(self.current_wave_file):
            QMessageBox.critical(self, "File Not Found", 
                               f"The file no longer exists:\n{self.current_wave_file}")
            self.current_wave_file = None
            self._set_waveform_actions_enabled(False)
            return
            
        # Reload the file
        self.statusBar().showMessage(f"Reloading {os.path.basename(self.current_wave_file)}...")
        self.load_file(self.current_wave_file)
    
    def _set_waveform_actions_enabled(self, enabled: bool):
        """Enable or disable waveform-related actions."""
        self.reload_action.setEnabled(enabled and self.current_wave_file is not None)
        self.zoom_in_action.setEnabled(enabled)
        self.zoom_out_action.setEnabled(enabled)
        self.zoom_fit_action.setEnabled(enabled)
        self.pan_left_action.setEnabled(enabled)
        self.pan_right_action.setEnabled(enabled)
    
    def open_file(self):
        """Open a waveform file using file dialog."""

        # Get file path from user
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Waveform File",
            "",
            "Waveform Files (*.vcd *.fst *.ghw);;VCD Files (*.vcd);;FST Files (*.fst);;GHDL Files (*.ghw);;All Files (*)"
        )
        
        if file_path:
            # Use QTimer to defer loading, allowing the dialog to close first
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, lambda: self.load_file(file_path))
            
    def load_file(self, file_path: str):
        """Load a waveform file asynchronously using thread pool."""
        # Store the file path for reload functionality
        self.current_wave_file = file_path
        
        # Show loading status
        file_name = os.path.basename(file_path)
        
        # Create progress dialog
        self.progress_dialog = QProgressDialog(
            f"Loading {file_name}...",
            "Cancel",
            0,
            0,  # Indeterminate progress
            self
        )
        self.progress_dialog.setWindowTitle("Loading Waveform")
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.setMinimumDuration(0)  # Show immediately
        self.progress_dialog.setCancelButton(None)  # No cancel for now
        self.progress_dialog.show()
        
        # Update status bar
        self.statusBar().showMessage(f"Loading {file_name}...")
        
        # Create and run loader
        loader = LoaderRunnable(create_sample_session, file_path)
        loader.signals.finished.connect(self._on_waveform_load_finished)
        loader.signals.error.connect(self._on_waveform_load_error)
        self.thread_pool.start(loader)
        
    def _on_waveform_load_finished(self, session):
        """Handle successful waveform load."""
        # Don't close progress dialog yet - keep it open during UI updates
        if self.progress_dialog:
            self.progress_dialog.setLabelText("Setting up UI...")
            
        # Enable waveform-related actions
        self._set_waveform_actions_enabled(True)
            
        self.on_load_finished(session)
        
    def _on_waveform_load_error(self, error_msg):
        """Handle waveform load error."""
        # Close progress dialog
        if self.progress_dialog:
            self.progress_dialog.close()
            self.progress_dialog = None
            
        # Clear the current file on error
        self.current_wave_file = None
        self._set_waveform_actions_enabled(False)
            
        self.on_load_error(error_msg)
        
    def on_load_finished(self, session):
        """Handle successful file load."""
        self.wave_widget.setSession(session)
        
        
        # Get filename from the session's waveform database (file_path is optional property)
        if session.waveform_db:
            file_path = getattr(session.waveform_db, 'file_path', None)
            if file_path:
                file_name = Path(file_path).name
            else:
                file_name = None
            # Include timescale info if available
            if file_name:
                if session.timescale:
                    timescale_str = f"{session.timescale.factor}{session.timescale.unit.value}"
                    self.statusBar().showMessage(f"Loaded: {file_name} (Timescale: {timescale_str})")
                else:
                    self.statusBar().showMessage(f"Loaded: {file_name}")
                # Print confirmation for CLI/integration tests
                if file_path:
                    try:
                        print(f"Successfully loaded waveform: {file_path}")
                    except Exception:
                        pass
            else:
                self.statusBar().showMessage("File loaded successfully")
        else:
            self.statusBar().showMessage("File loaded successfully")
            
        # Defer heavy UI updates to allow UI to remain responsive
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QApplication
        
        def update_design_tree():
            if session.waveform_db:
                # Show progress for tree building
                tree_progress = QProgressDialog(
                    "Building design hierarchy...",
                    None,  # No cancel button
                    0,
                    0,
                    self
                )
                tree_progress.setWindowTitle("Processing")
                tree_progress.setWindowModality(Qt.WindowModal)
                tree_progress.show()
                QApplication.processEvents()
                
                self.design_tree_view.set_waveform_db(session.waveform_db)
                    
                tree_progress.close()
                
                # Close the main progress dialog now that everything is done
                if self.progress_dialog:
                    self.progress_dialog.close()
                    self.progress_dialog = None
                # In integration/test mode, exit after load completes
                if getattr(self, 'exit_after_load', False):
                    try:
                        print("Waveform load completed, exiting as requested.")
                    except Exception:
                        pass
                    QTimer.singleShot(0, lambda: QApplication.exit(0))
                
        # Use timer to defer tree update, allowing UI to update first
        QTimer.singleShot(100, update_design_tree)
        
    def on_load_error(self, error_msg):
        """Handle file load error."""
        QMessageBox.critical(self, "Load Error", f"Failed to load file:\n{error_msg}")
        self.statusBar().showMessage("Load failed")
        # If running in test/integration mode, exit with error
        if getattr(self, 'exit_after_load', False):
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, lambda: QApplication.exit(1))
            
    def load_vcd(self, path: str):
        """Load a VCD file synchronously."""
        self.load_file(path)
                
    def save_session(self):
        """Save the current session to a YAML file."""
        if not self.wave_widget.session:
            QMessageBox.warning(self, "No Session", "No session to save.")
            return
            
        # Get file path from user
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Session",
            "",
            "YAML Files (*.yaml *.yml);;All Files (*)"
        )
        
        if file_path:
            try:
                save_session(self.wave_widget.session, Path(file_path))
                self.statusBar().showMessage(f"Session saved to: {Path(file_path).name}")
            except Exception as e:
                QMessageBox.critical(self, "Save Error", f"Failed to save session:\n{str(e)}")
                
    def load_session(self):
        """Load a session from a YAML file using file dialog."""
        # Force garbage collection before opening dialog
        import gc
        gc.collect()
        
        # Get file path from user
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Session",
            "",
            "YAML Files (*.yaml *.yml);;All Files (*)"
        )
        
        if file_path:
            # Use QTimer to defer loading, allowing the dialog to close first
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, lambda: self.load_session_file(file_path))
    
    def load_session_file(self, file_path: str):
        """Load a session from a specified file path."""
        if not os.path.exists(file_path):
            print(f"Error: Session file not found: {file_path}")
            return
            
        # Clear the design tree before loading new session
        self.design_tree_view.set_waveform_db(None)
        
        # Get filename for progress dialog
        file_name = os.path.basename(file_path)
        
        # Create progress dialog
        self.progress_dialog = QProgressDialog(
            f"Loading session {file_name}...",
            "Cancel",
            0,
            0,  # Indeterminate progress
            self
        )
        self.progress_dialog.setWindowTitle("Loading Session")
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.setMinimumDuration(0)  # Show immediately
        self.progress_dialog.setCancelButton(None)  # No cancel for now
        self.progress_dialog.show()
        
        # Update status bar
        self.statusBar().showMessage(f"Loading session {file_name}...")
        
        # Store file path for later use
        self._loading_session_path = file_path
        
        # Create and run loader
        loader = LoaderRunnable(load_session, Path(file_path))
        loader.signals.finished.connect(self._on_session_load_finished)
        loader.signals.error.connect(self._on_session_load_error)
        self.thread_pool.start(loader)
        
    def _on_session_load_finished(self, session):
        """Handle successful session load."""
        # Don't close progress dialog yet - keep it open during UI updates
        if self.progress_dialog:
            self.progress_dialog.setLabelText("Setting up UI...")
            
        # Enable waveform-related actions
        self._set_waveform_actions_enabled(True)
            
        # Update UI
        self.wave_widget.setSession(session)
        
        
        session_file = getattr(self, '_loading_session_path', 'session')
        self.statusBar().showMessage(f"Session loaded from: {Path(session_file).name}")
        print(f"Successfully loaded session from: {session_file}")
        
        # Defer heavy UI updates to allow UI to remain responsive
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QApplication
        
        def update_design_tree():
            if session.waveform_db:
                # Show progress for tree building
                tree_progress = QProgressDialog(
                    "Building design hierarchy...",
                    None,  # No cancel button
                    0,
                    0,
                    self
                )
                tree_progress.setWindowTitle("Processing")
                tree_progress.setWindowModality(Qt.WindowModal)
                tree_progress.show()
                QApplication.processEvents()
                
                self.design_tree_view.set_waveform_db(session.waveform_db)
                    
                tree_progress.close()
                
                # Close the main progress dialog now that everything is done
                if self.progress_dialog:
                    self.progress_dialog.close()
                    self.progress_dialog = None
                
        # Use timer to defer tree update, allowing UI to update first
        QTimer.singleShot(100, update_design_tree)
        
        # Clean up stored path
        # Note: hasattr check needed because _loading_session_path is a temporary attribute
        # that may not exist if loading was interrupted
        if hasattr(self, '_loading_session_path'):
            delattr(self, '_loading_session_path')
            
    def _on_session_load_error(self, error_msg):
        """Handle session load error."""
        # Close progress dialog
        if self.progress_dialog:
            self.progress_dialog.close()
            self.progress_dialog = None
        
        # Disable waveform actions on error
        self._set_waveform_actions_enabled(False)
            
        session_file = getattr(self, '_loading_session_path', 'unknown')
        error_msg = f"Failed to load session from {session_file}:\n{error_msg}"
        print(f"Error: {error_msg}")
        QMessageBox.critical(self, "Load Error", error_msg)
        self.statusBar().showMessage("Session load failed")
        
        # Clean up stored path
        # Note: hasattr check needed because _loading_session_path is a temporary attribute
        # that may not exist if loading was interrupted
        if hasattr(self, '_loading_session_path'):
            delattr(self, '_loading_session_path')

    def _expand_tree_levels(self, tree_view: QTreeView, levels: int, parent=None):
        """Recursively expand tree to specified number of levels."""
        model = tree_view.model()
        if not model:
            return
            
        if parent is None:
            # Expand from root level
            for row in range(model.rowCount()):
                index = model.index(row, 0)
                if index.isValid():
                    tree_view.expand(index)
                    if levels > 1:
                        self._expand_tree_levels(tree_view, levels - 1, index)
        else:
            if levels <= 0:
                return
                
            for row in range(model.rowCount(parent)):
                index = model.index(row, 0, parent)
                if index.isValid():
                    tree_view.expand(index)
                    self._expand_tree_levels(tree_view, levels - 1, index)


    def _on_signals_selected(self, signal_nodes):
        """Handle signals selected from the design tree view."""
        if not self.wave_widget.session:
            return
            
        for node in signal_nodes:
            self._add_node_to_session(node)
        
    def _add_node_to_session(self, new_node):
        """Add a node to the waveform session after the last selected node."""
        session = self.wave_widget.session
        model = self.wave_widget.model
        
        if session.selected_nodes:
            # Find the last selected node
            last_selected = session.selected_nodes[-1]
            
            # Find its parent and position
            if last_selected.parent:
                # Add after the selected node in its parent's children
                parent = last_selected.parent
                idx = parent.children.index(last_selected) + 1
                parent.children.insert(idx, new_node)
                new_node.parent = parent
            else:
                # It's a root node, add after it in root_nodes
                idx = session.root_nodes.index(last_selected) + 1
                session.root_nodes.insert(idx, new_node)
        else:
            # No selection, add to end of root nodes
            session.root_nodes.append(new_node)
            
        # Notify the model about the change
        if model:
            model.layoutChanged.emit()
            
        self.statusBar().showMessage(f"Added signal: {new_node.name}")
    
    def _drop_marker(self):
        """Add a marker at the current cursor position."""
        if self.wave_widget.controller and self.wave_widget.session:
            # Find the first available marker slot
            for i in range(RENDERING.MAX_MARKERS):
                marker = self.wave_widget.controller.get_marker(i)
                if not marker:
                    self.wave_widget.controller.add_marker(i, self.wave_widget.session.cursor_time)
                    self.statusBar().showMessage(f"Marker {chr(65 + i)} added at cursor position", 3000)
                    break
            else:
                self.statusBar().showMessage("All marker slots are in use", 3000)
    
    def _show_markers_window(self):
        """Show the markers management window."""
        from wavescout.markers_window import MarkersWindow
        
        if self.wave_widget.controller and self.wave_widget.session:
            dialog = MarkersWindow(self.wave_widget.controller, self)
            dialog.exec()
    
    def _set_ui_scale(self, scale: float):
        """Set the UI scaling factor."""
        # Save the scale preference
        self.settings.setValue("ui_scale", scale)
        
        # Show message
        self.statusBar().showMessage(f"UI Scale: {int(scale * 100)}%", 2000)
        
        # Inform user that restart is required
        result = QMessageBox.question(
            self,
            "UI Scaling Changed",
            f"UI scaling set to {int(scale * 100)}%.\n\n"
            "The application needs to restart for the scaling to take effect.\n"
            "Would you like to restart now?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        
        if result == QMessageBox.Yes:
            # Restart the application
            import subprocess
            subprocess.Popen([sys.executable] + sys.argv)
            QApplication.quit()
    
    def _apply_ui_scale(self, scale: float):
        """Apply the UI scaling factor to the application."""
        # Store current scale for reference
        self.current_ui_scale = scale
        
        # The actual scaling will be applied through environment variable
        # on next application start


def main():
    """Run the demo application."""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="WaveScout Waveform Viewer Demo")
    parser.add_argument("--load_session", type=str, help="Load a session file on startup")
    parser.add_argument("--load_wave", type=str, help="Load a waveform file (.vcd or .fst) on startup")
    parser.add_argument("--exit_after_load", action="store_true", help="Exit the application after loading completes (for automation/testing)")
    args = parser.parse_args()
    
    # Load saved UI scale and apply it before creating QApplication
    settings = QSettings("WaveScout", "Scout")
    saved_scale = settings.value("ui_scale", 1.0, type=float)
    
    # Set the QT_SCALE_FACTOR environment variable
    if saved_scale != 1.0:
        os.environ["QT_SCALE_FACTOR"] = str(saved_scale)
    
    # Enable high DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    
    app = QApplication(sys.argv)
    
    # Create main window with optional session or wave file
    window = WaveScoutMainWindow(session_file=args.load_session, wave_file=args.load_wave, exit_after_load=args.exit_after_load)
    window.show()
    
    print("WaveScout Demo")
    print("=============")
    if args.load_session:
        print(f"- Loading session from: {args.load_session}")
    elif args.load_wave:
        print(f"- Loading waveform from: {args.load_wave}")
    else:
        print("- Loading swerv1.vcd")
    print("- Click on waveform to move cursor")
    print("- Use View menu to zoom in/out")
    print("- Expand/collapse signal groups in the tree")
    print()
    
    # Run with standard Qt event loop
    app.exec()


if __name__ == "__main__":
    main()