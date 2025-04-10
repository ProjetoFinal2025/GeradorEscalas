from django.db import models
from django.contrib.auth.models import User

# Models

class Militar(models.Model):
    # Campos Gerais
    nim = models.IntegerField(primary_key=True)
    # Liga ao user login
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    nome = models.CharField(max_length=100)
    posto = models.CharField(max_length=50)
    funcao= models.CharField(max_length=50)
    e_administrador = models.BooleanField(default=False)
    telefone = models.BigIntegerField()
    email = models.EmailField()

    # Campos em Relaçao a escalas
    ordem_semana = models.IntegerField()
    ordem_fds = models.IntegerField()
    # Array com Ids de Escalas
    escalas = models.JSONField(default=list, blank=True)

    def __str__(self):
        return f"{self.posto} {self.nome} ({str(self.nim).zfill(8)})"

class Dispensa(models.Model):
    id = models.AutoField(primary_key = True)
    # Cria ligaçao entre Militar e Dispensa acedendo diretamente a PK de militar
    militar = models.ForeignKey(Militar, on_delete=models.CASCADE, related_name='dispensas')
    data_inicio = models.DateField()
    data_fim = models.DateField()
    motivo = models.TextField()

    def __str__(self):
        return f"Dispensa de {self.militar.nome} ({self.data_inicio} - {self.data_fim})"


class Configuracao(models.Model):
    id = models.AutoField(primary_key=True)
    hora_inicio = models.TimeField()
    hora_fim = models.TimeField()
    feriados = models.JSONField(default=list,blank=True,help_text="Lista de datas dos feriados no formato YYYY-MM-DD")
    tem_escala_B = models.BooleanField(default=False)
    n_elementos = models.IntegerField()
    n_dias = models.IntegerField()


class Servico(models.Model):
    # Campos de identificação
    id = models.AutoField(primary_key=True)
    nome = models.CharField(max_length=100, unique=True)
    descricao = models.TextField(blank=True)
    local = models.CharField(max_length=100)
    armamento_necessario = models.BooleanField(default=False)

    # Campos para as escalas
    n_elementos_dia = models.IntegerField(default=1, help_text="Número de militares necessários por dia")
    tem_escala_B = models.BooleanField(default=False, help_text="Indica se o serviço tem escala B")
    lista_militares = models.JSONField(default=list, blank=True)
    ativo = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.nome} ({self.n_elementos_dia} elementos/dia)"


class Escala(models.Model):
    id = models.AutoField(primary_key=True)

    servico = models.ForeignKey(
        Servico,
        on_delete=models.CASCADE,
        related_name='escalas'
    )
    comentario = models.TextField(blank=True)
    data = models.DateField()

    configuracao = models.ForeignKey(
        Configuracao,
        on_delete=models.PROTECT
    )

    # Arrays de Nims
    sequencia_semana = models.JSONField(default=list, blank=True)
    sequencia_fds = models.JSONField(default=list, blank=True)
    e_escala_b = models.BooleanField(default=False)
    def __str__(self):
        if self.e_escala_b:
            return f"Escala B [{self.id}] for Servico {self.servico.nome}"
        return f"Escala A [{self.id}] for Servico {self.servico.nome}"

    # Retorna a lista de NIMS presentes no service a que a escala corresponde
    def get_militares_da_escala(self):
        return Militar.objects.filter(nim__in=self.servico.lista_militares)

    # TEMP? Retorna os nomes dos militares associados
    def nomes_militares(self):
        militares = self.get_militares_da_escala()
        if not militares.exists():
            return "Nenhum militar associado ao serviço desta Escala."
        return ", ".join([f"{m.posto} {m.nome} ({m.nim})" for m in militares])




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

