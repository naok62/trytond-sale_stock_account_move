=============
Sale Scenario
=============

Imports::

    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from operator import attrgetter
    >>> from proteus import config, Model, Wizard
    >>> today = datetime.date.today()

Create database::

    >>> config = config.set_trytond()
    >>> config.pool.test = True

Install sale::

    >>> Module = Model.get('ir.module.module')
    >>> sale_module, = Module.find([('name', '=', 'sale_stock_account_move')])
    >>> analytic_module, = Module.find([('name', '=', 'analytic_sale')])
    >>> Module.install([sale_module.id, analytic_module.id], config.context)
    >>> Wizard('ir.module.module.install_upgrade').execute('upgrade')

Create company::

    >>> Currency = Model.get('currency.currency')
    >>> CurrencyRate = Model.get('currency.currency.rate')
    >>> currencies = Currency.find([('code', '=', 'EUR')])
    >>> if not currencies:
    ...     currency = Currency(name='Euro', symbol=u'€', code='EUR',
    ...         rounding=Decimal('0.01'), mon_grouping='[3, 3, 0]',
    ...         mon_decimal_point=',')
    ...     currency.save()
    ...     CurrencyRate(date=today + relativedelta(month=1, day=1),
    ...         rate=Decimal('1.0'), currency=currency).save()
    ... else:
    ...     currency, = currencies
    >>> Company = Model.get('company.company')
    >>> Party = Model.get('party.party')
    >>> company_config = Wizard('company.company.config')
    >>> company_config.execute('company')
    >>> company = company_config.form
    >>> party = Party(name='B2CK')
    >>> party.save()
    >>> company.party = party
    >>> company.currency = currency
    >>> company_config.execute('add')
    >>> company, = Company.find([])

Reload the context::

    >>> User = Model.get('res.user')
    >>> Group = Model.get('res.group')
    >>> config._context = User.get_preferences(True, config.context)

Create sale user::

    >>> sale_user = User()
    >>> sale_user.name = 'Sale'
    >>> sale_user.login = 'sale'
    >>> sale_user.main_company = company
    >>> sale_group, = Group.find([('name', '=', 'Sales')])
    >>> sale_user.groups.append(sale_group)
    >>> sale_user.save()

Create stock user::

    >>> stock_user = User()
    >>> stock_user.name = 'Stock'
    >>> stock_user.login = 'stock'
    >>> stock_user.main_company = company
    >>> stock_group, = Group.find([('name', '=', 'Stock')])
    >>> stock_user.groups.append(stock_group)
    >>> stock_user.save()

Create account user::

    >>> account_user = User()
    >>> account_user.name = 'Account'
    >>> account_user.login = 'account'
    >>> account_user.main_company = company
    >>> account_group, = Group.find([('name', '=', 'Account')])
    >>> account_user.groups.append(account_group)
    >>> account_user.save()

Create fiscal year::

    >>> FiscalYear = Model.get('account.fiscalyear')
    >>> Sequence = Model.get('ir.sequence')
    >>> SequenceStrict = Model.get('ir.sequence.strict')
    >>> fiscalyear = FiscalYear(name=str(today.year))
    >>> fiscalyear.start_date = today + relativedelta(month=1, day=1)
    >>> fiscalyear.end_date = today + relativedelta(month=12, day=31)
    >>> fiscalyear.company = company
    >>> post_move_seq = Sequence(name=str(today.year), code='account.move',
    ...     company=company)
    >>> post_move_seq.save()
    >>> fiscalyear.post_move_sequence = post_move_seq
    >>> invoice_seq = SequenceStrict(name=str(today.year),
    ...     code='account.invoice', company=company)
    >>> invoice_seq.save()
    >>> fiscalyear.out_invoice_sequence = invoice_seq
    >>> fiscalyear.in_invoice_sequence = invoice_seq
    >>> fiscalyear.out_credit_note_sequence = invoice_seq
    >>> fiscalyear.in_credit_note_sequence = invoice_seq
    >>> fiscalyear.save()
    >>> FiscalYear.create_period([fiscalyear.id], config.context)

