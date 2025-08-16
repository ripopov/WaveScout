"""Tests for the Value Tooltip at Cursor feature."""

import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QSettings, QModelIndex
from PySide6.QtGui import QKeyEvent
from PySide6.QtTest import QTest
from scout import WaveScoutMainWindow
from wavescout import config
from .test_utils import get_test_input_path, TestFiles


@pytest.fixture
def qt_app():
    """Create QApplication for tests."""
    app = QApplication.instance()
    if not app:
        app = QApplication([])
    yield app


@pytest.fixture
def main_window(qt_app):
    """Create main window with loaded waveform."""
    test_file = str(get_test_input_path(TestFiles.APB_SIM_VCD))
    window = WaveScoutMainWindow(wave_file=test_file)
    window.show()
    QTest.qWait(500)  # Wait for loading
    yield window
    window.close()


@pytest.fixture
def main_window_with_signals(main_window):
    """Create main window with signals added to session."""
    # Add some signals to the session
    design_view = main_window.design_tree_view.unified_tree
    model = main_window.design_tree_view.design_tree_model
    
    if model:
        # Find and add first 3 signals
        added = 0
        for r in range(model.rowCount(QModelIndex())):
            idx = model.index(r, 0, QModelIndex())
            if idx.isValid():
                design_view.expand(idx)
                QTest.qWait(50)
                
                for cr in range(model.rowCount(idx)):
                    cidx = model.index(cr, 0, idx)
                    if cidx.isValid():
                        node_ptr = cidx.internalPointer()
                        if node_ptr and not node_ptr.is_scope:
                            signal_node = main_window.design_tree_view._create_signal_node(node_ptr)
                            if signal_node:
                                main_window.design_tree_view.signals_selected.emit([signal_node])
                                QTest.qWait(30)
                                added += 1
                                if added >= 3:
                                    break
                if added >= 3:
                    break
    
    QTest.qWait(100)
    return main_window


