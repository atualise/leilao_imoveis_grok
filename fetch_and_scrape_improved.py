#!/usr/bin/env python3
import sys
import os
import logging
import time
import argparse
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings
from myproject.google_search.search import get_auction_websites as search_auction_sites
from myproject.database.connection import get_session
from init_db import initialize_database
from myproject.database.models import AuctionData
from myproject.spiders.auction_spider import AuctionSpider

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/auction_scraper_improved.log"),
        logging.StreamHandler(sys.stdout)
    ]
)

# Reduzir verbosidade de bibliotecas externas
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("selenium").setLevel(logging.WARNING)
logging.getLogger("scrapy").setLevel(logging.WARNING)
logging.getLogger("filelock").setLevel(logging.WARNING)
logging.getLogger("asyncio").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

def check_dns_resolution(urls):
    """
    Verifica se os URLs têm resolução DNS válida.
    Retorna apenas URLs válidos.
    """
    import socket
    from urllib.parse import urlparse
    
    valid_urls = []
    for url in urls:
        try:
            domain = urlparse(url).netloc
            socket.gethostbyname(domain)
            valid_urls.append(url)
            logger.info(f"DNS válido para: {url}")
        except socket.gaierror:
            logger.warning(f"Não foi possível resolver DNS para: {url}")
    
    return valid_urls

def display_latest_results(limit=5):
    """
    Exibe os resultados mais recentes do banco de dados.
    """
    import re
    
    # Função para limpar tags HTML
    def clean_html(text):
        if not text:
            return ''
        # Remove tags HTML
        clean = re.sub(r'<[^>]+>', '', text)
        # Remove espaços extras
        clean = re.sub(r'\s+', ' ', clean).strip()
        return clean
    
    session = get_session()
    results = session.query(AuctionData).order_by(AuctionData.extracted_at.desc()).limit(limit).all()
    
    if not results:
        print("\nNenhum resultado encontrado no banco de dados.")
        return
    
    print(f"\n=== {len(results)} Resultados Mais Recentes ===")
    for i, result in enumerate(results, 1):
        print(f"\n--- Resultado {i} ---")
        print(f"Título: {clean_html(result.title)}")
        print(f"Preço: {clean_html(result.price)}")
        print(f"Endereço: {clean_html(result.address)}")
        print(f"Tipo: {clean_html(result.property_type)}")
        print(f"Data do Leilão: {clean_html(result.auction_date)}")
        print(f"URL: {result.url}")
        if result.screenshot_path:
            print(f"Screenshot: {result.screenshot_path}")
    
    print("\n=== Fim dos Resultados ===")

def parse_args():
    """
    Processa os argumentos de linha de comando.
    """
    parser = argparse.ArgumentParser(description='Web scraper para sites de leilão de imóveis')
    parser.add_argument('search_term', nargs='?', default="leilão imóveis", 
                        help='Termo de busca para encontrar sites de leilão')
    parser.add_argument('--depth', type=int, default=2, 
                        help='Profundidade de navegação (1=apenas lista, 2=lista+detalhes, 3+=paginação/categorias)')
    parser.add_argument('--max-items', type=int, default=5, 
                        help='Número máximo de itens para extrair por site')
    parser.add_argument('--debug', action='store_true', 
                        help='Ativar modo de depuração com logs mais detalhados')
    
    return parser.parse_args()

def main():
    """
    Função principal que executa o scraper.
    """
    # Processa argumentos de linha de comando
    args = parse_args()
    
    # Configura logging adicional se modo debug estiver ativado
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logging.getLogger("scrapy").setLevel(logging.INFO)
        logger.debug("Modo de depuração ativado")
    
    # Cria o diretório de logs se não existir
    os.makedirs("logs", exist_ok=True)
    
    # Cria o diretório de prints se não existir
    os.makedirs("prints", exist_ok=True)
    
    # Inicializa o banco de dados
    initialize_database()
    logger.info("Banco de dados inicializado")
    
    # Define o termo de busca a partir dos argumentos
    search_term = args.search_term
    logger.info(f"Buscando sites de leilão com o termo: {search_term}")
    
    # Busca sites de leilão
    urls = search_auction_sites(search_term)
    logger.info(f"Encontrados {len(urls)} sites de leilão")
    
    # Verifica resolução DNS
    valid_urls = check_dns_resolution(urls)
    logger.info(f"URLs válidos para scraping: {len(valid_urls)}")
    
    if not valid_urls:
        logger.error("Nenhum URL válido encontrado para scraping")
        return
    
    # Exibe os URLs que serão processados
    print("\nURLs que serão processados:")
    for i, url in enumerate(valid_urls, 1):
        print(f"{i}. {url}")
    
    print(f"\nProfundidade de navegação: {args.depth} (1=lista, 2=lista+detalhes)")
    print(f"Itens máximos por site: {args.max_items}")
    confirmation = input("\nDeseja continuar? (s/n): ")
    
    if confirmation.lower() != 's':
        print("Operação cancelada pelo usuário.")
        return
    
    # Configura e inicia o crawler
    settings = get_project_settings()
    
    # Garante que o pipeline está ativado
    settings.set('ITEM_PIPELINES', {
        'myproject.pipelines.DatabasePipeline': 300,
    })
    
    # Define a profundidade explicitamente
    settings.set('DEPTH_LIMIT', args.depth)
    settings.set('DEPTH_STATS', True)
    settings.set('DEPTH_PRIORITY', 1)  # Prioridade para navegação em profundidade (DFS)
    
    # Configura o processo do crawler
    process = CrawlerProcess(settings)
    
    # Adiciona o spider ao processo
    logger.info(f"Configurando spider com profundidade {args.depth} e max_items={args.max_items}")
    process.crawl(
        AuctionSpider, 
        start_urls=valid_urls, 
        max_items_per_site=args.max_items,
        config_depth=args.depth  # Passa a profundidade para o spider também
    )
    
    # Inicia o processo de scraping
    logger.info("Iniciando o processo de scraping")
    process.start()
    
    # Exibe os resultados mais recentes
    logger.info("Scraping concluído, exibindo resultados")
    display_latest_results()
    
    logger.info("Dados salvos no banco de dados. Use a ferramenta de visualização para ver os resultados.")
    print("\nDados salvos no banco de dados. Use a ferramenta de visualização para ver os resultados.")

if __name__ == "__main__":
    main() 