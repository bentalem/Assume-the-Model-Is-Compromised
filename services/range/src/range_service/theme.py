"""The Range's stylesheet.

System fonts only. The lab is meant to run offline and a webfont that silently fails to load is a
page that silently changes shape, so the type stack is the one every machine already has.

Two rules the brief is strict about, and they are structural rather than decorative:

  * Semantic colour is separate from the accent. `--armed`, `--broken` and `--held` mean one thing
    each. A learner glancing at the console must be able to read the state without reading words,
    and that fails the moment the accent starts meaning "something".
  * Nothing animates in from invisible. A learner scrolling back must find the page as they left it.

Every colour is defined on bare `:root` first, so the un-stamped state (a viewer on "system") is a
complete palette rather than a half of one.
"""

STYLESHEET = """
:root {
  --ground:      #F4F6F7;
  --surface:     #FFFFFF;
  --surface-alt: #E9EDEF;
  --ink:         #12181B;
  --ink-soft:    #3A464C;
  --muted:       #64757C;
  --rule:        #D3DBDE;
  --rule-strong: #B0BCC1;

  --accent:      #1B4F72;
  --accent-soft: #DEE9F1;

  /* Semantic. Never used as decoration, never doubled with the accent. */
  --armed:       #A86212;
  --armed-soft:  #FAEEDC;
  --broken:      #A3342A;
  --broken-soft: #F8E3E1;
  --held:        #2C6B45;
  --held-soft:   #DFEFE5;

  --sans: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  --mono: ui-monospace, "Cascadia Mono", "SF Mono", Menlo, Consolas, monospace;

  color-scheme: light;
}

@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --ground:      #0E1416;
    --surface:     #151D20;
    --surface-alt: #1C262A;
    --ink:         #E6EDEF;
    --ink-soft:    #C0CCD1;
    --muted:       #8B9BA1;
    --rule:        #263337;
    --rule-strong: #38474C;

    --accent:      #6FA8D4;
    --accent-soft: #15242F;

    --armed:       #D79B4A;
    --armed-soft:  #2A2114;
    --broken:      #E08478;
    --broken-soft: #2C1A18;
    --held:        #6FC08D;
    --held-soft:   #15271D;

    color-scheme: dark;
  }
}

:root[data-theme="dark"] {
  --ground:      #0E1416;
  --surface:     #151D20;
  --surface-alt: #1C262A;
  --ink:         #E6EDEF;
  --ink-soft:    #C0CCD1;
  --muted:       #8B9BA1;
  --rule:        #263337;
  --rule-strong: #38474C;
  --accent:      #6FA8D4;
  --accent-soft: #15242F;
  --armed:       #D79B4A;
  --armed-soft:  #2A2114;
  --broken:      #E08478;
  --broken-soft: #2C1A18;
  --held:        #6FC08D;
  --held-soft:   #15271D;
  color-scheme: dark;
}

* { box-sizing: border-box; }

body {
  margin: 0;
  padding-inline: 20px;
  padding-block: 0 72px;
  background: var(--ground);
  color: var(--ink);
  font-family: var(--sans);
  font-size: 15px;
  line-height: 1.6;
  -webkit-font-smoothing: antialiased;
}

.wrap { max-width: 61rem; margin-inline: auto; }

a { color: var(--accent); }
a:focus-visible, button:focus-visible, summary:focus-visible, input:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

/* ---------- masthead ---------- */

.masthead {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 8px 16px;
  border-bottom: 2px solid var(--ink);
  padding-block: 28px 14px;
  margin-bottom: 28px;
}
.masthead h1 { font-size: 1.2rem; margin: 0; letter-spacing: -.01em; }
.masthead h1 a { color: inherit; text-decoration: none; }
.masthead .tag {
  font-family: var(--mono);
  font-size: .7rem;
  letter-spacing: .12em;
  text-transform: uppercase;
  color: var(--muted);
}
.masthead .spacer { flex: 1 1 auto; }

/* ---------- catalogue ---------- */

.track { margin-bottom: 34px; }
.track > h2 {
  font-size: .78rem;
  letter-spacing: .1em;
  text-transform: uppercase;
  color: var(--muted);
  margin: 0 0 4px;
  display: flex;
  align-items: baseline;
  gap: 10px;
}
.track > h2 .num { font-family: var(--mono); color: var(--accent); }
.track > p.claim {
  margin: 0 0 14px;
  color: var(--ink-soft);
  max-width: 54rem;
}

.cards { display: grid; gap: 10px; grid-template-columns: repeat(auto-fill, minmax(19rem, 1fr)); }

.card {
  display: block;
  background: var(--surface);
  border: 1px solid var(--rule);
  border-left: 3px solid var(--rule-strong);
  border-radius: 3px;
  padding: 13px 15px;
  text-decoration: none;
  color: inherit;
}
.card:hover { border-color: var(--rule-strong); border-left-color: var(--accent); }
.card.inert { opacity: .72; }
.card .head {
  display: flex;
  align-items: baseline;
  gap: 9px;
  margin-bottom: 4px;
}
.card .id {
  font-family: var(--mono);
  font-size: .76rem;
  font-weight: 600;
  color: var(--accent);
}
.card .title { font-weight: 600; }
.card .summary { color: var(--muted); font-size: .88rem; line-height: 1.45; }
.card .meta {
  margin-top: 9px;
  font-family: var(--mono);
  font-size: .7rem;
  letter-spacing: .04em;
  color: var(--muted);
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

/* ---------- stages ---------- */

.stage {
  background: var(--surface);
  border: 1px solid var(--rule);
  border-radius: 4px;
  margin-bottom: 22px;
  overflow: hidden;
}
.stage > header {
  display: flex;
  align-items: baseline;
  gap: 12px;
  padding: 14px 18px;
  border-bottom: 1px solid var(--rule);
  background: var(--surface-alt);
}
.stage > header .num {
  font-family: var(--mono);
  font-size: .76rem;
  font-weight: 600;
  color: var(--accent);
  letter-spacing: .06em;
}
.stage > header h2 { margin: 0; font-size: 1rem; }
.stage > header .note { margin-left: auto; font-size: .8rem; color: var(--muted); }
.stage .body { padding: 18px; }

/* ---------- tabs, which are links and work without script ---------- */

.tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 2px;
  padding: 0 18px;
  border-bottom: 1px solid var(--rule);
  background: var(--surface-alt);
}
.tabs a {
  padding: 8px 12px;
  font-size: .84rem;
  text-decoration: none;
  color: var(--muted);
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
}
.tabs a[aria-current="page"] {
  color: var(--ink);
  font-weight: 600;
  border-bottom-color: var(--accent);
  background: var(--surface);
}

/* ---------- prose inside a stage ---------- */

.prose { max-width: 44rem; }
.prose h1, .prose h2, .prose h3, .prose h4 { line-height: 1.25; text-wrap: balance; }
.prose h2 { font-size: 1.08rem; margin: 26px 0 8px; }
.prose h3 { font-size: .95rem; margin: 22px 0 6px; }
.prose > :first-child { margin-top: 0; }
.prose p { margin: 0 0 14px; }
.prose ul, .prose ol { margin: 0 0 14px; padding-left: 1.25em; }
.prose li { margin-bottom: 5px; }
.prose blockquote {
  margin: 0 0 16px;
  padding: 2px 0 2px 15px;
  border-left: 3px solid var(--accent);
  font-weight: 600;
  color: var(--ink);
}
.prose hr { border: none; border-top: 1px solid var(--rule); margin: 22px 0; }

code {
  font-family: var(--mono);
  font-size: .86em;
  background: var(--surface-alt);
  border-radius: 3px;
  padding: .08em .32em;
  word-break: break-word;
}
pre {
  font-family: var(--mono);
  font-size: .8rem;
  line-height: 1.6;
  background: var(--surface-alt);
  border: 1px solid var(--rule);
  border-radius: 3px;
  padding: 12px 14px;
  margin: 0 0 16px;
  overflow-x: auto;
}
pre code { background: none; padding: 0; font-size: inherit; }

.scroller { overflow-x: auto; margin: 0 0 16px; }
table { border-collapse: collapse; width: 100%; min-width: 26rem; font-size: .86rem; }
th {
  text-align: left;
  font-size: .68rem;
  letter-spacing: .08em;
  text-transform: uppercase;
  color: var(--muted);
  border-bottom: 1px solid var(--rule-strong);
  padding: 0 12px 7px 0;
  vertical-align: bottom;
}
td { padding: 8px 12px 8px 0; border-bottom: 1px solid var(--rule); vertical-align: top; }
th:last-child, td:last-child { padding-right: 0; }
tr:last-child td { border-bottom: none; }

/* ---------- the skip test ---------- */

.skip {
  background: var(--accent-soft);
  border-left: 3px solid var(--accent);
  padding: 11px 14px;
  margin: 0 0 18px;
  font-size: .89rem;
}
.skip b { display: block; font-size: .7rem; letter-spacing: .08em; text-transform: uppercase; color: var(--muted); }

/* ---------- the console ---------- */

.console { display: grid; gap: 18px; grid-template-columns: minmax(0, 5fr) minmax(0, 6fr); }
@media (max-width: 760px) { .console { grid-template-columns: 1fr; } }

.panel { border: 1px solid var(--rule); border-radius: 3px; }
.panel > h3 {
  margin: 0;
  padding: 10px 14px;
  font-size: .72rem;
  letter-spacing: .09em;
  text-transform: uppercase;
  color: var(--muted);
  border-bottom: 1px solid var(--rule);
  background: var(--surface-alt);
}
.panel .inner { padding: 14px; }

.state {
  display: flex;
  align-items: center;
  gap: 9px;
  font-family: var(--mono);
  font-size: .76rem;
  padding: 9px 14px;
  border-bottom: 1px solid var(--rule);
}
.state .dot { width: 9px; height: 9px; border-radius: 50%; flex: 0 0 auto; }
.state.held  { background: var(--held-soft);  color: var(--held); }
.state.held .dot  { background: var(--held); }
.state.armed { background: var(--armed-soft); color: var(--armed); }
.state.armed .dot { background: var(--armed); }
.state.unknown { background: var(--surface-alt); color: var(--muted); }
.state.unknown .dot { background: var(--muted); }

.control {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px 0;
  border-bottom: 1px solid var(--rule);
}
.control:last-of-type { border-bottom: none; }
.control .text { flex: 1 1 auto; min-width: 0; }
.control .label { font-weight: 600; font-size: .92rem; }
.control .detail { color: var(--muted); font-size: .82rem; line-height: 1.45; }
.control .mut {
  font-family: var(--mono);
  font-size: .7rem;
  color: var(--muted);
  display: block;
  margin-top: 3px;
}

button {
  font: inherit;
  font-size: .84rem;
  font-weight: 600;
  color: var(--ink);
  background: var(--surface);
  border: 1px solid var(--rule-strong);
  border-radius: 3px;
  padding: 6px 12px;
  cursor: pointer;
}
button:hover:not(:disabled) { border-color: var(--accent); color: var(--accent); }
button:disabled { opacity: .5; cursor: not-allowed; }
button.arm { border-color: var(--armed); color: var(--armed); }
button.restore { border-color: var(--held); color: var(--held); }

.inert-note {
  font-size: .82rem;
  color: var(--muted);
  background: var(--surface-alt);
  border: 1px dashed var(--rule-strong);
  border-radius: 3px;
  padding: 11px 13px;
}

.result {
  font-family: var(--mono);
  font-size: .78rem;
  line-height: 1.6;
  background: var(--surface-alt);
  border-radius: 3px;
  padding: 12px 14px;
  overflow-x: auto;
  white-space: pre;
  min-height: 4.4rem;
  color: var(--ink-soft);
}

.flagform { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 14px; }
.flagform input[type="text"] {
  font: inherit;
  font-family: var(--mono);
  font-size: .84rem;
  flex: 1 1 12rem;
  min-width: 0;
  padding: 6px 10px;
  color: var(--ink);
  background: var(--surface);
  border: 1px solid var(--rule-strong);
  border-radius: 3px;
}

/* ---------- source, in stage 03 ---------- */

.source > .path {
  font-family: var(--mono);
  font-size: .74rem;
  color: var(--muted);
  padding: 8px 14px;
  background: var(--surface-alt);
  border-bottom: 1px solid var(--rule);
}
.sourcelines { font-family: var(--mono); font-size: .78rem; line-height: 1.6; overflow-x: auto; }
.sourcelines table { min-width: 0; }
.sourcelines td { border: none; padding: 0 0 0 14px; white-space: pre; }
.sourcelines td.n {
  padding: 0 12px 0 14px;
  color: var(--muted);
  text-align: right;
  user-select: none;
  width: 1%;
}
.sourcelines tr.hit { background: var(--accent-soft); }
.sourcelines tr.hit td.n { color: var(--accent); font-weight: 600; }

/* ---------- hints ---------- */

details.hint {
  border: 1px solid var(--rule);
  border-radius: 3px;
  padding: 0;
  margin-bottom: 8px;
  background: var(--surface);
}
details.hint > summary {
  cursor: pointer;
  padding: 9px 13px;
  font-size: .85rem;
  font-weight: 600;
  list-style: none;
}
details.hint > summary::-webkit-details-marker { display: none; }
details.hint > summary::before { content: "› "; color: var(--muted); }
details.hint[open] > summary::before { content: "⌄ "; }
details.hint > p { margin: 0; padding: 0 13px 12px; color: var(--ink-soft); font-size: .88rem; }

/* ---------- footer ---------- */

.foot {
  margin-top: 34px;
  padding-top: 16px;
  border-top: 1px solid var(--rule);
  font-family: var(--mono);
  font-size: .72rem;
  color: var(--muted);
}

@media (prefers-reduced-motion: reduce) {
  * { animation: none !important; transition: none !important; }
}
"""
