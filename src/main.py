import os
import sys

# DON'T CHANGE THIS !!!
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from flask import Flask, send_from_directory
from flask_cors import CORS # Removido a importação duplicada de CORS
from flask_jwt_extended import JWTManager # Importe JWTManager

# Importe db e bcrypt do arquivo de extensões
from src.extensions import db, bcrypt
from flask_migrate import Migrate # Se você estiver usando Flask-Migrate

# Importe seus modelos
from src.models.user import User
from src.models.admin_user import AdminUser
from src.models.service import Service
from src.models.customer import Customer
from src.models.booking import Booking
from src.models.blocked_time import BlockedTime

# Importar seus blueprints
from src.routes.auth import auth_bp
from src.routes.user import user_bp
from src.routes.services import services_bp
from src.routes.bookings import bookings_bp
from src.routes.blocked_times import blocked_times_bp
from src.routes.whatsapp import whatsapp_bp
from src.routes.admin import admin_bp # Já estava importado, mantido

app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), 'static'))

# --- Configurações do Flask ---
app.config['SECRET_KEY'] = 'asdf#FGSgvasgf$5$WGT' # Sua chave secreta
# **MUDAÇA IMPORTANTE AQUI:** Adicione a chave secreta para JWT
app.config["JWT_SECRET_KEY"] = "sua_chave_secreta_para_jwt_aqui" # MUDE ISSO PARA UMA CHAVE DIFERENTE E SEGURA!

# Configuração do banco de dados (antes de inicializar db)
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(os.path.dirname(__file__), 'database', 'app.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# --- Inicializar Extensões ---
db.init_app(app)
bcrypt.init_app(app)
jwt = JWTManager(app) # <--- **ESSENCIAL:** Inicialize o JWTManager com o app

# --- Configurar CORS ---
# Esta linha é suficiente para configurar o CORS corretamente.
# Ela permite requisições PUT e outras para endpoints sob /api/
# Especificamos a origem do frontend para segurança (http://localhost:5173).
CORS(app, resources={r"/api/*": {"origins": "http://localhost:5173", "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"]}})


# Registrar blueprints
app.register_blueprint(user_bp, url_prefix='/api')
app.register_blueprint(services_bp, url_prefix='/api')
app.register_blueprint(bookings_bp, url_prefix='/api')
app.register_blueprint(blocked_times_bp, url_prefix='/api')
app.register_blueprint(whatsapp_bp, url_prefix='/api')
app.register_blueprint(auth_bp, url_prefix='/api/auth') # <--- MANTENHA ESTE PREFIXO PARA O Blueprint de AUTH
app.register_blueprint(admin_bp, url_prefix='/api')


