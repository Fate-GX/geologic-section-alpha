"""Reusable evidence-gated synthetic 3D geology engine."""

__version__ = "0.13.0-stage11-integrity1"

from .config import EngineConfig, load_config
from .topology import GeologicalTopologyGraph

__all__ = ["EngineConfig", "GeologicalTopologyGraph", "load_config"]
