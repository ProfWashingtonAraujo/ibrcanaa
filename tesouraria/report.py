"""Relatório mensal da Tesouraria (tela e PDF).

Os saldos vêm só de `balances.month_summary`; aqui nada é recalculado. Os nomes de membros respeitam
`visibility.description_for` com o usuário que vê o relatório (Diretoria não vê nomes).
"""
from datetime import date
from decimal import Decimal
from io import BytesIO
from xml.sax.saxutils import escape

from . import opinions as opinions_service
from .balances import month_summary
from .models import Kind, Movement, Payable
from .rules import get_settings, month_end, month_start
from .visibility import description_for

CHURCH_NAME = 'Igreja Batista Regular Canaã'
MONTH_NAMES = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 'Julho', 'Agosto',
               'Setembro', 'Outubro', 'Novembro', 'Dezembro']
OPEN_WARNING = 'Mês em aberto — valores provisórios'


def month_label(month: date) -> str:
    return f'{MONTH_NAMES[month.month - 1]} de {month.year}'


def money(value) -> str:
    text = f'{Decimal(value):,.2f}'
    return 'R$ ' + text.replace(',', '#').replace('.', ',').replace('#', '.')


def _year_rows(month: date) -> list[dict]:
    """Mês a mês do ano de `month`, a partir do início da tesouraria (uma `month_summary` por mês)."""
    start_month = month_start(get_settings().start_date)
    rows = []
    for number in range(1, 13):
        first = date(month.year, number, 1)
        if first < start_month:
            continue
        s = month_summary(first)
        rows.append({'month': first, 'income': s.income_total, 'expense': s.expense_total, 'total': s.closing_total})
    return rows


def build_report_context(month: date, *, user) -> dict:
    """Levanta NotConfigured/BeforeStart (de `month_summary`)."""
    summary = month_summary(month)
    first, last = summary.month, month_end(summary.month)
    movements = list(Movement.objects.counted().filter(date__gte=first, date__lte=last)
                     .select_related('category').order_by('date', 'id'))
    for movement in movements:
        movement.shown_description = description_for(movement, user)
    paid = list(Payable.objects.filter(status=Payable.Status.PAID, paid_date__gte=first, paid_date__lte=last)
                .select_related('category').order_by('paid_date', 'id'))
    to_pay = list(Payable.objects.filter(status=Payable.Status.OPEN, due_date__gte=first, due_date__lte=last)
                  .select_related('category').order_by('due_date', 'id'))
    return {
        'church_name': CHURCH_NAME,
        'month': first,
        'month_label': month_label(first),
        'month_param': f'{first:%Y-%m}',
        'summary': summary,
        'is_open': not summary.is_closed,
        'open_warning': OPEN_WARNING,
        'movements': movements,
        'paid_payables': paid,
        'open_payables': to_pay,
        'opinions': opinions_service.opinions_for(first),
        'year_rows': _year_rows(first),
    }


