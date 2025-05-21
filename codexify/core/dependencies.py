# File: codexify/core/dependencies.py
# ------------------------------------------------------------
import subprocess
import sys
from typing import Any, Callable, Optional

def _install_and_import(package_name: str, import_name: Optional[str] = None) -> Any:
    """
    Attempts to install a package using pip and then import it.

    If `import_name` is not provided, it defaults to `package_name`.
    This function is intended for automatically handling missing optional
    dependencies.

    Args:
        package_name: The name of the package to install via pip (e.g., "PyYAML").
        import_name: The name to use for importing the module (e.g., "yaml").
                     If None, `package_name` is used.

    Returns:
        The imported module.

    Raises:
        SystemExit: If installation or import fails.
    """
    actual_import_name: str = import_name if import_name is not None else package_name

    print(f"Dependency '{actual_import_name}' not found. Attempting to install '{package_name}'...")
    try:
        # Use --quiet for less pip output, and --disable-pip-version-check to avoid warnings
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "--quiet",
            "--disable-pip-version-check", package_name
        ])
        print(f"Successfully installed '{package_name}'.")
        module: Any = __import__(actual_import_name)
        return module
    except subprocess.CalledProcessError as e:
        print(f"Error: Failed to install '{package_name}' using pip. Process exited with {e.returncode}.")
        print(f"Please try installing it manually: pip install {package_name}")
        sys.exit(1)
    except ImportError:
        print(f"Error: Could not import '{actual_import_name}' even after attempting installation of '{package_name}'.")
        print(f"Please ensure '{package_name}' is correctly installed and accessible.")
        sys.exit(1)
    except Exception as e: # Catch any other unexpected error during pip install or import
        print(f"An unexpected error occurred during installation/import of '{package_name}': {e}")
        sys.exit(1)

# Define the expected signature of the gitignore_parser.parse_gitignore function
# It takes a path to the .gitignore file and an optional base directory,
# and returns a callable (the matcher) that takes a file path and returns a bool.
GitignoreMatcher = Callable[[str], bool]
ParseGitignoreFuncType = Callable[[str, Optional[str]], GitignoreMatcher]

def ensure_gitignore_parser_module() -> ParseGitignoreFuncType:
    """
    Ensures the 'gitignore_parser' module is available and returns its 'parse_gitignore' function.

    If the module is not found, it attempts to install 'gitignore-parser' via pip.

    Returns:
        The `parse_gitignore` function from the `gitignore_parser` module, typed
        as `ParseGitignoreFuncType`.

    Raises:
        SystemExit: If the module cannot be installed or the function cannot be found.
    """
    try:
        from gitignore_parser import parse_gitignore
        # Cast to our defined type to satisfy consumers, even if stubs are missing.
        return parse_gitignore # type: ignore[return-value]
    except ImportError:
        module: Any = _install_and_import("gitignore-parser")
        try:
            # Attempt to get the function after installation
            parse_func: Any = getattr(module, 'parse_gitignore')
            if not callable(parse_func): # Basic check
                raise AttributeError("'parse_gitignore' is not callable.")
            return parse_func # type: ignore[return-value]
        except AttributeError:
            print("Error: 'parse_gitignore' function not found in the installed 'gitignore-parser' module.")
            print("This might indicate an issue with the package version or installation.")
            sys.exit(1)

def ensure_pyyaml_module() -> Any:
    """
    Ensures the 'PyYAML' (imported as 'yaml') module is available.

    If the module is not found, it attempts to install 'PyYAML' via pip.

    Returns:
        The imported 'yaml' module.

    Raises:
        SystemExit: If the module cannot be installed or imported.
    """
    try:
        import yaml
        return yaml
    except ImportError:
        return _install_and_import("PyYAML", "yaml")

def ensure_tiktoken_module() -> Any:
    """
    Ensures the 'tiktoken' module is available.

    If the module is not found, it attempts to install 'tiktoken' via pip.

    Returns:
        The imported 'tiktoken' module.

    Raises:
        SystemExit: If the module cannot be installed or imported.
    """
    try:
        import tiktoken
        return tiktoken
    except ImportError:
        return _install_and_import("tiktoken")