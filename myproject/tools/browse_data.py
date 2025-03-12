#!/usr/bin/env python
"""
Ferramenta para visualizar dados coletados pelo scraper de leilões.
Execute com: python -m myproject.tools.browse_data
"""

import os
import sys
from datetime import datetime
from sqlalchemy.orm import sessionmaker
from myproject.database.models import AuctionData, ProblemSite, engine

def clear_screen():
    """Limpa a tela do terminal"""
    os.system('cls' if os.name == 'nt' else 'clear')

def print_header(title):
    """Imprime um cabeçalho formatado"""
    print("\n" + "=" * 80)
    print(f" {title} ".center(80, "="))
    print("=" * 80 + "\n")

def print_item(item, index=None):
    """Imprime os detalhes de um item de leilão"""
    prefix = f"[{index}] " if index is not None else ""
    print(f"{prefix}Título: {item.title}")
    print(f"    Preço: {item.price}")
    print(f"    Tipo: {item.property_type or 'Não especificado'}")
    print(f"    Endereço: {item.address or 'Não disponível'}")
    print(f"    Data do leilão: {item.auction_date or 'Não especificada'}")
    print(f"    URL: {item.url}")
    print(f"    Extraído em: {item.extracted_at.strftime('%d/%m/%Y %H:%M')}")
    print(f"    Fonte: {item.source_domain}")
    print()

def view_all_items(session):
    """Visualiza todos os itens no banco de dados"""
    clear_screen()
    print_header("TODOS OS ITENS")
    
    items = session.query(AuctionData).order_by(AuctionData.extracted_at.desc()).all()
    
    if not items:
        print("Nenhum item encontrado no banco de dados.\n")
        input("Pressione Enter para voltar ao menu principal...")
        return
        
    print(f"Total de itens: {len(items)}\n")
    
    for i, item in enumerate(items, 1):
        print_item(item, i)
        if i % 5 == 0 and i < len(items):
            input("Pressione Enter para continuar...")
            
    print(f"Total de {len(items)} itens mostrados.\n")
    input("Pressione Enter para voltar ao menu principal...")

def view_problem_sites(session):
    """Visualiza sites problemáticos"""
    clear_screen()
    print_header("SITES PROBLEMÁTICOS")
    
    sites = session.query(ProblemSite).order_by(ProblemSite.attempts.desc()).all()
    
    if not sites:
        print("Nenhum site problemático registrado.\n")
        input("Pressione Enter para voltar ao menu principal...")
        return
        
    print(f"Total de sites problemáticos: {len(sites)}\n")
    
    for i, site in enumerate(sites, 1):
        print(f"[{i}] Domínio: {site.domain}")
        print(f"    Tentativas: {site.attempts}")
        print(f"    Primeiro erro: {site.first_error}")
        print(f"    Último erro: {site.last_error}")
        print()
    
    input("Pressione Enter para voltar ao menu principal...")

def search_items(session):
    """Busca itens no banco de dados"""
    clear_screen()
    print_header("BUSCAR ITENS")
    
    # Verifica se há itens no banco antes de continuar
    if session.query(AuctionData).count() == 0:
        print("Não há itens no banco de dados para buscar.\n")
        input("Pressione Enter para voltar ao menu principal...")
        return
    
    term = input("Digite um termo para buscar (deixe em branco para cancelar): ").strip()
    
    if not term:
        return
        
    # Busca em vários campos
    items = session.query(AuctionData).filter(
        (AuctionData.title.like(f"%{term}%")) |
        (AuctionData.description.like(f"%{term}%")) |
        (AuctionData.address.like(f"%{term}%")) |
        (AuctionData.property_type.like(f"%{term}%"))
    ).all()
    
    if not items:
        print(f"\nNenhum item encontrado para o termo '{term}'.\n")
        input("Pressione Enter para voltar ao menu principal...")
        return
        
    clear_screen()
    print_header(f"RESULTADOS PARA '{term}'")
    print(f"Total de itens encontrados: {len(items)}\n")
    
    for i, item in enumerate(items, 1):
        print_item(item, i)
        
    input("Pressione Enter para voltar ao menu principal...")

def filter_by_price(session):
    """Filtra itens por faixa de preço"""
    clear_screen()
    print_header("FILTRAR POR PREÇO")
    
    # Verifica se há itens no banco antes de continuar
    if session.query(AuctionData).count() == 0:
        print("Não há itens no banco de dados para filtrar.\n")
        input("Pressione Enter para voltar ao menu principal...")
        return
    
    try:
        min_price = input("Preço mínimo (deixe em branco para não definir): ").strip()
        min_price = float(min_price) if min_price else None
        
        max_price = input("Preço máximo (deixe em branco para não definir): ").strip()
        max_price = float(max_price) if max_price else None
        
        query = session.query(AuctionData)
        
        if min_price is not None:
            # Tenta converter o preço para número antes de comparar
            query = query.filter(AuctionData.price.cast(float) >= min_price)
            
        if max_price is not None:
            query = query.filter(AuctionData.price.cast(float) <= max_price)
            
        items = query.all()
        
        if not items:
            print("\nNenhum item encontrado nessa faixa de preço.\n")
            input("Pressione Enter para voltar ao menu principal...")
            return
            
        clear_screen()
        price_range = ""
        if min_price is not None and max_price is not None:
            price_range = f"ENTRE {min_price} E {max_price}"
        elif min_price is not None:
            price_range = f"ACIMA DE {min_price}"
        elif max_price is not None:
            price_range = f"ABAIXO DE {max_price}"
            
        print_header(f"IMÓVEIS {price_range}")
        print(f"Total de itens encontrados: {len(items)}\n")
        
        for i, item in enumerate(items, 1):
            print_item(item, i)
            if i % 5 == 0 and i < len(items):
                input("Pressione Enter para continuar...")
                
    except ValueError:
        print("\nValor inválido. Use apenas números.\n")
        
    input("Pressione Enter para voltar ao menu principal...")

def main_menu():
    """Menu principal da aplicação"""
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        while True:
            clear_screen()
            print_header("VISUALIZADOR DE DADOS DE LEILÕES")
            
            try:
                count = session.query(AuctionData).count()
                problem_count = session.query(ProblemSite).count()
            except Exception as e:
                print(f"Erro ao acessar o banco de dados: {str(e)}")
                print("Reinicialize o banco de dados usando o script init_db.py\n")
                input("Pressione Enter para sair...")
                return
            
            print(f"Total de imóveis no banco: {count}")
            print(f"Total de sites problemáticos: {problem_count}\n")
            
            if count == 0:
                print("O banco de dados está vazio. Execute o scraper para coletar dados.\n")
                print("Execute: python fetch_and_scrape.py\n")
            
            print("1. Ver todos os imóveis")
            print("2. Buscar imóveis")
            print("3. Filtrar por preço")
            print("4. Ver sites problemáticos")
            print("0. Sair\n")
            
            choice = input("Escolha uma opção: ").strip()
            
            if choice == '1':
                view_all_items(session)
            elif choice == '2':
                search_items(session)
            elif choice == '3':
                filter_by_price(session)
            elif choice == '4':
                view_problem_sites(session)
            elif choice == '0':
                break
            else:
                print("\nOpção inválida. Tente novamente.\n")
                input("Pressione Enter para continuar...")
    finally:
        session.close()

if __name__ == "__main__":
    # Verifica se o banco de dados existe
    if not os.path.exists('auction.db'):
        print("Erro: Banco de dados não encontrado.")
        print("Execute primeiro o script fetch_and_scrape.py para criar o banco de dados.")
        sys.exit(1)
        
    main_menu() 