Create chart of accounts::

    >>> AccountTemplate = Model.get('account.account.template')
    >>> Account = Model.get('account.account')
    >>> account_template, = AccountTemplate.find([('parent', '=', None)])
    >>> create_chart = Wizard('account.create_chart')
    >>> create_chart.execute('account')
    >>> create_chart.form.account_template = account_template
    >>> create_chart.form.company = company
    >>> create_chart.execute('create_account')
    >>> receivable, = Account.find([
    ...         ('kind', '=', 'receivable'),
    ...         ('company', '=', company.id),
    ...         ])
    >>> payable, = Account.find([
    ...         ('kind', '=', 'payable'),
    ...         ('company', '=', company.id),
    ...         ])
    >>> revenue, = Account.find([
    ...         ('kind', '=', 'revenue'),
    ...         ('company', '=', company.id),
    ...         ])
    >>> revenue.code = 'R1'
    >>> revenue.save()
    >>> revenue2 = Account()
    >>> revenue2.code = 'R2'
    >>> revenue2.name = 'Second Revenue'
    >>> revenue2.type = revenue.type
    >>> revenue2.kind = 'revenue'
    >>> revenue2.parent = revenue.parent
    >>> revenue2.save()
    >>> pending_receivable = Account()
    >>> pending_receivable.code = 'PR'
    >>> pending_receivable.name = 'Pending Receivable'
    >>> pending_receivable.type = receivable.type
    >>> pending_receivable.kind = 'receivable'
    >>> pending_receivable.reconcile = True
    >>> pending_receivable.parent = receivable.parent
    >>> pending_receivable.save()
    >>> expense, = Account.find([
    ...         ('kind', '=', 'expense'),
    ...         ('company', '=', company.id),
    ...         ])
    >>> create_chart.form.account_receivable = receivable
    >>> create_chart.form.account_payable = payable
    >>> create_chart.execute('create_properties')

Create analytic accounts::

    >>> AnalyticAccount = Model.get('analytic_account.account')
    >>> root = AnalyticAccount(type='root', name='Root')
    >>> root.save()
    >>> analytic_account = AnalyticAccount(root=root, parent=root,
    ...     name='Analytic')
    >>> analytic_account.save()


Configure sale to track pending_receivables in accounting::

    >>> SaleConfig = Model.get('sale.configuration')
    >>> sale_config = SaleConfig(1)
    >>> sale_config.sale_shipment_method = 'order'
    >>> sale_config.sale_invoice_method = 'shipment'
    >>> sale_config.pending_invoice_account = pending_receivable
    >>> sale_config.save()

Create parties::

    >>> Party = Model.get('party.party')
    >>> supplier = Party(name='Supplier')
    >>> supplier.save()
    >>> customer = Party(name='Customer')
    >>> customer.save()

Create category::

    >>> ProductCategory = Model.get('product.category')
    >>> category = ProductCategory(name='Category')
    >>> category.save()

Create products::

    >>> ProductUom = Model.get('product.uom')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> ProductTemplate = Model.get('product.template')
    >>> Product = Model.get('product.product')
    >>> product1 = Product()
    >>> template1 = ProductTemplate()
    >>> template1.name = 'product'
    >>> template1.category = category
    >>> template1.default_uom = unit
    >>> template1.type = 'goods'
    >>> template1.purchasable = True
    >>> template1.salable = True
    >>> template1.list_price = Decimal('15')
    >>> template1.cost_price = Decimal('10')
    >>> template1.cost_price_method = 'fixed'
    >>> template1.account_expense = expense
    >>> template1.account_revenue = revenue
    >>> template1.save()
    >>> product1.template = template1
    >>> product1.save()
    >>> template2 = ProductTemplate()
    >>> template2.name = 'product'
    >>> template2.category = category
    >>> template2.default_uom = unit
    >>> template2.type = 'goods'
    >>> template2.purchasable = True
    >>> template2.salable = True
    >>> template2.list_price = Decimal('25')
    >>> template2.cost_price = Decimal('12')
    >>> template2.cost_price_method = 'fixed'
    >>> template2.account_expense = expense
    >>> template2.account_revenue = revenue2
    >>> template2.save()
    >>> product2 = Product()
    >>> product2.template = template2
    >>> product2.save()
    >>> service_product = Product()
    >>> service_template = ProductTemplate()
    >>> service_template.name = 'product'
    >>> service_template.category = category
    >>> service_template.default_uom = unit
    >>> service_template.type = 'service'
    >>> service_template.purchasable = True
    >>> service_template.salable = True
    >>> service_template.list_price = Decimal('15')
    >>> service_template.cost_price = Decimal('10')
    >>> service_template.cost_price_method = 'fixed'
    >>> service_template.account_expense = expense
    >>> service_template.account_revenue = revenue
    >>> service_template.save()
    >>> service_product.template = service_template
    >>> service_product.save()

