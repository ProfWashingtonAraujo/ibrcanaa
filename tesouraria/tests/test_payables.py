from datetime import date
from decimal import Decimal
from unittest import mock

from django.test import TestCase
from django.utils import timezone
from django.urls import reverse

from core.models import AccessProfile
from tesouraria import balances, ledger, payables
from tesouraria.models import AuditLog, Category, Kind, MonthClosing, Movement, Payable, Status
from tesouraria.navigation import build_treasury_nav
from tesouraria.rules import MonthClosed, TreasuryError

from .helpers import WITHOUT_AXES, configure, make_user

Role = AccessProfile.Role
D = Decimal
TODAY = date(2026, 6, 15)


class PayableBase(TestCase):
    def setUp(self):
        configure(date(2026, 1, 1), cash='500.00', bank='1000.00')
        self.tes = make_user('tes', Role.TREASURER)
        self.category = Category.objects.filter(kind=Kind.EXPENSE, active=True).first()

    def make(self, due=date(2026, 6, 20), amount='200.00', **kw):
        return Payable.objects.create(description='Conta de luz', payee='Energisa', category=self.category,
                                      amount=D(amount), due_date=due, created_by=self.tes, **kw)

    def pay(self, payable, **kw):
        args = dict(user=self.tes, paid_amount=payable.amount, paid_date=date(2026, 6, 18),
                    account='bank', method='pix')
        args.update(kw)
        return payables.pay_payable(payable, **args)

    def total(self):
        return balances.total_balance(date(2026, 6, 30))


