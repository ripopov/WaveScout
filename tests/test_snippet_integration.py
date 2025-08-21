"""Integration tests for the Signal Snippets feature."""

import json
import tempfile
from pathlib import Path
from typing import Optional
import pytest
from PySide6.QtWidgets import QApplication
from wavescout.data_model import SignalNode, DisplayFormat, DataFormat, RenderType, WaveformSession
from wavescout.snippet_manager import Snippet, SnippetManager
from wavescout.persistence import serialize_snippet_nodes, deserialize_snippet_nodes
from wavescout.waveform_db import WaveformDB
from wavescout.snippet_dialogs import InstantiateSnippetDialog


@pytest.fixture(scope="module")
def qapp():
    """Create QApplication for tests."""
    app = QApplication.instance()
    if not app:
        app = QApplication([])
    yield app


@pytest.fixture
def waveform_db():
    """Load real VCD file for testing."""
    db = WaveformDB()
    test_vcd = Path("test_inputs/swerv1.vcd")
    if not test_vcd.exists():
        pytest.skip(f"Test VCD file not found: {test_vcd}")
    db.open(str(test_vcd))
    return db


@pytest.fixture
def snippet_manager(tmp_path, monkeypatch):
    """Create SnippetManager with temporary directory."""
    # Monkey-patch the snippets directory to use temp dir
    manager = SnippetManager()
    temp_snippets_dir = tmp_path / "snippets"
    temp_snippets_dir.mkdir()
    monkeypatch.setattr(manager, '_snippets_dir', temp_snippets_dir)
    manager._snippets.clear()
    return manager


def find_test_signals(waveform_db: WaveformDB, scope_prefix: str, count: int = 3) -> list[tuple[str, int]]:
    """Find test signals from a specific scope in the waveform."""
    signals = []
    
    if not waveform_db.hierarchy:
        return signals
    
    def collect_signals(scope, current_path=""):
        nonlocal signals
        if len(signals) >= count:
            return
            
        scope_name = scope.name(waveform_db.hierarchy)
        full_path = f"{current_path}.{scope_name}" if current_path else scope_name
        
        # Check if this scope matches our prefix
        if full_path.startswith(scope_prefix):
            # Collect signals from this scope
            for var in scope.vars(waveform_db.hierarchy):
                if len(signals) >= count:
                    break
                var_name = var.name(waveform_db.hierarchy)
                full_name = f"{full_path}.{var_name}"
                handle = waveform_db.find_handle_by_path(full_name)
                if handle is not None:
                    signals.append((full_name, handle))
        
        # Recurse into child scopes
        for child_scope in scope.scopes(waveform_db.hierarchy):
            collect_signals(child_scope, full_path)
    
    # Start from top scopes
    for top_scope in waveform_db.hierarchy.top_scopes():
        collect_signals(top_scope)
    
    return signals


