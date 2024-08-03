# -*- coding: utf-8 -*-
{
    'name': "KAT Project  (kat_accounting_report_generator)",

    'summary': """
        KAT Project  (kat_accounting_report_generator)""",

    'description': """
        KAT Project  (kat_accounting_report_generator)
    """,

    'author': "KAT",
    'website': "https://kayanat.net",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/14.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Accounting',
    'version': '14.1.2022.08.01',

    # any module necessary for this one to work correctly
    'depends': ['base', 'account', 'contacts', 'report_xlsx', 'discount_app'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'views/views.xml',
        'views/report.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}
