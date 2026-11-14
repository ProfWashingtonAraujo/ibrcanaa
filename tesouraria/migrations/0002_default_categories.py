from django.db import migrations

INCOME = [
    ('Dízimos', {'is_tithe': True}),
    ('Ofertas', {}),
    ('Ofertas especiais', {'is_special': True}),
]
EXPENSE = ['Água e luz', 'Manutenção', 'Missões', 'Ajuda social', 'Material', 'Outros']


def create_categories(apps, schema_editor):
    Category = apps.get_model('tesouraria', 'Category')
    for name, extra in INCOME:
        Category.objects.get_or_create(name=name, kind='income', defaults=extra)
    for name in EXPENSE:
        Category.objects.get_or_create(name=name, kind='expense')


class Migration(migrations.Migration):
    dependencies = [('tesouraria', '0001_initial')]
    operations = [migrations.RunPython(create_categories, migrations.RunPython.noop)]
