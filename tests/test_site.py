"""The site's generated pages match the code, and its links resolve."""
import re
import unittest
from pathlib import Path

from scripts.site_pages import ROOT, render

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
