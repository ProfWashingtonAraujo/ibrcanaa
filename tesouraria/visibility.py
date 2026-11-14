from .permissions import can_see_member_names


def description_for(movement, user):
    """Descrição do movimento, mascarada para quem não pode ver nomes de membros."""
    if movement.member_id is None or can_see_member_names(user):
        return movement.description
    return f'{movement.category.name} (contribuição de membro)'
