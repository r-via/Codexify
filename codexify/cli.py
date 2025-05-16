# codexify/codexify/cli.py
import os
import sys
import argparse
import fnmatch
from typing import Dict, Any, Optional

from .main import generate_compiled_output, CompilationConfig
from .core.dependencies import ensure_pyyaml_module
from .core.common import CONFIG_FILE_PATTERN, DEFAULT_OUTPUT_BASENAME
from .core.file_system import get_parent_folder_name


def _load_config_from_yaml_for_cli(config_file_path: str,
                                   yaml_module: Any) -> Dict[str, Any]:
    """Loads configuration from a YAML file for CLI use."""
    try:
        abs_config_path = os.path.abspath(config_file_path)
        config_basename = os.path.basename(config_file_path)
        if not (config_basename.lower().endswith('.yaml')
                or config_basename.lower().endswith('.yml')):
            print(
                f"Warning: Config file '{config_file_path}' does not end with .yaml or .yml."
            )
        if not fnmatch.fnmatch(config_basename, CONFIG_FILE_PATTERN):
            print(
                f"Warning: Config file name '{config_basename}' doesn't match expected pattern '{CONFIG_FILE_PATTERN}'."
            )

        with open(abs_config_path, 'r', encoding='utf-8') as f:
            loaded_config = yaml_module.safe_load(f)
        if not loaded_config:
            print(
                f"Error: Config file '{config_file_path}' is empty or invalid YAML."
            )
            sys.exit(1)

        config_dir = os.path.dirname(abs_config_path)

        project_path_from_yaml_value = loaded_config.get('path')
        abs_project_path_from_yaml: Optional[str] = None
        if project_path_from_yaml_value is not None:
            abs_project_path_from_yaml = os.path.normpath(
                os.path.join(config_dir, str(project_path_from_yaml_value)))

        gitignore_in_yaml_value = loaded_config.get('gitignore')
        resolved_gitignore_path: Optional[str] = None
        if gitignore_in_yaml_value is not None:
            if os.path.isabs(gitignore_in_yaml_value):
                resolved_gitignore_path = str(gitignore_in_yaml_value)
            elif abs_project_path_from_yaml:
                project_base_dir_for_gitignore = os.path.dirname(
                    abs_project_path_from_yaml) if os.path.isfile(
                        abs_project_path_from_yaml
                    ) else abs_project_path_from_yaml
                resolved_gitignore_path = os.path.normpath(
                    os.path.join(project_base_dir_for_gitignore,
                                 str(gitignore_in_yaml_value)))
            else:
                resolved_gitignore_path = os.path.normpath(
                    os.path.join(config_dir, str(gitignore_in_yaml_value)))

        if abs_project_path_from_yaml and 'extensions' not in loaded_config:
            print(
                "Config Error: 'extensions' field is required when 'path' is specified."
            )
            sys.exit(1)
        if not abs_project_path_from_yaml and not loaded_config.get(
                'packages'):
            print(
                "Config Error: Config must contain at least one of 'path' or 'packages'."
            )
            sys.exit(1)

        default_output_base_no_ext = DEFAULT_OUTPUT_BASENAME
        if default_output_base_no_ext.endswith(".txt"):
            default_output_base_no_ext = default_output_base_no_ext[:-4]
        output_base_no_ext = loaded_config.get('output',
                                               default_output_base_no_ext)

        return {
            "project_path": abs_project_path_from_yaml,
            "extensions": loaded_config.get('extensions', []),
            "go_packages": loaded_config.get('packages', []),
            "output_base_name_no_ext": output_base_no_ext,
            "exclude_dirs": loaded_config.get('exclude', []),
            "exclude_files": loaded_config.get('exclude_files', []),
            "gitignore_file_path": resolved_gitignore_path,
            "config_source_dir": config_dir
        }
    except FileNotFoundError:
        print(f"Error: Config file not found: '{config_file_path}'")
        sys.exit(1)
    except Exception as e:
        print(
            f"Error loading or parsing config file '{config_file_path}': {e}")
        sys.exit(1)


