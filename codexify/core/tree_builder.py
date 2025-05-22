# File: codexify/core/tree_builder.py
import os
import fnmatch
from typing import List, Dict, Optional, Set, Any, Tuple, Union, cast

from .file_system import (
    load_gitignore,
    count_contents,
    ParseGitignoreFuncType,
    GitignoreMatcher,
)

TreeDict = Dict[str, Any]
FileEntry = Dict[str, Union[str, bool]]


def build_filtered_file_list(
    root: str,  # This is the current scan root (e.g., project_path or Go package dir)
    extensions: List[str],
    exclude_dirs: List[str],
    exclude_files: List[str],
    gitignore_file_abs_path: Optional[str],  # Expecting absolute path from CLI/main
    parse_gitignore_func: ParseGitignoreFuncType,
    permanent_exclusions: Set[str],
    config_pattern_yaml_local: str,
) -> List[str]:
    """
    Builds a sorted list of relative file paths to be included for content compilation.
    # ... (docstring as before) ...
    Args:
        root: The absolute or relative path to the root directory to scan.
        extensions: A list of file "extensions" or names (e.g., [".py", "Makefile"]) to include.
        # ...
        gitignore_file_abs_path: Absolute path to a .gitignore file to use.
        # ...
    """
    exact_match_patterns: Set[str] = set()
    suffix_match_patterns: Set[str] = set()

    for ext_input in extensions:
        ext_lower = ext_input.lower()
        if ext_lower.startswith("."):
            suffix_match_patterns.add(ext_lower)
        elif "." not in ext_lower:
            exact_match_patterns.add(ext_lower)
            suffix_match_patterns.add("." + ext_lower)
        else:
            exact_match_patterns.add(ext_lower)

    file_list: List[str] = []
    abs_root = os.path.abspath(root)  # Key: base for rule interpretation

    # MODIFICATION: gitignore_file_abs_path is passed directly.
    # base_dir_for_rules_interpretation is abs_root.
    ignore_matcher: GitignoreMatcher = load_gitignore(
        gitignore_file_abs_path,  # Already absolute
        parse_gitignore_func,
        abs_root,  # Rules in the gitignore are interpreted relative to this scan root
    )

    exclude_dirs_set: Set[str] = set(exclude_dirs)
    exclude_files_set: Set[str] = set(exclude_files)
    perm_exclude_set: Set[str] = permanent_exclusions

    for dirpath, dirnames, filenames in os.walk(abs_root, topdown=True):
        # ... (rest of the function remains the same as your "production ready" version)
        abs_dirpath = os.path.abspath(dirpath)

        original_dirnames = list(dirnames)
        dirnames[:] = []
        for d_name in original_dirnames:
            if d_name in perm_exclude_set:
                continue
            if d_name in exclude_dirs_set:
                continue
            abs_subdir_path = os.path.join(abs_dirpath, d_name)
            if ignore_matcher(abs_subdir_path):
                continue
            dirnames.append(d_name)

        rel_dirpath = os.path.relpath(abs_dirpath, abs_root)

        for filename_str in filenames:
            if filename_str in perm_exclude_set or any(
                fnmatch.fnmatch(filename_str, pat)
                for pat in perm_exclude_set
                if "*" in pat or "?" in pat
            ):
                continue
            if fnmatch.fnmatch(filename_str, config_pattern_yaml_local):
                continue
            if filename_str in exclude_files_set:
                continue

            full_path = os.path.join(abs_dirpath, filename_str)
            if ignore_matcher(full_path):
                continue

            fn_lower = filename_str.lower()
            matched = False
            if fn_lower in exact_match_patterns:
                matched = True
            if not matched and any(
                fn_lower.endswith(s_ext) for s_ext in suffix_match_patterns
            ):
                matched = True

            if matched:
                rel_path_intermediate = (
                    os.path.join(rel_dirpath, filename_str)
                    if rel_dirpath != "."
                    else filename_str
                )
                rel_path_normalized = rel_path_intermediate.replace(os.sep, "/")
                file_list.append(rel_path_normalized)
    file_list.sort()
    return file_list


