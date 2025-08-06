# src/routes/bookings.py
from flask import Blueprint, jsonify, request
from src.models.user import db
from src.models.booking import Booking
from src.models.customer import Customer
from src.models.service import Service
from src.models.blocked_time import BlockedTime
from datetime import datetime, date, time, timedelta
# Lembre-se de importar no topo do arquivo:
from sqlalchemy.exc import IntegrityError
from datetime import date, timedelta  # Apenas para garantir que estão presentes
import json

bookings_bp = Blueprint('bookings', __name__)

# Importe a função auxiliar do admin.py para reutilizar a lógica da regra recorrente
from src.routes.admin import get_recurring_unavailable_slots


@bookings_bp.route('/bookings', methods=['GET'])
def get_bookings():
    """Retorna agendamentos com filtros opcionais por data, status, serviço e ordenação."""
    try:
        # Parâmetros de filtro
        single_date_str = request.args.get('date')  # Novo parâmetro para data única
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        status = request.args.get('status')
        service_id = request.args.get('service_id', type=int)  # Novo parâmetro para filtrar por serviço
        limit = request.args.get('limit', type=int)  # Novo parâmetro para limitar resultados
        order_by = request.args.get('order_by')  # Novo parâmetro para tipo de ordenação

        query = Booking.query

        # Filtrar por uma data específica (se 'date' for fornecido)
        if single_date_str:
            target_date = datetime.strptime(single_date_str, '%Y-%m-%d').date()
            query = query.filter(Booking.booking_date == target_date)
        else:  # Se 'date' não for fornecido, usar 'start_date' e 'end_date'
            if start_date_str:
                query = query.filter(Booking.booking_date >= datetime.strptime(start_date_str, '%Y-%m-%d').date())
            if end_date_str:
                query = query.filter(Booking.booking_date <= datetime.strptime(end_date_str, '%Y-%m-%d').date())

        if status:
            query = query.filter(Booking.status == status)

        if service_id:
            query = query.filter(Booking.service_id == service_id)

        # Ordenação
        if order_by == 'latest':
            query = query.order_by(Booking.created_at.desc())  # Ordenar por mais recente
        else:
            query = query.order_by(Booking.booking_date, Booking.booking_time)  # Ordenação padrão

        # Limitar resultados (para 'Mais Recentes')
        if limit:
            query = query.limit(limit)

        bookings = query.all()
        return jsonify([booking.to_dict() for booking in bookings])
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bookings_bp.route('/bookings/<int:booking_id>', methods=['GET'])
def get_booking(booking_id):
    """Retorna um agendamento específico"""
    try:
        booking = Booking.query.get_or_404(booking_id)
        return jsonify(booking.to_dict())
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bookings_bp.route('/bookings', methods=['POST'])
def create_booking():
    """Cria um novo agendamento de forma atômica, confiando na constraint do DB."""
    # Sua lógica para obter os dados e o cliente permanece a mesma.
    data = request.get_json()
    customer_data = data.get('customer')
    if not customer_data or not all(k in customer_data for k in ('email', 'name', 'phone')):
        return jsonify({'error': 'Dados do cliente ausentes'}), 400

    customer = Customer.query.filter_by(email=customer_data.get('email')).first()
    if not customer:
        customer = Customer(name=customer_data.get('name'), phone=customer_data.get('phone'),
                            email=customer_data.get('email'))
        db.session.add(customer)
        db.session.flush()

    try:
        booking_date = datetime.strptime(data['booking_date'], '%Y-%m-%d').date()
        booking_time = datetime.strptime(data['booking_time'], '%H:%M').time()
        service_id = data['service_id']

        # 1. REMOVA A VERIFICAÇÃO MANUAL DE AGENDAMENTO EXISTENTE
        # O banco de dados fará isso por nós agora, de forma mais segura.
        #
        # existing_booking = Booking.query.filter_by(...) -> REMOVIDO

        # 2. MANTENHA AS VERIFICAÇÕES DE BLOQUEIOS (RECORRENTES E MANUAIS)
        # É bom verificar isso antes para dar uma resposta mais específica ao usuário.
        recurring_blocked_slots = get_recurring_unavailable_slots(booking_date)
        if booking_time.strftime('%H:%M') in recurring_blocked_slots:
            return jsonify(
                {'error': 'Este horário não está disponível para agendamento (manutenção).'}), 409  # Use 409 Conflict

        blocked_explicitly = BlockedTime.query.filter_by(blocked_date=booking_date, active=True).all()
        service_duration = Service.query.get(service_id).duration_minutes
        booking_slot_start_dt = datetime.combine(date.min, booking_time)
        booking_slot_end_dt = booking_slot_start_dt + timedelta(minutes=service_duration)

        for block in blocked_explicitly:
            if block.start_time is None and block.end_time is None:
                return jsonify({'error': 'Data inteira bloqueada para agendamentos.'}), 409

            blocked_start_dt = datetime.combine(date.min, block.start_time)
            blocked_end_dt = datetime.combine(date.min, block.end_time)
            if (booking_slot_start_dt < blocked_end_dt and booking_slot_end_dt > blocked_start_dt):
                return jsonify({'error': 'Este horário está bloqueado.'}), 409

        # 3. TENTE CRIAR O AGENDAMENTO DIRETAMENTE
        booking = Booking(
            customer_id=customer.id,
            service_id=service_id,
            booking_date=booking_date,
            booking_time=booking_time,
            notes=data.get('notes', ''),
            status='confirmed'
        )
        db.session.add(booking)
        db.session.flush()

        # Sua lógica de criar BlockedTime associado está correta e permanece aqui
        service_name = Service.query.get(service_id).name
        blocked_by_booking = BlockedTime(
            blocked_date=booking_date,
            start_time=booking_time,
            end_time=booking_slot_end_dt.time(),
            reason=f"Agendamento de {customer.name} para {service_name}",
            booking_id=booking.id,
            created_at=datetime.utcnow(),
            active=True
        )
        db.session.add(blocked_by_booking)

        db.session.commit()

        return jsonify(booking.to_dict()), 201

    # 4. CAPTURE O ERRO DE INTEGRIDADE DO BANCO DE DADOS
    except IntegrityError:
        db.session.rollback()
        # Este erro acontece se a UniqueConstraint for violada (horário duplicado)
        return jsonify({'error': 'Desculpe, este horário acabou de ser agendado. Por favor, escolha outro.'}), 409

    except Exception as e:
        db.session.rollback()
        print(f"Erro ao criar agendamento: {e}")
        return jsonify({'error': 'Ocorreu um erro inesperado ao processar seu agendamento.'}), 500


