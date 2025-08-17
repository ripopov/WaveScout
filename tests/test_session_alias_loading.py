"""Test session loading with signal aliases across different backends."""

import pytest
import tempfile
import yaml
from pathlib import Path
from typing import List, Dict, Any
from wavescout.persistence import load_session, save_session
from wavescout.data_model import WaveformSession, SignalNode, DisplayFormat
from wavescout.waveform_db import WaveformDB
from .test_utils import get_test_input_path, TestFiles


class TestSessionAliasLoading:
    """Test that session loading correctly handles signal aliases across backends."""
    
    @pytest.fixture
    def test_waveform_path(self) -> Path:
        """Path to test waveform file."""
        # Note: Using FST file which may not exist in TestFiles enum
        # This test requires apb_sim.fst, not apb_sim.vcd
        try:
            return get_test_input_path("apb_sim.fst")
        except FileNotFoundError:
            # Fallback to direct path if not in TestFiles
            return Path(__file__).parent.parent / "test_inputs" / "apb_sim.fst"
    
    @pytest.fixture
    def session_with_aliases(self, test_waveform_path: Path) -> Dict[str, Any]:
        """Create a session dict with aliased signals (same signal referenced multiple times)."""
        return {
            'db_uri': str(test_waveform_path),
            'root_nodes': [
                {
                    'name': 'Group1',
                    'handle': None,
                    'format': {
                        'render_type': 'bool',
                        'data_format': 'unsigned',
                        'color': '#56B6C2',
                        'analog_scaling_mode': 'scale_to_all'
                    },
                    'nickname': '',
                    'is_group': True,
                    'group_render_mode': 'separate_rows',
                    'is_expanded': True,
                    'height_scaling': 1,
                    'is_multi_bit': False,
                    'instance_id': 100,
                    'children': [
                        # These signals will be loaded first
                        {
                            'name': 'apb_testbench.pready',
                            'handle': 0,
                            'format': {'render_type': 'bool', 'data_format': 'unsigned', 'color': '#56B6C2', 'analog_scaling_mode': 'scale_to_all'},
                            'nickname': '',
                            'is_group': False,
                            'group_render_mode': None,
                            'is_expanded': True,
                            'height_scaling': 1,
                            'is_multi_bit': False,
                            'instance_id': 101
                        },
                        {
                            'name': 'apb_testbench.pclk',
                            'handle': 3,
                            'format': {'render_type': 'bool', 'data_format': 'unsigned', 'color': '#56B6C2', 'analog_scaling_mode': 'scale_to_all'},
                            'nickname': '',
                            'is_group': False,
                            'group_render_mode': None,
                            'is_expanded': True,
                            'height_scaling': 1,
                            'is_multi_bit': False,
                            'instance_id': 102
                        }
                    ]
                },
                {
                    'name': 'Group2_Aliases',
                    'handle': None,
                    'format': {
                        'render_type': 'bool',
                        'data_format': 'unsigned',
                        'color': '#56B6C2',
                        'analog_scaling_mode': 'scale_to_all'
                    },
                    'nickname': '',
                    'is_group': True,
                    'group_render_mode': 'separate_rows',
                    'is_expanded': True,
                    'height_scaling': 1,
                    'is_multi_bit': False,
                    'instance_id': 200,
                    'children': [
                        # These are aliases - same handles as above but different names
                        {
                            'name': 'apb_testbench.dut.pready',
                            'handle': 0,  # Same handle as apb_testbench.pready (alias)
                            'format': {'render_type': 'bool', 'data_format': 'unsigned', 'color': '#56B6C2', 'analog_scaling_mode': 'scale_to_all'},
                            'nickname': '',
                            'is_group': False,
                            'group_render_mode': None,
                            'is_expanded': True,
                            'height_scaling': 1,
                            'is_multi_bit': False,
                            'instance_id': 201
                        },
                        {
                            'name': 'apb_testbench.dut.pclk',
                            'handle': 3,  # Same handle as apb_testbench.pclk (alias)
                            'format': {'render_type': 'bool', 'data_format': 'unsigned', 'color': '#56B6C2', 'analog_scaling_mode': 'scale_to_all'},
                            'nickname': '',
                            'is_group': False,
                            'group_render_mode': None,
                            'is_expanded': True,
                            'height_scaling': 1,
                            'is_multi_bit': False,
                            'instance_id': 202
                        }
                    ]
                }
            ],
            'viewport': {
                'left': 0.0,
                'right': 1.0,
                'total_duration': 10350000,
                'config': {
                    'edge_space': 0.2,
                    'minimum_width_time': 10,
                    'scroll_sensitivity': 0.05,
                    'zoom_wheel_factor': 1.1
                }
            },
            'markers': [],
            'cursor_time': 0,
            'analysis_mode': {
                'mode': 'none',
                'range_start': None,
                'range_end': None
            },
            'timescale': {
                'factor': 1,
                'unit': 'ps'
            }
        }
    
    def test_load_session_with_aliases_pywellen(self, session_with_aliases: Dict[str, Any], test_waveform_path: Path):
        """Test loading a session with aliased signals using pywellen backend."""
        if not test_waveform_path.exists():
            pytest.skip(f"Test file {test_waveform_path} not found")
        
        # Save the session to a temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(session_with_aliases, f)
            session_file = Path(f.name)
        
        try:
            # Load session with pywellen backend
            session = load_session(session_file, backend_preference="pywellen")
            
            assert session is not None
            assert session.waveform_db is not None
            
            # Check that signals are loaded correctly
            db = session.waveform_db
            
            # Test pready (handle 0) - should be a 1-bit signal with value 1 at t=0
            value_pready = db.sample(0, 0)
            assert value_pready == "1", f"pready should be 1 at t=0, got {value_pready}"
            
            # Test pclk (handle 3) - should be a clock with many transitions
            transitions_pclk = db.transitions(3, 0, 1000000)
            assert len(transitions_pclk) > 10, f"pclk should have many transitions, got {len(transitions_pclk)}"
            
            # Verify the first transition is correct
            assert transitions_pclk[0] == (0, '0'), f"First pclk transition should be (0, '0'), got {transitions_pclk[0]}"
            
            # Test that aliases reference the same data
            # Both Group1 and Group2_Aliases should have the same values for their respective signals
            group1_pready = None
            group2_pready = None
            
            for group in session.root_nodes:
                if group.name == "Group1":
                    for child in group.children:
                        if "pready" in child.name and child.handle is not None:
                            group1_pready = db.sample(child.handle, 0)
                elif group.name == "Group2_Aliases":
                    for child in group.children:
                        if "pready" in child.name and child.handle is not None:
                            group2_pready = db.sample(child.handle, 0)
            
            assert group1_pready == group2_pready == "1", \
                f"Aliased pready signals should have same value: group1={group1_pready}, group2={group2_pready}"
            
        finally:
            # Clean up temp file
            session_file.unlink(missing_ok=True)
    
    def test_load_session_with_aliases_pylibfst(self, session_with_aliases: Dict[str, Any], test_waveform_path: Path):
        """Test loading a session with aliased signals using pylibfst backend."""
        if not test_waveform_path.exists():
            pytest.skip(f"Test file {test_waveform_path} not found")
        
        # Save the session to a temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(session_with_aliases, f)
            session_file = Path(f.name)
        
        try:
            # Load session with pylibfst backend
            session = load_session(session_file, backend_preference="pylibfst")
            
            assert session is not None
            assert session.waveform_db is not None
            
            # Check that signals are loaded correctly
            db = session.waveform_db
            
            # Test pready (handle 0)
            value_pready = db.sample(0, 0)
            assert value_pready == "1", f"pready should be 1 at t=0, got {value_pready}"
            
            # Test pclk (handle 3)
            transitions_pclk = db.transitions(3, 0, 1000000)
            assert len(transitions_pclk) > 10, f"pclk should have many transitions, got {len(transitions_pclk)}"
            
            # Test that aliases work correctly
            group1_pclk_value = None
            group2_pclk_value = None
            
            for group in session.root_nodes:
                if group.name == "Group1":
                    for child in group.children:
                        if "pclk" in child.name and child.handle is not None:
                            group1_pclk_value = db.sample(child.handle, 100000)  # Sample at 100ns
                elif group.name == "Group2_Aliases":
                    for child in group.children:
                        if "pclk" in child.name and child.handle is not None:
                            group2_pclk_value = db.sample(child.handle, 100000)  # Sample at 100ns
            
            assert group1_pclk_value == group2_pclk_value, \
                f"Aliased pclk signals should have same value at t=100000: group1={group1_pclk_value}, group2={group2_pclk_value}"
            
        finally:
            # Clean up temp file
            session_file.unlink(missing_ok=True)
    
    def test_cross_backend_session_loading(self, session_with_aliases: Dict[str, Any], test_waveform_path: Path):
        """Test that a session saved with one backend can be loaded correctly with another."""
        if not test_waveform_path.exists():
            pytest.skip(f"Test file {test_waveform_path} not found")
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(session_with_aliases, f)
            session_file = Path(f.name)
        
        try:
            # Load with both backends and compare results
            session_pywellen = load_session(session_file, backend_preference="pywellen")
            session_pylibfst = load_session(session_file, backend_preference="pylibfst")
            
            db_pywellen = session_pywellen.waveform_db
            db_pylibfst = session_pylibfst.waveform_db
            
            # Compare values for handle 0 (pready)
            for t in [0, 100, 1000, 10000]:
                val_pywellen = db_pywellen.sample(0, t)
                val_pylibfst = db_pylibfst.sample(0, t)
                assert val_pywellen == val_pylibfst, \
                    f"Values differ at t={t}: pywellen={val_pywellen}, pylibfst={val_pylibfst}"
            
            # Compare transition counts for handle 3 (pclk)
            trans_pywellen = db_pywellen.transitions(3, 0, 1000000)
            trans_pylibfst = db_pylibfst.transitions(3, 0, 1000000)
            assert len(trans_pywellen) == len(trans_pylibfst), \
                f"Transition counts differ: pywellen={len(trans_pywellen)}, pylibfst={len(trans_pylibfst)}"
            
            # Verify signal names are handled correctly (trailing spaces)
            for group in session_pywellen.root_nodes:
                for child in group.children:
                    if child.handle is not None:
                        # Names should not have trailing spaces in pywellen
                        assert not child.name.endswith(' '), \
                            f"pywellen should strip trailing spaces: '{child.name}'"
            
        finally:
            session_file.unlink(missing_ok=True)
    
    def test_duplicate_handle_preloading(self, test_waveform_path: Path):
        """Test that preload_signals correctly handles duplicate handles."""
        if not test_waveform_path.exists():
            pytest.skip(f"Test file {test_waveform_path} not found")
        
        # Create a WaveformDB with pywellen
        db = WaveformDB(backend_preference="pywellen")
        db.open(str(test_waveform_path))
        
        # Create a list with duplicate handles (simulating what happens with aliases)
        handles_with_duplicates = [0, 1, 2, 3, 0, 3, 0, 4, 3, 5]
        
        # Preload signals - this should handle duplicates correctly
        db.preload_signals(handles_with_duplicates)
        
        # Verify that signals are cached and have correct values
        assert db.is_signal_cached(0), "Handle 0 should be cached"
        assert db.is_signal_cached(3), "Handle 3 should be cached"
        
        # Check that values are correct (not corrupted by duplicate loading)
        value_0 = db.sample(0, 0)
        assert value_0 == "1", f"Handle 0 (pready) should have value 1, got {value_0}"
        
        # Check clock transitions
        transitions_3 = db.transitions(3, 0, 1000000)
        assert len(transitions_3) > 10, \
            f"Handle 3 (pclk) should have many transitions, got {len(transitions_3)}"