"""The DMP API: every write assessed, then stored with its assessment, every
DMP read back. ``handle_template()``, ``handle_new_production()`` and
``handle_production_version()`` each do what one write route does, without a
server.
"""

from madmp.api.service import (
    check_document,
    handle_new_production,
    handle_production_version,
    handle_template,
)

__all__ = [
    "check_document",
    "handle_new_production",
    "handle_production_version",
    "handle_template",
]
