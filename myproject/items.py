import scrapy

class AuctionItem(scrapy.Item):
    # Campos básicos
    url = scrapy.Field()
    title = scrapy.Field()
    price = scrapy.Field()
    description = scrapy.Field()
    
    # Campos adicionais
    address = scrapy.Field()
    auction_date = scrapy.Field()
    area = scrapy.Field()
    property_type = scrapy.Field()
    image_url = scrapy.Field()
    
    # Metadados
    extracted_at = scrapy.Field()
    source_domain = scrapy.Field()
    
    # Caminho do screenshot (novo)
    screenshot_path = scrapy.Field()