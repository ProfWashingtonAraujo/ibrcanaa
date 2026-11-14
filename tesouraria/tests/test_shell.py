from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import AccessProfile
from tesouraria.models import Account, Category, Kind, Method, Movement, Source, Status
from tesouraria.rules import parse_month

from .helpers import WITHOUT_AXES, configure, make_user

Role = AccessProfile.Role


class ParseMonthTests(TestCase):
    def test_parse_month(self):
        current = timezone.localdate().replace(day=1)
        self.assertEqual(parse_month('2026-11'), date(2026, 11, 1))
        for value in (None, '', 'lixo', '2026-13', '2026'):
            with self.subTest(value=value):
                self.assertEqual(parse_month(value), current)


@WITHOUT_AXES
class ShellTests(TestCase):
    def setUp(self):
        self.url = reverse('tesouraria:home')

    def login(self, username, role=None, **kw):
        user = make_user(username, role, **kw)
        self.client.force_login(user)
        return user

    def test_home_requires_view_permission(self):
        self.assertEqual(self.client.get(self.url).status_code, 302)
        for role in (Role.SECRETARY, Role.DEACON, Role.PASTOR, Role.MEMBER):
            with self.subTest(role=role):
                self.client.force_login(make_user(f'u-{role}', role))
                self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_not_configured_redirects_editor_to_settings_and_explains_to_readers(self):
        self.login('tes', Role.TREASURER)
        response = self.client.get(self.url)
        self.assertRedirects(response, reverse('tesouraria:settings'), fetch_redirect_response=False)
        self.login('dir', Role.BOARD)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'ainda não foi configurada')

    def _populate(self):
        configure(start=date(2026, 10, 1), cash='100.00', bank='50.00')
        cat = Category.objects.filter(kind=Kind.INCOME, is_special=False).first()
        today_month = date(2026, 11, 10)
        Movement.objects.create(
            date=today_month, kind=Kind.INCOME, amount=Decimal('1234.56'), category=cat,
            description='Oferta do culto', account=Account.CASH, method=Method.CASH,
            status=Status.CONFIRMED, source=Source.TREASURY)
        Movement.objects.create(
            date=date(2026, 10, 5), kind=Kind.INCOME, amount=Decimal('10.00'), category=cat,
            description='Entrada de outubro', account=Account.BANK, method=Method.PIX,
            status=Status.CONFIRMED, source=Source.TREASURY)
        Movement.objects.create(
            date=today_month, kind=Kind.INCOME, amount=Decimal('9.00'), category=cat,
            description='Pendente escondido', account=Account.CASH, method=Method.CASH,
            status=Status.PENDING, source=Source.TREASURY)

    def test_home_shows_summary_labels(self):
        self._populate()
        self.login('tes', Role.TREASURER)
        response = self.client.get(self.url, {'mes': '2026-11'})
        self.assertEqual(response.status_code, 200)
        for label in ('Caixa do Mês', 'Saldo do Caixa', 'Saldo do Banco', 'Saldo total', 'Em dinheiro', 'Por Pix'):
            with self.subTest(label=label):
                self.assertContains(response, label)
        self.assertContains(response, 'Oferta do culto')
        self.assertContains(response, 'R$ 1.234,56')
        self.assertNotContains(response, 'Pendente escondido')
        self.assertNotContains(response, 'Entrada de outubro')

    def test_month_query_parameter(self):
        self._populate()
        self.login('tes', Role.TREASURER)
        october = self.client.get(self.url, {'mes': '2026-10'})
        self.assertContains(october, 'Entrada de outubro')
        self.assertNotContains(october, 'Oferta do culto')
        self.assertContains(october, 'Outubro de 2026')
        junk = self.client.get(self.url, {'mes': 'lixo'})
        self.assertEqual(junk.status_code, 200)
        self.assertEqual(junk.context['month'], timezone.localdate().replace(day=1))

    def test_month_before_start_shows_message(self):
        self._populate()
        self.login('tes', Role.TREASURER)
        response = self.client.get(self.url, {'mes': '2026-01'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'anterior ao início')
        self.assertContains(response, '?mes=2026-10')

    def test_board_never_sees_member_name_in_description(self):
        self._populate()
        from core.models import Member
        member = Member.objects.create(name='Maria Secreta', email='maria@example.com')
        cat = Category.objects.filter(kind=Kind.INCOME, is_special=False).first()
        Movement.objects.create(
            date=date(2026, 11, 11), kind=Kind.INCOME, amount=Decimal('50.00'), category=cat,
            description='Dízimo de Maria Secreta', account=Account.CASH, method=Method.CASH,
            status=Status.CONFIRMED, source=Source.TREASURY, member=member)
        self.login('dir', Role.BOARD)
        response = self.client.get(self.url, {'mes': '2026-11'})
        self.assertNotContains(response, 'Maria Secreta')
        self.assertContains(response, 'contribuição de membro')

    def test_shell_hides_panel_search_and_changes_brand(self):
        self._populate()
        self.login('tes', Role.TREASURER)
        response = self.client.get(self.url, {'mes': '2026-11'})
        self.assertNotContains(response, 'class="admin-search"')
        self.assertContains(response, 'Tesouraria')
        self.assertContains(response, f'href="{self.url}"')

    def test_panel_keeps_search_and_brand(self):
        self.login('pastor', Role.PASTOR)
        response = self.client.get(reverse('dashboard'))
        self.assertContains(response, 'class="admin-search"')
        self.assertContains(response, 'Gestão Eclesiástica')
        self.assertNotContains(response, 'Ir para o painel')

    def test_nav_matches_role(self):
        # Só os itens cujas rotas já existem; as Tasks 5-11 estendem as asserções
        # (Relatório, Dizimistas, A confirmar, Configurações, Contas a pagar,
        # Lançamentos, Ofertas especiais, Histórico) conforme registrarem suas rotas.
        self._populate()
        editor_only = ('A confirmar',)
        self.login('dir', Role.BOARD)
        html = self.client.get(self.url, {'mes': '2026-11'}).content.decode()
        self.assertIn('Caixa do Mês', html.split('side-nav', 1)[1])
        for label in ('Dizimistas', 'Lançamentos', 'Histórico', 'Contas a pagar') + editor_only:
            self.assertNotIn(label, html.split('side-nav', 1)[1].split('side-user', 1)[0])
        self.login('com', Role.COMMITTEE)
        nav = self.client.get(self.url, {'mes': '2026-11'}).content.decode().split('side-nav', 1)[1].split('side-user', 1)[0]
        self.assertIn('Caixa do Mês', nav)
        for label in editor_only + ('Configurações',):
            self.assertNotIn(label, nav)
        self.login('tes', Role.TREASURER)
        nav = self.client.get(self.url, {'mes': '2026-11'}).content.decode().split('side-nav', 1)[1].split('side-user', 1)[0]
        self.assertIn('Caixa do Mês', nav)
        self.assertIn('Configurações', nav)

    def test_nav_item_visibility_rules(self):
        from tesouraria.navigation import ITEMS
        by_label = {item['label']: item['visible'] for item in ITEMS}
        board = make_user('b', Role.BOARD)
        com = make_user('c', Role.COMMITTEE)
        tes = make_user('t', Role.TREASURER)
        self.assertEqual({l for l, v in by_label.items() if v(board)}, {'Caixa do Mês', 'Relatório'})
        self.assertEqual({l for l, v in by_label.items() if v(com)},
                         {'Caixa do Mês', 'Relatório', 'Dizimistas', 'Contas a pagar', 'Lançamentos',
                          'Ofertas especiais', 'Histórico', 'Histórico anterior'})
        self.assertEqual({l for l, v in by_label.items() if v(tes)}, set(by_label))

    def test_panel_link_only_for_panel_users(self):
        configure()
        self.login('tes', Role.TREASURER)  # staff
        self.assertContains(self.client.get(self.url), reverse('dashboard'))
        self.assertContains(self.client.get(self.url), 'Ir para o painel')
        self.login('com', Role.COMMITTEE)  # sem is_staff
        self.assertNotContains(self.client.get(self.url), 'Ir para o painel')

    def test_settings_placeholder_is_editor_only(self):
        url = reverse('tesouraria:settings')
        self.login('dir', Role.BOARD)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.login('tes', Role.TREASURER)
        self.assertContains(self.client.get(url), 'Configurações')
