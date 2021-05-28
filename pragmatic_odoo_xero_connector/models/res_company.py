import base64
import json
import logging
import math
from datetime import date, datetime
import datetime
from math import ceil, floor

import requests
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError

_logger = logging.getLogger(__name__)


class ResCompany(models.Model):
    _inherit = "res.company"

    # Company level XERO Configuration fields
    xero_client_id = fields.Char('Client Id', copy=False,
                                 help="The Client Id that you obtain from the developer dashboard.")
    xero_client_secret = fields.Char('Client Secret', copy=False,
                                     help="The Client Secret that you obtain from the developer dashboard.")
    xero_user_id = fields.Char('User Id', copy=False,
                               help="The Email id that you use to login to your odoo account")
    xero_password = fields.Char('Password', copy=False,
                                help="The Password that you use to login to your odoo account")
    xero_auth_base_url = fields.Char('Authorization URL',
                                     default="https://login.xero.com/identity/connect/authorize   ",
                                     help="User authenticate uri")
    xero_access_token_url = fields.Char('Access Token URL',
                                        default="https://identity.xero.com/connect/token",
                                        help="One of the redirect URIs listed for this project in the developer dashboard used to get the verifier code.")
    chrome_executable_path = fields.Char('Executable Path', copy=False, help='Add Executable path of your chromedriver')
    xero_tenant_id_url = fields.Char('Tenant ID URL', default="https://api.xero.com/connections",
                                     help="Check the full set of tenants you've been authorized to access.")
    xero_redirect_url = fields.Char('Redirect URL', help="http://localhost:8069/get_auth_code")

    # used for api calling, generated during authorization process.
    # xero_verifier_code = fields.Char('Verifier Code',help="The token that must be used to access the Xero API. Access token expires in 1800 seconds.")
    xero_access_token = fields.Char('Access Token')
    xero_oauth_token = fields.Char('Oauth Token', help="OAuth Token")
    xero_oauth_token_secret = fields.Char('Oauth Token Secret')
    xero_company_id = fields.Char('Xero Company ID')
    xero_country_name = fields.Char('Xero Country Name')
    x_invoice_date = fields.Date(string='Import Invoice From', copy=False)
    x_purchaseorder_date = fields.Date(string='Import PurchaseOrder From', copy=False)
    x_salesorder_date = fields.Date(string='Import SalesOrder From', copy=False)

    x_journal_date = fields.Date(string='Import Journal From', copy=False)

    x_credit_note_date = fields.Date(string='Import Credit Note From', copy=False)
    x_payments_date = fields.Date(string='Import Payments From', copy=False)
    x_prepayments_date = fields.Date(string='Import Prepayments From', copy=False)
    x_overpayments_date = fields.Date(string='Import Overpayments From', copy=False)

    xero_company_name = fields.Char('Xero Company Name/Organisation', help="Add name of your organisation.")
    # log_ids = fields.One2many('xero.log', 'company_id', ondelete="cascade", string='Logs')
    xero_tenant_id = fields.Char('Tenant Id')
    refresh_token_xero = fields.Char('Refresh Token')
    skip_emails = fields.Char('Skip the following emails',
                              help='This field is used to skip the contacts having following email ids. \n Note : Separate the email ids with comma.')
    default_account = fields.Many2one('account.account',
                                      help='This Account will be attached to the invoice lines which does not contain quantity,unit price and account',
                                      string='Default Account')
    overpayment_journal = fields.Many2one('account.journal', help='Overpayment Journal')
    prepayment_journal = fields.Many2one('account.journal', help='Prepayment Journal')
    xero_tenant_name = fields.Char('Xero Company', copy=False)
    manual_journal = fields.Many2one('account.journal', help="Manual Journal" )

    export_invoice_without_product = fields.Boolean('Export Invoices with description only', copy=False)
    export_bill_without_product = fields.Boolean('Export Bills with description only', copy=False)
    invoice_status = fields.Selection([('draft', 'DRAFT'), ('authorised', 'AUTHORISED')], 'Invoice/Bill Status',
                                      default='authorised')
    non_tracked_item = fields.Boolean('Export Stockable Product as Non Tracked Items', copy=False)

    def login(self):
        if not self.id == self.env.user.company_id.id:
            raise ValidationError(
                "Selected Company Does not match current active company. Please change selected company or active company")

        if not self.xero_client_id:
            raise ValidationError("Please Enter Client ID")
        if not self.xero_client_secret:
            raise ValidationError("Please Enter Client Secret")

        requests_url = 'https://login.xero.com/identity/connect/authorize?' + 'response_type=code&' + 'client_id=' + self.xero_client_id + '&redirect_uri=' + self.xero_redirect_url + '&scope= openid profile email accounting.transactions accounting.settings accounting.settings.read accounting.contacts payroll.employees  offline_access'

        return {
            "type": "ir.actions.act_url",
            "url": requests_url,
            "target": "new"
        }

    def refresh_token(self):

        xero_id = self.env['res.users'].search([('id', '=', self._uid)], limit=1).company_id

        if not xero_id:
            user_obj = self.env['res.users'].browse(self._uid)
            raise ValidationError('Company not found for User Name : ' + user_obj.name + 'and User Id : ' + self._uid)

        if not xero_id.id == self.env.user.company_id.id:
            raise ValidationError(
                "Selected Company Does not match current active company. Please change selected company or active company")

        client_id = xero_id.xero_client_id
        client_secret = xero_id.xero_client_secret
        url = 'https://identity.xero.com/connect/token'
        data = client_id + ":" + client_secret

        encodedBytes = base64.b64encode(data.encode("utf-8"))
        encodedStr = str(encodedBytes, "utf-8")

        headers = {
            'Authorization': "Basic " + encodedStr,
            'Content-Type': 'application/x-www-form-urlencoded'
        }

        data_token = {
            'grant_type': 'refresh_token',
            'refresh_token': xero_id.refresh_token_xero,
        }
        access_token = requests.post(url, data=data_token, headers=headers)
        parsed_token_response = json.loads(access_token.text)

        if parsed_token_response:
            xero_id.refresh_token_xero = parsed_token_response.get('refresh_token')
            xero_id.xero_oauth_token = parsed_token_response.get('access_token')

            if access_token.status_code == 200:
                _logger.info(_("(UPDATE) - Token generated successfully"))

            elif access_token.status_code == 401:
                _logger.info(_("Time Out.\nPlease Check Your Connection or error in application or refresh token..!!"))
            elif access_token.status_code == 400:
                if parsed_token_response.get('error'):
                    raise ValidationError(parsed_token_response.get('error'))

    def get_headers(self):
        headers = {}
        headers['Authorization'] = 'Bearer ' + str(self.xero_oauth_token)
        headers['Xero-tenant-id'] = self.xero_tenant_id
        headers['Accept'] = 'application/json'

        return headers

    @api.model
    def get_data(self, url, post=0):
        data = {}

        if self.xero_oauth_token:
            headers = self.get_headers()
            protected_url = url
            # print(protected_url, headers, '|||||||||||||||||||||||||||||||||||||||||')
            if post == 0:
                data = requests.request('GET', protected_url, headers=headers)
            else:
                data = requests.request('POST', protected_url, headers=headers)

        else:
            raise UserError('Please Authenticate First With Xero.')
        return data

    def import_accounts(self):
        """IMPORT ACCOUNTS FROM XERO TO ODOO"""

        url = 'https://api.xero.com/api.xro/2.0/Accounts'

        data = self.get_data(url)
        if data:
            _logger.info("DATA RECEIVED FROM API IS {} ".format(data.text))
            self.create_account_in_odoo(data)
            self._cr.commit()
            self.import_tracking_categories()
            success_form = self.env.ref('pragmatic_odoo_xero_connector.import_successfull_view', False)
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
        elif data.status_code == 401:
            raise ValidationError('Time Out..!!\n Please check your connection or error in application.')

    @api.model
    def create_account_in_odoo(self, data):
        """Data fetched from xero is available in XML form this function converts the data from xml to dict and makes it readable"""
        if data:
            recs = []

        parsed_dict = json.loads(data.text)

        if parsed_dict.get('Accounts'):
            record = parsed_dict.get('Accounts')
            if isinstance(record, (dict,)):
                self.create_imported_accounts(record)
            else:
                for acc in parsed_dict.get('Accounts'):
                    self.create_imported_accounts(acc)
        else:
            raise ValidationError('There is no any account present in XERO.')

    @api.model
    def create_imported_accounts(self, acc):
        """Get the data and create a dictionary for account creation"""

        # ''' This will avoid duplications'''
        account_acc = self.env['account.account'].search(
            ['|', ('xero_account_id', '=', acc.get('AccountID')), ('code', '=', acc.get('Code'))])
        account_account = self.env['account.account'].search(
            [('id', 'in', account_acc.ids), ('company_id', '=', self.id)])

        dict_e = {}
        if acc.get('Code'):
            dict_e['code'] = acc.get('Code')
        if acc.get('Name'):
            dict_e['name'] = acc.get('Name')

        if acc.get('TaxType'):
            tax_type = self.env['xero.tax.type'].search([('xero_tax_type', '=', acc.get('TaxType'))])
            if tax_type:
                dict_e['xero_tax_type_for_accounts'] = tax_type.id
            else:
                self.env['xero.tax.type'].create({'xero_tax_type': acc.get('TaxType')})
                tax_type = self.env['xero.tax.type'].search([('xero_tax_type', '=', acc.get('TaxType'))])
                if tax_type:
                    dict_e['xero_tax_type_for_accounts'] = tax_type.id

        if acc.get('EnablePaymentsToAccount'):
            dict_e['enable_payments_to_account'] = True
        if acc.get('AccountID'):
            dict_e['xero_account_id'] = acc.get('AccountID')
        if acc.get('Description'):
            dict_e['xero_description'] = acc.get('Description')
        if acc.get('Type'):
            account_type_odoo = {'CURRENT': 'Current Assets',
                                 'CURRLIAB': 'Current Liabilities',
                                 'DEPRECIATN': 'Depreciation',
                                 'DIRECTCOSTS': 'Cost of Revenue',
                                 'EQUITY': 'Equity',
                                 'EXPENSE': 'Expenses',
                                 'FIXED': 'Fixed Assets',
                                 'INVENTORY': 'Current Assets',
                                 'LIABILITY': 'Non-current Liabilities',
                                 'NONCURRENT': 'Non-current Assets',
                                 'OTHERINCOME': 'Other Income',
                                 'OVERHEADS': 'Expenses',
                                 'PREPAYMENT': 'Prepayments',
                                 'REVENUE': 'Cost of Revenue',
                                 'SALES': 'Income',
                                 'TERMLIAB': 'Non-current Liabilities',
                                 }
            acc_type_odoo = self.env['account.account.type']
            if acc.get('Type') in account_type_odoo:
                user_type = acc_type_odoo.search([('name', '=', account_type_odoo.get(acc.get('Type')))])
                dict_e['user_type_id'] = user_type.id
            else:
                acc_type_odoo = self.env['account.account.type']
                user_type = acc_type_odoo.search(
                    [('name', '=', 'Expenses')])
                dict_e['user_type_id'] = user_type.id

            account_type_xero = {'CURRENT': 'Current Asset account',
                                 'CURRLIAB': 'Current Liability account',
                                 'DEPRECIATN': 'Depreciation account',
                                 'DIRECTCOSTS': 'Direct Costs account',
                                 'EQUITY': 'Equity account',
                                 'EXPENSE': 'Expense account',
                                 'FIXED': 'Fixed Asset account',
                                 'INVENTORY': 'Inventory Asset account',
                                 'LIABILITY': 'Liability account',
                                 'NONCURRENT': 'Non-current Asset account',
                                 'OTHERINCOME': 'Other Income account',
                                 'OVERHEADS': 'Overhead account',
                                 'PREPAYMENT': 'Prepayment account',
                                 'REVENUE': 'Revenue account',
                                 'SALES': 'Sale account',
                                 'TERMLIAB': 'Non-current Liability account',
                                 }
            if acc.get('Type') in account_type_xero:
                acc_type_xero = self.env['xero.account.account']
                user_type_xero = acc_type_xero.search(
                    [('xero_account_type_name', '=', account_type_xero.get(acc.get('Type')))])
                dict_e['xero_account_type'] = user_type_xero.id

        if not account_account:

            '''If Account is not present we create it'''
            _logger.info("ATTEMPTING TO CREATE RECORD WITH DATA {}".format(dict_e))
            if 'code' in dict_e and dict_e.get('code'):
                dept_create = account_account.create(dict_e)
                if dept_create:
                    _logger.info(_("Account Created Sucessfully..!!"))
                else:
                    _logger.info(_("Account Not Created..!!"))
                    raise ValidationError(
                        'Account could not be updated \n Please check Account ' + dict_e['code'] + ' in Xero.')
            else:
                _logger.error("code key is not there in data dict for create, skipping the record.")
        else:
            _logger.info("ATTEMPTING TO UPDATE RECORD WITH DATA {}".format(dict_e))
            if 'code' in dict_e and dict_e.get('code'):
                if 'user_type_id' in dict_e:
                    del dict_e['user_type_id']
                if 'name' in dict_e:
                    del dict_e['name']
                dept_write = account_account.write(dict_e)
                if dept_write:
                    _logger.info(_("Account Updated Sucessfully..!!"))
                else:
                    _logger.info(_("Account Not Updated..!!"))
                    raise ValidationError(
                        'Account could not be updated \n Please check Account ' + dict_e['code'] + ' in Xero.')
            else:
                _logger.error("code key is not there in data dict for update, skipping the record.")

    def import_tracking_categories(self, Tracking_categ_id=None):
        """IMPORT TRECKING CATEGORIES FROM XERO TO ODOO"""

        if Tracking_categ_id is None:
            url = 'https://api.xero.com/api.xro/2.0/TrackingCategories'
        else:
            url = 'https://api.xero.com/api.xro/2.0/TrackingCategories?IDs={}'.format(Tracking_categ_id)

        data = self.get_data(url)
        # print(url, '\n\n\nGET Response For Tracking Id : ', data.text)
        group_flag = 0
        if data.status_code == 200:
            parsed_dict = json.loads(data.text)
            if parsed_dict.get('TrackingCategories'):
                account_id = None
                for categ in parsed_dict.get('TrackingCategories'):
                    _logger.info('\n\nPrepearing Import of Analytic Account Group : %s'%categ.get('Name') )
                    if categ.get('TrackingCategoryID'):
                        group_id = self.env['account.analytic.group'].search([('xero_tracking_id', '=', categ.get('TrackingCategoryID'))])

                    if not group_id:

                        group = {}
                        account = {}

                        if categ.get('Name'):
                            group.update({
                                'name': categ.get('Name'),
                                'description': categ.get('Name'),
                                'xero_tracking_id': categ.get('TrackingCategoryID')
                            })
                            group_id = self.env['account.analytic.group'].create(group)
                            self._cr.commit()
                        account_id = None
                        _logger.info('\n\n Group Dict : %s \n\n'%group)
                        if group_id:
                            if categ.get('Options'):
                                options = categ.get('Options')
                                for option in options:
                                    if option.get('Name'):
                                        account.update({
                                            'name': option.get('Name'),
                                            'xero_tracking_opt_id': option.get('TrackingOptionID'),
                                            'group_id': group_id.id
                                        })
                                        account_id = self.env['account.analytic.account'].create(account)
                                        self._cr.commit()
                                        _logger.info('\n\n Group Account Dict : %s \n\n' % account)

                            else:
                                _logger.info('No Options available for %s' % categ.get('Name'))

                        if account_id or group_id:
                            group_flag += 1
                            _logger.info(' %s Successfully Imported' % categ.get('Name'))

                    else:
                        _logger.info('Category %s already imported '%categ.get('Name'))

                if group_flag != 0:
                    return account_id
                else:
                    _logger.info('No any Record Import...')

        elif data.status_code == 401:
            raise ValidationError('Time Out..!!\n Please check your connection or error in application.')

    def create_categ_in_odoo(self, categ, group_flag=0):
        # print('\n\n ______________________________________Category Line : \n\n', categ)
        _logger.info('\n\nPrepearing Import of Analytic Account Group : %s' % categ.get('Name'))

        group_id = None

        if categ.get('TrackingCategoryID'):
            group_id = self.env['account.analytic.group'].search(
                [('xero_tracking_id', '=', categ.get('TrackingCategoryID'))])
        account_id = None
        group = {}
        account = {}

        url = " https://api.xero.com/api.xro/2.0/TrackingCategories/{}".format(categ.get('TrackingCategoryID'))
        data = self.get_data(url)
        status = False
        ChildOptions = None
        if data.status_code == 200:
            parsed_dict = json.loads(data.text)
            # print('parsed Dict :++++++++++++++++++ \n\n', parsed_dict)
            catgories = parsed_dict.get('TrackingCategories')
            if catgories[0].get('Status') == 'ACTIVE':
               status = True
            ChildOptions = catgories[0].get('Options')

        if not group_id:
            if categ.get('Name'):
                group.update({
                    'name': categ.get('Name'),
                    'is_active': status,
                    'description': categ.get('Name'),
                    'xero_tracking_id': categ.get('TrackingCategoryID')
                })
                group_id = self.env['account.analytic.group'].create(group)
                self._cr.commit()

            _logger.info('\n\n Group Dict : %s \n\n' % group)

        if group_id:
            if categ.get('TrackingOptionID'):
                for option in ChildOptions:
                    if option.get('TrackingOptionID') == categ.get('TrackingOptionID'):
                        if option.get('Status') == 'ACTIVE':
                            isActive = True
                        else:
                            isActive = False

                        account_id = self.env['account.analytic.account'].search([('xero_tracking_opt_id', '=', categ.get('TrackingOptionID'))])
                        if not account_id:
                            account.update({
                                'name': categ.get('Option'),
                                'is_active': isActive,
                                'xero_tracking_opt_id': categ.get('TrackingOptionID'),
                                'group_id': group_id.id
                            })
                            account_id = self.env['account.analytic.account'].create(account)
                            self._cr.commit()
                            _logger.info('\n\n Group Account Dict : %s \n\n' % account)
                        else:
                            _logger.info('\n\n Account Already Exists : %s \n\n' % categ.get('Option'))
            else:
               _logger.info('No Options available for %s' % categ.get('Name'))

            if account_id or group_id:
                _logger.info(' %s Successfully Imported' % categ.get('Name'))
                return account_id

        else:
            _logger.info('Category %s already imported ' % categ.get('Name'))


    def import_tax(self):
        """IMPORT TAX FROM XERO TO ODOO"""
        url = 'https://api.xero.com/api.xro/2.0/TaxRates'
        data = self.get_data(url)
        if data:
            recs = []

            parsed_dict = json.loads(data.text)
            # print("============", parsed_dict)

            if parsed_dict.get('TaxRates'):

                xero_id = self.env['res.users'].search([('id', '=', self._uid)], limit=1).company_id

                record = parsed_dict.get('TaxRates')
                if isinstance(record, (dict,)):
                    if xero_id.xero_country_name == 'United States':
                        if record.get('TaxType') != 'AVALARA':
                            self.create_imported_tax(record)
                    else:
                        self.create_imported_tax(record)
                else:
                    for acc in parsed_dict.get('TaxRates'):
                        if xero_id.xero_country_name == 'United States':
                            if acc.get('TaxType') != 'AVALARA':
                                self.create_imported_tax(acc)
                        else:
                            self.create_imported_tax(acc)

                success_form = self.env.ref('pragmatic_odoo_xero_connector.import_successfull_view', False)
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
            else:
                raise ValidationError('There is no any tax present in XERO.')

        elif data.status_code == 401:
            raise ValidationError('Time Out..!!\n Please check your connection or error in application.')

    @api.model
    def create_imported_tax(self, acc):
        # ''' This will avoid duplications'''

        _logger.info("Process Tax Rate : %s ", acc.get('Name'))

        account_tax = self.env['account.tax'].search(
            [('xero_tax_type_id', '=', acc.get('TaxType')), ('price_include', '=', False),
             ('type_tax_use', '=', 'sale'), ('company_id', '=', self.id)]) or self.env['account.tax'].search(
            [('xero_tax_type_id', '=', acc.get('TaxType')), ('price_include', '=', False),
             ('type_tax_use', '=', 'purchase'), ('company_id', '=', self.id)]) or self.env['account.tax'].search(
            [('xero_tax_type_id', '=', acc.get('TaxType')), ('price_include', '=', True),
             ('type_tax_use', '=', 'sale'), ('company_id', '=', self.id)]) or self.env['account.tax'].search(
            [('xero_tax_type_id', '=', acc.get('TaxType')), ('price_include', '=', True),
             ('type_tax_use', '=', 'purchase'), ('company_id', '=', self.id)])

        dict_t = {}
        if acc.get('TaxType'):
            dict_t['xero_tax_type_id'] = acc.get('TaxType')
        if acc.get('ReportTaxType'):
            dict_t['xero_record_taxtype'] = acc.get('ReportTaxType')
        # if acc.get('Status'):
        #     dict_t['xero_tax_status'] = acc.get('Status')
        if acc.get('Name'):
            dict_t['name'] = acc.get('Name')
        if acc.get('EffectiveRate') or acc.get('DisplayTaxRate'):
            dict_t['amount'] = acc.get('EffectiveRate') or acc.get('DisplayTaxRate')
        else:
            dict_t['amount'] = 0.0

        if acc.get('Status') == 'ACTIVE':
            if not account_tax:
                '''If tax is not present we create it'''
                list_tax = []
                if acc.get('TaxComponents'):
                    if acc.get('TaxComponents'):
                        tax_c = acc.get('TaxComponents')
                        if isinstance(tax_c, (list,)):

                            if len(tax_c) >= 1:
                                dict_t['amount_type'] = 'group'
                                list_t = []

                                for i in tax_c:
                                    _logger.info("Processing Tax Component Rate : %s ", i.get('Name'))

                                    if i.get('Name'):
                                        individual_tax = self.env['account.tax'].search(
                                            [('name', '=', i.get('Name')), ('company_id', '=', self.id)], limit=1)
                                        # print("individual_tax : ",individual_tax)
                                        if len(individual_tax) > 1:
                                            raise UserError('Recursion found for tax component' + i.get('Name') + '.')
                                        dict_l = {}

                                        if i.get('Name'):
                                            dict_l['name'] = i.get('Name')
                                            dict_l['type_tax_use'] = 'none'
                                        if i.get('Rate'):

                                            dict_l['amount'] = i.get('Rate')
                                        else:
                                            dict_l['amount'] = 0.0


                                        if not individual_tax:
                                            create_p = self.env['account.tax'].create(dict_l)
                                            if create_p:
                                                list_tax = list_t.append((4, create_p.id))
                                                dict_t['children_tax_ids'] = list_t
                                        else:
                                            create_p = individual_tax.write(dict_l)
                                            if create_p:
                                                list_tax = list_t.append((4, individual_tax.id))

                                                dict_t['children_tax_ids'] = list_t

                account_tax_name = self.env['account.tax'].search(
                    [('name', '=', acc.get('Name')), ('company_id', '=', self.id)])
                if not account_tax_name:
                    dict_t.update({'name': acc.get('Name')})
                    dict_t.update({'type_tax_use': 'sale'})
                    account_tax_create_s = self.env['account.tax'].create(dict_t)

                    if account_tax_create_s:
                        dict_t['name'] = acc.get('Name') + '(Inc)'
                        dict_t.update({'price_include': True})
                        inclusive_sale_tax_create = self.env['account.tax'].create(dict_t)

                    dict_t.update({'name': acc.get('Name')})
                    dict_t.update({'type_tax_use': 'purchase'})
                    dict_t.update({'price_include': False})
                    account_tax_create = self.env['account.tax'].create(dict_t)
                    if account_tax_create:
                        dict_t.update({'price_include': True})
                        dict_t['name'] = acc.get('Name') + '(Inc)'
                        inclusive_purchase_tax_create = self.env['account.tax'].create(dict_t)

                else:
                    account_tax_name.write(dict_t)

            else:
                list_tax = []
                if acc.get('TaxComponents'):
                    if acc.get('TaxComponents'):
                        tax_c = acc.get('TaxComponents')
                        if isinstance(tax_c, (list,)):
                            if len(tax_c) >= 1:
                                dict_t['amount_type'] = 'group'
                                list_t = []

                                for i in tax_c:
                                    _logger.info("Processing Tax Component Rate : %s ", i.get('Name'))

                                    if i.get('Name'):
                                        # print("\n\ni.get('Name') : ",i.get('Name'))
                                        individual_tax = self.env['account.tax'].search(
                                            [('name', '=', i.get('Name')), ('company_id', '=', self.id)])
                                        if len(individual_tax) > 1:
                                            raise UserError('Recursion found for tax component' + i.get('Name') + '.')
                                        dict_l = {}

                                        if i.get('Name'):
                                            dict_l['name'] = i.get('Name')
                                            dict_l['type_tax_use'] = 'none'

                                        if i.get('Rate'):
                                            dict_l['amount'] = i.get('Rate')
                                        else:
                                            dict_l['amount'] = 0.0
                                        # print("\n\nindividual_tax : ",individual_tax)
                                        if not individual_tax:

                                            create_p = self.env['account.tax'].create(dict_l)

                                            if create_p:
                                                list_tax = list_t.append((4, create_p.id))
                                                dict_t['children_tax_ids'] = list_t

                                        else:
                                            create_p = individual_tax.write(dict_l)

                                            if create_p:
                                                list_tax = list_t.append((4, individual_tax.id))
                                                dict_t['children_tax_ids'] = list_t
                account_tax_create = account_tax.write(dict_t)

                if account_tax_create:
                    _logger.info(_("Tax Updated"))

    def import_products(self):
        """IMPORT Products FROM XERO TO ODOO"""
        url = 'https://api.xero.com/api.xro/2.0/items'
        data = self.get_data(url)
        res = self.create_products(data)
        if res:
            success_form = self.env.ref('pragmatic_odoo_xero_connector.import_successfull_view', False)
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
    def fetch_the_required_product(self, prod_internal_code):
        """IMPORT THE SPECIFIC PRODUCT"""
        _logger.info("FETCHING THE REQUIRED PRODUCT")

        url = 'https://api.xero.com/api.xro/2.0/items/' + str(prod_internal_code)
        data = self.get_data(url)
        self.create_products(data)

    @api.model
    def create_products(self, data):
        if data:

            recs = []

            parsed_dict = json.loads(data.text)

            if parsed_dict.get('Items'):

                record = parsed_dict.get('Items')
                if isinstance(record, (dict,)):
                    self.create_imported_products(record)
                else:
                    for item in parsed_dict.get('Items'):
                        self.create_imported_products(item)
                return True
            else:
                raise ValidationError('There is no any product present in XERO.')
        elif data.status_code == 401:
            raise ValidationError('Time Out..!!\n Please check your connection or error in application.')

    @api.model
    def create_imported_products(self, item):

        product_exists = self.env['product.product'].search(
            ['|', ('xero_product_id', '=', item.get('ItemID')), ('default_code', '=', item.get('Code'))])
        # product_exists = self.env['product.product'].search(
        #     [('id', 'in', get_product.ids), ('company_id', '=', self.id)])

        dict_create = {'xero_product_id': item.get('ItemID')}
        if item.get('Name'):
            dict_create.update({'name': item.get('Name')})
        else:
            _logger.info("Product Name is not defined : PRODUCT CODE = %s ", item.get('Code'))

        dict_create.update({'default_code': item.get('Code')})

        if item.get('SalesDetails', False):
            if item.get('SalesDetails').get('UnitPrice', False):
                dict_create.update(
                    {'list_price': float(item.get('SalesDetails').get('UnitPrice'))})
            if item.get('SalesDetails').get('TaxType', False):
                product_tax_s = self.env['account.tax'].search(
                    [('xero_tax_type_id', '=', item.get('SalesDetails').get('TaxType')), ('type_tax_use', '=', 'sale'),
                     ('price_include', '=', False), ('company_id', '=', self.id)])
                if product_tax_s:
                    dict_create.update(
                        {'taxes_id': [(6, 0, [product_tax_s.id])]})
                else:
                    self.import_tax()
                    product_tax_s1 = self.env['account.tax'].search(
                        [('xero_tax_type_id', '=', item.get('SalesDetails').get('TaxType')),
                         ('type_tax_use', '=', 'sale'), ('price_include', '=', False), ('company_id', '=', self.id)])
                    if product_tax_s1:
                        dict_create.update(
                            {'taxes_id': [(6, 0, [product_tax_s1.id])]})

            if item.get('SalesDetails').get('AccountCode', False):
                acc_id_s = self.env['account.account'].search(
                    [('code', '=', item.get('SalesDetails').get('AccountCode')), ('company_id', '=', self.id)])
                if acc_id_s:
                    dict_create.update({'property_account_income_id': acc_id_s.id})
                else:
                    self.import_accounts()
                    acc_id_s1 = self.env['account.account'].search(
                        [('code', '=', item.get('SalesDetails').get('AccountCode')), ('company_id', '=', self.id)])
                    if acc_id_s1:
                        dict_create.update({'property_account_income_id': acc_id_s1.id})

        if item.get('PurchaseDetails', False):
            if item.get('PurchaseDetails').get('UnitPrice', False):
                dict_create.update(
                    {'standard_price': float(item.get('PurchaseDetails').get('UnitPrice'))})
            if item.get('PurchaseDetails').get('TaxType', False):
                product_tax_p = self.env['account.tax'].search(
                    [('xero_tax_type_id', '=', item.get('PurchaseDetails').get('TaxType')),
                     ('type_tax_use', '=', 'purchase'), ('price_include', '=', False), ('company_id', '=', self.id)])

                if product_tax_p:
                    dict_create.update(
                        {'supplier_taxes_id': [(6, 0, [product_tax_p.id])]})
                else:
                    self.import_tax()
                    product_tax = self.env['account.tax'].search(
                        [('xero_tax_type_id', '=', item.get('PurchaseDetails').get('TaxType')),
                         ('type_tax_use', '=', 'purchase'), ('price_include', '=', False),
                         ('company_id', '=', self.id)])
                    if product_tax:
                        dict_create.update(
                            {'supplier_taxes_id': [(6, 0, [product_tax.id])]})

            if item.get('IsTrackedAsInventory') == True:
                if item.get('PurchaseDetails').get('COGSAccountCode', False):
                    acc_id_p = self.env['account.account'].search(
                        [('code', '=', item.get('PurchaseDetails').get('COGSAccountCode')),
                         ('company_id', '=', self.id)])
                    if acc_id_p:
                        dict_create.update({'property_account_expense_id': acc_id_p.id})
                    else:
                        self.import_accounts()
                        acc_id_p1 = self.env['account.account'].search(
                            [('code', '=', item.get('PurchaseDetails').get('COGSAccountCode')),
                             ('company_id', '=', self.id)])
                        if acc_id_p1:
                            dict_create.update({'property_account_expense_id': acc_id_p1.id})
            else:
                if item.get('PurchaseDetails').get('AccountCode', False):
                    acc_id_p = self.env['account.account'].search(
                        [('code', '=', item.get('PurchaseDetails').get('AccountCode')), ('company_id', '=', self.id)])
                    if acc_id_p:
                        dict_create.update({'property_account_expense_id': acc_id_p.id})
                    else:
                        self.import_accounts()
                        acc_id_p1 = self.env['account.account'].search(
                            [('code', '=', item.get('PurchaseDetails').get('AccountCode')),
                             ('company_id', '=', self.id)])
                        if acc_id_p1:
                            dict_create.update({'property_account_expense_id': acc_id_p1.id})

        if item.get(item.get('IsPurchased')):
            dict_create.update({'sale_ok': True})
        if item.get(item.get('IsSold')):
            dict_create.update({'purchase_ok': True})

        if item.get('Description'):
            dict_create.update({'description_sale': item.get('Description')})
        if item.get('PurchaseDescription'):
            dict_create.update({'description_purchase': item.get('PurchaseDescription')})

        if item.get('IsTrackedAsInventory'):
            if item.get('IsTrackedAsInventory') == True:
                dict_create.update({'type': 'product'})

        if dict_create and not product_exists:
            dict_create.update({'company_id': self.id})
            product_id = self.env['product.product'].create(dict_create)
            _logger.info("Product Created Sucessfully..!! PRODUCT CODE = %s ", item.get('Code'))

        else:

            product_exists.write(dict_create)
            _logger.info("\nProduct Updated Sucessfully..!! PRODUCT CODE = %s ", item.get('Code'))

    def import_contact_groups(self):
        """IMPORT CONTACT GROUPS FROM XERO TO ODOO"""
        url = 'https://api.xero.com/api.xro/2.0/ContactGroups'
        data = self.get_data(url)

        if data:
            recs = []
            parsed_dict = json.loads(data.text)

            if parsed_dict.get('ContactGroups'):
                record = parsed_dict.get('ContactGroups')
                if isinstance(record, (dict,)):
                    self.create_imported_contact_groups(record)
                else:
                    for grp in parsed_dict.get('ContactGroups'):
                        self.create_imported_contact_groups(grp)
                success_form = self.env.ref('pragmatic_odoo_xero_connector.import_successfull_view', False)
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
            else:
                raise ValidationError('There is no any contact group present in XERO.')

        elif data.status_code == 401:
            raise ValidationError('Time Out..!!\n Please check your connection or error in application.')

    @api.model
    def create_imported_contact_groups(self, grp):
        group = self.env['res.partner.category'].search(
            [('xero_contact_group_id', '=', grp.get('ContactGroupID'))])

        dict_g = {}
        if grp.get('ContactGroupID'):
            dict_g['xero_contact_group_id'] = grp.get('ContactGroupID')

        if grp.get('Name'):
            dict_g['name'] = grp.get('Name')

        if not group:
            grp_create = group.create(dict_g)
            if grp_create:
                _logger.info(_("Group Created Sucessfully..!!"))
            else:
                _logger.info(_("Group Not Created..!!"))
                raise ValidationError('Error occurred could not create group.')
        else:
            grp_write = group.write(dict_g)
            if grp_write:
                _logger.info(_("Group Updated Sucessfully..!!"))
            else:
                _logger.info(_("Group Not Updated..!!"))
                raise ValidationError('Error occurred could not update group.')

    def import_manual_journals(self):
        """IMPORT MANUAL JOURNALS FROM XERO TO ODOO"""
        _logger.info(
            "\n\n\n<-----------------------------------MANUAL JOURNAL-------------------------------------->", )

        if not self.manual_journal:
            raise UserError("Manual journal is not defined in the configuration.")

        # for i in range(10000):
        res = self.journal_main_function()
        _logger.info("RESPONSE : %s", res)
        # if not res:
        #     break
        success_form = self.env.ref('pragmatic_odoo_xero_connector.import_successfull_view', False)
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

    def journal_main_function(self):

        if self.x_journal_date:
            date_from = datetime.datetime.strptime(str(self.x_journal_date), '%Y-%m-%d').date()
        else:
            date_from = 0

        if date_from:
            url = 'https://api.xero.com/api.xro/2.0/ManualJournals?where=Date>=DateTime(%s,%s,%s)' % (
                date_from.year, date_from.month, date_from.day)
        else:
            url = 'https://api.xero.com/api.xro/2.0/ManualJournals'

        data = self.get_data(url)
        # print('\n\n\nStatus code : ',data.status_code)
        if data.status_code == 200:
            parsed_dict = json.loads(data.text)
            ManualJournals = parsed_dict.get('ManualJournals')
            if ManualJournals:
                for Manual_Journal in ManualJournals:
                    get_data = self.get_data(
                        'https://api.xero.com/api.xro/2.0/ManualJournals/{}'.format(Manual_Journal.get('ManualJournalID')))
                    if get_data:
                        parsed_dict2 = json.loads(get_data.text)
                        _logger.info(_('Header : \n\n\n\nManual Journals From Xero : %s\n\n\n\n' % parsed_dict2))
                        for rec in parsed_dict2.get('ManualJournals'):
                            self.create_journal_entry(rec)
                    else:
                        _logger.info('No Response From XERO .......')
                self.x_journal_date = datetime.datetime.today().strftime('%Y-%m-%d')
        elif data.status_code == 400:
            self._cr.commit()
            self.show_error_message(data)

        elif data.status_code == 401:
            raise ValidationError(
                "Time Out.\nPlease Check Your Connection or error in application or refresh token..!!")
        return True

    def create_journal_entry(self, rec):

        journal_entry = {}
        if rec.get('ManualJournals'):
            _logger.info("PROCESSING Manual Journal NUMBER : %s", rec.get('Narration'))
        _logger.info("PROCESSING Manual Journal ID : %s", rec.get('ManualJournalID'))

        journal_id = self.manual_journal
        journal_entry['journal_id'] = journal_id.id

        journal_object = self.env['account.move'].search([('xero_invoice_id', '=', rec.get('ManualJournalID')),
                                                              ('company_id', '=', self.id)])
        if not journal_object:
            journal_entry['move_type'] = 'entry'  # For Journal

            if rec.get('Narration'):
                journal_entry['ref'] = rec.get('Narration')

            if rec.get('ManualJournalID'):
                journal_entry['xero_invoice_id'] = rec.get('ManualJournalID')

            if rec.get('Date'):
                journal_date = self.compute_payment_date(rec.get('Date'))
                journal_date_a = journal_date.split('T')
                converted_date = datetime.datetime.strptime(journal_date_a[0], '%Y-%m-%d')
                journal_entry['date'] = converted_date

            journal_entry['line_ids'] = []

            if rec.get('LineAmountTypes'):
                if rec.get('LineAmountTypes') == "Exclusive":
                    journal_entry['tax_state'] = 'exclusive'
                if rec.get('LineAmountTypes') == "Inclusive":
                    journal_entry['tax_state'] = 'inclusive'
                if rec.get('LineAmountTypes') == "NoTax":
                    journal_entry['tax_state'] = 'no_tax'

            if rec.get('JournalLines'):
                line_rec = rec.get('JournalLines')

                # _logger.info(_('Lines: \n\n\n\nLines of Manual Journals From Xero ______________________________________________: %s\n\n\n\n' %line_rec))

                if isinstance(line_rec, (dict,)):
                    line_ids = self.create_journal_line_entries(line_rec, lineAmountType=rec.get('LineAmountTypes'))
                    if line_ids:
                        journal_entry['line_ids'].append((0, 0, line_ids))

                    if line_rec.get('TaxType') != "NONE":
                        tax_line_ids = self.create_journal_tax_lines(line_rec,lineAmountType=rec.get('LineAmountTypes'))
                        if line_rec.get('Tracking'):
                            for tracking_line in line_rec.get('Tracking'):
                                account_id = self.create_categ_in_odoo(tracking_line, group_flag=0)
                            if account_id:
                                tax_line_ids['analytic_account_id']= account_id.id

                        if tax_line_ids:
                            journal_entry['line_ids'].append((0, 0, tax_line_ids))

                else:
                    for line in line_rec:
                        # print('\n\n\n1111111111  ', line, '\n\n\n')
                        line_ids = self.create_journal_line_entries(line, lineAmountType=rec.get('LineAmountTypes'))
                        if line_ids:
                            journal_entry['line_ids'].append((0, 0, line_ids))

                        if line.get('TaxType') != "NONE":
                            # print('\n\n\n 222222222222  ',line,'\n\n\n')
                            tax_line_ids = {}
                            tax_line_ids = self.create_journal_tax_lines(line, lineAmountType=rec.get('LineAmountTypes'))
                            if tax_line_ids:
                                if line.get('Tracking'):
                                    for tracking_line in line.get('Tracking'):
                                        accnt = self.create_categ_in_odoo(tracking_line, group_flag=0)
                                    # print('\n\n\n 222222222222  ', line, tax_line_ids, '\n\n\n', accnt)
                                    if accnt:
                                        tax_line_ids['analytic_account_id'] = accnt.id

                            if tax_line_ids:
                                journal_entry['line_ids'].append((0, 0, tax_line_ids))

            if rec.get('Status') == 'POSTED':
                # if not journal_object:
                # print('\n\nDictionary :', journal_entry, '\n\n\n\n\n\n', )
                account_journal_id = self.env['account.move'].create(journal_entry)
                account_journal_id.action_post()
                self._cr.commit()
                _logger.info('%s Journal imported Successfully...' % rec.get('Narration'))
        else:
            _logger.info('%s Journal Already imported...'% rec.get('Narration'))

    def create_journal_tax_lines(self, line_rec, lineAmountType=None):

        acc_tax = self.env['account.tax'].search(
            [('xero_tax_type_id', '=', line_rec.get('TaxType')),
             ('company_id', '=', self.id)])
        acc_ids = acc_tax.mapped('children_tax_ids')


        for tax in acc_ids:
            if tax.amount:
                if lineAmountType == 'Inclusive':
                    lineAmount = abs(line_rec.get('LineAmount')) - abs(line_rec.get('TaxAmount'))
                    tax_amount = lineAmount * (tax.amount / 100)
                else:
                    tax_amount = line_rec.get('LineAmount') * (tax.amount / 100)

                tax_line_ids = {}
                tax_diff = abs(tax_amount) - abs(line_rec.get('TaxAmount'))

                if abs(tax_diff) < 0.5:
                    tax_lines = tax.mapped('invoice_repartition_line_ids')
                    for t in tax_lines:
                        if t.repartition_type == 'tax':
                            # _logger.info(_("Preparing Tax Line2 : %s" % t))
                            if t.account_id:
                                tax_line_ids = self.create_journal_line_entries(line_rec,
                                                                                account_id=t.account_id,
                                                                                is_tax=1)
                            else:
                                tax_line_ids = self.create_journal_line_entries(line_rec, is_tax=1)
                if tax_line_ids:
                    # print('\n\n\n\n Tax Line: ',tax_line_ids,' \n\n\n________________________________________________________________\n')
                    return tax_line_ids

    def create_journal_line_entries(self, line, lineAmountType=None, account_id=None, is_tax=0):

        line_ids = {}
        account_obj = self.env['account.account']

        if line.get('Tracking'):
            for tracking_line in line.get('Tracking'):
                analytic_account = self.create_categ_in_odoo(tracking_line, group_flag=0)
            if analytic_account:
                line_ids['analytic_account_id'] = analytic_account.id


        if line.get('Description'):
            line_ids['name'] = line.get('Description')
        else:
            raise ValidationError('Description missing at line level')

        if is_tax == 0:
            if lineAmountType == "Inclusive":
                if line.get('LineAmount') > 0:
                    line_ids['debit'] = abs(line.get('LineAmount')) - abs(line.get('TaxAmount'))
                else:
                    line_ids['credit'] = abs(line.get('LineAmount')) - abs(line.get('TaxAmount'))
            else:
                if line.get('LineAmount') > 0:
                    line_ids['debit'] = abs(line.get('LineAmount'))
                else:
                    line_ids['credit'] = abs(line.get('LineAmount'))
        else:
            if line.get('TaxAmount') > 0:
                line_ids['debit'] = line.get('TaxAmount')
            else:
                line_ids['credit'] = abs(line.get('TaxAmount'))

        if account_id is None:
            account_id = account_obj.search([('xero_account_id', '=', line.get('AccountID'))])

        if not account_id:
            account_id = account_obj.search([('code', '=', line.get('AccountCode'))])

        # print("\n\n\n\n\n\n\n\n\n", account_id.code, line.get('AccountCode'), "\n\n\n\n\n\n\n\n\n")

        if not account_id:
            url = 'https://api.xero.com/api.xro/2.0/Accounts/{}'.format(line.get('AccountID'))
            data = self.get_data(url)
            if data:
                self.create_account_in_odoo(data)
            account_id = account_obj.search([('xero_account_id', '=', line.get('AccountID'))])

        if account_id:
            line_ids['account_id'] = account_id.id

        # print('\n\n\n\n\n\nLine Amount:', lineAmountType, line.get('TaxAmount'), line.get('LineAmount'), '\nline_ids:',line_ids )

        return line_ids

    def import_invoice(self):
        """IMPORT INVOICE(Customer Invoice and Vendor Bills) FROM XERO TO ODOO"""
        _logger.info("\n\n\n<-----------------------------------INVOICE-------------------------------------->", )

        for i in range(10000):
            res = self.invoice_main_function(i + 1)
            _logger.info("RESPONSE : %s", res)
            if not res:
                break
        success_form = self.env.ref('pragmatic_odoo_xero_connector.import_successfull_view', False)
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
    def invoice_main_function(self, page_no):
        _logger.info("INVOICE PAGE NO : %s", page_no)

        if self.x_invoice_date:
            date_from = datetime.datetime.strptime(str(self.x_invoice_date), '%Y-%m-%d').date()
        else:
            date_from = 0

        if date_from:
            url = 'https://api.xero.com/api.xro/2.0/Invoices?page=' + str(
                page_no) + '&where=Date>=DateTime(%s,%s,%s)' % (date_from.year, date_from.month, date_from.day)
        else:
            url = 'https://api.xero.com/api.xro/2.0/Invoices?page=' + str(page_no)

        data = self.get_data(url)
        if data:
            recs = []

            parsed_dict = json.loads(data.text)
            if parsed_dict.get('Invoices'):
                record = parsed_dict.get('Invoices')
                if isinstance(record, (dict,)):
                    if not (record.get('Status') == 'DRAFT' or record.get('Status') == 'DELETED' or record.get(
                            'Status') == 'VOIDED' or record.get('Status') == 'SUBMITTED'):
                        self.create_imported_invoice(record)
                else:
                    for cust in parsed_dict.get('Invoices'):
                        if not (cust.get('Status') == 'DRAFT' or cust.get('Status') == 'DELETED' or cust.get(
                                'Status') == 'VOIDED' or cust.get('Status') == 'SUBMITTED'):
                            self.create_imported_invoice(cust)
                return True
            else:
                if page_no == 1:
                    raise ValidationError('There is no any invoice present in XERO.')
                else:
                    self.x_invoice_date = datetime.datetime.today().strftime('%Y-%m-%d')
                    return False

        elif data.status_code == 401:
            raise ValidationError(
                'Time Out..!!\n Please check your connection or error in application or refresh token.')

    @api.model
    def create_imported_invoice(self, cust):
        if cust.get('InvoiceNumber'):
            _logger.info("PROCESSING INVOICE NUMBER : %s", cust.get('InvoiceNumber'))
        _logger.info("PROCESSING INVOICE ID : %s", cust.get('InvoiceID'))

        account_invoice = self.env['account.move'].search(
            [('xero_invoice_id', '=', cust.get('InvoiceID')), ('company_id', '=', self.id)])
        if not account_invoice:
            res_partner = self.env['res.partner'].search(
                [('xero_cust_id', '=', cust.get('Contact').get('ContactID')), ('company_id', '=', self.id)], limit=1)
            if res_partner:
                self.create_customer_for_invoice(cust, res_partner)
            else:
                self.fetch_the_required_customer(cust.get('Contact').get('ContactID'))
                res_partner2 = self.env['res.partner'].search(
                    [('xero_cust_id', '=', cust.get('Contact').get('ContactID')), ('company_id', '=', self.id)],
                    limit=1)

                if res_partner2:
                    self.create_customer_for_invoice(cust, res_partner2)
        else:
            _logger.info("INVOICE OBJECT : %s", account_invoice)
            _logger.info("INVOICE STATE : %s", account_invoice.state)

            if account_invoice.state == 'posted':
                _logger.info("You cannot update a posted invoice.")
            if account_invoice.state == 'draft':
                _logger.info(
                    "Code is not available for updating invoices, please delete the particular invoice and import the invoice again.")
            if account_invoice.state == 'cancel':
                _logger.info("You cannot update a cancelled invoice.")

    @api.model
    def create_customer_for_invoice(self, cust, res_partner):

        dict_i = {}
        if cust.get('InvoiceID'):
            dict_i['partner_id'] = res_partner.id
            dict_i['xero_invoice_id'] = cust.get('InvoiceID')
            dict_i['company_id'] = self.id

        if cust.get('CurrencyCode'):
            currency = self.env['res.currency'].search([('name', '=', cust.get('CurrencyCode'))], limit=1)
            dict_i['currency_id'] = currency.id

        if cust.get('Type') == 'ACCREC':
            sale = self.env['account.journal'].search([('type', '=', 'sale')], limit=1)
            if sale:
                dict_i['journal_id'] = sale.id

        if cust.get('Type') == 'ACCPAY':
            purchase = self.env['account.journal'].search([('type', '=', 'purchase')], limit=1)
            if purchase:
                dict_i['journal_id'] = purchase.id

        if cust.get('LineAmountTypes'):
            if cust.get('LineAmountTypes') == "Exclusive":
                dict_i['tax_state'] = 'exclusive'
            if cust.get('LineAmountTypes') == "Inclusive":
                dict_i['tax_state'] = 'inclusive'
            if cust.get('LineAmountTypes') == "NoTax":
                dict_i['tax_state'] = 'no_tax'

        if cust.get('Status'):
            if (cust.get('Status') == 'AUTHORISED') or (
                    cust.get('Status') == 'PAID'):
                dict_i['state'] = 'draft'

        if cust.get('InvoiceNumber'):
            dict_i['xero_invoice_number'] = cust.get('InvoiceNumber')

        if cust.get('DueDateString'):
            dict_i['invoice_date_due'] = cust.get('DueDateString')
        if cust.get('DateString'):
            dict_i['invoice_date'] = cust.get('DateString')
        if cust.get('Type'):
            if cust.get('Type') == 'ACCREC':
                dict_i['move_type'] = 'out_invoice'
            elif cust.get('Type') == 'ACCPAY':
                dict_i['move_type'] = 'in_invoice'
        if cust.get('Reference'):
            dict_i['ref'] = cust.get('Reference')

        dict_i['invoice_line_ids'] = []

        invoice_line_vals = {}
        invoice_type = dict_i['move_type']
        tax_state = dict_i['tax_state']
        if cust.get('LineItems'):
            order_lines = cust.get('LineItems')
            if isinstance(order_lines, (dict,)):
                i = cust.get('LineItems')
                if not i.get('ItemCode'):
                    res_product = ''
                    invoice_line_vals = self.create_invoice_line(i, res_product, cust, invoice_type, tax_state)
                else:
                    res_product = self.env['product.product'].search([('default_code', '=', i.get('ItemCode'))])
                    if res_product:
                        invoice_line_vals = self.create_invoice_line(i, res_product, cust, invoice_type, tax_state)
                    else:
                        self.fetch_the_required_product(i.get('ItemCode'))
                        res_product = self.env['product.product'].search([('default_code', '=', i.get('ItemCode'))])
                        if res_product:
                            invoice_line_vals = self.create_invoice_line(i, res_product, cust, invoice_type, tax_state)
                if invoice_line_vals:
                    dict_i['invoice_line_ids'].append((0, 0, invoice_line_vals))
            else:
                for i in cust.get('LineItems'):
                    if not i.get('ItemCode'):
                        res_product = ''

                        invoice_line_vals = self.create_invoice_line(i, res_product, cust, invoice_type, tax_state)
                    else:
                        res_product = self.env['product.product'].search([('default_code', '=', i.get('ItemCode'))])
                        if res_product:
                            invoice_line_vals = self.create_invoice_line(i, res_product, cust, invoice_type, tax_state)
                        else:
                            self.fetch_the_required_product(i.get('ItemCode'))
                            res_product = self.env['product.product'].search([('default_code', '=', i.get('ItemCode'))])
                            if res_product:
                                invoice_line_vals = self.create_invoice_line(i, res_product, cust, invoice_type,
                                                                             tax_state)

                    if invoice_line_vals:
                        dict_i['invoice_line_ids'].append((0, 0, invoice_line_vals))

        _logger.info("Xero Invoice Data :----------------> %s ", cust)

        _logger.info("Invoice Dictionary :----------------> %s ", dict_i)

        invoice_obj = self.env['account.move'].create(dict_i)
        if invoice_obj:
            if invoice_obj.state == 'draft':
                invoice_obj.action_post()
            _logger.info("Invoice Object created in odoo :  %s ", invoice_obj)

            if cust.get('InvoiceNumber'):
                _logger.info("Invoice Created Successfully...!!! INV NO = %s ", cust.get('InvoiceNumber'))

    @api.model
    def create_invoice_line(self, i, res_product, cust, invoice_type, tax_state):

        dict_ol = {}

        if res_product == '':
            _logger.info("Product Not Defined.")
        else:
            dict_ol['product_id'] = res_product.id

        if i.get('LineItemID'):
            dict_ol['xero_invoice_line_id'] = i.get('LineItemID')

        if i.get('DiscountRate'):
            dict_ol['discount'] = i.get('DiscountRate')

        acc_tax = ''

        if i.get('TaxType'):
            if invoice_type == 'out_invoice':
                if tax_state == 'inclusive':
                    acc_tax = self.env['account.tax'].search(
                        [('xero_tax_type_id', '=', i.get('TaxType')), ('type_tax_use', '=', 'sale'),
                         ('price_include', '=', True), ('company_id', '=', self.id)])
                    if acc_tax:
                        dict_ol['tax_ids'] = [(6, 0, [acc_tax.id])]
                    else:
                        self.import_tax()
                        product_tax_s1 = self.env['account.tax'].search(
                            [('xero_tax_type_id', '=', i.get('TaxType')), ('type_tax_use', '=', 'sale'),
                             ('price_include', '=', True), ('company_id', '=', self.id)])
                        if product_tax_s1:
                            dict_ol['itax_ids'] = [(6, 0, [product_tax_s1.id])]
                elif tax_state == 'exclusive':

                    acc_tax = self.env['account.tax'].search(
                        [('xero_tax_type_id', '=', i.get('TaxType')), ('type_tax_use', '=', 'sale'),
                         ('price_include', '=', False), ('company_id', '=', self.id)])
                    if acc_tax:
                        dict_ol['tax_ids'] = [(6, 0, [acc_tax.id])]
                    else:
                        self.import_tax()
                        product_tax_s1 = self.env['account.tax'].search(
                            [('xero_tax_type_id', '=', i.get('TaxType')), ('type_tax_use', '=', 'sale'),
                             ('price_include', '=', False), ('company_id', '=', self.id)])
                        if product_tax_s1:
                            dict_ol['tax_ids'] = [(6, 0, [product_tax_s1.id])]
                elif tax_state == 'no_tax':
                    acc_tax = self.env['account.tax'].search(
                        [('xero_tax_type_id', '=', i.get('TaxType')), ('type_tax_use', '=', 'sale'),
                         ('price_include', '=', False), ('company_id', '=', self.id)])
                    if acc_tax:
                        dict_ol['tax_ids'] = [(6, 0, [acc_tax.id])]
                    else:
                        self.import_tax()
                        product_tax_s1 = self.env['account.tax'].search(
                            [('xero_tax_type_id', '=', i.get('TaxType')), ('type_tax_use', '=', 'sale'),
                             ('price_include', '=', False), ('company_id', '=', self.id)])
                        if product_tax_s1:
                            dict_ol['tax_ids'] = [(6, 0, [product_tax_s1.id])]

            elif invoice_type == 'in_invoice':

                if tax_state == 'inclusive':
                    acc_tax = self.env['account.tax'].search(
                        [('xero_tax_type_id', '=', i.get('TaxType')), ('type_tax_use', '=', 'purchase'),
                         ('price_include', '=', True), ('company_id', '=', self.id)])
                    if acc_tax:
                        dict_ol['tax_ids'] = [(6, 0, [acc_tax.id])]
                    else:
                        self.import_tax()
                        product_tax_s1 = self.env['account.tax'].search(
                            [('xero_tax_type_id', '=', i.get('TaxType')), ('type_tax_use', '=', 'purchase'),
                             ('price_include', '=', True), ('company_id', '=', self.id)])
                        if product_tax_s1:
                            dict_ol['tax_ids'] = [(6, 0, [product_tax_s1.id])]
                elif tax_state == 'exclusive':
                    acc_tax = self.env['account.tax'].search(
                        [('xero_tax_type_id', '=', i.get('TaxType')), ('type_tax_use', '=', 'purchase'),
                         ('price_include', '=', False), ('company_id', '=', self.id)])
                    if acc_tax:
                        dict_ol['tax_ids'] = [(6, 0, [acc_tax.id])]
                    else:
                        self.import_tax()
                        product_tax_s1 = self.env['account.tax'].search(
                            [('xero_tax_type_id', '=', i.get('TaxType')), ('type_tax_use', '=', 'purchase'),
                             ('price_include', '=', False), ('company_id', '=', self.id)])
                        if product_tax_s1:
                            dict_ol['tax_ids'] = [(6, 0, [product_tax_s1.id])]
                elif tax_state == 'no_tax':

                    acc_tax = self.env['account.tax'].search(
                        [('xero_tax_type_id', '=', i.get('TaxType')), ('type_tax_use', '=', 'purchase'),
                         ('price_include', '=', False), ('company_id', '=', self.id)])
                    if acc_tax:
                        dict_ol['tax_ids'] = [(6, 0, [acc_tax.id])]
                    else:
                        self.import_tax()
                        product_tax_s1 = self.env['account.tax'].search(
                            [('xero_tax_type_id', '=', i.get('TaxType')), ('type_tax_use', '=', 'purchase'),
                             ('price_include', '=', False), ('company_id', '=', self.id)])
                        if product_tax_s1:
                            dict_ol['tax_ids'] = [(6, 0, [product_tax_s1.id])]

        if i.get('Quantity'):
            dict_ol['quantity'] = i.get('Quantity')
        else:
            dict_ol['quantity'] = 0

        if i.get('UnitAmount'):
            dict_ol['price_unit'] = i.get('UnitAmount')

        if i.get('Description'):
            dict_ol['name'] = i.get('Description')
        else:
            dict_ol['name'] = 'NA'

        if i.get('AccountCode'):
            acc_id_s = self.env['account.account'].search(
                [('code', '=', i.get('AccountCode')), ('company_id', '=', self.id)])
            if acc_id_s:
                dict_ol['account_id'] = acc_id_s.id
            else:
                self.import_accounts()
                acc_id_s = self.env['account.account'].search(
                    [('code', '=', i.get('AccountCode')), ('company_id', '=', self.id)])
                if acc_id_s:
                    dict_ol['account_id'] = acc_id_s.id
        elif not i.get('AccountCode') and not i.get('Quantity') and not i.get('UnitAmount'):
            if not self.default_account:
                raise ValidationError('PLease Set the Default Account in Xero Configuration.')
            if self.default_account:
                dict_ol['account_id'] = self.default_account.id
                dict_ol['quantity'] = 1.0
                dict_ol['price_unit'] = 0.0
        elif not i.get('AccountCode') and not i.get('ItemCode'):
            if not self.default_account:
                raise ValidationError('PLease Set the Default Account in Xero Configuration.')

            if self.default_account:
                dict_ol['account_id'] = self.default_account.id

        tax_val = i.get('TaxType')
        if tax_val:
            if acc_tax:
                dict_ol['tax_ids'] = [(6, 0, [acc_tax.id])]
            else:
                dict_ol['tax_ids'] = [(6, 0, [])]
        else:
            dict_ol['tax_ids'] = [[6, False, []]]

        if i.get('ItemCode') and not i.get('AccountCode'):
            if invoice_type == 'out_invoice':
                if res_product:
                    if res_product.property_account_income_id:
                        dict_ol['account_id'] = res_product.property_account_income_id.id
                        _logger.info("PRODUCT has income account set")
                    else:
                        dict_ol['account_id'] = res_product.categ_id.property_account_income_categ_id.id
                        _logger.info("No Income account was set, taking from product category..")
            else:
                if res_product:
                    if res_product.property_account_expense_id:
                        dict_ol['account_id'] = res_product.property_account_expense_id.id
                        _logger.info("PRODUCT has income account set")
                    else:
                        dict_ol['account_id'] = res_product.categ_id.property_account_expense_categ_id.id
                        _logger.info("No Income account was set, taking from product category..")

        return dict_ol

    def import_sale_order(self, qo_number=False):
        """IMPORT SALE ORDER FROM XERO TO ODOO"""
        for i in range(10000):
            if self:
                res = self.so_main_function(i + 1, qo_number)
            else:
                company = self.env['res.users'].search([('id', '=', self._uid)]).company_id
                res = company.so_main_function(i + 1, qo_number)
            _logger.info("RESPONSE : %s", res)

            if not res:
                break;
        success_form = self.env.ref('pragmatic_odoo_xero_connector.import_successfull_view', False)
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
    def so_main_function(self, page_no, qo_number):
        _logger.info("SALE PAGE NO : %s", page_no)
        if self.x_salesorder_date:
            date_from = datetime.datetime.strptime(str(self.x_salesorder_date), '%Y-%m-%d').date()
        else:
            date_from = 0

        if qo_number:
            url = 'https://api.xero.com/api.xro/2.0/Quotes?QuoteNumber=%s' % (qo_number)
        elif date_from:
            url = 'https://api.xero.com/api.xro/2.0/Quotes?DateFrom=%s' % (date_from)
        else:
            url = 'https://api.xero.com/api.xro/2.0/Quotes?page=' + str(page_no)

        data = self.get_data(url)
        if data:
            recs = []

            parsed_dict = json.loads(data.text)
            if parsed_dict.get('Quotes'):
                record = parsed_dict.get('Quotes')
                if isinstance(record, (dict,)):
                    product_exist = self.check_if_product_present(record)
                    if product_exist:
                        self.create_imported_sale_order(record)
                    else:
                        if record.get('Quotes'):
                            _logger.info("SALES ORDER DOES NOT CONTAIN ANY PRODUCT. PO = %s", record.get('Quotes'))

                else:
                    for cust in parsed_dict.get('Quotes'):
                        product_exist = self.check_if_product_present(cust)
                        if product_exist:
                            self.create_imported_sale_order(cust)
                        else:
                            if cust.get('Quotes'):
                                _logger.info("SALES ORDER DOES NOT CONTAIN ANY PRODUCT. PO = %s", cust.get('Quotes'))

                # print("record:::::::::::::::::::",record)
                if self.x_salesorder_date:
                    self.x_salesorder_date = datetime.datetime.today().strftime('%Y-%m-%d')
                    return False
                return True
            else:
                if page_no == 1:
                    raise ValidationError('There is no any sale order present in XERO.')
                else:
                    self.x_salesorder_date = datetime.datetime.today().strftime('%Y-%m-%d')
                    return False

        elif data.status_code == 401:
            raise ValidationError(
                'Time Out..!!\n Please check your connection or error in application or refresh token.')

    @api.model
    def create_imported_sale_order(self, cust):
        sale_order = self.env['sale.order'].search(
            [('xero_sale_id', '=', cust.get('QuoteID')), ('company_id', '=', self.id)])

        if not sale_order:
            res_partner = self.env['res.partner'].search(
                [('xero_cust_id', '=', cust.get('Contact').get('ContactID')), ('company_id', '=', self.id)], limit=1)

            if res_partner:
                self.create_customer_for_sale_order(cust, res_partner)
            else:
                self.fetch_the_required_customer(cust.get('Contact').get('ContactID'))
                res_partner = self.env['res.partner'].search(
                    [('xero_cust_id', '=', cust.get('Contact').get('ContactID')), ('company_id', '=', self.id)],
                    limit=1)

                if res_partner:
                    self.create_customer_for_sale_order(cust, res_partner)
        else:
            res_partner = self.env['res.partner'].search(
                [('xero_cust_id', '=', cust.get('Contact').get('ContactID')), ('company_id', '=', self.id)], limit=1)
            if res_partner:
                self.update_customer_for_sale_order(cust, res_partner, sale_order)
            else:
                self.fetch_the_required_customer(cust.get('Contact').get('ContactID'))
                res_partner = self.env['res.partner'].search(
                    [('xero_cust_id', '=', cust.get('Contact').get('ContactID')), ('company_id', '=', self.id)],
                    limit=1)
                if res_partner:
                    self.update_customer_for_sale_order(cust, res_partner, sale_order)

    @api.model
    def create_customer_for_sale_order(self, cust, res_partner):
        dict_s = {}
        if cust.get('QuoteID'):
            dict_s['partner_id'] = res_partner.id
            dict_s['xero_sale_id'] = cust.get('QuoteID')

        if cust.get('LineAmountTypes'):
            if cust.get('LineAmountTypes') == "Exclusive":
                dict_s['tax_state'] = 'exclusive'
            if cust.get('LineAmountTypes') == "Inclusive":
                dict_s['tax_state'] = 'inclusive'
            if cust.get('LineAmountTypes') == "NoTax":
                dict_s['tax_state'] = 'no_tax'

        if cust.get('Status'):
            if cust.get('Status') == 'DRAFT':
                dict_s['state'] = 'draft'

            elif cust.get('Status') == 'DELETED':
                dict_s['state'] = 'cancel'
            elif cust.get('Status') == 'DECLINED':
                dict_s['state'] = 'cancel'

            elif cust.get('Status') == 'SENT':
                dict_s['state'] = 'sent'

            elif cust.get('Status') == 'ACCEPTED':
                dict_s['state'] = 'sale'
            elif cust.get('Status') == 'INVOICED':
                dict_s['state'] = 'sale'

            else:
                dict_s['state'] = 'draft'

        if cust.get('QuoteNumber'):
            dict_s['name'] = cust.get('QuoteNumber')
        if cust.get('DateString'):
            gte = cust.get('DateString')
            date1 = datetime.datetime.strptime(gte[0:10], '%Y-%m-%d')
            dict_s['date_order'] = gte[0:10]

        # if cust.get('DeliveryInstructions'):
        #     dict_s['notes'] = cust.get('DeliveryInstructions')
        if cust.get('Reference'):
            dict_s['client_order_ref'] = cust.get('Reference')

        so_obj = self.env['sale.order'].create(dict_s)
        if so_obj:
            _logger.info("Sale Order Created successfully  SO = %s ", cust.get('QuoteNumber'))
        else:
            _logger.info("Sale Order Not Created successfully  SO = %s ", cust.get('QuoteNumber'))

        if cust.get('LineItems'):
            order_lines = cust.get('LineItems')
            if isinstance(order_lines, (dict,)):
                i = cust.get('LineItems')
                res_product = self.env['product.product'].search(
                    [('default_code', '=', i.get('ItemCode'))])
                if res_product:
                    self.create_sale_order_line(i, so_obj, res_product)
                else:
                    if i.get('ItemCode'):
                        self.fetch_the_required_product(i.get('ItemCode'))
                        res_product = self.env['product.product'].search(
                            [('default_code', '=', i.get('ItemCode'))])
                        if res_product:
                            self.create_sale_order_line(i, so_obj, res_product)
                    else:
                        _logger.info('[SO ORDER LINE] Item Code Not defined.')
            else:
                for i in cust.get('LineItems'):
                    res_product = self.env['product.product'].search(
                        [('default_code', '=', i.get('ItemCode'))])
                    if res_product:
                        self.create_sale_order_line(i, so_obj, res_product)
                    else:
                        if i.get('ItemCode'):
                            self.fetch_the_required_product(i.get('ItemCode'))
                            res_product = self.env['product.product'].search(
                                [('default_code', '=', i.get('ItemCode'))])
                            if res_product:
                                self.create_sale_order_line(i, so_obj, res_product)
                        else:
                            _logger.info('[SO ORDER LINE] Item Code Not defined.')

    @api.model
    def update_customer_for_sale_order(self, cust, res_partner, sale_order):
        dict_s = {}

        if cust.get('QuoteID'):
            dict_s['partner_id'] = res_partner.id
            dict_s['xero_sale_id'] = cust.get('QuoteID')

        if cust.get('Status') == 'DRAFT':
            dict_s['state'] = 'draft'

        elif cust.get('Status') == 'DELETED':
            dict_s['state'] = 'cancel'
        elif cust.get('Status') == 'DECLINED':
            dict_s['state'] = 'cancel'

        elif cust.get('Status') == 'SENT':
            dict_s['state'] = 'sent'

        elif cust.get('Status') == 'ACCEPTED':
            dict_s['state'] = 'sale'
        elif cust.get('Status') == 'INVOICED':
            dict_s['state'] = 'sale'

        else:
            dict_s['state'] = 'draft'

        if cust.get('LineAmountTypes'):
            if cust.get('LineAmountTypes') == "Exclusive":
                dict_s['tax_state'] = 'exclusive'
            if cust.get('LineAmountTypes') == "Inclusive":
                dict_s['tax_state'] = 'inclusive'
            if cust.get('LineAmountTypes') == "NoTax":
                dict_s['tax_state'] = 'no_tax'

        if cust.get('QuoteNumber'):
            dict_s['name'] = cust.get('QuoteNumber')
        if cust.get('DateString'):
            gte = cust.get('DateString')
            date1 = datetime.datetime.strptime(gte[0:10], '%Y-%m-%d')
            dict_s['date_order'] = gte[0:10]

        if cust.get('DeliveryInstructions'):
            dict_s['notes'] = cust.get('DeliveryInstructions')
        if cust.get('Reference'):
            dict_s['client_order_ref'] = cust.get('Reference')

        s_o = sale_order.write(dict_s)
        if s_o:
            _logger.info("Sale Order Updated successfully  SO = %s ", cust.get('QuoteNumber'))
        else:
            _logger.info("Sale Order Not Updated successfully  PO = %s ", cust.get('QuoteNumber'))

        if cust.get('LineItems'):
            order_lines = cust.get('LineItems')
            if isinstance(order_lines, (dict,)):
                i = cust.get('LineItems')
                res_product = self.env['product.product'].search(
                    [('default_code', '=', i.get('ItemCode'))])
                if res_product:
                    self.update_sale_order_line(i, sale_order, res_product, cust)
                else:
                    if i.get('ItemCode'):
                        self.fetch_the_required_product(i.get('ItemCode'))
                        res_product = self.env['product.product'].search(
                            [('default_code', '=', i.get('ItemCode'))])
                        if res_product:
                            self.update_sale_order_line(i, sale_order, res_product, cust)
                    else:
                        _logger.info('[SO ORDER LINE] Item Code Not defined.')

            else:
                for i in cust.get('LineItems'):
                    res_product = self.env['product.product'].search(
                        [('default_code', '=', i.get('ItemCode'))])

                    if res_product:
                        self.update_sale_order_line(i, sale_order, res_product, cust)
                    else:
                        if i.get('ItemCode'):
                            self.fetch_the_required_product(i.get('ItemCode'))
                            res_product = self.env['product.product'].search(
                                [('default_code', '=', i.get('ItemCode'))])

                            if res_product:
                                self.update_sale_order_line(i, sale_order, res_product, cust)
                        else:
                            _logger.info('[SO ORDER LINE] Item Code Not defined.')

    @api.model
    def create_sale_order_line(self, i, so_obj, res_product):
        """  CREATES PURCHASE ORDER LINES FOR THE FIRST TIME  """

        dict_l = {}
        dict_l.clear()
        dict_l['order_id'] = so_obj.id
        dict_l['product_id'] = res_product.id

        if i.get('Quantity'):
            dict_l['product_uom_qty'] = i.get('Quantity')

        if i.get('TaxType'):
            if so_obj.tax_state == 'inclusive':
                acc_tax = self.env['account.tax'].search(
                    [('xero_tax_type_id', '=', i.get('TaxType')), ('type_tax_use', '=', 'sale'),
                     ('price_include', '=', True), ('company_id', '=', self.id)])
                if acc_tax:
                    dict_l['tax_id'] = [(6, 0, [acc_tax.id])]
                else:
                    self.import_tax()
                    product_tax_s1 = self.env['account.tax'].search(
                        [('xero_tax_type_id', '=', i.get('TaxType')), ('type_tax_use', '=', 'sale;e'),
                         ('price_include', '=', True), ('company_id', '=', self.id)])
                    if product_tax_s1:
                        dict_l['tax_id'] = [(6, 0, [product_tax_s1.id])]
            elif so_obj.tax_state == 'exclusive':
                acc_tax = self.env['account.tax'].search(
                    [('xero_tax_type_id', '=', i.get('TaxType')), ('type_tax_use', '=', 'sale'),
                     ('price_include', '=', False), ('company_id', '=', self.id)])
                if acc_tax:
                    dict_l['tax_id'] = [(6, 0, [acc_tax.id])]
                else:
                    self.import_tax()
                    product_tax_s1 = self.env['account.tax'].search(
                        [('xero_tax_type_id', '=', i.get('TaxType')), ('type_tax_use', '=', 'sale'),
                         ('price_include', '=', False), ('company_id', '=', self.id)])
                    if product_tax_s1:
                        dict_l['tax_id'] = [(6, 0, [product_tax_s1.id])]
            elif so_obj.tax_state == 'no_tax':
                acc_tax = self.env['account.tax'].search(
                    [('xero_tax_type_id', '=', i.get('TaxType')), ('type_tax_use', '=', 'sale'),
                     ('price_include', '=', False), ('company_id', '=', self.id)])
                if acc_tax:
                    dict_l['tax_id'] = [(6, 0, [acc_tax.id])]
                else:
                    self.import_tax()
                    product_tax_s1 = self.env['account.tax'].search(
                        [('xero_tax_type_id', '=', i.get('TaxType')), ('type_tax_use', '=', 'sale'),
                         ('price_include', '=', False), ('company_id', '=', self.id)])
                    if product_tax_s1:
                        dict_l['tax_id'] = [(6, 0, [product_tax_s1.id])]

        if i.get('LineItemID'):
            dict_l['xero_sale_line_id'] = i.get('LineItemID')
            # dict_l['date_planned'] = so_obj.date_order

        dict_l['product_uom'] = 1

        if i.get('UnitAmount'):
            dict_l['price_unit'] = float(i.get('UnitAmount'))
        else:
            dict_l['price_unit'] = 0.0

        if i.get('Description'):
            dict_l['name'] = i.get('Description')
        else:
            dict_l['name'] = 'NA'

        create_p = self.env['sale.order.line'].create(dict_l)
        if create_p:
            _logger.info(_(" Sale line Created successfully"))
        else:
            _logger.info(_("Sale line not Created successfully"))

    @api.model
    def update_sale_order_line(self, i, sale_order, res_product, cust):
        so_order_line = self.env['sale.order.line'].search(
            [('product_id', '=', res_product.id),
             ('order_id', '=', sale_order.id), ('company_id', '=', self.id)], limit=1)

        # if cust.get('DeliveryDateString'):
        #     xero_delivery_time = cust.get('DeliveryDateString').split("T")
        #     xero_delivery_datetime = xero_delivery_time[0] + ' ' + xero_delivery_time[1]
        #     xero_datetime = datetime.datetime.strptime(xero_delivery_datetime, '%Y-%m-%d %H:%M:%S')
        #     date_planned = xero_datetime
        # else:
        #     date_planned = purchase_order.date_order

        if so_order_line:
            quantity = 1
            taxes_id = 0
            ol_qb_id = 0

            if i.get('Quantity'):
                quantity = i.get('Quantity')

            if i.get('TaxType'):
                if sale_order.tax_state == 'inclusive':
                    acc_tax = self.env['account.tax'].search(
                        [('xero_tax_type_id', '=', i.get('TaxType')), ('type_tax_use', '=', 'sale'),
                         ('price_include', '=', True), ('company_id', '=', self.id)])
                    if acc_tax:
                        taxes_id = [(6, 0, [acc_tax.id])]
                    else:
                        self.import_tax()
                        product_tax_s1 = self.env['account.tax'].search(
                            [('xero_tax_type_id', '=', i.get('TaxType')), ('type_tax_use', '=', 'sale'),
                             ('price_include', '=', True), ('company_id', '=', self.id)])
                        if product_tax_s1:
                            taxes_id = [(6, 0, [product_tax_s1.id])]
                elif sale_order.tax_state == 'exclusive':
                    acc_tax = self.env['account.tax'].search(
                        [('xero_tax_type_id', '=', i.get('TaxType')), ('type_tax_use', '=', 'sale'),
                         ('price_include', '=', False), ('company_id', '=', self.id)])
                    if acc_tax:
                        taxes_id = [(6, 0, [acc_tax.id])]
                    else:
                        self.import_tax()
                        product_tax_s1 = self.env['account.tax'].search(
                            [('xero_tax_type_id', '=', i.get('TaxType')), ('type_tax_use', '=', 'sale'),
                             ('price_include', '=', False), ('company_id', '=', self.id)])
                        if product_tax_s1:
                            taxes_id = [(6, 0, [product_tax_s1.id])]
                elif sale_order.tax_state == 'no_tax':
                    acc_tax = self.env['account.tax'].search(
                        [('xero_tax_type_id', '=', i.get('TaxType')), ('type_tax_use', '=', 'purchase'),
                         ('price_include', '=', False), ('company_id', '=', self.id)])
                    if acc_tax:
                        taxes_id = [(6, 0, [acc_tax.id])]
                    else:
                        self.import_tax()
                        product_tax_s1 = self.env['account.tax'].search(
                            [('xero_tax_type_id', '=', i.get('TaxType')), ('type_tax_use', '=', 'purchase'),
                             ('price_include', '=', False), ('company_id', '=', self.id)])
                        if product_tax_s1:
                            taxes_id = [(6, 0, [product_tax_s1.id])]
            else:
                taxes_id = 0

            if i.get('LineItemID'):
                ol_qb_id = i.get('LineItemID')

            if i.get('UnitAmount'):
                sp = float(i.get('UnitAmount'))
            else:
                sp = 0.0

            if i.get('Description'):
                description = i.get('Description')
            else:
                description = 'NA'

            create_so = self.env['sale.order.line'].search(
                [('product_id', '=', res_product.id),
                 ('order_id', '=', sale_order.id), ('company_id', '=', self.id)])
            if create_so:

                write_values = {
                    'product_id': res_product.id,
                    'name': description,
                    'product_uom_qty': quantity,
                    # 'date_planned': p_order_line.date_order,
                    'xero_sale_line_id': ol_qb_id,
                    'product_uom': 1,
                    'price_unit': sp,
                }
                if taxes_id:
                    write_values['tax_id'] = taxes_id

                res = create_so.write(write_values)

            if create_so:
                _logger.info(_("Order line updated successfully"))
            else:
                _logger.info(_("Order line not updated successfully"))
        else:
            '''CREATE NEW SALE ORDER LINES IN EXISTING SALE ORDER'''

            dict_l = {}
            dict_l.clear()
            dict_l['order_id'] = sale_order.id
            dict_l['product_id'] = res_product.id

            if i.get('Quantity'):
                dict_l['product_uom_qty'] = i.get('Quantity')

            if i.get('TaxType'):
                if sale_order.tax_state == 'inclusive':
                    acc_tax = self.env['account.tax'].search(
                        [('xero_tax_type_id', '=', i.get('TaxType')), ('type_tax_use', '=', 'sale'),
                         ('price_include', '=', True), ('company_id', '=', self.id)])
                    if acc_tax:
                        dict_l['tax_id'] = [(6, 0, [acc_tax.id])]
                    else:
                        self.import_tax()
                        product_tax_s1 = self.env['account.tax'].search(
                            [('xero_tax_type_id', '=', i.get('TaxType')), ('type_tax_use', '=', 'sale'),
                             ('price_include', '=', True), ('company_id', '=', self.id)])
                        if product_tax_s1:
                            dict_l['tax_id'] = [(6, 0, [product_tax_s1.id])]
                elif sale_order.tax_state == 'exclusive':
                    acc_tax = self.env['account.tax'].search(
                        [('xero_tax_type_id', '=', i.get('TaxType')), ('type_tax_use', '=', 'sale'),
                         ('price_include', '=', False), ('company_id', '=', self.id)])
                    if acc_tax:
                        dict_l['tax_id'] = [(6, 0, [acc_tax.id])]
                    else:
                        self.import_tax()
                        product_tax_s1 = self.env['account.tax'].search(
                            [('xero_tax_type_id', '=', i.get('TaxType')), ('type_tax_use', '=', 'sale'),
                             ('price_include', '=', False), ('company_id', '=', self.id)])
                        if product_tax_s1:
                            dict_l['tax_id'] = [(6, 0, [product_tax_s1.id])]
                elif sale_order.tax_state == 'no_tax':
                    acc_tax = self.env['account.tax'].search(
                        [('xero_tax_type_id', '=', i.get('TaxType')), ('type_tax_use', '=', 'sale'),
                         ('price_include', '=', False), ('company_id', '=', self.id)])
                    if acc_tax:
                        dict_l['tax_id'] = [(6, 0, [acc_tax.id])]
                    else:
                        self.import_tax()
                        product_tax_s1 = self.env['account.tax'].search(
                            [('xero_tax_type_id', '=', i.get('TaxType')), ('type_tax_use', '=', 'sale'),
                             ('price_include', '=', False), ('company_id', '=', self.id)])
                        if product_tax_s1:
                            dict_l['tax_id'] = [(6, 0, [product_tax_s1.id])]

            if i.get('LineItemID'):
                dict_l['xero_purchase_line_id'] = i.get('LineItemID')
                # dict_l['date_planned'] = sale_order.date_order

            dict_l['product_uom'] = 1

            if i.get('UnitAmount'):
                dict_l['price_unit'] = float(i.get('UnitAmount'))
            else:
                dict_l['price_unit'] = 0.0

            if i.get('Description'):
                dict_l['name'] = i.get('Description')
            else:
                dict_l['name'] = 'NA'

            # if cust.get('DeliveryDate'):
            #     dict_l['date_planned'] = date_planned

            create_p = self.env['sale.order.line'].create(dict_l)
            if create_p:
                _logger.info(_("Sale line Created Successfully"))
            else:
                _logger.info(_("Sale line not Created Successfully"))

    def import_purchase_order(self):
        """IMPORT PURCHASE ORDER FROM XERO TO ODOO"""
        for i in range(10000):
            res = self.po_main_function(i + 1)
            _logger.info("RESPONSE : %s", res)

            if not res:
                break;
        success_form = self.env.ref('pragmatic_odoo_xero_connector.import_successfull_view', False)
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
    def po_main_function(self, page_no):
        _logger.info("PURCHASE PAGE NO : %s", page_no)
        if self.x_purchaseorder_date:
            date_from = datetime.datetime.strptime(str(self.x_purchaseorder_date), '%Y-%m-%d').date()
        else:
            date_from = 0

        if date_from:
            url = 'https://api.xero.com/api.xro/2.0/PurchaseOrders?DateFrom=%s' % (date_from)
        else:
            url = 'https://api.xero.com/api.xro/2.0/PurchaseOrders?page=' + str(page_no)

        data = self.get_data(url)
        if data:
            recs = []

            parsed_dict = json.loads(data.text)
            if parsed_dict.get('PurchaseOrders'):
                record = parsed_dict.get('PurchaseOrders')
                if isinstance(record, (dict,)):
                    product_exist = self.check_product_present_po(record)
                    if product_exist:
                        self.create_imported_purchase_order(record)
                        self._cr.commit()
                    else:
                        if record.get('PurchaseOrderNumber'):
                            _logger.info("PURCHASE ORDER DOES NOT CONTAIN ANY PRODUCT. PO = %s",
                                         record.get('PurchaseOrderNumber'))

                else:
                    for cust in parsed_dict.get('PurchaseOrders'):
                        product_exist = self.check_product_present_po(cust)
                        if product_exist:
                            self.create_imported_purchase_order(cust)
                            self._cr.commit()
                        else:
                            if cust.get('PurchaseOrderNumber'):
                                _logger.info("PURCHASE ORDER DOES NOT CONTAIN ANY PRODUCT. PO = %s",
                                             cust.get('PurchaseOrderNumber'))

                # print("record:::::::::::::::::::",record)
                if self.x_purchaseorder_date:
                    self.x_purchaseorder_date = datetime.datetime.today().strftime('%Y-%m-%d')
                    return False
                return True
            else:
                if page_no == 1:
                    raise ValidationError('There is no any purchase order present in XERO.')
                else:
                    self.x_purchaseorder_date = datetime.datetime.today().strftime('%Y-%m-%d')
                    return False

        elif data.status_code == 401:
            raise ValidationError(
                'Time Out..!!\n Please check your connection or error in application or refresh token.')

    @api.model
    def check_product_present_po(self, cust):
        if cust.get('LineItems'):
            order_lines = cust.get('LineItems')
            if isinstance(order_lines, (dict,)):
                i = cust.get('LineItems')
                if i.get('ItemCode'):
                    return True
                else:
                    return False
            else:
                for i in cust.get('LineItems'):
                    if i.get('ItemCode'):
                        continue
                    else:
                        return False
        return True

    @api.model
    def check_if_product_present(self, cust):
        if cust.get('LineItems'):
            if cust.get('LineItems'):
                order_lines = cust.get('LineItems')
                if isinstance(order_lines, (dict,)):
                    i = cust.get('LineItems')
                    if i.get('ItemCode'):
                        return True
                    else:
                        return False
                else:
                    for i in cust.get('LineItems'):
                        if i.get('ItemCode'):
                            return True
                        else:
                            return False

    @api.model
    def create_imported_purchase_order(self, cust):
        purchase_order = self.env['purchase.order'].search(
            [('xero_purchase_id', '=', cust.get('PurchaseOrderID')), ('company_id', '=', self.id)])

        if not purchase_order:
            res_partner = self.env['res.partner'].search(
                [('xero_cust_id', '=', cust.get('Contact').get('ContactID')), ('company_id', '=', self.id)], limit=1)

            if res_partner:
                self.create_customer_for_purchase_order(cust, res_partner)
            else:
                self.fetch_the_required_customer(cust.get('Contact').get('ContactID'))
                res_partner = self.env['res.partner'].search(
                    [('xero_cust_id', '=', cust.get('Contact').get('ContactID')), ('company_id', '=', self.id)],
                    limit=1)

                if res_partner:
                    self.create_customer_for_purchase_order(cust, res_partner)
        else:

            res_partner = self.env['res.partner'].search(
                [('xero_cust_id', '=', cust.get('Contact').get('ContactID')), ('company_id', '=', self.id)], limit=1)
            if res_partner:
                self.update_customer_for_purchase_order(cust, res_partner, purchase_order)
            else:
                self.fetch_the_required_customer(cust.get('Contact').get('ContactID'))
                res_partner = self.env['res.partner'].search(
                    [('xero_cust_id', '=', cust.get('Contact').get('ContactID')), ('company_id', '=', self.id)],
                    limit=1)
                if res_partner:
                    self.update_customer_for_purchase_order(cust, res_partner, purchase_order)

    @api.model
    def create_customer_for_purchase_order(self, cust, res_partner):
        dict_s = {}
        if cust.get('PurchaseOrderID'):
            dict_s['partner_id'] = res_partner.id
            dict_s['xero_purchase_id'] = cust.get('PurchaseOrderID')
        # else:
        #     dict_s['parent_id'] = cust.get('Contact').get('Name')

        # if cust.get('DeliveryAddress'):

        if cust.get('LineAmountTypes'):
            if cust.get('LineAmountTypes') == "Exclusive":
                dict_s['tax_state'] = 'exclusive'
            if cust.get('LineAmountTypes') == "Inclusive":
                dict_s['tax_state'] = 'inclusive'
            if cust.get('LineAmountTypes') == "NoTax":
                dict_s['tax_state'] = 'no_tax'

        if cust.get('Status'):
            if cust.get('Status') == 'DRAFT':
                dict_s['state'] = 'draft'
            elif cust.get('Status') == 'DELETED':
                dict_s['state'] = 'cancel'
            elif cust.get('Status') == 'AUTHORISED' or cust.get('Status') == 'BILLED' or cust.get(
                    'Status') == 'SUBMITTED':
                dict_s['state'] = 'draft'

        if cust.get('PurchaseOrderNumber'):
            dict_s['name'] = cust.get('PurchaseOrderNumber')
        if cust.get('DateString'):
            gte = cust.get('DateString')
            date1 = datetime.datetime.strptime(gte[0:10], '%Y-%m-%d')
            dict_s['date_order'] = gte[0:10]

        if cust.get('DeliveryInstructions'):
            dict_s['notes'] = cust.get('DeliveryInstructions')
        if cust.get('Reference'):
            dict_s['partner_ref'] = cust.get('Reference')
        so_obj = self.env['purchase.order'].create(dict_s)
        if so_obj:
            if cust.get('Status') == 'AUTHORISED' or cust.get('Status') == 'BILLED' or cust.get(
                    'Status') == 'SUBMITTED':
                so_obj.button_confirm()

            _logger.info("Purchase Order Created successfully  PO = %s ", cust.get('PurchaseOrderNumber'))
        else:
            _logger.info("Purchase Order Not Created successfully  PO = %s ", cust.get('PurchaseOrderNumber'))

        if cust.get('LineItems'):
            order_lines = cust.get('LineItems')
            if isinstance(order_lines, (dict,)):
                i = cust.get('LineItems')
                res_product = self.env['product.product'].search(
                    [('default_code', '=', i.get('ItemCode'))])
                if res_product:
                    self.create_purchase_order_line(i, so_obj, res_product)
                else:
                    if i.get('ItemCode'):
                        self.fetch_the_required_product(i.get('ItemCode'))
                        res_product = self.env['product.product'].search(
                            [('default_code', '=', i.get('ItemCode'))])
                        if res_product:
                            self.create_purchase_order_line(i, so_obj, res_product)
                    else:
                        _logger.info('[PO ORDER LINE] Item Code Not defined.')
            else:
                for i in cust.get('LineItems'):
                    res_product = self.env['product.product'].search(
                        [('default_code', '=', i.get('ItemCode'))])
                    if res_product:
                        self.create_purchase_order_line(i, so_obj, res_product)
                    else:
                        if i.get('ItemCode'):
                            self.fetch_the_required_product(i.get('ItemCode'))
                            res_product = self.env['product.product'].search(
                                [('default_code', '=', i.get('ItemCode'))])
                            if res_product:
                                self.create_purchase_order_line(i, so_obj, res_product)
                        else:
                            _logger.info('[PO ORDER LINE] Item Code Not defined.')

    @api.model
    def update_customer_for_purchase_order(self, cust, res_partner, purchase_order):
        dict_s = {}

        if cust.get('PurchaseOrderID'):
            dict_s['partner_id'] = res_partner.id
            dict_s['xero_purchase_id'] = cust.get('PurchaseOrderID')
        # if cust.get('DeliveryAddress'):

        if cust.get('Status'):
            if cust.get('Status') == 'DRAFT':
                dict_s['state'] = 'draft'
            elif cust.get('Status') == 'DELETED':
                dict_s['state'] = 'cancel'
            elif not cust.get('Status') == 'AUTHORISED':
                dict_s['state'] = 'draft'
            elif not cust.get('Status') == 'BILLED':
                dict_s['state'] = 'draft'
            elif not cust.get('Status') == 'SUBMITTED':
                dict_s['state'] = 'draft'

        if cust.get('LineAmountTypes'):
            if cust.get('LineAmountTypes') == "Exclusive":
                dict_s['tax_state'] = 'exclusive'
            if cust.get('LineAmountTypes') == "Inclusive":
                dict_s['tax_state'] = 'inclusive'
            if cust.get('LineAmountTypes') == "NoTax":
                dict_s['tax_state'] = 'no_tax'

        if cust.get('PurchaseOrderNumber'):
            dict_s['name'] = cust.get('PurchaseOrderNumber')
        if cust.get('DateString'):
            gte = cust.get('DateString')
            date1 = datetime.datetime.strptime(gte[0:10], '%Y-%m-%d')
            dict_s['date_order'] = gte[0:10]

        if cust.get('DeliveryInstructions'):
            dict_s['notes'] = cust.get('DeliveryInstructions')
        if cust.get('Reference'):
            dict_s['partner_ref'] = cust.get('Reference')

        p_o = purchase_order.write(dict_s)
        if p_o:
            if purchase_order.state == 'draft' and (
                    cust.get('Status') == 'AUTHORISED' or cust.get('Status') == 'BILLED' or cust.get(
                'Status') == 'SUBMITTED'):
                purchase_order.button_confirm()

            _logger.info("Purchase Order Updated successfully  PO = %s ", cust.get('PurchaseOrderNumber'))
        else:
            _logger.info("Purchase Order Not Updated successfully  PO = %s ", cust.get('PurchaseOrderNumber'))

        if cust.get('LineItems'):
            order_lines = cust.get('LineItems')
            if isinstance(order_lines, (dict,)):
                i = cust.get('LineItems')
                res_product = self.env['product.product'].search(
                    [('default_code', '=', i.get('ItemCode'))])
                if res_product:
                    self.update_purchase_order_line(i, purchase_order, res_product, cust)
                else:
                    if i.get('ItemCode'):
                        self.fetch_the_required_product(i.get('ItemCode'))
                        res_product = self.env['product.product'].search(
                            [('default_code', '=', i.get('ItemCode'))])
                        if res_product:
                            self.update_purchase_order_line(i, purchase_order, res_product, cust)
                    else:
                        _logger.info('[PO ORDER LINE] Item Code Not defined.')

            else:
                for i in cust.get('LineItems'):
                    res_product = self.env['product.product'].search(
                        [('default_code', '=', i.get('ItemCode'))])

                    if res_product:
                        self.update_purchase_order_line(i, purchase_order, res_product, cust)
                    else:
                        if i.get('ItemCode'):
                            self.fetch_the_required_product(i.get('ItemCode'))
                            res_product = self.env['product.product'].search(
                                [('default_code', '=', i.get('ItemCode'))])

                            if res_product:
                                self.update_purchase_order_line(i, purchase_order, res_product, cust)
                        else:
                            _logger.info('[PO ORDER LINE] Item Code Not defined.')

    @api.model
    def create_purchase_order_line(self, i, so_obj, res_product):
        """  CREATES PURCHASE ORDER LINES FOR THE FIRST TIME  """

        dict_l = {}
        dict_l.clear()
        dict_l['order_id'] = so_obj.id
        dict_l['product_id'] = res_product.id

        if i.get('Quantity'):
            dict_l['product_qty'] = i.get('Quantity')
        else:
            dict_l['product_qty'] = 0

        if i.get('TaxType'):
            if so_obj.tax_state == 'inclusive':
                acc_tax = self.env['account.tax'].search(
                    [('xero_tax_type_id', '=', i.get('TaxType')), ('type_tax_use', '=', 'purchase'),
                     ('price_include', '=', True), ('company_id', '=', self.id)])
                if acc_tax:
                    dict_l['taxes_id'] = [(6, 0, [acc_tax.id])]
                else:
                    self.import_tax()
                    product_tax_s1 = self.env['account.tax'].search(
                        [('xero_tax_type_id', '=', i.get('TaxType')), ('type_tax_use', '=', 'purchase'),
                         ('price_include', '=', True), ('company_id', '=', self.id)])
                    if product_tax_s1:
                        dict_l['taxes_id'] = [(6, 0, [product_tax_s1.id])]
            elif so_obj.tax_state == 'exclusive':
                acc_tax = self.env['account.tax'].search(
                    [('xero_tax_type_id', '=', i.get('TaxType')), ('type_tax_use', '=', 'purchase'),
                     ('price_include', '=', False), ('company_id', '=', self.id)])
                if acc_tax:
                    dict_l['taxes_id'] = [(6, 0, [acc_tax.id])]
                else:
                    self.import_tax()
                    product_tax_s1 = self.env['account.tax'].search(
                        [('xero_tax_type_id', '=', i.get('TaxType')), ('type_tax_use', '=', 'purchase'),
                         ('price_include', '=', False), ('company_id', '=', self.id)])
                    if product_tax_s1:
                        dict_l['taxes_id'] = [(6, 0, [product_tax_s1.id])]
            elif so_obj.tax_state == 'no_tax':
                acc_tax = self.env['account.tax'].search(
                    [('xero_tax_type_id', '=', i.get('TaxType')), ('type_tax_use', '=', 'purchase'),
                     ('price_include', '=', False), ('company_id', '=', self.id)])
                if acc_tax:
                    dict_l['taxes_id'] = [(6, 0, [acc_tax.id])]
                else:
                    self.import_tax()
                    product_tax_s1 = self.env['account.tax'].search(
                        [('xero_tax_type_id', '=', i.get('TaxType')), ('type_tax_use', '=', 'purchase'),
                         ('price_include', '=', False), ('company_id', '=', self.id)])
                    if product_tax_s1:
                        dict_l['taxes_id'] = [(6, 0, [product_tax_s1.id])]

        if i.get('LineItemID'):
            dict_l['xero_purchase_line_id'] = i.get('LineItemID')
            dict_l['date_planned'] = so_obj.date_order

        dict_l['product_uom'] = 1

        if i.get('UnitAmount'):
            dict_l['price_unit'] = float(i.get('UnitAmount'))
        else:
            dict_l['price_unit'] = 0.0

        if i.get('Description'):
            dict_l['name'] = i.get('Description')
        else:
            dict_l['name'] = 'NA'

        create_p = self.env['purchase.order.line'].create(dict_l)
        if create_p:
            _logger.info(_(" Purchase line Created successfully"))
        else:
            _logger.info(_("Purchase line not Created successfully"))

    @api.model
    def update_purchase_order_line(self, i, purchase_order, res_product, cust):
        p_order_line = self.env['purchase.order.line'].search(
            [('product_id', '=', res_product.id),
             ('order_id', '=', purchase_order.id), ('company_id', '=', self.id)], limit=1)

        if cust.get('DeliveryDateString'):
            xero_delivery_time = cust.get('DeliveryDateString').split("T")
            xero_delivery_datetime = xero_delivery_time[0] + ' ' + xero_delivery_time[1]
            xero_datetime = datetime.datetime.strptime(xero_delivery_datetime, '%Y-%m-%d %H:%M:%S')
            date_planned = xero_datetime

        else:
            date_planned = purchase_order.date_order

        if p_order_line:
            quantity = 0
            taxes_id = 0
            ol_qb_id = 0

            if i.get('Quantity'):
                quantity = i.get('Quantity')

            if i.get('TaxType'):
                if purchase_order.tax_state == 'inclusive':
                    acc_tax = self.env['account.tax'].search(
                        [('xero_tax_type_id', '=', i.get('TaxType')), ('type_tax_use', '=', 'purchase'),
                         ('price_include', '=', True), ('company_id', '=', self.id)])
                    if acc_tax:
                        taxes_id = [(6, 0, [acc_tax.id])]
                    else:
                        self.import_tax()
                        product_tax_s1 = self.env['account.tax'].search(
                            [('xero_tax_type_id', '=', i.get('TaxType')), ('type_tax_use', '=', 'purchase'),
                             ('price_include', '=', True), ('company_id', '=', self.id)])
                        if product_tax_s1:
                            taxes_id = [(6, 0, [product_tax_s1.id])]
                elif purchase_order.tax_state == 'exclusive':
                    acc_tax = self.env['account.tax'].search(
                        [('xero_tax_type_id', '=', i.get('TaxType')), ('type_tax_use', '=', 'purchase'),
                         ('price_include', '=', False), ('company_id', '=', self.id)])
                    if acc_tax:
                        taxes_id = [(6, 0, [acc_tax.id])]
                    else:
                        self.import_tax()
                        product_tax_s1 = self.env['account.tax'].search(
                            [('xero_tax_type_id', '=', i.get('TaxType')), ('type_tax_use', '=', 'purchase'),
                             ('price_include', '=', False), ('company_id', '=', self.id)])
                        if product_tax_s1:
                            taxes_id = [(6, 0, [product_tax_s1.id])]
                elif purchase_order.tax_state == 'no_tax':
                    acc_tax = self.env['account.tax'].search(
                        [('xero_tax_type_id', '=', i.get('TaxType')), ('type_tax_use', '=', 'purchase'),
                         ('price_include', '=', False), ('company_id', '=', self.id)])
                    if acc_tax:
                        taxes_id = [(6, 0, [acc_tax.id])]
                    else:
                        self.import_tax()
                        product_tax_s1 = self.env['account.tax'].search(
                            [('xero_tax_type_id', '=', i.get('TaxType')), ('type_tax_use', '=', 'purchase'),
                             ('price_include', '=', False), ('company_id', '=', self.id)])
                        if product_tax_s1:
                            taxes_id = [(6, 0, [product_tax_s1.id])]
            else:
                taxes_id = 0

            if i.get('LineItemID'):
                ol_qb_id = i.get('LineItemID')

            if i.get('UnitAmount'):
                sp = float(i.get('UnitAmount'))
            else:
                sp = 0.0

            if i.get('Description'):
                description = i.get('Description')
            else:
                description = 'NA'

            create_po = self.env['purchase.order.line'].search(
                [('product_id', '=', res_product.id),
                 ('order_id', '=', purchase_order.id), ('company_id', '=', self.id)])

            if taxes_id == 0:

                if create_po:
                    res = create_po.update({

                        'product_id': res_product.id,
                        'name': description,
                        'product_qty': quantity,
                        # 'date_planned': p_order_line.date_order,
                        'xero_purchase_line_id': ol_qb_id,
                        'product_uom': 1,
                        'price_unit': sp,
                        # 'taxes_id':taxes_id,
                        'date_planned': date_planned
                    })
            else:
                if create_po:
                    res = create_po.update({

                        'product_id': res_product.id,
                        'name': description,
                        'product_qty': quantity,
                        # 'date_planned': p_order_line.date_order,
                        'xero_purchase_line_id': ol_qb_id,
                        'product_uom': 1,
                        'price_unit': sp,
                        'taxes_id': taxes_id,
                        'date_planned': date_planned
                    })

            if create_po:
                _logger.info(_("Purchase line updated successfully"))
            else:
                _logger.info(_("Purchase line not updated successfully"))
        else:
            '''CREATE NEW PURCHASE ORDER LINES IN EXISTING PURCHASE ORDER'''

            dict_l = {}
            dict_l.clear()
            dict_l['order_id'] = purchase_order.id
            dict_l['product_id'] = res_product.id

            if i.get('Quantity'):
                dict_l['product_qty'] = i.get('Quantity')

            if i.get('TaxType'):
                if purchase_order.tax_state == 'inclusive':
                    acc_tax = self.env['account.tax'].search(
                        [('xero_tax_type_id', '=', i.get('TaxType')), ('type_tax_use', '=', 'purchase'),
                         ('price_include', '=', True), ('company_id', '=', self.id)])
                    if acc_tax:
                        dict_l['taxes_id'] = [(6, 0, [acc_tax.id])]
                    else:
                        self.import_tax()
                        product_tax_s1 = self.env['account.tax'].search(
                            [('xero_tax_type_id', '=', i.get('TaxType')), ('type_tax_use', '=', 'purchase'),
                             ('price_include', '=', True), ('company_id', '=', self.id)])
                        if product_tax_s1:
                            dict_l['taxes_id'] = [(6, 0, [product_tax_s1.id])]
                elif purchase_order.tax_state == 'exclusive':
                    acc_tax = self.env['account.tax'].search(
                        [('xero_tax_type_id', '=', i.get('TaxType')), ('type_tax_use', '=', 'purchase'),
                         ('price_include', '=', False), ('company_id', '=', self.id)])
                    if acc_tax:
                        dict_l['taxes_id'] = [(6, 0, [acc_tax.id])]
                    else:
                        self.import_tax()
                        product_tax_s1 = self.env['account.tax'].search(
                            [('xero_tax_type_id', '=', i.get('TaxType')), ('type_tax_use', '=', 'purchase'),
                             ('price_include', '=', False), ('company_id', '=', self.id)])
                        if product_tax_s1:
                            dict_l['taxes_id'] = [(6, 0, [product_tax_s1.id])]
                elif purchase_order.tax_state == 'no_tax':
                    acc_tax = self.env['account.tax'].search(
                        [('xero_tax_type_id', '=', i.get('TaxType')), ('type_tax_use', '=', 'purchase'),
                         ('price_include', '=', False), ('company_id', '=', self.id)])
                    if acc_tax:
                        dict_l['taxes_id'] = [(6, 0, [acc_tax.id])]
                    else:
                        self.import_tax()
                        product_tax_s1 = self.env['account.tax'].search(
                            [('xero_tax_type_id', '=', i.get('TaxType')), ('type_tax_use', '=', 'purchase'),
                             ('price_include', '=', False), ('company_id', '=', self.id)])
                        if product_tax_s1:
                            dict_l['taxes_id'] = [(6, 0, [product_tax_s1.id])]

            if i.get('LineItemID'):
                dict_l['xero_purchase_line_id'] = i.get('LineItemID')
                dict_l['date_planned'] = purchase_order.date_order

            dict_l['product_uom'] = 1

            if i.get('UnitAmount'):
                dict_l['price_unit'] = float(i.get('UnitAmount'))
            else:
                dict_l['price_unit'] = 0.0

            if i.get('Description'):
                dict_l['name'] = i.get('Description')
            else:
                dict_l['name'] = 'NA'

            if cust.get('DeliveryDate'):
                dict_l['date_planned'] = date_planned

            create_p = self.env['purchase.order.line'].create(dict_l)
            if create_p:
                _logger.info(_("Purchase line Created Successfully"))
            else:
                _logger.info(_("Purchase line not Created Successfully"))

    """IMPORTING CUSTOMERS AND CONTACTS FROM XERO TO ODOO"""

    def create_contact(self, parent_id, con_id, new_dict):
        firstname = ''
        lastname = ''
        contact_name = ''
        temp_dict = {}

        if (isinstance(new_dict, list)):
            for val in new_dict:
                if val.get('FirstName'):
                    firstname = val.get('FirstName')
                else:
                    firstname = ''
                if val.get('LastName'):
                    lastname = val.get('LastName')
                else:
                    lastname = ''
                contact_name = firstname + ' ' + lastname
                temp_dict.update({'name': contact_name})
                if val.get('EmailAddress', False):
                    temp_dict.update({'email': val.get('EmailAddress')})
                if isinstance(parent_id, int):
                    temp_dict.update({'parent_id': parent_id})
                else:
                    temp_dict.update({'parent_id': parent_id[0].id})
                temp_dict.update({'type': 'contact'})
                temp_dict.update({'xero_cust_id': con_id})

                # -----------------------------------------------------------
                # 'it is added to avoid the error a Partner Cannot Follow Twice The Same Object'
                if 'message_follower_ids' in temp_dict:
                    del temp_dict['message_follower_ids']
                # -----------------------------------------------------------

                if val.get('FirstName') or val.get('LastName'):
                    if val.get('EmailAddress') not in self.skip_emails:
                        con_search = self.env['res.partner'].search(
                            [('parent_id', '=', parent_id), ('type', '=', 'contact'),
                             ('email', '=', val.get('EmailAddress')), ('company_id', '=', self.id)])
                        if not con_search:
                            new_con = self.env['res.partner'].create(temp_dict)
                            self._cr.commit()
                        else:
                            con_search.write(temp_dict)

    def import_customers(self):
        """IMPORT CUSTOMER FROM XERO TO ODOO"""
        for i in range(10000):
            res = self.customer_main_function(i + 1)
            _logger.info("RESPONSE : %s", res)

            if not res:
                break;
        success_form = self.env.ref('pragmatic_odoo_xero_connector.import_successfull_view', False)
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
    def customer_main_function(self, page_no):
        _logger.info("CUSTOMER PAGE NO : %s", page_no)

        url = 'https://api.xero.com/api.xro/2.0/Contacts?page=' + str(page_no)
        res = self.create_customers(url, page_no)
        if res:
            return True
        else:
            return False

    @api.model
    def fetch_the_required_customer(self, customer_id):
        _logger.info("FETCHING THE CUSTOMER GIVEN CUSTOMER -----> ")

        url = 'https://api.xero.com/api.xro/2.0/Contacts/' + str(customer_id)
        page_no = 0
        self.create_customers(url, page_no)

    @api.model
    def create_customers(self, url, page_no):
        if not self.skip_emails:
            self.skip_emails = ''

        data = self.get_data(url)

        if data:
            recs = []
            #
            parsed_dict = json.loads(data.text)

            if parsed_dict.get('Contacts', False):
                record = parsed_dict.get('Contacts')
                if isinstance(record, (dict,)):
                    self.create_imported_customers(record)
                else:
                    for item in parsed_dict.get('Contacts'):
                        self.create_imported_customers(item)
                return True
            else:
                if page_no == 1:
                    raise ValidationError('There is no any contact present in XERO.')
                else:
                    return False
        elif data.status_code == 401:
            raise ValidationError(
                'Time Out..!!\n Please check your connection or error in application or refresh token.')

    @api.model
    def create_imported_customers(self, item):
        if item.get('AccountNumber'):

            customer = self.env['res.partner'].search(
                ['|', ('xero_cust_id', '=', item.get('ContactID')),
                 ('ref', '=', item.get('AccountNumber'))])
            customer_exists = self.env['res.partner'].search([('id', 'in', customer.ids), ('company_id', '=', self.id)])
        else:

            customer_exists = self.env['res.partner'].search(
                [('company_id', '=', self.id), ('xero_cust_id', '=', item.get('ContactID')), ])

        dict_customer = {}

        _logger.info("Xero Customer Name : %s", item.get('Name'))
        _logger.info("Xero Customer ContactID : %s", item.get('ContactID'))

        if (item.get('IsSupplier') == 'false' and (item.get('IsCustomer') == 'false')):
            dict_customer.update({'company_type': 'person'})
            dict_customer.update({'is_company': True})
        # dict_customer.update({'company_id': self.ids})

        if item.get('EmailAddress', False):
            if item.get('EmailAddress') not in self.skip_emails:
                dict_customer.update({'email': item.get('EmailAddress')})
            else:
                dict_customer.update({'email': ''})

        if item.get('AccountNumber', False):
            dict_customer.update({'ref': item.get('AccountNumber')})

        if item.get('PaymentTerms'):
            if item.get('PaymentTerms').get('Bills'):
                type = item.get('PaymentTerms').get('Bills').get('Type')
                day = item.get('PaymentTerms').get('Bills').get('Day')

                if type == 'DAYSAFTERBILLDATE':
                    option = 'day_after_invoice_date'
                    term_name = str(day) + ' day(s) after the bill date'

                if type == 'DAYSAFTERBILLMONTH':
                    option = 'after_invoice_month'
                    term_name = str(day) + ' day(s) after the end of the bill month'

                if type == 'OFCURRENTMONTH':
                    option = 'day_current_month'
                    term_name = str(day) + ' of the current month'

                if type == 'OFFOLLOWINGMONTH':
                    option = 'day_following_month'
                    term_name = str(day) + ' of the following month'

                payment_terms = self.env['account.payment.term'].search([('name','=',term_name)])
                if not payment_terms:
                    term_dict = {}
                    term_dict['name'] = term_name
                    term_dict['line_ids'] = [(0, 0, {'value': 'balance',
                                                     'days': day,
                                                     'option': option})]

                    payment_terms = self.env['account.payment.term'].create(term_dict)

                    if payment_terms:
                        dict_customer['property_supplier_payment_term_id'] = payment_terms.id
                else:
                    dict_customer['property_supplier_payment_term_id'] = payment_terms.id

            if item.get('PaymentTerms').get('Sales'):
                type = item.get('PaymentTerms').get('Sales').get('Type')
                day = item.get('PaymentTerms').get('Sales').get('Day')

                if type == 'DAYSAFTERBILLDATE':
                    option = 'day_after_invoice_date'
                    term_name = str(day) + ' day(s) after the invoice date'

                if type == 'DAYSAFTERBILLMONTH':
                    option = 'after_invoice_month'
                    term_name = str(day) + ' day(s) after the end of the invoice month'

                if type == 'OFCURRENTMONTH':
                    option = 'day_current_month'
                    term_name = str(day) + ' of the current month'

                if type == 'OFFOLLOWINGMONTH':
                    option = 'day_following_month'
                    term_name = str(day) + ' of the following month'

                payment_terms = self.env['account.payment.term'].search([('name','=',term_name)])
                if not payment_terms:
                    term_dict = {}
                    term_dict['name'] = term_name
                    term_dict['line_ids'] = [(0, 0, {'value': 'balance',
                                              'days': day,
                                              'option': option})]

                    payment_terms = self.env['account.payment.term'].create(term_dict)

                    if payment_terms:
                        dict_customer['property_payment_term_id'] = payment_terms.id
                else:
                    dict_customer['property_payment_term_id'] = payment_terms.id

        if item.get('Name'):
            dict_customer.update({'name': item.get('Name')})
            dict_customer.update({'xero_cust_id': item.get('ContactID')})

        if item.get('Addresses'):
            for address in item.get('Addresses'):
                if address.get('AddressType',False):
                    if address.get('AddressType') == 'POBOX':
                        street1 = ''
                        street2 = ''
                        country = ''
                        state = ''

                        if address.get('AddressLine1'):
                            street1 = address.get('AddressLine1')
                        if address.get('AddressLine2'):
                            street2 = address.get('AddressLine2')
                        if address.get('AddressLine3'):
                            street2 = street2 + '\n' + address.get('AddressLine3')
                        if address.get('AddressLine4'):
                            street2 = street2 + '\n' + address.get('AddressLine4')

                        if address.get('Country'):
                            if len(address.get('Country')) == 2:
                                country = self.env['res.country'].search([('code', '=ilike', address.get('Country'))],limit=1)
                            else:
                                country = self.env['res.country'].search([('name', 'ilike', address.get('Country'))],limit=1)

                            if not country:
                                raise UserError('Country Not Found : ' + address.get('Country') + '\nContact Name : ' + item.get('Name'))

                        if address.get('Region'):
                            state = self.env['res.country.state'].search([('name','=ilike',address.get('Region'))])
                            if not state:
                                if country:
                                    state = self.env['res.country.state'].search(
                                        [('code', '=', address.get('Region')),('country_id','=',country.id)])
                                    if not state:
                                        raise UserError('State Not Found : ' + address.get('Region') + '\nContact Name : ' + item.get('Name'))

                        dict_customer.update({
                            'street':street1,
                            'street2': street2,
                            'city': address.get('City'),
                            'zip': address.get('PostalCode'),
                            'country_id': country.id if country else False,
                            'state_id': state.id if state else False,
                        })

        if item.get('Phones', False):
            for phones in item.get('Phones'):
                if phones.get('PhoneType', False):
                    if phones.get('PhoneType') == 'DEFAULT' and phones.get('PhoneNumber',
                                                                           False):
                        phone_str = phones.get('PhoneNumber')
                        dict_customer.update({'phone': phone_str})
                    if phones.get('PhoneType') == 'MOBILE' and phones.get('PhoneNumber',
                                                                          False):
                        phone_str = phones.get('PhoneNumber')
                        dict_customer.update({'mobile': phone_str})
        dict_customer.update({'company_id': int(self.id)})

        if not customer_exists:
            create_cust = self.env['res.partner'].create(dict_customer)
        else:
            customer_exists[0].write(dict_customer)

        if item.get('ContactPersons'):
            new_dict = item.get('ContactPersons')
            if not customer_exists:
                self.create_contact(create_cust.id, item.get('ContactID'), new_dict)
            else:
                self.create_contact(customer_exists[0].id, item.get('ContactID'), new_dict)

    def import_credit_notes(self):
        """IMPORT CREDIT NOTES(Customer refund bill and vendor refund bill) FROM XERO TO ODOO"""
        for i in range(10000):
            res = self.cn_main_function(i + 1)
            _logger.info("RESPONSE : %s", res)
            if not res:
                break;
        success_form = self.env.ref('pragmatic_odoo_xero_connector.import_successfull_view', False)
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
    def cn_main_function(self, page_no):
        _logger.info("CREDIT NOTE PAGE NO : %s", page_no)

        if self.x_credit_note_date:
            date_from = datetime.datetime.strptime(str(self.x_credit_note_date), '%Y-%m-%d').date()
        else:
            date_from = 0

        if date_from:
            url = 'https://api.xero.com/api.xro/2.0/CreditNotes?page=' + str(
                page_no) + '&where=Date>=DateTime(%s,%s,%s)' % (date_from.year, date_from.month, date_from.day)
        else:
            url = 'https://api.xero.com/api.xro/2.0/CreditNotes?page=' + str(page_no)
        data = self.get_data(url)

        if data:
            recs = []

            parsed_dict = json.loads(data.text)

            if parsed_dict.get('CreditNotes'):
                if parsed_dict.get('CreditNotes'):
                    record = parsed_dict.get('CreditNotes')
                    if isinstance(record, (dict,)):
                        if not (record.get('Status') == 'DRAFT' or record.get('Status') == 'DELETED' or record.get(
                                'Status') == 'VOIDED' or record.get('Status') == 'SUBMITTED'):
                            self.create_imported_credit_notes(record)
                    else:
                        for cust in parsed_dict.get('CreditNotes'):
                            if not (cust.get('Status') == 'DRAFT' or cust.get('Status') == 'DELETED' or cust.get(
                                    'Status') == 'VOIDED' or cust.get('Status') == 'SUBMITTED'):
                                self.create_imported_credit_notes(cust)
                    return True
            else:
                if page_no == 1:
                    raise ValidationError('There is no any credit note present in XERO.')
                else:
                    self.x_credit_note_date = datetime.datetime.today().strftime('%Y-%m-%d')
                    return False
        elif data.status_code == 401:
            raise ValidationError(
                'Time Out..!!\n Please check your connection or error in application or refresh token.')

    @api.model
    def create_imported_credit_notes(self, cust):
        if cust.get('CreditNoteNumber'):
            _logger.info("PROCESSING CREDIT NOTE NUMBER : %s", cust.get('CreditNoteNumber'))
        _logger.info("PROCESSING CREDIT NOTE ID : %s", cust.get('CreditNoteID'))

        account_invoice = self.env['account.move'].search(
            [('xero_invoice_id', '=', cust.get('CreditNoteID')), ('company_id', '=', self.id)])
        if not account_invoice:

            res_partner = self.env['res.partner'].search(
                [('xero_cust_id', '=', cust.get('Contact').get('ContactID')), ('company_id', '=', self.id)], limit=1)

            if res_partner:
                self.create_customer_for_credit_note(cust, res_partner)
            else:
                self.fetch_the_required_customer(cust.get('Contact').get('ContactID'))
                res_partner2 = self.env['res.partner'].search(
                    [('xero_cust_id', '=', cust.get('Contact').get('ContactID')), ('company_id', '=', self.id)],
                    limit=1)

                if res_partner2:
                    self.create_customer_for_credit_note(cust, res_partner2)
        else:

            _logger.info("CREDIT NOTE OBJECT : %s", account_invoice)
            _logger.info("CREDIT NOTE STATE : %s", account_invoice.state)

            if account_invoice.state == 'posted':
                _logger.info("You cannot update a posted credit note.")
            if account_invoice.state == 'draft':
                _logger.info(
                    "Code is not available for updating credit note, please delete the particular credit note and import the credit notes again.")
            if account_invoice.state == 'cancel':
                _logger.info("You cannot update a cancelled credit note.")

    @api.model
    def create_customer_for_credit_note(self, cust, res_partner):

        dict_i = {}

        if cust.get('CreditNoteID'):
            dict_i['partner_id'] = res_partner.id
            dict_i['xero_invoice_id'] = cust.get('CreditNoteID')
            dict_i['company_id'] = self.id

        if cust.get('CurrencyCode'):
            currency = self.env['res.currency'].search([('name', '=', cust.get('CurrencyCode'))], limit=1)
            dict_i['currency_id'] = currency.id

        if cust.get('Type') == 'ACCRECCREDIT':
            sale = self.env['account.journal'].search([('type', '=', 'sale')], limit=1)
            if sale:
                dict_i['journal_id'] = sale.id

        if cust.get('Type') == 'ACCPAYCREDIT':
            purchase = self.env['account.journal'].search([('type', '=', 'purchase')], limit=1)
            if purchase:
                dict_i['journal_id'] = purchase.id

        if cust.get('LineAmountTypes'):
            if cust.get('LineAmountTypes') == "Exclusive":
                dict_i['tax_state'] = 'exclusive'
            if cust.get('LineAmountTypes') == "Inclusive":
                dict_i['tax_state'] = 'inclusive'
            if cust.get('LineAmountTypes') == "NoTax":
                dict_i['tax_state'] = 'no_tax'

        if cust.get('Status'):
            if (cust.get('Status') == 'AUTHORISED') or (
                    cust.get('Status') == 'PAID'):
                dict_i['state'] = 'draft'

        if cust.get('CreditNoteNumber'):
            dict_i['xero_invoice_number'] = cust.get('CreditNoteNumber')

        if cust.get('DateString'):
            dict_i['invoice_date'] = cust.get('DateString')

        if cust.get('Type'):
            if cust.get('Type') == 'ACCRECCREDIT':
                dict_i['move_type'] = 'out_refund'
            elif cust.get('Type') == 'ACCPAYCREDIT':
                dict_i['move_type'] = 'in_refund'

        if cust.get('Reference'):
            dict_i['ref'] = cust.get('Reference')

        dict_i['invoice_line_ids'] = []

        invoice_line_vals = {}
        invoice_type = dict_i['move_type']
        tax_state = dict_i['tax_state']

        if cust.get('LineItems'):
            order_lines = cust.get('LineItems')
            if isinstance(order_lines, (dict,)):
                i = cust.get('LineItems')
                if not i.get('ItemCode'):
                    res_product = ''
                    invoice_line_vals = self.create_credit_note_invoice_line(i, res_product, cust, invoice_type,
                                                                             tax_state)
                else:
                    res_product = self.env['product.product'].search([('default_code', '=', i.get('ItemCode'))])
                    if res_product:
                        invoice_line_vals = self.create_credit_note_invoice_line(i, res_product, cust, invoice_type,
                                                                                 tax_state)
                    else:
                        self.fetch_the_required_product(i.get('ItemCode'))
                        res_product = self.env['product.product'].search([('default_code', '=', i.get('ItemCode'))])
                        if res_product:
                            invoice_line_vals = self.create_credit_note_invoice_line(i, res_product, cust, invoice_type,
                                                                                     tax_state)
                if invoice_line_vals:
                    dict_i['invoice_line_ids'].append((0, 0, invoice_line_vals))

            else:
                for i in cust.get('LineItems'):
                    if not i.get('ItemCode'):
                        res_product = ''
                        invoice_line_vals = self.create_credit_note_invoice_line(i, res_product, cust, invoice_type,
                                                                                 tax_state)
                    else:
                        res_product = self.env['product.product'].search([('default_code', '=', i.get('ItemCode'))])
                        if res_product:
                            invoice_line_vals = self.create_credit_note_invoice_line(i, res_product, cust, invoice_type,
                                                                                     tax_state)
                        else:
                            self.fetch_the_required_product(i.get('ItemCode'))
                            res_product = self.env['product.product'].search([('default_code', '=', i.get('ItemCode'))])
                            if res_product:
                                invoice_line_vals = self.create_credit_note_invoice_line(i, res_product, cust,
                                                                                         invoice_type, tax_state)
                    if invoice_line_vals:
                        dict_i['invoice_line_ids'].append((0, 0, invoice_line_vals))

        invoice_obj = self.env['account.move'].create(dict_i)
        if invoice_obj:
            if invoice_obj.state == 'draft':
                invoice_obj.action_post()
            _logger.info("\nCredit Note Created Successfully...!!! CN = %s", cust.get('CreditNoteNumber'))

    @api.model
    def create_credit_note_invoice_line(self, i, res_product, cust, invoice_type, tax_state):
        dict_ol = {}

        if res_product == '':
            _logger.info("Product Not Defined.")
        else:
            dict_ol['product_id'] = res_product.id

        if i.get('LineItemID'):
            dict_ol['xero_invoice_line_id'] = i.get('LineItemID')

        if i.get('DiscountRate'):
            dict_ol['discount'] = i.get('DiscountRate')

        acc_tax = ''

        if i.get('TaxType'):

            if invoice_type == 'out_refund':

                if tax_state == 'inclusive':

                    acc_tax = self.env['account.tax'].search(
                        [('xero_tax_type_id', '=', i.get('TaxType')), ('type_tax_use', '=', 'sale'),
                         ('price_include', '=', True), ('company_id', '=', self.id)])
                    if acc_tax:
                        dict_ol['tax_ids'] = [(6, 0, [acc_tax.id])]
                    else:
                        self.import_tax()
                        product_tax_s1 = self.env['account.tax'].search(
                            [('xero_tax_type_id', '=', i.get('TaxType')), ('type_tax_use', '=', 'sale'),
                             ('price_include', '=', True), ('company_id', '=', self.id)])
                        if product_tax_s1:
                            dict_ol['itax_ids'] = [(6, 0, [product_tax_s1.id])]
                elif tax_state == 'exclusive':

                    acc_tax = self.env['account.tax'].search(
                        [('xero_tax_type_id', '=', i.get('TaxType')), ('type_tax_use', '=', 'sale'),
                         ('price_include', '=', False), ('company_id', '=', self.id)])
                    if acc_tax:
                        dict_ol['tax_ids'] = [(6, 0, [acc_tax.id])]
                    else:
                        self.import_tax()
                        product_tax_s1 = self.env['account.tax'].search(
                            [('xero_tax_type_id', '=', i.get('TaxType')), ('type_tax_use', '=', 'sale'),
                             ('price_include', '=', False), ('company_id', '=', self.id)])
                        if product_tax_s1:
                            dict_ol['tax_ids'] = [(6, 0, [product_tax_s1.id])]
                elif tax_state == 'no_tax':
                    acc_tax = self.env['account.tax'].search(
                        [('xero_tax_type_id', '=', i.get('TaxType')), ('type_tax_use', '=', 'sale'),
                         ('price_include', '=', False), ('company_id', '=', self.id)])
                    if acc_tax:
                        dict_ol['tax_ids'] = [(6, 0, [acc_tax.id])]
                    else:
                        self.import_tax()
                        product_tax_s1 = self.env['account.tax'].search(
                            [('xero_tax_type_id', '=', i.get('TaxType')), ('type_tax_use', '=', 'sale'),
                             ('price_include', '=', False), ('company_id', '=', self.id)])
                        if product_tax_s1:
                            dict_ol['tax_ids'] = [(6, 0, [product_tax_s1.id])]

            elif invoice_type == 'in_refund':

                if tax_state == 'inclusive':
                    acc_tax = self.env['account.tax'].search(
                        [('xero_tax_type_id', '=', i.get('TaxType')), ('type_tax_use', '=', 'purchase'),
                         ('price_include', '=', True), ('company_id', '=', self.id)])
                    if acc_tax:
                        dict_ol['tax_ids'] = [(6, 0, [acc_tax.id])]
                    else:
                        self.import_tax()
                        product_tax_s1 = self.env['account.tax'].search(
                            [('xero_tax_type_id', '=', i.get('TaxType')), ('type_tax_use', '=', 'purchase'),
                             ('price_include', '=', True), ('company_id', '=', self.id)])
                        if product_tax_s1:
                            dict_ol['tax_ids'] = [(6, 0, [product_tax_s1.id])]
                elif tax_state == 'exclusive':
                    acc_tax = self.env['account.tax'].search(
                        [('xero_tax_type_id', '=', i.get('TaxType')), ('type_tax_use', '=', 'purchase'),
                         ('price_include', '=', False), ('company_id', '=', self.id)])
                    if acc_tax:
                        dict_ol['tax_ids'] = [(6, 0, [acc_tax.id])]
                    else:
                        self.import_tax()
                        product_tax_s1 = self.env['account.tax'].search(
                            [('xero_tax_type_id', '=', i.get('TaxType')), ('type_tax_use', '=', 'purchase'),
                             ('price_include', '=', False), ('company_id', '=', self.id)])
                        if product_tax_s1:
                            dict_ol['tax_ids'] = [(6, 0, [product_tax_s1.id])]
                elif tax_state == 'no_tax':

                    acc_tax = self.env['account.tax'].search(
                        [('xero_tax_type_id', '=', i.get('TaxType')), ('type_tax_use', '=', 'purchase'),
                         ('price_include', '=', False), ('company_id', '=', self.id)])
                    if acc_tax:
                        dict_ol['tax_ids'] = [(6, 0, [acc_tax.id])]
                    else:
                        self.import_tax()
                        product_tax_s1 = self.env['account.tax'].search(
                            [('xero_tax_type_id', '=', i.get('TaxType')), ('type_tax_use', '=', 'purchase'),
                             ('price_include', '=', False), ('company_id', '=', self.id)])
                        if product_tax_s1:
                            dict_ol['tax_ids'] = [(6, 0, [product_tax_s1.id])]

        if i.get('Quantity'):
            dict_ol['quantity'] = i.get('Quantity')
        else:
            dict_ol['quantity'] = 0

        if i.get('UnitAmount'):
            dict_ol['price_unit'] = i.get('UnitAmount')

        if i.get('Description'):
            dict_ol['name'] = i.get('Description')
        else:
            dict_ol['name'] = 'NA'

        if i.get('AccountCode'):

            acc_id_s = self.env['account.account'].search(
                [('code', '=', i.get('AccountCode')), ('company_id', '=', self.id)])
            if acc_id_s:
                dict_ol['account_id'] = acc_id_s.id
            else:
                self.import_accounts()
                acc_id_s1 = self.env['account.account'].search(
                    [('code', '=', i.get('AccountCode')), ('company_id', '=', self.id)])
                if acc_id_s1:
                    dict_ol['account_id'] = acc_id_s1.id
        elif not i.get('AccountCode') and not i.get('Quantity') and not i.get('UnitAmount'):
            if not self.default_account:
                raise ValidationError('PLease Set the Default Account in Xero Configuration.')

            if self.default_account:
                dict_ol['account_id'] = self.default_account.id
                dict_ol['quantity'] = 1.0
                dict_ol['price_unit'] = 0.0
        elif not i.get('AccountCode') and not i.get('ItemCode'):
            if not self.default_account:
                raise ValidationError('PLease Set the Default Account in Xero Configuration.')

            if self.default_account:
                dict_ol['account_id'] = self.default_account.id

        tax_val = i.get('TaxType')
        if tax_val:
            if acc_tax:
                dict_ol['tax_ids'] = [(6, 0, [acc_tax.id])]
            else:
                dict_ol['tax_ids'] = [(6, 0, [])]
        else:
            dict_ol['tax_ids'] = [[6, False, []]]

        if i.get('ItemCode') and not i.get('AccountCode'):
            if invoice_type == 'out_refund':
                if res_product:
                    if res_product.property_account_income_id:
                        dict_ol['account_id'] = res_product.property_account_income_id.id
                        _logger.info("PRODUCT has income account set")
                    else:
                        dict_ol['account_id'] = res_product.categ_id.property_account_income_categ_id.id
                        _logger.info("No Income account was set, taking from product category..")
            else:
                if res_product:
                    if res_product.property_account_expense_id:
                        dict_ol['account_id'] = res_product.property_account_expense_id.id
                        _logger.info("PRODUCT has income account set")
                    else:
                        dict_ol['account_id'] = res_product.categ_id.property_account_expense_categ_id.id
                        _logger.info("No Income account was set, taking from product category..")

        return dict_ol

    @api.model
    def import_organization(self):
        """IMPORT Organization FROM XERO TO ODOO ,It is basically used to fetch the country name for which xero organization is created """
        url = 'https://api.xero.com/api.xro/2.0/Organisations'
        data = self.get_data(url)

        if data:
            recs = []

            parsed_dict = json.loads(data.text)

            if parsed_dict.get('Organisations'):
                if parsed_dict.get('Organisations'):
                    record = parsed_dict.get('Organisations')
                    if isinstance(record, (dict,)):
                        country_id = self.env['res.country'].search(
                            [('code', '=', record.get('CountryCode'))])
                        country_name = country_id.name
                        return country_name
                    else:
                        for c_id in parsed_dict.get('Organisations'):
                            country_id = self.env['res.country'].search(
                                [('code', '=', c_id.get('CountryCode'))])
                            country_name = country_id.name
                            return country_name

    def import_payments(self):
        """IMPORT PAYMENTS(Customer payments and Vendor payments) FROM XERO TO ODOO"""

        if self.x_payments_date:
            date_from = datetime.datetime.strptime(str(self.x_payments_date), '%Y-%m-%d').date()
        else:
            date_from = 0

        if date_from:
            url = 'https://api.xero.com/api.xro/2.0/Payments?where=Date>=DateTime(%s,%s,%s)' % (
                date_from.year, date_from.month, date_from.day)
        else:
            url = 'https://api.xero.com/api.xro/2.0/Payments'
        data = self.get_data(url)

        if data:
            recs = []

            parsed_dict = json.loads(data.text)

            if parsed_dict.get('Payments'):
                if parsed_dict.get('Payments'):
                    record = parsed_dict.get('Payments')
                    if isinstance(record, (dict,)):
                        if not record.get('Status') == 'DELETED':
                            self.create_imported_payments(record)
                    else:
                        for grp in parsed_dict.get('Payments'):
                            if not grp.get('Status') == 'DELETED':
                                self.create_imported_payments(grp)
                    success_form = self.env.ref('pragmatic_odoo_xero_connector.import_successfull_view',
                                                False)
                    self.x_payments_date = datetime.datetime.today().strftime('%Y-%m-%d')

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
            else:
                raise ValidationError('There is no any payment present in XERO.')

        elif data.status_code == 401:
            raise ValidationError(
                'Time Out..!!\n Please check your connection or error in application or refresh token.')

    def compute_payment_date(self, datestring):
        timepart = datestring.split('(')[1].split(')')[0]
        milliseconds = int(timepart[:-5])
        hours = int(timepart[-5:]) / 100
        time = milliseconds / 1000

        dt = datetime.datetime.utcfromtimestamp(time + hours * 3600)
        return dt.strftime("%Y-%m-%dT%H:%M:%S") + '%02d:00' % hours

    @api.model
    def create_imported_payments(self, pay):
        acc_pay = self.env['account.payment'].search(
            [('xero_payment_id', '=', pay.get('PaymentID')), ('company_id', '=', self.id)])

        dict_g = {}
        invoice_pay = False

        if pay.get('Amount'):
            dict_g['amount'] = pay.get('Amount')
        else:
            dict_g['amount'] = 0.0

        if pay.get('Date'):
            payment_date = self.compute_payment_date(pay.get('Date'))
            payment_date_a = payment_date.split('T')
            converted_date = datetime.datetime.strptime(payment_date_a[0], '%Y-%m-%d')

            dict_g['date'] = converted_date

        # pm_type = 0
        if pay.get('Invoice'):
            if pay.get('Invoice').get('InvoiceID'):

                pay_type = None

                inv = self.env['account.move'].search(
                    ['|', ('xero_invoice_id', '=', pay.get('Invoice').get('InvoiceID')),
                     ('xero_invoice_number', '=', pay.get('Invoice').get('InvoiceNumber'))]) or self.env[
                          'account.move'].search(
                    ['|', ('xero_invoice_id', '=', pay.get('Invoice').get('InvoiceID')),
                     ('name', '=', pay.get('Invoice').get('InvoiceNumber'))])
                invoices = self.env['account.move'].search([('id', 'in', inv.ids), ('company_id', '=', self.id)])
                invoice_pay = invoices and invoices[0]
                if invoice_pay and pay.get('Invoice').get('Type') and pay.get('Invoice').get('Type') not in [
                    'APPREPAYMENT', 'ARPREPAYMENT', 'APOVERPAYMENT', 'AROVERPAYMENT']:
                    # Because of this line the invoice gets reconciled i.e the invoice for which this payment is done will be set to paid state
                    if invoice_pay.state == 'draft':
                        invoice_pay.action_post()

                    dict_g['communication'] = invoice_pay.name
                    # dict_g['reconciled_invoice_ids'] = [(4, invoice_pay.id,None)]

                    _logger.info('[Payment] ODOO INVOICE :: %s', invoice_pay)

                    if invoice_pay.partner_id.parent_id:
                        dict_g['partner_id'] = invoice_pay.partner_id.parent_id.id
                        _logger.info('[Payment] if INV : CUSTOMER :child :: %s', invoice_pay.partner_id)
                    else:
                        dict_g['partner_id'] = invoice_pay.partner_id.id
                        _logger.info('[Payment] if INV : CUSTOMER :parent :: %s', invoice_pay.partner_id)
                else:
                    if pay.get('Invoice').get('Contact'):
                        if pay.get('Invoice').get('Contact').get('ContactID'):
                            customer_id = self.env['res.partner'].search(
                                [('xero_cust_id', '=', pay.get('Invoice').get('Contact').get('ContactID')),
                                 ('company_id', '=', self.id)], limit=1) or self.env['res.partner'].search(
                                [('name', '=', pay.get('Invoice').get('Contact').get('Name')),
                                 ('company_id', '=', self.id)], limit=1)
                            if customer_id:
                                if customer_id.parent_id:
                                    dict_g['partner_id'] = customer_id.parent_id.id
                                    _logger.info('[Payment] existing CUSTOMER :parent :: %s', customer_id)
                                else:
                                    dict_g['partner_id'] = customer_id.id
                                    _logger.info('[Payment] existing CUSTOMER :child :: %s', customer_id)
                            else:
                                self.fetch_the_required_customer(pay.get('Invoice').get('Contact').get('ContactID'))
                                res_partner = self.env['res.partner'].search(
                                    [('xero_cust_id', '=', pay.get('Invoice').get('Contact').get('ContactID')),
                                     ('company_id', '=', self.id)], limit=1)
                                if res_partner:
                                    if res_partner.parent_id:
                                        dict_g['partner_id'] = res_partner.parent_id.id
                                        _logger.info('[Payment] CUSTOMER :parent :: %s', res_partner)
                                    else:
                                        dict_g['partner_id'] = res_partner.id
                                        _logger.info('[Payment] CUSTOMER :child :: %s', res_partner)
                if pay.get('PaymentType') == 'ACCRECPAYMENT':
                    dict_g['partner_type'] = 'customer'
                    # Receive money - Inbound
                    pay_type = 'sale'
                elif pay.get('PaymentType') == 'ACCPAYPAYMENT':
                    dict_g['partner_type'] = 'supplier'
                    # Send money - Outbound
                    pay_type = 'purchase'
                elif pay.get('PaymentType') == 'ARCREDITPAYMENT':
                    dict_g['partner_type'] = 'customer'
                    # Send money - Outbound
                    pay_type = 'purchase'
                elif pay.get('PaymentType') == 'APCREDITPAYMENT':
                    dict_g['partner_type'] = 'supplier'
                    # Receive money - Inbound
                    pay_type = 'sale'
                elif pay.get('PaymentType') == 'AROVERPAYMENTPAYMENT':
                    dict_g['partner_type'] = 'customer'
                    pay_type = 'sale'
                elif pay.get('PaymentType') == 'APOVERPAYMENTPAYMENT':
                    dict_g['partner_type'] = 'supplier'
                    pay_type = 'purchase'
                elif pay.get('PaymentType') == 'ARPREPAYMENTPAYMENT':
                    dict_g['partner_type'] = 'customer'
                    pay_type = 'sale'
                elif pay.get('PaymentType') == 'APPREPAYMENTPAYMENT':
                    dict_g['partner_type'] = 'supplier'
                    pay_type = 'purchase'

                if 'partner_id' in dict_g:
                    journal_id = self.env['account.journal'].get_journal_from_account(
                        pay.get('Account').get('Code'))
                    dict_g['journal_id'] = journal_id.id

                    payment_type = 'inbound' if pay_type == 'sale' else 'outbound'
                    payment_method = False
                    journal = journal_id[0]
                    if payment_type == 'inbound':
                        dict_g['payment_type'] = 'inbound'
                        payment_method = self.env.ref('account.account_payment_method_manual_in')
                        journal_payment_methods = journal.inbound_payment_method_ids
                    else:
                        dict_g['payment_type'] = 'outbound'
                        payment_method = self.env.ref('account.account_payment_method_manual_out')
                        journal_payment_methods = journal.outbound_payment_method_ids

                    if payment_method:
                        dict_g['payment_method_id'] = payment_method.id

                    if payment_method not in journal_payment_methods:
                        self._cr.commit()
                        raise ValidationError(_('No appropriate payment method enabled on journal %s') % journal.name)
        if not acc_pay:
            if 'partner_id' in dict_g:
                if 'journal_id' not in dict_g:
                    raise ValidationError(_('Payment Journal required'))
                else:
                    _logger.info('\n\n[Payment] DICTIONARY :: %s', dict_g)
                    if invoice_pay:
                        if dict_g['date']:
                            dict_g['payment_date'] = dict_g['date']
                            del dict_g['date']
                        register_payments = self.env['account.payment.register'].with_context(
                            active_model='account.move',
                            active_ids=invoice_pay.id).create(dict_g)
                        payment_id = register_payments._create_payments()
                        if pay.get('PaymentID') and payment_id:
                            payment_id.xero_payment_id = pay.get('PaymentID')

                        self._cr.commit()
                    else:
                        if pay.get('PaymentID'):
                            dict_g['xero_payment_id'] = pay.get('PaymentID')
                        if dict_g['communication']:
                            dict_g['ref'] = dict_g['communication']
                            del dict_g['communication']

                        pay_create = acc_pay.create(dict_g)
                        pay_create.action_post()
                        self._cr.commit()

    def import_prepayments(self):
        """IMPORT PREPAYMENTS(Customer payments and Vendor payments) FROM XERO TO ODOO"""

        if self.x_prepayments_date:
            date_from = datetime.datetime.strptime(str(self.x_prepayments_date), '%Y-%m-%d').date()
        else:
            date_from = 0

        if date_from:
            url = 'https://api.xero.com/api.xro/2.0/Prepayments?where=Date>=DateTime(%s,%s,%s)' % (
                date_from.year, date_from.month, date_from.day)
        else:
            url = 'https://api.xero.com/api.xro/2.0/Prepayments'
        data = self.get_data(url)

        if data:

            parsed_dict = json.loads(data.text)

            if parsed_dict.get('Prepayments'):
                if parsed_dict.get('Prepayments'):
                    record = parsed_dict.get('Prepayments')
                    if isinstance(record, (dict,)):
                        if not record.get('Status') == 'VOIDED':
                            self.create_imported_prepayments(record)
                    else:
                        for grp in parsed_dict.get('Prepayments'):
                            if not grp.get('Status') == 'VOIDED':
                                self.create_imported_prepayments(grp)
                    success_form = self.env.ref('pragmatic_odoo_xero_connector.import_successfull_view',
                                                False)
                    self.x_prepayments_date = datetime.datetime.today().strftime('%Y-%m-%d')

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
            else:
                raise UserError('There is no any payment present in XERO.')

        elif data.status_code == 401:
            raise UserError('Time Out..!!\n Please check your connection or error in application or refresh token.')

    @api.model
    def create_imported_prepayments(self, pay):
        acc_pay = self.env['account.payment'].search(
            [('xero_prepayment_id', '=', pay.get('PrepaymentID')), ('company_id', '=', self.id)])

        # if not acc_pay:
        dict_g = {}

        if pay.get('DateString'):
            dict_g['date'] = pay.get('DateString')

        if pay.get('Total'):
            dict_g['amount'] = pay.get('Total')
        else:
            dict_g['amount'] = 0.0

        if pay.get('Allocations'):
            if len(pay.get('Allocations')) == 1:
                for invoice in pay.get('Allocations'):

                    if invoice.get('Invoice'):
                        if invoice.get('Invoice').get('InvoiceID'):

                            pay_type = None

                            inv = self.env['account.move'].search(
                                ['|', ('xero_invoice_id', '=', invoice.get('Invoice').get('InvoiceID')),
                                 ('xero_invoice_number', '=', invoice.get('Invoice').get('InvoiceNumber'))]) or \
                                  self.env[
                                      'account.move'].search(
                                      ['|', ('xero_invoice_id', '=', invoice.get('Invoice').get('InvoiceID')),
                                       ('name', '=', invoice.get('Invoice').get('InvoiceNumber'))])
                            invoices = self.env['account.move'].search(
                                [('id', 'in', inv.ids), ('company_id', '=', self.id)])
                            invoice_pay = invoices and invoices[0]
                            if invoice_pay:

                                dict_g['communication'] = invoice_pay.name
                                # dict_g['invoice_ids'] = [(4, invoice_pay.id, None)]
                                _logger.info('[Payment] ODOO INVOICE :: %s', invoice_pay)

                                if invoice_pay.partner_id.parent_id:
                                    dict_g['partner_id'] = invoice_pay.partner_id.parent_id.id
                                    _logger.info('[Payment] if INV : CUSTOMER :child :: %s', invoice_pay.partner_id)
                                else:
                                    dict_g['partner_id'] = invoice_pay.partner_id.id
                                    _logger.info('[Payment] if INV : CUSTOMER :parent :: %s', invoice_pay.partner_id)
                            else:
                                dict_g['partner_id'] = self.get_payment_contact(pay)

                            if pay.get('Type') == 'RECEIVE-PREPAYMENT':
                                dict_g['partner_type'] = 'customer'
                                # Receive money - Inbound
                                pay_type = 'sale'
                            elif pay.get('Type') == 'SPEND-PREPAYMENT':
                                dict_g['partner_type'] = 'supplier'
                                # Send money - Outbound
                                pay_type = 'purchase'

                            if 'partner_id' in dict_g:
                                if not self.prepayment_journal:
                                    raise UserError("Prepayment journal is not defined in the configuration.")
                                journal_id = self.prepayment_journal
                                dict_g['journal_id'] = journal_id.id

                                payment_type = 'inbound' if pay_type == 'sale' else 'outbound'
                                payment_method = False
                                journal = journal_id[0]
                                if payment_type == 'inbound':
                                    dict_g['payment_type'] = 'inbound'
                                    payment_method = self.env.ref('account.account_payment_method_manual_in')
                                    journal_payment_methods = journal.inbound_payment_method_ids
                                else:
                                    dict_g['payment_type'] = 'outbound'
                                    payment_method = self.env.ref('account.account_payment_method_manual_out')
                                    journal_payment_methods = journal.outbound_payment_method_ids

                                if payment_method:
                                    dict_g['payment_method_id'] = payment_method.id

                                if payment_method not in journal_payment_methods:
                                    self._cr.commit()
                                    raise UserError(
                                        _('No appropriate payment method enabled on journal %s') % journal.name)
            if len(pay.get('Allocations')) > 1:
                communication = ''
                invoice_ids = []
                for invoice in pay.get('Allocations'):

                    if invoice.get('Invoice'):
                        if invoice.get('Invoice').get('InvoiceID'):

                            inv = self.env['account.move'].search(
                                ['|', ('xero_invoice_id', '=', invoice.get('Invoice').get('InvoiceID')),
                                 ('xero_invoice_number', '=', invoice.get('Invoice').get('InvoiceNumber'))]) or \
                                  self.env[
                                      'account.move'].search(
                                      ['|', ('xero_invoice_id', '=', invoice.get('Invoice').get('InvoiceID')),
                                       ('name', '=', invoice.get('Invoice').get('InvoiceNumber'))])
                            invoices = self.env['account.move'].search(
                                [('id', 'in', inv.ids), ('company_id', '=', self.id)])
                            invoice_pay = invoices and invoices[0]
                            if invoice_pay:
                                if invoice_pay.name:
                                    if communication:
                                        communication = communication + ',' + invoice_pay.name
                                    else:
                                        communication = invoice_pay.name

                                invoice_ids.append(invoice_pay.id)
                                _logger.info('[Payment] ODOO INVOICE :: %s', invoice_pay)

                                # partner_id = self.get_payment_contact(pay)

                pay_type = None

                # if invoice_ids:
                #     dict_g['invoice_ids'] = [(6, 0, invoice_ids)]
                if communication:
                    dict_g['communication'] = communication

                # if not invoice_ids:
                dict_g['partner_id'] = self.get_payment_contact(pay)

                if pay.get('Type') == 'RECEIVE-PREPAYMENT':
                    dict_g['partner_type'] = 'customer'
                    # Receive money - Inbound
                    pay_type = 'sale'
                elif pay.get('Type') == 'SPEND-PREPAYMENT':
                    dict_g['partner_type'] = 'supplier'
                    # Send money - Outbound
                    pay_type = 'purchase'

                if 'partner_id' in dict_g:
                    if not self.prepayment_journal:
                        raise UserError("Prepayment journal is not defined in the configuration.")
                    journal_id = self.prepayment_journal
                    dict_g['journal_id'] = journal_id.id

                    payment_type = 'inbound' if pay_type == 'sale' else 'outbound'
                    payment_method = False
                    journal = journal_id[0]
                    if payment_type == 'inbound':
                        dict_g['payment_type'] = 'inbound'
                        payment_method = self.env.ref('account.account_payment_method_manual_in')
                        journal_payment_methods = journal.inbound_payment_method_ids
                    else:
                        dict_g['payment_type'] = 'outbound'
                        payment_method = self.env.ref('account.account_payment_method_manual_out')
                        journal_payment_methods = journal.outbound_payment_method_ids

                    if payment_method:
                        dict_g['payment_method_id'] = payment_method.id

                    if payment_method not in journal_payment_methods:
                        self._cr.commit()
                        raise UserError(
                            _('No appropriate payment method enabled on journal %s') % journal.name)
        elif not pay.get('Allocations'):

            dict_g['partner_id'] = self.get_payment_contact(pay)

            if pay.get('Type') == 'RECEIVE-PREPAYMENT':
                dict_g['partner_type'] = 'customer'
                # Receive money - Inbound
                pay_type = 'sale'
            elif pay.get('Type') == 'SPEND-PREPAYMENT':
                dict_g['partner_type'] = 'supplier'
                # Send money - Outbound
                pay_type = 'purchase'

            if 'partner_id' in dict_g:
                if not self.prepayment_journal:
                    raise UserError("Prepayment journal is not defined in the configuration.")
                journal_id = self.prepayment_journal
                dict_g['journal_id'] = journal_id.id

                payment_type = 'inbound' if pay_type == 'sale' else 'outbound'
                payment_method = False
                journal = journal_id[0]
                if payment_type == 'inbound':
                    dict_g['payment_type'] = 'inbound'
                    payment_method = self.env.ref('account.account_payment_method_manual_in')
                    journal_payment_methods = journal.inbound_payment_method_ids
                else:
                    dict_g['payment_type'] = 'outbound'
                    payment_method = self.env.ref('account.account_payment_method_manual_out')
                    journal_payment_methods = journal.outbound_payment_method_ids

                if payment_method:
                    dict_g['payment_method_id'] = payment_method.id

                if payment_method not in journal_payment_methods:
                    self._cr.commit()
                    raise UserError(
                        _('No appropriate payment method enabled on journal %s') % journal.name)

        if not acc_pay:
            if 'partner_id' in dict_g:
                if 'journal_id' not in dict_g:
                    raise ValidationError(_('Payment Journal required'))
                else:
                    _logger.info('\n\n[Payment] DICTIONARY :: %s', dict_g)

                    if len(pay.get('Allocations')) == 1:

                        if invoice_pay:
                            if dict_g['date']:
                                dict_g['payment_date'] = dict_g['date']
                                del dict_g['date']
                            register_payments = self.env['account.payment.register'].with_context(
                                active_model='account.move',
                                active_ids=invoice_pay.id).create(dict_g)
                            payment_id = register_payments._create_payments()
                            if pay.get('PrepaymentID') and payment_id:
                                payment_id.xero_prepayment_id = pay.get('PrepaymentID')

                            self._cr.commit()
                    if len(pay.get('Allocations')) > 1:
                        if pay.get('PrepaymentID'):
                            dict_g['xero_prepayment_id'] = pay.get('PrepaymentID')
                        if dict_g['communication']:
                            dict_g['ref'] = dict_g['communication']
                            del dict_g['communication']

                        pay_create = acc_pay.create(dict_g)

                        # if invoice_ids:
                        # invoice_ids = self.env['account.move'].browse(invoice_ids)
                        # if dict_g['date']:
                        #     dict_g['payment_date'] = dict_g['date']
                        #     del dict_g['date']
                        #
                        # register_payments = self.env['account.payment.register'].with_context(
                        #     active_model='account.move',
                        #     active_ids=invoice_ids.ids).create(dict_g)
                        # payment_id = register_payments._create_payments()
                        # if pay.get('PrepaymentID') and payment_id:
                        #     payment_id.xero_prepayment_id = pay.get('PrepaymentID')
                        #
                        # self._cr.commit()
                    if len(pay.get('Allocations')) == 0 and len(pay.get('Payments')) == 0:
                        if pay.get('PrepaymentID'):
                            dict_g['xero_prepayment_id'] = pay.get('PrepaymentID')
                        if dict_g['communication']:
                            dict_g['ref'] = dict_g['communication']
                            del dict_g['communication']

                        pay_create = acc_pay.create(dict_g)
                        pay_create.action_post()

                    self._cr.commit()

    def import_overpayments(self):
        """IMPORT OVERPAYMENTS(Customer payments and Vendor payments) FROM XERO TO ODOO"""

        if self.x_overpayments_date:
            date_from = datetime.datetime.strptime(str(self.x_overpayments_date), '%Y-%m-%d').date()
        else:
            date_from = 0

        if date_from:
            url = 'https://api.xero.com/api.xro/2.0/Overpayments?where=Date>=DateTime(%s,%s,%s)' % (
                date_from.year, date_from.month, date_from.day)
        else:
            url = 'https://api.xero.com/api.xro/2.0/Overpayments'
        data = self.get_data(url)
        if data:

            parsed_dict = json.loads(data.text)
            if parsed_dict.get('Overpayments'):
                if parsed_dict.get('Overpayments'):
                    record = parsed_dict.get('Overpayments')
                    if isinstance(record, (dict,)):
                        if not record.get('Status') == 'VOIDED':
                            self.create_imported_overpayments(record)
                    else:
                        for grp in parsed_dict.get('Overpayments'):
                            if not grp.get('Status') == 'VOIDED':
                                self.create_imported_overpayments(grp)
                    success_form = self.env.ref('pragmatic_odoo_xero_connector.import_successfull_view',
                                                False)
                    self.x_overpayments_date = datetime.datetime.today().strftime('%Y-%m-%d')

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
            else:
                raise UserError('There is no any payment present in XERO.')

        elif data.status_code == 401:
            raise UserError('Time Out..!!\n Please check your connection or error in application or refresh token.')

    @api.model
    def create_imported_overpayments(self, pay):
        acc_pay = self.env['account.payment'].search(
            [('xero_overpayment_id', '=', pay.get('OverpaymentID')), ('company_id', '=', self.id)])
        # if not acc_pay:
        dict_g = {}

        if pay.get('DateString'):
            dict_g['date'] = pay.get('DateString')

        if pay.get('Total'):
            dict_g['amount'] = pay.get('Total')
        else:
            dict_g['amount'] = 0.0

        if pay.get('Allocations'):
            if len(pay.get('Allocations')) == 1:
                for invoice in pay.get('Allocations'):

                    if invoice.get('Invoice'):
                        if invoice.get('Invoice').get('InvoiceID'):

                            pay_type = None

                            inv = self.env['account.move'].search(
                                ['|', ('xero_invoice_id', '=', invoice.get('Invoice').get('InvoiceID')),
                                 ('xero_invoice_number', '=', invoice.get('Invoice').get('InvoiceNumber'))]) or \
                                  self.env[
                                      'account.move'].search(
                                      ['|', ('xero_invoice_id', '=', invoice.get('Invoice').get('InvoiceID')),
                                       ('name', '=', invoice.get('Invoice').get('InvoiceNumber'))])
                            invoices = self.env['account.move'].search(
                                [('id', 'in', inv.ids), ('company_id', '=', self.id)])
                            invoice_pay = invoices and invoices[0]
                            if invoice_pay:

                                dict_g['communication'] = invoice_pay.name
                                # dict_g['invoice_ids'] = [(4, invoice_pay.id, None)]
                                _logger.info('[Payment] ODOO INVOICE :: %s', invoice_pay)

                                if invoice_pay.partner_id.parent_id:
                                    dict_g['partner_id'] = invoice_pay.partner_id.parent_id.id
                                    _logger.info('[Payment] if INV : CUSTOMER :child :: %s', invoice_pay.partner_id)
                                else:
                                    dict_g['partner_id'] = invoice_pay.partner_id.id
                                    _logger.info('[Payment] if INV : CUSTOMER :parent :: %s', invoice_pay.partner_id)
                            else:
                                dict_g['partner_id'] = self.get_payment_contact(pay)

                            if pay.get('Type') == 'RECEIVE-OVERPAYMENT':
                                dict_g['partner_type'] = 'customer'
                                # Receive money - Inbound
                                pay_type = 'sale'
                            elif pay.get('Type') == 'SPEND-OVERPAYMENT':
                                dict_g['partner_type'] = 'supplier'
                                # Send money - Outbound
                                pay_type = 'purchase'

                            if 'partner_id' in dict_g:
                                if not self.overpayment_journal:
                                    raise UserError("Overpayment journal is not defined in the configuration.")
                                journal_id = self.overpayment_journal
                                dict_g['journal_id'] = journal_id.id

                                payment_type = 'inbound' if pay_type == 'sale' else 'outbound'
                                payment_method = False
                                journal = journal_id[0]
                                if payment_type == 'inbound':
                                    dict_g['payment_type'] = 'inbound'
                                    payment_method = self.env.ref('account.account_payment_method_manual_in')
                                    journal_payment_methods = journal.inbound_payment_method_ids
                                else:
                                    dict_g['payment_type'] = 'outbound'
                                    payment_method = self.env.ref('account.account_payment_method_manual_out')
                                    journal_payment_methods = journal.outbound_payment_method_ids

                                if payment_method:
                                    dict_g['payment_method_id'] = payment_method.id

                                if payment_method not in journal_payment_methods:
                                    self._cr.commit()
                                    raise UserError(
                                        _('No appropriate payment method enabled on journal %s') % journal.name)
            if len(pay.get('Allocations')) > 1:
                communication = ''
                invoice_ids = []
                for invoice in pay.get('Allocations'):

                    if invoice.get('Invoice'):
                        if invoice.get('Invoice').get('InvoiceID'):

                            inv = self.env['account.move'].search(
                                ['|', ('xero_invoice_id', '=', invoice.get('Invoice').get('InvoiceID')),
                                 ('xero_invoice_number', '=', invoice.get('Invoice').get('InvoiceNumber'))]) or \
                                  self.env[
                                      'account.move'].search(
                                      ['|', ('xero_invoice_id', '=', invoice.get('Invoice').get('InvoiceID')),
                                       ('name', '=', invoice.get('Invoice').get('InvoiceNumber'))])
                            invoices = self.env['account.move'].search(
                                [('id', 'in', inv.ids), ('company_id', '=', self.id)])
                            invoice_pay = invoices and invoices[0]
                            if invoice_pay:
                                if invoice_pay.name:
                                    if communication:
                                        communication = communication + ',' + invoice_pay.name
                                    else:
                                        communication = invoice_pay.name

                                invoice_ids.append(invoice_pay.id)
                                _logger.info('[Payment] ODOO INVOICE :: %s', invoice_pay)

                                # partner_id = self.get_payment_contact(pay)

                pay_type = None

                # if invoice_ids:
                #     dict_g['invoice_ids'] = [(6, 0, invoice_ids)]
                if communication:
                    dict_g['communication'] = communication

                # if not invoice_ids:
                dict_g['partner_id'] = self.get_payment_contact(pay)

                if pay.get('Type') == 'RECEIVE-OVERPAYMENT':
                    dict_g['partner_type'] = 'customer'
                    # Receive money - Inbound
                    pay_type = 'sale'
                elif pay.get('Type') == 'SPEND-OVRPAYMENT':
                    dict_g['partner_type'] = 'supplier'
                    # Send money - Outbound
                    pay_type = 'purchase'

                if 'partner_id' in dict_g:
                    if not self.overpayment_journal:
                        raise UserError("Overpayment journal is not defined in the configuration.")
                    journal_id = self.overpayment_journal
                    dict_g['journal_id'] = journal_id.id

                    payment_type = 'inbound' if pay_type == 'sale' else 'outbound'
                    payment_method = False
                    journal = journal_id[0]
                    if payment_type == 'inbound':
                        dict_g['payment_type'] = 'inbound'
                        payment_method = self.env.ref('account.account_payment_method_manual_in')
                        journal_payment_methods = journal.inbound_payment_method_ids
                    else:
                        dict_g['payment_type'] = 'outbound'
                        payment_method = self.env.ref('account.account_payment_method_manual_out')
                        journal_payment_methods = journal.outbound_payment_method_ids

                    if payment_method:
                        dict_g['payment_method_id'] = payment_method.id

                    if payment_method not in journal_payment_methods:
                        self._cr.commit()
                        raise UserError(
                            _('No appropriate payment method enabled on journal %s') % journal.name)
        elif not pay.get('Allocations'):
            dict_g['partner_id'] = self.get_payment_contact(pay)

            if pay.get('Type') == 'RECEIVE-OVERPAYMENT':
                dict_g['partner_type'] = 'customer'
                # Receive money - Inbound
                pay_type = 'sale'
            elif pay.get('Type') == 'SPEND-OVERPAYMENT':
                dict_g['partner_type'] = 'supplier'
                # Send money - Outbound
                pay_type = 'purchase'

            if 'partner_id' in dict_g:
                if not self.overpayment_journal:
                    raise UserError("Overpayment journal is not defined in the configuration.")
                journal_id = self.overpayment_journal
                dict_g['journal_id'] = journal_id.id

                payment_type = 'inbound' if pay_type == 'sale' else 'outbound'
                payment_method = False
                journal = journal_id[0]
                if payment_type == 'inbound':
                    dict_g['payment_type'] = 'inbound'
                    payment_method = self.env.ref('account.account_payment_method_manual_in')
                    journal_payment_methods = journal.inbound_payment_method_ids
                else:
                    dict_g['payment_type'] = 'outbound'
                    payment_method = self.env.ref('account.account_payment_method_manual_out')
                    journal_payment_methods = journal.outbound_payment_method_ids

                if payment_method:
                    dict_g['payment_method_id'] = payment_method.id

                if payment_method not in journal_payment_methods:
                    self._cr.commit()
                    raise UserError(
                        _('No appropriate payment method enabled on journal %s') % journal.name)

        if not acc_pay:
            if 'partner_id' in dict_g:
                if 'journal_id' not in dict_g:
                    raise ValidationError(_('Payment Journal required'))
                else:
                    _logger.info('\n\n[Payment] DICTIONARY :: %s', dict_g)

                    if len(pay.get('Allocations')) == 1:
                        if invoice_pay:
                            if dict_g['date']:
                                dict_g['payment_date'] = dict_g['date']
                                del dict_g['date']
                            register_payments = self.env['account.payment.register'].with_context(
                                active_model='account.move',
                                active_ids=invoice_pay.id).create(dict_g)
                            payment_id = register_payments._create_payments()
                            if pay.get('OverpaymentID') and payment_id:
                                payment_id.xero_overpayment_id = pay.get('OverpaymentID')

                            self._cr.commit()
                    if len(pay.get('Allocations')) > 1:
                        if pay.get('OverpaymentID'):
                            dict_g['xero_overpayment_id'] = pay.get('OverpaymentID')
                        if dict_g['communication']:
                            dict_g['ref'] = dict_g['communication']
                            del dict_g['communication']
                        pay_create = acc_pay.create(dict_g)

                        # if invoice_ids:
                        #     invoice_ids = self.env['account.move'].browse(invoice_ids)
                        #     if dict_g['date']:
                        #         dict_g['payment_date'] = dict_g['date']
                        #         del dict_g['date']
                        #     register_payments = self.env['account.payment.register'].with_context(
                        #         active_model='account.move',
                        #         active_ids=invoice_ids.ids).create(dict_g)
                        #     payment_id = register_payments._create_payments()
                        #     if pay.get('OverpaymentID') and payment_id:
                        #         payment_id.xero_overpayment_id = pay.get('OverpaymentID')
                        #
                        # self._cr.commit()
                    if len(pay.get('Allocations')) == 0 and len(pay.get('Payments')) == 0:
                        if pay.get('OverpaymentID'):
                            dict_g['xero_overpayment_id'] = pay.get('OverpaymentID')
                        if dict_g['communication']:
                            dict_g['ref'] = dict_g['communication']
                            del dict_g['communication']
                        pay_create = acc_pay.create(dict_g)
                        pay_create.action_post()

                    self._cr.commit()

    def get_payment_contact(self, pay):
        partner_id = ''
        if pay.get('Contact'):
            if pay.get('Contact').get('ContactID'):
                customer_id = self.env['res.partner'].search(
                    [('xero_cust_id', '=', pay.get('Contact').get('ContactID')),
                     ('company_id', '=', self.id)], limit=1) or self.env['res.partner'].search(
                    [('name', '=', pay.get('Contact').get('Name')),
                     ('company_id', '=', self.id)], limit=1)
                if customer_id:
                    if customer_id.parent_id:
                        partner_id = customer_id.parent_id.id
                        _logger.info('[Payment] existing CUSTOMER :parent :: %s', customer_id)
                    else:
                        partner_id = customer_id.id
                        _logger.info('[Payment] existing CUSTOMER :child :: %s', customer_id)
                else:
                    self.fetch_the_required_customer(
                        pay.get('Contact').get('ContactID'))
                    res_partner = self.env['res.partner'].search(
                        [('xero_cust_id', '=',
                          pay.get('Contact').get('ContactID')),
                         ('company_id', '=', self.id)], limit=1)
                    if res_partner:
                        if res_partner.parent_id:
                            partner_id = res_partner.parent_id.id
                            _logger.info('[Payment] CUSTOMER :parent :: %s', res_partner)
                        else:
                            partner_id = res_partner.id
                            _logger.info('[Payment] CUSTOMER :child :: %s', res_partner)
        return partner_id

    @api.model
    def import_payments_cron(self):
        company = self.env['res.users'].search([('id', '=', self._uid)]).company_id
        company.import_payments()

    @api.model
    def import_invoice_cron(self):
        company = self.env['res.users'].search([('id', '=', self._uid)]).company_id
        company.import_invoice()

    @api.model
    def import_manual_journal_cron(self):
        company = self.env['res.users'].search([('id', '=', self._uid)]).company_id
        company.import_manual_journals()

    @api.model
    def import_purchase_order_cron(self):
        company = self.env['res.users'].search([('id', '=', self._uid)]).company_id
        company.import_purchase_order()


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    def get_journal_from_account(self, xero_account_code):
        res_id_user = self.env['res.company'].search([])

        xero_config = self.env['res.users'].search([('id', '=', self._uid)], limit=1).company_id

        account_id = self.env['account.account'].search(
            [('code', '=', xero_account_code), ('company_id', '=', xero_config.id)])

        account = self.env['account.account'].browse(account_id)

        journal_id = self.search([('type', 'in', ['bank', 'cash']), ('default_account_id', '=', account_id.id),
                                  ('company_id', '=', xero_config.id)],
                                 limit=1)

        if not journal_id:
            raise ValidationError(_("Payment journal is not defined for XERO's Account : %s " % (xero_account_code)))
        return journal_id
