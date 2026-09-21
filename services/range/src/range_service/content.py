"""Challenge discovery and validation.

A challenge is a directory, not a code path. The service walks `content/` at startup, reads each
`challenge.toml`, and validates it. An invalid challenge is skipped with a loud log line and the
service still starts — a content mistake must not take the lab down in front of a learner, and a
silent skip would be worse than either.

    content/
      02-tenant-isolation/
        01-policy-that-filters-nothing/
          challenge.toml     metadata, controls, observations, flag, source references
          stage-01/*.md      the learning tabs, in filename order
          stage-03/*.md      decision chain and review questions

Metadata is TOML rather than YAML: `tomllib` is in the standard library, and a lab that teaches
people to ask what a dependency can reach should not add a parser it does not need.
"""

from __future__ import annotations

import logging
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger("supportpilot.range.content")

# Tracks are fixed. A challenge naming a track that does not exist is a content error, not a new
# track: the ordering is the curriculum and it is not extended by accident.
TRACKS: dict[int, str] = {
    1: "Identity",
    2: "Tenant isolation",
    3: "Authorization",
    4: "Tool authority",
    5: "Untrusted content",
    6: "Irreversible actions",
    7: "Evidence",
    8: "The control plane",
}

FLAG_KINDS = {"value", "reason", "written"}


class ContentError(Exception):
    """A challenge that cannot be trusted to render correctly."""


@dataclass(frozen=True)
class Tab:
    title: str
    body: str


@dataclass(frozen=True)
class Control:
    """One switch in Stage 02.

    `mutation` is a registry id. The browser posts the id and nothing else — no table, no role, no
    container, no statement. A control whose mutation is not registered fails validation, which is
    what stops content from inventing authority the service does not have.
    """

    mutation: str
    label: str
    detail: str = ""


@dataclass(frozen=True)
class Observation:
    """One button that produces a result panel. Also a registry id, for the same reason."""

    observation: str
    label: str
    detail: str = ""


@dataclass(frozen=True)
class SourceRef:
    path: str
    lines: tuple[int, int]
    highlight: tuple[int, int] | None
    caption: str


@dataclass(frozen=True)
class Flag:
    kind: str
    label: str
    observation: str = ""
    field: str = ""
    reason_code: str = ""
    rubric: tuple[str, ...] = ()


@dataclass(frozen=True)
class Challenge:
    id: str
    track: int
    number: str
    title: str
    points: int
    summary: str
    objective: str
    skip_test: str
    stage_01: tuple[Tab, ...]
    stage_03: tuple[Tab, ...]
    controls: tuple[Control, ...]
    observations: tuple[Observation, ...]
    sources: tuple[SourceRef, ...]
    flag: Flag | None
    hints: tuple[str, ...] = ()
    # What the learner is practising here, and how it connects to securing an agent. Separate from
    # `summary` (which sells the challenge) and `objective` (which says what to do): these two
    # answer "why am I doing this, and what has it got to do with agents" — including for the
    # challenges whose subject is ordinary application security that agents only make sharper.
    purpose: str = ""
    agent_link: str = ""
    directory: Path = field(default=Path("."), compare=False)

    @property
    def track_name(self) -> str:
        return TRACKS[self.track]

    @property
    def ready(self) -> bool:
        """A challenge with no controls cannot be broken yet; it renders, inert."""
        return bool(self.controls)


def _require(data: dict, key: str, kind: type, where: str):
    if key not in data:
        raise ContentError(f"{where}: missing required key '{key}'")
    value = data[key]
    if not isinstance(value, kind):
        raise ContentError(f"{where}: '{key}' must be {kind.__name__}, got {type(value).__name__}")
    return value


def _read_tabs(directory: Path) -> tuple[Tab, ...]:
    """Each .md file is one tab. Filename order is tab order, so `01-`, `02-` is the interface.

    The first line must be a level-1 heading and becomes the tab title; it is then dropped from the
    body so the title is not rendered twice.
    """
    if not directory.is_dir():
        return ()

    tabs: list[Tab] = []
    for path in sorted(directory.glob("*.md")):
        text = path.read_text(encoding="utf-8").strip()
        if not text.startswith("# "):
            raise ContentError(f"{path}: must begin with a level-1 heading, used as the tab title")
        first, _, rest = text.partition("\n")
        tabs.append(Tab(title=first[2:].strip(), body=rest.strip()))
    return tuple(tabs)


