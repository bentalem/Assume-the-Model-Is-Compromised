"""A small Markdown renderer for challenge content.

Deliberately not a dependency. The content is ours, the subset is fixed, and the alternative was
adding a parser to a repository whose first lesson is asking what a component can reach.

Supported, because this is what the material actually uses: ATX headings, paragraphs, unordered and
ordered lists, fenced code blocks, blockquotes, pipe tables, horizontal rules, and inline code,
bold, italics and links.

Everything is HTML-escaped before any markup is added, so a stray `<` in a policy snippet renders as
a `<` rather than as an element. Link targets are restricted to http, https and same-document
anchors — the content is trusted, and the check costs one line.
"""

from __future__ import annotations

import html
import re

_INLINE_CODE = re.compile(r"`([^`]+)`")
# Bold may contain single-asterisk emphasis: `**a maximum, per call *and* per session**`.
# The obvious `\*\*([^*]+)\*\*` refuses any `*` inside and leaves the literal `**` on the
# page. The content test caught exactly that, which is the only reason this is a comment.
_BOLD = re.compile(r"\*\*((?:[^*]|\*(?!\*))+)\*\*")
_ITALIC = re.compile(r"(?<![*\w])\*([^*]+)\*(?!\*)")
_LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
_SAFE_HREF = re.compile(r"^(https?://|#|/)")


def _inline(text: str) -> str:
    """Escape first, then add markup. Order matters: doing it the other way lets content inject."""
    out = html.escape(text, quote=False)

    # Code spans are taken first so a `*` inside one is not read as emphasis.
    placeholders: list[str] = []

    def stash(match: re.Match[str]) -> str:
        placeholders.append(f"<code>{match.group(1)}</code>")
        return f"\x00{len(placeholders) - 1}\x00"

    out = _INLINE_CODE.sub(stash, out)
    out = _BOLD.sub(r"<strong>\1</strong>", out)
    out = _ITALIC.sub(r"<em>\1</em>", out)

    def link(match: re.Match[str]) -> str:
        label, href = match.group(1), match.group(2)
        if not _SAFE_HREF.match(href):
            return label
        return f'<a href="{html.escape(href, quote=True)}">{label}</a>'

    out = _LINK.sub(link, out)

    for index, value in enumerate(placeholders):
        out = out.replace(f"\x00{index}\x00", value)
    return out


def _table(rows: list[str]) -> str:
    """A pipe table. The second row is the alignment rule and is discarded."""
    def cells(line: str) -> list[str]:
        return [cell.strip() for cell in line.strip().strip("|").split("|")]

    header = cells(rows[0])
    body = [cells(row) for row in rows[2:]]

    out = ['<div class="scroller"><table><thead><tr>']
    out += [f"<th>{_inline(cell)}</th>" for cell in header]
    out.append("</tr></thead><tbody>")
    for row in body:
        out.append("<tr>" + "".join(f"<td>{_inline(cell)}</td>" for cell in row) + "</tr>")
    out.append("</tbody></table></div>")
    return "".join(out)


def render(text: str) -> str:
    """Render a Markdown subset to HTML."""
    lines = text.replace("\r\n", "\n").split("\n")
    out: list[str] = []
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        # Fenced code. The info string is ignored: nothing here highlights, and a language label
        # that does not change the output is a promise the renderer cannot keep.
        if stripped.startswith("```"):
            i += 1
            block: list[str] = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                block.append(lines[i])
                i += 1
            i += 1
            out.append(f"<pre><code>{html.escape(chr(10).join(block), quote=False)}</code></pre>")
            continue

        if stripped.startswith("#"):
            level = len(stripped) - len(stripped.lstrip("#"))
            level = min(max(level, 1), 4)
            out.append(f"<h{level}>{_inline(stripped[level:].strip())}</h{level}>")
            i += 1
            continue

        if set(stripped) <= {"-", "*", "_"} and len(stripped) >= 3:
            out.append("<hr>")
            i += 1
            continue

        # A table needs a header row and an alignment rule directly under it.
        if stripped.startswith("|") and i + 1 < len(lines) and set(lines[i + 1].strip()) <= set("|-: "):
            block = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                block.append(lines[i])
                i += 1
            out.append(_table(block))
            continue

        if stripped.startswith(">"):
            block = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                block.append(lines[i].strip().lstrip(">").strip())
                i += 1
            out.append(f"<blockquote>{_inline(' '.join(block))}</blockquote>")
            continue

        if re.match(r"^[-*+]\s+", stripped):
            block = []
            while i < len(lines) and re.match(r"^\s*[-*+]\s+", lines[i]):
                block.append(re.sub(r"^\s*[-*+]\s+", "", lines[i]))
                i += 1
            out.append("<ul>" + "".join(f"<li>{_inline(item)}</li>" for item in block) + "</ul>")
            continue

        if re.match(r"^\d+[.)]\s+", stripped):
            block = []
            while i < len(lines) and re.match(r"^\s*\d+[.)]\s+", lines[i]):
                block.append(re.sub(r"^\s*\d+[.)]\s+", "", lines[i]))
                i += 1
            out.append("<ol>" + "".join(f"<li>{_inline(item)}</li>" for item in block) + "</ol>")
            continue

        # Paragraph: consume until a blank line or the start of another block.
        block = []
        while i < len(lines) and lines[i].strip() and not re.match(
            r"^\s*(#|```|>|[-*+]\s|\d+[.)]\s|\|)", lines[i]
        ):
            block.append(lines[i].strip())
            i += 1
        if block:
            out.append(f"<p>{_inline(' '.join(block))}</p>")
        else:
            i += 1

    return "\n".join(out)
