from PySide6.QtWidgets import QSystemTrayIcon, QMenu, QApplication
from PySide6.QtGui import QFont, QPixmap, QPainter, QColor
from PySide6.QtCore import QSize, Qt
import platform
import subprocess
import configparser
from logger_config import get_logger

logger = get_logger(__name__)

def setup_system_tray(clock):
    """Setup system tray icon and menu"""
    tray = QSystemTrayIcon(clock)
    
    # Create icon with white 'J'
    icon_size = QSize(64, 64)
    pixmap = QPixmap(icon_size)
    pixmap.fill(Qt.transparent)
    
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    
    # Use system font
    font = QFont()
    font.setPixelSize(50)
    font.setBold(True)
    painter.setFont(font)
    
    # Center text
    metrics = painter.fontMetrics()
    text_rect = metrics.boundingRect("J")
    x = (icon_size.width() - text_rect.width()) / 2
    y = (icon_size.height() + text_rect.height()) / 2 - metrics.descent()
    
    # Draw white J
    painter.setPen(QColor(255, 255, 255))
    painter.drawText(int(x), int(y), "J")
    
    painter.end()
    tray.setIcon(pixmap)
    
    # Create menu
    menu = QMenu()
    
    open_config = menu.addAction("Open Config")
    open_config.triggered.connect(lambda: open_config_file(clock))
    
    menu.addSeparator()
    
    clock.toggle_actions = {}
    toggle_options = [
        ('always_on_top', 'window', 'Always on Top'),
        ('hide_in_fullscreen', 'behavior', 'Hide in Fullscreen'),
        ('auto_hide', 'behavior', 'Auto Hide')
    ]
    
    for setting_key, section, label in toggle_options:
        action = menu.addAction(label)
        action.setCheckable(True)
        # Read from correct section for each setting
        action.setChecked(clock.settings.get_bool(section, setting_key, True))
        action.triggered.connect(lambda checked, k=setting_key, s=section: toggle_tray_setting(clock, k, s, checked))
        clock.toggle_actions[setting_key] = action
    
    menu.addSeparator()
    
    quit_action = menu.addAction("Quit")
    quit_action.triggered.connect(lambda: quit_tray_application(clock))
    
    tray.setContextMenu(menu)
    tray.show()
    
    return tray

def open_config_file(clock):
    """Open config file with default editor"""
    try:
        config_path = clock.settings.ini_path
        if platform.system() == 'Darwin':
            subprocess.run(['open', str(config_path)])
        else:
            subprocess.run(['xdg-open', str(config_path)])
    except Exception as e:
        logger.error(f"Error opening config: {e}")

def toggle_tray_setting(clock, key: str, section: str, value: bool):
    """Toggle a boolean setting while preserving comments"""
    try:
        # Read the original file content
        with open(clock.settings.ini_path, 'r') as f:
            lines = f.readlines()
        
        # Find the section and key
        current_section = ''
        for i, line in enumerate(lines):
            line = line.strip()
            # Check for section
            if line.startswith('[') and line.endswith(']'):
                current_section = line[1:-1]
            # When in correct section, find and update the key
            elif current_section == section and line.split('=')[0].strip() == key:
                # Preserve any comment that might exist
                parts = line.split(';', 1)
                base = parts[0].split('=')[0]
                comment = ';' + parts[1] if len(parts) > 1 else ''
                # Update the line with new value while keeping comment
                lines[i] = f"{base}= {str(value).lower()}{comment}\n"
                break
        
        # Write back the modified content
        with open(clock.settings.ini_path, 'w') as f:
            f.writelines(lines)
        
        # Handle specific settings separately
        if key == 'always_on_top':
            clock.settings._update_window_attributes(clock)
        elif key == 'auto_hide':
            clock.hidden = not value
            if not value:
                clock.setWindowOpacity(1.0)
                
    except Exception as e:
        logger.error(f"Error toggling setting {key}: {e}")

def quit_tray_application(clock):
    """Properly quit the entire application"""
    clock.close()
    QApplication.instance().quit()
