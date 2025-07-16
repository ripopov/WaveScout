import os
import sys
import subprocess
import time
from pathlib import Path

import pytest
import yaml
from PySide6.QtWidgets import QApplication, QMenu
from PySide6.QtCore import Qt, QModelIndex
from wavescout import create_sample_session, WaveScoutWidget, save_session
from wavescout.waveform_loader import create_signal_node_from_wellen


def test_load_wave_apb_sim_vcd():
    # Path to the repo root and scout.py
    repo_root = Path(__file__).resolve().parent.parent
    scout_py = repo_root / "scout.py"
    wave_path = repo_root / "test_inputs" / "apb_sim.vcd"

    assert scout_py.exists(), f"scout.py not found at {scout_py}"
    assert wave_path.exists(), f"Waveform file not found: {wave_path}"

    # Run Qt in offscreen mode for CI/headless environments
    env = os.environ.copy()
    env.setdefault("QT_QPA_PLATFORM", "offscreen")

    # Run the application to load the waveform and exit after load
    cmd = [sys.executable, str(scout_py), "--load_wave", str(wave_path), "--exit_after_load"]

    proc = subprocess.run(
        cmd,
        cwd=str(repo_root),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=120,
    )

    # Debug help on failure
    if proc.returncode != 0:
        print("STDOUT:\n" + proc.stdout)
        print("STDERR:\n" + proc.stderr)

    assert proc.returncode == 0, "Application exited with non-zero code"
    # We expect a confirmation line from the app including the absolute path or the given path
    assert "Successfully loaded waveform" in proc.stdout
    assert "apb_sim.vcd" in proc.stdout


def test_height_scaling(qtbot):
    # Prepare session and widget
    repo_root = Path(__file__).resolve().parent.parent
    vcd_path = repo_root / "test_inputs" / "apb_sim.vcd"
    assert vcd_path.exists(), f"VCD not found: {vcd_path}"

    session = create_sample_session(str(vcd_path))

    widget = WaveScoutWidget()
    widget.resize(1200, 800)
    widget.setSession(session)
    qtbot.addWidget(widget)
    widget.show()
    qtbot.waitExposed(widget)

    # Add apb_testbench.prdata and apb_testbench.paddr to the session
    db = session.waveform_db
    assert db is not None and db.hierarchy is not None
    hierarchy = db.hierarchy

    prdata_node = None
    paddr_node = None

    target_suffixes = {
        "prdata": ("prdata", None),
        "paddr": ("paddr", None),
    }

    for handle, vars_list in db.iter_handles_and_vars():
        for var in vars_list:
            full_name = var.full_name(hierarchy)
            if full_name.endswith("apb_testbench.prdata"):
                node = create_signal_node_from_wellen(var, hierarchy, handle)
                node.name = full_name
                prdata_node = node
            elif full_name.endswith("apb_testbench.paddr"):
                node = create_signal_node_from_wellen(var, hierarchy, handle)
                node.name = full_name
                paddr_node = node
        if prdata_node and paddr_node:
            break

    assert prdata_node is not None, "apb_testbench.prdata not found in VCD"
    assert paddr_node is not None, "apb_testbench.paddr not found in VCD"

    session.root_nodes.append(prdata_node)
    session.root_nodes.append(paddr_node)

    # Notify model about changes
    widget.model.layoutChanged.emit()
    qtbot.wait(50)

    # Simulate context menu action: Set Height Scaling -> 8x for prdata
    # Use the names view internal API to set the height scaling as the context menu would
    names_view = widget._names_view
    # Ensure default is not 8
    assert prdata_node.height_scaling != 8
    names_view._set_height_scaling(prdata_node, 8)

    # Snapshot of application (the WaveScout widget)
    snap_path = repo_root / "snap01.png"
    pixmap = widget.grab()
    pixmap.save(str(snap_path))
    assert snap_path.exists(), "Snapshot was not saved"

    # Save session via API (equivalent to File -> Save Session...)
    yaml_path = repo_root / "test_height_scaling.yaml"
    save_session(session, yaml_path)
    assert yaml_path.exists(), "Session YAML was not saved"

    # Verify that YAML has height_scaling 8 for apb_testbench.prdata
    with open(yaml_path, "r") as f:
        data = yaml.safe_load(f)
    nodes = data.get("root_nodes", [])
    prdata_yaml = None
    for n in nodes:
        if n.get("name", "").endswith("apb_testbench.prdata"):
            prdata_yaml = n
            break
    assert prdata_yaml is not None, "prdata node not found in saved YAML"
    assert prdata_yaml.get("height_scaling") == 8, f"Expected height_scaling 8, got {prdata_yaml.get('height_scaling')}"

    # Wait for 2 seconds then close application
    # qtbot.wait(2000)
    widget.close()


