"""Page composition.

Server-rendered, like the approval portal: no build step, no framework, no bundler. Tabs are links
and switches are form posts, so every page works with scripting disabled — the small amount of
JavaScript here remembers which challenges this browser has solved and offers a theme switch, and
neither of those is load-bearing.

Three pages, one vocabulary:

    /            the landing page: what this is, the eight tracks, and three ways in
    /catalogue   the index: every challenge, as a table per track
    /c/<id>      one challenge: the stage spine, the console, the source

Everything repeated is a function here rather than a shape copied three times — `_strip`,
`_progress_bar`, `_panel`, `_switch` — because the instrument has to look like one instrument.
"""

from __future__ import annotations

import html
from collections import defaultdict

from . import source
from . import guide as guide_text
from .content import Challenge, TRACKS
from .markdown import render as md
from .theme import STYLESHEET

# What each track establishes. Shown at the head of its section, because a learner picking a
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

STAGE_TITLES = ("Learn the mechanism", "Break it", "Understand what you did")
STAGE_VERBS = ("read", "run", "review")

E = lambda text: html.escape(str(text), quote=True)  # noqa: E731 — used constantly, reads better short


def plural(count: int, noun: str, suffix: str = "s") -> str:
    """`3 tabs`, `1 tab`. Written once because it is otherwise written nine times and wrong twice."""
    return f"{count} {noun}{suffix if count != 1 else ''}"


# --------------------------------------------------------------------------------------------------
# Progressive enhancement.
#
# Two jobs, both optional. Without script the page is complete and correct; it simply shows nobody
# as having solved anything, which is the truthful default for a service that keeps no accounts.
# --------------------------------------------------------------------------------------------------

# Restores a chosen theme before first paint. Anything longer than this belongs at the end of the
# body; a page that blocks on script above the fold is a page that can fail to appear.
_THEME_SCRIPT = (
    "try{var t=localStorage.getItem('range.theme');"
    "if(t&&t!=='system'){document.documentElement.setAttribute('data-theme',t);}}catch(e){}"
)

_SCRIPT = """
(function () {
  var KEY = "range.solved.v1";
  function read() {
    try { return JSON.parse(localStorage.getItem(KEY)) || []; } catch (e) { return []; }
  }
  function write(list) {
    try { localStorage.setItem(KEY, JSON.stringify(list)); } catch (e) {}
  }

  var root = document.documentElement;
  var just = root.getAttribute("data-solved-now");
  var solved = read();
  if (just && solved.indexOf(just) < 0) { solved.push(just); write(solved); }
  var set = {};
  for (var i = 0; i < solved.length; i++) { set[solved[i]] = 1; }

  var rows = document.querySelectorAll("[data-cid]");
  var perTrack = {};
  for (var j = 0; j < rows.length; j++) {
    var el = rows[j], done = set[el.getAttribute("data-cid")] ? 1 : 0;
    el.setAttribute("data-solved", done ? "1" : "0");
    var t = el.getAttribute("data-track");
    if (t) { perTrack[t] = (perTrack[t] || 0) + done; }
  }

  var bars = document.querySelectorAll("[data-track-bar]");
  for (var k = 0; k < bars.length; k++) {
    var bar = bars[k];
    var track = bar.getAttribute("data-track-bar");
    var total = parseInt(bar.getAttribute("data-total"), 10) || 0;
    var done = perTrack[track] || 0;
    var fill = bar.querySelector("i"), count = bar.querySelector(".n");
    if (fill) { fill.style.width = (total ? Math.round((done / total) * 100) : 0) + "%"; }
    if (count) { count.textContent = done + "/" + total; }
    bar.className = "bar" + (total && done === total ? " done" : "");
  }

  var counter = document.querySelector("[data-count-solved]");
  if (counter) { counter.firstChild.nodeValue = String(solved.length); }

  // A tab strip that scrolls (below 900px) has to start with the current tab in view, or the
  // section you are reading is the one off the right edge. scrollLeft, never scrollIntoView:
  // this must not move the page.
  var strips = document.querySelectorAll(".tabs");
  for (var ci = 0; ci < strips.length; ci++) {
    var here = strips[ci].querySelector("a[aria-current]");
    if (here && strips[ci].scrollWidth > strips[ci].clientWidth) {
      strips[ci].scrollLeft = Math.max(0, here.offsetLeft - 16);
    }
  }

  // The spine is the primary orientation device on this page and it marked nothing: parked on
  // stage 03, the only mark in it was stage 02's armed rail, pointing at the wrong stage.
  var spineLinks = document.querySelectorAll(".spine a[href^='#']");
  if (spineLinks.length && "IntersectionObserver" in window) {
    var spineMap = {}, spineSecs = [];
    for (var si = 0; si < spineLinks.length; si++) {
      var spineSec = document.getElementById(spineLinks[si].getAttribute("href").slice(1));
      if (spineSec) { spineMap[spineSec.id] = spineLinks[si]; spineSecs.push(spineSec); }
    }
    // Marking only on entry leaves the last mark standing when you scroll back above the first
    // stage — the spine then points at stage 03 from the top of the page. So both directions are
    // recorded, and when nothing is in the band (above the first stage, or below the last) the
    // nearest section to it wins. A section taller than the band always intersects it, so the
    // fallback cannot fire in the middle of one.
    var spineSeen = {};
    var spineMark = function () {
      var band = window.innerHeight * 0.12, pick = null, mi;
      for (mi = 0; mi < spineSecs.length; mi++) {
        if (spineSeen[spineSecs[mi].id]) { pick = spineSecs[mi]; break; }
      }
      if (!pick) {
        var bestGap = Infinity;
        for (mi = 0; mi < spineSecs.length; mi++) {
          var gap = Math.abs(spineSecs[mi].getBoundingClientRect().top - band);
          if (gap < bestGap) { bestGap = gap; pick = spineSecs[mi]; }
        }
      }
      for (var sid in spineMap) { spineMap[sid].removeAttribute("aria-current"); }
      if (pick) { spineMap[pick.id].setAttribute("aria-current", "true"); }
    };
    var spineObs = new IntersectionObserver(function (entries) {
      for (var ei = 0; ei < entries.length; ei++) {
        spineSeen[entries[ei].target.id] = entries[ei].isIntersecting;
      }
      spineMark();
    }, { rootMargin: "-12% 0px -68% 0px" });
    for (var ti = 0; ti < spineSecs.length; ti++) { spineObs.observe(spineSecs[ti]); }
  }

  var slot = document.getElementById("themeslot");
  if (!slot) { return; }
  var button = document.createElement("button");
  button.id = "themeswitch";
  button.type = "button";
  button.setAttribute("aria-live", "polite");
  function label() {
    var t = root.getAttribute("data-theme");
    var word = t === "dark" ? "Dark" : t === "light" ? "Light" : "System";
    button.textContent = word;
    button.setAttribute("aria-label", "Theme: " + word + ". Activate to change.");
  }
  label();
  button.addEventListener("click", function () {
    var order = ["system", "light", "dark"];
    var now = root.getAttribute("data-theme") || "system";
    var next = order[(order.indexOf(now) + 1) % 3];
    if (next === "system") { root.removeAttribute("data-theme"); } else { root.setAttribute("data-theme", next); }
    try { localStorage.setItem("range.theme", next); } catch (e) {}
    label();
  });
  slot.appendChild(button);
})();
"""


