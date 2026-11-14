from datetime import date, datetime, timezone
from decimal import Decimal

from django.test import TestCase

from tesouraria import balances, rules
from tesouraria.models import (
    Account, Category, Kind, Method, Movement, MonthClosing, Source, Status, Transfer,
)

from .helpers import configure

D = Decimal
NOV = date(2026, 11, 1)


class BalancesTests(TestCase):
    def setUp(self):
        configure(start=NOV, cash='1000', bank='5000')
        self.income = Category.objects.filter(kind=Kind.INCOME, is_special=False).first()
        self.special = Category.objects.filter(kind=Kind.INCOME, is_special=True).first()
        self.expense = Category.objects.filter(kind=Kind.EXPENSE).first()

    def mov(self, category=None, **kw):
        category = category or self.income
        defaults = dict(
            date=date(2026, 11, 5), kind=category.kind, amount=D('100.00'), category=category,
            description='x', account=Account.CASH, method=Method.CASH,
            status=Status.CONFIRMED, source=Source.TREASURY,
        )
        defaults.update(kw)
        return Movement.objects.create(**defaults)

    def bal(self, account, on=date(2026, 11, 30)):
        return balances.account_balance(account, on)

    def test_opening_only(self):
        self.assertEqual(self.bal(Account.CASH, NOV), D('1000'))
        self.assertEqual(self.bal(Account.BANK, NOV), D('5000'))

    def test_income_cash_goes_to_cash_pix_to_bank(self):
        self.mov(amount=D('200'))
        self.mov(amount=D('300'), method=Method.PIX, account=Account.BANK)
        self.assertEqual(self.bal(Account.CASH), D('1200'))
        self.assertEqual(self.bal(Account.BANK), D('5300'))

    def test_expense_reduces_chosen_account(self):
        self.mov(self.expense, amount=D('150'), account=Account.BANK)
        self.assertEqual(self.bal(Account.BANK), D('4850'))
        self.assertEqual(self.bal(Account.CASH), D('1000'))

    def test_deposit_moves_without_income_or_expense(self):
        self.mov(amount=D('200'))
        before = balances.month_summary(NOV)
        Transfer.objects.create(date=date(2026, 11, 6), from_account=Account.CASH,
                                to_account=Account.BANK, amount=D('400'))
        self.assertEqual(self.bal(Account.CASH), D('800'))
        self.assertEqual(self.bal(Account.BANK), D('5400'))
        s = balances.month_summary(NOV)
        self.assertEqual(s.income_total, before.income_total)
        self.assertEqual(s.expense_total, before.expense_total)
        self.assertEqual(s.deposits_to_bank, D('400'))

    def test_withdrawal_banco_para_caixa(self):
        Transfer.objects.create(date=date(2026, 11, 6), from_account=Account.BANK,
                                to_account=Account.CASH, amount=D('250'))
        self.assertEqual(self.bal(Account.CASH), D('1250'))
        self.assertEqual(self.bal(Account.BANK), D('4750'))
        self.assertEqual(balances.month_summary(NOV).withdrawals_to_cash, D('250'))

    def test_pending_rejected_deleted_do_not_count(self):
        self.mov(status=Status.PENDING)
        self.mov(status=Status.REJECTED)
        self.mov(deleted_at=datetime(2026, 11, 7, tzinfo=timezone.utc))
        Transfer.objects.create(date=date(2026, 11, 6), from_account=Account.CASH, to_account=Account.BANK,
                                amount=D('400'), deleted_at=datetime(2026, 11, 7, tzinfo=timezone.utc))
        self.assertEqual(self.bal(Account.CASH), D('1000'))
        self.assertEqual(self.bal(Account.BANK), D('5000'))

    def test_before_start_date_ignored(self):
        self.mov(date=date(2026, 10, 31), amount=D('999'))
        self.assertEqual(self.bal(Account.CASH), D('1000'))

    def test_total_is_cash_plus_bank(self):
        self.mov(amount=D('200'))
        self.assertEqual(balances.total_balance(date(2026, 11, 30)), D('6200'))

    def test_month_summary_splits_cash_and_pix_and_special_by_destination(self):
        self.mov(amount=D('200'))
        self.mov(amount=D('300'), method=Method.PIX, account=Account.BANK)
        self.mov(amount=D('50'), method=Method.OTHER, account=Account.BANK)
        self.mov(self.special, amount=D('100'), destination='Missões')
        self.mov(self.special, amount=D('80'), destination='Obra')
        self.mov(self.special, amount=D('70'), destination='Missões')
        self.mov(self.expense, amount=D('40'))
        s = balances.month_summary(NOV)
        self.assertEqual(s.income_cash, D('450'))
        self.assertEqual(s.income_pix, D('300'))
        self.assertEqual(s.income_other, D('50'))
        self.assertEqual(s.income_total, D('800'))
        self.assertEqual(s.expense_total, D('40'))
        self.assertEqual(s.special_by_destination, [('Missões', D('170')), ('Obra', D('80'))])
        self.assertEqual(s.closing_cash, D('1000') + D('450') - D('40'))
        self.assertEqual(s.closing_bank, D('5350'))
        self.assertEqual(s.closing_total, s.closing_cash + s.closing_bank)
        self.assertEqual(s.projected_total, s.closing_total)
        self.assertEqual(s.payables_open_total, D('0'))
        self.assertIsNone(s.counted_cash)
        self.assertFalse(s.is_closed)
        self.assertEqual(dict(s.income_by_category)[self.income], D('550'))

    def test_second_month_opening_is_previous_closing(self):
        self.mov(amount=D('200'))
        self.mov(self.expense, amount=D('50'), account=Account.BANK)
        dec = date(2026, 12, 1)
        self.assertEqual(balances.opening_balance(Account.CASH, NOV), D('1000'))
        self.assertEqual(balances.opening_balance(Account.CASH, dec), D('1200'))
        self.assertEqual(balances.opening_balance(Account.BANK, dec), D('4950'))
        s = balances.month_summary(dec)
        self.assertEqual((s.opening_cash, s.opening_bank), (D('1200'), D('4950')))

    def test_ensure_month_open_and_after_start_raise(self):
        with self.assertRaises(rules.BeforeStart):
            rules.ensure_after_start(date(2026, 10, 31))
        rules.ensure_after_start(NOV)
        rules.ensure_month_open(date(2026, 11, 15))
        MonthClosing.objects.create(month=NOV, closed_at=datetime(2026, 12, 1, tzinfo=timezone.utc))
        with self.assertRaises(rules.MonthClosed):
            rules.ensure_month_open(date(2026, 11, 15))
        rules.ensure_month_open(date(2026, 12, 15))

    def test_month_before_start_or_unconfigured_raises(self):
        with self.assertRaises(rules.BeforeStart):
            balances.month_summary(date(2026, 10, 1))
        with self.assertRaises(rules.BeforeStart):
            balances.account_balance(Account.CASH, date(2026, 10, 31))
        from tesouraria.models import TreasurySettings
        TreasurySettings.objects.all().delete()
        with self.assertRaises(rules.NotConfigured):
            balances.total_balance(NOV)
        with self.assertRaises(rules.NotConfigured):
            rules.ensure_after_start(NOV)

    def test_confirmed_does_not_exclude_deleted_but_counted_does(self):
        m = self.mov(deleted_at=datetime(2026, 11, 7, tzinfo=timezone.utc))
        self.assertIn(m, Movement.objects.confirmed())
        self.assertNotIn(m, Movement.objects.counted())
        self.assertIn(self.mov(), Movement.objects.counted())
