import pandas as pd
from django.core.exceptions import ValidationError
from ..models import Militar

def criar_template_excel():
    """Cria um template Excel para importação de militares"""
    # Definir as colunas do template
    colunas = [
        'NIM*',
        'Nome*',
        'Posto*',
        'Função*',
        'Telefone*',
        'Email*',
        'É Administrador'
    ]
    
    # Criar DataFrame vazio com as colunas
    df = pd.DataFrame(columns=colunas)
    
    # Adicionar algumas linhas de exemplo
    exemplos = [
        ['12345678', 'João Silva', 'SOL', 'Condutor', '912345678', 'joao.silva@exercito.pt', 'Não'],
        ['87654321', 'Maria Santos', '1SARG', 'Operador', '987654321', 'maria.santos@exercito.pt', 'Não']
    ]
    
    df_exemplos = pd.DataFrame(exemplos, columns=colunas)
    df = pd.concat([df, df_exemplos], ignore_index=True)
    
    # Salvar como Excel
    df.to_excel('template_importacao_militares.xlsx', index=False)
    return 'template_importacao_militares.xlsx'

def importar_militares_excel(arquivo_excel):
    """Importa militares de um arquivo Excel"""
    try:
        # Ler o arquivo Excel
        df = pd.read_excel(arquivo_excel)
        
        # Lista para armazenar erros
        erros = []
        militares_importados = []
        
        # Validar e importar cada linha
        for index, row in df.iterrows():
            try:
                # Validar campos obrigatórios
                campos_obrigatorios = ['NIM*', 'Nome*', 'Posto*', 'Função*', 'Telefone*', 'Email*']
                for campo in campos_obrigatorios:
                    if pd.isna(row[campo]):
                        raise ValidationError(f'Campo {campo} é obrigatório')
                
                # Criar dicionário com os dados do militar
                dados_militar = {
                    'nim': str(int(row['NIM*'])).zfill(8),  # Garantir 8 dígitos
                    'nome': row['Nome*'],
                    'posto': row['Posto*'],
                    'funcao': row['Função*'],
                    'telefone': int(row['Telefone*']),
                    'email': row['Email*'],
                    'e_administrador': row['É Administrador'].lower() == 'sim' if not pd.isna(row['É Administrador']) else False
                }
                
                # Criar ou atualizar militar
                militar, created = Militar.objects.update_or_create(
                    nim=dados_militar['nim'],
                    defaults=dados_militar
                )
                
                militares_importados.append(militar)
                
            except Exception as e:
                erros.append(f'Linha {index + 2}: {str(e)}')
        
        return {
            'sucesso': len(militares_importados),
            'erros': erros,
            'militares': militares_importados
        }
        
    except Exception as e:
        raise ValidationError(f'Erro ao processar arquivo: {str(e)}') 