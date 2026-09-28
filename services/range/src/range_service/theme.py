"""The Range's stylesheet.

DESIGN DIRECTION — "Workspace"
==============================

A modern SaaS workspace for security practitioners: the calm, dense, card-based surface of a
product people use for hours — a cloud console, an issue tracker, a code host — rather than a
marketing page or a retro instrument panel. Content leads; chrome recedes; colour is rare enough
that when it appears it means something.

Palette — neutrals, one accent, three states
--------------------------------------------
    Neutrals   a cool gray ramp (--bg, --surface, --surface-2/3, --border, --ink ... --faint).
               White cards on a very light gray canvas in light mode; layered near-black
               surfaces in dark mode.
    Accent     indigo (--accent). Interactive affordances, current location, identifiers.
               Never used for state.
    States     --held (green), --armed (amber), --broken (red), each with a soft fill and an edge
               tone. Used ONLY for the condition of the lab and for answers being right or wrong.
               A learner must be able to read "armed" at a glance, which fails the moment the
               accent starts meaning something similar.
    Console    the result terminal and code blocks are dark in both themes, because output that
               changes colour with the OS stops looking like the same output.

Contrast: body text (--ink-2) and muted text (--muted) clear 4.5:1 on every surface they are set
on, in both themes; control edges (--border-strong) clear 3:1 against the canvas.

Type — system faces, no webfont
-------------------------------
The lab runs offline, and a face that silently fails to load is a page that silently changes
shape. So the stacks name faces that are already on the machine: Inter or the platform UI face for
everything, and a platform monospace for anything the *system* said — identifiers, paths, output.
One family for reading and UI is the modern convention, and it removes the page's old split
personality between "the lesson" and "the instrument".

Layout
------
A full-width top bar (brand, navigation, theme), then a centred content column. The challenge page
is a two-column workspace: a sticky stage navigator on the left, stacked stage cards on the right.
The console inside stage 02 stacks the environment panel above a full-width dark result pane,
because observation output is a wide table and half a column made every result scroll sideways.
Below 1024px the workspace collapses to one column; below 640px the gutters tighten to 16px.

Rules that are structural rather than decorative
------------------------------------------------
  * State is always said in words as well as colour (the stage navigator, the alert, the control
    badge), so nothing depends on colour vision.
  * Motion explains interaction — a hover, an open disclosure — stays under 200ms, and
    `prefers-reduced-motion` removes it.
  * Every colour is defined on bare `:root` first, so a viewer on "system" gets a complete palette.
"""

_TOKENS = """
:root {
  --bg:            #F5F6F8;
  --surface:       #FFFFFF;
  --surface-2:     #F9FAFB;
  --surface-3:     #F2F4F7;
  --border:        #E4E7EC;
  --border-strong: #C7CDD6;
  --ink:           #101828;
  --ink-2:         #344054;
  --muted:         #5D6679;
  --faint:         #8A93A5;

  --accent:        #4F46E5;
  --accent-hover:  #4338CA;
  --accent-soft:   #EEF0FF;
  --accent-edge:   #C7CBFB;
  --accent-ink:    #3730A3;
  --on-accent:     #FFFFFF;

  --held:          #067647;
  --held-soft:     #ECFDF3;
  --held-edge:     #ABEFC6;
  --armed:         #B54708;
  --armed-soft:    #FFFAEB;
  --armed-edge:    #FEDF89;
  --broken:        #B42318;
  --broken-soft:   #FEF3F2;
  --broken-edge:   #FECDCA;

  --hit:           #FFF6CC;
  --hit-edge:      #F5C542;

  --console:       #0F1422;
  --console-2:     #161C2D;
  --console-ink:   #D8DEE9;
  --console-dim:   #8B95A8;
  --console-rule:  #232B3E;
  --console-accent:#A5B4FC;

  --focus-ring:    0 0 0 3px rgba(79, 70, 229, .28);

  --sh-xs: 0 1px 2px rgba(16, 24, 40, .05);
  --sh-sm: 0 1px 3px rgba(16, 24, 40, .08), 0 1px 2px rgba(16, 24, 40, .04);
  --sh-md: 0 6px 16px -4px rgba(16, 24, 40, .10), 0 2px 4px -2px rgba(16, 24, 40, .05);
  --sh-lg: 0 16px 32px -8px rgba(16, 24, 40, .14), 0 4px 8px -4px rgba(16, 24, 40, .06);

  --sans: "Inter", "InterVariable", system-ui, -apple-system, "Segoe UI Variable Text", "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  --mono: ui-monospace, "JetBrains Mono", "SF Mono", "Cascadia Code", "Cascadia Mono", Menlo, Consolas, "Liberation Mono", monospace;

  --t-xs:  .75rem;     /* 12 */
  --t-s:   .8125rem;   /* 13 */
  --t-m:   .875rem;    /* 14 */
  --t-base:.9375rem;   /* 15 */
  --t-r:   1rem;       /* 16 */
  --t-l:   1.125rem;   /* 18 */
  --t-xl:  1.25rem;    /* 20 */
  --t-2xl: 1.5rem;     /* 24 */
  --t-3xl: 1.875rem;   /* 30 */
  --t-4xl: 2.5rem;     /* 40 */

  --s-1: 4px;  --s-2: 8px;  --s-3: 12px; --s-4: 16px;
  --s-5: 20px; --s-6: 24px; --s-7: 32px; --s-8: 48px; --s-9: 64px;

  --r-sm: 6px; --r: 8px; --r-lg: 12px; --r-xl: 16px; --r-pill: 999px;

  --topbar-h: 60px;
  --ease: cubic-bezier(.2, .7, .3, 1);

  color-scheme: light;
}

@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg:            #0B0E14;
    --surface:       #121620;
    --surface-2:     #161B26;
    --surface-3:     #1C2230;
    --border:        #252C3B;
    --border-strong: #3A4357;
    --ink:           #F2F4F7;
    --ink-2:         #CDD3DE;
    --muted:         #9AA3B5;
    --faint:         #6E788C;
    --accent:        #8B8FF9;
    --accent-hover:  #A5A9FB;
    --accent-soft:   rgba(99, 102, 241, .14);
    --accent-edge:   rgba(139, 143, 249, .38);
    --accent-ink:    #C7CAFD;
    --on-accent:     #0B0E14;
    --held:          #47CD89;
    --held-soft:     rgba(23, 178, 106, .12);
    --held-edge:     rgba(71, 205, 137, .34);
    --armed:         #FDB022;
    --armed-soft:    rgba(247, 144, 9, .12);
    --armed-edge:    rgba(253, 176, 34, .36);
    --broken:        #F97066;
    --broken-soft:   rgba(240, 68, 56, .12);
    --broken-edge:   rgba(249, 112, 102, .36);
    --hit:           rgba(250, 204, 21, .12);
    --hit-edge:      rgba(250, 204, 21, .45);
    --console:       #080B12;
    --console-2:     #0F1420;
    --console-rule:  #1E2536;
    --focus-ring:    0 0 0 3px rgba(139, 143, 249, .35);
    --sh-xs: 0 1px 2px rgba(0, 0, 0, .3);
    --sh-sm: 0 1px 3px rgba(0, 0, 0, .35);
    --sh-md: 0 8px 20px -6px rgba(0, 0, 0, .5);
    --sh-lg: 0 18px 36px -10px rgba(0, 0, 0, .6);
    color-scheme: dark;
  }
}

:root[data-theme="dark"] {
  --bg:            #0B0E14;
  --surface:       #121620;
  --surface-2:     #161B26;
  --surface-3:     #1C2230;
  --border:        #252C3B;
  --border-strong: #3A4357;
  --ink:           #F2F4F7;
  --ink-2:         #CDD3DE;
  --muted:         #9AA3B5;
  --faint:         #6E788C;
  --accent:        #8B8FF9;
  --accent-hover:  #A5A9FB;
  --accent-soft:   rgba(99, 102, 241, .14);
  --accent-edge:   rgba(139, 143, 249, .38);
  --accent-ink:    #C7CAFD;
  --on-accent:     #0B0E14;
  --held:          #47CD89;
  --held-soft:     rgba(23, 178, 106, .12);
  --held-edge:     rgba(71, 205, 137, .34);
  --armed:         #FDB022;
  --armed-soft:    rgba(247, 144, 9, .12);
  --armed-edge:    rgba(253, 176, 34, .36);
  --broken:        #F97066;
  --broken-soft:   rgba(240, 68, 56, .12);
  --broken-edge:   rgba(249, 112, 102, .36);
  --hit:           rgba(250, 204, 21, .12);
  --hit-edge:      rgba(250, 204, 21, .45);
  --console:       #080B12;
  --console-2:     #0F1420;
  --console-rule:  #1E2536;
  --focus-ring:    0 0 0 3px rgba(139, 143, 249, .35);
  --sh-xs: 0 1px 2px rgba(0, 0, 0, .3);
  --sh-sm: 0 1px 3px rgba(0, 0, 0, .35);
  --sh-md: 0 8px 20px -6px rgba(0, 0, 0, .5);
  --sh-lg: 0 18px 36px -10px rgba(0, 0, 0, .6);
  color-scheme: dark;
}
"""

