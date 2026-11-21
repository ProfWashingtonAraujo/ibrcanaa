from django.db import migrations, models


SHOW_URL = 'https://open.spotify.com/show/7cIt85QzUPeO10vOLYDsAp'
OLD_EPISODE_URL = 'https://open.spotify.com/episode/7jSvOSYGtfbP3XIiwrD1nY'
OLD_TITLE = 'Série em Lamentações - Episódio 3'
NEW_TITLE = 'Mensagens da Igreja Batista Regular Canaã'


def follow_show(apps, schema_editor):
    # Só troca páginas ainda com o episódio fixo da 0026; edições manuais ficam intactas.
    ChurchAboutPage = apps.get_model('core', 'ChurchAboutPage')
    ChurchAboutPage.objects.filter(
        spotify_playlist_title=OLD_TITLE, spotify_playlist_url=OLD_EPISODE_URL,
    ).update(spotify_playlist_title=NEW_TITLE, spotify_playlist_url=SHOW_URL)


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0027_no_default_pinned_video'),
    ]

    operations = [
        migrations.AlterField(
            model_name='churchaboutpage',
            name='spotify_playlist_title',
            field=models.CharField(default=NEW_TITLE, max_length=120, verbose_name='título no Spotify'),
        ),
        migrations.AlterField(
            model_name='churchaboutpage',
            name='spotify_playlist_url',
            field=models.URLField(blank=True, default=SHOW_URL, verbose_name='URL da playlist ou programa no Spotify'),
        ),
        migrations.RunPython(follow_show, migrations.RunPython.noop),
    ]