class TestSnippetSaveLoad:
    """Test saving and loading snippets."""
    
    def test_create_and_save_snippet(self, waveform_db, snippet_manager):
        """Test creating a snippet from signal nodes."""
        # Find some real signals from the VCD
        test_signals = find_test_signals(waveform_db, "TOP", count=3)
        assert len(test_signals) > 0, "No test signals found in VCD"
        
        # Create signal nodes
        signal_nodes = []
        for signal_name, handle in test_signals:
            node = SignalNode(
                name=signal_name,
                handle=handle,
                format=DisplayFormat(data_format=DataFormat.HEX),
                is_multi_bit=True
            )
            signal_nodes.append(node)
        
        # Find common parent
        parent_scope = snippet_manager.find_common_parent(
            SignalNode(name="group", is_group=True, children=signal_nodes)
        )
        
        # Create and save snippet
        snippet = Snippet(
            name="test_memory_signals",
            parent_name=parent_scope,
            num_nodes=len(signal_nodes),
            nodes=signal_nodes,
            description="Test snippet with memory signals"
        )
        
        assert snippet_manager.save_snippet(snippet)
        assert snippet_manager.snippet_exists("test_memory_signals")
        
        # Verify saved file exists
        snippet_file = snippet_manager._snippets_dir / "test_memory_signals.json"
        assert snippet_file.exists()
        
        # Load and verify JSON structure
        with open(snippet_file, 'r') as f:
            data = json.load(f)
        
        assert data["name"] == "test_memory_signals"
        assert data["parent_name"] == parent_scope
        assert data["num_nodes"] == len(signal_nodes)
        assert len(data["nodes"]) == len(signal_nodes)
        
        # Verify handles are -1 in saved snippet
        for node_data in data["nodes"]:
            assert node_data["handle"] == -1, "Snippet handles should be -1"
    
    def test_load_snippet_from_disk(self, snippet_manager, tmp_path):
        """Test loading snippet from JSON file."""
        # Create a test snippet JSON file
        snippet_data = {
            "name": "test_load",
            "parent_name": "TOP.core",
            "num_nodes": 2,
            "description": "Test loading",
            "created_at": "2024-01-01T00:00:00",
            "nodes": [
                {
                    "name": "signal1",
                    "handle": -1,
                    "format": {
                        "data_format": "hex",
                        "render_type": "bus"
                    },
                    "nickname": None,
                    "is_group": False,
                    "group_render_mode": None,
                    "is_expanded": True,
                    "height_scaling": 1.0,
                    "is_multi_bit": True
                },
                {
                    "name": "signal2",
                    "handle": -1,
                    "format": {
                        "data_format": "bin",
                        "render_type": "bus"
                    },
                    "nickname": None,
                    "is_group": False,
                    "group_render_mode": None,
                    "is_expanded": True,
                    "height_scaling": 1.0,
                    "is_multi_bit": False
                }
            ]
        }
        
        # Save to file
        snippet_file = snippet_manager._snippets_dir / "test_load.json"
        with open(snippet_file, 'w') as f:
            json.dump(snippet_data, f)
        
        # Load snippets
        snippet_manager.load_snippets()
        
        # Verify loaded
        assert snippet_manager.snippet_exists("test_load")
        snippet = snippet_manager.get_snippet("test_load")
        assert snippet is not None
        assert snippet.parent_name == "TOP.core"
        assert snippet.num_nodes == 2
        assert len(snippet.nodes) == 2
        assert snippet.nodes[0].name == "signal1"
        assert snippet.nodes[1].name == "signal2"


class TestSnippetInstantiation:
    """Test snippet instantiation with scope remapping."""
    
    def test_instantiate_snippet_same_scope(self, waveform_db, snippet_manager):
        """Test instantiating snippet in the same scope."""
        # Find test signals
        test_signals = find_test_signals(waveform_db, "TOP", count=2)
        if len(test_signals) < 2:
            pytest.skip("Not enough test signals found")
        
        # Create snippet
        signal_nodes = []
        for signal_name, handle in test_signals:
            node = SignalNode(name=signal_name, handle=handle)
            signal_nodes.append(node)
        
        parent_scope = snippet_manager.find_common_parent(
            SignalNode(name="group", is_group=True, children=signal_nodes)
        )
        
        snippet = Snippet(
            name="test_instantiate",
            parent_name=parent_scope,
            num_nodes=len(signal_nodes),
            nodes=signal_nodes
        )
        
        # Serialize for snippet (makes names relative, sets handles to -1)
        serialized = serialize_snippet_nodes(snippet.nodes, parent_scope)
        
        # Deserialize back with same scope
        remapped = deserialize_snippet_nodes(serialized, parent_scope, waveform_db)
        
        assert remapped is not None, "Deserialization failed"
        assert len(remapped) == len(signal_nodes)
        
        # Verify handles were resolved
        for node in remapped:
            assert node.handle != -1, f"Handle not resolved for {node.name}"
            # Verify handle is valid in waveform
            var = waveform_db.var_from_handle(node.handle)
            assert var is not None, f"Invalid handle {node.handle}"
    
    def test_instantiate_snippet_different_scope(self, waveform_db):
        """Test instantiating snippet with scope remapping."""
        # This test demonstrates remapping to a different scope
        # We'll create a snippet with relative names and try to instantiate
        # it in a different parent scope
        
        # Create snippet data with relative names - using core_clk which exists in swerv1.vcd
        snippet_data = [
            {
                "name": "core_clk",  # Relative name that exists in the VCD
                "handle": -1,
                "format": None,
                "nickname": None,
                "is_group": False,
                "group_render_mode": None,
                "is_expanded": True,
                "height_scaling": 1.0,
                "is_multi_bit": False
            }
        ]
        
        # The core_clk signal exists at TOP.core_clk in swerv1.vcd
        # Test remapping it to the TOP scope
        remapped = deserialize_snippet_nodes(snippet_data, "TOP", waveform_db)
        
        # Should successfully remap
        assert remapped is not None, "Failed to remap core_clk to TOP scope"
        assert len(remapped) == 1
        assert remapped[0].handle != -1
        assert remapped[0].name == "TOP.core_clk"
        
        # Also test that remapping to a different scope where core_clk doesn't exist fails
        remapped_fail = deserialize_snippet_nodes(snippet_data, "TOP.rvtop", waveform_db)
        assert remapped_fail is None, "Should fail when signal doesn't exist in target scope"
    
    def test_instantiate_snippet_invalid_signals(self, waveform_db):
        """Test that instantiation fails gracefully for non-existent signals."""
        # Create snippet with non-existent signal
        snippet_data = [
            {
                "name": "non_existent_signal_xyz",
                "handle": -1,
                "format": None,
                "nickname": None,
                "is_group": False,
                "group_render_mode": None,
                "is_expanded": True,
                "height_scaling": 1.0,
                "is_multi_bit": False
            }
        ]
        
        # Try to instantiate in TOP scope
        remapped = deserialize_snippet_nodes(snippet_data, "TOP", waveform_db)
        
        # Should return None when signal doesn't exist
        assert remapped is None


