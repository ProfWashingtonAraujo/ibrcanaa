from django.db import migrations, models


def copy_ministry_to_ministries(apps, schema_editor):
    Member = apps.get_model('core', 'Member')
    for member in Member.objects.exclude(legacy_ministry_id=None).iterator():
        member.ministries.add(member.legacy_ministry_id)


def copy_ministries_to_ministry(apps, schema_editor):
    Member = apps.get_model('core', 'Member')
    for member in Member.objects.prefetch_related('ministries').iterator():
        ministry = member.ministries.first()
        if ministry:
            member.legacy_ministry_id = ministry.pk
            member.save(update_fields=['legacy_ministry'])


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0006_ministry_description'),
    ]

    operations = [
        migrations.RenameField(
            model_name='member',
            old_name='ministry',
            new_name='legacy_ministry',
        ),
        migrations.AddField(
            model_name='member',
            name='ministries',
            field=models.ManyToManyField(blank=True, related_name='members', to='core.ministry', verbose_name='ministérios'),
        ),
        migrations.RunPython(copy_ministry_to_ministries, copy_ministries_to_ministry),
        migrations.RemoveField(
            model_name='member',
            name='legacy_ministry',
        ),
    ]
