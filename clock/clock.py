from PySide6.QtWidgets import (
    QMainWindow, 
    QLabel, 
    QWidget, 
    QGraphicsDropShadowEffect, 
    QApplication,
    QSystemTrayIcon,
    QMenu
)
from PySide6.QtCore import (
    Qt, 
    QTimer, 
    QPoint, 
    QSize, 
    QPropertyAnimation, 
    QEasingCurve, 
    Property
)
from PySide6.QtGui import (
    QFont, 
    QColor, 
    QCursor, 
    QPainter, 
    QPainterPath,
    QPen, 
    QBrush,
    QLinearGradient,
    QFontMetrics,
    QAction, 
    QPixmap
)
from datetime import datetime
import logging
from math import cos, sin, radians
import time
import subprocess
import platform
import configparser
from pathlib import Path  # Add this import

from clock.config_manager import ClockSettings
from clock.system_tray import setup_system_tray, open_config_file, toggle_tray_setting, quit_tray_application
from clock.platform import APPKIT_AVAILABLE, get_target_screen
from logger_config import setup_logging, get_logger  # Import the logging setup and utility

# Configure logger
logger = get_logger(__name__)

# Update AppKit imports for better fullscreen detection
try:
    from AppKit import (
        NSWorkspace,
        NSApplicationActivationPolicyRegular,
        NSScreen,
        NSWindow,
        NSFullScreenWindowMask,
        NSWindowCollectionBehaviorCanJoinAllSpaces,
        NSWindowCollectionBehaviorParticipatesInCycle,
        NSWindowCollectionBehaviorStationary,
        NSFloatingWindowLevel,
        NSNormalWindowLevel
    )
    from Quartz import (
        CGWindowListCopyWindowInfo,
        kCGWindowListOptionOnScreenOnly,
        kCGNullWindowID,
        kCGWindowBounds,
        kCGWindowLayer,
        kCGWindowOwnerName,
        kCGWindowName
    )
    from Foundation import NSBundle
    import objc
    from ctypes import c_void_p
except ImportError:
    logger.warning("AppKit not available - fullscreen detection disabled")

class ClockGeometry:
    """Handles all sizing and positioning calculations for the clock"""
    def __init__(self, window, label):
        self.window = window
        self.label = label
        self.dpi_scale = self._get_dpi_scale()
        
    def _get_dpi_scale(self):
        """Get the current screen's DPI scaling factor"""
        try:
            screen = QApplication.primaryScreen()
            if screen:
                # Get both logical and physical DPI
                logical_dpi = screen.logicalDotsPerInch()
                physical_dpi = screen.physicalDotsPerInch()
                # Use the ratio or fall back to device pixel ratio
                if physical_dpi > 0:
                    return logical_dpi / 96.0
            return screen.devicePixelRatio() if screen else 1.0
        except Exception as e:
            logger.error(f"Error getting DPI scale: {e}")
            return 1.0
        
    def calculate_text_size(self, text):
        """Calculate the true size of text"""
        metrics = self.label.fontMetrics()
        return (metrics.horizontalAdvance(text), metrics.height())
        
    def calculate_padding(self):
        """Calculate padding based on font size and DPI"""
        base_padding = 10  # Base padding in pixels
        return int(base_padding * self.dpi_scale)
        
    def calculate_shadow_space(self, blur, offset_x, offset_y):
        """Calculate space needed for shadow"""
        blur = int(blur * self.dpi_scale)
        offset_x = int(offset_x * self.dpi_scale)
        offset_y = int(offset_y * self.dpi_scale)
        
        # Shadow space needs to account for blur radius and offset
        space_x = max(abs(offset_x), blur) * 2
        space_y = max(abs(offset_y), blur) * 2
        return (space_x, space_y)
        
    def calculate_total_size(self, text):
        """Calculate total window size including all spacing"""
        try:
            # Get base text size
            text_width, text_height = self.calculate_text_size(text)
            
            # Get padding
            padding = self.calculate_padding()
            total_padding_x = padding * 2
            total_padding_y = padding * 2
            
            # Get shadow spacing if enabled - Fix section name
            shadow_x, shadow_y = (0, 0)
            if self.window.settings.get_bool('styling', 'shadow_enabled', True):
                shadow_x, shadow_y = self.calculate_shadow_space(
                    self.window.settings.get_int('styling', 'shadow_blur', 2),
                    self.window.settings.get_int('styling', 'shadow_offset_x', 2),
                    self.window.settings.get_int('styling', 'shadow_offset_y', 2)
                )
            
            # Calculate final dimensions with shadow space
            total_width = text_width + total_padding_x + shadow_x
            total_height = text_height + total_padding_y + shadow_y
            
            return (total_width, total_height)
            
        except Exception as e:
            logger.error(f"Error calculating size: {e}")
            return (100, 50)  # Fallback size

