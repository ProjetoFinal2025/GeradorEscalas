from datetime import date, timedelta
from django.utils import timezone
from .models import Servico, Militar, Escala, EscalaMilitar, RegraNomeacao, Dispensa, Feriado

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

def obter_feriados(data_inicio=None, data_fim=None):
    """Retorna lista de feriados para o período especificado"""
    if data_inicio is None:
        data_inicio = date.today()
    if data_fim is None:
        data_fim = date(data_inicio.year, 12, 31)

    feriados = []
    anos = range(data_inicio.year, data_fim.year + 1)
    
    for ano in anos:
        # Adiciona feriados nacionais
        feriados_nacionais = [
            date(ano, 1, 1),   # Ano Novo
            date(ano, 4, 25),  # Dia da Liberdade
            date(ano, 5, 1),   # Dia do Trabalhador
            date(ano, 6, 10),  # Dia de Portugal
            date(ano, 8, 15),  # Assunção de Nossa Senhora
            date(ano, 10, 5),  # Implantação da República
            date(ano, 11, 1),  # Todos os Santos
            date(ano, 12, 1),  # Restauração da Independência
            date(ano, 12, 8),  # Imaculada Conceição
            date(ano, 12, 25), # Natal
        ]
        feriados.extend(feriados_nacionais)
        
        # Adiciona feriados móveis para 2024
        if ano == 2024:
            feriados.extend([
                date(2024, 2, 13),  # Carnaval
                date(2024, 3, 29),  # Sexta-feira Santa
                date(2024, 3, 31),  # Páscoa
                date(2024, 5, 30),  # Corpo de Deus
            ])
        elif ano == 2025:
            feriados.extend([
                date(2025, 3, 4),   # Carnaval
                date(2025, 4, 18),  # Sexta-feira Santa
                date(2025, 4, 20),  # Páscoa
                date(2025, 6, 19),  # Corpo de Deus
            ])
    
    # Adiciona feriados personalizados
    feriados_personalizados = Feriado.objects.filter(
        data__gte=data_inicio,
        data__lte=data_fim
    )
    feriados.extend([f.data for f in feriados_personalizados])
    
    # Filtra apenas os feriados dentro do período especificado
    feriados = [f for f in feriados if data_inicio <= f <= data_fim]
    
    return sorted(list(set(feriados)))  # Remove duplicatas e ordena 