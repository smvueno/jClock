import logging
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor
import platform
import subprocess
import time

logger = logging.getLogger(__name__)

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
    APPKIT_AVAILABLE = True
except ImportError:
    APPKIT_AVAILABLE = False
    logger.warning("AppKit not available - fullscreen detection disabled")

def get_target_screen(screen_index: int):
    """Enhanced screen detection using Cocoa"""
    try:
        # Get all screens using Cocoa
        ns_screens = NSScreen.screens()
        if not ns_screens or screen_index >= len(ns_screens):
            return QApplication.primaryScreen()
        
        # Get target screen
        target_ns_screen = ns_screens[screen_index]
        
        # Match NSScreen to Qt screen
        target_frame = target_ns_screen.frame()
        qt_screens = QApplication.screens()
        
        for qt_screen in qt_screens:
            qt_geometry = qt_screen.geometry()
            # Match by position and size
            if (abs(qt_geometry.x() - target_frame.origin.x) < 1 and
                abs(qt_geometry.y() - target_frame.origin.y) < 1):
                return qt_screen
        
        return QApplication.primaryScreen()
        
    except Exception as e:
        logger.error(f"Error getting target screen: {e}")
        return QApplication.primaryScreen()

def hide_dock_icon():
    """Hide the dock icon using PyObjC bridge - always hidden by default"""
    try:
        info = NSBundle.mainBundle().infoDictionary()
        info["LSBackgroundOnly"] = "1"  # Always set to background only
        info["LSUIElement"] = "1"       # Additional setting to ensure dock icon is hidden
        logger.debug("Dock icon hidden")
    except Exception as e:
        logger.error(f"Could not hide dock icon: {e}")  # Changed to error level since this is required