def page(title: str, body: str, *, wide: bool = False, solved_now: str = "") -> str:
    stamp = f' data-solved-now="{E(solved_now)}"' if solved_now else ""
    return (
        "<!doctype html>"
        f'<html lang="en"{stamp}><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<meta name="robots" content="noindex">'
        f"<title>{E(title)} · The Range</title>"
        f"<style>{STYLESHEET}</style>"
        f"<script>{_THEME_SCRIPT}</script>"
        "</head><body>"
        '<a class="skiplink" href="#content">Skip to content</a>'
        f'<div class="wrap{" wide" if wide else ""}"><main id="content" tabindex="-1">{body}</main></div>'
        f"<script>{_SCRIPT}</script>"
        "</body></html>"
    )


# --------------------------------------------------------------------------------------------------
# Shared furniture
# --------------------------------------------------------------------------------------------------

def masthead(current: str = "") -> str:
    """The same five elements on every page, in the same order, at the same size."""
    def link(href: str, label: str, key: str) -> str:
        mark = ' aria-current="page"' if key == current else ""
        return f'<a href="{href}"{mark}>{label}</a>'

    return (
        '<header class="masthead">'
        '<p class="mark"><a href="/">The Range</a></p>'
        '<span class="sep" aria-hidden="true"></span>'
        '<span class="lab">SupportPilot lab</span>'
        '<span class="spacer"></span>'
        "<nav>"
        + link("/", "Start", "landing")
        + link("/catalogue", "Catalogue", "catalogue")
        + link("/guide", "How it works", "guide")
        + '<span id="themeslot"></span>'
        "</nav></header>"
    )


def _summarise(state: dict[str, str] | None) -> tuple[str, str, str]:
    """(css class, headline, detail) for a set of probe readings.

    `unknown` outranks `armed` outranks `correct`. A state nobody can read is the worst of the
    three, because every measurement taken under it is unexplained rather than merely wrong.
    """
    if not state:
        return ("", "", "")
    unknown = sorted(mid for mid, value in state.items() if value == "unknown")
    armed = sorted(mid for mid, value in state.items() if value == "armed")
    if unknown:
        return (
            "unknown",
            "State unreadable · " + plural(len(unknown), "control"),
            ", ".join(unknown),
        )
    if armed:
        return (
            "armed",
            "Armed · " + plural(len(armed), "control") + " away from correct",
            ", ".join(armed),
        )
    return ("held", f"Correct · all {len(state)} controls at their designed setting", "")


def _strip(state: dict[str, str] | None, *, reset_for: str = "", anchor: str = "") -> str:
    """The status band under the masthead. One object, three colours, hatched when not correct."""
    css, headline, ids = _summarise(state)
    if not css:
        return (
            '<div class="strip"><span class="dot"></span>'
            "<b>Environment</b><span>not readable from here</span></div>"
        )
    reset = ""
    if reset_for:
        reset = (
            f'<form method="post" action="/c/{E(reset_for)}/reset{anchor}">'
            '<button type="submit" class="small restore">Reset the lab</button></form>'
        )
    return (
        f'<div class="strip {css}"><span class="dot"></span>'
        f"<b>Environment</b><span>{E(headline)}</span>"
        f'<span class="fill"></span>'
        + (f'<span class="ids">{E(ids)}</span>' if ids else "")
        + reset
        + "</div>"
    )


