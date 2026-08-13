import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0007_member_ministries'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='MembershipApplication',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('candidate_name', models.CharField(max_length=160, verbose_name='nome do candidato')),
                ('candidate_email', models.EmailField(max_length=254, verbose_name='e-mail do candidato')),
                ('form_date', models.DateField(blank=True, null=True, verbose_name='data do formulário')),
                ('status', models.CharField(choices=[('draft', 'Rascunho'), ('review', 'Em avaliação pastoral'), ('completed', 'Concluído')], default='draft', max_length=20, verbose_name='situação')),
                ('responses', models.JSONField(blank=True, default=dict, verbose_name='respostas do candidato')),
                ('pastoral_review', models.JSONField(blank=True, default=dict, verbose_name='avaliação pastoral')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='criado em')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='atualizado em')),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='created_membership_applications', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'candidatura à membresia',
                'verbose_name_plural': 'candidaturas à membresia',
                'ordering': ['-updated_at'],
            },
        ),
    ]
