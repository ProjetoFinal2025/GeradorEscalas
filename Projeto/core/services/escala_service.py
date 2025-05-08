from datetime import date, timedelta
from typing import Tuple, List, Dict
from django.utils import timezone
from collections import defaultdict
from django.db.models import Count

from ..models import Escala, Militar, Servico, Feriado, EscalaMilitar, Dispensa, Nomeacao


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

        # Obter todos os feriados
        feriados = Feriado.objects.filter(
            data__gte=data_inicio,
            data__lte=data_fim
        ).values_list('data', flat=True)

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
    def obter_feriados_personalizados(data_inicio: date, data_fim: date) -> List[date]:
        return list(Feriado.objects.filter(data__gte=data_inicio, data__lte=data_fim).values_list('data', flat=True))

    @staticmethod
    def obter_feriados(data_inicio: date, data_fim: date) -> List[date]:
        """Obtém todos os feriados no período especificado."""
        feriados = []
        for ano in range(data_inicio.year, data_fim.year + 1):
            feriados.extend([
                date(ano, 1, 1),  # Ano Novo
                date(ano, 4, 25),  # Dia da Liberdade
                date(ano, 5, 1),  # Dia do Trabalhador
                date(ano, 6, 10),  # Dia de Portugal
                date(ano, 8, 15),  # Assunção de Nossa Senhora
                date(ano, 10, 5),  # Implantação da República
                date(ano, 11, 1),  # Todos os Santos
                date(ano, 12, 1),  # Restauração da Independência
                date(ano, 12, 8),  # Imaculada Conceição
                date(ano, 12, 25),  # Natal
            ])
            if ano == 2024:
                feriados.extend([
                    date(2024, 2, 13),  # Carnaval
                    date(2024, 3, 29),  # Sexta-feira Santa
                    date(2024, 3, 31),  # Páscoa
                    date(2024, 5, 30),  # Corpo de Deus
                ])
            elif ano == 2025:
                feriados.extend([
                    date(2025, 3, 4),  # Carnaval
                    date(2025, 4, 18),  # Sexta-feira Santa
                    date(2025, 4, 20),  # Páscoa
                    date(2025, 6, 19),  # Corpo de Deus
                ])
        feriados.extend(
            list(Feriado.objects.filter(data__gte=data_inicio, data__lte=data_fim).values_list('data', flat=True)))
        feriados = [f for f in feriados if data_inicio <= f <= data_fim]
        return sorted(list(set(feriados)))

    @staticmethod
    def militar_em_dispensa(militar: Militar, data: date) -> bool:
        return Dispensa.objects.filter(militar=militar, data_inicio__lte=data, data_fim__gte=data).exists()

    @staticmethod
    def militar_ja_nomeado(militar: Militar, data: date) -> bool:
        # Verifica se o militar já tem nomeação para esta data
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
        escala, _ = Escala.objects.get_or_create(servico=servico, e_escala_b=e_escala_b )
        return escala

    @staticmethod
    def gerar_escalas_automaticamente(servico: Servico, data_inicio: date, data_fim: date) -> bool:
        try:
            # Limpar os dados da previsão para o período pedido
            escala_militares_ids = EscalaMilitar.objects.filter(
                escala__servico=servico
            ).values_list('id', flat=True)

            # Excluir as nomeações dentro do período para essas escalas
            Nomeacao.objects.filter(
                escala_militar__id__in=escala_militares_ids,
                data__gte=data_inicio,
                data__lte=data_fim
            ).delete()

            # Obter todos os dias do período para escalas tipo A e B
            dias_escala = EscalaService.obter_dias_escala(data_inicio, data_fim)

            # Obter todos os militares associados ao serviço
            militares = list(servico.militares.all())

            # Para garantir resultados consistentes, devemos primeiro carregar TODAS as informações
            # de última nomeação antes de começar a modificar o banco de dados
            militares_info = []
            for militar in militares:
                # Criar uma cópia dos dados para não modificar o objeto original diretamente
                militares_info.append({
                    'nim': militar.nim,
                    'militar': militar,
                    'ultima_nomeacao_a': militar.ultima_nomeacao_a,
                    'ultima_nomeacao_b': militar.ultima_nomeacao_b
                })

            # Processar dias para escala tipo A
            EscalaService._processar_escala_por_tipo(
                dias=dias_escala['escala_a'],
                tipo='A',
                militares_info=militares_info,
                servico=servico
            )

            # Processar dias para escala tipo B
            EscalaService._processar_escala_por_tipo(
                dias=dias_escala['escala_b'],
                tipo='B',
                militares_info=militares_info,
                servico=servico
            )

            # Atualizar todos os militares com suas últimas nomeações em uma única operação
            for info in militares_info:
                militar = info['militar']
                if militar.ultima_nomeacao_a != info['ultima_nomeacao_a']:
                    militar.ultima_nomeacao_a = info['ultima_nomeacao_a']
                if militar.ultima_nomeacao_b != info['ultima_nomeacao_b']:
                    militar.ultima_nomeacao_b = info['ultima_nomeacao_b']
                militar.save()

            return True
        except Exception as e:
            print(f"Erro ao gerar escalas: {str(e)}")
            return False

    @staticmethod
    def _processar_escala_por_tipo(dias, tipo, militares_info, servico):
        """
        Processa a geração de escala para um tipo específico (A ou B).

        Args:
            dias: Lista de dias para processamento
            tipo: Tipo de escala ('A' ou 'B')
            militares_info: Lista com informações dos militares
            servico: Objeto Servico
        """
        for dia in dias:
            # Obter disponíveis para o dia
            disponiveis = []
            for info in militares_info:
                militar = info['militar']
                disponivel, _ = EscalaService.verificar_disponibilidade_militar(militar, dia)
                if disponivel:
                    disponiveis.append(info)

            # Ordenar disponíveis por data da última nomeação e NIM (para desempate)
            campo_data = 'ultima_nomeacao_b' if tipo == 'B' else 'ultima_nomeacao_a'
            disponiveis.sort(key=lambda x: (x[campo_data] or date.min, x['nim']))

            # Criar ou obter a escala
            escala = EscalaService.criar_ou_obter_escala(servico, e_escala_b=(tipo == 'B'))

            # Nomear efetivo se houver disponíveis
            if disponiveis:
                # Nomear efetivo
                EscalaService._nomear_militar(
                    info=disponiveis[0],
                    dia=dia,
                    escala=escala,
                    e_reserva=False,
                    tipo=tipo
                )

                # Nomear reserva se houver mais de um disponível
                if len(disponiveis) > 1:
                    EscalaService._nomear_militar(
                        info=disponiveis[1],
                        dia=dia,
                        escala=escala,
                        e_reserva=True,
                        tipo=tipo
                    )

    @staticmethod
    def _nomear_militar(info, dia, escala, e_reserva, tipo):
        """
        Nomeia um militar para uma escala específica.

        Args:
            info: Dicionário com informações do militar
            dia: Data da nomeação
            escala: Objeto Escala
            e_reserva: Se é nomeação de reserva
            tipo: Tipo de escala ('A' ou 'B')
        """
        militar = info['militar']

        # Verificar ou criar a relação EscalaMilitar
        ordem = 2 if e_reserva else 1
        escala_militar, _ = EscalaMilitar.objects.get_or_create(
            escala=escala,
            militar=militar,
            defaults={'ordem': ordem}
        )

        # Criar nomeação para este dia se não existir
        if not Nomeacao.objects.filter(
                escala_militar=escala_militar,
                data=dia,
                e_reserva=e_reserva
        ).exists():
            Nomeacao.objects.create(
                escala_militar=escala_militar,
                data=dia,
                e_reserva=e_reserva
            )

            # Atualizar data da última nomeação (apenas na estrutura de dados local)
            if tipo == 'B':
                info['ultima_nomeacao_b'] = dia
            else:
                info['ultima_nomeacao_a'] = dia
