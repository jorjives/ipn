import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout

from ideclare.cli import main
from tests.test_parser import FLEET, RATING


def run(*argv) -> tuple[int, str]:
    out = io.StringIO()
    with redirect_stdout(out):
        code = main(list(argv))
    return code, out.getvalue()


class QuoteCommand(unittest.TestCase):
    def test_items_come_from_a_csv(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "fleet.idl"), "w") as f:
                f.write(FLEET)
            with open(os.path.join(d, "bikes.csv"), "w") as f:
                f.write("value,age,security\n2000,0,gold\n1000,3,silver\n")
            code, out = run("quote", os.path.join(d, "fleet.idl"), "rider_age=30", "bikes=bikes.csv")
        self.assertEqual(code, 0, out)
        self.assertIn("Theft on bike 1: included, limit 2000.00", out)
        self.assertIn("Theft on bike 2: included, limit 1000.00", out)
        self.assertIn("bike 2 Bike age", out)
        self.assertIn("= 82.65", out)  # 60 + 27, x 0.95



if __name__ == "__main__":
    unittest.main()
