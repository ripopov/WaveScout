"""Utility functions for creating copyable message boxes."""

from PySide6.QtWidgets import QMessageBox
from PySide6.QtCore import Qt
from typing import Optional


def show_critical(parent, title: str, text: str, detailed_text: Optional[str] = None) -> int:
    """Show a critical error message with copyable text.
    
    Args:
        parent: Parent widget
        title: Dialog title
        text: Main message text
        detailed_text: Optional detailed error information
        
    Returns:
        Button that was clicked
    """
    msg = QMessageBox(parent)
    msg.setIcon(QMessageBox.Critical)
    msg.setWindowTitle(title)
    msg.setText(text)
    if detailed_text:
        msg.setDetailedText(detailed_text)
    
    # Make text selectable and copyable
    msg.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
    
    # Add OK button
    msg.setStandardButtons(QMessageBox.Ok)
    
    return msg.exec()


def show_warning(parent, title: str, text: str, detailed_text: Optional[str] = None) -> int:
    """Show a warning message with copyable text.
    
    Args:
        parent: Parent widget
        title: Dialog title
        text: Main message text
        detailed_text: Optional detailed warning information
        
    Returns:
        Button that was clicked
    """
    msg = QMessageBox(parent)
    msg.setIcon(QMessageBox.Warning)
    msg.setWindowTitle(title)
    msg.setText(text)
    if detailed_text:
        msg.setDetailedText(detailed_text)
    
    # Make text selectable and copyable
    msg.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
    
    # Add OK button
    msg.setStandardButtons(QMessageBox.Ok)
    
    return msg.exec()


def show_information(parent, title: str, text: str, detailed_text: Optional[str] = None) -> int:
    """Show an information message with copyable text.
    
    Args:
        parent: Parent widget
        title: Dialog title
        text: Main message text
        detailed_text: Optional detailed information
        
    Returns:
        Button that was clicked
    """
    msg = QMessageBox(parent)
    msg.setIcon(QMessageBox.Information)
    msg.setWindowTitle(title)
    msg.setText(text)
    if detailed_text:
        msg.setDetailedText(detailed_text)
    
    # Make text selectable and copyable
    msg.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
    
    # Add OK button
    msg.setStandardButtons(QMessageBox.Ok)
    
    return msg.exec()


def show_question(parent, title: str, text: str, 
                  buttons=QMessageBox.Yes | QMessageBox.No,
                  default_button=QMessageBox.No) -> int:
    """Show a question dialog with copyable text.
    
    Args:
        parent: Parent widget
        title: Dialog title
        text: Question text
        buttons: Buttons to show
        default_button: Default button
        
    Returns:
        Button that was clicked
    """
    msg = QMessageBox(parent)
    msg.setIcon(QMessageBox.Question)
    msg.setWindowTitle(title)
    msg.setText(text)
    
    # Make text selectable and copyable
    msg.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
    
    # Set buttons
    msg.setStandardButtons(buttons)
    msg.setDefaultButton(default_button)
    
    return msg.exec()