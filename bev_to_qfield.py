"""Compatibility wrapper for the shared BEV-to-QField converter implementation."""

from bev_to_qfield_plugin.bev_to_qfield_core import (
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
