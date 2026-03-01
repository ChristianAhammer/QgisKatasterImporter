"""Compatibility wrapper for plugin imports of the shared converter core."""

try:
    from .bev_to_qfield_core import (
        BEVToQField,
        BEVToQFieldConfig,
        _resolve_default_base_path,
        run_standalone,
    )
except ImportError:  # pragma: no cover - direct script execution fallback
    from bev_to_qfield_core import (  # type: ignore
        BEVToQField,
        BEVToQFieldConfig,
        _resolve_default_base_path,
        run_standalone,
    )

__all__ = [
    "BEVToQFieldConfig",
    "BEVToQField",
    "_resolve_default_base_path",
    "run_standalone",
]


if __name__ == "__main__":
    run_standalone()
