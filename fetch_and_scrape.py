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
    
    # Verifica argumentos da linha de comando
    depth = 2  # Profundidade padrão (2 = lista + detalhes)
    query = None
    max_items_per_site = 10  # Número máximo de itens por site

    # Processa argumentos da linha de comando
    if len(sys.argv) > 1:
        for arg in sys.argv[1:]:
            if arg.startswith("--depth="):
                try:
                    depth = int(arg.split("=")[1])
                except ValueError:
                    print(f"Valor inválido para profundidade: {arg}")
                    depth = 2
            elif arg.startswith("--max-items="):
                try:
                    max_items_per_site = int(arg.split("=")[1])
                except ValueError:
                    print(f"Valor inválido para max-items: {arg}")
            elif not arg.startswith("--"):
                query = arg
    
    # Lista de consultas em português para encontrar sites de leilão brasileiros
    queries = [
        "sites de leilão de imóveis",
        "leilão de imóveis brasil",
        "leilões judiciais de imóveis",
        "portais de leilão imobiliário",
        "plataformas de leilão de casas e apartamentos"
    ]
    
    # Se uma consulta específica foi fornecida, usa apenas ela
    if query:
        queries = [query]
    
    # Coleta URLs de todas as consultas e remove duplicatas
    all_urls = set()
    for query in queries:
        print(f"Buscando sites com a consulta: '{query}'")
        urls = get_auction_websites(query=query)
        all_urls.update(urls)
        print(f"Encontrados {len(urls)} sites")
    
    urls_list = list(all_urls)
    print(f"Total de {len(urls_list)} sites únicos encontrados")
    
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
    
    # Pergunta se o usuário deseja continuar com o scraping
    response = input("\nDeseja iniciar o processo de scraping? (s/n): ")
    if response.lower() != 's':
        print("Operação cancelada pelo usuário.")
        return
    
    print(f"\nIniciando processo de scraping com profundidade {depth} e máximo de {max_items_per_site} itens por site...")
    
    # Garante que o diretório de logs existe
    os.makedirs('logs', exist_ok=True)
    
    # Configurações do Scrapy
    settings = get_project_settings()
    settings.set('LOG_LEVEL', 'INFO')
    settings.set('LOG_FILE', 'logs/auction_scraper.log')
    
    # Explicitamente habilita o pipeline
    settings.set('ITEM_PIPELINES', {'myproject.pipelines.DatabasePipeline': 300})
    
    # Define a profundidade máxima de navegação (1=apenas páginas iniciais, 2=incluir páginas de detalhes)
    settings.set('DEPTH_LIMIT', depth)
    
    # Inicia o processo de scraping apenas com URLs válidos
    process = CrawlerProcess(settings)
    process.crawl(AuctionSpider, start_urls=valid_urls, max_items_per_site=max_items_per_site)
    process.start()  # Este método bloqueia até que o scraping seja concluído
    
    # Exibe os resultados mais recentes
    show_latest_results()
    
    print("\nProcesso concluído! Os dados foram salvos no banco de dados.")
    print("Use 'python -m myproject.tools.browse_data' para visualizar todos os resultados.")
    
    print(f"\nDicas de uso avançado:")
    print(f"  - Para definir a profundidade de scraping: python fetch_and_scrape.py --depth=3")
    print(f"  - Para limitar o número de itens por site: python fetch_and_scrape.py --max-items=20")
    print(f"  - Para usar uma consulta específica: python fetch_and_scrape.py \"leilões de fazendas\"")
    print(f"  - Combinando opções: python fetch_and_scrape.py \"leilões de fazendas\" --depth=3 --max-items=20")

if __name__ == '__main__':
    main()