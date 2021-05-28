from odoo import models, fields, api,_
from odoo.exceptions import ValidationError
import requests
import base64
import json
import logging
_logger = logging.getLogger(__name__)

class ContactGroup(models.Model):
    _inherit = 'res.partner.category'

    xero_contact_group_id = fields.Char(string="Xero Contact Group Id",copy=False)

    @api.model
    def prepare_contact_group_export_dict(self):
        """Create Dictionary to export to XERO"""
        vals = {}
        if self.active:
            if self.active == True:
                vals.update({
                    'Status': 'ACTIVE',
                })
        if self.name:
            vals.update({
                'Name': self.name,
            })
        return vals

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
    def create_contact_group_in_xero(self):
        """export accounts to XERO"""
        xero_config = self.env['res.users'].search([('id', '=', self._uid)], limit=1).company_id
        if self._context.get('active_ids'):
            group = self.browse(self._context.get('active_ids'))
        else:
            group = self

        for a in group:
            if not a.xero_contact_group_id:
                vals = a.prepare_contact_group_export_dict()
                parsed_dict = json.dumps(vals)

                if xero_config.xero_oauth_token:
                    token = xero_config.xero_oauth_token

                headers=self.get_head()
                if token:
                    protected_url = 'https://api.xero.com/api.xro/2.0/ContactGroups'

                    data = requests.request('POST', url=protected_url, data=parsed_dict, headers=headers)
                    # print("DATA : ", data, data.text)
                    if data.status_code == 200:

                        response_data = json.loads(data.text)
                        if response_data.get('ContactGroups')[0].get('ContactGroupID'):
                            # update xero tag id
                            a.xero_contact_group_id = response_data.get('ContactGroups')[0].get('ContactGroupID')
                            _logger.info(_("(CREATE) - Exported successfully to XERO"))
                    elif data.status_code == 401:
                        raise ValidationError("Time Out.\nPlease Check Your Connection or error in application or refresh token..!!")
                    else:
                        logs = self.env['xero.error.log'].create({
                            'transaction': 'ContactGroup Export',
                            'xero_error_response': data.text,
                            'error_date': fields.datetime.now(),
                            'record_id': a,
                        })
                        self._cr.commit()
                else:
                    raise ValidationError("Please Check Your Connection or error in application or refresh token..!!")
            else:
                vals = a.prepare_contact_group_export_dict()
                parsed_dict = json.dumps(vals)

                if xero_config.xero_oauth_token:
                    token = xero_config.xero_oauth_token
                headers = self.get_head()

                if token:
                    client_key = xero_config.xero_client_id
                    client_secret = xero_config.xero_client_secret
                    resource_owner_key = xero_config.xero_oauth_token
                    resource_owner_secret = xero_config.xero_oauth_token_secret

                    protected_url_2 = 'https://api.xero.com/api.xro/2.0/ContactGroups/'+a.xero_contact_group_id
                    data = requests.request('POST', url=protected_url_2, data=parsed_dict, headers=headers)
                    # print("DATA : ", data, data.text)
                    if data.status_code == 200:
                       _logger.info(_("(UPDATE) - Exported successfully to XERO"))

                    elif data.status_code == 401:
                        raise ValidationError("Time Out.\nPlease Check Your Connection or error in application or refresh token..!!")
                    else:
                        logs = self.env['xero.error.log'].create({
                            'transaction': 'ContactGroups Export',
                            'xero_error_response': data.text,
                            'error_date': fields.datetime.now(),
                            'record_id': a,
                        })
                        self._cr.commit()
                else:
                    raise ValidationError("Please Check Your Connection or refresh token..!!")
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