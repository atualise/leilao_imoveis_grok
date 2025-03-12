"""
Script para adicionar dados de exemplo ao banco de dados.
"""
from datetime import datetime
from myproject.database.connection import get_session
from myproject.database.models import AuctionData, ProblemSite

def add_sample_data():
    """
    Adiciona alguns imóveis e sites problemáticos de exemplo ao banco de dados.
    """
    session = get_session()
    
    # Adiciona alguns imóveis de exemplo
    imoveis = [
        AuctionData(
            url="https://exemplo.com/imovel/1",
            title="Apartamento de 2 quartos no Centro",
            price="150000.00",
            description="Apartamento bem localizado, próximo ao comércio e transporte público.",
            address="Rua das Flores, 123, Centro, São Paulo - SP",
            auction_date="2023-12-15",
            area="75",
            property_type="Apartamento",
            image_url="https://exemplo.com/imagens/apt1.jpg",
            extracted_at=datetime.now(),
            source_domain="exemplo.com"
        ),
        AuctionData(
            url="https://exemplo.com/imovel/2",
            title="Casa com 3 quartos e jardim",
            price="320000.00",
            description="Linda casa com jardim, piscina e área de lazer completa.",
            address="Av. Principal, 456, Jardim das Flores, Rio de Janeiro - RJ",
            auction_date="2023-12-20",
            area="180",
            property_type="Casa",
            image_url="https://exemplo.com/imagens/casa1.jpg",
            extracted_at=datetime.now(),
            source_domain="exemplo.com"
        ),
        AuctionData(
            url="https://outrosite.com/imovel/3",
            title="Terreno para construção",
            price="95000.00",
            description="Terreno plano, pronto para construção em condomínio fechado.",
            address="Rua dos Ipês, 789, Condomínio Verde, Curitiba - PR",
            auction_date="2024-01-10",
            area="450",
            property_type="Terreno",
            image_url="https://outrosite.com/imagens/terreno1.jpg",
            extracted_at=datetime.now(),
            source_domain="outrosite.com"
        )
    ]
    
    for imovel in imoveis:
        session.add(imovel)
    
    # Adiciona alguns sites problemáticos de exemplo
    problemas = [
        ProblemSite(
            domain="siteproblemático.com.br",
            attempts=5,
            last_error="DNS lookup failed",
            is_blocked=1
        ),
        ProblemSite(
            domain="outrositefalhando.com.br",
            attempts=3,
            last_error="HTTP 403 Forbidden"
        )
    ]
    
    for problema in problemas:
        session.add(problema)
    
    # Salva tudo no banco de dados
    session.commit()
    session.close()
    
    print("Dados de exemplo adicionados com sucesso!")

if __name__ == "__main__":
    add_sample_data() 