import requests
from myproject.config import OLLAMA_API_URL, OLLAMA_MODEL
import json
import re
import logging
import time
from urllib.parse import urljoin
import os
import hashlib
from datetime import datetime

logger = logging.getLogger(__name__)

class LlmApi:
    """
    Classe para encapsular as chamadas à API do LLM.
    """
    def __init__(self):
        self.api_url = OLLAMA_API_URL
        self.model = OLLAMA_MODEL
        self.cache_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'cache', 'llm_responses')
        
        # Cria o diretório de cache se não existir
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # Reduzir verbosidade do requests
        logging.getLogger("requests").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)
    
    def _truncate_text(self, text, max_length=100):
        """Trunca texto para logging, evitando dumps muito grandes."""
        if text and len(text) > max_length:
            return text[:max_length] + "... [truncado]"
        return text
    
    def _get_cache_key(self, prompt):
        """Gera uma chave de cache baseada no prompt."""
        # Usa apenas os primeiros 500 caracteres do prompt para a chave
        # Isso ajuda a identificar prompts similares sem criar chaves muito longas
        prompt_hash = hashlib.md5(prompt[:500].encode('utf-8')).hexdigest()
        return prompt_hash
    
    def _get_from_cache(self, prompt):
        """Tenta obter uma resposta do cache."""
        cache_key = self._get_cache_key(prompt)
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.json")
        
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                
                # Verifica se o cache não está expirado (7 dias)
                cache_time = datetime.fromisoformat(cache_data.get('timestamp', '2000-01-01'))
                current_time = datetime.now()
                
                # Se o cache tiver menos de 7 dias, usa-o
                if (current_time - cache_time).days < 7:
                    logger.info(f"Usando resposta em cache para prompt: {self._truncate_text(prompt)}")
                    return cache_data.get('response')
            except Exception as e:
                logger.warning(f"Erro ao ler cache: {str(e)}")
        
        return None
    
    def _save_to_cache(self, prompt, response):
        """Salva uma resposta no cache."""
        if not response:
            return
            
        try:
            cache_key = self._get_cache_key(prompt)
            cache_file = os.path.join(self.cache_dir, f"{cache_key}.json")
            
            cache_data = {
                'timestamp': datetime.now().isoformat(),
                'response': response
            }
            
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
                
            logger.info(f"Resposta salva no cache: {cache_file}")
        except Exception as e:
            logger.warning(f"Erro ao salvar no cache: {str(e)}")
    
    def generate(self, prompt):
        """
        Chama a API do LLM para processar o prompt e retorna o resultado já parseado como JSON.
        """
        # Tenta obter do cache primeiro
        cached_response = self._get_from_cache(prompt)
        if cached_response:
            return parse_llm_response(cached_response)
            
        # Se não estiver em cache, chama a API
        response_text = self.call_api(prompt)
        
        # Se a resposta for válida, salva no cache
        if response_text:
            self._save_to_cache(prompt, response_text)
            
        return parse_llm_response(response_text)
    
    def call_api(self, prompt, max_retries=3, retry_delay=2):
        """
        Chama a API do LLM com o prompt fornecido.
        """
        endpoint = urljoin(self.api_url, "api/generate")
        
        # Log do prompt truncado para evitar dumps grandes
        logger.debug(f"Enviando prompt para LLM: {self._truncate_text(prompt)}")
        
        data = {
            "model": self.model,
            "prompt": prompt,
            "stream": False
        }
        
        for attempt in range(max_retries):
            try:
                response = requests.post(endpoint, json=data, timeout=60)
                
                if response.status_code == 200:
                    result = response.json()
                    response_text = result.get('response', '')
                    
                    # Log da resposta truncada para evitar dumps grandes
                    logger.info("Resposta do LLM recebida com sucesso")
                    logger.debug(f"Resposta do LLM: {self._truncate_text(response_text)}")
                    
                    return response_text
                else:
                    logger.error(f"Erro na API do LLM: {response.status_code} - {response.text}")
            except requests.RequestException as e:
                logger.error(f"Erro de conexão com a API do LLM: {str(e)}")
            
            if attempt < max_retries - 1:
                logger.info(f"Tentando novamente em {retry_delay} segundos...")
                time.sleep(retry_delay)
                # Aumenta o tempo de espera entre tentativas
                retry_delay *= 2
        
        logger.error(f"Falha após {max_retries} tentativas de chamar a API do LLM")
        return None

# Mantém a função original para compatibilidade
def call_llm_api(prompt):
    """
    Chama a API do Ollama usando o modelo DeepSeek para processar o prompt.
    """
    api = LlmApi()
    return api.call_api(prompt)

