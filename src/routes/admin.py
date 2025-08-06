from flask import Blueprint, jsonify, request
from src.models.user import db
from src.models.blocked_time import BlockedTime
from src.models.booking import Booking
from src.models.service import Service
from datetime import datetime, date, time, timedelta
from sqlalchemy import func

admin_bp = Blueprint('admin', __name__)


# --- Funções Auxiliares para Regras Recorrentes e Horários de Funcionamento ---

def generate_time_slots(start_time_str, end_time_str, interval_minutes=30):
    """Gera uma lista de slots de tempo no formato HH:MM."""
    slots = []
    start_time = datetime.strptime(start_time_str, '%H:%M').time()
    end_time = datetime.strptime(end_time_str, '%H:%M').time()

    current_slot_dt = datetime.combine(date.min, start_time)
    # Gerar slots até o início do último slot
    end_dt = datetime.combine(date.min, end_time)

    while current_slot_dt < end_dt:  # Use < para que o último slot seja o final do horário (ex: 18:00 não entra se for 18:00-18:30)
        slots.append(current_slot_dt.strftime('%H:%M'))
        current_slot_dt += timedelta(minutes=interval_minutes)
    return slots


def get_daily_working_slots(target_date):
    """
    Retorna os slots de trabalho (horários de funcionamento) para uma data específica,
    considerando as regras da clínica.
    """
    day_of_week = target_date.isoweekday()  # 1=Segunda, 7=Domingo

    if day_of_week >= 1 and day_of_week <= 5:  # Segunda a Sexta
        return generate_time_slots("09:00", "18:00")
    elif day_of_week == 6:  # Sábado
        return generate_time_slots("09:00", "13:00")
    else:  # Domingo (day_of_week == 7)
        return []  # Domingo fechado


def get_recurring_unavailable_slots(target_date):
    """
    Retorna os slots indisponíveis de acordo com a regra recorrente para uma data específica.
    Segunda, Quarta, Sexta: 09:00 - 11:00
    """
    recurring_blocked_slots = []
    day_of_week = target_date.isoweekday()

    # 1=Segunda, 3=Quarta, 5=Sexta
    if day_of_week in [1, 3, 5]:
        # Slots das 09:00, 09:30, 10:00, 10:30 são bloqueados.
        # O loop vai até ANTES de 11:00.
        start_time = time(9, 0)
        end_time = time(11, 30)

        current_slot = datetime.combine(date.min, start_time)
        end_dt = datetime.combine(date.min, end_time)

        while current_slot.time() < end_dt.time():
            recurring_blocked_slots.append(current_slot.strftime('%H:%M'))
            current_slot += timedelta(minutes=30)
    return recurring_blocked_slots


# --- Endpoints de Configurações (Predefined Time Slots) ---
@admin_bp.route('/settings/time-slots', methods=['GET'])
def get_predefined_time_slots():
    """
    Retorna uma lista abrangente de todos os horários que a clínica PODE ter,
    baseado nos horários de funcionamento mais amplos (Segunda a Sexta).
    Isso é para o frontend popular a lista de slots para seleção.
    """
    predefined_slots = generate_time_slots("09:00", "18:00")
    return jsonify({'time_slots': predefined_slots}), 200


