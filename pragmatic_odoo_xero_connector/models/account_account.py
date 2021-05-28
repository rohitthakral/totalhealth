import base64
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import requests
import json
import logging

_logger = logging.getLogger(__name__)


class Account(models.Model):
    _inherit = 'account.account'

    xero_account_id = fields.Char(string="Xero Account Id", copy=False)
    enable_payments_to_account = fields.Boolean(string="Enable Payments", default=False, copy=False)
    xero_account_type = fields.Many2one('xero.account.account', string="Xero Account Type")
    xero_description = fields.Text(string="Description")
    xero_tax_type_for_accounts = fields.Many2one('xero.tax.type', string="Tax Type")

    @api.model
    def prepare_account_export_dict(self):
        """Create Dictionary to export to XERO"""
        vals = {}
        if self.code:
            vals.update({
                'Code': self.code,
                'TaxType': 'NONE'
            })
        if self.name:
            vals.update({
                'Name': self.name,
            })
        if self.enable_payments_to_account:
            if self.enable_payments_to_account == True:
                vals.update({
                    'EnablePaymentsToAccount': 'true',
                })
            else:
                vals.update({
                    'EnablePaymentsToAccount': 'false',
                })
        if self.xero_description:
            vals.update({
                'Description': self.xero_description,
            })
        if self.xero_tax_type_for_accounts:
            vals.update({
                'TaxType': self.xero_tax_type_for_accounts.xero_tax_type,
            })
        if self.xero_account_type:
            account_type = {'Current Asset account': 'CURRENT',
                            'Current Liability account': 'CURRLIAB',
                            'Depreciation account': 'DEPRECIATN',
                            'Direct Costs account': 'DIRECTCOSTS',
                            'Equity account': 'EQUITY',
                            'Expense account': 'EXPENSE',
                            'Fixed Asset account': 'FIXED',
                            'Inventory Asset account': 'INVENTORY',
                            'Liability account': 'LIABILITY',
                            'Non-current Asset account': 'NONCURRENT',
                            'Other Income account': 'OTHERINCOME',
                            'Overhead account': 'OVERHEADS',
                            'Prepayment account': 'PREPAYMENT',
                            'Revenue account': 'REVENUE',
                            'Sale account': 'SALES',
                            'Non-current Liability account': 'TERMLIAB',
                            }

            type_name = self.env['xero.account.account'].search([('id', '=', self.xero_account_type.id)])
            if type_name.xero_account_type_name in account_type:
                vals.update({
                    'Type': account_type.get(type_name.xero_account_type_name)
                })
        return vals

    @api.model
    def create_account_in_xero(self):
        res_id_user = self.env['res.company'].search([])

        """export accounts to XERO"""
        xero_config = self.env['res.users'].search([('id', '=', self._uid)], limit=1).company_id
        if self._context.get('active_ids'):
            account = self.browse(self._context.get('active_ids'))
        else:
            account = self

        for a in account:
            self.create_account_main(a, xero_config)
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
    def create_account_ref_in_xero(self, account_id):
        """export accounts to XERO"""
        xero_config = self.env['res.users'].search([('id', '=', self._uid)], limit=1).company_id
        # if self._context.get('active_ids'):
        #     account = self.browse(self._context.get('active_ids'))
        # else:
        if account_id:
            account = account_id
        else:
            account = self
        if account:
            self.create_account_main(account, xero_config)

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
    def create_account_main(self, a, xero_config):
        if not a.xero_account_type:
            # abc = acc.code
            raise ValidationError('Please Add Xero Account Type and Tax Type for Account No ' + a.code)
        else:
            if not a.xero_account_id:
                vals = a.prepare_account_export_dict()
                parsed_dict = json.dumps(vals)
                # print("PARSED DICT : ",parsed_dict,type(parsed_dict))

                if xero_config.xero_oauth_token:
                    token = xero_config.xero_oauth_token

                headers = self.get_head()
                if token:
                    client_key = xero_config.xero_client_id
                    client_secret = xero_config.xero_client_secret
                    resource_owner_key = xero_config.xero_oauth_token
                    resource_owner_secret = xero_config.xero_oauth_token_secret

                    protected_url = 'https://api.xero.com/api.xro/2.0/Accounts'
                    data = requests.request('PUT', url=protected_url, data=parsed_dict, headers=headers)
                    # print("DATA : ",data,data.text)
                    if data.status_code == 200:
                        response_data = json.loads(data.text)
                        if response_data.get('Accounts'):
                            # update xero accound id
                            if response_data.get('Accounts')[0].get('AccountID'):
                                a.update({
                                    'xero_account_id': response_data.get('Accounts')[0].get('AccountID')
                                })
                                self._cr.commit()
                                # print("ACC ID : ",a.xero_account_id)
                                _logger.info(_(" (CREATE) - Exported successfully to XERO"))
                                # self._cr.commit()
                                # self.SuccessMessage()
                    elif data.status_code == 400:
                        logs = self.env['xero.error.log'].create({
                            'transaction': 'Account Export',
                            'xero_error_response': data.text,
                            'error_date': fields.datetime.now(),
                            'record_id': a,
                        })
                        self._cr.commit()
                        response_data = json.loads(data.text)
                        if response_data:
                            if response_data.get('Elements'):
                                for element in response_data.get('Elements'):
                                    if element.get('ValidationErrors'):
                                        for err in element.get('ValidationErrors'):
                                            if err.get('Message'):
                                                raise ValidationError(
                                                    '(Account) Xero Exception : ' + err.get('Message'))
                            elif response_data.get('Message'):
                                raise ValidationError(
                                    '(Account) Xero Exception : ' + response_data.get('Message'))
                            else:
                                raise ValidationError(
                                    '(Account) Xero Exception : please check xero logs in odoo for more details')
                    elif data.status_code == 401:
                        raise ValidationError(
                            "Time Out.\nPlease Check Your Connection or error in application or refresh token..!!")

            elif a.xero_account_id:
                vals = a.prepare_account_export_dict()
                parsed_dict = json.dumps(vals)
                if xero_config.xero_oauth_token:
                    token = xero_config.xero_oauth_token

                headers = self.get_head()
                if token:
                    client_key = xero_config.xero_client_id
                    client_secret = xero_config.xero_client_secret
                    resource_owner_key = xero_config.xero_oauth_token
                    resource_owner_secret = xero_config.xero_oauth_token_secret

                    protected_url = 'https://api.xero.com/api.xro/2.0/Accounts/' + a.xero_account_id

                    data = requests.request('POST', url=protected_url, headers=headers, data=parsed_dict)
                    # print("DATA ----------------> ", data, data.text)
                    if data.status_code == 200:
                        _logger.info(_(" (UPDATE) - Exported successfully to XERO"))
                    elif data.status_code == 401:
                        raise ValidationError(
                            "Time Out..!!\nPlease Check Your Connection or error in application or refresh token.")
                    else:
                        logs = self.env['xero.error.log'].create({
                            'transaction': 'Account Export',
                            'xero_error_response': data.text,
                            'error_date': fields.datetime.now(),
                            'record_id': a,
                        })
                        self._cr.commit()


