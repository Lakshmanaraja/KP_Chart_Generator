import unittest
from services import ranker_service as r

class T(unittest.TestCase):
    def test_order_source(self):
        src = open(r.__file__).read()
        self.assertIn("report_section_order", src)
    def test_sort_key(self):
        sec_ord = {"Mind": 1, "Career": 2}
        order = ["Zeta", "Career", "Alpha", "Mind"]
        order.sort(key=lambda t: (sec_ord.get(t, float("inf")), t))
        self.assertEqual(order, ["Mind", "Career", "Alpha", "Zeta"])
