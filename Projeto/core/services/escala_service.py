from datetime import date, timedelta
from typing import Tuple, List, Dict
from django.utils import timezone
from collections import defaultdict
from django.db.models import Count

from ..models import Escala, Militar, Servico, Feriado, EscalaMilitar, Dispensa, Nomeacao
from ..utils import obter_feriados


class EscalaService:
    """Serviço para gerir escalas e nomeações militares."""

    @staticmethod
    def verificar_periodo(
            data_inicio: date, data_fim: date) -> Tuple[bool, str]:
        """Verifica se o período para nomeações é válido."""
        hoje = timezone.now().date()

        if data_inicio > data_fim:
            return False, "A data inicial não pode ser posterior à data final"

        if data_inicio < hoje:
            return False, "A data inicial não pode ser no passado"

        dias_intervalo = (data_fim - data_inicio).days
        if dias_intervalo > 60:
            return False, "O intervalo máximo para nomeações é de 60 dias"

        return True, "Período válido"

    @staticmethod
    def obter_dias_escala(
            data_inicio: date, data_fim: date) -> Dict[str, List[date]]:
        """Obtém as datas separadas por tipo de escala (dias úteis e fins de semana/feriados)."""
        dias = {
            'escala_a': [],
            'escala_b': []
        }

        # Verifica se o período é válido
        valido, mensagem = EscalaService.verificar_periodo(
            data_inicio, data_fim)
        if not valido:
            return dias

        # Obter todos os feriados usando a função unificada
        feriados = obter_feriados(data_inicio, data_fim)

        data_atual = data_inicio
        while data_atual <= data_fim:
            e_fds = data_atual.weekday() >= 5
            e_feriado = data_atual in feriados

            if e_fds or e_feriado:
                dias['escala_b'].append(data_atual)
            else:
                dias['escala_a'].append(data_atual)

            data_atual += timedelta(days=1)

        return dias

    @staticmethod
    def militar_em_dispensa(militar: Militar, data: date) -> bool:
        """Verifica se um militar está em período de dispensa numa data específica."""
        return Dispensa.objects.filter(
            militar=militar,
            data_inicio__lte=data,
            data_fim__gte=data).exists()

    @staticmethod
    def militar_ja_nomeado(militar: Militar, data: date) -> bool:
        """Verifica se um militar já foi nomeado para uma escala numa data específica."""
        return Nomeacao.objects.filter(
            escala_militar__militar=militar,
            data=data
        ).exists()

    @staticmethod
    def militar_licenca_antes(militar: Militar, data: date) -> bool:
        """Verifica se a dispensa de um militar terminou no dia anterior à data fornecida."""
        return Dispensa.objects.filter(
            militar=militar,
            data_fim=data -
            timedelta(
                days=1)).exists()

    @staticmethod
    def militar_licenca_depois(militar: Militar, data: date) -> bool:
        """Verifica se um militar inicia uma dispensa no dia seguinte à data fornecida."""
        return Dispensa.objects.filter(
            militar=militar,
            data_inicio=data +
            timedelta(
                days=1)).exists()

    @staticmethod
    def verificar_conflito_nomeacao(militar: Militar, data: date) -> bool:
        """
        Verifica se existe conflito de nomeação para o militar na data especificada.
        Impede nomeações em dias consecutivos, independentemente do tipo de escala (A ou B).
        Ou seja, se o militar for nomeado no dia anterior ou seguinte, não pode ser nomeado neste dia.
        """
        data_anterior = data - timedelta(days=1)
        data_posterior = data + timedelta(days=1)
        # Verifica nomeações como efetivo ou reserva, em qualquer escala
        return Nomeacao.objects.filter(
            escala_militar__militar=militar,
            data__in=[data_anterior, data_posterior]
        ).exists()

    @staticmethod
    def verificar_disponibilidade_militar(
            militar: Militar, data: date) -> Tuple[bool, str]:
        if EscalaService.militar_em_dispensa(militar, data):
            return False, "Militar em dispensa"
        if EscalaService.militar_ja_nomeado(militar, data):
            return False, "Militar já tem escala neste dia"
        if EscalaService.militar_licenca_depois(militar, data):
            return False, "Militar entra de licença no dia seguinte"
        if EscalaService.militar_licenca_antes(militar, data):
            return False, "Militar apresentou-se de licença no dia anterior"
        if EscalaService.verificar_conflito_nomeacao(militar, data):
            return False, "Militar tem escala no dia anterior ou seguinte"
        return True, "Militar disponível"

    @staticmethod
    def obter_militares_disponiveis(
            servico: Servico,
            data: date) -> List[Militar]:
        """Obtém uma lista de militares disponíveis para um serviço numa data específica."""
        # Obter todos os militares do serviço
        militares = servico.militares.all()

        # Filtrar apenas os disponíveis
        militares_disponiveis = [
            m for m in militares
            if EscalaService.verificar_disponibilidade_militar(m, data)[0]
        ]

        # Ordenar por folga (menor folga primeiro)
        militares_disponiveis.sort(
            key=lambda m: m.calcular_folga(data, servico)
        )

        return militares_disponiveis

    @staticmethod
    def criar_ou_obter_escala(servico: Servico, e_escala_b: bool) -> Escala:
        """Cria uma nova escala ou obtém uma já existente para um serviço e tipo de escala."""
        escala, _ = Escala.objects.get_or_create(
            servico=servico, e_escala_b=e_escala_b)
        return escala

    @staticmethod
    def nomear_efetivo(escala, militar, dia):
        """Nomeia um militar como efetivo para uma escala num dia específico, se ainda não estiver nomeado."""
        if not Nomeacao.objects.filter(
            escala_militar__escala=escala,
            escala_militar__militar=militar,
            data=dia,
            e_reserva=False
        ).exists():
            escala_militar, _ = EscalaMilitar.objects.get_or_create(
                escala=escala,
                militar=militar,
                defaults={'ordem': 1}
            )
            Nomeacao.objects.create(
                escala_militar=escala_militar,
                data=dia,
                e_reserva=False
            )
            return True
        return False

    @staticmethod
    def nomear_reserva(escala, militar, dia):
        """Nomeia um militar como reserva para uma escala num dia específico, se ainda não estiver nomeado."""
        if not Nomeacao.objects.filter(
            escala_militar__escala=escala,
            escala_militar__militar=militar,
            data=dia,
            e_reserva=True
        ).exists():
            escala_militar, _ = EscalaMilitar.objects.get_or_create(
                escala=escala,
                militar=militar,
                defaults={'ordem': 2}
            )
            Nomeacao.objects.create(
                escala_militar=escala_militar,
                data=dia,
                e_reserva=True
            )
            return True
        return False

    @staticmethod
    def verificar_disponibilidade_reserva(
            militar: Militar, data: date, e_escala_b: bool) -> Tuple[bool, str]:
        """
        Verifica se um militar pode ser nomeado como reserva em uma data específica.
        Considera dispensa, nomeações como efetivo em outras escalas e o dia após dispensa.
        """
        # Verificar se está em dispensa
        if EscalaService.militar_em_dispensa(militar, data):
            return False, "Militar em dispensa"

        # Verificar se é o primeiro dia após uma dispensa
        dia_anterior = data - timedelta(days=1)
        if Dispensa.objects.filter(
            militar=militar,
            data_fim=dia_anterior
        ).exists():
            return False, "Militar apresentou-se de dispensa no dia anterior"

        # Verificar se já está nomeado como efetivo ou reserva neste dia
        if EscalaService.militar_ja_nomeado(militar, data):
            return False, "Militar já tem escala neste dia"

        # Verificar se está nomeado como efetivo em outra escala no dia seguinte
        dia_seguinte = data + timedelta(days=1)
        nomeacao_seguinte = Nomeacao.objects.filter(
            escala_militar__militar=militar,
            data=dia_seguinte,
            e_reserva=False
        ).first()

        if nomeacao_seguinte:
            # Se a nomeação seguinte for de uma escala diferente
            if nomeacao_seguinte.escala_militar.escala.e_escala_b != e_escala_b:
                return False, "Militar é efetivo de outra escala no dia seguinte"

        return True, "Militar disponível para reserva"

    @staticmethod
    def encontrar_proximo_efetivo_valido(dia_atual: date,
                                         efetivos_dict: dict,
                                         dias_escala: list,
                                         e_escala_b: bool) -> Tuple[Militar,
                                                                    date]:
        """
        Encontra o próximo efetivo disponível para ser reserva após o dia atual.
        Retorna uma tupla com o militar e a data em que ele é efetivo.
        """
        dias_ordenados = sorted(dias_escala)
        idx_atual = dias_ordenados.index(dia_atual)

        # Procura nos próximos dias
        for dia_futuro in dias_ordenados[idx_atual + 1:]:
            if dia_futuro in efetivos_dict:
                # Pega o primeiro militar disponível da lista de efetivos
                for militar in efetivos_dict[dia_futuro]:
                    # Verificar se o militar pode ser reserva
                    disponivel, _ = EscalaService.verificar_disponibilidade_reserva(
                        militar, dia_atual, e_escala_b)
                    if disponivel:
                        return militar, dia_futuro
        return None, None

    @staticmethod
    def gerar_alerta_escassez_militares(servico: Servico, data_inicio: date, data_fim: date, minimo: int = 4):
        """
        Verifica se há escassez de militares e retorna uma lista de períodos problemáticos.
        Um período é uma sequência de um ou mais dias consecutivos.
        """
        militares_servico = servico.militares.all()
        total_militares = militares_servico.count()

        dispensas_por_dia = defaultdict(set)
        dispensas_periodo = Dispensa.objects.filter(
            militar__in=militares_servico,
            data_inicio__lte=data_fim,
            data_fim__gte=data_inicio
        )
        for dispensa in dispensas_periodo:
            d_atual = max(dispensa.data_inicio, data_inicio)
            d_fim_periodo = min(dispensa.data_fim, data_fim)
            while d_atual <= d_fim_periodo:
                dispensas_por_dia[d_atual].add(dispensa.militar_id)
                d_atual += timedelta(days=1)

        dias_problematicos = []
        current_day = data_inicio
        while current_day <= data_fim:
            num_em_dispensa = len(dispensas_por_dia.get(current_day, set()))
            if total_militares - num_em_dispensa < minimo:
                dias_problematicos.append(current_day)
            current_day += timedelta(days=1)

        if not dias_problematicos:
            return None

        # Agrupar dias consecutivos em períodos
        periodos = []
        if dias_problematicos:
            start_periodo = dias_problematicos[0]
            for i in range(1, len(dias_problematicos)):
                if dias_problematicos[i] != dias_problematicos[i-1] + timedelta(days=1):
                    periodos.append({'inicio': start_periodo, 'fim': dias_problematicos[i-1]})
                    start_periodo = dias_problematicos[i]
            periodos.append({'inicio': start_periodo, 'fim': dias_problematicos[-1]})
        
        return periodos

    @staticmethod
    def _inicializar_geracao(servico, data_inicio, data_fim):
        """Valida as datas, limpa nomeações existentes e retorna os dados iniciais."""
        hoje = timezone.now().date()
        if data_inicio <= hoje:
            raise ValueError("Só é possível gerar previsões para datas futuras.")

        Nomeacao.objects.filter(
            escala_militar__escala__servico=servico,
            data__gte=data_inicio,
            data__lte=data_fim
        ).delete()

        dias_escala = EscalaService.obter_dias_escala(data_inicio, data_fim)
        militares = list(servico.militares.all())
        militares_dict = {m.nim: m for m in militares}
        return dias_escala, militares, militares_dict

    @staticmethod
    def _atualizar_ultimas_nomeacoes(militares, data_inicio):
        """Atualiza e retorna as últimas datas de nomeação para cada militar."""
        for militar in militares:
            ultima_a = Nomeacao.objects.filter(
                escala_militar__militar=militar, data__lt=data_inicio, e_reserva=False
            ).order_by('-data').first()
            ultima_b = Nomeacao.objects.filter(
                escala_militar__militar=militar, data__lt=data_inicio, e_reserva=False
            ).order_by('-data').first()
            militar.ultima_nomeacao_a = ultima_a.data if ultima_a else None
            militar.ultima_nomeacao_b = ultima_b.data if ultima_b else None
            militar.save()

        ultima_nomeacao_a = {m.nim: m.ultima_nomeacao_a for m in militares}
        ultima_nomeacao_b = {m.nim: m.ultima_nomeacao_b for m in militares}
        return ultima_nomeacao_a, ultima_nomeacao_b

    @staticmethod
    def _processar_efetivos_para_escala(servico, dias_para_processar, ultima_nomeacao_dict, e_escala_b, militares_dict):
        """Processa e nomeia os efetivos para um tipo de escala (A ou B)."""
        efetivos_por_dia = defaultdict(list)
        escala = EscalaService.criar_ou_obter_escala(servico, e_escala_b=e_escala_b)
        
        dias_ordenados = sorted(dias_para_processar)
        
        for dia in dias_ordenados:
            def get_ordem(nim):
                militar = militares_dict[nim]
                try:
                    escala_militar = EscalaMilitar.objects.get(escala=escala, militar=militar)
                    return escala_militar.ordem if escala_militar.ordem is not None else 9999
                except EscalaMilitar.DoesNotExist:
                    return 9999

            rotacao_nim = sorted(
                [m.nim for m in militares_dict.values()],
                key=lambda nim: (ultima_nomeacao_dict.get(nim) or date.min, get_ordem(nim))
            )

            disponiveis_nim = [
                nim for nim in rotacao_nim if EscalaService.verificar_disponibilidade_militar(militares_dict[nim], dia)[0]
            ]

            for i in range(servico.n_elementos):
                if i < len(disponiveis_nim):
                    nim_efetivo = disponiveis_nim[i]
                    militar_efetivo = militares_dict[nim_efetivo]
                
                if EscalaService.nomear_efetivo(escala, militar_efetivo, dia):
                    ultima_nomeacao_dict[nim_efetivo] = dia
                    militar_efetivo.ultima_nomeacao_a = dia if not e_escala_b else militar_efetivo.ultima_nomeacao_a
                    militar_efetivo.ultima_nomeacao_b = dia if e_escala_b else militar_efetivo.ultima_nomeacao_b
                    militar_efetivo.save()
                    efetivos_por_dia[dia].append(militar_efetivo)

        return efetivos_por_dia

    @staticmethod
    def _processar_reservas_para_escala(servico, dias_para_processar, efetivos_por_dia, todos_dias_escala, e_escala_b):
        """Processa e nomeia os reservas para um tipo de escala (A ou B)."""
        escala = EscalaService.criar_ou_obter_escala(servico, e_escala_b=e_escala_b)
        
        for dia in sorted(dias_para_processar):
            reservas_nomeados = 0
            while reservas_nomeados < servico.n_reservas:
                dia_seguinte = dia + timedelta(days=1)
                militar_reserva = None

                # Tenta encontrar no dia seguinte imediato da mesma escala
                if dia_seguinte in efetivos_por_dia:
                    for militar in efetivos_por_dia[dia_seguinte]:
                        disponivel, _ = EscalaService.verificar_disponibilidade_reserva(militar, dia, e_escala_b)
                        if disponivel and not Nomeacao.objects.filter(escala_militar__escala=escala, escala_militar__militar=militar, data=dia, e_reserva=True).exists():
                            militar_reserva = militar
                            break

                # Se não encontrou, procura no próximo dia de escala válido
                if not militar_reserva:
                    militar_reserva, _ = EscalaService.encontrar_proximo_efetivo_valido(
                        dia, efetivos_por_dia, todos_dias_escala, e_escala_b
                    )

                if militar_reserva and EscalaService.nomear_reserva(escala, militar_reserva, dia):
                    reservas_nomeados += 1
                else:
                    break  # Não há mais militares para nomear como reserva ou ocorreu um erro

    @staticmethod
    def gerar_escalas_automaticamente(
            servico: Servico,
            data_inicio: date,
            data_fim: date) -> bool:
        """
        Gera escalas automaticamente para um serviço no período especificado.
        Esta função orquestra a chamada a sub-funções para inicialização,
        processamento de efetivos e de reservas para cada tipo de escala.
        """
        try:
            dias_escala, militares, militares_dict = EscalaService._inicializar_geracao(servico, data_inicio, data_fim)
            
            ultima_nomeacao_a, ultima_nomeacao_b = EscalaService._atualizar_ultimas_nomeacoes(militares, data_inicio)

            efetivos_por_dia_b = defaultdict(list)
            if servico.tipo_escalas in ("B", "AB"):
                efetivos_por_dia_b = EscalaService._processar_efetivos_para_escala(
                    servico, dias_escala['escala_b'], ultima_nomeacao_b, True, militares_dict
                )

            efetivos_por_dia_a = defaultdict(list)
            if servico.tipo_escalas in ("A", "AB"):
                efetivos_por_dia_a = EscalaService._processar_efetivos_para_escala(
                    servico, dias_escala['escala_a'], ultima_nomeacao_a, False, militares_dict
                )
            
            if servico.tipo_escalas in ("B", "AB") and servico.n_reservas > 0:
                EscalaService._processar_reservas_para_escala(
                    servico, dias_escala['escala_b'], efetivos_por_dia_b, dias_escala['escala_b'], True
                )

            if servico.tipo_escalas in ("A", "AB") and servico.n_reservas > 0:
                EscalaService._processar_reservas_para_escala(
                    servico, dias_escala['escala_a'], efetivos_por_dia_a, dias_escala['escala_a'], False
                )

            return True
        except (ValueError, Exception) as e:
            print(f"Erro ao gerar escalas: {str(e)}")
            return False
