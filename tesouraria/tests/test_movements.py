from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import AccessProfile, Member
from tesouraria import ledger
from tesouraria.balances import account_balance, total_balance
from tesouraria.models import (Account, AuditLog, Category, Kind, Method, Movement, MonthClosing, Status,
                               Transfer)
from tesouraria.rules import TreasuryError

from .helpers import WITHOUT_AXES, configure, make_user

Role = AccessProfile.Role
JUN = date(2026, 6, 10)


def post_data(category, **extra):
    data = {'date': '2026-06-10', 'category': category.pk, 'description': 'Oferta do culto',
            'amount': '120.00', 'account': 'cash', 'method': 'cash', 'member': '', 'destination': ''}
    data.update(extra)
    return data


def make_member(name='Maria Souza', email='maria@example.com'):
    return Member.objects.create(name=name, email=email)


@WITHOUT_AXES
class MovementBase(TestCase):
    def setUp(self):
        configure(date(2026, 1, 1), cash='100.00', bank='1000.00')
        self.tes = make_user('tes', Role.TREASURER)
        self.client.force_login(self.tes)
        self.income = Category.objects.get(name='Ofertas', kind=Kind.INCOME)
        self.tithe = Category.objects.get(name='Dízimos')
        self.special = Category.objects.get(name='Ofertas especiais')
        self.expense = Category.objects.get(name='Manutenção')

    def make(self, category=None, when=JUN, amount='50.00', **extra):
        category = category or self.income
        fields = dict(date=when, kind=category.kind, amount=Decimal(amount), category=category,
                      description='Lançamento', account=Account.CASH)
        fields.update(extra)
        return Movement.objects.create(**fields)

    def close_month(self, when=JUN):
        MonthClosing.objects.create(month=when.replace(day=1), closed_at=timezone.now())