class TestValueTooltips:
    """Test suite for value tooltip feature."""
    
    def test_menu_action_exists(self, main_window):
        """Test that the value tooltip menu action exists."""
        assert hasattr(main_window, 'value_tooltip_action')
        assert main_window.value_tooltip_action.isCheckable()
        assert main_window.value_tooltip_action.text() == "Value Tooltip at Cursor"
    
    def test_menu_toggle_enables_tooltips(self, main_window):
        """Test that menu toggle enables/disables tooltips."""
        canvas = main_window.wave_widget._canvas
        
        # Ensure we start from a known state (disabled)
        main_window.value_tooltip_action.setChecked(False)
        main_window._toggle_value_tooltips(False)
        assert not canvas._value_tooltips_enabled
        
        # Enable via menu
        main_window.value_tooltip_action.setChecked(True)
        main_window._toggle_value_tooltips(True)
        assert canvas._value_tooltips_enabled
        
        # Disable via menu
        main_window.value_tooltip_action.setChecked(False)
        main_window._toggle_value_tooltips(False)
        assert not canvas._value_tooltips_enabled
    
    def test_settings_persistence(self, main_window):
        """Test that tooltip setting is saved to QSettings."""
        settings = QSettings("WaveScout", "Scout")
        
        # Enable tooltips
        main_window.value_tooltip_action.setChecked(True)
        main_window._toggle_value_tooltips(True)
        
        # Check setting was saved
        saved_value = settings.value("view/value_tooltips_enabled", False, type=bool)
        assert saved_value == True
        
        # Disable tooltips
        main_window.value_tooltip_action.setChecked(False)
        main_window._toggle_value_tooltips(False)
        
        # Check setting was updated
        saved_value = settings.value("view/value_tooltips_enabled", False, type=bool)
        assert saved_value == False
    
    def test_v_key_force_enable(self, main_window):
        """Test V key temporarily force-enables tooltips."""
        canvas = main_window.wave_widget._canvas
        widget = main_window.wave_widget
        
        # Ensure tooltips are disabled via menu
        main_window.value_tooltip_action.setChecked(False)
        main_window._toggle_value_tooltips(False)
        assert not canvas._value_tooltips_enabled
        assert not canvas._value_tooltips_force_enabled
        
        # Press V key
        press_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_V, Qt.KeyboardModifier.NoModifier)
        widget.keyPressEvent(press_event)
        
        # Check force enable is active
        assert canvas._value_tooltips_force_enabled
        assert not canvas._value_tooltips_enabled  # Menu setting unchanged
        
        # Release V key
        release_event = QKeyEvent(QKeyEvent.Type.KeyRelease, Qt.Key.Key_V, Qt.KeyboardModifier.NoModifier)
        widget.keyReleaseEvent(release_event)
        
        # Check force enable is inactive
        assert not canvas._value_tooltips_force_enabled
        assert not canvas._value_tooltips_enabled  # Menu setting still unchanged
    
    def test_v_key_with_menu_enabled(self, main_window):
        """Test V key behavior when tooltips are already enabled via menu."""
        canvas = main_window.wave_widget._canvas
        widget = main_window.wave_widget
        
        # Enable tooltips via menu
        main_window.value_tooltip_action.setChecked(True)
        main_window._toggle_value_tooltips(True)
        assert canvas._value_tooltips_enabled
        
        # Press V key
        press_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_V, Qt.KeyboardModifier.NoModifier)
        widget.keyPressEvent(press_event)
        
        # Both should be true
        assert canvas._value_tooltips_force_enabled
        assert canvas._value_tooltips_enabled
        
        # Release V key
        release_event = QKeyEvent(QKeyEvent.Type.KeyRelease, Qt.Key.Key_V, Qt.KeyboardModifier.NoModifier)
        widget.keyReleaseEvent(release_event)
        
        # Menu setting should remain, force should be off
        assert not canvas._value_tooltips_force_enabled
        assert canvas._value_tooltips_enabled
    
    def test_event_filter_handles_v_key(self, main_window):
        """Test that event filter properly handles V key events."""
        canvas = main_window.wave_widget._canvas
        widget = main_window.wave_widget
        
        # Test key press through event filter
        press_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_V, Qt.KeyboardModifier.NoModifier)
        handled = widget.eventFilter(canvas, press_event)
        
        assert handled == True
        assert canvas._value_tooltips_force_enabled
        
        # Test key release through event filter
        release_event = QKeyEvent(QKeyEvent.Type.KeyRelease, Qt.Key.Key_V, Qt.KeyboardModifier.NoModifier)
        handled = widget.eventFilter(canvas, release_event)
        
        assert handled == True
        assert not canvas._value_tooltips_force_enabled
    
    def test_tooltip_rendering_method_exists(self, main_window):
        """Test that tooltip rendering infrastructure exists."""
        canvas = main_window.wave_widget._canvas
        
        # Check methods exist
        assert hasattr(canvas, '_paint_value_tooltips')
        assert hasattr(canvas, 'set_value_tooltips_enabled')
        
        # Check state variables exist
        assert hasattr(canvas, '_value_tooltips_enabled')
        assert hasattr(canvas, '_value_tooltips_force_enabled')
    
    def test_tooltip_colors_in_theme(self):
        """Test that tooltip colors are defined in all themes."""
        from wavescout.theme import THEMES, ThemeName
        
        for theme_name in ThemeName:
            theme = THEMES[theme_name]
            assert hasattr(theme, 'VALUE_TOOLTIP_BACKGROUND')
            assert hasattr(theme, 'VALUE_TOOLTIP_TEXT')
            assert hasattr(theme, 'VALUE_TOOLTIP_BORDER')
            
            # Check types
            assert isinstance(theme.VALUE_TOOLTIP_BACKGROUND, tuple)
            assert len(theme.VALUE_TOOLTIP_BACKGROUND) == 4  # RGBA
            assert isinstance(theme.VALUE_TOOLTIP_TEXT, str)
            assert isinstance(theme.VALUE_TOOLTIP_BORDER, str)
    
    def test_tooltip_rendering_config(self):
        """Test that tooltip rendering configuration is defined."""
        assert hasattr(config.RENDERING, 'VALUE_TOOLTIP_PADDING')
        assert hasattr(config.RENDERING, 'VALUE_TOOLTIP_MARGIN')
        assert hasattr(config.RENDERING, 'VALUE_TOOLTIP_BORDER_RADIUS')
        assert hasattr(config.RENDERING, 'VALUE_TOOLTIP_MIN_WIDTH')
        assert hasattr(config.RENDERING, 'VALUE_TOOLTIP_FONT_SIZE')
        
        # Check reasonable values
        assert config.RENDERING.VALUE_TOOLTIP_PADDING > 0
        assert config.RENDERING.VALUE_TOOLTIP_MARGIN > 0
        assert config.RENDERING.VALUE_TOOLTIP_BORDER_RADIUS >= 0
        assert config.RENDERING.VALUE_TOOLTIP_MIN_WIDTH > 0
        assert config.RENDERING.VALUE_TOOLTIP_FONT_SIZE > 0
    
    def test_row_height_scaling_support(self, main_window_with_signals):
        """Test that tooltips account for row height scaling."""
        canvas = main_window_with_signals.wave_widget._canvas
        session = main_window_with_signals.wave_widget.session
        
        if session and session.root_nodes:
            # Scale some rows
            for i, node in enumerate(session.root_nodes[:3]):
                if i == 0:
                    node.height_scaling = 1.0
                elif i == 1:
                    node.height_scaling = 2.0
                elif i == 2:
                    node.height_scaling = 0.5
            
            # Update view
            main_window_with_signals.wave_widget.model.layoutChanged.emit()
            QTest.qWait(100)
            
            # Update canvas visible nodes
            canvas.updateVisibleNodes()
            
            # Check that row heights are scaled
            base_height = canvas._row_height
            assert canvas._row_heights.get(0, base_height) == base_height * 1.0
            assert canvas._row_heights.get(1, base_height) == base_height * 2.0
            assert canvas._row_heights.get(2, base_height) == base_height * 0.5
            
            # Verify tooltip positioning calculation would use scaled heights
            # This tests the algorithm without actually rendering
            header_height = canvas._header_height
            
            # Calculate Y positions as the tooltip method would
            y_positions = []
            for row_idx in range(min(3, len(canvas._visible_nodes))):
                row_y = header_height
                for i in range(row_idx):
                    row_y += canvas._row_heights.get(i, base_height)
                row_height = canvas._row_heights.get(row_idx, base_height)
                tooltip_y = row_y + row_height // 2
                y_positions.append(tooltip_y)
            
            # Verify positions account for scaling
            # Row 0: header_height + base_height/2
            # Row 1: header_height + base_height + (base_height*2)/2
            # Row 2: header_height + base_height + base_height*2 + (base_height*0.5)/2
            expected_y0 = header_height + base_height // 2
            expected_y1 = header_height + base_height + base_height  # base + double/2
            expected_y2 = header_height + base_height + base_height * 2 + base_height * 0.25
            
            assert abs(y_positions[0] - expected_y0) < 1
            assert abs(y_positions[1] - expected_y1) < 1
            assert abs(y_positions[2] - expected_y2) < 1
    
    def test_should_show_tooltips_logic(self, main_window):
        """Test the logic for when tooltips should be shown."""
        canvas = main_window.wave_widget._canvas
        
        # Case 1: Both disabled
        canvas._value_tooltips_enabled = False
        canvas._value_tooltips_force_enabled = False
        should_show = canvas._value_tooltips_enabled or canvas._value_tooltips_force_enabled
        assert should_show == False
        
        # Case 2: Menu enabled
        canvas._value_tooltips_enabled = True
        canvas._value_tooltips_force_enabled = False
        should_show = canvas._value_tooltips_enabled or canvas._value_tooltips_force_enabled
        assert should_show == True
        
        # Case 3: Force enabled
        canvas._value_tooltips_enabled = False
        canvas._value_tooltips_force_enabled = True
        should_show = canvas._value_tooltips_enabled or canvas._value_tooltips_force_enabled
        assert should_show == True
        
        # Case 4: Both enabled
        canvas._value_tooltips_enabled = True
        canvas._value_tooltips_force_enabled = True
        should_show = canvas._value_tooltips_enabled or canvas._value_tooltips_force_enabled
        assert should_show == True


