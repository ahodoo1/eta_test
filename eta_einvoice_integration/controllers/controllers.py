from odoo import http, _
import json
import logging

_logger = logging.getLogger(__name__)


class EinvoiceIntegration(http.Controller):
    def get_error_msg(self, exception):
        if hasattr(exception, 'name'):
            return exception.name
        elif hasattr(exception, 'content'):
            return exception.content
        elif hasattr(exception, 'args'):
            return exception.args
        elif hasattr(exception, 'pgerror'):
            return exception.pgerror

    @http.route('/api/v1/get_invoices', auth='public', methods=['GET'], csrf=False, cors="*")
    def get_invoices(self, **kwargs):
        try:
            invs = http.request.env['account.move'].sudo().search([('eta_invoice_sent', '=', False),
                                                                   ('eta_invoice_signed', '=', False),
                                                                   ('move_type', 'in', ('out_invoice', 'out_refund')),
                                                                   ('issued_date', '!=', False),
                                                                   ('state', '=', 'posted')])
            if invs:
                invs_list = []
                for inv in invs:
                    invoice = inv._prepare_eta_invoice()
                    if 'signatures' in invoice:
                        invoice.pop("signatures")
                    invs_list.append(invoice)
                data = json.dumps(invs_list, ensure_ascii=False)
                return data.encode('utf-8')
            else:
                return "No Invoice to sign!!"
        except Exception as e:
            return self.get_error_msg(e)

    @http.route('/api/v1/sign_invoices', auth='public', type='json', methods=['POST', 'OPTIONS'], csrf=False, cors="*")
    def sign_invoices(self, **kwargs):
        data = json.loads(http.request.httprequest.data.decode('utf-8'))
        result = "no result"
        if data.get('documents'):
            doc = data.get('documents')
            if len(doc) > 0:
                for d in doc:
                    invoice = http.request.env['account.move'].sudo().search([('name', '=', d.get('internalID'))],limit=1)
                    if invoice:
                        signatures = d.get('signatures')
                        signature = signatures[0]
                        invoice.write({
                            'signature_type': str(signature.get("signatureType")),
                            'signature_value': str(signature.get("value")),
                            'eta_invoice_signed': True,
                        })
                        result = invoice.name + "Signed"
        return result
