import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('core', '0010_course_lesson'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(
            name='LessonProgress',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('completed_at', models.DateTimeField(auto_now_add=True, verbose_name='concluída em')),
                ('lesson', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='progress_records', to='core.lesson')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lesson_progress', to=settings.AUTH_USER_MODEL)),
            ],
            options={'verbose_name': 'progresso de aula', 'verbose_name_plural': 'progressos de aulas'},
        ),
        migrations.CreateModel(
            name='CourseEvaluation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('rating', models.PositiveSmallIntegerField(verbose_name='nota')),
                ('learning', models.TextField(max_length=2000, verbose_name='principal aprendizado')),
                ('feedback', models.TextField(blank=True, max_length=2000, verbose_name='comentários e sugestões')),
                ('certificate_id', models.UUIDField(default=uuid.uuid4, editable=False, unique=True, verbose_name='código do certificado')),
                ('completed_at', models.DateTimeField(auto_now_add=True, verbose_name='concluído em')),
                ('course', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='evaluations', to='core.course')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='course_evaluations', to=settings.AUTH_USER_MODEL)),
            ],
            options={'verbose_name': 'avaliação de curso', 'verbose_name_plural': 'avaliações de cursos', 'ordering': ['-completed_at']},
        ),
        migrations.AddConstraint(model_name='lessonprogress', constraint=models.UniqueConstraint(fields=('user', 'lesson'), name='unique_user_lesson_progress')),
        migrations.AddConstraint(model_name='courseevaluation', constraint=models.UniqueConstraint(fields=('user', 'course'), name='unique_user_course_evaluation')),
    ]
