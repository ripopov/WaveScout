#!/usr/bin/env python3
"""
Generate PNG snapshots of WaveScout waveform viewer from saved sessions.

Usage:
    python take_snapshot.py <session.yaml> [output.png]
    
Args:
    session.yaml - WaveScout session file (auto-detected if omitted)
    output.png   - Output image path (default: snapshot.png)

Renders a 1200x800 WaveScout widget with the loaded session and saves it as PNG.
Useful for documentation, testing, and sharing waveform views.
"""

import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from wavescout import WaveScoutWidget, load_session

def take_snapshot(session_file: str, output_file: str = "snapshot.png"):
    """Load a session and take a snapshot of the widget."""
    app = QApplication(sys.argv)
    
    # Apply dark theme
    app.setStyle("Fusion")
    
    # Create widget
    widget = WaveScoutWidget()
    widget.resize(1200, 800)
    
    # Load session
    print(f"Loading session from: {session_file}")
    session = load_session(Path(session_file))
    widget.setSession(session)
    
    # Show widget (needed for rendering)
    widget.show()
    
    # Process events to ensure proper layout
    app.processEvents()
    
    # Use a timer to take the snapshot after the widget is fully rendered
    def grab_snapshot():
        pixmap = widget.grab()
        pixmap.save(output_file)
        print(f"Snapshot saved to: {output_file}")
        app.quit()
    
    QTimer.singleShot(50, grab_snapshot)
    app.exec()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        # Look for existing session files
        session_files = list(Path(".").glob("*.yaml")) + list(Path(".").glob("*.yml"))
        if session_files:
            session_file = str(session_files[0])
            print(f"No session file specified, using: {session_file}")
        else:
            print("Usage: python take_snapshot.py <session_file.yaml> [output_file.png]")
            print("Error: No session file specified and no .yaml files found in current directory")
            sys.exit(1)
    else:
        session_file = sys.argv[1]
    
    output_file = sys.argv[2] if len(sys.argv) > 2 else "snapshot.png"
    
    take_snapshot(session_file, output_file)