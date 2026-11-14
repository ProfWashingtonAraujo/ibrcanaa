from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from core.models import AccessProfile, Member
from tesouraria import ledger, pending
from tesouraria.models import AuditLog, Category, Kind, Movement, Status
from tesouraria.tithers import tithers

from .helpers import WITHOUT_AXES, configure, make_user

Role = AccessProfile.Role


def member(name, n):
    return Member.objects.create(name=name, email=f'm{n}@example.com')


@WITHOUT_AXES
class Base(TestCase):
    def setUp(self):
        configure(date(2026, 1, 1), cash='0.00', bank='0.00')
        self.tes = make_user('tes', Role.TREASURER)
        self.client.force_login(self.tes)
        self.tithe = Category.objects.get(name='Dízimos', kind=Kind.INCOME)
        self.offer = Category.objects.get(name='Ofertas', kind=Kind.INCOME)
        self.special = Category.objects.filter(kind=Kind.INCOME, is_special=True).first()
        if self.special is None:
            self.special = Category.objects.create(name='Missões', kind=Kind.INCOME, is_special=True)

    def add(self, category, amount, day, **extra):
        data = dict(date=day, kind=Kind.INCOME, amount=Decimal(amount), category=category,
                    description='x', account='cash', status=Status.CONFIRMED)
        data.update(extra)
        return Movement.objects.create(**data)


class SpecialTests(Base):
    def test_special_groups_by_destination_for_month_and_year(self):
        self.add(self.special, '100.00', date(2026, 6, 5), destination='Missões', description='Oferta A')
        self.add(self.special, '50.00', date(2026, 6, 6), destination='Missões')
        self.add(self.special, '30.00', date(2026, 6, 7), destination='')
        self.add(self.special, '70.00', date(2026, 3, 7), destination='Missões')
        r = self.client.get(reverse('tesouraria:special'), {'mes': '2026-06'})
        self.assertEqual(r.status_code, 200)
        self.assertEqual([(g['label'], g['total']) for g in r.context['month_groups']],
                         [('Missões', Decimal('150.00')), ('Sem destino', Decimal('30.00'))])
        self.assertEqual(len(r.context['month_groups'][0]['movements']), 2)
        self.assertEqual([(g['label'], g['total']) for g in r.context['year_groups']],
                         [('Missões', Decimal('220.00')), ('Sem destino', Decimal('30.00'))])
        r = self.client.get(reverse('tesouraria:special'), {'mes': '2026-06', 'ano': '2026'})
        self.assertContains(r, 'Oferta A')

    def test_special_ignores_pending_and_deleted(self):
        from django.utils import timezone
        self.add(self.special, '100.00', date(2026, 6, 5), destination='X')
        self.add(self.special, '40.00', date(2026, 6, 5), destination='X', status=Status.PENDING, account=None)
        self.add(self.special, '60.00', date(2026, 6, 5), destination='X', deleted_at=timezone.now())
        self.add(self.offer, '60.00', date(2026, 6, 5), destination='X')
        r = self.client.get(reverse('tesouraria:special'), {'mes': '2026-06'})
        self.assertEqual([g['total'] for g in r.context['month_groups']], [Decimal('100.00')])

    def test_special_empty_state_and_bad_year(self):
        r = self.client.get(reverse('tesouraria:special'), {'ano': 'abc'})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Nenhuma oferta especial')
        self.assertEqual(self.client.get(reverse('tesouraria:special'), {'ano': '99999'}).status_code, 200)