class OutlinedClock(QLabel):
    """Custom label with gradient outline support"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.outline_width = 0  # Will be set from config
        self.gradient_start = QColor(255, 255, 255, 255)
        self.gradient_end = QColor(0, 0, 0, 255)
        self.gradient_angle = 90
        self.text_color = QColor(255, 255, 255, 255)
        self.time_text = ""
        self.seconds_text = ""
        self.seconds_size = 30
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Clear background
        painter.fillRect(self.rect(), Qt.transparent)
        
        # Draw main time text
        main_font = self.font()
        painter.setFont(main_font)
        
        # Draw seconds with different size
        seconds_font = QFont(main_font)
        seconds_font.setPointSize(self.seconds_size)
        
        # Calculate positions
        metrics = painter.fontMetrics()
        seconds_metrics = QFontMetrics(seconds_font)
        
        main_width = metrics.horizontalAdvance(self.time_text)
        main_height = metrics.height()
        
        x = (self.width() - (main_width + seconds_metrics.horizontalAdvance(self.seconds_text))) / 2
        y = (self.height() + main_height) / 2 - metrics.descent()
        
        # Draw main text
        path = QPainterPath()
        path.addText(x, y, main_font, self.time_text)
        
        # Draw seconds text
        seconds_path = QPainterPath()
        seconds_path.addText(x + main_width, y, seconds_font, self.seconds_text)
        
        # Combine paths
        path.addPath(seconds_path)
        
        # Draw outline and text (rest of the existing painting code)
        # Create gradient for outline
        if self.outline_width > 0:
            # Calculate gradient vector based on angle
            angle_rad = radians(self.gradient_angle)
            
            # Calculate gradient start/end points based on text bounds
            center_x = path.boundingRect().center().x()
            center_y = path.boundingRect().center().y()
            radius = max(path.boundingRect().width(), path.boundingRect().height()) / 2
            
            # Calculate gradient points from center of text
            start_x = center_x - cos(angle_rad) * radius
            start_y = center_y - sin(angle_rad) * radius
            end_x = center_x + cos(angle_rad) * radius
            end_y = center_y + sin(angle_rad) * radius
            
            # Create gradient
            gradient = QLinearGradient(
                start_x, start_y,  # Start point
                end_x, end_y       # End point
            )
            gradient.setColorAt(0, self.gradient_start)
            gradient.setColorAt(1, self.gradient_end)
            
            # Draw outline with gradient
            pen = QPen(QBrush(gradient), self.outline_width * 2)
            pen.setJoinStyle(Qt.RoundJoin)
            pen.setCapStyle(Qt.RoundCap)  # Add round caps for smoother outline
            painter.setPen(pen)
            painter.drawPath(path)

        # Draw text
        painter.setPen(Qt.NoPen)
        painter.setBrush(self.text_color)
        painter.drawPath(path)

class FloatingClock(QMainWindow):
    def __init__(self):
        super().__init__(flags=(
            Qt.FramelessWindowHint |
            Qt.Tool |
            Qt.WindowStaysOnTopHint |
            Qt.WindowTransparentForInput |  # Click-through is always enabled
            Qt.NoDropShadowWindowHint |
            Qt.WindowDoesNotAcceptFocus
        ))
        
        # Initialize attributes first
        self.settings = ClockSettings()
        self.timer = None
        self.mouse_timer = None
        self.geometry_handler = None
        self.fullscreen_timer = None
        self.is_fullscreen_active = False
        self.hidden = False
        
        # Add opacity property and animation
        self._opacity = 1.0
        self.animation = QPropertyAnimation(self, b"windowOpacity", self)
        self.animation.setEasingCurve(QEasingCurve.InOutCubic)
        
        # Setup UI first so window is created
        self._initialize_ui()
        
        # Setup native window behavior AFTER window is shown
        self.show()
        
        if APPKIT_AVAILABLE:
            try:
                # Get the native window handle - different approach
                view = self.winId().__int__()
                nsview = objc.objc_object(c_void_p=view)
                
                # Try different methods to get the window
                if hasattr(nsview, 'window'):
                    self.native_window = nsview.window()
                elif hasattr(nsview, 'windowHandle'):
                    self.native_window = nsview.windowHandle()
                
                if self.native_window is not None:
                    # Set window level and behavior
                    self.native_window.setLevel_(NSFloatingWindowLevel)
                    self.native_window.setCollectionBehavior_(
                        NSWindowCollectionBehaviorCanJoinAllSpaces |
                        NSWindowCollectionBehaviorStationary |
                        NSWindowCollectionBehaviorParticipatesInCycle
                    )
                    self.native_window.orderFront_(None)
                else:
                    logger.error("Could not get native window handle")
            except Exception as e:
                logger.error(f"Failed to set native window behavior: {e}")
        
        # Setup watchers and complete initialization
        self.settings.add_watcher(lambda: self.settings.apply_settings(self))
        self.settings.apply_settings(self)
        
        # Setup tray icon
        self.tray = setup_system_tray(self)
        
    def getOpacity(self):
        return self._opacity
        
    def setOpacity(self, opacity):
        self._opacity = opacity
        self.setWindowOpacity(opacity)
        
    opacity = Property(float, getOpacity, setOpacity)
    
    def animate_opacity(self, end_value, on_finished=None):
        """Animate window opacity with configurable duration"""
        if self.animation.state() == QPropertyAnimation.Running:
            self.animation.stop()
            
        duration = self.settings.get_int('behavior', 'fade_duration', 500)
        self.animation.setDuration(duration)
        self.animation.setStartValue(self.windowOpacity())
        self.animation.setEndValue(end_value)
        
        if on_finished:
            self.animation.finished.connect(lambda: (
                on_finished(), 
                self.animation.finished.disconnect()
            ))
            
        self.animation.start()
    
    def _initialize_ui(self):
        # Create central widget with correct attributes
        central = QWidget()
        central.setAttribute(Qt.WA_TranslucentBackground)  # Add this line
        self.setCentralWidget(central)
        
        # Create time label with custom painting
        self.time_label = OutlinedClock(central)
        self.time_label.setContentsMargins(10, 10, 10, 10)  # Add margins for shadow space
        
        # Initialize geometry handler
        self.geometry_handler = ClockGeometry(self, self.time_label)
        
        # Create timer only if not exists
        if self.timer is None:
            self.timer = QTimer(self)  # Set parent for proper cleanup
            self.timer.timeout.connect(self.update_time)
        
        # Setup mouse tracking timer
        self.mouse_timer = QTimer(self)
        self.mouse_timer.timeout.connect(self.check_mouse_proximity)
        self.mouse_timer.start(200)  # Check every 200ms
        
        # Setup fullscreen detection timer - only if hide_in_fullscreen is enabled
        if APPKIT_AVAILABLE:
            self.fullscreen_timer = QTimer(self)
            self.fullscreen_timer.timeout.connect(self._check_fullscreen)
            if self.settings.get_bool('behavior', 'hide_in_fullscreen', True):
                self.fullscreen_timer.start(1000)  # Check every second
        
        # Apply initial settings
        self.settings.apply_settings(self)
        
        # Start timer
        self.timer.start(1000)  # Default 1 second, will be updated from settings
        
    def update_time(self):
        """Update the displayed time and adjust size for shadow"""
        try:
            now = datetime.now()
            time_format = self.settings.get('format', 'time_format')
            seconds_format = self.settings.get('format', 'time_seconds_format')
            
            # Format time without leading zeros for 12h format
            if '%I' in time_format:
                self.time_label.time_text = now.strftime(time_format).lstrip('0')
                if '%I' in seconds_format:
                    self.time_label.seconds_text = now.strftime(seconds_format).lstrip('0')
                else:
                    self.time_label.seconds_text = now.strftime(seconds_format)
            else:
                self.time_label.time_text = now.strftime(time_format)
                self.time_label.seconds_text = now.strftime(seconds_format)
            
            # Calculate seconds size as a ratio of main font size
            main_size = self.settings.get_int('appearance', 'font_size', 40)
            seconds_ratio = self.settings.get_float('format', 'time_seconds_size', 0.5)
            self.time_label.seconds_size = int(main_size * seconds_ratio)
            
            # Force repaint
            self.time_label.update()
            
            # Calculate size and update window
            total_size = self.geometry_handler.calculate_total_size(
                self.time_label.time_text + self.time_label.seconds_text
            )
            if total_size:
                self.setFixedSize(*total_size)
                self.time_label.setGeometry(0, 0, *total_size)
                self._apply_position()
                
        except Exception as e:
            logger.error(f"Error updating time display: {e}")

    def check_mouse_proximity(self):
        """Handle mouse proximity and clock visibility with animation"""
        try:
            if not self.isVisible() or not self.settings.get_bool('behavior', 'auto_hide', True):
                return
                
            cursor_pos = QCursor.pos()
            widget_rect = self.geometry()
            proximity_threshold = self.settings.get_int('window', 'proximity_threshold', 50)

            # Check if mouse is near the clock
            is_near = widget_rect.adjusted(
                -proximity_threshold, 
                -proximity_threshold,
                proximity_threshold, 
                proximity_threshold
            ).contains(cursor_pos)

            # Update visibility based on mouse position
            if is_near and not self.hidden:
                self.animate_opacity(0)
                self.hidden = True
            elif not is_near and self.hidden:
                self.animate_opacity(1)
                self.hidden = False
        except Exception as e:
            logger.exception("Error during mouse proximity check")
            
    def closeEvent(self, event):
        """Enhanced cleanup with tray icon removal"""
        self.animate_opacity(0, lambda: super().closeEvent(event))
        event.ignore()  # Prevent immediate close
        if hasattr(self, 'tray'):
            self.tray.hide()
        if self.timer is not None:
            self.timer.stop()
        if self.mouse_timer:
            self.mouse_timer.stop()
        if self.fullscreen_timer:
            self.fullscreen_timer.stop()
        if self.settings:
            self.settings.remove_watcher(lambda: self.settings.apply_settings(self))
        super().closeEvent(event)
        # Then quit the application
        QApplication.instance().quit()
        
    def _check_fullscreen(self):
        """Universal fullscreen detection using simple size check"""
        try:
            if not APPKIT_AVAILABLE or not self.settings.get_bool('behavior', 'hide_in_fullscreen', True):
                self.is_fullscreen_active = False
                self.setVisible(True)  # Make sure clock is visible if setting is disabled
                return

            # Get all windows
            window_list = CGWindowListCopyWindowInfo(kCGWindowListOptionOnScreenOnly, kCGNullWindowID)
            if not window_list:
                return

            # Get main screen dimensions
            main_screen = NSScreen.mainScreen()
            screen_frame = main_screen.frame()
            screen_width = int(screen_frame.size.width)
            screen_height = int(screen_frame.size.height)

            was_fullscreen = self.is_fullscreen_active
            self.is_fullscreen_active = False

            # Check each window
            for window in window_list:
                bounds = window.get(kCGWindowBounds)
                if not bounds:
                    continue

                # Get window dimensions and properties
                width = int(bounds.get('Width', 0))
                height = int(bounds.get('Height', 0))
                window_owner = window.get(kCGWindowOwnerName, '')

                # Get exclusion list from settings
                exclude_list = {x.strip() for x in self.settings.get('behavior', 'fullscreen_exclude', '').split(',')}

                # Skip excluded system components
                if window_owner in exclude_list:
                    continue

                # Simple fullscreen check: just check if window covers most of screen
                if (width >= screen_width * 0.98 and
                    height >= screen_height * 0.98):
                    self.is_fullscreen_active = True
                    # Only log which app triggered fullscreen
                    logger.info(f"Fullscreen detected: {window_owner}")
                    break

            # Only update visibility if state changed
            if was_fullscreen != self.is_fullscreen_active:
                if self.is_fullscreen_active:
                    self.animate_opacity(0, lambda: self.setVisible(False))
                else:
                    self.setVisible(True)
                    self.animate_opacity(1)

        except Exception as e:
            # Throttle error logging
            current_time = time.time()
            if not hasattr(self, '_last_fullscreen_error'):
                self._last_fullscreen_error = 0
            if current_time - self._last_fullscreen_error > 60:
                logger.error(f"Fullscreen check error: {e}")
                self._last_fullscreen_error = current_time

    def _quit_application(self):
        """Properly quit the entire application"""
        # First close the window (triggers cleanup)
        self.close()
        # Then quit the application
        QApplication.instance().quit()
        
    def showEvent(self, event):
        """Fade in when showing"""
        super().showEvent(event)
        self.setWindowOpacity(0)
        self.animate_opacity(1)

    def _apply_position(self):
        """Apply position settings using percentage positioning"""
        self.settings._apply_position(self)