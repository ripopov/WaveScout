"""
Centralized application settings management using QSettings.
"""

from typing import Optional, cast, Any
from PySide6.QtCore import QObject, QSettings, Signal


class SettingsManager(QObject):
    """
    Singleton manager for application-level settings.
    
    Provides type-safe access to application preferences stored in QSettings.
    """
    
    # Signal emitted when hierarchy levels setting changes
    hierarchy_levels_changed = Signal(int)
    
    _instance: Optional['SettingsManager'] = None
    
    def __new__(cls) -> 'SettingsManager':
        """Ensure singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self) -> None:
        """Initialize the settings manager."""
        if not hasattr(self, '_initialized'):
            super().__init__()
            self._settings = QSettings("WaveScout", "WaveScout")
            self._initialized = True
            
            # Cache for frequently accessed settings
            self._hierarchy_levels_cache: Optional[int] = None
    
    def get_hierarchy_levels(self) -> int:
        """
        Get the number of hierarchical name levels to display.
        
        Returns:
            Number of levels (0 = show full hierarchy, N = show last N levels)
        """
        if self._hierarchy_levels_cache is None:
            # Default to 0 (show full hierarchy)
            value: Any = self._settings.value("SignalDisplay/HierarchyLevels", 0, type=int)
            # Ensure we have an int (QSettings.value can return None even with type=int)
            self._hierarchy_levels_cache = int(value) if value is not None else 0
        return self._hierarchy_levels_cache
    
    def set_hierarchy_levels(self, levels: int) -> None:
        """
        Set the number of hierarchical name levels to display.
        
        Args:
            levels: Number of levels (0 = show full hierarchy, N = show last N levels)
        """
        # Validate input
        if levels < 0:
            levels = 0
        elif levels > 999:
            levels = 999
            
        # Only update if changed
        if self._hierarchy_levels_cache != levels:
            self._hierarchy_levels_cache = levels
            self._settings.setValue("SignalDisplay/HierarchyLevels", levels)
            self._settings.sync()  # Ensure immediate persistence
            
            # Notify listeners
            self.hierarchy_levels_changed.emit(levels)
    
    def get_settings(self) -> QSettings:
        """
        Get the underlying QSettings object for direct access if needed.
        
        Returns:
            The QSettings instance
        """
        return self._settings