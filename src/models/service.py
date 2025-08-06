from src.models.user import db

class Service(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Float, nullable=False) # Este será o preço atual (novo preço se estiver em promoção)
    original_price = db.Column(db.Float, nullable=True) # Preço original antes da promoção
    on_promotion = db.Column(db.Boolean, default=False) # Indica se o serviço está em promoção

    category = db.Column(db.String(50), nullable=False)  # avulsas, combos, pacotes, bronzeamento
    sessions = db.Column(db.Integer, default=1)  # Para pacotes
    services_included = db.Column(db.Text)  # Para combos (JSON string)
    duration_minutes = db.Column(db.Integer, default=30)
    active = db.Column(db.Boolean, default=True) # Para desativar/excluir logicamente

    def __repr__(self):
        return f'<Service {self.name}>'

    def to_dict(self):
        # Calcula a porcentagem de desconto se estiver em promoção
        discount_percentage = None
        if self.on_promotion and self.original_price and self.original_price > 0:
            discount_percentage = ((self.original_price - self.price) / self.original_price) * 100
            discount_percentage = round(discount_percentage, 2) # Arredonda para 2 casas decimais

        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'price': self.price,
            'original_price': self.original_price,
            'on_promotion': self.on_promotion,
            'discount_percentage': discount_percentage, # Campo calculado para o frontend
            'category': self.category,
            'sessions': self.sessions,
            'services_included': self.services_included,
            'duration_minutes': self.duration_minutes,
            'active': self.active
        }