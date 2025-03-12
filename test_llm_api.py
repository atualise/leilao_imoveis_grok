import logging
import sys
from myproject.llm.api import LlmApi

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

def test_llm_api():
    """
    Testa a API do LLM com um prompt simples.
    """
    api = LlmApi()
    
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
    result = api.generate(prompt)
    
    print("\nResultado parseado:")
    print(result)
    
    if result and 'list_selector' in result:
        print("\nTeste bem-sucedido! A API retornou um JSON válido com o campo 'list_selector'.")
    else:
        print("\nTeste falhou! A API não retornou um JSON válido com o campo 'list_selector'.")

if __name__ == "__main__":
    test_llm_api()