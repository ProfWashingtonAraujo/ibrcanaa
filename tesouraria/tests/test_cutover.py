"""Virada: portal grava "a confirmar", fim do Financeiro antigo e "Histórico anterior"."""

from datetime import date
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.contrib import admin
from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import RequestFactory, TestCase, override_settings
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from core.models import AccessProfile, Member, Transaction
from tesouraria import pending
from tesouraria.balances import total_balance
from tesouraria.models import (AuditLog, Category, Kind, Movement, Payable, RecurringBill, Source, Status,
                               TreasurySettings)
from tesouraria.permissions import landing_url

from .helpers import WITHOUT_AXES, configure, make_user

Role = AccessProfile.Role


def portal_member(username='membro', name='Maria Membro'):
    user = make_user(username, Role.MEMBER)
    member = Member.objects.create(user=user, name=name, email=f'{username}@example.com')
    return user, member


def contribute(client, amount='250.50', category='Dízimos', note='Contribuição de agosto'):
    return client.post(reverse('member_portal'), {
        'category': category, 'amount': amount, 'note': note,
        # Campos que o membro não controla: ignorados.
        'member': '999', 'kind': Kind.EXPENSE, 'status': Status.CONFIRMED, 'account': 'cash',
    })


@WITHOUT_AXES
class PortalTests(TestCase):
    def setUp(self):
        configure(date(2026, 1, 1), cash='100.00', bank='200.00')
        self.user, self.member = portal_member()
        self.client.force_login(self.user)
        self.treasurer = make_user('tes', Role.TREASURER)

    def test_portal_contribution_is_pending_and_does_not_touch_balances(self):
        before = total_balance(timezone.localdate())
        response = contribute(self.client)
        self.assertRedirects(response, reverse('member_portal'))
        movement = Movement.objects.get()
        self.assertEqual(movement.status, Status.PENDING)
        self.assertEqual(movement.source, Source.PORTAL)
        self.assertEqual(movement.kind, Kind.INCOME)
        self.assertEqual(movement.member, self.member)
        self.assertIsNone(movement.account)
        self.assertEqual(movement.amount, Decimal('250.50'))
        self.assertEqual(movement.category.name, 'Dízimos')
        self.assertTrue(movement.category.is_tithe)
        self.assertEqual(movement.created_by, self.user)
        self.assertEqual(Transaction.objects.count(), 0)
        self.assertEqual(total_balance(timezone.localdate()), before)

    def test_portal_keeps_amount_validation(self):
        response = contribute(self.client, amount='0')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Certifique-se que este valor seja maior ou igual a 1.00')
        self.assertFalse(Movement.objects.exists())

    def test_portal_shows_waiting_then_confirmed_total(self):
        contribute(self.client)
        portal = self.client.get(reverse('member_portal'))
        self.assertContains(portal, 'aguardando confirmação')
        self.assertEqual(portal.context['contribution_total'], Decimal('0'))

        pending.confirm_pending(Movement.objects.get(), user=self.treasurer, account='bank', method='pix',
                                date=timezone.localdate())
        portal = self.client.get(reverse('member_portal'))
        self.assertNotContains(portal, 'aguardando confirmação')
        self.assertEqual(portal.context['contribution_total'], Decimal('250.50'))
        self.assertContains(portal, 'R$ 250,50')

    def test_rejected_contribution_shows_reason_to_member(self):
        contribute(self.client, amount='80.00')
        pending.reject_pending(Movement.objects.get(), user=self.treasurer, reason='Valor não encontrado no extrato')
        portal = self.client.get(reverse('member_portal'))
        self.assertContains(portal, 'Recusada')
        self.assertContains(portal, 'Valor não encontrado no extrato')
        self.assertEqual(portal.context['contribution_total'], Decimal('0'))

    def test_portal_only_shows_own_contributions(self):
        other_user, other = portal_member('outro', 'Outro Membro')
        pending.create_portal_contribution(other, 'Ofertas', Decimal('777.77'), 'segredo do outro')
        Movement.objects.create(date=timezone.localdate(), kind=Kind.INCOME, amount=Decimal('555.55'),
                                category=Category.objects.get(name='Dízimos', kind=Kind.INCOME),
                                description='Dízimo de outro', account='cash', member=other)
        contribute(self.client, amount='12.00')
        portal = self.client.get(reverse('member_portal'))
        self.assertNotContains(portal, '777,77')
        self.assertNotContains(portal, '555,55')
        self.assertNotContains(portal, 'Outro Membro')
        self.assertEqual([m.member for m in portal.context['contributions']], [self.member])

    def test_portal_accepts_declaration_before_treasury_is_configured(self):
        TreasurySettings.objects.all().delete()
        response = contribute(self.client)
        self.assertRedirects(response, reverse('member_portal'))
        self.assertEqual(Movement.objects.get().status, Status.PENDING)

    def test_portal_handles_missing_or_archived_category(self):
        Category.objects.filter(name='Dízimos', kind=Kind.INCOME).update(active=False)
        response = contribute(self.client)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'não está disponível')
        Category.objects.filter(name='Ofertas', kind=Kind.INCOME).delete()
        response = contribute(self.client, category='Ofertas')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'não está disponível')
        self.assertFalse(Movement.objects.exists())