def _save_config_for_cli(args: argparse.Namespace, yaml_module: Any,
                         determined_output_dir: str,
                         output_base_name_no_ext_for_yaml: str) -> str:
    """
    Saves CLI arguments to a YAML configuration file.
    output_base_name_no_ext_for_yaml: The base name (e.g., "myproject") to be stored in the YAML's 'output' key.
    """
    config_data: Dict[str, Any] = {}
    if not args.path and not args.packages:
        print(
            "Error: Cannot use --save without providing either --path or --packages."
        )
        sys.exit(1)
    if args.path and not args.extensions:
        print(
            "Error: --extensions are required when specifying --path with --save."
        )
        sys.exit(1)

    config_name_base = args.config_name if args.config_name else (
        get_parent_folder_name(args.path) if args.path else "output")
    config_basename_final = f"config.compiled.{config_name_base}.yaml"
    config_filename = os.path.abspath(
        os.path.join(determined_output_dir, config_basename_final))
    config_file_actual_dir = os.path.dirname(config_filename)
    print(f"Determined config file path for saving: {config_filename}")

    # 1. Determine absolute path of the project processed by CLI (from CWD of command)
    abs_cli_project_path: Optional[str] = None
    if args.path:
        abs_cli_project_path = os.path.abspath(args.path)

    # 2. Determine path to be stored in YAML for the project (relative to YAML's future location)
    path_in_yaml: Optional[str] = None
    if abs_cli_project_path:
        try:
            path_in_yaml = os.path.relpath(abs_cli_project_path,
                                           config_file_actual_dir)
        except ValueError:
            path_in_yaml = abs_cli_project_path  # Different drives

    # 3. Determine absolute path of the gitignore file intended by CLI
    #    (relative to abs_cli_project_path if args.gitignore is relative)
    abs_intended_cli_gitignore_path: Optional[str] = None
    if args.gitignore:
        if os.path.isabs(args.gitignore):
            abs_intended_cli_gitignore_path = args.gitignore
        elif abs_cli_project_path:  # --gitignore is relative to --path
            abs_intended_cli_gitignore_path = os.path.normpath(
                os.path.join(abs_cli_project_path, args.gitignore))
        else:  # --gitignore is relative to CWD (no --path provided)
            abs_intended_cli_gitignore_path = os.path.abspath(args.gitignore)

    # 4. Determine gitignore path to be stored in YAML (relative to path_in_yaml)
    gitignore_in_yaml: Optional[str] = None
    if abs_intended_cli_gitignore_path:
        if path_in_yaml:  # If a project path will be in YAML
            # Base for relativity is the project path as it will be known from the YAML
            project_dir_for_yaml_relativity = os.path.abspath(
                os.path.join(config_file_actual_dir, path_in_yaml))
            if os.path.isfile(project_dir_for_yaml_relativity
                              ):  # If path_in_yaml points to a file
                project_dir_for_yaml_relativity = os.path.dirname(
                    project_dir_for_yaml_relativity)

            try:
                gitignore_in_yaml = os.path.relpath(
                    abs_intended_cli_gitignore_path,
                    project_dir_for_yaml_relativity)
            except ValueError:  # Different drives
                gitignore_in_yaml = abs_intended_cli_gitignore_path  # Fallback to absolute
        else:  # No project path in YAML, make gitignore relative to YAML file itself or absolute
            try:
                gitignore_in_yaml = os.path.relpath(
                    abs_intended_cli_gitignore_path, config_file_actual_dir)
            except ValueError:
                gitignore_in_yaml = abs_intended_cli_gitignore_path

    config_data['path'] = path_in_yaml
    config_data['extensions'] = args.extensions if args.extensions else []
    config_data['output'] = output_base_name_no_ext_for_yaml
    config_data['packages'] = args.packages if args.packages else []
    config_data['exclude'] = args.exclude if args.exclude else []
    config_data[
        'exclude_files'] = args.exclude_files if args.exclude_files else []
    config_data['gitignore'] = gitignore_in_yaml

    print(f"Attempting to save configuration to: {config_filename}")
    try:
        os.makedirs(config_file_actual_dir, exist_ok=True)
        with open(config_filename, 'w', encoding='utf-8') as f:
            yaml_module.safe_dump(config_data,
                                  f,
                                  default_flow_style=None,
                                  sort_keys=False,
                                  allow_unicode=True)
        print(f"Configuration successfully saved to '{config_filename}'.")
    except Exception as e:
        print(
            f"Error: Failed to save configuration to '{config_filename}': {e}")
        sys.exit(1)
    return config_filename


