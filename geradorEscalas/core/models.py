from django.db import models

# Models

class Militar(models.Model):
    nim = models.IntegerField(primary_key=True)
    nome = models.CharField(max_length=100)
    posto = models.CharField(max_length=50)
    funcao= models.CharField(max_length=50)
    ordem_semana = models.IntegerField()
    ordem_fds = models.IntegerField()
    telefone = models.BigIntegerField()
    e_administrador = models.BooleanField(default=False)
    email = models.EmailField()

    # Array com Ids de Escalas
    escalas = models.JSONField(default=list, blank=True)

    def __str__(self):
        return f"{self.posto}{self.nome} (str{self.nim}.zfill(8)"

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
    id = models.AutoField(primary_key=True)

    nome = models.CharField(max_length=100)
    local = models.CharField(max_length=100)
    efetivo_necessario = models.IntegerField()
    armamento_necessario = models.BooleanField(default=False)
    prioridade = models.BooleanField(default=False)

    lista_militares = models.JSONField(default=list, blank=True)

    def __str__(self):
        return f"{self.nome} - {self.local}"


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

    is_secundaria = models.BooleanField(default=False)

    def __str__(self):
        if self.is_secundaria:
            return f"Escala B [{self.id}] for Servico {self.servico.nome}"
        return f"Escala A [{self.id}] for Servico {self.servico.nome}"



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

