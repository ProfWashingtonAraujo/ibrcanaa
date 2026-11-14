from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import AccessProfile
from tesouraria import balances, closing, ledger, payables, pending
from tesouraria.models import AuditLog, Category, Kind, MonthClosing, Movement, Payable
from tesouraria.rules import MonthClosed, TreasuryError

from .helpers import WITHOUT_AXES, configure, make_user

Role = AccessProfile.Role
D = Decimal
JAN, FEB, MAR = date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1)


class ClosingBase(TestCase):
    def setUp(self):
        configure(date(2026, 1, 1), cash='100.00', bank='200.00')
        self.tes = make_user('tes', Role.TREASURER)
        self.income = Category.objects.filter(kind=Kind.INCOME, active=True, is_special=False).first()
        self.expense = Category.objects.filter(kind=Kind.EXPENSE, active=True).first()

    def entrada(self, when, amount='50.00', account='cash'):
        return ledger.create_movement(self.tes, date=when, category=self.income, description='x',
                                      amount=D(amount), account=account, method='cash')

    def saida(self, when, amount='20.00', account='cash'):
        return ledger.create_movement(self.tes, date=when, category=self.expense, description='y',
                                      amount=D(amount), account=account, method='cash')


class ClosingServiceTests(ClosingBase):
    def test_cash_count_shows_difference(self):
        self.entrada(date(2026, 1, 5))  # caixa 150
        closing.record_cash_count(JAN, D('140.00'), self.tes)
        summary = balances.month_summary(JAN)
        self.assertEqual(summary.counted_cash, D('140.00'))
        self.assertEqual(summary.cash_difference, D('-10.00'))
        self.assertFalse(summary.is_closed)
        self.assertTrue(AuditLog.objects.filter(action='count').exists())
        closing.record_cash_count(JAN, D('150.00'), self.tes)
        self.assertEqual(balances.month_summary(JAN).cash_difference, D('0.00'))
        self.assertEqual(MonthClosing.objects.count(), 1)

    def test_summary_without_count_has_no_difference(self):
        summary = balances.month_summary(JAN)
        self.assertIsNone(summary.counted_cash)
        self.assertIsNone(summary.cash_difference)

    def test_close_blocked_by_pending_contribution_in_month(self):
        member_user = make_user('m')
        from core.models import Member
        member = Member.objects.create(name='Fulano', user=member_user)
        movement = pending.create_portal_contribution(member, self.income.name, D('10.00'))
        Movement.objects.filter(pk=movement.pk).update(date=date(2026, 1, 10))
        with self.assertRaises(TreasuryError):
            closing.close_month(JAN, self.tes)
        self.assertFalse(MonthClosing.objects.filter(closed_at__isnull=False).exists())

    def test_close_requires_previous_month_closed(self):
        with self.assertRaises(TreasuryError):
            closing.close_month(FEB, self.tes)
        closing.close_month(JAN, self.tes)  # primeiro mês: sem exigência anterior
        closing.close_month(FEB, self.tes)

    def test_cannot_close_future_month(self):
        today = timezone.localdate()
        future = date(today.year + 1, 1, 1)
        configure(date(2026, 1, 1))
        with self.assertRaises(TreasuryError):
            closing.close_month(future, self.tes)

    def test_cannot_close_twice_or_before_start(self):
        closing.close_month(JAN, self.tes)
        with self.assertRaises(TreasuryError):
            closing.close_month(JAN, self.tes)
        with self.assertRaises(TreasuryError):
            closing.close_month(date(2025, 12, 1), self.tes)

    def test_close_snapshots_balances_equal_to_summary(self):
        self.entrada(date(2026, 1, 5))
        self.saida(date(2026, 1, 6), '30.00', 'bank')
        summary = balances.month_summary(JAN)
        result = closing.close_month(date(2026, 1, 17), self.tes, notes='ok')
        result.refresh_from_db()
        self.assertEqual((result.opening_cash, result.opening_bank, result.closing_cash, result.closing_bank),
                         (summary.opening_cash, summary.opening_bank, summary.closing_cash, summary.closing_bank))
        self.assertEqual((result.month, result.closed_by, result.notes), (JAN, self.tes, 'ok'))
        self.assertIsNotNone(result.closed_at)
        self.assertTrue(balances.month_summary(JAN).is_closed)
        self.assertTrue(AuditLog.objects.filter(action='close').exists())

    def test_next_month_opening_equals_previous_closing(self):
        self.entrada(date(2026, 1, 5))
        self.saida(date(2026, 1, 6), '30.00', 'bank')
        closing.close_month(JAN, self.tes)
        jan, feb = balances.month_summary(JAN), balances.month_summary(FEB)
        self.assertEqual((feb.opening_cash, feb.opening_bank), (jan.closing_cash, jan.closing_bank))

    def test_closed_month_is_read_only_via_every_mutation(self):
        m = self.entrada(date(2026, 1, 5))
        m2 = self.entrada(date(2026, 1, 6))
        payable = Payable.objects.create(description='Luz', category=self.expense, amount=D('10.00'),
                                         due_date=date(2026, 1, 20), created_by=self.tes)
        payable2 = Payable.objects.create(description='Agua', category=self.expense, amount=D('10.00'),
                                          due_date=date(2026, 1, 21), created_by=self.tes)
        paid_movement = payables.pay_payable(payable2, user=self.tes, paid_amount=D('10.00'),
                                             paid_date=date(2026, 1, 22), account='bank', method='pix')
        transfer = ledger.create_transfer(self.tes, date=date(2026, 1, 7), from_account='cash',
                                          to_account='bank', amount=D('5.00'))
        member_user = make_user('m')
        from core.models import Member
        member = Member.objects.create(name='Fulano', user=member_user)
        pend = pending.create_portal_contribution(member, self.income.name, D('10.00'))
        Movement.objects.filter(pk=pend.pk).update(date=date(2026, 3, 10))  # fora de jan, para fechar
        closing.close_month(JAN, self.tes)
        with self.assertRaises(MonthClosed):
            self.entrada(date(2026, 1, 9))
        with self.assertRaises(MonthClosed):
            ledger.create_transfer(self.tes, date=date(2026, 1, 9), from_account='cash',
                                   to_account='bank', amount=D('5.00'))
        with self.assertRaises(MonthClosed):
            ledger.update_movement(self.tes, m, amount=D('99.00'))
        with self.assertRaises(MonthClosed):
            ledger.delete_movement(self.tes, m)
        with self.assertRaises(MonthClosed):
            ledger.delete_transfer(self.tes, transfer)
        with self.assertRaises(MonthClosed):
            payables.pay_payable(payable, user=self.tes, paid_amount=D('10.00'),
                                 paid_date=date(2026, 1, 25), account='bank', method='pix')
        with self.assertRaises(MonthClosed):
            payables.undo_payment(payable2, self.tes)
        with self.assertRaises(MonthClosed):
            pending.confirm_pending(pend, user=self.tes, account='cash', method='cash', date=date(2026, 1, 12))
        with self.assertRaises(MonthClosed):
            closing.record_cash_count(JAN, D('1.00'), self.tes)
        # mover para dentro / para fora do mês fechado
        feb_move = self.entrada(date(2026, 2, 3))
        with self.assertRaises(MonthClosed):
            ledger.update_movement(self.tes, feb_move, date=date(2026, 1, 8))
        with self.assertRaises(MonthClosed):
            ledger.update_movement(self.tes, m2, date=date(2026, 2, 8))
        self.assertEqual(paid_movement.pk, Movement.objects.get(pk=paid_movement.pk).pk)

    def test_reopen_allows_edits_and_audits(self):
        m = self.entrada(date(2026, 1, 5))
        closing.close_month(JAN, self.tes)
        reopened = closing.reopen_month(JAN, self.tes)
        self.assertFalse(reopened.is_closed)
        self.assertFalse(balances.month_summary(JAN).is_closed)
        ledger.update_movement(self.tes, m, amount=D('60.00'))
        self.assertTrue(AuditLog.objects.filter(action='reopen').exists())

    def test_reopen_not_closed_month_is_refused(self):
        with self.assertRaises(TreasuryError):
            closing.reopen_month(JAN, self.tes)

    def test_cannot_reopen_when_next_month_closed(self):
        closing.close_month(JAN, self.tes)
        closing.close_month(FEB, self.tes)
        with self.assertRaises(TreasuryError):
            closing.reopen_month(JAN, self.tes)
        closing.reopen_month(FEB, self.tes)
        closing.reopen_month(JAN, self.tes)

    def test_ledger_guard_locks_settings_row_inside_atomic(self):
        from unittest import mock
        from tesouraria import rules
        with mock.patch.object(rules, 'lock_settings', wraps=rules.lock_settings) as spy:
            self.entrada(date(2026, 1, 5))
        self.assertTrue(spy.called)


