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
    feriados = models.JSONField(default=list, help_text="Lista de datas dos feriados no formato YYYY-MM-DD")
    tem_escala_B = models.BooleanField(default=False)
    n_elementos = models.IntegerField()
    n_dias = models.IntegerField()


class Servico(models.Model):
    id = models.AutoField(primary_key=True)

class Escala(models.Model):
    id = models.AutoField(primary_key=True)
    militar = models.ForeignKey(Militar, on_delete=models.CASCADE, related_name='escalas')
    nim_reserva = models.ForeignKey(Militar, on_delete=models.SET_NULL, null=True, blank=True, related_name='reservas')
    comentario = models.TextField(blank=True)
    data = models.DateField()
    configuracao = models.ForeignKey(Configuracao, on_delete=models.PROTECT)

    sequencia_semana = models.JSONField(default=list)  # ex: [123, 124]
    sequencia_fds = models.JSONField(default=list)  # ex: [128, 129]

    class Meta:
        ordering = ['data']

    def __str__(self):
        return f"Escala de {self.data}"

