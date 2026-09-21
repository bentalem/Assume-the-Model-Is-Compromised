"""Page composition.

Server-rendered, like the approval portal: no build step, no framework, no bundler. Tabs are links
and switches are form posts, so every page works with scripting disabled — the small amount of
JavaScript the Range will grow makes things feel immediate, it does not make them work.
"""

from __future__ import annotations

import html
from collections import defaultdict

from . import source
from . import guide as guide_text
from .content import Challenge, TRACKS
from .markdown import render as md
from .theme import STYLESHEET

# What each track establishes. Shown once at the head of its section, because a learner picking a
# challenge should be able to see what the track is for without opening one.
TRACK_CLAIMS: dict[int, str] = {
    1: "Which token is on the tool call decides the blast radius of everything else.",
    2: "The database is the layer that holds when the code above it is wrong.",
    3: "A policy engine answers; something else has to enforce.",
    4: "A tool is a standing grant to something steerable, not a function.",
    5: "Injection is the delivery method; reachable authority is the vulnerability.",
    6: "For anything that cannot be undone, the control is structure.",
    7: "What you can prove afterwards, and what only looked like proof.",
    8: "What the runtime may change about itself, and where data can leave.",
}

E = lambda text: html.escape(str(text), quote=True)  # noqa: E731 — used constantly, reads better short


def page(title: str, body: str) -> str:
    return (
        "<!doctype html>"
        '<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{E(title)} · The Range</title>"
        f"<style>{STYLESHEET}</style>"
        "</head><body>"
        f'<div class="wrap">{body}</div>'
        "</body></html>"
    )


def masthead(subtitle: str = "") -> str:
    right = f'<span class="tag">{E(subtitle)}</span>' if subtitle else ""
    return (
        '<header class="masthead">'
        '<h1><a href="/">The Range</a></h1>'
        '<span class="tag">SupportPilot</span>'
        '<span class="spacer"></span>'
        f"{right}"
        "</header>"
    )


def footer(note: str) -> str:
    return f'<p class="foot">{E(note)}</p>'


# --------------------------------------------------------------------------------------------------
# Catalogue
# --------------------------------------------------------------------------------------------------

def guide(challenges: list[Challenge]) -> str:
    """The landing page. Everything a learner needs before opening their first challenge.

    The track list is generated from TRACKS and TRACK_CLAIMS rather than written out, and the
    challenge counts are counted, so neither can drift from what is actually loaded.
    """
    per_track: dict[int, int] = defaultdict(int)
    for challenge in challenges:
        per_track[challenge.track] += 1

    rows = ["| | Track | The claim it makes | Challenges |", "|---|---|---|---|"]
    for track in sorted(TRACKS):
        rows.append(
            f"| {track:02d} | {TRACKS[track]} | {TRACK_CLAIMS[track]} | {per_track.get(track, 0)} |"
        )

    body = (
        masthead("start here")
        + md(guide_text.OPENING)
        + md(guide_text.STAGES)
        + md(guide_text.CONSOLE)
        + md(guide_text.FLAGS)
        + md(guide_text.TRACKS_INTRO)
        + md(chr(10).join(rows))
        + md(guide_text.READING)
        + md(guide_text.START)
        + md(guide_text.CLOSING)
        + '<p style="margin:26px 0 0"><a class="cta" href="/">'
        f"Open the catalogue — {len(challenges)} challenges</a></p>"
        + footer("Nothing here knows who you are. There is no scoreboard, and nothing is timed.")
    )
    return body