def _parse_flag(data: dict | None, where: str) -> Flag | None:
    if data is None:
        return None
    kind = _require(data, "kind", str, where)
    if kind not in FLAG_KINDS:
        raise ContentError(f"{where}: flag kind '{kind}' is not one of {sorted(FLAG_KINDS)}")

    flag = Flag(
        kind=kind,
        label=_require(data, "label", str, where),
        observation=data.get("observation", ""),
        field=data.get("field", ""),
        reason_code=data.get("reason_code", ""),
        rubric=tuple(data.get("rubric", ())),
    )

    # Each kind has to carry what it needs to be checkable. A `value` flag compares against a
    # registered observation rather than a literal in the file: the answer lives in the seed data
    # and the Range asks the database, so a content author cannot get it wrong by retyping it.
    if kind == "value" and not (flag.observation and flag.field):
        raise ContentError(f"{where}: a 'value' flag needs both 'observation' and 'field'")
    if kind == "reason" and not flag.reason_code:
        raise ContentError(f"{where}: a 'reason' flag needs 'reason_code'")
    if kind == "written" and not flag.rubric:
        raise ContentError(f"{where}: a 'written' flag needs a non-empty 'rubric'")
    return flag


def _parse_sources(rows: list, where: str) -> tuple[SourceRef, ...]:
    sources: list[SourceRef] = []
    for row in rows:
        lines = _require(row, "lines", list, where)
        if len(lines) != 2 or not all(isinstance(n, int) for n in lines):
            raise ContentError(f"{where}: 'lines' must be two integers")
        highlight = row.get("highlight")
        if highlight is not None:
            if len(highlight) != 2 or not all(isinstance(n, int) for n in highlight):
                raise ContentError(f"{where}: 'highlight' must be two integers")
            highlight = (highlight[0], highlight[1])
        sources.append(
            SourceRef(
                path=_require(row, "path", str, where),
                lines=(lines[0], lines[1]),
                highlight=highlight,
                caption=row.get("caption", ""),
            )
        )
    return tuple(sources)


def load_challenge(directory: Path) -> Challenge:
    """Read and validate one challenge directory. Raises ContentError on anything unrenderable."""
    manifest = directory / "challenge.toml"
    if not manifest.is_file():
        raise ContentError(f"{directory}: no challenge.toml")

    where = str(manifest)
    try:
        data = tomllib.loads(manifest.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ContentError(f"{where}: {exc}") from exc

    track = _require(data, "track", int, where)
    if track not in TRACKS:
        raise ContentError(f"{where}: track {track} is not one of {sorted(TRACKS)}")

    stage_01 = _read_tabs(directory / "stage-01")
    if not stage_01:
        raise ContentError(f"{directory}: stage-01 has no tabs; a challenge must teach before it breaks")

    challenge = Challenge(
        id=_require(data, "id", str, where),
        track=track,
        number=_require(data, "number", str, where),
        title=_require(data, "title", str, where),
        points=_require(data, "points", int, where),
        summary=_require(data, "summary", str, where),
        objective=_require(data, "objective", str, where),
        skip_test=data.get("skip_test", ""),
        purpose=data.get("purpose", ""),
        agent_link=data.get("agent_link", ""),
        stage_01=stage_01,
        stage_03=_read_tabs(directory / "stage-03"),
        controls=tuple(
            Control(
                mutation=_require(row, "mutation", str, where),
                label=_require(row, "label", str, where),
                detail=row.get("detail", ""),
            )
            for row in data.get("control", [])
        ),
        observations=tuple(
            Observation(
                observation=_require(row, "observation", str, where),
                label=_require(row, "label", str, where),
                detail=row.get("detail", ""),
            )
            for row in data.get("observation", [])
        ),
        sources=_parse_sources(data.get("source", []), where),
        flag=_parse_flag(data.get("flag"), where),
        hints=tuple(data.get("hints", ())),
        directory=directory,
    )

    if len(challenge.hints) > 3:
        raise ContentError(f"{where}: at most three hints; a fourth is an answer wearing a question mark")
    return challenge


def load_all(root: Path) -> list[Challenge]:
    """Discover every challenge under `root`, newest content error loudly skipped.

    Sorted by track then number, which is the order the curriculum intends. Nothing is gated: a
    learner who wants 6.1 first should have it.
    """
    if not root.is_dir():
        logger.error("content root %s does not exist; the Range has nothing to serve", root)
        return []

    challenges: list[Challenge] = []
    seen: dict[str, Path] = {}

    for manifest in sorted(root.glob("*/*/challenge.toml")):
        directory = manifest.parent
        try:
            challenge = load_challenge(directory)
        except ContentError as exc:
            logger.error("SKIPPING CHALLENGE %s: %s", directory.name, exc)
            continue

        if challenge.id in seen:
            logger.error(
                "SKIPPING CHALLENGE %s: id '%s' already used by %s",
                directory.name, challenge.id, seen[challenge.id].name,
            )
            continue

        seen[challenge.id] = directory
        challenges.append(challenge)

    challenges.sort(key=lambda c: (c.track, c.number))
    logger.info("loaded %d challenge(s) from %s", len(challenges), root)
    return challenges
