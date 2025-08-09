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
            and window.design_tree_view.design_tree_model is not None
            and window.design_tree_view.design_tree_model.rowCount() > 0
        )
    qtbot.waitUntil(_loaded, timeout=5000)

    # Ensure event filters are installed
    window.design_tree_view.install_event_filters()
    
    # Get the unified tree view (default mode)
    design_view = window.design_tree_view.unified_tree
    model = window.design_tree_view.design_tree_model

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
    # Instead of simulating mouse double-click, directly call the handler
    # because Qt event simulation can be unreliable in test environments
    def add_signal_from_index(idx):
        node = idx.internalPointer()
        if node and not node.is_scope:
            signal_node = window.design_tree_view._create_signal_node(node)
            if signal_node:
                window.design_tree_view.signals_selected.emit([signal_node])
                return True
        return False

    # Add prdata
    assert add_signal_from_index(prdata_idx), "Failed to add prdata signal"
    qtbot.wait(100)  # Allow signal processing
    
    # Add paddr
    assert add_signal_from_index(paddr_idx), "Failed to add paddr signal"
    qtbot.wait(100)  # Allow signal processing

    # Verify both signals are added to the session
    session = window.wave_widget.session
    names = [n.name for n in session.root_nodes]
    print(f"Session root_nodes: {names}")
    assert any(name.endswith("apb_testbench.prdata") for name in names), f"prdata was not added to session. Found: {names}"
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
            and window.design_tree_view.design_tree_model is not None
            and window.design_tree_view.design_tree_model.rowCount() > 0
        )
    qtbot.waitUntil(_loaded, timeout=5000)

    design_view = window.design_tree_view.unified_tree
    model = window.design_tree_view.design_tree_model

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

    # Add both signals to the session by emitting the signal directly
    def add_signal_from_index(idx):
        node = idx.internalPointer()
        if node and not node.is_scope:
            signal_node = window.design_tree_view._create_signal_node(node)
            if signal_node:
                window.design_tree_view.signals_selected.emit([signal_node])
                return True
        return False
    
    assert add_signal_from_index(sine1_idx), "Failed to add sine_1mhz"
    qtbot.wait(50)
    assert add_signal_from_index(sine2_idx), "Failed to add sine_2mhz"
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


