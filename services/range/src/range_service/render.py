"""Page composition.

Server-rendered, like the approval portal: no build step, no framework, no bundler. Tabs are links
and switches are form posts, so every page works with scripting disabled — the small amount of
JavaScript the Range will grow makes things feel immediate, it does not make them work.
"""

from __future__ import annotations

import html
from collections import defaultdict

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

def catalogue(challenges: list[Challenge]) -> str:
    by_track: dict[int, list[Challenge]] = defaultdict(list)
    for challenge in challenges:
        by_track[challenge.track].append(challenge)

    out = [masthead(f"{len(challenges)} challenges")]

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


def _stage_02(challenge: Challenge) -> str:
    """The console.

    Phase 0 renders it inert: the controls are declared by the content and shown with their registry
    ids, and nothing can be armed because no mutation is registered yet. Showing the ids now is not
    filler — it is the part a reviewer should check, and it makes the next phase a wiring change
    rather than a redesign.
    """
    if not challenge.controls and not challenge.observations:
        return (
            '<section class="stage" id="stage-02">'
            '<header><span class="num">STAGE 02</span><h2>Break it</h2></header>'
            '<div class="body"><p class="inert-note">This challenge declares no controls yet.</p></div>'
            "</section>"
        )

    controls = "".join(
        '<div class="control">'
        f'<div class="text"><div class="label">{E(control.label)}</div>'
        f'<div class="detail">{E(control.detail)}</div>'
        f'<code class="mut">{E(control.mutation)}</code></div>'
        '<button type="button" class="arm" disabled>Arm</button>'
        "</div>"
        for control in challenge.controls
    )

    observations = "".join(
        '<div class="control">'
        f'<div class="text"><div class="label">{E(obs.label)}</div>'
        f'<div class="detail">{E(obs.detail)}</div>'
        f'<code class="mut">{E(obs.observation)}</code></div>'
        '<button type="button" disabled>Run</button>'
        "</div>"
        for obs in challenge.observations
    )

    flag = ""
    if challenge.flag:
        flag = (
            f'<div class="flagform">'
            f'<input type="text" placeholder="{E(challenge.flag.label)}" disabled>'
            '<button type="button" disabled>Check</button></div>'
        )

    return (
        '<section class="stage" id="stage-02">'
        '<header><span class="num">STAGE 02</span><h2>Break it</h2>'
        '<span class="note">objective below</span></header>'
        '<div class="state unknown"><span class="dot"></span>'
        "Environment state unavailable — no mutation is registered yet</div>"
        '<div class="body">'
        f'<p class="prose"><strong>Objective.</strong> {E(challenge.objective)}</p>'
        '<div class="console">'
        '<div class="panel"><h3>Environment</h3><div class="inner">'
        f"{controls}{observations}"
        '<p class="inert-note" style="margin-top:12px">Controls are inert in this build. Each one is '
        "a registry id; the browser will send the id and nothing else — no table, no role, no "
        "container, no statement.</p>"
        "</div></div>"
        '<div class="panel"><h3>Result</h3><div class="inner">'
        '<div class="result">Nothing run yet.</div>'
        f"{flag}"
        "</div></div>"
        "</div></div></section>"
    )


def _stage_03(challenge: Challenge, active: int) -> str:
    tabs = challenge.stage_03
    if not tabs and not challenge.sources:
        return ""

    sources = "".join(
        '<div class="panel source" style="margin-bottom:14px">'
        f'<div class="path">{E(ref.path)} · lines {ref.lines[0]}–{ref.lines[1]}'
        f'{" · " + E(ref.caption) if ref.caption else ""}</div>'
        '<div class="sourcelines"><table><tbody>'
        '<tr><td class="n">—</td><td>source is fetched from the running stack; '
        "not wired in this build</td></tr>"
        "</tbody></table></div></div>"
        for ref in challenge.sources
    )

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


def challenge_page(challenge: Challenge, tab_01: int = 0, tab_03: int = 0) -> str:
    body = (
        masthead(f"{challenge.number} · {challenge.track_name}")
        + f'<h2 style="margin:0 0 4px;font-size:1.34rem;letter-spacing:-.015em">{E(challenge.title)}</h2>'
        + f'<p style="margin:0 0 22px;color:var(--muted);max-width:44rem">{E(challenge.summary)}</p>'
        + _stage_01(challenge, tab_01)
        + _stage_02(challenge)
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
