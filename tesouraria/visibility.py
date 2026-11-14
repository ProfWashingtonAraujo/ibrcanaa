from .models import Source
from .permissions import can_see_member_names


def description_for(movement, user):
    """Descrição do movimento, mascarada para quem não pode ver nomes de membros."""
    if can_see_member_names(user) or (movement.member_id is None and movement.source != Source.PORTAL):
        return movement.description
    return f'{movement.category.name} (contribuição de membro)'
