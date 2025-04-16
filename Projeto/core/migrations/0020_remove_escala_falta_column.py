from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('core', '0019_remove_escala_falta_field'),
    ]

    operations = [
        migrations.RunSQL(
            'ALTER TABLE core_escala DROP COLUMN falta;',
            reverse_sql=None
        ),
    ] 