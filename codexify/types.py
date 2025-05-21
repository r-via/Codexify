# File: codexify/types.py
# ------------------------------------------------------------
from typing import List, Optional, Any, Callable, Set
from dataclasses import dataclass, field

@dataclass
class CompilationConfig:
    """
    Configuration settings for the Codexify compilation process.

    Attributes:
        project_path: Optional absolute or relative path to the root directory of the project to analyze.
        extensions: List of file extensions (e.g., [".py", ".md"]) whose content should be included
                    if found within `project_path`.
        go_packages: List of Go package import paths (e.g., ["github.com/gin-gonic/gin"])
                     whose source code should be included.
        output_file_path: Optional absolute or relative path where the compiled text output
                          should be saved. If None, output might be returned directly or not saved.
        exclude_dirs: List of directory names (e.g., ["node_modules", ".venv"]) to exclude from
                      content compilation when processing `project_path`. Their presence might still be
                      noted in the tree structure.
        exclude_files: List of file names (e.g., ["temp.log", ".DS_Store"]) to exclude from
                       content compilation when processing `project_path`.
        gitignore_file_path: Optional path to a .gitignore file to use for filtering files and
                             directories within `project_path`.
        additional_path_permanent_exclusions: A set of file or directory names/patterns that should
                                              always be excluded during local path processing, in addition
                                              to defaults like ".git".
        additional_go_permanent_exclusions: A set of file or directory names/patterns that should
                                            always be excluded during Go package processing.
        tiktoken_module: Optional pre-loaded `tiktoken` module instance. If None, the system
                         will attempt to import or install it.
        parse_gitignore_func: Optional pre-loaded `parse_gitignore` function (e.g., from
                              `gitignore_parser`). If None, the system will attempt to import
                              or install the necessary library.
        verbose: Boolean flag indicating whether to print detailed progress messages during compilation.
    """
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
    parse_gitignore_func: Optional[Callable[[str, Optional[str]], Callable[[str], bool]]] = None
    verbose: bool = True

@dataclass
class CompilationResult:
    """
    Represents the outcome of a Codexify compilation process.

    Attributes:
        success: Boolean indicating whether the compilation was successful.
        compiled_text: The generated compiled text output, if successful.
                       Can be None if `success` is False or if output was only written to a file
                       and not stored in memory by choice.
        token_count: Estimated number of tokens in the `compiled_text`, typically calculated
                     using a tokenizer like tiktoken. 0 if estimation failed or not performed.
        files_compiled_count: The number of files whose content was successfully read and included
                              in the `compiled_text`.
        files_skipped_count: The number of files that were identified for potential inclusion but
                             were skipped (e.g., binary files, read errors).
        output_file_path: The absolute path to the file where the `compiled_text` was saved,
                          if it was saved to a file. None otherwise.
        error_message: A descriptive error message if `success` is False.
    """
    success: bool = False
    compiled_text: Optional[str] = None
    token_count: int = 0
    files_compiled_count: int = 0
    files_skipped_count: int = 0
    output_file_path: Optional[str] = None
    error_message: Optional[str] = None