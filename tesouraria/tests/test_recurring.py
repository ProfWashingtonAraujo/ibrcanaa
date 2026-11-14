from datetime import date
from decimal import Decimal
from unittest import mock

from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import AccessProfile
from tesouraria import recurring
from tesouraria.forms import RecurringForm
from tesouraria.models import AuditLog, Category, Kind, Payable, RecurringBill
from tesouraria.navigation import build_treasury_nav
from tesouraria.rules import TreasuryError

from .helpers import WITHOUT_AXES, configure, make_user

Role = AccessProfile.Role
D = Decimal


class RecurringBase(TestCase):
    def setUp(self):
        configure(date(2026, 1, 1))
        self.tes = make_user('tes', Role.TREASURER)
        self.category = Category.objects.filter(kind=Kind.EXPENSE, active=True).first()

    def bill(self, start=date(2026, 6, 1), due_day=10, installments=None, **kw):
        data = dict(description='Aluguel', payee='Imobiliária', category=self.category, amount=D('1500.00'),
                    due_day=due_day, start_date=start, installments=installments, created_by=self.tes)
        data.update(kw)
        return RecurringBill.objects.create(**data)


class DueDateTests(TestCase):
    def test_due_date_clamps_to_last_day(self):
        self.assertEqual(recurring.due_date_for(date(2027, 2, 1), 31), date(2027, 2, 28))
        self.assertEqual(recurring.due_date_for(date(2028, 2, 1), 30), date(2028, 2, 29))
        self.assertEqual(recurring.due_date_for(date(2026, 4, 1), 31), date(2026, 4, 30))
        self.assertEqual(recurring.due_date_for(date(2026, 4, 1), 5), date(2026, 4, 5))


