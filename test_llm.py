"""
Script para testar a API do LLM diretamente.
"""
import json
import requests
from myproject.config import OLLAMA_API_URL, OLLAMA_MODEL
from myproject.llm.api import call_llm_api, parse_llm_response

def test_llm_api():
    """
    Testa a API do LLM diretamente.
    """
    # Prompt simples para testar a API
    prompt = """
    Você é um especialista em web scraping especializado em sites de leilão de imóveis brasileiros.
    
    Sua tarefa é analisar o HTML a seguir e identificar o seletor CSS mais preciso para encontrar LINKS 
    para páginas de detalhes de imóveis individuais.
    
    Responda apenas com um objeto JSON no formato:
    {
      "selector": "seu_seletor_css_aqui"
    }
    """
    
    # Chama a API diretamente
    print("Chamando a API do LLM diretamente...")
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0,
            "num_predict": 150
        }
    }
    
    response = requests.post(f"{OLLAMA_API_URL}/api/generate", json=payload)
    
    print(f"Status code: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print("Resposta bruta:")
        print(result)
        
        # Tenta analisar a resposta
        llm_response = result.get("response", "").strip()
        print("\nTexto da resposta:")
        print(llm_response)
        
        # Tenta analisar como JSON
        print("\nTentando analisar como JSON:")
        parsed = parse_llm_response(llm_response)
        print(json.dumps(parsed, indent=2))
    else:
        print(f"Erro ao chamar a API: {response.text}")
    
    # Testa a função call_llm_api
    print("\nTestando a função call_llm_api...")
    llm_response = call_llm_api(prompt)
    print("Resposta da função call_llm_api:")
    print(llm_response)
    
    # Tenta analisar como JSON
    print("\nTentando analisar como JSON:")
    parsed = parse_llm_response(llm_response)
    print(json.dumps(parsed, indent=2))

if __name__ == "__main__":
    test_llm_api() 