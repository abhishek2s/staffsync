"""Runtime settings that must be applied before numerical libraries load."""

from __future__ import annotations

import os


def configure_numeric_threads() -> None:
    """Limit native numerical-library threads for the Streamlit process."""
    for variable in (
        "OPENBLAS_NUM_THREADS",
        "OMP_NUM_THREADS",
        "MKL_NUM_THREADS",
        "NUMEXPR_NUM_THREADS",
    ):
        os.environ.setdefault(variable, "1")
