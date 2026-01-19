# codexify/main.py
# ------------------------------------------------------------
from typing import List, Optional, Dict, Any, Callable, Set, Tuple
import os
import shutil
import tiktoken
from gitignore_parser import parse_gitignore

from .types import CompilationConfig, CompilationResult
from .core.common import BASE_PERMANENT_EXCLUSIONS, CONFIG_FILE_PATTERN
from .core.go_utils import get_go_package_locations, get_go_package_content_files
from .core.tree_builder import (
    build_tree_structure,
    print_tree,
    build_filtered_file_list,
    TreeDict,
)
from .core.content_compiler import assemble_compiled_content


def generate_compiled_output(config: CompilationConfig) -> CompilationResult:
    """
    Generates compiled output based on the provided configuration.

    This function orchestrates the entire compilation process:
    1. Initializes necessary modules (tiktoken, gitignore parser).
    2. Sets up permanent exclusions.
    3. Iterates over all provided `project_paths`:
        - Builds a directory tree structure for each path.
        - Filters files based on extensions and rules.
        - Collects tree representations and file lists.
    4. Processes Go packages if specified:
        - Locates packages on disk.
        - Builds trees and gathers source files.
    5. Assembles the final compiled text.
    6. Calculates token counts.
    7. Writes to disk if an output path is configured.

    Args:
        config: A `CompilationConfig` object containing all parameters.

    Returns:
        A `CompilationResult` object containing the outcome (success, text, stats).
    """
    if config.verbose:
        print("--- Starting Compilation Process (Programmatic Call) ---")

    # 1. Module Initialization
    # If modules are not injected via config, rely on global imports.
    effective_tiktoken_mod: Any = config.tiktoken_module or tiktoken
    effective_parse_git_func: Callable[
        [str, Optional[str]], Callable[[str], bool]
    ] = (config.parse_gitignore_func or parse_gitignore)

    # 2. Exclusions Setup
    path_perm_excludes: Set[str] = BASE_PERMANENT_EXCLUSIONS.union(
        config.additional_path_permanent_exclusions
    )
    path_perm_excludes.add(CONFIG_FILE_PATTERN)
    go_perm_excludes: Set[str] = BASE_PERMANENT_EXCLUSIONS.union(
        config.additional_go_permanent_exclusions
    )

    # 3. Process Local Project Paths (Multi-path support)
    # Stores tuples of (absolute_root, tree_lines_list, filtered_files_list)
    all_paths_data: List[Tuple[str, List[str], List[str]]] = []

    if config.project_paths:
        for p_path in config.project_paths:
            root_abs_path = os.path.abspath(p_path)

            if not os.path.isdir(root_abs_path):
                print(
                    f"Warning: Project path '{p_path}' is not a valid directory. Skipping."
                )
                continue

            if config.verbose:
                print(f"\n--- Processing Directory: {root_abs_path} ---")
                print(
                    f"Permanently excluding: {', '.join(sorted(list(path_perm_excludes)))}"
                )

            # Build Tree Structure
            path_tree: TreeDict = build_tree_structure(
                root_abs_path,
                True,  # use_gitignore
                config.gitignore_file_path,
                effective_parse_git_func,
                path_perm_excludes,
                config.exclude_dirs,
                config.exclude_files,
                config.extensions,
                config.search_keywords,
            )

            # Build Filtered File List (relative paths)
            filtered_files = build_filtered_file_list(
                root_abs_path,
                config.extensions,
                config.exclude_dirs,
                config.exclude_files,
                config.gitignore_file_path,
                effective_parse_git_func,
                path_perm_excludes,
                CONFIG_FILE_PATTERN,
                config.search_keywords,
            )

            # Generate Tree String Representation
            root_dir_name = (
                os.path.basename(root_abs_path)
                if root_abs_path != "."
                else "current_directory"
            )
            tree_lines = print_tree(path_tree, root_display_name=root_dir_name)

            all_paths_data.append((root_abs_path, tree_lines, filtered_files))
            
    elif config.verbose and not config.go_packages:
        print("\n--- No project_paths specified. ---")

    # 4. Process Go Packages
    package_tree_lines_map: Dict[str, List[str]] = {}
    package_content_files: List[Dict[str, str]] = []
    package_trees_map: Dict[str, TreeDict] = {}

    if config.go_packages:
        if config.verbose:
            print(f"\n--- Processing Go Packages: {config.go_packages} ---")

        # Logic to find 'go.mod' to help 'go list' context.
        # We use the first valid project path as a hint, or CWD.
        search_start_dir = os.getcwd()
        if config.project_paths:
            for p in config.project_paths:
                if os.path.isdir(p):
                    search_start_dir = os.path.abspath(p)
                    break

        def find_go_mod_root(start_path: str) -> Optional[str]:
            current_path = os.path.abspath(start_path)
            while True:
                if os.path.exists(os.path.join(current_path, "go.mod")):
                    return current_path
                parent_path = os.path.dirname(current_path)
                if parent_path == current_path:
                    return None
                current_path = parent_path

        go_list_execution_dir = find_go_mod_root(search_start_dir)
        if not go_list_execution_dir:
            # Fallback to search_start_dir if no go.mod found up the tree
            go_list_execution_dir = search_start_dir
            if config.verbose:
                print(
                    f"Warning: 'go.mod' not found. Using '{go_list_execution_dir}' context for Go resolution."
                )
        elif config.verbose:
            print(f"Using Go module root: {go_list_execution_dir}")

        package_locations = get_go_package_locations(
            config, config.go_packages, go_list_execution_dir
        )

        if package_locations:
            for pkg_path, pkg_dir in package_locations.items():
                if config.verbose:
                    print(f"Building tree for package: {pkg_path}")
                
                # Build package tree (only showing .go files usually)
                pkg_tree: TreeDict = build_tree_structure(
                    pkg_dir,
                    False,  # No gitignore for installed packages usually
                    None,
                    effective_parse_git_func,
                    go_perm_excludes,
                    [],
                    [],
                    [".go"],
                    config.search_keywords,
                )
                package_trees_map[pkg_path] = pkg_tree
                package_tree_lines_map[pkg_path] = print_tree(
                    pkg_tree, root_display_name=f"package:{pkg_path}"
                )
            
            package_content_files = get_go_package_content_files(
                config, package_locations
            )
        elif config.verbose:
            print("No Go package locations found or 'go' command failed.")

    # 5. Assemble Compiled Content
    compiled_text, files_compiled, files_skipped = assemble_compiled_content(
        config,
        all_paths_data,  # Pass the list of processed path data
        package_tree_lines_map,
        package_content_files,
        package_trees_map,
        path_perm_excludes,
        go_perm_excludes,
    )

    # 6. Calculate Token Count
    token_count_val = 0
    if effective_tiktoken_mod:
        try:
            encoding = effective_tiktoken_mod.get_encoding("cl100k_base")
            token_count_val = len(encoding.encode(compiled_text, allowed_special="all"))
        except Exception as e_token:
            if config.verbose:
                print(f"\nWarning: Token counting failed: {e_token}")
            if isinstance(e_token, ImportError):
                print("Ensure 'tiktoken' is installed for token estimation.")

    # 7. Write Output to File
    output_file_written_path = None
    if config.output_file_path:
        try:
            abs_output_path = os.path.abspath(config.output_file_path)
            os.makedirs(os.path.dirname(abs_output_path), exist_ok=True)
            with open(abs_output_path, "w", encoding="utf-8") as outfile:
                outfile.write(compiled_text)
            output_file_written_path = abs_output_path
            if config.verbose:
                print(f"Output successfully written to: {abs_output_path}")
        except IOError as e_io:
            return CompilationResult(
                success=False,
                error_message=f"Failed to write output file: {e_io}",
            )
        except Exception as e_gen:
            return CompilationResult(
                success=False,
                error_message=f"Unexpected error writing file: {e_gen}",
            )

    return CompilationResult(
        success=True,
        compiled_text=compiled_text,
        token_count=token_count_val,
        files_compiled_count=files_compiled,
        files_skipped_count=files_skipped,
        output_file_path=output_file_written_path,
    )