import base64
from odoo import models, fields, api,_
from odoo.exceptions import ValidationError
import requests
import json
import logging
_logger = logging.getLogger(__name__)

class Customer(models.Model):
    _inherit = 'res.partner'

    xero_cust_id = fields.Char('Xero Customer Id',copy=False)

    # @api.model
    # def create(self, vals):
    #     res = super(Customer, self).create(vals)
    #     # print("\n\n\nRES : ------------> ",res)
    #     return res

    @api.model
    def get_xero_partner_ref(self, partner):
        xero_config = self.env['res.users'].search([('id', '=', self._uid)], limit=1).company_id

        if partner:
            if partner.xero_cust_id or (partner.parent_id and partner.parent_id.xero_cust_id):
                return partner.xero_cust_id or partner.parent_id.xero_cust_id
            else:
                self.create_main_customer_in_xero(partner,xero_config)
                if partner.xero_cust_id or (partner.parent_id and partner.parent_id.xero_cust_id):
                    return partner.xero_cust_id or partner.parent_id.xero_cust_id
        else:

            if partner.xero_cust_id or (partner.parent_id and partner.parent_id.xero_cust_id):
                return partner.xero_cust_id or partner.parent_id.xero_cust_id
            else:
                self.create_main_customer_in_xero(partner,xero_config)
                if partner.xero_cust_id or (partner.parent_id and partner.parent_id.xero_cust_id):
                    return partner.xero_cust_id or partner.parent_id.xero_cust_id

    @api.model
    def prepare_customer_export_dict(self):
        company = self.env['res.users'].search([('id', '=', self._uid)], limit=1).company_id

        if self:

            ''' This Function Exports Record to Quickbooks '''
            dict = {}
            dict_contact = {}
            con_list = []
            final_dict = {}
            del_add_dict = {}
            bill_add_dict = {}
            phone_dict = {}
            final_dict = {}
            final_list = []
            con_dict = {}
            mobile_dict = {}

            if self.name:
                dict['Name'] = self.name
            #                 dict['firstName']= 'firstname'
            #                 dict['LastName']= 'Lastname'
            # if self.email:
            #     dict['EmailAddress'] = self.email and self.email.split(",")[0]
            #     _logger.info("\nEmail Address : %s", self.email)

            # if self.id:
            #     dict['ContactNumber'] = self.id

            # if self.supplier:
            #     dict['IsSupplier'] = True
            # if self.customer:
            #     dict['IsCustomer'] = True

            # if self.id:

            #     billing_addr = self.search([('parent_id', '=', self.id), ('type', '=', 'invoice'),('company_id','=',company.id)])

            #     if billing_addr:
            #         bill_add_dict['AddressType'] = "POBOX"
            #         if billing_addr.street:
            #             bill_add_dict.update({'AddressLine1': billing_addr.street})
            #         if billing_addr.street2:
            #             bill_add_dict.update({'AddressLine2': billing_addr.street2})
            #         if billing_addr.city:
            #             bill_add_dict.update({'City': billing_addr.city})
            #         if billing_addr.zip:
            #             bill_add_dict.update({'PostalCode': billing_addr.zip})
            #         if billing_addr.state_id:
            #             bill_add_dict.update({'Region': billing_addr.state_id.name})
            #         else:
            #             bill_add_dict.update({'Region': ''})
            #         if billing_addr.country_id:
            #             country_id = self.env['res.country'].search([('id', '=', billing_addr.country_id.id)])
            #             if country_id:
            #                 bill_add_dict.update({'Country': country_id.name})

            #     delivery_addr = self.search([('parent_id', '=', self.id), ('type', '=', 'delivery'),('company_id','=',company.id)])
            #     if delivery_addr:
            #         del_add_dict['AddressType'] = "STREET"
            #         if delivery_addr.street:
            #             del_add_dict.update({'AddressLine1': delivery_addr.street})
            #         if delivery_addr.street2:
            #             del_add_dict.update({'AddressLine2': delivery_addr.street2})
            #         if delivery_addr.city:
            #             del_add_dict.update({'City': delivery_addr.city})
            #         if delivery_addr.zip:
            #             del_add_dict.update({'PostalCode': delivery_addr.zip})
            #         if delivery_addr.state_id:
            #                 del_add_dict.update({'Region': delivery_addr.state_id.name})
            #         else:
            #             del_add_dict.update({'Region': ''})
            #         if delivery_addr.country_id:
            #             country_id = self.env['res.country'].search([('id', '=', delivery_addr.country_id.id)])
            #             if country_id:
            #                 del_add_dict.update({'Country': country_id.name})

            #     if (not delivery_addr) and (not billing_addr):
            #         del_add_dict['AddressType'] = "STREET"
            #         bill_add_dict['AddressType'] = "POBOX"
            #         if self.street:
            #             del_add_dict.update({'AddressLine1': self.street})
            #             bill_add_dict.update({'AddressLine1': self.street})
            #         if self.street2:
            #             del_add_dict.update({'AddressLine2': self.street2})
            #             bill_add_dict.update({'AddressLine2': self.street2})
            #         if self.city:
            #             del_add_dict.update({'City': self.city})
            #             bill_add_dict.update({'City': self.city})
            #         if self.zip:
            #             del_add_dict.update({'PostalCode': self.zip})
            #             bill_add_dict.update({'PostalCode': self.zip})
            #         if self.state_id:
            #             del_add_dict.update({'Region': self.state_id.name})
            #             bill_add_dict.update({'Region': self.state_id.name})
            #         else:
            #             del_add_dict.update({'Region': ''})
            #             bill_add_dict.update({'Region': ''})
            #         if self.country_id:
            #             del_add_dict.update({'Country': self.country_id.name})
            #             bill_add_dict.update({'Country': self.country_id.name})

            # list_address = []
            # list_address.append(del_add_dict)
            # list_address.append(bill_add_dict)
            # dict.update({"Addresses": list_address})

            # if self.phone:
            #     phone_dict.update({'PhoneType': "DEFAULT"})
            #     phone_dict.update({'PhoneNumber': self.phone})
            # if self.mobile:
            #     mobile_dict.update({'PhoneType': "MOBILE"})
            #     mobile_dict.update({'PhoneNumber': self.mobile})
            # list_phone = []
            # list_phone.append(phone_dict)
            # list_phone.append(mobile_dict)
            # dict.update({'Phones': list_phone})

            # contacts = self.search([('parent_id', '=', self.id), ('type', '=', 'contact'),('company_id','=',company.id)],limit=5)

            # if contacts:
            #     for con in contacts:
            #         fname = ''
            #         lname = ''
            #         if con.name:
            #             txt = con.name
            #             x = txt.split()
            #             if len(x) == 2:
            #                 fname = x[0]
            #                 lname = x[1]
            #             elif len(x) == 1:
            #                 fname = x[0]
            #                 lname = ''
            #             elif len(x) > 2:
            #                 fname = con.name
            #                 lname = ''
            #         if con.email:
            #             email = con.email

            #             con_dict = {
            #                 'FirstName': fname,
            #                 'LastName': lname,
            #                 'EmailAddress': email
            #             }

            #             con_list.append(con_dict)
            #     dict.update({'ContactPersons': con_list})

            # bills = {}
            # if self.property_supplier_payment_term_id:
            #     line_ids = self.property_supplier_payment_term_id.line_ids[0]
            #     if line_ids.option == 'day_after_invoice_date':
            #         type = 'DAYSAFTERBILLDATE'
            #     if line_ids.option == 'after_invoice_month':
            #         type = 'DAYSAFTERBILLMONTH'
            #     if line_ids.option == 'day_current_month':
            #         type = 'OFCURRENTMONTH'
            #     if line_ids.option == 'day_following_month':
            #         type = 'OFFOLLOWINGMONTH'
            #     bills = {
            #             "Day": line_ids.days,
            #             "Type": type
            #             }
            # sales = {}
            # if self.property_payment_term_id:
            #     line_ids = self.property_payment_term_id.line_ids[0]
            #     if line_ids.option == 'day_after_invoice_date':
            #         type = 'DAYSAFTERBILLDATE'
            #     if line_ids.option == 'after_invoice_month':
            #         type = 'DAYSAFTERBILLMONTH'
            #     if line_ids.option == 'day_current_month':
            #         type = 'OFCURRENTMONTH'
            #     if line_ids.option == 'day_following_month':
            #         type = 'OFFOLLOWINGMONTH'
            #     sales = {
            #         "Day": line_ids.days,
            #         "Type": type
            #     }

            # if self.property_supplier_payment_term_id or self.property_payment_term_id:
            #     dict.update({
            #         "PaymentTerms": {
            #             "Bills": bills,
            #             "Sales": sales
            #         }
            #     })

            final_list.append(dict)
            final_dict.update({'Contacts': final_list})
            return final_dict

    @api.model
    def create_customer_in_xero(self):
        """export Customers to XERO"""
        xero_config = self.env['res.users'].search([('id', '=', self._uid)], limit=1).company_id
        if self._context.get('active_ids'):
            partner = self.browse(self._context.get('active_ids'))
        else:
            partner = self

        for con in partner:
            self.create_main_customer_in_xero(con,xero_config)
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
        client_id=xero_config.xero_client_id
        client_secret=xero_config.xero_client_secret

        data = client_id + ":" + client_secret
        encodedBytes = base64.b64encode(data.encode("utf-8"))
        encodedStr = str(encodedBytes, "utf-8")
        headers = {
            'Authorization': "Bearer " + str(xero_config.xero_oauth_token),
            'Xero-tenant-id' : xero_config.xero_tenant_id,
            'Accept': 'application/json'

        }
        return headers





    @api.model
    def create_main_customer_in_xero(self,con,xero_config):
            if con:
                vals = con.prepare_customer_export_dict()
                parsed_dict = json.dumps(vals)
                token = ''
                if xero_config.xero_oauth_token:
                    token = xero_config.xero_oauth_token

                if not token:
                    raise ValidationError('Token not found,Authentication Unsuccessful Please check your connection!!')

                headers=self.get_head()

                if token:
                    protected_url = 'https://api.xero.com/api.xro/2.0/Contacts'
                    data = requests.request('POST', url=protected_url, data=parsed_dict ,headers=headers)
                    if data.status_code == 200:

                        response_data = json.loads(data.text)
                        if response_data.get('Contacts'):
                                con.xero_cust_id = response_data.get('Contacts')[0].get('ContactID')
                                _logger.info("\nExported Contact : %s %s", con,con.name)
                                child_ids_all = self.search(
                                    [('parent_id', '=', con.id), ('company_id', '=', xero_config.id)])
                                if child_ids_all:
                                    for child in child_ids_all:
                                        child.xero_cust_id = ''

                                child_ids = self.search([('parent_id', '=', con.id),('company_id','=',xero_config.id)],limit=5)
                                if child_ids:
                                    for child in child_ids:
                                        child.xero_cust_id = response_data.get('Contacts')[0].get('ContactID')
                                        _logger.info("\nExported Sub-Contact : %s %s", child,child.name)

                    elif data.status_code == 400:
                        logs = self.env['xero.error.log'].create({
                            'transaction': 'Contact Export',
                            'xero_error_response': data.text,
                            'error_date': fields.datetime.now(),
                            'record_id': con,
                        })
                        self._cr.commit()
                        response_data = json.loads(data.text)
                        if response_data:
                            if response_data.get('Elements'):
                                for element in response_data.get('Elements'):
                                    if element.get('ValidationErrors'):
                                        for err in element.get('ValidationErrors'):
                                            raise ValidationError('(Contacts) Xero Exception : ' + err.get('Message'))
                            elif response_data.get('Message'):
                                raise ValidationError(
                                    '(Contacts) Xero Exception : ' + response_data.get('Message'))
                            else:
                                raise ValidationError(
                                    '(Contacts) Xero Exception : please check xero logs in odoo for more details')

                    elif data.status_code == 401:
                        raise ValidationError("Time Out.\nPlease Check Your Connection or error in application or refresh token..!!")
