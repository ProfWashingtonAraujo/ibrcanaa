from django.db import migrations, models


DEMO_URL = 'https://open.spotify.com/playlist/37i9dQZF1DX4sWSpwq3LiO'
SHOW_URL = 'https://open.spotify.com/show/7cIt85QzUPeO10vOLYDsAp?si=bd85139b74144700'


def forwards(apps, schema_editor):
    ChurchAboutPage = apps.get_model('core', 'ChurchAboutPage')
    ChurchAboutPage.objects.filter(spotify_playlist_url=DEMO_URL).update(
        spotify_playlist_title='Série em Atos dos Apóstolos - Episódio 23',
        spotify_playlist_text='Acompanhe esta série de mensagens e aprofunde seu estudo da Palavra de Deus.',
        spotify_playlist_url=SHOW_URL,
    )


def backwards(apps, schema_editor):
    ChurchAboutPage = apps.get_model('core', 'ChurchAboutPage')
    ChurchAboutPage.objects.filter(spotify_playlist_url=SHOW_URL).update(
        spotify_playlist_title='Música para momentos de reflexão',
        spotify_playlist_text='Uma seleção para acompanhar seus momentos de oração, leitura e descanso.',
        spotify_playlist_url=DEMO_URL,
    )


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0021_churchaboutpage_spotify_playlist'),
    ]

    operations = [
        migrations.AlterField(
            model_name='churchaboutpage',
            name='spotify_playlist_text',
            field=models.TextField(
                default='Acompanhe esta série de mensagens e aprofunde seu estudo da Palavra de Deus.',
                verbose_name='apresentação do conteúdo',
            ),
        ),
        migrations.AlterField(
            model_name='churchaboutpage',
            name='spotify_playlist_title',
            field=models.CharField(
                default='Série em Atos dos Apóstolos - Episódio 23',
                max_length=120,
                verbose_name='título no Spotify',
            ),
        ),
        migrations.AlterField(
            model_name='churchaboutpage',
            name='spotify_playlist_url',
            field=models.URLField(
                blank=True,
                default=SHOW_URL,
                verbose_name='URL da playlist ou programa no Spotify',
            ),
        ),
        migrations.RunPython(forwards, backwards),
    ]
