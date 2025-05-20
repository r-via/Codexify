import subprocess
import sys
from typing import Any

def _install_and_import(package_name: str, import_name: str = None) -> Any:
    """Attempts to install and import a package if not already available."""
    actual_import_name = import_name or package_name
    print(f"Dependency '{actual_import_name}' not found. Installing '{package_name}'...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet", "--disable-pip-version-check", package_name])
        print(f"Successfully installed '{package_name}'.")
        module = __import__(actual_import_name)
        return module
    except subprocess.CalledProcessError:
        print(f"Error: Install '{package_name}' manually:\n    pip install {package_name}")
        sys.exit(1)
    except ImportError:
        print(f"Error: Could not import '{actual_import_name}' after install.")
        sys.exit(1)

def ensure_gitignore_parser_module() -> Any:
    """Ensures gitignore_parser is available, installing it if necessary."""
    try:
        from gitignore_parser import parse_gitignore
        return parse_gitignore
    except ImportError:
        # return _install_and_import("gitignore-parser") # This returns the module, not the function
        print(f"Dependency 'gitignore-parser' not found. Installing...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet", "--disable-pip-version-check", "gitignore-parser"])
            print(f"Successfully installed 'gitignore-parser'.")
            from gitignore_parser import parse_gitignore # Re-import after install
            return parse_gitignore
        except subprocess.CalledProcessError:
            print(f"Error: Install 'gitignore-parser' manually:\n    pip install gitignore-parser")
            sys.exit(1)
        except ImportError:
            print(f"Error: Could not import 'gitignore_parser' after install.")
            sys.exit(1)


def ensure_pyyaml_module() -> Any:
    """Ensures PyYAML (yaml) is available, installing it if necessary."""
    try:
        import yaml
        return yaml
    except ImportError:
        return _install_and_import("PyYAML", "yaml")

def ensure_tiktoken_module() -> Any:
    """Ensures tiktoken is available, installing it if necessary."""
    try:
        import tiktoken
        return tiktoken
    except ImportError:
        return _install_and_import("tiktoken")