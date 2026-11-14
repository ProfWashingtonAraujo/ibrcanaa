"""Conferência do caixa e fechamento do mês.

Toda função aqui roda em `atomic` e começa travando a configuração (`rules.lock_settings`),
a mesma trava que `ensure_month_open` pega nas gravações de lançamentos: assim ninguém cria
um movimento num mês enquanto ele é fechado, reaberto ou conferido.
"""

from datetime import date
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from . import audit
from .balances import month_summary
from .ledger import money
from .models import Movement, MonthClosing, Status
from .rules import (BeforeStart, TreasuryError, ensure_month_open, get_settings, lock_settings, month_end,
                    month_start, shift_month)


def _lock(month: date):
    """Trava a configuração e devolve (primeiro dia do mês, configuração)."""
    lock_settings()
    settings_obj = get_settings()
    first = month_start(month)
    if first < month_start(settings_obj.start_date):
        raise BeforeStart(f'O mês {first:%m/%Y} é anterior ao início da tesouraria.')
    return first, settings_obj


def _snapshot(closing):
    return audit.snapshot(closing) if closing is not None else None


@transaction.atomic
def record_cash_count(month: date, counted: Decimal, user) -> MonthClosing:
    first, _ = _lock(month)
    try:
        counted = Decimal(counted)
    except (TypeError, ValueError, ArithmeticError):
        raise TreasuryError('Informe um valor válido para o caixa contado.')
    if not counted.is_finite() or counted < 0 or counted.as_tuple().exponent < -2:
        raise TreasuryError('O caixa contado deve ser um valor válido, sem mais de duas casas decimais.')
    ensure_month_open(first)
    closing, _created = MonthClosing.objects.select_for_update().get_or_create(month=first)
    before = _snapshot(closing)
    closing.counted_cash, closing.counted_by, closing.counted_at = counted, user, timezone.now()
    closing.save()
    audit.record(user, audit.COUNT, closing, f'Caixa de {first:%m/%Y} conferido: {money(counted)}',
                 before=before, after=audit.snapshot(closing))
    return closing


@transaction.atomic
def close_month(month: date, user, notes: str = '') -> MonthClosing:
    first, settings_obj = _lock(month)
    if first > month_start(timezone.localdate()):
        raise TreasuryError('Não é possível fechar um mês futuro.')
    closing, _created = MonthClosing.objects.select_for_update().get_or_create(month=first)
    if closing.is_closed:
        raise TreasuryError(f'O mês {first:%m/%Y} já está fechado.')
    if first > month_start(settings_obj.start_date):
        previous = shift_month(first, -1)
        if not MonthClosing.objects.filter(month=previous, closed_at__isnull=False).exists():
            raise TreasuryError(f'Feche antes o mês anterior ({previous:%m/%Y}).')
    if Movement.objects.filter(status=Status.PENDING, deleted_at__isnull=True,
                               date__gte=first, date__lte=month_end(first)).exists():
        raise TreasuryError('Há contribuições a confirmar neste mês; trate-as na tela "A confirmar" antes de fechar.')
    before = _snapshot(closing)
    summary = month_summary(first)
    closing.opening_cash, closing.opening_bank = summary.opening_cash, summary.opening_bank
    closing.closing_cash, closing.closing_bank = summary.closing_cash, summary.closing_bank
    closing.closed_at, closing.closed_by, closing.notes = timezone.now(), user, (notes or '').strip()
    closing.save()
    audit.record(user, audit.CLOSE, closing, f'Mês {first:%m/%Y} fechado: saldo total {money(summary.closing_total)}',
                 before=before, after=audit.snapshot(closing))
    return closing


@transaction.atomic
def reopen_month(month: date, user) -> MonthClosing:
    first, _ = _lock(month)
    closing = MonthClosing.objects.select_for_update().filter(month=first).first()
    if closing is None or not closing.is_closed:
        raise TreasuryError(f'O mês {first:%m/%Y} não está fechado.')
    following = shift_month(first, 1)
    if MonthClosing.objects.filter(month=following, closed_at__isnull=False).exists():
        raise TreasuryError(f'Reabra antes o mês seguinte ({following:%m/%Y}).')
    before = _snapshot(closing)
    closing.closed_at = closing.closed_by = None
    closing.opening_cash = closing.opening_bank = closing.closing_cash = closing.closing_bank = None
    closing.save()
    audit.record(user, audit.REOPEN, closing, f'Mês {first:%m/%Y} reaberto', before=before,
                 after=audit.snapshot(closing))
    return closing
