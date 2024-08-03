
from odoo import models, fields, api


class res_partner(models.Model):
    _inherit = 'res.company'

    eta_client_id = fields.Char('ETA Client ID')
    eta_client_secret_1 = fields.Char('ETA Client Secret 1')
    eta_client_secret_2 = fields.Char('ETA Client Secret 2')
    eta_code = fields.Char('ETA Code (TAX ID)', related='partner_id.eta_code', readonly=False,
                           help='This is the code (TAX ID) of your eta account according to egyptian tax authority')
    eta_activity_type = fields.Char('ETA Activity Code', related='partner_id.eta_activity_type', readonly=False,
                                    help='This is the activity type of partner according to egyptian tax authority')
    eta_branch_id = fields.Char('ETA Branch ID')

    # partner fields
    building_no = fields.Char('Building No.', related='partner_id.building_no', readonly=False)
    floor = fields.Char('Floor', related='partner_id.floor', readonly=False)
    room = fields.Char('Room', related='partner_id.room', readonly=False)
    landmark = fields.Char('Landmark', related='partner_id.landmark', readonly=False)
    additional_information = fields.Char('Additional Information', related='partner_id.additional_information',
                                         readonly=False)
