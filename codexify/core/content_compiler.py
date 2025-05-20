import os
from typing import List, Dict, Optional, Tuple, Set, Any
# Corrected import for CompilationConfig - it's in the parent package
from ..main import CompilationConfig
from ..types import CompilationConfig
from .file_system import is_likely_binary

def assemble_compiled_content(
    config: CompilationConfig,
    root_abs_path: Optional[str],
    path_tree_lines: List[str],
    filtered_path_files: List[str],
    package_tree_lines_map: Dict[str, List[str]],
    package_content_files: List[Dict[str, str]],
    package_trees_map: Dict[str, Dict],
    path_perm_excludes: Set[str],
    go_perm_excludes: Set[str]
) -> Tuple[str, int, int]:
    """Assembles the final compiled text output and returns stats."""
    output_content_parts: List[str] = []
    files_compiled = 0
    files_skipped = 0

    if config.project_path and root_abs_path:
        gitignore_desc = f"using rules from '{os.path.basename(str(config.gitignore_file_path))}'" if config.gitignore_file_path and os.path.exists(os.path.abspath(str(config.gitignore_file_path))) else "no gitignore used"
        user_exclude_dir_desc = f", user dir excludes: [{', '.join(config.exclude_dirs)}]" if config.exclude_dirs else ""
        user_exclude_file_desc = f", user file excludes: [{', '.join(config.exclude_files)}]" if config.exclude_files else ""
        permanent_path_excludes_str = ', '.join(sorted(list(path_perm_excludes)))
        root_display_name = os.path.basename(root_abs_path) if root_abs_path != '.' else 'current_directory'

        output_content_parts.append(f"# === Directory Tree for Local Path: '{root_display_name}' ===\n")
        output_content_parts.append(f"# (Source: {root_abs_path})\n")
        output_content_parts.append(f"# (Options: {gitignore_desc}{user_exclude_dir_desc}{user_exclude_file_desc})\n")
        output_content_parts.append(f"# (Permanently Excluded: {permanent_path_excludes_str})\n")
        output_content_parts.append("# (File content read with UTF-8 encoding, 'replace' error handling for decode issues)\n")
        output_content_parts.append("# (Dirs/Files marked [Content Omitted] exist but their content is excluded based on rules/extensions)\n")
        output_content_parts.append(f"# {'='*70}\n")
        if not path_tree_lines: output_content_parts.append("# (Directory appears empty or all items were excluded)\n")
        else:
            for line in path_tree_lines: output_content_parts.append(f"# {line}\n")
        output_content_parts.append(f"# {'='*70}\n\n")
    else:
        output_content_parts.append("# === No local path processed ===\n\n")

    if package_tree_lines_map:
        output_content_parts.append("# === Go Package Trees ===\n")
        output_content_parts.append(f"# (Permanently Excluded: {', '.join(sorted(list(go_perm_excludes)))})\n")
        output_content_parts.append(f"# {'='*70}\n\n")
        for pkg_path_key in sorted(package_tree_lines_map.keys()):
            output_content_parts.append(f"# --- Tree for Package: {pkg_path_key} ---\n")
            output_content_parts.append(f"# {'-'*70}\n")
            if not package_trees_map.get(pkg_path_key) or not any(package_trees_map[pkg_path_key]):
                 output_content_parts.append("# (Package directory seems empty or only contained excluded items)\n")
            else:
                for line in package_tree_lines_map[pkg_path_key]: output_content_parts.append(f"# {line}\n")
            output_content_parts.append(f"# {'-'*70}\n\n")
        output_content_parts.append(f"# {'='*70}\n\n")
    elif config.go_packages:
         output_content_parts.append("# === Go Package Trees (None Found or Processed) ===\n\n")

    has_path_content = bool(filtered_path_files)
    has_package_content = bool(package_content_files)

    if not has_path_content and not has_package_content:
        output_content_parts.append("# === No files matched criteria for content compilation ===\n")
    else:
        output_content_parts.append(f"# === Compiled File Contents ===\n# {'='*70}\n\n")
        if has_path_content and root_abs_path:
            root_display_name = os.path.basename(root_abs_path) if root_abs_path != '.' else 'current_directory'
            output_content_parts.append(f"# --- Content from Path: '{root_display_name}' (Source: {root_abs_path}, Extensions: {config.extensions}) ---\n\n")
            for file_rel in filtered_path_files:
                file_abs_p = os.path.join(root_abs_path, file_rel.replace('/', os.sep))
                if is_likely_binary(file_abs_p):
                    if config.verbose: print(f"Skipping likely binary file from path: {file_rel}"); files_skipped += 1; continue
                output_content_parts.append(f"# File: {file_rel}\n# {'-' * 60}\n")
                try:
                    with open(file_abs_p, "r", encoding="utf-8", errors='replace') as infile: content = infile.read()
                    output_content_parts.append(content); output_content_parts.append("\n\n"); files_compiled += 1
                except FileNotFoundError:
                    output_content_parts.append(f"# Error: File not found during content read '{file_abs_p}'.\n\n")
                    if config.verbose: print(f"Error: File listed for compilation not found: {file_abs_p}"); files_skipped += 1
                except Exception as e_read:
                    output_content_parts.append(f"# Error reading file '{file_rel}': {e_read}.\n\n")
                    if config.verbose: print(f"Error reading file {file_rel}: {e_read}"); files_skipped += 1
            output_content_parts.append("\n")

        if has_package_content:
            output_content_parts.append("# --- Content from Go Packages ---\n\n")
            current_pkg = None
            for pkg_file_data in package_content_files:
                pkg, rel_path, abs_p = pkg_file_data['package'], pkg_file_data['relative_path'], pkg_file_data['absolute_path']
                if pkg != current_pkg: output_content_parts.append(f"# --- Package: {pkg} ---\n\n"); current_pkg = pkg
                output_content_parts.append(f"# File: package:{pkg}/{rel_path}\n# {'-' * 60}\n")
                try:
                    with open(abs_p, "r", encoding="utf-8", errors='replace') as infile: content = infile.read()
                    output_content_parts.append(content); output_content_parts.append("\n\n"); files_compiled += 1
                except Exception as e_read_pkg:
                    output_content_parts.append(f"# Error reading package file '{pkg}/{rel_path}': {e_read_pkg}.\n\n")
                    if config.verbose: print(f"Error reading package file {pkg}/{rel_path}: {e_read_pkg}"); files_skipped += 1

    if files_skipped > 0:
         output_content_parts.append(f"# {'='*70}\n# Note: {files_skipped} file(s) were skipped (e.g., binary, unreadable, not found during read).\n# {'='*70}\n")

    full_output_text = "".join(output_content_parts)
    return full_output_text, files_compiled, files_skipped