# © 2016 Pedro M. Baeza
# © 2018 Xavier Jimenez (QubiQ)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo.exceptions import ValidationError
from odoo.fields import Domain
from odoo.tests import TransactionCase, tagged
from odoo.tools import SQL

from ..hooks import post_init_hook


@tagged("post_install", "-at_install")
class TestProductMultiBarcode(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Product 1
        cls.product = cls.env["product.product"]
        cls.product_1 = cls.product.create({"name": "Test product 1"})
        cls.valid_barcode_1 = "1234567890128"
        cls.valid_barcode2_1 = "0123456789012"
        # Product 2
        cls.product_2 = cls.product.create({"name": "Test product 2"})
        cls.valid_barcode_2 = "9780471117094"
        cls.valid_barcode2_2 = "4006381333931"

    def _set_barcodes(self):
        self.product_1.barcode_ids = [
            (0, 0, {"name": self.valid_barcode_1}),
            (0, 0, {"name": self.valid_barcode2_1}),
        ]
        self.product_2.barcode_ids = [
            (0, 0, {"name": self.valid_barcode_2}),
            (0, 0, {"name": self.valid_barcode2_2}),
        ]

    def test_set_main_barcode(self):
        self.product_1.barcode = self.valid_barcode_1
        self.assertEqual(len(self.product_1.barcode_ids), 1)
        self.assertEqual(self.product_1.barcode_ids.name, self.product_1.barcode)

    def test_set_incorrect_barcode(self):
        self.product_1.barcode = self.valid_barcode_1
        # Insert duplicated EAN13
        with self.assertRaisesRegex(
            ValidationError,
            (
                f'The Barcode "{self.valid_barcode_1}" already exists '
                f'for product "{self.product_1.name}"'
            ),
        ):
            self.product_1.barcode_ids = [(0, 0, {"name": self.valid_barcode_1})]

    def test_post_init_hook(self):
        self.env.cr.execute(
            """
            UPDATE product_product
            SET barcode = %s
            WHERE id = %s""",
            (self.valid_barcode_1, self.product_1.id),
        )
        post_init_hook(self.env)
        self.product_1.invalidate_recordset()
        self.assertEqual(len(self.product_1.barcode_ids), 1)
        self.assertEqual(self.product_1.barcode_ids.name, self.valid_barcode_1)

    def test_search(self):
        self._set_barcodes()
        products = self.product.search([("barcode", "=", self.valid_barcode_1)])
        self.assertEqual(len(products), 1)
        self.assertEqual(products, self.product_1)
        products = self.product.search([("barcode", "=", self.valid_barcode2_1)])
        self.assertEqual(len(products), 1)
        self.assertEqual(products, self.product_1)
        products = self.product.search(
            [
                "|",
                ("barcode", "=", self.valid_barcode2_1),
                ("barcode", "=", self.valid_barcode2_2),
            ]
        )
        self.assertEqual(len(products), 2)

    def test_search_operators(self):
        """Every positive operator matches on any barcode of the product."""
        self._set_barcodes()
        for domain in (
            [("barcode", "in", [self.valid_barcode2_1])],
            [("barcode", "in", [self.valid_barcode2_1, self.valid_barcode_1])],
            [("barcode", "ilike", self.valid_barcode2_1)],
            Domain("barcode", "=", self.valid_barcode2_1),
            Domain("barcode", "=", self.valid_barcode2_1) & Domain("active", "=", True),
        ):
            products = self.product.search(domain)
            self.assertEqual(products, self.product_1, f"Failed for {domain}")

    def test_search_negative_operators(self):
        """A product owning the value must not match, whichever other barcodes
        it also owns."""
        self._set_barcodes()
        for domain in (
            [("barcode", "!=", self.valid_barcode2_1)],
            [("barcode", "not in", [self.valid_barcode2_1])],
            [("barcode", "not ilike", self.valid_barcode2_1)],
        ):
            products = self.product.search(domain)
            self.assertNotIn(self.product_1, products, f"Failed for {domain}")
            self.assertIn(self.product_2, products, f"Failed for {domain}")
        products = self.product.search(
            [("barcode", "not in", [self.valid_barcode2_1, self.valid_barcode_2])]
        )
        self.assertNotIn(self.product_1, products)
        self.assertNotIn(self.product_2, products)

    def test_search_without_barcode(self):
        """A falsy value filters on the barcode list, not on its names."""
        self._set_barcodes()
        product_3 = self.product.create({"name": "Test product 3"})
        products = self.product.search([("barcode", "=", False)])
        self.assertIn(product_3, products)
        self.assertNotIn(self.product_1, products)
        products = self.product.search([("barcode", "!=", False)])
        self.assertIn(self.product_1, products)
        self.assertNotIn(product_3, products)
        # A product without barcodes satisfies any negative condition
        products = self.product.search(
            [("barcode", "not ilike", self.valid_barcode2_1)]
        )
        self.assertIn(product_3, products)

    def test_search_custom_condition(self):
        """A condition generating its own SQL is left untouched."""
        self._set_barcodes()
        always_true = Domain.custom(to_sql=lambda model, alias, query: SQL("TRUE"))
        products = self.product.search(
            Domain("barcode", "=", self.valid_barcode2_1) & always_true
        )
        self.assertEqual(products, self.product_1)
