import os
import fnmatch
from typing import List, Dict, Optional, Callable, Set, Any, Tuple

from .file_system import load_gitignore, count_contents

def build_filtered_file_list(root: str, extensions: List[str], exclude_dirs: List[str], exclude_files: List[str], gitignore_path: Optional[str], parse_gitignore_func: Callable, permanent_exclusions: Set[str], config_pattern_yaml_local: str) -> List[str]:
    """Builds a list of files to be included for content compilation after applying all filters."""
    processed_extensions = [ext.lower() if ext.startswith('.') else '.' + ext.lower() for ext in extensions]
    file_list: List[str] = []
    ignore_matcher = load_gitignore(gitignore_path, parse_gitignore_func)
    abs_root = os.path.abspath(root)
    exclude_dirs_set = set(exclude_dirs)
    exclude_files_set = set(exclude_files)
    perm_exclude_set = set(permanent_exclusions)

    for dirpath, dirnames, filenames in os.walk(abs_root, topdown=True):
        abs_dirpath = os.path.abspath(dirpath)
        dirnames[:] = [d for d in dirnames if d not in perm_exclude_set and not ignore_matcher(os.path.join(abs_dirpath, d)) and d not in exclude_dirs_set]
        rel_dirpath = os.path.relpath(abs_dirpath, abs_root)

        for filename_str in filenames:
            is_perm_excluded_pattern = any(fnmatch.fnmatch(filename_str, pat) for pat in perm_exclude_set)
            is_perm_excluded_name = filename_str in perm_exclude_set
            if is_perm_excluded_pattern or is_perm_excluded_name: continue

            is_config_file = fnmatch.fnmatch(filename_str, config_pattern_yaml_local)
            if is_config_file: continue

            if any(part in perm_exclude_set for part in os.path.join(abs_dirpath, filename_str).split(os.sep)): continue
            if filename_str in exclude_files_set: continue

            full_path = os.path.join(abs_dirpath, filename_str)
            if ignore_matcher(full_path): continue

            if any(filename_str.lower().endswith(ext) for ext in processed_extensions):
                 rel_path = os.path.join(rel_dirpath, filename_str).replace(os.sep, '/') if rel_dirpath != '.' else filename_str
                 file_list.append(rel_path)
    file_list.sort(); return file_list


