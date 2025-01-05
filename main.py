# main.py
import sys
import os
import signal
import warnings
import subprocess
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QTimer
from Foundation import NSBundle
from clock.platform import hide_dock_icon  # Import hide_dock_icon
from logger_config import setup_logging, get_logger  # Import the logging setup and utility

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from clock.clock import FloatingClock

# Configure logger
logger = get_logger(__name__)

def cleanup(logger):
    """Clean up resources and ensure proper exit"""
    try:
        logger.info("Cleaning up application...")
        app = QApplication.instance()
        if app:
            for window in app.topLevelWidgets():
                window.close()
            app.quit()
    except Exception as e:
        logger.exception("Error during cleanup")
    sys.exit(0)

def signal_handler(signum, frame, logger):
    """Handle interrupt signals"""
    logger.info(f"Received signal {signum}")
    cleanup(logger)

def launch_background():
    """Launch the clock in background mode using venv"""
    script_dir = Path(__file__).parent
    venv_dir = script_dir / "venv"
    
    # Try different Python executables
    python_executables = [
        venv_dir / "bin" / "pythonw",
        venv_dir / "bin" / "python3",
        venv_dir / "bin" / "python"
    ] if sys.platform == "darwin" else [
        venv_dir / "Scripts" / "pythonw.exe",
        venv_dir / "Scripts" / "python.exe"
    ]
    
    # Find first available Python executable
    python_path = next((str(exe) for exe in python_executables if exe.exists()), None)
    
    if not python_path:
        logger.error("Error: Could not find Python executable in venv")
        sys.exit(1)
    
    # Setup environment
    env = os.environ.copy()
    env["PYTHONPATH"] = str(script_dir)
    
    if sys.platform == "darwin":
        env["PYTHONUNBUFFERED"] = "1"
        env["QT_MAC_DISABLE_FOREGROUND_APPLICATION_TRANSFORM"] = "1"
    
    # Launch the application
    try:
        subprocess.Popen(
            [python_path, str(__file__), "--foreground"],
            env=env,
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        logger.info(f"Launched clock using {python_path}")
        return 0
    except Exception as e:
        logger.exception(f"Error launching clock: {e}")
        return 1

def main():
    """Application entry point"""
    # Check if running in background mode
    if "--background" in sys.argv:
        return launch_background()
        
    app = None
    
    try:
        # Setup logging path to match new settings name
        logger = setup_logging(Path(__file__).parent / 'logs' / 'floating_clock.log')
        
        # Setup signal handlers for better cleanup
        signal.signal(signal.SIGINT, lambda s, f: signal_handler(s, f, logger))
        signal.signal(signal.SIGTERM, lambda s, f: signal_handler(s, f, logger))
        
        # Suppress deprecation warnings
        warnings.filterwarnings("ignore", category=DeprecationWarning)
        
        # Configure environment
        os.environ['NSSupportsAutomaticGraphicsSwitching'] = 'True'
        os.environ['QT_LOGGING_RULES'] = '*.debug=false;qt.qpa.*=false;*.warning=false'
        # Add these to suppress IMK messages
        os.environ['OBJC_DEBUG_MISSING_POOLS'] = 'NO'
        os.environ['PYTHONUNBUFFERED'] = '1'
        
        # Hide dock icon first, before any UI initialization
        hide_dock_icon()
        
        # Initialize application with system tray support
        app = QApplication(sys.argv)
        app.setApplicationName("FloatingClock")
        app.setQuitOnLastWindowClosed(False)  # Keep running when window is closed
        
        # Create and show clock (fixed initialization)
        clock = FloatingClock()  # Remove incorrect parameters
        clock.show()
        clock.raise_()
        clock.activateWindow()
        
        return app.exec()
        
    except Exception as e:
        logger.exception("Fatal error in main")
        if app:
            cleanup(logger)
        return 1
    finally:
        if app:
            app.quit()

if __name__ == "__main__":
    sys.exit(main())