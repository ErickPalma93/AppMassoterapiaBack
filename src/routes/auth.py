# src/routes/auth.py

from flask import Blueprint, jsonify, request
from src.models.admin_user import AdminUser
from src.extensions import db, bcrypt
from flask_jwt_extended import jwt_required, get_jwt_identity, create_access_token

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({"message": "Email e senha são obrigatórios"}), 400

    admin_user = AdminUser.query.filter_by(email=email).first()

    if not admin_user or not admin_user.check_password(password):
        return jsonify({"message": "Credenciais inválidas"}), 401

    access_token = create_access_token(identity=str(admin_user.id))

    return jsonify({"message": "Login bem-sucedido", "user": admin_user.to_dict(), "access_token": access_token}), 200


# Esta rota é para o registro inicial de UM administrador, geralmente feito uma vez na instalação.
# NÃO será a rota usada por um admin logado para criar outros.
@auth_bp.route('/register_admin', methods=['POST'])
def register_admin():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({"message": "Email e senha são obrigatórios"}), 400

    if AdminUser.query.filter_by(email=email).first():
        return jsonify({"message": "Email de administrador já registrado"}), 409

    new_admin = AdminUser(email=email)
    new_admin.set_password(password)

    db.session.add(new_admin)
    db.session.commit()

    return jsonify({"message": "Administrador registrado com sucesso", "admin_user": new_admin.to_dict()}), 201


@auth_bp.route('/admin/change-password', methods=['PUT'])
@jwt_required()
def change_admin_password():
    current_admin_id = get_jwt_identity()
    admin_user = AdminUser.query.get(int(current_admin_id))

    if not admin_user:
        return jsonify({"error": "Usuário não encontrado."}), 404

    data = request.get_json()
    current_password = data.get('current_password')
    new_password = data.get('new_password')

    if not current_password or not new_password:
        return jsonify({"error": "Senha atual e nova senha são obrigatórias."}), 400

    if not admin_user.check_password(current_password):
        return jsonify({"error": "Senha atual incorreta."}), 401

    if len(new_password) < 6:
        return jsonify({"error": "A nova senha deve ter no mínimo 6 caracteres."}), 400

    admin_user.set_password(new_password)
    db.session.commit()

    return jsonify({"message": "Senha alterada com sucesso!"}), 200


@auth_bp.route('/admin/create-admin', methods=['POST'])
@jwt_required()  # Protegida: Somente admins logados podem criar outros admins
def create_new_admin():
    current_admin_id = get_jwt_identity()
    current_admin_user = AdminUser.query.get(int(current_admin_id))

    if not current_admin_user:
        return jsonify({"error": "Administrador atual não encontrado."}), 404

    data = request.get_json()

    # 1. Valida a senha do admin logado
    current_admin_password = data.get('current_admin_password')
    if not current_admin_password or not current_admin_user.check_password(current_admin_password):
        return jsonify({"error": "Senha do administrador atual incorreta ou não fornecida."}), 401

    # 2. Obtém e valida os dados do novo admin
    new_admin_email = data.get('new_admin_email')
    new_admin_password = data.get('new_admin_password')

    if not new_admin_email or not new_admin_password:
        return jsonify({"error": "Email e senha para o novo administrador são obrigatórios."}), 400

    if AdminUser.query.filter_by(email=new_admin_email).first():
        return jsonify({"error": "Email para o novo administrador já registrado."}), 409

    if len(new_admin_password) < 6:
        return jsonify({"error": "A senha do novo administrador deve ter no mínimo 6 caracteres."}), 400

    # 3. Cria o novo admin
    new_admin = AdminUser(email=new_admin_email)
    new_admin.set_password(new_admin_password)  # Hash da nova senha

    db.session.add(new_admin)
    db.session.commit()

    return jsonify({"message": "Novo administrador criado com sucesso!", "admin_user": new_admin.to_dict()}), 201