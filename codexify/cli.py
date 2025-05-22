# codexify/cli.py
import os
import sys
import argparse
import fnmatch
from typing import Dict, Any, Optional, List
import yaml

from .main import generate_compiled_output
from .types import CompilationConfig
from .core.common import CONFIG_FILE_PATTERN, DEFAULT_OUTPUT_BASENAME
from .core.file_system import get_parent_folder_name


def _load_config_from_yaml_for_cli(
    config_file_path: str, yaml_module: Any
) -> Dict[str, Any]:
    """
    Loads configuration from a YAML file for CLI use.

    Paths within the YAML file ('path', 'gitignore') are resolved.
    'path' is relative to the YAML file's directory if relative.
    'gitignore' (if relative in YAML) is resolved relative to the YAML file's directory.
    If 'path' is specified, 'extensions' must also be present.
    The config must define either 'path' or 'packages'.

    Args:
        config_file_path: Path to the YAML configuration file.
        yaml_module: The imported 'yaml' module (PyYAML).

    Returns:
        A dictionary containing processed configuration values:
        - "project_path": Absolute path to the project, or None.
        - "extensions": List of file extensions.
        - "go_packages": List of Go package paths.
        - "output_base_name_no_ext": Base name for the output file (no "compiled." prefix or .txt).
        - "exclude_dirs": List of directory names to exclude.
        - "exclude_files": List of file names to exclude.
        - "gitignore_file_path": Absolute path to the .gitignore file, or None.
        - "config_source_dir": Absolute path to the directory containing the config file.

    Raises:
        SystemExit: If the config file is not found, invalid, or essential fields are missing.
    """
    try:
        abs_config_path = os.path.abspath(config_file_path)
        config_basename = os.path.basename(config_file_path)
        if not (
            config_basename.lower().endswith(".yaml")
            or config_basename.lower().endswith(".yml")
        ):
            print(
                f"Warning: Config file '{config_file_path}' does not end with .yaml or .yml."
            )
        if not fnmatch.fnmatch(config_basename, CONFIG_FILE_PATTERN):
            print(
                f"Warning: Config file name '{config_basename}' doesn't match expected pattern '{CONFIG_FILE_PATTERN}'."
            )

        with open(abs_config_path, "r", encoding="utf-8") as f:
            loaded_config_any = yaml_module.safe_load(f)
        if not isinstance(loaded_config_any, dict):
            print(
                f"Error: Config file '{config_file_path}' is empty or invalid YAML (not a dictionary)."
            )
            sys.exit(1)
        loaded_config: Dict[str, Any] = loaded_config_any

        config_dir = os.path.dirname(abs_config_path)

        project_path_from_yaml_value = loaded_config.get("path")
        abs_project_path_from_yaml: Optional[str] = None
        if project_path_from_yaml_value is not None:
            abs_project_path_from_yaml = os.path.normpath(
                os.path.join(config_dir, str(project_path_from_yaml_value))
            )

        gitignore_in_yaml_value = loaded_config.get("gitignore")
        resolved_gitignore_path: Optional[str] = None
        if gitignore_in_yaml_value is not None:
            str_gitignore_value = str(gitignore_in_yaml_value)
            if os.path.isabs(str_gitignore_value):
                resolved_gitignore_path = str_gitignore_value
            else:
                # MODIFICATION: Always resolve relative gitignore path from YAML
                # relative to the config file's directory.
                resolved_gitignore_path = os.path.normpath(
                    os.path.join(config_dir, str_gitignore_value)
                )

        if abs_project_path_from_yaml and "extensions" not in loaded_config:
            print(
                "Config Error: 'extensions' field is required when 'path' is specified."
            )
            sys.exit(1)
        if not abs_project_path_from_yaml and not loaded_config.get("packages"):
            print(
                "Config Error: Config must contain at least one of 'path' or 'packages'."
            )
            sys.exit(1)

        default_output_base_no_ext = DEFAULT_OUTPUT_BASENAME
        if default_output_base_no_ext.endswith(".txt"):
            default_output_base_no_ext = default_output_base_no_ext[:-4]

        output_base_no_ext_any = loaded_config.get("output", default_output_base_no_ext)
        output_base_no_ext: str
        if isinstance(output_base_no_ext_any, str):
            output_base_no_ext = output_base_no_ext_any
        else:
            output_base_no_ext = default_output_base_no_ext

        return {
            "project_path": abs_project_path_from_yaml,
            "extensions": loaded_config.get("extensions", []),
            "go_packages": loaded_config.get("packages", []),
            "output_base_name_no_ext": output_base_no_ext,
            "exclude_dirs": loaded_config.get("exclude", []),
            "exclude_files": loaded_config.get("exclude_files", []),
            "gitignore_file_path": resolved_gitignore_path,
            "config_source_dir": config_dir,  # This is key for output dir
        }
    except FileNotFoundError:
        print(f"Error: Config file not found: '{config_file_path}'")
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"Error parsing YAML in config file '{config_file_path}': {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error loading or processing config file '{config_file_path}': {e}")
        sys.exit(1)


