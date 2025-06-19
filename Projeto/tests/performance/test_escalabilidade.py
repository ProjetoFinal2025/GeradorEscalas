import time
from datetime import date, timedelta
from django.test import TestCase
from django.utils import timezone
from core.models import Militar, Servico, Dispensa
from core.services.escala_service import EscalaService

class EscalaEscalabilidadeTest(TestCase):
    def gerar_militares(self, quantidade):
        """Gera um número específico de militares para teste"""
        militares = []
        for i in range(quantidade):
            militar = Militar.objects.create(
                nim=f'{10000000 + i}',
                nome=f'Militar Teste {i}',
                posto='SOL',
                funcao='Condutor',
                telefone=900000000 + i,
                email=f'militar{i}@exemplo.com'
            )
            militares.append(militar)
        return militares

    def criar_servico(self, militares, n_elementos, n_reservas):
        """Cria um serviço com os parâmetros especificados"""
        servico = Servico.objects.create(
            nome='Serviço de Escalabilidade Test',
            hora_inicio='08:00',
            hora_fim='08:00',
            tipo_escalas='AB',
            n_elementos=n_elementos,
            n_reservas=n_reservas
        )
        servico.militares.set(militares)
        return servico

    def criar_dispensas_aleatorias(self, militares, percentagem=20):
        """Cria dispensas aleatórias para uma percentagem dos militares"""
        import random
        militares_para_dispensa = random.sample(
            militares, 
            k=int(len(militares) * (percentagem/100))
        )
        data_hoje = timezone.now().date()
        
        for militar in militares_para_dispensa:
            inicio_dispensa = data_hoje + timedelta(days=random.randint(1, 30))
            Dispensa.objects.create(
                militar=militar,
                data_inicio=inicio_dispensa,
                data_fim=inicio_dispensa + timedelta(days=random.randint(1, 5)),
                motivo='Dispensa para teste de escalabilidade'
            )

    def test_escalabilidade_numero_militares(self):
        """
        Testa a escalabilidade do sistema com diferentes números de militares.
        Avalia como o tempo de geração de escalas aumenta com mais militares.
        """
        data_inicio = timezone.now().date() + timedelta(days=1)
        data_fim = data_inicio + timedelta(days=7)  # Período fixo de 7 dias
        tamanhos_equipe = [10, 25, 50, 100]  # Diferentes tamanhos de equipe
        
        resultados = []
        for n_militares in tamanhos_equipe:
            # Configurar teste
            militares = self.gerar_militares(n_militares)
            n_elementos = max(2, n_militares // 10)  # Ajusta número de elementos baseado no tamanho da equipe
            n_reservas = max(1, n_elementos // 2)    # Ajusta número de reservas
            
            servico = self.criar_servico(militares, n_elementos, n_reservas)
            self.criar_dispensas_aleatorias(militares)
            
            # Medir tempo de execução
            inicio = time.time()
            sucesso = EscalaService.gerar_escalas_automaticamente(
                servico,
                data_inicio,
                data_fim
            )
            fim = time.time()
            
            tempo_execucao = fim - inicio
            resultados.append({
                'n_militares': n_militares,
                'n_elementos': n_elementos,
                'n_reservas': n_reservas,
                'tempo_execucao': tempo_execucao,
                'sucesso': sucesso
            })
            
            # Limpar dados para próximo teste
            servico.escalas.all().delete()
            Militar.objects.all().delete()
        
        # Imprimir resultados
        print("\nResultados do Teste de Escalabilidade - Número de Militares:")
        print("=" * 70)
        for resultado in resultados:
            print(f"Militares: {resultado['n_militares']}")
            print(f"Elementos por escala: {resultado['n_elementos']}")
            print(f"Reservas por escala: {resultado['n_reservas']}")
            print(f"Tempo de execução: {resultado['tempo_execucao']:.2f} segundos")
            print(f"Geração bem sucedida: {'Sim' if resultado['sucesso'] else 'Não'}")
            print("-" * 50)

    def test_escalabilidade_periodo(self):
        """
        Testa a escalabilidade do sistema com diferentes períodos de tempo.
        Avalia como o tempo de geração aumenta com períodos mais longos.
        """
        n_militares = 50  # Número fixo de militares
        periodos_dias = [7, 15, 30, 45, 60]  # Diferentes períodos
        
        # Configurar militares e serviço
        militares = self.gerar_militares(n_militares)
        servico = self.criar_servico(militares, n_elementos=5, n_reservas=2)
        self.criar_dispensas_aleatorias(militares)
        
        resultados = []
        data_inicio = timezone.now().date() + timedelta(days=1)
        
        for dias in periodos_dias:
            data_fim = data_inicio + timedelta(days=dias)
            
            # Medir tempo de execução
            inicio = time.time()
            sucesso = EscalaService.gerar_escalas_automaticamente(
                servico,
                data_inicio,
                data_fim
            )
            fim = time.time()
            
            tempo_execucao = fim - inicio
            resultados.append({
                'periodo_dias': dias,
                'tempo_execucao': tempo_execucao,
                'sucesso': sucesso,
                'nomeacoes_por_segundo': (dias * 2) / tempo_execucao  # 2 escalas por dia (A e B)
            })
            
            # Limpar nomeações para próximo teste
            servico.escalas.all().delete()
        
        # Imprimir resultados
        print("\nResultados do Teste de Escalabilidade - Período:")
        print("=" * 70)
        for resultado in resultados:
            print(f"Período: {resultado['periodo_dias']} dias")
            print(f"Tempo de execução: {resultado['tempo_execucao']:.2f} segundos")
            print(f"Nomeações por segundo: {resultado['nomeacoes_por_segundo']:.2f}")
            print(f"Geração bem sucedida: {'Sim' if resultado['sucesso'] else 'Não'}")
            print("-" * 50)

    def test_escalabilidade_carga_maxima(self):
        """
        Testa os limites do sistema com uma carga máxima.
        Combina grande número de militares com período longo.
        """
        n_militares = 200  # Teste com um número grande de militares
        periodo_dias = 45   # Período longo
        
        # Configurar teste
        militares = self.gerar_militares(n_militares)
        servico = self.criar_servico(militares, n_elementos=10, n_reservas=5)
        self.criar_dispensas_aleatorias(militares, percentagem=30)  # Mais dispensas
        
        data_inicio = timezone.now().date() + timedelta(days=1)
        data_fim = data_inicio + timedelta(days=periodo_dias)
        
        # Medir tempo e uso de memória
        inicio = time.time()
        sucesso = EscalaService.gerar_escalas_automaticamente(
            servico,
            data_inicio,
            data_fim
        )
        fim = time.time()
        
        tempo_execucao = fim - inicio
        nomeacoes_por_segundo = (periodo_dias * 2) / tempo_execucao
        
        # Imprimir resultados
        print("\nResultados do Teste de Carga Máxima:")
        print("=" * 70)
        print(f"Número de militares: {n_militares}")
        print(f"Período: {periodo_dias} dias")
        print(f"Tempo total de execução: {tempo_execucao:.2f} segundos")
        print(f"Nomeações por segundo: {nomeacoes_por_segundo:.2f}")
        print(f"Geração bem sucedida: {'Sim' if sucesso else 'Não'}")
        
        # Verificar se o sistema consegue lidar com a carga máxima
        self.assertTrue(sucesso, "O sistema não conseguiu lidar com a carga máxima") 