@WITHOUT_AXES
class ClosingViewTests(ClosingBase):
    def setUp(self):
        super().setUp()
        self.committee = make_user('com', Role.COMMITTEE)
        self.board = make_user('dir', Role.BOARD)

    def test_treasurer_counts_and_closes_via_views(self):
        self.client.login(username='tes', password='senha-forte-123')
        page = self.client.get(reverse('tesouraria:home') + '?mes=2026-01')
        self.assertContains(page, 'Conferir caixa')
        self.assertContains(page, 'Fechar mês')
        r = self.client.post(reverse('tesouraria:cash_count') + '?mes=2026-01', {'counted_cash': '90.00'})
        self.assertEqual(r.status_code, 302)
        page = self.client.get(reverse('tesouraria:home') + '?mes=2026-01')
        self.assertContains(page, 'Diferença')
        r = self.client.post(reverse('tesouraria:month_close') + '?mes=2026-01', {'notes': 'tudo certo'})
        self.assertEqual(r.status_code, 302)
        page = self.client.get(reverse('tesouraria:home') + '?mes=2026-01')
        self.assertContains(page, 'Mês fechado')
        self.assertContains(page, 'Reabrir')
        self.assertNotContains(page, 'Fechar mês')
        self.client.post(reverse('tesouraria:month_reopen') + '?mes=2026-01')
        self.assertFalse(MonthClosing.objects.get(month=JAN).is_closed)

    def test_close_page_get_and_error_flash(self):
        self.client.login(username='tes', password='senha-forte-123')
        self.assertEqual(self.client.get(reverse('tesouraria:month_close') + '?mes=2026-01').status_code, 200)
        self.assertEqual(self.client.get(reverse('tesouraria:cash_count') + '?mes=2026-01').status_code, 200)
        r = self.client.post(reverse('tesouraria:month_close') + '?mes=2026-02', {}, follow=True)
        self.assertContains(r, 'mês anterior')
        self.assertFalse(MonthClosing.objects.filter(closed_at__isnull=False).exists())

    def test_close_and_reopen_forbidden_for_readers(self):
        closing.close_month(JAN, self.tes)
        for username in ('com', 'dir'):
            self.client.login(username=username, password='senha-forte-123')
            for name, data in (('cash_count', {'counted_cash': '1'}), ('month_close', {}), ('month_reopen', {})):
                r = self.client.post(reverse(f'tesouraria:{name}') + '?mes=2026-01', data)
                self.assertEqual(r.status_code, 403, (username, name))
            page = self.client.get(reverse('tesouraria:home') + '?mes=2026-01')
            if username == 'com':
                self.assertContains(page, 'Mês fechado')
                self.assertNotContains(page, 'Reabrir')
                self.assertNotContains(page, 'Conferir caixa')
        self.assertTrue(MonthClosing.objects.get(month=JAN).is_closed)