def build_tree_structure(
    root: str,  # This is the current scan root
    use_gitignore: bool,  # Still useful to conditionally apply gitignore logic
    gitignore_file_abs_path: Optional[str],  # Expecting absolute path from CLI/main
    parse_gitignore_func: ParseGitignoreFuncType,
    permanent_exclusions: Set[str],
    user_exclude_dirs: List[str],
    user_exclude_files: List[str],
    extensions_for_content: List[str],
) -> TreeDict:
    """
    Builds a nested dictionary representing the directory tree structure.
    # ... (docstring as before) ...
    Args:
        root: The absolute path to the root directory for building the tree.
        use_gitignore: Whether to apply .gitignore rules (even if path is provided).
        gitignore_file_abs_path: Absolute path to a .gitignore file.
        # ...
    """
    tree: TreeDict = {}
    abs_root = os.path.abspath(root)  # Key: base for rule interpretation

    ignore_matcher: GitignoreMatcher = lambda _p: False
    if (
        use_gitignore and gitignore_file_abs_path
    ):  # Only load if path is given and we want to use it
        # MODIFICATION: gitignore_file_abs_path is passed directly.
        # base_dir_for_rules_interpretation is abs_root.
        ignore_matcher = load_gitignore(
            gitignore_file_abs_path,  # Already absolute
            parse_gitignore_func,
            abs_root,  # Rules in the gitignore are interpreted relative to this scan root
        )

    perm_exclude_set: Set[str] = permanent_exclusions
    # ... (rest of the function remains the same as your "production ready" version) ...
    user_exclude_dirs_set: Set[str] = set(user_exclude_dirs)
    user_exclude_files_set: Set[str] = set(user_exclude_files)

    exact_match_patterns_for_content: Set[str] = set()
    suffix_match_patterns_for_content: Set[str] = set()

    if extensions_for_content:
        for ext_input in extensions_for_content:
            ext_lower = ext_input.lower()
            if ext_lower.startswith("."):
                suffix_match_patterns_for_content.add(ext_lower)
            elif "." not in ext_lower:
                exact_match_patterns_for_content.add(ext_lower)
                suffix_match_patterns_for_content.add("." + ext_lower)
            else:
                exact_match_patterns_for_content.add(ext_lower)

    excluded_counts_cache: Dict[str, Tuple[int, int]] = {}

    for dirpath, dirnames, filenames in os.walk(abs_root, topdown=True):
        abs_dirpath = os.path.abspath(dirpath)
        rel_dirpath = os.path.relpath(abs_dirpath, abs_root)

        path_parts = abs_dirpath.split(os.sep)
        # Ensure we don't descend into permanently excluded paths beyond the root itself
        # Example: if abs_root is /a/b and perm_exclude has '.git', then /a/b/.git is fine for this check
        # but /a/b/c/.git would make the `any` condition true if '.git' is in path_parts[2:]
        is_in_perm_excluded_subpath = False
        if abs_dirpath != abs_root:  # Only check subpaths, not the root itself
            # Construct path parts relative to abs_root to check for permanent exclusions
            # in the sub-path components.
            # Example: abs_root = /foo, dirpath = /foo/bar/.git
            # rel_dirpath_parts = ['bar', '.git'] -> check if 'bar' or '.git' are perm excluded
            # This logic seems more complex than needed if perm_exclude are just names.
            # The original simple check on d_name and filename_str later is usually sufficient
            # if perm_exclude are names like '.git', not paths like 'some/sub/.git'
            # For now, let's stick to the simpler check on d_name and filename_str later.
            # The original check was:
            # if any(part in perm_exclude_set for part in path_parts if os.path.join(*path_parts[:path_parts.index(part)+1]) != abs_root and part != '.'):
            # This check is a bit convoluted. A simpler approach is to check `d_name` before adding to `dirnames[:]`.
            pass

        current_level_node: TreeDict = tree
        if rel_dirpath != ".":
            parts = rel_dirpath.split(os.sep)
            path_is_valid = True
            for part_idx, part in enumerate(parts):
                child_node_any = current_level_node.get(part)

                if not isinstance(child_node_any, dict):
                    is_parent_excluded = False
                    temp_node_check: TreeDict = tree
                    for p_check in parts[: part_idx + 1]:
                        node_val_any = temp_node_check.get(p_check)
                        if isinstance(node_val_any, dict):
                            node_val_as_treedict = cast(TreeDict, node_val_any)
                            if node_val_as_treedict.get("_excluded_dir"):
                                is_parent_excluded = True
                                break
                            temp_node_check = node_val_as_treedict
                        else:  # Path component not a dict, implies structure error or excluded parent
                            is_parent_excluded = True
                            break

                    if is_parent_excluded:
                        dirnames[:] = []
                        filenames[:] = []
                        path_is_valid = False
                        break

                    new_child_node: TreeDict = {}
                    current_level_node[part] = new_child_node
                    current_level_node = new_child_node
                else:
                    current_level_node = cast(TreeDict, child_node_any)

                if current_level_node.get("_excluded_dir"):
                    dirnames[:] = []
                    filenames[:] = []
                    path_is_valid = False
                    break
            if not path_is_valid:
                continue

        original_dirnames = list(
            dirnames
        )  # dirnames here are already filtered by os.walk's topdown=True if perm_exclude were in parent
        dirnames[:] = []  # Prepare to rebuild list of dirs to descend into
        for d_name in original_dirnames:
            if d_name in perm_exclude_set:  # Check for permanent exclusions by name
                continue

            abs_subdir_path = os.path.join(abs_dirpath, d_name)
            is_user_dir_excluded_explicitly = d_name in user_exclude_dirs_set
            is_dir_ignored_by_git: bool = use_gitignore and ignore_matcher(
                abs_subdir_path
            )  # ignore_matcher is pre-configured

            if is_user_dir_excluded_explicitly or is_dir_ignored_by_git:
                if abs_subdir_path not in excluded_counts_cache:
                    d_count, f_count = count_contents(abs_subdir_path, perm_exclude_set)
                    excluded_counts_cache[abs_subdir_path] = (d_count, f_count)
                else:
                    d_count, f_count = excluded_counts_cache[abs_subdir_path]
                current_level_node[d_name] = {"_excluded_dir": True, "_dir_count": d_count, "_file_count": f_count, "_files": []}  # type: ignore
            else:
                current_level_node.setdefault(d_name, {})  # Ensure dir entry exists
                dirnames.append(d_name)  # Add to list of dirs to descend into

        node_files_list_any = current_level_node.get("_files")
        if node_files_list_any is None or not isinstance(node_files_list_any, list):
            files_in_node: List[FileEntry] = []
            current_level_node["_files"] = files_in_node  # type: ignore
        else:
            files_in_node = cast(List[FileEntry], node_files_list_any)

        for filename_str in filenames:
            if filename_str in perm_exclude_set or any(
                fnmatch.fnmatch(filename_str, pat)
                for pat in perm_exclude_set
                if "*" in pat or "?" in pat
            ):
                continue

            full_path = os.path.join(abs_dirpath, filename_str)
            is_content_omitted_by_user_rule = filename_str in user_exclude_files_set
            is_content_omitted_by_gitignore: bool = use_gitignore and ignore_matcher(
                full_path
            )

            is_content_omitted_by_extension_rule: bool = False
            if extensions_for_content:
                fn_lower = filename_str.lower()
                content_matched_by_extension = False
                if fn_lower in exact_match_patterns_for_content:
                    content_matched_by_extension = True
                if not content_matched_by_extension and any(
                    fn_lower.endswith(s_ext)
                    for s_ext in suffix_match_patterns_for_content
                ):
                    content_matched_by_extension = True

                if not content_matched_by_extension:
                    is_content_omitted_by_extension_rule = True

            is_content_omitted: bool = (
                is_content_omitted_by_user_rule
                or is_content_omitted_by_gitignore
                or is_content_omitted_by_extension_rule
            )
            files_in_node.append({"name": filename_str, "omitted": is_content_omitted})

        if files_in_node:
            files_in_node.sort(key=lambda file_entry: file_entry["name"])
        elif "_files" in current_level_node and not current_level_node.get(
            "_files"
        ):  # No files added
            current_level_node.pop("_files", None)  # Remove empty list
    return tree


