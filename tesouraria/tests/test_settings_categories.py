from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from core.models import AccessProfile
from tesouraria.forms import active_categories
from tesouraria.models import (AuditLog, Category, Kind, Movement, MonthClosing, Transfer,
                               TreasurySettings)

from .helpers import WITHOUT_AXES, configure, make_user

Role = AccessProfile.Role


def make_movement(category, when=date(2026, 3, 10)):
    return Movement.objects.create(date=when, kind=category.kind, amount=Decimal('10.00'),
                                   category=category, description='x')


@WITHOUT_AXES
class SettingsTests(TestCase):
    def setUp(self):
        self.url = reverse('tesouraria:settings')
        self.tes = make_user('tes', Role.TREASURER)
        self.client.force_login(self.tes)

    def post(self, **extra):
        data = {'start_date': '2026-01-01', 'opening_cash': '100.50', 'opening_bank': '2000.00'}
        data.update(extra)
        return self.client.post(self.url, data)

    def test_editor_saves_opening_and_audits(self):
        self.assertEqual(self.client.get(self.url).status_code, 200)
        response = self.post()
        self.assertEqual(response.status_code, 302)
        settings_obj = TreasurySettings.get()
        self.assertEqual(settings_obj.start_date, date(2026, 1, 1))
        self.assertEqual(settings_obj.opening_cash, Decimal('100.50'))
        self.assertEqual(settings_obj.opening_bank, Decimal('2000.00'))
        log = AuditLog.objects.get(action='settings')
        self.assertEqual(log.summary, 'Abertura registrada')
        self.assertEqual(log.user, self.tes)
        self.assertIsNone(log.before)
        self.assertEqual(log.after['opening_cash'], '100.50')
        self.post(opening_cash='50.00')
        self.assertEqual(TreasurySettings.objects.count(), 1)
        self.assertEqual(AuditLog.objects.filter(action='settings').count(), 2)
        self.assertEqual(AuditLog.objects.filter(action='settings').first().before['opening_cash'], '100.50')

    def test_page_links_to_categories(self):
        self.assertContains(self.client.get(self.url), reverse('tesouraria:categories'))

    def test_opening_locked_after_a_month_is_closed(self):
        configure(date(2026, 1, 1), '10.00', '20.00')
        MonthClosing.objects.create(month=date(2026, 1, 1),
                                    closed_at=datetime(2026, 2, 1, tzinfo=dt_timezone.utc))
        response = self.post(opening_cash='999.00')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'fechado')
        self.assertEqual(TreasurySettings.get().opening_cash, Decimal('10.00'))
        self.assertFalse(AuditLog.objects.filter(action='settings').exists())

    def test_open_month_closing_without_closed_at_does_not_lock(self):
        configure()
        MonthClosing.objects.create(month=date(2026, 1, 1))
        self.assertEqual(self.post(opening_cash='5.00').status_code, 302)
        self.assertEqual(TreasurySettings.get().opening_cash, Decimal('5.00'))

    def test_readers_get_403_on_settings_post(self):
        for role in (Role.BOARD, Role.COMMITTEE):
            with self.subTest(role=role):
                self.client.force_login(make_user(f'u-{role}', role))
                self.assertEqual(self.post().status_code, 403)
                self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertIsNone(TreasurySettings.get())

    def test_start_date_cannot_be_in_the_future_of_existing_movements(self):
        configure(date(2026, 1, 1))
        cat = Category.objects.filter(kind=Kind.INCOME).first()
        make_movement(cat, date(2026, 3, 10))
        response = self.post(start_date='2026-04-01')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'anterior à nova data')
        self.assertEqual(TreasurySettings.get().start_date, date(2026, 1, 1))
        self.assertEqual(self.post(start_date='2026-03-10').status_code, 302)

    def test_start_date_checks_transfers_but_ignores_deleted(self):
        configure(date(2026, 1, 1))
        Transfer.objects.create(date=date(2026, 2, 5), from_account='cash', to_account='bank',
                                amount=Decimal('1.00'))
        self.assertEqual(self.post(start_date='2026-03-01').status_code, 200)
        Transfer.objects.update(deleted_at=datetime(2026, 2, 6, tzinfo=dt_timezone.utc))
        self.assertEqual(self.post(start_date='2026-03-01').status_code, 302)