class PayableServiceTests(PayableBase):
    def test_open_payable_does_not_change_balances(self):
        before = self.total()
        self.make()
        self.assertEqual(self.total(), before)

    def test_pay_creates_confirmed_expense_and_marks_paid(self):
        p = self.make()
        before = self.total()
        movement = self.pay(p)
        p.refresh_from_db()
        self.assertEqual((p.status, p.movement, p.paid_amount, p.paid_date),
                         (Payable.Status.PAID, movement, D('200.00'), date(2026, 6, 18)))
        self.assertEqual((movement.kind, movement.status, movement.category, movement.account),
                         (Kind.EXPENSE, Status.CONFIRMED, self.category, 'bank'))
        self.assertEqual(self.total(), before - D('200.00'))
        self.assertTrue(AuditLog.objects.filter(action='pay', object_id=str(p.pk)).exists())

    def test_pay_with_different_amount_uses_paid_amount_in_balance(self):
        p = self.make()
        before = self.total()
        self.pay(p, paid_amount=D('185.50'))
        p.refresh_from_db()
        self.assertEqual(p.paid_amount, D('185.50'))
        self.assertEqual(p.amount, D('200.00'))
        self.assertEqual(self.total(), before - D('185.50'))

    def test_pay_only_open_and_validates_amount(self):
        p = self.make()
        with self.assertRaises(TreasuryError):
            self.pay(p, paid_amount=D('0'))
        with self.assertRaises(TreasuryError):
            self.pay(p, paid_amount=D('1.005'))
        with self.assertRaises(TreasuryError):
            self.pay(p, paid_amount=D('10000000000.00'))
        self.pay(p)
        with self.assertRaises(TreasuryError):
            self.pay(p)
        self.assertEqual(Movement.objects.filter(kind=Kind.EXPENSE).count(), 1)

    def test_pay_is_atomic_when_closed_month(self):
        p = self.make()
        MonthClosing.objects.create(month=date(2026, 6, 1), closed_at=timezone.now())
        with self.assertRaises(MonthClosed):
            self.pay(p)
        p.refresh_from_db()
        self.assertEqual(p.status, Payable.Status.OPEN)
        self.assertFalse(Movement.objects.filter(kind=Kind.EXPENSE).exists())

    def test_pay_is_atomic_when_audit_fails(self):
        p = self.make()
        with mock.patch('tesouraria.payables.audit.record', side_effect=RuntimeError('boom')):
            with self.assertRaises(RuntimeError):
                self.pay(p)
        p.refresh_from_db()
        self.assertEqual(p.status, Payable.Status.OPEN)
        self.assertFalse(Movement.objects.filter(kind=Kind.EXPENSE).exists())

    def test_pay_before_start_is_refused(self):
        p = self.make()
        with self.assertRaises(TreasuryError):
            self.pay(p, paid_date=date(2025, 12, 31))

    def test_undo_restores_open_and_removes_expense(self):
        p = self.make()
        before = self.total()
        self.pay(p)
        payables.undo_payment(p, self.tes)
        p.refresh_from_db()
        self.assertEqual((p.status, p.movement, p.paid_amount, p.paid_date),
                         (Payable.Status.OPEN, None, None, None))
        self.assertEqual(self.total(), before)
        self.assertTrue(AuditLog.objects.filter(action='undo_pay').exists())
        self.pay(p)  # pode pagar de novo
        self.assertEqual(Movement.objects.counted().filter(kind=Kind.EXPENSE).count(), 1)

    def test_undo_blocked_when_payment_month_is_closed(self):
        p = self.make()
        self.pay(p)
        MonthClosing.objects.create(month=date(2026, 6, 1), closed_at=timezone.now())
        with self.assertRaises(MonthClosed):
            payables.undo_payment(p, self.tes)
        p.refresh_from_db()
        self.assertEqual(p.status, Payable.Status.PAID)
        self.assertTrue(Movement.objects.counted().filter(kind=Kind.EXPENSE).exists())

    def test_undo_blocked_when_paid_date_month_is_closed(self):
        p = self.make()
        self.pay(p)
        Payable.objects.filter(pk=p.pk).update(paid_date=date(2026, 5, 10))
        MonthClosing.objects.create(month=date(2026, 5, 1), closed_at=timezone.now())
        with self.assertRaises(MonthClosed):
            payables.undo_payment(p, self.tes)
        p.refresh_from_db()
        self.assertEqual(p.status, Payable.Status.PAID)

    def test_payment_movement_cannot_be_edited_or_deleted_directly(self):
        p = self.make()
        movement = self.pay(p)
        with self.assertRaises(TreasuryError) as ctx:
            ledger.delete_movement(self.tes, movement)
        self.assertIn('desfaça o pagamento', str(ctx.exception))
        with self.assertRaises(TreasuryError):
            ledger.update_movement(self.tes, movement, amount=D('1.00'))
        movement.refresh_from_db()
        self.assertIsNone(movement.deleted_at)
        self.assertEqual(movement.amount, D('200.00'))
        payables.undo_payment(p, self.tes)  # o desfazer continua funcionando
        movement.refresh_from_db()
        self.assertIsNotNone(movement.deleted_at)

    def test_undo_only_paid(self):
        with self.assertRaises(TreasuryError):
            payables.undo_payment(self.make(), self.tes)

    def test_cancel_only_open(self):
        p = self.make()
        payables.cancel_payable(p, self.tes)
        p.refresh_from_db()
        self.assertEqual(p.status, Payable.Status.CANCELED)
        with self.assertRaises(TreasuryError):
            payables.cancel_payable(p, self.tes)
        q = self.make()
        self.pay(q)
        with self.assertRaises(TreasuryError):
            payables.cancel_payable(q, self.tes)

    def test_update_only_open_and_audited_with_before(self):
        p = self.make()
        payables.update_payable(self.tes, p, description='Luz', payee='X', category=self.category,
                                amount=D('210.00'), due_date=date(2026, 6, 25))
        log = AuditLog.objects.filter(action='update', object_id=str(p.pk)).get()
        self.assertEqual(log.before['amount'], '200.00')
        self.assertEqual(log.after['amount'], '210.00')
        self.pay(p)
        with self.assertRaises(TreasuryError):
            payables.update_payable(self.tes, p, description='Luz', payee='X', category=self.category,
                                    amount=D('1.00'), due_date=date(2026, 6, 25))

    def test_overview_splits_overdue_upcoming_paid(self):
        self.make(due=date(2026, 6, 1), amount='100.00')
        self.make(due=date(2026, 6, 15), amount='50.00')
        self.make(due=date(2026, 6, 30), amount='70.00')
        paid = self.make(due=date(2026, 6, 10), amount='300.00')
        self.pay(paid, paid_amount=D('290.00'))
        ov = payables.payables_overview(TODAY)
        self.assertEqual(ov['overdue'], {'count': 1, 'total': D('100.00')})
        self.assertEqual(ov['upcoming'], {'count': 2, 'total': D('120.00')})
        self.assertEqual(ov['paid'], {'count': 1, 'total': D('290.00')})

    def test_summary_projected_total_subtracts_open_payables_of_the_month(self):
        self.make(due=date(2026, 6, 20), amount='200.00')
        self.make(due=date(2026, 7, 2), amount='999.00')
        paid = self.make(due=date(2026, 6, 5), amount='80.00')
        self.pay(paid, paid_amount=D('75.00'))
        s = balances.month_summary(date(2026, 6, 1))
        self.assertEqual(s.payables_open_total, D('200.00'))
        self.assertEqual(s.payables_paid_total, D('75.00'))
        self.assertEqual(s.projected_total, s.closing_total - D('200.00'))

    def test_category_with_payable_is_in_use(self):
        fresh = Category.objects.create(name='Nova saída', kind=Kind.EXPENSE)
        self.assertFalse(fresh.in_use())
        Payable.objects.create(description='x', category=fresh, amount=D('1'), due_date=TODAY)
        self.assertTrue(fresh.in_use())


