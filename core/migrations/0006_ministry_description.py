from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0005_biblefavorite_biblenote'),
    ]

    operations = [
        migrations.AddField(
            model_name='ministry',
            name='description',
            field=models.TextField(blank=True, max_length=500, verbose_name='descrição pública'),
        ),
    ]