def _progress_bar(track: int, total: int, done: int = 0) -> str:
    """Solved-count for one track. Rendered at `done`, then corrected by script from this browser."""
    pct = round((done / total) * 100) if total else 0
    css = "bar done" if total and done == total else "bar"
    return (
        f'<span class="{css}" data-track-bar="{track}" data-total="{total}">'
        f'<span class="track"><i style="width:{pct}%"></i></span>'
        f'<span class="n">{done}/{total}</span></span>'
    )


def footer(*items: str) -> str:
    cells = "".join(f"<span>{E(item)}</span>" for item in items if item)
    return f'<footer class="foot">{cells}<span class="fill"></span><span>no accounts · no scoreboard · no timer</span></footer>'


def _panel(title: str, inner: str, *, side: str = "", flush: bool = False) -> str:
    side_html = f'<span class="fill"></span><span class="side">{E(side)}</span>' if side else ""
    klass = "inner flush" if flush else "inner"
    return (
        f'<section class="panel"><h3>{E(title)}{side_html}</h3>'
        f'<div class="{klass}">{inner}</div></section>'
    )


# --------------------------------------------------------------------------------------------------
# The landing page
#
# Three jobs in one screen: say what this is, show the eight tracks and what each one establishes,
# and put the learner in a challenge. So: no hero. The masthead, a three-line statement beside a
# live readout of the lab, then the eight tracks as a table, then three named ways in.
#
# Every number on it is counted rather than written down, and the environment line is a probe
# reading rather than an assumption — a landing page that says "correct" while the lab is armed
# would be the first lie the course tells.
# --------------------------------------------------------------------------------------------------

def _find(challenges: list[Challenge], number: str) -> Challenge | None:
    for challenge in challenges:
        if challenge.number == number:
            return challenge
    return None


def _route(key: str, blurb: str, challenge: Challenge | None, fallback: str) -> str:
    if challenge is None:
        target, label = "/catalogue", fallback
    else:
        target = f"/c/{E(challenge.id)}"
        label = f"{challenge.number} · {challenge.title}"
    return (
        f'<div class="route"><span class="k">{E(key)}</span>'
        f"<p>{E(blurb)}</p>"
        f'<a class="go" href="{target}"><span>{E(label)}</span>'
        '<span class="arrow" aria-hidden="true">&rarr;</span></a></div>'
    )


