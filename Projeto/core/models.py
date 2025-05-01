from django.db import models
from django.contrib.auth.models import User, Permission
from django.core.exceptions import ValidationError
from datetime import time, date, timedelta
from django.utils.translation import gettext_lazy as _

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
    posto = models.CharField(max_length=30, choices=POSTOS_CHOICES)
    funcao= models.CharField(max_length=50)
    e_administrador = models.BooleanField(default=False)
    telefone = models.BigIntegerField()
    email = models.EmailField()


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
        if self.nim is not None:
            if not (10000000 <= self.nim <= 99999999):
                raise ValidationError({'nim': "O NIM deve ter exatamente 8 dígitos."})

        # Verifica se o numero de telefone tem 9 digitos.
        if self.telefone is not None:
            if not (100000000 <= self.telefone <= 999999999):
                raise ValidationError({'telefone': "O número de telefone deve conter exatamente 9 dígitos."})

    def esta_disponivel(self, data):
        """
        Verifica se o militar está disponível para serviço em uma determinada data
        """
        # Verifica se está de licença
        if self.licencas.filter(
            data_inicio__lte=data,
            data_fim__gte=data
        ).exists():
            return False

        # Verifica se está dispensado
        if self.dispensas.filter(
            data_inicio__lte=data,
            data_fim__gte=data
        ).exists():
            return False

        # Verifica dia útil antes da entrada de licença
        dia_anterior = data - timedelta(days=1)
        if self.licencas.filter(
            data_inicio=dia_anterior
        ).exists():
            return False

        # Verifica dia da apresentação de licença
        if self.licencas.filter(
            data_fim=data
        ).exists():
            return False

        return True

    def obter_ultimo_servico(self, servico=None):
        """
        Obtém a data do último serviço do militar
        """
        query = EscalaMilitar.objects.filter(
            militar=self,
            escala__data__lt=date.today()
        ).select_related('escala').order_by('-escala__data')

        if servico:
            query = query.filter(escala__servico=servico)

        ultimo_servico = query.first()
        return ultimo_servico.escala.data if ultimo_servico else None

    def calcular_folga(self, data_proposta, servico=None):
        """
        Calcula a folga em horas desde o último serviço
        """
        ultimo_servico = self.obter_ultimo_servico(servico)
        if not ultimo_servico:
            return float('inf')  # Nunca fez serviço, folga infinita

        diferenca = data_proposta - ultimo_servico
        return diferenca.total_seconds() / 3600  # Converter para horas

    class Meta:
        verbose_name = "Militar"
        verbose_name_plural = "Militares"


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
    ESCALA_OPTIONS = [
        ("A", "Só Escala A"),
        ("B", "Só Escala B"),
        ("AB", "Escala A e B"),
    ]

    id = models.AutoField(primary_key=True)
    nome = models.CharField(max_length=100)
    militares = models.ManyToManyField('Militar', related_name='servicos')
    ativo = models.BooleanField(default=True)
    hora_inicio = models.TimeField(default=time(8, 0), help_text="Hora de início do serviço")
    hora_fim = models.TimeField(default=time(17, 0), help_text="Hora de fim do serviço")
    n_elementos = models.IntegerField(default=1, help_text="Número de elementos efetivos necessários por escala")
    n_reservas = models.IntegerField(default=1, help_text="Número de elementos reserva necessários por escala")

    tipo_escalas = models.CharField(
        max_length=2,
        choices=ESCALA_OPTIONS,
        default="A",
        help_text="Que tipo de escalas compõem este serviço.",
    )

    armamento = models.BooleanField(default=False, help_text="Se o serviço requer armamento")

    def clean(self):
        super().clean()


        if not self.pk:
            return

        escalas = self.escalas.all()

        # Checks if Escalas already exists when changing Servico escala type
        if self.tipo_escalas == "A" and escalas.filter(e_escala_b=True).exists():
            raise ValidationError(
                _("Não pode mudar este serviço para 'Só Escala A' "
                  "enquanto existir uma Escala B associada. "
                  "Apague ou modifique essa escala primeiro.")
            )

        if self.tipo_escalas == "B" and escalas.filter(e_escala_b=False).exists():
            raise ValidationError(
                _("Não pode mudar este serviço para 'Só Escala B' "
                  "enquanto existir uma Escala A associada. "
                  "Apague ou modifique essa escala primeiro.")
            )

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
    e_escala_b = models.BooleanField(default=False, verbose_name="Escala B")
    observacoes = models.TextField(blank=True, verbose_name="Observações")
    prevista = models.BooleanField(default=True, verbose_name="Prevista")

    class Meta:
        verbose_name = "Escala"
        verbose_name_plural = "Escalas"
        ordering = ['data', 'servico']

    def clean(self):
        super().clean()

        # "A" "B" or "AB"
        tipo_srv = self.servico.tipo_escalas

        # checks that A/B matches the Serviço
        if tipo_srv == "A" and self.e_escala_b:
            raise ValidationError(_("Este serviço só pode ter escalas do tipo A."))
        if tipo_srv == "B" and not self.e_escala_b:
            raise ValidationError(_("Este serviço só pode ter escalas do tipo B."))

        # checks only one escala of that kind for this Serviço
        clash = (
            Escala.objects
            .filter(servico=self.servico, e_escala_b=self.e_escala_b)
            .exclude(pk=self.pk)
            .exists()
        )
        if clash:
            raise ValidationError(_("Já existe uma escala deste tipo para este serviço."))

    def __str__(self):
        tipo_escala = "B" if self.e_escala_b else "A"
        return f"Escala {tipo_escala} - {self.servico.nome} - {self.data.strftime('%d-%b-%y')}"