@WITHOUT_AXES
class PayableScreenTests(PayableBase):
    def login(self, role, name='u'):
        self.client.force_login(make_user(name, role))

    def test_tabs_screen_shows_Vencidas_A_vencer_Pagas_with_totals(self):
        self.make(due=date(2020, 1, 1), amount='100.00')
        self.make(due=date(2099, 1, 1), amount='70.00')
        paid = self.make(amount='300.00')
        self.pay(paid, paid_amount=D('290.00'))
        self.client.force_login(self.tes)
        html = self.client.get(reverse('tesouraria:payables')).content.decode()
        for text in ('Vencidas', 'A vencer', 'Pagas', '100,00', '70,00', '290,00'):
            self.assertIn(text, html)

    def test_screen_tab_switch(self):
        self.make(due=date(2020, 1, 1), amount='111.11')
        self.make(due=date(2099, 1, 1), amount='222.22')
        self.client.force_login(self.tes)
        html = self.client.get(reverse('tesouraria:payables') + '?aba=a-vencer').content.decode()
        self.assertIn('222,22', html.split('<table')[1])
        self.assertNotIn('111,11', html.split('<table')[1])

    def test_committee_can_read_payables(self):
        self.login(Role.COMMITTEE)
        self.assertEqual(self.client.get(reverse('tesouraria:payables')).status_code, 200)

    def test_board_cannot_open_payables_screen(self):
        self.login(Role.BOARD)
        self.assertEqual(self.client.get(reverse('tesouraria:payables')).status_code, 403)

    def test_readers_cannot_pay(self):
        p = self.make()
        for role in (Role.COMMITTEE, Role.BOARD):
            self.login(role, f'r{role}')
            for name in ('payable_pay', 'payable_undo', 'payable_cancel'):
                r = self.client.post(reverse(f'tesouraria:{name}', args=[p.pk]), {})
                self.assertEqual(r.status_code, 403, name)
            self.assertEqual(self.client.get(reverse('tesouraria:payable_create')).status_code, 403)
        p.refresh_from_db()
        self.assertEqual(p.status, Payable.Status.OPEN)

    def test_create_edit_pay_undo_cancel_flow(self):
        self.client.force_login(self.tes)
        r = self.client.post(reverse('tesouraria:payable_create'), {
            'description': 'Aluguel', 'payee': 'Imob', 'category': self.category.pk,
            'amount': '350.00', 'due_date': '2026-06-25'})
        self.assertRedirects(r, reverse('tesouraria:payables'))
        p = Payable.objects.get(description='Aluguel')
        r = self.client.post(reverse('tesouraria:payable_edit', args=[p.pk]), {
            'description': 'Aluguel junho', 'payee': 'Imob', 'category': self.category.pk,
            'amount': '360.00', 'due_date': '2026-06-26'})
        self.assertEqual(r.status_code, 302)
        p.refresh_from_db()
        self.assertEqual(p.amount, D('360.00'))
        page = self.client.get(reverse('tesouraria:payable_pay', args=[p.pk]))
        self.assertContains(page, '360.00')  # valor padrão = previsto
        r = self.client.post(reverse('tesouraria:payable_pay', args=[p.pk]), {
            'paid_amount': '355.00', 'paid_date': '2026-06-26', 'account': 'cash', 'method': 'cash'})
        self.assertEqual(r.status_code, 302)
        p.refresh_from_db()
        self.assertEqual((p.status, p.paid_amount), (Payable.Status.PAID, D('355.00')))
        self.assertEqual(self.client.get(reverse('tesouraria:payable_edit', args=[p.pk])).status_code, 302)
        self.client.post(reverse('tesouraria:payable_undo', args=[p.pk]))
        p.refresh_from_db()
        self.assertEqual(p.status, Payable.Status.OPEN)
        self.client.post(reverse('tesouraria:payable_cancel', args=[p.pk]))
        p.refresh_from_db()
        self.assertEqual(p.status, Payable.Status.CANCELED)

    def test_view_refuses_delete_and_edit_of_payment_movement(self):
        p = self.make()
        movement = self.pay(p)
        self.client.force_login(self.tes)
        self.client.post(reverse('tesouraria:movement_delete', args=[movement.pk]))
        self.client.post(reverse('tesouraria:movement_edit', args=[movement.pk]), {
            'date': '2026-06-18', 'category': self.category.pk, 'description': 'x', 'amount': '1.00',
            'method': 'pix', 'account': 'bank'})
        movement.refresh_from_db()
        self.assertEqual((movement.deleted_at, movement.amount), (None, D('200.00')))
        html = self.client.get(reverse('tesouraria:movements') + '?mes=2026-06').content.decode()
        self.assertIn('desfaça o pagamento', html)
        self.assertNotIn(reverse('tesouraria:movement_delete', args=[movement.pk]), html)

    def test_view_undo_refused_in_closed_month(self):
        p = self.make()
        movement = self.pay(p)
        MonthClosing.objects.create(month=date(2026, 6, 1), closed_at=timezone.now())
        self.client.force_login(self.tes)
        self.client.post(reverse('tesouraria:payable_undo', args=[p.pk]))
        p.refresh_from_db()
        movement.refresh_from_db()
        self.assertEqual(p.status, Payable.Status.PAID)
        self.assertIsNone(movement.deleted_at)

    def test_form_hides_archived_category_but_keeps_current_on_edit(self):
        archived = Category.objects.create(name='Velha', kind=Kind.EXPENSE, active=False)
        income = Category.objects.filter(kind=Kind.INCOME).first()
        self.client.force_login(self.tes)
        create = self.client.get(reverse('tesouraria:payable_create'))
        ids = [c.pk for c in create.context['form'].fields['category'].queryset]
        self.assertNotIn(archived.pk, ids)
        self.assertNotIn(income.pk, ids)
        p = self.make()
        p.category = archived
        p.save()
        edit = self.client.get(reverse('tesouraria:payable_edit', args=[p.pk]))
        self.assertIn(archived.pk, [c.pk for c in edit.context['form'].fields['category'].queryset])

    def test_pay_in_closed_month_shows_error_and_keeps_open(self):
        p = self.make()
        MonthClosing.objects.create(month=date(2026, 6, 1), closed_at=timezone.now())
        self.client.force_login(self.tes)
        r = self.client.post(reverse('tesouraria:payable_pay', args=[p.pk]), {
            'paid_amount': '200.00', 'paid_date': '2026-06-18', 'account': 'bank', 'method': 'pix'})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'fechado')
        p.refresh_from_db()
        self.assertEqual(p.status, Payable.Status.OPEN)

    def test_nav_counter_counts_overdue_open_payables(self):
        self.make(due=date(2020, 1, 1))
        self.make(due=date(2099, 1, 1))
        self.client.force_login(self.tes)
        request = mock.Mock(user=self.tes, resolver_match=None)
        items = build_treasury_nav(request)['groups'][0]['items']
        item = next(i for i in items if i['label'] == 'Contas a pagar')
        self.assertEqual(item['count'], 1)

    def test_home_shows_contas_do_mes_block(self):
        self.make(due=date(2026, 6, 20), amount='200.00')
        self.client.force_login(self.tes)
        html = self.client.get(reverse('tesouraria:home') + '?mes=2026-06').content.decode()
        for text in ('Contas do mês', 'Saldo depois de pagar o que falta', '200,00'):
            self.assertIn(text, html)
