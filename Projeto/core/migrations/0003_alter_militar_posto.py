# Generated by Django 5.2 on 2025-04-12 23:50

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_alter_militar_posto'),
    ]

    operations = [
        migrations.AlterField(
            model_name='militar',
            name='posto',
            field=models.CharField(choices=[('COR', 'Coronel'), ('TCOR', 'Tenente-Coronel'), ('MAJ', 'Major'), ('CAP', 'Capitão'), ('TEN', 'Tenente'), ('ALF', 'Alferes'), ('ASP', 'Aspirante'), ('SCH', 'Sargento-Chefe'), ('SAJ', 'Sargento-Ajudante'), ('1SARG', 'Primeiro-Sargento'), ('2SARG', 'Segundo-Sargento'), ('FUR', 'Furriel'), ('2FUR', '2ºFurriel'), ('CABSEC', 'Cabo de Secção'), ('CADJ', 'Cabo-Ajunto'), ('1CAB', 'Primeiro-Cabo'), ('2CAB', 'Segundo-Cabo'), ('SOL', 'Soldado')], max_length=30),
        ),
    ]