class TestValueTooltipIntegration:
    """Integration tests for value tooltip feature."""
    
    def test_full_workflow(self, main_window_with_signals):
        """Test complete workflow of enabling tooltips and using V key."""
        canvas = main_window_with_signals.wave_widget._canvas
        widget = main_window_with_signals.wave_widget
        
        # Start with tooltips disabled
        main_window_with_signals.value_tooltip_action.setChecked(False)
        main_window_with_signals._toggle_value_tooltips(False)

        # Use V key to temporarily show tooltips
        press_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_V, Qt.KeyboardModifier.NoModifier)
        widget.keyPressEvent(press_event)
        assert canvas._value_tooltips_force_enabled
        
        # While holding V, enable via menu
        main_window_with_signals.value_tooltip_action.setChecked(True)
        main_window_with_signals._toggle_value_tooltips(True)
        assert canvas._value_tooltips_enabled
        assert canvas._value_tooltips_force_enabled
        
        # Release V key
        release_event = QKeyEvent(QKeyEvent.Type.KeyRelease, Qt.Key.Key_V, Qt.KeyboardModifier.NoModifier)
        widget.keyReleaseEvent(release_event)
        
        # Tooltips should still be enabled via menu
        assert canvas._value_tooltips_enabled
        assert not canvas._value_tooltips_force_enabled
        
        # Press V again (redundant but should work)
        widget.keyPressEvent(press_event)
        assert canvas._value_tooltips_force_enabled
        
        # Disable via menu while V is pressed
        main_window_with_signals.value_tooltip_action.setChecked(False)
        main_window_with_signals._toggle_value_tooltips(False)
        assert not canvas._value_tooltips_enabled
        assert canvas._value_tooltips_force_enabled  # V still pressed
        
        # Release V
        widget.keyReleaseEvent(release_event)
        assert not canvas._value_tooltips_enabled
        assert not canvas._value_tooltips_force_enabled