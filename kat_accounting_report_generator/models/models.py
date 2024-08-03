# -*- coding: utf-8 -*-

from odoo import models, fields, api
from datetime import datetime
from datetime import date
from odoo.exceptions import ValidationError



class TransactionGeneratorWizard(models.TransientModel):
    _name = 'transaction.generator.wizard'
    _description = 'Transaction Generator'

    type = fields.Selection([
        ('invoices', 'Invoices'),
        ('bills', 'Bills')], string='Type')

    from_date = fields.Date('From Date')
    to_date = fields.Date('To Date')
    partner_ids = fields.Many2many(comodel_name="res.partner",
                                    relation="partner_transaction_rel",
                                    column1="patient_id", column2="transaction_id",
                                    string="Partner")
    is_draft = fields.Boolean('Draft')
    is_posted = fields.Boolean('Posted')
    is_cancelled = fields.Boolean('Cancelled')

    @api.model
    def create(self, vals):
        if vals['to_date'] >= vals['from_date']:
            result = super(TransactionGeneratorWizard, self).create(vals)
            return result
        else:
            raise ValidationError("To date must be after from date")


    def action_print_transaction(self):
        domain = []
        type = self.type
        if type == 'invoices':
            domain += [('move_type', '=', 'out_invoice')]
        elif type == 'bills':
            domain += [('move_type', '=', 'in_invoice')]
        from_date = self.from_date
        if from_date:
            domain += [('invoice_date', '>=', from_date)]
        to_date = self.to_date
        if to_date:
            domain += [('invoice_date', '<=', to_date)]
        partner_ids = self.partner_ids
        if partner_ids:
            domain += [('partner_id', 'in', partner_ids.ids)]
        invoice_status = []
        is_draft = self.is_draft
        if is_draft == True:
            invoice_status.append('draft')

        is_posted = self.is_posted
        if is_posted == True:
            invoice_status.append('posted')

        is_cancelled = self.is_cancelled
        if is_cancelled == True:
            invoice_status.append('cancel')
        if invoice_status:
            domain += [('state', 'in', invoice_status)]

        transactions = self.env['account.move'].search_read(domain)
        data = {
            'transactions': transactions
        }
        return self.env.ref('kat_accounting_report_generator.report_transaction_xlsx').report_action(self, data=data)



class TransactionXlsx(models.AbstractModel):
    _name = 'report.kat_accounting_report_generator.transaction_xlsx'
    _inherit = 'report.report_xlsx.abstract'


    def generate_xlsx_report(self, workbook, data, transactions):
        payment_status = {'not_paid': 'Not Paid',
        'in_payment': 'In Payment',
        'paid': 'Paid',
        'partial': 'Partially Paid',
        'reversed': 'Reversed',
        'invoicing_legacy': 'Invoicing App Legacy'}

        tax_groups = self.env['account.tax.group'].search([]).mapped('name')
        sheet = workbook.add_worksheet('Transactions')
        bold = workbook.add_format({'bold': True})
        sheet.set_column('A:A', 20)
        sheet.set_column('B:B', 25)
        sheet.set_column('C:C', 12)
        sheet.set_column('D:D', 12)
        sheet.set_column('E:E', 22)
        sheet.set_column('F:F', 18)
        sheet.set_column('G:G', 15)
        sheet.set_column('H:H', 12)
        sheet.set_column('I:I', 12)
        sheet.set_column('J:J', 12)
        sheet.set_column('K:K', 15)
        sheet.set_column('L:L', 12)
        sheet.set_column('M:M', 20)
        row = 0
        col = 0
        sheet.write(row, col, 'Number', bold)
        sheet.write(row, col + 1, 'Partner', bold)
        sheet.write(row, col + 2, 'Date', bold)
        sheet.write(row, col + 3, 'Due Date', bold)
        sheet.write(row, col + 4, 'Total Before Discount', bold)
        sheet.write(row, col + 5, 'Discount Amount', bold)
        sheet.write(row, col + 6, 'Tax Excluded', bold)
        sheet.write(row, col + 7, 'Total Tax', bold)
        counter = 7
        for n in tax_groups:
            counter = counter + 1
            sheet.write(row, counter, n, bold)
        sheet.write(row, counter + 1, 'Total', bold)
        sheet.write(row, counter + 2, 'Amount Due', bold)
        sheet.write(row, counter + 3, 'Status', bold)
        sheet.write(row, counter + 4, 'Payment status', bold)
        for transaction in data['transactions']:
            tax_groups_dic = {}
            total_tax = 0
            for t in transaction['amount_by_group']:
                tax_groups_dic[t[0]] = t
                total_tax += t[1]

            row += 1
            sheet.write(row, col, transaction['name'])
            sheet.write(row, col + 1, transaction['partner_id'][1])
            sheet.write(row, col + 2, transaction['invoice_date'])
            sheet.write(row, col + 3, transaction['invoice_date_due'])
            sheet.write(row, col + 4, transaction['total_before_discount'])
            sheet.write(row, col + 5, transaction['total_discount'])
            sheet.write(row, col + 6, transaction['amount_untaxed'])
            sheet.write(row, col + 7, total_tax)
            d_counter = 7
            for d in tax_groups:
                d_counter = d_counter + 1

                if d in tax_groups_dic:
                    sheet.write(row, d_counter , tax_groups_dic[d][1])
            sheet.write(row, d_counter + 1, transaction['amount_total'])
            sheet.write(row, d_counter + 2, transaction['amount_total'])
            sheet.write(row, d_counter + 3, transaction['state'])
            sheet.write(row, d_counter + 4, payment_status[transaction['payment_state']])







