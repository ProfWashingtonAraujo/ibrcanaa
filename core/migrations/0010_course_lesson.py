import core.models
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('core', '0009_membershipapplication_secure_link')]

    operations = [
        migrations.CreateModel(
            name='Course',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=160, verbose_name='título')),
                ('description', models.TextField(max_length=2000, verbose_name='descrição')),
                ('instructor', models.CharField(blank=True, max_length=120, verbose_name='instrutor')),
                ('cover_url', models.URLField(blank=True, help_text='Opcional. Use uma imagem horizontal.', verbose_name='URL da capa')),
                ('published', models.BooleanField(default=False, verbose_name='publicado para os membros')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='criado em')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='atualizado em')),
            ],
            options={'verbose_name': 'curso', 'verbose_name_plural': 'cursos', 'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='Lesson',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=160, verbose_name='título')),
                ('description', models.TextField(blank=True, max_length=2000, verbose_name='descrição')),
                ('youtube_url', models.URLField(validators=[core.models.validate_youtube_url], verbose_name='URL do vídeo no YouTube')),
                ('position', models.PositiveSmallIntegerField(default=1, verbose_name='ordem')),
                ('course', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lessons', to='core.course', verbose_name='curso')),
            ],
            options={'verbose_name': 'aula', 'verbose_name_plural': 'aulas', 'ordering': ['position', 'id']},
        ),
        migrations.AddConstraint(model_name='lesson', constraint=models.UniqueConstraint(fields=('course', 'position'), name='unique_course_lesson_position')),
    ]
