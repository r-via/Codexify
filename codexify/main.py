from typing import List, Optional, Tuple, Dict, Any, Callable, Set
from dataclasses import dataclass, field
import os # Added os import

from .types import CompilationConfig, CompilationResult

from .core.common import BASE_PERMANENT_EXCLUSIONS, CONFIG_FILE_PATTERN, DEFAULT_OUTPUT_BASENAME
from .core.dependencies import ensure_tiktoken_module, ensure_gitignore_parser_module
from .core.file_system import load_gitignore, is_likely_binary, get_parent_folder_name, count_contents
from .core.go_utils import get_go_package_locations, get_go_package_content_files
from .core.tree_builder import build_tree_structure, print_tree, build_filtered_file_list
from .core.content_compiler import assemble_compiled_content

@dataclass
class CompilationConfig:
    """Configuration for the compilation process."""
    project_path: Optional[str] = None
    extensions: List[str] = field(default_factory=list)
    go_packages: List[str] = field(default_factory=list)
    output_file_path: Optional[str] = None
    exclude_dirs: List[str] = field(default_factory=list)
    exclude_files: List[str] = field(default_factory=list)
    gitignore_file_path: Optional[str] = None
    additional_path_permanent_exclusions: Set[str] = field(default_factory=set)
    additional_go_permanent_exclusions: Set[str] = field(default_factory=set)
    tiktoken_module: Optional[Any] = None
    parse_gitignore_func: Optional[Callable] = None
    verbose: bool = True

@dataclass
class CompilationResult:
    """Result of the compilation process."""
    success: bool = False
    compiled_text: Optional[str] = None
    token_count: int = 0
    files_compiled_count: int = 0
    files_skipped_count: int = 0
    output_file_path: Optional[str] = None
    error_message: Optional[str] = None

def generate_compiled_output(config: CompilationConfig) -> CompilationResult:
    """
    Generates compiled output based on the provided configuration.

    Args:
        config: A CompilationConfig object.

    Returns:
        A CompilationResult object.
    """
    if config.verbose: print("--- Starting Compilation Process (Programmatic Call) ---")

    tiktoken_mod = config.tiktoken_module or ensure_tiktoken_module()
    parse_git_func = config.parse_gitignore_func or ensure_gitignore_parser_module()

    path_perm_excludes = BASE_PERMANENT_EXCLUSIONS.union(config.additional_path_permanent_exclusions)
    path_perm_excludes.add(CONFIG_FILE_PATTERN)
    go_perm_excludes = BASE_PERMANENT_EXCLUSIONS.union(config.additional_go_permanent_exclusions)

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

        path_tree = build_tree_structure(
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
    package_trees_map: Dict[str, Dict] = {}

    if config.go_packages:
        if config.verbose:
            print(f"\n--- Processing Go Packages: {config.go_packages} ---")
            print(f"Permanently excluding from Go package processing: {', '.join(sorted(list(go_perm_excludes)))}")

        project_root_for_go_mod = root_abs_path if root_abs_path and os.path.exists(os.path.join(root_abs_path, 'go.mod')) else os.getcwd()
        package_locations = get_go_package_locations(config.go_packages, project_root_for_go_mod)

        if package_locations:
            for pkg_path, pkg_dir in package_locations.items():
                if config.verbose: print(f"Building tree for package: {pkg_path} (from {pkg_dir})")
                pkg_tree = build_tree_structure(
                    pkg_dir, False, None, parse_git_func,
                    go_perm_excludes, [], [], ['.go']
                )
                package_trees_map[pkg_path] = pkg_tree
                package_tree_lines_map[pkg_path] = print_tree(pkg_tree, root_display_name=f"package:{pkg_path}")
            package_content_files = get_go_package_content_files(package_locations)
        elif config.verbose:
            print("No Go package locations found or 'go' command failed, cannot process packages.")
    elif config.verbose:
        print("\n--- No go_packages specified, skipping Go package processing. ---")

    compiled_text, files_compiled, files_skipped = assemble_compiled_content(
        config, root_abs_path, path_tree_lines, filtered_path_files,
        package_tree_lines_map, package_content_files, package_trees_map,
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