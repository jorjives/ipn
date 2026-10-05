"""parse() raises only ParseError, located on a line, whatever text it is given."""
import random
import unittest
from pathlib import Path

from ipngine.parser import ParseError, parse

ROOT = Path(__file__).resolve().parent.parent

# (product, a line in it, a hostile replacement): each once escaped parse as another exception.
CASES = [
    ("examples/cycle.ipn", "  term 12 months", "  term ) months"),
    ("examples/cycle.ipn", "  term 12 months", "  term ( months"),
    ("examples/cycle.ipn", "  cancellation by customer: refund pro rata, fee 25", "  cancellation by"),
    ("examples/cycle.ipn", "  cancellation by customer: refund pro rata, fee 25", "  cancellation by customer"),
    ("examples/cycle.ipn", "  adjustment: reprice, charge pro rata difference, fee 10", "  adjustment: reprice, charge pro rata difference, fee ,"),
    ("examples/cycle.ipn", "  lapse when unpaid after 30 days", "  lapse when unpaid after , days"),
    ("examples/cycle.ipn", "    invite 21 days before expiry", "    invite x days before expiry"),
    ("examples/cycle.ipn", "    increase capped at 20%", "    increase capped at x%"),
    ("examples/cycle.ipn", "    decrease collared at 10%", "    decrease collared at x%"),
    ("examples/cycle.ipn", "  after 2 claims in term: renewal load x 1.25", "  after"),
    ("examples/cycle.ipn", "  after 2 claims in term: renewal load x 1.25", "  after % claims in term: renewal load x 1.25"),
    ("examples/cycle.ipn", "  after 2 claims in term: renewal load x 1.25", "  after 2 claims in term: renewal load x after"),
    ("examples/cycle.ipn", "  after 1 claim in term", "  after x claim in term"),
    ("examples/cycle.ipn", "given bike_value 2000, rider_age 30,", "given bike_value 2000, rider_age 2024-13-40,"),
    ("examples/multibike.ipn", "  bikes: collection of bike, 1 to 6", "  bikes: collection of bike, 1 to ,"),
    ("examples/income.ipn", "  waiting period 90 days", "  waiting period ( days"),
    ("examples/pi.ipn", "  reinstatement at 100% of premium pro rata", "  reinstatement at x% of premium pro rata"),
    ("examples/motor.ipn", "  instalments 12 monthly, charge 10%", "  instalments 12 monthly, charge x%"),
    ("examples/motor.ipn", "      index ncd_years by -2, at least 0", "      index ncd_years by -2, at least -"),
    ("examples/leasing.ipn", "lease_start 2026-01-01", "lease_start 2026-13-40"),
    ("examples/versioned/bike-2026-07-01.ipn", "    from 2027-03-01 requires", "    from 2027-13-01 requires"),
    ("templates/versioned/versioned-product-2027-01-01.ipn", "  published 2027-01-01", "  published 2027-02-30"),
    ("templates/versioned/versioned-product-2027-01-01.ipn", "  when bound on 2027-02-01", "  when bound on 2027-02-31"),
]


def attempt(test, path, text):
    try:
        parse(text, base=str((ROOT / path).parent))
    except ParseError as e:
        test.assertRegex(str(e), r"^line \d+: ", text)
    except Exception as e:  # noqa: BLE001 - the point is that nothing else escapes
        test.fail(f"{type(e).__name__}: {e}")


class Hostile(unittest.TestCase):
    def test_each_known_escape_is_a_located_parse_error(self):
        for path, old, new in CASES:
            with self.subTest(path=path, line=new):
                text = (ROOT / path).read_text()
                self.assertIn(old, text)
                attempt(self, path, text.replace(old, new, 1))

    def test_deep_nesting_is_a_located_parse_error(self):
        text = (ROOT / "examples/cycle.ipn").read_text()
        for deep in ("(" * 500 + "1" + ")" * 500, "not " * 2000 + "yes", "- " * 2000 + "1", "2 ^ " * 2000 + "1"):
            with self.subTest(deep=deep[:12]):
                attempt(self, "examples/cycle.ipn", text.replace("rider_age < 16", deep, 1))

    def test_random_mutations_raise_only_parse_errors(self):
        """A fixed-seed fuzz: truncate, drop, repeat or replace one word on one line of each product."""
        paths = sorted(p.relative_to(ROOT) for d in ("examples", "templates") for p in (ROOT / d).rglob("*.ipn"))
        junk = ["x", "0", ":", ",", "(", ")", "%", '"', "-1", "2024-13-40", "1x", "by", "at", "when"]
        for path in paths:
            lines = (ROOT / path).read_text().splitlines()
            rng = random.Random(str(path))
            for _ in range(60):
                i = rng.randrange(len(lines))
                words = lines[i].split()
                if not words:
                    continue
                j = rng.randrange(len(words))
                op = rng.randrange(4)
                if op == 0:
                    words = words[:j]
                elif op == 1:
                    del words[j]
                elif op == 2:
                    words.insert(j, rng.choice(words))
                else:
                    words[j] = rng.choice(junk)
                indent = lines[i][:len(lines[i]) - len(lines[i].lstrip())]
                mutated = lines[:i] + [indent + " ".join(words)] + lines[i + 1:]
                with self.subTest(path=str(path), line=i + 1, text=mutated[i]):
                    attempt(self, path, "\n".join(mutated))


if __name__ == "__main__":
    unittest.main()