_BASE = """
*, *::before, *::after { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; text-size-adjust: 100%; scroll-padding-top: calc(var(--topbar-h) + 16px); }
body {
  margin: 0;
  background: var(--bg);
  color: var(--ink-2);
  font: 400 var(--t-base)/1.55 var(--sans);
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  font-feature-settings: "cv11", "ss01";
  text-rendering: optimizeLegibility;
}
h1, h2, h3, h4 { color: var(--ink); margin: 0; font-weight: 650; letter-spacing: -.011em; }
p { margin: 0; }
a { color: var(--accent); text-decoration: none; }
a:hover { color: var(--accent-hover); }
code, pre, kbd, samp { font-family: var(--mono); }
b, strong { color: var(--ink); font-weight: 600; }
::selection { background: var(--accent-soft); color: var(--ink); }
:focus { outline: none; }
:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; border-radius: var(--r-sm); }
[hidden] { display: none !important; }

.skiplink {
  position: absolute; left: var(--s-4); top: -60px; z-index: 100;
  background: var(--accent); color: var(--on-accent); padding: var(--s-2) var(--s-4);
  border-radius: var(--r); font-weight: 600; font-size: var(--t-m);
}
.skiplink:focus { top: var(--s-3); color: var(--on-accent); }

/* ---- the top bar ------------------------------------------------------------------------- */
.topbar {
  position: sticky; top: 0; z-index: 50;
  background: color-mix(in srgb, var(--surface) 86%, transparent);
  -webkit-backdrop-filter: saturate(180%) blur(12px);
  backdrop-filter: saturate(180%) blur(12px);
  border-bottom: 1px solid var(--border);
}
.masthead {
  max-width: 1360px; margin: 0 auto; height: var(--topbar-h);
  display: flex; align-items: center; gap: var(--s-3);
  padding: 0 var(--s-6);
}
.masthead .mark { font-size: var(--t-base); font-weight: 700; letter-spacing: -.015em; }
.masthead .mark { flex: none; }
.masthead .mark a { display: inline-flex; align-items: center; gap: 10px; color: var(--ink); white-space: nowrap; }
.masthead .logo {
  width: 30px; height: 30px; border-radius: var(--r);
  display: inline-grid; place-items: center; flex: none;
  background: linear-gradient(135deg, #6366F1 0%, #4F46E5 55%, #3730A3 100%);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, .25), var(--sh-xs);
}
.masthead .logo svg { width: 18px; height: 18px; }
.masthead .sep { width: 1px; height: 20px; background: var(--border); }
.masthead .lab {
  font-size: var(--t-xs); font-weight: 600; color: var(--muted);
  padding: 3px 8px; border: 1px solid var(--border); border-radius: var(--r-pill);
  background: var(--surface-2); white-space: nowrap;
}
.masthead .spacer { flex: 1; }
.masthead nav { display: flex; align-items: center; gap: 2px; min-width: 0; }
.masthead nav a {
  font-size: var(--t-m); font-weight: 500; color: var(--muted);
  padding: 7px 12px; border-radius: var(--r); white-space: nowrap;
  transition: background-color .14s var(--ease), color .14s var(--ease);
}
.masthead nav a:hover { color: var(--ink); background: var(--surface-3); }
.masthead nav a[aria-current] { color: var(--ink); background: var(--surface-3); font-weight: 600; }
#themeslot { margin-left: var(--s-2); }
#themeswitch {
  font: 500 var(--t-s)/1 var(--sans); color: var(--ink-2);
  padding: 7px 12px; border-radius: var(--r-pill);
  border: 1px solid var(--border); background: var(--surface); box-shadow: var(--sh-xs);
  cursor: pointer; display: inline-flex; align-items: center; gap: 6px;
}
#themeswitch::before { content: "\\25D0"; font-size: 13px; color: var(--muted); }
#themeswitch:hover { border-color: var(--border-strong); color: var(--ink); }

/* ---- the page column --------------------------------------------------------------------- */
.wrap { max-width: 1200px; margin: 0 auto; padding: var(--s-7) var(--s-6) var(--s-9); }
.wrap.wide { max-width: 1360px; }
main:focus { outline: none; }

/* ---- the environment alert --------------------------------------------------------------- */
.strip {
  display: flex; align-items: center; flex-wrap: wrap; gap: var(--s-2) var(--s-3);
  padding: 10px var(--s-4); margin: 0 0 var(--s-6);
  background: var(--surface); border: 1px solid var(--border); border-radius: var(--r-lg);
  box-shadow: var(--sh-xs); font-size: var(--t-m); color: var(--ink-2);
}
.strip .dot {
  width: 8px; height: 8px; border-radius: 50%; flex: none; background: var(--faint);
  box-shadow: 0 0 0 4px var(--surface-3);
}
.strip b { font-weight: 600; color: var(--ink); }
.strip .fill { flex: 1; }
.strip .ids {
  font: 500 var(--t-xs)/1.4 var(--mono); color: var(--muted);
  max-width: 100%; overflow-wrap: anywhere;
}
.strip form { margin: 0; }
.strip.held .dot { background: var(--held); box-shadow: 0 0 0 4px var(--held-soft); }
.strip.armed { background: var(--armed-soft); border-color: var(--armed-edge); }
.strip.armed .dot { background: var(--armed); box-shadow: 0 0 0 4px var(--armed-edge); animation: pulse 2s var(--ease) infinite; }
.strip.armed b, .strip.armed span:not(.dot):not(.fill) { color: var(--armed); }
.strip.unknown { background: var(--broken-soft); border-color: var(--broken-edge); }
.strip.unknown .dot { background: var(--broken); box-shadow: 0 0 0 4px var(--broken-edge); }
.strip.unknown b, .strip.unknown span:not(.dot):not(.fill) { color: var(--broken); }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: .45; } }

/* ---- buttons ----------------------------------------------------------------------------- */
button, .btn {
  -webkit-appearance: none; appearance: none;
  display: inline-flex; align-items: center; justify-content: center; gap: 6px;
  font: 600 var(--t-m)/1.25 var(--sans); color: var(--ink);
  padding: 8px 14px; border-radius: var(--r);
  background: var(--surface); border: 1px solid var(--border-strong); box-shadow: var(--sh-xs);
  cursor: pointer; white-space: nowrap; text-decoration: none;
  transition: background-color .14s var(--ease), border-color .14s var(--ease),
              color .14s var(--ease), box-shadow .14s var(--ease), transform .14s var(--ease);
}
button:hover, .btn:hover { background: var(--surface-2); color: var(--ink); }
button:active, .btn:active { transform: translateY(1px); }
button:focus-visible, .btn:focus-visible { outline: none; box-shadow: var(--focus-ring); }
.btn.primary, button.restore, .flagform button {
  background: var(--accent); border-color: var(--accent); color: var(--on-accent);
  box-shadow: var(--sh-xs), inset 0 1px 0 rgba(255, 255, 255, .14);
}
.btn.primary:hover, button.restore:hover, .flagform button:hover {
  background: var(--accent-hover); border-color: var(--accent-hover); color: var(--on-accent);
}
.btn.quiet { background: var(--surface); }
button.arm { color: var(--armed); border-color: var(--armed-edge); background: var(--surface); }
button.arm:hover { background: var(--armed-soft); color: var(--armed); }
button.small { padding: 5px 10px; font-size: var(--t-s); }
.btn.primary, .btn.quiet { padding: 10px 18px; font-size: var(--t-base); border-radius: var(--r); }

/* ---- page headers ------------------------------------------------------------------------ */
.eyebrow {
  display: inline-flex; align-items: center; gap: 6px;
  font-size: var(--t-xs); font-weight: 600; letter-spacing: .06em; text-transform: uppercase;
  color: var(--accent);
}
.eyebrow a { color: inherit; }
.eyebrow a:hover { color: var(--accent-hover); text-decoration: underline; text-underline-offset: 3px; }
.chead { margin: 0 0 var(--s-7); }
.chead .eyebrow { margin-bottom: var(--s-3); }
.chead h1 { font-size: var(--t-3xl); line-height: 1.2; font-weight: 700; letter-spacing: -.022em; }
.chead .summary { margin-top: var(--s-3); font-size: var(--t-l); line-height: 1.55; color: var(--muted); max-width: 72ch; }
.chead .facts { display: flex; flex-wrap: wrap; gap: var(--s-2); margin-top: var(--s-5); }
.chead .facts span {
  font-size: var(--t-s); color: var(--muted);
  padding: 4px 10px; border-radius: var(--r-pill);
  background: var(--surface); border: 1px solid var(--border); box-shadow: var(--sh-xs);
}
.chead .facts b { color: var(--ink); font-variant-numeric: tabular-nums; }

.sec { margin-top: var(--s-8); }
.sec > h2 { font-size: var(--t-xl); font-weight: 650; }
.sec > .note { margin: 6px 0 var(--s-5); color: var(--muted); max-width: 72ch; font-size: var(--t-base); }
.sec > .note a { font-weight: 500; }

.inert-note {
  padding: var(--s-4) var(--s-5); border-radius: var(--r-lg);
  background: var(--surface-2); border: 1px dashed var(--border-strong);
  color: var(--muted); font-size: var(--t-m);
}

/* ---- footer ------------------------------------------------------------------------------ */
.foot {
  margin-top: var(--s-9); padding-top: var(--s-5); border-top: 1px solid var(--border);
  display: flex; flex-wrap: wrap; align-items: center; gap: var(--s-2) var(--s-4);
  font-size: var(--t-s); color: var(--faint);
}
.foot .fill { flex: 1; }
.foot span:not(.fill) + span:not(.fill)::before { content: "·"; margin-right: var(--s-4); color: var(--border-strong); }
"""