Create payment term::

    >>> PaymentTerm = Model.get('account.invoice.payment_term')
    >>> PaymentTermLine = Model.get('account.invoice.payment_term.line')
    >>> payment_term = PaymentTerm(name='Direct')
    >>> payment_term_line = PaymentTermLine(type='remainder', days=0)
    >>> payment_term.lines.append(payment_term_line)
    >>> payment_term.save()

Create an Inventory::

    >>> config.user = stock_user.id
    >>> Inventory = Model.get('stock.inventory')
    >>> InventoryLine = Model.get('stock.inventory.line')
    >>> Location = Model.get('stock.location')
    >>> storage, = Location.find([
    ...         ('code', '=', 'STO'),
    ...         ])
    >>> inventory = Inventory()
    >>> inventory.location = storage
    >>> inventory.save()
    >>> inventory_line = InventoryLine(product=product1, inventory=inventory)
    >>> inventory_line.quantity = 100.0
    >>> inventory_line.expected_quantity = 0.0
    >>> inventory.save()
    >>> inventory_line.save()
    >>> inventory_line = InventoryLine(product=product2, inventory=inventory)
    >>> inventory_line.quantity = 100.0
    >>> inventory_line.expected_quantity = 0.0
    >>> inventory.save()
    >>> inventory_line.save()
    >>> Inventory.confirm([inventory.id], config.context)
    >>> inventory.state
    u'done'

Sale products::

    >>> config.user = sale_user.id
    >>> Sale = Model.get('sale.sale')
    >>> SaleLine = Model.get('sale.line')
    >>> AnalyticSelection = Model.get('analytic_account.account.selection')
    >>> sale = Sale()
    >>> sale.party = customer
    >>> sale.payment_term = payment_term
    >>> sale_line = SaleLine()
    >>> sale.lines.append(sale_line)
    >>> sale_line.product = product1
    >>> sale_line.quantity = 20.0
    >>> analytic_selection = AnalyticSelection()
    >>> analytic_selection.accounts.append(analytic_account)
    >>> analytic_selection.save()
    >>> sale_line.analytic_accounts = analytic_selection
    >>> sale_line = SaleLine()
    >>> sale.lines.append(sale_line)
    >>> sale_line.type = 'comment'
    >>> sale_line.description = 'Comment'
    >>> sale_line = SaleLine()
    >>> sale.lines.append(sale_line)
    >>> sale_line.product = product2
    >>> sale_line.quantity = 20.0
    >>> analytic_account, = AnalyticAccount.find([('type', '=', 'normal')])
    >>> analytic_selection = AnalyticSelection()
    >>> analytic_selection.accounts.append(analytic_account)
    >>> analytic_selection.save()
    >>> sale_line.analytic_accounts = analytic_selection
    >>> sale.save()
    >>> Sale.quote([sale.id], config.context)
    >>> Sale.confirm([sale.id], config.context)
    >>> Sale.process([sale.id], config.context)
    >>> sale.state
    u'processing'
    >>> sale.reload()
    >>> len(sale.shipments), len(sale.shipment_returns), len(sale.invoices)
    (1, 0, 0)
    >>> shipment, = sale.shipments
    >>> shipment.origins == sale.rec_name
    True
    >>> analytic_account.reload()
    >>> analytic_account.credit == Decimal('0.0')
    True

