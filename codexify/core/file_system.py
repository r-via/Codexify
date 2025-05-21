# File: codexify/core/file_system.py
# ------------------------------------------------------------
import os
import fnmatch
from typing import Optional, Tuple, Set, List

from .dependencies import ParseGitignoreFuncType, GitignoreMatcher

def load_gitignore(
    gitignore_path: Optional[str],
    parse_gitignore_func: ParseGitignoreFuncType,
    base_dir_for_rules: Optional[str]
) -> GitignoreMatcher:
    """
    Loads and parses a .gitignore file, returning a callable matcher function.

    If `gitignore_path` is provided and exists, it's parsed using `parse_gitignore_func`.
    The `base_dir_for_rules` specifies the directory context for interpreting
    gitignore rules (e.g., a rule like `/foo` should match `foo` in that base directory).
    If `base_dir_for_rules` is None, the directory of the gitignore_path itself is used.
    The returned matcher takes an absolute path and returns True if it should be ignored.

    Args:
        gitignore_path: Absolute or relative path to the .gitignore file.
        parse_gitignore_func: The function to parse the gitignore file
                              (e.g., from the `gitignore_parser` library).
        base_dir_for_rules: The directory relative to which gitignore rules are applied.
                            If None, it defaults to the directory of the gitignore_path.

    Returns:
        A function that takes a file path (string) and returns True if
        the path matches any ignore rule, False otherwise. If no gitignore
        file is loaded, it returns a function that always returns False.
    """
    if gitignore_path:
        abs_gitignore_path = os.path.abspath(gitignore_path)
        if os.path.exists(abs_gitignore_path):
            try:
                effective_base_dir = base_dir_for_rules or os.path.dirname(abs_gitignore_path)
                
                rules_matcher: GitignoreMatcher = parse_gitignore_func(
                    abs_gitignore_path,
                    effective_base_dir
                )
                
                return lambda path_to_check: rules_matcher(os.path.abspath(path_to_check))
            except Exception as e:
                print(f"Warning: Could not parse gitignore file '{gitignore_path}': {e}")
        else:
            print(f"Warning: gitignore file '{gitignore_path}' not found.")
    return lambda path_to_check: False # Default: ignore nothing


def is_likely_binary(file_path: str) -> bool:
    """
    Checks if a file is likely a binary file.

    It reads a small chunk of the file and checks for null bytes or
    decoding errors with UTF-8, which are common indicators of binary files.

    Args:
        file_path: The path to the file to check.

    Returns:
        True if the file is likely binary, False otherwise.
    """
    try:
        with open(file_path, 'rb') as f:
            chunk = f.read(1024) # Read the first 1KB
        # If null bytes are present, it's very likely a binary file.
        if b'\x00' in chunk:
            return True
        # Try to decode as UTF-8. If it fails, it's likely binary.
        chunk.decode('utf-8', errors='strict')
        return False # Decoded successfully, likely text
    except UnicodeDecodeError:
        return True # Failed to decode, likely binary
    except Exception:
        # Any other error (e.g., file not found, permission denied)
        # can be treated as "likely binary" to be safe and avoid processing.
        return True


def get_parent_folder_name(path_str: Optional[str]) -> Optional[str]:
    """
    Extracts the name of the immediate parent folder from a given path string.

    If the path is a directory, its own name is returned. If it's a file,
    the name of the directory containing it is returned.

    Args:
        path_str: The file or directory path string.

    Returns:
        The name of the parent folder, or None if the path is None, empty,
        or an error occurs.
    """
    if not path_str:
        return None
    try:
        abs_path = os.path.abspath(path_str)
        if os.path.isdir(abs_path):
            return os.path.basename(abs_path)
        else: # It's a file or does not exist, try to get dirname
            return os.path.basename(os.path.dirname(abs_path))
    except Exception as e:
        # Log a warning or handle as appropriate for your application
        print(f"Warning: Could not determine parent folder name for '{str(path_str)}': {e}")
        return None


def count_contents(start_path: str, permanent_exclusions: Set[str]) -> Tuple[int, int]:
    """
    Counts the number of subdirectories and files under a given path,
    respecting permanent exclusions.

    This function is used to report statistics for directories whose
    content is omitted from the main tree display. It traverses
    the directory structure similarly to how the tree builder might,
    but only counts items not matching `permanent_exclusions`.

    Args:
        start_path: The absolute path to the directory to start counting from.
        permanent_exclusions: A set of directory or file names/patterns
                              that should always be excluded from the count.

    Returns:
        A tuple (dir_count, file_count) representing the number of
        non-excluded subdirectories and files found.
    """
    dir_count: int = 0
    file_count: int = 0
    perm_exclude_set_str: Set[str] = permanent_exclusions

    try:
        for _, dirnames, filenames in os.walk(start_path, topdown=True):
            # Filter dirnames based on permanent_exclusions before further traversal
            dirs_to_traverse: List[str] = []
            for d_name in dirnames:
                if d_name not in perm_exclude_set_str and \
                   not any(fnmatch.fnmatch(d_name, pat) for pat in perm_exclude_set_str if '*' in pat or '?' in pat):
                    dirs_to_traverse.append(d_name)
            
            dir_count += len(dirs_to_traverse) # Add to count *before* modifying dirnames for traversal
            dirnames[:] = dirs_to_traverse # Modify dirnames in place to control os.walk traversal

            # Count files in the current directory, respecting permanent_exclusions
            for f_name in filenames:
                if f_name not in perm_exclude_set_str and \
                   not any(fnmatch.fnmatch(f_name, pat) for pat in perm_exclude_set_str if '*' in pat or '?' in pat):
                    file_count += 1
    except OSError as e:
        # Log error if path is inaccessible, e.g., permission denied
        print(f"Warning: Could not count contents of '{start_path}' due to an OS error: {e}")
    except Exception as e_general:
        print(f"Warning: An unexpected error occurred while counting contents of '{start_path}': {e_general}")
        
    return dir_count, file_count