@WITHOUT_AXES
class OldFinanceRemovedTests(TestCase):
    def setUp(self):
        configure(date(2026, 1, 1), cash='1234.56', bank='6543.21')
        Transaction.objects.create(date=date(2025, 8, 12), description='Valor antigo', category='Dízimos',
                                   kind=Transaction.Kind.INCOME, amount=Decimal('9876.54'))

    def test_old_finance_urls_are_gone(self):
        for name in ('finance', 'transaction_create'):
            with self.subTest(name=name), self.assertRaises(NoReverseMatch):
                reverse(name)
        self.client.force_login(make_user('board', Role.BOARD))
        self.assertEqual(self.client.get('/admin/financeiro/').status_code, 404)
        self.assertEqual(self.client.get('/admin/financeiro/novo/').status_code, 404)

    def test_panel_has_no_financial_data_or_menu_item(self):
        users = [make_user('tes', Role.TREASURER), make_user('board', Role.BOARD),
                 make_user('root', None, is_staff=True, is_superuser=True), make_user('pastor', Role.PASTOR)]
        for user in users:
            self.client.force_login(user)
            for name in ('dashboard', 'reports'):
                with self.subTest(user=user.username, page=name):
                    response = self.client.get(reverse(name))
                    self.assertEqual(response.status_code, 200)
                    for text in ('Financeiro', 'financeiro', 'Saldo', '9876', '9.876', '1234', '1.234'):
                        self.assertNotContains(response, text)
                    for key in ('show_finances', 'balance', 'income', 'expense'):
                        self.assertNotIn(key, response.context)

    def test_panel_topbar_has_treasury_shortcut_only_for_treasury_profiles(self):
        link = f'href="{reverse("tesouraria:home")}"'
        for user in (make_user('tes', Role.TREASURER), make_user('board', Role.BOARD),
                     make_user('root', None, is_staff=True, is_superuser=True)):
            self.client.force_login(user)
            with self.subTest(user=user.username):
                self.assertContains(self.client.get(reverse('dashboard')), link)
        for role in (Role.PASTOR, Role.SECRETARY, Role.DEACON):
            self.client.force_login(make_user(f'n-{role}', role))
            with self.subTest(role=role):
                self.assertNotContains(self.client.get(reverse('dashboard')), link)

    def test_roles_without_treasury_land_on_dashboard_and_are_blocked(self):
        for role in (Role.PASTOR, Role.SECRETARY, Role.DEACON):
            user = make_user(f'u-{role}', role)
            with self.subTest(role=role):
                self.assertEqual(landing_url(user), reverse('dashboard'))
                self.client.force_login(user)
                self.assertEqual(self.client.get(reverse('dashboard')).status_code, 200)
                self.assertEqual(self.client.get(reverse('tesouraria:home')).status_code, 403)
                self.assertEqual(self.client.get(reverse('tesouraria:legacy')).status_code, 403)


@WITHOUT_AXES
class LegacyTests(TestCase):
    def setUp(self):
        self.member = Member.objects.create(name='João Antigo', email='joao@example.com')
        Transaction.objects.create(date=date(2025, 3, 1), description='Conta de luz antiga', category='Manutenção',
                                   kind=Transaction.Kind.EXPENSE, amount=Decimal('1350.00'))
        Transaction.objects.create(date=date(2025, 4, 2), description='<script>alert(1)</script>',
                                   category='Dízimos', kind=Transaction.Kind.INCOME, amount=Decimal('500.00'),
                                   member=self.member)

    def _body(self, response):
        html = response.content.decode()
        start, end = html.index('<!-- legacy:start -->'), html.index('<!-- legacy:end -->')
        return html[start:end]

    def test_legacy_page_lists_old_transactions_read_only(self):
        for user in (make_user('tes', Role.TREASURER), make_user('com', Role.COMMITTEE),
                     make_user('root', None, is_staff=True, is_superuser=True)):
            self.client.force_login(user)
            with self.subTest(user=user.username):
                response = self.client.get(reverse('tesouraria:legacy'))
                self.assertEqual(response.status_code, 200)
                body = self._body(response)
                self.assertIn('Conta de luz antiga', body)
                self.assertIn('R$ 1.350,00', body)
                self.assertIn('João Antigo', body)
                self.assertIn('&lt;script&gt;', body)
                self.assertNotIn('<script>alert', body)
                for tag in ('<form', '<button', '<input', '<textarea', '<select'):
                    self.assertNotIn(tag, body)
                # Mais recente primeiro.
                self.assertLess(body.index('&lt;script&gt;'), body.index('Conta de luz antiga'))
                self.assertEqual(self.client.post(reverse('tesouraria:legacy')).status_code, 405)
        for role in (Role.BOARD, Role.SECRETARY):
            self.client.force_login(make_user(f'x-{role}', role))
            with self.subTest(role=role):
                self.assertEqual(self.client.get(reverse('tesouraria:legacy')).status_code, 403)
                self.assertEqual(self.client.post(reverse('tesouraria:legacy')).status_code, 403)
        self.assertEqual(Transaction.objects.count(), 2)

    def test_legacy_page_is_limited_with_note(self):
        self.client.force_login(make_user('tes', Role.TREASURER))
        with patch('tesouraria.views.LEGACY_LIMIT', 1):
            response = self.client.get(reverse('tesouraria:legacy'))
        self.assertEqual(len(response.context['transactions']), 1)
        self.assertContains(response, 'Mostrando só os 1 lançamentos mais recentes de 2')

    def test_legacy_page_appears_in_treasury_menu(self):
        self.client.force_login(make_user('tes', Role.TREASURER))
        configure()
        response = self.client.get(reverse('tesouraria:legacy'))
        self.assertContains(response, 'Histórico anterior')
        self.assertContains(response, f'href="{reverse("tesouraria:legacy")}"')


