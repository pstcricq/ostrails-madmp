"""The assessment of one DMP against the rules it pins, offline:
``read_document()`` reads it, ``check_conformance()`` checks it,
``has_failures()`` gives the verdict and ``envelope()`` gathers the results.
"""

from madmp.assessment.conformance import (
    STATUSES,
    CheckResult,
    check_conformance,
    envelope,
    has_failures,
    results_to_dicts,
)
from madmp.assessment.document import read_document

__all__ = [
    "STATUSES",
    "CheckResult",
    "check_conformance",
    "envelope",
    "has_failures",
    "read_document",
    "results_to_dicts",
]