class TestSnippetRoundTrip:
    """Test complete round-trip: create, save, load, instantiate."""
    
    def test_full_round_trip(self, waveform_db, snippet_manager, qapp):
        """Test complete workflow from creation to instantiation."""
        # Step 1: Find real signals from VCD
        test_signals = find_test_signals(waveform_db, "TOP", count=3)
        if len(test_signals) < 2:
            pytest.skip("Not enough test signals found")
        
        # Step 2: Create signal nodes with formatting
        signal_nodes = []
        for i, (signal_name, handle) in enumerate(test_signals):
            node = SignalNode(
                name=signal_name,
                handle=handle,
                format=DisplayFormat(
                    data_format=DataFormat.HEX if i == 0 else DataFormat.BIN,
                    render_type=RenderType.BUS
                ),
                nickname=f"sig_{i}",
                is_multi_bit=(i == 0),
                height_scaling=1.5 if i == 0 else 1.0
            )
            signal_nodes.append(node)
        
        # Step 3: Create group and find parent scope
        group = SignalNode(
            name="Test Group",
            is_group=True,
            children=signal_nodes
        )
        parent_scope = snippet_manager.find_common_parent(group)
        
        # Step 4: Create and save snippet
        snippet = Snippet(
            name="round_trip_test",
            parent_name=parent_scope,
            num_nodes=len(signal_nodes),
            nodes=signal_nodes,
            description="Round trip test snippet"
        )
        
        assert snippet_manager.save_snippet(snippet)
        
        # Step 5: Clear and reload snippets
        snippet_manager._snippets.clear()
        snippet_manager.load_snippets()
        
        # Step 6: Retrieve snippet
        loaded_snippet = snippet_manager.get_snippet("round_trip_test")
        assert loaded_snippet is not None
        assert loaded_snippet.name == "round_trip_test"
        assert loaded_snippet.parent_name == parent_scope
        assert len(loaded_snippet.nodes) == len(signal_nodes)
        
        # Step 7: Test instantiation dialog (just creation, not execution)
        dialog = InstantiateSnippetDialog(loaded_snippet, waveform_db)
        assert dialog.snippet == loaded_snippet
        assert dialog.waveform_db == waveform_db
        
        # Step 8: Manually test remapping
        # Serialize nodes (as would happen in save)
        serialized = serialize_snippet_nodes(loaded_snippet.nodes, parent_scope)
        
        # Deserialize with same scope (as would happen in instantiation)
        remapped = deserialize_snippet_nodes(serialized, parent_scope, waveform_db)
        
        assert remapped is not None
        assert len(remapped) == len(signal_nodes)
        
        # Verify all properties preserved
        for original, restored in zip(signal_nodes, remapped):
            # Name should match
            assert restored.name == original.name
            # Handle should be resolved (not -1)
            assert restored.handle != -1
            # Format should be preserved
            assert restored.format.data_format == original.format.data_format
            assert restored.format.render_type == original.format.render_type
            # Other properties preserved
            assert restored.nickname == original.nickname
            assert restored.is_multi_bit == original.is_multi_bit
            assert restored.height_scaling == original.height_scaling
    
    def test_snippet_instantiated_as_group(self, waveform_db, snippet_manager, qapp):
        """Test that snippets are instantiated as a group with custom name."""
        # Find test signals
        test_signals = find_test_signals(waveform_db, "TOP", count=2)
        if len(test_signals) < 2:
            pytest.skip("Not enough test signals found")
        
        # Create signal nodes
        signal_nodes = []
        for signal_name, handle in test_signals:
            node = SignalNode(name=signal_name, handle=handle)
            signal_nodes.append(node)
        
        # Create snippet
        parent_scope = snippet_manager.find_common_parent(
            SignalNode(name="group", is_group=True, children=signal_nodes)
        )
        
        snippet = Snippet(
            name="test_group_snippet",
            parent_name=parent_scope,
            num_nodes=len(signal_nodes),
            nodes=signal_nodes,
            description="Test snippet for group instantiation"
        )
        
        # Save snippet
        assert snippet_manager.save_snippet(snippet)
        
        # Test the dialog with custom group name
        dialog = InstantiateSnippetDialog(snippet, waveform_db)
        
        # Check default group name
        assert dialog.group_name_edit.text() == snippet.name
        
        # Set custom group name
        custom_name = "Custom Group Name"
        dialog.group_name_edit.setText(custom_name)
        dialog._on_group_name_changed(custom_name)
        
        assert dialog.get_group_name() == custom_name
        
        # Serialize and deserialize
        from wavescout.persistence import serialize_snippet_nodes
        serialized = serialize_snippet_nodes(snippet.nodes, parent_scope)
        remapped = deserialize_snippet_nodes(serialized, parent_scope, waveform_db)
        
        assert remapped is not None
        
        # Wrap in group with custom name as would happen in the UI
        group_node = SignalNode(
            name=custom_name,  # Use custom name
            is_group=True,
            children=remapped,
            is_expanded=True
        )
        
        # Set parent references
        for child in remapped:
            child.parent = group_node
        
        # Verify group structure with custom name
        assert group_node.is_group
        assert group_node.name == custom_name
        assert len(group_node.children) == len(signal_nodes)
        assert group_node.is_expanded
        
        # Verify children have parent reference
        for child in group_node.children:
            assert child.parent == group_node
    
    def test_complex_snippet_double_instantiation(self, waveform_db, snippet_manager, qapp):
        """Test saving and instantiating complex snippet with all features twice."""
        # Find test signals
        test_signals = find_test_signals(waveform_db, "TOP", count=6)
        if len(test_signals) < 6:
            pytest.skip("Not enough test signals found")
        
        # Create complex nested structure with various properties
        # First subgroup - expanded, with analog signal
        analog_signal = SignalNode(
            name=test_signals[0][0],
            handle=test_signals[0][1],
            nickname="Analog Wave",
            format=DisplayFormat(
                data_format=DataFormat.HEX,
                render_type=RenderType.ANALOG
            ),
            height_scaling=2.5,
            is_multi_bit=True
        )
        
        digital_signal = SignalNode(
            name=test_signals[1][0],
            handle=test_signals[1][1],
            nickname="Clock",
            format=DisplayFormat(
                data_format=DataFormat.BIN,
                render_type=RenderType.BOOL
            ),
            height_scaling=1.0,
            is_multi_bit=False
        )
        
        subgroup1 = SignalNode(
            name="Analog Signals",
            is_group=True,
            is_expanded=True,  # Expanded
            children=[analog_signal, digital_signal]
        )
        
        # Second subgroup - collapsed, with bus signals
        bus_signal1 = SignalNode(
            name=test_signals[2][0],
            handle=test_signals[2][1],
            nickname="Data Bus",
            format=DisplayFormat(
                data_format=DataFormat.HEX,
                render_type=RenderType.BUS
            ),
            height_scaling=1.5,
            is_multi_bit=True
        )
        
        bus_signal2 = SignalNode(
            name=test_signals[3][0],
            handle=test_signals[3][1],
            nickname="Address Bus",
            format=DisplayFormat(
                data_format=DataFormat.UNSIGNED,
                render_type=RenderType.BUS
            ),
            height_scaling=1.2,
            is_multi_bit=True
        )
        
        subgroup2 = SignalNode(
            name="Bus Signals",
            is_group=True,
            is_expanded=False,  # Collapsed
            children=[bus_signal1, bus_signal2]
        )
        
        # Third subgroup - nested groups
        nested_signal1 = SignalNode(
            name=test_signals[4][0],
            handle=test_signals[4][1],
            nickname="Control",
            format=DisplayFormat(
                data_format=DataFormat.BIN,
                render_type=RenderType.BOOL
            ),
            height_scaling=0.8
        )
        
        nested_signal2 = SignalNode(
            name=test_signals[5][0],
            handle=test_signals[5][1],
            nickname="Status",
            format=DisplayFormat(
                data_format=DataFormat.SIGNED,
                render_type=RenderType.BUS
            ),
            height_scaling=1.0
        )
        
        inner_group = SignalNode(
            name="Control Signals",
            is_group=True,
            is_expanded=True,
            children=[nested_signal1, nested_signal2]
        )
        
        subgroup3 = SignalNode(
            name="Nested Group",
            is_group=True,
            is_expanded=False,
            children=[inner_group]
        )
        
        # Main group containing all subgroups
        main_group = SignalNode(
            name="Complex Test Group",
            is_group=True,
            is_expanded=True,
            children=[subgroup1, subgroup2, subgroup3]
        )
        
        # Set parent references
        for child in main_group.children:
            child.parent = main_group
            for grandchild in child.children:
                grandchild.parent = child
                if grandchild.is_group:
                    for great_grandchild in grandchild.children:
                        great_grandchild.parent = grandchild
        
        # Find common parent scope
        parent_scope = snippet_manager.find_common_parent(main_group)
        
        # Create and save snippet
        snippet = Snippet(
            name="complex_test_snippet",
            parent_name=parent_scope,
            num_nodes=6,  # Total leaf signals
            nodes=[main_group],  # Save the whole tree
            description="Complex snippet with all features for testing"
        )
        
        assert snippet_manager.save_snippet(snippet)
        print(f"Saved complex snippet: {snippet.name}")
        
        # Reload snippets
        snippet_manager._snippets.clear()
        snippet_manager.load_snippets()
        
        loaded_snippet = snippet_manager.get_snippet("complex_test_snippet")
        assert loaded_snippet is not None
        
        # Verify structure is preserved
        assert len(loaded_snippet.nodes) == 1
        loaded_main = loaded_snippet.nodes[0]
        assert loaded_main.is_group
        assert loaded_main.name == "Complex Test Group"
        assert loaded_main.is_expanded == True
        assert len(loaded_main.children) == 3
        
        # Verify first subgroup (analog signals)
        loaded_sub1 = loaded_main.children[0]
        assert loaded_sub1.name == "Analog Signals"
        assert loaded_sub1.is_expanded == True
        assert len(loaded_sub1.children) == 2
        
        # Check analog signal properties
        loaded_analog = loaded_sub1.children[0]
        assert loaded_analog.nickname == "Analog Wave"
        assert loaded_analog.format.render_type == RenderType.ANALOG
        assert loaded_analog.height_scaling == 2.5
        assert loaded_analog.is_multi_bit == True
        
        # Verify second subgroup (bus signals - collapsed)
        loaded_sub2 = loaded_main.children[1]
        assert loaded_sub2.name == "Bus Signals"
        assert loaded_sub2.is_expanded == False  # Should be collapsed
        assert len(loaded_sub2.children) == 2
        
        # Check bus signal properties
        loaded_bus1 = loaded_sub2.children[0]
        assert loaded_bus1.nickname == "Data Bus"
        assert loaded_bus1.format.render_type == RenderType.BUS
        assert loaded_bus1.height_scaling == 1.5
        
        # Verify third subgroup (nested groups)
        loaded_sub3 = loaded_main.children[2]
        assert loaded_sub3.name == "Nested Group"
        assert loaded_sub3.is_expanded == False
        assert len(loaded_sub3.children) == 1
        
        # Check inner nested group
        loaded_inner = loaded_sub3.children[0]
        assert loaded_inner.name == "Control Signals"
        assert loaded_inner.is_expanded == True
        assert len(loaded_inner.children) == 2
        
        # Now test instantiation - FIRST INSTANCE
        from wavescout.persistence import serialize_snippet_nodes
        serialized = serialize_snippet_nodes(loaded_snippet.nodes, parent_scope)
        
        # First instantiation
        remapped1 = deserialize_snippet_nodes(serialized, parent_scope, waveform_db)
        assert remapped1 is not None
        assert len(remapped1) == 1
        
        # Wrap in group with custom name
        group1 = SignalNode(
            name="First Instance",
            is_group=True,
            children=remapped1,
            is_expanded=True
        )
        
        # Set parent references
        for child in remapped1:
            child.parent = group1
        
        # Verify first instance structure
        instance1_main = remapped1[0]
        assert instance1_main.is_group
        assert instance1_main.name == "Complex Test Group"
        assert len(instance1_main.children) == 3
        
        # Verify properties preserved in first instance
        inst1_analog = instance1_main.children[0].children[0]
        assert inst1_analog.nickname == "Analog Wave"
        assert inst1_analog.format.render_type == RenderType.ANALOG
        assert inst1_analog.height_scaling == 2.5
        assert inst1_analog.handle != -1  # Handle should be resolved
        
        # SECOND INSTANCE - instantiate the same snippet again
        remapped2 = deserialize_snippet_nodes(serialized, parent_scope, waveform_db)
        assert remapped2 is not None
        assert len(remapped2) == 1
        
        # Wrap in group with different custom name
        group2 = SignalNode(
            name="Second Instance",
            is_group=True,
            children=remapped2,
            is_expanded=True
        )
        
        # Set parent references
        for child in remapped2:
            child.parent = group2
        
        # Verify second instance structure
        instance2_main = remapped2[0]
        assert instance2_main.is_group
        assert instance2_main.name == "Complex Test Group"
        assert len(instance2_main.children) == 3
        
        # Verify properties preserved in second instance
        inst2_analog = instance2_main.children[0].children[0]
        assert inst2_analog.nickname == "Analog Wave"
        assert inst2_analog.format.render_type == RenderType.ANALOG
        assert inst2_analog.height_scaling == 2.5
        assert inst2_analog.handle != -1  # Handle should be resolved
        
        # Verify both instances are independent (different instance IDs)
        assert group1.instance_id != group2.instance_id
        assert instance1_main.instance_id != instance2_main.instance_id
        assert inst1_analog.instance_id != inst2_analog.instance_id
        
        # But they should have the same handles (pointing to same signals)
        assert inst1_analog.handle == inst2_analog.handle
        
        print("Successfully instantiated complex snippet twice with all properties preserved")
    
    def test_nested_groups_round_trip(self, waveform_db, snippet_manager):
        """Test round-trip with nested groups."""
        # Find test signals
        test_signals = find_test_signals(waveform_db, "TOP", count=4)
        if len(test_signals) < 4:
            pytest.skip("Not enough test signals found")
        
        # Create nested structure
        subgroup1 = SignalNode(
            name="Subgroup 1",
            is_group=True,
            children=[
                SignalNode(name=test_signals[0][0], handle=test_signals[0][1]),
                SignalNode(name=test_signals[1][0], handle=test_signals[1][1])
            ]
        )
        
        subgroup2 = SignalNode(
            name="Subgroup 2",
            is_group=True,
            children=[
                SignalNode(name=test_signals[2][0], handle=test_signals[2][1]),
                SignalNode(name=test_signals[3][0], handle=test_signals[3][1])
            ]
        )
        
        main_group = SignalNode(
            name="Main Group",
            is_group=True,
            children=[subgroup1, subgroup2]
        )
        
        parent_scope = snippet_manager.find_common_parent(main_group)
        
        # Save as snippet
        snippet = Snippet(
            name="nested_test",
            parent_name=parent_scope,
            num_nodes=4,
            nodes=[main_group]  # Save the whole tree
        )
        
        assert snippet_manager.save_snippet(snippet)
        
        # Reload and verify structure
        snippet_manager._snippets.clear()
        snippet_manager.load_snippets()
        
        loaded = snippet_manager.get_snippet("nested_test")
        assert loaded is not None
        assert len(loaded.nodes) == 1
        assert loaded.nodes[0].is_group
        assert len(loaded.nodes[0].children) == 2
        assert all(child.is_group for child in loaded.nodes[0].children)
        assert len(loaded.nodes[0].children[0].children) == 2
        assert len(loaded.nodes[0].children[1].children) == 2


