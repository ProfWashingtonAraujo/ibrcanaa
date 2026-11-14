"""Menu lateral da Tesouraria, no mesmo formato de `core.navigation.build_admin_nav`.

Itens cujas rotas ainda não existem são omitidos em silêncio; cada tela nova aparece
no menu assim que registra a sua rota.
"""
from django.urls import NoReverseMatch, reverse
from django.utils.safestring import mark_safe

from core.navigation import ICONS

from .models import Movement, Status
from .permissions import can_edit_treasury, can_see_member_names, can_view_details, can_view_treasury


def _pending_count():
    return Movement.objects.live().filter(status=Status.PENDING).count()


def _overdue_count():
    # Contas a pagar vencidas: passa a contar quando a Task 9 criar o modelo.
    return 0


# (rótulo, ícone, nome da rota, rotas que o destacam, visível para, contador)
ITEMS = [
    {'label': 'Caixa do Mês', 'icon': 'finance', 'url_name': 'home', 'active': {'home'}, 'visible': can_view_treasury},
    {'label': 'Relatório', 'icon': 'reports', 'url_name': 'report', 'active': {'report'}, 'visible': can_view_treasury},
    {'label': 'Dizimistas', 'icon': 'members', 'url_name': 'tithers', 'active': {'tithers'}, 'visible': can_see_member_names},
    {'label': 'A confirmar', 'icon': 'inbox', 'url_name': 'pending', 'active': {'pending'}, 'visible': can_edit_treasury, 'count': _pending_count},
    {'label': 'Contas a pagar', 'icon': 'applications', 'url_name': 'payables', 'active': {'payables'}, 'visible': can_view_details, 'count': _overdue_count},
    {'label': 'Lançamentos', 'icon': 'content', 'url_name': 'movements', 'active': {'movements'}, 'visible': can_view_details},
    {'label': 'Ofertas especiais', 'icon': 'ministries', 'url_name': 'special', 'active': {'special'}, 'visible': can_view_details},
    {'label': 'Histórico', 'icon': 'events', 'url_name': 'audit', 'active': {'audit'}, 'visible': can_view_details},
    {'label': 'Histórico anterior', 'icon': 'books', 'url_name': 'legacy', 'active': {'legacy'}, 'visible': can_view_details},
    {'label': 'Configurações', 'icon': 'settings', 'url_name': 'settings', 'active': {'settings'}, 'visible': can_edit_treasury},
]


def build_treasury_nav(request):
    """Devolve {'groups': [...]} ou None para quem não pode ver a Tesouraria."""
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated or not can_view_treasury(user):
        return None
    match = request.resolver_match
    current = match.url_name if match and match.namespace == 'tesouraria' else None
    items = []
    for spec in ITEMS:
        if not spec['visible'](user):
            continue
        try:
            url = reverse(f"tesouraria:{spec['url_name']}")
        except NoReverseMatch:
            continue
        count = spec['count']() if 'count' in spec else 0
        items.append({
            'label': spec['label'],
            'icon': mark_safe(ICONS[spec['icon']]),
            'url': url,
            'is_active': current in spec['active'],
            'count': count,
            'count_label': '99+' if count > 99 else str(count),
        })
    return {'groups': [{'title': 'Tesouraria', 'items': items}]}
