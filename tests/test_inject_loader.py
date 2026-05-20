"""Tests for scripts/inject_loader.py — the post-build hook that
decorates pygbag's generated index.html with a styled loading overlay."""
import sys
import os
import importlib.util
from pathlib import Path

import pytest

# Load the script module directly — it lives outside the package tree.
_INJECT_PATH = (
    Path(__file__).resolve().parent.parent / "scripts" / "inject_loader.py"
)
spec = importlib.util.spec_from_file_location("inject_loader", _INJECT_PATH)
inject_loader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inject_loader)


PYGBAG_LIKE_INDEX = """\
<!DOCTYPE html>
<html>
<head>
<title>Crossed Out</title>
<meta charset="utf-8" />
</head>
<body>
<canvas id="canvas" width="720" height="1280"></canvas>
<script src="https://example.com/pythons.js" async defer type="module"></script>
</body>
</html>
"""


@pytest.fixture
def tmp_index(tmp_path):
    p = tmp_path / "index.html"
    p.write_text(PYGBAG_LIKE_INDEX, encoding="utf-8")
    return p


class TestInjection:
    def test_first_run_injects(self, tmp_index):
        assert inject_loader.inject(tmp_index) is True
        text = tmp_index.read_text(encoding="utf-8")
        assert inject_loader.SENTINEL in text
        assert "#cx-loader" in text
        assert "CROSSED OUT" in text
        # Hide-script must be present so the overlay actually disappears
        # once pygame starts drawing.
        assert "gameReady" in text

    def test_second_run_is_no_op(self, tmp_index):
        inject_loader.inject(tmp_index)
        text_after_first = tmp_index.read_text(encoding="utf-8")
        assert inject_loader.inject(tmp_index) is False
        text_after_second = tmp_index.read_text(encoding="utf-8")
        # No duplicate injection.
        assert text_after_first == text_after_second

    def test_css_lands_inside_head(self, tmp_index):
        inject_loader.inject(tmp_index)
        text = tmp_index.read_text(encoding="utf-8")
        # The <style> block should appear before </head>.
        head_close = text.lower().index("</head>")
        style_open = text.lower().index("<style>")
        assert style_open < head_close

    def test_overlay_lands_inside_body(self, tmp_index):
        inject_loader.inject(tmp_index)
        text = tmp_index.read_text(encoding="utf-8")
        # The overlay div should be inside <body>...</body>.
        body_close = text.lower().index("</body>")
        loader_open = text.index("<div id=\"cx-loader\"")
        assert loader_open < body_close
        body_open = text.lower().index("<body>")
        assert loader_open > body_open

    def test_missing_head_tag_does_not_crash(self, tmp_path):
        weird = tmp_path / "weird.html"
        weird.write_text("<html><body><p>no head</p></body></html>", encoding="utf-8")
        # Should print a warning but still inject something useful.
        assert inject_loader.inject(weird) is True
        text = weird.read_text(encoding="utf-8")
        assert "#cx-loader" in text

    def test_main_returns_nonzero_when_missing(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        rc = inject_loader.main()
        assert rc == 1