# --- Endpoints de Gerenciamento de Disponibilidade ---
@admin_bp.route('/availability', methods=['GET'])
def get_availability():
    """
    Retorna o mapa de disponibilidade para um determinado mês e ano,
    incluindo bloqueios explícitos e recorrentes, e horários de funcionamento.
    Ex: /api/availability?year=2025&month=7
    """
    try:
        year = request.args.get('year', type=int)
        month = request.args.get('month', type=int)

        if not year or not month:
            return jsonify({'error': 'Ano e mês são obrigatórios'}), 400

        # Calcular o número de dias no mês
        last_day_of_month = date(year, month, 1) + timedelta(days=get_days_in_month(year, month) - 1)
        num_days = last_day_of_month.day

        availability_map = {}

        # Busca todos os bloqueios ativos para o mês e ano
        blocked_times_in_month = BlockedTime.query.filter(
            func.strftime('%Y-%m', BlockedTime.blocked_date) == f"{year}-{month:02d}",
            BlockedTime.active == True
        ).all()

        # Constrói um dicionário para acesso rápido aos bloqueios por data
        explicit_blocks = {}
        for block in blocked_times_in_month:
            date_str = block.blocked_date.isoformat()
            if date_str not in explicit_blocks:
                explicit_blocks[date_str] = []
            explicit_blocks[date_str].append(block)

        for day in range(1, num_days + 1):
            current_date = date(year, month, day)
            date_str = current_date.isoformat()

            full_day_closed_by_rule = False
            explicitly_full_day_closed = False
            current_day_unavailable_slots_set = set()

            # 1. Obter horários de funcionamento padrão para o dia
            daily_working_slots = get_daily_working_slots(current_date)

            if not daily_working_slots:  # Se for domingo ou um dia com 0 horas de trabalho
                full_day_closed_by_rule = True
            else:
                # 2. Adiciona horários da regra recorrente (Seg, Qua, Sex - manhã)
                recurring_slots = get_recurring_unavailable_slots(current_date)
                current_day_unavailable_slots_set.update(recurring_slots)

                # 3. Adiciona bloqueios explícitos do banco de dados
                if date_str in explicit_blocks:
                    for block in explicit_blocks[date_str]:
                        if block.start_time is None and block.end_time is None:
                            explicitly_full_day_closed = True
                            break  # O dia está explicitamente fechado, não precisamos verificar mais slots
                        else:
                            # Adiciona slots bloqueados explicitamente
                            start_dt = datetime.combine(date.min, block.start_time)
                            end_dt = datetime.combine(date.min, block.end_time)
                            current_slot = start_dt
                            while current_slot.time() < end_dt.time():  # Use < para iterar pelos slots do bloqueio
                                slot_str = current_slot.strftime('%H:%M')
                                # Apenas adicione se o slot realmente existe nos horários de trabalho do dia
                                if slot_str in daily_working_slots:
                                    current_day_unavailable_slots_set.add(slot_str)
                                current_slot += timedelta(minutes=30)

            # Determina o estado final de full_day_closed
            final_full_day_closed = full_day_closed_by_rule or explicitly_full_day_closed

            final_unavailable_slots = []
            if final_full_day_closed:
                # Se o dia está fechado (por regra ou explicitamente), todos os slots de trabalho são indisponíveis
                final_unavailable_slots = sorted(list(set(daily_working_slots)))
            else:
                # Caso contrário, apenas os slots explicitamente ou recorrentemente bloqueados
                # que estão dentro dos horários de trabalho do dia
                final_unavailable_slots = sorted([
                    s for s in list(current_day_unavailable_slots_set)
                    if s in daily_working_slots
                ])

            availability_map[date_str] = {
                'fullDayClosed': final_full_day_closed,
                'unavailableSlots': final_unavailable_slots
            }

        return jsonify({'availability': availability_map}), 200

    except ValueError:
        return jsonify({'error': 'Ano ou mês inválido. Use números inteiros.'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def get_days_in_month(year, month):
    """Retorna o número de dias em um determinado mês e ano."""
    if month == 2:
        if (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0):
            return 29
        return 28
    elif month in [4, 6, 9, 11]:
        return 30
    return 31


@admin_bp.route('/availability/<string:date_string>', methods=['PUT'])
def update_day_availability(date_string):
    """
    Atualiza a disponibilidade de um dia específico.
    date_string: YYYY-MM-DD
    Data de entrada: { fullDayClosed: boolean, unavailableSlots: string[] }
    """
    try:
        data = request.get_json()
        target_date = datetime.strptime(date_string, '%Y-%m-%d').date()

        full_day_closed_request = data.get('fullDayClosed', False)
        unavailable_slots_request = data.get('unavailableSlots', [])

        # 1. Desativa todos os bloqueios existentes para esta data
        BlockedTime.query.filter_by(blocked_date=target_date, active=True).update({'active': False})
        db.session.commit()

        # 2. Adiciona novos bloqueios baseados na requisição
        if full_day_closed_request:
            # Bloqueia o dia inteiro
            new_block = BlockedTime(
                blocked_date=target_date,
                start_time=None,
                end_time=None,
                reason="Fechado pelo administrador (dia inteiro)",
                active=True
            )
            db.session.add(new_block)
        else:
            # Identifica os slots recorrentes para esta data
            recurring_slots_for_day = get_recurring_unavailable_slots(target_date)

            # Adiciona apenas os slots que NÃO são recorrentes
            for slot_str in unavailable_slots_request:
                if slot_str not in recurring_slots_for_day:
                    slot_time = datetime.strptime(slot_str, '%H:%M').time()
                    new_block = BlockedTime(
                        blocked_date=target_date,
                        start_time=slot_time,
                        # Para slots individuais de 30 minutos, o end_time é o início do slot + 29 minutos,
                        # para que o próximo slot comece exatamente aos 30.
                        end_time=(datetime.combine(date.min, slot_time) + timedelta(minutes=29)).time(),
                        reason=f"Slot bloqueado pelo administrador: {slot_str}",
                        active=True
                    )
                    db.session.add(new_block)

        db.session.commit()
        return jsonify({'message': 'Disponibilidade atualizada com sucesso'}), 200

    except ValueError as ve:
        db.session.rollback()
        return jsonify({'error': f'Erro de valor: {ve}'}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


# --- Endpoints do Dashboard (mantidos como estão, já foram corrigidos) ---

@admin_bp.route('/admin/dashboard/daily-appointments-count', methods=['GET'])
def get_daily_appointments_count():
    """Retorna a contagem de agendamentos confirmados para o dia atual."""
    try:
        today = date.today()
        count = Booking.query.filter_by(booking_date=today, status='confirmed').count()
        return jsonify({'count': count}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/admin/dashboard/next-appointments', methods=['GET'])
def get_next_appointments():
    """Retorna os próximos agendamentos confirmados."""
    try:
        now = datetime.now()
        next_bookings = Booking.query.filter(
            (Booking.booking_date > now.date()) |
            ((Booking.booking_date == now.date()) & (Booking.booking_time >= now.time())),
            Booking.status == 'confirmed'
        ).order_by(Booking.booking_date, Booking.booking_time).limit(5).all()

        return jsonify({'appointments': [booking.to_dict() for booking in next_bookings]}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/admin/dashboard/appointments-by-service', methods=['GET'])
def get_appointments_by_service():
    """Retorna a contagem de agendamentos por tipo de serviço."""
    try:
        service_counts = db.session.query(
            Service.name, func.count(Booking.id)
        ).join(Booking, Service.id == Booking.service_id) \
            .filter(Booking.status == 'confirmed') \
            .group_by(Service.name) \
            .order_by(func.count(Booking.id).desc()) \
            .all()

        result = [{'service': name, 'count': count} for name, count in service_counts]
        return jsonify({'stats': result}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/admin/dashboard/appointments-by-month', methods=['GET'])
def get_appointments_by_month():
    """Retorna a contagem de agendamentos por mês no ano atual."""
    try:
        current_year = date.today().year
        month_counts = db.session.query(
            func.strftime('%m', Booking.booking_date).label('month'),
            func.count(Booking.id)
        ).filter(
            func.strftime('%Y', Booking.booking_date) == str(current_year),
            Booking.status == 'confirmed'
        ).group_by('month') \
            .order_by('month') \
            .all()

        result_dict = {month: count for month, count in month_counts}
        full_year_data = {f"{i:02d}": result_dict.get(f"{i:02d}", 0) for i in range(1, 13)}
        formatted_month_data = [{"month": month, "count": count} for month, count in full_year_data.items()]
        return jsonify({'stats': formatted_month_data}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500