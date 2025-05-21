# File: codexify/core/go_utils.py
# ------------------------------------------------------------
import os
import subprocess
from typing import List, Dict, Optional, Sequence, Union # Added Union
import shutil

from ..types import CompilationConfig
from .file_system import is_likely_binary

def _format_command_for_display(cmd_attr: Union[str, Sequence[str]]) -> str:
    """Helper to format a command attribute for display."""
    if isinstance(cmd_attr, str):
        return cmd_attr
    # At this point, cmd_attr should be Sequence[str]
    # We can iterate and ensure elements are strings if Pylance is still unsure
    return ' '.join(str(arg) for arg in cmd_attr)


def get_go_package_locations(config: CompilationConfig, package_paths: List[str], project_root_for_go_mod: Optional[str]) -> Dict[str, str]:
    """
    Finds the on-disk locations of specified Go packages using 'go list'.

    This function attempts to resolve each Go package import path to its
    corresponding directory on the filesystem. It uses the 'go list'
    command for this purpose.

    Args:
        config: The `CompilationConfig` object, used for `verbose` logging.
        package_paths: A list of Go package import paths (e.g., "github.com/gin-gonic/gin").
        project_root_for_go_mod: The absolute path to the project root directory
                                 that might contain a 'go.mod' file. This path
                                 is used as the current working directory for
                                 'go list' if a 'go.mod' is present, potentially
                                 helping to resolve module-local packages.
                                 If `None` or no `go.mod` is found, the current
                                 working directory of the script is used.

    Returns:
        A dictionary mapping successfully located Go package import paths
        to their absolute directory paths on disk. Packages that could not be
        found or resulted in an error are omitted.
    """
    package_locations: Dict[str, str] = {}
    if not package_paths:
        return package_locations

    if config.verbose:
        print("Locating Go packages...")

    go_list_cwd = project_root_for_go_mod if project_root_for_go_mod and os.path.exists(os.path.join(project_root_for_go_mod, 'go.mod')) else os.getcwd()

    go_executable = shutil.which("go")

    if not go_executable:
        print("Error: 'go' command not found in PATH. Please ensure Go is installed and its 'bin' directory is in your system's PATH environment variable.")
        if config.verbose:
            print("Skipping all Go package processing.")
        return {}

    go_cmd_path: str = go_executable

    try:
        version_check_cmd: List[str] = [go_cmd_path, "version"]
        version_check_result = subprocess.run(version_check_cmd, check=True, capture_output=True, text=True, cwd=go_list_cwd)
        if config.verbose:
             print(f"Go version found: {version_check_result.stdout.strip()}")
    except FileNotFoundError:
        print(f"Error: Could not run the Go command '{go_cmd_path}'. This is unexpected as shutil.which() found it. Ensure it's executable.")
        if config.verbose:
            print("Skipping all Go package processing.")
        return {}
    except subprocess.CalledProcessError as e:
        error_output = e.stderr.strip() if e.stderr else e.stdout.strip() if e.stdout else "(no output)"
        cmd_executed_str = _format_command_for_display(e.cmd)
        print(f"Error: The command '{cmd_executed_str}' failed. Error: {error_output}")
        print("Please ensure your Go installation is working correctly.")
        if config.verbose:
            print("Skipping all Go package processing.")
        return {}
    except Exception as e_version_check:
        print(f"Error: An unexpected error occurred while checking Go version with '{go_cmd_path}': {e_version_check}")
        if config.verbose:
            print("Skipping all Go package processing.")
        return {}

    for pkg_path in package_paths:
        if config.verbose:
            print(f"  Locating package: {pkg_path}")

        current_command_list: List[str] = [go_cmd_path, "list", "-f", "{{.Dir}}", pkg_path]

        try:
            result = subprocess.run(current_command_list, check=True, capture_output=True, text=True, encoding='utf-8', cwd=go_list_cwd)
            pkg_dir = result.stdout.strip()
            if not pkg_dir or not os.path.isdir(pkg_dir):
                print(f"    Warning: Could not find valid directory for package '{pkg_path}'. 'go list' returned: '{pkg_dir}'. Skipping.")
                continue
            if config.verbose:
                print(f"    Found at: {pkg_dir}")
            package_locations[pkg_path] = pkg_dir
        except subprocess.CalledProcessError as e_sub:
            error_output = e_sub.stderr.strip() if e_sub.stderr else "(no stderr)"
            cmd_that_failed_str = _format_command_for_display(e_sub.cmd)
            print(f"    Warning: '{cmd_that_failed_str}' failed for package '{pkg_path}'. Error: {error_output}")
        except Exception as e_gen:
            print(f"    Warning: An unexpected error occurred while locating package '{pkg_path}': {e_gen}")

    if not package_locations and config.verbose:
        print("No Go package locations were successfully found.")
    return package_locations


def get_go_package_content_files(config: CompilationConfig, package_locations: Dict[str, str]) -> List[Dict[str, str]]:
    """
    Collects .go source files from the specified Go package directories.

    This function walks through each directory provided in `package_locations`,
    identifies all `.go` files, and gathers their information. It skips
    directories named '.git' and files that appear to be binary.

    Args:
        config: The `CompilationConfig` object, used for `verbose` logging.
        package_locations: A dictionary mapping Go package import paths to their
                           absolute directory paths on disk (as returned by
                           `get_go_package_locations`).

    Returns:
        A list of dictionaries. Each dictionary represents a `.go` file and contains:
        -   'package': The original Go package import path.
        -   'relative_path': The file's path relative to its package root,
                             using forward slashes.
        -   'absolute_path': The absolute path to the `.go` file on disk.
        The list is sorted by package name and then by relative path.
    """
    package_content_files: List[Dict[str, str]] = []
    if config.verbose:
        print("Collecting Go package source files for compilation...")

    for pkg_path, pkg_dir in package_locations.items():
        if not pkg_dir or not os.path.isdir(pkg_dir):
            if config.verbose:
                print(f"  Skipping package '{pkg_path}' due to invalid directory: {pkg_dir}")
            continue
        if config.verbose:
            print(f"  Scanning package: {pkg_path} (in {pkg_dir})")

        for dirpath, _, filenames in os.walk(pkg_dir):
            if '.git' in dirpath.split(os.sep):
                continue
            for filename_str in filenames:
                if filename_str.lower().endswith(".go"):
                    file_abs_path = os.path.join(dirpath, filename_str)
                    if is_likely_binary(file_abs_path):
                        if config.verbose:
                            print(f"    Skipping likely binary file in package '{pkg_path}': {filename_str}")
                        continue
                    rel_path = os.path.relpath(file_abs_path, pkg_dir).replace(os.sep, '/')
                    package_content_files.append({
                        'package': pkg_path,
                        'relative_path': rel_path,
                        'absolute_path': file_abs_path
                    })

    package_content_files.sort(key=lambda x_file: (x_file['package'], x_file['relative_path']))
    if config.verbose:
        print(f"Found {len(package_content_files)} Go source files in packages for compilation.")
    return package_content_files