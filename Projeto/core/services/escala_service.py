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
    def obter_feriados_nacionais(ano: int) -> List[date]:
        return [
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
        ]

    @staticmethod
    def obter_feriados_moveis(ano: int) -> List[date]:
        if ano == 2024:
            return [
                date(2024, 2, 13),  # Carnaval
                date(2024, 3, 29),  # Sexta-feira Santa
                date(2024, 3, 31),  # Páscoa
                date(2024, 5, 30),  # Corpo de Deus
            ]
        elif ano == 2025:
            return [
                date(2025, 3, 4),  # Carnaval
                date(2025, 4, 18),  # Sexta-feira Santa
                date(2025, 4, 20),  # Páscoa
                date(2025, 6, 19),  # Corpo de Deus
            ]
        return []

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
    def nomear_efetivos(escala: Escala, militares: List[Militar], data: date, n_efetivos: int):
        nomeados = 0
        for militar in militares:
            if nomeados >= n_efetivos:
                break

            # Verifica se já existe uma escala_militar para este militar e esta escala
            escala_militar, created = EscalaMilitar.objects.get_or_create(
                escala=escala,
                militar=militar,
                defaults={'ordem': nomeados + 1}  # Definir ordem default se for criado
            )

            # Apenas cria uma nomeação se ainda não existe
            if not Nomeacao.objects.filter(escala_militar=escala_militar, data=data, e_reserva=False).exists():
                Nomeacao.objects.create(
                    escala_militar=escala_militar,
                    data=data,
                    e_reserva=False
                )

                # Atualiza a última nomeação do militar
                if escala.e_escala_b:
                    militar.ultima_nomeacao_b = data
                else:
                    militar.ultima_nomeacao_a = data
                militar.save()

                nomeados += 1
                print(f"[DEBUG] Nomeando militar {militar.nim} para o dia {data} como efetivo")

    @staticmethod
    def nomear_reservas(escala: Escala, militares: List[Militar], data: date, n_efetivos: int, n_reservas: int):
        nomeados_reserva = 0
        for militar in militares[n_efetivos:]:
            if nomeados_reserva >= n_reservas:
                break

            # Verifica se já existe uma escala_militar para este militar e esta escala
            escala_militar, created = EscalaMilitar.objects.get_or_create(
                escala=escala,
                militar=militar,
                defaults={'ordem': n_efetivos + nomeados_reserva + 1}  # Ordem após os efetivos
            )

            # Apenas cria uma nomeação se ainda não existe
            if not Nomeacao.objects.filter(escala_militar=escala_militar, data=data, e_reserva=True).exists():
                Nomeacao.objects.create(
                    escala_militar=escala_militar,
                    data=data,
                    e_reserva=True
                )

                # Atualiza a última nomeação do militar
                if escala.e_escala_b:
                    militar.ultima_nomeacao_b = data
                else:
                    militar.ultima_nomeacao_a = data
                militar.save()

                nomeados_reserva += 1
                print(f"[DEBUG] Nomeando militar {militar.nim} para o dia {data} como reserva")

    @staticmethod
    def nomear_escala_a(servico: Servico, data: date) -> Tuple[bool, str]:
        """Nomeia um efetivo e um reserva para um dia útil."""
        militares_disponiveis = EscalaService.obter_militares_disponiveis(servico, data)
        n_efetivos = servico.n_elementos
        n_reservas = servico.n_reservas
        if len(militares_disponiveis) < n_efetivos + n_reservas:
            return False, "Não existem militares suficientes disponíveis"

        escala = EscalaService.criar_ou_obter_escala(servico, e_escala_b=False)
        EscalaService.nomear_efetivos(escala, militares_disponiveis, data, n_efetivos)
        EscalaService.nomear_reservas(escala, militares_disponiveis, data, n_efetivos, n_reservas)

        return True, "Escala A nomeada com sucesso"

    @staticmethod
    def nomear_escala_b(servico: Servico, data: date) -> Tuple[bool, str]:
        """Nomeia um efetivo e um reserva para um fim de semana ou feriado."""
        militares_disponiveis = EscalaService.obter_militares_disponiveis(servico, data)
        n_efetivos = servico.n_elementos
        n_reservas = servico.n_reservas
        if len(militares_disponiveis) < n_efetivos + n_reservas:
            return False, "Não existem militares suficientes disponíveis"

        escala = EscalaService.criar_ou_obter_escala(servico, e_escala_b=True)
        EscalaService.nomear_efetivos(escala, militares_disponiveis, data, n_efetivos)
        EscalaService.nomear_reservas(escala, militares_disponiveis, data, n_efetivos, n_reservas)

        return True, "Escala B nomeada com sucesso"

    @staticmethod
    def nomear_escala(servico: Servico, data: date) -> Tuple[bool, str]:
        """Nomeia um efetivo e um reserva para um dia específico, escolhendo automaticamente o tipo de escala."""
        if not servico.ativo:
            return False, "O serviço não está ativo"
        feriados = EscalaService.obter_feriados(data, data)
        if data.weekday() >= 5 or data in feriados:
            return EscalaService.nomear_escala_b(servico, data)
        else:
            return EscalaService.nomear_escala_a(servico, data)

    @staticmethod
    def obter_nomeacoes_por_dia(servico: Servico, data_inicio: date, data_fim: date) -> Dict[date, List[Nomeacao]]:
        nomeacoes_por_dia = defaultdict(list)

        # Obter todas as nomeações para as escalas do serviço no período
        nomeacoes = Nomeacao.objects.filter(
            escala_militar__escala__servico=servico,
            data__range=(data_inicio, data_fim)
        ).select_related('escala_militar', 'escala_militar__militar', 'escala_militar__escala')

        for nomeacao in nomeacoes:
            nomeacoes_por_dia[nomeacao.data].append(nomeacao)

        return nomeacoes_por_dia

    @staticmethod
    def nomear_efetivo(escala: Escala, militar: Militar, dia: date) -> bool:
        # Verificar ou criar a relação EscalaMilitar
        escala_militar, created = EscalaMilitar.objects.get_or_create(
            escala=escala,
            militar=militar,
            defaults={'ordem': 1}  # Definir ordem default se for criado
        )

        # Verificar se já existe nomeação
        if not Nomeacao.objects.filter(escala_militar=escala_militar, data=dia, e_reserva=False).exists():
            Nomeacao.objects.create(
                escala_militar=escala_militar,
                data=dia,
                e_reserva=False
            )
            return True
        return False

    @staticmethod
    def nomear_reserva(escala: Escala, militar: Militar, dia: date) -> bool:
        # Verificar ou criar a relação EscalaMilitar
        escala_militar, created = EscalaMilitar.objects.get_or_create(
            escala=escala,
            militar=militar,
            defaults={'ordem': 2}  # Definir ordem default se for criado
        )

        # Verificar se já existe nomeação
        if not Nomeacao.objects.filter(escala_militar=escala_militar, data=dia, e_reserva=True).exists():
            Nomeacao.objects.create(
                escala_militar=escala_militar,
                data=dia,
                e_reserva=True
            )
            return True
        return False

    @staticmethod
    def atualizar_ultima_nomeacao(militar: Militar, dia: date, tipo: str):
        if tipo == 'B':
            militar.ultima_nomeacao_b = dia
        else:
            militar.ultima_nomeacao_a = dia
        militar.save()

    @staticmethod
    def mover_efetivo_para_fim(disponiveis_nim: List[int], nim: int):
        if nim in disponiveis_nim:
            disponiveis_nim.append(disponiveis_nim.pop(disponiveis_nim.index(nim)))

    @staticmethod
    def reordenar_disponiveis(disponiveis_nim: List[int], ultima_nomeacao_a: Dict[int, date],
                              ultima_nomeacao_b: Dict[int, date], tipo: str):
        if tipo == 'B':
            disponiveis_nim.sort(key=lambda nim: (ultima_nomeacao_b[nim] or date.min, nim))
        else:
            disponiveis_nim.sort(key=lambda nim: (ultima_nomeacao_a[nim] or date.min, nim))

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
            # Primeiro, encontrar todas as EscalaMilitar associadas ao serviço
            escala_militares_ids = EscalaMilitar.objects.filter(
                escala__servico=servico
            ).values_list('id', flat=True)

            # Agora, excluir as nomeações dentro do período para essas escalas
            Nomeacao.objects.filter(
                escala_militar__id__in=escala_militares_ids,
                data__gte=data_inicio,
                data__lte=data_fim
            ).delete()

            dias_escala = EscalaService.obter_dias_escala(data_inicio, data_fim)
            militares = list(servico.militares.all())
            militares_dict = {m.nim: m for m in militares}

            # Inicializar dicionários de última nomeação
            ultima_nomeacao_a = {m.nim: m.ultima_nomeacao_a for m in militares}
            ultima_nomeacao_b = {m.nim: m.ultima_nomeacao_b for m in militares}

            for dia in dias_escala['escala_a'] + dias_escala['escala_b']:
                tipo = 'B' if dia in dias_escala['escala_b'] else 'A'
                print(f"\n[DEBUG] Dia: {dia} | Tipo: {tipo}")

                # Obter disponíveis para o dia
                disponiveis_nim = [nim for nim, m in militares_dict.items()
                                   if EscalaService.verificar_disponibilidade_militar(m, dia)[0]]

                # Ordenar disponíveis por data da última nomeação
                if tipo == 'B':
                    disponiveis_nim.sort(key=lambda nim: (ultima_nomeacao_b[nim] or date.min, nim))
                else:
                    disponiveis_nim.sort(key=lambda nim: (ultima_nomeacao_a[nim] or date.min, nim))

                print("Ordem dos disponíveis para o próximo dia:")
                # for nim in disponiveis_nim:
                #     print(
                #         f"  Militar: {nim} | Última nomeação A: {ultima_nomeacao_a[nim]} | Última nomeação B: {ultima_nomeacao_b[nim]}")

                n_efetivos = servico.n_elementos
                n_reservas = servico.n_reservas
                escala = EscalaService.criar_ou_obter_escala(servico, e_escala_b=(tipo == 'B'))

                # Nomear efetivos e reservas
                nomeados = []
                if disponiveis_nim:
                    # Nomear efetivo
                    nim = disponiveis_nim[0]
                    militar = militares_dict[nim]

                    # Verificar ou criar a relação EscalaMilitar
                    escala_militar, created = EscalaMilitar.objects.get_or_create(
                        escala=escala,
                        militar=militar,
                        defaults={'ordem': 1}  # Definir ordem default
                    )

                    # Criar nomeação para este dia
                    if not Nomeacao.objects.filter(escala_militar=escala_militar, data=dia, e_reserva=False).exists():
                        Nomeacao.objects.create(
                            escala_militar=escala_militar,
                            data=dia,
                            e_reserva=False
                        )
                        nomeados.append(nim)

                        # Atualizar data da última nomeação
                        if tipo == 'B':
                            ultima_nomeacao_b[nim] = dia
                            militar.ultima_nomeacao_b = dia
                        else:
                            ultima_nomeacao_a[nim] = dia
                            militar.ultima_nomeacao_a = dia
                        militar.save()
                        print(f"[DEBUG] Militar nomeado: {nim} | Nova última nomeação {tipo}: {dia}")

                    # Nomear reserva
                    if len(disponiveis_nim) > 1:
                        nim = disponiveis_nim[1]
                        militar = militares_dict[nim]

                        # Verificar ou criar a relação EscalaMilitar
                        escala_militar, created = EscalaMilitar.objects.get_or_create(
                            escala=escala,
                            militar=militar,
                            defaults={'ordem': 2}  # Definir ordem default
                        )

                        # Criar nomeação para este dia
                        if not Nomeacao.objects.filter(escala_militar=escala_militar, data=dia,
                                                       e_reserva=True).exists():
                            Nomeacao.objects.create(
                                escala_militar=escala_militar,
                                data=dia,
                                e_reserva=True
                            )
                            nomeados.append(nim)
                            print(f"[DEBUG] Reserva nomeado: {nim}")

                # Mover nomeados para o fim da lista
                for nim in nomeados:
                    if nim in disponiveis_nim:
                        disponiveis_nim.append(disponiveis_nim.pop(disponiveis_nim.index(nim)))

                # Reordenar lista de disponíveis
                if tipo == 'B':
                    disponiveis_nim.sort(key=lambda nim: (ultima_nomeacao_b[nim] or date.min, nim))
                else:
                    disponiveis_nim.sort(key=lambda nim: (ultima_nomeacao_a[nim] or date.min, nim))

            return True
        except Exception as e:
            print(f"Erro ao gerar escalas: {str(e)}")
            return False


# Encontrar duplicados nas nomeações
def remover_nomeacoes_duplicadas():
    dups = (
        Nomeacao.objects
        .values('escala_militar', 'data', 'e_reserva')
        .annotate(count=Count('id'))
        .filter(count__gt=1)
    )

    for dup in dups:
        qs = Nomeacao.objects.filter(
            escala_militar=dup['escala_militar'],
            data=dup['data'],
            e_reserva=dup['e_reserva']
        )
        # Mantém só o primeiro, apaga os outros
        for n in qs[1:]:
            n.delete()