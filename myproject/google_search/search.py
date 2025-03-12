from googleapiclient.discovery import build
from myproject.config import GOOGLE_API_KEY, GOOGLE_CSE_ID
import logging

# Configuração de logging
logger = logging.getLogger(__name__)

def get_auction_websites(query="sites de leilão de imóveis", max_results=50):
    """
    Obtém websites de leilão de imóveis usando a API do Google Custom Search.
    
    Args:
        query: Consulta de pesquisa em português (padrão: "sites de leilão de imóveis")
        max_results: Número máximo de resultados a serem retornados (padrão: 50)
        
    Returns:
        Lista de URLs de sites de leilão de imóveis
    """
    service = build("customsearch", "v1", developerKey=GOOGLE_API_KEY)
    
    # Parâmetros adicionais para restringir os resultados ao Brasil:
    # cr=countryBR - Restringe os resultados ao Brasil
    # gl=br - Define a geolocalização como Brasil para melhorar a relevância dos resultados
    # hl=pt-BR - Define o idioma da interface como português do Brasil
    
    # Coletando resultados em lotes de 10
    batch_size = 10
    all_urls = []
    unique_domains = set()
    
    # Calcula o número de lotes necessários
    num_batches = min(5, max_results // batch_size)  # No máximo 5 lotes (50 resultados)
    
    logger.info(f"Buscando até {max_results} sites com a consulta: '{query}'")
    
    for batch in range(num_batches):
        start_index = (batch * batch_size) + 1  # API do Google usa índice 1-based
        
        try:
            logger.info(f"Buscando lote {batch+1}/{num_batches} (resultados {start_index}-{start_index+batch_size-1})")
            
            res = service.cse().list(
                q=query, 
                cx=GOOGLE_CSE_ID, 
                num=batch_size,
                start=start_index,
                cr="countryBR",  # Restringe ao Brasil
                gl="br",         # Geolocalização para o Brasil
                hl="pt-BR"       # Idioma português do Brasil
            ).execute()
            
            # Verificação para caso não haja mais resultados
            if 'items' not in res:
                logger.info(f"Nenhum resultado adicional encontrado no lote {batch+1}")
                break
                
            batch_urls = [item['link'] for item in res['items']]
            logger.info(f"Encontrados {len(batch_urls)} URLs no lote {batch+1}")
            
            # Adiciona URLs à lista, evitando duplicatas de domínio
            for url in batch_urls:
                from urllib.parse import urlparse
                domain = urlparse(url).netloc
                
                # Se ainda não temos muitos URLs, permite alguns domínios duplicados
                if domain not in unique_domains or len(all_urls) < max_results // 2:
                    all_urls.append(url)
                    unique_domains.add(domain)
            
            # Se já temos resultados suficientes, para a busca
            if len(all_urls) >= max_results:
                break
                
        except Exception as e:
            logger.error(f"Erro ao buscar lote {batch+1}: {str(e)}")
            # Continua com o próximo lote em caso de erro
    
    logger.info(f"Busca concluída. Encontrados {len(all_urls)} URLs únicos de {len(unique_domains)} domínios diferentes")
    
    # Retorna no máximo max_results URLs
    return all_urls[:max_results]