class CreateTests(MovementBase):
    def test_create_income_cash_updates_cash_balance(self):
        response = self.client.post(reverse('tesouraria:movement_create') + '?tipo=income', post_data(self.income))
        self.assertEqual(response.status_code, 302)
        movement = Movement.objects.get()
        self.assertEqual((movement.kind, movement.amount, movement.account, movement.status),
                         ('income', Decimal('120.00'), 'cash', 'confirmed'))
        self.assertEqual(movement.created_by, self.tes)
        self.assertEqual(account_balance(Account.CASH, date(2026, 6, 30)), Decimal('220.00'))
        log = AuditLog.objects.get(action='create')
        self.assertEqual(log.summary, 'Entrada de R$ 120,00 em Ofertas')

    def test_create_expense_from_bank(self):
        data = post_data(self.expense, account='bank', method='pix', amount='300.00')
        self.client.post(reverse('tesouraria:movement_create') + '?tipo=expense', data)
        movement = Movement.objects.get()
        self.assertEqual((movement.kind, movement.account), ('expense', 'bank'))
        self.assertEqual(account_balance(Account.BANK, date(2026, 6, 30)), Decimal('700.00'))

    def test_special_offering_requires_destination(self):
        url = reverse('tesouraria:movement_create') + '?tipo=income'
        response = self.client.post(url, post_data(self.special))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Movement.objects.exists())
        self.assertIn('destination', response.context['form'].errors)
        self.client.post(url, post_data(self.special, destination='Missões'))
        self.assertEqual(Movement.objects.get().destination, 'Missões')

    def test_destination_cleared_for_non_special_category(self):
        self.client.post(reverse('tesouraria:movement_create') + '?tipo=income',
                         post_data(self.income, destination='Missões'))
        self.assertEqual(Movement.objects.get().destination, '')

    def test_amount_must_be_positive(self):
        url = reverse('tesouraria:movement_create') + '?tipo=income'
        for value in ('0', '-5', '1.234', 'abc'):
            with self.subTest(value=value):
                response = self.client.post(url, post_data(self.income, amount=value))
                self.assertEqual(response.status_code, 200)
                self.assertIn('amount', response.context['form'].errors)
        self.assertFalse(Movement.objects.exists())

    def test_account_is_required(self):
        response = self.client.post(reverse('tesouraria:movement_create') + '?tipo=income',
                                    post_data(self.income, account=''))
        self.assertIn('account', response.context['form'].errors)

    def test_category_must_match_type(self):
        response = self.client.post(reverse('tesouraria:movement_create') + '?tipo=income',
                                    post_data(self.expense))
        self.assertIn('category', response.context['form'].errors)

    def test_tithe_without_member_saves_with_hint_and_with_member_keeps_link(self):
        url = reverse('tesouraria:movement_create') + '?tipo=income'
        response = self.client.post(url, post_data(self.tithe, amount='80.00'), follow=True)
        self.assertEqual(Movement.objects.count(), 1)
        self.assertContains(response, 'Informe o membro para ele constar na relação de dizimistas')
        member = make_member()
        response = self.client.post(url, post_data(self.tithe, member=member.pk), follow=True)
        self.assertNotContains(response, 'Informe o membro para ele constar')
        self.assertEqual(Movement.objects.get(member=member).category, self.tithe)

    def test_create_form_shows_only_active_categories_of_type(self):
        Category.objects.create(name='Antiga', kind=Kind.INCOME, active=False)
        response = self.client.get(reverse('tesouraria:movement_create') + '?tipo=income')
        names = [c.name for c in response.context['form'].fields['category'].queryset]
        self.assertIn('Ofertas', names)
        self.assertNotIn('Antiga', names)
        self.assertNotIn('Manutenção', names)

    def test_before_start_date_is_refused(self):
        response = self.client.post(reverse('tesouraria:movement_create') + '?tipo=income',
                                    post_data(self.income, date='2025-12-31'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'anterior ao início')
        self.assertFalse(Movement.objects.exists())


class ConstraintTests(MovementBase):
    def test_confirmed_without_account_rejected_by_service_and_database(self):
        with self.assertRaises(TreasuryError):
            ledger.create_movement(self.tes, date=JUN, category=self.income, description='x',
                                   amount=Decimal('10.00'), account=None, method=Method.CASH)
        self.assertFalse(Movement.objects.exists())
        with self.assertRaises(IntegrityError), transaction.atomic():
            Movement.objects.create(date=JUN, kind='income', amount=Decimal('1.00'), category=self.income,
                                    description='x', account=None, status=Status.CONFIRMED)
        # pendente sem conta continua permitido (fila da Task 7)
        Movement.objects.create(date=JUN, kind='income', amount=Decimal('1.00'), category=self.income,
                                description='x', account=None, status=Status.PENDING)

    def test_update_cannot_clear_account(self):
        movement = self.make()
        with self.assertRaises(TreasuryError):
            ledger.update_movement(self.tes, movement, account=None)


class EditDeleteTests(MovementBase):
    def test_edit_records_before_and_after_in_audit(self):
        movement = self.make(amount='50.00', description='Original')
        url = reverse('tesouraria:movement_edit', args=[movement.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        response = self.client.post(url, post_data(self.income, amount='75.50', description='Alterado'))
        self.assertEqual(response.status_code, 302)
        movement.refresh_from_db()
        self.assertEqual(movement.amount, Decimal('75.50'))
        log = AuditLog.objects.get(action='update')
        self.assertEqual(log.before['amount'], '50.00')
        self.assertEqual(log.after['amount'], '75.50')
        self.assertEqual(log.before['description'], 'Original')
        self.assertNotIn('Alterado', log.summary)

    def test_edit_moving_date_requires_both_months_open(self):
        movement = self.make(when=date(2026, 6, 10))
        self.close_month(date(2026, 7, 5))
        response = self.client.post(reverse('tesouraria:movement_edit', args=[movement.pk]),
                                    post_data(self.income, date='2026-07-05'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'fechado')
        movement.refresh_from_db()
        self.assertEqual(movement.date, date(2026, 6, 10))

    def test_delete_is_logical_and_audited(self):
        movement = self.make(description='Some da lista')
        response = self.client.post(reverse('tesouraria:movement_delete', args=[movement.pk]))
        self.assertEqual(response.status_code, 302)
        movement.refresh_from_db()
        self.assertIsNotNone(movement.deleted_at)
        self.assertEqual(AuditLog.objects.filter(action='delete', object_id=str(movement.pk)).count(), 1)
        listing = self.client.get(reverse('tesouraria:movements') + '?mes=2026-06')
        self.assertNotContains(listing, 'Some da lista')
        self.assertEqual(account_balance(Account.CASH, date(2026, 6, 30)), Decimal('100.00'))

    def test_delete_requires_post(self):
        movement = self.make()
        response = self.client.get(reverse('tesouraria:movement_delete', args=[movement.pk]))
        self.assertEqual(response.status_code, 405)

    def test_closed_month_blocks_create_edit_delete(self):
        movement = self.make()
        self.close_month()
        response = self.client.post(reverse('tesouraria:movement_create') + '?tipo=income', post_data(self.income))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'fechado')
        response = self.client.post(reverse('tesouraria:movement_edit', args=[movement.pk]),
                                    post_data(self.income, amount='99.00'))
        self.assertContains(response, 'fechado')
        response = self.client.post(reverse('tesouraria:movement_delete', args=[movement.pk]), follow=True)
        self.assertContains(response, 'fechado')
        movement.refresh_from_db()
        self.assertEqual(movement.amount, Decimal('50.00'))
        self.assertIsNone(movement.deleted_at)
        self.assertEqual(Movement.objects.count(), 1)

    def test_pending_and_rejected_cannot_be_edited_or_deleted_here(self):
        for status in (Status.PENDING, Status.REJECTED):
            with self.subTest(status=status):
                movement = self.make(status=status, account=None)
                data = post_data(self.income)
                response = self.client.post(reverse('tesouraria:movement_edit', args=[movement.pk]), data)
                self.assertEqual(response.status_code, 200)
                response = self.client.post(reverse('tesouraria:movement_delete', args=[movement.pk]))
                self.assertEqual(response.status_code, 302)
                movement.refresh_from_db()
                self.assertIsNone(movement.deleted_at)
                self.assertEqual(self.client.get(reverse('tesouraria:movement_edit', args=[movement.pk])).status_code,
                                 302)

    def test_deleted_movement_is_404(self):
        movement = self.make(deleted_at=timezone.now())
        self.assertEqual(self.client.get(reverse('tesouraria:movement_edit', args=[movement.pk])).status_code, 404)

    def test_non_editors_cannot_write(self):
        movement = self.make()
        for role in (Role.COMMITTEE, Role.BOARD):
            self.client.force_login(make_user(f'u-{role}', role))
            self.assertEqual(self.client.post(reverse('tesouraria:movement_delete', args=[movement.pk])).status_code,
                             403)
            self.assertEqual(self.client.get(reverse('tesouraria:movement_create')).status_code, 403)
            self.assertEqual(self.client.get(reverse('tesouraria:transfer_create')).status_code, 403)


class TransferTests(MovementBase):
    def test_transfer_deposit_updates_both_accounts_and_not_totals(self):
        before_total = total_balance(date(2026, 6, 30))
        response = self.client.post(reverse('tesouraria:transfer_create'), {
            'from_account': 'cash', 'to_account': 'bank', 'date': '2026-06-12', 'amount': '60.00', 'note': ''})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(account_balance(Account.CASH, date(2026, 6, 30)), Decimal('40.00'))
        self.assertEqual(account_balance(Account.BANK, date(2026, 6, 30)), Decimal('1060.00'))
        self.assertEqual(total_balance(date(2026, 6, 30)), before_total)
        self.assertEqual(AuditLog.objects.get(action='create', model='Transfer').summary,
                         'Transferência de R$ 60,00 de Caixa para Banco')

    def test_transfer_validation(self):
        url = reverse('tesouraria:transfer_create')
        base = {'from_account': 'cash', 'to_account': 'bank', 'date': '2026-06-12', 'amount': '60.00'}
        for change in ({'to_account': 'cash'}, {'amount': '0'}, {'date': '2025-01-01'}):
            with self.subTest(change=change):
                response = self.client.post(url, {**base, **change})
                self.assertEqual(response.status_code, 200)
        self.assertFalse(Transfer.objects.exists())

    def test_transfer_delete_is_logical_and_blocked_in_closed_month(self):
        transfer = ledger.create_transfer(self.tes, from_account='cash', to_account='bank', date=date(2026, 6, 12),
                                          amount=Decimal('60.00'))
        self.close_month()
        response = self.client.post(reverse('tesouraria:transfer_delete', args=[transfer.pk]), follow=True)
        self.assertContains(response, 'fechado')
        transfer.refresh_from_db()
        self.assertIsNone(transfer.deleted_at)
        MonthClosing.objects.all().delete()
        self.client.post(reverse('tesouraria:transfer_delete', args=[transfer.pk]))
        transfer.refresh_from_db()
        self.assertIsNotNone(transfer.deleted_at)
        self.assertTrue(AuditLog.objects.filter(action='delete', model='Transfer').exists())


class ListTests(MovementBase):
    def test_movements_list_filters_by_type_category_account_method_and_month(self):
        self.make(self.income, description='A-entrada-caixa', method=Method.CASH, account=Account.CASH)
        self.make(self.expense, description='B-saida-banco', method=Method.PIX, account=Account.BANK)
        self.make(self.tithe, description='C-dizimo-banco', method=Method.PIX, account=Account.BANK)
        self.make(self.income, description='D-outro-mes', when=date(2026, 5, 3))
        url = reverse('tesouraria:movements')

        def names(**params):
            params.setdefault('mes', '2026-06')
            response = self.client.get(url, params)
            self.assertEqual(response.status_code, 200)
            return {m.description for m in response.context['movements']}

        self.assertEqual(names(), {'A-entrada-caixa', 'B-saida-banco', 'C-dizimo-banco'})
        self.assertEqual(names(tipo='expense'), {'B-saida-banco'})
        self.assertEqual(names(categoria=self.tithe.pk), {'C-dizimo-banco'})
        self.assertEqual(names(conta='bank'), {'B-saida-banco', 'C-dizimo-banco'})
        self.assertEqual(names(forma='cash'), {'A-entrada-caixa'})
        self.assertEqual(names(mes='2026-05'), {'D-outro-mes'})
        for bad in ({'tipo': 'x'}, {'categoria': 'abc'}, {'conta': 'zz'}, {'forma': '!'}, {'mes': 'lixo'}):
            with self.subTest(bad=bad):
                self.assertEqual(self.client.get(url, bad).status_code, 200)
        self.assertEqual(names(tipo='x', categoria='abc', conta='zz', forma='!'),
                         {'A-entrada-caixa', 'B-saida-banco', 'C-dizimo-banco'})

    def test_list_has_no_n_plus_one(self):
        member = make_member()
        for i in range(5):
            self.make(self.tithe, member=member, description=f'm{i}')
        url = reverse('tesouraria:movements') + '?mes=2026-06'
        self.client.get(url)
        with self.assertNumQueries(self._count(url)):
            self.client.get(url)
        for i in range(10):
            self.make(self.tithe, member=member, description=f'n{i}')
        with self.assertNumQueries(self._count(url)):
            self.client.get(url)

    def _count(self, url):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        with CaptureQueriesContext(connection) as ctx:
            self.client.get(url)
        return len(ctx)

    def test_list_shows_transfers_and_controls_for_editor(self):
        transfer = ledger.create_transfer(self.tes, from_account='cash', to_account='bank', date=date(2026, 6, 12),
                                          amount=Decimal('60.00'))
        response = self.client.get(reverse('tesouraria:movements') + '?mes=2026-06')
        self.assertContains(response, reverse('tesouraria:transfer_delete', args=[transfer.pk]))

    def test_home_list_masks_member_description_for_board_but_not_for_treasurer_or_committee(self):
        member = make_member('Maria Souza')
        self.make(self.tithe, member=member, description='Dízimo de Maria Souza', amount='80.00',
                  when=JUN)
        url = reverse('tesouraria:home') + '?mes=2026-06'
        self.assertContains(self.client.get(url), 'Dízimo de Maria Souza')
        self.client.force_login(make_user('com', Role.COMMITTEE))
        self.assertContains(self.client.get(url), 'Dízimo de Maria Souza')
        self.client.force_login(make_user('dir', Role.BOARD))
        response = self.client.get(url)
        self.assertNotContains(response, 'Maria Souza')
        self.assertContains(response, 'Dízimos (contribuição de membro)')

    def test_home_has_buttons_for_editor_only(self):
        url = reverse('tesouraria:home') + '?mes=2026-06'
        response = self.client.get(url)
        for label in ('Nova entrada', 'Nova saída', 'Depósito'):
            self.assertContains(response, label)
        self.client.force_login(make_user('com', Role.COMMITTEE))
        self.assertNotContains(self.client.get(url), 'Nova entrada')

    def test_board_cannot_open_movements_list(self):
        self.client.force_login(make_user('dir', Role.BOARD))
        self.assertEqual(self.client.get(reverse('tesouraria:movements')).status_code, 403)

    def test_committee_can_open_movements_list_read_only(self):
        movement = self.make(description='Visível à comissão')
        self.client.force_login(make_user('com', Role.COMMITTEE))
        response = self.client.get(reverse('tesouraria:movements') + '?mes=2026-06')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Visível à comissão')
        self.assertNotContains(response, reverse('tesouraria:movement_edit', args=[movement.pk]))
        self.assertNotContains(response, reverse('tesouraria:movement_delete', args=[movement.pk]))


class MonthRangeTests(MovementBase):
    def test_extreme_months_do_not_crash_home_or_list(self):
        from tesouraria.rules import parse_month
        current = timezone.localdate().replace(day=1)
        for value in ('9999-12', '0001-01', '2101-01', '1999-12'):
            with self.subTest(value=value):
                self.assertEqual(parse_month(value), current)
                self.assertEqual(self.client.get(reverse('tesouraria:home'), {'mes': value}).status_code, 200)
                self.assertEqual(self.client.get(reverse('tesouraria:movements'), {'mes': value}).status_code, 200)
        self.assertEqual(parse_month('2000-01'), date(2000, 1, 1))
        self.assertEqual(parse_month('2100-12'), date(2100, 12, 1))


class PreservedLinkTests(MovementBase):
    def edit(self, movement, category, **extra):
        return self.client.post(reverse('tesouraria:movement_edit', args=[movement.pk]),
                                post_data(category, **extra))

    def test_edit_with_empty_member_keeps_member(self):
        member = make_member()
        movement = self.make(self.tithe, member=member, source='portal')
        self.assertEqual(self.edit(movement, self.tithe, member='', amount='60.00').status_code, 302)
        movement.refresh_from_db()
        self.assertEqual((movement.member_id, movement.amount), (member.pk, Decimal('60.00')))

    def test_edit_form_prefills_member(self):
        member = make_member()
        movement = self.make(self.tithe, member=member)
        response = self.client.get(reverse('tesouraria:movement_edit', args=[movement.pk]))
        self.assertEqual(response.context['form']['member'].value(), member.pk)

    def test_edit_with_another_member_switches(self):
        member, other = make_member(), make_member('João Lima', 'joao@example.com')
        movement = self.make(self.tithe, member=member)
        self.edit(movement, self.tithe, member=other.pk)
        movement.refresh_from_db()
        self.assertEqual(movement.member_id, other.pk)

    def test_expense_edit_leaves_member_untouched(self):
        member = make_member()
        movement = self.make(self.expense, member=member)
        self.assertEqual(self.edit(movement, self.expense, amount='7.00').status_code, 302)
        movement.refresh_from_db()
        self.assertEqual((movement.member_id, movement.amount), (member.pk, Decimal('7.00')))


class ArchivedCategoryTests(MovementBase):
    def test_edit_keeps_archived_category_but_create_does_not_offer_it(self):
        movement = self.make(self.income)
        Category.objects.filter(pk=self.income.pk).update(active=False)
        response = self.client.post(reverse('tesouraria:movement_edit', args=[movement.pk]),
                                    post_data(self.income, amount='88.00'))
        self.assertEqual(response.status_code, 302)
        movement.refresh_from_db()
        self.assertEqual((movement.amount, movement.category_id), (Decimal('88.00'), self.income.pk))
        create = self.client.get(reverse('tesouraria:movement_create') + '?tipo=income')
        self.assertNotIn(self.income, create.context['form'].fields['category'].queryset)
