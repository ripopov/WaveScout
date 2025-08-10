"""Centralized configuration for WaveScout.

This module contains all configuration constants, colors, and magic numbers
used throughout the application to improve maintainability and consistency.
"""

from dataclasses import dataclass
from typing import Optional, List

# Marker labels
MARKER_LABELS: List[str] = ["A", "B", "C", "D", "E", "F", "G", "H", "I"]


@dataclass(frozen=True)
class RenderingConfig:
    """Configuration for signal rendering."""
    SIGNAL_MARGIN_TOP: int = 3
    SIGNAL_MARGIN_BOTTOM: int = 3
    BUS_TRANSITION_MAX_WIDTH: int = 4  # Maximum width for diagonal transitions
    BUS_TRANSITION_SLOPE_FACTOR: float = 0.125  # Controls transition steepening rate
    MIN_BUS_TEXT_WIDTH: int = 30
    DEFAULT_ROW_HEIGHT: int = 20
    DEFAULT_HEADER_HEIGHT: int = 35
    
    # Font settings
    FONT_FAMILY: str = "Consolas"
    FONT_SIZE_SMALL: int = 8
    FONT_SIZE_NORMAL: int = 9
    FONT_SIZE_LARGE: int = 10
    FONT_FAMILY_MONO: str = "Monospace"
    
    # Canvas settings
    MIN_CANVAS_WIDTH: int = 400
    UPDATE_TIMER_DELAY: int = 100  # milliseconds
    MAX_ITERATIONS_SAFETY: int = 10  # multiplier for canvas width
    
    # Cache settings
    TRANSITION_CACHE_MAX_ENTRIES: int = 1000
    
    # Cursor settings
    CURSOR_WIDTH: int = 2
    CURSOR_PADDING: int = 2
    
    # Marker settings
    MARKER_WIDTH: int = 1
    MAX_MARKERS: int = 9
    
    # Debug display settings
    DEBUG_FONT_FAMILY: str = "Consolas"
    DEBUG_FONT_SIZE: int = 10
    DEBUG_BG_ALPHA: int = 200
    DEBUG_TEXT_PADDING: int = 10
    DEBUG_TEXT_MARGIN: int = 10


@dataclass(frozen=True)
class ColorScheme:
    """Color scheme for the application."""
    # Backgrounds
    BACKGROUND: str = "#1e1e1e"
    BACKGROUND_DARK: str = "#1a1a1a"
    BACKGROUND_INVALID: str = "#1a1a1a"  # For invalid time ranges
    ALTERNATE_ROW: str = "#2d2d30"
    HEADER_BACKGROUND: str = "#2d2d30"
    
    # Borders and lines
    BORDER: str = "#3e3e42"
    GRID: str = "#3e3e42"
    RULER_LINE: str = "#808080"
    BOUNDARY_LINE: str = "#606060"
    
    # Text
    TEXT: str = "#cccccc"
    TEXT_MUTED: str = "#808080"
    
    # Selections and highlights
    SELECTION: str = "#094771"
    CURSOR: str = "#ff0000"
    MARKER_DEFAULT_COLOR: str = "#00ff00"
    
    # Debug colors
    DEBUG_TEXT: str = "#ffff00"  # Yellow
    DEBUG_BACKGROUND: tuple[int, int, int, int] = (0, 0, 0, 200)  # RGBA
    
    # Default signal color
    DEFAULT_SIGNAL: str = "#33C3F0"
    
    # Splitter
    SPLITTER_HANDLE: str = "#3e3e42"


@dataclass(frozen=True)
class UIConfig:
    """UI-related configuration."""
    # Splitter settings
    SPLITTER_INITIAL_SIZES: Optional[List[int]] = None  # Will be set in __post_init__
    SPLITTER_HANDLE_WIDTH: int = 2
    
    # Tree view settings
    TREE_ROW_HEIGHT_BASE: int = 20
    TREE_ALTERNATING_ROWS: bool = True
    TREE_UNIFORM_ROW_HEIGHTS: bool = False
    
    # Info bar settings
    INFO_BAR_HEIGHT: int = 25
    
    # Scrolling settings
    SCROLL_SENSITIVITY: float = 0.05
    ZOOM_WHEEL_FACTOR: float = 1.1
    PAN_PERCENTAGE: float = 0.1
    
    # Selection
    SELECTION_MODE_EXTENDED: bool = True
    
    # Drag and drop
    DRAG_DROP_ENABLED: bool = True
    
    def __post_init__(self) -> None:
        if self.SPLITTER_INITIAL_SIZES is None:
            object.__setattr__(self, 'SPLITTER_INITIAL_SIZES', [200, 100, 600])


@dataclass(frozen=True)
class TimeRulerDefaults:
    """Default settings for time ruler."""
    TICK_DENSITY: float = 0.8
    TEXT_SIZE: int = 10
    SHOW_GRID_LINES: bool = True
    GRID_STYLE: str = "solid"
    NICE_NUMBERS: Optional[List[float]] = None  # Will be set in __post_init__
    
    # Ruler dimensions
    RULER_HEIGHT: int = 35
    TICK_HEIGHT: int = 5
    TICK_Y_START: int = 29
    TEXT_Y_OFFSET: int = 5
    
    def __post_init__(self) -> None:
        if self.NICE_NUMBERS is None:
            object.__setattr__(self, 'NICE_NUMBERS', [1, 2, 2.5, 5])


# Global instances for easy access
RENDERING = RenderingConfig()
COLORS = ColorScheme()
UI = UIConfig()
TIME_RULER = TimeRulerDefaults()