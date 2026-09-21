"""The Range's stylesheet.

DESIGN DIRECTION — "Instrument"
===============================

This is a measuring device for professionals, not a product page. It should read like the front
panel of a piece of test equipment and the report that comes out of it: cold metal, hairline rules,
type doing the work, colour used almost nowhere so that when colour appears it *means* something.

Palette — seven named values, each with a job
---------------------------------------------
    Graphite   #101619   the ink. Near-black with a blue-green cast so it sits inside the steel
                         ramp instead of fighting it. Pure #000 would read as print, not panel.
    Steel      #586670   the muted tone: labels, units, secondary data. Cold enough that it can
                         never be misread as a state colour, and dark enough to clear 4.5:1 on all
                         three light surfaces it is set on rather than only on panel white:
                         5.22:1 on Paper, 5.92:1 on Panel, 4.90:1 on the raised surface.
    Paper      #EFF1F2   the ground, and Panel #FFFFFF the raised surface. Almost no warmth —
                         the page should feel like glass and anodised aluminium, not stationery.
    Prussian   #134A73   the accent, and the ONLY accent. Interactive affordances and identifiers.
                         A deep cold blue, 9.2:1 on white, and far enough from amber/red/green in
                         hue that it can never be mistaken for a state.
    Amber      #8C4E00   ARMED. Something in the lab is deliberately in its wrong setting. It has
                         to clear on its own tinted strip, not just on paper: 5.72:1 there, at the
                         11px the strip sets it in.
    Red        #A02C22   BROKEN / refused / unreadable.
    Green      #1F6B41   HELD. The control is at its designed setting.

    plus Slate ink #131A1E — the console surface, dark in BOTH themes, because a terminal that
    changes colour with the OS stops looking like the same instrument.

The three signal colours are the only saturated fills on the page and they are never used for
decoration. The accent is never used for state. That separation is the whole point: a learner has
to be able to read "armed" from across the room without reading a word, and that fails the instant
the accent starts meaning something.

Type — three roles, three stacks, all already on the machine
------------------------------------------------------------
    UI / data     system-ui grotesque. Labels, tables, buttons, navigation, meta. Tight, neutral,
                  invisible. `font-variant-numeric: tabular-nums` everywhere numbers line up.
    Reading       Charter / Iowan Old Style / Georgia / Cambria. Stage prose only. The material is
                  long-form technical writing and it earns a reading face; it also draws a hard
                  line between "the lesson" and "the instrument", which is the page's main
                  hierarchy problem.
    Data / ident  ui-monospace. Identifiers, mutation ids, paths, state words, console output,
                  numerals in the spine. Anything the system said rather than anything we wrote.

No webfont. The lab runs offline and a face that silently fails to load is a page that silently
changes shape. The type scale in `--t-*` is two regimes joined at the reading size — 1px steps
below it, because at 11-16px a ratio rounds to the same pixel, and roughly 1.2 at and above it —
and spacing is a 4px scale fixed in `--s-*`, with control padding named separately in `--c-pad-*`
so a button and a field cannot drift apart. Every size and gap comes off those ladders except a
few deliberate optical one-offs (1px and 2px nudges) and the em-relative padding on inline `code`.

Layout
------
Everything hangs from one left edge: a single measure column, a hairline rule grid, and — on the
challenge page — a fixed stage spine in the left margin carrying the 01/02/03 numerals and the live
environment state. Nothing is centred, nothing is a rounded card by default, and state is expressed
structurally: a panel whose environment is armed grows a thick amber margin rail and a hatched
banner, so the condition of the lab is a property of the page's shape rather than a badge on it.

Two rules that are structural rather than decorative:

  * Semantic colour is separate from the accent (above).
  * Nothing animates in from invisible. A learner scrolling back must find the page as they left
    it, and `prefers-reduced-motion` removes what little movement there is.

Every colour is defined on bare `:root` first, so the un-stamped state (a viewer on "system") is a
complete palette rather than a half of one.
"""

_TOKENS = """
:root {
  /* ---- neutral ramp: cold steel, no warmth ---- */
  --ground:      #EFF1F2;
  --surface:     #FFFFFF;
  --surface-2:   #E7EAEC;
  --surface-3:   #DCE1E3;
  --ink:         #101619;
  --ink-2:       #39464C;
  --muted:       #586670;
  --rule:        #D6DCDF;
  --rule-2:      #B4BEC3;
  /* Rules are hairlines by design (1.2-1.9:1). A control EDGE is a UI component boundary and
     owes 3:1, so it is its own value rather than a darker --rule-2. */
  --control-edge: #6E7A80;

  /* ---- accent: interactive + identifiers, never state ---- */
  --accent:      #134A73;
  --accent-2:    #0E3A5C;
  --accent-soft: #DEE8F0;
  --on-accent:   #FFFFFF;

  /* ---- semantic: state, never decoration ---- */
  --armed:       #8C4E00;
  --armed-soft:  #FAEEDC;
  --armed-edge:  #AE7F26;
  --broken:      #A02C22;
  --broken-soft: #F8E4E1;
  --broken-edge: #B8564A;
  --held:        #1F6B41;
  --held-soft:   #DFEEE5;
  --held-edge:   #3F8A60;

  /* ---- the console reads the same in both themes ---- */
  --console:     #131A1E;
  --console-2:   #1D272C;
  --console-ink: #CBD6DA;
  --console-dim: #7C8D94;
  --console-rule:#2B383E;

  /* Painted ON console surfaces, which do not flip with the theme — so these must not either. */
  --console-accent: #7FB4DE;
  --console-armed:  #D99A3E;
  --console-hit:    #3A2E1C;

  --focus:       #134A73;

  /* ---- type ---- */
  --sans: system-ui, -apple-system, "Segoe UI Variable Text", "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  --read: Charter, "Bitstream Charter", "Iowan Old Style", "Palatino Linotype", Georgia, Cambria, "Times New Roman", serif;
  --mono: ui-monospace, "SF Mono", "Cascadia Mono", "JetBrains Mono", Menlo, Consolas, "Liberation Mono", monospace;

  /* Two regimes, deliberately. Below the reading size, 1px steps, because at 11-16px a ratio
     scale rounds to the same pixel and the ladder stops being a ladder. At and above the
     reading size, roughly 1.2. Ten steps; nothing below uses a size off this list. */
  --t-2xs: .6875rem;  /* 11  eyebrows, table heads, mono labels */
  --t-xs:  .75rem;    /* 12  meta, captions */
  --t-s:   .8125rem;  /* 13  table body, console */
  --t-m:   .875rem;   /* 14  dense UI */
  --t-base:.9375rem;  /* 15  UI base */
  --t-r:   1rem;      /* 16  reading base */
  --t-l:   1.125rem;  /* 18  panel titles */
  --t-xl:  1.3125rem; /* 21  stage titles */
  --t-2xl: 1.625rem;  /* 26  page titles */
  --t-3xl: 2.125rem;  /* 34  landing title */

  /* 4px scale. Every gap and pad below comes off it, except seven deliberate optical one-offs —
     1px and 2px nudges that sit a border or a label on the right hairline — and the em-relative
     padding on inline `code`, which has to scale with whatever type it sits inside. */
  --s-1: 4px;  --s-2: 8px;  --s-3: 12px; --s-4: 16px;
  --s-5: 24px; --s-6: 32px; --s-7: 48px; --s-8: 64px; --s-9: 96px;

  /* Control padding-block. Named, so a button and a field cannot drift apart. */
  --c-pad:   7px;  /* default control: 14px text + 2x7 + 2x1 border = 34px */
  --c-pad-l: 9px;  /* large control (.btn.primary / .btn.quiet) */
  --c-pad-s: 3px;  /* compact mono control (#themeswitch, button.small) */

  /* Radii are small and few. A hairline box is the default; roundness is not a style here. */
  --r-1: 2px; --r-2: 3px;

  /* Tracking. Display type tightens, mono labels open up. Five values, not twelve. */
  --tr-tight:  -.022em;  /* the landing h1 only */
  --tr-snug:   -.012em;  /* every other sans heading and the masthead mark */
  --tr-num:    -.03em;   /* mono numerals set solid */
  --tr-label:  .1em;     /* uppercase mono labels */
  --tr-label-s:.06em;    /* uppercase mono at 11px in tight rows */

  color-scheme: light;
}

/* Dark is designed, not inverted: the ramp is re-picked so the rules stay hairlines and the
   signal colours stay signals rather than glowing. */
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --ground:      #0C1113;
    --surface:     #171F23;
    --surface-2:   #1F2A2F;
    --surface-3:   #2A363C;
    --ink:         #E4EBED;
    --ink-2:       #BCC8CD;
    --muted:       #87969D;
    --rule:        #232F33;
    --rule-2:      #36454B;
    --control-edge: #6A7D85;

    --accent:      #6BA6D8;
    --accent-2:    #9CC6E8;
    --accent-soft: #12242F;
    --on-accent:   #0C1113;

    --armed:       #E0A44E;
    --armed-soft:  #2B2114;
    --armed-edge:  #8A6B31;
    --broken:      #E88C7E;
    --broken-soft: #2D1A18;
    --broken-edge: #9A5248;
    --held:        #63C08C;
    --held-soft:   #142720;
    --held-edge:   #468562;

    --console:     #0A0E10;
    --console-2:   #151E22;
    --console-ink: #C6D2D7;
    --console-dim: #77878E;
    --console-rule:#232F34;
    --console-hit:  #31281B;

    --focus:       #8FC2E8;
    color-scheme: dark;
  }
}

:root[data-theme="dark"] {
  --ground:      #0C1113;
  --surface:     #171F23;
  --surface-2:   #1F2A2F;
  --surface-3:   #2A363C;
  --ink:         #E4EBED;
  --ink-2:       #BCC8CD;
  --muted:       #87969D;
  --rule:        #232F33;
  --rule-2:      #36454B;
  --control-edge: #6A7D85;
  --accent:      #6BA6D8;
  --accent-2:    #9CC6E8;
  --accent-soft: #12242F;
  --on-accent:   #0C1113;
  --armed:       #E0A44E;
  --armed-soft:  #2B2114;
  --armed-edge:  #8A6B31;
  --broken:      #E88C7E;
  --broken-soft: #2D1A18;
  --broken-edge: #9A5248;
  --held:        #63C08C;
  --held-soft:   #142720;
  --held-edge:   #468562;
  --console:     #0A0E10;
  --console-2:   #151E22;
  --console-ink: #C6D2D7;
  --console-dim: #77878E;
  --console-rule:#232F34;
  --console-hit:  #31281B;
  --focus:       #8FC2E8;
  color-scheme: dark;
}
"""

