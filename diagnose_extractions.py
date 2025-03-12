#!/usr/bin/env python3
"""
Script de diagnóstico para análise de dados extraídos do scraper de leilões.
Ajuda a identificar problemas na extração e armazenamento de dados.
"""
import os
import sys
import json
import logging
import argparse
import sqlite3
from datetime import datetime
from tabulate import tabulate
from collections import Counter, defaultdict

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/diagnose.log"),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

def conectar_bd():
    """Conecta ao banco de dados SQLite"""
    try:
        return sqlite3.connect('auctions.db')
    except sqlite3.Error as e:
        logger.error(f"Erro ao conectar ao banco de dados: {e}")
        sys.exit(1)

def analisar_seletores_cache():
    """Analisa os seletores armazenados em cache e sua taxa de sucesso"""
    conn = conectar_bd()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT domain, url_pattern, selector_type, success_rate, selectors, timestamp 
            FROM selector_cache
            ORDER BY domain, success_rate DESC
        """)
        
        results = cursor.fetchall()
        
        if not results:
            print("Nenhum seletor encontrado no cache.")
            return
        
        print("\n=== ANÁLISE DE SELETORES CACHE ===")
        print(f"Total de registros: {len(results)}")
        
        # Agrupar por domínio
        domain_stats = defaultdict(list)
        for domain, url_pattern, selector_type, success_rate, selectors, timestamp in results:
            domain_stats[domain].append({
                'tipo': selector_type,
                'taxa_sucesso': success_rate,
                'padrao_url': url_pattern,
                'seletores': json.loads(selectors) if selectors else {},
                'timestamp': timestamp
            })
        
        # Exibir estatísticas por domínio
        print("\nEstatísticas por domínio:")
        domain_table = []
        for domain, items in domain_stats.items():
            listing_count = sum(1 for item in items if item['tipo'] == 'listing')
            detail_count = sum(1 for item in items if item['tipo'] == 'detail')
            avg_success = sum(item['taxa_sucesso'] for item in items) / len(items) if items else 0
            
            domain_table.append([
                domain, 
                listing_count,
                detail_count,
                f"{avg_success:.2f}%"
            ])
        
        print(tabulate(
            domain_table,
            headers=['Domínio', 'Seletores Listagem', 'Seletores Detalhe', 'Taxa Média Sucesso'],
            tablefmt='grid'
        ))
        
        # Análise detalhada por domínio (opcional)
        detalhes = input("\nMostrar detalhes de um domínio específico? (s/n): ")
        if detalhes.lower() == 's':
            domain_select = input("Digite o nome do domínio: ")
            if domain_select in domain_stats:
                print(f"\nDetalhes para domínio: {domain_select}")
                for item in domain_stats[domain_select]:
                    print(f"\nTipo: {item['tipo']}")
                    print(f"Taxa de sucesso: {item['taxa_sucesso']:.2f}%")
                    print(f"Padrão URL: {item['padrao_url']}")
                    print(f"Data: {item['timestamp']}")
                    print("Seletores:")
                    for key, value in item['seletores'].items():
                        print(f"  - {key}: {value}")
            else:
                print(f"Domínio '{domain_select}' não encontrado.")
        
    except sqlite3.Error as e:
        logger.error(f"Erro ao analisar seletores: {e}")
    finally:
        conn.close()

def analisar_imoveis():
    """Analisa os imóveis armazenados no banco de dados"""
    conn = conectar_bd()
    cursor = conn.cursor()
    
    try:
        # Verificar se a tabela property existe
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='property'")
        if not cursor.fetchone():
            print("Tabela 'property' não encontrada no banco de dados.")
            return
        
        # Obter contagem total
        cursor.execute("SELECT COUNT(*) FROM property")
        total = cursor.fetchone()[0]
        
        if total == 0:
            print("Nenhum imóvel encontrado no banco de dados.")
            return
        
        print("\n=== ANÁLISE DE IMÓVEIS ===")
        print(f"Total de imóveis: {total}")
        
        # Analisar completude dos dados
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN title IS NOT NULL AND title != '' THEN 1 ELSE 0 END) as has_title,
                SUM(CASE WHEN price IS NOT NULL AND price != '' THEN 1 ELSE 0 END) as has_price,
                SUM(CASE WHEN description IS NOT NULL AND description != '' THEN 1 ELSE 0 END) as has_description,
                SUM(CASE WHEN location IS NOT NULL AND location != '' THEN 1 ELSE 0 END) as has_location,
                SUM(CASE WHEN images IS NOT NULL AND images != '' THEN 1 ELSE 0 END) as has_images,
                SUM(CASE WHEN auction_date IS NOT NULL AND auction_date != '' THEN 1 ELSE 0 END) as has_auction_date
            FROM property
        """)
        
        result = cursor.fetchone()
        
        if result:
            total, has_title, has_price, has_description, has_location, has_images, has_auction_date = result
            
            completeness_table = [
                ["Título", has_title, f"{(has_title/total)*100:.2f}%"],
                ["Preço", has_price, f"{(has_price/total)*100:.2f}%"],
                ["Descrição", has_description, f"{(has_description/total)*100:.2f}%"],
                ["Localização", has_location, f"{(has_location/total)*100:.2f}%"],
                ["Imagens", has_images, f"{(has_images/total)*100:.2f}%"],
                ["Data do Leilão", has_auction_date, f"{(has_auction_date/total)*100:.2f}%"]
            ]
            
            print("\nCompletude dos dados:")
            print(tabulate(
                completeness_table,
                headers=['Campo', 'Total com valor', 'Porcentagem'],
                tablefmt='grid'
            ))
        
        # Analisar por domínio
        cursor.execute("""
            SELECT 
                domain,
                COUNT(*) as count
            FROM property
            GROUP BY domain
            ORDER BY count DESC
        """)
        
        domains = cursor.fetchall()
        
        if domains:
            print("\nImóveis por domínio:")
            domain_table = [[domain, count] for domain, count in domains]
            print(tabulate(
                domain_table,
                headers=['Domínio', 'Quantidade'],
                tablefmt='grid'
            ))
            
            # Opção para ver detalhes de um domínio específico
            ver_detalhes = input("\nVer detalhes de um domínio específico? (s/n): ")
            if ver_detalhes.lower() == 's':
                domain_name = input("Digite o nome do domínio: ")
                
                cursor.execute("""
                    SELECT id, title, price, url, created_at
                    FROM property
                    WHERE domain = ?
                    ORDER BY created_at DESC
                    LIMIT 10
                """, (domain_name,))
                
                properties = cursor.fetchall()
                
                if properties:
                    print(f"\nÚltimos 10 imóveis do domínio '{domain_name}':")
                    prop_table = []
                    for prop_id, title, price, url, created_at in properties:
                        title_short = (title[:40] + '...') if title and len(title) > 40 else title
                        prop_table.append([prop_id, title_short, price, created_at])
                    
                    print(tabulate(
                        prop_table,
                        headers=['ID', 'Título', 'Preço', 'Data Criação'],
                        tablefmt='grid'
                    ))
                    
                    # Ver detalhes completos de um imóvel
                    ver_imovel = input("\nVer detalhes completos de um imóvel? (s/n): ")
                    if ver_imovel.lower() == 's':
                        imovel_id = input("Digite o ID do imóvel: ")
                        
                        cursor.execute("""
                            SELECT * FROM property WHERE id = ?
                        """, (imovel_id,))
                        
                        imovel = cursor.fetchone()
                        
                        if imovel:
                            columns = [column[0] for column in cursor.description]
                            imovel_dict = dict(zip(columns, imovel))
                            
                            print(f"\nDetalhes do imóvel ID {imovel_id}:")
                            for campo, valor in imovel_dict.items():
                                if campo in ('images', 'additional_info'):
                                    try:
                                        parsed_val = json.loads(valor) if valor else {}
                                        print(f"{campo}:")
                                        for k, v in parsed_val.items():
                                            print(f"  - {k}: {v}")
                                    except:
                                        print(f"{campo}: {valor}")
                                else:
                                    print(f"{campo}: {valor}")
                        else:
                            print(f"Imóvel com ID {imovel_id} não encontrado.")
                else:
                    print(f"Nenhum imóvel encontrado para o domínio '{domain_name}'.")
                
    except sqlite3.Error as e:
        logger.error(f"Erro ao analisar imóveis: {e}")
    finally:
        conn.close()

