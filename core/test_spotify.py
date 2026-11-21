import json
from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import SimpleTestCase, override_settings

from core import spotify

SHOW = '7cIt85QzUPeO10vOLYDsAp'


def page(entity):
    data = {'props': {'pageProps': {'state': {'data': {'entity': entity}}}}}
    return f'<html><script id="__NEXT_DATA__" type="application/json">{json.dumps(data)}</script></html>'.encode()


def episode_entity(**extra):
    return {
        'type': 'episode', 'id': 'EP1abc', 'title': ' Quando a Ira de Deus ',
        'relatedEntityUri': f'spotify:show:{SHOW}', 'releaseDate': {'isoString': '2026-11-18T11:00:00Z'}, **extra,
    }


def response(body):
    mock = MagicMock()
    mock.__enter__.return_value.read.return_value = body
    return mock


@override_settings(SPOTIFY_LATEST_EPISODE=True)
class LatestEpisodeTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    @patch('core.spotify.urlopen')
    def test_reads_latest_episode_and_caches_it(self, urlopen):
        urlopen.return_value = response(page(episode_entity()))
        expected = {'id': 'EP1abc', 'title': 'Quando a Ira de Deus', 'released': '2026-11-18T11:00:00Z'}
        self.assertEqual(spotify.latest_episode(SHOW), expected)
        self.assertEqual(spotify.latest_episode(SHOW), expected)
        self.assertEqual(urlopen.call_count, 1)

    @patch('core.spotify.urlopen', side_effect=OSError)
    def test_network_failure_returns_none_and_backs_off(self, urlopen):
        self.assertIsNone(spotify.latest_episode(SHOW))
        self.assertIsNone(spotify.latest_episode(SHOW))
        self.assertEqual(urlopen.call_count, 1)

    @patch('core.spotify.urlopen')
    def test_failure_keeps_last_good_episode(self, urlopen):
        urlopen.return_value = response(page(episode_entity()))
        spotify.latest_episode(SHOW)
        cache.delete(f'spotify:fresh:{SHOW}')
        urlopen.return_value = response(b'<html>mudou</html>')
        self.assertEqual(spotify.latest_episode(SHOW)['id'], 'EP1abc')

    @patch('core.spotify.urlopen')
    def test_rejects_entity_from_another_show_or_bad_id(self, urlopen):
        for entity in (
            episode_entity(relatedEntityUri='spotify:show:OUTRO'),
            episode_entity(id='<script>'),
            episode_entity(type='show'),
        ):
            cache.clear()
            urlopen.return_value = response(page(entity))
            self.assertIsNone(spotify.latest_episode(SHOW))

    def test_invalid_show_id_is_not_fetched(self):
        with patch('core.spotify.urlopen') as urlopen:
            self.assertIsNone(spotify.latest_episode('../x'))
        urlopen.assert_not_called()