def test_height_scaling_ui(qtbot):
    # Prepare main window and load waveform
    from scout import WaveScoutMainWindow

    repo_root = Path(__file__).resolve().parent.parent
    vcd_path = repo_root / "test_inputs" / "apb_sim.vcd"
    assert vcd_path.exists(), f"VCD not found: {vcd_path}"

    window = WaveScoutMainWindow(wave_file=str(vcd_path))
    window.resize(1400, 900)
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)

    # Wait until the session is loaded and the design tree is populated
    def _loaded():
        return (
            window.wave_widget.session is not None
            and window.wave_widget.session.waveform_db is not None
            and window.design_tree.model() is not None
            and window.design_tree.model().rowCount() > 0
        )
    qtbot.waitUntil(_loaded, timeout=5000)

    design_view = window.design_tree
    model = design_view.model()

    # Helper to find first child index by display name under a given parent index
    def find_child_by_name(parent_index, name: str):
        rows = model.rowCount(parent_index)
        for r in range(rows):
            idx = model.index(r, 0, parent_index)
            if not idx.isValid():
                continue
            if model.data(idx, Qt.DisplayRole) == name:
                return idx
        return None

    # Find the 'apb_testbench' scope at root level
    root = QModelIndex()
    apb_idx = find_child_by_name(root, "apb_testbench")
    assert apb_idx and apb_idx.isValid(), "apb_testbench scope not found in design tree"

    # Ensure scope is expanded
    design_view.expand(apb_idx)
    qtbot.wait(50)

    # Locate prdata and paddr under apb_testbench
    prdata_idx = find_child_by_name(apb_idx, "prdata")
    paddr_idx = find_child_by_name(apb_idx, "paddr")
    assert prdata_idx and prdata_idx.isValid(), "prdata not found under apb_testbench"
    assert paddr_idx and paddr_idx.isValid(), "paddr not found under apb_testbench"

    # Double-click to add prdata and paddr to the waveform session
    def dclick_index(idx):
        rect = design_view.visualRect(idx)
        assert rect.isValid(), "Invalid visual rect for index"
        pos = rect.center()
        # In some offscreen environments, QTreeView may not emit doubleClicked reliably.
        # Call the slot directly to simulate double-click behavior.
        window._on_design_tree_double_click(idx)

    dclick_index(prdata_idx)
    qtbot.wait(50)
    dclick_index(paddr_idx)
    qtbot.wait(100)

    # Verify both signals are added to the session
    session = window.wave_widget.session
    names = [n.name for n in session.root_nodes]
    assert any(name.endswith("apb_testbench.prdata") for name in names), "prdata was not added to session"
    assert any(name.endswith("apb_testbench.paddr") for name in names), "paddr was not added to session"

    # Find the SignalNode for prdata from the session for later assertion
    prdata_node = next(n for n in session.root_nodes if n.name.endswith("apb_testbench.prdata"))

    # Open context menu in the names view for prdata and choose Set Height Scaling -> 8x
    names_view = window.wave_widget._names_view
    index = names_view._find_node_index(prdata_node)
    assert index.isValid(), "Index for prdata not found in names view"
    names_view.scrollTo(index)
    rect = names_view.visualRect(index)
    assert rect.isValid(), "Visual rect for prdata is invalid"
    click_pos = rect.center()

    # Directly set height scaling using the same method invoked by the context menu
    names_view._set_height_scaling(prdata_node, 8)

    # Verify the node height scaling changed
    assert prdata_node.height_scaling == 8, f"Expected height_scaling 8, got {prdata_node.height_scaling}"

    # Snapshot of the whole application window
    snap_path = repo_root / "snap01.png"
    pixmap = window.grab()
    pixmap.save(str(snap_path))
    assert snap_path.exists(), "Snapshot was not saved"

    # Save session via API and validate YAML
    yaml_path = repo_root / "test_height_scaling.yaml"
    save_session(session, yaml_path)
    assert yaml_path.exists(), "Session YAML was not saved"

    with open(yaml_path, "r") as f:
        data = yaml.safe_load(f)
    nodes = data.get("root_nodes", [])
    prdata_yaml = None
    for n in nodes:
        if n.get("name", "").endswith("apb_testbench.prdata"):
            prdata_yaml = n
            break
    assert prdata_yaml is not None, "prdata node not found in saved YAML"
    assert prdata_yaml.get("height_scaling") == 8, (
        f"Expected height_scaling 8, got {prdata_yaml.get('height_scaling')}"
    )

    # Wait for 2 seconds then close application
    # qtbot.wait(2000)
    window.close()


