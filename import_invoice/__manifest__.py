# -*- coding: utf-8 -*-

{
    'name': 'Import Invoices from Excel or CSV File in odoo',
    'version': '14.0.0.3',
    'sequence': 11,
    'category': 'Accounting',
    'summary': 'Import Invoice Data App for import customer invoice import vendor bills import account invoice data import invoices import validate invoice import paid invoice excel import invoice from excel import invoice from csv import mass invoice import bulk invoices',
    'description': """
	
    """,
    'author': 'Kareem Allam',
    'website': '',
    'depends': ['base','account'],
    'data': [
            'security/ir.model.access.csv',  
            'wizard/account_invoice.xml',
            'data/attachment_sample.xml',
        ],
	'qweb': [
		],
    'demo': [],
    'test': [],
    'installable': True,
    'auto_install': False,
    "images":['static/description/Banner.png'],
}