class TithersTests(Base):
    def test_tithers_lists_only_members_with_confirmed_tithe_in_period_sorted_by_name(self):
        zeca, ana, alvaro, ghost = member('Zeca', 1), member('Ana', 2), member('Álvaro', 3), member('Sem', 4)
        self.add(self.tithe, '10.00', date(2026, 6, 1), member=zeca)
        self.add(self.tithe, '20.00', date(2026, 6, 9), member=ana)
        self.add(self.tithe, '5.00', date(2026, 6, 20), member=ana)
        self.add(self.tithe, '7.00', date(2026, 6, 3), member=alvaro)
        self.add(self.tithe, '9.00', date(2026, 5, 3), member=ghost)
        rows, unidentified = tithers(date(2026, 6, 1), date(2026, 6, 30))
        self.assertEqual([r.member.name for r in rows], ['Álvaro', 'Ana', 'Zeca'])
        ana_row = rows[1]
        self.assertEqual((ana_row.total, ana_row.count, ana_row.last_date), (Decimal('25.00'), 2, date(2026, 6, 20)))
        self.assertEqual(unidentified, Decimal('0.00'))

    def test_tithers_ignores_pending_rejected_deleted_and_non_tithe_categories(self):
        from django.utils import timezone
        ana = member('Ana', 1)
        self.add(self.tithe, '10.00', date(2026, 6, 1), member=ana, status=Status.PENDING, account=None)
        self.add(self.tithe, '10.00', date(2026, 6, 1), member=ana, status=Status.REJECTED, account=None)
        self.add(self.tithe, '10.00', date(2026, 6, 1), member=ana, deleted_at=timezone.now())
        self.add(self.offer, '10.00', date(2026, 6, 1), member=ana)
        self.add(self.tithe, '10.00', date(2026, 6, 1), member=None, status=Status.PENDING, account=None)
        rows, unidentified = tithers(date(2026, 6, 1), date(2026, 6, 30))
        self.assertEqual((rows, unidentified), ([], Decimal('0.00')))

    def test_tithers_separates_unidentified_total(self):
        ana = member('Ana', 1)
        self.add(self.tithe, '10.00', date(2026, 6, 1), member=ana)
        self.add(self.tithe, '33.00', date(2026, 6, 2))
        self.add(self.tithe, '2.00', date(2026, 6, 3))
        rows, unidentified = tithers(date(2026, 6, 1), date(2026, 6, 30))
        self.assertEqual(len(rows), 1)
        self.assertEqual(unidentified, Decimal('35.00'))
        r = self.client.get(reverse('tesouraria:tithers'), {'mes': '2026-06'})
        self.assertContains(r, 'Sem identificação')

    def test_tithers_403_for_board_and_secretary_and_ok_for_committee(self):
        url = reverse('tesouraria:tithers')
        for role in (Role.BOARD, Role.SECRETARY):
            self.client.force_login(make_user(f'u{role}', role))
            self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_login(make_user('com', Role.COMMITTEE))
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_tithers_month_and_year_filters(self):
        ana, bia = member('Ana', 1), member('Bia', 2)
        self.add(self.tithe, '10.00', date(2026, 6, 1), member=ana)
        self.add(self.tithe, '10.00', date(2026, 3, 1), member=bia)
        r = self.client.get(reverse('tesouraria:tithers'), {'mes': '2026-06'})
        self.assertContains(r, 'Ana')
        self.assertNotContains(r, 'Bia')
        r = self.client.get(reverse('tesouraria:tithers'), {'ano': '2026'})
        self.assertContains(r, 'Ana')
        self.assertContains(r, 'Bia')
        self.assertEqual(self.client.get(reverse('tesouraria:tithers'), {'ano': 'x'}).status_code, 200)

    def test_tithers_empty_state(self):
        r = self.client.get(reverse('tesouraria:tithers'), {'mes': '2026-06'})
        self.assertContains(r, 'Nenhum dízimo')

    def test_tithers_query_count_does_not_grow(self):
        for i in range(6):
            self.add(self.tithe, '10.00', date(2026, 6, 1), member=member(f'M{i}', i))
        with self.assertNumQueries(2):
            tithers(date(2026, 6, 1), date(2026, 6, 30))