_TABLES = """
/* ---- tables in cards --------------------------------------------------------------------- */
.scroller {
  overflow-x: auto; background: var(--surface);
  border: 1px solid var(--border); border-radius: var(--r-lg); box-shadow: var(--sh-xs);
}
table { width: 100%; border-collapse: separate; border-spacing: 0; font-size: var(--t-m); }
th {
  text-align: left; font-size: var(--t-xs); font-weight: 600; color: var(--muted);
  letter-spacing: .04em; text-transform: uppercase;
  padding: 10px var(--s-4); background: var(--surface-2); border-bottom: 1px solid var(--border);
  white-space: nowrap;
}
td { padding: 14px var(--s-4); border-bottom: 1px solid var(--border); vertical-align: top; }
tbody tr:last-child td { border-bottom: 0; }
th.num, td.n, td.num { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }

table.index tbody tr { transition: background-color .12s var(--ease); }
table.index tbody tr:hover { background: var(--surface-2); }
table.index td.id {
  width: 1%; white-space: nowrap;
  font: 600 var(--t-s)/1.5 var(--mono); color: var(--muted);
}
table.index td.name { font-weight: 600; color: var(--ink); min-width: 180px; }
table.index td.name a { color: var(--ink); }
table.index td.name a:hover { color: var(--accent); }
table.index tr:hover td.name a { color: var(--accent); }
table.index td.claim, table.index td.what { color: var(--muted); line-height: 1.5; }
table.index tr.inert td.name a { color: var(--ink-2); }
table.index tr[data-solved="1"] td.name a::after {
  content: "Solved"; margin-left: var(--s-2); vertical-align: 2px;
  font: 600 10.5px/1 var(--sans); letter-spacing: .02em;
  padding: 3px 7px; border-radius: var(--r-pill);
  color: var(--held); background: var(--held-soft); border: 1px solid var(--held-edge);
}

/* ---- progress ---------------------------------------------------------------------------- */
.bar { display: inline-flex; align-items: center; gap: var(--s-2); }
.bar .track {
  width: 72px; height: 6px; border-radius: var(--r-pill); background: var(--surface-3);
  overflow: hidden; display: inline-block; box-shadow: inset 0 0 0 1px var(--border);
}
.bar .track i { display: block; height: 100%; background: var(--accent); border-radius: inherit; transition: width .3s var(--ease); }
.bar.done .track i { background: var(--held); }
.bar .n { font-size: var(--t-xs); font-weight: 600; color: var(--muted); font-variant-numeric: tabular-nums; min-width: 28px; }

/* ---- the landing page -------------------------------------------------------------------- */
.lede {
  display: grid; grid-template-columns: minmax(0, 1fr) 380px; gap: var(--s-7);
  align-items: start; padding: var(--s-8) var(--s-7);
  background:
    radial-gradient(1000px 360px at 0% 0%, var(--accent-soft), transparent 70%),
    var(--surface);
  border: 1px solid var(--border); border-radius: var(--r-xl); box-shadow: var(--sh-sm);
}
.lede h1 {
  margin-top: var(--s-4); font-size: var(--t-4xl); line-height: 1.1; font-weight: 750;
  letter-spacing: -.028em; max-width: 16ch;
}
.lede .standfirst { margin-top: var(--s-5); font-size: var(--t-l); line-height: 1.6; color: var(--ink-2); max-width: 58ch; }
.lede .sub { margin-top: var(--s-3); color: var(--muted); max-width: 60ch; }

.rail { display: flex; flex-direction: column; gap: var(--s-4); }
.readout {
  display: grid; grid-template-columns: 1fr 1fr; gap: 1px;
  background: var(--border); border: 1px solid var(--border); border-radius: var(--r-lg);
  overflow: hidden; box-shadow: var(--sh-xs);
}
.readout .row { background: var(--surface); padding: 14px var(--s-4); display: flex; flex-direction: column; gap: 4px; }
.readout .row .k { font-size: var(--t-xs); font-weight: 500; color: var(--muted); }
.readout .row .v { font-size: var(--t-2xl); font-weight: 700; color: var(--ink); letter-spacing: -.02em; font-variant-numeric: tabular-nums; }
.readout .row .v .u { font-size: var(--t-m); font-weight: 500; color: var(--faint); }
.readout .row.state { grid-column: 1 / -1; flex-direction: row; align-items: center; justify-content: space-between; }
.readout .row.state .k::before {
  content: ""; display: inline-block; width: 8px; height: 8px; border-radius: 50%;
  margin-right: 8px; vertical-align: 1px; background: var(--faint);
}
.readout .row.state .v { font-size: var(--t-l); }
.readout .row.state.held .k::before { background: var(--held); }
.readout .row.state.held .v { color: var(--held); }
.readout .row.state.armed { background: var(--armed-soft); }
.readout .row.state.armed .k::before { background: var(--armed); }
.readout .row.state.armed .v { color: var(--armed); }
.readout .row.state.unknown { background: var(--broken-soft); }
.readout .row.state.unknown .k::before { background: var(--broken); }
.readout .row.state.unknown .v { color: var(--broken); }
.rail .go { display: grid; grid-template-columns: 1fr 1fr; gap: var(--s-2); }
.rail .go .btn { width: 100%; }

.key {
  margin: 0; padding: var(--s-3) var(--s-4); display: grid; gap: var(--s-2);
  background: var(--surface-2); border: 1px solid var(--border); border-radius: var(--r-lg);
}
.key div { display: grid; grid-template-columns: 10px 90px 1fr; align-items: start; gap: var(--s-2); }
.key dt { font-size: var(--t-s); font-weight: 600; color: var(--ink); }
.key dd { margin: 0; font-size: var(--t-s); color: var(--muted); }
.sw { width: 8px; height: 8px; border-radius: 50%; display: inline-block; margin-top: 6px; }
.sw.held { background: var(--held); }
.sw.armed { background: var(--armed); }
.sw.unknown { background: var(--broken); }

.routes { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--s-4); }
.route {
  display: flex; flex-direction: column; gap: var(--s-3);
  padding: var(--s-5); background: var(--surface);
  border: 1px solid var(--border); border-radius: var(--r-lg); box-shadow: var(--sh-xs);
  transition: box-shadow .16s var(--ease), transform .16s var(--ease), border-color .16s var(--ease);
}
.route:hover { box-shadow: var(--sh-md); transform: translateY(-2px); border-color: var(--border-strong); }
.routes.flat .route:hover { transform: none; box-shadow: var(--sh-xs); border-color: var(--border); }
.route .k { font-size: var(--t-xs); font-weight: 600; letter-spacing: .05em; text-transform: uppercase; color: var(--accent); }
.route p { color: var(--muted); font-size: var(--t-m); line-height: 1.6; flex: 1; }
.route .go {
  display: flex; align-items: center; justify-content: space-between; gap: var(--s-2);
  font-weight: 600; font-size: var(--t-m); color: var(--ink);
  padding: 10px var(--s-3); margin: 0 calc(-1 * var(--s-2)) calc(-1 * var(--s-2));
  border-radius: var(--r); background: var(--surface-2); border: 1px solid var(--border);
}
.route .go:hover { color: var(--accent); border-color: var(--accent-edge); background: var(--accent-soft); }
.route .go .arrow { transition: transform .16s var(--ease); }
.route .go:hover .arrow { transform: translateX(3px); }
.routes.flat { counter-reset: step; }
.routes.flat .route .k::before {
  counter-increment: step; content: counter(step);
  display: inline-grid; place-items: center; width: 22px; height: 22px; margin-right: 8px;
  border-radius: 50%; background: var(--accent-soft); color: var(--accent-ink);
  font-size: 11px; letter-spacing: 0;
}

/* ---- the catalogue ----------------------------------------------------------------------- */
.tracknav {
  position: sticky; top: calc(var(--topbar-h) + 8px); z-index: 20;
  display: flex; flex-wrap: wrap; gap: 4px; overflow-x: auto; scrollbar-width: none;
  padding: 6px; margin: 0 0 var(--s-6);
  background: color-mix(in srgb, var(--surface) 90%, transparent);
  -webkit-backdrop-filter: blur(10px); backdrop-filter: blur(10px);
  border: 1px solid var(--border); border-radius: var(--r-lg); box-shadow: var(--sh-sm);
}
.tracknav::-webkit-scrollbar { display: none; }
.tracknav a {
  display: inline-flex; align-items: center; gap: 8px; flex: none;
  padding: 6px 12px; border-radius: var(--r); font-size: var(--t-s); font-weight: 500; color: var(--ink-2);
  transition: background-color .14s var(--ease), color .14s var(--ease);
}
.tracknav a:hover { background: var(--surface-3); color: var(--ink); }
.tracknav a .n { font: 600 var(--t-xs)/1 var(--mono); color: var(--faint); }

.trackblock {
  margin-top: var(--s-6); background: var(--surface);
  border: 1px solid var(--border); border-radius: var(--r-xl); box-shadow: var(--sh-xs);
  overflow: hidden;
}
.trackblock .band { display: flex; align-items: center; gap: var(--s-3); padding: var(--s-5) var(--s-5) 0; }
.trackblock .band > .n {
  display: inline-grid; place-items: center; width: 36px; height: 36px; flex: none;
  border-radius: var(--r); background: var(--accent-soft); color: var(--accent-ink);
  font: 700 var(--t-m)/1 var(--mono);
}
.trackblock .band h2 { font-size: var(--t-l); font-weight: 650; }
.trackblock .band .fill { flex: 1; }
.trackblock .claimline { padding: 6px var(--s-5) var(--s-5) calc(var(--s-5) + 36px + var(--s-3)); color: var(--muted); font-size: var(--t-m); }
.trackblock .scroller { border: 0; border-top: 1px solid var(--border); border-radius: 0; box-shadow: none; }
"""