def catalogue(challenges: list[Challenge]) -> str:
    by_track: dict[int, list[Challenge]] = defaultdict(list)
    for challenge in challenges:
        by_track[challenge.track].append(challenge)

    out = [masthead(f"{len(challenges)} challenges")]
    out.append(
        '<p class="orient">New here? <a href="/guide">Read how to use The Range</a> — how a '
        "challenge is laid out, what the console does, and where to start.</p>"
    )

    if not challenges:
        out.append(
            '<p class="inert-note">No challenge content loaded. The service log names every '
            "directory it skipped and why.</p>"
        )
        return "".join(out)

    for track in sorted(by_track):
        out.append('<section class="track">')
        out.append(
            f'<h2><span class="num">{track:02d}</span> {E(TRACKS[track])}</h2>'
            f'<p class="claim">{E(TRACK_CLAIMS[track])}</p>'
        )
        out.append('<div class="cards">')
        for challenge in by_track[track]:
            inert = "" if challenge.ready else " inert"
            state = "" if challenge.ready else '<span>console not wired yet</span>'
            out.append(
                f'<a class="card{inert}" href="/c/{E(challenge.id)}">'
                f'<span class="head"><span class="id">{E(challenge.number)}</span>'
                f'<span class="title">{E(challenge.title)}</span></span>'
                f'<span class="summary">{E(challenge.summary)}</span>'
                f'<span class="meta"><span>{challenge.points} pts</span>'
                f"<span>{len(challenge.stage_01)} tabs</span>{state}</span>"
                "</a>"
            )
        out.append("</div></section>")

    out.append(
        footer(
            "Progress is kept in this browser. There are no accounts and no scoreboard — "
            "nothing here knows who is playing."
        )
    )
    return "".join(out)


# --------------------------------------------------------------------------------------------------
# One challenge: three stages on one page, in order
# --------------------------------------------------------------------------------------------------

def _tabs(challenge: Challenge, stage: str, tabs, active: int) -> str:
    if len(tabs) <= 1:
        return ""
    links = "".join(
        f'<a href="/c/{E(challenge.id)}?{stage}={index}#{stage}"'
        f'{" aria-current=\"page\"" if index == active else ""}>{E(tab.title)}</a>'
        for index, tab in enumerate(tabs)
    )
    return f'<nav class="tabs">{links}</nav>'


def _stage_01(challenge: Challenge, active: int) -> str:
    tabs = challenge.stage_01
    active = max(0, min(active, len(tabs) - 1))

    skip = ""
    if challenge.skip_test:
        skip = (
            f'<div class="skip"><b>Skip test</b>Skip this stage only if you can already answer: '
            f"{md(challenge.skip_test)[3:-4]}</div>"
        )

    return (
        '<section class="stage" id="stage-01">'
        '<header><span class="num">STAGE 01</span><h2>Learn the mechanism</h2>'
        f'<span class="note">{len(tabs)} tab{"s" if len(tabs) != 1 else ""}</span></header>'
        f"{_tabs(challenge, 'stage-01', tabs, active)}"
        f'<div class="body">{skip}<div class="prose">{md(tabs[active].body)}</div></div>'
        "</section>"
    )


def _result_table(columns: list[str], rows: list[list[str]]) -> str:
    if not rows:
        return "no rows"
    widths = [max(len(column), *(len(row[index]) for row in rows)) for index, column in enumerate(columns)]
    head = "  ".join(column.ljust(widths[index]) for index, column in enumerate(columns))
    rule = "  ".join("-" * width for width in widths)
    body = "\n".join(
        "  ".join(cell.ljust(widths[index]) for index, cell in enumerate(row)) for row in rows
    )
    return f"{head}\n{rule}\n{body}\n\n{len(rows)} row(s)"