class EnsureRecurringTests(RecurringBase):
    def test_creates_current_and_next_month(self):
        self.bill()
        self.assertEqual(recurring.ensure_recurring(date(2026, 6, 15)), 2)
        rows = list(Payable.objects.order_by('due_date'))
        self.assertEqual([r.due_date for r in rows], [date(2026, 6, 10), date(2026, 7, 10)])
        self.assertEqual([r.period for r in rows], [date(2026, 6, 1), date(2026, 7, 1)])
        self.assertEqual(rows[0].amount, D('1500.00'))
        self.assertEqual(rows[0].status, Payable.Status.OPEN)
        self.assertEqual((rows[0].description, rows[0].payee, rows[0].category), ('Aluguel', 'Imobiliária', self.category))
        self.assertIsNone(rows[0].installment_number)
        self.assertIsNone(rows[0].created_by)

    def test_december_rolls_to_january(self):
        self.bill(start=date(2026, 1, 1))
        recurring.ensure_recurring(date(2026, 12, 20))
        self.assertEqual(sorted(Payable.objects.values_list('period', flat=True)),
                         [date(2026, 12, 1), date(2027, 1, 1)])

    def test_mid_month_start_date_counts_start_month_as_first(self):
        self.bill(start=date(2026, 6, 20), installments=3, due_day=5)
        recurring.ensure_recurring(date(2026, 6, 25))
        first = Payable.objects.get(period=date(2026, 6, 1))
        self.assertEqual((first.installment_number, first.installments_total), (1, 3))

    def test_idempotent_when_called_twice(self):
        self.bill()
        self.assertEqual(recurring.ensure_recurring(date(2026, 6, 15)), 2)
        self.assertEqual(recurring.ensure_recurring(date(2026, 6, 15)), 0)
        self.assertEqual(Payable.objects.count(), 2)

    def test_idempotent_under_integrity_error(self):
        bill = self.bill()
        Payable.objects.create(description='x', category=self.category, amount=D('1'), due_date=date(2026, 6, 10),
                               recurring=bill, period=date(2026, 6, 1))
        self.assertEqual(recurring.ensure_recurring(date(2026, 6, 15)), 1)  # só julho
        # Corrida: get_or_create não encontra a linha, mas o INSERT bate na restrição única.
        with mock.patch.object(Payable.objects, 'get_or_create', side_effect=IntegrityError):
            self.assertEqual(recurring.ensure_recurring(date(2026, 6, 15)), 0)

    def test_unique_constraint_blocks_duplicates(self):
        bill = self.bill()
        make = lambda: Payable.objects.create(description='x', category=self.category, amount=D('1'),
                                              due_date=date(2026, 6, 10), recurring=bill, period=date(2026, 6, 1))
        make()
        with self.assertRaises(IntegrityError):
            make()

    def test_installments_stop_at_last_and_are_numbered(self):
        self.bill(start=date(2026, 10, 1), installments=3)
        recurring.ensure_recurring(date(2026, 10, 5))
        recurring.ensure_recurring(date(2026, 11, 5))
        recurring.ensure_recurring(date(2026, 12, 5))
        recurring.ensure_recurring(date(2027, 1, 5))
        recurring.ensure_recurring(date(2027, 2, 5))
        rows = list(Payable.objects.order_by('period'))
        self.assertEqual([(r.period.month, r.installment_number, r.installments_total) for r in rows],
                         [(10, 1, 3), (11, 2, 3), (12, 3, 3)])

    def test_number_comes_from_month_difference_not_row_count(self):
        bill = self.bill(start=date(2026, 6, 1), installments=10)
        recurring.ensure_recurring(date(2026, 6, 5))
        Payable.objects.filter(recurring=bill, period=date(2026, 6, 1)).delete()
        recurring.ensure_recurring(date(2026, 7, 5))
        self.assertEqual(Payable.objects.get(period=date(2026, 8, 1)).installment_number, 3)

    def test_no_rows_before_start_date_month(self):
        self.bill(start=date(2026, 9, 1))
        self.assertEqual(recurring.ensure_recurring(date(2026, 6, 15)), 0)
        self.assertEqual(recurring.ensure_recurring(date(2026, 8, 15)), 1)  # só setembro (mês seguinte)
        self.assertEqual(Payable.objects.get().period, date(2026, 9, 1))

    def test_inactive_recurring_is_skipped(self):
        self.bill(active=False)
        self.assertEqual(recurring.ensure_recurring(date(2026, 6, 15)), 0)

    def test_canceled_generated_payable_is_not_regenerated(self):
        self.bill()
        recurring.ensure_recurring(date(2026, 6, 15))
        Payable.objects.filter(period=date(2026, 6, 1)).update(status=Payable.Status.CANCELED)
        self.assertEqual(recurring.ensure_recurring(date(2026, 6, 15)), 0)
        self.assertEqual(Payable.objects.count(), 2)

    def test_skips_months_before_treasury_start(self):
        configure(date(2026, 7, 1))
        self.bill(start=date(2026, 1, 1))
        recurring.ensure_recurring(date(2026, 6, 15))
        self.assertEqual(list(Payable.objects.values_list('period', flat=True)), [date(2026, 7, 1)])

    def test_works_without_treasury_settings(self):
        from tesouraria.models import TreasurySettings
        TreasurySettings.objects.all().delete()
        self.bill()
        self.assertEqual(recurring.ensure_recurring(date(2026, 6, 15)), 2)

    def test_generation_writes_no_audit_rows(self):
        self.bill()
        recurring.ensure_recurring(date(2026, 6, 15))
        self.assertFalse(AuditLog.objects.filter(model='Payable').exists())

    def test_deactivating_stops_future_but_keeps_created(self):
        bill = self.bill()
        recurring.ensure_recurring(date(2026, 6, 15))
        recurring.set_active(self.tes, bill, False)
        recurring.ensure_recurring(date(2026, 8, 15))
        self.assertEqual(Payable.objects.count(), 2)
        self.assertEqual(AuditLog.objects.filter(model='RecurringBill', action='update').count(), 1)

    def test_editing_affects_only_future_payables(self):
        bill = self.bill()
        recurring.ensure_recurring(date(2026, 6, 15))
        recurring.update_recurring(self.tes, bill, description='Aluguel', payee='', category=self.category,
                                   amount=D('1800.00'), due_day=15, start_date=date(2026, 6, 1), installments=None)
        recurring.ensure_recurring(date(2026, 7, 15))
        amounts = dict(Payable.objects.values_list('period', 'amount'))
        self.assertEqual(amounts[date(2026, 6, 1)], D('1500.00'))
        self.assertEqual(amounts[date(2026, 8, 1)], D('1800.00'))

    def test_generated_payable_can_be_edited_and_paid_via_service(self):
        from tesouraria import payables
        self.bill()
        recurring.ensure_recurring(date(2026, 6, 15))
        p = Payable.objects.get(period=date(2026, 6, 1))
        payables.update_payable(self.tes, p, description='Aluguel', payee='', category=self.category,
                                amount=D('1600.00'), due_date=date(2026, 6, 12))
        p.refresh_from_db()
        self.assertEqual(p.amount, D('1600.00'))
        self.assertIsNotNone(p.recurring_id)


class RecurringServiceTests(RecurringBase):
    def fields(self, **kw):
        data = dict(description='Internet', payee='Operadora', category=self.category, amount=D('120.00'),
                    due_day=10, start_date=date(2026, 6, 1), installments=None)
        data.update(kw)
        return data

    def test_create_audits_and_validates(self):
        bill = recurring.create_recurring(self.tes, **self.fields())
        self.assertTrue(AuditLog.objects.filter(action='create', model='RecurringBill',
                                                object_id=str(bill.pk)).exists())
        for bad in ({'amount': D('0')}, {'amount': D('1.005')}, {'amount': D('10000000000.00')},
                    {'due_day': 0}, {'due_day': 32}, {'installments': 0}, {'description': '  '},
                    {'start_date': None}):
            with self.assertRaises(TreasuryError, msg=bad):
                recurring.create_recurring(self.tes, **self.fields(**bad))
        income = Category.objects.filter(kind=Kind.INCOME).first()
        with self.assertRaises(TreasuryError):
            recurring.create_recurring(self.tes, **self.fields(category=income))

    def test_update_keeps_before_snapshot(self):
        bill = recurring.create_recurring(self.tes, **self.fields())
        recurring.update_recurring(self.tes, bill, **self.fields(amount=D('150.00')))
        log = AuditLog.objects.get(action='update', model='RecurringBill')
        self.assertEqual(log.before['amount'], '120.00')
        self.assertEqual(log.after['amount'], '150.00')