class XeroAccountType(models.Model):
    _name = 'xero.account.account'
    _description = 'xero account account'
    _rec_name = 'xero_account_type_name'

    xero_account_type_name = fields.Char(string='Account Type', readonly=True, copy=False)


class XeroAccountTaxType(models.Model):
    _name = 'xero.tax.type'
    _description = 'xero tax type'
    _rec_name = 'xero_tax_type'

    xero_tax_type = fields.Char(string='Account Tax Type', readonly=True, copy=False)


class AnalyticAccountGroupsInherit(models.Model):
    _inherit = 'account.analytic.group'

    xero_tracking_id = fields.Char(string="Xero Tracking Id", copy=False)
    is_active = fields.Boolean(string="Active", default=True)

    def put_data(self, url, parsed_dict, post=None):
        xero_config = self.env['res.users'].search([('id', '=', self._uid)], limit=1).company_id

        if xero_config.xero_oauth_token:
            token = xero_config.xero_oauth_token

        headers = {
            'Authorization': "Bearer " + str(xero_config.xero_oauth_token),
            'Xero-tenant-id': xero_config.xero_tenant_id,
            'Accept': 'application/json'
        }

        if token:
            protected_url = url
            if post is None:
                data = requests.request('PUT', url=protected_url, data=parsed_dict, headers=headers)
            else:
                data = requests.request('POST', url=protected_url, data=parsed_dict, headers=headers)

        return data

    def create_analytic_account_group_in_xero(self, group=None):

        if not group:
            if self._context.get('active_ids'):
                group = self.browse(self._context.get('active_ids'))
            else:
                group = self

        for t in group:
            vals = {}
            if t.is_active:
                status = "ACTIVE"
            else:
                status = "ARCHIVED"

            if not t.xero_tracking_id:

                vals.update({'Name': t.name, 'Status': status})
                parsed_dict = json.dumps(vals)
                # print('\n\n\n___________________________1')
                url = 'https://api.xero.com/api.xro/2.0/TrackingCategories'
                data = self.put_data(url, parsed_dict)

                # print('\n\n\n___________________________2',data)
                if data.status_code == 200:
                    parsed_data = json.loads(data.text)

                    # print('\n\n\n___________________________3', parsed_data)
                    if parsed_data:
                        if parsed_data.get('TrackingCategories'):
                            t.xero_tracking_id = parsed_data.get(
                                'TrackingCategories')[0].get('TrackingCategoryID')
                            self._cr.commit()
                            _logger.info(_("(CREATE) Exported successfully to XERO"))
                            return parsed_data.get('TrackingCategories')[0].get('TrackingCategoryID')

                elif data.status_code == 400:
                    parsed_error = json.loads(data.text)
                    if parsed_error.get('ErrorNumber') == 10:
                        Error = parsed_error.get('Elements')
                        msg = Error[0].get('ValidationErrors')
                        msg = msg[0].get('Message')

                        _logger.info(_("\n\n\n Error \n %s\n\n" %msg))
                        raise ValidationError(_('%s'%msg))

                elif data.status_code == 401:
                    raise ValidationError('Please refresh token first')
            else:
                vals.update({'Name': t.name, 'Status': status})
                parsed_dict = json.dumps(vals)
                url = 'https://api.xero.com/api.xro/2.0/TrackingCategories/{}'.format(t.xero_tracking_id)
                data = self.put_data(url, parsed_dict, post=1)

                if data.status_code == 200:
                    _logger.info(_("'{}' Analytic Account Group Updated Successfully ".format(t.name)))

                elif data.status_code == 400:
                    parsed_error = json.loads(data.text)
                    if parsed_error.get('ErrorNumber') == 10:
                        Error = parsed_error.get('Elements')
                        msg = Error[0].get('ValidationErrors')
                        msg = msg[0].get('Message')

                        _logger.info(_("\n\n\n Error \n %s\n\n" % msg))
                        raise ValidationError(_('%s' % msg))