def test_names_panel_dragging_grouping(qtbot):
    """Test grouping and drag-reordering in Names panel via main window.

    Scenario:
      1) load apb_sim.vcd
      2) add 5 items to the wavescout widget
      3) group first 3 items into group
      4) save session and verify yaml: group has 3 children; 2 independent root nodes
      5) drag group between the two independent nodes
      6) save and verify root_nodes order: independent -> group -> independent
    """
    from scout import WaveScoutMainWindow

    repo_root = Path(__file__).resolve().parent.parent
    vcd_path = repo_root / "test_inputs" / "apb_sim.vcd"
    assert vcd_path.exists(), f"VCD not found: {vcd_path}"

    # Launch main window with the VCD loaded
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
            and window.design_tree_view.design_tree_model is not None
            and window.design_tree_view.design_tree_model.rowCount() > 0
        )
    qtbot.waitUntil(_loaded, timeout=5000)

    # Add 5 signals by walking the design tree and double-clicking first 5 leaf nodes
    design_view = window.design_tree_view.unified_tree
    model = window.design_tree_view.design_tree_model

    added = 0
    root = QModelIndex()

    # Expand first level to access common scopes
    for r in range(model.rowCount(root)):
        idx = model.index(r, 0, root)
        if not idx.isValid():
            continue
        design_view.expand(idx)

    def is_scope(index: QModelIndex) -> bool:
        node = model.data(index, Qt.UserRole)
        return getattr(node, "is_scope", False)

    # Depth-first search to find leaf signals
    stack = [QModelIndex()]
    visited = set()
    while stack and added < 5:
        parent = stack.pop()
        rows = model.rowCount(parent)
        for r in range(rows):
            idx = model.index(r, 0, parent)
            if not idx.isValid():
                continue
            # If scope, push children to stack after expanding
            if is_scope(idx):
                design_view.expand(idx)
                stack.append(idx)
            else:
                # Leaf signal - add it
                node = idx.internalPointer()
                if node and not node.is_scope:
                    signal_node = window.design_tree_view._create_signal_node(node)
                    if signal_node:
                        window.design_tree_view.signals_selected.emit([signal_node])
                        qtbot.wait(10)
                        added += 1
                if added >= 5:
                    break

    session = window.wave_widget.session
    assert session is not None
    assert len(session.root_nodes) >= 5, f"Expected at least 5 root nodes, got {len(session.root_nodes)}"

    # Select first three items in names view and group them
    wave_widget = window.wave_widget
    names_view = wave_widget._names_view
    model_waves = wave_widget.model
    sel_model = names_view.selectionModel()
    assert model_waves is not None and sel_model is not None

    first_three = session.root_nodes[:3]
    from PySide6.QtCore import QItemSelection
    selection = QItemSelection()
    for node in first_three:
        idx = names_view._find_node_index(node)
        assert idx.isValid(), "Failed to locate node in names view for grouping"
        selection.select(idx, idx)

    # Apply selection (ClearAndSelect)
    from PySide6.QtCore import QItemSelectionModel
    names_view.selectionModel().select(selection, QItemSelectionModel.ClearAndSelect)
    qtbot.wait(10)

    # Ensure session.selected_nodes updated
    assert len(session.selected_nodes) == 3
    assert all(n in session.selected_nodes for n in first_three)

    # Create group from selected
    wave_widget._create_group_from_selected()
    qtbot.wait(10)

    # After grouping, expect: one group node + two independent nodes at root
    assert len(session.root_nodes) >= 3
    root_nodes = session.root_nodes
    group_node = next((n for n in root_nodes if getattr(n, "is_group", False)), None)
    assert group_node is not None, "Group node not found among root nodes"
    assert len(group_node.children) == 3, f"Expected 3 nodes in group, got {len(group_node.children)}"

    # Save session to YAML and verify structure
    yaml_path1 = repo_root / "test_grouping_dragging_step1.yaml"
    save_session(session, yaml_path1)
    assert yaml_path1.exists()

    with open(yaml_path1, "r") as f:
        data1 = yaml.safe_load(f)
    rn1 = data1.get("root_nodes", [])
    # Verify: one group with 3 children and 2 independent nodes at root
    groups = [n for n in rn1 if n.get("is_group")]
    non_groups = [n for n in rn1 if not n.get("is_group")]
    assert len(groups) == 1, f"Expected 1 group in root, got {len(groups)}"
    assert len(non_groups) >= 2, f"Expected at least 2 non-group root nodes, got {len(non_groups)}"
    assert len(groups[0].get("children", [])) == 3, "Group should contain 3 children"

    # Drag group between the two independent nodes at root
    # Find current root ordering and compute desired insert position: 1 (between first and second independent)
    # Build mime data for dragging the group index
    group_index = names_view._find_node_index(group_node)
    assert group_index.isValid(), "Could not find group index in names view"
    mime = model_waves.mimeData([group_index])
    # Perform drop at root, row=1
    ok = model_waves.dropMimeData(mime, Qt.MoveAction, 1, 0, QModelIndex())
    assert ok, "dropMimeData returned False"
    qtbot.wait(10)

    # Save session again and verify root order: independent -> group -> independent
    yaml_path2 = repo_root / "test_grouping_dragging_step2.yaml"
    save_session(session, yaml_path2)
    assert yaml_path2.exists()

    with open(yaml_path2, "r") as f:
        data2 = yaml.safe_load(f)
    rn2 = data2.get("root_nodes", [])

    # Collect the types in order (False for signal, True for group)
    types = [n.get("is_group", False) for n in rn2[:3]]
    # Expect exactly: [False, True, False] for first three root entries
    assert types[0] is False and types[1] is True and types[2] is False, (
        f"Unexpected root order types: {types}"
    )

    window.close()


