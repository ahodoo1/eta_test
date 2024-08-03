# -*- coding: utf-8 -*-
{
    'name': "E-Invoice Integration",
    'summary': """
            Egyptian Tax Authority Invoice Integration
        """,
    'description': """
       This module integrate with the ETA Portal to automatically sign and send your invoices to the tax Authority.
    """,
    'author': 'Ahmed Amen',
    'category': 'account',
    'version': '0.1',
    'depends': ['base', 'account'],
    'data': [
        'security/ir.model.access.csv',
        'data/data.xml',
        'views/account_tax_view.xml',
        'views/product_template_view.xml',
        'views/res_company_view.xml',
        'views/res_config_settings_view.xml',
        'views/res_partner_view.xml',
        'views/uom_uom_view.xml',
        'views/account_move_view.xml',
    ],
}