# print_tree remains the same
def print_tree(
    tree: TreeDict,
    root_display_name: Optional[str] = None,
    indent: str = "",
    is_last_entry_in_parent: bool = True,
) -> List[str]:
    """
    Generates a list of strings representing the formatted directory tree.

    Args:
        tree: The TreeDict structure (nested dictionaries) to print.
        root_display_name: If provided, this name is printed as the root of the tree.
                           If None, the function assumes it's printing a sub-tree.
        indent: The string prefix for indentation of the current level.
        is_last_entry_in_parent: Flag indicating if the current tree/node being printed
                                 is the last child of its parent. Affects connectors.

    Returns:
        A list of strings, where each string is a line in the formatted tree.
    """
    lines: List[str] = []
    current_prefix = indent

    if root_display_name is not None:
        lines.append(root_display_name)
        current_prefix = ""

    dir_items: List[Tuple[str, TreeDict]] = []
    raw_files_any = tree.get(
        "_files", []
    )  # Default to empty list if _files is not present
    file_items_from_tree: List[FileEntry] = []

    if isinstance(raw_files_any, list):
        # Ensure items in the list are indeed FileEntry (dicts)
        for item_entry_any in raw_files_any:
            if isinstance(item_entry_any, dict):
                # Heuristic check for expected keys; adapt if FileEntry has mandatory keys
                if "name" in item_entry_any and "omitted" in item_entry_any:
                    file_items_from_tree.append(cast(FileEntry, item_entry_any))
                # else: log a warning or handle malformed FileEntry if necessary

    for key, value_any in tree.items():
        if key == "_files":
            continue  # Handled above
        if isinstance(value_any, dict):  # It's a subdirectory node
            value_as_treedict: TreeDict = cast(TreeDict, value_any)
            dir_items.append((key, value_as_treedict))

    # Sort directories first, then files, keeping original sorting for files by name
    dir_items.sort(
        key=lambda item_lambda: (
            bool(item_lambda[1].get("_excluded_dir")),
            item_lambda[0].lower(),
        )
    )
    # file_items_from_tree are already sorted by name if populated by build_tree_structure

    all_entries_count = len(dir_items) + len(file_items_from_tree)
    entry_index = 0

    for dir_name, dir_content_node in dir_items:
        entry_index += 1
        is_last = (
            entry_index == all_entries_count
        ) and not file_items_from_tree  # Last dir AND no files follow
        connector = "└── " if is_last else "├── "
        if dir_content_node.get("_excluded_dir"):
            dir_count_val = dir_content_node.get("_dir_count", 0)
            file_count_val = dir_content_node.get("_file_count", 0)
            # Ensure these are ints for formatting
            dir_count = (
                int(dir_count_val) if isinstance(dir_count_val, (int, float)) else 0
            )
            file_count = (
                int(file_count_val) if isinstance(file_count_val, (int, float)) else 0
            )
            lines.append(
                f"{current_prefix}{connector}{dir_name}/ [Content Omitted: Dirs: {dir_count}, Files: {file_count}]"
            )
        else:
            lines.append(f"{current_prefix}{connector}{dir_name}/")
            child_indent = current_prefix + ("    " if is_last else "│   ")
            # Recursively print the subtree
            lines.extend(
                print_tree(
                    dir_content_node,
                    root_display_name=None,
                    indent=child_indent,
                    is_last_entry_in_parent=is_last,
                )
            )

    for file_data in file_items_from_tree:
        entry_index += 1
        is_last = entry_index == all_entries_count
        connector = "└── " if is_last else "├── "
        filename_str = file_data.get("name", "UnknownFile")
        omitted_flag = file_data.get(
            "omitted", True
        )  # Default to omitted if flag is missing
        omitted_suffix = " [Content Omitted]" if omitted_flag else ""
        lines.append(f"{current_prefix}{connector}{filename_str}{omitted_suffix}")
    return lines
