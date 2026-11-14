from datetime import date
from decimal import Decimal
from io import BytesIO

from django.test import TestCase
from django.urls import reverse
from pypdf import PdfReader

from core.models import AccessProfile, Member
from tesouraria import closing, ledger, opinions, report
from tesouraria.balances import month_summary
from tesouraria.models import Category, Kind, Method, Movement, Payable, Status

from .helpers import WITHOUT_AXES, configure, make_user

Role = AccessProfile.Role
D = Decimal
JAN = date(2026, 1, 1)
PASSWORD = 'senha-forte-123'


def pdf_text(response_or_bytes):
    data = response_or_bytes if isinstance(response_or_bytes, bytes) else response_or_bytes.content
    return '\n'.join(page.extract_text() for page in PdfReader(BytesIO(data)).pages)


@WITHOUT_AXES
class ReportBase(TestCase):
    def setUp(self):
        configure(date(2026, 1, 1), cash='100.00', bank='200.00')
        self.tes = make_user('tes', Role.TREASURER)
        self.com = make_user('com', Role.COMMITTEE)
        self.dir = make_user('dir', Role.BOARD)
        self.tithe = Category.objects.get(name='Dízimos', kind=Kind.INCOME)
        self.offer = Category.objects.get(name='Ofertas', kind=Kind.INCOME)
        self.expense = Category.objects.filter(kind=Kind.EXPENSE, active=True).first()
        self.special = Category.objects.filter(kind=Kind.INCOME, is_special=True).first() or \
            Category.objects.create(name='Missões', kind=Kind.INCOME, is_special=True)
        self.ana = Member.objects.create(name='Ana Souza', email='ana@example.com')

    def add(self, category, amount, day, kind=Kind.INCOME, **extra):
        data = dict(date=day, kind=kind, amount=D(amount), category=category, description='x',
                    account='cash', status=Status.CONFIRMED)
        data.update(extra)
        return Movement.objects.create(**data)

    def seed(self):
        self.add(self.tithe, '100.00', date(2026, 1, 5), description='Dízimo Ana Souza', member=self.ana)
        self.add(self.offer, '40.00', date(2026, 1, 6), method=Method.PIX, account='bank', description='Oferta culto')
        self.add(self.special, '30.00', date(2026, 1, 7), destination='Missões', description='Oferta missões')
        self.add(self.expense, '25.00', date(2026, 1, 8), kind=Kind.EXPENSE, description='Luz <b>&</b>')

    def get(self, name, user, mes='2026-01'):
        self.client.force_login(user)
        return self.client.get(reverse(f'tesouraria:{name}'), {'mes': mes})


