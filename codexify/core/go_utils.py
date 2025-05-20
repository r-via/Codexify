import os
import subprocess
from typing import List, Dict, Optional

from .file_system import is_likely_binary

def get_go_package_locations(package_paths: List[str], project_root_for_go_mod: Optional[str]) -> Dict[str, str]:
    """Uses 'go list' to find the disk locations of Go packages."""
    package_locations: Dict[str, str] = {}
    if not package_paths: return package_locations
    print("Locating Go packages...")
    go_list_cwd = project_root_for_go_mod if project_root_for_go_mod and os.path.exists(os.path.join(project_root_for_go_mod, 'go.mod')) else None
    go_cmd_path = "go"

    try: subprocess.run([go_cmd_path, "version"], check=True, capture_output=True, text=True, cwd=go_list_cwd)
    except (FileNotFoundError, subprocess.CalledProcessError) as e:
        print(f"Error: Could not run the '{go_cmd_path}' command. Is Go installed and in your PATH? ({e})\nSkipping all Go package processing."); return {}

    for pkg_path in package_paths:
        print(f"  Locating package: {pkg_path}")
        try:
            cmd = [go_cmd_path, "list", "-f", "{{.Dir}}", pkg_path]
            result = subprocess.run(cmd, check=True, capture_output=True, text=True, encoding='utf-8', cwd=go_list_cwd)
            pkg_dir = result.stdout.strip()
            if not pkg_dir or not os.path.isdir(pkg_dir):
                print(f"    Warning: Could not find valid directory for package '{pkg_path}'. 'go list' returned: '{pkg_dir}'. Skipping."); continue
            print(f"    Found at: {pkg_dir}"); package_locations[pkg_path] = pkg_dir
        except subprocess.CalledProcessError as e_sub: print(f"    Warning: 'go list' failed for '{pkg_path}'. Error: {e_sub.stderr.strip() if e_sub.stderr else '(no stderr)'}")
        except Exception as e_gen: print(f"    Warning: An unexpected error occurred while locating package '{pkg_path}': {e_gen}")

    if not package_locations: print("No Go package locations were successfully found.")
    return package_locations


def get_go_package_content_files(package_locations: Dict[str, str]) -> List[Dict[str, str]]:
    """Collects .go source files from the located Go packages."""
    package_content_files: List[Dict[str, str]] = []
    print("Collecting Go package source files for compilation...")
    for pkg_path, pkg_dir in package_locations.items():
        if not pkg_dir or not os.path.isdir(pkg_dir):
            print(f"  Skipping package '{pkg_path}' due to invalid directory: {pkg_dir}"); continue
        print(f"  Scanning package: {pkg_path} (in {pkg_dir})")
        for dirpath, _, filenames in os.walk(pkg_dir):
            if '.git' in dirpath.split(os.sep): continue
            for filename_str in filenames:
                if filename_str.lower().endswith(".go"):
                    file_abs_path = os.path.join(dirpath, filename_str)
                    if is_likely_binary(file_abs_path):
                        print(f"    Skipping likely binary file in package '{pkg_path}': {filename_str}"); continue
                    rel_path = os.path.relpath(file_abs_path, pkg_dir).replace(os.sep, '/')
                    package_content_files.append({'package': pkg_path, 'relative_path': rel_path, 'absolute_path': file_abs_path})
    package_content_files.sort(key=lambda x_file: (x_file['package'], x_file['relative_path']))
    print(f"Found {len(package_content_files)} Go source files in packages for compilation.")
    return package_content_files