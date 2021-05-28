from odoo import fields, models, _
from odoo.exceptions import ValidationError

# class Xero_Log(models.Model):
#     _name = 'xero.log'
#     _description = 'xero log'
#     _order = 'id desc'
#
#     company_id = fields.Many2one('res.company', String='Company')
#     payment_id = fields.Many2one('account.payment', string="Payment", ondelete="cascade")
#     invoice_id = fields.Many2one('account.move', string="Invoice", ondelete="cascade")
#     xero_payment_id = fields.Char('Xero Payment Id')
#     payment_status = fields.Char('Status')
#     active = fields.Boolean('Active')

    # def delete_payment(self):
    #     if self.payment_id:
    #         payment = self.env['account.payment'].search([('xero_payment_id', '=', self.xero_payment_id)])
    #         if payment:
    #             self.active = False
    #         else:
    #             raise Warning('The payment your looking for is not present.')

    # def reconcile_payment(self):
    #
    #     if self.xero_payment_id and self.invoice_id:
    #         if self.invoice_id.state != 'paid':
    #             self.payment_id.post(xero_payment_id=self.xero_payment_id, invoice_id=self.invoice_id)
    #             self.active = False
    #         else:
    #             raise ValidationError('The Invoice need to be unreconciled.')


class XeroErrorLog(models.Model):
    _name = 'xero.error.log'
    _description = 'Xero Error Log'
    _rec_name = 'transaction'
    _order = 'id desc'

    transaction = fields.Char('Transaction')
    record_id = fields.Char('Record Id')
    xero_error_response = fields.Char('Error Response')
    error_date = fields.Datetime('Date')
    # active = fields.Boolean('Active')