class TestSnippetBugRegressions:
    """Test cases to prevent regressions on recently fixed bugs."""
    
    def test_save_snippet_does_not_modify_session(self, snippet_manager):
        """Test that saving a snippet doesn't modify the original session nodes.
        
        This was a bug where save_snippet modified handles in-place, causing
        signals to disappear from the canvas.
        """
        # Create signal nodes with specific handles (simulating loaded signals)
        signal1 = SignalNode(name="TOP.module.sig1", handle=42)
        signal2 = SignalNode(name="TOP.module.sig2", handle=84)
        signal3 = SignalNode(name="TOP.module.sig3", handle=126)
        
        # Create a group as would be in a session
        group = SignalNode(
            name="Session Group",
            is_group=True,
            children=[signal1, signal2, signal3]
        )
        
        # Store original handles
        original_handles = [signal1.handle, signal2.handle, signal3.handle]
        assert all(h != -1 for h in original_handles), "Test setup: handles should not be -1"
        
        # Create snippet from the group (as SaveSnippetDialog does)
        snippet = Snippet(
            name="test_no_modify",
            parent_name="TOP.module",
            num_nodes=3,
            nodes=group.children,  # Pass the actual children from session
            description="Test that save doesn't modify"
        )
        
        # Save the snippet
        success = snippet_manager.save_snippet(snippet)
        assert success, "Failed to save snippet"
        
        # CRITICAL: Verify original nodes still have their handles
        assert signal1.handle == 42, f"Handle modified! Was 42, now {signal1.handle}"
        assert signal2.handle == 84, f"Handle modified! Was 84, now {signal2.handle}"
        assert signal3.handle == 126, f"Handle modified! Was 126, now {signal3.handle}"
        
        # Verify the saved file has handles set to -1
        snippet_file = snippet_manager._snippets_dir / "test_no_modify.json"
        with open(snippet_file, 'r') as f:
            data = json.load(f)
        
        for node_data in data["nodes"]:
            assert node_data["handle"] == -1, "Saved snippet should have handle=-1"
        
        # Clean up
        snippet_manager.delete_snippet("test_no_modify")
    
    def test_cli_snippet_loading_with_relative_paths(self, waveform_db, snippet_manager, tmp_path):
        """Test CLI snippet loading with relative signal names.
        
        This was a bug where CLI loading failed because it wasn't properly
        concatenating parent_name with relative signal names.
        """
        # Create a snippet file with relative names (as saved by GUI)
        snippet_data = {
            "name": "cli_test",
            "parent_name": "TOP.tb_top.rvtop",
            "num_nodes": 2,
            "description": "Test CLI loading",
            "created_at": "2024-01-01T00:00:00",
            "nodes": [
                {
                    "name": "swerv.dec.active_clk",  # Relative path
                    "handle": -1,
                    "format": {
                        "data_format": "hex",
                        "render_type": "bool"
                    },
                    "is_group": False,
                    "is_expanded": True,
                    "height_scaling": 1.0,
                    "is_multi_bit": False
                },
                {
                    "name": "mem.rst_l",  # Another relative path
                    "handle": -1,
                    "format": {
                        "data_format": "bin",
                        "render_type": "bool"
                    },
                    "is_group": False,
                    "is_expanded": True,
                    "height_scaling": 1.0,
                    "is_multi_bit": False
                }
            ]
        }
        
        # Save snippet file
        snippet_file = snippet_manager._snippets_dir / "cli_test.json"
        with open(snippet_file, 'w') as f:
            json.dump(snippet_data, f)
        
        # Load the snippet
        loaded_snippet = snippet_manager.load_snippet_file("cli_test.json")
        assert loaded_snippet is not None
        assert loaded_snippet.parent_name == "TOP.tb_top.rvtop"
        assert len(loaded_snippet.nodes) == 2
        
        # Test the path building logic (as used by CLI)
        from wavescout.snippet_dialogs import InstantiateSnippetDialog
        
        # Build full paths by concatenating parent with relative names
        full_path_nodes = []
        for node in loaded_snippet.nodes:
            full_node = InstantiateSnippetDialog.build_full_paths(
                node, loaded_snippet.parent_name
            )
            full_path_nodes.append(full_node)
        
        # Verify full paths are built correctly
        assert full_path_nodes[0].name == "TOP.tb_top.rvtop.swerv.dec.active_clk"
        assert full_path_nodes[1].name == "TOP.tb_top.rvtop.mem.rst_l"
        
        # For swerv1.vcd, these specific signals won't exist, but we can verify
        # the path building worked correctly
        print(f"Full path 1: {full_path_nodes[0].name}")
        print(f"Full path 2: {full_path_nodes[1].name}")
    
    def test_snippet_path_concatenation_logic(self):
        """Test the static build_full_paths method for proper concatenation.
        
        This tests the simplified logic that just concatenates parent + "." + relative_name
        without complex remapping.
        """
        from wavescout.snippet_dialogs import InstantiateSnippetDialog
        
        # Test case 1: Simple signal
        signal = SignalNode(name="signal1", handle=-1)
        result = InstantiateSnippetDialog.build_full_paths(signal, "TOP.module")
        assert result.name == "TOP.module.signal1"
        
        # Test case 2: Nested path
        signal = SignalNode(name="sub.module.signal", handle=-1)
        result = InstantiateSnippetDialog.build_full_paths(signal, "TOP.parent")
        assert result.name == "TOP.parent.sub.module.signal"
        
        # Test case 3: Empty parent scope
        signal = SignalNode(name="signal", handle=-1)
        result = InstantiateSnippetDialog.build_full_paths(signal, "")
        assert result.name == "signal"  # Should keep as-is
        
        # Test case 4: Group with children
        child1 = SignalNode(name="sig1", handle=-1)
        child2 = SignalNode(name="sig2", handle=-1)
        group = SignalNode(
            name="MyGroup",
            is_group=True,
            children=[child1, child2]
        )
        
        result = InstantiateSnippetDialog.build_full_paths(group, "TOP.scope")
        
        # Group name should not be modified
        assert result.name == "MyGroup"
        assert result.is_group == True
        
        # Children should have full paths
        assert len(result.children) == 2
        assert result.children[0].name == "TOP.scope.sig1"
        assert result.children[1].name == "TOP.scope.sig2"
        
        # Parent references should be set
        assert result.children[0].parent == result
        assert result.children[1].parent == result
    
    def test_snippet_with_nested_groups_preserves_structure(self, snippet_manager):
        """Test that nested groups in snippets maintain their structure.
        
        This verifies the complex nested group handling works correctly.
        """
        # Create a complex nested structure
        leaf1 = SignalNode(name="signal1", handle=10)
        leaf2 = SignalNode(name="signal2", handle=20)
        leaf3 = SignalNode(name="signal3", handle=30)
        leaf4 = SignalNode(name="signal4", handle=40)
        
        inner_group1 = SignalNode(
            name="Inner1",
            is_group=True,
            is_expanded=False,
            children=[leaf1, leaf2]
        )
        
        inner_group2 = SignalNode(
            name="Inner2", 
            is_group=True,
            is_expanded=True,
            children=[leaf3, leaf4]
        )
        
        outer_group = SignalNode(
            name="Outer",
            is_group=True,
            is_expanded=True,
            children=[inner_group1, inner_group2]
        )
        
        # Create snippet
        snippet = Snippet(
            name="nested_preserve",
            parent_name="TOP",
            num_nodes=4,
            nodes=[outer_group]
        )
        
        # Save (this should not modify the original nodes)
        assert snippet_manager.save_snippet(snippet)
        
        # Verify original structure unchanged
        assert outer_group.children[0].is_expanded == False
        assert outer_group.children[1].is_expanded == True
        assert leaf1.handle == 10  # Handle should not be modified
        
        # Load and verify saved structure
        snippet_manager._snippets.clear()
        snippet_manager.load_snippets()
        loaded = snippet_manager.get_snippet("nested_preserve")
        
        assert loaded is not None
        loaded_outer = loaded.nodes[0]
        assert loaded_outer.name == "Outer"
        assert loaded_outer.is_expanded == True
        assert len(loaded_outer.children) == 2
        
        # Check inner groups
        assert loaded_outer.children[0].name == "Inner1"
        assert loaded_outer.children[0].is_expanded == False
        assert loaded_outer.children[1].name == "Inner2"
        assert loaded_outer.children[1].is_expanded == True
        
        # Check leaf nodes exist
        assert len(loaded_outer.children[0].children) == 2
        assert len(loaded_outer.children[1].children) == 2
    
    def test_instantiate_dialog_validate_and_resolve(self, waveform_db):
        """Test the static validate_and_resolve_nodes method.
        
        This method is used by CLI loading to validate signals exist and resolve handles.
        """
        from wavescout.snippet_dialogs import InstantiateSnippetDialog
        
        # Find a real signal from the waveform
        test_signals = find_test_signals(waveform_db, "TOP", count=1)
        if not test_signals:
            pytest.skip("No test signals found")
        
        real_signal_path, _ = test_signals[0]
        
        # Test case 1: Valid signal
        valid_node = SignalNode(name=real_signal_path, handle=-1)
        
        validated = InstantiateSnippetDialog.validate_and_resolve_nodes(
            [valid_node], waveform_db
        )
        
        assert len(validated) == 1
        assert validated[0].name == real_signal_path
        assert validated[0].handle != -1  # Handle should be resolved
        
        # Test case 2: Invalid signal should raise ValueError
        invalid_node = SignalNode(name="TOP.does.not.exist", handle=-1)
        
        with pytest.raises(ValueError) as exc_info:
            InstantiateSnippetDialog.validate_and_resolve_nodes(
                [invalid_node], waveform_db
            )
        assert "not found in waveform" in str(exc_info.value)
        
        # Test case 3: Group with valid child
        group_node = SignalNode(
            name="TestGroup",
            is_group=True,
            children=[SignalNode(name=real_signal_path, handle=-1)]
        )
        
        validated = InstantiateSnippetDialog.validate_and_resolve_nodes(
            [group_node], waveform_db
        )
        
        assert len(validated) == 1
        assert validated[0].is_group == True
        assert len(validated[0].children) == 1
        assert validated[0].children[0].handle != -1