class RecurringFormTests(RecurringBase):
    def test_archived_category_not_offered_for_new_but_kept_on_edit(self):
        self.category.active = False
        self.category.save()
        self.assertNotIn(self.category, RecurringForm().fields['category'].queryset)
        self.assertIn(self.category, RecurringForm(current_category=self.category).fields['category'].queryset)

    def test_category_in_use_by_recurring(self):
        cat = Category.objects.create(name='Nova saída', kind=Kind.EXPENSE)
        self.assertFalse(cat.in_use())
        self.bill(category=cat)
        self.assertTrue(cat.in_use())


@WITHOUT_AXES
class RecurringViewTests(RecurringBase):
    def setUp(self):
        super().setUp()
        self.com = make_user('com', Role.COMMITTEE)
        self.board = make_user('dir', Role.BOARD)
        self.url = reverse('tesouraria:recurring')
        self.post_data = {'description': 'Água', 'payee': 'Cia', 'category': self.category.pk, 'amount': '90.00',
                          'due_day': '8', 'start_date': '2026-06-01', 'installments': ''}

    def login(self, user):
        self.client.login(username=user.username, password='senha-forte-123')

    def test_treasurer_creates_edits_and_toggles(self):
        self.login(self.tes)
        r = self.client.post(reverse('tesouraria:recurring_create'), self.post_data)
        self.assertRedirects(r, self.url)
        bill = RecurringBill.objects.get()
        self.assertEqual(bill.created_by, self.tes)
        self.assertContains(self.client.get(reverse('tesouraria:recurring_edit', args=[bill.pk])),
                            'valem apenas para as próximas contas')
        self.post_data['amount'] = '95.00'
        self.client.post(reverse('tesouraria:recurring_edit', args=[bill.pk]), self.post_data)
        bill.refresh_from_db()
        self.assertEqual(bill.amount, D('95.00'))
        self.client.post(reverse('tesouraria:recurring_toggle', args=[bill.pk]))
        bill.refresh_from_db()
        self.assertFalse(bill.active)
        self.client.post(reverse('tesouraria:recurring_toggle', args=[bill.pk]))
        bill.refresh_from_db()
        self.assertTrue(bill.active)

    def test_invalid_post_shows_error_and_creates_nothing(self):
        self.login(self.tes)
        self.post_data['due_day'] = '40'
        r = self.client.post(reverse('tesouraria:recurring_create'), self.post_data)
        self.assertEqual(r.status_code, 200)
        self.assertFalse(RecurringBill.objects.exists())

    def test_readers_cannot_create_recurring(self):
        bill = self.bill()
        self.login(self.com)
        self.assertEqual(self.client.get(self.url).status_code, 200)
        for name, args in (('recurring_create', []), ('recurring_edit', [bill.pk]), ('recurring_toggle', [bill.pk])):
            self.assertEqual(self.client.post(reverse(f'tesouraria:{name}', args=args),
                                              self.post_data).status_code, 403)
        self.assertEqual(self.client.get(reverse('tesouraria:recurring_create')).status_code, 403)
        bill.refresh_from_db()
        self.assertTrue(bill.active)
        self.assertEqual(RecurringBill.objects.count(), 1)

    def test_board_gets_403(self):
        self.login(self.board)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_nav_item_for_treasurer_and_committee_not_board(self):
        for user, expected in ((self.tes, True), (self.com, True), (self.board, False)):
            request = mock.Mock(user=user, resolver_match=None)
            nav = build_treasury_nav(request)
            urls = [i['url'] for i in nav['groups'][0]['items']]
            self.assertEqual(self.url in urls, expected, user.username)

    def test_open_screen_triggers_generation(self):
        self.bill(start=date(2020, 1, 1))
        self.login(self.tes)
        self.client.get(reverse('tesouraria:payables'))
        self.assertEqual(Payable.objects.count(), 2)
        Payable.objects.all().delete()
        self.client.get(reverse('tesouraria:home'))
        self.assertEqual(Payable.objects.count(), 2)

    def test_committee_opening_payables_generates_and_shows_installment(self):
        today = timezone.localdate()
        self.bill(start=today.replace(day=1), installments=10)
        self.login(self.com)
        r = self.client.get(reverse('tesouraria:payables') + '?aba=a-vencer')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(Payable.objects.filter(installment_number=1, installments_total=10).exists())
        self.assertFalse(AuditLog.objects.filter(model='Payable').exists())
        self.assertContains(self.client.get(reverse('tesouraria:payables') + '?aba=a-vencer'), '2/10')
