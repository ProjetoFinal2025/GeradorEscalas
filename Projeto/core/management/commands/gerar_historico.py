from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime, date, timedelta
import random
from ...models import Servico, Escala, EscalaMilitar, Militar, Feriado
from ...utils import obter_feriados

class Command(BaseCommand):
    help = 'Gera registos históricos artificiais de escalas para os últimos 2 meses'

    def handle(self, *args, **options):
        # Obter data atual e calcular data de início (2 meses atrás)
        hoje = timezone.now().date()
        data_inicio = hoje - timedelta(days=60)
        
        # Obter todos os serviços
        servicos = Servico.objects.all()
        if not servicos.exists():
            self.stdout.write(self.style.ERROR('Não existem serviços.'))
            return

        # Obter todos os militares
        militares = list(Militar.objects.all())
        if not militares:
            self.stdout.write(self.style.ERROR('Não existem militares.'))
            return

        # Obter feriados no período
        feriados = obter_feriados(data_inicio, hoje)

        # Gerar escalas para cada dia
        data_atual = data_inicio
        while data_atual <= hoje:
            # Verificar se é fim de semana ou feriado
            e_fim_semana = data_atual.weekday() >= 5
            e_feriado = data_atual in feriados

            # Para cada serviço
            for servico in servicos:
                # Verificar se já existe escala para este dia e serviço
                if Escala.objects.filter(servico=servico, data=data_atual).exists():
                    continue

                # Criar escala
                escala = Escala.objects.create(
                    servico=servico,
                    data=data_atual,
                    e_escala_b=e_fim_semana or e_feriado,
                    observacoes='Registo histórico gerado automaticamente'
                )

                # Selecionar militares aleatórios para efetivo e reserva
                militares_disponiveis = random.sample(militares, min(2, len(militares)))
                
                # Criar nomeação para efetivo
                if militares_disponiveis:
                    EscalaMilitar.objects.create(
                        escala=escala,
                        militar=militares_disponiveis[0],
                        e_reserva=False
                    )

                # Criar nomeação para reserva
                if len(militares_disponiveis) > 1:
                    EscalaMilitar.objects.create(
                        escala=escala,
                        militar=militares_disponiveis[1],
                        e_reserva=True
                    )

            data_atual += timedelta(days=1)

        self.stdout.write(self.style.SUCCESS(f'Registos históricos gerados com sucesso de {data_inicio} até {hoje}')) 