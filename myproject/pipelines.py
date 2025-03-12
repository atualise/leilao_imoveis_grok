from myproject.database.connection import get_session
from myproject.database.models import AuctionData
from urllib.parse import urlparse
from datetime import datetime
import re
import logging

class DatabasePipeline:
    def open_spider(self, spider):
        self.session = get_session()
        self.logger = logging.getLogger(__name__)

    def close_spider(self, spider):
        self.session.close()
        
    def clean_price(self, price_str):
        """
        Remove caracteres não numéricos e converte o preço para um formato padronizado.
        Por exemplo: "R$ 1.500.000,00" -> "1500000.00"
        """
        if not price_str:
            return price_str
            
        # Remove símbolos de moeda e pontuação irrelevante
        clean = re.sub(r'[^\d,.]', '', price_str)
        
        # Trata formatos brasileiros (1.234.567,89)
        if ',' in clean and '.' in clean:
            # Formato brasileiro (pontos como separadores de milhar e vírgula decimal)
            clean = clean.replace('.', '')
            clean = clean.replace(',', '.')
        elif ',' in clean:
            # Apenas vírgula como decimal
            clean = clean.replace(',', '.')
            
        # Tenta converter para float para garantir que é um número válido
        try:
            value = float(clean)
            return clean
        except ValueError:
            self.logger.warning(f"Não foi possível converter o preço: {price_str}")
            return price_str
            
    def extract_domain(self, url):
        """
        Extrai o domínio de uma URL.
        """
        return urlparse(url).netloc

    def process_item(self, item, spider):
        try:
            # Valores padrão para campos obrigatórios
            url = item.get('url', '')
            
            if not url:
                self.logger.error("Item sem URL ignorado")
                return item
                
            # Verifica se o item já existe no banco de dados
            existing = self.session.query(AuctionData).filter_by(url=url).first()
            if existing:
                self.logger.info(f"Item já existe no banco de dados: {url}")
                return item
                
            # Cria o objeto AuctionData com todos os campos possíveis
            auction = AuctionData(
                url=url,
                title=item.get('title', ''),
                price=self.clean_price(item.get('price', '')),
                description=item.get('description', ''),
                address=item.get('address', ''),
                auction_date=item.get('auction_date', ''),
                area=item.get('area', ''),
                property_type=item.get('property_type', ''),
                image_url=item.get('image_url', ''),
                screenshot_path=item.get('screenshot_path', ''),
                extracted_at=datetime.now(),
                source_domain=self.extract_domain(url)
            )
            
            self.session.add(auction)
            self.session.commit()
            self.logger.info(f"Item salvo com sucesso: {url}")
            
        except Exception as e:
            self.logger.error(f"Erro ao salvar item: {str(e)}")
            self.session.rollback()
            
        return item