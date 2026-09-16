"""Render the article to a PDF, images and all.

The article HTML is written for the Artifact runtime, which supplies the document wrapper. A
browser printing it directly gets a fragment in quirks mode, so this builds a complete print
document around the same content rather than maintaining a second copy of the article: one source,
two outputs.

The print stylesheet does the part a screen stylesheet cannot: page margins, and keeping figures,
tables and code blocks off page boundaries. A screenshot split across two pages is unreadable, and
a caption orphaned from its image is worse than no caption.

    python scripts/build_article_pdf.py

Chrome renders it. The fonts come from Google Fonts, so this needs network access; without it the
fallback stack still produces a correct document, just not the intended one.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ARTICLE = REPO / "docs" / "article" / "securing-ai-agents.html"
OUTPUT = REPO / "docs" / "article" / "securing-ai-agents.pdf"

CHROME_CANDIDATES = [
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
    Path.home() / r"AppData\Local\Google\Chrome\Application\chrome.exe",
]

GREEN, RED, GREY, BOLD, RESET = "\033[32m", "\033[31m", "\033[90m", "\033[1m", "\033[0m"

# Print-only rules. Everything else is inherited from the article's own stylesheet, so the PDF and
# the published page cannot drift apart.
PRINT_CSS = """
@page { size: A4; margin: 16mm 14mm; }

html { -webkit-print-color-adjust: exact; print-color-adjust: exact; }

body {
  font-size: 10.5pt;
  padding-inline: 0;
  padding-block: 0 0;
}

.wrap { max-width: none; }

/* Nothing that carries meaning may be split across a page boundary. */
figure, pre, table, .record, .claim, .formula, .aside, .lede .transcript { break-inside: avoid; }
figcaption { break-before: avoid; }
h1, h2, h3 { break-after: avoid; }
.decision { break-inside: auto; }

/* The masthead is the cover: give it the first page to itself. */
header.masthead { padding-block: 0 24px; margin-bottom: 32px; }
header.masthead + section { break-before: page; }

figure img { border-color: #C8D4D1; }

/* Links are printed, so the underline is the only thing left doing the work. */
a { color: inherit; text-decoration: underline; }

/* Screen-only affordances that mean nothing on paper. */
.scroller { overflow: visible; }
pre { white-space: pre-wrap; word-break: break-word; }
"""


def find_chrome() -> Path:
    for candidate in CHROME_CANDIDATES:
        if candidate.exists():
            return candidate
    found = shutil.which("chrome") or shutil.which("msedge")
    if found:
        return Path(found)
    raise SystemExit(f"{RED}No Chrome or Edge found. Install one, or print the page from a browser.{RESET}")


def build_print_document(source: str) -> str:
    """Wrap the article fragment in a real document, and force the light palette.

    The article defines its dark theme behind prefers-color-scheme. A print job that inherits the
    machine's dark setting produces a black-ink-heavy PDF nobody wants, so the root is stamped
    light — the same switch a reader's explicit choice uses, not a separate code path.
    """
    title_match = re.search(r"<title>(.*?)</title>", source, re.S)
    title = title_match.group(1).strip() if title_match else "Article"

    return (
        '<!doctype html>\n<html lang="en" data-theme="light">\n<head>\n'
        '<meta charset="utf-8">\n'
        f"<title>{title}</title>\n"
        f"{source}\n"
        f"<style>{PRINT_CSS}</style>\n"
        "</head>\n<body>\n</body>\n</html>\n"
    )


def main() -> int:
    if not ARTICLE.exists():
        raise SystemExit(f"{RED}Article not found: {ARTICLE}{RESET}")

    chrome = find_chrome()
    source = ARTICLE.read_text(encoding="utf-8")

    missing = [
        ref for ref in re.findall(r'<img[^>]+src="([^"]+)"', source)
        if not (ARTICLE.parent / ref).exists()
    ]
    if missing:
        raise SystemExit(f"{RED}Missing images: {', '.join(missing)}{RESET}")

    # Written beside the article so the relative image paths resolve unchanged.
    temp = ARTICLE.parent / f".print-{ARTICLE.stem}.html"
    temp.write_text(build_print_document(source), encoding="utf-8")

    profile = Path(tempfile.mkdtemp(prefix="article-pdf-"))
    try:
        print()
        print(f"  {GREY}rendering with {chrome.name}...{RESET}")
        result = subprocess.run(
            [
                str(chrome),
                "--headless=new",
                "--disable-gpu",
                f"--user-data-dir={profile}",
                "--no-pdf-header-footer",
                "--virtual-time-budget=15000",   # let the webfonts and images settle
                f"--print-to-pdf={OUTPUT}",
                temp.as_uri(),
            ],
            capture_output=True, text=True, timeout=180,
            encoding="utf-8", errors="replace",
        )
    finally:
        temp.unlink(missing_ok=True)
        shutil.rmtree(profile, ignore_errors=True)

    if not OUTPUT.exists():
        detail = (result.stderr or result.stdout or "").strip()[:400]
        raise SystemExit(f"{RED}Chrome produced no file.{RESET}\n{detail}")

    size_kb = OUTPUT.stat().st_size / 1024
    print()
    print(f"  {GREEN}{OUTPUT.relative_to(REPO)}{RESET}  {GREY}{size_kb:.0f} KB{RESET}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
