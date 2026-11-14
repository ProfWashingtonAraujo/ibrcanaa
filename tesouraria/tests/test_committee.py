from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from core.models import AccessProfile, Member
from tesouraria import closing, ledger, opinions
from tesouraria.models import AuditLog, Category, CommitteeOpinion, Kind, MonthClosing
from tesouraria.rules import TreasuryError

from .helpers import WITHOUT_AXES, configure, make_user

Role = AccessProfile.Role
D = Decimal
JAN = date(2026, 1, 1)
PASSWORD = 'senha-forte-123'


@WITHOUT_AXES
class CommitteeBase(TestCase):
    def setUp(self):
        configure(date(2026, 1, 1), cash='100.00', bank='200.00')
        self.tes = make_user('tes', Role.TREASURER)
        self.com = make_user('com', Role.COMMITTEE)
        self.com.first_name = 'Maria'
        self.com.last_name = 'Souza'
        self.com.save()
        self.com2 = make_user('com2', Role.COMMITTEE)
        self.dir = make_user('dir', Role.BOARD)
        self.income = Category.objects.filter(kind=Kind.INCOME, active=True, is_special=False).first()

    def close_jan(self):
        closing.close_month(JAN, self.tes)

    def url(self):
        return reverse('tesouraria:opinion') + '?mes=2026-01'


class OpinionServiceTests(CommitteeBase):
    def test_committee_registers_opinion_on_closed_month_only(self):
        with self.assertRaises(TreasuryError):
            opinions.record_opinion(JAN, self.com, 'approved', 'ok')
        self.assertEqual(CommitteeOpinion.objects.count(), 0)
        self.close_jan()
        opinion = opinions.record_opinion(date(2026, 1, 17), self.com, 'approved', 'Contas conferidas.')
        self.assertEqual(opinion.month, JAN)
        self.assertEqual(CommitteeOpinion.objects.count(), 1)

    def test_replacing_opinion_audits_the_change(self):
        self.close_jan()
        opinions.record_opinion(JAN, self.com, 'approved', 'ok')
        opinions.record_opinion(JAN, self.com, 'reservations', 'Faltou recibo.')
        self.assertEqual(CommitteeOpinion.objects.count(), 1)
        self.assertEqual(CommitteeOpinion.objects.get().result, 'reservations')
        logs = AuditLog.objects.filter(action='opinion').order_by('id')
        self.assertEqual(logs.count(), 2)
        last = logs.last()
        self.assertEqual(last.before['result'], 'approved')
        self.assertEqual(last.after['result'], 'reservations')
        self.assertNotIn('Maria', last.summary)
        self.assertNotIn('Faltou recibo', last.summary)
        self.assertIsNone(logs.first().before)

    def test_two_members_each_have_their_own_opinion(self):
        self.close_jan()
        opinions.record_opinion(JAN, self.com, 'approved', 'a')
        opinions.record_opinion(JAN, self.com2, 'reservations', 'b')
        self.assertEqual(CommitteeOpinion.objects.count(), 2)

    def test_text_length_enforced_by_model(self):
        self.close_jan()
        with self.assertRaises(ValidationError):
            opinions.record_opinion(JAN, self.com, 'approved', 'x' * 2001)
        with self.assertRaises(ValidationError):
            opinions.record_opinion(JAN, self.com, 'bogus', 'x')
        self.assertEqual(CommitteeOpinion.objects.count(), 0)

    def test_reopened_month_keeps_opinion_but_marks_it_stale(self):
        self.close_jan()
        opinions.record_opinion(JAN, self.com, 'approved', 'ok')
        closing.reopen_month(JAN, self.tes)
        self.assertEqual(CommitteeOpinion.objects.count(), 1)
        self.assertTrue(opinions.opinions_for(JAN)[0].stale)
        with self.assertRaises(TreasuryError):
            opinions.record_opinion(JAN, self.com, 'approved', 'de novo')
        self.close_jan()
        self.assertFalse(opinions.opinions_for(JAN)[0].stale)


