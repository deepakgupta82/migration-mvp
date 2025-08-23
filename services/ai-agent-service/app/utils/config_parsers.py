# Re-export backend ConfigurationParser for ai-agent-service tools to use
from .. import __package__  # noqa: F401

try:
    # Prefer a local copy if present
    from ._local_config_parsers import ConfigurationParser  # type: ignore
except Exception:
    # Fallback to backend implementation (shared workspace path)
    try:
        import importlib.util, sys, os
        backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'backend', 'app', 'utils', 'config_parsers.py'))
        spec = importlib.util.spec_from_file_location('backend_config_parsers', backend_path)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            sys.modules['backend_config_parsers'] = module
            spec.loader.exec_module(module)
            ConfigurationParser = getattr(module, 'ConfigurationParser')  # type: ignore
        else:
            raise ImportError('Cannot load backend ConfigurationParser module')
    except Exception as e:
        raise ImportError(f"ConfigurationParser unavailable: {e}")
