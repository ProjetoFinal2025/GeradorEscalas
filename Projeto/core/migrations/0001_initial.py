# Generated by Django 5.2 on 2025-04-12 23:37

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Configuracao',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('hora_inicio', models.TimeField()),
                ('hora_fim', models.TimeField()),
                ('feriados', models.JSONField(blank=True, default=list, help_text='Lista de datas dos feriados no formato YYYY-MM-DD')),
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
                ('modelo', models.CharField(default='Sistema', help_text='Nome do modelo alterado', max_length=50)),
                ('tipo_acao', models.CharField(choices=[('CREATE', 'Criar'), ('UPDATE', 'Atualizar'), ('DELETE', 'Remover'), ('LOGIN', 'Login'), ('LOGOUT', 'Logout')], default='UPDATE', max_length=20)),
                ('data', models.DateTimeField(auto_now_add=True, help_text='Data e hora da ação')),
            ],
            options={
                'verbose_name': 'Log',
                'verbose_name_plural': 'Logs',
                'ordering': ['-data'],
            },
        ),
        migrations.CreateModel(
            name='Militar',
            fields=[
                ('nim', models.IntegerField(primary_key=True, serialize=False)),
                ('nome', models.CharField(max_length=100)),
                ('posto', models.CharField(max_length=50)),
                ('funcao', models.CharField(max_length=50)),
                ('e_administrador', models.BooleanField(default=False)),
                ('telefone', models.BigIntegerField()),
                ('email', models.EmailField(max_length=254)),
                ('ordem_semana', models.IntegerField()),
                ('ordem_fds', models.IntegerField()),
                ('user', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='Dispensa',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('data_inicio', models.DateField()),
                ('data_fim', models.DateField()),
                ('motivo', models.TextField()),
                ('militar', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='dispensas', to='core.militar')),
            ],
        ),
        migrations.CreateModel(
            name='Role',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(max_length=100, unique=True)),
                ('descricao', models.TextField(blank=True)),
                ('permissions', models.ManyToManyField(blank=True, to='auth.permission')),
            ],
        ),
        migrations.CreateModel(
            name='Servico',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('nome', models.CharField(max_length=100, unique=True)),
                ('descricao', models.TextField(blank=True)),
                ('local', models.CharField(max_length=100)),
                ('armamento_necessario', models.BooleanField(default=False)),
                ('n_elementos_dia', models.IntegerField(default=1, help_text='Número de militares necessários por dia')),
                ('tem_escala_B', models.BooleanField(default=False, help_text='Indica se o serviço tem escala B')),
                ('ativo', models.BooleanField(default=True)),
                ('militares', models.ManyToManyField(blank=True, related_name='servicos', to='core.militar')),
            ],
        ),
        migrations.CreateModel(
            name='Escala',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('comentario', models.TextField(blank=True)),
                ('data', models.DateField()),
                ('e_escala_b', models.BooleanField(default=False)),
                ('configuracao', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='core.configuracao')),
                ('servico', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='escalas', to='core.servico')),
            ],
        ),
    ]