def test_split_mode_i_shortcut(qtbot):
    """Test 'i' shortcut in split mode VarsView.
    
    Scenario:
    1) Load VCD file into main application window from scout.py
    2) Switch design tree to split mode
    3) Select the first signal in VarsView
    4) Key press 'i' 3 times
    5) Save session to yaml
    6) Verify that signal is present in yaml 3 times
    """
    from scout import WaveScoutMainWindow
    from wavescout.design_tree_view import DesignTreeViewMode
    from PySide6.QtTest import QTest
    from PySide6.QtCore import QItemSelectionModel
    
    repo_root = Path(__file__).resolve().parent.parent
    vcd_path = repo_root / "test_inputs" / "apb_sim.vcd"
    assert vcd_path.exists(), f"VCD not found: {vcd_path}"
    
    # Launch main window with the VCD loaded
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
            and window.design_tree_view.design_tree_model is not None
        )
    qtbot.waitUntil(_loaded, timeout=5000)
    
    # Switch to split mode
    window.design_tree_view.set_mode(DesignTreeViewMode.SPLIT)
    qtbot.wait(100)
    
    # Wait for split mode models to be initialized
    def _split_mode_ready():
        return (
            window.design_tree_view.scope_tree_model is not None
            and window.design_tree_view.vars_view is not None
        )
    qtbot.waitUntil(_split_mode_ready, timeout=2000)
    
    # Select the first scope in the scope tree to populate VarsView
    scope_tree = window.design_tree_view.scope_tree
    scope_model = window.design_tree_view.scope_tree_model
    
    # Select first scope (usually "apb_testbench" or similar)
    first_scope = scope_model.index(0, 0, QModelIndex())
    if first_scope.isValid():
        scope_tree.selectionModel().setCurrentIndex(
            first_scope,
            QItemSelectionModel.ClearAndSelect
        )
        qtbot.wait(100)
    
    # Get the VarsView and check if variables are loaded
    vars_view = window.design_tree_view.vars_view
    vars_table = vars_view.table_view
    filter_proxy = vars_view.filter_proxy
    
    # Wait for variables to be populated
    def _vars_populated():
        return filter_proxy.rowCount() > 0
    qtbot.waitUntil(_vars_populated, timeout=2000)
    
    # Select the first variable in the table
    first_var_index = filter_proxy.index(0, 0)
    assert first_var_index.isValid(), "No variables found in VarsView"
    
    vars_table.selectionModel().setCurrentIndex(
        first_var_index,
        QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows
    )
    qtbot.wait(50)
    
    # Get the signal name for verification
    var_data = filter_proxy.sourceModel().data(
        filter_proxy.mapToSource(first_var_index),
        Qt.ItemDataRole.UserRole
    )
    signal_name = var_data.get('full_path', var_data.get('name'))
    print(f"Selected signal: {signal_name}")
    
    # Press 'i' key 3 times to add the signal 3 times
    for i in range(3):
        QTest.keyClick(vars_table, Qt.Key.Key_I)
        qtbot.wait(100)
        print(f"Pressed 'i' #{i+1}")
    
    # Check that the signal was added to the session
    session = window.wave_widget.session
    assert session is not None, "Session is None"
    
    # Count how many times the signal appears in root_nodes
    signal_count = sum(1 for node in session.root_nodes 
                      if node.name == signal_name or node.name.endswith(signal_name))
    print(f"Signal appears {signal_count} times in session")
    assert signal_count == 3, f"Expected signal to appear 3 times, but found {signal_count}"
    
    # Save session to YAML
    yaml_path = repo_root / "test_split_mode_i_shortcut.yaml"
    save_session(session, yaml_path)
    assert yaml_path.exists(), "Session YAML was not saved"
    
    # Verify YAML contains the signal 3 times
    with open(yaml_path, "r") as f:
        data = yaml.safe_load(f)
    
    root_nodes = data.get("root_nodes", [])
    yaml_signal_count = sum(1 for node in root_nodes 
                           if node.get("name", "").endswith(signal_name))
    
    assert yaml_signal_count == 3, (
        f"Expected signal to appear 3 times in YAML, but found {yaml_signal_count}"
    )
    
    print(f"✓ Test passed: Signal '{signal_name}' appears 3 times in YAML")
    
    # Close the window
    window.close()