_BASE = """
*, *::before, *::after { box-sizing: border-box; }

html { -webkit-text-size-adjust: 100%; }

body {
  margin: 0;
  padding: 0 var(--s-4) var(--s-9);
  background: var(--ground);
  color: var(--ink);
  font-family: var(--sans);
  font-size: var(--t-base);
  line-height: 1.55;
  font-variant-numeric: tabular-nums;
  -webkit-font-smoothing: antialiased;
  text-rendering: optimizeLegibility;
}

.wrap { max-width: 64rem; margin-inline: auto; }
.wrap.wide { max-width: 76rem; }

a { color: var(--accent); text-underline-offset: 2px; text-decoration-thickness: 1px; }
a:hover { color: var(--accent-2); }

/* `bolder` resolves against the inherited weight, so a <strong> in a 600 blockquote computes
   to 900. Pin it: the system has one bold. */
strong, b { font-weight: 700; }

:focus-visible {
  outline: 2px solid var(--focus);
  outline-offset: 2px;
  box-shadow: 0 0 0 2px var(--ground);
  border-radius: var(--r-1);
}

/* Console surfaces are dark in both themes, so the ring on them must be too. */
.term :focus-visible, .src :focus-visible, pre:focus-visible { outline-color: var(--console-accent); }

/* A keyboard user otherwise passes eleven links before the first stage, on every reload. */
.skiplink {
  position: absolute; left: var(--s-4); top: 0; transform: translateY(-120%); z-index: 10;
  background: var(--accent); color: var(--on-accent);
  font-family: var(--mono); font-size: var(--t-2xs); font-weight: 600;
  letter-spacing: var(--tr-label); text-transform: uppercase; text-decoration: none;
  padding: var(--s-2) var(--s-3); border-radius: var(--r-1);
}
.skiplink:focus-visible { transform: translateY(var(--s-2)); }
main:focus { outline: none; }

/* One shared label style: the small uppercase mono tag that names a region. It appears on panel
   heads, table heads, eyebrows and readouts, and it is defined once so it cannot drift. */
.eyebrow, .panel > h3, th, .readout .k, .route .k, .flag .k, .spine .k {
  font-family: var(--mono);
  font-size: var(--t-2xs);
  font-weight: 600;
  letter-spacing: var(--tr-label);
  text-transform: uppercase;
  color: var(--muted);
}

/* ================================================================== masthead */

.masthead {
  display: flex;
  align-items: center;
  gap: var(--s-3);
  flex-wrap: wrap;
  padding: var(--s-4) 0 var(--s-3);
  border-bottom: 1px solid var(--ink);
  margin-bottom: 0;
}
.masthead .mark {
  font-size: var(--t-r);
  font-weight: 650;
  letter-spacing: var(--tr-snug);
  margin: 0;
  white-space: nowrap;
}
.masthead .mark a { color: inherit; text-decoration: none; }
.masthead .mark a:hover { color: var(--accent); }
.masthead .sep { width: 1px; height: 1em; background: var(--rule-2); flex: 0 0 auto; }
.masthead .lab {
  font-family: var(--mono);
  font-size: var(--t-2xs);
  letter-spacing: var(--tr-label);
  text-transform: uppercase;
  color: var(--muted);
  white-space: nowrap;
}
.masthead .spacer { flex: 1 1 auto; }
.masthead nav { display: flex; gap: var(--s-3); align-items: center; flex-wrap: wrap; }
.masthead nav a {
  font-size: var(--t-m);
  text-decoration: none;
  color: var(--ink-2);
  padding-bottom: 1px;
  border-bottom: 1px solid transparent;
}
.masthead nav a:hover { color: var(--accent); border-bottom-color: var(--accent); }
.masthead nav a[aria-current="page"] { color: var(--ink); font-weight: 600; border-bottom-color: var(--ink); }

/* The theme switch is written by script and is absent without it: it changes how the page looks,
   never whether it works. */
#themeswitch {
  font-family: var(--mono);
  font-size: var(--t-2xs);
  letter-spacing: var(--tr-label-s);
  text-transform: uppercase;
  color: var(--muted);
  background: none;
  border: 1px solid var(--control-edge);
  border-radius: var(--r-1);
  padding: var(--c-pad-s) var(--s-2);
  cursor: pointer;
}
#themeswitch:hover { color: var(--accent); border-color: var(--accent); }

/* ================================================================== status strip

   Directly under the masthead on every page that can read the lab. This is the "across the room"
   signal: colour, a dot, AND a diagonal hatch, so it survives a colour-blind reader and a bad
   projector. */

.strip {
  display: flex;
  align-items: center;
  gap: var(--s-3);
  flex-wrap: wrap;
  padding: var(--s-2) var(--s-3);
  border: 1px solid var(--rule);
  border-top: 0;
  font-family: var(--mono);
  font-size: var(--t-xs);
  color: var(--ink-2);
  background: var(--surface);
}
.strip .dot { width: 8px; height: 8px; border-radius: 50%; flex: 0 0 auto; background: var(--muted); }
.strip b { font-weight: 700; letter-spacing: var(--tr-label-s); text-transform: uppercase; font-size: var(--t-2xs); }
/* The identifier belongs next to the state it names, not a thousand pixels away at the far
   right, and it is part of the sentence rather than the dimmest thing in the bar.
   Reading order: dot, label, state, identifier, filler, button. */
.strip .fill { flex: 1 1 auto; order: 2; }
.strip .ids { flex: 0 1 auto; order: 1; color: currentColor; opacity: .8; overflow: hidden;
              text-overflow: ellipsis; white-space: nowrap; min-width: 0; }
.strip form { margin: 0; order: 3; }
.strip button.small { order: 3; }

/* A green button inside an amber bar is the state inversion of C1. The strip's controls take
   the strip's own colour. */
.strip button.small { border-color: currentColor; color: inherit; }
.strip button.small:hover:not(:disabled) {
  background: color-mix(in srgb, currentColor 10%, transparent); color: inherit; border-color: currentColor;
}
@supports not (background: color-mix(in srgb, red 10%, transparent)) {
  .strip button.small:hover:not(:disabled) { background: var(--surface); }
}

.strip.held   { background: var(--held-soft);   border-color: var(--held-edge);   color: var(--held); }
.strip.held .dot { background: var(--held); }
.strip.armed  { background: var(--armed-soft);  border-color: var(--armed-edge);  color: var(--armed); }
.strip.armed .dot { background: var(--armed); }
.strip.unknown{ background: var(--broken-soft); border-color: var(--broken-edge); color: var(--broken); }
.strip.unknown .dot { background: var(--broken); }
.strip.armed, .strip.unknown {
  background-image: repeating-linear-gradient(
    -45deg, transparent 0 7px, color-mix(in srgb, currentColor 9%, transparent) 7px 14px);
}
@supports not (background: color-mix(in srgb, red 9%, transparent)) {
  .strip.armed, .strip.unknown { background-image: none; }
}

/* At 390 the strip wrapped to three lines of hatched caution tape and became the loudest
   object on a page whose whole direction is "colour almost nowhere". Smaller type, and the
   state carried by an edge rather than by a filled field. */
@media (max-width: 640px) {
  .strip { gap: var(--s-2); font-size: var(--t-2xs); }
  .strip.armed, .strip.unknown { background-image: none; border-left: 3px solid currentColor; }
}


/* ================================================================== landing */

.lede {
  display: grid;
  grid-template-columns: minmax(0, 1.55fr) minmax(0, 1fr);
  gap: var(--s-6);
  align-items: start;
  padding: var(--s-6) 0 var(--s-5);
  border-bottom: 1px solid var(--rule);
  margin-bottom: var(--s-5);
}
/* Stacked, the readout's five rows become a 788px label-to-value strip. Below 860 it is a
   row of instrument faces instead. */
@media (max-width: 860px) {
  .lede { grid-template-columns: minmax(0, 1fr); gap: var(--s-5); }
  .readout { display: grid; grid-template-columns: repeat(auto-fit, minmax(9rem, 1fr)); }
  .readout .row {
    flex-direction: column; align-items: flex-start; gap: var(--s-1);
    border-bottom: 0; border-right: 1px solid var(--rule);
  }
  .readout .row:last-child { border-right: 0; }
  .readout .row.state { border-top: 0; }
}

.lede h1 {
  font-size: var(--t-3xl);
  line-height: 1.1;
  letter-spacing: var(--tr-tight);
  font-weight: 650;
  margin: var(--s-2) 0 var(--s-3);
  text-wrap: balance;
  /* Deliberately short: the h1 is a headline, not a measure. Standfirst and subs share one
     right edge below it, so the ragged stack becomes two edges instead of three. */
  max-width: 15ch;
}
.lede .standfirst {
  font-family: var(--read);
  font-size: var(--t-l);
  line-height: 1.45;
  color: var(--ink);
  margin: 0 0 var(--s-3);
  max-width: 54ch;
}
/* The explanation, not a caption: body base, and a paragraph gap wider than the line gap so two
   paragraphs read as two. */
.lede p.sub {
  font-size: var(--t-base);
  color: var(--ink-2);
  margin: 0 0 var(--s-4);
  max-width: 54ch;
}
.lede .go { display: flex; flex-wrap: wrap; gap: var(--s-2); margin-top: var(--s-4); }

/* The readout: four facts about the lab as it is right now, set like an instrument face. */
.readout { border: 1px solid var(--rule-2); background: var(--surface); }
.readout .row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--s-3);
  padding: var(--s-3) var(--s-4);
  border-bottom: 1px solid var(--rule);
}
.readout .row:last-child { border-bottom: 0; }
.readout .v {
  font-family: var(--mono);
  font-size: var(--t-xl);
  font-weight: 600;
  line-height: 1;
  letter-spacing: var(--tr-snug);
  color: var(--ink);
}
.readout .v .u { font-size: var(--t-xs); font-weight: 400; color: var(--muted); letter-spacing: 0; }
.readout .row.state { border-top: 1px solid var(--rule-2); }
.readout .row.state .v { letter-spacing: var(--tr-snug); }
.readout .row.state.held .v   { color: var(--held); }
.readout .row.state.armed .v  { color: var(--armed); }
.readout .row.state.unknown .v{ color: var(--broken); }

/* The hero's right column: reading, then the way in, then what the three state words mean. The
   site names states everywhere and defined them nowhere. */
.lede .rail { display: flex; flex-direction: column; gap: var(--s-4); }
.lede .rail .go { margin-top: 0; }
.lede .rail .btn { flex: 1 1 auto; text-align: center; }

.key { margin: 0; border-top: 1px solid var(--rule-2); }
.key > div {
  display: grid;
  grid-template-columns: var(--s-2) 7rem minmax(0, 1fr);
  align-items: baseline;
  gap: var(--s-2) var(--s-3);
  padding: var(--s-2) 0;
  border-bottom: 1px solid var(--rule);
}
.key .sw { width: 8px; height: 8px; border-radius: 50%; align-self: center; }
.key .sw.held { background: var(--held); }
.key .sw.armed { background: var(--armed); }
.key .sw.unknown { background: var(--broken); }
.key dt {
  font-family: var(--mono); font-size: var(--t-2xs); font-weight: 600;
  letter-spacing: var(--tr-label); text-transform: uppercase; color: var(--ink-2);
}
.key dd { margin: 0; font-size: var(--t-xs); line-height: 1.4; color: var(--muted); }
"""

