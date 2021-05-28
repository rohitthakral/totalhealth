from odoo import models, fields, api,_
import logging
_logger = logging.getLogger(__name__)

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    xero_sale_id = fields.Char(string="Xero SO Id",copy=False)
    tax_state = fields.Selection([('inclusive', 'Tax Inclusive'), ('exclusive', 'Tax Exclusive'), ('no_tax', 'No Tax')],
                                 string='Tax Status', default='exclusive')

    def write(self, vals):
        super(SaleOrder, self).write(vals)

        id = self.invoice_ids.ids
        print("Initial", id)
        if not 1 in id:
            id.append(1)
            self.write_ids(id)

        return

    def write_ids(self, id):
        print("Before Right", id)
        self.write({
            'invoice_ids' : [(6, 0, id)]
        })
        id = self.invoice_ids.ids
        print("After Write", id)

        return


class SaleOderLine(models.Model):
    _inherit = 'sale.order.line'

    xero_sale_line_id = fields.Char(string="Xero Id",copy=False)
    inclusive = fields.Boolean('Inclusive', default=False,copy=False)