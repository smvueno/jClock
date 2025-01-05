import os
import logging
from typing import Any, Callable, List, Tuple
from pathlib import Path
import configparser
from PySide6.QtCore import QTimer
from clock.platform import APPKIT_AVAILABLE
from PySide6.QtGui import QColor, QFont, QFontMetrics
from PySide6.QtWidgets import QGraphicsDropShadowEffect
from PySide6.QtCore import Qt
from clock.platform import get_target_screen
from logger_config import get_logger

# Configure logger
logger = get_logger(__name__)

if APPKIT_AVAILABLE:
    from AppKit import NSFloatingWindowLevel, NSNormalWindowLevel, NSWindowCollectionBehaviorCanJoinAllSpaces, NSWindowCollectionBehaviorStationary, NSWindowCollectionBehaviorParticipatesInCycle

class ClockSettings:
    def __init__(self):
        """Initialize settings with watchers"""
        self.watchers: List[Callable] = []
        self.config = configparser.ConfigParser(interpolation=None)
        
        # Initialize paths
        self.config_dir = Path(__file__).parent.parent / "config"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.ini_path = self.config_dir / "settings.ini"  # Updated filename
        
        # Try loading settings.ini first, fall back to default.ini if it exists
        if not self.ini_path.exists():
            old_path = self.config_dir / "default.ini"
            if old_path.exists():
                logger.info("Migrating from default.ini to settings.ini")
                old_path.rename(self.ini_path)
        
        # Load settings
        self.load()
        
        # Setup file watcher
        self.last_modified = self._get_file_mtime()
        self.file_watcher = QTimer()
        self.file_watcher.timeout.connect(self._check_file_changes)
        self.file_watcher.start(1000)  # Check every second

    def _get_file_mtime(self) -> float:
        """Get file modification time"""
        try:
            return self.ini_path.stat().st_mtime if self.ini_path.exists() else 0
        except Exception:
            return 0

    def _check_file_changes(self) -> None:
        """Check if settings file has been modified"""
        try:
            current_mtime = self._get_file_mtime()
            if current_mtime > self.last_modified:
                logger.info("Settings file changed, reloading...")
                self.last_modified = current_mtime
                self.load()
                self._notify_watchers()
        except Exception as e:
            logger.error(f"Error checking file changes: {e}")

    def load(self) -> None:
        """Load settings from INI file"""
        try:
            if not self.ini_path.exists():
                logger.error(f"Settings file not found: {self.ini_path}")
                return
                
            self.config.read(self.ini_path)
            logger.debug(f"Settings loaded from {self.ini_path}")
            
        except Exception as e:
            logger.error(f"Settings load error: {e}")

    def get(self, section: str, key: str, default: Any = None) -> str:
        """Get a setting value with optional default"""
        try:
            if not self.config.has_section(section):
                return str(default)
            if not self.config.has_option(section, key):
                return str(default)
            return self.config.get(section, key)
        except Exception as e:
            logger.debug(f"Settings get error: {section}.{key}")
            return str(default)

    def get_int(self, section: str, key: str, default: int = 0) -> int:
        """Get a setting value as integer"""
        try:
            return self.config.getint(section, key)
        except:
            return default

    def get_float(self, section: str, key: str, default: float = 0.0) -> float:
        """Get a setting value as float"""
        try:
            value = self.get(section, key, str(default))
            value = value.split(';')[0].strip()
            return float(value)
        except (ValueError, TypeError) as e:
            logger.error(f"Error converting [{section}] {key} to float: {e}")
            return default

    def get_bool(self, section: str, key: str, default: bool = False) -> bool:
        """Get a setting value as boolean"""
        try:
            value = self.get(section, key, str(default))
            value = value.split(';')[0].strip().lower()
            return value in ('true', 'yes', '1', 'on', 't')
        except:
            return default

    def get_color(self, section: str, key: str) -> Tuple[int, int, int, int]:
        """Get a color setting as RGBA tuple"""
        try:
            value = self.get(section, key)
            value = value.split(';')[0].strip()
            color = [int(x.strip()) for x in value.split(',')]
            while len(color) < 4:
                color.append(255)
            return tuple(color[:4])
        except:
            return (255, 255, 255, 255)

    def add_watcher(self, callback: Callable) -> None:
        """Add a settings change watcher"""
        if callback not in self.watchers:
            self.watchers.append(callback)

    def remove_watcher(self, callback: Callable) -> None:
        """Remove a settings change watcher"""
        if callback in self.watchers:
            self.watchers.remove(callback)

    def _notify_watchers(self) -> None:
        """Notify all watchers of settings changes"""
        for watcher in self.watchers:
            try:
                watcher()
            except Exception as e:
                logger.error(f"Error in settings watcher: {e}")

    def apply_settings(self, clock):
        """Enhanced settings application with position memory"""
        try:
            saved_opacity = clock.windowOpacity()
            clock.hide()
            
            # First update window flags and attributes
            self._update_window_attributes(clock)
            self.apply_appearance(clock)
            self._apply_position(clock)
            
            # Handle auto-hide state without changing window flags
            if not self.get_bool('behavior', 'auto_hide', True):
                clock.hidden = False
            
            # Restore opacity and show window
            clock.show()
            clock.setWindowOpacity(saved_opacity)
            if self.get_bool('window', 'always_on_top', True):
                clock.raise_()
            
            self._update_timers(clock)
            
        except Exception as e:
            logger.error(f"Error applying settings: {e}", exc_info=True)

    def _update_window_attributes(self, clock):
        """Update window flags and attributes"""
        try:
            # Store current state
            was_visible = clock.isVisible()
            
            # Set base flags that never change
            flags = (Qt.FramelessWindowHint |
                    Qt.Tool |
                    Qt.WindowTransparentForInput |
                    Qt.NoDropShadowWindowHint |
                    Qt.WindowDoesNotAcceptFocus)
            
            # Add always-on-top flag if enabled (independent of auto-hide)
            if self.get_bool('window', 'always_on_top', True):
                flags |= Qt.WindowStaysOnTopHint
            
            # Update window flags
            clock.setWindowFlags(flags)
            
            # Set basic attributes
            clock.setAttribute(Qt.WA_TranslucentBackground)
            clock.setAttribute(Qt.WA_ShowWithoutActivating)
            clock.setAttribute(Qt.WA_MacAlwaysShowToolWindow)
            
            # Update native window (macOS)
            if APPKIT_AVAILABLE and hasattr(clock, 'native_window'):
                try:
                    if self.get_bool('window', 'always_on_top', True):
                        clock.native_window.setLevel_(NSFloatingWindowLevel)
                        clock.native_window.orderFrontRegardless()
                    else:
                        clock.native_window.setLevel_(NSNormalWindowLevel)
                    
                    clock.native_window.setCollectionBehavior_(
                        NSWindowCollectionBehaviorCanJoinAllSpaces |
                        NSWindowCollectionBehaviorStationary |
                        NSWindowCollectionBehaviorParticipatesInCycle
                    )
                except Exception as e:
                    logger.error(f"Error updating native window level: {e}")
            
            # Restore visibility
            if was_visible:
                clock.show()
                if self.get_bool('window', 'always_on_top', True):
                    clock.raise_()
                    
        except Exception as e:
            logger.error(f"Error updating window attributes: {e}")

    def _update_timers(self, clock):
        """Update timer intervals"""
        try:
            update_interval = self.get_int('behavior', 'update_interval', 1000)
            mouse_interval = self.get_int('behavior', 'mouse_check_interval', 200)
            
            if clock.timer:
                clock.timer.setInterval(update_interval)
            if clock.mouse_timer:
                clock.mouse_timer.setInterval(mouse_interval)
        except Exception as e:
            logger.error(f"Error updating timers: {e}")

    def _apply_position(self, clock):
        """Apply position settings using percentage positioning"""
        try:
            screen = get_target_screen(self.get_int('window', 'position_screen', 0))
            if not screen:
                return
                
            pos_x = self.get_float('window', 'position_x', 50)
            pos_y = self.get_float('window', 'position_y', 50)
            
            screen_rect = screen.geometry()
            
            main_metrics = clock.time_label.fontMetrics()
            main_width = main_metrics.horizontalAdvance(clock.time_label.time_text)
            
            seconds_font = QFont(clock.time_label.font())
            seconds_font.setPointSize(clock.time_label.seconds_size)
            seconds_metrics = QFontMetrics(seconds_font)
            seconds_width = seconds_metrics.horizontalAdvance(clock.time_label.seconds_text)
            
            total_text_width = main_width + seconds_width
            text_height = main_metrics.height()
            
            text_x = screen_rect.x() + ((screen_rect.width() - total_text_width) * pos_x / 100.0)
            text_y = screen_rect.y() + ((screen_rect.height() - text_height) * pos_y / 100.0)
            
            offset_x = (clock.width() - total_text_width) / 2
            offset_y = (clock.height() - text_height) / 2
            
            window_x = text_x - offset_x
            window_y = text_y - offset_y
            
            clock.move(round(window_x), round(window_y))
            
        except Exception as e:
            logger.error(f"Position error: {e}")

    def apply_appearance(self, clock):
        """Apply clock appearance settings"""
        try:
            shadow_enabled = self.get_bool('styling', 'shadow_enabled', True)
            
            self._apply_colors(clock)
            self._apply_font(clock)
            
            clock.time_label.outline_width = self.get_int('styling', 'outline_width', 1)
            clock.time_label.gradient_angle = self.get_int('styling', 'gradient_angle', 90)
            
            self._apply_effects(clock, shadow_enabled)
            
            total_size = clock.geometry_handler.calculate_total_size(clock.time_label.text())
            if total_size:
                clock.setFixedSize(*total_size)
                
        except Exception as e:
            logger.error(f"Appearance error: {e}")

    def _apply_colors(self, clock):
        """Apply color settings"""
        clock.time_label.text_color = QColor(*self.get_color('styling', 'text'))
        clock.time_label.gradient_start = QColor(*self.get_color('styling', 'gradient_start'))
        clock.time_label.gradient_end = QColor(*self.get_color('styling', 'gradient_end'))

    def _apply_font(self, clock):
        """Apply font settings"""
        font = QFont(
            self.get('styling', 'font_family', 'Sen'),
            self.get_int('styling', 'font_size', 40)
        )
        
        weight_map = {
            'thin': QFont.Thin,
            'extralight': QFont.ExtraLight,
            'light': QFont.Light,
            'normal': QFont.Normal,
            'medium': QFont.Medium,
            'demibold': QFont.DemiBold,
            'bold': QFont.Bold,
            'extrabold': QFont.ExtraBold,
            'black': QFont.Black
        }
        
        weight = self.get('styling', 'font_weight', 'normal').lower()
        font.setWeight(weight_map.get(weight, QFont.Normal))
        
        font.setStyleStrategy(QFont.PreferAntialias | QFont.PreferQuality)
        clock.time_label.setFont(font)

    def _apply_effects(self, clock, shadow_enabled: bool):
        """Apply visual effects"""
        clock.time_label.setGraphicsEffect(None)
        if shadow_enabled:
            shadow = QGraphicsDropShadowEffect(clock.time_label)
            shadow.setColor(QColor(*self.get_color('styling', 'shadow')))
            shadow.setBlurRadius(self.get_int('styling', 'shadow_blur', 4) * 4)
            shadow.setXOffset(self.get_int('styling', 'shadow_offset_x', 2))
            shadow.setYOffset(self.get_int('styling', 'shadow_offset_y', 2))
            clock.time_label.setGraphicsEffect(shadow)

def _test_settings():
    """Test settings functionality"""
    logging.basicConfig(level=logging.DEBUG)
    settings = ClockSettings()
    
    print("\nTesting settings:")
    print("-" * 40)
    print(f"Position: {settings.get_float('window', 'position_x')}%, {settings.get_float('window', 'position_y')}%")
    print(f"Font: {settings.get('appearance', 'font_family')} {settings.get_int('appearance', 'font_size')}pt")
    print(f"Time format: {settings.get('appearance', 'time_format')}")
    print(f"Text color: {settings.get_color('colors', 'text')}")
    print(f"Shadow enabled: {settings.get_bool('effects', 'shadow_enabled')}")
    print("-" * 40)

if __name__ == "__main__":
    _test_settings()