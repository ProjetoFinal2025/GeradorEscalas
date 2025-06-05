# Documentação Técnica do Gerador de Escalas

Este documento descreve o funcionamento técnico do sistema de geração automática de escalas, detalhando a arquitetura, as estruturas de dados e os algoritmos utilizados.

## Visão Geral do Processo de Agendamento

O objetivo do sistema é gerar escalas de serviço de forma automática, nomeando militares para dias específicos com base num conjunto de regras complexas. O processo garante uma rotação justa entre os militares, respeita as suas dispensas e feriados, e segue uma lógica distinta para dias úteis (Escala A) e fins de semana/feriados (Escala B).

O coração do sistema reside no método `gerar_escalas_automaticamente` da classe `EscalaService`, que orquestra todo o processo.

## Estruturas de Dados Chave (Modelos Django)

A base de dados é estruturada em torno dos seguintes modelos Django, que representam as entidades centrais do sistema:

-   **`Militar`**: Representa um militar, contendo informações pessoais como NIM (Número de Identificação Militar), posto e contacto. Crucialmente, armazena as datas da sua última nomeação para a Escala A (`ultima_nomeacao_a`) e B (`ultima_nomeacao_b`) para garantir a rotação.
-   **`Servico`**: Define um tipo de serviço (ex: "Oficial de Dia"). Especifica o número de militares efetivos e de reserva necessários, e se opera em dias úteis (A), fins de semana/feriados (B) ou ambos (AB).
-   **`Escala`**: Representa uma escala específica dentro de um serviço. Existe uma distinção clara entre `e_escala_b=False` (Escala A) e `e_escala_b=True` (Escala B).
-   **`EscalaMilitar`**: Tabela de associação que liga um `Militar` a uma `Escala`, definindo a sua ordem de rotação manual.
-   **`Nomeacao`**: Regista a nomeação de um militar para um dia específico numa escala, indicando se é um `e_reserva`. Esta é a tabela que guarda o resultado final do agendamento.
-   **`Dispensa`**: Regista os períodos em que um militar não está disponível para serviço (ex: férias, baixa médica).
-   **`Feriado`**: Armazena os feriados, que são tratados como dias de Escala B.

## Algoritmo de Geração de Escalas

O algoritmo é implementado no método `gerar_escalas_automaticamente` e nas suas funções auxiliares. Segue uma sequência lógica de passos para garantir que todas as regras são cumpridas.

### Passo 1: Inicialização e Validação (`_inicializar_geracao`)

1.  **Validação de Datas**: O sistema verifica se a data de início do agendamento é futura.
2.  **Limpeza de Dados Anteriores**: Todas as `Nomeacao` existentes no período solicitado são eliminadas para evitar duplicados e garantir um novo começo.
3.  **Recolha de Dados**: Os militares associados ao serviço são carregados, e os dias do período são classificados em `escala_a` (dias úteis) e `escala_b` (fins de semana e feriados).

### Passo 2: Atualização das Últimas Nomeações (`_atualizar_ultimas_nomeacoes`)

-   Para cada militar, o sistema consulta a base de dados para encontrar a data da sua última nomeação efetiva (não reserva) antes do início do período de agendamento.
-   As datas são guardadas nos campos `ultima_nomeacao_a` e `ultima_nomeacao_b` do modelo `Militar` e também em dicionários em memória para acesso rápido.

### Passo 3: Processamento de Efetivos (`_processar_efetivos_para_escala`)

Esta é a fase central, executada separadamente para Escala B e depois para Escala A, para garantir que os serviços de fim de semana são prioritários e bloqueiam os dias adjacentes.

1.  **Ordenação por Rotação**: Para cada dia a processar, os militares são ordenados com base em dois critérios:
    1.  **Data da Última Nomeação**: Militares que não são nomeados há mais tempo têm prioridade (data mais antiga ou `None`).
    2.  **Ordem Manual**: Como critério de desempate, utiliza-se a ordem definida na tabela `EscalaMilitar`.
2.  **Verificação de Disponibilidade**: A lista ordenada é filtrada, removendo militares que não estão disponíveis nesse dia. A disponibilidade é verificada através de `verificar_disponibilidade_militar`, que consolida várias regras:
    -   Não estar em período de `Dispensa`.
    -   Não ter já uma nomeação para esse dia.
    -   Não ter uma nomeação no dia anterior ou seguinte (regra de 24h de folga).
3.  **Nomeação**: Os primeiros `n_elementos` militares da lista de disponíveis são nomeados como efetivos.
4.  **Atualização de Estado**: Após a nomeação, a data da última nomeação do militar é atualizada em memória e na base de dados, e ele é adicionado a um dicionário de efetivos do dia (`efetivos_por_dia`).

### Passo 4: Processamento de Reservas (`_processar_reservas_para_escala`)

A lógica para nomear reservas é diferente e baseia-se no princípio de que a reserva de um dia é, preferencialmente, o efetivo do dia seguinte na mesma escala.

1.  **Procura no Dia Seguinte**: Para cada dia, o sistema tenta encontrar um militar nomeado como efetivo no dia seguinte (`dia + 1 dia`) que esteja disponível para ser reserva.
2.  **Procura Alargada**: Se não for encontrado ninguém no dia seguinte (por exemplo, se for o último dia do período ou não houver efetivos), o sistema utiliza `encontrar_proximo_efetivo_valido` para procurar nos dias subsequentes da mesma escala.
3.  **Nomeação de Reserva**: Assim que um militar válido é encontrado, é nomeado como reserva para o dia atual através de `nomear_reserva`.
4.  **Repetição**: O processo repete-se até que o número necessário de reservas (`n_reservas`) seja atingido para o dia.

## Estruturas de Dados em Memória

Durante a execução, o algoritmo utiliza várias estruturas de dados em memória para gerir o estado de forma eficiente, evitando consultas repetidas à base de dados:

-   **`militares_dict`**: Um dicionário (`dict`) que mapeia o NIM de um militar ao seu objeto de modelo, permitindo acesso rápido (`O(1)`).
-   **`ultima_nomeacao_a` e `ultima_nomeacao_b`**: Dicionários que armazenam a última data de nomeação para cada militar, permitindo uma ordenação rápida durante o cálculo da rotação.
-   **`efetivos_por_dia_a` e `efetivos_por_dia_b`**: Dicionários `defaultdict(list)` que guardam a lista de militares nomeados como efetivos para cada dia. Esta estrutura é fundamental para a nomeação de reservas, pois permite consultar rapidamente quem estará de serviço nos dias seguintes.
