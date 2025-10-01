# © 2012-2014 Guewen Baconnier (Camptocamp SA)
# © 2015 Roberto Lizana (Trey)
# © 2016 Pedro M. Baeza
# © 2018 Xavier Jimenez (QubiQ)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import api, fields, models
from odoo.fields import Domain


class ProductProduct(models.Model):
    _inherit = "product.product"

    barcode_ids = fields.One2many(
        comodel_name="product.barcode",
        inverse_name="product_id",
        string="Barcodes",
        bypass_search_access=True,
    )
    barcode = fields.Char(
        string="Main barcode",
        compute="_compute_barcode",
        store=True,
        inverse="_inverse_barcode",
        compute_sudo=True,
    )

    @api.depends("barcode_ids.name", "barcode_ids.sequence")
    def _compute_barcode(self):
        for product in self:
            product.barcode = product.barcode_ids[:1].name

    def _inverse_barcode(self):
        """Store the product's barcode value in the barcode model."""
        barcodes_to_unlink = self.env["product.barcode"]
        create_barcode_vals_list = []
        for product in self:
            if product.barcode_ids:
                product.barcode_ids[0].name = product.barcode
            elif not product.barcode:
                barcodes_to_unlink |= product.barcode_ids
            else:
                create_barcode_vals_list.append(product._prepare_barcode_vals())
        if barcodes_to_unlink:
            barcodes_to_unlink.unlink()
        if create_barcode_vals_list:
            self.env["product.barcode"].create(create_barcode_vals_list)

    def _prepare_barcode_vals(self):
        self.ensure_one()
        return {
            "product_id": self.id,
            "name": self.barcode,
        }

    @api.model
    def _search(self, domain, *args, **kwargs):
        domain = Domain(domain).map_conditions(self._map_barcode_condition)
        return super()._search(domain, *args, **kwargs)

    def _map_barcode_condition(self, condition):
        """Redirect a condition on ``barcode`` to the product's whole barcode list.

        ``barcode`` only holds the first of ``barcode_ids``, so matching it as
        such would ignore every other barcode of the product.
        """
        if condition.field_expr != "barcode":
            return condition
        positive_operator = Domain.NEGATIVE_OPERATORS.get(condition.operator)
        if positive_operator:
            # Negate the positive match rather than forwarding the negative
            # operator: on a one2many the latter matches as soon as *another*
            # barcode of the product differs from the value.
            return ~self._get_barcode_domain(positive_operator, condition.value)
        return self._get_barcode_domain(condition.operator, condition.value)

    def _get_barcode_domain(self, operator, value):
        """Return the domain on ``barcode_ids`` positively matching ``value``."""
        if operator == "=":
            values = [value]
        elif operator == "in":
            values = list(value)
        else:
            return Domain("barcode_ids.name", operator, value)
        # A falsy barcode means "no barcode at all", which is a condition on the
        # one2many itself: a product without lines never matches on their name.
        domain = Domain("barcode_ids.name", "in", [v for v in values if v])
        if not all(values):
            domain |= Domain("barcode_ids", "=", False)
        return domain
