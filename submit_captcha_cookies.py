#!/usr/bin/env python3
"""
Script auxiliar para submeter cookies após resolver um CAPTCHA manualmente.
Uso: python3 submit_captcha_cookies.py <url>
"""

import os
import sys
import json
import glob
from urllib.parse import urlparse
from datetime import datetime

def find_captcha_request(url):
    """
    Encontra o arquivo de requisição de CAPTCHA mais recente para a URL especificada.
    """
    domain = urlparse(url).netloc
    domain_safe = domain.replace('.', '_')
    
    # Procura por arquivos de requisição para este domínio
    request_files = glob.glob(os.path.join('cookies', f"{domain_safe}_*_request.json"))
    
    if not request_files:
        print(f"Nenhuma requisição de CAPTCHA encontrada para {url}")
        return None
        
    # Ordena por data de modificação (mais recente primeiro)
    request_files.sort(key=os.path.getmtime, reverse=True)
    
    # Retorna o arquivo mais recente
    return request_files[0]

def submit_cookies(request_file):
    """
    Solicita os cookies do usuário e os salva no arquivo de resposta correspondente.
    """
    try:
        # Lê o arquivo de requisição
        with open(request_file, 'r') as f:
            request_data = json.load(f)
            
        url = request_data['url']
        domain = request_data['domain']
        screenshot_path = request_data.get('screenshot_path', '')
        
        # Determina o arquivo de resposta
        response_file = request_file.replace('_request.json', '_response.json')
        
        print("\n" + "="*80)
        print(f"Submissão de cookies para: {url}")
        if os.path.exists(screenshot_path):
            print(f"Screenshot disponível em: {screenshot_path}")
        print("\nVocê tem três opções:")
        print("1. Cole os cookies em formato JSON diretamente")
        print("2. Forneça o caminho para um arquivo de cookies exportado")
        print("3. Digite 'pular' para ignorar este site")
        print("="*80)
        
        user_input = input("\nCole os cookies JSON, informe o caminho do arquivo ou digite 'pular': ")
        
        if user_input.lower() == 'pular':
            print(f"Pulando site: {url}")
            with open(response_file, 'w') as f:
                json.dump({
                    'status': 'skipped',
                    'url': url,
                    'timestamp': datetime.now().strftime("%Y%m%d_%H%M%S")
                }, f, indent=2)
            return True
            
        cookies = None
        try:
            # Verifica se é um caminho de arquivo
            if os.path.exists(user_input):
                with open(user_input, 'r') as f:
                    cookies = json.load(f)
                print(f"Cookies carregados do arquivo: {user_input}")
            else:
                # Tenta processar como JSON direto
                cookies = json.loads(user_input)
                print(f"Cookies recebidos diretamente para {domain}")
                
            if cookies:
                # Salva os cookies no arquivo de resposta
                with open(response_file, 'w') as f:
                    json.dump({
                        'status': 'completed',
                        'url': url,
                        'cookies': cookies,
                        'timestamp': datetime.now().strftime("%Y%m%d_%H%M%S")
                    }, f, indent=2)
                
                # Também salva uma cópia permanente dos cookies
                cookies_file = os.path.join('cookies', f"{domain.replace('.', '_')}_cookies.json")
                with open(cookies_file, 'w') as f:
                    json.dump(cookies, f, indent=2)
                
                print(f"\nCookies salvos com sucesso para {url}")
                print(f"Arquivo de resposta: {response_file}")
                print(f"Arquivo de cookies permanente: {cookies_file}")
                print("\nO scraping continuará automaticamente na próxima execução.")
                return True
                
        except json.JSONDecodeError:
            print(f"Erro: Formato de cookies inválido. Os cookies devem estar em formato JSON.")
        except Exception as e:
            print(f"Erro ao processar cookies: {str(e)}")
            
        return False
        
    except Exception as e:
        print(f"Erro ao processar arquivo de requisição: {str(e)}")
        return False

def main():
    """
    Função principal.
    """
    # Verifica se o diretório de cookies existe
    if not os.path.exists('cookies'):
        os.makedirs('cookies', exist_ok=True)
        
    # Verifica argumentos
    if len(sys.argv) < 2:
        print("Uso: python3 submit_captcha_cookies.py <url>")
        return
        
    url = sys.argv[1]
    
    # Encontra o arquivo de requisição
    request_file = find_captcha_request(url)
    
    if not request_file:
        print("Nenhuma requisição de CAPTCHA pendente encontrada.")
        return
        
    # Submete os cookies
    submit_cookies(request_file)

if __name__ == "__main__":
    main() 