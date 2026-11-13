import json
from io import BytesIO
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse

from django.db import IntegrityError, transaction
from django.forms.models import model_to_dict
from django.test import SimpleTestCase, TestCase

from core.forms import ChurchAboutPageForm
from core.models import ChurchAboutPage, YoutubeSnapshot
from core.youtube import YoutubeError, fetch_feed_entries, fetch_video_details

CHANNEL_ID = 'UCnJeIwpnusCcbJa9nAInb8Q'
FEED_XML = '''<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015" xmlns="http://www.w3.org/2005/Atom">
 <entry><id>yt:video:AAAAAAAAAAA</id><yt:videoId>AAAAAAAAAAA</yt:videoId>
  <title>Culto de Louvor - 08/11/2026</title><published>2026-11-09T11:44:52+00:00</published></entry>
 <entry><id>yt:video:BBBBBBBBBBB</id><yt:videoId>BBBBBBBBBBB</yt:videoId>
  <title>Escola Bíblica - 08/11/2026</title><published>2026-11-09T02:36:23+00:00</published></entry>
</feed>'''


def respond_with(mocked_urlopen, body):
    data = body.encode() if isinstance(body, str) else body
    mocked_urlopen.return_value.__enter__.return_value = BytesIO(data)


class FeaturedVideoFieldTests(TestCase):
    def form(self, **overrides):
        page = ChurchAboutPage.objects.create(site_key='about')
        data = model_to_dict(page)
        data.update(overrides)
        return ChurchAboutPageForm(data, instance=page)

    def test_defaults_point_to_the_podcast(self):
        page = ChurchAboutPage.objects.create(site_key='about')
        self.assertEqual(page.featured_video_id, 'i7tGR33yy-o')
        self.assertIn('PodcastCanaã#01', page.featured_video_title)

    def test_form_accepts_valid_youtube_url(self):
        form = self.form(featured_video_url='https://youtu.be/AAAAAAAAAAA')
        self.assertTrue(form.is_valid(), form.errors)

    def test_form_rejects_non_youtube_url(self):
        form = self.form(featured_video_url='https://example.com/video')
        self.assertFalse(form.is_valid())
        self.assertIn('featured_video_url', form.errors)

    def test_blank_url_is_allowed_and_has_no_video_id(self):
        form = self.form(featured_video_url='')
        self.assertTrue(form.is_valid(), form.errors)
        page = form.save()
        self.assertIsNone(page.featured_video_id)

    def test_snapshot_key_is_unique(self):
        YoutubeSnapshot.objects.create(key='channel')
        with self.assertRaises(IntegrityError), transaction.atomic():
            YoutubeSnapshot.objects.create(key='channel')


@patch('core.youtube.urlopen')
class FeedParsingTests(SimpleTestCase):
    def test_feed_entries_are_parsed_in_order(self, mocked_urlopen):
        respond_with(mocked_urlopen, FEED_XML)
        entries = fetch_feed_entries(CHANNEL_ID)
        self.assertEqual([entry['video_id'] for entry in entries], ['AAAAAAAAAAA', 'BBBBBBBBBBB'])
        self.assertEqual(entries[0]['title'], 'Culto de Louvor - 08/11/2026')
        self.assertEqual(entries[0]['published'], '2026-11-09T11:44:52+00:00')

    def test_feed_requests_the_channel_feed_url(self, mocked_urlopen):
        respond_with(mocked_urlopen, FEED_XML)
        fetch_feed_entries(CHANNEL_ID)
        request = mocked_urlopen.call_args.args[0]
        url = request.full_url if hasattr(request, 'full_url') else request
        self.assertEqual(url, f'https://www.youtube.com/feeds/videos.xml?channel_id={CHANNEL_ID}')
        self.assertEqual(mocked_urlopen.call_args.kwargs['timeout'], 2)

    def test_feed_rejects_malformed_xml(self, mocked_urlopen):
        respond_with(mocked_urlopen, '<feed><entry>')
        with self.assertRaises(YoutubeError):
            fetch_feed_entries(CHANNEL_ID)

    def test_feed_rejects_oversized_body(self, mocked_urlopen):
        respond_with(mocked_urlopen, b'<feed>' + b'x' * (1024 * 1024 + 10) + b'</feed>')
        with self.assertRaises(YoutubeError):
            fetch_feed_entries(CHANNEL_ID)

    def test_feed_network_error_becomes_youtube_error(self, mocked_urlopen):
        mocked_urlopen.side_effect = URLError('sem rede')
        with self.assertRaises(YoutubeError):
            fetch_feed_entries(CHANNEL_ID)


