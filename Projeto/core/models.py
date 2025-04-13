from django.db import models
from django.contrib.auth.models import User, Permission
from django.core.exceptions import ValidationError
from datetime import time

# Lista de postos do Exército Português (excluindo oficiais generais)
POSTOS_CHOICES = [
    ('COR', 'Coronel'),
    ('TCOR', 'Tenente-Coronel'),
    ('MAJ', 'Major'),
    ('CAP', 'Capitão'),
    ('TEN', 'Tenente'),
    ('ALF', 'Alferes'),
    ('ASP', 'Aspirante'),
    ('SCH', 'Sargento-Chefe'),
    ('SAJ', 'Sargento-Ajudante'),
    ('1SARG', 'Primeiro-Sargento'),
    ('2SARG', 'Segundo-Sargento'),
    ('FUR', 'Furriel'),
    ('2FUR', '2ºFurriel'),    
    ('CABSEC', 'Cabo de Secção'),
    ('CADJ', 'Cabo-Ajunto'),
    ('1CAB', 'Primeiro-Cabo'),
    ('2CAB', 'Segundo-Cabo'),
    ('SOL', 'Soldado')
]

# Models
class Role(models.Model):
    nome = models.CharField(max_length=100, unique=True)
    descricao = models.TextField(blank=True)
    permissions = models.ManyToManyField(Permission, blank=True)

    def __str__(self):
        return self.nome


class Militar(models.Model):
    # Campos Gerais
    nim = models.IntegerField(primary_key=True)
    # Liga ao user login
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    nome = models.CharField(max_length=100)
    posto = models.CharField(max_length=10, choices=POSTOS_CHOICES)
    funcao= models.CharField(max_length=50)
    e_administrador = models.BooleanField(default=False)
    telefone = models.BigIntegerField()
    email = models.EmailField()

    # Campos em Relaçao a escalas
    ordem_semana = models.IntegerField()
    ordem_fds = models.IntegerField()

    # Retorna os serviços em que Militar está inscrito
    def listar_servicos(self):
        return ", ".join([s.nome for s in self.servicos.all()]) or "Nenhum Serviço atribuido."

    listar_servicos.short_description = "Serviços"

    # Retorna as escalas em que Militar está inscrito
    def listar_escalas(self):
        escalas = Escala.objects.filter(servico__militares=self)
        if not escalas.exists():
            return "Nenhuma escala atribuída."
        return ", ".join([str(e) for e in escalas])

    listar_escalas.short_description = "Escalas"

    def listar_dispensas(self):
        return ", ".join([f"{d.data_inicio} a {d.data_fim}" for d in self.dispensas.all()]) or "Nenhuma dispensa atribuida."

    listar_dispensas.short_description = "Dispensas"

    def __str__(self):
        return f"{self.posto} {self.nome} ({str(self.nim).zfill(8)})"


    def clean(self):
        super().clean()
        # Verifica se o NIM tem 8 digitos.
        if not (10000000 <= self.nim <= 99999999):
            raise ValidationError({'nim': "O NIM deve ter exatamente 8 dígitos."})

        # Verifica se o numero de telefone tem 9 digitos.
        if not (100000000 <= self.telefone <= 999999999):
            raise ValidationError({'telefone': "O número de telefone deve conter exatamente 9 dígitos."})


class Dispensa(models.Model):
    id = models.AutoField(primary_key = True)
    # Cria ligaçao entre Militar e Dispensa acedendo diretamente a PK de militar
    militar = models.ForeignKey(Militar, on_delete=models.CASCADE, related_name='dispensas')
    data_inicio = models.DateField()
    data_fim = models.DateField()
    motivo = models.TextField()

    def __str__(self):
        return f"Dispensa de {self.militar.nome} ({self.data_inicio} - {self.data_fim})"


class Feriado(models.Model):
    id = models.AutoField(primary_key=True)
    TIPO_CHOICES = [
        ('FIXO', 'Feriado Fixo'),
        ('MOVEL', 'Feriado Móvel'),
    ]

    nome = models.CharField(max_length=100)
    data = models.DateField()
    tipo = models.CharField(
        max_length=5,
        choices=TIPO_CHOICES,
        default='FIXO'
    )
    
    def __str__(self):
        return f"{self.nome} - {self.data.strftime('%d/%m/%Y')}"
    
    class Meta:
        verbose_name = "Feriado"
        verbose_name_plural = "Feriados"
        ordering = ['data']


class Servico(models.Model):
    id = models.AutoField(primary_key=True)
    nome = models.CharField(max_length=100)
    militares = models.ManyToManyField('Militar', related_name='servicos')
    ativo = models.BooleanField(default=True)
    hora_inicio = models.TimeField(default=time(8, 0), help_text="Hora de início do serviço")
    hora_fim = models.TimeField(default=time(17, 0), help_text="Hora de fim do serviço")
    n_elementos = models.IntegerField(default=1, help_text="Número de elementos necessários por escala")
    tem_escala_B = models.BooleanField(default=False, help_text="Se o serviço tem escala B")
    armamento = models.BooleanField(default=False, help_text="Se o serviço requer armamento")

    def __str__(self):
        return self.nome


class Configuracao(models.Model):
    DIA_SEMANA_CHOICES = [
        ('SEG', 'Segunda-feira'),
        ('DOM', 'Domingo'),
    ]

    id = models.AutoField(primary_key=True)
    inicio_semana = models.CharField(
        max_length=3,
        choices=DIA_SEMANA_CHOICES,
        default='SEG',
        help_text="Define se a semana começa na Segunda-feira ou no Domingo"
    )

    def __str__(self):
        return f"Configuração {self.id} - Início: {self.get_inicio_semana_display()}"

    class Meta:
        verbose_name = "Configuração"
        verbose_name_plural = "Configurações"


class Escala(models.Model):
    id = models.AutoField(primary_key=True)
    servico = models.ForeignKey('Servico', on_delete=models.CASCADE, related_name='escalas')
    comentario = models.TextField(blank=True)
    data = models.DateField()
    e_escala_b = models.BooleanField(default=False)

    def __str__(self):
        if self.e_escala_b:
            return f"Escala B [{self.id}] - Serviço {self.servico.nome}"
        return f"Escala A [{self.id}] - Serviço {self.servico.nome}"

class Log(models.Model):
    id = models.AutoField(primary_key=True)
    nim_admin = models.BigIntegerField(help_text="NIM do administrador que realizou a ação")
    acao = models.CharField(max_length=255, help_text="Descrição da ação realizada")
    modelo = models.CharField(max_length=50, help_text="Nome do modelo alterado", default='Sistema')
    tipo_acao = models.CharField(max_length=20, choices=[
        ('CREATE', 'Criar'),
        ('UPDATE', 'Atualizar'),
        ('DELETE', 'Remover'),
        ('LOGIN', 'Login'),
        ('LOGOUT', 'Logout')
    ], default='UPDATE')
    data = models.DateTimeField(auto_now_add=True, help_text="Data e hora da ação")

    class Meta:
        verbose_name = "Log"
        verbose_name_plural = "Logs"
        ordering = ['-data']  # Ordenar do mais recente para o mais antigo

    def __str__(self):
        return f"{self.data.strftime('%d/%m/%Y %H:%M:%S')} - {self.acao} (NIM: {str(self.nim_admin).zfill(8)})"