_TABLES = """
/* ================================================================== tables

   This application is mostly tables, so the table is the component that gets the most care: no
   vertical rules, no zebra, one hairline per row, uppercase mono heads on a stronger rule, and
   tabular numerals so columns of figures line up as columns. */

.scroller { overflow-x: auto; margin: 0 0 var(--s-4); }
table { border-collapse: collapse; width: 100%; font-size: var(--t-s); }
.prose table { min-width: 28rem; }

th {
  text-align: left;
  padding: 0 var(--s-4) var(--s-2) 0;
  border-bottom: 1px solid var(--rule-2);
  vertical-align: bottom;
  white-space: nowrap;
}
td {
  padding: var(--s-2) var(--s-4) var(--s-2) 0;
  border-bottom: 1px solid var(--rule);
  vertical-align: top;
  color: var(--ink-2);
}
th:last-child, td:last-child { padding-right: 0; }
td:first-child, th:first-child { padding-left: 0; }
tbody tr:last-child td { border-bottom: 0; }
td.num, th.num { text-align: right; font-family: var(--mono); font-variant-numeric: tabular-nums; }

/* The index table. Rows are reachable by one link each; the whole row responds so the target
   feels like the row rather than the six words in it. */
.index { width: 100%; border-collapse: collapse; }
.index th { font-size: var(--t-2xs); }
.index td { padding-block: var(--s-3); color: var(--ink-2); }
/* The row advertises a click target, so the row has to BE one: the title's link is stretched
   over the whole row by an overlay, and the hover is a step on the ramp rather than 1.1:1. */
.index tbody tr { position: relative; transition: background-color .08s linear; }
.index tbody tr:hover, .index tbody tr:focus-within { background: var(--surface-2); }
.index tbody tr:hover td, .index tbody tr:focus-within td { border-bottom-color: var(--rule-2); }
.index tbody tr:hover .name a { color: var(--accent); text-decoration: underline; }
.index .name a::after { content: ""; position: absolute; inset: 0; }
.index .id {
  font-family: var(--mono);
  font-size: var(--t-s);
  font-weight: 600;
  color: var(--accent);
  white-space: nowrap;
  width: 1%;
}
.index .name { width: 1%; white-space: nowrap; padding-right: var(--s-6); }
.index .name a {
  color: var(--ink);
  font-weight: 600;
  font-size: var(--t-base);
  text-decoration: none;
}
.index .name a:hover { color: var(--accent); text-decoration: underline; }
/* The serif's job on these pages is the standfirst, the catalogue summary and the eight
   claimlines. In a table cell it made the description outrank the title beside it. */
.index .claim { font-size: var(--t-s); line-height: 1.5; color: var(--ink-2); }
.index .what { font-size: var(--t-s); line-height: 1.5; }
/* Cells only: `.n` is also the class on the count inside a progress bar, and a descendant
   selector here collapsed that span to 1% of the table and clipped the figure. */
.index td.n, .index th.n { width: 1%; white-space: nowrap; text-align: right; font-family: var(--mono); color: var(--ink-2); }
/* A percentage-collapsed column still has to be wide enough for what is in it. */
.index th.num:last-child, .index td.n:last-child { min-width: 6rem; }
.index tr.inert .name a { color: var(--muted); }
/* Solved is this browser's memory, stamped by script (or server-side in a preview). A mark
   in the number column rather than a badge: the row stays a row. */
.index tr[data-solved="1"] .id { color: var(--held); }
.index tr[data-solved="1"] .id::before { content: "\2713\00a0"; font-weight: 700; }

/* A bar that says how much of a track is done, read as a shape before it is read as a number. */
td.n > .bar { justify-content: flex-end; }
.bar {
  display: flex;
  align-items: center;
  gap: var(--s-2);
  font-family: var(--mono);
  font-size: var(--t-2xs);
  color: var(--muted);
  white-space: nowrap;
}
.bar .track {
  width: 56px; height: 5px; flex: 0 0 auto;
  background: var(--surface-3);
  border: 1px solid var(--control-edge);
  border-radius: 1px;
  overflow: hidden;
}
.bar .track i { display: block; height: 100%; background: var(--accent); }
.bar .n { flex: 0 0 auto; }
.bar.done .track i { background: var(--held); }
.bar.done { color: var(--held); }

/* ================================================================== buttons and fields */

button, .btn {
  font-family: var(--sans);
  font-size: var(--t-m);
  font-weight: 600;
  line-height: 1.3;
  color: var(--ink);
  background: var(--surface);
  border: 1px solid var(--control-edge);
  border-radius: var(--r-1);
  padding: var(--c-pad) var(--s-3);
  cursor: pointer;
  text-decoration: none;
  display: inline-block;
}
button:hover:not(:disabled), .btn:hover { border-color: var(--accent); color: var(--accent); }
button:disabled { opacity: .45; cursor: not-allowed; }

.btn.primary {
  background: var(--accent);
  border-color: var(--accent);
  color: var(--on-accent);
  padding: var(--c-pad-l) var(--s-4);
  font-size: var(--t-base);
}
.btn.primary:hover { background: var(--accent-2); border-color: var(--accent-2); color: var(--on-accent); }
.btn.quiet { padding: var(--c-pad-l) var(--s-4); font-size: var(--t-base); background: transparent; }

button.arm { border-color: var(--armed); color: var(--armed); }
button.arm:hover:not(:disabled) { background: var(--armed-soft); border-color: var(--armed); color: var(--armed); }
button.restore { border-color: var(--held); color: var(--held); }
button.restore:hover:not(:disabled) { background: var(--held-soft); border-color: var(--held); color: var(--held); }
button.small { font-size: var(--t-2xs); padding: var(--c-pad-s) var(--s-2); font-family: var(--mono); letter-spacing: var(--tr-label-s); text-transform: uppercase; }

/* Inside a switch row the buttons are neutral. Colour on this page belongs to STATE, and a
   green "Restore" on an amber row reads as the opposite of what the row says. The verb is the
   affordance; the rail and the chip are the state. The rules above still dress the reset foot,
   which sits outside a row and is the one place the colour still means the outcome. */
.control button { min-width: 6.25rem; text-align: center; }
.control button.arm, .control button.restore { border-color: var(--control-edge); color: var(--ink); }
.control button.arm:hover:not(:disabled)     { border-color: var(--armed); color: var(--armed); background: var(--armed-soft); }
.control button.restore:hover:not(:disabled) { border-color: var(--held);  color: var(--held);  background: var(--held-soft); }

input[type="text"] {
  font-family: var(--mono);
  font-size: var(--t-s);
  color: var(--ink);
  background: var(--surface);
  border: 1px solid var(--control-edge);
  border-radius: var(--r-1);
  padding: var(--c-pad) var(--s-3);
  min-width: 0;
}
input[type="text"]::placeholder { color: var(--muted); }

/* ================================================================== the three routes in */

.routes {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0;
  border-top: 1px solid var(--rule-2);
  border-bottom: 1px solid var(--rule-2);
  margin: 0 0 var(--s-6);
}
.route { padding: var(--s-4) var(--s-4) var(--s-4) 0; border-right: 1px solid var(--rule); }
.route:last-child { border-right: 0; }
.route:not(:first-child) { padding-left: var(--s-4); }
.route .k { display: block; margin-bottom: var(--s-2); }
.route p { margin: 0 0 var(--s-3); font-size: var(--t-m); color: var(--ink-2); line-height: 1.45; }
.route a.go {
  font-family: var(--mono);
  font-size: var(--t-m);
  font-weight: 600;
  text-decoration: none;
  display: inline-flex;
  align-items: baseline;
  gap: var(--s-2);
}
.route a.go:hover { text-decoration: underline; }
.route a.go .arrow { color: var(--muted); }
/* "How a challenge works" is the same grid as "Three ways in" and must not read as the same
   object: no closing rule, no bottom padding, and the key drops out of accent. */
.routes.flat { border-bottom: 0; }
.routes.flat .route { padding-bottom: 0; }
.routes.flat .route .k { color: var(--ink-2); }

@media (max-width: 760px) {
  .routes { grid-template-columns: minmax(0, 1fr); }
  .route { border-right: 0; border-bottom: 1px solid var(--rule); padding: var(--s-4) 0; }
  .route:not(:first-child) { padding-left: 0; }
  .route:last-child { border-bottom: 0; }
}

/* ================================================================== section heads */

.sec { margin: 0 0 var(--s-6); }
.sec > h2 {
  font-size: var(--t-l);
  font-weight: 650;
  letter-spacing: var(--tr-snug);
  margin: 0 0 var(--s-2);
}
.sec > p.note { margin: 0 0 var(--s-4); color: var(--muted); font-size: var(--t-m); max-width: 62ch; }

/* Track band on the catalogue: number, name, claim, count — one object, used eight times. */
.band {
  display: flex;
  align-items: baseline;
  gap: var(--s-3);
  flex-wrap: wrap;
  padding-bottom: var(--s-2);
  border-bottom: 2px solid var(--ink);
  margin-bottom: var(--s-1);
}
/* The section numeral: a two-digit mono figure in accent naming a section. The same object on
   the catalogue band and in a stage header, so it is declared once. Child combinator on .band:
   `.n` is also the count inside a progress bar, which is a descendant of .band. */
.band > .n, .stage > header .n {
  font-family: var(--mono);
  font-size: var(--t-xl);
  font-weight: 600;
  line-height: 1;
  letter-spacing: var(--tr-num);
  color: var(--accent);
  flex: 0 0 auto;
}
.band h2 { margin: 0; font-size: var(--t-l); font-weight: 650; letter-spacing: var(--tr-snug); }
.band .fill { flex: 1 1 auto; }
.band .count { font-family: var(--mono); font-size: var(--t-xs); color: var(--muted); white-space: nowrap; }
.claimline {
  font-family: var(--read);
  font-size: var(--t-r);
  line-height: 1.45;
  color: var(--ink-2);
  margin: var(--s-2) 0 var(--s-3);
  max-width: 64ch;
}
/* The catalogue's Console column is prose ("read-only", "2 controls"), so it sets flush left.
   Right alignment is for figures. */
.trackblock .index td.n:nth-last-child(2),
.trackblock .index th.num:nth-last-child(2) { text-align: left; padding-left: var(--s-4); }

/* A way between the eight tracks, on a page that is 4,000px of rows. */
.tracknav {
  display: flex; flex-wrap: wrap; gap: 0 var(--s-5);
  border-top: 1px solid var(--rule-2); border-bottom: 1px solid var(--rule-2);
  padding: var(--s-2) 0; margin: 0 0 var(--s-6);
}
.tracknav a {
  display: inline-flex; align-items: baseline; gap: var(--s-2);
  padding: var(--s-1) 0; font-size: var(--t-m); color: var(--ink-2); text-decoration: none;
}
.tracknav a:hover { color: var(--accent); }
.tracknav .n { font-family: var(--mono); font-size: var(--t-2xs); font-weight: 600; color: var(--muted); }

/* The band is the horizon line: it holds the track you are inside while you scroll its rows. */
.band { position: sticky; top: 0; z-index: 2; background: var(--ground); padding-top: var(--s-2); }
.trackblock { margin-bottom: var(--s-7); scroll-margin-top: var(--s-7); }

/* L8: an unbuilt challenge says so in the data column. A title dimmed to --muted read as a
   disabled link on a page whose own standfirst says nothing is locked. */
.index tr.inert .name a { color: var(--ink-2); }
.index tr.inert td.n:nth-last-child(2) { color: var(--muted); font-style: normal; }
"""

