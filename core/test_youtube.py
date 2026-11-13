from django.db import IntegrityError, transaction
from django.forms.models import model_to_dict
from django.test import TestCase

from core.forms import ChurchAboutPageForm
from core.models import ChurchAboutPage, YoutubeSnapshot


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
