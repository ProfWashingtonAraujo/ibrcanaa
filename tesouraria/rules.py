import calendar
from datetime import date

from django.db import connection
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


def shift_month(d: date, delta: int) -> date:
    """Primeiro dia do mês `delta` meses depois (ou antes) de `d`."""
    index = d.year * 12 + d.month - 1 + delta
    return date(index // 12, index % 12 + 1, 1)


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


def lock_settings():
    """Trava a linha única de TreasurySettings (select_for_update) até o fim da transação.

    É o "mutex" do fechamento: fechar/reabrir/conferir o mês e toda gravação que passa por
    `ensure_month_open` pegam essa mesma trava antes de olhar o fechamento, então um
    lançamento não nasce num mês enquanto ele está sendo fechado. No SQLite o
    `select_for_update` é ignorado (o banco já serializa as escritas). Exige `atomic`.
    """
    return TreasurySettings.objects.select_for_update().filter(pk=1).first()


def ensure_month_open(d: date) -> None:
    """Levanta MonthClosed se o mês de `d` já foi fechado.

    Dentro de uma transação, trava antes a configuração (`lock_settings`), serializando
    com `close_month`/`reopen_month`.
    """
    if connection.in_atomic_block:
        lock_settings()
    if MonthClosing.objects.filter(month=month_start(d), closed_at__isnull=False).exists():
        raise MonthClosed(f'O mês {d:%m/%Y} está fechado; reabra-o para alterar lançamentos.')


def parse_month(value: str | None) -> date:
    """'2026-11' vira 1º/11/2026; vazio, inválido ou com ano fora de 2000..2100 vira o primeiro dia do mês atual."""
    try:
        year, month = (value or '').split('-')
        parsed = date(int(year), int(month), 1)
        if not 2000 <= parsed.year <= 2100:
            raise ValueError
        return parsed
    except (ValueError, TypeError):
        return month_start(timezone.localdate())
