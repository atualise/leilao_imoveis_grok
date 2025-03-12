"""
Script para testar a funcionalidade de captura de screenshots.
"""
import os
import sys
import logging
from myproject.utils.screenshot import capture_property_screenshot

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

def test_screenshot():
    """
    Testa a funcionalidade de captura de screenshots.
    """
    # Garantir que o diretório "prints" existe
    prints_dir = "prints"
    if not os.path.exists(prints_dir):
        os.makedirs(prints_dir)
        logger.info(f"Diretório '{prints_dir}' criado.")
    
    # Lista de URLs de exemplo para testar
    test_urls = [
        "https://www.megaleiloes.com.br/",
        "https://www.portalzuk.com.br/",
        "https://www.sodresantoro.com.br/"
    ]
    
    logger.info("Iniciando testes de captura de screenshots...")
    
    for url in test_urls:
        logger.info(f"Capturando screenshot de: {url}")
        try:
            screenshot_path = capture_property_screenshot(url, wait_time=5)
            if screenshot_path:
                logger.info(f"Screenshot salvo em: {screenshot_path}")
            else:
                logger.error(f"Falha ao capturar screenshot de: {url}")
        except Exception as e:
            logger.error(f"Erro ao capturar screenshot de {url}: {str(e)}")
    
    logger.info("Testes de screenshot concluídos.")

if __name__ == "__main__":
    test_screenshot() 