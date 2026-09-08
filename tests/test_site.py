"""The site's generated pages match the code, and its links resolve."""
import re
import unittest
from pathlib import Path

from scripts.site_pages import EXAMPLES, ROOT, TEMPLATES, render

DOCS = ROOT / "docs"


class Config(unittest.TestCase):
    def test_plain_scalars_do_not_contain_colon_space(self):
        """GitHub Pages (Psych) rejects unquoted `key: foo: bar` as a nested mapping."""
        for i, line in enumerate((DOCS / "_config.yml").read_text(encoding="utf-8").splitlines(), 1):
            stripped = line.lstrip()
            if not stripped or stripped.startswith("#"):
                continue
            if stripped.startswith("- "):
                rest = stripped[2:]
                if ": " in rest and rest[:1] not in {'"', "'", "[", "{"}:
                    value = rest.split(": ", 1)[1]
                else:
                    value = rest
            elif ": " in stripped:
                value = stripped.split(": ", 1)[1]
            else:
                continue
            if value[:1] in {'"', "'", "[", "{", "|", ">"}:
                continue
            self.assertNotIn(
                ": ",
                value,
                f"docs/_config.yml:{i}: quote this value; an unquoted colon-space is invalid YAML",
            )


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


class Truthful(unittest.TestCase):
    """No hand-written page may still say a repeatable item cannot be batched."""

    def test_no_page_says_items_cannot_be_batched(self):
        for page in DOCS.rglob("*.md"):
            if "superpowers" in page.parts:
                continue
            with self.subTest(page.relative_to(ROOT)):
                self.assertNotIn("cannot be given in a batch row", page.read_text(encoding="utf-8"))

    def test_the_command_line_page_documents_the_collection_bindings(self):
        md = (DOCS / "cli.md").read_text(encoding="utf-8")
        self.assertIn("python3 -m ipngine batch FILE.ipn RISKS.csv [collection=file.csv ...]", md)
        self.assertIn(
            "python3 -m ipngine batch examples/home.ipn examples/home-risks.csv "
            "specified_items=examples/home-specified-items.csv",
            md,
        )
        self.assertIn("`risk`", md)

    def test_the_language_pages_point_at_the_join(self):
        inputs = (DOCS / "reference/inputs.md").read_text(encoding="utf-8")
        self.assertIn("`risk`", inputs)
        self.assertIn("(../cli.md)", inputs)
        started = (DOCS / "getting-started.md").read_text(encoding="utf-8")
        self.assertIn("second CSV", started)
        glossary = (DOCS / "glossary.md").read_text(encoding="utf-8")
        self.assertIn("cli.md", glossary)


class Playground(unittest.TestCase):
    """The browser playground fetches the engine and the products by name, so the names must not drift."""

    def test_engine_file_list_matches_the_package(self):
        expected = {p.name for p in (ROOT / "ipngine").glob("*.py")}
        for name in ("playground.js", "book.js"):
            js = (DOCS / "assets/js" / name).read_text(encoding="utf-8")
            with self.subTest(name):
                self.assertEqual(set(re.findall(r'"(\w+\.py)"', js)), expected)

    def test_every_same_site_asset_the_playground_uses_exists(self):
        js = (DOCS / "assets/js/playground.js").read_text(encoding="utf-8")
        md = (DOCS / "playground.md").read_text(encoding="utf-8")
        used = ([DOCS / "assets/js" / m for m in re.findall(r'"\./([\w.-]+)"', js)]
                + [DOCS / "assets" / m for m in re.findall(r'"\.\./([\w.-]+)"', js)]
                + [DOCS / "assets" / m for m in re.findall(r'/assets/([\w./-]+)"', md)])
        self.assertEqual(len(used), 3, "the module, the grammar table and the page's script")
        for path in used:
            with self.subTest(path.name):
                self.assertTrue(path.exists(), f"{path.name} is used by the playground but missing")

    def test_example_menu_matches_the_generated_pages(self):
        md = (DOCS / "playground.md").read_text(encoding="utf-8")
        expected = [f"examples/{s}.ipn" for s, *_ in EXAMPLES] + [f"templates/{s}.ipn" for s, *_ in TEMPLATES]
        self.assertEqual(re.findall(r'value="([^"]+\.ipn)"', md), expected)


class Book(unittest.TestCase):
    """The Price a book page prices a prepared sample twice and must keep its files."""

    def test_the_page_loads_the_prepared_files_from_the_site(self):
        md = (DOCS / "book.md").read_text(encoding="utf-8")
        js = (DOCS / "assets/js/book.js").read_text(encoding="utf-8")
        self.assertIn("title: Price a book", md)
        self.assertIn("assets/js/book.js", md)
        for name in ("before.ipn", "after.ipn", "risks.csv"):
            self.assertIn(name, js)
            self.assertTrue((DOCS / "assets/book" / name).exists(), name)

    def test_every_same_site_asset_the_page_uses_exists(self):
        js = (DOCS / "assets/js/book.js").read_text(encoding="utf-8")
        md = (DOCS / "book.md").read_text(encoding="utf-8")
        used = ([DOCS / "assets/js" / m for m in re.findall(r'"\./([\w.-]+)"', js)]
                + [DOCS / "assets" / m for m in re.findall(r'"\.\./([\w./-]+)"', js)]
                + [DOCS / "assets" / m for m in re.findall(r'/assets/([\w./-]+)"', md)])
        self.assertGreaterEqual(len(used), 2, "the page script and the files it fetches")
        for path in used:
            with self.subTest(str(path.relative_to(DOCS))):
                self.assertTrue(path.exists(), f"{path.name} is used by Price a book but missing")

    def test_the_page_shows_the_two_file_shape_for_risks_with_items(self):
        md = (DOCS / "book.md").read_text(encoding="utf-8")
        self.assertNotIn("cannot be given in a batch row", md)
        self.assertIn("## Risks with items", md)
        self.assertIn("home-risks.csv", md)
        self.assertIn("home-specified-items.csv", md)
        self.assertIn("specified_items=examples/home-specified-items.csv", md)
        self.assertIn("(cli.md)", md)

    def test_the_live_comparison_is_untouched(self):
        js = (DOCS / "assets/js/book.js").read_text(encoding="utf-8")
        self.assertNotIn("home-specified-items.csv", js)
        self.assertNotIn("specified_items", js)
