"""The site's generated pages match the code, and its links resolve."""
import re
import unittest
from pathlib import Path

from scripts.site_pages import EXAMPLES, ROOT, TEMPLATES, render

DOCS = ROOT / "docs"


class GeneratedPages(unittest.TestCase):
    def test_committed_pages_are_what_the_script_renders(self):
        for rel, content in render().items():
            with self.subTest(rel):
                path = ROOT / rel
                self.assertTrue(path.exists(), f"{rel} is missing; run python3 scripts/site_pages.py")
                self.assertEqual(path.read_text(encoding="utf-8"), content, f"{rel} is stale; run python3 scripts/site_pages.py")


class Links(unittest.TestCase):
    def test_every_relative_markdown_link_resolves(self):
        for page in DOCS.rglob("*.md"):
            if "superpowers" in page.parts:
                continue
            for target in re.findall(r"\]\(([^)#]+\.md)(?:#[^)]*)?\)", page.read_text(encoding="utf-8")):
                if target.startswith("http"):
                    continue
                with self.subTest(f"{page.relative_to(ROOT)} -> {target}"):
                    self.assertTrue((page.parent / target).resolve().exists(), f"{page.relative_to(ROOT)} links to missing {target}")


class Playground(unittest.TestCase):
    """The browser playground fetches the engine and the products by name, so the names must not drift."""

    def test_engine_file_list_matches_the_package(self):
        js = (DOCS / "assets/js/playground.js").read_text(encoding="utf-8")
        self.assertEqual(set(re.findall(r'"(\w+\.py)"', js)), {p.name for p in (ROOT / "ideclare").glob("*.py")})

    def test_example_menu_matches_the_generated_pages(self):
        md = (DOCS / "playground.md").read_text(encoding="utf-8")
        expected = [f"examples/{s}.idl" for s, *_ in EXAMPLES] + [f"templates/{s}.idl" for s, *_ in TEMPLATES]
        self.assertEqual(re.findall(r'value="([^"]+\.idl)"', md), expected)
