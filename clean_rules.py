#!/usr/bin/env python3
"""
Script para limpar as regras de scraping existentes no banco de dados.
"""
from myproject.database.connection import get_session
from myproject.database.models import ScrapingRule

def clean_rules():
    """
    Remove todas as regras de scraping existentes no banco de dados.
    """
    session = get_session()
    try:
        # Conta o número de regras existentes
        count = session.query(ScrapingRule).count()
        print(f"Encontradas {count} regras de scraping no banco de dados.")
        
        # Remove todas as regras
        session.query(ScrapingRule).delete()
        session.commit()
        
        print(f"Todas as regras foram removidas com sucesso.")
    except Exception as e:
        session.rollback()
        print(f"Erro ao limpar regras: {str(e)}")
    finally:
        session.close()

if __name__ == "__main__":
    clean_rules() 