def _stage_02(
    challenge: Challenge,
    state: dict[str, str] | None = None,
    result: str = "",
    ran: str = "",
    flag_note: str = "",
    flag_ok: bool | None = None,
) -> str:
    """The console.

    Left: the environment controls and the objective. Right: the result and the flag field.

    The state line is not decoration. A learner who forgets that two controls are still armed spends
    the rest of the session measuring a broken system and drawing conclusions from it, so the panel
    says how many are away from their correct setting, on every render, read from the system.
    """
    if not challenge.controls and not challenge.observations:
        return (
            '<section class="stage" id="stage-02">'
            '<header><span class="num">STAGE 02</span><h2>Break it</h2></header>'
            '<div class="body"><p class="inert-note">This challenge declares no controls yet.</p></div>'
            "</section>"
        )

    state = state or {}
    armed = [mid for mid, value in state.items() if value == "armed"]
    unknown = [mid for mid, value in state.items() if value == "unknown"]

    if unknown:
        banner = (
            '<div class="state unknown"><span class="dot"></span>'
            f"Environment state unreadable for {len(unknown)} control(s) — treat every result below "
            "as unexplained</div>"
        )
    elif armed:
        banner = (
            '<div class="state armed"><span class="dot"></span>'
            f"Environment armed · {len(armed)} change{'s' if len(armed) != 1 else ''} away from correct</div>"
        )
    else:
        banner = (
            '<div class="state held"><span class="dot"></span>'
            "Environment correct · every control at its designed setting</div>"
        )

    controls = ""
    for control in challenge.controls:
        value = state.get(control.mutation, "unknown")
        is_armed = value == "armed"
        action = "restore" if is_armed else "arm"
        label = "Restore" if is_armed else "Arm"
        css = "restore" if is_armed else "arm"
        armed_line = (
            f'<div class="detail" style="color:var(--armed)">Armed: {E(control.detail)}</div>'
            if is_armed
            else f'<div class="detail">{E(control.detail)}</div>'
        )
        controls += (
            '<form method="post" class="control" '
            f'action="/c/{E(challenge.id)}/{action}#stage-02">'
            f'<input type="hidden" name="mutation" value="{E(control.mutation)}">'
            f'<div class="text"><div class="label">{E(control.label)}</div>'
            f"{armed_line}"
            f'<code class="mut">{E(control.mutation)} · {E(value)}</code></div>'
            f'<button type="submit" class="{css}">{label}</button>'
            "</form>"
        )

    observations = "".join(
        '<form method="post" class="control" '
        f'action="/c/{E(challenge.id)}/observe#stage-02">'
        f'<input type="hidden" name="observation" value="{E(obs.observation)}">'
        f'<div class="text"><div class="label">{E(obs.label)}</div>'
        f'<div class="detail">{E(obs.detail)}</div>'
        f'<code class="mut">{E(obs.observation)}</code></div>'
        '<button type="submit">Run</button>'
        "</form>"
        for obs in challenge.observations
    )

    reset = (
        f'<form method="post" action="/c/{E(challenge.id)}/reset#stage-02" style="margin-top:14px">'
        '<button type="submit" class="restore">Reset the environment</button>'
        '<span class="detail" style="margin-left:10px">Restores every control and reports what it '
        "changed.</span></form>"
    )

    flag = ""
    if challenge.flag:
        note = ""
        if flag_note:
            colour = "var(--held)" if flag_ok else "var(--broken)"
            note = f'<p class="detail" style="color:{colour};margin:8px 0 0">{E(flag_note)}</p>'
        flag = (
            f'<form method="post" class="flagform" action="/c/{E(challenge.id)}/flag#stage-02">'
            f'<input type="text" name="answer" placeholder="{E(challenge.flag.label)}" '
            'autocomplete="off">'
            "<button type=\"submit\">Check</button></form>" + note
        )

    ran_line = (
        f'<p class="detail" style="margin:0 0 8px"><code>{E(ran)}</code></p>' if ran else ""
    )

    return (
        '<section class="stage" id="stage-02">'
        '<header><span class="num">STAGE 02</span><h2>Break it</h2></header>'
        f"{banner}"
        '<div class="body">'
        f'<p class="prose"><strong>Objective.</strong> {E(challenge.objective)}</p>'
        '<div class="console">'
        '<div class="panel"><h3>Environment</h3><div class="inner">'
        f"{controls}{observations}{reset}"
        "</div></div>"
        '<div class="panel"><h3>Result</h3><div class="inner">'
        f"{ran_line}"
        f'<div class="result">{E(result) if result else "Nothing run yet."}</div>'
        f"{flag}"
        "</div></div>"
        "</div></div></section>"
    )


