"""Import scripts/load_recalls.py for tests (scripts/ isn't a package)."""
import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location("load_recalls", Path(__file__).parents[1] / "scripts" / "load_recalls.py")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
windows = _mod.windows
