BOT_NAME = 'myproject'

SPIDER_MODULES = ['myproject.spiders']
NEWSPIDER_MODULE = 'myproject.spiders'

# User agent comum para evitar bloqueios
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'

# Respeita robots.txt - pode ser desativado se necessário
ROBOTSTXT_OBEY = True

# Pipeline para salvar os dados no banco
ITEM_PIPELINES = {
    'myproject.pipelines.DatabasePipeline': 300,
}

# Configurações de desempenho e anti-bloqueio
DOWNLOAD_DELAY = 1.5  # Delay entre requisições para o mesmo domínio
DOWNLOAD_TIMEOUT = 30  # Timeout para requisições
CONCURRENT_REQUESTS_PER_DOMAIN = 4  # Limita requisições por domínio
CONCURRENT_REQUESTS = 16  # Máximo de requisições simultâneas

# Retry e tratamento de erros
RETRY_ENABLED = True
RETRY_TIMES = 3  # Máximo de retentativas
RETRY_HTTP_CODES = [500, 502, 503, 504, 408, 429]  # Códigos para retentativa

# Cache
HTTPCACHE_ENABLED = True
HTTPCACHE_EXPIRATION_SECS = 86400  # 24 horas
HTTPCACHE_IGNORE_HTTP_CODES = [403, 404, 500, 502, 503]

# Cookies e cabeçalhos
COOKIES_ENABLED = True  # Habilita cookies para sites que exigem
DEFAULT_REQUEST_HEADERS = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
}

# Logging
LOG_LEVEL = 'INFO'
LOG_FILE = 'auction_scraper.log'
LOG_STDOUT = False

# Desativa o log de requests e responses HTTP
LOG_FORMAT = '%(asctime)s [%(name)s] %(levelname)s: %(message)s'
LOG_SHORT_NAMES = True

# Desativa o log de headers e bodies HTTP
DUPEFILTER_DEBUG = False
LOG_HTTP_HEADERS = False
LOG_HTTP_BODIES = False

# Middleware personalizado para rotação de User-Agent
DOWNLOADER_MIDDLEWARES = {
    'scrapy.downloadermiddlewares.useragent.UserAgentMiddleware': None,
    'scrapy.downloadermiddlewares.retry.RetryMiddleware': 90,
    'scrapy.downloadermiddlewares.httpproxy.HttpProxyMiddleware': 110,
}