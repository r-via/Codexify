# File: codexify/main.py
# ------------------------------------------------------------
from typing import List, Optional, Dict, Any, Callable, Set
import os

from .types import CompilationConfig, CompilationResult

from .core.common import BASE_PERMANENT_EXCLUSIONS, CONFIG_FILE_PATTERN
from .core.dependencies import ensure_tiktoken_module, ensure_gitignore_parser_module
from .core.go_utils import get_go_package_locations, get_go_package_content_files
from .core.tree_builder import build_tree_structure, print_tree, build_filtered_file_list, TreeDict
from .core.content_compiler import assemble_compiled_content


def generate_compiled_output(config: CompilationConfig) -> CompilationResult:
    """
    Generates compiled output based on the provided configuration.

    This function orchestrates the entire compilation process:
    1. Initializes necessary modules (tiktoken, gitignore parser).
    2. Sets up permanent exclusions for path and Go package processing.
    3. If a project path is provided:
        - Builds a directory tree structure, respecting .gitignore and other exclusions.
        - Filters files based on specified extensions and exclusion rules.
        - Collects lines for the tree representation.
    4. If Go packages are specified:
        - Locates Go packages on disk using the `go` command-line tool.
        - Builds tree structures for each Go package, focusing on `.go` files.
        - Collects `.go` files for content compilation from these packages.
    5. Assembles the final compiled text, including all gathered tree representations
       and the content of the selected files from both the project path and Go packages.
    6. Calculates an estimated token count of the compiled text using the tiktoken
       library with the "cl100k_base" encoding.
    7. If an output file path is specified in the configuration, writes the compiled
       text to that file, creating parent directories if they do not exist.

    Args:
        config: A `CompilationConfig` object containing all parameters
                for the compilation.
    Returns:
        A `CompilationResult` object containing the outcome of the compilation.
    """
    if config.verbose:
        print("--- Starting Compilation Process (Programmatic Call) ---")

    tiktoken_mod: Any = config.tiktoken_module or ensure_tiktoken_module()

    parse_git_func: Callable[[str, Optional[str]], Callable[[str], bool]] = \
        config.parse_gitignore_func or ensure_gitignore_parser_module()

    path_perm_excludes: Set[str] = BASE_PERMANENT_EXCLUSIONS.union(config.additional_path_permanent_exclusions)
    path_perm_excludes.add(CONFIG_FILE_PATTERN)
    go_perm_excludes: Set[str] = BASE_PERMANENT_EXCLUSIONS.union(config.additional_go_permanent_exclusions)

    path_tree_lines: List[str] = []
    filtered_path_files: List[str] = []
    root_abs_path: Optional[str] = None

    if config.project_path:
        root_abs_path = os.path.abspath(config.project_path)
        if not os.path.isdir(root_abs_path):
            return CompilationResult(success=False, error_message=f"Project path '{config.project_path}' is not a valid directory.")
        if config.verbose:
            print(f"\n--- Processing Directory: {root_abs_path} ---")
            print(f"Permanently excluding from path processing: {', '.join(sorted(list(path_perm_excludes)))}")

        path_tree: TreeDict = build_tree_structure(
            root_abs_path, True, config.gitignore_file_path, parse_git_func,
            path_perm_excludes, config.exclude_dirs, config.exclude_files, config.extensions
        )
        filtered_path_files = build_filtered_file_list(
            root_abs_path, config.extensions, config.exclude_dirs, config.exclude_files,
            config.gitignore_file_path, parse_git_func, path_perm_excludes, CONFIG_FILE_PATTERN
        )
        root_dir_name = os.path.basename(root_abs_path) if root_abs_path != '.' else 'current_directory'
        path_tree_lines = print_tree(path_tree, root_display_name=root_dir_name)
    elif config.verbose:
         print("\n--- No project_path specified, skipping local directory processing. ---")

    package_tree_lines_map: Dict[str, List[str]] = {}
    package_content_files: List[Dict[str, str]] = []
    package_trees_map: Dict[str, TreeDict] = {}

    if config.go_packages:
        if config.verbose:
            print(f"\n--- Processing Go Packages: {config.go_packages} ---")
            print(f"Permanently excluding from Go package processing: {', '.join(sorted(list(go_perm_excludes)))}")

        project_root_for_go_mod = root_abs_path if root_abs_path and os.path.exists(os.path.join(root_abs_path, 'go.mod')) else os.getcwd()
        package_locations = get_go_package_locations(config, config.go_packages, project_root_for_go_mod)

        if package_locations:
            for pkg_path, pkg_dir in package_locations.items():
                if config.verbose: print(f"Building tree for package: {pkg_path} (from {pkg_dir})")
                pkg_tree: TreeDict = build_tree_structure(
                    pkg_dir, False, None, parse_git_func,
                    go_perm_excludes, [], [], ['.go']
                )
                package_trees_map[pkg_path] = pkg_tree
                package_tree_lines_map[pkg_path] = print_tree(pkg_tree, root_display_name=f"package:{pkg_path}")
            package_content_files = get_go_package_content_files(config, package_locations)
        elif config.verbose:
            print("No Go package locations found or 'go' command failed, cannot process packages.")
    elif config.verbose:
        print("\n--- No go_packages specified, skipping Go package processing. ---")

    compiled_text, files_compiled, files_skipped = assemble_compiled_content(
        config, root_abs_path, path_tree_lines, filtered_path_files,
        package_tree_lines_map, package_content_files, package_trees_map, # pyright: ignore [reportArgumentType]
        path_perm_excludes, go_perm_excludes
    )

    token_count_val = 0
    if tiktoken_mod:
        try:
            encoding = tiktoken_mod.get_encoding("cl100k_base")
            token_count_val = len(encoding.encode(compiled_text, allowed_special="all"))
        except Exception as e_token:
            if config.verbose: print(f"\nWarning: Could not calculate token count using tiktoken: {e_token}")

    output_file_written_path = None
    if config.output_file_path:
        try:
            abs_output_path = os.path.abspath(config.output_file_path)
            os.makedirs(os.path.dirname(abs_output_path), exist_ok=True)
            with open(abs_output_path, "w", encoding="utf-8") as outfile:
                outfile.write(compiled_text)
            output_file_written_path = abs_output_path
            if config.verbose: print(f"Output successfully written to: {abs_output_path}")
        except IOError as e_io:
            return CompilationResult(success=False, error_message=f"Failed to write output file '{config.output_file_path}': {e_io}")

    return CompilationResult(
        success=True,
        compiled_text=compiled_text,
        token_count=token_count_val,
        files_compiled_count=files_compiled,
        files_skipped_count=files_skipped,
        output_file_path=output_file_written_path
    )