"""Draft interoperability format for Minecraft visual-effect accessibility metadata."""

__version__ = "0.1.0"

from .validator import Issue, ValidationReport, validate_file, validate_manifest

__all__ = ["Issue", "ValidationReport", "validate_file", "validate_manifest", "__version__"]
