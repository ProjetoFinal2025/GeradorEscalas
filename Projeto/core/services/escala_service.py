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
    def verificar_disponibilidade_militar(militar: Militar, data: date) -> Tuple[bool, str]:
        if EscalaService.militar_em_dispensa(militar, data):
            return False, "Militar em dispensa"
        if EscalaService.militar_ja_nomeado(militar, data):
            return False, "Militar já tem escala neste dia"
        if EscalaService.militar_licenca_depois(militar, data):
            return False, "Militar entra de licença no dia seguinte"
        if EscalaService.militar_licenca_antes(militar, data):
            return False, "Militar apresentou-se de licença no dia anterior"
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
    def gerar_escalas_automaticamente(servico: Servico, data_inicio: date, data_fim: date) -> bool:
        """
        Gera escalas automaticamente para um serviço no período especificado,
        mantendo em memória a última nomeação de cada militar para garantir rotação justa.
        Atualiza as datas de última nomeação apenas no final de cada iteração diária.
        Usa sempre o NIM como referência para garantir consistência.
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
            
            # Inicializar dicionários de última nomeação
            ultima_nomeacao_a = {m.nim: m.ultima_nomeacao_a for m in militares}
            ultima_nomeacao_b = {m.nim: m.ultima_nomeacao_b for m in militares}

            # Construir lista de rotação ordenada pela última nomeação
            rotacao_nim = sorted([m.nim for m in militares], key=lambda nim: (ultima_nomeacao_b[nim] or ultima_nomeacao_a[nim] or date.min, nim))

            for dia in dias_escala['escala_a'] + dias_escala['escala_b']:
                tipo = 'B' if dia in dias_escala['escala_b'] else 'A'
                print(f"\n[DEBUG] Dia: {dia} | Tipo: {tipo}")
                # Filtrar indisponíveis no próprio dia, mas manter ordem da rotação
                disponiveis_nim = [nim for nim in rotacao_nim if EscalaService.verificar_disponibilidade_militar(militares_dict[nim], dia)[0]]
                print("Ordem dos disponíveis para o dia:")
                for nim in disponiveis_nim:
                    print(f"  Militar: {nim} | Última nomeação A: {ultima_nomeacao_a[nim]} | Última nomeação B: {ultima_nomeacao_b[nim]}")
                n_efetivos = servico.n_elementos
                n_reservas = servico.n_reservas
                escala = EscalaService.criar_ou_obter_escala(servico, e_escala_b=(tipo=='B'))
                # Nomear efetivo
                if disponiveis_nim:
                    nim_efetivo = disponiveis_nim[0]
                    militar_efetivo = militares_dict[nim_efetivo]
                    if EscalaService.nomear_efetivo(escala, militar_efetivo, dia):
                        if tipo == 'B':
                            ultima_nomeacao_b[nim_efetivo] = dia
                            militar_efetivo.ultima_nomeacao_b = dia
                        else:
                            ultima_nomeacao_a[nim_efetivo] = dia
                            militar_efetivo.ultima_nomeacao_a = dia
                        militar_efetivo.save()
                        print(f"[DEBUG] Militar nomeado EFETIVO: {nim_efetivo} | Nova última nomeação {tipo}: {dia}")
                        # Mover o efetivo para o fim da rotação
                        rotacao_nim.append(rotacao_nim.pop(rotacao_nim.index(nim_efetivo)))
                # Nomear reserva
                if len(disponiveis_nim) > 1:
                    nim_reserva = disponiveis_nim[1]
                    militar_reserva = militares_dict[nim_reserva]
                    if EscalaService.nomear_reserva(escala, militar_reserva, dia):
                        print(f"[DEBUG] Militar nomeado RESERVA: {nim_reserva}")
                # O reserva NÃO é movido na rotação!
            
            return True
        except Exception as e:
            print(f"Erro ao gerar escalas: {str(e)}")
            return False