def test_height_scaling_for_analog_sines(qtbot):
    """Load analog_signals_short.vcd, add top.sine_1mhz and top.sine_2mhz,
    set different height scaling, save session and verify YAML."""
    from scout import WaveScoutMainWindow

    repo_root = Path(__file__).resolve().parent.parent
    vcd_path = repo_root / "test_inputs" / "analog_signals_short.vcd"
    assert vcd_path.exists(), f"VCD not found: {vcd_path}"

    # Create and show main window with the VCD loaded
    window = WaveScoutMainWindow(wave_file=str(vcd_path))
    window.resize(1400, 900)
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)

    # Wait until session and design tree are ready
    def _loaded():
        return (
            window.wave_widget.session is not None
            and window.wave_widget.session.waveform_db is not None
            and window.design_tree.model() is not None
            and window.design_tree.model().rowCount() > 0
        )
    qtbot.waitUntil(_loaded, timeout=5000)

    design_view = window.design_tree
    model = design_view.model()

    # Helper to find child by name under a parent index
    def find_child_by_name(parent_index, name: str):
        rows = model.rowCount(parent_index)
        for r in range(rows):
            idx = model.index(r, 0, parent_index)
            if not idx.isValid():
                continue
            if model.data(idx, Qt.DisplayRole) == name:
                return idx
        return None

    # Navigate to top scope and find sine signals
    root = QModelIndex()
    top_idx = find_child_by_name(root, "top")
    assert top_idx and top_idx.isValid(), "top scope not found in design tree"
    design_view.expand(top_idx)
    qtbot.wait(50)

    sine1_idx = find_child_by_name(top_idx, "sine_1mhz")
    sine2_idx = find_child_by_name(top_idx, "sine_2mhz")
    assert sine1_idx and sine1_idx.isValid(), "sine_1mhz not found under top"
    assert sine2_idx and sine2_idx.isValid(), "sine_2mhz not found under top"

    # Add both signals to the session by simulating double click handler
    window._on_design_tree_double_click(sine1_idx)
    qtbot.wait(50)
    window._on_design_tree_double_click(sine2_idx)
    qtbot.wait(100)

    # Retrieve nodes from session
    session = window.wave_widget.session
    names = [n.name for n in session.root_nodes]
    assert any(name.endswith("top.sine_1mhz") for name in names), "top.sine_1mhz was not added to session"
    assert any(name.endswith("top.sine_2mhz") for name in names), "top.sine_2mhz was not added to session"

    sine1_node = next(n for n in session.root_nodes if n.name.endswith("top.sine_1mhz"))
    sine2_node = next(n for n in session.root_nodes if n.name.endswith("top.sine_2mhz"))

    # Set height scaling: 8x for sine_1mhz and 3x for sine_2mhz
    names_view = window.wave_widget._names_view
    names_view._set_height_scaling(sine1_node, 8)
    names_view._set_height_scaling(sine2_node, 3)

    assert sine1_node.height_scaling == 8
    assert sine2_node.height_scaling == 3

    # Save session to YAML and verify contents
    yaml_path = repo_root / "test_height_scaling_analog.yaml"
    save_session(session, yaml_path)
    assert yaml_path.exists(), "Session YAML was not saved"

    with open(yaml_path, "r") as f:
        data = yaml.safe_load(f)
    nodes = data.get("root_nodes", [])

    s1_yaml = next((n for n in nodes if n.get("name", "").endswith("top.sine_1mhz")), None)
    s2_yaml = next((n for n in nodes if n.get("name", "").endswith("top.sine_2mhz")), None)

    assert s1_yaml is not None, "top.sine_1mhz node not found in saved YAML"
    assert s2_yaml is not None, "top.sine_2mhz node not found in saved YAML"
    assert s1_yaml.get("height_scaling") == 8, f"Expected 8x for sine_1mhz, got {s1_yaml.get('height_scaling')}"
    assert s2_yaml.get("height_scaling") == 3, f"Expected 3x for sine_2mhz, got {s2_yaml.get('height_scaling')}"

    # # wait 2 sec
    # qtbot.wait(2000)

    # done: close
    window.close()
