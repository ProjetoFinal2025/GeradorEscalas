import time
from datetime import date, timedelta
from django.test import TestCase
from django.utils import timezone
from core.models import Militar, Servico, Dispensa
from core.services.escala_service import EscalaService

class EscalaPerformanceTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Criar um conjunto grande de militares para teste
        cls.militares = []
        for i in range(100):  # Testando com 100 militares
            militar = Militar.objects.create(
                nim=f'{10000000 + i}',
                nome=f'Militar Teste {i}',
                posto='SOL',
                funcao='Condutor',
                telefone=900000000 + i,
                email=f'militar{i}@exemplo.com'
            )
            cls.militares.append(militar)

        # Criar um serviço de teste
        cls.servico = Servico.objects.create(
            nome='Serviço de Performance Test',
            hora_inicio='08:00',
            hora_fim='08:00',
            tipo_escalas='AB',  # Testando ambos os tipos de escala
            n_elementos=5,
            n_reservas=2
        )

        # Adicionar militares ao serviço
        cls.servico.militares.set(cls.militares)

    def setUp(self):
        # Criar algumas dispensas aleatórias
        self.criar_dispensas_aleatorias()

    def criar_dispensas_aleatorias(self):
        """Cria dispensas aleatórias para 20% dos militares"""
        import random
        militares_para_dispensa = random.sample(self.militares, k=len(self.militares) // 5)
        data_hoje = timezone.now().date()
        
        for militar in militares_para_dispensa:
            inicio_dispensa = data_hoje + timedelta(days=random.randint(1, 30))
            Dispensa.objects.create(
                militar=militar,
                data_inicio=inicio_dispensa,
                data_fim=inicio_dispensa + timedelta(days=random.randint(1, 5)),
                motivo='Dispensa para teste de performance'
            )

    def test_performance_geracao_escala(self):
        """Testa a performance da geração de escalas para diferentes períodos"""
        data_inicio = timezone.now().date() + timedelta(days=1)
        periodos_teste = [7, 15, 30]  # Reduzindo para períodos menores para teste

        resultados = []
        for dias in periodos_teste:
            data_fim = data_inicio + timedelta(days=dias)
            
            # Medir tempo de execução
            inicio = time.time()
            sucesso = EscalaService.gerar_escalas_automaticamente(
                self.servico,
                data_inicio,
                data_fim
            )
            fim = time.time()
            
            tempo_execucao = fim - inicio
            resultados.append({
                'periodo_dias': dias,
                'tempo_execucao': tempo_execucao,
                'sucesso': sucesso
            })
            
            # Limpar as nomeações para o próximo teste
            self.servico.escalas.all().delete()

        # Imprimir resultados
        print("\nResultados do Teste de Performance de Geração:")
        print("=" * 50)
        for resultado in resultados:
            print(f"Período: {resultado['periodo_dias']} dias")
            print(f"Tempo de execução: {resultado['tempo_execucao']:.2f} segundos")
            print(f"Geração bem sucedida: {'Sim' if resultado['sucesso'] else 'Não'}")
            print("-" * 30)

        # Verificar se pelo menos uma geração foi bem sucedida
        self.assertTrue(any(r['sucesso'] for r in resultados), 
                       "Nenhuma geração de escala foi bem sucedida")

    def test_performance_verificacao_disponibilidade(self):
        """Testa a performance da verificação de disponibilidade dos militares"""
        data_teste = timezone.now().date() + timedelta(days=5)
        n_verificacoes = 100  # Reduzindo o número de verificações para teste
        
        inicio = time.time()
        resultados = []
        for _ in range(n_verificacoes):
            for militar in self.militares[:10]:  # Testando com 10 militares
                disponivel, _ = EscalaService.verificar_disponibilidade_militar(militar, data_teste)
                resultados.append(disponivel)
        fim = time.time()
        
        tempo_total = fim - inicio
        tempo_medio = tempo_total / (n_verificacoes * 10)
        
        print("\nResultados do Teste de Verificação de Disponibilidade:")
        print("=" * 50)
        print(f"Número total de verificações: {n_verificacoes * 10}")
        print(f"Tempo total: {tempo_total:.2f} segundos")
        print(f"Tempo médio por verificação: {tempo_medio*1000:.2f} ms")
        
        # Verificar se obtivemos resultados
        self.assertTrue(len(resultados) > 0, "Nenhuma verificação foi realizada")

    def test_performance_carga(self):
        """Testa a performance do sistema sob carga"""
        data_inicio = timezone.now().date() + timedelta(days=1)
        data_fim = data_inicio + timedelta(days=7)  # Reduzindo para 7 dias
        n_iteracoes = 3  # Reduzindo o número de iterações
        
        inicio = time.time()
        sucessos = 0
        for i in range(n_iteracoes):
            sucesso = EscalaService.gerar_escalas_automaticamente(
                self.servico,
                data_inicio,
                data_fim
            )
            if sucesso:
                sucessos += 1
            # Limpar as nomeações para a próxima iteração
            self.servico.escalas.all().delete()
        fim = time.time()
        
        tempo_total = fim - inicio
        tempo_medio = tempo_total / n_iteracoes
        
        print("\nResultados do Teste de Carga:")
        print("=" * 50)
        print(f"Número de iterações: {n_iteracoes}")
        print(f"Tempo total: {tempo_total:.2f} segundos")
        print(f"Tempo médio por geração: {tempo_medio:.2f} segundos")
        print(f"Taxa de sucesso: {(sucessos/n_iteracoes)*100:.1f}%")
        
        # Verificar se pelo menos uma geração foi bem sucedida
        self.assertTrue(sucessos > 0, "Nenhuma geração de escala foi bem sucedida") 