def landing(
    challenges: list[Challenge],
    state: dict[str, str] | None = None,
    solved: frozenset[str] = frozenset(),
) -> str:
    per_track: dict[int, list[Challenge]] = defaultdict(list)
    for challenge in challenges:
        per_track[challenge.track].append(challenge)

    total = len(challenges)
    points = sum(challenge.points for challenge in challenges)
    css, _headline, _ids = _summarise(state)
    # The strip above already sounds the alarm; this row is the reading behind it.
    off = sum(1 for value in (state or {}).values() if value != "correct")
    state_word = f"{off} / {len(state)}" if state else "unknown"

    first = _find(challenges, "1.1")
    start_href = f"/c/{E(first.id)}" if first else "/catalogue"

    readout = (
        '<aside class="readout">'
        '<div class="row"><span class="k">Challenges</span>'
        f'<span class="v">{total}</span></div>'
        '<div class="row"><span class="k">Tracks</span>'
        f'<span class="v">{len(TRACKS)}</span></div>'
        '<div class="row"><span class="k">Points on offer</span>'
        f'<span class="v">{points:,}</span></div>'
        '<div class="row"><span class="k">Solved here</span>'
        f'<span class="v" data-count-solved>{len(solved)}<span class="u"> / {total}</span></span></div>'
        f'<div class="row state {css or "unknown"}"><span class="k">Controls off-nominal</span>'
        f'<span class="v">{E(state_word)}</span></div>'
        "</aside>"
    )

    # The right rail carries the reading, the way in, and the legend for the three state words.
    # Those three belong together: the readout states a condition, the legend says what the
    # condition means, and the buttons are what you do about it.
    rail = (
        '<div class="rail">'
        + readout
        + '<div class="go">'
        f'<a class="btn primary" href="{start_href}">Start at 1.1</a>'
        f'<a class="btn quiet" href="/catalogue">All {total} challenges</a>'
        "</div>"
        '<dl class="key">'
        '<div><span class="sw held" aria-hidden="true"></span><dt>Correct</dt>'
        "<dd>every control at its designed setting</dd></div>"
        '<div><span class="sw armed" aria-hidden="true"></span><dt>Armed</dt>'
        "<dd>a control is deliberately in its wrong setting</dd></div>"
        '<div><span class="sw unknown" aria-hidden="true"></span><dt>Unreadable</dt>'
        "<dd>the probe could not tell, so no reading is trustworthy</dd></div>"
        "</dl></div>"
    )

    lede = (
        '<div class="lede"><div>'
        '<span class="eyebrow">Practice range · securing AI agents</span>'
        f"<h1>{E(guide_text.LANDING_TITLE)}</h1>"
        f'<p class="standfirst">{E(guide_text.LANDING_STANDFIRST)}</p>'
        f'<p class="sub">{E(guide_text.LANDING_SUB_1)}</p>'
        f'<p class="sub">{E(guide_text.LANDING_SUB_2)}</p>'
        "</div>"
        f"{rail}</div>"
    )

    rows = []
    for track in sorted(TRACKS):
        here = per_track.get(track, [])
        done = sum(1 for challenge in here if challenge.id in solved)
        rows.append(
            f'<tr data-track="{track}">'
            f'<td class="id">{track:02d}</td>'
            f'<td class="name"><a href="/catalogue#track-{track}">{E(TRACKS[track])}</a></td>'
            f'<td class="claim">{E(TRACK_CLAIMS[track])}</td>'
            f'<td class="n">{len(here)}</td>'
            f'<td class="n">{_progress_bar(track, len(here), done)}</td>'
            "</tr>"
        )
    # The per-challenge markers the script needs to recount this browser's progress per track.
    markers = "".join(
        f'<span data-cid="{E(challenge.id)}" data-track="{challenge.track}" hidden></span>'
        for challenge in challenges
    )

    tracks_section = (
        '<section class="sec">'
        "<h2>The eight tracks</h2>"
        '<p class="note">Each track makes one claim. The challenges inside it are the evidence '
        "for that claim, and they are meant to be read in order the first time.</p>"
        '<div class="scroller"><table class="index">'
        '<thead><tr><th scope="col">№</th><th scope="col">Track</th>'
        '<th scope="col">The claim it makes</th>'
        '<th class="num" scope="col">Ch.</th><th class="num" scope="col">Solved</th></tr></thead>'
        f"<tbody>{''.join(rows)}</tbody></table></div>{markers}</section>"
    )

    routes = (
        '<section class="sec"><h2>Three ways in</h2>'
        '<p class="note">Nothing is gated and nothing is timed. A learner who wants 6.1 first '
        "should have it.</p>"
        '<div class="routes">'
        + _route("New to this", guide_text.ROUTE_NEW, _find(challenges, "1.1"), "Open the catalogue")
        + _route("Short of time", guide_text.ROUTE_SHORT, _find(challenges, "4.1"), "Open the catalogue")
        + _route("Already in security", guide_text.ROUTE_PRO, _find(challenges, "7.3"), "Open the catalogue")
        + "</div></section>"
    )

    stages = "".join(
        '<div class="route">'
        f'<span class="k">Stage {index + 1:02d} · {E(STAGE_TITLES[index])}</span>'
        f"<p>{E(text)}</p></div>"
        for index, text in enumerate(guide_text.STAGE_LINES)
    )
    how = (
        '<section class="sec"><h2>How a challenge works</h2>'
        f'<p class="note">Every one of the {total} is laid out the same way, and the order is '
        "deliberate: you cannot learn anything from breaking something you did not understand "
        'first. <a href="/guide">The long version</a> covers the console, the three kinds of flag '
        "and what the service is allowed to do.</p>"
        f'<div class="routes flat">{stages}</div></section>'
    )

    return (
        masthead("landing")
        + _strip(state)
        + lede
        + tracks_section
        + routes
        + how
        + footer(f"{total} challenges", f"{points:,} points", "progress is kept in this browser")
    )


# --------------------------------------------------------------------------------------------------
# The catalogue
# --------------------------------------------------------------------------------------------------

def catalogue(
    challenges: list[Challenge],
    state: dict[str, str] | None = None,
    solved: frozenset[str] = frozenset(),
) -> str:
    by_track: dict[int, list[Challenge]] = defaultdict(list)
    for challenge in challenges:
        by_track[challenge.track].append(challenge)

    out = [masthead("catalogue"), _strip(state)]
    out.append(
        '<div class="chead">'
        '<span class="eyebrow">Catalogue</span>'
        f"<h1>{len(challenges)} challenges, eight tracks</h1>"
        '<p class="summary">Every challenge in the range, in curriculum order. Nothing is locked. '
        'If you have not used this before, <a href="/guide">read how it works</a> first — it is '
        "four minutes and it explains the console.</p></div>"
    )

    if not challenges:
        out.append(
            '<p class="inert-note">No challenge content loaded. The service log names every '
            "directory it skipped and why.</p>"
        )
        out.append(footer("0 challenges"))
        return "".join(out)

    # Eight tracks over four thousand pixels of rows. The nav is the only way to move between
    # them without a scrollbar, and it doubles as the page's own contents list.
    out.append(
        '<nav class="tracknav" aria-label="Tracks">'
        + "".join(
            f'<a href="#track-{track}"><span class="n">{track:02d}</span>'
            f"<span>{E(TRACKS[track])}</span></a>"
            for track in sorted(by_track)
        )
        + "</nav>"
    )

    for track in sorted(by_track):
        here = by_track[track]
        done = sum(1 for challenge in here if challenge.id in solved)
        rows = []
        for challenge in here:
            inert = "" if challenge.ready else " inert"
            # A challenge with no controls has no console yet. Say that in the Console column
            # rather than greying out its title, which made a working link look disabled.
            console = (
                plural(len(challenge.controls), "control")
                if challenge.controls
                else "no console yet"
            )
            klass = f' class="{inert.strip()}"' if inert.strip() else ""
            rows.append(
                f'<tr{klass} data-cid="{E(challenge.id)}" '
                f'data-track="{challenge.track}" '
                f'data-solved="{"1" if challenge.id in solved else "0"}">'
                f'<td class="id">{E(challenge.number)}</td>'
                f'<td class="name"><a href="/c/{E(challenge.id)}">{E(challenge.title)}</a></td>'
                f'<td class="what">{E(challenge.summary)}</td>'
                f'<td class="n">{console}</td>'
                f'<td class="n">{challenge.points}</td>'
                "</tr>"
            )
        out.append(
            f'<section class="trackblock" id="track-{track}">'
            f'<div class="band"><span class="n">{track:02d}</span>'
            f"<h2>{E(TRACKS[track])}</h2>"
            '<span class="fill"></span>'
            f'<span class="count">{_progress_bar(track, len(here), done)}</span></div>'
            f'<p class="claimline">{E(TRACK_CLAIMS[track])}</p>'
            '<div class="scroller"><table class="index">'
            '<thead><tr><th scope="col">№</th><th scope="col">Challenge</th>'
            '<th scope="col">What it is</th>'
            '<th class="num" scope="col">Console</th><th class="num" scope="col">Pts</th></tr></thead>'
            f"<tbody>{''.join(rows)}</tbody></table></div></section>"
        )

    out.append(
        footer(
            f"{len(challenges)} challenges",
            "progress is kept in this browser",
            "nothing here knows who is playing",
        )
    )
    return "".join(out)


