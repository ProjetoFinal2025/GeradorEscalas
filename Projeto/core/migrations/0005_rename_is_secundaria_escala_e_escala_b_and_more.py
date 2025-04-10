# Generated by Django 5.2 on 2025-04-10 08:25

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_alter_configuracao_feriados'),
    ]

    operations = [
        migrations.RenameField(
            model_name='escala',
            old_name='is_secundaria',
            new_name='e_escala_b',
        ),
        migrations.RemoveField(
            model_name='servico',
            name='efetivo_necessario',
        ),
        migrations.RemoveField(
            model_name='servico',
            name='prioridade',
        ),
        migrations.AddField(
            model_name='log',
            name='modelo',
            field=models.CharField(default='Sistema', help_text='Nome do modelo alterado', max_length=50),
        ),
        migrations.AddField(
            model_name='log',
            name='tipo_acao',
            field=models.CharField(choices=[('CREATE', 'Criar'), ('UPDATE', 'Atualizar'), ('DELETE', 'Remover'), ('LOGIN', 'Login'), ('LOGOUT', 'Logout')], default='UPDATE', max_length=20),
        ),
        migrations.AddField(
            model_name='servico',
            name='ativo',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='servico',
            name='descricao',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='servico',
            name='n_elementos_dia',
            field=models.IntegerField(default=1, help_text='Número de militares necessários por dia'),
        ),
        migrations.AddField(
            model_name='servico',
            name='tem_escala_B',
            field=models.BooleanField(default=False, help_text='Indica se o serviço tem escala B'),
        ),
        migrations.AlterField(
            model_name='servico',
            name='nome',
            field=models.CharField(max_length=100, unique=True),
        ),
    ]