_CHALLENGE = """
/* ---- the challenge workspace ------------------------------------------------------------- */
.layout { display: grid; grid-template-columns: 248px minmax(0, 1fr); gap: var(--s-7); align-items: start; }
.layout > * { min-width: 0; }
.col { display: flex; flex-direction: column; gap: var(--s-6); min-width: 0; }

.spine {
  position: sticky; top: calc(var(--topbar-h) + var(--s-5));
  background: var(--surface); border: 1px solid var(--border); border-radius: var(--r-lg);
  box-shadow: var(--sh-xs); padding: var(--s-2);
}
.spine ol { list-style: none; margin: 0; padding: 0; display: grid; gap: 2px; }
.spine li a {
  display: flex; flex-direction: column; gap: 2px;
  padding: 10px var(--s-3); border-radius: var(--r);
  font-size: var(--t-m); font-weight: 600; color: var(--ink);
  border-left: 3px solid transparent;
  transition: background-color .14s var(--ease), border-color .14s var(--ease);
}
.spine li a:hover { background: var(--surface-3); }
.spine li a[aria-current] { background: var(--accent-soft); border-left-color: var(--accent); color: var(--accent-ink); }
.spine li a .k { font-size: var(--t-xs); font-weight: 600; letter-spacing: .04em; text-transform: uppercase; color: var(--faint); }
.spine li a[aria-current] .k { color: var(--accent); }
.spine li.armed a .k { color: var(--armed); }
.spine li.armed a { border-left-color: var(--armed); }
.spine li.unknown a .k { color: var(--broken); }
.spine li.unknown a { border-left-color: var(--broken); }
.spine .foot {
  margin: var(--s-2) 0 0; padding: var(--s-3) var(--s-3) var(--s-2);
  border-top: 1px solid var(--border);
  font: 500 var(--t-xs)/1.6 var(--mono); color: var(--faint); overflow-wrap: anywhere;
}

/* orientation: two info cards */
.why { display: grid; grid-template-columns: 1fr 1fr; gap: var(--s-4); }
.why > div {
  padding: var(--s-5); background: var(--surface);
  border: 1px solid var(--border); border-radius: var(--r-lg); box-shadow: var(--sh-xs);
}
.why > div:first-child { background: linear-gradient(180deg, var(--accent-soft), var(--surface) 70%); }
.why h2.eyebrow { margin: 0 0 var(--s-3); }
.why p { font-size: var(--t-m); line-height: 1.65; color: var(--ink-2); }
.why p + p { margin-top: var(--s-2); }

/* stage cards */
.stage {
  background: var(--surface); border: 1px solid var(--border); border-radius: var(--r-xl);
  box-shadow: var(--sh-xs); overflow: hidden; scroll-margin-top: calc(var(--topbar-h) + 16px);
}
.stage > header {
  display: flex; align-items: center; flex-wrap: wrap; gap: var(--s-3);
  padding: var(--s-4) var(--s-5); border-bottom: 1px solid var(--border);
}
.stage > header .n {
  display: inline-grid; place-items: center; width: 30px; height: 30px; flex: none;
  border-radius: 50%; background: var(--accent); color: var(--on-accent);
  font: 700 var(--t-s)/1 var(--sans); font-variant-numeric: tabular-nums;
  box-shadow: 0 0 0 4px var(--accent-soft);
}
.stage > header h2 { font-size: var(--t-l); font-weight: 650; }
.stage > header .verb {
  font-size: 10.5px; font-weight: 700; letter-spacing: .06em; text-transform: uppercase;
  color: var(--muted); padding: 3px 8px; border-radius: var(--r-pill);
  background: var(--surface-3); border: 1px solid var(--border);
}
.stage > header .fill { flex: 1; }
.stage > header .note { font-size: var(--t-s); color: var(--faint); font-variant-numeric: tabular-nums; }
.stage > .body { padding: var(--s-6) var(--s-7) var(--s-7); }
.stage[data-state="armed"] { border-color: var(--armed-edge); box-shadow: var(--sh-xs), inset 4px 0 0 var(--armed); }
.stage[data-state="unknown"] { border-color: var(--broken-edge); box-shadow: var(--sh-xs), inset 4px 0 0 var(--broken); }
.stage > .strip { margin: var(--s-4) var(--s-5) 0; box-shadow: none; }

/* underline tabs */
.tabs {
  display: flex; flex-wrap: wrap; column-gap: var(--s-1); overflow-x: auto; scrollbar-width: none;
  padding: 0 var(--s-5); border-bottom: 1px solid var(--border); background: var(--surface-2);
}
.tabs::-webkit-scrollbar { display: none; }
.tabs a {
  flex: none; padding: 12px var(--s-3) 11px; margin-bottom: -1px;
  font-size: var(--t-m); font-weight: 500; color: var(--muted);
  border-bottom: 2px solid transparent;
  transition: color .14s var(--ease), border-color .14s var(--ease);
}
.tabs a:hover { color: var(--ink); border-bottom-color: var(--border-strong); }
.tabs a[aria-current] { color: var(--ink); font-weight: 600; border-bottom-color: var(--accent); }

/* callouts */
.skip {
  display: flex; gap: var(--s-3); align-items: baseline;
  padding: var(--s-3) var(--s-4); margin: 0 0 var(--s-6);
  background: var(--surface-2); border: 1px solid var(--border); border-radius: var(--r-lg);
  font-size: var(--t-m); color: var(--muted);
}
.skip b {
  flex: none; font-size: var(--t-xs); font-weight: 700; letter-spacing: .05em; text-transform: uppercase;
  color: var(--accent);
}
.objective {
  display: flex; flex-direction: column; gap: 6px;
  padding: var(--s-4) var(--s-5); margin: 0 0 var(--s-5);
  background: linear-gradient(180deg, var(--accent-soft), transparent 140%);
  border: 1px solid var(--accent-edge); border-radius: var(--r-lg);
  font-size: var(--t-base); line-height: 1.6; color: var(--ink);
}
.objective b { font-size: var(--t-xs); font-weight: 700; letter-spacing: .06em; text-transform: uppercase; color: var(--accent); }

/* ---- long-form prose --------------------------------------------------------------------- */
.prose { font-size: var(--t-r); line-height: 1.72; color: var(--ink-2); }
/* Text keeps a reading measure; tables, code and callouts may use the whole card. */
.prose > p, .prose > ul, .prose > ol, .prose > h1, .prose > h2, .prose > h3, .prose > h4 { max-width: 76ch; }
.prose > :first-child { margin-top: 0; }
.prose h1 { font-size: var(--t-2xl); margin: var(--s-7) 0 var(--s-3); }
.prose h2 { font-size: var(--t-xl); font-weight: 650; margin: var(--s-7) 0 var(--s-3); letter-spacing: -.014em; }
.prose h3 { font-size: var(--t-l); font-weight: 650; margin: var(--s-6) 0 var(--s-2); }
.prose h4 { font-size: var(--t-r); margin: var(--s-5) 0 var(--s-2); }
.prose p { margin: 0 0 var(--s-4); }
.prose a { text-decoration: underline; text-decoration-color: var(--accent-edge); text-underline-offset: 3px; }
.prose a:hover { text-decoration-color: currentColor; }
.prose ul, .prose ol { margin: 0 0 var(--s-4); padding-left: 1.4em; }
.prose li { margin: 6px 0; padding-left: 4px; }
.prose li::marker { color: var(--faint); }
.prose ol li::marker { font-weight: 600; font-variant-numeric: tabular-nums; }
.prose hr { border: 0; border-top: 1px solid var(--border); margin: var(--s-7) 0; }
.prose code {
  font-size: .86em; padding: .15em .42em; border-radius: 5px;
  background: var(--surface-3); border: 1px solid var(--border); color: var(--ink);
  overflow-wrap: anywhere;
}
.prose pre {
  margin: 0 0 var(--s-5); padding: var(--s-4) var(--s-5); overflow-x: auto;
  background: var(--console); color: var(--console-ink);
  border: 1px solid var(--console-rule); border-radius: var(--r-lg);
  font-size: var(--t-s); line-height: 1.65; box-shadow: var(--sh-xs);
}
.prose pre code { background: none; border: 0; padding: 0; color: inherit; font-size: inherit; }
.prose blockquote {
  margin: 0 0 var(--s-5); padding: var(--s-4) var(--s-5);
  background: var(--accent-soft); border: 1px solid var(--accent-edge); border-left: 4px solid var(--accent);
  border-radius: var(--r) var(--r-lg) var(--r-lg) var(--r);
  color: var(--ink); font-size: var(--t-base); line-height: 1.65;
}
.prose blockquote b, .prose blockquote strong { color: var(--ink); }
.prose .scroller { margin: 0 0 var(--s-5); max-width: 100%; }
.prose table { font-size: var(--t-m); line-height: 1.5; }
.prose table td:first-child { color: var(--ink); font-weight: 500; }

/* the numbered procedure in stage 02 */
.prose[aria-label="Steps to follow"] {
  max-width: none; margin: 0 0 var(--s-5); padding: var(--s-5);
  background: var(--surface-2); border: 1px solid var(--border); border-radius: var(--r-lg);
}
.prose[aria-label="Steps to follow"] h3 {
  margin: 0 0 var(--s-4); font-size: var(--t-xs); font-weight: 700; letter-spacing: .06em;
  text-transform: uppercase; color: var(--muted);
}
.prose[aria-label="Steps to follow"] ol { list-style: none; padding: 0; margin: 0; counter-reset: step; display: grid; gap: var(--s-3); }
.prose[aria-label="Steps to follow"] li {
  counter-increment: step; position: relative; margin: 0;
  padding: 0 0 0 40px; font-size: var(--t-base); line-height: 1.6; color: var(--ink-2);
}
.prose[aria-label="Steps to follow"] li::before {
  content: counter(step); position: absolute; left: 0; top: 0;
  display: grid; place-items: center; width: 26px; height: 26px; border-radius: 50%;
  background: var(--surface); border: 1px solid var(--border-strong); color: var(--ink);
  font: 700 var(--t-s)/1 var(--sans); box-shadow: var(--sh-xs);
}
.prose[aria-label="Steps to follow"] li:not(:last-child)::after {
  content: ""; position: absolute; left: 12.5px; top: 30px; bottom: -10px;
  width: 1px; background: var(--border-strong);
}

/* ---- source references: a code viewer ---------------------------------------------------- */
.body > .eyebrow { display: flex; margin: var(--s-7) 0 var(--s-3) !important; color: var(--muted); }
.src {
  margin: 0 0 var(--s-4); background: var(--surface);
  border: 1px solid var(--border); border-radius: var(--r-lg); box-shadow: var(--sh-xs); overflow: hidden;
}
.src .path {
  display: flex; flex-wrap: wrap; align-items: center; gap: 6px var(--s-2);
  padding: 10px var(--s-4); background: var(--surface-2); border-bottom: 1px solid var(--border);
}
.src .path .file { font: 600 var(--t-s)/1.4 var(--mono); color: var(--ink); overflow-wrap: anywhere; }
.src .path .file::before { content: "\\2261"; margin-right: 8px; color: var(--faint); font-family: var(--sans); }
.src .path .lines {
  font: 600 var(--t-xs)/1 var(--mono); color: var(--muted);
  padding: 3px 7px; border-radius: var(--r-pill); background: var(--surface); border: 1px solid var(--border);
}
.src .path .cap { flex-basis: 100%; font-size: var(--t-m); color: var(--muted); }
.src .inner { padding: var(--s-4); }
.src .lines-wrap { overflow: auto; max-height: 440px; background: var(--surface); }
.src table { font: 400 var(--t-s)/1.7 var(--mono); border-spacing: 0; width: auto; min-width: 100%; }
.src td { padding: 0 var(--s-4) 0 var(--s-3); border: 0; white-space: pre; color: var(--ink-2); vertical-align: top; }
.src td.n {
  position: sticky; left: 0; width: 1%; padding: 0 var(--s-3); text-align: right;
  color: var(--faint); background: var(--surface-2); border-right: 1px solid var(--border);
  user-select: none; -webkit-user-select: none;
}
.src tr:first-child td { padding-top: var(--s-2); }
.src tr:last-child td { padding-bottom: var(--s-2); }
.src tr.hit td { background: var(--hit); color: var(--ink); }
.src tr.hit td.n { background: var(--hit); color: var(--armed); font-weight: 700; box-shadow: inset 3px 0 0 var(--hit-edge); }

/* ---- hints: an accordion ----------------------------------------------------------------- */
#hints .body { display: grid; gap: var(--s-2); padding-top: var(--s-5); }
#hints > header .n { background: var(--surface-3); color: var(--ink); box-shadow: 0 0 0 4px var(--surface-2); }
.hint { border: 1px solid var(--border); border-radius: var(--r-lg); background: var(--surface); overflow: hidden; }
.hint summary {
  display: flex; align-items: center; gap: var(--s-3); cursor: pointer;
  padding: var(--s-3) var(--s-4); list-style: none; font-size: var(--t-m);
  transition: background-color .14s var(--ease);
}
.hint summary::-webkit-details-marker { display: none; }
.hint summary:hover { background: var(--surface-2); }
.hint summary .i {
  display: inline-grid; place-items: center; width: 26px; height: 26px; border-radius: var(--r-sm);
  background: var(--accent-soft); color: var(--accent-ink); font: 700 var(--t-xs)/1 var(--mono);
}
.hint summary .t { font-weight: 600; color: var(--ink); }
.hint summary .fill { flex: 1; }
.hint summary .more { font-size: var(--t-s); font-weight: 600; color: var(--accent); }
.hint summary .more::after { content: "\\203A"; display: inline-block; margin-left: 6px; transition: transform .16s var(--ease); }
.hint[open] summary { border-bottom: 1px solid var(--border); background: var(--surface-2); }
.hint[open] summary .more::after { transform: rotate(90deg); }
.hint .inner { padding: var(--s-4) var(--s-5); font-size: var(--t-base); line-height: 1.65; color: var(--ink-2); }
"""

