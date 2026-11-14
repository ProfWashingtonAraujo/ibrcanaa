from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from core.models import AccessProfile, Member
from tesouraria import audit
from tesouraria.models import Account, Category, Kind, Method, Movement, Source, Status, Transfer, TreasurySettings
from tesouraria.visibility import description_for

from .helpers import configure, make_user

Role = AccessProfile.Role


def make_movement(category, **kwargs):
    defaults = dict(
        date=date(2026, 3, 1), kind=category.kind, amount=Decimal('120.00'), category=category,
        description='Oferta', account=Account.CASH, method=Method.CASH,
        status=Status.CONFIRMED, source=Source.TREASURY,
    )
    defaults.update(kwargs)
    return Movement.objects.create(**defaults)


class ModelsTests(TestCase):
    def test_settings_get_returns_none_until_configured(self):
        self.assertIsNone(TreasurySettings.get())
        configure(cash='10.00')
        self.assertEqual(TreasurySettings.get().opening_cash, Decimal('10.00'))

    def test_category_unique_per_kind(self):
        Category.objects.create(name='Teste', kind=Kind.INCOME)
        Category.objects.create(name='Teste', kind=Kind.EXPENSE)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Category.objects.create(name='Teste', kind=Kind.INCOME)

    def test_default_categories_exist(self):
        self.assertTrue(Category.objects.get(name='Dízimos', kind=Kind.INCOME).is_tithe)
        self.assertTrue(Category.objects.filter(name='Ofertas', kind=Kind.INCOME).exists())
        self.assertTrue(Category.objects.get(name='Ofertas especiais', kind=Kind.INCOME).is_special)
        for name in ['Água e luz', 'Manutenção', 'Missões', 'Ajuda social', 'Material', 'Outros']:
            self.assertTrue(Category.objects.filter(name=name, kind=Kind.EXPENSE).exists(), name)

    def test_category_in_use(self):
        cat = Category.objects.get(name='Ofertas', kind=Kind.INCOME)
        self.assertFalse(cat.in_use())
        make_movement(cat)
        self.assertTrue(cat.in_use())

    def test_movement_live_excludes_deleted(self):
        from django.utils import timezone
        cat = Category.objects.get(name='Ofertas', kind=Kind.INCOME)
        keep = make_movement(cat)
        gone = make_movement(cat, deleted_at=timezone.now())
        pending = make_movement(cat, status=Status.PENDING)
        self.assertEqual(set(Movement.objects.live()), {keep, pending})
        self.assertNotIn(gone, Movement.objects.live())
        self.assertEqual(set(Movement.objects.live().confirmed()), {keep})

    def test_transfer_rejects_same_account_and_non_positive(self):
        with self.assertRaises(ValidationError):
            Transfer(date=date(2026, 3, 1), from_account=Account.CASH, to_account=Account.CASH,
                     amount=Decimal('10')).clean()
        with self.assertRaises(ValidationError):
            Transfer(date=date(2026, 3, 1), from_account=Account.CASH, to_account=Account.BANK,
                     amount=Decimal('0')).clean()
        Transfer(date=date(2026, 3, 1), from_account=Account.CASH, to_account=Account.BANK,
                 amount=Decimal('5')).clean()

    def test_audit_snapshot_serialises_decimal_and_date(self):
        cat = Category.objects.get(name='Dízimos', kind=Kind.INCOME)
        mv = make_movement(cat)
        snap = audit.snapshot(mv)
        self.assertEqual(snap['amount'], '120.00')
        self.assertEqual(snap['date'], '2026-03-01')
        user = make_user('tes', Role.TREASURER)
        entry = audit.record(user, audit.CREATE, mv, 'Entrada de R$ 120,00 em Dízimos', after=snap)
        self.assertEqual(entry.model, 'Movement')
        self.assertEqual(entry.object_id, str(mv.pk))
        self.assertEqual(entry.after['amount'], '120.00')
        self.assertEqual(entry.user, user)

    def test_description_for_masks_member_movements(self):
        cat = Category.objects.get(name='Dízimos', kind=Kind.INCOME)
        member = Member.objects.create(name='Fulano de Tal', email='fulano@example.com')
        with_member = make_movement(cat, member=member, description='Dízimo do Fulano')
        without = make_movement(cat, description='Oferta avulsa')
        board = make_user('dir', Role.BOARD)
        committee = make_user('com', Role.COMMITTEE)
        treasurer = make_user('tes', Role.TREASURER)
        self.assertEqual(description_for(with_member, board), 'Dízimos (contribuição de membro)')
        self.assertEqual(description_for(with_member, committee), 'Dízimo do Fulano')
        self.assertEqual(description_for(with_member, treasurer), 'Dízimo do Fulano')
        for user in (board, committee, treasurer):
            self.assertEqual(description_for(without, user), 'Oferta avulsa')

    def test_month_closing_is_closed(self):
        from django.utils import timezone
        from tesouraria.models import MonthClosing
        closing = MonthClosing(month=date(2026, 3, 1))
        self.assertFalse(closing.is_closed)
        closing.closed_at = timezone.now()
        self.assertTrue(closing.is_closed)
