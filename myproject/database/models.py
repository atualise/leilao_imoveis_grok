from sqlalchemy import Column, Integer, String, Text, DateTime, Float, Boolean
from sqlalchemy.ext.declarative import declarative_base
from myproject.database.connection import engine
from datetime import datetime

Base = declarative_base()

class ScrapingRule(Base):
    __tablename__ = 'scraping_rules'
    id = Column(Integer, primary_key=True)
    domain = Column(String, unique=True)
    list_selector = Column(String)
    detail_selectors = Column(Text)  # JSON string

class ProblemSite(Base):
    __tablename__ = 'problem_sites'
    id = Column(Integer, primary_key=True)
    domain = Column(String, unique=True)
    first_error = Column(DateTime, default=datetime.now)
    last_error = Column(Text)
    attempts = Column(Integer, default=1)
    is_blocked = Column(Integer, default=0)  # 0=não, 1=sim

class SelectorCache(Base):
    __tablename__ = 'selector_cache'
    id = Column(Integer, primary_key=True)
    url = Column(String, unique=True)
    domain = Column(String, index=True)
    page_type = Column(String)  # 'list' ou 'detail'
    selectors = Column(Text)  # JSON string
    success_rate = Column(Float, default=0.0)  # Taxa de sucesso (0-1)
    created_at = Column(DateTime, default=datetime.now)
    last_used = Column(DateTime, default=datetime.now)
    use_count = Column(Integer, default=1)
    is_valid = Column(Boolean, default=True)

class AuctionData(Base):
    __tablename__ = 'auction_data'
    id = Column(Integer, primary_key=True)
    url = Column(String, unique=True)
    
    # Campos básicos
    title = Column(String)
    price = Column(String)
    description = Column(Text)
    
    # Campos adicionais
    address = Column(String)
    auction_date = Column(String)
    area = Column(String)
    property_type = Column(String)
    image_url = Column(String)
    
    # Metadados
    extracted_at = Column(DateTime, default=datetime.now)
    source_domain = Column(String)
    
    # Caminho do screenshot
    screenshot_path = Column(String, nullable=True)
    
    # Adições futuras
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    success_bid = Column(String, nullable=True)  # Valor do lance vencedor, se disponível