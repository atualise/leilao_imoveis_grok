import scrapy
from urllib.parse import urlparse
import json
import logging
import re
import time
from datetime import datetime
from urllib.parse import urljoin
import traceback
from myproject.llm.api import call_llm_api, parse_llm_response, LlmApi
from myproject.database.connection import get_session
from myproject.database.models import ScrapingRule, ProblemSite, SelectorCache
from myproject.items import AuctionItem
from myproject.utils.screenshot import capture_property_screenshot
import os
from selenium import webdriver
import glob
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from PIL import Image

class AuctionSpider(scrapy.Spider):
    name = 'auction'
    
    # Define limites e configurações para evitar sobrecarregar servidores
    custom_settings = {
        'CONCURRENT_REQUESTS': 4,  # Limita o número de requisições simultâneas
        'DOWNLOAD_TIMEOUT': 30,    # Timeout em segundos
        'RETRY_TIMES': 2,          # Número de tentativas de retry
        'ROBOTSTXT_OBEY': True,    # Respeita o robots.txt
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',  # User agent mais comum
        'ITEM_PIPELINES': {
            'myproject.pipelines.DatabasePipeline': 300,
        }
    }

    def __init__(self, start_urls=None, max_items_per_site=10, config_depth=2, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.start_urls = start_urls or []
        self.max_items_per_site = int(max_items_per_site)
        self.config_depth = int(config_depth)  # Salva a profundidade configurada
        self.session = get_session()
        self.logger.setLevel(logging.INFO)
        
        # Contadores para limitar o número de itens por site
        self.items_count = {}
        
        # Inicializa a API do LLM
        from myproject.llm.api import LlmApi
        self.llm_api = LlmApi()
        
        self.logger.info(f"Spider inicializado com {len(self.start_urls)} URLs, limite de {self.max_items_per_site} itens por site e profundidade {self.config_depth}")
        
    def start_requests(self):
        """
        Inicia as requisições e adiciona tratamento de erros.
        Também verifica se o site está na lista de sites problemáticos.
        """
        # Verifica se há respostas de CAPTCHA pendentes
        self._check_captcha_responses()
        
        for url in self.start_urls:
            try:
                # Extrai o domínio para contagem
                domain = urlparse(url).netloc
                
                # Inicializa o contador para este domínio
                if domain not in self.items_count:
                    self.items_count[domain] = 0
                
                # Verifica se o site está na lista de problemáticos
                problem_site = self.session.query(ProblemSite).filter_by(domain=domain).first()
                
                if problem_site and problem_site.attempts > 3:
                    self.logger.warning(f"Pulando site problemático: {url} (falhou {problem_site.attempts} vezes)")
                    continue
                    
                # Verifica se temos cookies salvos para este domínio
                cookies_file = os.path.join('cookies', f"{domain.replace('.', '_')}_cookies.json")
                cookies = None
                
                if os.path.exists(cookies_file):
                    try:
                        with open(cookies_file, 'r') as f:
                            cookies = json.load(f)
                        self.logger.info(f"Usando cookies salvos para {domain} de {cookies_file}")
                    except Exception as e:
                        self.logger.error(f"Erro ao carregar cookies de {cookies_file}: {str(e)}")
                
                self.logger.info(f"Processando URL: {url}")
                
                # Prepara os metadados da requisição
                meta = {
                    'handle_httpstatus_list': [403, 404, 500, 502, 503],
                    'dont_retry': False,
                    'download_timeout': 30,
                    'domain': domain
                }
                
                # Adiciona o caminho do arquivo de cookies se disponível
                if cookies:
                    meta['manual_cookies'] = True
                    meta['cookies_file'] = cookies_file
                
                yield scrapy.Request(
                    url=url, 
                    callback=self.parse,
                    errback=self.errback_httpbin,
                    cookies=cookies,  # Usa os cookies se disponíveis
                    meta=meta
                )
            except Exception as e:
                self.logger.error(f"Erro ao iniciar requisição para {url}: {str(e)}")
                self._register_problem_site(urlparse(url).netloc, str(e))
                
    def _check_captcha_responses(self):
        """
        Verifica se há respostas de CAPTCHA pendentes e as processa.
        """
        try:
            # Procura por arquivos de resposta
            response_files = glob.glob(os.path.join('cookies', '*_response.json'))
            
            for response_file in response_files:
                try:
                    with open(response_file, 'r') as f:
                        response_data = json.load(f)
                    
                    # Verifica o formato dos dados carregados
                    if isinstance(response_data, list):
                        # Se for uma lista de cookies, salva diretamente
                        domain = self._extract_domain_from_filename(response_file)
                        if domain:
                            cookies_file = os.path.join('cookies', f"{domain}_cookies.json")
                            with open(cookies_file, 'w') as f:
                                json.dump(response_data, f, indent=2)
                            self.logger.info(f"Cookies processados para {domain} e salvos em {cookies_file}")
                    elif isinstance(response_data, dict):
                        # Verifica se a resposta já foi processada
                        if response_data.get('status') == 'processed':
                            continue
                            
                        # Verifica se a resposta foi completada
                        if response_data.get('status') == 'completed':
                            url = response_data.get('url')
                            cookies = response_data.get('cookies')
                            
                            if url and cookies:
                                domain = urlparse(url).netloc
                                
                                # Salva os cookies permanentemente
                                cookies_file = os.path.join('cookies', f"{domain.replace('.', '_')}_cookies.json")
                                with open(cookies_file, 'w') as f:
                                    json.dump(cookies, f, indent=2)
                                
                                self.logger.info(f"Cookies processados para {url} e salvos em {cookies_file}")
                                
                                # Marca a resposta como processada
                                response_data['status'] = 'processed'
                                with open(response_file, 'w') as f:
                                    json.dump(response_data, f, indent=2)
                    else:
                        self.logger.warning(f"Formato de dados desconhecido no arquivo {response_file}")
                        
                except Exception as e:
                    self.logger.error(f"Erro ao processar arquivo de resposta {response_file}: {str(e)}")
                    
        except Exception as e:
            self.logger.error(f"Erro ao verificar respostas de CAPTCHA: {str(e)}")
            
    def _extract_domain_from_filename(self, filename):
        """
        Extrai o domínio do nome do arquivo de resposta.
        Exemplo: cookies/www_example_com_20250311_124720_response.json -> www_example_com
        """
        try:
            basename = os.path.basename(filename)
            # Remove a extensão e o sufixo _response
            parts = basename.replace('_response.json', '').split('_')
            
            # Os timestamps geralmente têm 8 dígitos para a data e 6 para a hora
            # Vamos remover esses elementos se existirem
            filtered_parts = []
            for part in parts:
                if not (len(part) == 8 and part.isdigit()) and not (len(part) == 6 and part.isdigit()):
                    filtered_parts.append(part)
            
            # Junta as partes restantes para formar o domínio
            domain = '_'.join(filtered_parts)
            return domain
        except Exception as e:
            self.logger.error(f"Erro ao extrair domínio do arquivo {filename}: {str(e)}")
            return None

    def errback_httpbin(self, failure):
        """
        Manipula erros durante as requisições.
        """
        # Extrai o objeto de requisição original
        request = failure.request
        url = request.url
        domain = urlparse(url).netloc
        
        self.logger.error(f"Erro ao processar {url}: {repr(failure)}")
        self._register_problem_site(domain, repr(failure))

    def _register_problem_site(self, domain, error_message):
        """
        Registra um site problemático no banco de dados
        """
        try:
            problem_site = self.session.query(ProblemSite).filter_by(domain=domain).first()
            
            if problem_site:
                problem_site.attempts += 1
                problem_site.last_error = error_message
            else:
                problem_site = ProblemSite(domain=domain, attempts=1, last_error=error_message)
                self.session.add(problem_site)
                
            self.session.commit()
        except Exception as e:
            self.logger.error(f"Erro ao registrar site problemático: {str(e)}")

    def _detect_page_type(self, html_content, url):
        """
        Detecta se uma página é uma listagem ou uma página de detalhes
        baseado em padrões comuns encontrados em sites de leilão.
        
        Args:
            html_content: Conteúdo HTML da página
            url: URL da página
            
        Returns:
            str: 'list' ou 'detail'
        """
        # Verifica se o conteúdo HTML é válido
        if not html_content or not isinstance(html_content, str):
            self.logger.warning(f"Conteúdo HTML inválido para {url}")
            return 'list'  # Valor padrão seguro
            
        # Padrões comuns em URLs de páginas de detalhe
        detail_url_patterns = [
            r'/imovel/\d+', r'/detalhe', r'/detalhes', r'/item/\d+', r'/lote/\d+',
            r'/auction/\d+', r'/leilao/\d+', r'/lance/\d+', r'/bem/\d+',
            r'/property/\d+', r'/ficha', r'/info', r'/produto/\d+',
            r'/imovel-', r'/lote-', r'/bem-', r'/propriedade-', r'/id-\d+',
            r'/codigo-\d+', r'/ref-\d+', r'/oferta/\d+', r'/oportunidade/\d+'
        ]
        
        # Verifica se a URL parece ser de uma página de detalhes
        for pattern in detail_url_patterns:
            if re.search(pattern, url):
                self.logger.info(f"URL {url} corresponde ao padrão de detalhe: {pattern}")
                return 'detail'
        
        # Padrões comuns em conteúdo HTML de páginas de listagem
        list_patterns = [
            r'class=".*?lista.*?"', r'class=".*?grid.*?"', r'class=".*?results.*?"',
            r'class=".*?catalog.*?"', r'class=".*?listing.*?"', r'class=".*?search.*?results.*?"',
            r'class=".*?cards.*?"', r'class=".*?properties.*?"', r'class=".*?imoveis.*?"',
            r'<div[^>]*id=".*?lista.*?"', r'<div[^>]*id=".*?grid.*?"', r'<div[^>]*id=".*?results.*?"',
            r'class=".*?pagination.*?"', r'class=".*?paginacao.*?"', r'class=".*?pages.*?"',
            r'class=".*?resultados.*?"', r'class=".*?busca.*?"', r'class=".*?search.*?"'
        ]
        
        # Padrões comuns em conteúdo HTML de páginas de detalhes
        detail_patterns = [
            r'class=".*?detalhe.*?"', r'class=".*?produto.*?"', r'class=".*?imovel.*?info.*?"',
            r'<h1.*?>.*?</h1>', r'class=".*?price.*?"', r'class=".*?valor.*?"',
            r'class=".*?property.*?detail.*?"', r'class=".*?auction-details.*?"',
            r'class=".*?product-info.*?"', r'class=".*?item-detail.*?"',
            r'<div[^>]*id=".*?detalhe.*?"', r'<div[^>]*id=".*?produto.*?"',
            r'class=".*?caracteristicas.*?"', r'class=".*?especificacoes.*?"',
            r'class=".*?ficha.*?tecnica.*?"', r'class=".*?descricao.*?imovel.*?"',
            r'class=".*?galeria.*?"', r'class=".*?gallery.*?"', r'class=".*?fotos.*?"',
            r'class=".*?lances.*?"', r'class=".*?ofertas.*?"', r'class=".*?bid.*?"'
        ]
        
        # Usa try/except para evitar erros em expressões regulares com conteúdo inválido
        try:
            # Conta quantos padrões de cada tipo foram encontrados
            list_matches = sum(1 for pattern in list_patterns if re.search(pattern, html_content, re.IGNORECASE))
            detail_matches = sum(1 for pattern in detail_patterns if re.search(pattern, html_content, re.IGNORECASE))
            
            # Verifica se há elementos que indicam uma página de detalhes
            has_price_element = bool(re.search(r'R\$\s*[\d\.,]+', html_content))
            has_property_details = bool(re.search(r'(área|area)\s*:?\s*\d+\s*(m²|m2)', html_content, re.IGNORECASE))
            has_auction_date = bool(re.search(r'(data\s*do\s*leilão|leilão\s*em|data\s*:)', html_content, re.IGNORECASE))
            
            # Adiciona pontos extras para elementos específicos de páginas de detalhes
            if has_price_element:
                detail_matches += 2
            if has_property_details:
                detail_matches += 2
            if has_auction_date:
                detail_matches += 2
            
            # Verifica se há múltiplos cards/itens na página (indicativo de listagem)
            multiple_items_pattern = r'(<div[^>]*class="[^"]*(?:card|item|produto|imovel|property)[^"]*".*?){3,}'
            has_multiple_items = bool(re.search(multiple_items_pattern, html_content, re.DOTALL | re.IGNORECASE))
            
            if has_multiple_items:
                list_matches += 3  # Dá mais peso para múltiplos itens
            
            # Verifica se há paginação (indicativo de listagem)
            pagination_pattern = r'class="[^"]*(?:pag(?:ination|inacao|e)|pages|numeros)[^"]*"'
            has_pagination = bool(re.search(pagination_pattern, html_content, re.IGNORECASE))
            
            if has_pagination:
                list_matches += 2
                
            # Verifica se há elementos de navegação entre resultados (indicativo de listagem)
            navigation_pattern = r'(?:próxima|proxima|próximo|proximo|anterior|seguinte|next|prev|previous)'
            has_navigation = bool(re.search(navigation_pattern, html_content, re.IGNORECASE))
            
            if has_navigation:
                list_matches += 1
                
            # Verifica se há elementos de filtro ou ordenação (indicativo de listagem)
            filter_pattern = r'(?:filtrar|ordenar|filtros|filtro por|ordernar por|classificar)'
            has_filters = bool(re.search(filter_pattern, html_content, re.IGNORECASE))
            
            if has_filters:
                list_matches += 1
                
            # Verifica se há elementos de compartilhamento ou contato (indicativo de detalhes)
            share_pattern = r'(?:compartilhar|compartilhe|enviar|contato|contate|whatsapp|email|telefone)'
            has_share = bool(re.search(share_pattern, html_content, re.IGNORECASE))
            
            if has_share:
                detail_matches += 1
                
            # Verifica se há elementos de galeria de imagens (indicativo de detalhes)
            gallery_pattern = r'(?:galeria|slideshow|carrossel|carousel|slider|slide)'
            has_gallery = bool(re.search(gallery_pattern, html_content, re.IGNORECASE))
            
            if has_gallery:
                detail_matches += 1
            
            # Se encontrou mais padrões de detalhe que de lista, considera página de detalhe
            self.logger.info(f"Análise de página para {url}: list_matches={list_matches}, detail_matches={detail_matches}")
            
            if detail_matches > list_matches:
                return 'detail'
            else:
                return 'list'
        except Exception as e:
            self.logger.error(f"Erro ao analisar padrões HTML para {url}: {str(e)}")
            return 'list'  # Valor padrão seguro

    def _is_text_response(self, response):
        """
        Verifica se a resposta é texto e não um binário.
        """
        try:
            # Verifica o Content-Type no cabeçalho
            content_type = response.headers.get('Content-Type', b'').decode('utf-8', 'ignore').lower()
            
            # Tipos de conteúdo de texto comuns
            text_types = ['text/html', 'text/plain', 'application/json', 'application/xml', 
                         'text/xml', 'application/javascript', 'text/css']
            
            # Verifica se algum dos tipos de texto está no Content-Type
            is_text = any(text_type in content_type for text_type in text_types)
            
            # Tenta acessar o texto para confirmar (isso pode lançar uma exceção se não for texto)
            if is_text:
                # Apenas tenta acessar para ver se funciona, não armazena o resultado
                _ = response.text
                return True
            return False
        except AttributeError:
            # Se ocorrer um AttributeError, a resposta não é texto
            return False
        except Exception as e:
            self.logger.warning(f"Erro ao verificar se a resposta é texto: {str(e)}")
            return False

    def _is_captcha_page(self, response):
        """
        Detecta se a página atual contém um CAPTCHA ou mecanismo de verificação anti-bot.
        """
        # Verifica se a resposta é texto antes de tentar acessar o conteúdo
        if not self._is_text_response(response):
            return False
            
        # Busca por padrões comuns em páginas de CAPTCHA ou verificação
        captcha_patterns = [
            'captcha', 'recaptcha', 'validate', 'verification', 
            'robot', 'human', 'bot check', 'security check',
            'perfdrive', 'cloudflare', 'ddos', 'protection',
            'verify you are human'
        ]
        
        # Verifica no HTML e URL
        page_text = response.text.lower()
        url_text = response.url.lower()
        
        # Verifica se algum padrão está presente
        for pattern in captcha_patterns:
            if pattern in page_text or pattern in url_text:
                return True
                
        # Verifica elementos específicos de CAPTCHA
        captcha_selectors = [
            'iframe[src*="captcha"]', 
            'iframe[src*="recaptcha"]',
            'div.g-recaptcha',
            'div[class*="captcha"]',
            'input[name*="captcha"]'
        ]
        
        for selector in captcha_selectors:
            if response.css(selector):
                return True
                
        return False
        
    def _handle_captcha(self, response):
        """
        Manipula páginas de CAPTCHA, salvando informações para resolução manual.
        """
        url = response.url
        domain = urlparse(url).netloc
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        domain_safe = domain.replace('.', '_')
        
        # Cria o diretório de cookies se não existir
        os.makedirs('cookies', exist_ok=True)
        
        # Cria o diretório de prints se não existir
        os.makedirs('prints', exist_ok=True)
        
        # Salva um screenshot da página de CAPTCHA
        screenshot_path = os.path.join('prints', f"{domain_safe}_{timestamp}_captcha.png")
        
        try:
            # Captura um screenshot da página de CAPTCHA
            self._take_screenshot(url, screenshot_path)
            
            # Salva informações sobre a requisição para resolução manual
            request_file = os.path.join('cookies', f"{domain_safe}_{timestamp}_request.json")
            with open(request_file, 'w') as f:
                json.dump({
                    'url': url,
                    'domain': domain,
                    'timestamp': timestamp,
                    'screenshot_path': screenshot_path
                }, f, indent=2)
                
            # Cria um arquivo de resposta vazio para ser preenchido manualmente
            response_file = os.path.join('cookies', f"{domain_safe}_{timestamp}_response.json")
            with open(response_file, 'w') as f:
                json.dump({
                    'status': 'pending',
                    'url': url,
                    'timestamp': timestamp
                }, f, indent=2)
                
            # Exibe instruções para o usuário
            print("\n" + "="*80)
            print(f"CAPTCHA detectado na URL: {url}")
            print(f"Screenshot salvo em: {screenshot_path}")
            print("\nPor favor, siga as instruções abaixo para resolver o CAPTCHA manualmente:")
            print("1. Abra a URL acima em seu navegador")
            print("2. Complete a verificação CAPTCHA/desafio de segurança")
            print("3. Após completar a verificação, você tem duas opções:")
            print("   a) Salve os cookies (use extensões como 'Cookie-Editor') e cole-os no arquivo:")
            print(f"      {response_file}")
            print("   b) Ou execute o comando auxiliar:")
            print(f"      python3 submit_captcha_cookies.py {url}")
            print("4. O scraping continuará automaticamente após detectar o arquivo de resposta")
            print("="*80)
            
            # Aguarda um tempo para dar ao usuário a chance de ver as instruções
            self.logger.info(f"Aguardando resolução manual de CAPTCHA para {url}")
            
            # Retorna None para indicar que o CAPTCHA precisa ser resolvido manualmente
            return None
            
        except Exception as e:
            self.logger.error(f"Erro ao manipular CAPTCHA para {url}: {str(e)}")
            self._register_problem_site(domain, f"Erro ao manipular CAPTCHA: {str(e)}")
            return None
        
    def _take_screenshot(self, url, screenshot_path, cookies_file=None):
        """
        Captura um screenshot da página usando Selenium.
        """
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
        
        try:
            driver = webdriver.Chrome(options=options)
            driver.set_page_load_timeout(30)  # Timeout de 30 segundos
            
            # Primeiro acessa a página para poder definir cookies
            try:
                driver.get(url)
            except TimeoutException:
                self.logger.warning(f"Timeout ao carregar a página {url}, continuando mesmo assim")
            except WebDriverException as e:
                self.logger.error(f"Erro ao carregar a página {url}: {str(e)}")
                driver.quit()
                return
                
            # Aplica cookies se disponíveis
            if cookies_file and os.path.exists(cookies_file):
                try:
                    self.logger.info(f"Aplicando cookies do arquivo {cookies_file}")
                    with open(cookies_file, 'r') as f:
                        cookies = json.load(f)
                    self._apply_cookies_to_webdriver(driver, cookies)
                    
                    # Recarrega a página com os cookies aplicados
                    try:
                        driver.get(url)
                    except TimeoutException:
                        self.logger.warning(f"Timeout ao recarregar a página {url} com cookies, continuando mesmo assim")
                    except WebDriverException as e:
                        self.logger.error(f"Erro ao recarregar a página {url} com cookies: {str(e)}")
                        driver.quit()
                        return
                        
                    # Verifica se ainda estamos na página de CAPTCHA
                    page_source = driver.page_source.lower()
                    captcha_terms = ['captcha', 'robot', 'human verification', 'security check']
                    if any(term in page_source for term in captcha_terms):
                        self.logger.warning(f"Ainda na página de CAPTCHA mesmo com cookies aplicados: {url}")
                except Exception as e:
                    self.logger.error(f"Erro ao aplicar cookies de {cookies_file}: {str(e)}")
            
            # Aguarda um pouco para garantir que a página carregue completamente
            time.sleep(2)
            
            # Tenta rolar a página para garantir que todos os elementos sejam carregados
            try:
                # Rola até o final da página
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(1)
                # Rola de volta para o topo
                driver.execute_script("window.scrollTo(0, 0);")
                time.sleep(1)
            except Exception as e:
                self.logger.warning(f"Erro ao rolar a página {url}: {str(e)}")
            
            # Captura o screenshot
            driver.save_screenshot(screenshot_path)
            
            driver.quit()
        except Exception as e:
            self.logger.error(f"Erro ao capturar screenshot de {url}: {str(e)}")
            # Tenta criar um screenshot vazio para evitar erros posteriores
            try:
                img = Image.new('RGB', (1280, 720), color='white')
                img.save(screenshot_path)
                self.logger.warning(f"Criado screenshot vazio para {url} devido a erro")
            except Exception:
                self.logger.error(f"Não foi possível criar screenshot vazio para {url}")
                
    def _apply_cookies_to_webdriver(self, driver, cookies):
        """
        Aplica cookies ao webdriver.
        """
        if isinstance(cookies, list):
            for cookie in cookies:
                try:
                    # Verifica se o cookie tem os campos necessários
                    if 'name' in cookie and 'value' in cookie:
                        # Prepara o cookie para o formato do Selenium
                        cookie_dict = {
                            'name': cookie['name'],
                            'value': cookie['value'],
                            'domain': cookie.get('domain', ''),
                            'path': cookie.get('path', '/'),
                            'secure': cookie.get('secure', False),
                            'httpOnly': cookie.get('httpOnly', False)
                        }
                        
                        # Remove campos vazios ou None
                        cookie_dict = {k: v for k, v in cookie_dict.items() if v}
                        
                        # Adiciona o cookie
                        try:
                            driver.add_cookie(cookie_dict)
                        except Exception as e:
                            self.logger.warning(f"Erro ao adicionar cookie {cookie['name']}: {str(e)}")
                except Exception as e:
                    self.logger.warning(f"Erro ao processar cookie: {str(e)}")
        else:
            self.logger.warning(f"Formato de cookies inválido: {type(cookies)}")

    def parse(self, response):
        """
        Analisa a resposta e determina o tipo de página.
        """
        url = response.url
        domain = response.meta.get('domain') or urlparse(url).netloc
        self.logger.info(f"Analisando página: {url}")
        
        # Verifica limites de itens por site
        if self.items_count.get(domain, 0) >= self.max_items_per_site:
            self.logger.info(f"Limite de itens atingido para o domínio: {domain}")
            return
        
        # Verifica se é uma resposta de texto
        if not self._is_text_response(response):
            self.logger.warning(f"Resposta não é um texto para {url}")
            self._register_problem_site(domain, "Resposta não é texto")
            return
        
        # Verifica se é uma página de CAPTCHA
        if self._is_captcha_page(response) and not response.meta.get('manual_cookies'):
            self.logger.info(f"CAPTCHA detectado em {url}")
            captcha_request = self._handle_captcha(response)
            if captcha_request:
                yield captcha_request
            return
            
        # Continua com o processamento normal
        try:
            # Obtém a profundidade atual da navegação
            current_depth = response.meta.get('depth', 0)
            self.logger.info(f"Processando página com profundidade {current_depth}/{self.config_depth}")
            
            # Obtém o tipo de página atual do meta, se disponível
            current_page_type = response.meta.get('page_type', None)
            
            # Se não houver tipo definido, detecta o tipo de página
            if not current_page_type:
                # Detecta o tipo de página (lista ou detalhe)
                page_type = self._detect_page_type(response.text, url)
                self.logger.info(f"Tipo de página detectado para {url}: {page_type}")
                
                # Para URLs iniciais (Home), força reconhecimento como lista
                if current_depth == 0 and url in self.start_urls:
                    self.logger.info(f"URL inicial tratada como página HOME: {url}")
                    page_type = 'list'  # Consideramos a Home como uma listagem para seguir os links
            else:
                # Usa o tipo de página definido no meta
                page_type = current_page_type
                self.logger.info(f"Usando tipo de página definido no meta: {page_type}")
            
            # Verifica se atingiu a profundidade máxima configurada
            if current_depth >= self.config_depth:
                self.logger.info(f"Profundidade máxima atingida ({current_depth}/{self.config_depth}) para {url}")
                # Se for um detalhe na profundidade máxima, processa
                if page_type == 'detail' or response.meta.get('is_detail_page', False):
                    self.logger.info(f"Processando página de detalhes na profundidade máxima: {url}")
                    yield from self.parse_detail(response)
                return

            # Realiza o processamento com base no tipo de página
            if page_type == 'list':
                # Se estamos na profundidade máxima-1, só seguimos links para detalhes
                if current_depth == self.config_depth - 1:
                    self.logger.info(f"Na profundidade {current_depth}, buscando apenas links para páginas de detalhe")
                    only_detail_links = True
                else:
                    only_detail_links = False
                
                # Verifica se há seletores em cache para esta URL
                cached_selector = self._get_cached_selector(url, 'list')
                
                if cached_selector:
                    list_selector = cached_selector
                    self.logger.info(f"Usando seletor de lista em cache para {url}: {list_selector}")
                else:
                    # Se não há cache, verifica se há regra para o domínio
                    rule = self.session.query(ScrapingRule).filter_by(domain=domain).first()
                    
                    if rule and rule.list_selector:
                        list_selector = rule.list_selector
                        self.logger.info(f"Usando seletor de lista existente para {domain}: {list_selector}")
                    else:
                        self.logger.info(f"Gerando novo seletor de lista para {domain}")
                        list_selector = self._generate_list_selector(response)
                        
                        if list_selector:
                            # Salva o seletor para uso futuro
                            if rule:
                                rule.list_selector = list_selector
                            else:
                                rule = ScrapingRule(domain=domain, list_selector=list_selector)
                                self.session.add(rule)
                            self.session.commit()
                            
                            # Adiciona ao cache
                            self._cache_selector(url, domain, 'list', {'list_selector': list_selector})
                
                if list_selector:
                    # Extrai links de imóveis
                    links = []
                    # Se o seletor ainda for um dicionário (antigo cache), extrai o valor correto
                    if isinstance(list_selector, dict) and 'list_selector' in list_selector:
                        list_selector = list_selector['list_selector']
                        
                    # Tenta extrair links diretamente se o seletor já for um link
                    if isinstance(list_selector, str) and (list_selector.endswith('a') or 'a[' in list_selector or list_selector.endswith('a.')):
                        links = response.css(f"{list_selector}::attr(href)").getall()
                    # Caso contrário, procura por links dentro dos elementos selecionados
                    elif isinstance(list_selector, str):
                        links = response.css(f"{list_selector} a::attr(href)").getall()
                        # Se não encontrar links, tenta o seletor original com href
                        if not links:
                            links = response.css(f"{list_selector}::attr(href)").getall()
                    else:
                        self.logger.error(f"Tipo de seletor inválido para {url}: {type(list_selector)}")
                        return
                    
                    self.logger.info(f"Encontrados {len(links)} links de imóveis em {url}")
                    
                    # Atualiza a taxa de sucesso do seletor no cache
                    if links:
                        self._update_selector_success(url, True)
                    else:
                        self._update_selector_success(url, False)
                    
                    # Limita o número de links processados para não sobrecarregar
                    max_links = min(len(links), self.max_items_per_site * 2)  # Processamos mais links do que o limite para compensar possíveis falhas
                    self.logger.info(f"Processando até {max_links} links dos {len(links)} encontrados")
                    
                    # Filtra links duplicados
                    processed_links = set()
                    valid_links = []
                    detail_links = []
                    list_links = []
                    
                    for link in links[:max_links]:  # Limita o número de links para processar
                        if self.items_count.get(domain, 0) >= self.max_items_per_site:
                            self.logger.info(f"Limite de {self.max_items_per_site} itens atingido para {domain}")
                            break
                            
                        # Normaliza o link
                        full_url = urljoin(response.url, link)
                        
                        # Evita links duplicados
                        if full_url in processed_links:
                            continue
                        
                        processed_links.add(full_url)
                        
                        # Verifica se o link é do mesmo domínio
                        if urlparse(full_url).netloc == domain:
                            # Verifica se o link parece ser uma página de detalhes (usando padrões de URL)
                            is_detail_url = False
                            detail_url_patterns = [
                                r'/imovel/\d+', r'/detalhe', r'/detalhes', r'/item/\d+', r'/lote/\d+',
                                r'/auction/\d+', r'/leilao/\d+', r'/lance/\d+', r'/bem/\d+',
                                r'/property/\d+', r'/ficha', r'/info', r'/produto/\d+',
                                r'/imovel-', r'/lote-', r'/bem-', r'/propriedade-', r'/id-\d+',
                                r'/codigo-\d+', r'/ref-\d+', r'/oferta/\d+', r'/oportunidade/\d+'
                            ]
                            
                            for pattern in detail_url_patterns:
                                if re.search(pattern, full_url):
                                    is_detail_url = True
                                    break
                            
                            # Separa links de detalhe e de listagem
                            if is_detail_url:
                                detail_links.append(full_url)
                            elif not only_detail_links:  # Só adiciona links de listagem se não estivermos limitados a detalhes
                                list_links.append(full_url)
                    
                    # Prioriza links de detalhe se estamos prestes a atingir a profundidade máxima
                    if current_depth == self.config_depth - 1 or self.config_depth == 2:
                        valid_links = detail_links  # Só usa links de detalhe
                        self.logger.info(f"Usando apenas links de detalhe ({len(valid_links)}) na profundidade {current_depth}")
                    else:
                        # Combina os links, priorizando detalhes
                        valid_links = detail_links + list_links
                        self.logger.info(f"Combinando links: {len(detail_links)} de detalhe e {len(list_links)} de listagem")
                    
                    # Limita o número de links válidos ao máximo configurado
                    valid_links = valid_links[:self.max_items_per_site]
                    self.logger.info(f"Agendando {len(valid_links)} links válidos para processamento")
                    
                    # Processa os links válidos
                    for full_url in valid_links:
                        self.logger.info(f"Agendando requisição para: {full_url}")
                        
                        # Transfere cookies se disponíveis
                        cookies_meta = {}
                        if response.meta.get('manual_cookies'):
                            cookies_meta['manual_cookies'] = True
                            if response.meta.get('cookies_file'):
                                cookies_meta['cookies_file'] = response.meta.get('cookies_file')
                        
                        # Verifica se parece ser um link de detalhes
                        is_detail = full_url in detail_links
                        
                        # Se for um link de detalhes e estivermos na profundidade certa, usa parse_detail
                        # Caso contrário, usa parse normal para continuar a navegação
                        if is_detail and (current_depth == self.config_depth - 1 or self.config_depth == 2):
                            yield scrapy.Request(
                                url=full_url,
                                callback=self.parse_detail,  # Força o uso do parse_detail para garantir extração de dados
                                meta={
                                    'domain': domain, 
                                    'is_detail_page': True,  # Marca explicitamente como página de detalhes
                                    'page_type': 'detail',  # Define explicitamente o tipo de página
                                    'depth': current_depth + 1,  # Incrementa a profundidade
                                    **cookies_meta
                                }
                            )
                        else:
                            yield scrapy.Request(
                                url=full_url,
                                callback=self.parse,  # Usa o parse padrão para continuar navegando
                                meta={
                                    'domain': domain,
                                    'page_type': 'list' if not is_detail else 'detail',
                                    'depth': current_depth + 1,  # Incrementa a profundidade
                                    **cookies_meta
                                }
                            )
            elif page_type == 'detail':
                # Processa diretamente como página de detalhe
                self.logger.info(f"Processando {url} como página de detalhes")
                yield from self.parse_detail(response)
            else:
                self.logger.warning(f"Tipo de página não reconhecido para {url}")
                
        except Exception as e:
            self.logger.error(f"Erro ao processar {url}: {str(e)}")
            self.logger.error(traceback.format_exc())

    def _clean_html(self, text):
        """
        Remove tags HTML de um texto.
        """
        if not text:
            return ''
            
        # Padrão para encontrar tags HTML
        import re
        clean_text = re.sub(r'<[^>]+>', '', text)
        
        # Remove espaços extras
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()
        
        return clean_text
        
    def parse_detail(self, response):
        """
        Processa páginas de detalhes de imóveis.
        
        Args:
            response: Objeto de resposta do Scrapy
            
        Yields:
            AuctionItem: Item com os dados do imóvel
        """
        url = response.url
        domain = response.meta.get('domain') or urlparse(url).netloc
        self.logger.info(f"Analisando página de detalhes: {url} (domínio: {domain})")
        
        # Verifica se realmente parece ser uma página de detalhes usando a detecção
        is_marked_detail = response.meta.get('is_detail_page', False)
        
        if not is_marked_detail:
            # Só faz essa verificação se não foi explicitamente marcada como detalhe
            page_type = self._detect_page_type(response.text, url)
            if page_type != 'detail':
                self.logger.warning(f"Página {url} não parece ser uma página de detalhes. Detectado: {page_type}")
                # Se não for detalhes mas estiver em um nível de profundidade adequado, tenta processar como listagem
                current_depth = response.meta.get('depth', 1)
                if current_depth < self.config_depth:
                    self.logger.info(f"Tentando processar como listagem: {url}")
                    yield from self.parse(response)
                return
        
        if response.status == 403:
            self.logger.warning(f"Acesso proibido (403) para página de detalhes {url}")
            self._register_problem_site(domain, "HTTP 403 Forbidden")
            return
            
        if response.status != 200:
            self.logger.warning(f"Status não-200 para página de detalhes {url}: {response.status}")
            return
            
        # Verifica se o conteúdo é texto antes de tentar processá-lo
        if not self._is_text_response(response):
            self.logger.warning(f"Conteúdo não textual para {url}")
            self._register_problem_site(domain, "Conteúdo não textual")
            return
            
        # Verifica se é uma página de CAPTCHA
        if self._is_captcha_page(response) and not response.meta.get('manual_cookies'):
            self.logger.info(f"CAPTCHA detectado na página de detalhes: {url}")
            captcha_request = self._handle_captcha(response)
            if captcha_request:
                yield captcha_request
            return
            
        try:
            # Verifica se já atingiu o limite de itens para este domínio
            if self.items_count.get(domain, 0) >= self.max_items_per_site:
                self.logger.info(f"Limite de {self.max_items_per_site} itens atingido para o domínio {domain}")
                return
            
            # Verifica se há seletores em cache para esta URL
            cached_selectors = self._get_cached_selector(url, 'detail')
            
            if cached_selectors:
                self.logger.info(f"Usando seletores de detalhe em cache para {url}")
                selectors = cached_selectors
            else:
                # Se não há cache, verifica se há regra para o domínio
                rule = self.session.query(ScrapingRule).filter_by(domain=domain).first()
                
                if rule and rule.detail_selectors:
                    try:
                        selectors = json.loads(rule.detail_selectors)
                        self.logger.info(f"Usando seletores de detalhe existentes para {domain}")
                    except json.JSONDecodeError:
                        self.logger.warning(f"Erro ao decodificar seletores para {domain}: {rule.detail_selectors}")
                        selectors = self._generate_detail_selectors(response, domain)
                else:
                    self.logger.info(f"Gerando novos seletores de detalhe para {url}")
                    selectors = self._generate_detail_selectors(response, domain)
                    
                    if selectors:
                        # Salva o seletor para uso futuro
                        if rule:
                            rule.detail_selectors = json.dumps(selectors)
                        else:
                            rule = ScrapingRule(
                                domain=domain,
                                detail_selectors=json.dumps(selectors)
                            )
                            self.session.add(rule)
                        
                        try:
                            self.session.commit()
                        except Exception as e:
                            self.logger.error(f"Erro ao salvar seletores para {domain}: {str(e)}")
                            self.session.rollback()
                        
                        # Adiciona ao cache
                        self._cache_selector(url, domain, 'detail', selectors)
            
            if selectors:
                # Tira um screenshot da página para depuração se possível
                if os.environ.get('TAKE_SCREENSHOTS', 'false').lower() == 'true':
                    try:
                        screenshot_path = capture_property_screenshot(url, domain)
                        if screenshot_path:
                            self.logger.info(f"Screenshot salvo em {screenshot_path}")
                    except Exception as e:
                        self.logger.error(f"Erro ao tirar screenshot: {str(e)}")
                
                # Usa o novo método para extrair dados do imóvel
                property_data = self._extract_property_data(response, selectors)
                
                # Verifica se conseguiu extrair dados essenciais
                if property_data:
                    # Incrementa contador de itens para este domínio
                    self.items_count[domain] = self.items_count.get(domain, 0) + 1
                    
                    # Retorna o item
                    item = AuctionItem(**property_data)
                    return item
                else:
                    self.logger.warning(f"Não foi possível extrair dados suficientes de {url}")
                    return None
            else:
                self.logger.warning(f"Não foi possível gerar seletores para {url}")
                return None
                
        except Exception as e:
            self.logger.error(f"Erro ao processar detalhes para {url}: {str(e)}")
            self.logger.error(traceback.format_exc())
            return None

    def _generate_list_selector(self, response):
        """Gera um seletor CSS para a lista de imóveis usando LLM."""
        html = response.text
        url = response.url
        
        prompt = f"""
        Você é um especialista em web scraping. Analise o HTML abaixo de um site de leilão de imóveis e forneça um seletor CSS preciso para encontrar os links para as páginas de detalhes de cada imóvel.

        URL do site: {url}

        Requisitos:
        1. O seletor deve capturar APENAS links (elementos <a>) que levem às páginas de detalhes de imóveis individuais
        2. Ignore links de navegação, menus, rodapés ou qualquer outro tipo de link
        3. O seletor deve ser o mais específico possível para evitar falsos positivos
        4. Se houver múltiplos tipos de cards/elementos para imóveis, forneça o seletor que captura todos eles
        5. Forneça APENAS um seletor CSS válido, não descrições ou HTML
        6. NÃO inclua espaços no início ou fim do seletor
        7. NÃO inclua URLs completas ou texto descritivo como seletor
        8. Use apenas seletores CSS válidos como '.class', '#id', 'tag', etc.
        9. IMPORTANTE: O seletor deve terminar com 'a' ou incluir 'a[' para garantir que estamos selecionando links

        Exemplos de bons seletores:
        - ".property-card a.property-link"
        - "div.auction-item a.details-link"
        - ".listing-grid .item-card a[href*='/imovel/']"
        - "a.property-card"
        - "a[href*='/detalhe/']"

        IMPORTANTE: Sua resposta deve ser APENAS um objeto JSON válido no seguinte formato, sem texto adicional, comentários ou explicações:
        {{
            "list_selector": "seu_seletor_css_aqui"
        }}

        Se não conseguir identificar um seletor adequado, use null como valor.
        NÃO inclua markdown, texto explicativo, ou qualquer outro conteúdo além do JSON puro.
        NÃO inclua campos adicionais além do "list_selector".
        NÃO inclua análises ou descrições do HTML.
        NÃO inclua o código HTML de volta na resposta.
        Responda APENAS com o JSON solicitado.

        HTML do site:
        {html[:30000]}  # Limitando para evitar tokens excessivos
        """
        
        try:
            self.logger.info(f"Gerando seletor de lista para {url}")
            response_json = self.llm_api.generate(prompt)
            
            if not response_json:
                self.logger.warning(f"API LLM retornou resposta vazia para {url}")
                return self._get_fallback_list_selectors(response)
                
            if response_json and 'list_selector' in response_json:
                selector = response_json['list_selector']
                # Verifica se o seletor parece ser um seletor CSS válido
                if selector and isinstance(selector, str) and not selector.startswith('http') and not ' ' in selector and not selector.startswith('{') and not selector.startswith('<'):
                    self.logger.info(f"Seletor de lista gerado com sucesso: {selector}")
                    
                    # Verifica se o seletor termina com 'a' ou contém 'a['
                    if not (selector.endswith('a') or 'a[' in selector or selector.endswith('a.')):
                        # Tenta adicionar 'a' ao seletor se não for um seletor de link
                        modified_selector = f"{selector} a"
                        self.logger.info(f"Modificando seletor para garantir que selecione links: {modified_selector}")
                        selector = modified_selector
                    
                    # Testa o seletor para verificar se ele encontra algum elemento
                    elements = []
                    if selector.endswith('a') or 'a[' in selector or selector.endswith('a.'):
                        elements = response.css(f"{selector}::attr(href)").getall()
                    else:
                        elements = response.css(f"{selector} a::attr(href)").getall()
                    
                    if elements:
                        self.logger.info(f"Seletor encontrou {len(elements)} links")
                        return selector
                    else:
                        self.logger.warning(f"Seletor não encontrou nenhum link: {selector}")
                        return self._get_fallback_list_selectors(response)
                else:
                    self.logger.warning(f"Seletor de lista inválido gerado para {url}: {selector}")
                    return self._get_fallback_list_selectors(response)
            else:
                self.logger.warning(f"Não foi possível gerar seletor de lista para {url}. Resposta: {response_json}")
                return self._get_fallback_list_selectors(response)
        except Exception as e:
            self.logger.error(f"Erro ao gerar seletor de lista para {url}: {str(e)}")
            return self._get_fallback_list_selectors(response)
            
    def _get_fallback_list_selectors(self, response):
        """
        Tenta encontrar um seletor de lista usando uma série de seletores fallback comuns em sites de leilão brasileiros.
        
        Args:
            response: Objeto de resposta do Scrapy
            
        Returns:
            str: Seletor CSS que funcionou ou None se nenhum funcionou
        """
        # Seletores fallback específicos para sites de leilão brasileiros
        fallback_selectors = [
            # Seletores gerais
            "a[href*='/imovel']", 
            "a[href*='detalhe']", 
            "a[href*='lote']", 
            "a[href*='leilao']", 
            "a.card", 
            ".card a", 
            ".item a", 
            ".produto a",
            "a.item",
            "a.produto",
            "a[href*='item']",
            "a[href*='bem']",
            "a[href*='auction']",
            ".property a",
            "a.property",
            
            # Seletores específicos para sites brasileiros
            "a[href*='imovel']",
            "a[href*='detalhes']",
            "a[href*='ficha']",
            "a[href*='lance']",
            ".imovel a",
            "a.imovel",
            ".lote a",
            "a.lote",
            ".card-imovel a",
            "a.card-imovel",
            ".bloco-imovel a",
            "a.bloco-imovel",
            ".resultado a",
            "a.resultado",
            ".thumb-imovel a",
            "a.thumb-imovel",
            ".leilao-item a",
            "a.leilao-item",
            ".imovel-card a",
            "a.imovel-card",
            ".propriedade a",
            "a.propriedade",
            ".anuncio a",
            "a.anuncio",
            ".oferta a",
            "a.oferta",
            ".oportunidade a",
            "a.oportunidade",
            ".grid-item a",
            "a.grid-item",
            ".lista-item a",
            "a.lista-item"
        ]
        
        for fallback in fallback_selectors:
            elements = response.css(f"{fallback}::attr(href)").getall()
            if elements:
                self.logger.info(f"Usando seletor fallback: {fallback} (encontrou {len(elements)} links)")
                return fallback
                
        # Se nenhum seletor específico funcionou, tenta seletores mais genéricos
        generic_selectors = [
            "a[href]",
            ".container a",
            "#content a",
            "main a",
            "article a",
            "section a",
            ".results a",
            ".listing a"
        ]
        
        for generic in generic_selectors:
            elements = response.css(f"{generic}::attr(href)").getall()
            if elements and len(elements) > 0 and len(elements) < 100:  # Evita pegar todos os links da página
                self.logger.info(f"Usando seletor genérico: {generic} (encontrou {len(elements)} links)")
                return generic
                
        self.logger.warning("Nenhum seletor fallback funcionou")
        return None

    def _is_valid_css_selector(self, selector):
        """
        Verifica se um seletor CSS é válido.
        
        Args:
            selector: O seletor CSS a ser verificado
            
        Returns:
            bool: True se o seletor for válido, False caso contrário
        """
        if not selector or not isinstance(selector, str):
            return False
            
        # Verifica se o seletor contém caracteres inválidos
        invalid_chars = ['<', '>', '{', '}', '\\', '`', '|']
        if any(char in selector for char in invalid_chars):
            return False
            
        # Verifica se o seletor começa com caracteres válidos
        valid_starts = ['.', '#', 'a', 'div', 'span', 'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 
                        'img', 'ul', 'li', 'table', 'tr', 'td', 'th', 'section', 'article', 
                        'main', 'header', 'footer', 'nav', 'aside', 'figure', 'figcaption', 
                        'time', 'strong', 'em', 'i', 'b', 'small', 'button', 'input', 'form',
                        'iframe', 'meta', '*']
                        
        # Verifica se o seletor começa com um caractere válido ou se é um seletor composto
        is_valid_start = False
        for start in valid_starts:
            if selector.startswith(start) or ' ' + start in selector or '>' + start in selector:
                is_valid_start = True
                break
                
        if not is_valid_start:
            return False
            
        # Verifica se o seletor contém URLs ou texto descritivo
        if selector.startswith('http') or len(selector) > 200:
            return False
            
        # Verifica se o seletor tem um número equilibrado de colchetes e parênteses
        if selector.count('[') != selector.count(']') or selector.count('(') != selector.count(')'):
            return False
            
        # Se o seletor contém vírgulas, verifica cada parte separadamente
        if ',' in selector:
            for part in selector.split(','):
                part = part.strip()
                if part and not self._is_valid_css_selector(part):
                    return False
                    
        return True

    def _generate_detail_selectors(self, response, domain=None):
        """
        Gera seletores CSS para extrair dados de detalhes de um imóvel usando LLM.
        
        Args:
            response: Objeto de resposta do Scrapy
            domain: Domínio do site
            
        Returns:
            dict: Dicionário de seletores CSS para cada campo
        """
        url = response.url
        if not domain:
            domain = urlparse(url).netloc
        
        self.logger.info(f"Gerando seletores de detalhes para {url}")
        
        # Captura uma amostra do HTML para enviar para a API
        html_sample = self._get_html_sample(response.text)
        
        # Define a prompt para o modelo LLM
        prompt = f"""
        Analise o HTML a seguir e forneça seletores CSS para extrair informações sobre um imóvel de leilão.
        
        URL: {url}
        
        HTML:
        ```
        {html_sample}
        ```
        
        Forneça seletores CSS para os seguintes campos:
        1. title: Título do imóvel
        2. price: Preço ou valor do imóvel (valor de lance)
        3. description: Descrição do imóvel
        4. address: Endereço do imóvel
        5. location: Localização (cidade/estado)
        6. area: Área do imóvel (m²)
        7. property_type: Tipo do imóvel (casa, apartamento, etc.)
        8. auction_date: Data do leilão
        9. image_url: URL da imagem principal do imóvel
        
        Regras:
        1. Retorne APENAS seletores CSS válidos para cada campo
        2. Os seletores devem ser o mais específicos possíveis
        3. Forneça APENAS seletores CSS válidos, não descrições ou HTML
        4. Se não conseguir identificar um campo, use null como valor
        5. Use formato JSON: {"field": "selector"}
        
        Exemplo de resposta:
        ```json
        {
            "title": ".property-title",
            "price": ".property-price",
            "description": ".property-description",
            "address": ".property-address",
            "location": ".property-location",
            "area": ".property-area",
            "property_type": ".property-type",
            "auction_date": ".auction-date",
            "image_url": ".property-image"
        }
        ```
        """
        
        # Salva a requisição em cache para depuração
        cache_dir = "cache/llm_responses"
        os.makedirs(cache_dir, exist_ok=True)
        
        # Cria uma versão simplificada da URL para usar como nome de arquivo
        url_safe = re.sub(r'[^\w\-_]', '_', url)[:100]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        cache_file = os.path.join(cache_dir, f"detail_selectors_{domain}_{timestamp}_{url_safe}.json")
        
        try:
            # Faz a chamada para a API LLM
            response_json = call_llm_api(prompt, api_key=os.environ.get('API_KEY_GROK'), temperature=0.3)
            
            # Salva a resposta original para depuração
            with open(cache_file, 'w') as f:
                json.dump({
                    'url': url,
                    'prompt': prompt,
                    'response': response_json
                }, f, indent=2)
                
            if not response_json:
                self.logger.warning(f"API LLM retornou resposta vazia para {url}")
                return self._get_generic_selectors()
                
            # Parse da resposta
            parsed_response = parse_llm_response(response_json)
            
            if not parsed_response:
                self.logger.warning(f"Não foi possível interpretar a resposta da API para {url}")
                return self._get_generic_selectors()
                
            # Valida os seletores
            valid_selectors = {}
            for field, selector in parsed_response.items():
                if selector and isinstance(selector, str) and self._is_valid_css_selector(selector):
                    valid_selectors[field] = selector
                    self.logger.info(f"Seletor válido para {field}: {selector}")
                else:
                    self.logger.warning(f"Seletor inválido para {field}: {selector}")
                    # Usa um seletor genérico para este campo
                    valid_selectors[field] = self._get_generic_selectors().get(field)
            
            # Se não conseguiu gerar seletores válidos, usa os genéricos
            if not valid_selectors:
                self.logger.warning(f"Não foi possível gerar seletores válidos para {url}")
                return self._get_generic_selectors()
                
            return valid_selectors
            
        except Exception as e:
            self.logger.error(f"Erro ao gerar seletores para {url}: {str(e)}")
            self.logger.error(traceback.format_exc())
            # Em caso de erro, retorna os seletores genéricos
            return self._get_generic_selectors()

    def _get_generic_selectors(self):
        """
        Retorna um conjunto de seletores CSS genéricos para campos comuns em páginas de detalhes de imóveis.
        
        Returns:
            dict: Dicionário com seletores genéricos para cada campo
        """
        return {
            'title': 'h1, .title, .product-title, .property-title, .auction-title, .main-title, .imovel-titulo, .leilao-titulo, .nome-imovel',
            'price': '.price, .value, .auction-price, .property-price, span[itemprop="price"], .valor, .lance-minimo, .valor-lance, .preco, .valor-inicial, .lance-inicial, .avaliacao',
            'address': '.address, .location, .property-address, .endereco, [itemprop="address"], .localizacao, .local, .local-imovel, .imovel-endereco',
            'description': '.description, .details, .property-description, .descricao, [itemprop="description"], .content p, .detalhes, .caracteristicas, .imovel-descricao, .texto-descritivo',
            'area': '.area, .property-area, .tamanho, .metros, [itemprop="size"], .area-total, .area-construida, .area-terreno, .area-util, .metragem',
            'property_type': '.type, .property-type, .categoria, .imovel-tipo, [itemprop="category"], .tipo-imovel, .tipo, .categoria-imovel',
            'auction_date': '.date, .auction-date, .data-leilao, .leilao-data, time, [itemprop="date"], .data, .data-evento, .data-inicio, .data-termino, .data-realizacao',
            'image_url': '.main-image img, .property-image img, .foto-principal img, .carousel img, [itemprop="image"], .gallery img:first-child, .imagem-principal img, .foto img, .imagem-destaque img, .slide img:first-child'
        }

    def _get_cached_selector(self, url, page_type):
        """
        Obtém seletores em cache para uma URL específica.
        
        Args:
            url: URL da página
            page_type: Tipo de página ('list' ou 'detail')
            
        Returns:
            Para page_type='list': str - Seletor CSS em cache ou None
            Para page_type='detail': dict - Dicionário de seletores ou None
        """
        try:
            cache_entry = self.session.query(SelectorCache).filter_by(
                url=url, 
                page_type=page_type,
                is_valid=True
            ).first()
            
            if cache_entry:
                # Atualiza a data de último uso e incrementa o contador
                cache_entry.last_used = datetime.now()
                cache_entry.use_count += 1
                self.session.commit()
                
                # Retorna os seletores
                selectors = json.loads(cache_entry.selectors)
                
                # Para lista, retorna a string de seletor em vez do dicionário
                if page_type == 'list' and 'list_selector' in selectors:
                    return selectors['list_selector']
                return selectors
            
            # Se não encontrou para a URL exata, tenta encontrar para o mesmo domínio
            # com uma taxa de sucesso alta (acima de 0.7)
            domain = urlparse(url).netloc
            similar_entry = self.session.query(SelectorCache).filter_by(
                domain=domain, 
                page_type=page_type,
                is_valid=True
            ).filter(SelectorCache.success_rate > 0.7).order_by(
                SelectorCache.success_rate.desc()
            ).first()
            
            if similar_entry:
                self.logger.info(f"Usando seletores de URL similar para {url} (domínio: {domain})")
                selectors = json.loads(similar_entry.selectors)
                
                # Para lista, retorna a string de seletor em vez do dicionário
                if page_type == 'list' and 'list_selector' in selectors:
                    return selectors['list_selector']
                return selectors
                
            return None
        except Exception as e:
            self.logger.error(f"Erro ao obter seletores em cache para {url}: {str(e)}")
            return None

    def _cache_selector(self, url, domain, page_type, selectors):
        """
        Armazena seletores em cache para uso futuro.
        
        Args:
            url: URL da página
            domain: Domínio do site
            page_type: Tipo de página ('list' ou 'detail')
            selectors: Seletores a serem armazenados (str ou dict)
        """
        try:
            # Converte para dicionário se for string (caso dos seletores de lista)
            if isinstance(selectors, str):
                selectors = {'list_selector': selectors}
                
            # Verifica se já existe em cache
            existing = self.session.query(SelectorCache).filter_by(
                url=url, 
                page_type=page_type
            ).first()
            
            if existing:
                # Atualiza o existente
                existing.selectors = json.dumps(selectors)
                existing.success_rate = 0.5  # Reset da taxa de sucesso
                existing.timestamp = datetime.now()
                self.session.commit()
                self.logger.info(f"Seletores atualizados em cache para {url}")
            else:
                # Cria um novo
                selector_cache = SelectorCache(
                    domain=domain,
                    url=url,
                    page_type=page_type,
                    selectors=json.dumps(selectors),
                    success_rate=0.5,  # Começa com 50% de confiança
                    created_at=datetime.now(),
                    last_used=datetime.now()
                )
                self.session.add(selector_cache)
                self.session.commit()
                self.logger.info(f"Seletores armazenados em cache para {url}")
        except Exception as e:
            self.logger.error(f"Erro ao armazenar seletores em cache para {url}: {str(e)}")

    def _update_selector_success(self, url, success, success_rate=None):
        """
        Atualiza a taxa de sucesso de um seletor em cache.
        
        Args:
            url: URL da página
            success: Se a extração foi bem-sucedida
            success_rate: Taxa de sucesso (opcional)
        """
        try:
            # Correto: url já é o nome do campo na classe SelectorCache
            cache_entry = self.session.query(SelectorCache).filter_by(url=url).first()
            
            if cache_entry:
                if success_rate is not None:
                    # Usa a taxa de sucesso fornecida
                    cache_entry.success_rate = success_rate
                else:
                    # Calcula uma média ponderada com o histórico
                    current_rate = cache_entry.success_rate
                    use_count = cache_entry.use_count
                    
                    # Quanto mais usos, menor o impacto de um único resultado
                    weight = 1 / (use_count + 1)
                    new_rate = current_rate * (1 - weight) + (1.0 if success else 0.0) * weight
                    
                    cache_entry.success_rate = new_rate
                
                self.session.commit()
                self.logger.info(f"Taxa de sucesso atualizada para seletor de {url}: {cache_entry.success_rate:.2f}")
        except Exception as e:
            self.logger.error(f"Erro ao atualizar taxa de sucesso para {url}: {str(e)}")

    def _invalidate_selector_cache(self, url):
        """
        Marca um seletor em cache como inválido.
        
        Args:
            url: URL da página
        """
        try:
            # Correto: url já é o nome do campo na classe SelectorCache
            cache_entry = self.session.query(SelectorCache).filter_by(url=url).first()
            
            if cache_entry:
                cache_entry.is_valid = False
                self.session.commit()
                self.logger.info(f"Seletor em cache marcado como inválido para {url}")
        except Exception as e:
            self.logger.error(f"Erro ao invalidar seletor em cache para {url}: {str(e)}")

    def _extract_property_data(self, response, selectors):
        """
        Extrai dados de um imóvel usando seletores CSS.
        
        Args:
            response: Objeto de resposta do Scrapy
            selectors: Dicionário com seletores CSS para cada campo
            
        Returns:
            dict: Dados do imóvel extraídos
        """
        domain = response.meta.get('domain') or urlparse(response.url).netloc
        
        self.logger.info(f"Extraindo dados de imóvel em {response.url} com seletores: {selectors}")
        
        # Função auxiliar para extrair texto de um seletor
        def extract_text(selector_key):
            if not selectors.get(selector_key):
                return None
                
            selector = selectors[selector_key]
            result = None
            
            # Tenta diferentes formatos de extração
            try:
                # Tenta extrair texto diretamente
                result = response.css(f"{selector}::text").get()
                
                # Se não funcionou, tenta extrair o valor do atributo content (meta tags)
                if not result:
                    result = response.css(f"{selector}::attr(content)").get()
                    
                # Se ainda não funcionou, tenta extrair o HTML e limpar
                if not result:
                    html = response.css(f"{selector}").get()
                    if html:
                        # Remove todas as tags HTML para obter apenas o texto
                        result = re.sub(r'<[^>]+>', ' ', html).strip()
                
                # Limpa o resultado se existir
                if result:
                    # Remove espaços extras e quebras de linha
                    result = re.sub(r'\s+', ' ', result).strip()
                    # Remove caracteres não imprimíveis
                    result = ''.join(c for c in result if c.isprintable() or c.isspace())
            except Exception as e:
                self.logger.error(f"Erro ao extrair {selector_key} com seletor {selector}: {str(e)}")
                
            return result
            
        # Extrai dados principais
        title = extract_text('title')
        price = extract_text('price')
        description = extract_text('description')
        address = extract_text('address')
        location = extract_text('location') or address  # Location pode ser o mesmo que endereço
        area = extract_text('area')
        property_type = extract_text('property_type')
        auction_date = extract_text('auction_date')

        # Tenta extrair imagens (pode haver múltiplas)
        images = []
        image_selector = selectors.get('image_url')
        
        if image_selector:
            try:
                # Tenta diferentes atributos para imagens
                for attr in ['src', 'data-src', 'data-lazy-src', 'data-original']:
                    imgs = response.css(f"{image_selector}::attr({attr})").getall()
                    if imgs:
                        images.extend(imgs)
                
                # Se não encontrou nada, tenta seletores mais genéricos para galerias de imagens
                if not images:
                    # Tenta encontrar imagens em galerias comuns
                    gallery_selectors = [
                        '.gallery img', '.carousel img', '.slider img',
                        '.photos img', '.images img', '[data-fancybox] img',
                        '.owl-carousel img', '.swiper-container img'
                    ]
                    
                    for gallery_selector in gallery_selectors:
                        imgs = response.css(f"{gallery_selector}::attr(src)").getall()
                        if imgs:
                            images.extend(imgs)
                            break
                
                # Normaliza URLs de imagens (converte relativos para absolutos)
                images = [urljoin(response.url, img) for img in images if img]
                
                # Remove duplicatas preservando a ordem
                seen = set()
                images = [x for x in images if x not in seen and not seen.add(x)]
            except Exception as e:
                self.logger.error(f"Erro ao extrair imagens com seletor {image_selector}: {str(e)}")
        
        # Se não tiver título mas tiver algum outro dado, tenta extrair um título genérico da página
        if not title and (price or description or address):
            try:
                title = response.css('h1::text').get() or response.css('title::text').get()
                if title:
                    # Limpa o título
                    title = re.sub(r'\s+', ' ', title).strip()
            except Exception as e:
                self.logger.error(f"Erro ao extrair título alternativo: {str(e)}")
        
        # Se não tiver preço, tenta extrair de padrões comuns no texto
        if not price and description:
            try:
                # Padrões comuns de preço em texto (em português)
                price_patterns = [
                    r'R\$\s*[\d\.,]+', r'valor[:\s]+R\$\s*[\d\.,]+',
                    r'preço[:\s]+R\$\s*[\d\.,]+', r'lance[:\s]+R\$\s*[\d\.,]+',
                    r'avaliado[^R]*R\$\s*[\d\.,]+'
                ]
                
                for pattern in price_patterns:
                    price_match = re.search(pattern, description, re.IGNORECASE)
                    if price_match:
                        price = price_match.group(0)
                        break
            except Exception as e:
                self.logger.error(f"Erro ao extrair preço de padrões: {str(e)}")
        
        # Tenta normalizar e formatar o preço
        if price:
            try:
                # Remove texto adicional e mantém apenas o valor numérico com R$
                price = re.sub(r'[^\d,.R$]', '', price)
                # Garante que há apenas um R$
                if 'R$' in price:
                    price_parts = price.split('R$')
                    if len(price_parts) > 1:
                        price = f"R$ {price_parts[-1].strip()}"
            except Exception as e:
                self.logger.error(f"Erro ao normalizar preço: {str(e)}")
        
        # Se não tiver data do leilão, tenta extrair de padrões comuns no texto
        if not auction_date and description:
            try:
                # Padrões comuns de data em texto (em português)
                date_patterns = [
                    r'\d{2}/\d{2}/\d{4}', r'\d{1,2}\s+de\s+[a-zA-Zç]+\s+de\s+\d{4}',
                    r'dia\s+\d{1,2}[^\d]+\d{1,2}[^\d]+\d{4}', r'data[:\s]+\d{1,2}[^\d]+\d{1,2}[^\d]+\d{4}'
                ]
                
                for pattern in date_patterns:
                    date_match = re.search(pattern, description, re.IGNORECASE)
                    if date_match:
                        auction_date = date_match.group(0)
                        break
            except Exception as e:
                self.logger.error(f"Erro ao extrair data de padrões: {str(e)}")
        
        # Estrutura os dados extraídos
        property_data = {
            'url': response.url,
            'source_domain': domain,  # Correto: usando source_domain em vez de domain
            'title': title,
            'price': price,
            'description': description,
            'address': address,
            'area': area,
            'property_type': property_type,
            'auction_date': auction_date,
            'image_url': images[0] if images else None,  # Usando image_url em vez de images
            # Removido o campo additional_info que não é suportado
            'extracted_at': datetime.now().isoformat()  # Adicionando o campo extracted_at que existe no modelo
        }
        
        # Faz um logging do resultado
        self.logger.info(f"Dados extraídos para {response.url}: "
                         f"título='{title}', preço='{price}', "
                         f"endereço='{address}', {len(images)} imagens")
        
        # Verifica se extraiu dados essenciais (título ou preço ou descrição)
        if title or price or description:
            self.logger.info(f"Extração bem-sucedida para {response.url}")
            # Marca o seletor como bem-sucedido no cache
            self._update_selector_success(response.url, True)
            return property_data
        else:
            self.logger.warning(f"Falha na extração de dados essenciais para {response.url}")
            # Marca o seletor como falho no cache
            self._update_selector_success(response.url, False)
            return None

    def _get_html_sample(self, html_content):
        """
        Extrai uma amostra representativa do HTML para enviar ao LLM.
        
        Args:
            html_content: String com o conteúdo HTML completo
            
        Returns:
            str: Amostra do HTML com as partes mais relevantes
        """
        # Limita o tamanho do HTML para evitar tokens excessivos
        max_sample_size = 15000
        
        # Se o HTML já é menor que o limite, retorna ele inteiro
        if len(html_content) <= max_sample_size:
            return html_content
            
        # Extrai o conteúdo do body
        body_match = re.search(r'<body[^>]*>(.*?)</body>', html_content, re.DOTALL | re.IGNORECASE)
        
        if body_match:
            body_content = body_match.group(1)
            
            # Se o body é menor que o limite, retorna ele inteiro
            if len(body_content) <= max_sample_size:
                return f"<body>{body_content}</body>"
                
            # Procura por elementos com maior probabilidade de conter informações relevantes
            # 1. Div principal de conteúdo
            relevant_patterns = [
                r'<(div|section|article|main)[^>]*(?:id|class)=["\'](content|main|property|detail|produto|imovel)["\'][^>]*>.*?</\1>',
                r'<(div|section|article)[^>]*(?:id|class)=["\'](container|wrapper|auction|leilao|details|detalhes)["\'][^>]*>.*?</\1>',
                r'<h1.*?>.*?</h1>.*?(<div.*?>.*?</div>)',
                r'<(div|section|article)[^>]*>.*?(?:preço|valor|price|value|imóvel|property).*?</\1>'
            ]
            
            # Tenta encontrar o conteúdo mais relevante
            relevant_content = ""
            
            for pattern in relevant_patterns:
                matches = re.findall(pattern, body_content, re.DOTALL | re.IGNORECASE)
                
                if matches:
                    # Se encontrou múltiplas correspondências, une-as
                    if isinstance(matches[0], tuple):
                        # Quando os grupos são capturados, pegamos o último grupo que contém o conteúdo
                        for match in matches:
                            relevant_content += match[-1]
                    else:
                        # Quando não há grupos de captura específicos, juntamos tudo
                        relevant_content += "".join(matches)
                    
                    # Se já temos conteúdo suficiente, paramos
                    if len(relevant_content) >= max_sample_size * 0.5:
                        break
            
            # Se encontrou conteúdo relevante, usa-o
            if relevant_content and len(relevant_content) > 200:  # Verifica se é significativo
                # Trunca se necessário
                if len(relevant_content) > max_sample_size:
                    relevant_content = relevant_content[:max_sample_size]
                return f"<body>{relevant_content}</body>"
        
        # Se não conseguiu extrair de forma inteligente, pega as primeiras e últimas partes do HTML
        head_size = min(2000, int(max_sample_size * 0.2))  # 20% para o head
        
        # Extrai a parte inicial (incluindo head e início do body)
        start_content = html_content[:head_size]
        
        # Calcula quanto espaço resta para o conteúdo principal e final
        remaining_size = max_sample_size - head_size
        middle_size = int(remaining_size * 0.6)  # 60% para o meio
        end_size = int(remaining_size * 0.4)     # 40% para o final
        
        # Tenta encontrar o início do conteúdo principal (após a navegação/menu)
        start_body_match = re.search(r'<body[^>]*>', html_content, re.IGNORECASE)
        menu_end_match = re.search(r'</(?:nav|header|menu)[^>]*>', html_content[head_size:], re.IGNORECASE)
        
        if start_body_match and menu_end_match:
            # Calcula a posição para começar a extrair o conteúdo principal
            body_start = start_body_match.end()
            menu_end = head_size + menu_end_match.end()
            
            # Extrai a parte do meio (após menus/cabeçalhos)
            middle_content = html_content[menu_end:menu_end + middle_size]
            
            # Extrai a parte final (pode conter detalhes importantes)
            end_offset = max(0, len(html_content) - end_size)
            end_content = html_content[end_offset:]
            
            return f"{start_content}...{middle_content}...{end_content}"
        
        # Fallback: divide o HTML em três partes aproximadamente iguais
        third = len(html_content) // 3
        
        start_part = html_content[:third]
        middle_part = html_content[third:2*third]
        end_part = html_content[2*third:]
        
        # Pega uma amostra de cada parte
        sample_size = max_sample_size // 3
        
        return f"{start_part[:sample_size]}...{middle_part[:sample_size]}...{end_part[:sample_size]}"
