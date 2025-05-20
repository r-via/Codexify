import os
import fnmatch
from typing import Optional, Callable, Tuple, Set

def load_gitignore(gitignore_path: Optional[str], parse_gitignore_func: Callable) -> Callable[[str], bool]:
    """Loads and parses a .gitignore file, returning a callable matcher."""
    if gitignore_path:
        abs_gitignore_path = os.path.abspath(gitignore_path)
        if os.path.exists(abs_gitignore_path):
            if callable(parse_gitignore_func):
                 try:
                     ignore_dir = os.path.dirname(abs_gitignore_path)
                     rules = parse_gitignore_func(abs_gitignore_path, base_dir=ignore_dir)
                     return lambda p: rules(os.path.abspath(p))
                 except Exception as e:
                     print(f"Warning: Could not parse gitignore '{gitignore_path}': {e}")
            else:
                print(f"Warning: gitignore parser unavailable (parse_gitignore_func not provided or callable).")
        else:
            print(f"Warning: gitignore file '{gitignore_path}' not found.")
    return lambda p: False


def is_likely_binary(file_path: str) -> bool:
    """Checks if a file is likely binary by looking for null bytes or UTF-8 decode errors."""
    try:
        with open(file_path, 'rb') as f: chunk = f.read(1024)
        if b'\x00' in chunk: return True
        chunk.decode('utf-8', errors='strict'); return False
    except UnicodeDecodeError: return True
    except Exception: return True


def get_parent_folder_name(path_str: Optional[str]) -> Optional[str]:
    """Extracts the parent folder name from a given path string."""
    if not path_str: return None
    try:
        abs_path = os.path.abspath(path_str)
        return os.path.basename(abs_path) if os.path.isdir(abs_path) else os.path.basename(os.path.dirname(abs_path))
    except Exception as e: print(f"Warning: Could not determine parent folder for '{str(path_str)}': {e}"); return None


def count_contents(start_path: str, permanent_exclusions: Set[str]) -> Tuple[int, int]:
    """Counts directories and files under a path, respecting permanent exclusions."""
    dir_count = 0; file_count = 0
    perm_exclude_set = set(permanent_exclusions)
    try:
        for _, dirnames, filenames in os.walk(start_path, topdown=True):
            dirnames[:] = [d for d in dirnames if d not in perm_exclude_set]
            dir_count += len(dirnames)
            valid_filenames = [f for f in filenames if not any(fnmatch.fnmatch(f, pat) for pat in perm_exclude_set) and f not in perm_exclude_set]
            file_count += len(valid_filenames)
    except OSError as e: print(f"Warning: Could not count contents of '{start_path}': {e}")
    return dir_count, file_count