# --------------------------------------------------------------------------------------------------
# The long-form guide
# --------------------------------------------------------------------------------------------------

def guide(challenges: list[Challenge]) -> str:
    """How to use The Range. The track list is generated, so it cannot drift from what loaded."""
    per_track: dict[int, int] = defaultdict(int)
    for challenge in challenges:
        per_track[challenge.track] += 1

    rows = ["| | Track | The claim it makes | Challenges |", "|---|---|---|---|"]
    for track in sorted(TRACKS):
        rows.append(
            f"| {track:02d} | {TRACKS[track]} | {TRACK_CLAIMS[track]} | {per_track.get(track, 0)} |"
        )

    body = (
        masthead("guide")
        + '<div class="chead"><span class="eyebrow">Reference</span>'
        + f"<h1>{E(guide_text.GUIDE_TITLE)}</h1>"
        + f'<p class="summary">{E(guide_text.GUIDE_STANDFIRST)}</p></div>'
        + '<div class="prose">'
        + md(guide_text.OPENING)
        + md(guide_text.STAGES)
        + md(guide_text.CONSOLE)
        + md(guide_text.FLAGS)
        + md(guide_text.TRACKS_INTRO)
        + md(chr(10).join(rows))
        + md(guide_text.READING)
        + md(guide_text.START)
        + md(guide_text.CLOSING)
        + "</div>"
        + '<p style="margin:var(--s-6) 0 0">'
        f'<a class="btn primary" href="/catalogue">Open the catalogue — {len(challenges)} challenges</a> '
        '<a class="btn quiet" href="/">Back to the start</a></p>'
        + footer("nothing here knows who you are", "no scoreboard", "nothing is timed")
    )
    return body


# --------------------------------------------------------------------------------------------------
# One challenge
# --------------------------------------------------------------------------------------------------

def _tabs(challenge: Challenge, stage: str, tabs, active: int) -> str:
    if len(tabs) <= 1:
        return ""
    current = ' aria-current="page"'
    links = "".join(
        f'<a href="/c/{E(challenge.id)}?{stage}={index}#{stage}"'
        f'{current if index == active else ""}>{E(tab.title)}</a>'
        for index, tab in enumerate(tabs)
    )
    number = int(stage.rsplit("-", 1)[-1])
    named = f"Sections of stage {number:02d}, {STAGE_TITLES[number - 1]}"
    return f'<nav class="tabs" aria-label="{E(named)}">{links}</nav>'


def _stage_head(number: int, note: str = "", extra: str = "") -> str:
    return (
        "<header>"
        f'<span class="n">{number:02d}</span>'
        f"<h2>{E(STAGE_TITLES[number - 1])}</h2>"
        f'<span class="verb">{E(STAGE_VERBS[number - 1])}</span>'
        '<span class="fill"></span>'
        + (f'<span class="note">{E(note)}</span>' if note else "")
        + extra
        + "</header>"
    )


def _challenge_state(challenge: Challenge, state: dict[str, str] | None) -> dict[str, str]:
    """Only this challenge's controls. The masthead strip carries the whole lab; a stage carries
    what it can itself change, because those are different questions."""
    state = state or {}
    return {control.mutation: state.get(control.mutation, "unknown") for control in challenge.controls}


