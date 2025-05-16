# codexify/codexify/cli.py
import os
import sys
import argparse
import fnmatch # For CLI YAML config name check
from typing import Dict, Any # Added Any for yaml_module
from .types import CompilationConfig # Import direct

from .main import generate_compiled_output, CompilationConfig
from .core.dependencies import ensure_pyyaml_module
from .core.common import CONFIG_FILE_PATTERN, DEFAULT_OUTPUT_BASENAME
from .core.file_system import get_parent_folder_name


def _load_config_from_yaml_for_cli(config_file_path: str, yaml_module: Any) -> Dict[str, Any]:
    """Loads configuration from a YAML file for CLI use."""
    try:
        abs_config_path = os.path.abspath(config_file_path)
        config_basename = os.path.basename(config_file_path)
        if not (config_basename.lower().endswith('.yaml') or config_basename.lower().endswith('.yml')):
             print(f"Warning: Config file '{config_file_path}' does not end with .yaml or .yml.")
        if not fnmatch.fnmatch(config_basename, CONFIG_FILE_PATTERN):
             print(f"Warning: Config file name '{config_basename}' doesn't match expected pattern '{CONFIG_FILE_PATTERN}'.")

        with open(abs_config_path, 'r', encoding='utf-8') as f:
             loaded_config = yaml_module.safe_load(f)
        if not loaded_config:
            print(f"Error: Config file '{config_file_path}' is empty or invalid YAML."); sys.exit(1)

        config_dir = os.path.dirname(abs_config_path)

        if 'path' in loaded_config and loaded_config['path'] is not None:
            loaded_config['path'] = os.path.normpath(os.path.join(config_dir, loaded_config['path']))
        if 'gitignore' in loaded_config and loaded_config['gitignore'] is not None:
            loaded_config['gitignore'] = os.path.normpath(os.path.join(config_dir, loaded_config['gitignore']))

        if loaded_config.get('path') and 'extensions' not in loaded_config:
            print("Config Error: 'extensions' field is required when 'path' is specified."); sys.exit(1)
        if not loaded_config.get('path') and not loaded_config.get('packages'):
             print("Config Error: Config must contain at least one of 'path' or 'packages'."); sys.exit(1)

        return {
            "project_path": loaded_config.get('path'),
            "extensions": loaded_config.get('extensions', []),
            "go_packages": loaded_config.get('packages', []),
            "output_base_name": loaded_config.get('output', DEFAULT_OUTPUT_BASENAME),
            "exclude_dirs": loaded_config.get('exclude', []),
            "exclude_files": loaded_config.get('exclude_files', []),
            "gitignore_file_path": loaded_config.get('gitignore'),
            "config_source_dir": config_dir
        }
    except FileNotFoundError: print(f"Error: Config file not found: '{config_file_path}'"); sys.exit(1)
    except Exception as e: print(f"Error loading or parsing config file '{config_file_path}': {e}"); sys.exit(1)


def _save_config_for_cli(args: argparse.Namespace, yaml_module: Any, determined_output_dir: str, output_base_name: str) -> str:
    """Saves CLI arguments to a YAML configuration file."""
    config_data: Dict[str, Any] = {}
    if not args.path and not args.packages:
        print("Error: Cannot use --save without providing either --path or --packages."); sys.exit(1)
    if args.path and not args.extensions:
        print("Error: --extensions are required when specifying --path with --save."); sys.exit(1)

    config_name_base = args.config_name if args.config_name else (get_parent_folder_name(args.path) if args.path else "output")
    config_basename_final = f"config.compiled.{config_name_base}.yaml"
    config_filename = os.path.abspath(os.path.join(determined_output_dir, config_basename_final))
    config_file_actual_dir = os.path.dirname(config_filename)
    print(f"Determined config file path for saving: {config_filename}")

    path_relative_to_config = None
    if args.path:
        try: path_relative_to_config = os.path.relpath(os.path.abspath(args.path), config_file_actual_dir)
        except ValueError: path_relative_to_config = os.path.abspath(args.path)

    gitignore_relative_to_config = None
    if args.gitignore:
        try: gitignore_relative_to_config = os.path.relpath(os.path.abspath(args.gitignore), config_file_actual_dir)
        except ValueError: gitignore_relative_to_config = os.path.abspath(args.gitignore)

    config_data['path'] = path_relative_to_config if args.path else None
    config_data['extensions'] = args.extensions if args.extensions else []
    config_data['output'] = output_base_name
    config_data['packages'] = args.packages if args.packages else []
    config_data['exclude'] = args.exclude if args.exclude else []
    config_data['exclude_files'] = args.exclude_files if args.exclude_files else []
    config_data['gitignore'] = gitignore_relative_to_config

    print(f"Attempting to save configuration to: {config_filename}")
    try:
        os.makedirs(config_file_actual_dir, exist_ok=True)
        with open(config_filename, 'w', encoding='utf-8') as f:
            yaml_module.safe_dump(config_data, f, default_flow_style=None, sort_keys=False, allow_unicode=True)
        print(f"Configuration successfully saved to '{config_filename}'.")
    except Exception as e: print(f"Error: Failed to save configuration to '{config_filename}': {e}"); sys.exit(1)
    return config_filename

