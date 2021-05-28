from odoo import models, fields, api,_
from odoo.exceptions import UserError, ValidationError
import requests
import json
import logging
import base64
_logger = logging.getLogger(__name__)

class Account_Payment(models.Model):
    _inherit = 'account.payment'

    xero_payment_id = fields.Char(string="Xero Payment Id",copy=False)
    xero_prepayment_id = fields.Char(string="Xero Prepayment Id", copy=False)
    xero_overpayment_id = fields.Char(string="Xero Overpayment Id", copy=False)

    # @api.model
    # def create_log(self,xero_payment_id,invoice_id):
    #     xero_config = self.env['res.users'].search([('id', '=', self._uid)], limit=1).company_id
    #     # print("Payment create function.")
    #
    #     log_id = self.env['xero.log'].create(
    #         {
    #             'company_id': xero_config.id,
    #             'payment_id': self.id,
    #             'invoice_id':invoice_id.id,
    #             'active':True,
    #             'xero_payment_id': xero_payment_id,
    #             'payment_status': 'The payment cannot be processed because the invoice is not open!',
    #         }
    #     )
    #     print("log_id : ",log_id)
    #     return True

    # @api.model
    # def delete_log(self,log_search):
    #     # Deletes the record of the payments from logs when reconciled from front-end
    #     # print("Payment delete function.")
    #     log_id = log_search.write(
    #         {
    #             'active': False,
    #         }
    #     )

    # def action_post(self,xero_payment_id=None,invoice_id=None):
    #     # Post the payments "normally" if no transactions are needed.
    #     # If not, let the acquirer updates the state.
    #     #                                __________            ______________
    #     #                               | Payments |          | Transactions |
    #     #                               |__________|          |______________|
    #     #                                  ||                      |    |
    #     #                                  ||                      |    |
    #     #                                  ||                      |    |
    #     #  __________  no s2s required   __\/______   s2s required |    | s2s_do_transaction()
    #     # |  Posted  |<-----------------|  post()  |----------------    |
    #     # |__________|                  |__________|<-----              |
    #     #                                                |              |
    #     #                                               OR---------------
    #     #  __________                    __________      |
    #     # | Cancelled|<-----------------| cancel() |<-----
    #     # |__________|                  |__________|
    #     print("here :--------------------5------------------>")
    #     log_created = None
    #     for rec in self:
    #
    #         print("rec.state : ",rec.state)
    #         if rec.state != 'draft':
    #             raise UserError(_("Only a draft payment can be posted."))
    #         print("rec.reconciled_invoice_ids : ",rec.reconciled_invoice_ids)
    #
    #         if any(inv.state != 'posted' for inv in rec.reconciled_invoice_ids):
    #             # raise ValidationError(_("The payment cannot be processed because the invoice is not open!"))
    #             print("xero_payment_id : ",xero_payment_id)
    #             if xero_payment_id:
    #                 log_search = self.env['xero.log'].search([('xero_payment_id', '=', self.xero_payment_id)])
    #                 print("log_search : ",log_search)
    #                 if log_search:
    #                     _logger.info(_("Payment found in Logs details."))
    #                 elif not log_search:
    #                     print("invoice_id.state :----------------> ",invoice_id.state)
    #                     if (invoice_id.state == 'draft'):
    #                         log_created = self.create_log(xero_payment_id, invoice_id)
    #         else:
    #             log_search = self.env['xero.log'].search([('xero_payment_id', '=', self.xero_payment_id)])
    #             if log_search:
    #                 log_created = self.delete_log(log_search)
    #
    #     print("log_created :-----------------------> ",log_created)
    #     mmmmmmmmmmmmm
    #     if not log_created:
    #         payments_need_trans = self.filtered(lambda pay: pay.payment_token_id and not pay.payment_transaction_id)
    #         transactions = payments_need_trans._create_payment_transaction()
    #
    #         res = super(Account_Payment, self - payments_need_trans).action_post()
    #
    #         transactions.s2s_do_transaction()
    #
    #         return res




    def prepare_payment_export_dict(self):
        """Create Dictionary to export to XERO"""
        vals = {}

        invoice_ids = False
        if self.reconciled_invoice_ids:
            invoice_ids = self.reconciled_invoice_ids
        if self.reconciled_bill_ids:
            invoice_ids = self.reconciled_bill_ids

        if invoice_ids:

            xero_id = False
            if len(invoice_ids) == 1:
                for invoice in invoice_ids:
                    if not invoice.xero_invoice_id:
                        if invoice.state == 'posted':
                            if invoice.move_type == 'out_invoice' or invoice.move_type == 'in_invoice':
                                invoice.exportInvoice(payment_export=True)
                            if invoice.move_type == 'out_refund' or invoice.move_type == 'in_refund':
                                invoice.exportCreditNote(payment_export=True)
                            xero_id = invoice.xero_invoice_id
                    if invoice.xero_invoice_id:
                        xero_id = invoice.xero_invoice_id
                    if invoice.move_type == 'out_invoice' or invoice.move_type == 'in_invoice':
                        ApplyOn = "Invoice"
                        ApplyOn_Dict = {"InvoiceID": xero_id}
                    if invoice.move_type == 'out_refund' or invoice.move_type == 'in_refund':
                        ApplyOn = "CreditNote"
                        ApplyOn_Dict = {"CreditNoteID": xero_id}

                    # print("xero_id ::::::::::::: ",xero_id)
                    # print("ApplyOn ::::::::::::: ",ApplyOn)
                    # print("ApplyOn_Dict ::::::::::::: ",ApplyOn_Dict)
                    #
                    # print("self.journal_id : ",self.journal_id)
                    # print("self.journal_id.default_debit_account_id : ",self.journal_id.default_account_id)
                    # print("self.journal_id.default_debit_account_id.xero_account_id : ",self.journal_id.default_account_id.xero_account_id)

                    if self.journal_id.default_account_id:
                        if not self.journal_id.default_account_id.xero_account_id:
                            self.env['account.account'].create_account_ref_in_xero(self.journal_id.default_account_id)

                        if xero_id and ApplyOn and ApplyOn_Dict:
                            # if len(self.invoice_ids) > 1:
                            #     vals.update({
                            #         "Payments": [
                            #             {
                            #                 ApplyOn : ApplyOn_Dict,
                            #                 "Account": {"AccountID": self.journal_id.default_debit_account_id.xero_account_id},
                            #                 "Date": self.payment_date,
                            #                 "Amount": self.amount,
                            #                 "Reference": self.name
                            #             }
                            #         ]
                            #     })
                            if len(invoice_ids) == 1:
                                vals.update({
                                              ApplyOn: ApplyOn_Dict ,
                                              "Account": {"AccountID": self.journal_id.default_account_id.xero_account_id},
                                              "Date": str(self.date),
                                              "Amount": self.amount,
                                              "Reference": self.name
                                            })
        print('vals :----------------------> ',vals)

        return vals

    # @api.multi
    def get_head(self):
        xero_config = self.env['res.users'].search([('id', '=', self._uid)], limit=1).company_id
        client_id = xero_config.xero_client_id
        client_secret = xero_config.xero_client_secret

        # data = client_id + ":" + client_secret
        data = ('%s:%s' % (client_id, client_secret))
        encodedBytes = base64.b64encode(data.encode("utf-8"))
        encodedStr = str(encodedBytes).encode("utf-8")
        headers = {
            'Authorization': "Bearer " + str(xero_config.xero_oauth_token),
            'Xero-tenant-id': xero_config.xero_tenant_id,
            'Accept': 'application/json'

        }
        return headers


    @api.model
    def create_payment_in_xero(self):
        """export payment to XERO"""
        xero_config = self.env['res.users'].search([('id', '=', self._uid)], limit=1).company_id
        if self._context.get('active_ids'):
            payments = self.browse(self._context.get('active_ids'))
        else:
            payments = self


        for payment in payments:
            if payment.xero_payment_id:
                raise ValidationError("Payment is already exported to Xero!")
            if not payment.xero_payment_id:
                vals = payment.prepare_payment_export_dict()
                if not vals:
                    raise ValidationError("Payment can not be exported, something went wrong...!!")

                parsed_dict = json.dumps(vals)
                if xero_config.xero_oauth_token:
                    token = xero_config.xero_oauth_token
                headers = self.get_head()
                if token:
                    protected_url = 'https://api.xero.com/api.xro/2.0/Payments'
                    data = requests.request('POST', url=protected_url, data=parsed_dict, headers=headers)
                    print("\n\n\nDATA : ", data, data.text)
                    if data.status_code == 200:

                        response_data = json.loads(data.text)
                        if response_data.get('Payments')[0].get('PaymentID'):
                            payment.xero_payment_id = response_data.get('Payments')[0].get('PaymentID')
                            _logger.info(_("(CREATE) - Exported successfully to XERO"))
                    elif data.status_code == 401:
                        raise ValidationError(
                            "Time Out.\nPlease Check Your Connection or error in application or refresh token..!!")
                    elif data.status_code == 400:
                        logs = self.env['xero.error.log'].create({
                            'transaction': 'Payment Export',
                            'xero_error_response': data.text,
                            'error_date': fields.datetime.now(),
                            'record_id': payment,
                        })
                        self._cr.commit()

                        response_data = json.loads(data.text)
                        if response_data:
                            if response_data.get('Elements'):
                                for element in response_data.get('Elements'):
                                    if element.get('ValidationErrors'):
                                        for err in element.get('ValidationErrors'):
                                            raise ValidationError(
                                                '(Payment) Xero Exception : ' + err.get(
                                                    'Message'))
                            elif response_data.get('Message'):
                                raise ValidationError(
                                    '(Payment) Xero Exception : ' + response_data.get(
                                        'Message'))
                            else:
                                raise ValidationError(
                                    '(Payment) Xero Exception : please check xero logs in odoo for more details')


                else:
                    raise ValidationError("Please Check Your Connection or error in application or refresh token..!!")

        success_form = self.env.ref('pragmatic_odoo_xero_connector.export_successfull_view', False)
        return {
            'name': _('Notification'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'res.company.message',
            'views': [(success_form.id, 'form')],
            'view_id': success_form.id,
            'target': 'new',
        }

    @api.model
    def exportPayment_cron(self):
        payment_records = self.env['account.payment'].search([('xero_payment_id', '=', False)])
        for payment in payment_records:
            payment.create_payment_in_xero()