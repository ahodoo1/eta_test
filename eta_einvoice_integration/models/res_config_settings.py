
from odoo import api, fields, models, _


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    eta_connection_mode = fields.Selection([('pre', 'Pre-production'),
                                            ('pro', 'Production')], string='ETA Connection Mode', default='pre')
    eta_force_sign = fields.Boolean('Use Invoice Signature')

    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        params = self.env['ir.config_parameter'].sudo()
        res.update(
            eta_connection_mode=params.get_param('eta.connection.mode'),
            eta_force_sign=params.get_param('eta.force.sign'),
        )
        return res

    def set_values(self):
        super(ResConfigSettings, self).set_values()
        res_config = self.env['ir.config_parameter'].sudo()
        res_config.set_param("eta.connection.mode", self.eta_connection_mode)
        res_config.set_param("eta.force.sign", self.eta_force_sign)
