#!/usr/bin/env python3
"""WaveScout Main Application Window"""

import sys
import argparse
import os
from pathlib import Path
from PySide6.QtWidgets import (QApplication, QMainWindow, 
                              QSplitter, QTreeView, QFileDialog,
                              QMessageBox, QProgressDialog, QAbstractItemView)
from PySide6.QtCore import Qt, QThreadPool, QRunnable, Signal, QObject, QSettings, QEvent
from PySide6.QtGui import QAction, QActionGroup
# QtAsyncio and asyncio removed - using single-threaded execution
from wavescout import WaveScoutWidget, create_sample_session, save_session, load_session
from wavescout.design_tree_model import DesignTreeModel


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
    """Main window for WaveScout demo."""
    
    def __init__(self, session_file=None, wave_file: str | None = None, exit_after_load: bool = False):
        super().__init__()
        self.setWindowTitle("WaveScout - Waveform Viewer Demo")
        self.resize(1400, 800)
        
        # Initialize thread pool and progress dialog
        self.thread_pool = QThreadPool()
        self.progress_dialog = None
        
        # Initialize settings
        self.settings = QSettings("WaveScout", "Demo")
        
        # Store current UI scale
        self.current_ui_scale = self.settings.value("ui_scale", 1.0, type=float)
        
        # Create main splitter
        self.main_splitter = QSplitter(Qt.Horizontal)
        
        # Create design tree (left pane)
        self.design_tree = QTreeView()
        self.design_tree.setAlternatingRowColors(True)
        # Enable multi-selection to allow adding multiple signals at once
        self.design_tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.design_tree.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.design_tree_model = DesignTreeModel()
        self.design_tree.setModel(self.design_tree_model)
        # Install event filter to handle keyboard shortcuts on the design tree
        self.design_tree.installEventFilter(self)
        
        # Connect double-click signal
        self.design_tree.doubleClicked.connect(self._on_design_tree_double_click)
        
        # Add design tree to splitter first to place it on the left
        self.main_splitter.addWidget(self.design_tree)
        
        # Create wave view widget (right pane)
        self.wave_widget = WaveScoutWidget()
        self.main_splitter.addWidget(self.wave_widget)
        
        # Set splitter sizes (design tree: 30%, wave widget: 70%)
        self.main_splitter.setSizes([420, 980])
        
        self.setCentralWidget(self.main_splitter)
        
        # Create menu bar
        self._create_menus()
        
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
        
    def _create_menus(self):
        """Create application menus."""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("&File")
        file_menu.addAction("&Open...", self.open_file)
        file_menu.addSeparator()
        file_menu.addAction("&Save Session...", self.save_session)
        file_menu.addAction("&Load Session...", self.load_session)
        file_menu.addSeparator()
        file_menu.addAction("E&xit", self.close)
        
        # View menu
        view_menu = menubar.addMenu("&View")
        view_menu.addAction("Zoom &In\t+", self.wave_widget._zoom_in)
        view_menu.addAction("Zoom &Out\t-", self.wave_widget._zoom_out)
        view_menu.addAction("Zoom to &Fit\tF", self.wave_widget._zoom_to_fit)
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
        
        # Canvas mode submenu
        canvas_mode_menu = view_menu.addMenu("Canvas &Mode")
        
        # Create action group for exclusive selection
        canvas_mode_group = QActionGroup(self)
        
        # Normal mode action
        normal_mode_action = QAction("&Normal (Waveforms)", self)
        normal_mode_action.setCheckable(True)
        normal_mode_action.setChecked(True)
        normal_mode_action.triggered.connect(lambda: self._set_canvas_mode(False))
        canvas_mode_group.addAction(normal_mode_action)
        canvas_mode_menu.addAction(normal_mode_action)
        
        # Benchmark mode action
        benchmark_mode_action = QAction("&Benchmark (Rainbow Pixels)", self)
        benchmark_mode_action.setCheckable(True)
        benchmark_mode_action.triggered.connect(lambda: self._set_canvas_mode(True))
        canvas_mode_group.addAction(benchmark_mode_action)
        canvas_mode_menu.addAction(benchmark_mode_action)
        
        # Store references for later use
        self.normal_mode_action = normal_mode_action
        self.benchmark_mode_action = benchmark_mode_action
        
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
            
        self.on_load_finished(session)
        
    def _on_waveform_load_error(self, error_msg):
        """Handle waveform load error."""
        # Close progress dialog
        if self.progress_dialog:
            self.progress_dialog.close()
            self.progress_dialog = None
            
        self.on_load_error(error_msg)
        
    def on_load_finished(self, session):
        """Handle successful file load."""
        self.wave_widget.setSession(session)
        
        # Update canvas mode menu to match session
        if session.canvas_benchmark_mode:
            self.benchmark_mode_action.setChecked(True)
        else:
            self.normal_mode_action.setChecked(True)
        
        # Get filename from the session's waveform database
        if session.waveform_db and hasattr(session.waveform_db, 'file_path'):
            file_name = Path(session.waveform_db.file_path).name
            # Include timescale info if available
            if session.timescale:
                timescale_str = f"{session.timescale.factor}{session.timescale.unit.value}"
                self.statusBar().showMessage(f"Loaded: {file_name} (Timescale: {timescale_str})")
            else:
                self.statusBar().showMessage(f"Loaded: {file_name}")
            # Print confirmation for CLI/integration tests
            try:
                print(f"Successfully loaded waveform: {session.waveform_db.file_path}")
            except Exception:
                pass
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
                
                self.design_tree_model.load_hierarchy(session.waveform_db)
                # Expand first few levels
                self._expand_tree_levels(self.design_tree, 2)
                # Resize columns to content
                for i in range(3):
                    self.design_tree.resizeColumnToContents(i)
                    
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
            
        # Clear the design tree model before loading new session
        self.design_tree_model.beginResetModel()
        self.design_tree_model.root_node = None
        self.design_tree_model.endResetModel()
        
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
            
        # Update UI
        self.wave_widget.setSession(session)
        
        # Update canvas mode menu to match session
        if session.canvas_benchmark_mode:
            self.benchmark_mode_action.setChecked(True)
        else:
            self.normal_mode_action.setChecked(True)
        
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
                
                self.design_tree_model.load_hierarchy(session.waveform_db)
                self._expand_tree_levels(self.design_tree, 2)
                for i in range(3):
                    self.design_tree.resizeColumnToContents(i)
                    
                tree_progress.close()
                
                # Close the main progress dialog now that everything is done
                if self.progress_dialog:
                    self.progress_dialog.close()
                    self.progress_dialog = None
                
        # Use timer to defer tree update, allowing UI to update first
        QTimer.singleShot(100, update_design_tree)
        
        # Clean up stored path
        if hasattr(self, '_loading_session_path'):
            delattr(self, '_loading_session_path')
            
    def _on_session_load_error(self, error_msg):
        """Handle session load error."""
        # Close progress dialog
        if self.progress_dialog:
            self.progress_dialog.close()
            self.progress_dialog = None
            
        session_file = getattr(self, '_loading_session_path', 'unknown')
        error_msg = f"Failed to load session from {session_file}:\n{error_msg}"
        print(f"Error: {error_msg}")
        QMessageBox.critical(self, "Load Error", error_msg)
        self.statusBar().showMessage("Session load failed")
        
        # Clean up stored path
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


    def _on_design_tree_double_click(self, index):
        """Handle double-click on design tree item."""
        if not index.isValid() or not self.wave_widget.session:
            return
            
        # Get the node from the design tree
        node = self.design_tree_model.data(index, Qt.UserRole)
        if not node or node.is_scope:
            # Only add signals, not scopes
            return
            
        # Create a new SignalNode with default settings
        from wavescout.data_model import SignalNode, DisplayFormat, RenderType
        
        # Get full signal path from waveform database
        full_name = self._get_full_signal_path(node)
        if not full_name:
            return
            
        # Find the handle for this signal
        handle = self._find_signal_handle(node, full_name)
        
        # Get the var object
        var = None
        if hasattr(node, 'var') and node.var is not None:
            var = node.var
        elif handle is not None:
            var = self.wave_widget.session.waveform_db.get_var(handle)
            
        if var and self.wave_widget.session.waveform_db:
            # Use the existing function to create the node
            from wavescout.waveform_loader import create_signal_node_from_wellen
            hierarchy = self.wave_widget.session.waveform_db.hierarchy
            new_node = create_signal_node_from_wellen(var, hierarchy, handle)
            # Override the name to use the full path we found
            new_node.name = full_name
        else:
            # Fallback if we don't have var object
            from wavescout.data_model import SignalNode, DisplayFormat
            new_node = SignalNode(
                name=full_name,
                handle=handle,
                format=DisplayFormat(),
                nickname="",
                children=[],
                parent=None,
                is_group=False,
                group_render_mode=None,
                is_expanded=True
            )
        
        # Add the node to the session
        self._add_node_to_session(new_node)
        
    def _get_full_signal_path(self, design_node):
        """Get the full hierarchical path for a signal from design tree."""
        if not self.wave_widget.session.waveform_db:
            return None
            
        # First try to use the var object directly
        if hasattr(design_node, 'var') and design_node.var is not None:
            if hasattr(self.wave_widget.session.waveform_db, 'hierarchy'):
                hierarchy = self.wave_widget.session.waveform_db.hierarchy
                return design_node.var.full_name(hierarchy)
        
        # Fallback to using handle if available
        elif hasattr(design_node, 'var_handle') and design_node.var_handle is not None:
            var = self.wave_widget.session.waveform_db.get_var(design_node.var_handle)
            if var and hasattr(self.wave_widget.session.waveform_db, 'hierarchy'):
                hierarchy = self.wave_widget.session.waveform_db.hierarchy
                return var.full_name(hierarchy)
        
        return None
        
    def _find_signal_handle(self, design_node, full_name):
        """Find the handle for a signal in the waveform database."""
        if not self.wave_widget.session.waveform_db:
            return None
            
        db = self.wave_widget.session.waveform_db
        hierarchy = db.hierarchy
        
        # If the design node has a var object, find its handle
        if hasattr(design_node, 'var') and design_node.var is not None:
            handle = db.get_handle_for_var(design_node.var)
            if handle is not None:
                return handle
        
        # Fallback: search by name
        return db.find_handle_by_name(full_name)
        
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
    
    def _set_canvas_mode(self, benchmark_mode: bool):
        """Set canvas rendering mode (normal or benchmark)."""
        if self.wave_widget.session:
            self.wave_widget.session.canvas_benchmark_mode = benchmark_mode
            # Invalidate the last render hash to force re-render
            if hasattr(self.wave_widget._canvas, '_last_render_hash'):
                self.wave_widget._canvas._last_render_hash = None
            # Force canvas to repaint
            self.wave_widget._canvas.update()
            
            # Update status message
            mode_name = "Benchmark (Rainbow Pixels)" if benchmark_mode else "Normal (Waveforms)"
            self.statusBar().showMessage(f"Canvas mode: {mode_name}", 2000)
    
    def eventFilter(self, watched, event):
        """Handle key shortcuts on the design tree."""
        if watched is self.design_tree and event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_I:
                # Add all selected items from the design tree into the wave widget
                sel_model = self.design_tree.selectionModel()
                if sel_model and self.wave_widget.session:
                    # Use only the first column indexes
                    indexes = sel_model.selectedRows(0)
                    # Preserve current order; add in the order as selectedRows returns
                    for idx in indexes:
                        self._on_design_tree_double_click(idx)
                    return True
        return super().eventFilter(watched, event)
    
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
    settings = QSettings("WaveScout", "Demo")
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