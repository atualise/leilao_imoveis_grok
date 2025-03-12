# Scraper de Leilões de Imóveis

Sistema de web scraping especializado em extrair dados de imóveis em sites de leilão brasileiros.

## Funcionalidades

- Busca automática de sites de leilão de imóveis
- Navegação inteligente seguindo o fluxo: Home >> Listagem >> Detalhes
- Extração de dados detalhados dos imóveis (título, preço, descrição, localização, etc.)
- Cache de seletores CSS para melhorar a performance
- Detecção automática de CAPTCHAs e páginas de proteção
- Geração de seletores CSS usando LLM (Large Language Model)
- Fallbacks para casos de falha na extração

## Requisitos

- Python 3.8+
- Bibliotecas Python (ver `requirements.txt`)
- Chave de API para o modelo LLM (Grok, Claude ou similar)

## Instalação

1. Clone o repositório:
```bash
git clone https://github.com/seu-usuario/leilao_imoveis_grok.git
cd leilao_imoveis_grok
```

2. Crie e ative um ambiente virtual:
```bash
python -m venv venv
source venv/bin/activate  # No Windows: venv\Scripts\activate
```

3. Instale as dependências:
```bash
pip install -r requirements.txt
```

4. Configure a chave de API:
```bash
export API_KEY_GROK="sua-chave-api-aqui"
```

## Uso

### Script Simplificado

O script `scrape_auctions.py` oferece uma interface simplificada para executar o scraper:

```bash
# Modo básico (usa configurações padrão)
./scrape_auctions.py

# Especificar termo de busca
./scrape_auctions.py --termo "leilão de imóveis em São Paulo"

# Limitar número de imóveis por site
./scrape_auctions.py --itens 10

# Modo de operação (apenas listagem ou com detalhes)
./scrape_auctions.py --modo listagem
./scrape_auctions.py --modo detalhes

# Ativar modo de depuração
./scrape_auctions.py --debug
```

### Script Original

O script original `fetch_and_scrape_improved.py` oferece mais opções de configuração:

```bash
python fetch_and_scrape_improved.py "leilão de imóveis" --depth=2 --max-items=5 --debug
```

Parâmetros:
- Termo de busca (obrigatório): termo para buscar sites de leilão
- `--depth`: profundidade de navegação (1 = apenas listagem, 2 = listagem + detalhes)
- `--max-items`: número máximo de imóveis a extrair por site
- `--debug`: ativa logs detalhados

### Diagnóstico

O script `diagnose_extractions.py` ajuda a analisar os dados extraídos:

```bash
# Análise completa
./diagnose_extractions.py

# Análise específica
./diagnose_extractions.py --analise seletores
./diagnose_extractions.py --analise imoveis
./diagnose_extractions.py --analise logs
```

## Estrutura do Projeto

- `myproject/`: Pacote principal
  - `spiders/`: Contém os spiders do Scrapy
    - `auction_spider.py`: Spider principal para leilões
  - `database/`: Módulos de banco de dados
  - `llm/`: Integração com API de LLM
  - `utils/`: Utilitários diversos
- `scrape_auctions.py`: Script simplificado
- `fetch_and_scrape_improved.py`: Script original
- `diagnose_extractions.py`: Ferramenta de diagnóstico

## Fluxo de Navegação

O sistema segue um fluxo específico de navegação:

1. **Home**: Página inicial do site de leilão
2. **Listagem**: Páginas com listas de imóveis disponíveis
3. **Detalhes**: Páginas com informações detalhadas de um imóvel específico

Este fluxo é controlado pelo parâmetro `depth`:
- `depth=1`: Navega apenas até as páginas de listagem
- `depth=2`: Navega até as páginas de detalhes (padrão)

## Solução de Problemas

### Dados não estão sendo extraídos corretamente

1. Verifique se a profundidade está configurada corretamente (deve ser 2 para extrair detalhes)
2. Execute o diagnóstico para verificar os seletores: `./diagnose_extractions.py --analise seletores`
3. Verifique os logs para identificar erros: `./diagnose_extractions.py --analise logs`

### CAPTCHAs ou Bloqueios

1. Alguns sites implementam proteções contra scraping
2. O sistema tenta detectar e registrar esses sites
3. Verifique os sites problemáticos: `./diagnose_extractions.py --analise logs`

## Contribuição

Contribuições são bem-vindas! Por favor, sinta-se à vontade para enviar pull requests ou abrir issues para melhorias e correções.

## Licença

Este projeto está licenciado sob a licença MIT - veja o arquivo LICENSE para detalhes.



