# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    discount_value = fields.Float(digits='Product Price', compute="compute_discount_value")

    @api.depends('discount', 'price_unit', 'quantity')
    def compute_discount_value(self):
        for rec in self:
            rec.discount_value = 0
            if rec.discount > 0 and rec.price_unit > 0 and rec.quantity > 0:
                rec.discount_value = (rec.price_unit * rec.quantity * rec.discount) /100


class AccountMove(models.Model):
    _inherit = 'account.move'

    discount_type = fields.Selection(string="Type", selection=[('per', 'Percent'), ('val', 'Value')], default='per')
    discount_amount = fields.Float(digits='Product Price')
    discount_percent = fields.Float(digits='Product Price')
    total_before_discount = fields.Float(digits='Product Price', compute="_compute_total_before_discount")
    total_discount = fields.Float(digits='Product Price', compute="_compute_total_before_discount")

    @api.depends('amount_untaxed', 'total_discount', 'invoice_line_ids.discount')
    def _compute_total_before_discount(self):
        for rec in self:
            total_discount = 0
            for line in rec.invoice_line_ids:
                total_discount += ((line.quantity * line.price_unit) * line.discount) / 100
            rec.total_before_discount = total_discount + rec.amount_untaxed
            rec.total_discount = total_discount

    @api.onchange('percent_type', 'discount_amount', 'discount_percent', 'invoice_line_ids')
    def onchange_percent_type(self):
        for rec in self:
            if len(rec.invoice_line_ids) > 0:
                print('yes')
                if rec.discount_type == 'per':
                    disc_amount = 0
                    if rec.discount_percent > 100 or rec.discount_percent < 0:
                        raise UserError(_("Discount Percent Not Valid"))
                    discount = rec.discount_percent
                    for line in rec.invoice_line_ids:
                        line.discount = discount
                        line.recompute_tax_line = True
                        disc_amount += ((line.price_unit * line.quantity) * line.discount) /100
                        line._onchange_price_subtotal()
                        line._get_price_total_and_subtotal()
                    rec._onchange_recompute_dynamic_lines()
                    rec._recompute_dynamic_lines(recompute_tax_base_amount=True)
                    rec.discount_amount = disc_amount
                if rec.discount_type == 'val':
                    if rec.discount_amount < 0:
                        raise UserError(_("Discount Percent Not Valid"))
                    discount = (rec.discount_amount / rec.amount_total) * 100
                    for line in rec.invoice_line_ids:
                        line.discount = discount
                        line.recompute_tax_line = True
                        line._onchange_price_subtotal()
                        line._get_price_total_and_subtotal()
                    rec._onchange_recompute_dynamic_lines()
                    rec._recompute_dynamic_lines(recompute_tax_base_amount=True)
                    rec.discount_percent = discount
                    rec._onchange_recompute_dynamic_lines()

    @api.depends(
        'discount_amount',
        'discount_percent',
        'line_ids.matched_debit_ids.debit_move_id.move_id.payment_id.is_matched',
        'line_ids.matched_debit_ids.debit_move_id.move_id.line_ids.amount_residual',
        'line_ids.matched_debit_ids.debit_move_id.move_id.line_ids.amount_residual_currency',
        'line_ids.matched_credit_ids.credit_move_id.move_id.payment_id.is_matched',
        'line_ids.matched_credit_ids.credit_move_id.move_id.line_ids.amount_residual',
        'line_ids.matched_credit_ids.credit_move_id.move_id.line_ids.amount_residual_currency',
        'line_ids.debit',
        'line_ids.credit',
        'line_ids.currency_id',
        'line_ids.amount_currency',
        'line_ids.amount_residual',
        'line_ids.amount_residual_currency',
        'line_ids.payment_id.state',
        'line_ids.full_reconcile_id')
    def _compute_amount(self):
        for move in self:
            print('rererere')
            if move.payment_state == 'invoicing_legacy':
                # invoicing_legacy state is set via SQL when setting setting field
                # invoicing_switch_threshold (defined in account_accountant).
                # The only way of going out of this state is through this setting,
                # so we don't recompute it here.
                move.payment_state = move.payment_state
                continue

            total_untaxed = 0.0
            total_untaxed_currency = 0.0
            total_tax = 0.0
            total_tax_currency = 0.0
            total_to_pay = 0.0
            total_residual = 0.0
            total_residual_currency = 0.0
            total = 0.0
            total_currency = 0.0
            currencies = move._get_lines_onchange_currency().currency_id

            for line in move.line_ids:
                if move.is_invoice(include_receipts=True):
                    # === Invoices ===

                    if not line.exclude_from_invoice_tab:
                        # Untaxed amount.
                        total_untaxed += line.balance
                        total_untaxed_currency += line.amount_currency
                        total += line.balance
                        total_currency += line.amount_currency
                    elif line.tax_line_id:
                        # Tax amount.
                        total_tax += line.balance
                        total_tax_currency += line.amount_currency
                        total += line.balance
                        total_currency += line.amount_currency
                    elif line.account_id.user_type_id.type in ('receivable', 'payable'):
                        # Residual amount.
                        total_to_pay += line.balance
                        total_residual += line.amount_residual
                        total_residual_currency += line.amount_residual_currency
                else:
                    # === Miscellaneous journal entry ===
                    if line.debit:
                        total += line.balance
                        total_currency += line.amount_currency

            if move.move_type == 'entry' or move.is_outbound():
                sign = 1
            else:
                sign = -1
            move.amount_untaxed = sign * (total_untaxed_currency if len(currencies) == 1 else total_untaxed)
            move.amount_tax = sign * (total_tax_currency if len(currencies) == 1 else total_tax)
            move.amount_total = sign * (total_currency if len(currencies) == 1 else total)
            move.amount_residual = -sign * (total_residual_currency if len(currencies) == 1 else total_residual)
            move.amount_untaxed_signed = -total_untaxed
            move.amount_tax_signed = -total_tax
            move.amount_total_signed = abs(total) if move.move_type == 'entry' else -total
            move.amount_residual_signed = total_residual

            currency = len(currencies) == 1 and currencies or move.company_id.currency_id

            # Compute 'payment_state'.
            new_pmt_state = 'not_paid' if move.move_type != 'entry' else False

            if move.is_invoice(include_receipts=True) and move.state == 'posted':

                if currency.is_zero(move.amount_residual):
                    reconciled_payments = move._get_reconciled_payments()
                    if not reconciled_payments or all(payment.is_matched for payment in reconciled_payments):
                        new_pmt_state = 'paid'
                    else:
                        new_pmt_state = move._get_invoice_in_payment_state()
                elif currency.compare_amounts(total_to_pay, total_residual) != 0:
                    new_pmt_state = 'partial'

            if new_pmt_state == 'paid' and move.move_type in ('in_invoice', 'out_invoice', 'entry'):
                reverse_type = move.move_type == 'in_invoice' and 'in_refund' or move.move_type == 'out_invoice' and 'out_refund' or 'entry'
                reverse_moves = self.env['account.move'].search(
                    [('reversed_entry_id', '=', move.id), ('state', '=', 'posted'), ('move_type', '=', reverse_type)])

                # We only set 'reversed' state in cas of 1 to 1 full reconciliation with a reverse entry; otherwise, we use the regular 'paid' state
                reverse_moves_full_recs = reverse_moves.mapped('line_ids.full_reconcile_id')
                if reverse_moves_full_recs.mapped('reconciled_line_ids.move_id').filtered(lambda x: x not in (
                        reverse_moves + reverse_moves_full_recs.mapped('exchange_move_id'))) == move:
                    new_pmt_state = 'reversed'

            move.payment_state = new_pmt_state

