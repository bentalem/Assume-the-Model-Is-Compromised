"""The approval portal builds HTML by hand, so these tests are the thing that notices if it stops.

This directory existed and was empty. Challenge 5.4 sends a learner to read `main.py`, find that
every interpolated value goes through `html.escape`, and then observe that nothing in the repository
would catch it if one of them did not — which breaches the lab's own convention that every
capability ships with tests. This is that gap closed.

Why it matters here specifically: this page is the one screen a human reads before authorising money
to move. It renders values that came from a request body, and there is no template engine doing
autoescaping. The safety is `html.escape`, applied by hand, sixteen times. A missed application is a
one-character diff.

Two properties are checked, and the second is the one people forget:

  * markup in a value is escaped, so it renders as text rather than as elements;
  * quotes are escaped too. Several values are interpolated inside single-quoted HTML attributes,
    and Python's `html.escape` only escapes quotes because `quote=True` is its default. A future
    edit passing `quote=False` would still escape `<` and `>` and would still look correct in every
    test that only checks for angle brackets.
"""

from __future__ import annotations

import html
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from approval_portal.main import _page  # noqa: E402

PAYLOAD = "<script>alert('x')</script>"


def test_page_escapes_markup_in_the_title() -> None:
    rendered = _page(PAYLOAD, "<p>body</p>")
    assert "<script>" not in rendered
    assert "&lt;script&gt;" in rendered


def test_page_escapes_quotes_in_the_title() -> None:
    """The title sits inside a `<title>` element, but the same helper guards attribute contexts.

    Asserted separately from the markup test because `quote=False` would pass that one.
    """
    rendered = _page("it's \"quoted\"", "<p>body</p>")
    assert "'" not in rendered.split("<title>", 1)[1].split("</title>", 1)[0]
    assert "&#x27;" in rendered


def test_page_does_not_escape_the_body() -> None:
    """`body` is HTML this module has already built from escaped values.

    Escaping it again would render the page as its own source. This test records that the asymmetry
    is deliberate, so that nobody "fixes" it later.
    """
    rendered = _page("title", "<p>body</p>")
    assert "<p>body</p>" in rendered


def test_html_escape_defaults_to_escaping_quotes() -> None:
    """Guards the assumption the page depends on rather than the page itself.

    `main.py` interpolates values into single-quoted attributes and relies on `html.escape`'s
    default. If that default ever changed, every attribute in the review page would become
    injectable and nothing else here would fail.
    """
    assert html.escape("'") == "&#x27;"
    assert html.escape('"') == "&quot;"
