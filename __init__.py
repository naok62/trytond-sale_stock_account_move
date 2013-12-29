#The COPYRIGHT file at the top level of this repository contains the full
#copyright notices and license terms.
from trytond.pool import Pool
from .configuration import *
from .sale import *


def register():
    Pool.register(
        Configuration,
        ConfigurationCompany,
        Sale,
        SaleLine,
        InvoiceLine,
        Move,
        module='sale_stock_account_move', type_='model')
