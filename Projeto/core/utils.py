from datetime import date, timedelta
from django.utils import timezone
from .models import Servico, Militar, Escala, EscalaMilitar, RegraNomeacao, Dispensa

def gerar_escalas_automaticamente(servico, data_inicio, data_fim):
    """
    Gera escalas automaticamente para um serviço no período especificado
    """
    # Obter regras de nomeação
    regras = RegraNomeacao.objects.filter(servico=servico)
    regra_mesma_escala = regras.filter(tipo_folga='mesma_escala').first()
    regra_entre_escalas = regras.filter(tipo_folga='entre_escalas').first()

    # Obter militares do serviço ordenados por posto e antiguidade
    militares = servico.militares.all().order_by('posto', 'nim')

    # Gerar previsões para cada dia
    data_atual = data_inicio
    while data_atual <= data_fim:
        # Determinar se é escala A ou B
        e_fim_semana = data_atual.weekday() >= 5
        e_escala_b = e_fim_semana

        # Criar ou obter escala
        escala, created = Escala.objects.get_or_create(
            servico=servico,
            data=data_atual,
            e_escala_b=e_escala_b
        )

        # Encontrar militar disponível com maior folga
        militar_efetivo = None
        militar_reserva = None
        maior_folga = -1

        for militar in militares:
            # Verificar disponibilidade
            disponivel = True
            
            # Verificar dispensas
            if Dispensa.objects.filter(
                militar=militar,
                data_inicio__lte=data_atual,
                data_fim__gte=data_atual
            ).exists():
                disponivel = False
                continue

            # Calcular folga
            folga = militar.calcular_folga(data_atual, servico)
            
            # Verificar regras de folga
            if e_escala_b:
                if folga < regra_mesma_escala.horas_minimas:
                    disponivel = False
                    continue
            else:
                if folga < regra_entre_escalas.horas_minimas:
                    disponivel = False
                    continue

            if disponivel and folga > maior_folga:
                maior_folga = folga
                militar_efetivo = militar

        # Encontrar reserva (próximo disponível)
        if militar_efetivo:
            for militar in militares:
                if militar == militar_efetivo:
                    continue
                
                # Verificar disponibilidade
                disponivel = True
                
                # Verificar dispensas
                if Dispensa.objects.filter(
                    militar=militar,
                    data_inicio__lte=data_atual,
                    data_fim__gte=data_atual
                ).exists():
                    disponivel = False
                    continue

                # Calcular folga
                folga = militar.calcular_folga(data_atual, servico)
                
                # Verificar regras de folga
                if e_escala_b:
                    if folga < regra_mesma_escala.horas_minimas:
                        disponivel = False
                        continue
                else:
                    if folga < regra_entre_escalas.horas_minimas:
                        disponivel = False
                        continue

                if disponivel:
                    militar_reserva = militar
                    break

        # Atribuir militares à escala
        if militar_efetivo:
            escala.militar = militar_efetivo
            escala.militar_reserva = militar_reserva
            escala.save()

        data_atual += timedelta(days=1)

    return True 