def _save_config_for_cli(
    args: argparse.Namespace,
    yaml_module: Any,
    determined_output_dir: str,  # This is where config is saved
    output_base_name_no_ext_for_yaml: str,
) -> str:
    """
    Saves CLI arguments to a YAML configuration file.

    'path' in YAML is relative to the config file's directory.
    'gitignore' in YAML is relative to the config file's directory.
    'output' is just a base name, output file will be in config file's directory.

    Args:
        args: Parsed command-line arguments (argparse.Namespace).
        yaml_module: The imported 'yaml' module (PyYAML).
        determined_output_dir: The absolute directory where the config file will be saved.
        output_base_name_no_ext_for_yaml: The base name for the 'output' field in YAML.

    Returns:
        The absolute path to the saved configuration file.

    Raises:
        SystemExit: If required arguments for saving are missing or if saving fails.
    """
    config_data: Dict[str, Any] = {}
    if not args.path and not args.packages:
        print("Error: Cannot use --save without providing either --path or --packages.")
        sys.exit(1)
    if args.path and not args.extensions:
        print("Error: --extensions are required when specifying --path with --save.")
        sys.exit(1)

    _name_candidate: Optional[str] = None
    if args.config_name and isinstance(args.config_name, str):
        _name_candidate = args.config_name
    elif args.path and isinstance(args.path, str):
        _name_candidate = get_parent_folder_name(args.path)

    config_name_base: str = (
        _name_candidate if _name_candidate and _name_candidate.strip() else "output"
    )

    config_basename_final = f"config.compiled.{config_name_base}.yaml"
    config_filename = os.path.abspath(
        os.path.join(determined_output_dir, config_basename_final)
    )
    config_file_actual_dir = os.path.dirname(
        config_filename
    )  # Should be same as determined_output_dir

    if args.path and isinstance(args.path, str):
        print(f"Determined config file path for saving: {config_filename}")
    else:
        print(f"Config file for saving: {config_filename}")

    abs_cli_project_path: Optional[str] = None
    if args.path and isinstance(args.path, str):
        abs_cli_project_path = os.path.abspath(args.path)

    path_in_yaml: Optional[str] = None
    if abs_cli_project_path:
        try:
            path_in_yaml = os.path.relpath(abs_cli_project_path, config_file_actual_dir)
        except ValueError:
            path_in_yaml = abs_cli_project_path

    abs_intended_cli_gitignore_path: Optional[str] = None
    if args.gitignore and isinstance(args.gitignore, str):
        if os.path.isabs(args.gitignore):
            abs_intended_cli_gitignore_path = args.gitignore
        # MODIFICATION: If CLI gitignore is relative, it's relative to CWD or --path,
        # then made absolute. For saving, we make it relative to config dir.
        elif (
            abs_cli_project_path
        ):  # If --path is given, CLI gitignore is relative to it
            abs_intended_cli_gitignore_path = os.path.normpath(
                os.path.join(abs_cli_project_path, args.gitignore)
            )
        else:  # No --path, CLI gitignore is relative to CWD
            abs_intended_cli_gitignore_path = os.path.abspath(args.gitignore)

    gitignore_in_yaml: Optional[str] = None
    if abs_intended_cli_gitignore_path:
        try:
            # MODIFICATION: Always make gitignore path in YAML relative to the config file's directory
            gitignore_in_yaml = os.path.relpath(
                abs_intended_cli_gitignore_path, config_file_actual_dir
            )
        except ValueError:  # Different drive on Windows, etc.
            gitignore_in_yaml = abs_intended_cli_gitignore_path

    config_data["path"] = path_in_yaml
    config_data["extensions"] = args.extensions if args.extensions else []
    config_data["output"] = output_base_name_no_ext_for_yaml
    config_data["packages"] = args.packages if args.packages else []
    config_data["exclude"] = args.exclude if args.exclude else []
    config_data["exclude_files"] = args.exclude_files if args.exclude_files else []
    config_data["gitignore"] = gitignore_in_yaml

    print(f"Attempting to save configuration to: {config_filename}")
    try:
        os.makedirs(config_file_actual_dir, exist_ok=True)
        with open(config_filename, "w", encoding="utf-8") as f:
            yaml_module.safe_dump(
                config_data,
                f,
                default_flow_style=None,
                sort_keys=False,
                allow_unicode=True,
            )
        print(f"Configuration successfully saved to '{config_filename}'.")
    except Exception as e:
        print(f"Error: Failed to save configuration to '{config_filename}': {e}")
        sys.exit(1)
    return config_filename