@WITHOUT_AXES
class CategoryTests(TestCase):
    def setUp(self):
        self.tes = make_user('tes', Role.TREASURER)
        self.client.force_login(self.tes)

    def test_create_edit_category(self):
        response = self.client.post(reverse('tesouraria:category_create'),
                                    {'name': 'Missões', 'kind': 'income', 'is_special': 'on'})
        self.assertRedirects(response, reverse('tesouraria:categories'))
        cat = Category.objects.get(name='Missões', kind=Kind.INCOME)
        self.assertTrue(cat.is_special and not cat.is_tithe)
        self.assertEqual(AuditLog.objects.get(action='create').summary, 'Categoria criada: Missões')
        self.client.post(reverse('tesouraria:category_edit', args=[cat.pk]),
                         {'name': 'Missões Mundiais', 'kind': 'income', 'is_tithe': 'on'})
        cat.refresh_from_db()
        self.assertEqual(cat.name, 'Missões Mundiais')
        self.assertTrue(cat.is_tithe and not cat.is_special)
        self.assertEqual(AuditLog.objects.get(action='update').summary, 'Categoria alterada: Missões Mundiais')
        listing = self.client.get(reverse('tesouraria:categories'))
        self.assertContains(listing, 'Missões Mundiais')
        self.assertContains(listing, 'Entradas')
        self.assertContains(listing, 'Saídas')

    def test_special_and_tithe_rules(self):
        url = reverse('tesouraria:category_create')
        both = self.client.post(url, {'name': 'A', 'kind': 'income', 'is_special': 'on', 'is_tithe': 'on'})
        self.assertEqual(both.status_code, 200)
        expense = self.client.post(url, {'name': 'B', 'kind': 'expense', 'is_tithe': 'on'})
        self.assertEqual(expense.status_code, 200)
        self.assertFalse(Category.objects.filter(name__in=['A', 'B']).exists())

    def test_duplicate_name_same_kind_is_rejected_with_message(self):
        Category.objects.create(name='Extra', kind=Kind.INCOME)
        url = reverse('tesouraria:category_create')
        response = self.client.post(url, {'name': 'Extra', 'kind': 'income'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Já existe uma categoria')
        self.assertEqual(Category.objects.filter(name='Extra').count(), 1)
        self.assertEqual(self.client.post(url, {'name': 'Extra', 'kind': 'expense'}).status_code, 302)
        cat = Category.objects.get(name='Extra', kind='expense')
        clash = self.client.post(reverse('tesouraria:category_edit', args=[cat.pk]),
                                 {'name': 'Extra', 'kind': 'income'})
        self.assertContains(clash, 'Já existe uma categoria')

    def test_delete_unused_category_removes_it(self):
        cat = Category.objects.create(name='Temp', kind=Kind.EXPENSE)
        response = self.client.post(reverse('tesouraria:category_delete', args=[cat.pk]), follow=True)
        self.assertFalse(Category.objects.filter(pk=cat.pk).exists())
        self.assertContains(response, 'excluída')
        self.assertEqual(AuditLog.objects.get(action='delete').summary, 'Categoria excluída: Temp')

    def test_delete_used_category_archives_it_and_keeps_history(self):
        cat = Category.objects.create(name='Usada', kind=Kind.INCOME)
        movement = make_movement(cat)
        self.assertIn(cat, active_categories(Kind.INCOME))
        response = self.client.post(reverse('tesouraria:category_delete', args=[cat.pk]), follow=True)
        cat.refresh_from_db()
        self.assertFalse(cat.active)
        self.assertContains(response, 'arquivada')
        self.assertEqual(AuditLog.objects.get(action='archive').summary, 'Categoria arquivada: Usada')
        movement.refresh_from_db()
        self.assertEqual(movement.category, cat)
        self.assertNotIn(cat, active_categories(Kind.INCOME))
        listing = self.client.get(reverse('tesouraria:categories'))
        self.assertContains(listing, 'Arquivada')

    def test_reactivate_category(self):
        cat = Category.objects.create(name='Velha', kind=Kind.INCOME, active=False)
        self.client.post(reverse('tesouraria:category_reactivate', args=[cat.pk]))
        cat.refresh_from_db()
        self.assertTrue(cat.active)
        self.assertIn(cat, active_categories(Kind.INCOME))
        self.assertEqual(AuditLog.objects.filter(action='update').last().summary, 'Categoria reativada: Velha')

    def test_mutations_are_post_only(self):
        cat = Category.objects.create(name='Z', kind=Kind.INCOME)
        for name in ('category_delete', 'category_reactivate'):
            with self.subTest(name=name):
                self.assertEqual(self.client.get(reverse(f'tesouraria:{name}', args=[cat.pk])).status_code, 405)
        self.assertTrue(Category.objects.filter(pk=cat.pk).exists())

    def test_readers_get_403(self):
        cat = Category.objects.create(name='Z', kind=Kind.INCOME)
        urls = [reverse('tesouraria:categories'), reverse('tesouraria:category_create'),
                reverse('tesouraria:category_edit', args=[cat.pk])]
        post_urls = [reverse('tesouraria:category_delete', args=[cat.pk]),
                     reverse('tesouraria:category_reactivate', args=[cat.pk])]
        for role in (Role.BOARD, Role.COMMITTEE):
            self.client.force_login(make_user(f'u-{role}', role))
            for url in urls:
                self.assertEqual(self.client.get(url).status_code, 403)
            for url in post_urls + [reverse('tesouraria:category_create')]:
                self.assertEqual(self.client.post(url, {'name': 'Q', 'kind': 'income'}).status_code, 403)
        self.assertTrue(Category.objects.filter(pk=cat.pk, active=True).exists())
