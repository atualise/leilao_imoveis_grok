"""
Script para inicializar o banco de dados com o esquema correto.
"""
from myproject.database.models import Base, engine

def initialize_database():
    """
    Cria todas as tabelas definidas nos modelos.
    """
    print("Inicializando banco de dados...")
    Base.metadata.create_all(engine)
    print("Banco de dados inicializado com sucesso!")

if __name__ == "__main__":
    initialize_database() 