class EscalaMilitar(models.Model):
    escala = models.ForeignKey('Escala', on_delete=models.CASCADE, related_name='militares_info')
    militar = models.ForeignKey('Militar', on_delete=models.CASCADE)

    # Where each Militar fits in for this Escala
    ordem_semana = models.IntegerField(null=True, blank=True)
    ordem_fds = models.IntegerField(null=True, blank=True)

    e_reserva = models.BooleanField(default=False, verbose_name="É Reserva")

    class Meta:
        unique_together = ('escala', 'militar')
        verbose_name = "Militares Na Escala"
        verbose_name_plural = "Militares Na Escala"

    def __str__(self):
        # Return an empty string so the TabularInline won't show
        return ''


class Log(models.Model):
    id = models.AutoField(primary_key=True)
    nim_admin = models.BigIntegerField(help_text="NIM do administrador que realizou a ação")
    acao = models.CharField(max_length=255, help_text="Descrição da ação realizada")
    tipo_acao = models.CharField(max_length=20, choices=[
        ('CREATE', 'Criar'),
        ('UPDATE', 'Atualizar'),
        ('DELETE', 'Remover'),
        ('LOGIN', 'Login'),
        ('LOGOUT', 'Logout')
    ], default='UPDATE')
    modelo = models.CharField(max_length=50, help_text="Nome do modelo alterado", default='Sistema')
    data = models.DateTimeField(auto_now_add=True, help_text="Data e hora da ação")

    class Meta:
        verbose_name = "Log"
        verbose_name_plural = "Logs"
        ordering = ['-data']  # Ordenar do mais recente para o mais antigo

    def __str__(self):
        return f"{self.data.strftime('%d/%m/%Y %H:%M:%S')} - {self.acao} (NIM: {str(self.nim_admin).zfill(8)})"


class RegraNomeacao(models.Model):
    TIPO_FOLGA_CHOICES = [
        ('mesma_escala', 'Mesma Escala (A/B)'),
        ('entre_escalas', 'Entre Escalas (A/B)'),
    ]
    
    servico = models.ForeignKey('Servico', on_delete=models.CASCADE, related_name='regras_nomeacao')
    tipo_folga = models.CharField(max_length=20, choices=TIPO_FOLGA_CHOICES)
    horas_minimas = models.IntegerField(help_text="Número mínimo de horas de folga")
    prioridade_modernos = models.BooleanField(default=True, help_text="Prioridade para militares mais modernos")
    considerar_ultimo_servico = models.BooleanField(default=True, help_text="Considerar data do último serviço")
    permitir_trocas = models.BooleanField(default=True, help_text="Permitir trocas de serviço")
    
    class Meta:
        verbose_name = "Regra de Nomeação"
        verbose_name_plural = "Regras de Nomeação"
        unique_together = ('servico', 'tipo_folga')

    def __str__(self):
        return f"{self.servico.nome} - {self.get_tipo_folga_display()}"