def run_cli():
    """
    Handles CLI argument parsing and orchestrates the compilation.
    # ... (rest of docstring) ...
    """
    package_name_str = "codexify"

    parser = argparse.ArgumentParser(
        # ... (parser setup remains the same) ...
        description="Codexify: Compiles project files into structured text for LLM context.",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=f"Example:\n  python3 -m {package_name_str}.cli --path ../p --ext .py --save\n  {package_name_str} --path ../p --ext .py --gitignore .gitignore",
        add_help=False,
    )

    parser.add_argument(
        "--path",
        help="Directory to explore (relative to current working directory or absolute).",
    )
    parser.add_argument(
        "--extensions",
        "--ext",
        nargs="+",
        help="File extensions for content compilation from --path (e.g., .py .md Makefile).",
    )
    parser.add_argument(
        "--packages",
        nargs="+",
        help="Go package import path(s) to include (e.g., github.com/gin-gonic/gin).",
    )

    parser.add_argument(
        "--config",
        help=f"Path to YAML config file (e.g., {CONFIG_FILE_PATTERN.replace('*', 'myproject')}). Overrides most other CLI args.",
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="Save CLI arguments to 'config.compiled.<name>.yaml' and then compile. Ignored if --config is used.",
    )
    parser.add_argument(
        "--config-name",
        help="Base name for the generated config file when using --save (e.g., 'myproj'). Defaults based on --path or 'output'.",
    )

    parser.add_argument(
        "--output",
        help="Base name or full path for the output file. If a path, its directory is used as the output directory. Default name is derived from --path or 'output'. When --config is used, output is relative to config file's directory.",
    )

    parser.add_argument(
        "--exclude",
        nargs="*",
        default=[],
        help="Directory names to exclude from content compilation when processing --path.",
    )
    parser.add_argument(
        "--exclude-files",
        nargs="*",
        default=[],
        help="File names to exclude from content compilation when processing --path.",
    )
    parser.add_argument(
        "--gitignore",
        help="Path to a .gitignore file to use. If --config is used, this path (if relative) is relative to the config file. Otherwise, relative to --path or CWD.",
    )

    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress verbose output from core logic (progress messages).",
    )
    parser.add_argument(
        "-h",
        "--help",
        action="help",
        default=argparse.SUPPRESS,
        help="Show this help message and exit.",
    )

    try:
        from .version import __version__ as version_str
    except ImportError:
        version_str = "unknown"
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {version_str}"
    )

    args = parser.parse_args()

    comp_config = CompilationConfig(verbose=not args.quiet)
    output_base_name_no_ext: str
    output_dir_cli: str  # This will be the final output directory

    # Arguments from CLI or to be loaded from YAML
    cli_path_arg: Optional[str] = args.path
    cli_extensions_arg: Optional[List[str]] = args.extensions
    cli_packages_arg: Optional[List[str]] = args.packages
    cli_exclude_arg: List[str] = args.exclude
    cli_exclude_files_arg: List[str] = args.exclude_files
    # `cli_gitignore_arg` from `args.gitignore` will be processed based on context (config or not)
    cli_output_arg: Optional[str] = args.output  # From --output

    if args.config and isinstance(args.config, str):
        try:
            cli_loaded_yaml_config = _load_config_from_yaml_for_cli(args.config, yaml)
        except ImportError:
            print(
                "Error: PyYAML module is required to load configuration from a YAML file."
            )
            print("Please install it by running: pip install PyYAML")
            print(
                f"Alternatively, install '{package_name_str}' with all its dependencies: pip install {package_name_str}"
            )
            sys.exit(1)
        except Exception as e:
            print(f"An unexpected error occurred while trying to load YAML config: {e}")
            sys.exit(1)

        comp_config.project_path = cli_loaded_yaml_config["project_path"]
        comp_config.extensions = cli_loaded_yaml_config["extensions"]
        comp_config.go_packages = cli_loaded_yaml_config["go_packages"]
        comp_config.exclude_dirs = cli_loaded_yaml_config["exclude_dirs"]
        comp_config.exclude_files = cli_loaded_yaml_config["exclude_files"]
        comp_config.gitignore_file_path = cli_loaded_yaml_config["gitignore_file_path"]

        output_base_name_no_ext = cli_loaded_yaml_config["output_base_name_no_ext"]
        # MODIFICATION: When --config is used, output_dir_cli is ALWAYS the config file's directory.
        output_dir_cli = cli_loaded_yaml_config["config_source_dir"]

        if comp_config.verbose:
            print(f"Loaded configuration from: {args.config}")
        if comp_config.verbose:
            print(f"Output directory (from config): {output_dir_cli}")
        if comp_config.gitignore_file_path and comp_config.verbose:
            print(
                f"Gitignore path (from config, resolved): {comp_config.gitignore_file_path}"
            )

    else:  # No --config, using direct CLI args
        if not cli_path_arg and not cli_packages_arg:
            parser.error(
                "Either --path or --packages must be specified if not using --config."
            )
        if cli_path_arg and not cli_extensions_arg:
            parser.error(
                "--extensions (--ext) are required when --path is specified without --config."
            )

        if cli_path_arg:
            comp_config.project_path = os.path.abspath(cli_path_arg)
        else:
            comp_config.project_path = (
                None  # Should not happen due to check above if no packages
            )

        comp_config.extensions = cli_extensions_arg if cli_extensions_arg else []
        comp_config.go_packages = cli_packages_arg if cli_packages_arg else []
        comp_config.exclude_dirs = cli_exclude_arg
        comp_config.exclude_files = cli_exclude_files_arg

        # Handle gitignore path for CLI mode
        if args.gitignore:  # User provided --gitignore
            if os.path.isabs(args.gitignore):
                comp_config.gitignore_file_path = args.gitignore
            elif (
                comp_config.project_path
            ):  # If --path is given, gitignore is relative to it
                comp_config.gitignore_file_path = os.path.normpath(
                    os.path.join(comp_config.project_path, args.gitignore)
                )
            else:  # No --path, gitignore is relative to CWD
                comp_config.gitignore_file_path = os.path.abspath(args.gitignore)
        else:  # No --gitignore provided
            comp_config.gitignore_file_path = None

        if comp_config.gitignore_file_path and comp_config.verbose:
            print(
                f"Gitignore path (from CLI, resolved): {comp_config.gitignore_file_path}"
            )

        # Determine output_dir_cli and output_base_name_no_ext for CLI mode
        if cli_output_arg:  # --output was given
            abs_cli_output_arg = os.path.abspath(cli_output_arg)
            output_base_name_from_arg = os.path.basename(abs_cli_output_arg)

            # If --output looks like a file name (e.g. "report" or "report.txt")
            if output_base_name_from_arg and (
                "." in output_base_name_from_arg
                or not os.path.isdir(abs_cli_output_arg)
            ):
                output_base_name_no_ext = (
                    output_base_name_from_arg[:-4]
                    if output_base_name_from_arg.lower().endswith(".txt")
                    else output_base_name_from_arg
                )
                output_dir_cli = os.path.dirname(abs_cli_output_arg)
                if not output_dir_cli:  # e.g. --output myreport (no path part)
                    output_dir_cli = (
                        comp_config.project_path
                        if comp_config.project_path
                        else os.getcwd()
                    )
            else:  # --output looks like a directory path (e.g. "./out_dir" or "/abs/out_dir")
                output_dir_cli = abs_cli_output_arg
                parent_name = (
                    get_parent_folder_name(comp_config.project_path)
                    if comp_config.project_path
                    else None
                )
                default_base = (
                    DEFAULT_OUTPUT_BASENAME[:-4]
                    if DEFAULT_OUTPUT_BASENAME.lower().endswith(".txt")
                    else DEFAULT_OUTPUT_BASENAME
                )
                output_base_name_no_ext = parent_name if parent_name else default_base
        else:  # --output was NOT given, derive from --path or use default
            parent_name = (
                get_parent_folder_name(comp_config.project_path)
                if comp_config.project_path
                else None
            )
            default_base = (
                DEFAULT_OUTPUT_BASENAME[:-4]
                if DEFAULT_OUTPUT_BASENAME.lower().endswith(".txt")
                else DEFAULT_OUTPUT_BASENAME
            )
            output_base_name_no_ext = parent_name if parent_name else default_base

            if comp_config.project_path:
                output_dir_cli = comp_config.project_path  # Output to project_path dir
            else:
                output_dir_cli = os.getcwd()  # Output to CWD

        if comp_config.verbose:
            print("Using command-line arguments for configuration.")
        if comp_config.verbose:
            print(f"Output directory (from CLI args): {output_dir_cli}")

    # Ensure output_dir_cli is a directory and exists
    if os.path.isfile(output_dir_cli):  # If it accidentally resolved to a file
        output_dir_cli = os.path.dirname(output_dir_cli)
    os.makedirs(output_dir_cli, exist_ok=True)  # Create if not exists

    final_output_filename = f"compiled.{output_base_name_no_ext}.txt"
    comp_config.output_file_path = os.path.join(output_dir_cli, final_output_filename)
    if comp_config.verbose:
        print(f"Output file will be: {comp_config.output_file_path}")

    # Add self to permanent exclusions (remains the same)
    if comp_config.project_path:
        try:
            cli_module_file_path = __import__(
                f"{package_name_str}.cli", fromlist=["__file__"]
            ).__file__
            if cli_module_file_path:
                abs_script_path = os.path.abspath(cli_module_file_path)
                # Ensure project_path is absolute for comparison
                abs_project_path_for_compare = os.path.abspath(comp_config.project_path)
                if (
                    os.path.commonpath([abs_script_path, abs_project_path_for_compare])
                    == abs_project_path_for_compare
                ):
                    script_rel_path = os.path.relpath(
                        abs_script_path, abs_project_path_for_compare
                    )
                    comp_config.additional_path_permanent_exclusions.add(
                        script_rel_path.replace(os.sep, "/")
                    )
                    if comp_config.verbose:
                        print(f"Excluding self (module): {script_rel_path}")
        except (ImportError, AttributeError, TypeError, ValueError):
            if sys.argv and sys.argv[0] and sys.argv[0].endswith(".py"):
                try:
                    potential_script_path = os.path.abspath(sys.argv[0])
                    abs_project_path_for_compare = os.path.abspath(
                        comp_config.project_path
                    )
                    if (
                        os.path.commonpath(
                            [potential_script_path, abs_project_path_for_compare]
                        )
                        == abs_project_path_for_compare
                    ):
                        script_rel_path = os.path.relpath(
                            potential_script_path, abs_project_path_for_compare
                        )
                        comp_config.additional_path_permanent_exclusions.add(
                            script_rel_path.replace(os.sep, "/")
                        )
                        if comp_config.verbose:
                            print(f"Excluding self (script): {script_rel_path}")
                except ValueError:
                    pass  # commonpath issues if on different drives
                except Exception:
                    pass  # Catch all for safety

    if args.save:
        if args.config:
            if comp_config.verbose:
                print("Warning: --save option is ignored when --config is used.")
        else:
            if comp_config.verbose:
                print("Processing --save flag...")
            try:
                # For --save, the config file is saved in output_dir_cli
                # output_base_name_no_ext is used for the 'output' field in YAML
                _save_config_for_cli(
                    args, yaml, output_dir_cli, output_base_name_no_ext
                )
            except ImportError:
                print(
                    "Error: PyYAML module is required to save configuration to a YAML file."
                )
                # ... (rest of error message) ...
                sys.exit(1)
            except Exception as e:
                print(
                    f"An unexpected error occurred while trying to save YAML config: {e}"
                )
                sys.exit(1)
            if comp_config.verbose:
                print("Proceeding with compilation using the current arguments...")

    result = generate_compiled_output(comp_config)

    if result.success:
        print("\n" + "-" * 40)
        # No specific message for --save here anymore, it's part of the flow
        print("Compilation completed successfully.")
        if result.output_file_path:
            print(f"Output file: {result.output_file_path}")
        print(f"Included content from {result.files_compiled_count} file(s).")
        if result.files_skipped_count > 0:
            print(
                f"Skipped {result.files_skipped_count} file(s) during content processing."
            )
        if result.token_count > 0:
            print(f"Estimated token count (cl100k_base): {result.token_count}")
        else:
            print(
                "Token count estimation failed or skipped (no content generated or tiktoken issue)."
            )
        print("-" * 40)
    else:
        print(f"\nError during compilation: {result.error_message}")
        sys.exit(1)


if __name__ == "__main__":
    run_cli()