def run_cli():
    """Handles CLI argument parsing and orchestrates the compilation."""
    # Use a fixed package name string here or import it if defined as a constant elsewhere
    package_name_str = "codexify"

    script_filename = os.path.basename(sys.argv[0] if sys.argv else package_name_str)
    parser = argparse.ArgumentParser(
        description="Codexify: Compiles project files into structured text for LLM context.",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=f"Example:\n  python3 -m {package_name_str}.cli --path ../p --ext .py --save\n  {package_name_str} --path ../p --ext .py",
        add_help=False
    )
    parser.add_argument('-h', '--help', action='help', default=argparse.SUPPRESS, help='Show this help message and exit.')
    parser.add_argument("--save", action='store_true', help="Save CLI args to 'config.compiled.<name>.yaml' and compile.")
    parser.add_argument("--config", help=f"Path to YAML config file (e.g., {CONFIG_FILE_PATTERN.replace('*', 'name')}).")
    parser.add_argument("--path", help="Directory to explore.")
    parser.add_argument("--extensions", "--ext", nargs='+', help="File extensions for content compilation from --path.")
    parser.add_argument("--packages", nargs='+', help="Go package path(s) to include.")
    parser.add_argument("--output", help="Base name for output file. If a path, its dirname is used for output dir. Default: 'compiled.<path_parent_or_output>.txt'.")
    parser.add_argument("--config-name", help="Base name for config file (e.g., 'myproj'). Used with --save.")
    parser.add_argument("--exclude", nargs="*", default=[], help="Dir names to exclude from content in --path.")
    parser.add_argument("--exclude-files", nargs="*", default=[], help="File names to exclude from content in --path.")
    parser.add_argument("--gitignore", help="Path to .gitignore file for --path processing.")
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress verbose output from core logic.")

    try:
        # Dynamically import version from within the package
        version_str = __import__(f"{package_name_str}.version", fromlist=['__version__']).__version__
    except ImportError:
        version_str = "unknown" # Fallback if package structure not fully set up
    parser.add_argument('--version', action='version', version=f'%(prog)s {version_str}')

    args = parser.parse_args()

    comp_config = CompilationConfig(verbose=not args.quiet)
    output_base_name_cli: str
    output_dir_cli: str

    yaml_mod = None # Lazy load yaml module
    if args.config:
        if not yaml_mod: yaml_mod = ensure_pyyaml_module()
        cli_loaded_yaml_config = _load_config_from_yaml_for_cli(args.config, yaml_mod)
        comp_config.project_path = cli_loaded_yaml_config["project_path"]
        comp_config.extensions = cli_loaded_yaml_config["extensions"]
        comp_config.go_packages = cli_loaded_yaml_config["go_packages"]
        comp_config.exclude_dirs = cli_loaded_yaml_config["exclude_dirs"]
        comp_config.exclude_files = cli_loaded_yaml_config["exclude_files"]
        comp_config.gitignore_file_path = cli_loaded_yaml_config["gitignore_file_path"]
        output_base_name_cli = cli_loaded_yaml_config["output_base_name"]
        output_dir_cli = cli_loaded_yaml_config["config_source_dir"] # Output relative to config file
        print(f"Loaded configuration from: {args.config}")
    else:
        if not args.path and not args.packages:
            parser.error("Either --path or --packages must be specified if not using --config.")
        if args.path and not args.extensions:
            parser.error("--extensions (--ext) are required when --path is specified without --config.")

        comp_config.project_path = args.path
        comp_config.extensions = args.extensions if args.extensions else []
        comp_config.go_packages = args.packages if args.packages else []
        comp_config.exclude_dirs = args.exclude
        comp_config.exclude_files = args.exclude_files
        comp_config.gitignore_file_path = args.gitignore

        if args.output:
            output_base_name_cli = os.path.basename(args.output)
            output_dir_candidate = os.path.dirname(args.output)
            if output_dir_candidate: # --output was a path
                output_dir_cli = os.path.abspath(output_dir_candidate)
            elif comp_config.project_path: # --output was just a name, use project_path dir
                output_dir_cli = os.path.abspath(comp_config.project_path)
            else: # --output was just a name, no project_path, use CWD
                output_dir_cli = os.getcwd()
        else: # No --output arg, derive from project_path or use default
            parent_folder_name = get_parent_folder_name(comp_config.project_path) if comp_config.project_path else None
            output_base_name_cli = f"{parent_folder_name}.txt" if parent_folder_name else DEFAULT_OUTPUT_BASENAME
            if comp_config.project_path:
                output_dir_cli = os.path.abspath(comp_config.project_path)
            else: # No project_path, output to CWD
                output_dir_cli = os.getcwd()
        print("Using command-line arguments for configuration.")

    final_output_filename_cli = "compiled." + output_base_name_cli
    comp_config.output_file_path = os.path.join(output_dir_cli, final_output_filename_cli)
    if comp_config.verbose: print(f"Output file will be: {comp_config.output_file_path}")

    # Exclude the CLI script itself if it's within the processed project_path
    if comp_config.project_path:
        abs_project_path = os.path.abspath(comp_config.project_path)
        try:
            # This attempts to find the installed location of the cli.py module
            # It assumes that if the script is run, 'codexify.cli' is in sys.modules
            cli_module_path = sys.modules[f"{package_name_str}.cli"].__file__
            if cli_module_path: # Check if __file__ is not None
                abs_script_path = os.path.abspath(cli_module_path)
                # Check if the found script path is within the project path being processed
                if os.path.commonpath([abs_script_path, abs_project_path]) == abs_project_path:
                    script_rel_path = os.path.relpath(abs_script_path, abs_project_path)
                    comp_config.additional_path_permanent_exclusions.add(script_rel_path.replace(os.sep, '/'))
        except (KeyError, AttributeError, TypeError, ValueError): # Added ValueError for relpath
             # Fallback if module inspection fails (e.g. when run directly as __main__ from source tree)
            if sys.argv and sys.argv[0] and sys.argv[0].endswith(".py"):
                 potential_script_path = os.path.abspath(sys.argv[0])
                 if os.path.commonpath([potential_script_path, abs_project_path]) == abs_project_path:
                    try:
                        script_rel_path = os.path.relpath(potential_script_path, abs_project_path)
                        comp_config.additional_path_permanent_exclusions.add(script_rel_path.replace(os.sep, '/'))
                    except ValueError: # Paths might be on different drives
                        pass


    if args.save:
        if args.config:
            print("Warning: --save option is ignored when --config is used.")
        else:
            if not yaml_mod: yaml_mod = ensure_pyyaml_module()
            print("Processing --save flag...")
            _save_config_for_cli(args, yaml_mod, output_dir_cli, output_base_name_cli)
            print(f"Proceeding with compilation using the current arguments...")

    result = generate_compiled_output(comp_config)

    if result.success:
        print("\\n" + "-" * 40)
        if args.save and not args.config: print(f"Configuration saved previously during this run.")
        print(f"Compilation completed successfully.")
        if result.output_file_path:
            print(f"Output file: {result.output_file_path}")
        print(f"Included content from {result.files_compiled_count} file(s).")
        if result.files_skipped_count > 0:
            print(f"Skipped {result.files_skipped_count} file(s) during content processing.")
        if result.token_count > 0:
            print(f"Estimated token count (cl100k_base): {result.token_count}")
        else: print("Token count estimation failed or skipped.")
        print("-" * 40)
    else:
        print(f"\\nError during compilation: {result.error_message}")
        sys.exit(1)

if __name__ == "__main__":
    run_cli()