def render_report_pdf(month: date, *, user) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    ctx = build_report_context(month, user=user)
    s = ctx['summary']
    navy = colors.HexColor('#071f49')
    line = colors.HexColor('#c9d2e3')
    base = getSampleStyleSheet()['Normal']
    cell = ParagraphStyle('cell', parent=base, fontName='Helvetica', fontSize=8.5, leading=10.5)
    cell_right = ParagraphStyle('cellr', parent=cell, alignment=2)
    head = ParagraphStyle('head', parent=cell, fontName='Helvetica-Bold', textColor=colors.white)
    head_right = ParagraphStyle('headr', parent=head, alignment=2)
    h1 = ParagraphStyle('h1', parent=base, fontName='Helvetica-Bold', fontSize=16, leading=20, textColor=navy)
    h2 = ParagraphStyle('h2', parent=base, fontName='Helvetica-Bold', fontSize=11, leading=14, textColor=navy,
                        spaceBefore=10, spaceAfter=4)
    warn = ParagraphStyle('warn', parent=base, fontName='Helvetica-Bold', fontSize=10, textColor=colors.HexColor('#a23a2e'))
    note = ParagraphStyle('note', parent=cell, textColor=colors.HexColor('#555555'))

    def P(text, style=cell):
        return Paragraph(escape(str(text)), style)

    def table(rows, widths, header=True, right_cols=(), zebra=True):
        data = []
        for i, row in enumerate(rows):
            out = []
            for j, value in enumerate(row):
                is_head = header and i == 0
                style = (head_right if j in right_cols else head) if is_head else (cell_right if j in right_cols else cell)
                out.append(P(value, style))
            data.append(out)
        t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
        styles = [('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LINEBELOW', (0, 0), (-1, -1), 0.25, line),
                  ('TOPPADDING', (0, 0), (-1, -1), 2), ('BOTTOMPADDING', (0, 0), (-1, -1), 2)]
        if header:
            styles.append(('BACKGROUND', (0, 0), (-1, 0), navy))
        t.setStyle(TableStyle(styles))
        return t

    width = A4[0] - 30 * mm
    kv = [width * 0.7, width * 0.3]

    def kv_table(pairs):
        return table(pairs, kv, header=False, right_cols=(1,))

    def section(title, flowable):
        return [Paragraph(escape(title), h2), flowable]

    story = [Paragraph(escape(CHURCH_NAME), h1),
             Paragraph(escape(f'Relatório da Tesouraria — {ctx["month_label"]}'), ParagraphStyle('sub', parent=base, fontSize=11, leading=14))]
    if ctx['is_open']:
        story += [Spacer(1, 4), Paragraph(escape(OPEN_WARNING), warn)]

    story += section('Resumo do mês', kv_table([
        ('Saldo do mês anterior', money(s.opening_cash + s.opening_bank)),
        ('Entradas', money(s.income_total)),
        ('Saídas', money(s.expense_total)),
        ('Saldo do Caixa', money(s.closing_cash)),
        ('Saldo do Banco', money(s.closing_bank)),
        ('Saldo total', money(s.closing_total)),
    ] + ([('Caixa contado', money(s.counted_cash)), ('Diferença da contagem', money(s.cash_difference))]
         if s.counted_cash is not None else [])))
    story += section('Entradas por forma', kv_table([
        ('Em dinheiro', money(s.income_cash)), ('Por Pix', money(s.income_pix)),
        ('Outras formas', money(s.income_other))]))
    story += section('Depósitos e saques', kv_table([
        ('Depósitos no banco', money(s.deposits_to_bank)), ('Saques para o caixa', money(s.withdrawals_to_cash))]))
    story += section('Entradas por categoria', kv_table(
        [(c.name, money(v)) for c, v in s.income_by_category] or [('Nenhuma entrada no mês', '')]))
    story += section('Saídas por categoria', kv_table(
        [(c.name, money(v)) for c, v in s.expense_by_category] or [('Nenhuma saída no mês', '')]))
    story += section('Ofertas especiais por destino', kv_table(
        [(d, money(v)) for d, v in s.special_by_destination] or [('Nenhuma oferta especial no mês', '')]))

    payable_rows = [('Conta', 'Data', 'Valor')]
    payable_rows += [(f'Paga: {p.description}', f'{p.paid_date:%d/%m/%Y}', money(p.paid_amount)) for p in ctx['paid_payables']]
    payable_rows += [(f'A pagar: {p.description}', f'{p.due_date:%d/%m/%Y}', money(p.amount)) for p in ctx['open_payables']]
    if len(payable_rows) == 1:
        payable_rows.append(('Nenhuma conta no mês', '', ''))
    payable_rows += [('Total pago no mês', '', money(s.payables_paid_total)),
                     ('Total a pagar', '', money(s.payables_open_total)),
                     ('Saldo depois de pagar o que falta', '', money(s.projected_total))]
    story += section('Contas do mês', table(payable_rows, [width * 0.6, width * 0.18, width * 0.22], right_cols=(2,)))

    year_rows = [('Mês', 'Entradas', 'Saídas', 'Saldo total')]
    year_rows += [(MONTH_NAMES[r['month'].month - 1], money(r['income']), money(r['expense']), money(r['total']))
                  for r in ctx['year_rows']]
    story += section(f'Resumo do ano {ctx["month"].year}', table(year_rows, [width * 0.34, width * 0.22, width * 0.22, width * 0.22], right_cols=(1, 2, 3)))

    op_rows = []
    for o in ctx['opinions']:
        stale = ' (de mês reaberto — será refeito)' if o.stale else ''
        op_rows.append((f'{o.get_result_display()}{stale} — {o.author_name} · {o.updated_at:%d/%m/%Y}', ''))
        if o.text:
            op_rows.append((o.text, ''))
    story += section('Parecer da Comissão de Contas',
                     table(op_rows, kv, header=False) if op_rows else P('Nenhum parecer da Comissão de Contas para este mês.', note))

    mov_rows = [('Data', 'Descrição', 'Categoria', 'Forma', 'Valor')]
    for m in ctx['movements']:
        sign = '− ' if m.kind == Kind.EXPENSE else ''
        mov_rows.append((f'{m.date:%d/%m/%Y}', m.shown_description, m.category.name, m.get_method_display(),
                         f'{sign}{money(m.amount)}'))
    if len(mov_rows) == 1:
        mov_rows.append(('', 'Nenhum movimento confirmado neste mês.', '', '', ''))
    story += [Paragraph('Movimentos do mês', h2),
              table(mov_rows, [width * 0.13, width * 0.39, width * 0.2, width * 0.11, width * 0.17], right_cols=(4,))]

    sign_line = Table([['', ''], [P('Tesoureiro'), P('Comissão de Contas')]], colWidths=[width * 0.45, width * 0.45], rowHeights=[22 * mm, None])
    sign_line.hAlign = 'CENTER'
    sign_line.setStyle(TableStyle([('LINEBELOW', (0, 0), (-1, 0), 0.6, colors.black), ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                                   ('LEFTPADDING', (0, 0), (-1, -1), 6), ('RIGHTPADDING', (0, 0), (-1, -1), 6)]))
    story += [Spacer(1, 10 * mm), KeepTogether([sign_line])]

    footer = f'{CHURCH_NAME} · Tesouraria · {ctx["month_label"]}' + (' · ' + OPEN_WARNING if ctx['is_open'] else '')

    def decorate(canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(colors.HexColor('#555555'))
        canvas.drawString(15 * mm, 9 * mm, footer)
        canvas.drawRightString(A4[0] - 15 * mm, 9 * mm, f'Página {doc.page}')
        canvas.restoreState()

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=15 * mm,
                            bottomMargin=16 * mm, title=f'Relatório da Tesouraria — {ctx["month_label"]}',
                            author=CHURCH_NAME)
    doc.build(story, onFirstPage=decorate, onLaterPages=decorate)
    return buffer.getvalue()
