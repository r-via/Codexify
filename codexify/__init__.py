# codexify/codexify/__init__.py
from .types import CompilationConfig, CompilationResult # Ajouter cet import
from .main import generate_compiled_output
from .version import __version__

__all__ = [
    "generate_compiled_output",
    "CompilationConfig",       # Maintenant importé de types
    "CompilationResult",       # Maintenant importé de types
    "__version__",
]