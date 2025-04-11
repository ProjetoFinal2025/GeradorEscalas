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


    # Retorna os serviços em que Militar está inscrito
    def listar_servicos(self):
        return ", ".join([s.nome for s in self.servicos.all()])

    listar_servicos.short_description = "Serviços"

    # Retorna as escalas em que Militar está inscrito
    def listar_escalas(self):
        escalas = Escala.objects.filter(servico__militares=self)
        if not escalas.exists():
            return "Nenhuma escala atribuída"
        return ", ".join([str(e) for e in escalas])

    listar_escalas.short_description = "Escalas"

    def listar_dispensas(self):
        return ", ".join([f"{d.data_inicio} a {d.data_fim}" for d in self.dispensas.all()]) or "-"

    listar_dispensas.short_description = "Dispensas"

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

    militares = models.ManyToManyField(
        'Militar',
        blank=True,
        related_name='servicos'
    )

    ativo = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.nome} ({self.n_elementos_dia} elementos/dia)"


class Escala(models.Model):
    id = models.AutoField(primary_key=True)
    servico = models.ForeignKey('Servico', on_delete=models.CASCADE, related_name='escalas')
    comentario = models.TextField(blank=True)
    data = models.DateField()
    configuracao = models.ForeignKey('Configuracao', on_delete=models.PROTECT)
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

