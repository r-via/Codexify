# codexify/core/file_system.py
import os
import fnmatch
import codecs  # <--- Ajout essentiel
from typing import Optional, Tuple, Set, List, Callable

GitignoreMatcher = Callable[[str], bool]
ParseGitignoreFuncType = Callable[[str, Optional[str]], GitignoreMatcher]


def load_gitignore(
    gitignore_file_abs_path: Optional[str],
    parse_gitignore_func: ParseGitignoreFuncType,
    base_dir_for_rules_interpretation: Optional[str],
) -> GitignoreMatcher:
    """
    Loads and parses a .gitignore file, returning a callable matcher function.
    """
    if gitignore_file_abs_path:
        if os.path.exists(gitignore_file_abs_path):
            try:
                rules_matcher: GitignoreMatcher = parse_gitignore_func(
                    gitignore_file_abs_path,
                    base_dir_for_rules_interpretation,
                )
                return lambda path_to_check: rules_matcher(
                    os.path.abspath(path_to_check)
                )
            except Exception as e:
                print(
                    f"Warning: Could not parse gitignore file '{gitignore_file_abs_path}': {e}"
                )
        else:
            print(f"Warning: gitignore file '{gitignore_file_abs_path}' not found.")
    return lambda path_to_check: False


def is_likely_binary(file_path: str) -> bool:
    """
    Checks if a file is likely binary.

    This implementation handles multi-byte characters (emojis, box-drawing chars)
    correctly even if they are split at the chunk boundary.

    Args:
        file_path: The path to the file to check.

    Returns:
        True if the file is likely binary or unreadable, False if it is valid text.
    """
    try:
        with open(file_path, "rb") as f:
            chunk = f.read(1024)

        if not chunk:
            return False

        # 1. Null byte detection (standard for binary files)
        if b'\x00' in chunk:
            return True

        # 2. Incremental UTF-8 Decoding
        # Instead of chunk.decode('utf-8'), which fails if a character is cut
        # in half at the end of the 1024 bytes (common with emojis/diagrams),
        # we use an incremental decoder.
        # final=False tells the decoder: "If the end is incomplete, wait, don't crash."
        decoder = codecs.getincrementaldecoder("utf-8")(errors="strict")
        try:
            decoder.decode(chunk, final=False)
            return False
        except UnicodeDecodeError:
            # Real decoding error found in the middle of the chunk -> Binary
            return True

    except Exception:
        # IO errors or other issues -> Treat as binary to be safe
        return True


def get_parent_folder_name(path_str: Optional[str]) -> Optional[str]:
    """
    Extracts the name of the immediate parent folder from a given path string.
    """
    if not path_str:
        return None
    try:
        abs_path = os.path.abspath(path_str)
        if os.path.isdir(abs_path):
            return os.path.basename(abs_path)
        else:
            return os.path.basename(os.path.dirname(abs_path))
    except Exception:
        return None


def count_contents(start_path: str, permanent_exclusions: Set[str]) -> Tuple[int, int]:
    """
    Counts subdirectories and files under a path, respecting permanent exclusions.
    """
    dir_count: int = 0
    file_count: int = 0

    try:
        for _, dirnames, filenames in os.walk(start_path, topdown=True):
            dirs_to_traverse: List[str] = []
            for d_name in dirnames:
                if d_name in permanent_exclusions or any(
                    fnmatch.fnmatch(d_name, pat)
                    for pat in permanent_exclusions
                    if "*" in pat or "?" in pat
                ):
                    continue
                dirs_to_traverse.append(d_name)

            dir_count += len(dirs_to_traverse)
            dirnames[:] = dirs_to_traverse

            for f_name in filenames:
                if f_name in permanent_exclusions or any(
                    fnmatch.fnmatch(f_name, pat)
                    for pat in permanent_exclusions
                    if "*" in pat or "?" in pat
                ):
                    continue
                file_count += 1
    except Exception:
        pass

    return dir_count, file_count