# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from decimal import Decimal

from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction

__all__ = ['Sale', 'Move', 'Line']
__metaclass__ = PoolMeta
_ZERO = Decimal('0.0')


class Sale:
    __name__ = 'sale.sale'

    @classmethod
    def __setup__(cls):
        super(Sale, cls).__setup__()
        cls._error_messages.update({
                'no_pending_invoice_account': ('There is no Pending Invoice '
                    'Account Defined. Please define one in sale '
                    'configuration.'),
                })

    @classmethod
    def process(cls, sales):
        super(Sale, cls).process(sales)
        for sale in sales:
            if sale.invoice_method not in ['manual', 'order']:
                with Transaction().set_user(0, set_context=True):
                    sale.create_account_move()
                    sale.reconcile_moves()

    def create_account_move(self):
        "Creates account move for not invoiced shipments"
        pool = Pool()
        Move = pool.get('account.move')
        Config = pool.get('sale.configuration')
        config = Config(1)
        if not config.pending_invoice_account:
            self.raise_user_error('no_pending_invoice_account')

        if (self._get_shipment_amount() - self._get_accounting_amount() !=
                _ZERO):
            move = self._get_account_move()
            if move:
                move.save()
                Move.post([move])

    def reconcile_moves(self):
        "Reconciles account moves if sale is finished"
        pool = Pool()
        Move = pool.get('account.move')
        Line = pool.get('account.move.line')
        Config = pool.get('sale.configuration')

        config = Config(1)
        invoiced = self._get_invoiced_amount()
        invoiced_amount = sum(invoiced.values(), _ZERO)

        to_reconcile = Line.search([
                    ('move.origin', '=', str(self)),
                    ('account', '=', config.pending_invoice_account),
                    ('reconciliation', '=', None),
                    ])
        if invoiced_amount == _ZERO or not to_reconcile:
            return

        move = self._get_reconcile_move()
        move_lines = []
        total_invoiced_amount = _ZERO
        #One line for each sale line
        for sale_line, invoice_amount in invoiced.iteritems():
            line = Line()
            line.account = sale_line.product.account_revenue_used
            if line.account.party_required:
                line.party = self.party
            if invoice_amount > _ZERO:
                line.debit = invoice_amount
                line.credit = _ZERO
            else:
                line.credit = abs(invoice_amount)
                line.debit = _ZERO
            line.sale_line = sale_line
            self._set_analytic_lines(line, sale_line)
            move_lines.append(line)
            total_invoiced_amount += invoice_amount

        amount = sum(l.debit - l.credit for l in to_reconcile)
        line = Line()
        line.account = config.pending_invoice_account
        if line.account.party_required:
            line.party = self.party
        if amount > Decimal('0.0'):
            line.credit = amount
        else:
            line.debit = abs(amount)
        line.reconciliation = None
        move.lines = [line]
        move.save()
        #Reload in order to get the id and make reconcile work.
        line, = move.lines
        to_reconcile.append(line)

        pending_amount = amount - total_invoiced_amount
        line = Line()
        line.account = config.pending_invoice_account
        if line.account.party_required:
            line.party = self.party
        if pending_amount > Decimal('0.0'):
            line.debit = pending_amount
        else:
            line.credit = abs(pending_amount)
        move_lines.append(line)
        move.lines += tuple(move_lines)

        move.save()
        Move.post([move])
        Line.reconcile(to_reconcile)

    def _get_shipment_quantity(self):
        "Returns the shipped quantity grouped by sale_line"
        pool = Pool()
        Uom = pool.get('product.uom')
        ret = {}
        for line in self.lines:
            if not line.product or line.product.type == 'service':
                continue
            skip_ids = set(x.id for x in line.moves_ignored)
            skip_ids.update(x.id for x in line.moves_recreated)
            sign = -1 if line.quantity < 0.0 else 1
            for move in line.moves:
                if move.state != 'done' \
                        and move.id not in skip_ids:
                    continue
                quantity = Uom.compute_qty(move.uom, move.quantity, line.unit)
                quantity *= sign
                if line in ret:
                    ret[line] += quantity
                else:
                    ret[line] = quantity
        return ret

    def _get_shipment_amount(self):
        "Returns the total shipped amount"
        pool = Pool()
        Currency = pool.get('currency.currency')
        amount = _ZERO
        for line, quantity in self._get_shipment_quantity().iteritems():
            amount += Currency.compute(self.company.currency,
                Decimal(quantity) * line.unit_price, self.currency)
        return amount

    def _get_accounting_amount(self):
        "Returns the amount in accounting for this sale"
        pool = Pool()
        Line = pool.get('account.move.line')
        Config = pool.get('sale.configuration')

        config = Config(1)

        lines = Line.search([
                ('move.origin', '=', str(self)),
                ('account', '=', config.pending_invoice_account),
                ])
        if not lines:
            return Decimal('0.0')
        return sum(l.debit - l.credit for l in lines)

    def _get_invoiced_amount(self):
        " Returns the invoiced amount grouped by account"
        skip_ids = set(x.id for x in self.invoices_ignored)
        skip_ids.update(x.id for x in self.invoices_recreated)
        moves = [i.move for i in self.invoices if i.id not in skip_ids
            and i.move]

        ret = {}
        for sale_line in self.lines:
            for invoice_line in sale_line.invoice_lines:
                if (invoice_line.invoice and invoice_line.invoice.move and
                        invoice_line.invoice.move in moves):
                    amount = invoice_line.amount
                    if 'credit_note' in invoice_line.invoice_type:
                        amount = amount.copy_negate()
                    if sale_line in ret:
                        ret[sale_line] += amount
                    else:
                        ret[sale_line] = amount
        return ret

    def _get_accounting_journal(self):
        pool = Pool()
        Journal = pool.get('account.journal')
        journals = Journal.search([
                ('type', '=', 'revenue'),
                ], limit=1)
        if journals:
            journal, = journals
        else:
            journal = None
        return journal

    def _get_account_move(self):
        "Return the move object to create"
        pool = Pool()
        Move = pool.get('account.move')
        Date = pool.get('ir.date')
        Period = pool.get('account.period')

        accounting_date = Date().today()
        period_id = Period.find(self.company.id, date=accounting_date)

        lines = self._get_account_move_lines()
        if all(getattr(l, 'credit', _ZERO) == _ZERO and
                getattr(l, 'debit', _ZERO) == _ZERO for l in lines):
            return

        return Move(
            origin=self,
            period=period_id,
            journal=self._get_accounting_journal(),
            date=accounting_date,
            lines=lines,
            )

    def _get_reconcile_move(self):
        "Return the move object to create"
        pool = Pool()
        Move = pool.get('account.move')
        Date = pool.get('ir.date')
        Period = pool.get('account.period')

        accounting_date = Date().today()
        period_id = Period.find(self.company.id, date=accounting_date)

        return Move(
            origin=self,
            period=period_id,
            journal=self._get_accounting_journal(),
            date=accounting_date,
            )

    def _get_account_move_lines(self):
        "Return the move object to create"
        pool = Pool()
        Line = pool.get('account.move.line')
        Currency = pool.get('currency.currency')
        Config = pool.get('sale.configuration')
        config = Config(1)

        shipment_amount = _ZERO

        posted_amounts = {}.fromkeys([x for x in self.lines], _ZERO)
        for line in Line.search([
                    ('sale_line', 'in', [x.id for x in self.lines])
                    ]):
            posted_amounts[line.sale_line] += line.credit - line.debit

        lines = []
        #One line for each sale_line
        for sale_line, quantity in self._get_shipment_quantity().iteritems():
            account = sale_line.product.account_revenue_used
            line = Line()
            line.account = account
            if line.account.party_required:
                line.party = self.party
            line.sale_line = sale_line
            amount = Currency.compute(self.company.currency,
                Decimal(quantity) * sale_line.unit_price, self.currency)
            amount -= posted_amounts[sale_line]
            if amount > 0:
                line.credit = abs(amount)
                line.debit = _ZERO
            else:
                line.debit = abs(amount)
                line.credit = _ZERO
            self._set_analytic_lines(line, sale_line)
            lines.append(line)
            shipment_amount += amount

        #Line with invoice_pending amount
        line = Line()
        line.account = config.pending_invoice_account
        if line.account.party_required:
            line.party = self.party
        if shipment_amount > 0:
            line.debit = abs(shipment_amount)
        else:
            line.credit = abs(shipment_amount)
        lines.append(line)

        return lines

    def _set_analytic_lines(self, move_line, sale_line):
        "Sets the analytic_lines for a move_line related to sale_line"
        pool = Pool()
        Date = pool.get('ir.date')
        try:
            AnalyticLine = pool.get('analytic_account.line')
        except KeyError:
            return []

        lines = []
        if (sale_line.analytic_accounts and
                sale_line.analytic_accounts.accounts):
                for account in sale_line.analytic_accounts.accounts:
                    line = AnalyticLine()
                    line.name = sale_line.description
                    line.debit = move_line.debit
                    line.credit = move_line.credit
                    line.account = account
                    line.journal = self._get_accounting_journal()
                    line.date = Date.today()
                    line.reference = self.reference
                    if hasattr(move_line, 'party'):
                        line.party = move_line.party
                    lines.append(line)
        move_line.analytic_lines = lines
        return lines


class Move:
    __name__ = 'account.move'

    @classmethod
    def _get_origin(cls):
        origins = super(Move, cls)._get_origin()
        if not 'sale.sale' in origins:
            origins.append('sale.sale')
        return origins


class Line:
    __name__ = 'account.move.line'
    sale_line = fields.Many2One('sale.line', 'Sale Line')
