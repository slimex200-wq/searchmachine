import unittest

from pipelines.classify import filter_major_sales


class TestFilterMajorSales(unittest.TestCase):
    def test_keeps_only_major_with_title_and_link(self) -> None:
        rows = [
            {"sale_tier": "major", "sale_name": "Mega Sale", "link": "https://example.com/event/1"},
            {"sale_tier": "minor", "sale_name": "Small Sale", "link": "https://example.com/event/2"},
            {"sale_tier": "major", "sale_name": "", "link": "https://example.com/event/3"},
            {"sale_tier": "major", "sale_name": "No Link", "link": ""},
        ]
        kept, filtered = filter_major_sales(rows, title_key="sale_name")

        self.assertEqual(1, len(kept))
        self.assertEqual("Mega Sale", kept[0]["sale_name"])
        self.assertEqual(3, len(filtered))


if __name__ == "__main__":
    unittest.main()
