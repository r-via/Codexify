# codexify/types.py
# ------------------------------------------------------------
from typing import List, Optional, Any, Callable, Set
from dataclasses import dataclass, field


@dataclass
class CompilationConfig:
    """
    Configuration settings for the Codexify compilation process.

    This dataclass holds all parameters required to customize the analysis,
    filtering, and aggregation of codebases.

    Attributes:
        project_paths:
            A list of absolute or relative paths to the root directories of the
            projects/modules to analyze. If multiple paths are provided, they
            will be processed sequentially and combined in the final output.
        extensions:
            List of file extensions (e.g., [".py", ".md", ".ts"]) whose content
            should be included in the output if found within `project_paths`.
        go_packages:
            List of Go package import paths (e.g., ["github.com/gin-gonic/gin"])
            whose source code should be resolved and included.
        output_file_path:
            Optional absolute or relative path where the compiled text output
            should be saved. If None, the output is not written to disk automatically
            (but is still available in CompilationResult).
        exclude_dirs:
            List of directory names (e.g., ["node_modules", ".venv"]) to exclude
            from content compilation. Their presence might still be noted in the
            tree structure with a [Content Omitted] tag.
        exclude_files:
            List of file names (e.g., ["temp.log", ".DS_Store"]) to exclude from
            content compilation.
        gitignore_file_path:
            Optional path to a .gitignore file. If provided, its rules will be
            used to filter files and directories within `project_paths`.
        additional_path_permanent_exclusions:
            A set of file or directory names/patterns that should always be
            completely ignored during local path processing (e.g., ".git"), in
            addition to the default hardcoded exclusions.
        additional_go_permanent_exclusions:
            A set of file or directory names/patterns that should always be
            completely ignored during Go package processing.
        tiktoken_module:
            Optional pre-loaded `tiktoken` module instance. If None, the system
            will attempt to import it dynamically to calculate token counts.
        parse_gitignore_func:
            Optional pre-loaded `parse_gitignore` function (from `gitignore_parser`).
            If None, the system will attempt to import it dynamically.
        verbose:
            Boolean flag indicating whether to print detailed progress messages
            to stdout during compilation.
    """
    project_paths: List[str] = field(default_factory=list)
    extensions: List[str] = field(default_factory=list)
    go_packages: List[str] = field(default_factory=list)
    output_file_path: Optional[str] = None
    exclude_dirs: List[str] = field(default_factory=list)
    exclude_files: List[str] = field(default_factory=list)
    gitignore_file_path: Optional[str] = None
    additional_path_permanent_exclusions: Set[str] = field(default_factory=set)
    additional_go_permanent_exclusions: Set[str] = field(default_factory=set)
    tiktoken_module: Optional[Any] = None
    parse_gitignore_func: Optional[
        Callable[[str, Optional[str]], Callable[[str], bool]]
    ] = None
    verbose: bool = True


@dataclass
class CompilationResult:
    """
    Represents the outcome of a Codexify compilation process.

    This dataclass captures the result of the operation, including the generated
    content, statistics, and potential error messages.

    Attributes:
        success:
            Boolean indicating whether the compilation was successful.
        compiled_text:
            The generated compiled text output containing the tree structures and
            file contents. None if `success` is False.
        token_count:
            Estimated number of tokens in `compiled_text` (using cl100k_base encoding).
            Returns 0 if estimation failed or was skipped.
        files_compiled_count:
            The total number of files whose content was successfully read and
            included in the output.
        files_skipped_count:
            The number of files that matched the extension criteria but were
            skipped during processing (e.g., binary files, read errors).
        output_file_path:
            The absolute path to the file where `compiled_text` was saved.
            None if the output was not saved to a file.
        error_message:
            A descriptive error message if `success` is False, explaining why
            the compilation failed.
    """
    success: bool = False
    compiled_text: Optional[str] = None
    token_count: int = 0
    files_compiled_count: int = 0
    files_skipped_count: int = 0
    output_file_path: Optional[str] = None
    error_message: Optional[str] = None