_CHALLENGE = """
/* ================================================================== challenge head */

.chead { padding: var(--s-6) 0 var(--s-4); border-bottom: 1px solid var(--rule); margin-bottom: var(--s-5); }
.chead .eyebrow { display: block; margin-bottom: var(--s-2); }
.chead .eyebrow a { color: inherit; text-decoration: none; }
.chead .eyebrow a:hover { color: var(--accent); }
.chead h1 {
  font-size: var(--t-2xl);
  line-height: 1.12;
  letter-spacing: var(--tr-snug);
  font-weight: 650;
  margin: 0 0 var(--s-3);
  max-width: 24ch;
  text-wrap: balance;
}
.chead .summary {
  font-family: var(--read);
  font-size: var(--t-l);
  line-height: 1.45;
  color: var(--ink-2);
  margin: 0 0 var(--s-4);
  max-width: 62ch;
}
.chead .facts { display: flex; flex-wrap: wrap; gap: var(--s-2) var(--s-5); font-family: var(--mono); font-size: var(--t-xs); color: var(--muted); }
.chead .facts b { color: var(--ink-2); font-weight: 600; }

/* ================================================================== the layout: spine + column */

.layout { display: grid; grid-template-columns: 9.5rem minmax(0, 1fr); gap: 0 var(--s-6); align-items: start; }
.layout > .col { min-width: 0; }

.spine { position: sticky; top: var(--s-4); }
.spine ol { list-style: none; margin: 0; padding: 0; border-left: 1px solid var(--rule-2); }
.spine li { position: relative; }
.spine a {
  display: block;
  padding: var(--s-2) 0 var(--s-2) var(--s-3);
  text-decoration: none;
  color: var(--ink-2);
  font-size: var(--t-m);
  line-height: 1.25;
  border-left: 2px solid transparent;
  margin-left: -1px;
}
.spine a:hover { color: var(--accent); border-left-color: var(--accent); }
.spine .k { display: block; margin-bottom: 2px; }
.spine li.armed a { border-left-color: var(--armed); }
.spine li.armed .k { color: var(--armed); }
/* Where you are, distinct from what is armed: ink rail and a lift; armed keeps its amber. */
.spine a[aria-current="true"] {
  color: var(--ink); font-weight: 600; border-left-color: var(--ink); background: var(--surface);
}
.spine a[aria-current="true"] .k { color: var(--ink-2); }
.spine li.armed a[aria-current="true"] { border-left-color: var(--armed); }
.spine .foot { margin: var(--s-4) 0 0; padding-left: var(--s-3); font-family: var(--mono); font-size: var(--t-2xs); color: var(--muted); line-height: 1.5; }

@media (max-width: 980px) {
  .layout { grid-template-columns: minmax(0, 1fr); }
  .spine { position: static; margin-bottom: var(--s-4); }
  .spine ol { display: flex; flex-wrap: wrap; gap: 0; border-left: 0; border-bottom: 1px solid var(--rule-2); }
  .spine li { flex: 1 1 auto; }
  .spine a { border-left: 0; border-bottom: 2px solid transparent; margin-left: 0; margin-bottom: -1px; padding: var(--s-2) var(--s-3) var(--s-2) 0; }
  .spine li.armed a { border-bottom-color: var(--armed); }
  .spine a[aria-current="true"] { border-left-color: transparent; border-bottom-color: var(--ink); }
  .spine .foot { display: none; }
}

/* ================================================================== stages */

.stage {
  background: var(--surface);
  border: 1px solid var(--rule);
  border-left: 3px solid var(--rule-2);
  margin-bottom: var(--s-5);
  scroll-margin-top: var(--s-4);
}
.stage > header {
  display: flex;
  align-items: baseline;
  gap: var(--s-3);
  flex-wrap: wrap;
  padding: var(--s-3) var(--s-4);
  border-bottom: 1px solid var(--rule);
  background: var(--surface-2);
}
.stage > header h2 { margin: 0; font-size: var(--t-l); font-weight: 650; letter-spacing: var(--tr-snug); }
.stage > header .verb { font-family: var(--mono); font-size: var(--t-2xs); letter-spacing: var(--tr-label); text-transform: uppercase; color: var(--muted); }
.stage > header .fill { flex: 1 1 auto; }
.stage > header .note { font-family: var(--mono); font-size: var(--t-2xs); color: var(--muted); letter-spacing: var(--tr-label-s); text-transform: uppercase; }
.stage > .body { padding: var(--s-4); }

/* An armed stage is a different SHAPE, not a differently-coloured one: the margin rail thickens,
   the header warms, and the banner is hatched. Readable across a room and without colour. */
.stage[data-state="armed"]   { border-left: 6px solid var(--armed); }
.stage[data-state="armed"] > header { background: var(--armed-soft); border-bottom-color: var(--armed-edge); }
.stage[data-state="armed"] > header .n { color: var(--armed); }
.stage[data-state="unknown"] { border-left: 6px solid var(--broken); }
.stage[data-state="unknown"] > header { background: var(--broken-soft); border-bottom-color: var(--broken-edge); }
.stage[data-state="unknown"] > header .n { color: var(--broken); }
/* Held is a state too, so it gets a shape: a doubled rail, half the weight of armed.
   Colour alone would make it indistinguishable from an unprobed stage. */
.stage[data-state="held"] {
  border-left: 3px solid var(--held);
  box-shadow: inset 5px 0 0 -3px var(--held-soft), inset 6px 0 0 -3px var(--held);
}

/* Stage 02 is an instrument and earns the grid width. The reading stages are a document and
   should be as wide as their measure, not as wide as the page: a 562px paragraph inside a
   1032px box put 470px of permanent dead white beside every line of body text. */
#stage-01, #stage-03, #hints, .why { max-width: 56rem; }

.stage .strip { border-left: 0; border-right: 0; border-top: 0; }

/* ================================================================== tabs (links, no script) */

.tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 0;
  padding: 0 var(--s-4);
  border-bottom: 1px solid var(--rule);
  background: var(--surface-2);
}
/* Undecorated grey text is a caption, not a control: the strip read as one heading and three
   captions. Every tab gets a box on hover; the current one keeps it. */
.tabs a {
  padding: var(--s-2) var(--s-3); font-size: var(--t-m); text-decoration: none;
  color: var(--ink-2); border: 1px solid transparent; border-bottom: 2px solid transparent;
  margin-bottom: -1px; white-space: nowrap; transition: background-color .08s linear;
}
.tabs a:not([aria-current]):hover {
  color: var(--ink); background: color-mix(in srgb, var(--surface) 55%, transparent);
  border-color: var(--rule); border-bottom-color: var(--rule-2);
}
.tabs a[aria-current="page"] {
  color: var(--ink); font-weight: 650; background: var(--surface);
  border-color: var(--rule); border-bottom: 2px solid var(--accent);
}
@supports not (background: color-mix(in srgb, red 55%, transparent)) {
  .tabs a:not([aria-current]):hover { background: var(--surface); }
}

/* Wrapping is the wrong behaviour for a tab strip — at 390 it became four stacked full-width
   rows with the active one a lone block mid-stack. A tab strip scrolls. */
/* A tab strip is one row or it is not a tab strip. Wrapping turns it into a grid of captions
   with one boxed cell adrift in it, so when the tabs outgrow the column the strip scrolls. */
.tabs {
  flex-wrap: nowrap; overflow-x: auto; scroll-snap-type: x proximity;
  scrollbar-width: thin; scrollbar-color: var(--rule-2) transparent;
  -webkit-overflow-scrolling: touch;
}
/* The bar is the affordance: a hidden scrollbar on a strip that runs off the edge is the same
   as a strip with tabs missing. It only paints when there is somewhere to scroll. */
.tabs::-webkit-scrollbar { height: 4px; }
.tabs::-webkit-scrollbar-track { background: transparent; }
.tabs::-webkit-scrollbar-thumb { background: var(--rule-2); border-radius: 2px; }
.tabs a { flex: 0 0 auto; scroll-snap-align: start; }

/* ================================================================== reading prose */

.prose {
  font-family: var(--read);
  font-size: var(--t-r);
  line-height: 1.62;
  color: var(--ink);
}
/* The reading measure belongs to running text. Code, diagrams and tables are evidence, not
   prose: they get the whole column, because an ASCII diagram cut in half teaches nothing. */
.prose > p, .prose > ul, .prose > ol, .prose > blockquote,
.prose > h1, .prose > h2, .prose > h3, .prose > h4, .prose > dl { max-width: 68ch; }
.prose > pre, .prose > table, .prose > .scroller, .prose > figure { max-width: 100%; }
.prose h1, .prose h2, .prose h3, .prose h4 {
  font-family: var(--sans);
  line-height: 1.22;
  letter-spacing: var(--tr-snug);
  text-wrap: balance;
}
.prose h2 { font-size: var(--t-l); font-weight: 650; margin: var(--s-6) 0 var(--s-2); }
.prose h3 { font-size: var(--t-r); font-weight: 650; letter-spacing: var(--tr-snug); margin: var(--s-5) 0 var(--s-2); }
/* h4 separates from h3 by colour, not by dropping below the body it heads. */
.prose h4 { font-size: var(--t-r); font-weight: 650; margin: var(--s-4) 0 var(--s-1); color: var(--ink-2); }

/* A prose heading inside a stage is subordinate to the stage title, which is also an h2. */
.stage .prose h2 { font-size: var(--t-l); }
.prose > :first-child { margin-top: 0; }
.prose p { margin: 0 0 var(--s-3); }
.prose ul, .prose ol { margin: 0 0 var(--s-3); padding-left: 1.3em; }
.prose li { margin-bottom: var(--s-1); }
.prose li::marker { color: var(--muted); }
.prose blockquote {
  font-family: var(--sans);
  font-size: var(--t-base);
  font-weight: 600;
  line-height: 1.45;
  margin: var(--s-4) 0;
  padding: var(--s-1) 0 var(--s-1) var(--s-4);
  border-left: 2px solid var(--accent);
  color: var(--ink);
}
.prose hr { border: 0; border-top: 1px solid var(--rule); margin: var(--s-5) 0; }
.prose table { font-family: var(--sans); }
.prose a { text-decoration: underline; }

code {
  font-family: var(--mono);
  /* Mono at the same nominal size as a serif reads larger. One step down the ladder,
     not a magic ratio. */
  font-size: var(--t-s);
  background: var(--surface-2);
  border: 1px solid var(--rule);
  border-radius: var(--r-1);
  padding: .04em .3em;
  word-break: break-word;
}
td code, th code, .index code { font-size: var(--t-xs); }

/* Code blocks are console surfaces: the same instrument, in both themes. */
pre {
  font-family: var(--mono);
  font-size: var(--t-s);
  line-height: 1.6;
  background: var(--console);
  color: var(--console-ink);
  border: 1px solid var(--console-rule);
  border-radius: var(--r-1);
  padding: var(--s-3) var(--s-4);
  margin: 0 0 var(--s-4);
  overflow-x: auto;
}
pre code { background: none; border: 0; padding: 0; font-size: inherit; color: inherit; }

/* The skip test: an instruction, so it is the one accent-filled block in the reading column. */
.skip {
  font-family: var(--sans);
  background: var(--accent-soft);
  border-left: 2px solid var(--accent);
  padding: var(--s-3) var(--s-4);
  margin: 0 0 var(--s-4);
  font-size: var(--t-m);
  line-height: 1.5;
  color: var(--ink);
  max-width: 68ch;
}
.skip b { display: block; font-family: var(--mono); font-size: var(--t-2xs); font-weight: 600; letter-spacing: var(--tr-label); text-transform: uppercase; color: var(--accent); margin-bottom: var(--s-1); }
.skip p { margin: 0; }

/* Orientation: two columns of context above stage 01. Quieter than .skip on purpose. */
.why {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: var(--s-4) var(--s-6);
  margin: 0 0 var(--s-5);
  padding: var(--s-4) 0;
  border-top: 1px solid var(--rule-2);
  border-bottom: 1px solid var(--rule-2);
}
/* An h2 for heading order; the .eyebrow class carries the whole appearance. */
.why h2 { margin: 0 0 var(--s-2); }
/* This is the first prose on the page and it had the worst setting on it: 14px over a 71
   character measure with tighter leading than the .prose it introduces. */
.why p { margin: 0 0 var(--s-2); font-size: var(--t-base); line-height: 1.6; max-width: 56ch; color: var(--ink-2); }
.why p:last-child { margin-bottom: 0; }
.why > div + div { padding-left: var(--s-6); border-left: 1px solid var(--rule); }
@media (max-width: 760px) {
  .why { grid-template-columns: minmax(0, 1fr); gap: var(--s-4); }
  .why > div + div { padding-left: 0; border-left: 0; border-top: 1px solid var(--rule); padding-top: var(--s-4); }
}
"""

