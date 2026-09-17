from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0020_alter_churchhistorypage_opening_text'),
    ]

    operations = [
        migrations.AddField(
            model_name='churchaboutpage',
            name='spotify_playlist_text',
            field=models.TextField(
                default='Uma seleção para acompanhar seus momentos de oração, leitura e descanso.',
                verbose_name='apresentação da playlist',
            ),
        ),
        migrations.AddField(
            model_name='churchaboutpage',
            name='spotify_playlist_title',
            field=models.CharField(
                default='Música para momentos de reflexão',
                max_length=120,
                verbose_name='título da playlist',
            ),
        ),
        migrations.AddField(
            model_name='churchaboutpage',
            name='spotify_playlist_url',
            field=models.URLField(
                blank=True,
                default='https://open.spotify.com/playlist/37i9dQZF1DX4sWSpwq3LiO',
                verbose_name='URL da playlist no Spotify',
            ),
        ),
    ]
