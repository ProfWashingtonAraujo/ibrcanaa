from django.contrib.auth.models import AnonymousUser
from django.test import TestCase
from django.urls import reverse

from core.models import AccessProfile
from core.permissions import is_panel_user
from tesouraria.permissions import (
    can_edit_treasury, can_give_opinion, can_see_member_names, can_view_details,
    can_view_treasury, landing_url,
)

from .helpers import WITHOUT_AXES, configure, make_user

Role = AccessProfile.Role


class PermissionPredicatesTests(TestCase):
    def test_matrix(self):
        roles = [Role.TREASURER, Role.BOARD, Role.COMMITTEE, Role.DEACON, Role.SECRETARY, Role.PASTOR, Role.MEMBER]
        expected = {
            'edit': {Role.TREASURER},
            'view': {Role.TREASURER, Role.COMMITTEE},
            'details': {Role.TREASURER, Role.COMMITTEE},
            'names': {Role.TREASURER, Role.COMMITTEE},
            'opinion': {Role.COMMITTEE},
        }
        predicates = {
            'edit': can_edit_treasury, 'view': can_view_treasury, 'details': can_view_details,
            'names': can_see_member_names, 'opinion': can_give_opinion,
        }
        for role in roles:
            user = make_user(f'u-{role}', role)
            for name, predicate in predicates.items():
                with self.subTest(role=role, predicate=name):
                    self.assertIs(predicate(user), role in expected[name])
        superuser = make_user('root', is_staff=True, is_superuser=True)
        for name in ('edit', 'view', 'details', 'names'):
            with self.subTest(role='superuser', predicate=name):
                self.assertIs(predicates[name](superuser), True)
        self.assertIs(can_give_opinion(superuser), False)
        for name, predicate in predicates.items():
            with self.subTest(role='anonymous', predicate=name):
                self.assertIs(predicate(AnonymousUser()), False)

    def test_committee_is_not_panel_user(self):
        user = make_user('c', Role.COMMITTEE)
        self.assertIs(is_panel_user(user), False)
        self.assertIs(user.is_staff, False)

    def test_landing_url(self):
        self.assertEqual(landing_url(make_user('t', Role.TREASURER)), reverse('tesouraria:home'))
        self.assertEqual(landing_url(make_user('c', Role.COMMITTEE)), reverse('tesouraria:home'))
        self.assertEqual(landing_url(make_user('b', Role.BOARD)), reverse('dashboard'))
        self.assertEqual(landing_url(make_user('m', Role.MEMBER)), reverse('member_portal'))


@WITHOUT_AXES
class DecoratorAndLoginTests(TestCase):
    def test_login_redirects_by_role(self):
        for role in [Role.TREASURER, Role.COMMITTEE, Role.BOARD, Role.MEMBER]:
            user = make_user(f'login-{role}', role)
            with self.subTest(role=role):
                response = self.client.post(
                    reverse('login'), {'username': user.username, 'password': 'senha-forte-123'},
                )
                self.assertRedirects(response, landing_url(user), fetch_redirect_response=False)
                self.client.logout()

    def test_home_access(self):
        configure()  # sem configuração o tesoureiro é redirecionado às Configurações
        url = reverse('tesouraria:home')
        self.assertEqual(self.client.get(url).status_code, 302)
        for role, status in [(Role.TREASURER, 200), (Role.COMMITTEE, 200), (Role.BOARD, 403), (Role.MEMBER, 403)]:
            self.client.force_login(make_user(f'h-{role}', role))
            with self.subTest(role=role):
                self.assertEqual(self.client.get(url).status_code, status)