_CONSOLE = """
/* ---- the console: controls beside a result pane ------------------------------------------ */
.console { display: grid; grid-template-columns: minmax(0, 1fr); gap: var(--s-5); align-items: start; }
.panel {
  background: var(--surface); border: 1px solid var(--border); border-radius: var(--r-lg);
  box-shadow: var(--sh-xs); overflow: hidden; min-width: 0;
}
.panel > h3 {
  display: flex; align-items: center; gap: var(--s-2);
  padding: 12px var(--s-4); font-size: var(--t-m); font-weight: 650;
  background: var(--surface-2); border-bottom: 1px solid var(--border);
}
.panel > h3 .fill { flex: 1; }
.panel > h3 .side {
  font-size: 10.5px; font-weight: 700; letter-spacing: .05em; text-transform: uppercase;
  color: var(--muted); padding: 3px 8px; border-radius: var(--r-pill);
  background: var(--surface); border: 1px solid var(--border);
}
.panel .inner { padding: var(--s-4); }
.panel .inner.flush { padding: 0; }

.grp {
  padding: var(--s-4) var(--s-4) 6px;
  font-size: var(--t-xs); font-weight: 700; letter-spacing: .06em; text-transform: uppercase; color: var(--faint);
}
.grp + form.control { border-top: 0; }

form.control {
  display: flex; align-items: center; gap: var(--s-4);
  padding: var(--s-3) var(--s-4); margin: 0; border-top: 1px solid var(--border);
  transition: background-color .14s var(--ease);
}
form.control:hover { background: var(--surface-2); }
form.control .text { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
form.control .label { font-size: var(--t-m); font-weight: 600; color: var(--ink); line-height: 1.4; }
form.control .detail { font-size: var(--t-s); color: var(--muted); line-height: 1.5; }
form.control code.mut {
  margin-top: 4px; font-size: var(--t-xs); color: var(--faint);
  overflow-wrap: anywhere; line-height: 1.5;
}
form.control code.mut .s {
  display: inline-block; margin-left: 2px; padding: 1px 7px; border-radius: var(--r-pill);
  font: 700 10.5px/1.5 var(--sans); letter-spacing: .04em; text-transform: uppercase;
  color: var(--muted); background: var(--surface-3); border: 1px solid var(--border);
}
form.control[data-state="correct"] code.mut .s { color: var(--held); background: var(--held-soft); border-color: var(--held-edge); }
form.control[data-state="armed"] { background: var(--armed-soft); box-shadow: inset 3px 0 0 var(--armed); }
form.control[data-state="armed"] code.mut .s { color: var(--armed); background: var(--surface); border-color: var(--armed-edge); }
form.control[data-state="unknown"] code.mut .s,
form.control[data-state="absent"] code.mut .s { color: var(--broken); background: var(--broken-soft); border-color: var(--broken-edge); }
form.control button { flex: none; min-width: 76px; }

form.reset {
  display: flex; flex-wrap: wrap; align-items: center; gap: var(--s-3);
  padding: var(--s-4); margin: 0; border-top: 1px solid var(--border); background: var(--surface-2);
}
form.reset .detail { flex: 1; min-width: 180px; font-size: var(--t-s); color: var(--muted); line-height: 1.5; }

/* the result pane: a dark terminal inside a light card */
#result { scroll-margin-top: calc(var(--topbar-h) + 16px); }
.term { background: var(--console); color: var(--console-ink); }
.term .ran {
  display: flex; align-items: center; gap: 8px;
  padding: 10px var(--s-4); border-bottom: 1px solid var(--console-rule); background: var(--console-2);
  font: 500 var(--t-xs)/1.5 var(--mono); color: var(--console-dim); overflow-wrap: anywhere;
}
.term .ran::before { content: ""; width: 7px; height: 7px; border-radius: 50%; background: var(--held); flex: none; }
.term .out {
  margin: 0; padding: var(--s-4); max-height: 560px; overflow: auto;
  font: 400 12.5px/1.65 var(--mono); color: var(--console-ink); white-space: pre; tab-size: 2;
}
.term .out.idle {
  white-space: normal; font: 400 var(--t-m)/1.6 var(--sans); color: var(--console-dim);
  padding: var(--s-8) var(--s-6); text-align: center;
}
.term .out.idle::before {
  content: "\\25B8"; display: block; margin: 0 auto var(--s-3); width: 40px; height: 40px; line-height: 40px;
  border-radius: 50%; background: var(--console-2); border: 1px solid var(--console-rule);
  color: var(--console-accent); font-size: 16px;
}

.flag { padding: var(--s-4); border-top: 1px solid var(--border); display: grid; gap: var(--s-3); }
.flag .k { font-size: var(--t-xs); font-weight: 700; letter-spacing: .06em; text-transform: uppercase; color: var(--muted); }
.flagform { display: flex; gap: var(--s-2); margin: 0; }
.flagform input {
  flex: 1; min-width: 0; font: 400 var(--t-m)/1.4 var(--sans); color: var(--ink);
  padding: 9px var(--s-3); border-radius: var(--r);
  background: var(--surface); border: 1px solid var(--border-strong); box-shadow: var(--sh-xs);
  transition: border-color .14s var(--ease), box-shadow .14s var(--ease);
}
.flagform input::placeholder { color: var(--faint); }
.flagform input:focus { outline: none; border-color: var(--accent); box-shadow: var(--focus-ring); }
.flagnote {
  display: flex; gap: var(--s-2); align-items: baseline; margin: 0;
  padding: 10px var(--s-3); border-radius: var(--r); font-size: var(--t-m); line-height: 1.5;
  border: 1px solid var(--border);
}
.flagnote b { flex: none; }
.flagnote.ok { background: var(--held-soft); border-color: var(--held-edge); color: var(--held); }
.flagnote.ok b { color: var(--held); }
.flagnote.no { background: var(--broken-soft); border-color: var(--broken-edge); color: var(--broken); }
.flagnote.no b { color: var(--broken); }
"""