@bookings_bp.route('/bookings/<int:booking_id>', methods=['PUT'])
def update_booking(booking_id):
    """Atualiza um agendamento"""
    try:
        booking = Booking.query.get_or_404(booking_id)
        data = request.get_json()

        old_booking_date = booking.booking_date
        old_booking_time = booking.booking_time
        old_service_id = booking.service_id  # Precisamos do service_id antigo para calcular a duração do slot antigo
        old_status = booking.status

        # Determinar a duração do serviço para o cálculo do slot antigo
        old_service_duration = Service.query.get(old_service_id).duration_minutes

        # Atualiza o agendamento
        if 'booking_date' in data:
            booking.booking_date = datetime.strptime(data['booking_date'], '%Y-%m-%d').date()
        if 'booking_time' in data:
            booking.booking_time = datetime.strptime(data['booking_time'], '%H:%M').time()
        if 'status' in data:
            booking.status = data['status']
        if 'notes' in data:
            booking.notes = data['notes']
        if 'service_id' in data:
            booking.service_id = data['service_id']

        booking.updated_at = datetime.utcnow()
        db.session.flush()

        # --- LÓGICA DE ATUALIZAÇÃO DO BLOCKEDTIME CORRESPONDENTE ---
        # Primeiro, desativar o BlockedTime antigo associado a este agendamento
        existing_blocked_time_for_booking = BlockedTime.query.filter_by(
            booking_id=booking_id,
            blocked_date=old_booking_date,
            start_time=old_booking_time
            # Não filtrando por end_time, pois ele pode ter sido ligeiramente diferente dependendo da duração do serviço
        ).first()

        if existing_blocked_time_for_booking:
            existing_blocked_time_for_booking.active = False
            db.session.add(existing_blocked_time_for_booking)  # Marca para desativação

        # Se o agendamento ainda está ativo (não cancelado) e sua data/hora/serviço mudou,
        # ou se o status mudou para 'confirmed' (de 'pending' ou outro)
        if booking.status == 'confirmed' and \
                (booking.booking_date != old_booking_date or \
                 booking.booking_time != old_booking_time or \
                 booking.service_id != old_service_id or \
                 old_status != 'confirmed'):  # Se o status mudou para confirmado

            # 1. Verificar se o NOVO horário está disponível (apenas se o horário mudou ou o status foi confirmado)
            if booking.booking_date != old_booking_date or booking.booking_time != old_booking_time or old_status != 'confirmed':
                existing_booking_at_new_slot = Booking.query.filter(
                    Booking.booking_date == booking.booking_date,
                    Booking.booking_time == booking.booking_time,
                    Booking.status == 'confirmed',
                    Booking.id != booking_id  # Excluir o próprio agendamento da checagem
                ).first()
                if existing_booking_at_new_slot:
                    raise ValueError('O novo horário já está ocupado por outro agendamento confirmado.')

            # 2. Verificar regras recorrentes para o NOVO horário
            recurring_blocked_slots = get_recurring_unavailable_slots(booking.booking_date)
            if booking.booking_time.strftime('%H:%M') in recurring_blocked_slots:
                raise ValueError('O novo horário está bloqueado por regra recorrente (Manutenção).')

            # 3. Verificar bloqueios explícitos para o NOVO horário
            blocked_explicitly = BlockedTime.query.filter_by(
                blocked_date=booking.booking_date,
                active=True
            ).all()

            new_service_duration = Service.query.get(booking.service_id).duration_minutes
            new_booking_slot_start_dt = datetime.combine(date.min, booking.booking_time)
            new_booking_slot_end_dt = new_booking_slot_start_dt + timedelta(minutes=new_service_duration)

            for block in blocked_explicitly:
                # Ignorar o próprio blocked_time do agendamento que está sendo atualizado
                if block.booking_id == booking_id:
                    continue

                if block.start_time is None and block.end_time is None:
                    raise ValueError('A nova data está bloqueada para agendamentos.')

                blocked_start_dt = datetime.combine(date.min, block.start_time)
                blocked_end_dt = datetime.combine(date.min, block.end_time)

                if (new_booking_slot_start_dt < blocked_end_dt and new_booking_slot_end_dt > blocked_start_dt):
                    raise ValueError('O novo horário está bloqueado explicitamente.')

            # Recriar um novo registro BlockedTime para o agendamento com as novas informações
            new_blocked_by_booking = BlockedTime(
                blocked_date=booking.booking_date,
                start_time=booking.booking_time,
                end_time=new_booking_slot_end_dt.time(),
                reason=f"Agendamento de {booking.customer.name} para {booking.service.name}",
                booking_id=booking.id,
                created_at=datetime.utcnow(),
                active=True
            )
            db.session.add(new_blocked_by_booking)
        elif booking.status == 'cancelled' and old_status != 'cancelled':
            # Se o agendamento foi cancelado, certificar-se de desativar o blocked_time correspondente
            if existing_blocked_time_for_booking:
                existing_blocked_time_for_booking.active = False
                db.session.add(existing_blocked_time_for_booking)

        db.session.commit()

        return jsonify(booking.to_dict())
    except ValueError as ve:  # Captura erros de validação
        db.session.rollback()
        return jsonify({'error': str(ve)}), 400
    except Exception as e:
        db.session.rollback()
        print(f"Erro ao atualizar agendamento: {e}")
        return jsonify({'error': str(e)}), 500


