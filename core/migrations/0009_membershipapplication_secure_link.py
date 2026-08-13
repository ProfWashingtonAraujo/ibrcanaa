import uuid

import core.models
from django.db import migrations, models
from django.utils import timezone


def set_unique_tokens(apps, schema_editor):
    MembershipApplication = apps.get_model('core', 'MembershipApplication')
    for application in MembershipApplication.objects.all().iterator():
        application.access_token = uuid.uuid4()
        application.save(update_fields=['access_token'])


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0008_membershipapplication'),
    ]

    operations = [
        migrations.AddField(
            model_name='membershipapplication',
            name='access_token',
            field=models.UUIDField(default=uuid.uuid4, editable=False, null=True),
        ),
        migrations.AddField(
            model_name='membershipapplication',
            name='consented_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='consentimento registrado em'),
        ),
        migrations.AddField(
            model_name='membershipapplication',
            name='link_expires_at',
            field=models.DateTimeField(default=core.models.membership_link_expiry, verbose_name='link válido até'),
        ),
        migrations.AddField(
            model_name='membershipapplication',
            name='link_revoked_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='link revogado em'),
        ),
        migrations.AddField(
            model_name='membershipapplication',
            name='submitted_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='enviado pelo candidato em'),
        ),
        migrations.RunPython(set_unique_tokens, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='membershipapplication',
            name='access_token',
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True, verbose_name='token de acesso'),
        ),
    ]