def build_tree_structure(root: str, use_gitignore: bool, gitignore_path: Optional[str], parse_gitignore_func: Callable, permanent_exclusions: Set[str], user_exclude_dirs: List[str], user_exclude_files: List[str], extensions_for_content: List[str]) -> Dict:
    """Builds a nested dictionary representing the directory tree structure with exclusion markers."""
    tree: Dict[str, Any] = {}
    abs_root = os.path.abspath(root)
    ignore_matcher = load_gitignore(gitignore_path, parse_gitignore_func) if use_gitignore else lambda p: False
    perm_exclude_set = set(permanent_exclusions) if permanent_exclusions is not None else set()
    user_exclude_dirs_set = set(user_exclude_dirs) if user_exclude_dirs else set()
    user_exclude_files_set = set(user_exclude_files) if user_exclude_files else set()
    content_extensions_set = set(ext.lower() if ext.startswith('.') else '.' + ext.lower() for ext in extensions_for_content) if extensions_for_content else set()
    excluded_counts_cache: Dict[str, Tuple[int, int]] = {}

    for dirpath, dirnames, filenames in os.walk(abs_root, topdown=True):
        abs_dirpath = os.path.abspath(dirpath)
        rel_dirpath = os.path.relpath(abs_dirpath, abs_root)

        if any(part in perm_exclude_set for part in abs_dirpath.split(os.sep)):
            dirnames[:] = []
            filenames[:] = []
            continue

        current_level: Dict[str, Any] = tree
        if rel_dirpath != '.':
            parts = rel_dirpath.split(os.sep)
            temp_level = tree
            try:
                for part in parts:
                    if isinstance(temp_level.get(part), dict) and temp_level[part].get("_excluded_dir"):
                         dirnames[:] = []
                         filenames[:] = []
                         raise StopIteration
                    if part not in temp_level: temp_level[part] = {}
                    temp_level = temp_level[part]
                current_level = temp_level
            except StopIteration:
                 continue

        original_dirnames = list(dirnames)
        dirnames[:] = []

        for d_name in original_dirnames:
            abs_subdir_path = os.path.join(abs_dirpath, d_name)
            if d_name in perm_exclude_set:
                continue

            is_user_dir_excluded = (d_name in user_exclude_dirs_set) or (use_gitignore and ignore_matcher(abs_subdir_path))
            if is_user_dir_excluded:
                if abs_subdir_path not in excluded_counts_cache:
                     d_count, f_count = count_contents(abs_subdir_path, perm_exclude_set)
                     excluded_counts_cache[abs_subdir_path] = (d_count, f_count)
                else:
                     d_count, f_count = excluded_counts_cache[abs_subdir_path]
                current_level[d_name] = {"_excluded_dir": True, "_dir_count": d_count, "_file_count": f_count}
            else:
                current_level.setdefault(d_name, {})
                dirnames.append(d_name)

        files_in_node: List[Dict[str, Any]] = current_level.setdefault("_files", [])
        for filename_str in filenames:
            is_perm_excluded_pattern = any(fnmatch.fnmatch(filename_str, pat) for pat in perm_exclude_set)
            is_perm_excluded_name = filename_str in perm_exclude_set
            if is_perm_excluded_pattern or is_perm_excluded_name:
                continue

            full_path = os.path.join(abs_dirpath, filename_str)
            is_content_excluded_by_user_or_git = (filename_str in user_exclude_files_set) or (use_gitignore and ignore_matcher(full_path))
            is_extension_match_for_content = any(filename_str.lower().endswith(ext) for ext in content_extensions_set) if content_extensions_set else True
            is_content_omitted = is_content_excluded_by_user_or_git or not is_extension_match_for_content
            files_in_node.append({'name': filename_str, 'omitted': is_content_omitted})

        if "_files" in current_level:
             current_level["_files"].sort(key=lambda x_file: x_file['name'])
             if not current_level["_files"]:
                  current_level.pop("_files", None)
    return tree


def print_tree(tree: Dict, root_display_name: Optional[str] = None, indent: str = "", is_last_entry: bool = True) -> List[str]:
    """Generates a list of strings representing the formatted directory tree."""
    lines: List[str] = []
    child_indent_prefix = indent
    if root_display_name is not None:
        lines.append(root_display_name); child_indent_prefix = ""

    excluded_dir_keys: List[str] = []
    normal_dir_keys: List[str] = []
    file_items: List[Dict[str, Any]] = tree.get("_files", [])

    for key, value in tree.items():
        if key == "_files": continue
        if isinstance(value, dict):
            if value.get("_excluded_dir"): excluded_dir_keys.append(key)
            else: normal_dir_keys.append(key)

    excluded_dir_keys.sort(); normal_dir_keys.sort()
    all_dir_keys = excluded_dir_keys + normal_dir_keys
    total_entries = len(all_dir_keys) + len(file_items); entry_counter = 0

    for key_str in excluded_dir_keys:
        entry_counter += 1; is_last = (entry_counter == total_entries)
        connector = "└── " if is_last else "├── "
        counts = tree[key_str]
        lines.append(f"{child_indent_prefix}{connector}{key_str}/ [Content Omitted: Dirs: {counts.get('_dir_count', 0)}, Files: {counts.get('_file_count', 0)}]")

    for key_str in normal_dir_keys:
        entry_counter += 1; is_last = (entry_counter == total_entries)
        connector = "└── " if is_last else "├── "
        lines.append(child_indent_prefix + connector + key_str + "/")
        child_indent = child_indent_prefix + ("    " if is_last else "│   ")
        lines.extend(print_tree(tree[key_str], root_display_name=None, indent=child_indent, is_last_entry=is_last))

    for file_data in file_items:
        entry_counter += 1; is_last = (entry_counter == total_entries)
        connector = "└── " if is_last else "├── "
        filename_str = file_data['name']
        suffix = " [Content Omitted]" if file_data['omitted'] else ""
        lines.append(child_indent_prefix + connector + filename_str + suffix)
    return lines