@bookings_bp.route('/bookings/<int:booking_id>', methods=['DELETE'])
def delete_booking(booking_id):
    """Deleta um agendamento e desativa o blocked_time correspondente."""
    try:
        booking = Booking.query.get_or_404(booking_id)

        # Desativar o BlockedTime correspondente
        blocked_time_to_deactivate = BlockedTime.query.filter_by(booking_id=booking_id).first()
        if blocked_time_to_deactivate:
            blocked_time_to_deactivate.active = False
            db.session.add(blocked_time_to_deactivate)

        db.session.delete(booking)
        db.session.commit()
        return jsonify({'message': 'Agendamento deletado com sucesso!'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


# Endpoint para cancelar agendamento (similar a PUT, mas com foco no status)
@bookings_bp.route('/bookings/<int:booking_id>/cancel', methods=['PUT'])
def cancel_booking(booking_id):
    """Cancela um agendamento e desativa o blocked_time correspondente."""
    try:
        booking = Booking.query.get_or_404(booking_id)

        old_status = booking.status
        if old_status == 'cancelled':
            return jsonify({'message': 'Agendamento já está cancelado.'}), 200

        booking.status = 'cancelled'
        booking.updated_at = datetime.utcnow()
        db.session.flush()

        # Desativar o BlockedTime correspondente
        blocked_time_to_deactivate = BlockedTime.query.filter_by(booking_id=booking_id).first()
        if blocked_time_to_deactivate:
            blocked_time_to_deactivate.active = False
            db.session.add(blocked_time_to_deactivate)

        db.session.commit()
        return jsonify(booking.to_dict()), 200
    except Exception as e:
        db.session.rollback()
        print(f"Erro ao cancelar agendamento: {e}")
        return jsonify({'error': str(e)}), 500


@bookings_bp.route('/available-times', methods=['GET'])
def get_available_times():
    """Retorna horários disponíveis para uma data específica, considerando bloqueios e regras recorrentes."""
    try:
        date_str = request.args.get('date')
        if not date_str:
            return jsonify({'error': 'Data é obrigatória'}), 400

        booking_date = datetime.strptime(date_str, '%Y-%m-%d').date()

        # Horários de funcionamento (mantido como no seu original)
        business_hours = {
            1: [],  # Domingo
            2: ['14:00', '14:30', '15:00', '15:30', '16:00', '16:30', '17:00', '17:30'],  # Segunda
            3: ['09:00', '09:30', '10:00', '10:30', '14:00', '14:30', '15:00', '15:30', '16:00', '16:30', '17:00',
                '17:30'],  # Terça
            4: ['14:00', '14:30', '15:00', '15:30', '16:00', '16:30', '17:00', '17:30'],  # Quarta
            5: ['09:00', '09:30', '10:00', '10:30', '14:00', '14:30', '15:00', '15:30', '16:00', '16:30', '17:00',
                '17:30'],  # Quinta
            6: ['14:00', '14:30', '15:00', '15:30', '16:00', '16:30', '17:00', '17:30'],  # Sexta
            7: ['09:00', '09:30', '10:00', '10:30', '11:00', '11:30', '12:00', '12:30'],  # Sábado
        }

        day_of_week_iso = booking_date.isoweekday()
        weekday_for_business_hours = 1 if day_of_week_iso == 7 else day_of_week_iso + 1
        available_times = business_hours.get(weekday_for_business_hours, [])

        # 1. Remover horários da regra recorrente
        recurring_blocked = get_recurring_unavailable_slots(booking_date)
        available_times = [t for t in available_times if t not in recurring_blocked]

        # --- SEÇÃO REMOVIDA ---
        # A consulta direta aos Bookings foi removida para evitar redundância.
        # A lógica agora confia apenas na tabela BlockedTime.
        # booked_times = Booking.query.filter_by(...)
        # -----------------------

        # 2. Remover horários bloqueados (manualmente ou por agendamentos)
        # Esta consulta é a ÚNICA necessária, pois já lida com agendamentos (active=True)
        # e libera horários cancelados (active=False).
        explicitly_blocked_entries = BlockedTime.query.filter_by(
            blocked_date=booking_date,
            active=True  # Apenas bloqueios ativos são considerados!
        ).all()

        # Lógica de remoção otimizada
        slots_to_remove = set()
        for blocked_entry in explicitly_blocked_entries:
            if blocked_entry.start_time is None and blocked_entry.end_time is None:
                # Se o dia todo está bloqueado, esvazia a lista e para.
                available_times = []
                break

            blocked_start_dt = datetime.combine(date.min, blocked_entry.start_time)
            blocked_end_dt = datetime.combine(date.min, blocked_entry.end_time)

            for slot_str in available_times:
                slot_time = datetime.strptime(slot_str, '%H:%M').time()
                slot_datetime_obj = datetime.combine(date.min, slot_time)
                # Assumindo slots de 30 minutos
                slot_end_datetime_obj = slot_datetime_obj + timedelta(minutes=30)

                # Verifica se há qualquer sobreposição
                if slot_datetime_obj < blocked_end_dt and slot_end_datetime_obj > blocked_start_dt:
                    slots_to_remove.add(slot_str)

        if available_times:  # Continua apenas se o dia não foi totalmente bloqueado
            available_times = [t for t in available_times if t not in slots_to_remove]

        # 3. Opcional: Filtro para horários que já passaram no dia de hoje
        if booking_date == date.today():
            now_time = datetime.now().time()
            available_times = [t for t in available_times if datetime.strptime(t, '%H:%M').time() > now_time]

        return jsonify({'available_times': sorted(available_times)})

    except Exception as e:
        # É uma boa prática logar o erro para debug
        print(f"Erro em get_available_times: {e}")
        return jsonify({'error': str(e)}), 500