class AuditTests(Base):
    def make_history(self):
        ana = member('Ana Souza', 1)
        m = pending.create_portal_contribution(ana, 'Dízimos', Decimal('150.00'), '')
        pending.confirm_pending(m, user=self.tes, account='bank', method='pix', date=date(2026, 6, 10))
        return m

    def test_audit_lists_actions_newest_first(self):
        self.make_history()
        r = self.client.get(reverse('tesouraria:audit'))
        self.assertEqual(r.status_code, 200)
        logs = list(r.context['logs'])
        self.assertEqual([l.action for l in logs][:2], ['confirm', 'create'])
        self.assertContains(r, 'Confirmada')

    def test_audit_summary_never_contains_member_name(self):
        self.make_history()
        self.assertTrue(AuditLog.objects.exists())
        for log in AuditLog.objects.all():
            self.assertNotIn('Ana', log.summary)
            self.assertNotIn('via portal', log.summary)

    def test_board_and_secretary_get_403_on_audit_and_special(self):
        for role in (Role.BOARD, Role.SECRETARY):
            self.client.force_login(make_user(f'u{role}', role))
            for name in ('audit', 'special'):
                self.assertEqual(self.client.get(reverse(f'tesouraria:{name}')).status_code, 403)

    def test_audit_and_special_visible_to_committee_and_treasurer(self):
        for user in (self.tes, make_user('com', Role.COMMITTEE)):
            self.client.force_login(user)
            for name in ('audit', 'special'):
                self.assertEqual(self.client.get(reverse(f'tesouraria:{name}')).status_code, 200)

    def test_audit_detail_before_after_shown_only_to_names_viewers(self):
        self.make_history()
        for user in (self.tes, make_user('com', Role.COMMITTEE)):
            self.client.force_login(user)
            r = self.client.get(reverse('tesouraria:audit'))
            self.assertContains(r, 'Ana Souza')  # via detalhe (descrição do movimento)
            self.assertContains(r, 'Descrição')
            self.assertNotContains(r, "{'")
            for log in r.context['logs']:
                self.assertNotIn('Ana', log.summary)

    def test_audit_escapes_detail(self):
        AuditLog.objects.create(user=self.tes, action='update', model='Movement', object_id='1', summary='s',
                                before={'description': '<script>alert(1)</script>'}, after=None)
        r = self.client.get(reverse('tesouraria:audit'))
        self.assertNotContains(r, '<script>alert(1)</script>')
        self.assertContains(r, '&lt;script&gt;')

    def test_audit_filters_by_month_and_action(self):
        a = AuditLog.objects.create(user=self.tes, action='create', model='M', object_id='1', summary='um')
        b = AuditLog.objects.create(user=self.tes, action='delete', model='M', object_id='2', summary='dois')
        AuditLog.objects.filter(pk=a.pk).update(at='2026-05-10T12:00:00Z')
        AuditLog.objects.filter(pk=b.pk).update(at='2026-06-10T12:00:00Z')
        r = self.client.get(reverse('tesouraria:audit'), {'mes': '2026-05'})
        self.assertEqual([l.pk for l in r.context['logs']], [a.pk])
        r = self.client.get(reverse('tesouraria:audit'), {'acao': 'delete'})
        self.assertEqual([l.pk for l in r.context['logs']], [b.pk])
        r = self.client.get(reverse('tesouraria:audit'), {'acao': 'bogus'})
        self.assertEqual(len(r.context['logs']), 2)

    def test_audit_empty_state(self):
        self.assertContains(self.client.get(reverse('tesouraria:audit'), {'mes': '2026-05'}), 'Nenhuma alteração')

    def test_audit_no_n_plus_one_and_limit(self):
        users = [make_user(f'x{i}', Role.COMMITTEE) for i in range(5)]
        for i in range(30):
            AuditLog.objects.create(user=users[i % 5], action='create', model='M', object_id=str(i), summary='s',
                                    after={'description': 'd'})
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        url = reverse('tesouraria:audit')
        with CaptureQueriesContext(connection) as many:
            r = self.client.get(url)
        self.assertEqual(len(r.context['logs']), 30)
        AuditLog.objects.filter(pk__gt=AuditLog.objects.order_by('pk')[4].pk).delete()
        with CaptureQueriesContext(connection) as few:
            self.client.get(url)
        self.assertEqual(len(many), len(few))
