"""Sanningsmataren debate-analysis pipeline.

Artifact formats are specified in docs/debatt-format.md. Each pipeline stage
reads the previous artifact from debatt/data/<debate-id>/ and writes its own,
so any stage can be re-run in isolation.
"""

__version__ = "0.1.0"