def init_database():
    """Inicializa o banco de dados com dados de exemplo"""
    with app.app_context():
        db.create_all()

        # Verificar se já existe um administrador
        if AdminUser.query.count() == 0:
            print("Nenhum administrador encontrado. Criando um administrador padrão...")
            admin_user = AdminUser(email='evelin@teste.com')
            admin_user.set_password('eve123') # LEMBRE-SE DE TROCAR ESSA SENHA EM PRODUÇÃO!
            db.session.add(admin_user)
            db.session.commit()
            print("Administrador padrão 'admin@evelinpalma.com' criado.")

        # Verificar se já existem serviços
        if Service.query.count() == 0:
            services_data = [
                {'name': 'Liberação miofascial', 'description': 'Técnica para liberação de tensões musculares profundas', 'price': 120.00, 'category': 'avulsas'},
                {'name': 'Drenagem linfática', 'description': 'Estimula a circulação e reduz retenção de líquidos', 'price': 120.00, 'category': 'avulsas'},
                {'name': 'Modeladora', 'description': 'Massagem para modelagem corporal e redução de medidas', 'price': 120.00, 'category': 'avulsas'},
                {'name': 'Ventosaterapia', 'description': 'Terapia com ventosas para alívio de tensões', 'price': 70.00, 'category': 'avulsas'},
                {'name': 'Sauna', 'description': 'Desintoxicação e relaxamento em ambiente controlado', 'price': 110.00, 'category': 'avulsas'},
                {'name': 'Esfoliação corporal', 'description': 'Renovação celular e hidratação da pele', 'price': 100.00, 'category': 'avulsas'},
                {'name': 'Massagem relaxante', 'description': 'Alívio do estresse e tensões musculares', 'price': 120.00, 'category': 'avulsas'},
                {'name': 'Massagem terapêutica', 'description': 'Tratamento específico para dores e lesões', 'price': 120.00, 'category': 'avulsas'},
                {'name': 'Lipocavitação', 'description': 'Redução de gordura localizada com ultrassom', 'price': 100.00, 'category': 'avulsas'},
                {'name': 'Corrente Russa', 'description': 'Eletroestimulação para fortalecimento muscular', 'price': 100.00, 'category': 'avulsas'},
                {'name': 'Endermoterapia', 'description': 'Tratamento para celulite e flacidez', 'price': 100.00, 'category': 'avulsas'},
                # Combos
                {'name': 'Miofascial + Sauna', 'description': 'Liberação miofascial seguida de sessão de sauna', 'price': 200.00, 'category': 'combos', 'services_included': '["Liberação miofascial", "Sauna"]'},
                {'name': 'Drenagem + Sauna', 'description': 'Drenagem linfática seguida de sessão de sauna', 'price': 200.00, 'category': 'combos', 'services_included': '["Drenagem linfática", "Sauna"]'},
                {'name': 'Modeladora + Sauna', 'description': 'Massagem modeladora seguida de sessão de sauna', 'price': 200.00, 'category': 'combos', 'services_included': '["Modeladora", "Sauna"]'},
                {'name': 'Sauna + Esfoliação', 'description': 'Sessão de sauna seguida de esfoliação corporal', 'price': 200.00, 'category': 'combos', 'services_included': '["Sauna", "Esfoliação corporal"]'},
                # Pacotes
                {'name': 'Pacote 1: 5 massagens + 5 lipocavitação', 'description': '10 sessões para relaxamento e redução de medidas', 'price': 850.00, 'category': 'pacotes', 'sessions': 10},
                {'name': 'Pacote 2: 4 modeladora + 4 lipocavitação', 'description': '8 sessões para modelagem corporal', 'price': 680.00, 'category': 'pacotes', 'sessions': 8},
                {'name': 'Pacote 3: 2 drenagem + 2 modeladora', 'description': '4 sessões para drenagem e modelagem', 'price': 400.00, 'category': 'pacotes', 'sessions': 4},
                {'name': 'Pacote 4: 5 lipocavitação', 'description': '5 sessões de lipocavitação', 'price': 350.00, 'category': 'pacotes', 'sessions': 5},
                {'name': 'Pacote 5: 4 corrente russa + 4 lipocavitação', 'description': '8 sessões para fortalecimento e redução', 'price': 560.00, 'category': 'pacotes', 'sessions': 8},
                {'name': 'Pacote 6: 4 drenagem + 2 sauna', 'description': '6 sessões para drenagem e relaxamento', 'price': 580.00, 'category': 'pacotes', 'sessions': 6},
                {'name': 'Pacote 7: 4 sessões mistas de massagens', 'description': '4 sessões de massagens variadas', 'price': 400.00, 'category': 'pacotes', 'sessions': 4},
                {'name': 'Pacote 8: 5 endermoterapia', 'description': '5 sessões de endermoterapia', 'price': 350.00, 'category': 'pacotes', 'sessions': 5},
                # Bronzeamento
                {'name': '1 sessão', 'description': 'Uma sessão de bronzeamento artificial', 'price': 80.00, 'category': 'bronzeamento'},
                {'name': '2 sessões', 'description': 'Duas sessões de bronzeamento artificial', 'price': 150.00, 'category': 'bronzeamento'},
                {'name': '3 sessões', 'description': 'Três sessões de bronzeamento artificial', 'price': 210.00, 'category': 'bronzeamento'},
            ]

            for service_data in services_data:
                service = Service(**service_data)
                db.session.add(service)

            db.session.commit()
            print("Banco de dados inicializado com serviços de exemplo")

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    static_folder_path = app.static_folder
    if static_folder_path is None:
            return "Static folder not configured", 404

    if path != "" and os.path.exists(os.path.join(static_folder_path, path)):
        return send_from_directory(static_folder_path, path)
    else:
        index_path = os.path.join(static_folder_path, 'index.html')
        if os.path.exists(index_path):
            return send_from_directory(static_folder_path, 'index.html')
        else:
            return "index.html not found", 404

if __name__ == '__main__':
    init_database()
    app.run(host='0.0.0.0', port=5000, debug=True)