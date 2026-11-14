"""Parecer da Comissão de Contas sobre um mês fechado.

`record_opinion` roda em `atomic` e trava a configuração (`rules.lock_settings`), a mesma trava de
fechar/reabrir o mês: o mês não pode ser reaberto no meio da gravação do parecer.

Parecer de mês reaberto: continua guardado (nenhum dado é apagado) e aparece marcado como
"de mês reaberto — será refeito" (`opinion.stale`) até o mês ser fechado de novo e a Comissão refazer.
"""

from datetime import date

from django.db import transaction

from . import audit
from .models import CommitteeOpinion, MonthClosing
from .rules import TreasuryError, lock_settings, month_start

STALE_LABEL = 'de mês reaberto — será refeito'


@transaction.atomic
def record_opinion(month: date, author, result: str, text: str = '') -> CommitteeOpinion:
    lock_settings()
    first = month_start(month)
    if not MonthClosing.objects.filter(month=first, closed_at__isnull=False).exists():
        raise TreasuryError(f'O mês {first:%m/%Y} não está fechado; o parecer só pode ser dado sobre um mês fechado.')
    opinion = CommitteeOpinion.objects.select_for_update().filter(month=first, author=author).first()
    before = audit.snapshot(opinion) if opinion is not None else None  # antes de validar/alterar
    created = opinion is None
    if created:
        opinion = CommitteeOpinion(month=first, author=author)
    opinion.result, opinion.text = result, (text or '').strip()
    opinion.full_clean(exclude=['author'])
    opinion.save()
    label = opinion.get_result_display()
    audit.record(author, audit.OPINION, opinion,
                 f'Parecer sobre {first:%m/%Y}: {label}' if created else f'Parecer sobre {first:%m/%Y} refeito: {label}',
                 before=before, after=audit.snapshot(opinion))
    return opinion


def opinions_for(month: date) -> list[CommitteeOpinion]:
    """Pareceres do mês (para o Caixa do Mês e o relatório), com `stale=True` se o mês foi reaberto."""
    first = month_start(month)
    closed = MonthClosing.objects.filter(month=first, closed_at__isnull=False).exists()
    rows = list(CommitteeOpinion.objects.filter(month=first).select_related('author'))
    for opinion in rows:
        opinion.stale = not closed
        opinion.author_name = opinion.author.get_full_name() or opinion.author.get_username()
    return rows