class TransactionAdminTests(TestCase):
    def test_transaction_admin_is_read_only(self):
        root = make_user('root', None, is_staff=True, is_superuser=True)
        model_admin = admin.site._registry[Transaction]
        request = RequestFactory().get('/')
        request.user = root
        self.assertFalse(model_admin.has_add_permission(request))
        self.assertFalse(model_admin.has_change_permission(request))
        self.assertFalse(model_admin.has_delete_permission(request))
        self.assertTrue(model_admin.has_view_permission(request))
        transaction_row = Transaction.objects.create(date=date(2025, 1, 1), description='x', category='Ofertas',
                                                     kind=Transaction.Kind.INCOME, amount=Decimal('1.00'))
        self.client.force_login(root)
        self.assertEqual(self.client.get(reverse('admin:core_transaction_changelist')).status_code, 200)
        self.assertEqual(self.client.get(reverse('admin:core_transaction_add')).status_code, 403)
        self.assertEqual(self.client.post(reverse('admin:core_transaction_delete', args=[transaction_row.pk]),
                                          {'post': 'yes'}).status_code, 403)
        self.assertTrue(Transaction.objects.filter(pk=transaction_row.pk).exists())


@override_settings(DEBUG=True)
class SeedDemoTests(TestCase):
    def _run(self):
        out = StringIO()
        call_command('seed_demo', stdout=out)
        return out.getvalue()

    def _counts(self):
        return {
            'categories': Category.objects.count(), 'movements': Movement.objects.count(),
            'payables': Payable.objects.count(), 'recurring': RecurringBill.objects.count(),
            'users': User.objects.count(), 'transactions': Transaction.objects.count(),
            'members': Member.objects.count(),
        }

    def test_seed_demo_creates_treasury_data(self):
        self._run()
        settings_obj = TreasurySettings.get()
        self.assertIsNotNone(settings_obj)
        self.assertGreater(settings_obj.opening_cash + settings_obj.opening_bank, 0)
        self.assertLessEqual(settings_obj.start_date, timezone.localdate())
        for name in ('Dízimos', 'Ofertas', 'Ofertas especiais'):
            self.assertTrue(Category.objects.filter(name=name, kind=Kind.INCOME).exists())
        self.assertTrue(Category.objects.filter(kind=Kind.EXPENSE).exists())
        confirmed = Movement.objects.counted()
        self.assertEqual(set(confirmed.values_list('account', flat=True)), {'cash', 'bank'})
        self.assertTrue(confirmed.filter(category__is_tithe=True, member__isnull=False).exists())
        self.assertTrue(Movement.objects.filter(status=Status.PENDING, source=Source.PORTAL).exists())
        self.assertTrue(Payable.objects.filter(recurring__isnull=True).exists())
        self.assertTrue(RecurringBill.objects.filter(active=True).exists())
        self.assertEqual(User.objects.get(username='tesoureiro').access_profile.role, Role.TREASURER)
        self.assertTrue(User.objects.get(username='tesoureiro').is_staff)
        self.assertEqual(User.objects.get(username='comissao').access_profile.role, Role.COMMITTEE)
        self.assertTrue(Transaction.objects.exists())  # demonstração do "Histórico anterior"

        first = self._counts()
        self._run()
        self.assertEqual(self._counts(), first)
        self.assertEqual(TreasurySettings.objects.count(), 1)
        self.assertTrue(AuditLog.objects.exists())
