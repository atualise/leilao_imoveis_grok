from myproject.google_search.search import get_auction_websites
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings
from myproject.spiders.auction_spider import AuctionSpider
from myproject.database.models import Base, engine, AuctionData
import sys
import socket
import re
import os
from urllib.parse import urlparse
from datetime import datetime

def check_dns_resolution(url):
    """
    Verifica se o domínio de uma URL pode ser resolvido pelo DNS.
    
    Args:
        url: URL a ser verificada
        
    Returns:
        bool: True se o domínio for resolvido com sucesso, False caso contrário
    """
    try:
        # Extrai o domínio da URL
        domain = urlparse(url).netloc
        
        # Remove a porta se estiver presente
        domain = domain.split(':')[0]
        
        # Verifica se o domínio pode ser resolvido
        socket.gethostbyname(domain)
        return True
    except (socket.gaierror, UnicodeError):
        print(f"Aviso: Não foi possível resolver o domínio: {url}")
        return False

def show_latest_results(limit=5):
    """
    Mostra os resultados mais recentes do scraping.
    
    Args:
        limit: Número máximo de resultados a serem exibidos
    """
    from sqlalchemy.orm import sessionmaker
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        latest_items = session.query(AuctionData).order_by(
            AuctionData.extracted_at.desc()
        ).limit(limit).all()
        
        if not latest_items:
            print("\nNenhum resultado encontrado no banco de dados.")
            return
        
        print(f"\n=== {len(latest_items)} RESULTADOS MAIS RECENTES ===")
        for i, item in enumerate(latest_items, 1):
            print(f"\n--- Item {i} ---")
            print(f"Título: {item.title}")
            print(f"Preço: {item.price}")
            print(f"Endereço: {item.address or 'Não disponível'}")
            print(f"Tipo: {item.property_type or 'Não especificado'}")
            print(f"Data do Leilão: {item.auction_date or 'Não especificada'}")
            print(f"URL: {item.url}")
            print(f"Extraído em: {item.extracted_at.strftime('%d/%m/%Y %H:%M')}")
    finally:
        session.close()

def main():
    # Cria as tabelas do banco de dados (incluindo as novas)
    print("Inicializando banco de dados...")
    Base.metadata.create_all(engine)
    
    # Lista de sites de leilão conhecidos
    urls_list = [
        "https://www.megaleiloes.com.br/",
        "https://www.leilaovip.com.br/",
        "https://www.portalzuk.com.br/"
    ]
    
    print(f"Lista de sites para teste: {len(urls_list)}")
    
    # Filtra URLs com problemas de DNS
    valid_urls = [url for url in urls_list if check_dns_resolution(url)]
    filtered_count = len(urls_list) - len(valid_urls)
    
    if filtered_count > 0:
        print(f"\nRemovidos {filtered_count} sites com problemas de resolução de DNS")
    
    if not valid_urls:
        print("Nenhum site válido encontrado. Verifique sua conexão com a internet ou tente outras consultas.")
        return
    
    # Exibe os URLs válidos para referência
    print("\nURLs válidos encontrados:")
    for i, url in enumerate(valid_urls, 1):
        print(f"{i}. {url}")
    
    print("\nIniciando processo de scraping...")
    
    # Garante que o diretório de logs existe
    os.makedirs('logs', exist_ok=True)
    
    # Configurações do Scrapy
    settings = get_project_settings()
    settings.set('LOG_LEVEL', 'DEBUG')  # Debug para ver mais detalhes
    settings.set('LOG_FILE', 'logs/auction_scraper_test.log')
    
    # Explicitamente habilita o pipeline
    settings.set('ITEM_PIPELINES', {'myproject.pipelines.DatabasePipeline': 300})
    
    # Inicia o processo de scraping apenas com URLs válidos
    process = CrawlerProcess(settings)
    process.crawl(AuctionSpider, start_urls=valid_urls)
    process.start()  # Este método bloqueia até que o scraping seja concluído
    
    # Exibe os resultados mais recentes
    show_latest_results()
    
    print("\nProcesso concluído! Os dados foram salvos no banco de dados.")
    print("Use 'python -m myproject.tools.browse_data' para visualizar todos os resultados.")

if __name__ == '__main__':
    main() 