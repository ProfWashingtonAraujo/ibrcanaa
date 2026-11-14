from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from core.models import AccessProfile, Member
from tesouraria import pending
from tesouraria.balances import total_balance
from tesouraria.models import AuditLog, Category, Kind, MonthClosing, Movement, Status
from tesouraria.rules import TreasuryError

from .helpers import WITHOUT_AXES, configure, make_user

Role = AccessProfile.Role
JUN = date(2026, 6, 10)


@WITHOUT_AXES
class PendingBase(TestCase):
    def setUp(self):
        configure(date(2026, 1, 1), cash='100.00', bank='1000.00')
        self.tes = make_user('tes', Role.TREASURER)
        self.client.force_login(self.tes)
        self.member_user = make_user('maria')
        self.member = Member.objects.create(name='Maria Souza', email='maria@example.com', user=self.member_user)
        self.movement = pending.create_portal_contribution(self.member, 'Dízimos', Decimal('150.00'), '')

    def confirm(self, **extra):
        return pending.confirm_pending(self.movement, user=self.tes, **{
            'account': 'bank', 'method': 'pix', 'date': JUN, **extra})

    def post_confirm(self, **extra):
        pk = self.movement.pk
        data = {f'c{pk}-account': 'bank', f'c{pk}-method': 'pix', f'c{pk}-date': '2026-06-10'}
        data.update({f'c{pk}-{k}': v for k, v in extra.items()})
        return self.client.post(reverse('tesouraria:pending_confirm', args=[self.movement.pk]), data)


class PendingServiceTests(PendingBase):
    def test_portal_contribution_shape(self):
        m = self.movement
        self.assertEqual((m.status, m.source, m.account, m.method), (Status.PENDING, 'portal', None, 'pix'))
        self.assertEqual(m.description, 'Dízimo via portal - Maria Souza')
        self.assertEqual(m.created_by, self.member_user)

    def test_confirm_moves_money_into_chosen_account(self):
        total_before = total_balance(date(2026, 6, 30))
        self.confirm()
        self.movement.refresh_from_db()
        self.assertEqual((self.movement.status, self.movement.account, self.movement.date),
                         (Status.CONFIRMED, 'bank', JUN))
        self.assertEqual(total_balance(date(2026, 6, 30)), total_before + Decimal('150.00'))
        self.assertTrue(AuditLog.objects.filter(action='confirm', object_id=str(self.movement.pk)).exists())

    def test_pending_does_not_change_balances_until_confirmed(self):
        self.assertEqual(total_balance(date(2026, 6, 30)), Decimal('1100.00'))
        self.confirm()
        self.assertEqual(total_balance(date(2026, 6, 30)), Decimal('1250.00'))

    def test_reject_requires_reason_and_never_counts(self):
        with self.assertRaises(TreasuryError):
            pending.reject_pending(self.movement, user=self.tes, reason='  ')
        pending.reject_pending(self.movement, user=self.tes, reason='Não localizei o Pix')
        self.movement.refresh_from_db()
        self.assertEqual((self.movement.status, self.movement.rejection_reason),
                         (Status.REJECTED, 'Não localizei o Pix'))
        self.assertEqual(total_balance(date(2026, 6, 30)), Decimal('1100.00'))

    def test_cannot_confirm_twice(self):
        self.confirm()
        with self.assertRaisesMessage(TreasuryError, 'já foi tratado'):
            self.confirm()
        with self.assertRaisesMessage(TreasuryError, 'já foi tratado'):
            pending.reject_pending(self.movement, user=self.tes, reason='x')

    def test_confirm_into_closed_month_requires_open_date(self):
        MonthClosing.objects.create(month=date(2026, 6, 1), closed_at='2026-07-01T00:00:00Z')
        response = self.post_confirm()
        self.assertContains(response, 'fechado')
        self.movement.refresh_from_db()
        self.assertEqual(self.movement.status, Status.PENDING)
        self.assertEqual(self.post_confirm(date='2026-07-02').status_code, 302)

    def test_confirm_before_start_is_refused(self):
        with self.assertRaises(TreasuryError):
            self.confirm(date=date(2025, 12, 31))
        self.movement.refresh_from_db()
        self.assertEqual(self.movement.status, Status.PENDING)


class PendingViewTests(PendingBase):
    def test_queue_shows_member_name_to_treasurer_only(self):
        url = reverse('tesouraria:pending')
        self.assertContains(self.client.get(url), 'Maria Souza')
        self.client.force_login(make_user('com', Role.COMMITTEE))
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_login(make_user('dir', Role.BOARD))
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_empty_queue_invites(self):
        self.confirm()
        self.assertContains(self.client.get(reverse('tesouraria:pending')), 'Nada a confirmar')

    def test_confirm_via_view_and_nav_count(self):
        self.assertContains(self.client.get(reverse('tesouraria:pending')), 'A confirmar')
        self.assertEqual(self.post_confirm().status_code, 302)
        self.movement.refresh_from_db()
        self.assertEqual(self.movement.status, Status.CONFIRMED)

    def test_reject_via_view_needs_reason(self):
        url = reverse('tesouraria:pending_reject', args=[self.movement.pk])
        pk = self.movement.pk
        self.assertContains(self.client.post(url, {f'r{pk}-reason': ''}), 'motivo da recusa')
        self.client.post(url, {f'r{pk}-reason': 'Duplicado'})
        self.movement.refresh_from_db()
        self.assertEqual(self.movement.status, Status.REJECTED)

    def test_second_action_shows_message(self):
        self.post_confirm()
        pk = self.movement.pk
        response = self.client.post(
            reverse('tesouraria:pending_confirm', args=[pk]),
            {f'c{pk}-account': 'bank', f'c{pk}-method': 'pix', f'c{pk}-date': '2026-06-10'}, follow=True)
        self.assertContains(response, 'já foi tratado')

    def test_readers_cannot_post_confirm(self):
        for role in (Role.COMMITTEE, Role.BOARD):
            self.client.force_login(make_user(f'u{role}', role))
            self.assertEqual(self.post_confirm().status_code, 403)
        self.movement.refresh_from_db()
        self.assertEqual(self.movement.status, Status.PENDING)
