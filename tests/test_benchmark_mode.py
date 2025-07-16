"""Test the canvas benchmark mode functionality."""

import pytest
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter
from wavescout import WaveScoutWidget, create_sample_session


@pytest.fixture
def wave_widget(qtbot):
    """Create WaveScoutWidget with test data."""
    # Create widget
    widget = WaveScoutWidget()
    qtbot.addWidget(widget)
    
    # Create and set session
    test_file = Path(__file__).parent.parent / "test_inputs" / "swerv1.vcd"
    session = create_sample_session(str(test_file))
    widget.setSession(session)
    
    # Show widget
    widget.show()
    qtbot.waitExposed(widget)
    
    yield widget


def test_benchmark_mode_toggle(wave_widget, qtbot):
    """Test that benchmark mode can be toggled on and off."""
    session = wave_widget.session
    canvas = wave_widget._canvas
    
    # Initially benchmark mode should be off
    assert session.canvas_benchmark_mode == False
    
    # Enable benchmark mode
    session.canvas_benchmark_mode = True
    canvas.update()
    qtbot.wait(100)
    
    # Verify it's enabled
    assert session.canvas_benchmark_mode == True
    
    # Disable benchmark mode
    session.canvas_benchmark_mode = False
    canvas.update()
    qtbot.wait(100)
    
    # Verify it's disabled
    assert session.canvas_benchmark_mode == False


def test_benchmark_mode_rendering(wave_widget, qtbot):
    """Test that benchmark mode renders a rainbow pattern."""
    session = wave_widget.session
    canvas = wave_widget._canvas
    
    # Enable benchmark mode
    session.canvas_benchmark_mode = True
    canvas.update()
    qtbot.wait(100)
    
    # Capture the canvas as an image
    from PySide6.QtCore import QPoint
    image = QImage(canvas.size(), QImage.Format_RGB32)
    painter = QPainter(image)
    try:
        # Render requires a target offset
        canvas.render(painter, QPoint(0, 0))
    finally:
        painter.end()
    
    # Sample some pixels to verify they have different colors
    width = image.width()
    height = image.height()
    
    if width > 10 and height > 10:
        # Sample a few pixels
        colors = []
        sample_points = [
            (5, 5),
            (width // 2, height // 2),
            (width - 5, height - 5),
            (10, height // 2),
            (width // 2, 10)
        ]
        
        for x, y in sample_points:
            color = image.pixelColor(x, y)
            colors.append((color.red(), color.green(), color.blue()))
        
        # Check that we have different colors (not all black or all the same)
        unique_colors = set(colors)
        assert len(unique_colors) > 1, "Benchmark mode should produce different colors"
        
        # Check that not all pixels are black (background)
        black_count = sum(1 for r, g, b in colors if r == 0 and g == 0 and b == 0)
        assert black_count < len(colors), "Not all sampled pixels should be black"
        
        print(f"\nSampled colors in benchmark mode: {colors}")


def test_benchmark_mode_performance_message(wave_widget, qtbot):
    """Test that benchmark mode shows the performance message."""
    session = wave_widget.session
    canvas = wave_widget._canvas
    
    # Enable benchmark mode
    session.canvas_benchmark_mode = True
    canvas.update()
    qtbot.wait(100)
    
    # The canvas should display "BENCHMARK MODE" text
    # We can't easily test for the text, but we can verify the mode is active
    # and the canvas updated without errors
    assert session.canvas_benchmark_mode == True
    
    # Canvas should still respond to size changes in benchmark mode
    old_width = canvas.width()
    canvas.resize(old_width + 100, canvas.height())
    qtbot.wait(100)
    
    assert canvas.width() == old_width + 100