import requests
import json
import re
import logging
import sys

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

def call_llm_api(prompt):
    """
    Chama a API do Ollama usando o modelo configurado.
    """
    api_url = "http://localhost:11434"
    model = "deepseek-coder:6.7b"
    
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0,
            "num_predict": 150
        }
    }
    
    try:
        response = requests.post(f"{api_url}/api/generate", json=payload)
        
        if response.status_code == 200:
            result = response.json().get("response", "").strip()
            logger.info(f"Resposta do LLM recebida com sucesso")
            return result
        else:
            logger.error(f"Erro ao chamar a API do LLM: {response.status_code}")
            logger.error(response.text)
            return ""
    except Exception as e:
        logger.error(f"Exceção ao chamar a API do LLM: {str(e)}")
        return ""

def parse_llm_response(response):
    """
    Analisa a resposta do LLM e tenta extrair um objeto JSON.
    """
    # Se a resposta estiver vazia, retorna um dicionário vazio
    if not response or response.strip() == "":
        logger.warning("Resposta do LLM vazia")
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
                return result
            except json.JSONDecodeError as e:
                logger.warning(f"Erro ao analisar JSON: {str(e)}, tentando próximo match")
                continue
    
    # Se não encontrou um objeto JSON válido, tenta analisar a resposta completa
    try:
        response = response.strip()
        logger.info(f"Tentando analisar resposta completa como JSON: {response}")
        return json.loads(response)
    except json.JSONDecodeError as e:
        logger.warning(f"Erro ao analisar resposta completa como JSON: {str(e)}")
        
        # Se tudo falhar, retorna um dicionário vazio
        return {}

def test_llm_api():
    """
    Testa a API do LLM com um prompt simples.
    """
    # Prompt de teste simples que deve retornar um JSON
    prompt = """
    Você é um especialista em web scraping. Forneça um seletor CSS para encontrar links para páginas de detalhes de imóveis.
    
    IMPORTANTE: Sua resposta deve ser APENAS um objeto JSON válido no seguinte formato, sem texto adicional, comentários ou explicações:
    {
        "list_selector": "a.property-card"
    }
    
    NÃO inclua markdown, texto explicativo, ou qualquer outro conteúdo além do JSON puro.
    """
    
    print("Enviando prompt para a API do LLM...")
    response_text = call_llm_api(prompt)
    
    print("\nResposta bruta:")
    print(response_text)
    
    result = parse_llm_response(response_text)
    
    print("\nResultado parseado:")
    print(result)
    
    if result and 'list_selector' in result:
        print("\nTeste bem-sucedido! A API retornou um JSON válido com o campo 'list_selector'.")
    else:
        print("\nTeste falhou! A API não retornou um JSON válido com o campo 'list_selector'.")

if __name__ == "__main__":
    test_llm_api()