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
    def verificar_periodo(data_inicio: date, data_fim: date) -> Tuple[bool, str]:
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
    def obter_dias_escala(data_inicio: date, data_fim: date) -> Dict[str, List[date]]:
        """Obtém as datas separadas por tipo de escala (dias úteis e fins de semana/feriados)."""
        dias = {
            'escala_a': [],
            'escala_b': []
        }

        # Verifica se o período é válido
        valido, mensagem = EscalaService.verificar_periodo(data_inicio, data_fim)
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
        return Dispensa.objects.filter(militar=militar, data_inicio__lte=data, data_fim__gte=data).exists()

    @staticmethod
    def militar_ja_nomeado(militar: Militar, data: date) -> bool:
        return Nomeacao.objects.filter(
            escala_militar__militar=militar,
            data=data
        ).exists()

    @staticmethod
    def militar_licenca_antes(militar: Militar, data: date) -> bool:
        return Dispensa.objects.filter(militar=militar, data_fim=data - timedelta(days=1)).exists()

    @staticmethod
    def militar_licenca_depois(militar: Militar, data: date) -> bool:
        return Dispensa.objects.filter(militar=militar, data_inicio=data + timedelta(days=1)).exists()

    @staticmethod
    def verificar_conflito_nomeacao(militar: Militar, data: date) -> bool:
        """
        Verifica se existe conflito de nomeação para o militar na data especificada.
        Considera nomeações no dia anterior e posterior.
        """
        data_anterior = data - timedelta(days=1)
        data_posterior = data + timedelta(days=1)
        
        return Nomeacao.objects.filter(
            escala_militar__militar=militar,
            data__in=[data_anterior, data_posterior]
        ).exists()

    @staticmethod
    def verificar_disponibilidade_militar(militar: Militar, data: date) -> Tuple[bool, str]:
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
    def obter_militares_disponiveis(servico: Servico, data: date) -> List[Militar]:
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
        escala, _ = Escala.objects.get_or_create(servico=servico, e_escala_b=e_escala_b)
        return escala

    @staticmethod
    def nomear_efetivo(escala, militar, dia):
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
    def verificar_disponibilidade_reserva(militar: Militar, data: date, e_escala_b: bool) -> Tuple[bool, str]:
        """
        Verifica se um militar pode ser nomeado como reserva em uma data específica.
        Considera dispensa e nomeações como efetivo em outras escalas.
        """
        # Verificar se está em dispensa
        if EscalaService.militar_em_dispensa(militar, data):
            return False, "Militar em dispensa"

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
    def encontrar_proximo_efetivo_valido(dia_atual: date, efetivos_dict: dict, dias_escala: list, e_escala_b: bool) -> Tuple[Militar, date]:
        """
        Encontra o próximo efetivo disponível para ser reserva após o dia atual.
        Retorna uma tupla com o militar e a data em que ele é efetivo.
        """
        dias_ordenados = sorted(dias_escala)
        idx_atual = dias_ordenados.index(dia_atual)
        
        # Procura nos próximos dias
        for dia_futuro in dias_ordenados[idx_atual+1:]:
            if dia_futuro in efetivos_dict:
                militar = efetivos_dict[dia_futuro]
                # Verificar se o militar pode ser reserva
                disponivel, _ = EscalaService.verificar_disponibilidade_reserva(militar, dia_atual, e_escala_b)
                if disponivel:
                    return militar, dia_futuro
        return None, None

    @staticmethod
    def gerar_escalas_automaticamente(servico: Servico, data_inicio: date, data_fim: date) -> bool:
        """
        Gera escalas automaticamente para um serviço no período especificado,
        mantendo em memória a última nomeação de cada militar para garantir rotação justa.
        Processa primeiro as escalas B (fins de semana e feriados) e depois as escalas A (dias úteis).
        Garante folga mínima de 1 dia entre escalas.
        O militar de reserva é o efetivo do dia seguinte da mesma escala (A ou B).
        Se não houver efetivo no dia seguinte, procura o próximo efetivo disponível.
        Um militar não pode ser reserva se:
        - Estiver em dispensa
        - Já estiver nomeado como efetivo ou reserva no mesmo dia
        - For efetivo de outra escala no dia seguinte
        """
        try:
            # Limpar os dados da previsão para o período pedido
            Nomeacao.objects.filter(
                escala_militar__escala__servico=servico,
                data__gte=data_inicio,
                data__lte=data_fim
            ).delete()
            
            dias_escala = EscalaService.obter_dias_escala(data_inicio, data_fim)
            militares = list(servico.militares.all())
            militares_dict = {m.nim: m for m in militares}
            
            # Limpar e recalculcar as datas de última nomeação a partir da data de início
            for militar in militares:
                # Obter a última nomeação antes da data de início
                ultima_nomeacao_a = Nomeacao.objects.filter(
                    escala_militar__militar=militar,
                    data__lt=data_inicio,
                    e_reserva=False
                ).order_by('-data').first()
                
                ultima_nomeacao_b = Nomeacao.objects.filter(
                    escala_militar__militar=militar,
                    data__lt=data_inicio,
                    e_reserva=False
                ).order_by('-data').first()
                
                # Atualizar as datas de última nomeação
                militar.ultima_nomeacao_a = ultima_nomeacao_a.data if ultima_nomeacao_a else None
                militar.ultima_nomeacao_b = ultima_nomeacao_b.data if ultima_nomeacao_b else None
                militar.save()
            
            # Inicializar dicionários de última nomeação com os valores atualizados
            ultima_nomeacao_a = {m.nim: m.ultima_nomeacao_a for m in militares}
            ultima_nomeacao_b = {m.nim: m.ultima_nomeacao_b for m in militares}

            # Dicionários para armazenar os efetivos de cada dia por tipo de escala
            efetivos_por_dia_a = {}
            efetivos_por_dia_b = {}

            # Processar primeiro as escalas B (fins de semana e feriados)
            for dia in dias_escala['escala_b']:
                print(f"\n[DEBUG] Dia: {dia} | Tipo: B")
                # Ordenar por última nomeação B
                rotacao_nim = sorted([m.nim for m in militares], key=lambda nim: (ultima_nomeacao_b[nim] or date.min, nim))
                # Filtrar indisponíveis no próprio dia, mas manter ordem da rotação
                disponiveis_nim = [nim for nim in rotacao_nim if EscalaService.verificar_disponibilidade_militar(militares_dict[nim], dia)[0]]
                print("Ordem dos disponíveis para o dia:")
                for nim in disponiveis_nim:
                    print(f"  Militar: {nim} | Última nomeação B: {ultima_nomeacao_b[nim]}")
                n_efetivos = servico.n_elementos
                n_reservas = servico.n_reservas
                escala = EscalaService.criar_ou_obter_escala(servico, e_escala_b=True)
                # Nomear efetivo
                if disponiveis_nim:
                    nim_efetivo = disponiveis_nim[0]
                    militar_efetivo = militares_dict[nim_efetivo]
                    if EscalaService.nomear_efetivo(escala, militar_efetivo, dia):
                        ultima_nomeacao_b[nim_efetivo] = dia
                        militar_efetivo.ultima_nomeacao_b = dia
                        militar_efetivo.save()
                        print(f"[DEBUG] Militar nomeado EFETIVO: {nim_efetivo} | Nova última nomeação B: {dia}")
                        # Mover o efetivo para o fim da rotação
                        rotacao_nim.append(rotacao_nim.pop(rotacao_nim.index(nim_efetivo)))
                        # Guardar o efetivo para possível uso como reserva no dia anterior
                        efetivos_por_dia_b[dia] = militar_efetivo

            # Depois processar as escalas A (dias úteis)
            for dia in dias_escala['escala_a']:
                print(f"\n[DEBUG] Dia: {dia} | Tipo: A")
                # Ordenar por última nomeação A
                rotacao_nim = sorted([m.nim for m in militares], key=lambda nim: (ultima_nomeacao_a[nim] or date.min, nim))
                # Filtrar indisponíveis no próprio dia, mas manter ordem da rotação
                disponiveis_nim = [nim for nim in rotacao_nim if EscalaService.verificar_disponibilidade_militar(militares_dict[nim], dia)[0]]
                print("Ordem dos disponíveis para o dia:")
                for nim in disponiveis_nim:
                    print(f"  Militar: {nim} | Última nomeação A: {ultima_nomeacao_a[nim]}")
                n_efetivos = servico.n_elementos
                n_reservas = servico.n_reservas
                escala = EscalaService.criar_ou_obter_escala(servico, e_escala_b=False)
                # Nomear efetivo
                if disponiveis_nim:
                    nim_efetivo = disponiveis_nim[0]
                    militar_efetivo = militares_dict[nim_efetivo]
                    if EscalaService.nomear_efetivo(escala, militar_efetivo, dia):
                        ultima_nomeacao_a[nim_efetivo] = dia
                        militar_efetivo.ultima_nomeacao_a = dia
                        militar_efetivo.save()
                        print(f"[DEBUG] Militar nomeado EFETIVO: {nim_efetivo} | Nova última nomeação A: {dia}")
                        # Mover o efetivo para o fim da rotação
                        rotacao_nim.append(rotacao_nim.pop(rotacao_nim.index(nim_efetivo)))
                        # Guardar o efetivo para possível uso como reserva no dia anterior
                        efetivos_por_dia_a[dia] = militar_efetivo

            # Agora nomear os reservas usando os efetivos do dia seguinte da mesma escala
            # Primeiro para escala B
            for dia in sorted(dias_escala['escala_b']):
                escala = EscalaService.criar_ou_obter_escala(servico, e_escala_b=True)
                # Verificar se existe efetivo no dia seguinte da escala B
                dia_seguinte = dia + timedelta(days=1)
                militar_reserva = None
                dia_efetivo = None
                
                if dia_seguinte in efetivos_por_dia_b:
                    militar_reserva = efetivos_por_dia_b[dia_seguinte]
                    dia_efetivo = dia_seguinte
                    # Verificar se o militar pode ser reserva
                    disponivel, _ = EscalaService.verificar_disponibilidade_reserva(militar_reserva, dia, True)
                    if not disponivel:
                        militar_reserva = None
                        dia_efetivo = None
                
                if not militar_reserva:
                    # Se não houver efetivo válido no dia seguinte, procura o próximo disponível
                    militar_reserva, dia_efetivo = EscalaService.encontrar_proximo_efetivo_valido(dia, efetivos_por_dia_b, dias_escala['escala_b'], True)
                
                if militar_reserva and EscalaService.nomear_reserva(escala, militar_reserva, dia):
                    print(f"[DEBUG] Militar nomeado RESERVA B: {militar_reserva.nim} (efetivo do dia {dia_efetivo})")

            # Depois para escala A
            for dia in sorted(dias_escala['escala_a']):
                escala = EscalaService.criar_ou_obter_escala(servico, e_escala_b=False)
                # Verificar se existe efetivo no dia seguinte da escala A
                dia_seguinte = dia + timedelta(days=1)
                militar_reserva = None
                dia_efetivo = None
                
                if dia_seguinte in efetivos_por_dia_a:
                    militar_reserva = efetivos_por_dia_a[dia_seguinte]
                    dia_efetivo = dia_seguinte
                    # Verificar se o militar pode ser reserva
                    disponivel, _ = EscalaService.verificar_disponibilidade_reserva(militar_reserva, dia, False)
                    if not disponivel:
                        militar_reserva = None
                        dia_efetivo = None
                
                if not militar_reserva:
                    # Se não houver efetivo válido no dia seguinte, procura o próximo disponível
                    militar_reserva, dia_efetivo = EscalaService.encontrar_proximo_efetivo_valido(dia, efetivos_por_dia_a, dias_escala['escala_a'], False)
                
                if militar_reserva and EscalaService.nomear_reserva(escala, militar_reserva, dia):
                    print(f"[DEBUG] Militar nomeado RESERVA A: {militar_reserva.nim} (efetivo do dia {dia_efetivo})")
            
            return True
        except Exception as e:
            print(f"Erro ao gerar escalas: {str(e)}")
            return False
