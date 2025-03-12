#!/usr/bin/env python3
"""
Script simplificado para executar o scraper de leilões de imóveis com foco em extração de dados detalhados.
"""
import os
import sys
import logging
import argparse
from fetch_and_scrape_improved import main as scrape_main

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/scrape_auctions.log"),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

def main():
    """
    Função principal que configura e executa o scraper.
    """
    parser = argparse.ArgumentParser(description='Scraper otimizado para sites de leilão de imóveis')
    
    parser.add_argument('--termo', type=str, default="leilão de imóveis",
                        help='Termo de busca para encontrar sites de leilão (padrão: "leilão de imóveis")')
    
    parser.add_argument('--itens', type=int, default=5,
                        help='Número máximo de imóveis a extrair por site (padrão: 5)')
    
    parser.add_argument('--modo', choices=['listagem', 'detalhes'], default='detalhes',
                        help='Modo de operação: apenas listagem ou com detalhes dos imóveis (padrão: detalhes)')
    
    parser.add_argument('--debug', action='store_true',
                        help='Ativa o modo de depuração com logs mais detalhados')
    
    args = parser.parse_args()
    
    # Configura os argumentos do sistema para o script principal
    depth = 1 if args.modo == 'listagem' else 2
    
    # Inicializa os diretórios necessários
    os.makedirs("logs", exist_ok=True)
    os.makedirs("prints", exist_ok=True)
    os.makedirs("cache", exist_ok=True)
    os.makedirs("cache/llm_responses", exist_ok=True)
    
    # Exibe informações sobre a execução
    print("\n===== SCRAPER DE LEILÕES DE IMÓVEIS =====")
    print(f"Termo de busca: '{args.termo}'")
    print(f"Modo: {args.modo.upper()}")
    print(f"Máximo de itens por site: {args.itens}")
    print(f"Profundidade de navegação: {depth}")
    print("=========================================\n")
    
    # Configura os argumentos da linha de comando
    sys.argv = [
        sys.argv[0],  # O nome do script atual
        args.termo,  # O termo de busca
        f"--depth={depth}",  # A profundidade de navegação
        f"--max-items={args.itens}",  # Máximo de itens por site
    ]
    
    if args.debug:
        sys.argv.append("--debug")
    
    # Executa o script principal
    try:
        logger.info(f"Iniciando scraper no modo {args.modo} com termo '{args.termo}'")
        scrape_main()
        logger.info("Scraper finalizado com sucesso")
    except Exception as e:
        logger.error(f"Erro na execução do scraper: {str(e)}")
        print(f"\nErro na execução do scraper: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 