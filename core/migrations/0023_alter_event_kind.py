from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0022_use_church_spotify_show'),
    ]

    operations = [
        migrations.AlterField(
            model_name='event',
            name='kind',
            field=models.CharField(
                choices=[
                    ('Culto', 'Culto'),
                    ('EBD', 'EBD'),
                    ('Conferência', 'Conferência'),
                    ('PG', 'PG'),
                ],
                max_length=60,
                verbose_name='classificação',
            ),
        ),
    ]