class AnalyticAccountInherit(models.Model):
    _inherit = 'account.analytic.account'

    xero_tracking_opt_id = fields.Char(string="Xero Tracking Id", copy=False)
    is_active = fields.Boolean(string="Active", default=True)

    def create_analytic_account_in_xero(self, account_id=None):
        if account_id is None:
            if self._context.get('active_ids'):
                account = self.browse(self._context.get('active_ids'))
            else:
                account = self
        else:
            account = self.env['account.analytic.account'].browse(account_id)

        # print(account, '++___________+++++++++___________+++++++++++_________++++++')

        for t in account:
            vals = {}
            if t.is_active:
                status = "ACTIVE"
            else:
                status = "ARCHIVED"

            if not t.xero_tracking_opt_id:
                if t.group_id:
                    groupTrackingId = None
                    obj = self.env['account.analytic.group'].search([('id', '=', t.group_id.id)])
                    if not obj.xero_tracking_id:
                        groupTrackingId = obj.create_analytic_account_group_in_xero(t.group_id)

                    if not groupTrackingId:
                        groupTrackingId = obj.xero_tracking_id

                    vals.update({'Name': t.name, 'Status': status})
                    parsed_dict = json.dumps(vals)

                    url = 'https://api.xero.com/api.xro/2.0/TrackingCategories/{}/Options'.format(groupTrackingId)
                    data = obj.put_data(url, parsed_dict)

                    if data.status_code == 200:
                        parsed_data = json.loads(data.text)
                        if parsed_data:
                            # print("\n\nResponse From Api In Dictionary\n\n\n\n\n : ", data)
                            if parsed_data.get('Options'):
                                t.xero_tracking_opt_id = parsed_data.get(
                                    'Options')[0].get('TrackingOptionID')
                                self._cr.commit()
                                _logger.info(_("(CREATE) Exported successfully to XERO"))

                    elif data.status_code == 401:
                        raise ValidationError('Please Refresh Token First...')
                else:
                    raise ValidationError(_('Please Assign group for %s' % t.name))
            else:
                if t.group_id:
                    obj = self.env['account.analytic.group'].search([('id', '=', t.group_id.id)])
                    vals.update({'Name': t.name, 'Status': status})
                    parsed_dict = json.dumps(vals)
                    url = 'https://api.xero.com/api.xro/2.0/TrackingCategories/{}/Options/{}'.format(
                        obj.xero_tracking_id, t.xero_tracking_opt_id)
                    data = obj.put_data(url, parsed_dict, post=1)
                    # print('\n\n\n___________________________2', url, t.group_id.id, data, data.text)

                    if data.status_code == 200:
                        _logger.info(_('{} Analytic Account Updated Successfully '.format(t.name)))
                    elif data.status_code == 400:
                        parsed_error = json.loads(data.text)
                        if parsed_error.get('ErrorNumber') == 10:
                            Error = parsed_error.get('Elements')
                            msg = Error[0].get('ValidationErrors')
                            msg = msg[0].get('Message')

                            _logger.info(_("\n\n\n Error \n %s\n\n" % msg))
                            raise ValidationError(_('%s' % msg))

