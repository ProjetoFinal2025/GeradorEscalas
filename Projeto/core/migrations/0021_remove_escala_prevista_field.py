from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('core', '0020_remove_escala_falta_column'),
    ]

    operations = [
        migrations.RunSQL(
            'ALTER TABLE core_escala MODIFY COLUMN prevista BOOLEAN DEFAULT FALSE;',
            reverse_sql=None
        ),
        migrations.RunSQL(
            'ALTER TABLE core_escala DROP COLUMN prevista;',
            reverse_sql=None
        ),
    ] 