_RESPONSIVE = """
/* ---- responsive -------------------------------------------------------------------------- */
@media (max-width: 1024px) {
  .layout { grid-template-columns: minmax(0, 1fr); gap: var(--s-5); }
  .spine { position: static; padding: 6px; }
  .spine ol { grid-auto-flow: column; grid-auto-columns: max-content; overflow-x: auto; scrollbar-width: none; }
  .spine li a { border-left: 0; border-bottom: 2px solid transparent; }
  .spine li a[aria-current] { border-bottom-color: var(--accent); }
  .spine li.armed a { border-bottom-color: var(--armed); }
  .spine .foot { display: none; }
  .lede { grid-template-columns: 1fr; padding: var(--s-7) var(--s-6); }
  .routes { grid-template-columns: 1fr 1fr; }
}
@media (max-width: 760px) {
  .tabs, .tracknav { flex-wrap: nowrap; }
  .why { grid-template-columns: 1fr; }
  .routes { grid-template-columns: 1fr; }
  .masthead .lab, .masthead .sep { display: none; }
  .stage > .body { padding: var(--s-5); }
  table.index td.claim, table.index td.what { min-width: 220px; }
}
@media (max-width: 640px) {
  .masthead { padding: 0 var(--s-4); gap: var(--s-2); }
  .masthead nav a { padding: 6px 8px; font-size: var(--t-s); }
  .masthead .mark a { gap: 8px; }
  .masthead .logo { width: 26px; height: 26px; }
  #themeslot { margin-left: 0; }
  #themeswitch { font-size: 0; gap: 0; padding: 7px 9px; }
  #themeswitch::before { font-size: 13px; }
  .wrap { padding: var(--s-5) var(--s-4) var(--s-8); }
  .chead h1 { font-size: var(--t-2xl); }
  .lede { padding: var(--s-6) var(--s-5); }
  .lede h1 { font-size: var(--t-3xl); }
  .rail .go { grid-template-columns: 1fr; }
  .flagform { flex-direction: column; }
  form.control { flex-wrap: wrap; }
  form.control button { width: 100%; }
  .trackblock .claimline { padding-left: var(--s-5); }
}

@media (max-width: 420px) {
  /* The logo alone carries the brand on a phone, so the navigation keeps all its links. */
  .masthead .mark a { font-size: 0; gap: 0; }
  .masthead nav { overflow-x: auto; scrollbar-width: none; }
  .masthead nav::-webkit-scrollbar { display: none; }
}

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation: none !important; transition: none !important; }
  .route:hover { transform: none; }
}

@media print {
  .topbar, .tracknav, .spine, form, .foot { display: none !important; }
  body { background: #fff; }
  .stage, .trackblock, .scroller, .panel { box-shadow: none; }
}
"""

STYLESHEET = _TOKENS + _BASE + _TABLES + _CHALLENGE + _CONSOLE + _RESPONSIVE