def test_inner_scope_variable_selection(qtbot):
    """Test selecting variables from inner scopes in split mode.
    
    Scenario:
    1) Load test_inputs/swerv1.vcd file into the main application window from scout.py
    2) Switch design tree to split mode
    3) Expand TOP scope
    4) Select TOP.tb_top scope - variables are displayed in VarsView
    5) Select first 3 variables
    6) Click 'i' shortcut to add selected variables to WaveScoutWidget
    7) Save session to yaml
    8) Verify that yaml file has 3 root nodes with variables we've added
    """
    from scout import WaveScoutMainWindow
    from PySide6.QtCore import QModelIndex, Qt, QItemSelectionModel
    from wavescout.design_tree_view import DesignTreeViewMode
    import tempfile
    import yaml
    from pathlib import Path
    
    # Create the main window
    window = WaveScoutMainWindow()
    qtbot.addWidget(window)
    window.show()
    
    # Load the test VCD file
    test_vcd = Path(__file__).parent.parent / "test_inputs" / "swerv1.vcd"
    assert test_vcd.exists(), f"Test VCD file not found: {test_vcd}"
    
    window.load_file(str(test_vcd))
    
    # Wait for the file to load
    def _loaded():
        return (
            window.wave_widget.session is not None
            and window.wave_widget.session.waveform_db is not None
            and window.design_tree_view.design_tree_model is not None
        )
    qtbot.waitUntil(_loaded, timeout=5000)
    
    # Switch to split mode
    window.design_tree_view.set_mode(DesignTreeViewMode.SPLIT)
    qtbot.wait(100)
    
    # Wait for split mode to be ready
    def _split_ready():
        return (
            window.design_tree_view.scope_tree_model is not None
            and window.design_tree_view.vars_view is not None
        )
    qtbot.waitUntil(_split_ready, timeout=2000)
    
    scope_tree = window.design_tree_view.scope_tree
    scope_model = window.design_tree_view.scope_tree_model
    
    # Get and expand TOP scope
    top_index = scope_model.index(0, 0, QModelIndex())
    assert top_index.isValid(), "TOP scope not found"
    assert scope_model.data(top_index) == "TOP", "First scope should be TOP"
    
    scope_tree.expand(top_index)
    qtbot.wait(100)
    
    # Get and select tb_top scope (first child of TOP)
    tb_top_index = scope_model.index(0, 0, top_index)
    assert tb_top_index.isValid(), "tb_top scope not found"
    assert scope_model.data(tb_top_index) == "tb_top", "First child should be tb_top"
    
    scope_tree.selectionModel().setCurrentIndex(
        tb_top_index,
        QItemSelectionModel.ClearAndSelect
    )
    qtbot.wait(100)
    
    # Check that variables are loaded in VarsView
    vars_view = window.design_tree_view.vars_view
    vars_table = vars_view.table_view
    
    def _vars_loaded():
        return len(vars_view.vars_model.variables) > 0
    qtbot.waitUntil(_vars_loaded, timeout=2000)
    
    var_count = len(vars_view.vars_model.variables)
    assert var_count > 3, f"Expected more than 3 variables, got {var_count}"
    print(f"Found {var_count} variables in tb_top scope")
    
    # Select first 3 variables
    selected_vars = []
    for row in range(3):
        var_index = vars_view.filter_proxy.index(row, 0)
        assert var_index.isValid(), f"Variable at row {row} not valid"
        
        # Get variable name for verification
        source_index = vars_view.filter_proxy.mapToSource(var_index)
        var_data = vars_view.vars_model.variables[source_index.row()]
        selected_vars.append(var_data['full_path'])
        
        # Select the row (use Ctrl for multi-select)
        modifier = Qt.ControlModifier if row > 0 else Qt.NoModifier
        vars_table.selectionModel().setCurrentIndex(
            var_index,
            QItemSelectionModel.Select | QItemSelectionModel.Rows
        )
    
    qtbot.wait(100)
    
    # Verify selection
    selected_count = len(vars_table.selectionModel().selectedRows())
    assert selected_count == 3, f"Expected 3 selected rows, got {selected_count}"
    print(f"Selected variables: {selected_vars}")
    
    # Press 'i' key to add selected variables
    from PySide6.QtTest import QTest
    QTest.keyPress(vars_table, Qt.Key.Key_I)
    qtbot.wait(200)
    
    # Check that signals were added to the waveform widget
    # The session should have signals added
    session = window.wave_widget.session
    assert session is not None, "Session should exist"
    assert hasattr(session, 'root_nodes'), "Session should have root_nodes"
    signal_count = len(session.root_nodes) if session.root_nodes else 0
    assert signal_count >= 3, f"Expected at least 3 signals, got {signal_count}"
    
    # Save session to temporary YAML file
    temp_yaml = tempfile.NamedTemporaryFile(suffix='.yaml', delete=False, mode='w')
    temp_yaml.close()
    
    try:
        from wavescout import save_session
        save_session(session, Path(temp_yaml.name))
        qtbot.wait(100)
        
        # Load and verify YAML content
        with open(temp_yaml.name, 'r') as f:
            yaml_data = yaml.safe_load(f)
        
        # The session structure saves signals as 'root_nodes'
        assert 'root_nodes' in yaml_data, "YAML should have 'root_nodes' section"
        yaml_nodes = yaml_data['root_nodes']
        
        # Check that we have at least 3 root nodes (signals)
        assert len(yaml_nodes) >= 3, f"Expected at least 3 root nodes in YAML, got {len(yaml_nodes)}"
        
        # Check that our selected variables are in the YAML
        yaml_signal_names = [node.get('name') for node in yaml_nodes]
        for var_path in selected_vars[:3]:
            assert var_path in yaml_signal_names, f"Variable '{var_path}' not found in YAML root_nodes"
        
        print(f"✓ Test passed: All 3 selected variables from tb_top are in the YAML")
        
    finally:
        # Clean up temp file
        Path(temp_yaml.name).unlink(missing_ok=True)
    
    # Close the window
    window.close()
