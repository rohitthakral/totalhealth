import base64

import requests
import json
import logging
from odoo import http, _
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)


class xero_connector(http.Controller):
    @http.route('/get_auth_code', type="http", auth="public", website=True)
    def get_auth_code(self, **kwarg):
        if kwarg.get('code'):
            # print("\n\nIn controllers code"+ kwarg+ "\n\n\n",kwarg.get('code'))
            access_token_url = 'https://identity.xero.com/connect/token'

            xero_id = http.request.env['res.users'].search([('id', '=', http.request.uid)],limit=1).company_id
            # xero_id.code = kwarg.get('code')
            client_id = xero_id.xero_client_id
            client_secret = xero_id.xero_client_secret
            redirect_uri = xero_id.xero_redirect_url

            # print("base64.b64encode(client_id+""::::::::::::",base64.b64encode(client_id+":"+client_secret))
            data=client_id + ":" + client_secret
            encodedBytes = base64.b64encode(data.encode("utf-8"))
            encodedStr = str(encodedBytes, "utf-8")
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
                'Authorization': "Basic " + encodedStr
            }
            data_token = {
                'code': kwarg.get('code'),
                'redirect_uri': redirect_uri,
                'grant_type': 'authorization_code'
            }
            access_token = requests.post(access_token_url, data=data_token, headers=headers,verify=False)
            # access_token = requests.post(access_token_url, data=data_token, headers=headers)
            if access_token:
                parsed_token_response = json.loads(access_token.text)

                if parsed_token_response:
                    xero_id.write({
                        'xero_oauth_token': parsed_token_response.get('access_token'),
                        'refresh_token_xero': parsed_token_response.get('refresh_token'),
                    })


                header1={
                    'Authorization': "Bearer " + xero_id.xero_oauth_token,
                    'Content-Type': 'application/json'
                        }
                # print("header1:::::::::::::::",header1)

                xero_tenant_response=requests.request('GET','https://api.xero.com/connections', headers=header1)

                parsed_tenent=json.loads(xero_tenant_response.text)

                if parsed_tenent:
                    for tenant in parsed_tenent:
                        if 'tenantId' in tenant:
                            xero_id.xero_tenant_id = tenant.get('tenantId')
                            xero_id.xero_tenant_name = tenant.get('tenantName')
                    _logger.info(_("Authorization successfully!"))

                    country_name = xero_id.import_organization()

                    xero_id.write({
                        'xero_country_name':country_name
                    })

        return "Authenticated Successfully..!! \n You can close this window now"