Validate Shipments::

    >>> moves = sale.moves
    >>> config.user = stock_user.id
    >>> ShipmentOut = Model.get('stock.shipment.out')
    >>> for move in shipment.inventory_moves:
    ...     move.quantity = 15.0
    >>> shipment.save()
    >>> ShipmentOut.assign_try([shipment.id], config.context)
    True
    >>> ShipmentOut.pack([shipment.id], config.context)
    >>> ShipmentOut.done([shipment.id], config.context)
    >>> config.user = account_user.id
    >>> AccountMoveLine = Model.get('account.move.line')
    >>> account_moves = AccountMoveLine.find([
    ...     ('origin', '=', 'sale.sale,' + str(sale.id)),
    ...     ('account', '=', pending_receivable.id),
    ...     ])
    >>> len(account_moves)
    2
    >>> sum([a.debit for a in account_moves]) == Decimal('600.0')
    True
    >>> account_moves = AccountMoveLine.find([
    ...     ('origin', '=', 'sale.sale,' + str(sale.id)),
    ...     ('account.code', '=', 'R1'),
    ...     ])
    >>> len(account_moves) == 1
    True
    >>> sum([a.credit for a in account_moves]) == Decimal('225.0')
    True
    >>> account_moves = AccountMoveLine.find([
    ...     ('origin', '=', 'sale.sale,' + str(sale.id)),
    ...     ('account.code', '=', 'R2'),
    ...     ])
    >>> len(account_moves) == 1
    True
    >>> sum([a.credit for a in account_moves]) == Decimal('375.0')
    True
    >>> analytic_account.reload()
    >>> analytic_account.credit == Decimal('600.0')
    True
    >>> config.user = sale_user.id
    >>> sale.reload()
    >>> shipment, = sale.shipments.find([('state', '=', 'waiting')])
    >>> config.user = stock_user.id
    >>> ShipmentOut.assign_try([shipment.id], config.context)
    True
    >>> ShipmentOut.pack([shipment.id], config.context)
    >>> ShipmentOut.done([shipment.id], config.context)
    >>> config.user = account_user.id
    >>> account_moves = AccountMoveLine.find([
    ...     ('origin', '=', 'sale.sale,' + str(sale.id)),
    ...     ('account', '=', pending_receivable.id),
    ...     ])
    >>> len(account_moves)
    6
    >>> sum([a.debit - a.credit for a in account_moves]) == Decimal('800.0')
    True
    >>> account_moves = AccountMoveLine.find([
    ...     ('origin', '=', 'sale.sale,' + str(sale.id)),
    ...     ('account.code', '=', 'R1'),
    ...     ])
    >>> len(account_moves) == 2
    True
    >>> sum([a.credit for a in account_moves]) == Decimal('300.0')
    True
    >>> account_moves = AccountMoveLine.find([
    ...     ('origin', '=', 'sale.sale,' + str(sale.id)),
    ...     ('account.code', '=', 'R2'),
    ...     ])
    >>> len(account_moves) == 2
    True
    >>> sum([a.credit for a in account_moves]) == Decimal('500.0')
    True
    >>> analytic_account.reload()
    >>> analytic_account.credit == Decimal('800.0')
    True

Open customer invoice::

    >>> config.user = sale_user.id
    >>> sale.reload()
    >>> Invoice = Model.get('account.invoice')
    >>> invoice1, invoice2 = sale.invoices
    >>> config.user = account_user.id
    >>> Invoice.post([invoice1.id], config.context)
    >>> account_moves = AccountMoveLine.find([
    ...     ('origin', '=', 'sale.sale,' + str(sale.id)),
    ...     ('account', '=', pending_receivable.id),
    ...     ('reconciliation', '=', None),
    ...     ])
    >>> line, _ = account_moves
    >>> sum([a.debit for a in account_moves]) == Decimal('200.0')
    True
    >>> account_moves = AccountMoveLine.find([
    ...     ('account.code', '=', 'R1'),
    ...     ])
    >>> sum([a.credit - a.debit for a in account_moves]) == Decimal('300.0')
    True
    >>> account_moves = AccountMoveLine.find([
    ...     ('account.code', '=', 'R2'),
    ...     ])
    >>> sum([a.credit - a.debit for a in account_moves]) == Decimal('500.0')
    True
    >>> analytic_account.reload()
    >>> analytic_account.balance == Decimal('800.0')
    True
    >>> Invoice.post([invoice2.id], config.context)
    >>> account_moves = AccountMoveLine.find([
    ...     ('origin', '=', 'sale.sale,' + str(sale.id)),
    ...     ('account', '=', pending_receivable.id),
    ...     ])
    >>> sum([a.debit - a.credit for a in account_moves]) == Decimal('0.0')
    True
    >>> all(a.reconciliation is not None for a in account_moves)
    True
    >>> account_moves = AccountMoveLine.find([
    ...     ('account.code', '=', 'R1'),
    ...     ])
    >>> sum([a.credit - a.debit for a in account_moves]) == Decimal('300.0')
    True
    >>> account_moves = AccountMoveLine.find([
    ...     ('account.code', '=', 'R2'),
    ...     ])
    >>> sum([a.credit - a.debit for a in account_moves]) == Decimal('500.0')
    True
    >>> analytic_account.reload()
    >>> analytic_account.balance == Decimal('800.0')
    True