def _stage_01(challenge: Challenge, active: int) -> str:
    tabs = challenge.stage_01
    active = max(0, min(active, len(tabs) - 1))

    skip = ""
    if challenge.skip_test:
        skip = (
            '<div class="skip"><b>Skip test</b>'
            f"<p>Skip this stage only if you can already answer: {md(challenge.skip_test)[3:-4]}</p>"
            "</div>"
        )

    note = plural(len(tabs), "tab") if len(tabs) > 1 else ""
    return (
        '<section class="stage" id="stage-01">'
        + _stage_head(1, note)
        + _tabs(challenge, "stage-01", tabs, active)
        + f'<div class="body">{skip}<div class="prose">{md(tabs[active].body)}</div></div>'
        + "</section>"
    )


def _result_table(columns: list[str], rows: list[list[str]]) -> str:
    """Observation output, laid out as fixed-width columns for the terminal panel."""
    if not rows:
        return "no rows"
    widths = [max(len(column), *(len(row[index]) for row in rows)) for index, column in enumerate(columns)]
    head = "  ".join(column.ljust(widths[index]) for index, column in enumerate(columns))
    rule = "  ".join("-" * width for width in widths)
    body = "\n".join(
        "  ".join(cell.ljust(widths[index]) for index, cell in enumerate(row)) for row in rows
    )
    return f"{head}\n{rule}\n{body}\n\n{len(rows)} row(s)"


def _switch(action_url: str, field: str, value: str, label: str, detail: str, mono: str,
            button: str, button_css: str, row_state: str = "") -> str:
    """One row of the environment panel. Controls and observations are the same object, because
    to a learner they are the same gesture: press a labelled thing, read what the lab says back.

    The `data-` attributes are the machine-readable half of this row, and they are deliberate:
    `scripts/range_suite.py` reads a control's probe state off the rendered page — what the learner
    actually sees — and it should key on an attribute that exists for that purpose rather than on
    the punctuation inside a label, which is how it broke the last time this markup was touched.
    """
    attr = f' data-{E(field)}="{E(value)}"'
    if row_state:
        attr += f' data-state="{E(row_state)}"'
    press = f' class="{E(button_css)}"' if button_css else ""
    return (
        f'<form method="post" class="control"{attr} action="{action_url}">'
        f'<input type="hidden" name="{E(field)}" value="{E(value)}">'
        f'<div class="text"><div class="label">{E(label)}</div>'
        + (f'<div class="detail">{E(detail)}</div>' if detail else "")
        + f'<code class="mut">{mono}</code></div>'
        f'<button type="submit"{press} '
        f'aria-label="{E(button)} · {E(label)}">{E(button)}</button>'
        "</form>"
    )


def _stage_02(
    challenge: Challenge,
    state: dict[str, str] | None = None,
    result: str = "",
    ran: str = "",
    flag_note: str = "",
    flag_ok: bool | None = None,
) -> str:
    """The console.

    Left: the environment this challenge can change, and the observations it can run. Right: the
    terminal and the flag.

    The stage's own state is read from the probe on every render and expressed as the shape of the
    section — a thick amber rail and a hatched banner — rather than as a word somewhere in it. A
    learner who forgets that two controls are still armed spends the rest of the session measuring
    a broken system and drawing conclusions from it.
    """
    if not challenge.controls and not challenge.observations:
        return (
            '<section class="stage" id="stage-02">'
            + _stage_head(2)
            + '<div class="body"><p class="inert-note">This challenge declares no controls yet. '
            "The lesson is in stages 01 and 03.</p></div></section>"
        )

    mine = _challenge_state(challenge, state)
    css, headline, _ids = _summarise(mine) if mine else ("", "", "")
    data_state = css or "held"
    # The masthead strip already carries the lab. Repeating its sentence verbatim 2,300px lower
    # taught nothing twice; this one counts only the controls this challenge owns.
    armed_here = sum(1 for value in mine.values() if value == "armed")
    unreadable_here = sum(1 for value in mine.values() if value == "unknown")
    if unreadable_here:
        own = f"{unreadable_here} of {plural(len(mine), 'control')} unreadable"
    elif armed_here:
        own = f"{armed_here} of {plural(len(mine), 'control')} armed"
    else:
        own = f"all {plural(len(mine), 'control')} held"
    banner = (
        f'<div class="strip {css}"><span class="dot"></span><b>This challenge</b>'
        f"<span>{E(own)}</span></div>"
        if css
        else '<div class="strip"><span class="dot"></span><b>This challenge</b>'
             "<span>read-only · nothing here changes the lab</span></div>"
    )

    controls = "".join(
        _switch(
            f"/c/{E(challenge.id)}/{'restore' if mine.get(control.mutation) == 'armed' else 'arm'}#stage-02",
            "mutation",
            control.mutation,
            control.label,
            control.detail,
            f'{E(control.mutation)} · <span class="s">{E(mine.get(control.mutation, "unknown"))}</span>',
            "Restore" if mine.get(control.mutation) == "armed" else "Arm",
            "restore" if mine.get(control.mutation) == "armed" else "arm",
            mine.get(control.mutation, "unknown"),
        )
        for control in challenge.controls
    )

    observations = "".join(
        _switch(
            f"/c/{E(challenge.id)}/observe#result",
            "observation",
            obs.observation,
            obs.label,
            obs.detail,
            E(obs.observation),
            "Run",
            "",
        )
        for obs in challenge.observations
    )

    reset = (
        f'<form method="post" class="reset" action="/c/{E(challenge.id)}/reset#result">'
        '<button type="submit" class="restore">Reset the environment</button>'
        '<span class="detail">Asserts every control in the lab, not only this challenge\'s, and '
        "reports what it had to put back.</span></form>"
    )

    # Rows 1-2 change the lab; rows 3-5 only read it. Nothing in the console said so, and the
    # header counted them together as "switches".
    def _group(label: str, rows: str) -> str:
        return f'<p class="grp">{E(label)}</p>{rows}' if rows else ""

    left = _panel(
        "Environment",
        _group("Controls · these change the lab", controls)
        + _group("Observations · these only read it", observations)
        + reset,
        # No count here: the stage header already carries "N controls · N probes" 300px away,
        # and the two group labels below name what is in each half.
        flush=True,
    )

    flag = ""
    if challenge.flag:
        note = ""
        if flag_note:
            state_css = "ok" if flag_ok else "no"
            word = "Correct" if flag_ok else "Not yet"
            note = f'<p class="flagnote {state_css}"><b>{word}</b><span>{E(flag_note)}</span></p>'
        flag = (
            '<div class="flag"><span class="k">Flag · '
            f"{E(challenge.flag.kind)}</span>"
            f'<form method="post" class="flagform" action="/c/{E(challenge.id)}/flag#result">'
            f'<input type="text" name="answer" placeholder="{E(challenge.flag.label)}" '
            'autocomplete="off" spellcheck="false" aria-label="Your answer">'
            '<button type="submit">Check</button></form>'
            f"{note}</div>"
        )

    terminal = (
        '<div class="term">'
        + (f'<p class="ran" data-ran>{E(ran)}</p>' if ran else "")
        + (
            f'<pre class="out" data-result tabindex="0" role="region" '
            f'aria-label="Observation output">{E(result)}</pre>'
            if result
            else '<p class="out idle" data-result>Nothing run yet. Press an observation on the left and the '
                 "output appears here, exactly as the lab returned it.</p>"
        )
        + "</div>"
    )

    right = (
        '<section class="panel" id="result"><h3>Result'
        '<span class="fill"></span><span class="side">read-only</span></h3>'
        f"{terminal}{flag}</section>"
    )

    return (
        f'<section class="stage" id="stage-02" data-state="{E(data_state)}">'
        + _stage_head(2, f"{len(challenge.controls)} controls · {len(challenge.observations)} probes")
        + banner
        + '<div class="body">'
        + f'<p class="objective"><b>Objective</b>{E(challenge.objective)}</p>'
        + f'<div class="console">{left}{right}</div>'
        + "</div></section>"
    )


