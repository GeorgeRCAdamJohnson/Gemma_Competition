"""kblib — helper package for the Gemma knowledge-base builder (build_kb.py).

Runtime: CPython 3.13, stdlib only. Network access exists only in kblib.kaggle,
imported solely by `build_kb.py pull`. See ROOT/.kiro/specs/gemma-auditor/design.md.
"""

__all__ = [
    "paths",
    "io",
    "lock",
    "discover",
    "kernellog",
    "traces",
    "configs",
    "gold",
    "unidiff",
    "bashpy",
    "reconstruct",
    "harness_edit",
    "gitio",
    "nearmiss",
    "classify",
    "replay",
    "claims",
    "render",
    "verdict",
    "leak",
]
