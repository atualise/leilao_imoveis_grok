"""
Módulo para capturar screenshots de páginas web.
"""
import os
import time
import logging
from datetime import datetime
from urllib.parse import urlparse
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import WebDriverException

logger = logging.getLogger(__name__)

class ScreenshotManager:
    """Gerencia a captura de screenshots de páginas web."""
    
    def __init__(self, output_dir="prints", driver_path=None):
        """
        Inicializa o gerenciador de screenshots.
        
        Args:
            output_dir: Diretório para salvar os screenshots (padrão: "prints")
            driver_path: Caminho para o driver do Chrome (opcional)
        """
        self.output_dir = output_dir
        self.driver_path = driver_path
        self.ensure_output_dir()
        
    def ensure_output_dir(self):
        """Garante que o diretório de saída existe."""
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
            logger.info(f"Diretório para screenshots criado: {self.output_dir}")
    
    def get_filename(self, url):
        """
        Gera um nome de arquivo baseado na URL e timestamp.
        
        Args:
            url: URL da página
            
        Returns:
            str: Nome do arquivo para o screenshot
        """
        # Extrai o domínio e caminho da URL
        parsed_url = urlparse(url)
        domain = parsed_url.netloc.replace("www.", "")
        path = parsed_url.path.strip("/").replace("/", "_")
        
        # Limita o tamanho do nome do arquivo
        if len(path) > 50:
            path = path[:50]
            
        # Adiciona timestamp para evitar colisões
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Gera o nome do arquivo
        if path:
            filename = f"{domain}_{path}_{timestamp}.png"
        else:
            filename = f"{domain}_{timestamp}.png"
            
        # Remove caracteres inválidos para nome de arquivo
        filename = "".join(c if c.isalnum() or c in "._-" else "_" for c in filename)
        
        return filename
    
    def capture_screenshot(self, url, wait_time=3):
        """
        Captura um screenshot da página web.
        
        Args:
            url: URL da página
            wait_time: Tempo de espera em segundos após carregar a página
            
        Returns:
            str: Caminho do arquivo salvo ou None se falhar
        """
        driver = None
        try:
            # Configura as opções do Chrome em modo headless
            chrome_options = Options()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--window-size=1920,1080")
            
            # Inicializa o driver
            if self.driver_path:
                service = Service(executable_path=self.driver_path)
                driver = webdriver.Chrome(service=service, options=chrome_options)
            else:
                driver = webdriver.Chrome(options=chrome_options)
            
            # Carrega a página
            logger.info(f"Capturando screenshot de: {url}")
            driver.get(url)
            
            # Aguarda o carregamento da página
            time.sleep(wait_time)
            
            # Gera o nome do arquivo e salva o screenshot
            filename = self.get_filename(url)
            file_path = os.path.join(self.output_dir, filename)
            
            # Salva o screenshot
            driver.save_screenshot(file_path)
            logger.info(f"Screenshot salvo em: {file_path}")
            
            return file_path
        except WebDriverException as e:
            logger.error(f"Erro ao capturar screenshot de {url}: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Erro inesperado ao capturar screenshot de {url}: {str(e)}")
            return None
        finally:
            # Garante que o driver seja fechado
            if driver:
                driver.quit()

# Função de conveniência para uso em outros módulos
def capture_property_screenshot(url, output_dir="prints", wait_time=3, driver_path=None):
    """
    Captura um screenshot de uma página de detalhes de imóvel.
    
    Args:
        url: URL da página
        output_dir: Diretório para salvar os screenshots
        wait_time: Tempo de espera em segundos após carregar a página
        driver_path: Caminho para o driver do Chrome (opcional)
        
    Returns:
        str: Caminho do arquivo salvo ou None se falhar
    """
    manager = ScreenshotManager(output_dir=output_dir, driver_path=driver_path)
    return manager.capture_screenshot(url, wait_time=wait_time) 