def _source_panel(ref) -> str:
    """One source reference, read from the running stack at request time.

    A reference that no longer resolves says so, loudly, in the place the code would have been. The
    alternative — an empty panel — would let the material drift away from the lab without anybody
    noticing, which is the one thing this whole mechanism exists to prevent.
    """
    head = (
        f'<div class="path">{E(ref.path)} · lines {ref.lines[0]}–{ref.lines[1]}'
        f'{" · " + E(ref.caption) if ref.caption else ""}</div>'
    )
    try:
        lines = source.read_lines(ref.path, ref.lines[0], ref.lines[1])
    except source.SourceUnavailable as exc:
        return (
            '<div class="panel source" style="margin-bottom:14px">'
            f"{head}"
            f'<div class="inner"><p class="inert-note">Source unavailable — {E(str(exc))}</p></div>'
            "</div>"
        )

    rows = "".join(
        f'<tr{" class=\"hit\"" if ref.highlight and ref.highlight[0] <= number <= ref.highlight[1] else ""}>'
        f'<td class="n">{number}</td><td>{E(text)}</td></tr>'
        for number, text in lines
    )
    return (
        '<div class="panel source" style="margin-bottom:14px">'
        f"{head}"
        f'<div class="sourcelines"><table><tbody>{rows}</tbody></table></div>'
        "</div>"
    )


def _stage_03(challenge: Challenge, active: int) -> str:
    tabs = challenge.stage_03
    if not tabs and not challenge.sources:
        return ""

    sources = "".join(_source_panel(ref) for ref in challenge.sources)

    body = ""
    if tabs:
        active = max(0, min(active, len(tabs) - 1))
        body = f'<div class="prose">{md(tabs[active].body)}</div>'

    return (
        '<section class="stage" id="stage-03">'
        '<header><span class="num">STAGE 03</span><h2>Understand what you did</h2></header>'
        f"{_tabs(challenge, 'stage-03', tabs, active)}"
        f'<div class="body">{sources}{body}</div>'
        "</section>"
    )


def _hints(challenge: Challenge) -> str:
    if not challenge.hints:
        return ""
    items = "".join(
        f"<details class=\"hint\"><summary>Hint {index + 1}</summary><p>{md(hint)[3:-4]}</p></details>"
        for index, hint in enumerate(challenge.hints)
    )
    return (
        '<section class="stage"><header><span class="num">HINTS</span>'
        "<h2>Questions, not answers</h2>"
        '<span class="note">free, opened in order</span></header>'
        f'<div class="body">{items}</div></section>'
    )


def _why_this_challenge(challenge: Challenge) -> str:
    """The orientation panel, shown before Stage 01.

    A learner arriving at a challenge from the catalogue knows its title and one sentence. That is
    enough to decide whether to open it and not enough to know what they are practising or why it
    belongs in a course about agents. Several challenges here are ordinary application security
    that agents make sharper rather than anything agent-specific, and saying which is which is the
    honest thing to do — a learner who cannot tell will either over-apply the lesson or dismiss it.
    """
    if not challenge.purpose and not challenge.agent_link:
        return ""

    parts = ['<section class="why">']
    if challenge.purpose:
        parts.append(
            '<div><h3>What you are practising</h3>'
            f"{md(challenge.purpose)}</div>"
        )
    if challenge.agent_link:
        parts.append(
            '<div><h3>Why it matters for an agent</h3>'
            f"{md(challenge.agent_link)}</div>"
        )
    parts.append("</section>")
    return "".join(parts)


def challenge_page(
    challenge: Challenge,
    tab_01: int = 0,
    tab_03: int = 0,
    state: dict[str, str] | None = None,
    result: str = "",
    ran: str = "",
    flag_note: str = "",
    flag_ok: bool | None = None,
) -> str:
    body = (
        masthead(f"{challenge.number} · {challenge.track_name}")
        + f'<h2 style="margin:0 0 4px;font-size:1.34rem;letter-spacing:-.015em">{E(challenge.title)}</h2>'
        + f'<p style="margin:0 0 22px;color:var(--muted);max-width:44rem">{E(challenge.summary)}</p>'
        + _why_this_challenge(challenge)
        + _stage_01(challenge, tab_01)
        + _stage_02(challenge, state, result, ran, flag_note, flag_ok)
        + _stage_03(challenge, tab_03)
        + _hints(challenge)
        + footer(f"{challenge.id} · {challenge.points} points · track {challenge.track:02d}")
    )
    return page(challenge.title, body)


def not_found(what: str) -> str:
    return page(
        "Not found",
        masthead()
        + f'<p class="inert-note">{E(what)}</p><p><a href="/">Back to the catalogue</a></p>',
    )
