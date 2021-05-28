from odoo import models, fields, api,_
from odoo.exceptions import ValidationError
import requests
import json
import logging
import base64
_logger = logging.getLogger(__name__)

class ProductProduct(models.Model):
    _inherit = "product.product"

    xero_product_id = fields.Char('Xero ItemID', copy=False)

    def remove_html_tags(self,description):
        """Remove html tags from a string"""
        import re
        clean = re.compile('<.*?>')
        return re.sub(clean, '', description)


    @api.model
    def get_xero_product_ref(self, product):
        if product.xero_product_id:
            return product.xero_product_id
        else:
            # print("product : ", product)
            self.create_single_product_in_xero(product)
            if product.xero_product_id:
                return product.xero_product_id

    @api.model
    def prepare_product_export_dict(self):
        """Create Dictionary to export to XERO"""
        vals = {}

        xero_config = self.env['res.users'].search([('id', '=', self._uid)], limit=1).company_id

        if self.description_sale:
            description = self.remove_html_tags(self.description_sale)
        else:
            description = 'NA'

        if self.type == 'product':
            qty=self.qty_available
        else:
            qty=0

        if self.description_purchase:
            description_p = self.remove_html_tags(self.description_purchase)
        else:
            description_p = 'NA'

        if self.standard_price:
            standard_price = self.standard_price
        else:
            standard_price = 0

        if self.list_price:
            list_price = self.list_price
        else:
            list_price = 0

        if self.property_account_expense_id:
            if self.property_account_expense_id.xero_account_id:

                if self.type == 'product' and not xero_config.non_tracked_item:
                    purchase_dict = {
                        "UnitPrice": standard_price,
                        "COGSAccountCode": self.property_account_expense_id.code,
                    }
                else:

                    purchase_dict = {
                        "UnitPrice": standard_price,
                        "AccountCode": self.property_account_expense_id.code,
                    }
            else:
                self.env['account.account'].create_account_ref_in_xero(self.property_account_expense_id)
                if self.type == 'product' and not xero_config.non_tracked_item:
                    purchase_dict = {
                        "UnitPrice": standard_price,
                        "COGSAccountCode": self.property_account_expense_id.code,
                    }
                else:

                    purchase_dict = {
                        "UnitPrice": standard_price,
                        "AccountCode": self.property_account_expense_id.code,
                    }
        else:
            if self.categ_id.property_account_expense_categ_id.xero_account_id:
                # print("1 ------------> ", self.categ_id.property_account_expense_categ_id.xero_account_id)

                if self.type == 'product' and not xero_config.non_tracked_item:
                    purchase_dict = {
                        "UnitPrice": standard_price,
                        "COGSAccountCode": self.categ_id.property_account_expense_categ_id.code,
                    }
                else:

                    purchase_dict = {
                        "UnitPrice": standard_price,
                        "AccountCode": self.categ_id.property_account_expense_categ_id.code,
                    }
            else:

                self.env['account.account'].create_account_ref_in_xero(self.categ_id.property_account_expense_categ_id)
                if self.type == 'product' and not xero_config.non_tracked_item:
                    purchase_dict = {
                        "UnitPrice": standard_price,
                        "COGSAccountCode": self.categ_id.property_account_expense_categ_id.code,
                    }
                else:

                    purchase_dict = {
                        "UnitPrice": standard_price,
                        "AccountCode": self.categ_id.property_account_expense_categ_id.code,
                    }

        if self.property_account_income_id:
            if self.property_account_income_id.xero_account_id:
                sales_dict = {
                    "UnitPrice": list_price,
                    "AccountCode": self.property_account_income_id.code,
                }
            else:
                self.env['account.account'].create_account_ref_in_xero(self.property_account_income_id)
                sales_dict = {
                    "UnitPrice": list_price,
                    "AccountCode": self.property_account_income_id.code,
                }
        else:
            if self.categ_id.property_account_income_categ_id.xero_account_id:
                sales_dict = {
                    "UnitPrice": list_price,
                    "AccountCode": self.categ_id.property_account_income_categ_id.code,
                }
            else:
                self.env['account.account'].create_account_ref_in_xero(self.categ_id.property_account_income_categ_id)

                sales_dict = {
                    "UnitPrice": list_price,
                    "AccountCode": self.categ_id.property_account_income_categ_id.code,
                }

        #  DICTIONARY FOR PRODUCT WITHOUT ACCOUNTS
        if self.default_code:
            vals.update({
                "Code": self.default_code,
                "Name": self.name[:50],
                "Description": description,
                "PurchaseDescription": description_p,
                "PurchaseDetails": {
                    "UnitPrice": standard_price,

                },
                "SalesDetails": {
                    "UnitPrice": list_price,
                }
            })
        else:
            raise ValidationError('Please enter Internal Reference for ' + self.name)

        #   DICTIONARY FOR PRODUCT WITH INCOME AND EXPENSE ACCOUNTS
        if self.name:
            # purchase_dict.update(tax_id_purchase)
            # sales_dict.update(tax_id)
            vals.update({
                "Code": self.default_code,
                "Name": self.name[:50],
                "Description": description,
                # # "IsTrackedAsInventory":IsTrackedAsInventory,
                "PurchaseDescription": description_p,

                "PurchaseDetails": purchase_dict,
                "SalesDetails": sales_dict,
            })

            if self.type =='product':
                if not xero_config.non_tracked_item:
                    vals.update({
                        'InventoryAssetAccountCode': self.categ_id.xero_inventory_account.code,
                        'IsTrackedAsInventory': True,
                    })


            # print("DICT P : ------> ",purchase_dict.update(tax_id_purchase))
        # print("DICT  : ------> ", vals)
        return vals

    @api.model
    def create_product_in_xero(self):
        """export accounts to XERO"""
        xero_config = self.env['res.users'].search([('id', '=', self._uid)], limit=1).company_id
        if self._context.get('active_ids'):
            product = self.browse(self._context.get('active_ids'))
        else:
            product = self

        for p in product:
            self.create_main_product_in_xero(p, xero_config)
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
    def create_single_product_in_xero(self, product):
        xero_config = self.env['res.users'].search([('id', '=', self._uid)], limit=1).company_id

        # product_item = self.env['product.product'].search([('id', '=', product.id)])
        # if product.product_tmpl_id:
        #     print("hey", product.product_tmpl_id)
        #     self.create_main_product_in_xero(product, xero_config)
        # else:
        #     print("hello", product.product_tmpl_id, product)
        self.create_main_product_in_xero(product, xero_config)

    @api.model
    def create_main_product_in_xero(self, p, xero_config):
        # print("--------------=====================------------ ", p)
        vals = p.prepare_product_export_dict()
        parsed_dict = json.dumps(vals)
        # print("PARSED DICT : ", parsed_dict, type(parsed_dict))
        if xero_config.xero_oauth_token:
            token = xero_config.xero_oauth_token
        headers = self.get_head()

        if token:
            protected_url = 'https://api.xero.com/api.xro/2.0/Items'

            data = requests.request('POST', url=protected_url, headers=headers, data=parsed_dict)
            _logger.info("\n\nPRODUCT DATA : %s %s % s", p, data, data.text)

            if data.status_code == 200:

                response_data = json.loads(data.text)
                if response_data.get('Items'):
                    if response_data.get('Items')[0].get('ItemID'):
                        p.xero_product_id = response_data.get('Items')[0].get('ItemID')
                        self._cr.commit()
                        _logger.info("Exported Product successfully to XERO : %s ",p)

            elif data.status_code == 400:
                logs = self.env['xero.error.log'].create({
                    'transaction': 'Product Export',
                    'xero_error_response': data.text,
                    'error_date': fields.datetime.now(),
                    'record_id': p,
                })
                self._cr.commit()
                response_data = json.loads(data.text)
                # print("RESPONSE DATA : ", response_data)
                if response_data:
                    if response_data.get('Elements'):
                        for element in response_data.get('Elements'):
                            if element.get('ValidationErrors'):
                                for err in element.get('ValidationErrors'):
                                    raise ValidationError('(Products) Xero Exception : ' + err.get('Message'))
                    elif response_data.get('Message'):
                            raise ValidationError(
                                '(Products) Xero Exception : ' + response_data.get('Message'))
                    else:
                        raise ValidationError('(Products) Xero Exception : please check xero logs in odoo for more details')
            elif data.status_code == 401:
                raise ValidationError("Time Out.\nPlease Check Your Connection or error in application or refresh token..!!")
        else:
            raise ValidationError("Please Check Your Connection or error in application or refresh token..!!")


class product_template(models.Model):
    _inherit = "product.template"

    xero_product_id = fields.Char('Xero ItemID', related='product_variant_ids.xero_product_id', copy=False)

class product_category(models.Model):
    _inherit = "product.category"

    xero_inventory_account = fields.Many2one('account.account', string="XERO Inventory Account",copy=False)
