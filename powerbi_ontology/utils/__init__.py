"""Utility modules for PowerBI Ontology Extractor."""

from powerbi_ontology.utils.pbix_reader import PBIXReader

__all__ = ["PBIXReader"]


def __getattr__(name):
    """Lazy import to avoid circular dependency with ontology_generator."""
    if name == "OntologyVisualizer":
        from powerbi_ontology.utils.visualizer import OntologyVisualizer
        return OntologyVisualizer
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
