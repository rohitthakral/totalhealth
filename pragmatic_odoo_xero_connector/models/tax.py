from odoo import models, fields, api,_
from odoo.exceptions import ValidationError
import requests
import json
import logging
import base64
_logger = logging.getLogger(__name__)

class Tax(models.Model):
    _inherit = 'account.tax'

    # xero_tax_id = fields.Char(string="Xero Tax Id")
    CanApplyToEquity = fields.Boolean(string="Can Apply To Equity",default=False)
    CanApplyToLiabilities = fields.Boolean(string="Can Apply To Liabilities",default=False)
    CanApplyToRevenue = fields.Boolean(string="Can Apply To Revenue ",default=False)
    CanApplyToExpenses = fields.Boolean(string="Can Apply To Expenses",default=False)
    CanApplyToAssets = fields.Boolean(string="Can Apply To Assets",default=False)

    xero_tax_type_id = fields.Char(string="Xero TaxType" ,copy=False)
    xero_record_taxtype = fields.Char(string="Xero RecordTaxType",copy=False)
    # xero_tax_status = fields.Char(string="Xero Tax Status")

    @api.model
    def get_xero_tax_ref(self, tax):
        # print("TAX ID : ",tax)
        xero_config = self.env['res.users'].search([('id', '=', self._uid)], limit=1).company_id

        if tax.xero_tax_type_id:
            # print("TAX TYPE : -------------> ",tax.xero_tax_type_id)
            return tax
        else:
            # print("im here")
            self.create_main_tax_in_xero(tax,xero_config)
            if tax.xero_tax_type_id:
                return tax
    # @api.model
    # def create_tax_ref_in_xero(self, account_id):
    #     """export accounts to XERO"""
    #     xero_config = self.env['res.users'].search([('id', '=', self._uid)], limit=1).company_id
    #     # if self._context.get('active_ids'):
    #     #     account = self.browse(self._context.get('active_ids'))
    #     # else:
    #     account = account_id
    #     self.create_account_main(account, xero_config)

    @api.model
    def prepare_tax_export_dict(self):
        """Create Dictionary to export to XERO"""
        vals = {}
        ApplyToEquity = 'false'
        ApplyToLiabilities = 'false'
        ApplyToExpenses = 'false'
        ApplyToRevenue = 'false'
        ApplyToAssets = 'false'
        company = self.env['res.users'].search([('id', '=', self._uid)], limit=1).company_id

        if self.name:
            # print("name : ",self.name)
            if self.CanApplyToEquity:
                if self.CanApplyToEquity == True:
                        ApplyToEquity = 'true'
                else:
                        ApplyToEquity = 'false'

            if self.CanApplyToLiabilities:
                if self.CanApplyToLiabilities == True:
                        ApplyToLiabilities = 'true'
                else:
                        ApplyToLiabilities = 'false'

            if self.CanApplyToRevenue:
                if self.CanApplyToRevenue == True:
                        ApplyToRevenue = 'true'
                else:
                        ApplyToRevenue = 'false'

            if self.CanApplyToExpenses:
                # print("\nCanApplyToExpenses --------------> ",self.CanApplyToExpenses)
                if self.CanApplyToExpenses == True:
                        ApplyToExpenses = 'true'
                else:
                        ApplyToExpenses = 'false'

            if self.CanApplyToAssets:
                if self.CanApplyToAssets == True:
                        ApplyToAssets = 'true'
                else:
                        ApplyToAssets = 'false'


            component_list = []
            for i in self.children_tax_ids:
                tax = self.env['account.tax'].search([('id','=',i.id),('company_id','=',company.id)])
                if tax:
                    tax_name = tax.name
                    tax_amount = tax.amount

                    component_dict = {
                        "Name":tax_name,
                        "Rate":tax_amount,
                        "IsCompound": "false",
                        "IsNonRecoverable": "false"
                    }
                    component_list.append(component_dict)
            # print("TAX LIST : ",component_list)

            if self.amount_type:
                if self.amount_type == 'percent':

                    vals.update({
                        "Name": self.name,
                        "TaxComponents": [
                            {
                                "Name": self.name,
                                "Rate": self.amount,
                                "IsCompound": "false",
                                "IsNonRecoverable": "false"
                            }
                        ],
                        "CanApplyToEquity": ApplyToEquity,
                        "CanApplyToLiabilities": ApplyToLiabilities,
                        "CanApplyToRevenue": ApplyToRevenue,
                        "CanApplyToExpenses": ApplyToExpenses,
                        "CanApplyToAssets": ApplyToAssets,
                    })
                elif self.amount_type == 'group':
                    # print("---------------> ",self.amount_type)
                    vals.update({
                        "Name": self.name,
                        "TaxComponents": component_list,
                        "CanApplyToEquity": ApplyToEquity,
                        "CanApplyToLiabilities": ApplyToLiabilities,
                        "CanApplyToRevenue": ApplyToRevenue,
                        "CanApplyToExpenses": ApplyToExpenses,
                        "CanApplyToAssets": ApplyToAssets,
                    })
        # print("VALS : ",vals)
        return vals

    @api.model
    def create_tax_in_xero(self):
        """export accounts to XERO"""
        xero_config = self.env['res.users'].search([('id', '=', self._uid)], limit=1).company_id
        if self._context.get('active_ids'):
            tax = self.browse(self._context.get('active_ids'))
        else:
            tax = self

        for t in tax:
            self.create_main_tax_in_xero(t,xero_config)
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

    def get_head(self):
        xero_config = self.env['res.users'].search([('id', '=', self._uid)], limit=1).company_id
        client_id = xero_config.xero_client_id
        client_secret = xero_config.xero_client_secret

        data = client_id + ":" + client_secret
        encodedBytes = base64.b64encode(data.encode("utf-8"))
        encodedStr = str(encodedBytes, "utf-8")
        headers = {
            'Authorization': "Bearer " + str(xero_config.xero_oauth_token),
            'Xero-tenant-id': xero_config.xero_tenant_id,
            'Accept': 'application/json'

        }
        return headers

    @api.model
    def create_main_tax_in_xero(self,t,xero_config):

        vals = t.prepare_tax_export_dict()
        # print("--------------> ",vals)
        if (xero_config.xero_country_name == 'United Kingdom') or (xero_config.xero_country_name == 'New Zealand') or (xero_config.xero_country_name == 'Australia'):
            # if not self.xero_tax_type_id:
                    if t.xero_record_taxtype:
                        if t.xero_record_taxtype == 'REVERSECHARGES':
                            raise ValidationError(' The Tax with this ReportTaxType is not yet available for create and update via the API. They are returned on GET requests only')
                        if t.xero_record_taxtype == 'NONE':
                            raise ValidationError(' The Tax with this ReportTaxType is used for system tax rates and only returned on GET requests')
                        if t.xero_record_taxtype == 'GSTONIMPORTS':
                            raise ValidationError(' The Tax with this ReportTaxType is used for system tax rates and only returned on GET requests')

                        vals.update({
                            "ReportTaxType": t.xero_record_taxtype
                        })
                    else:
                        # print("\nGGGGGGGGGGGGGGGGGG",t.type_tax_use)
                        if t.type_tax_use:
                            # print("----------------")
                            if t.type_tax_use == 'sale':
                                vals.update({
                                    "ReportTaxType": 'OUTPUT'
                                })
                            elif t.type_tax_use == 'purchase':
                                vals.update({
                                    "ReportTaxType" : 'INPUT'
                                })

        parsed_dict = json.dumps(vals)
        # print("\n\n--------------> ",parsed_dict)

        if xero_config.xero_oauth_token:
            token = xero_config.xero_oauth_token

        headers = self.get_head()

        if token:
            client_key = xero_config.xero_client_id
            client_secret = xero_config.xero_client_secret
            resource_owner_key = xero_config.xero_oauth_token
            resource_owner_secret = xero_config.xero_oauth_token_secret

            protected_url = 'https://api.xero.com/api.xro/2.0/TaxRates'

            data = requests.request('POST', url=protected_url, data=parsed_dict, headers=headers)

            # print("DATA : ",data,data.text)
            if data.status_code == 200:

                response_data = json.loads(data.text)
                # if response_data.get('Response'):
                if response_data.get('TaxRates'):
                    t.xero_record_taxtype = response_data.get('TaxRates')[0].get('ReportTaxType')
                    t.xero_tax_type_id = response_data.get('TaxRates')[0].get('TaxType')
                    self._cr.commit()
                _logger.info(_("Exported successfully to XERO"))
            elif data.status_code == 400:
                logs = self.env['xero.error.log'].create({
                    'transaction': 'Tax Export',
                    'xero_error_response': data.text,
                    'error_date': fields.datetime.now(),
                    'record_id': t,
                })
                self._cr.commit()

                response_data = json.loads(data.text)
                if response_data:
                    if response_data.get('Elements'):
                        for element in response_data.get('Elements'):
                            if element.get('ValidationErrors'):
                                for err in element.get('ValidationErrors'):
                                    raise ValidationError('(Tax) Xero Exception : ' + err.get('Message'))
                    elif response_data.get('Message'):
                        raise ValidationError(
                            '(Tax) Xero Exception : ' + response_data.get('Message'))
                    else:
                        raise ValidationError(
                            '(Tax) Xero Exception : please check xero logs in odoo for more details')

            elif data.status_code == 401:
                raise ValidationError("Time Out.\nPlease Check Your Connection or error in application or refresh token..!!")
        else:
            raise ValidationError("Time Out.\nPlease Check Your Connection or error in application or refresh token..!!")


# class AccountTaxType(models.Model):
#     _name = 'xero.account.tax'
#     _rec_name = 'xero_tax_type'
#
#     xero_tax_type = fields.Char(string='Name')
#
