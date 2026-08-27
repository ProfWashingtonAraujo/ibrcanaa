from django.db import migrations, models


NEW_HEADING = 'Uma história guiada pela fidelidade de Deus.'
NEW_INTRO = 'Conheça a origem, o crescimento e a missão que Deus tem sustentado na Canaã ao longo dos anos.'
OLD_HEADING = 'A caminhada da Canaã ao longo do tempo.'
OLD_INTRO = 'Uma linha do tempo para registrar a origem, o crescimento e a missão que continuam moldando a igreja até hoje.'


def forwards(apps, schema_editor):
    ChurchHistoryPage = apps.get_model('core', 'ChurchHistoryPage')
    ChurchHistoryPage.objects.filter(site_key='history').update(heading=NEW_HEADING, intro=NEW_INTRO)


def backwards(apps, schema_editor):
    ChurchHistoryPage = apps.get_model('core', 'ChurchHistoryPage')
    ChurchHistoryPage.objects.filter(site_key='history').update(heading=OLD_HEADING, intro=OLD_INTRO)


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0019_alter_churchhistorypage_photos'),
    ]

    operations = [
        migrations.AlterField(
            model_name='churchhistorypage',
            name='heading',
            field=models.CharField(default=NEW_HEADING, max_length=140, verbose_name='título'),
        ),
        migrations.AlterField(
            model_name='churchhistorypage',
            name='intro',
            field=models.TextField(default=NEW_INTRO, verbose_name='introdução'),
        ),
        migrations.RunPython(forwards, backwards),
    ]
