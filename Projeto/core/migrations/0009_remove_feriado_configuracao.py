from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('core', '0008_remove_configuracao_from_feriado'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='feriado',
            name='configuracao',
        ),
    ] 