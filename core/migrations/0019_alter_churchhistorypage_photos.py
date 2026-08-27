from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0018_churchhistorypage_photo_1_url_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='churchhistorypage',
            name='photo_1_url',
            field=models.ImageField(blank=True, upload_to='church/history/%Y/%m/', verbose_name='foto 1'),
        ),
        migrations.AlterField(
            model_name='churchhistorypage',
            name='photo_2_url',
            field=models.ImageField(blank=True, upload_to='church/history/%Y/%m/', verbose_name='foto 2'),
        ),
        migrations.AlterField(
            model_name='churchhistorypage',
            name='photo_3_url',
            field=models.ImageField(blank=True, upload_to='church/history/%Y/%m/', verbose_name='foto 3'),
        ),
    ]