_CONSOLE = """
/* ================================================================== the console */

.objective {
  font-family: var(--read);
  font-size: var(--t-r);
  line-height: 1.5;
  margin: 0 0 var(--s-4);
  padding-left: var(--s-4);
  border-left: 2px solid var(--ink);
  max-width: 68ch;
  color: var(--ink);
}
.objective b { font-family: var(--sans); font-size: var(--t-2xs); font-weight: 600; letter-spacing: var(--tr-label); text-transform: uppercase; color: var(--muted); display: block; margin-bottom: 2px; }

.console { display: grid; gap: var(--s-4); grid-template-columns: minmax(0, 5fr) minmax(0, 6fr); align-items: start; }
/* At 1024 the two-column console left the terminal 409px wide for 523px of output, and the
   column it hid was the one the flag asks for. */
@media (max-width: 1100px) { .console { grid-template-columns: minmax(0, 1fr); } }

/* Both console scrollers are horizontal and must show it. An overlay scrollbar that never
   paints is the same as a hard clip. */
.term .out, .src .lines-wrap { scrollbar-width: thin; scrollbar-color: var(--console-rule) var(--console); }
.term .out::-webkit-scrollbar, .src .lines-wrap::-webkit-scrollbar { height: 10px; }
.term .out::-webkit-scrollbar-track, .src .lines-wrap::-webkit-scrollbar-track { background: var(--console); }
.term .out::-webkit-scrollbar-thumb, .src .lines-wrap::-webkit-scrollbar-thumb {
  background: var(--console-rule); border: 2px solid var(--console); border-radius: 5px;
}

/* The readout follows you down the switch column, which is what a front panel does. */
@media (min-width: 1101px) {
  .console > .panel + .panel { position: sticky; top: var(--s-4); }
}

.panel { border: 1px solid var(--rule); background: var(--surface); }
.panel > h3 {
  margin: 0;
  padding: var(--s-2) var(--s-3);
  border-bottom: 1px solid var(--rule);
  background: var(--surface-2);
  display: flex;
  align-items: baseline;
  gap: var(--s-2);
}
.panel > h3 .fill { flex: 1 1 auto; }
.panel > h3 .side { font-weight: 400; letter-spacing: var(--tr-label-s); text-transform: none; }
.panel > .inner { padding: var(--s-3); }
.panel > .inner.flush { padding: 0; }

/* One switch. Used for both controls and observations so the console has a single row rhythm. */
.control {
  display: flex;
  align-items: flex-start;
  gap: var(--s-3);
  margin: 0;
  padding: var(--s-3) var(--s-3);
  border-bottom: 1px solid var(--rule);
}
/* The reset row is a <form> too, so `form:last-of-type` resolved to .reset and this matched
   nothing at all — the console carried a stacked double rule above the reset foot. */
.control:last-child, .control:has(+ .reset), .control:has(+ .grp) { border-bottom: 0; }
.control .text { flex: 1 1 auto; min-width: 0; }
.control .label { font-size: var(--t-m); font-weight: 650; line-height: 1.35; color: var(--ink); }
.control .detail { font-size: var(--t-s); line-height: 1.45; color: var(--muted); margin-top: 2px; }
.control .mut {
  display: block;
  margin-top: var(--s-2);
  font-family: var(--mono);
  font-size: var(--t-2xs);
  letter-spacing: var(--tr-label-s);
  color: var(--muted);
  background: none;
  border: 0;
  padding: 0;
}
/* Every stateful row carries a rail in the gutter and a chip on its identifier. An observation
   has neither — that is how you tell a switch from a probe without reading a word.
   The explanatory sentence is NOT coloured: amber copy makes neutral text look like a warning
   and halves its contrast. The rail carries the state. */
.control[data-state]            { box-shadow: inset 3px 0 0 var(--rule-2); }
.control[data-state="armed"]    { background: var(--armed-soft); box-shadow: inset 3px 0 0 var(--armed); }
.control[data-state="correct"]  { box-shadow: inset 3px 0 0 var(--held); }
.control[data-state="unknown"]  { box-shadow: inset 3px 0 0 var(--broken); }
.control .mut .s {
  font-weight: 700; text-transform: uppercase; letter-spacing: var(--tr-label-s);
  border: 1px solid currentColor; border-radius: var(--r-1); padding: 0 .35em; margin-left: .15em;
}
.control[data-state="armed"] .mut .s   { color: var(--armed); }
.control[data-state="unknown"] .mut .s { color: var(--broken); }
.control[data-state="correct"] .mut .s { color: var(--held); }

/* A switch that does not respond to the pointer does not look like a switch. */
.control { transition: background-color .08s linear; }
.control:hover, .control:focus-within { background: var(--surface-2); }
.control[data-state="armed"]:hover, .control[data-state="armed"]:focus-within {
  background: color-mix(in srgb, var(--armed-soft) 86%, var(--armed));
}
@supports not (background: color-mix(in srgb, red 86%, blue)) {
  .control[data-state="armed"]:hover { background: var(--armed-soft); }
}

/* Controls change the lab; observations only read it. Same gesture, different consequence,
   so the console names the group before you press anything in it. */
.panel .grp {
  margin: 0; padding: var(--s-2) var(--s-3);
  font-family: var(--mono); font-size: var(--t-2xs); font-weight: 600;
  letter-spacing: var(--tr-label); text-transform: uppercase; color: var(--muted);
  background: var(--surface-2); border-bottom: 1px solid var(--rule);
}
.panel .grp + .control { border-top: 0; }

.panel .reset {
  display: flex;
  align-items: center;
  gap: var(--s-3);
  flex-wrap: wrap;
  margin: 0;
  padding: var(--s-3);
  border-top: 1px solid var(--rule-2);
  background: var(--surface-2);
}
.panel .reset .detail { font-size: var(--t-xs); color: var(--muted); line-height: 1.4; flex: 1 1 12rem; }

/* The result is a terminal: dark in both themes, one prompt line, monospace, and it keeps its
   height when empty so the console does not jump on every post. */
.term { background: var(--console); border-top: 1px solid var(--console-rule); }
.term .ran {
  margin: 0;
  font-family: var(--mono);
  font-size: var(--t-2xs);
  letter-spacing: var(--tr-label-s);
  color: var(--console-dim);
  padding: var(--s-2) var(--s-3);
  border-bottom: 1px solid var(--console-rule);
  white-space: pre-wrap;
  word-break: break-word;
}
.term .ran::before { content: "$ "; color: var(--console-accent); }
.term .out {
  border: 0;
  border-radius: 0;
  font-family: var(--mono);
  font-size: var(--t-s);
  line-height: 1.55;
  color: var(--console-ink);
  padding: var(--s-3);
  margin: 0;
  overflow-x: auto;
  white-space: pre;
  min-height: 7.5rem;
}
.term .out.idle { color: var(--console-dim); white-space: normal; }

/* The flag field is the end of the stage, so it is given its own foot rather than a floating row. */
.flag { border-top: 2px solid var(--rule-2); padding: var(--s-3); background: var(--surface-2); }
.flag .k { display: block; margin-bottom: var(--s-2); }
.flagform { display: flex; gap: var(--s-2); flex-wrap: wrap; }
.flagform input[type="text"] { flex: 1 1 12rem; font-size: var(--t-base); }
.flagform input[type="text"]:focus { border-color: var(--accent); }
/* The one filled button in the console. Everything else on this page is an outline. */
.flagform button {
  background: var(--accent); border-color: var(--accent); color: var(--on-accent);
  padding: var(--c-pad) var(--s-4);
}
.flagform button:hover:not(:disabled) {
  background: var(--accent-2); border-color: var(--accent-2); color: var(--on-accent);
}
.flagnote {
  display: flex;
  gap: var(--s-2);
  align-items: baseline;
  margin: var(--s-3) 0 0;
  padding: var(--s-2) var(--s-3);
  font-size: var(--t-m);
  line-height: 1.4;
  border: 1px solid var(--rule);
  border-radius: var(--r-1);
}
.flagnote b { font-family: var(--mono); font-size: var(--t-2xs); letter-spacing: var(--tr-label); text-transform: uppercase; white-space: nowrap; }
.flagnote.ok  { background: var(--held-soft);   border-color: var(--held-edge);   color: var(--held); }
.flagnote.no  { background: var(--broken-soft); border-color: var(--broken-edge); color: var(--broken); }

#result { scroll-margin-top: var(--s-4); }

.inert-note {
  font-size: var(--t-m);
  line-height: 1.5;
  color: var(--muted);
  background: var(--surface-2);
  border: 1px dashed var(--rule-2);
  border-radius: var(--r-1);
  padding: var(--s-3) var(--s-4);
  margin: 0;
}

/* ================================================================== source panels */

.src { border: 1px solid var(--console-rule); margin-bottom: var(--s-4); background: var(--console); }
.src > .path {
  display: flex;
  align-items: baseline;
  gap: var(--s-2) var(--s-3);
  flex-wrap: wrap;
  font-family: var(--mono);
  font-size: var(--t-2xs);
  color: var(--console-dim);
  padding: var(--s-2) var(--s-3);
  border-bottom: 1px solid var(--console-rule);
}
.src > .path .file { color: var(--console-ink); font-weight: 600; word-break: break-all; }
.src > .path .lines { letter-spacing: var(--tr-label-s); }
.src > .path .cap { font-family: var(--sans); font-size: var(--t-xs); letter-spacing: 0; text-transform: none; color: var(--console-dim); flex: 1 1 14rem; }
.src .lines-wrap { overflow-x: auto; padding: var(--s-2) 0; }
.src table { min-width: 0; width: 100%; font-family: var(--mono); font-size: var(--t-s); line-height: 1.55; }
.src td { border: 0; padding: 0 var(--s-3) 0 0; white-space: pre; color: var(--console-ink); vertical-align: top; }
.src td.n {
  width: 1%;
  text-align: right;
  padding: 0 var(--s-3);
  color: var(--console-dim);
  user-select: none;
  border-right: 1px solid var(--console-rule);
}
.src tr.hit td { background: var(--console-hit); }
.src tr.hit td.n {
  color: var(--console-armed);
  font-weight: 700;
  border-right-color: var(--console-armed);
  box-shadow: inset 3px 0 0 var(--console-armed);
}
.src .inner { padding: var(--s-3); }

/* ================================================================== hints */

.hint { border: 1px solid var(--control-edge); border-radius: var(--r-1); margin-bottom: var(--s-1); background: var(--surface); }
.hint > summary {
  cursor: pointer;
  padding: var(--s-2) var(--s-3);
  font-size: var(--t-m);
  font-weight: 600;
  list-style: none;
  display: flex;
  align-items: baseline;
  gap: var(--s-2);
}
.hint > summary::-webkit-details-marker { display: none; }
.hint > summary::before { content: "+"; font-family: var(--mono); color: var(--muted); font-weight: 700; }
.hint[open] > summary::before { content: "\\2212"; }
.hint[open] > summary { border-bottom: 1px solid var(--rule); }
/* A summary reading "Hint 1" is a 1000px bordered row carrying six characters. The face now
   carries the question itself, a number, and the word that says it opens. */
.hint > summary .i { font-family: var(--mono); font-size: var(--t-2xs); font-weight: 700; letter-spacing: var(--tr-label-s); color: var(--accent); }
.hint > summary .t { min-width: 0; }
.hint > summary .fill { flex: 1 1 auto; }
.hint > summary .more { font-family: var(--mono); font-size: var(--t-2xs); font-weight: 600; letter-spacing: var(--tr-label); text-transform: uppercase; color: var(--muted); }
.hint[open] > summary .more { visibility: hidden; }
.hint > summary:hover { background: var(--surface-2); }
.hint .inner { padding: var(--s-3); font-size: var(--t-m); line-height: 1.55; color: var(--ink-2); }
.hint .inner p { margin: 0; }

/* ================================================================== footer */

.foot {
  margin-top: var(--s-7);
  padding-top: var(--s-3);
  border-top: 1px solid var(--rule);
  display: flex;
  flex-wrap: wrap;
  gap: var(--s-2) var(--s-5);
  font-family: var(--mono);
  font-size: var(--t-2xs);
  letter-spacing: var(--tr-label-s);
  color: var(--muted);
}
.foot .fill { flex: 1 1 auto; }
.foot a { color: var(--muted); }

/* ================================================================== narrow */

@media (max-width: 560px) {
  body { padding-inline: var(--s-3); }
  .lede h1 { font-size: var(--t-2xl); }
  .lede .standfirst { font-size: var(--t-r); }
  .chead h1 { font-size: var(--t-xl); }
  .chead .summary { font-size: var(--t-r); }
  .stage > .body { padding: var(--s-3); }
  .tabs { padding-inline: var(--s-2); }

  /* A 21px tap target is not a tap target. */
  .masthead nav a { padding: var(--s-3) 0 1px; }

  /* Below 560 the index stops being a table. Five columns in 366px squeezed the description to
     93px — one sentence over thirteen lines — and pushed a whole column off-screen inside a
     scroller nothing marked as scrollable. Each row becomes a block: identifier, title,
     description, then the figures as a line of chips underneath. */
  /* Only the index scrollers: .scroller also wraps every prose table, and those still scroll. */
  .sec > .scroller, .trackblock > .scroller { overflow-x: visible; }
  .index, .index tbody, .index tr, .index td { display: block; width: auto; }
  /* `.index .id` and `.index .name` outrank `.index td`, so they have to be unset by name or
     they stay at width:1% and spill their text past the right edge of the page. */
  .index td.id, .index td.name { width: auto; white-space: normal; padding-right: 0; }
  /* Not merely hidden: `display: block` above has already dropped the header-to-cell
     association, so a visually hidden thead is a run of stray words before the first row. */
  .index thead { display: none; }
  .index tbody tr { padding: var(--s-3) 0; border-bottom: 1px solid var(--rule); }
  .index tbody tr:last-child { border-bottom: 0; }
  .index td { border: 0; padding: 0; }
  .index td.id { font-size: var(--t-2xs); margin-bottom: 2px; }
  .index .name a { font-size: var(--t-r); }
  .index td.claim, .index td.what { margin-top: var(--s-1); max-width: 40ch; }
  .index td.n, .index th.n { width: auto; text-align: left; }
  .index td.n:last-child, .index th.num:last-child { min-width: 0; }
  .index tbody td.n { display: inline-block; margin: var(--s-2) var(--s-4) 0 0;
                      font-size: var(--t-2xs); color: var(--muted); }
  td.n > .bar { justify-content: flex-start; }
  /* The column heads are gone here, so the two bare figures have to name their own unit. */
  .trackblock .index tbody td.n:last-child::after { content: " pts"; }
  .sec .index tbody td.n:nth-last-child(2)::after { content: " challenges"; }
}

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation-duration: .001ms !important; animation-iteration-count: 1 !important; transition-duration: .001ms !important; scroll-behavior: auto !important; }
}

@media print {
  body { background: #fff; color: #000; padding: 0; }
  .wrap, .wrap.wide { max-width: none; }

  /* Class selectors: a bare `form` is outranked by .control / .flagform / .panel .reset. */
  .spine, .masthead nav, #themeswitch, .skiplink,
  /* .panel .grp labels the two halves of a console whose rows are all forms: with the forms
     gone the labels would head nothing. */
  form, form.control, form.flagform, .panel .reset, .strip form,
  .panel .grp { display: none !important; }

  /* Console surfaces invert for paper: browsers drop background graphics by default,
     and the console ink is 1.48:1 on white. */
  pre, .term, .term .out, .term .ran, .src, .src > .path {
    background: #fff !important; color: #000 !important; border-color: #999 !important;
  }
  .src td, .src > .path .file, .term .out, pre code { color: #000 !important; }
  .src td.n, .term .ran, .src > .path .cap { color: #555 !important; }
  .src tr.hit td { background: #f0f0f0 !important; }

  .layout { display: block; }
  .console { display: block; }
  .stage, .panel, .src, .hint { break-inside: avoid; }
  .hint .inner, .hint[open] .inner { display: block; }
}
"""

STYLESHEET = _TOKENS + _BASE + _TABLES + _CHALLENGE + _CONSOLE
