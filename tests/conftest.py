"""Common test fixtures and utilities for WaveScout tests."""

import pytest
from pathlib import Path
from wavescout import create_sample_session, WaveScoutWidget
from wavescout.waveform_loader import create_signal_node_from_var
from wavescout.data_model import SignalNode
from .test_utils import get_test_input_path, TestFiles


@pytest.fixture
def vcd_file():
    """Path to test VCD file."""
    return get_test_input_path(TestFiles.SWERV1_VCD)


@pytest.fixture
def vcd_session(vcd_file):
    """Create a session with VCD file loaded."""
    return create_sample_session(str(vcd_file))


def add_signals_from_vcd(session, count=10, include_groups=True):
    """Helper to add signals from the VCD file to the session."""
    if not session.waveform_db:
        return
    
    db = session.waveform_db
    hierarchy = db.hierarchy
    num_vars = db.num_vars()
    
    # Add individual signals
    signals_added = 0
    for i in range(min(num_vars, count)):
        var = db.get_var(i)
        if var:
            node = create_signal_node_from_var(var, hierarchy, i)
            session.root_nodes.append(node)
            signals_added += 1
    
    # Add a group with some children if requested
    if include_groups and num_vars > count:
        group = SignalNode(name="Test Group", is_group=True, is_expanded=True)
        
        # Add 3 children to the group
        for i in range(count, min(count + 3, num_vars)):
            var = db.get_var(i)
            if var:
                child = create_signal_node_from_var(var, hierarchy, i)
                child.parent = group
                group.children.append(child)
        
        if group.children:
            session.root_nodes.append(group)


@pytest.fixture
def widget_with_signals(qtbot, vcd_session):
    """Create widget with VCD session and signals loaded."""
    widget = WaveScoutWidget()
    add_signals_from_vcd(vcd_session, count=10, include_groups=False)
    widget.setSession(vcd_session)
    
    # Show widget for testing
    widget.resize(800, 600)
    widget.show()
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    
    return widget


@pytest.fixture
def widget_with_groups(qtbot, vcd_session):
    """Create widget with VCD session including groups."""
    widget = WaveScoutWidget()
    add_signals_from_vcd(vcd_session, count=5, include_groups=True)
    widget.setSession(vcd_session)
    
    # Show widget for testing
    widget.resize(800, 600)
    widget.show()
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    
    return widget