import base64
import json
from odoo import models, fields, api, _
import requests
from odoo.exceptions import ValidationError
from base64 import b64encode
import logging
from collections import defaultdict

_logger = logging.getLogger(__name__)


class accounut_move(models.Model):
    _inherit = 'account.move'

    eta_invoice_sent = fields.Boolean('Document Sent', copy=False, tracking=True)
    eta_long_id = fields.Char('ETA Long ID', copy=False, tracking=True)
    eta_internal_id = fields.Char('ETA Internal ID', copy=False, tracking=True)
    eta_hash_key = fields.Char('ETA Hash Key', copy=False, tracking=True)
    eta_uuid = fields.Char(string='Document UUID', copy=False, tracking=True)
    eta_submission_id = fields.Char(string='Submission ID', copy=False, tracking=True)
    eta_pdf = fields.Binary(string='ETA PDF Document', copy=False)
    eta_document_name = fields.Char()
    eta_state = fields.Selection([('submitted', 'Submitted'),
                                  ('valid', 'Valid'),
                                  ('invalid', 'Invalid'),
                                  ('rejected', 'Rejected'),
                                  ('cancelled', 'Cancelled')], string='ETA Status', copy=False, tracking=True)
    eta_invoice_signed = fields.Boolean('Document Signed', copy=False, tracking=True)
    use_sign = fields.Boolean(copy=False, compute='_check_use_sign')
    signature_type = fields.Char(string='Signature Type', copy=False, tracking=True)
    signature_value = fields.Text(string='Signatures Value', copy=False)
    sign_button_eta = fields.Selection([('sign', 'sign'),
                                        ('resign', 'resign'),
                                        ('none', 'none')], compute='_compute_show_button_eta', default='none')
    send_button_eta = fields.Selection([('send', 'send'),
                                        ('resend', 'resend'),
                                        ('none', 'none')], compute='_compute_show_button_eta', default='none')
    cancel_button_eta = fields.Selection([('cancel', 'cancel'),
                                          ('none', 'none')], compute='_compute_show_button_eta', default='none')
    error_step = fields.Char(copy=False)
    invalid_error = fields.Char(copy=False, tracking=True)
    issued_date = fields.Datetime(copy=False, tracking=True, default=lambda self: fields.Datetime.now())
    validation_result_id = fields.Many2one('validation.result', 'Validation Result', copy=False)
    client_name = fields.Char("Customer")
    invoice_scope = fields.Selection([('i', 'Individual'),
                                      ('b', 'Business')], default='i')

    document_type = fields.Selection(selection=[('regular', 'Regular'), ('ei', 'Export Invoice')], default='regular',
                                     index=True,
                                     copy=False, required=True)

    service_delivery_date = fields.Date(string="Service Delivery Date", copy=False, tracking=True,
                                        default=fields.Date.context_today)
    purchase_order_ref = fields.Char(string="Purchase Order Reference", copy=False, tracking=True)
    purchase_order_desc = fields.Char(string="Purchase Order Description", copy=False, tracking=True)

    # bank information
    bank_name = fields.Char(string="Bank Name", copy=False, tracking=True)
    bank_address = fields.Char(string="Bank Address", copy=False, tracking=True)
    bank_account_num = fields.Char(string="Bank Account Number", copy=False, tracking=True)
    bank_account_iban = fields.Char(string="Bank Account IBAN", copy=False, tracking=True)
    swift_code = fields.Char(string="Swift Code", copy=False, tracking=True)
    bank_payment_terms = fields.Char(string="Terms", copy=False, tracking=True)

    # Delivery information
    approach = fields.Char(string="Approach", copy=False, tracking=True)
    packaging = fields.Char(string="Packaging", copy=False, tracking=True)
    date_validity = fields.Datetime(copy=False, tracking=True, default=lambda self: fields.Datetime.now())
    export_port = fields.Char(string="Export Port", copy=False, tracking=True)
    country_of_origin = fields.Char(string="Country Of Origin", copy=False, tracking=True)
    gross_weight = fields.Float(string="Gross Weight", copy=False, tracking=True)
    net_weight = fields.Float(string="Net Weight", copy=False, tracking=True)
    delivery_terms = fields.Char(string="Terms", copy=False, tracking=True)

    def test_invoice(self):
        eta_invoice = self._prepare_eta_invoice()
        cc = {
            "documents": [eta_invoice]
        }
        data = json.dumps(cc, ensure_ascii=False, indent=4).encode('utf-8')
        print(eta_invoice)
        print(data)

    def auto_send_invoice_to_eta(self):
        invoice = self.env['account.move'].sudo().search([('eta_invoice_sent', '=', False),
                                                          ('eta_invoice_signed', '=', True),
                                                          ('move_type', 'in', ('out_invoice', 'out_refund')),
                                                          ('state', '=', 'posted')], limit=1)
        if invoice:
            res = invoice.action_send_eta_invoice()

    def action_post(self):
        res = super(accounut_move, self).action_post()
        for move in self:
            if not move.issued_date:
                move.issued_date = fields.Datetime.now()
        return res

    def _compute_show_button_eta(self):
        for invoice in self:
            if invoice.move_type in ['out_invoice', 'out_refund', 'in_refund']:
                if invoice.state == 'posted' and invoice._eta_force_sign() and not invoice.eta_invoice_signed:
                    invoice.sign_button_eta = 'sign'

                elif invoice.state == 'posted' and invoice._eta_force_sign() and invoice.eta_invoice_signed and (
                        not invoice.eta_state or invoice.eta_state in ['invalid', 'rejected']):
                    invoice.sign_button_eta = 'resign'

                else:
                    invoice.sign_button_eta = 'none'

                if invoice.state == 'posted' and (not invoice._eta_force_sign() or (
                        invoice._eta_force_sign() and invoice.eta_invoice_signed)) and not invoice.eta_invoice_sent:
                    invoice.send_button_eta = 'send'

                elif invoice.state == 'posted' and (not invoice._eta_force_sign() or (
                        invoice._eta_force_sign() and invoice.eta_invoice_signed)) and invoice.eta_invoice_sent and invoice.eta_state in [
                    'invalid', 'rejected']:
                    invoice.send_button_eta = 'resend'

                else:
                    invoice.send_button_eta = 'none'

                if invoice.state == 'cancel' and invoice.eta_invoice_sent and invoice.eta_state == 'valid':
                    invoice.cancel_button_eta = 'cancel'

                else:
                    invoice.cancel_button_eta = 'none'
            else:
                invoice.send_button_eta = 'none'
                invoice.sign_button_eta = 'none'
                invoice.cancel_button_eta = 'none'

    def _check_use_sign(self):
        for move in self:
            move.use_sign = move._eta_force_sign()

    def _eta_connection_mode(self):
        params = self.env['ir.config_parameter']
        eta_connection_mode = params.sudo().get_param('eta.connection.mode')
        if not eta_connection_mode:
            raise ValidationError(_('Please select connection mode to ETA first.'))
        return eta_connection_mode

    def _eta_api_domain(self):
        params = self.env['ir.config_parameter']
        eta_connection_mode = self._eta_connection_mode()
        if eta_connection_mode == 'pre':
            api_domain = params.sudo().get_param('default.eta.preproduction.domain')
        else:
            api_domain = params.sudo().get_param('default.eta.production.domain')
        if not api_domain:
            raise ValidationError(_('Please set API domain of ETA first.'))
        print(api_domain)
        return api_domain

    def _eta_token_domain(self):
        params = self.env['ir.config_parameter']
        eta_connection_mode = self._eta_connection_mode()
        if eta_connection_mode == 'pre':
            token_domain = params.sudo().get_param('default.eta.token.preproduction.domain')
        else:
            token_domain = params.sudo().get_param('default.eta.token.production.domain')
        if not token_domain:
            raise ValidationError(_('Please set token domain of ETA first.'))
        return token_domain

    def _eta_force_sign(self):
        params = self.env['ir.config_parameter']
        eta_connection_mode = self._eta_connection_mode()
        eta_force_sign = params.sudo().get_param('eta.force.sign')
        if eta_connection_mode == 'pro' or (eta_connection_mode == 'pre' and eta_force_sign):
            force_sign = True
        else:
            force_sign = False
        return force_sign

    def _get_einvoice_token(self):
        token = False
        user = self.company_id.eta_client_id
        secret = self.company_id.eta_client_secret_1 or self.company_id.eta_client_secret_2
        access = '%s:%s' % (user, secret)
        userAndPass = b64encode(bytes(access, encoding='utf8')).decode("ascii")
        token_domain = self._eta_token_domain()
        request_url = "%s/connect/token" % (token_domain)
        request_payload = {
            "grant_type": "client_credentials",
        }
        headers = {'Authorization': 'Basic ' + userAndPass}
        try:
            request_response = requests.post(request_url, data=request_payload, headers=headers, timeout=None)
            if request_response:
                _logger.warning('%s.' % request_response.text)
                response_data = request_response.json()
                token = response_data.get('access_token')
            return token
        except Exception as ex:
            raise ValidationError(_('action code: 1006 \n%s' % ex))

    def action_send_eta_invoice(self):
        if self.state == 'posted':
            token = self._get_einvoice_token()
            uuid = self._action_send_eta_invoice(token)

            if uuid:
                self.eta_state = False
                self.eta_pdf = False
            return True
        else:
            return False

    def _action_send_eta_invoice(self, token):
        api_domain = self._eta_api_domain()
        request_url = "%s/api/v1/documentsubmissions" % (api_domain)
        eta_invoice = self._prepare_eta_invoice()
        _logger.warning('documents ::: %s.' % eta_invoice)
        request_payload = {
            "documents": [eta_invoice]
        }

        data = json.dumps(request_payload, ensure_ascii=False, indent=4).encode('utf-8')
        error_message = ''
        try:
            headers = {'Content-Type': 'application/json', 'Authorization': 'Bearer %s' % token}
            request_response = requests.post(request_url, data=data, headers=headers, timeout=None)
            _logger.warning('Logger send response: %s.' % request_response)
            submissionData = request_response.json()
            if request_response:
                _logger.warning('Logger send response: %s.' % request_response.text)
            if submissionData:
                if submissionData.get('error'):
                    self._error_handeling(submissionData.get('error'), action_code='1002')

                if submissionData.get('rejectedDocuments', False) and isinstance(
                        submissionData.get('rejectedDocuments'), list):
                    self._error_handeling(submissionData.get('rejectedDocuments')[0].get('error'), action_code='1003')

                if submissionData.get('submissionId') and not submissionData.get('submissionId') is None:
                    if submissionData.get('acceptedDocuments'):
                        self.eta_invoice_sent = True
                        self.eta_submission_id = submissionData.get('submissionId')
                        uuid = submissionData.get('acceptedDocuments')[0].get('uuid')
                        self.eta_uuid = uuid
                        self.eta_long_id = submissionData.get('acceptedDocuments')[0].get('longId')
                        self.eta_internal_id = submissionData.get('acceptedDocuments')[0].get('internalId')
                        self.eta_hash_key = submissionData.get('acceptedDocuments')[0].get('hashKey')
                        return uuid

            return False
        except Exception as ex:
            error_message += '\n' + 'action code: 1007 \n%s' % (ex)

        if error_message != '':
            raise ValidationError(error_message)

    def _get_eta_invoice(self, uuid, token=False):
        api_domain = self._eta_api_domain()
        request_url = "%s/api/v1/documents/%s/raw" % (api_domain, uuid)

        if not token:
            token = self._get_einvoice_token()
        request_payload = {}
        headers = {'Content-Type': 'application/json', 'Authorization': 'Bearer %s' % token}
        try:
            request_response = requests.request("GET", request_url, headers=headers, data=request_payload,
                                                timeout=None)
            if request_response:
                _logger.warning(
                    'GET Document: %s, response code: %s' % (request_response.text, request_response.status_code))
            if request_response.status_code in [404, 200]:
                getInvoiceData = request_response.json()
                return getInvoiceData
            else:
                return {
                    "error": request_response.text
                }
        except Exception as ex:
            return {
                "error": _('Document cannot be reached. \n%s' % ex)
            }

    def _get_eta_invoice_pdf(self, uuid, token=False):
        api_domain = self._eta_api_domain()
        request_url = "%s/api/v1/documents/%s/pdf" % (api_domain, uuid)
        if not token:
            token = self._get_einvoice_token()
        request_payload = {}
        headers = {'Content-Type': 'application/json', 'Authorization': 'Bearer %s' % token}
        try:
            request_response = requests.request("GET", request_url, headers=headers, data=request_payload,
                                                timeout=None)
            _logger.warning('PDF Function Response %s.' % request_response)
            if request_response:
                _logger.warning('PDF Function %s.' % request_response.text)
            if request_response.status_code in [404, 200]:
                getInvoiceData = request_response.content
                return getInvoiceData
            else:
                return {
                    "error": request_response.text
                }
        except Exception as ex:
            return {
                "error": _('PDF Not Reached. \n%s' % ex)
            }

    def _cancel_eta_invoice(self, uuid):
        api_domain = self._eta_api_domain()
        request_url = "%s/api/v1/documents/state/%s/state" % (api_domain, uuid)
        token = self._get_einvoice_token()
        request_payload = {
            "status": "cancelled",
            "reason": "Cancelled"
        }
        data = json.dumps(request_payload)
        headers = {'Content-Type': 'application/json', 'Authorization': 'Bearer %s' % token}
        request_response = requests.request("PUT", request_url, headers=headers, data=data, timeout=None)
        if request_response:
            _logger.warning('%s.' % request_response.text)
        if request_response.status_code in [500, 400, 200]:
            getInvoiceData = request_response.json()
            return getInvoiceData
        else:
            return {
                "error": request_response.text
            }

    def action_post_sign_invoice(self):
        for rec in self:
            if rec.eta_state != 'valid':
                rec.eta_invoice_signed = False
                rec.eta_invoice_sent = False
                rec.eta_pdf = False
                rec.eta_state = False
                rec.signature_type = False
                rec.signature_value = False

    @api.model
    def get_default_sign_host(self):
        params = self.env['ir.config_parameter']
        sign_host = params.sudo().get_param('default.sign.host')
        if not sign_host:
            raise ValidationError(_('Please define the host of sign toll.'))
        return sign_host

    def action_cancel_eta_invoice(self):
        uuid = self.eta_uuid
        invoice = self._cancel_eta_invoice(uuid)
        if invoice is dict and invoice.get('error', False):
            self._error_handeling(invoice.get('error'), action_code='1004')
        else:
            self.eta_state = "cancelled"

    def action_get_eta_invoice_state(self, token=False, eta_uuid=False):
        uuid = eta_uuid
        if not eta_uuid:
            uuid = self.eta_uuid
        _logger.warning('eta_user ::: %s.' % uuid)

        invoice = self._get_eta_invoice(uuid, token)
        _logger.warning('invoices signed ::: %s.' % invoice)

        if invoice.get('status', False) == "Submitted":
            self.eta_state = 'submitted'
        if invoice.get('status', False) == "Invalid":
            self.eta_state = 'invalid'
        if invoice.get('status', False) == "Valid":
            self.eta_state = 'valid'
        if invoice.get('status', False) == "Rejected":
            self.eta_state = 'rejected'
        if invoice.get('status', False) == "Cancelled":
            self.eta_state = 'cancelled'
        if invoice.get('error', False):
            self._error_handeling(invoice.get('error'), action_code='1005')

        if invoice and 'validationResults' in invoice and isinstance(invoice['validationResults'], dict):
            self._set_validation(invoice['validationResults'])

    def action_view_validation_results(self):
        return {
            'name': _('Validation Results Of UUID (%s)' % (self.eta_uuid)),
            'type': 'ir.actions.act_window',
            'res_model': 'validation.result',
            'view_mode': 'form',
            'target': 'new',
            'res_id': self.validation_result_id.id
        }

    def action_update_eta_data(self):
        return {
            'name': _('Invoice (%s)' % (self.name)),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_type': 'form',
            'view_mode': 'form',
            'view_id': self.env.ref('eta_einvoice_integration.view_invoice_update_uuid').id,
            'target': 'new',
            'res_id': self.id
        }

    def _set_validation(self, validation_results):
        validation_steps = []
        if 'validationSteps' in validation_results:
            for validation in validation_results['validationSteps']:
                error = 'No Error'
                if validation['error']:
                    error = '''
                        <div>
                            <ul style="padding:0px;">
                                <li>
                                    <strong>Error Code:</strong> {error_code1}
                                </li>
                                <li>
                                    <strong>Error:</strong> {error1}
                                </li>
                                <li>
                                    <strong>Inner Error:</strong>
                                    <ul>
                                        <li>
                                            <strong>Property Name:</strong> {property_name}
                                        </li>
                                        <li>
                                            <strong>Property Path:</strong> {property_path}
                                        </li>
                                        <li>
                                            <strong>Error Code:</strong> {error_code2}
                                        </li>
                                        <li >
                                            <strong>Error: </strong><span style="white-space: break-spaces;">{error2}</span>
                                        </li>
                                    </ul>
                                </li>
                            </ul>
                        </div>
                    '''.format(
                        error_code1=validation['error']['errorCode'],
                        error1=validation['error']['error'],
                        property_name=validation['error']['innerError'][0]['propertyName'],
                        property_path=validation['error']['innerError'][0]['propertyPath'],
                        error_code2=validation['error']['innerError'][0]['errorCode'],
                        error2=validation['error']['innerError'][0]['error'],
                    )
                validation_steps += [(0, 0, {
                    'name': validation['name'],
                    'status': validation['status'],
                    'error': error,

                })]

        validation_result_id = self.env['validation.result'].create({
            'status': validation_results['status'],
            'validation_steps_line': validation_steps,
            'move_id': self.id,
        })

        if self.validation_result_id:
            self.validation_result_id.unlink()

        self.validation_result_id = validation_result_id.id

    def action_get_eta_invoice_pdf(self, token=False, uuid=False):
        if not uuid:
            uuid = self.eta_uuid
        invoice = self._get_eta_invoice_pdf(uuid, token)
        if isinstance(invoice, dict) and invoice.get('error', False):
            _logger.warning('PDF Content Error:  %s.' % invoice.get('error'))
        else:
            pdf = base64.b64encode(invoice)
            self.eta_pdf = pdf
            self.eta_document_name = "%s.pdf" % self.name.replace('/', '_')

    def _error_handeling(self, error_msg, action_code='1000'):
        _logger.warning('ERROR: %s.' % error_msg)
        invoice = ''
        if isinstance(error_msg, dict):
            message = ''
            propertyPath = ''
            ddetails = ''
            details = error_msg.get('details', False)
            if details and isinstance(details, list) and details[0]:
                message = details[0].get('message', '')
                propertyPath = details[0].get('propertyPath', '')
                ddetails = details[0].get('details', '')
                invoice = self.name
            raise ValidationError(_('Invoice: %s\n action code: %s\n%s. %s \n%s, %s, %s') % (invoice,
                                                                                             action_code,
                                                                                             error_msg.get('code', ''),
                                                                                             error_msg.get('message',
                                                                                                           ''), message,
                                                                                             propertyPath, ddetails))
        else:
            raise ValidationError(_('Invoice: %s\n action code: %s\n %s' % (invoice, action_code, error_msg)))

    def calc_tax_totals(self):
        taxTotals = []
        taxes = []
        for line in self.invoice_line_ids:
            for ts in line.tax_ids:
                amount = (ts.amount * line.price_subtotal) / 100
                amt = self._get_amount(amount)
                tax_line = {
                    "taxType": ts.tax_group_id.tax_type,
                    "amount": abs(amt)
                }
                taxTotals.append(tax_line)

        counts = defaultdict(int)

        for tx in taxTotals:
            counts[tx['taxType']] += tx['amount']
        txs = dict(counts)
        for k, v in txs.items():
            t = {
                "taxType": k,
                "amount": round(v, 5) if not int(v) == float(v) else int(v),
            }
            taxes.append(t)
        print(taxes)
        return taxes

    def calc_totals_amount(self):
        totals = 0
        for line in self.invoice_line_ids:
            totals += self._get_amount(round(self._amount_with_tax(line.price_subtotal, line.tax_ids), 5)) if not int(
                self._get_amount(self._amount_with_tax(line.price_subtotal, line.tax_ids))) == float(
                self._get_amount(self._amount_with_tax(line.price_subtotal, line.tax_ids))) else int(
                self._get_amount(
                    self._amount_with_tax(line.price_subtotal, line.tax_ids)))
        amount_total = round(totals, 5) if not int(totals) == float(totals) else int(totals)

        print(amount_total)
        return amount_total

    def _prepare_eta_invoice(self):
        print(self.calc_tax_totals())
        # total_discount = sum(
        #     [(line.discount / 100.0) * line.quantity * line.price_unit for line in self.invoice_line_ids])
        total_discount = sum([line.discount_value for line in self.invoice_line_ids])
        total_sale_amount = sum([(line.quantity * line.price_unit) for line in self.invoice_line_ids])
        _logger.info('befor date' + str(self.id))
        date_string = self.issued_date.strftime('%Y-%m-%dT%H:%M:%SZ')
        service_delivery_date_string = self.service_delivery_date.strftime("%Y-%m-%d")
        _logger.info('im invoice')
        print(self.calc_totals_amount())
        eta_invoice = {
            "issuer": self._prepare_issuer_data(),
            "receiver": self._prepare_receiver_data(),
            "documentType": "I" if self.move_type == 'out_invoice' and self.document_type == 'regular' else 'EI' if self.move_type == 'out_invoice' and self.document_type == 'ei' else "C" if self.move_type == 'out_refund' else "D" if self.move_type == 'in_refund' else "",
            "documentTypeVersion": "1.0" if self._eta_force_sign() else "0.9",
            "dateTimeIssued": date_string,
            "serviceDeliveryDate": service_delivery_date_string,
            "taxpayerActivityCode": self.company_id.partner_id.eta_activity_type,
            "internalID": self.name,
            "purchaseOrderReference": self.purchase_order_ref or "",
            "purchaseOrderDescription": self.purchase_order_desc or "",
            "salesOrderReference": self.invoice_origin or "",
            "salesOrderDescription": "",
            "proformaInvoiceNumber": "",
        }
        if self.move_type in ['out_refund', 'in_refund']:
            # eta_invoice.update({
            #     'references': [
            #         self.reversed_entry_id.eta_uuid] if self.move_type == 'out_refund' and self.reversed_entry_id and self.reversed_entry_id.eta_uuid else []
            # })
            eta_invoice.update({
                'references': []
            })
            # salestotal if not int(salestotal) == float(salestotal) else int(salestotal)

        eta_invoice.update({
            "payment": self._prepare_payment_data(),
            "delivery": self._prepare_delivery_data(),
            "invoiceLines": self._prepare_invoice_lines_data(),
            "totalDiscountAmount": round(self._get_amount(total_discount), 5) if not int(
                self._get_amount(total_discount)) == float(self._get_amount(total_discount)) else int(
                self._get_amount(total_discount)),
            "totalSalesAmount": round(self._get_amount(total_sale_amount), 5) if not int(
                self._get_amount(total_sale_amount)) == float(self._get_amount(total_sale_amount)) else int(
                self._get_amount(total_sale_amount)),
            "netAmount": round(self._get_amount(self.amount_untaxed), 5) if not int(
                self._get_amount(self.amount_untaxed)) == float(self._get_amount(self.amount_untaxed)) else int(
                self._get_amount(self.amount_untaxed)),
            # "taxTotals": [{
            #     "taxType": self.env['account.tax.group'].browse(tax[6]).tax_type,
            #     "amount": round(self._get_amount(abs(tax[1])), 5) if not int(self._get_amount(abs(tax[1]))) == float(self._get_amount(abs(tax[1]))) else int(self._get_amount(abs(tax[1]))),
            # } for tax in self.amount_by_group],
            "taxTotals": self.calc_tax_totals(),
            # "totalAmount": round(self._get_amount(self.amount_total), 5) if not int(self._get_amount(self.amount_total)) == float(self._get_amount(self.amount_total)) else int(self._get_amount(self.amount_total)),
            "totalAmount": self.calc_totals_amount(),
            "extraDiscountAmount": 0,
            "totalItemsDiscountAmount": 0
        })
        force_sign = self._eta_force_sign()
        if force_sign:
            eta_invoice.update({"signatures": [
                {
                    "signatureType": "I",
                    "value": self.signature_value
                }
            ]})
        print(eta_invoice)
        return eta_invoice

    def _prepare_issuer_data(self):
        company_partner = self.company_id.partner_id
        issuer = {
            "address": {
                "branchID": self.company_id.eta_branch_id,
                "country": company_partner.country_id.code,
                "governate": company_partner.state_id.name,
                "regionCity": company_partner.city,
                "street": company_partner.street,
                "buildingNumber": company_partner.building_no,
                "postalCode": company_partner.zip or "",
                "floor": company_partner.floor or "",
                "room": company_partner.room or "",
                "landmark": company_partner.landmark or "",
                "additionalInformation": company_partner.additional_information or "",
            },
            "type": "B",
            "id": company_partner.eta_code,
            "name": self.company_id.name,
        }
        return issuer

    def _prepare_receiver_data(self):
        if self.invoice_scope == 'b':
            partner = self.partner_id
            receiver = {
                "address": {
                    "country": partner.country_id.code,
                    "governate": partner.state_id.name,
                    "regionCity": partner.city,
                    "street": partner.street,
                    "buildingNumber": partner.building_no,
                    "postalCode": partner.zip or "",
                    "floor": partner.floor or "",
                    "room": partner.room or "",
                    "landmark": partner.landmark or "",
                    "additionalInformation": partner.additional_information or "",
                },
                "type": "B" if partner.company_type == 'company' and partner.country_id.code == 'EG' else "P" if partner.company_type == 'person' and partner.country_id.code == 'EG' else "F",
                "id": partner.eta_code or partner.vat if partner.company_type == 'company' else partner.national_id or partner.vat,
                "name": partner.name,
            }
            return receiver
        if self.invoice_scope == 'i':
            partner = self.partner_id
            receiver = {
                "address": {
                    "country": partner.country_id.code or "",
                    "governate": partner.state_id.name or "",
                    "regionCity": partner.city or "",
                    "street": partner.street or "",
                    "buildingNumber": partner.building_no or "",
                    "postalCode": partner.zip or "",
                    "floor": partner.floor or "",
                    "room": partner.room or "",
                    "landmark": partner.landmark or "",
                    "additionalInformation": partner.additional_information or "",
                },
                "type": "P" if partner.country_id.code == 'EG' or not partner.country_id else "F",
                "id": partner.national_id or "",
                "name": self.client_name.strip() or "",
            }
            return receiver

    def _prepare_payment_data(self):
        # if not self.partner_bank_id:
        #     return {
        #         "bankName": "",
        #         "bankAddress": "",
        #         "bankAccountNo": "",
        #         "bankAccountIBAN": "",
        #         "swiftCode": "",
        #         "terms": ""
        #     }
        # bank = self.partner_bank_id
        payment = {
            "bankName": self.bank_name or "",
            "bankAddress": self.bank_address or "",
            "bankAccountNo": self.bank_account_num or "",
            "bankAccountIBAN": self.bank_account_iban or "",
            "swiftCode": self.swift_code or "",
            "terms": self.bank_payment_terms or "",
        }
        return payment

    def _prepare_delivery_data(self):
        date_string = self.date_validity.strftime('%Y-%m-%dT%H:%M:%SZ')

        delivery = {
            "approach": self.approach or "",
            "packaging": self.packaging or "",
            "dateValidity": date_string,
            "exportPort": self.export_port or "",
            "countryOfOrigin": self.country_of_origin or "",
            "grossWeight": self.gross_weight or 0,
            "netWeight": self.net_weight or 0,
            "terms": self.delivery_terms or ""
        }
        return delivery

    def _prepare_invoice_lines_data(self):
        lines = []
        for line in self.invoice_line_ids:
            # discount = (line.discount / 100.0) * line.quantity * line.price_unit
            lines.append({
                "description": line.name,
                "itemType": line.product_id.item_type if line.product_id.item_type else "GS1",
                "itemCode": line.product_id.item_code,
                "unitType": line.product_uom_id.unit_type,
                "quantity": line.quantity if not int(line.quantity) == float(line.quantity) else int(line.quantity),
                "internalCode": line.product_id.default_code or "",
                # Total amount for the invoice
                # line
                # considering
                # quantity and unit
                # price in EGP(
                # with excluded factory amounts if they are present for specific types in documents).
                "salesTotal": self._get_amount(round((line.quantity * line.price_unit), 5)) if not int(
                    self._get_amount(line.quantity * line.price_unit)) == float(
                    self._get_amount(line.quantity * line.price_unit)) else int(
                    self._get_amount(
                        line.quantity * line.price_unit)),
                "total": self._get_amount(
                    round(self._amount_with_tax(line.price_subtotal, line.tax_ids), 5)) if not int(
                    self._get_amount(self._amount_with_tax(line.price_subtotal, line.tax_ids))) == float(
                    self._get_amount(self._amount_with_tax(line.price_subtotal, line.tax_ids))) else int(
                    self._get_amount(
                        self._amount_with_tax(line.price_subtotal, line.tax_ids))),
                "valueDifference": 0,
                "totalTaxableFees": 0,
                "netTotal": self._get_amount(round(line.price_subtotal, 5)) if not int(
                    self._get_amount(line.price_subtotal)) == float(self._get_amount(line.price_subtotal)) else int(
                    self._get_amount(line.price_subtotal)),
                "itemsDiscount": 0,
                "unitValue": {
                    "currencySold": self.currency_id.name,
                    "amountEGP": self._get_amount(round(line.price_unit, 5)) if not int(
                        self._get_amount(round(line.price_unit, 5))) == float(
                        self._get_amount(round(line.price_unit, 5))) else int(
                        self._get_amount(round(line.price_unit, 5))),
                    "amountSold": (
                        (0 if line.price_unit == self._get_amount(line.price_unit) else round(line.price_unit,
                                                                                              5)) if self.document_type != 'ei' else self._get_amount_for_export(
                            line.price_unit)) if self.currency_id.name != "EGP" else 0,
                    "currencyExchangeRate": 0 if line.price_unit == self._get_amount(
                        line.price_unit) else self._exchange_currency_rate(),
                },
                "discount": {
                    "rate": round(line.discount, 2) if not int(round(line.discount, 2)) == float(
                        line.discount) else int(round(line.discount, 2)),
                    "amount": round(line.discount_value, 5) if not int(round(line.discount_value, 5)) == float(
                        round(line.discount_value, 5)) else int(round(line.discount_value, 5)),
                },
                "taxableItems": [
                    {
                        "taxType": tax.tax_group_id.tax_type,
                        "amount": self._get_amount(
                            round(abs((tax.amount / 100.0) * line.price_subtotal), 5)) if not int(
                            self._get_amount(abs((tax.amount / 100.0) * line.price_subtotal))) == float(
                            self._get_amount(abs((tax.amount / 100.0) * line.price_subtotal))) else int(
                            self._get_amount(abs((tax.amount / 100.0) * line.price_subtotal))),
                        "subType": tax.tax_type,
                        "rate": abs(tax.amount) if not int(abs(tax.amount)) == float(abs(tax.amount)) else int(
                            abs(tax.amount)),
                    } for tax in line.tax_ids
                ],
            })
            if self.document_type == 'ei':
                lines[0].update({
                    "weightUnitType": line.product_uom_id.unit_type,
                    "weightQuantity": round(
                        line.quantity if not int(line.quantity) == float(line.quantity) else int(line.quantity), 1),

                })
        return lines

    def _get_amount(self, amount):
        from_currency = self.currency_id
        to_currency = self.company_id.currency_id
        new_amount = amount
        if from_currency != to_currency:
            new_amount = amount * self._exchange_currency_rate()
        return round(new_amount, 5)

    def _get_amount_for_export(self, amount):
        new_amount = amount
        return round(new_amount, 5)

    def _exchange_currency_rate(self):
        from_currency = self.currency_id
        to_currency = self.company_id.currency_id
        company = self.company_id
        rate = 1.0
        if from_currency != to_currency:
            rate = self.env['res.currency']._get_conversion_rate(from_currency, to_currency, company,
                                                                 self.issued_date)
        return round(rate, 5)

    def _amount_with_tax(self, amount, tax_ids):
        total_amount = amount
        for tax in tax_ids:
            tax_amount = (tax.amount / 100.0) * amount
            total_amount += tax_amount
        return total_amount

    def _validation_msg(self, missing):
        return _('%s is missing.')

    def _sample_invoice(self):
        inv = {
            "issuer": {
                "address": {
                    "branchID": "0",
                    "country": "EG",
                    "governate": "Cairo",
                    "regionCity": "almaza",
                    "street": "el fas5any",
                    "buildingNumber": "8",
                    "postalCode": "12354",
                    "floor": "9",
                    "room": "8",
                    "landmark": "7",
                    "additionalInformation": "6"
                },
                "type": "B",
                "id": "204955823",
                "name": "green"
            },
            "receiver": {
                "address": {
                    "country": "EG",
                    "governate": "Cairo",
                    "regionCity": "gdfgdf",
                    "street": "trtrt",
                    "buildingNumber": "1",
                    "postalCode": "55326",
                    "floor": "2",
                    "room": "2",
                    "landmark": "6",
                    "additionalInformation": "5"
                },
                "type": "B",
                "id": "205087027",
                "name": "el alamya"
            },
            "documentType": "I",
            "documentTypeVersion": "1.0",
            "dateTimeIssued": "2021-05-23T14:56:38Z",
            "taxpayerActivityCode": "2011",
            "internalID": "INV/2021/05/0027",
            "purchaseOrderReference": "",
            "purchaseOrderDescription": "",
            "salesOrderReference": "",
            "salesOrderDescription": "",
            "proformaInvoiceNumber": "",
            "payment": {
                "bankName": "",
                "bankAddress": "",
                "bankAccountNo": "",
                "bankAccountIBAN": "",
                "swiftCode": "",
                "terms": ""
            },
            "delivery": {
                "approach": "",
                "packaging": "",
                "dateValidity": "",
                "exportPort": "",
                "grossWeight": 0,
                "netWeight": 0,
                "terms": ""
            },
            "invoiceLines": [
                {
                    "description": "[96553215] Product x",
                    "itemType": "GS1",
                    "itemCode": "6225000435117",
                    "unitType": "TNE",
                    "quantity": 7.0,
                    "internalCode": "96553215",
                    "salesTotal": 5600.0,
                    "total": 6384.0,
                    "valueDifference": 0,
                    "totalTaxableFees": 0,
                    "netTotal": 5600.0,
                    "itemsDiscount": 0,
                    "unitValue": {
                        "currencySold": "EGP",
                        "amountEGP": 800.0,
                        "amountSold": 0,
                        "currencyExchangeRate": 0
                    },
                    "discount": {
                        "rate": 0,
                        "amount": 0
                    },
                    "taxableItems": [
                        {
                            "taxType": "T1",
                            "amount": 784.0,
                            "subType": "V009",
                            "rate": 14.0
                        }
                    ]
                }
            ],
            "totalDiscountAmount": 0,
            "totalSalesAmount": 5600.0,
            "netAmount": 5600.0,
            "taxTotals": [
                {
                    "taxType": "T1",
                    "amount": 784.0
                }
            ],
            "totalAmount": 6384.0,
            "extraDiscountAmount": 0,
            "totalItemsDiscountAmount": 0
        }

        return inv


class ValidationResult(models.Model):
    _name = 'validation.result'

    status = fields.Char('Status', required=True, readonly=1)
    validation_steps_line = fields.One2many('validation.result.steps', 'validation_result_id', 'Steps', readonly=1)
    move_id = fields.Many2one('account.move', 'Invoice', readonly=1)
    result = fields.Boolean(compute='_compute_result')

    def _compute_result(self):
        for res in self:
            res.result = True if res.status == 'Valid' else False


class ValidationResultSteps(models.Model):
    _name = 'validation.result.steps'

    name = fields.Char('Step', required=True, copy=False)
    status = fields.Char('Status', copy=False)
    error = fields.Html('Error')
    validation_result_id = fields.Many2one('validation.result', 'Validation Result')