class ReportTests(ReportBase):
    def test_report_screen_numbers_match_month_summary(self):
        self.seed()
        r = self.get('report', self.tes)
        self.assertEqual(r.status_code, 200)
        summary = month_summary(JAN)
        ctx = r.context
        self.assertEqual(ctx['summary'], summary)
        self.assertEqual(ctx['summary'].income_cash, D('130.00'))
        self.assertEqual(ctx['summary'].income_pix, D('40.00'))
        self.assertEqual(len(ctx['movements']), 4)
        self.assertContains(r, 'Saldo do Caixa')
        self.assertContains(r, 'Em dinheiro')
        self.assertContains(r, 'Por Pix')

    def test_pdf_is_valid_and_contains_key_labels(self):
        self.seed()
        closing.close_month(JAN, self.tes)
        r = self.get('report_pdf', self.tes)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'application/pdf')
        self.assertEqual(r['Content-Disposition'], 'inline; filename="relatorio-2026-01.pdf"')
        self.assertIn('no-store', r['Cache-Control'])
        self.assertIn('private', r['Cache-Control'])
        text = pdf_text(r)
        for label in ('Saldo do Caixa', 'Saldo do Banco', 'Em dinheiro', 'Por Pix', 'Tesoureiro',
                      'Comissão de Contas', 'Janeiro', 'Igreja Batista Regular Canaã', 'Missões'):
            self.assertIn(label, text)
        self.assertNotIn('Mês em aberto', text)

    def test_pdf_masks_member_names_for_board_and_shows_for_committee(self):
        self.seed()
        for user, sees in ((self.dir, False), (self.com, True), (self.tes, True)):
            screen = self.get('report', user)
            text = pdf_text(self.get('report_pdf', user))
            self.assertEqual('Ana Souza' in text, sees, user.username)
            self.assertEqual('Ana Souza' in screen.content.decode(), sees, user.username)
        self.assertIn('contribuição de membro', pdf_text(self.get('report_pdf', self.dir)))

    def test_open_month_is_marked_in_report_and_pdf(self):
        self.seed()
        self.assertContains(self.get('report', self.tes), 'Mês em aberto')
        self.assertIn('Mês em aberto', pdf_text(self.get('report_pdf', self.tes)))
        closing.close_month(JAN, self.tes)
        self.assertNotContains(self.get('report', self.tes), 'Mês em aberto')

    def test_report_requires_view_permission(self):
        stranger = make_user('estranho', None)
        for name in ('report', 'report_pdf'):
            self.client.logout()
            self.assertEqual(self.client.get(reverse(f'tesouraria:{name}')).status_code, 302)
            for user in (self.tes, self.com, self.dir):
                self.assertEqual(self.get(name, user).status_code, 200, (name, user.username))
            self.assertEqual(self.get(name, stranger).status_code, 403)

    def test_year_summary_matches_sum_of_months(self):
        self.seed()
        self.add(self.tithe, '60.00', date(2026, 3, 2))
        self.add(self.expense, '10.00', date(2026, 3, 3), kind=Kind.EXPENSE)
        r = self.get('report', self.tes, mes='2026-03')
        rows = r.context['year_rows']
        self.assertEqual([row['month'] for row in rows][:3], [date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1)])
        for row in rows:
            s = month_summary(row['month'])
            self.assertEqual((row['income'], row['expense'], row['total']),
                             (s.income_total, s.expense_total, s.closing_total))
        self.assertEqual(sum(row['income'] for row in rows), D('230.00'))
        self.assertEqual(sum(row['expense'] for row in rows), D('35.00'))

    def test_year_summary_only_from_treasury_start(self):
        configure(date(2026, 6, 10))
        r = self.get('report', self.tes, mes='2026-08')
        self.assertEqual(rows := [row['month'].month for row in r.context['year_rows']], list(range(6, 13)), rows)

    def test_pdf_with_no_movements_still_renders(self):
        text = pdf_text(self.get('report_pdf', self.tes))
        self.assertIn('Saldo do Caixa', text)
        self.assertEqual(self.get('report', self.tes).status_code, 200)

    def test_pdf_paginates_many_rows_and_repeats_header(self):
        for i in range(150):
            self.add(self.offer, '1.00', date(2026, 1, 1 + i % 28), description=f'Movimento {i} ' + 'longo ' * 20)
        data = self.get('report_pdf', self.tes).content
        pages = PdfReader(BytesIO(data)).pages
        self.assertGreater(len(pages), 3)
        later = pages[2].extract_text()
        self.assertIn('Descrição', later)
        self.assertIn('Movimento 149', pdf_text(data))

    def test_pdf_escapes_markup_in_user_text(self):
        self.seed()
        closing.close_month(JAN, self.tes)
        opinions.record_opinion(JAN, self.com, 'reservations', 'Faltou <recibo> & nota')
        text = pdf_text(self.get('report_pdf', self.tes))
        self.assertIn('Luz <b>&</b>', text)
        self.assertIn('Faltou <recibo> & nota', text)

    def test_not_configured_and_before_start_do_not_crash(self):
        self.get('report', self.tes, mes='2025-05')
        for name in ('report', 'report_pdf'):
            r = self.get(name, self.tes, mes='2025-05')
            self.assertEqual(r.status_code, 200 if name == 'report' else 302, name)
        from tesouraria.models import TreasurySettings
        TreasurySettings.objects.all().delete()
        for user in (self.tes, self.dir):
            for name in ('report', 'report_pdf'):
                self.assertIn(self.get(name, user).status_code, (200, 302), name)

    def test_payables_listed(self):
        Payable.objects.create(description='Aluguel', amount=D('80.00'), category=self.expense,
                               due_date=date(2026, 1, 20), status=Payable.Status.OPEN)
        r = self.get('report', self.tes)
        self.assertContains(r, 'Aluguel')
        self.assertIn('Aluguel', pdf_text(self.get('report_pdf', self.tes)))

    def test_opinion_visible_on_home_and_report(self):
        self.seed()
        closing.close_month(JAN, self.tes)
        opinions.record_opinion(JAN, self.com, 'reservations', '<script>x</script> ressalva')
        for user in (self.com, self.dir, self.tes):
            page = self.get('report', user)
            self.assertContains(page, 'Aprovado com ressalvas')
            self.assertContains(page, '&lt;script&gt;x&lt;/script&gt; ressalva')
            self.assertNotContains(page, '<script>x')
            self.assertIn('Aprovado com ressalvas', pdf_text(self.get('report_pdf', user)))
            home = self.get('home', user)
            self.assertContains(home, 'Aprovado com ressalvas')
