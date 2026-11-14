"""Relação de dizimistas: quem devolveu dízimo confirmado em um período."""
import unicodedata
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.db.models import Count, Max, Sum

from core.models import Member

from .models import Kind, Movement

ZERO = Decimal('0.00')


@dataclass(frozen=True)
class TitherRow:
    member: Member
    total: Decimal
    count: int
    last_date: date


def _sort_key(name: str) -> str:
    return unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode().casefold()


def tithers(start: date, end: date) -> tuple[list[TitherRow], Decimal]:
    """Linhas por membro (ordem alfabética) e o total de dízimos sem membro identificado.

    Só entradas vivas e confirmadas, de categoria de dízimo, com data em [start, end].
    Duas consultas: um agregado agrupado por membro e uma busca dos membros.
    """
    grouped = (Movement.objects.counted()
               .filter(kind=Kind.INCOME, category__is_tithe=True, date__gte=start, date__lte=end)
               .order_by().values('member_id')
               .annotate(total=Sum('amount'), count=Count('id'), last=Max('date')))
    unidentified = ZERO
    data = {}
    for row in grouped:
        if row['member_id'] is None:
            unidentified = row['total']
        else:
            data[row['member_id']] = row
    members = Member.objects.in_bulk(list(data)) if data else {}
    rows = [TitherRow(member=members[pk], total=row['total'], count=row['count'], last_date=row['last'])
            for pk, row in data.items() if pk in members]
    rows.sort(key=lambda r: (_sort_key(r.member.name), r.member.pk))
    return rows, unidentified
