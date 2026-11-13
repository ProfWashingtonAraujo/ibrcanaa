from .navigation import build_admin_nav


def admin_nav(request):
    """Disponibiliza o menu do painel só nas páginas do painel (prefixo /admin/)."""
    if not request.path.startswith('/admin/'):
        return {}
    return {'admin_nav': build_admin_nav(request)}
