"""
Script para buscar e extrair dados de sites de leilão de imóveis sem interação.
"""
import time
import sys
import logging
import dns.resolver
from urllib.parse import urlparse
from myproject.database.connection import get_session
from myproject.database.models import AuctionData, Base, engine
from myproject.google_search.search import get_auction_websites
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings
from myproject.spiders.auction_spider import AuctionSpider

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('logs/auction_scraper_noninteractive.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

def initialize_database():
    """
    Inicializa o banco de dados.
    """
    logger.info("Inicializando banco de dados...")
    Base.metadata.create_all(engine)

def check_dns_resolution(urls):
    """
    Verifica se os domínios dos URLs têm uma resolução DNS válida.
    """
    valid_urls = []
    
    for url in urls:
        try:
            domain = urlparse(url).netloc
            dns.resolver.resolve(domain, 'A')
            valid_urls.append(url)
        except Exception as e:
            logger.warning(f"Erro de resolução DNS para {url}: {str(e)}")
    
    return valid_urls

def display_latest_results():
    """
    Exibe os resultados mais recentes no banco de dados.
    """
    session = get_session()
    results = session.query(AuctionData).order_by(AuctionData.id.desc()).limit(5).all()
    
    if not results:
        print("\nNenhum resultado encontrado no banco de dados.")
        return
    
    print("\nResultados recentes:")
    for i, item in enumerate(results, 1):
        print(f"\n{i}. {item.title if item.title else 'Sem título'}")
        print(f"   Preço: {item.price if item.price else 'N/A'}")
        print(f"   Endereço: {item.address if item.address else 'N/A'}")
        print(f"   Tipo: {item.property_type if item.property_type else 'N/A'}")
        print(f"   Data Leilão: {item.auction_date if item.auction_date else 'N/A'}")
        print(f"   URL: {item.url}")
        if hasattr(item, 'screenshot_path') and item.screenshot_path:
            print(f"   Screenshot: {item.screenshot_path}")
    
    session.close()

def main(search_query):
    """
    Função principal que realiza a busca e scraping de sites de leilão.
    """
    initialize_database()
    
    logger.info(f"Buscando sites de leilão com termo: {search_query}")
    urls = get_auction_websites(search_query)
    
    print(f"Lista de sites encontrados: {len(urls)}")
    
    valid_urls = check_dns_resolution(urls)
    
    print("\nURLs válidos encontrados:")
    for i, url in enumerate(valid_urls, 1):
        print(f"{i}. {url}")
    
    if not valid_urls:
        print("Nenhum URL válido encontrado. Encerrando.")
        return
    
    print("\nIniciando processo de scraping...")
    
    settings = get_project_settings()
    process = CrawlerProcess(settings)
    process.crawl(AuctionSpider, start_urls=valid_urls)
    process.start()  # Bloqueia até que o scraping seja concluído
    
    # Exibe os resultados
    display_latest_results()
    
    print("\nProcesso concluído! Os dados foram salvos no banco de dados.")
    print("Use 'python -m myproject.tools.browse_data' para visualizar todos os resultados.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python fetch_and_scrape_noninteractive.py \"termo de busca\"")
        sys.exit(1)
    
    search_query = sys.argv[1]
    main(search_query) 