import calendar
from datetime import date

from django.utils import timezone

from .models import MonthClosing, TreasurySettings


class TreasuryError(Exception):
    """Erro de regra da tesouraria; a mensagem é sempre em português."""


class MonthClosed(TreasuryError):
    pass


class BeforeStart(TreasuryError):
    pass


class NotConfigured(TreasuryError):
    pass


def month_start(d: date) -> date:
    return d.replace(day=1)


def month_end(d: date) -> date:
    return d.replace(day=calendar.monthrange(d.year, d.month)[1])


def get_settings() -> TreasurySettings:
    """Configuração da tesouraria; levanta NotConfigured se ainda não foi cadastrada."""
    settings_obj = TreasurySettings.get()
    if settings_obj is None:
        raise NotConfigured('A tesouraria ainda não foi configurada: informe a data de início e os saldos iniciais.')
    return settings_obj


def ensure_after_start(d: date) -> None:
    """Levanta NotConfigured sem configuração e BeforeStart se `d` é anterior à data de início."""
    start = get_settings().start_date
    if d < start:
        raise BeforeStart(f'A data {d:%d/%m/%Y} é anterior ao início da tesouraria ({start:%d/%m/%Y}).')


def ensure_month_open(d: date) -> None:
    """Levanta MonthClosed se o mês de `d` já foi fechado."""
    if MonthClosing.objects.filter(month=month_start(d), closed_at__isnull=False).exists():
        raise MonthClosed(f'O mês {d:%m/%Y} está fechado; reabra-o para alterar lançamentos.')


def parse_month(value: str | None) -> date:
    """'2026-11' vira 1º/11/2026; vazio ou inválido vira o primeiro dia do mês atual."""
    try:
        year, month = (value or '').split('-')
        return date(int(year), int(month), 1)
    except (ValueError, TypeError):
        return month_start(timezone.localdate())
