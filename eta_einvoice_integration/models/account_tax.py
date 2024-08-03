
from odoo import models, fields, api


class accounut_tax(models.Model):
    _inherit = 'account.tax'

    tax_type = fields.Char(string='ETA Tax Code', help='This is the type of tax according to egyptian tax authority')


class accounut_tax_group(models.Model):
    _inherit = 'account.tax.group'

    tax_type = fields.Char(string='ETA Tax Code',
                           help='This is the type of tax group (Parent) according to egyptian tax authority')
