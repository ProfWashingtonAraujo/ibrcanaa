from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import reverse

from core.models import ContactLead
from core.security import get_client_ip

PASSWORD = 'senha-de-teste-123'
LIMIT = 5


def make_user(username):
    return User.objects.create_user(username=username, password=PASSWORD, email=f'{username}@example.org')


class LoginThrottleTests(TestCase):
    def attempt(self, username, password, **extra):
        extra.setdefault('REMOTE_ADDR', '10.0.0.1')
        return self.client.post(reverse('login'), {'username': username, 'password': password}, **extra)

    def fail(self, username, times, **extra):
        for _ in range(times):
            response = self.attempt(username, 'senha-errada', **extra)
            self.assertNotEqual(response.status_code, 302)

    def test_repeated_failures_lock_the_account_even_with_correct_password(self):
        make_user('alice')
        self.fail('alice', LIMIT)
        response = self.attempt('alice', PASSWORD)
        self.assertEqual(response.status_code, 429)
        self.assertTemplateUsed(response, 'core/lockout.html')
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_failures_below_the_limit_do_not_lock(self):
        make_user('alice')
        self.fail('alice', LIMIT - 1)
        self.assertEqual(self.attempt('alice', PASSWORD).status_code, 302)

    def test_lockout_does_not_affect_other_users(self):
        make_user('alice')
        make_user('bob')
        self.fail('alice', LIMIT)
        self.assertEqual(self.attempt('bob', PASSWORD).status_code, 302)

    def test_successful_login_resets_the_failure_counter(self):
        make_user('alice')
        self.fail('alice', LIMIT - 1)
        self.assertEqual(self.attempt('alice', PASSWORD).status_code, 302)
        self.client.post(reverse('logout'))
        self.fail('alice', LIMIT - 1)
        self.assertEqual(self.attempt('alice', PASSWORD).status_code, 302)

    def test_forged_forwarding_headers_do_not_bypass_the_lockout(self):
        make_user('alice')
        for index in range(LIMIT):
            self.attempt(
                'alice', 'senha-errada',
                HTTP_X_FORWARDED_FOR=f'203.0.113.{index}',
                HTTP_X_VERCEL_FORWARDED_FOR=f'198.51.100.{index}',
            )
        response = self.attempt(
            'alice', PASSWORD,
            HTTP_X_FORWARDED_FOR='203.0.113.200',
            HTTP_X_VERCEL_FORWARDED_FOR='198.51.100.200',
        )
        self.assertEqual(response.status_code, 429)

    def test_on_vercel_the_lock_is_per_client_ip(self):
        make_user('alice')
        with patch.dict('os.environ', {'VERCEL': '1'}):
            self.fail('alice', LIMIT, HTTP_X_VERCEL_FORWARDED_FOR='198.51.100.1')
            locked = self.attempt('alice', PASSWORD, HTTP_X_VERCEL_FORWARDED_FOR='198.51.100.1')
            other_client = self.attempt('alice', PASSWORD, HTTP_X_VERCEL_FORWARDED_FOR='198.51.100.2')
        self.assertEqual(locked.status_code, 429)
        self.assertEqual(other_client.status_code, 302)

    def test_login_page_still_renders_and_shows_invalid_credentials(self):
        make_user('alice')
        response = self.attempt('alice', 'senha-errada')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Usuário ou senha inválidos.')


class ClientIpTests(SimpleTestCase):
    def request(self, **meta):
        return RequestFactory().get('/', **meta)

    def test_uses_remote_addr_outside_vercel_and_ignores_forwarding_headers(self):
        request = self.request(
            REMOTE_ADDR='10.1.1.1',
            HTTP_X_FORWARDED_FOR='203.0.113.9',
            HTTP_X_VERCEL_FORWARDED_FOR='198.51.100.9',
        )
        with patch.dict('os.environ', {}, clear=False) as env:
            env.pop('VERCEL', None)
            self.assertEqual(get_client_ip(request), '10.1.1.1')

    def test_uses_vercel_header_on_vercel_and_takes_first_address(self):
        request = self.request(
            REMOTE_ADDR='10.1.1.1',
            HTTP_X_FORWARDED_FOR='203.0.113.9',
            HTTP_X_VERCEL_FORWARDED_FOR='198.51.100.9, 10.2.2.2',
        )
        with patch.dict('os.environ', {'VERCEL': '1'}):
            self.assertEqual(get_client_ip(request), '198.51.100.9')

    def test_falls_back_to_remote_addr_on_vercel_without_header(self):
        with patch.dict('os.environ', {'VERCEL': '1'}):
            self.assertEqual(get_client_ip(self.request(REMOTE_ADDR='10.1.1.1')), '10.1.1.1')


class ContactHoneypotTests(TestCase):
    data = {
        'name': 'Maria Souza',
        'email': 'maria@example.org',
        'whatsapp': '85999990000',
        'interest': 'visit',
        'message': 'Gostaria de visitar a igreja.',
    }

    def test_normal_submission_is_saved(self):
        response = self.client.post(reverse('home'), self.data)
        self.assertRedirects(response, reverse('contact_thanks'), fetch_redirect_response=False)
        self.assertEqual(ContactLead.objects.count(), 1)

    def test_filled_honeypot_is_discarded_silently(self):
        response = self.client.post(reverse('home'), {**self.data, 'website': 'http://spam.example'})
        self.assertRedirects(response, reverse('contact_thanks'), fetch_redirect_response=False)
        self.assertEqual(ContactLead.objects.count(), 0)

    def test_honeypot_field_is_rendered_but_hidden_from_layout(self):
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'name="website"')
        self.assertContains(response, 'hp-field')