def _source_panel(ref) -> str:
    """One source reference, read from the running stack at request time.

    A reference that no longer resolves says so, loudly, in the place the code would have been. An
    empty panel would let the material drift away from the lab without anybody noticing, which is
    the one thing this mechanism exists to prevent.
    """
    head = (
        '<div class="path">'
        f'<span class="file">{E(ref.path)}</span>'
        f'<span class="lines">{ref.lines[0]}–{ref.lines[1]}</span>'
        + (f'<span class="cap">{E(ref.caption)}</span>' if ref.caption else "")
        + "</div>"
    )
    try:
        lines = source.read_lines(ref.path, ref.lines[0], ref.lines[1])
    except source.SourceUnavailable as exc:
        return (
            f'<div class="src">{head}<div class="inner">'
            f'<p class="inert-note">Source unavailable — {E(str(exc))}</p></div></div>'
        )

    hit = ' class="hit"'
    def marked(number: int) -> str:
        inside = bool(ref.highlight) and ref.highlight[0] <= number <= ref.highlight[1]
        return hit if inside else ""

    rows = "".join(
        f'<tr{marked(number)}><td class="n">{number}</td><td>{E(text)}</td></tr>'
        for number, text in lines
    )
    return (
        f'<div class="src">{head}'
        f'<div class="lines-wrap" tabindex="0" role="region" '
        f'aria-label="{E(ref.path)} lines {ref.lines[0]} to {ref.lines[1]}">'
        f'<table role="presentation"><tbody>{rows}</tbody></table></div></div>'
    )


def _stage_03(challenge: Challenge, active: int) -> str:
    tabs = challenge.stage_03
    if not tabs and not challenge.sources:
        return ""

    sources = "".join(_source_panel(ref) for ref in challenge.sources)
    if sources:
        sources = (
            '<p class="eyebrow" style="margin:0 0 var(--s-2)">'
            "The lab's own source · " + plural(len(challenge.sources), "reference") + "</p>" + sources
        )

    body = ""
    if tabs:
        active = max(0, min(active, len(tabs) - 1))
        body = f'<div class="prose">{md(tabs[active].body)}</div>'

    note = plural(len(tabs), "tab") if len(tabs) > 1 else ""
    return (
        '<section class="stage" id="stage-03">'
        + _stage_head(3, note)
        + _tabs(challenge, "stage-03", tabs, active)
        + f'<div class="body">{body}{sources}</div>'
        + "</section>"
    )


