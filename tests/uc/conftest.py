"""Bootstrap for the unified-core (tools/uc) tests.

The product modules import each other as the top-level package ``uc`` (tools/ on sys.path), so the
tests do the same. tests/uc must therefore be imported in importlib mode (see pytest.ini) or the test
package would shadow ``uc``.
"""

from __future__ import annotations

import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TOOLS = os.path.join(REPO_ROOT, "tools")
for path in (TOOLS, REPO_ROOT):
    if path not in sys.path:
        sys.path.insert(0, path)
