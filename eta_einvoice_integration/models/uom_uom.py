
from odoo import models, fields, api


class uom_uom(models.Model):
    _inherit = 'uom.uom'

    unit_type = fields.Char(string='ETA Unit Code', help='This is the type of unit according to egyptian tax authority')
