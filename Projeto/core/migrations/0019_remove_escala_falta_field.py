from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('core', '0018_alter_escalamilitar_options'),
    ]

    operations = [
        migrations.RunSQL(
            'ALTER TABLE core_escala MODIFY COLUMN falta BOOLEAN DEFAULT FALSE;',
            reverse_sql=None
        ),
    ] 