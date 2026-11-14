"""A única função que decide saldos da tesouraria.

Só entram movimentos vivos (não excluídos), confirmados e datados a partir da data de
início. Depósitos/saques (Transfer) movem dinheiro entre contas sem contar como entrada
ou saída. Toda consulta de movimentos passa por `Movement.objects.counted()`.
"""
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Q, Sum

from .models import Account, Category, Kind, Method, Movement, MonthClosing, Payable, Transfer
from .rules import BeforeStart, get_settings, month_end, month_start

ZERO = Decimal('0.00')
NO_DESTINATION = 'Sem destino'


@dataclass(frozen=True)
class MonthSummary:
    month: date
    opening_cash: Decimal
    opening_bank: Decimal
    income_total: Decimal
    expense_total: Decimal
    income_by_category: list[tuple[Category, Decimal]]
    expense_by_category: list[tuple[Category, Decimal]]
    special_by_destination: list[tuple[str, Decimal]]
    income_cash: Decimal
    income_pix: Decimal
    income_other: Decimal
    deposits_to_bank: Decimal
    withdrawals_to_cash: Decimal
    closing_cash: Decimal
    closing_bank: Decimal
    closing_total: Decimal
    payables_open_total: Decimal = Decimal('0')
    payables_paid_total: Decimal = Decimal('0')
    projected_total: Decimal = Decimal('0')
    counted_cash: Decimal | None = None
    cash_difference: Decimal | None = None
    is_closed: bool = False


def _opening(account: str, settings_obj) -> Decimal:
    return settings_obj.opening_cash if account == Account.CASH else settings_obj.opening_bank


def account_balance(account: str, on: date) -> Decimal:
    """Saldo da conta ao fim do dia `on`.

    Levanta NotConfigured sem configuração e BeforeStart se `on` é anterior ao início.
    """
    settings_obj = get_settings()
    if on < settings_obj.start_date:
        raise BeforeStart(
            f'A data {on:%d/%m/%Y} é anterior ao início da tesouraria ({settings_obj.start_date:%d/%m/%Y}).')
    window = dict(date__gte=settings_obj.start_date, date__lte=on)
    moves = Movement.objects.counted().filter(account=account, **window).aggregate(
        income=Sum('amount', filter=Q(kind=Kind.INCOME)),
        expense=Sum('amount', filter=Q(kind=Kind.EXPENSE)),
    )
    transfers = Transfer.objects.filter(deleted_at__isnull=True, **window).aggregate(
        inflow=Sum('amount', filter=Q(to_account=account)),
        outflow=Sum('amount', filter=Q(from_account=account)),
    )
    return (_opening(account, settings_obj)
            + (moves['income'] or ZERO) - (moves['expense'] or ZERO)
            + (transfers['inflow'] or ZERO) - (transfers['outflow'] or ZERO))


def opening_balance(account: str, month: date) -> Decimal:
    """Saldo de abertura do mês: o cadastrado no mês de início; nos demais, o fechamento do mês anterior."""
    settings_obj = get_settings()
    first = month_start(month)
    start_month = month_start(settings_obj.start_date)
    if first < start_month:
        raise BeforeStart(f'O mês {first:%m/%Y} é anterior ao início da tesouraria.')
    if first == start_month:
        return _opening(account, settings_obj)
    return account_balance(account, first - timedelta(days=1))


def total_balance(on: date) -> Decimal:
    return account_balance(Account.CASH, on) + account_balance(Account.BANK, on)


def _by_category(qs, kind):
    rows = (qs.filter(kind=kind).values('category').annotate(total=Sum('amount')))
    categories = Category.objects.in_bulk([r['category'] for r in rows])
    result = [(categories[r['category']], r['total']) for r in rows]
    return sorted(result, key=lambda item: (-item[1], item[0].name))


def month_summary(month: date) -> MonthSummary:
    """Resumo do mês. Levanta NotConfigured/BeforeStart como `opening_balance`.

    Saldos vêm sempre de `opening_balance`/`account_balance`; aqui só se somam totais do período.
    """
    first = month_start(month)
    last = month_end(first)
    opening_cash = opening_balance(Account.CASH, first)
    opening_bank = opening_balance(Account.BANK, first)
    closing_cash = account_balance(Account.CASH, last)
    closing_bank = account_balance(Account.BANK, last)

    start = max(first, get_settings().start_date)
    window = dict(date__gte=start, date__lte=last)
    moves = Movement.objects.counted().filter(**window)
    income = moves.filter(kind=Kind.INCOME)
    totals = moves.aggregate(
        income=Sum('amount', filter=Q(kind=Kind.INCOME)),
        expense=Sum('amount', filter=Q(kind=Kind.EXPENSE)),
        cash=Sum('amount', filter=Q(kind=Kind.INCOME, method=Method.CASH)),
        pix=Sum('amount', filter=Q(kind=Kind.INCOME, method=Method.PIX)),
        other=Sum('amount', filter=Q(kind=Kind.INCOME, method=Method.OTHER)),
    )
    special = {}
    for row in income.filter(category__is_special=True).values('destination').annotate(total=Sum('amount')):
        label = row['destination'].strip() or NO_DESTINATION
        special[label] = special.get(label, ZERO) + row['total']
    transfers = Transfer.objects.filter(deleted_at__isnull=True, **window).aggregate(
        deposits=Sum('amount', filter=Q(from_account=Account.CASH, to_account=Account.BANK)),
        withdrawals=Sum('amount', filter=Q(from_account=Account.BANK, to_account=Account.CASH)),
    )
    payables_open = Payable.objects.filter(
        status=Payable.Status.OPEN, due_date__gte=first, due_date__lte=last).aggregate(t=Sum('amount'))['t'] or ZERO
    payables_paid = Payable.objects.filter(
        status=Payable.Status.PAID, paid_date__gte=first, paid_date__lte=last).aggregate(t=Sum('paid_amount'))['t'] or ZERO
    closing = MonthClosing.objects.filter(month=first).first()
    closing_total = closing_cash + closing_bank
    return MonthSummary(
        month=first,
        opening_cash=opening_cash,
        opening_bank=opening_bank,
        income_total=totals['income'] or ZERO,
        expense_total=totals['expense'] or ZERO,
        income_by_category=_by_category(moves, Kind.INCOME),
        expense_by_category=_by_category(moves, Kind.EXPENSE),
        special_by_destination=sorted(special.items(), key=lambda item: (-item[1], item[0])),
        income_cash=totals['cash'] or ZERO,
        income_pix=totals['pix'] or ZERO,
        income_other=totals['other'] or ZERO,
        deposits_to_bank=transfers['deposits'] or ZERO,
        withdrawals_to_cash=transfers['withdrawals'] or ZERO,
        closing_cash=closing_cash,
        closing_bank=closing_bank,
        closing_total=closing_total,
        payables_open_total=payables_open,
        payables_paid_total=payables_paid,
        projected_total=closing_total - payables_open,
        is_closed=False,
    )
