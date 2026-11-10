"""Credential-shape detection shared by the router and the VST receipt builder (U2-3).

Side-effect free (stdlib ``re`` only; no sys.path change). The file is deliberately NOT named
``secrets.py``: ``python tools/uc/router.py`` puts this directory first on ``sys.path`` and such a
file would shadow the standard-library ``secrets`` module. ``router`` re-exports ``has_secret`` and
``_SECRET`` unchanged.
"""

from __future__ import annotations

import re

# Shapes of well-known credentials; text that matches is never copied into a result.
_SECRET = re.compile(
    r"sk_(?:live|test)_[A-Za-z0-9]+|sk-[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{8,}|gh[pousr]_[A-Za-z0-9]{10,}"
    r"|xox[abprs]-[A-Za-z0-9-]+|AIza[0-9A-Za-z_-]{10,}|-----BEGIN"
    r"|(?i:secret|passwd|password|api[_-]?key|token)[=_:-]*[A-Za-z0-9]{8,}")


def has_secret(text: object) -> bool:
    return _SECRET.search(str(text)) is not None
