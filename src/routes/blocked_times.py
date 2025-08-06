from flask import Blueprint, jsonify, request
from src.models.user import db
from src.models.blocked_time import BlockedTime
from datetime import datetime

blocked_times_bp = Blueprint('blocked_times', __name__)

@blocked_times_bp.route('/blocked-times', methods=['GET'])
def get_blocked_times():
    """Retorna todos os horários bloqueados"""
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        query = BlockedTime.query.filter_by(active=True)
        
        if start_date:
            query = query.filter(BlockedTime.blocked_date >= datetime.strptime(start_date, '%Y-%m-%d').date())
        if end_date:
            query = query.filter(BlockedTime.blocked_date <= datetime.strptime(end_date, '%Y-%m-%d').date())
            
        blocked_times = query.order_by(BlockedTime.blocked_date).all()
        return jsonify([blocked_time.to_dict() for blocked_time in blocked_times])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@blocked_times_bp.route('/blocked-times', methods=['POST'])
def create_blocked_time():
    """Cria um novo bloqueio de horário"""
    try:
        data = request.get_json()
        
        blocked_time = BlockedTime(
            blocked_date=datetime.strptime(data['blocked_date'], '%Y-%m-%d').date(),
            start_time=datetime.strptime(data['start_time'], '%H:%M').time() if data.get('start_time') else None,
            end_time=datetime.strptime(data['end_time'], '%H:%M').time() if data.get('end_time') else None,
            reason=data.get('reason', '')
        )
        
        db.session.add(blocked_time)
        db.session.commit()
        
        return jsonify(blocked_time.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@blocked_times_bp.route('/blocked-times/<int:blocked_time_id>', methods=['DELETE'])
def delete_blocked_time(blocked_time_id):
    """Remove um bloqueio de horário"""
    try:
        blocked_time = BlockedTime.query.get_or_404(blocked_time_id)
        blocked_time.active = False
        db.session.commit()
        
        return jsonify({'message': 'Bloqueio removido com sucesso'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