def run_cli():
    """Handles CLI argument parsing and orchestrates the compilation."""
    package_name_str = "codexify"

    script_filename = os.path.basename(
        sys.argv[0] if sys.argv else package_name_str)
    parser = argparse.ArgumentParser(
        description=
        "Codexify: Compiles project files into structured text for LLM context.",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=
        f"Example:\n  python3 -m {package_name_str}.cli --path ../p --ext .py --save\n  {package_name_str} --path ../p --ext .py --gitignore .gitignore",
        add_help=False)
    parser.add_argument('-h',
                        '--help',
                        action='help',
                        default=argparse.SUPPRESS,
                        help='Show this help message and exit.')
    parser.add_argument(
        "--save",
        action='store_true',
        help="Save CLI args to 'config.compiled.<name>.yaml' and compile.")
    parser.add_argument(
        "--config",
        help=
        f"Path to YAML config file (e.g., {CONFIG_FILE_PATTERN.replace('*', 'name')})."
    )
    parser.add_argument(
        "--path",
        help="Directory to explore (relative to current working directory).")
    parser.add_argument(
        "--extensions",
        "--ext",
        nargs='+',
        help="File extensions for content compilation from --path.")
    parser.add_argument("--packages",
                        nargs='+',
                        help="Go package path(s) to include.")
    parser.add_argument(
        "--output",
        help=
        "Base name for output file. If a path, its dirname is used for output dir. Default derived from --path or 'output'."
    )
    parser.add_argument(
        "--config-name",
        help="Base name for config file (e.g., 'myproj'). Used with --save.")
    parser.add_argument("--exclude",
                        nargs="*",
                        default=[],
                        help="Dir names to exclude from content in --path.")
    parser.add_argument("--exclude-files",
                        nargs="*",
                        default=[],
                        help="File names to exclude from content in --path.")
    parser.add_argument(
        "--gitignore",
        help=
        "Path to .gitignore file to use (relative to --path if relative CLI arg, otherwise absolute or resolved from YAML)."
    )
    parser.add_argument("-q",
                        "--quiet",
                        action="store_true",
                        help="Suppress verbose output from core logic.")

    try:
        version_str = __import__(f"{package_name_str}.version",
                                 fromlist=['__version__']).__version__
    except ImportError:
        version_str = "unknown"
    parser.add_argument('--version',
                        action='version',
                        version=f'%(prog)s {version_str}')

    args = parser.parse_args()

    comp_config = CompilationConfig(verbose=not args.quiet)
    output_base_name_no_ext: str
    output_dir_cli: str

    yaml_mod = None
    if args.config:
        if not yaml_mod: yaml_mod = ensure_pyyaml_module()
        cli_loaded_yaml_config = _load_config_from_yaml_for_cli(
            args.config, yaml_mod)

        comp_config.project_path = cli_loaded_yaml_config["project_path"]
        comp_config.extensions = cli_loaded_yaml_config["extensions"]
        comp_config.go_packages = cli_loaded_yaml_config["go_packages"]
        comp_config.exclude_dirs = cli_loaded_yaml_config["exclude_dirs"]
        comp_config.exclude_files = cli_loaded_yaml_config["exclude_files"]
        comp_config.gitignore_file_path = cli_loaded_yaml_config[
            "gitignore_file_path"]

        output_base_name_no_ext = cli_loaded_yaml_config[
            "output_base_name_no_ext"]

        if comp_config.project_path:
            output_dir_cli = os.path.dirname(
                comp_config.project_path) if os.path.isfile(
                    comp_config.project_path) else comp_config.project_path
        else:
            output_dir_cli = cli_loaded_yaml_config["config_source_dir"]
        print(f"Loaded configuration from: {args.config}")
    else:  # No --config, using CLI args
        if not args.path and not args.packages:
            parser.error(
                "Either --path or --packages must be specified if not using --config."
            )
        if args.path and not args.extensions:
            parser.error(
                "--extensions (--ext) are required when --path is specified without --config."
            )

        if args.path:
            comp_config.project_path = os.path.abspath(args.path)
        else:
            comp_config.project_path = None

        comp_config.extensions = args.extensions if args.extensions else []
        comp_config.go_packages = args.packages if args.packages else []
        comp_config.exclude_dirs = args.exclude
        comp_config.exclude_files = args.exclude_files

        if args.gitignore:
            if os.path.isabs(args.gitignore):
                comp_config.gitignore_file_path = args.gitignore
            elif comp_config.project_path:
                comp_config.gitignore_file_path = os.path.normpath(
                    os.path.join(comp_config.project_path, args.gitignore))
            else:
                comp_config.gitignore_file_path = os.path.abspath(
                    args.gitignore)
        else:
            comp_config.gitignore_file_path = None

        if args.output:
            output_base_name_from_arg = os.path.basename(args.output)
            output_base_name_no_ext = output_base_name_from_arg[:-4] if output_base_name_from_arg.endswith(
                ".txt") else output_base_name_from_arg

            output_dir_candidate = os.path.dirname(args.output)
            if output_dir_candidate:
                output_dir_cli = os.path.abspath(output_dir_candidate)
            elif comp_config.project_path:
                output_dir_cli = comp_config.project_path
            else:
                output_dir_cli = os.getcwd()
        else:
            parent_name = get_parent_folder_name(
                comp_config.project_path) if comp_config.project_path else None
            default_base_no_ext = DEFAULT_OUTPUT_BASENAME[:-4] if DEFAULT_OUTPUT_BASENAME.endswith(
                ".txt") else DEFAULT_OUTPUT_BASENAME
            output_base_name_no_ext = parent_name if parent_name else default_base_no_ext

            if comp_config.project_path:
                output_dir_cli = comp_config.project_path
            else:
                output_dir_cli = os.getcwd()
        print("Using command-line arguments for configuration.")

    output_base_name_with_ext = output_base_name_no_ext + ".txt"
    final_output_filename_for_compilation = "compiled." + output_base_name_with_ext
    comp_config.output_file_path = os.path.join(
        output_dir_cli, final_output_filename_for_compilation)
    if comp_config.verbose:
        print(f"Output file will be: {comp_config.output_file_path}")

    if comp_config.project_path:
        try:
            cli_module_path = sys.modules[f"{package_name_str}.cli"].__file__
            if cli_module_path:
                abs_script_path = os.path.abspath(cli_module_path)
                if os.path.commonpath(
                    [abs_script_path,
                     comp_config.project_path]) == comp_config.project_path:
                    script_rel_path = os.path.relpath(abs_script_path,
                                                      comp_config.project_path)
                    comp_config.additional_path_permanent_exclusions.add(
                        script_rel_path.replace(os.sep, '/'))
        except (KeyError, AttributeError, TypeError, ValueError):
            if sys.argv and sys.argv[0] and sys.argv[0].endswith(".py"):
                potential_script_path = os.path.abspath(sys.argv[0])
                if os.path.commonpath(
                    [potential_script_path,
                     comp_config.project_path]) == comp_config.project_path:
                    try:
                        script_rel_path = os.path.relpath(
                            potential_script_path, comp_config.project_path)
                        comp_config.additional_path_permanent_exclusions.add(
                            script_rel_path.replace(os.sep, '/'))
                    except ValueError:
                        pass

    if args.save:
        if args.config:
            print("Warning: --save option is ignored when --config is used.")
        else:
            if not yaml_mod: yaml_mod = ensure_pyyaml_module()
            print("Processing --save flag...")
            _save_config_for_cli(args, yaml_mod, output_dir_cli,
                                 output_base_name_no_ext)
            print(
                f"Proceeding with compilation using the current arguments...")

    result = generate_compiled_output(comp_config)

    if result.success:
        print("\\n" + "-" * 40)
        if args.save and not args.config:
            print(f"Configuration saved previously during this run.")
        print(f"Compilation completed successfully.")
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
            print("Token count estimation failed or skipped.")
        print("-" * 40)
    else:
        print(f"\\nError during compilation: {result.error_message}")
        sys.exit(1)


if __name__ == "__main__":
    run_cli()
