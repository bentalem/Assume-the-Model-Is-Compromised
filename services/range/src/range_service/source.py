"""Reading the lab's own source for Stage 03.

Stage 03 shows real code with its real path and line numbers, read from the running stack rather
than retyped into a content file. That is the mechanism that stops the material drifting away from
the system it describes: a challenge whose source reference has moved fails a test instead of
quietly teaching something that is no longer true.

Two things about how the path is handled, because this is a file reader inside a service that is
deliberately over-privileged elsewhere:

  * **No path ever comes from a request.** Stage 03 is rendered from the SourceRef objects the
    challenge already declared at startup. There is no endpoint that takes a path, so there is
    nothing to traverse.
  * **The mount is narrow.** The container sees four directories read-only. `.secrets/` is not
    among them, and neither is anything else at the repository root.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger("supportpilot.range.source")

REPO_ROOT = Path(os.environ.get("RANGE_REPO_DIR", "/repo"))

# The directories mounted into the container. A reference outside these resolves to nothing, which
# is reported as a missing source rather than silently rendering an empty panel.
ALLOWED_PREFIXES = ("database/", "services/", "policy/", "scripts/")


class SourceUnavailable(Exception):
    """The reference does not resolve. Always shown to the learner, never swallowed."""


def read_lines(path: str, first: int, last: int) -> list[tuple[int, str]]:
    """Return [(line number, text)] for an inclusive 1-based range."""
    if not any(path.startswith(prefix) for prefix in ALLOWED_PREFIXES):
        raise SourceUnavailable(f"{path} is outside the directories the Range can read")

    resolved = (REPO_ROOT / path).resolve()
    # Belt and braces. The path is not attacker-controlled, and this still costs one comparison.
    if not str(resolved).startswith(str(REPO_ROOT.resolve())):
        raise SourceUnavailable(f"{path} resolves outside the repository")
    if not resolved.is_file():
        raise SourceUnavailable(f"{path} is not present in this build")

    lines = resolved.read_text(encoding="utf-8", errors="replace").splitlines()
    if first < 1 or last > len(lines) or first > last:
        raise SourceUnavailable(
            f"{path} has {len(lines)} lines; the reference asks for {first}-{last}"
        )
    return [(number, lines[number - 1]) for number in range(first, last + 1)]


def available() -> bool:
    """Whether the repository mount is present at all, so the UI can say so once rather than n times."""
    return REPO_ROOT.is_dir()
