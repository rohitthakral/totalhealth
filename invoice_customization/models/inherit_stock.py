# -*- coding: utf-8 -*-

from odoo import api, fields, models, tools
from odoo.tools.translate import _
import logging
_logger = logging.getLogger(__name__)


class Picking(models.Model):
    _inherit = "stock.picking"
    
    def button_validate(self):
        res = super(Picking,self).button_validate()
        check = self.env['ir.default'].sudo().get('res.config.settings', 'post_invoice')
        for picking in self:
            if picking.state =='done' and picking.origin:
                SO=None
                flag=None
                if picking.picking_type_id.code=='outgoing':
                    SO = self.env['sale.order'].sudo().search([('name','=',picking.origin)])
                elif picking.picking_type_id.code=='incoming' and picking.picking_type_id.sequence_code=='DS':
                    SO = self.env['sale.order'].sudo().search([('name','=',picking.group_id.name)])
                    flag=True
                
                lines_to_pick = picking.move_line_ids.mapped('product_id').filtered(lambda product:True if product.invoice_policy=='delivery' and product.is_invoicable==False else False )
                if lines_to_pick:
                    context = self._context.copy()
                    context.update({
                        'onlydelivered': True,
                        'productId': lines_to_pick,
                    })
                    
                    if SO:
                        moves = SO.with_context(context)._create_invoices(final=True)
                        if not flag and check:
                            moves.action_post()

        return res

class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _get_invoiceable_lines(self, final=False):
        invoiceable_lines = super()._get_invoiceable_lines(final)
        context = self._context.copy()
        if context.get('onlydelivered',None):
            productId = context.get('productId',None)
            
            return invoiceable_lines.filtered(lambda line: True if line.product_id.invoice_policy=='delivery' and line.product_id in productId and line.product_id.is_invoicable==False else False)
        return invoiceable_lines.filtered(lambda line: True if line.product_id.is_invoicable==False else False)


class ProductTemplate(models.Model):
    _inherit = "product.template"

    is_invoicable = fields.Boolean('Not Invoiced', default=False)



class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    
    def _compute_invoice_status(self):
        super(SaleOrderLine, self)._compute_invoice_status()
        for line in self:
            if line.product_id.is_invoicable:
                line.invoice_status = 'invoiced'


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    post_invoice = fields.Boolean(string='Post Invoice Automatically (SO/WH)',default=True)

    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        IrDefault = self.env['ir.default'].sudo()
        res.update({
            'post_invoice':IrDefault.get('res.config.settings','post_invoice'),
        })
        return res



    @api.model
    def set_values(self):
        super(ResConfigSettings, self).set_values()
        IrDefault = self.env['ir.default'].sudo()
        IrDefault.set('res.config.settings','post_invoice', self.post_invoice)
        return True
