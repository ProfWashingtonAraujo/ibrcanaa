"""Contas recorrentes e parceladas: geram contas a pagar comuns, mês a mês.

A geração é uma ação do sistema (roda ao abrir a tela, para qualquer papel que a veja):
as contas geradas têm `created_by` nulo e não gravam auditoria, pois não há usuário
responsável. A auditoria registra apenas o que o Tesoureiro faz com a recorrência.
"""

import calendar
from datetime import date

from django.db import IntegrityError, transaction

from . import audit
from .ledger import money, validate_amount
from .models import Kind, Payable, RecurringBill, TreasurySettings
from .rules import TreasuryError, month_start

FIELDS = ('description', 'payee', 'category', 'amount', 'due_day', 'start_date', 'installments')
MAX_INSTALLMENTS = 600


def due_date_for(month: date, due_day: int) -> date:
    """Vencimento no mês de `month`; dias além do fim do mês caem no último dia."""
    return date(month.year, month.month, min(due_day, calendar.monthrange(month.year, month.month)[1]))


def _month_index(d: date) -> int:
    return d.year * 12 + d.month - 1


def _shift(month: date, delta: int) -> date:
    index = _month_index(month) + delta
    return date(index // 12, index % 12 + 1, 1)


def ensure_recurring(today: date) -> int:
    """Cria as contas do mês de `today` e do seguinte; devolve quantas foram criadas.

    Idempotente e seguro sob chamadas concorrentes: a restrição única (recorrência, mês)
    decide; quem perde a corrida recebe IntegrityError, tratado como "já existe". Uma conta
    cancelada continua ocupando o mês, então não é recriada.
    """
    current = month_start(today)
    settings_obj = TreasurySettings.get()
    floor = month_start(settings_obj.start_date) if settings_obj else None
    created = 0
    for bill in RecurringBill.objects.filter(active=True).select_related('category'):
        first = month_start(bill.start_date)
        for month in (current, _shift(current, 1)):
            number = _month_index(month) - _month_index(first) + 1
            if number < 1 or (bill.installments and number > bill.installments):
                continue
            if floor and month < floor:
                continue
            defaults = dict(description=bill.description, payee=bill.payee, category=bill.category,
                            amount=bill.amount, due_date=due_date_for(month, bill.due_day),
                            installment_number=number if bill.installments else None,
                            installments_total=bill.installments or None)
            try:
                with transaction.atomic():
                    _, was_created = Payable.objects.get_or_create(recurring=bill, period=month, defaults=defaults)
            except IntegrityError:
                was_created = False
            created += was_created
    return created


def _summary(bill, verb) -> str:
    return f'{verb}: conta recorrente de {money(bill.amount)} em {bill.category.name}, dia {bill.due_day}'


def _clean(fields) -> dict:
    data = {k: v for k, v in fields.items() if k in FIELDS}
    data['amount'] = validate_amount(data.get('amount'))
    data['description'] = (data.get('description') or '').strip()
    if not data['description']:
        raise TreasuryError('Informe a descrição da conta.')
    data['payee'] = (data.get('payee') or '').strip()
    if data.get('category') is None or data['category'].kind != Kind.EXPENSE:
        raise TreasuryError('A categoria deve ser de saída.')
    day = data.get('due_day')
    if not isinstance(day, int) or not 1 <= day <= 31:
        raise TreasuryError('O dia do vencimento deve estar entre 1 e 31.')
    if data.get('start_date') is None:
        raise TreasuryError('Informe o primeiro mês.')
    count = data.get('installments')
    if count is not None and not 1 <= count <= MAX_INSTALLMENTS:
        raise TreasuryError(f'O número de parcelas deve estar entre 1 e {MAX_INSTALLMENTS}.')
    return data


@transaction.atomic
def create_recurring(user, **fields) -> RecurringBill:
    data = _clean(fields)
    bill = RecurringBill.objects.create(created_by=user, **data)
    audit.record(user, audit.CREATE, bill, _summary(bill, 'Recorrência criada'), after=audit.snapshot(bill))
    return bill


@transaction.atomic
def update_recurring(user, bill, **fields) -> RecurringBill:
    bill = RecurringBill.objects.select_for_update(of=('self',)).select_related('category').get(pk=bill.pk)
    before = audit.snapshot(bill)
    for name, value in _clean(fields).items():
        setattr(bill, name, value)
    bill.save()
    audit.record(user, audit.UPDATE, bill, _summary(bill, 'Recorrência alterada'),
                 before=before, after=audit.snapshot(bill))
    return bill


@transaction.atomic
def set_active(user, bill, active: bool) -> RecurringBill:
    bill = RecurringBill.objects.select_for_update(of=('self',)).select_related('category').get(pk=bill.pk)
    before = audit.snapshot(bill)
    bill.active = active
    bill.save(update_fields=['active'])
    audit.record(user, audit.UPDATE, bill, _summary(bill, 'Recorrência ativada' if active else 'Recorrência desativada'),
                 before=before, after=audit.snapshot(bill))
    return bill