class OpinionViewTests(CommitteeBase):
    def test_committee_posts_opinion_via_view(self):
        self.close_jan()
        self.client.login(username='com', password=PASSWORD)
        self.assertEqual(self.client.get(self.url()).status_code, 200)
        r = self.client.post(self.url(), {'result': 'reservations', 'text': 'Faltou <b>recibo</b>'})
        self.assertRedirects(r, reverse('tesouraria:home') + '?mes=2026-01', fetch_redirect_response=False)
        self.assertEqual(CommitteeOpinion.objects.get().author, self.com)

    def test_view_validation_errors(self):
        self.close_jan()
        self.client.login(username='com', password=PASSWORD)
        for data in ({'result': 'approved', 'text': 'x' * 2001}, {'result': 'reservations', 'text': ''},
                     {'result': 'zzz', 'text': 'a'}):
            r = self.client.post(self.url(), data)
            self.assertEqual(r.status_code, 200)
        self.assertEqual(CommitteeOpinion.objects.count(), 0)

    def test_open_month_refuses_with_message(self):
        self.client.login(username='com', password=PASSWORD)
        r = self.client.post(self.url(), {'result': 'approved', 'text': 'ok'}, follow=True)
        self.assertContains(r, 'não está fechado')
        self.assertEqual(CommitteeOpinion.objects.count(), 0)
        r = self.client.get(self.url(), follow=True)
        self.assertContains(r, 'não está fechado')

    def test_treasurer_and_board_cannot_post_opinion(self):
        self.close_jan()
        for username in ('tes', 'dir'):
            self.client.login(username=username, password=PASSWORD)
            self.assertEqual(self.client.post(self.url(), {'result': 'approved', 'text': 'x'}).status_code, 403)
            self.assertEqual(self.client.get(self.url()).status_code, 403)
        self.assertEqual(CommitteeOpinion.objects.count(), 0)

    def test_opinion_visible_on_home_escaped(self):
        self.close_jan()
        opinions.record_opinion(JAN, self.com, 'reservations', '<script>alert(1)</script> ressalva')
        for username in ('com', 'dir', 'tes'):
            self.client.login(username=username, password=PASSWORD)
            page = self.client.get(reverse('tesouraria:home') + '?mes=2026-01')
            self.assertContains(page, 'Aprovado com ressalvas')
            self.assertContains(page, 'Maria Souza')
            self.assertContains(page, '&lt;script&gt;alert(1)&lt;/script&gt; ressalva')
            self.assertNotContains(page, '<script>alert(1)')
        # só a Comissão vê o formulário/botão de parecer
        self.client.login(username='com', password=PASSWORD)
        self.assertContains(self.client.get(reverse('tesouraria:home') + '?mes=2026-01'), self.url().replace('&', '&amp;'))
        for username in ('dir', 'tes'):
            self.client.login(username=username, password=PASSWORD)
            self.assertNotContains(self.client.get(reverse('tesouraria:home') + '?mes=2026-01'), reverse('tesouraria:opinion'))

    def test_opinion_form_link_hidden_when_month_open(self):
        self.client.login(username='com', password=PASSWORD)
        self.assertNotContains(self.client.get(reverse('tesouraria:home') + '?mes=2026-01'),
                               reverse('tesouraria:opinion'))

    def test_stale_opinion_is_labeled_on_home(self):
        self.close_jan()
        opinions.record_opinion(JAN, self.com, 'approved', 'ok')
        closing.reopen_month(JAN, self.tes)
        self.client.login(username='dir', password=PASSWORD)
        self.assertContains(self.client.get(reverse('tesouraria:home') + '?mes=2026-01'),
                            'de mês reaberto')

    def test_committee_sees_member_names_in_movements_but_board_sees_masked_text_on_home(self):
        member = Member.objects.create(name='Fulano Secreto')
        ledger.create_movement(self.tes, date=date(2026, 1, 5), category=self.income,
                               description='Dízimo de Fulano Secreto', amount=D('10.00'), account='cash',
                               method='cash', member=member)
        url = reverse('tesouraria:home') + '?mes=2026-01'
        self.client.login(username='com', password=PASSWORD)
        self.assertContains(self.client.get(url), 'Fulano Secreto')
        self.client.login(username='dir', password=PASSWORD)
        page = self.client.get(url)
        self.assertNotContains(page, 'Fulano Secreto')
        self.assertContains(page, 'contribuição de membro')


class WriteAccessTests(CommitteeBase):
    WRITE_URLS = [
        ('settings', {}), ('movement_create', {}), ('movement_edit', {'pk': 1}), ('movement_delete', {'pk': 1}),
        ('transfer_create', {}), ('transfer_delete', {'pk': 1}), ('pending_confirm', {'pk': 1}),
        ('pending_reject', {'pk': 1}), ('payable_create', {}), ('payable_edit', {'pk': 1}),
        ('payable_pay', {'pk': 1}), ('payable_undo', {'pk': 1}), ('payable_cancel', {'pk': 1}),
        ('recurring_create', {}), ('recurring_edit', {'pk': 1}), ('recurring_toggle', {'pk': 1}),
        ('cash_count', {}), ('month_close', {}), ('month_reopen', {}),
        ('category_create', {}), ('category_edit', {'pk': 1}), ('category_delete', {'pk': 1}),
        ('category_reactivate', {'pk': 1}),
    ]

    def test_every_write_url_returns_403_for_board_and_committee(self):
        from django.urls import get_resolver
        names = {p.name for p in get_resolver('tesouraria.urls').url_patterns if p.name}
        for name, kwargs in self.WRITE_URLS:
            self.assertIn(name, names)
        for username in ('dir', 'com'):
            self.client.login(username=username, password=PASSWORD)
            for name, kwargs in self.WRITE_URLS:
                with self.subTest(user=username, url=name):
                    r = self.client.post(reverse(f'tesouraria:{name}', kwargs=kwargs), {})
                    self.assertEqual(r.status_code, 403)
        self.assertFalse(MonthClosing.objects.exists())

    def test_committee_cannot_open_the_panel(self):
        self.client.login(username='com', password=PASSWORD)
        for name in ('dashboard', 'members'):
            with self.subTest(url=name):
                r = self.client.get(reverse(name))
                self.assertIn(r.status_code, (302, 403))
                if r.status_code == 302:
                    self.assertNotEqual(r['Location'], reverse(name))
                    self.assertEqual(self.client.get(reverse(name), follow=True).status_code, 200)
                    self.assertNotContains(self.client.get(reverse(name), follow=True), 'Membros ativos')
