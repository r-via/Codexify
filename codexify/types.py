from typing import List, Optional, Any, Callable, Set # Ajoutez les imports de typing nécessaires
from dataclasses import dataclass, field

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