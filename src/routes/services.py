from flask import Blueprint, jsonify, request
from src.models.user import db
from src.models.service import Service

services_bp = Blueprint('services', __name__)


@services_bp.route('/services', methods=['GET'])
def get_services():
    """Retorna todos os serviços ativos (para clientes) ou todos (para gerenciamento).
    Pode receber um parâmetro 'all=true' para retornar serviços inativos também.
    """
    try:
        # Apenas para fins de gerenciamento: retornar todos os serviços, incluindo inativos
        # Para o front-end voltado ao cliente, manteria apenas o filter_by(active=True)
        # ou faria um endpoint separado para "serviços visíveis para o cliente".
        if request.args.get('all') == 'true':
            services = Service.query.all()
        else:
            services = Service.query.filter_by(active=True).all()

        return jsonify([service.to_dict() for service in services])
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@services_bp.route('/services/<int:service_id>', methods=['GET'])
def get_service(service_id):
    """Retorna um serviço específico."""
    try:
        service = Service.query.get_or_404(service_id)
        return jsonify(service.to_dict())
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@services_bp.route('/services', methods=['POST'])
def create_service():
    """Cria um novo serviço."""
    try:
        data = request.get_json()

        # Validar dados mínimos
        if not all(k in data for k in ('name', 'price', 'category')):
            return jsonify({'error': 'Nome, preço e categoria são campos obrigatórios.'}), 400

        # Lógica para promoção na criação
        on_promotion = data.get('on_promotion', False)
        original_price = None
        current_price = data['price']

        if on_promotion:
            # Se for uma promoção, 'original_price' deve ser fornecido ou deduzido
            original_price = data.get('original_price')
            if original_price is None:
                # Se 'original_price' não for fornecido, assumimos que o 'price' atual é o promocional
                # e o 'original_price' deveria ter sido um valor maior.
                # Para evitar inconsistências, poderíamos retornar um erro ou forçar original_price = current_price
                # Por simplicidade, vamos exigir que original_price seja fornecido se on_promotion for True.
                return jsonify({'error': 'Original price é obrigatório para serviços em promoção.'}), 400

            if current_price >= original_price:
                return jsonify({'error': 'O preço promocional deve ser menor que o preço original.'}), 400
        else:
            # Se não estiver em promoção, o preço atual é o original
            original_price = current_price

        service = Service(
            name=data['name'],
            description=data.get('description', ''),
            price=current_price,
            original_price=original_price,
            on_promotion=on_promotion,
            category=data['category'],
            sessions=data.get('sessions', 1),
            services_included=data.get('services_included'),
            duration_minutes=data.get('duration_minutes', 30),
            active=data.get('active', True)  # Permite definir como inativo ao criar, se necessário
        )

        db.session.add(service)
        db.session.commit()

        return jsonify(service.to_dict()), 201
    except KeyError as e:
        db.session.rollback()
        return jsonify({'error': f'Campo obrigatório ausente: {e}'}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@services_bp.route('/services/<int:service_id>', methods=['PUT'])
def update_service(service_id):
    """Atualiza um serviço existente, incluindo lógica de promoção."""
    try:
        service = Service.query.get_or_404(service_id)
        data = request.get_json()

        # Atualiza campos básicos
        service.name = data.get('name', service.name)
        service.description = data.get('description', service.description)
        service.category = data.get('category', service.category)
        service.sessions = data.get('sessions', service.sessions)
        service.services_included = data.get('services_included', service.services_included)
        service.duration_minutes = data.get('duration_minutes', service.duration_minutes)
        service.active = data.get('active', service.active)

        # Lógica de atualização de preço e promoção
        new_price = data.get('price')
        new_on_promotion = data.get('on_promotion')
        new_original_price = data.get('original_price')

        # Se o preço atualizado for fornecido
        if new_price is not None:
            service.price = new_price

        # Se 'on_promotion' for explicitamente definido
        if new_on_promotion is not None:
            service.on_promotion = new_on_promotion

            if service.on_promotion:
                # Se o serviço está sendo colocado em promoção
                if new_original_price is not None:
                    service.original_price = new_original_price
                elif service.original_price is None:
                    # Se não houver 'original_price' e estamos ativando a promoção,
                    # o preço atual do serviço antes da atualização passa a ser o 'original_price'.
                    # Isso é crucial para que a porcentagem de desconto seja calculada corretamente.
                    # No PUT, o 'price' que chega é o preço já para ser aplicado (novo/promocional).
                    # O 'original_price' deve ser o valor que era ANTES da promoção.
                    # Se o front-end não enviar explicitamente um `original_price` quando ativa a promoção,
                    # podemos assumir que o 'price' que **estava** no banco (antes deste PUT) era o original.
                    # No entanto, para clareza e controle, é melhor que o front-end envie o `original_price`
                    # ou que o backend guarde o valor anterior antes de sobrescrever.
                    # Para simplificar, vou assumir que se `on_promotion` for True, `original_price` virá.
                    return jsonify({'error': 'Para ativar a promoção, "original_price" deve ser fornecido.'}), 400

                if service.price >= service.original_price:
                    return jsonify({'error': 'O preço promocional deve ser menor que o preço original.'}), 400
            else:
                # Se a promoção for desativada
                service.original_price = None  # Reseta o preço original
                # O preço atual (service.price) já estará no valor não promocional
                # se o front-end enviou o preço normal na requisição PUT.
                # Se não enviou, o service.price permanecerá como o último preço promocional,
                # o que pode ser indesejável. É bom que o front-end envie o 'price' normal
                # quando desativa a promoção.

        # Se 'original_price' for explicitamente definido (independentemente de 'on_promotion')
        elif new_original_price is not None:
            service.original_price = new_original_price
            # Se 'original_price' foi definido e 'on_promotion' não, assumimos que não é uma promoção
            # ou que a lógica de 'on_promotion' será tratada separadamente pelo front.
            # No entanto, a forma mais segura é que 'on_promotion' e 'original_price' sejam enviados juntos.

        db.session.commit()

        return jsonify(service.to_dict())
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@services_bp.route('/services/<int:service_id>/deactivate', methods=['PUT'])
def deactivate_service(service_id):
    """Desativa um serviço (soft delete)."""
    try:
        service = Service.query.get_or_404(service_id)
        service.active = False
        db.session.commit()

        return jsonify({'message': 'Serviço desativado com sucesso'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@services_bp.route('/services/<int:service_id>/activate', methods=['PUT'])
def activate_service(service_id):
    """Ativa um serviço previamente desativado."""
    try:
        service = Service.query.get_or_404(service_id)
        service.active = True
        db.session.commit()

        return jsonify({'message': 'Serviço ativado com sucesso'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@services_bp.route('/services/<int:service_id>', methods=['DELETE'])
def delete_service_permanent(service_id):
    """Exclui um serviço permanentemente do banco de dados (uso cauteloso)."""
    try:
        service = Service.query.get_or_404(service_id)
        db.session.delete(service)
        db.session.commit()

        return jsonify({'message': 'Serviço excluído permanentemente com sucesso'}), 204
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500