@patch('core.youtube.urlopen')
class VideoDetailsTests(SimpleTestCase):
    def test_details_flags_live_and_transmissions(self, mocked_urlopen):
        respond_with(mocked_urlopen, json.dumps({'items': [
            {'id': 'LIVE0000001', 'snippet': {'liveBroadcastContent': 'live'}, 'liveStreamingDetails': {}},
            {'id': 'ENDED000001', 'snippet': {'liveBroadcastContent': 'none'}, 'liveStreamingDetails': {}},
            {'id': 'UPLOAD00001', 'snippet': {'liveBroadcastContent': 'none'}},
            {'id': 'SOON0000001', 'snippet': {'liveBroadcastContent': 'upcoming'}, 'liveStreamingDetails': {}},
        ]}))
        details = fetch_video_details(['LIVE0000001', 'ENDED000001', 'UPLOAD00001', 'SOON0000001'], 'chave')
        self.assertEqual(details['LIVE0000001'], {'live': True, 'transmission': True})
        self.assertEqual(details['ENDED000001'], {'live': False, 'transmission': True})
        self.assertEqual(details['UPLOAD00001'], {'live': False, 'transmission': False})
        self.assertEqual(details['SOON0000001'], {'live': False, 'transmission': False})

    def test_details_request_asks_for_snippet_and_live_streaming_details(self, mocked_urlopen):
        respond_with(mocked_urlopen, json.dumps({'items': []}))
        fetch_video_details(['AAAAAAAAAAA', 'BBBBBBBBBBB'], 'chave')
        request = mocked_urlopen.call_args.args[0]
        url = request.full_url if hasattr(request, 'full_url') else request
        query = parse_qs(urlparse(url).query)
        self.assertEqual(urlparse(url).path, '/youtube/v3/videos')
        self.assertEqual(query['part'], ['snippet,liveStreamingDetails'])
        self.assertEqual(query['id'], ['AAAAAAAAAAA,BBBBBBBBBBB'])
        self.assertEqual(query['key'], ['chave'])

    def test_videos_missing_from_the_response_are_omitted(self, mocked_urlopen):
        respond_with(mocked_urlopen, json.dumps({'items': []}))
        self.assertEqual(fetch_video_details(['AAAAAAAAAAA'], 'chave'), {})

    def test_no_ids_means_no_request(self, mocked_urlopen):
        self.assertEqual(fetch_video_details([], 'chave'), {})
        mocked_urlopen.assert_not_called()

    def test_details_http_error_hides_the_api_key(self, mocked_urlopen):
        url = 'https://www.googleapis.com/youtube/v3/videos?key=SEGREDO123'
        mocked_urlopen.side_effect = HTTPError(url, 403, 'Forbidden', {}, None)
        with self.assertRaises(YoutubeError) as raised, self.assertNoLogs(level='DEBUG'):
            fetch_video_details(['AAAAAAAAAAA'], 'SEGREDO123')
        self.assertNotIn('SEGREDO123', str(raised.exception))
        self.assertIsNone(raised.exception.__cause__)
        self.assertTrue(raised.exception.__suppress_context__)

    def test_details_invalid_json_becomes_youtube_error(self, mocked_urlopen):
        respond_with(mocked_urlopen, 'não é json')
        with self.assertRaises(YoutubeError):
            fetch_video_details(['AAAAAAAAAAA'], 'chave')
