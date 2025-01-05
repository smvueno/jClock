import os
import shutil
from pathlib import Path

def cleanup_pyside():
    """Remove unnecessary PySide6 modules to reduce size"""
    venv_path = Path(__file__).parent / "venv"
    site_packages = list(venv_path.glob("**/site-packages"))[0]
    pyside6_path = site_packages / "PySide6"

    # Core modules needed by the clock
    keep_modules = {
        # Essential Python files
        "__init__.py",
        "_config.py",
        "_git_pyside_version.py",
        "py.typed",
        
        # Libraries
        "libpyside6.abi3.6.8.dylib",
        
        # Core Qt modules we use
        "QtCore.abi3.so",
        "QtGui.abi3.so",
        "QtWidgets.abi3.so",
        
        # Type hints we use
        "QtCore.pyi",
        "QtGui.pyi",
        "QtWidgets.pyi",
        
        # Required support dirs
        "support",
        "typesystems",
        
        # Required Qt subdirs
        "Qt",           # Contains core Qt resources
        "translations", # Required for any text rendering
        
        # Platform specific
        "plugins/platforms/libqcocoa.dylib",  # Required for macOS
        "plugins/styles/libqmacstyle.dylib",  # macOS styling
    }

    # Additional directories that need partial cleanup
    partial_keep = {
        "plugins/platforms",    # Keep only macOS platform
        "plugins/styles",       # Keep only macOS style
    }

    try:
        removed_size = 0
        files_removed = []
        
        for item in pyside6_path.iterdir():
            if item.name not in keep_modules:
                # Handle partial keeps
                if str(item.relative_to(pyside6_path)) in partial_keep:
                    continue
                    
                size = 0
                if item.is_file():
                    size = item.stat().st_size
                    files_removed.append(item.name)
                    item.unlink()
                elif item.is_dir():
                    size = sum(f.stat().st_size for f in item.rglob('*') if f.is_file())
                    files_removed.append(f"{item.name}/")
                    shutil.rmtree(item)
                removed_size += size

        # Clean up plugins directory to keep only essential files
        plugins_dir = pyside6_path / "plugins"
        if plugins_dir.exists():
            for plugin_cat in plugins_dir.iterdir():
                if plugin_cat.is_dir():
                    if plugin_cat.name not in ["platforms", "styles"]:
                        size = sum(f.stat().st_size for f in plugin_cat.rglob('*') if f.is_file())
                        files_removed.append(f"plugins/{plugin_cat.name}/")
                        shutil.rmtree(plugin_cat)
                        removed_size += size

        # Print summary
        print(f"\nCleaned up {removed_size / 1024 / 1024:.1f}MB")
        print("\nRemoved unnecessary modules:")
        for f in sorted(files_removed):
            print(f"- {f}")
        print("\nKept essential modules:")
        for f in sorted(keep_modules):
            print(f"+ {f}")

    except Exception as e:
        print(f"Error during cleanup: {e}")
        return False

    return True

if __name__ == "__main__":
    cleanup_pyside()