def analisar_logs():
    """Analisa os logs do scraper para identificar padrões de erro"""
    log_arquivo = "logs/scrape.log"
    if not os.path.exists(log_arquivo):
        print(f"Arquivo de log {log_arquivo} não encontrado.")
        return
    
    print("\n=== ANÁLISE DE LOGS ===")
    
    erros = []
    captchas = []
    avisos = []
    
    with open(log_arquivo, 'r') as f:
        for linha in f:
            if "ERROR" in linha:
                erros.append(linha.strip())
            elif "CAPTCHA" in linha:
                captchas.append(linha.strip())
            elif "WARNING" in linha:
                avisos.append(linha.strip())
    
    print(f"Total de erros: {len(erros)}")
    print(f"Total de CAPTCHAs detectados: {len(captchas)}")
    print(f"Total de avisos: {len(avisos)}")
    
    if erros:
        # Agrupar erros por tipo
        erro_patterns = defaultdict(int)
        for erro in erros:
            # Extrair a mensagem de erro principal
            try:
                mensagem = erro.split(' - ')[-1]
                # Generalizar mensagens similares
                for pattern in ['Failed to process', 'Error parsing', 'Timeout', 'Connection']:
                    if pattern in mensagem:
                        erro_patterns[pattern] += 1
                        break
                else:
                    erro_patterns['Outros'] += 1
            except:
                erro_patterns['Não classificado'] += 1
        
        print("\nTipos de erros mais comuns:")
        for pattern, count in sorted(erro_patterns.items(), key=lambda x: x[1], reverse=True):
            print(f"- {pattern}: {count} ocorrências")
        
        # Mostrar alguns exemplos de erros
        if len(erros) > 0:
            print("\nExemplos de mensagens de erro:")
            for erro in erros[:5]:  # Mostrar os 5 primeiros erros
                print(f"- {erro}")
            if len(erros) > 5:
                print(f"... e mais {len(erros) - 5} erros.")

def main():
    """Função principal"""
    parser = argparse.ArgumentParser(description='Ferramenta de diagnóstico para o scraper de leilões')
    
    parser.add_argument('--analise', choices=['seletores', 'imoveis', 'logs', 'tudo'],
                        default='tudo', help='Tipo de análise a realizar')
    
    args = parser.parse_args()
    
    # Verificar se o banco de dados existe
    if not os.path.exists('auctions.db'):
        print("Banco de dados 'auctions.db' não encontrado.")
        sys.exit(1)
    
    # Criar diretório de logs se não existir
    os.makedirs("logs", exist_ok=True)
    
    print("\n==== DIAGNÓSTICO DO SCRAPER DE LEILÕES ====")
    print(f"Data/hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if args.analise in ['seletores', 'tudo']:
        analisar_seletores_cache()
    
    if args.analise in ['imoveis', 'tudo']:
        analisar_imoveis()
    
    if args.analise in ['logs', 'tudo']:
        analisar_logs()
    
    print("\n==== FIM DO DIAGNÓSTICO ====")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nDiagnóstico interrompido pelo usuário.")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Erro durante o diagnóstico: {e}")
        print(f"\nErro durante o diagnóstico: {e}")
        sys.exit(1) 