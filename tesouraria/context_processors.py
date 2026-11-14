from django.urls import reverse

from core.permissions import is_panel_user

from .navigation import build_treasury_nav
from .permissions import can_view_treasury


def treasury_shell(request):
    """Menu e parâmetros da casca só nas páginas da Tesouraria (prefixo /tesouraria/)."""
    if request.path.startswith('/admin/'):
        # Atalho "Tesouraria" na barra do topo do painel (sem item no menu lateral).
        return {'treasury_url': reverse('tesouraria:home')} if can_view_treasury(request.user) else {}
    if not request.path.startswith('/tesouraria/'):
        return {}
    return {
        'admin_nav': build_treasury_nav(request),
        'shell': {
            'home_url': reverse('tesouraria:home'),
            'subtitle': 'Tesouraria',
            'search': False,
            'panel_url': reverse('dashboard') if is_panel_user(request.user) else None,
        },
    }
