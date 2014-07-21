#!/usr/bin/env python
# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
import unittest
import doctest
import trytond.tests.test_tryton
from trytond.tests.test_tryton import test_view, test_depends, doctest_dropdb
from trytond.tests.test_tryton import POOL, DB_NAME, USER, CONTEXT
from trytond.transaction import Transaction


class TestCase(unittest.TestCase):
    'Test module'

    def setUp(self):
        trytond.tests.test_tryton.install_module('sale_stock_account_move')
        self.company = POOL.get('company.company')
        self.config = POOL.get('sale.configuration')
        self.account = POOL.get('account.account')

    def test0005views(self):
        '''
        Test views.
        '''
        test_view('sale_stock_account_move')

    def test0006depends(self):
        '''
        Test depends.
        '''
        test_depends()

    def test0010_set_default_pending_account(self):
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            #This is needed in order to get default values for other test
            #executing in the same database
            company, = self.company.search([
                    ('rec_name', '=', 'Dunder Mifflin'),
                    ])
            accounts = self.account.search([
                    ('kind', '=', 'receivable'),
                    ], limit=1)
            if accounts:
                account, = accounts
                with transaction.set_context(company=company.id):
                    config = self.config(1)
                    config.pending_invoice_account = account
                    config.save()
                transaction.cursor.commit()


def suite():
    suite = trytond.tests.test_tryton.suite()
    from trytond.modules.company.tests import test_company
    for test in test_company.suite():
        if test not in suite:
            suite.addTest(test)
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestCase))
    suite.addTests(doctest.DocFileSuite('scenario_sale.rst',
            setUp=doctest_dropdb, tearDown=doctest_dropdb, encoding='utf-8',
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    suite.addTests(doctest.DocFileSuite('scenario_sale_analytic.rst',
            setUp=doctest_dropdb, tearDown=doctest_dropdb, encoding='utf-8',
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
