# Generated by Django 5.2 on 2025-04-13 10:45

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0009_remove_feriado_configuracao'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='configuracao',
            name='usar_feriados_nacionais',
        ),
        migrations.AlterField(
            model_name='feriado',
            name='id',
            field=models.AutoField(primary_key=True, serialize=False),
        ),
    ]