def _hints(challenge: Challenge) -> str:
    if not challenge.hints:
        return ""
    items = "".join(
        # Each hint IS one question, so its own first line cannot go on the face without
        # removing the disclosure entirely. The face carries the number, what kind of thing is
        # behind it, and the word that says it opens.
        f'<details class="hint"><summary><span class="i">{index + 1:02d}</span>'
        f'<span class="t">Question {index + 1}</span><span class="fill"></span>'
        f'<span class="more">reveal</span></summary>'
        f'<div class="inner"><p>{md(hint)[3:-4]}</p></div></details>'
        for index, hint in enumerate(challenge.hints)
    )
    return (
        '<section class="stage" id="hints"><header>'
        '<span class="n">?</span><h2>Questions, not answers</h2>'
        '<span class="verb">hints</span><span class="fill"></span>'
        f'<span class="note">{len(challenge.hints)} · free · in order</span></header>'
        f'<div class="body">{items}</div></section>'
    )


def _why_this_challenge(challenge: Challenge) -> str:
    """The orientation panel, before Stage 01.

    A learner arriving from the catalogue knows a title and one sentence. That is enough to decide
    whether to open it and not enough to know what they are practising or why it belongs in a
    course about agents. Several challenges here are ordinary application security that agents make
    sharper rather than anything agent-specific, and saying which is which is the honest thing to
    do — a learner who cannot tell will either over-apply the lesson or dismiss it.
    """
    if not challenge.purpose and not challenge.agent_link:
        return ""

    parts = ['<section class="why">']
    if challenge.purpose:
        parts.append(f'<div><h2 class="eyebrow">What you are practising</h2>{md(challenge.purpose)}</div>')
    if challenge.agent_link:
        parts.append(f'<div><h2 class="eyebrow">Why it matters for an agent</h2>{md(challenge.agent_link)}</div>')
    parts.append("</section>")
    return "".join(parts)


def _spine(challenge: Challenge, state: dict[str, str] | None) -> str:
    """The stage spine: where you are in the three stages, and whether this one is armed."""
    mine = _challenge_state(challenge, state)
    css, _headline, _ids = _summarise(mine) if mine else ("", "", "")

    entries = [("stage-01", 1, plural(len(challenge.stage_01), "tab"), "")]
    if challenge.controls or challenge.observations:
        entries.append(("stage-02", 2, "console", css if css in {"armed", "unknown"} else ""))
    if challenge.stage_03 or challenge.sources:
        entries.append(("stage-03", 3, plural(len(challenge.sources), "source"), ""))

    def entry(anchor: str, number: int, flag: str) -> str:
        # Colour alone is not a signal: the strip three inches above this says "armed" with a
        # colour AND a dot AND a hatch, so the spine says it in words.
        klass = f' class="{flag}"' if flag else ""
        state = f" · {flag.upper()}" if flag else ""
        return (
            f'<li{klass}><a href="#{anchor}">'
            f'<span class="k">Stage {number:02d}{state}</span>{E(STAGE_TITLES[number - 1])}'
            "</a></li>"
        )

    items = "".join(entry(anchor, number, flag) for anchor, number, _note, flag in entries)
    if challenge.hints:
        items += f'<li><a href="#hints"><span class="k">Hints</span>{len(challenge.hints)} questions</a></li>'

    return (
        '<nav class="spine" aria-label="Stages">'
        f"<ol>{items}</ol>"
        f'<p class="foot">{E(challenge.id)}<br>{challenge.points} points</p>'
        "</nav>"
    )


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
    head = (
        '<div class="chead">'
        f'<span class="eyebrow"><a href="/catalogue#track-{challenge.track}">'
        f"Track {challenge.track:02d} · {E(challenge.track_name)}</a> "
        f"&nbsp;/&nbsp; {E(challenge.number)}</span>"
        f"<h1>{E(challenge.title)}</h1>"
        f'<p class="summary">{E(challenge.summary)}</p>'
        '<p class="facts">'
        + f"<span><b>{challenge.points}</b> points</span>"
        + "".join(
            f"<span><b>{count}</b> {noun}{'s' if count != 1 else ''}</span>"
            for count, noun in (
                (len(challenge.stage_01), "reading tab"),
                (len(challenge.controls), "control"),
                (len(challenge.observations), "observation"),
                (len(challenge.sources), "source reference"),
            )
        )
        + (f"<span>flag · <b>{E(challenge.flag.kind)}</b></span>" if challenge.flag else "<span>no flag</span>")
        + "</p></div>"
    )

    column = (
        _why_this_challenge(challenge)
        + _stage_01(challenge, tab_01)
        + _stage_02(challenge, state, result, ran, flag_note, flag_ok)
        + _stage_03(challenge, tab_03)
        + _hints(challenge)
    )

    body = (
        masthead("catalogue")
        + _strip(state, reset_for=challenge.id, anchor="#result")
        + head
        + f'<div class="layout">{_spine(challenge, state)}<div class="col">{column}</div></div>'
        + footer(challenge.id, f"track {challenge.track:02d}", f"{challenge.points} points")
    )
    return page(
        challenge.title,
        body,
        wide=True,
        solved_now=challenge.id if flag_ok else "",
    )


def not_found(what: str) -> str:
    return page(
        "Not found",
        masthead()
        + '<div class="chead"><span class="eyebrow">404</span><h1>Not found</h1>'
        f'<p class="summary">{E(what)}</p></div>'
        '<p><a class="btn primary" href="/catalogue">Back to the catalogue</a></p>'
        + footer(),
    )
