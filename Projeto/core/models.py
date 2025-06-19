from django.db import models
from django.contrib.auth.models import User, Permission
from django.core.exceptions import ValidationError
from datetime import time
from django.utils.translation import gettext_lazy as _

# Lista de postos do Exército Português (excluindo oficiais generais)
POSTOS_CHOICES = [
    ('Cor', 'Coronel'),
    ('TCor', 'Tenente-Coronel'),
    ('Maj', 'Major'),
    ('Cap', 'Capitão'),
    ('Ten', 'Tenente'),
    ('Alf', 'Alferes'),
    ('AspOf', 'Aspirante'),
    ('SCh', 'Sargento-Chefe'),
    ('SAj', 'Sargento-Ajudante'),
    ('1Sarg', 'Primeiro-Sargento'),
    ('2Sarg', 'Segundo-Sargento'),
    ('Furr', 'Furriel'),
    ('2Fur', '2ºFurriel'),
    ('CabSec', 'Cabo de Secção'),
    ('CAdj', 'Cabo-Ajunto'),
    ('1Cb', 'Primeiro-Cabo'),
    ('2Cb', 'Segundo-Cabo'),
    ('Sold', 'Soldado'),
]


# Modelos
class Role(models.Model):
    nome = models.CharField(max_length=100, unique=True)
    descricao = models.TextField(blank=True)
    permissions = models.ManyToManyField(Permission, blank=True)

    def __str__(self):
        return self.nome


class Militar(models.Model):
    # Campos Gerais
    nim = models.CharField(max_length=8, primary_key=True)
    # Liga ao user login
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    nome = models.CharField(max_length=100)
    posto = models.CharField(max_length=30, choices=POSTOS_CHOICES)
    funcao = models.CharField(max_length=50)
    e_administrador = models.BooleanField(default=False)
    telefone = models.BigIntegerField()
    email = models.EmailField()

    #Nomeacoes
    ultima_nomeacao_a = models.DateField(null=True, blank=True)
    ultima_nomeacao_b = models.DateField(null=True, blank=True)

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
        return ", ".join(
            [f"{d.data_inicio} a {d.data_fim}" for d in self.dispensas.all()]) or "Nenhuma dispensa atribuida."

    listar_dispensas.short_description = "Dispensas"

    def __str__(self):
        return f"{self.posto} {self.nome} ({self.nim})"

    def clean(self):
        super().clean()
        # Verifica se o NIM tem 8 digitos.
        if self.nim is not None:
            if not self.nim.isdigit() or len(self.nim) != 8:
                raise ValidationError({'nim': "O NIM deve ter exatamente 8 dígitos numéricos."})

        # Verifica se o numero de telefone tem 9 digitos.
        if self.telefone is not None:
            if not (100000000 <= self.telefone <= 999999999):
                raise ValidationError({'telefone': "O número de telefone deve conter exatamente 9 dígitos."})

    def esta_disponivel(self, data):
        """
        Verifica se o militar está disponível para serviço numa determinada data
        """
        from .services.escala_service import EscalaService
        disponivel, _ = EscalaService.verificar_disponibilidade_militar(self, data)
        return disponivel

    def obter_ultimo_servico(self, servico=None):
        """
        Devolve a última *data* em que o militar serviu.
        """
        qs = (
            Nomeacao.objects
            .filter(escala_militar__militar=self)
            .order_by('-data')
        )
        if servico:
            qs = qs.filter(escala_militar__escala__servico=servico)
        ultimo = qs.first()
        return ultimo.data if ultimo else None

    def calcular_folga(self, data_proposta, servico=None):
        """
        Calcula a folga em horas desde o último serviço, necessário para escalas
        """
        ultimo_servico = self.obter_ultimo_servico(servico)
        if not ultimo_servico:
            return float('inf')

        diferenca = data_proposta - ultimo_servico
        return diferenca.total_seconds() / 3600  # Converter para horas

    class Meta:
        verbose_name = "Militar"
        verbose_name_plural = "Militares"


class Dispensa(models.Model):
    id = models.AutoField(primary_key=True)
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
    # Precisamos disto?
    armamento = models.BooleanField(default=False, help_text="Se o serviço requer armamento")

    def clean(self):
        super().clean()

        if not self.pk:
            return

        escalas = self.escalas.all()

        # Check se escalas já estão presentes
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


class Escala(models.Model):
    id = models.AutoField(primary_key=True)
    servico = models.ForeignKey('Servico', on_delete=models.CASCADE, related_name='escalas')

    e_escala_b = models.BooleanField(default=False, verbose_name="Escala B")
    observacoes = models.TextField(blank=True, verbose_name="Observações")
    prevista = models.BooleanField(default=True, verbose_name="Prevista")

    class Meta:
        verbose_name = "Escala"
        verbose_name_plural = "Escalas"
        ordering = ['servico']

    def clean(self):
        super().clean()

        # "A" "B" ou "AB"
        tipo_srv = self.servico.tipo_escalas

        # Verificaçao
        if tipo_srv == "A" and self.e_escala_b:
            raise ValidationError(_("Este serviço só pode ter escalas do tipo A."))
        if tipo_srv == "B" and not self.e_escala_b:
            raise ValidationError(_("Este serviço só pode ter escalas do tipo B."))

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
        return f"Escala {tipo_escala} - {self.servico.nome}"


# Modelo complementar a escala, nao possui view propria
class EscalaMilitar(models.Model):
    escala = models.ForeignKey(Escala, on_delete=models.CASCADE, related_name='roster')
    militar = models.ForeignKey('Militar', on_delete=models.CASCADE)
    ordem = models.IntegerField(null=True, blank=True, verbose_name="Ordem")
    ativo = models.BooleanField(default=True, verbose_name="Ativo", help_text="Desmarque para desativar este militar desta escala específica.")

    class Meta:
        unique_together = ('escala', 'militar')
        verbose_name = _("Militar na Escala")
        verbose_name_plural = _("Militares na Escala")

    def clean(self):
        super().clean()

        if self.ordem is None:
            tipo = "B" if self.escala.e_escala_b else "A"
            raise ValidationError(
                {"ordem": _(f"Campo obrigatório.")}
            )

    def __str__(self):
        return ''


# Nomeação diária: indica que um militar (via EscalaMilitar) cobre a data X, como efetivo ou reserva.
class Nomeacao(models.Model):
    escala_militar = models.ForeignKey(
        EscalaMilitar,
        on_delete=models.CASCADE,
        related_name='nomeacoes'
    )
    data = models.DateField()
    e_reserva = models.BooleanField(default=False, verbose_name="É Reserva")
    observacoes = models.TextField(blank=True, verbose_name="Observações")

    class Meta:
        unique_together = ('escala_militar', 'data')
        verbose_name = _("Nomeação")
        verbose_name_plural = _("Nomeações")
        ordering = ["data"]

    def __str__(self):
        tipo = "Reserva" if self.e_reserva else "Efetivo"
        return f"{self.escala_militar.militar} em {self.data:%d/%m/%Y} ({tipo})"

# Registos
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


class ConfiguracaoUnidade(models.Model):
    nome_unidade = models.CharField("Nome da Unidade", max_length=200)
    nome_subunidade = models.CharField("Nome da Subunidade", max_length=200, blank=True, null=True)

    def __str__(self):
        if self.nome_subunidade:
            return f"{self.nome_unidade} - {self.nome_subunidade}"
        return self.nome_unidade

    class Meta:
        verbose_name = "Configuração da Unidade"
        verbose_name_plural = "Configuração da Unidade"

