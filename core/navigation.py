"""Menu lateral do painel: grupos, itens, visibilidade por perfil e contadores."""
from django.urls import reverse
from django.utils.safestring import mark_safe

from .models import ContactLead, MembershipApplication
from .permissions import can_manage_users, is_pastor, is_panel_user

ICONS = {
    'overview': '<path d="M4 13h6V4H4v9Zm0 7h6v-4H4v4Zm10 0h6v-9h-6v9Zm0-16v4h6V4h-6Z"/>',
    'members': '<path d="M16 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8ZM8 12a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Zm8 2c-3 0-6 1.5-6 4.5V21h12v-2.5C22 15.5 19 14 16 14ZM8 14c-2.7 0-6 1.4-6 4.2V21h6v-2.5c0-1.7.7-3 1.8-4A8 8 0 0 0 8 14Z"/>',
    'applications': '<path d="M7 3h10v2h3v17H4V5h3V3Zm2 2h6V4H9v1Zm-3 2v13h12V7h-1v2H7V7H6Zm2 5h8v2H8v-2Zm0 4h6v2H8v-2Z"/>',
    'ministries': '<path d="M11 2h2v7h7v2h-7v11h-2V11H4V9h7V2Z"/><path d="M6 14h2v8H6v-8Zm10 0h2v8h-2v-8Z" opacity=".45"/>',
    'content': '<path d="M5 4h14v16H5z" opacity=".15"/><path d="M7 6h10v2H7zM7 10h10v2H7zM7 14h7v2H7z"/><path d="M4 3h16v18H4z" fill="none" stroke="currentColor" stroke-width="1.6"/>',
    'books': '<path d="M4 4a2 2 0 0 1 2-2h11a3 3 0 0 1 3 3v15a1 1 0 0 1-1 1H6a2 2 0 0 1-2-2V4Zm3 0v15h12V5a1 1 0 0 0-1-1H7Zm2 4h7v2H9V8Zm0 4h7v2H9v-2Z"/>',
    'courses': '<path d="M3 5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v11a2 2 0 0 1-2 2h-6v2h3v2H8v-2h3v-2H5a2 2 0 0 1-2-2V5Zm2 0v11h14V5H5Zm5 2 5 3.5-5 3.5V7Z"/>',
    'events': '<path d="M7 2h2v3h6V2h2v3h3a2 2 0 0 1 2 2v13a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2h3V2Zm13 9H4v9h16v-9ZM4 9h16V7H4v2Z"/>',
    'finance': '<path d="M3 6a3 3 0 0 1 3-3h12a3 3 0 0 1 3 3v2H6a3 3 0 0 0-3 3V6Zm0 5a2 2 0 0 1 2-2h16v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-8Zm13 2v4h5v-4h-5Zm2 1h2v2h-2v-2Z"/>',
    'reports': '<path d="M4 20h16v2H2V2h2v18Zm3-2H5v-6h2v6Zm4 0H9V7h2v11Zm4 0h-2V9h2v9Zm4 0h-2V4h2v14Z"/>',
    'settings': '<path d="m19.4 13 .1-1-.1-1 2-1.6-2-3.4-2.5 1a8 8 0 0 0-1.7-1L15 3h-4l-.4 2.8c-.6.3-1.2.6-1.7 1L6.4 6l-2 3.4L6.6 11l-.1 1 .1 1-2.2 1.6 2 3.4 2.5-1c.5.4 1.1.7 1.7 1L11 21h4l.4-3c.6-.3 1.2-.6 1.7-1l2.5 1 2-3.4-2.2-1.6ZM13 15.5A3.5 3.5 0 1 1 13 8a3.5 3.5 0 0 1 0 7.5Z"/>',
    'inbox': '<path d="M4 4h16a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2Zm0 2v.5l8 5 8-5V6H4Zm16 3-8 5-8-5v9h16V9Z"/>',
}


def _item(label, icon, url_name, active, count=0):
    return {
        'label': label,
        'icon': mark_safe(ICONS[icon]),
        'url': reverse(url_name),
        'active_names': set(active),
        'count': count,
    }


def build_admin_nav(request):
    """Devolve {'groups': [...], 'user_role': ...} ou None fora do painel."""
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated or not is_panel_user(user):
        return None
    match = request.resolver_match
    current = match.url_name if match else None
    pastor = is_pastor(user)

    contacts = ContactLead.objects.filter(contacted=False).count()
    reviews = MembershipApplication.objects.filter(status=MembershipApplication.Status.REVIEW).count() if pastor else 0

    people = [
        _item('Visão geral', 'overview', 'dashboard', {'dashboard'}, contacts),
        _item('Membros', 'members', 'members', {'members', 'member_create', 'member_edit', 'member_detail'}),
    ]
    if pastor:
        people.append(_item('Candidaturas', 'applications', 'membership_applications',
                            {'membership_applications', 'membership_application_create', 'membership_application_edit'}, reviews))
    people.append(_item('Ministérios', 'ministries', 'ministries', {'ministries', 'ministry_create', 'ministry_edit'}))

    teaching = [
        _item('Cursos', 'courses', 'courses', {'courses', 'course_create', 'course_edit', 'course_manage', 'lesson_create', 'lesson_edit'}),
        _item('Publicações', 'books', 'books', {'books', 'book_create', 'book_edit'}),
    ]
    agenda = [
        _item('Eventos', 'events', 'events', {'events', 'event_create', 'event_edit'}),
        _item('Conteúdo do site', 'content', 'institutional_content', {'institutional_content', 'church_about_edit', 'church_history_edit'}),
    ]
    management = []
    if not pastor:
        management.append(_item('Financeiro', 'finance', 'finance', {'finance', 'transaction_create'}))
    management.append(_item('Relatórios', 'reports', 'reports', {'reports'}))
    if user.is_superuser or can_manage_users(user):
        management.append(_item('Configurações', 'settings', 'user_accounts', {'user_accounts', 'user_account_create', 'user_account_edit'}))

    groups = [
        {'title': 'Pessoas', 'items': people},
        {'title': 'Ensino', 'items': teaching},
        {'title': 'Agenda e site', 'items': agenda},
        {'title': 'Gestão', 'items': management},
    ]
    for group in groups:
        for item in group['items']:
            item['is_active'] = current in item['active_names']
            item['count_label'] = '99+' if item['count'] > 99 else str(item['count'])
    return {'groups': groups}
