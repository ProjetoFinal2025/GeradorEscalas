# Generated by Django 5.2 on 2025-04-09 21:20

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_rename_nim_dispensa_militar'),
    ]

    operations = [
        migrations.CreateModel(
            name='Configuracao',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('hora_inicio', models.TimeField()),
                ('hora_fim', models.TimeField()),
                ('feriados', models.JSONField(default=list, help_text='Lista de datas dos feriados no formato YYYY-MM-DD')),
                ('tem_escala_B', models.BooleanField(default=False)),
                ('n_elementos', models.IntegerField()),
                ('n_dias', models.IntegerField()),
            ],
        ),
        migrations.CreateModel(
            name='Log',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('nim_admin', models.BigIntegerField(help_text='NIM do administrador que realizou a ação')),
                ('acao', models.CharField(help_text='Descrição da ação realizada', max_length=255)),
                ('data', models.DateTimeField(auto_now_add=True, help_text='Data e hora da ação')),
            ],
            options={
                'verbose_name': 'Log',
                'verbose_name_plural': 'Logs',
                'ordering': ['-data'],
            },
        ),
        migrations.CreateModel(
            name='Servico',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('nome', models.CharField(max_length=100)),
                ('local', models.CharField(max_length=100)),
                ('efetivo_necessario', models.IntegerField()),
                ('armamento_necessario', models.BooleanField(default=False)),
                ('prioridade', models.BooleanField(default=False)),
                ('lista_militares', models.JSONField(blank=True, default=list)),
            ],
        ),
        migrations.AddField(
            model_name='militar',
            name='escalas',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.CreateModel(
            name='Escala',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('comentario', models.TextField(blank=True)),
                ('data', models.DateField()),
                ('sequencia_semana', models.JSONField(blank=True, default=list)),
                ('sequencia_fds', models.JSONField(blank=True, default=list)),
                ('is_secundaria', models.BooleanField(default=False)),
                ('configuracao', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='core.configuracao')),
                ('servico', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='escalas', to='core.servico')),
            ],
        ),
    ]