def parse_llm_response(response):
    """
    Analisa a resposta do LLM e tenta extrair um objeto JSON.
    Lida com casos onde o JSON pode estar envolvido em texto adicional.
    """
    # Se a resposta estiver vazia, retorna um dicionário vazio
    if not response or response.strip() == "":
        logger.warning("Resposta do LLM vazia")
        return {}
        
    # Se a resposta for exatamente "{}", retorna um dicionário vazio
    if response.strip() == "{}":
        logger.info("Resposta do LLM é um JSON vazio")
        return {}
    
    # Remove prefixos comuns de código
    response = re.sub(r'^.*?```(?:json)?', '', response, flags=re.DOTALL)
    response = re.sub(r'```.*?$', '', response, flags=re.DOTALL)
    
    # Remove frases introdutórias comuns
    response = re.sub(r'^.*?(?:Aqui está|Baseado na|Com base na|Analisando o).*?JSON.*?:', '', response, flags=re.DOTALL)
    
    # Tenta encontrar um objeto JSON na resposta usando regex
    json_pattern = r'({[\s\S]*?})'
    json_matches = re.findall(json_pattern, response)
    
    # Se encontrou possíveis objetos JSON, tenta analisá-los
    if json_matches:
        for json_str in json_matches:
            try:
                # Tenta analisar o objeto JSON encontrado
                result = json.loads(json_str)
                logger.info(f"JSON extraído com sucesso: {json_str}")
                
                # Valida os seletores para garantir que são CSS válidos
                validated_result = {}
                for key, value in result.items():
                    if value and isinstance(value, str):
                        # Remove espaços no início e fim
                        value = value.strip()
                        # Verifica se o valor parece ser um seletor CSS válido
                        if key == 'list_selector' or key in ['title', 'price', 'address', 'description', 'area', 'property_type', 'auction_date', 'image_url']:
                            # Verifica se o seletor parece ser válido
                            if value.startswith('http') or value.startswith('{') or value.startswith('<'):
                                logger.warning(f"Seletor inválido para {key}: {value}")
                                validated_result[key] = None
                            else:
                                validated_result[key] = value
                        else:
                            validated_result[key] = value
                    else:
                        validated_result[key] = value
                
                return validated_result
            except json.JSONDecodeError as e:
                logger.warning(f"Erro ao analisar JSON: {str(e)}, tentando próximo match")
                continue
    
    # Se não encontrou um objeto JSON válido, tenta extrair seletores diretamente
    try:
        # Procura por padrões como "chave": "valor" ou "chave": valor
        pattern = r'"([^"]+)"\s*:\s*(?:"([^"]*)"|(null|true|false|[\d.]+)|(\{.*?\})|(\[.*?\]))'
        matches = re.findall(pattern, response)
        
        if matches:
            result = {}
            for match in matches:
                key = match[0]
                # Pega o primeiro valor não vazio entre os grupos de captura
                value = next((v for v in match[1:] if v), "")
                
                # Converte "null" para None
                if value == "null":
                    value = None
                
                # Valida o valor se for um seletor
                if value and isinstance(value, str) and (key == 'list_selector' or key in ['title', 'price', 'address', 'description', 'area', 'property_type', 'auction_date', 'image_url']):
                    value = value.strip()
                    if value.startswith('http') or value.startswith('{') or value.startswith('<'):
                        logger.warning(f"Seletor inválido para {key}: {value}")
                        result[key] = None
                    else:
                        result[key] = value
                else:
                    result[key] = value
            
            logger.info(f"Seletores extraídos manualmente: {result}")
            return result
    except Exception as e:
        logger.warning(f"Erro ao extrair seletores manualmente: {str(e)}")
    
    # Última tentativa: procura por seletores CSS comuns no texto
    try:
        # Procura por padrões como "title": ".class" ou "price": "#id"
        selector_pattern = r'"([^"]+)"\s*:\s*"([.#][^"]+)"'
        selector_matches = re.findall(selector_pattern, response)
        
        if selector_matches:
            result = {}
            for key, value in selector_matches:
                if key in ['title', 'price', 'address', 'description', 'area', 'property_type', 'auction_date', 'image_url', 'list_selector']:
                    result[key] = value.strip()
            
            if result:
                logger.info(f"Seletores CSS extraídos: {result}")
                return result
    except Exception as e:
        logger.warning(f"Erro ao extrair seletores CSS: {str(e)}")
    
    # Tenta extrair qualquer texto que pareça um seletor CSS
    try:
        css_pattern = r'[.#][a-zA-Z0-9_-]+(?:\s+[.#]?[a-zA-Z0-9_-]+)*'
        css_matches = re.findall(css_pattern, response)
        
        if css_matches:
            # Filtra seletores que parecem válidos
            valid_selectors = [s for s in css_matches if len(s) > 2 and not s.startswith('http')]
            
            if valid_selectors:
                logger.info(f"Encontrados possíveis seletores CSS: {valid_selectors}")
                # Tenta associar os seletores a campos comuns
                fields = ['title', 'price', 'address', 'description', 'area', 'property_type', 'auction_date', 'image_url']
                result = {}
                
                # Associa os seletores encontrados aos campos
                for i, field in enumerate(fields):
                    if i < len(valid_selectors):
                        result[field] = valid_selectors[i]
                
                if result:
                    logger.info(f"Seletores CSS extraídos de texto: {result}")
                    return result
    except Exception as e:
        logger.warning(f"Erro ao extrair seletores CSS de texto: {str(e)}")
    
    # Se tudo falhar, retorna um dicionário vazio
    logger.warning("Todas as tentativas de extrair JSON falharam, retornando dicionário vazio")
    return {}