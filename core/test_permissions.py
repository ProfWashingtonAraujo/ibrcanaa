from django.contrib.auth.models import AnonymousUser, User
from django.test import TestCase
from django.urls import reverse

from core import permissions
from core.models import AccessProfile, Member

Role = AccessProfile.Role


def make_user(username, role=None, *, is_staff=False, is_superuser=False):
    user = User.objects.create_user(
        username=username,
        password='senha-de-teste-123',
        email=f'{username}@example.org',
        is_staff=is_staff,
        is_superuser=is_superuser,
    )
    if role is not None:
        AccessProfile.objects.create(user=user, role=role)
    # Recarrega para não reutilizar o cache do perfil criado acima.
    return User.objects.get(pk=user.pk)


class PermissionPredicateTests(TestCase):
    def test_anonymous_has_no_access(self):
        user = AnonymousUser()
        self.assertFalse(permissions.is_panel_user(user))
        self.assertFalse(permissions.is_pastor(user))
        self.assertFalse(permissions.can_manage_users(user))
        self.assertFalse(permissions.can_access_finance(user))

    def test_panel_access_follows_role_for_staff_users(self):
        for role in AccessProfile.ADMIN_ROLES:
            with self.subTest(role=role):
                self.assertTrue(permissions.is_panel_user(make_user(f'staff-{role}', role, is_staff=True)))

    def test_staff_flag_alone_is_not_enough_for_non_admin_roles(self):
        for role in (Role.MEMBER, Role.VISITOR, Role.CHILD):
            with self.subTest(role=role):
                self.assertFalse(permissions.is_panel_user(make_user(f'sneaky-{role}', role, is_staff=True)))

    def test_admin_role_without_staff_flag_has_no_panel_access(self):
        self.assertFalse(permissions.is_panel_user(make_user('no-flag', Role.BOARD, is_staff=False)))

    def test_staff_without_profile_keeps_panel_access(self):
        self.assertTrue(permissions.is_panel_user(make_user('legacy-staff', None, is_staff=True)))

    def test_superuser_always_has_panel_access(self):
        user = make_user('root', Role.MEMBER, is_staff=True, is_superuser=True)
        self.assertTrue(permissions.is_panel_user(user))
        self.assertTrue(permissions.can_manage_users(user))

    def test_only_pastor_is_pastor(self):
        self.assertTrue(permissions.is_pastor(make_user('p', Role.PASTOR, is_staff=True)))
        self.assertFalse(permissions.is_pastor(make_user('b', Role.BOARD, is_staff=True)))
        self.assertFalse(permissions.is_pastor(make_user('nobody', None)))

    def test_user_management_is_limited_to_pastor_and_board(self):
        self.assertTrue(permissions.can_manage_users(make_user('p', Role.PASTOR, is_staff=True)))
        self.assertTrue(permissions.can_manage_users(make_user('b', Role.BOARD, is_staff=True)))
        self.assertFalse(permissions.can_manage_users(make_user('t', Role.TREASURER, is_staff=True)))
        self.assertFalse(permissions.can_manage_users(make_user('m', Role.MEMBER)))

    def test_finance_is_blocked_for_pastor_and_non_panel_users(self):
        self.assertFalse(permissions.can_access_finance(make_user('p', Role.PASTOR, is_staff=True)))
        self.assertTrue(permissions.can_access_finance(make_user('t', Role.TREASURER, is_staff=True)))
        self.assertFalse(permissions.can_access_finance(make_user('m', Role.MEMBER, is_staff=True)))


class PermissionViewTests(TestCase):
    def login(self, user):
        self.client.force_login(user)

    def test_staff_flag_with_member_role_cannot_open_panel(self):
        self.login(make_user('sneaky', Role.MEMBER, is_staff=True))
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response['Location'])

    def test_staff_flag_with_member_role_cannot_open_finance(self):
        self.login(make_user('sneaky', Role.MEMBER, is_staff=True))
        self.assertEqual(self.client.get(reverse('finance')).status_code, 403)

    def test_staff_flag_with_member_role_cannot_manage_users(self):
        self.login(make_user('sneaky', Role.MEMBER, is_staff=True))
        self.assertEqual(self.client.get(reverse('user_accounts')).status_code, 403)

    def test_login_sends_staff_flag_with_member_role_to_portal(self):
        user = make_user('sneaky', Role.MEMBER, is_staff=True)
        Member.objects.create(user=user, name='Sneaky', email='sneaky@example.org')
        response = self.client.post(reverse('login'), {'username': 'sneaky', 'password': 'senha-de-teste-123'})
        self.assertRedirects(response, reverse('member_portal'), fetch_redirect_response=False)

    def test_login_sends_admin_to_dashboard(self):
        make_user('admin', Role.BOARD, is_staff=True)
        response = self.client.post(reverse('login'), {'username': 'admin', 'password': 'senha-de-teste-123'})
        self.assertRedirects(response, reverse('dashboard'), fetch_redirect_response=False)

    def test_member_portal_does_not_bounce_member_with_staff_flag_to_panel(self):
        user = make_user('sneaky', Role.MEMBER, is_staff=True)
        Member.objects.create(user=user, name='Sneaky', email='sneaky@example.org')
        self.login(user)
        self.assertEqual(self.client.get(reverse('member_portal')).status_code, 200)

    def test_board_can_open_panel_and_finance(self):
        self.login(make_user('board', Role.BOARD, is_staff=True))
        self.assertEqual(self.client.get(reverse('dashboard')).status_code, 200)
        self.assertEqual(self.client.get(reverse('finance')).status_code, 200)

    def test_pastor_sees_panel_but_not_finance(self):
        self.login(make_user('pastor', Role.PASTOR, is_staff=True))
        self.assertEqual(self.client.get(reverse('dashboard')).status_code, 200)
        self.assertEqual(self.client.get(reverse('finance')).status_code, 403)

    def test_membership_applications_are_pastor_only(self):
        self.login(make_user('board', Role.BOARD, is_staff=True))
        self.assertEqual(self.client.get(reverse('membership_applications')).status_code, 403)
        self.client.logout()
        self.login(make_user('pastor', Role.PASTOR, is_staff=True))
        self.assertEqual(self.client.get(reverse('membership_applications')).status_code, 200)

    def test_user_accounts_allowed_for_board_and_denied_for_treasurer(self):
        self.login(make_user('board', Role.BOARD, is_staff=True))
        self.assertEqual(self.client.get(reverse('user_accounts')).status_code, 200)
        self.client.logout()
        self.login(make_user('treasurer', Role.TREASURER, is_staff=True))
        self.assertEqual(self.client.get(reverse('user_accounts')).status_code, 403)

    def test_superuser_without_profile_reaches_panel_and_users(self):
        self.login(make_user('root', None, is_staff=True, is_superuser=True))
        self.assertEqual(self.client.get(reverse('dashboard')).status_code, 200)
        self.assertEqual(self.client.get(reverse('user_accounts')).status_code, 200)
