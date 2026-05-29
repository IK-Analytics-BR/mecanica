"""
agenda_routes.py — Agenda de Mecânicos para IKFlow Mecânica
Funcionalidades:
  - Calendário visual semanal/diário por mecânico (FullCalendar)
  - API JSON de eventos (OS abertas, em andamento, agendadas)
  - Agendamento de OS com horário marcado
  - Preventivo automático ao concluir OS
  - Visão geral de carga de trabalho por técnico
"""
from datetime import datetime, date, timedelta
from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from database import get_db

agenda_bp = Blueprint('agenda', __name__)


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('Por favor, faça login para acessar esta página.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

_STATUS_COLOR = {
    'open':        '#3b82f6',   # azul
    'in_progress': '#f59e0b',   # amarelo
    'completed':   '#10b981',   # verde
    'canceled':    '#ef4444',   # vermelho
    'agendada':    '#8b5cf6',   # roxo
}

_STATUS_LABEL = {
    'open':        'Aberta',
    'in_progress': 'Em Andamento',
    'completed':   'Concluída',
    'canceled':    'Cancelada',
    'agendada':    'Agendada',
}


def _os_to_event(so: dict) -> dict:
    """Converte registro de OS em evento FullCalendar."""
    status = so.get('status', 'open')
    data_inicio = so.get('agendado_para') or so.get('open_date') or date.today()
    data_fim    = so.get('completion_date') or data_inicio

    if isinstance(data_inicio, str):
        try:
            data_inicio = datetime.strptime(data_inicio[:10], '%Y-%m-%d').date()
        except Exception:
            data_inicio = date.today()
    if isinstance(data_fim, str):
        try:
            data_fim = datetime.strptime(data_fim[:10], '%Y-%m-%d').date()
        except Exception:
            data_fim = data_inicio

    hora_inicio = so.get('hora_inicio') or '08:00'
    hora_fim    = so.get('hora_fim')    or '09:00'

    start = f"{data_inicio}T{hora_inicio}"
    end   = f"{data_fim}T{hora_fim}"

    return {
        'id':              so.get('id'),
        'title':           f"[{so.get('order_number', '')}] {so.get('customer_name', '')} — {so.get('equipment_name', '')}",
        'start':           start,
        'end':             end,
        'color':           _STATUS_COLOR.get(status, '#6b7280'),
        'textColor':       '#ffffff',
        'extendedProps': {
            'os_id':        so.get('id'),
            'status':       status,
            'status_label': _STATUS_LABEL.get(status, status),
            'technician':   so.get('technician_name', ''),
            'total':        float(so.get('total_geral') or 0),
            'placa':        so.get('placa', ''),
        }
    }


# ─────────────────────────────────────────────────────────────
# Rota principal — Calendário
# ─────────────────────────────────────────────────────────────

@agenda_bp.route('/agenda')
@login_required
def agenda_index():
    """Calendário geral de OS por mecânico."""
    db = get_db()
    try:
        tecnicos = db.fetch_all("""
            SELECT id, name, specialty, status
            FROM technicians
            WHERE active = TRUE AND status = 'active'
            ORDER BY name
        """)
    except Exception:
        tecnicos = []

    tecnico_id = request.args.get('tecnico_id', type=int)
    tecnico_selecionado = None
    if tecnico_id:
        try:
            tecnico_selecionado = db.fetch_one(
                "SELECT id, name, specialty FROM technicians WHERE id=%s AND active=TRUE",
                (tecnico_id,)
            )
        except Exception:
            pass

    return render_template(
        'agenda_mecanico.html',
        tecnicos=tecnicos,
        tecnico_id=tecnico_id,
        tecnico_selecionado=tecnico_selecionado,
        active_page='agenda'
    )


@agenda_bp.route('/agenda/tecnico/<int:tecnico_id>')
@login_required
def agenda_tecnico(tecnico_id):
    """Redireciona para agenda filtrada pelo técnico."""
    return redirect(url_for('agenda.agenda_index', tecnico_id=tecnico_id))


# ─────────────────────────────────────────────────────────────
# API JSON — eventos para FullCalendar
# ─────────────────────────────────────────────────────────────

@agenda_bp.route('/agenda/api/eventos')
@login_required
def agenda_api_eventos():
    """
    Retorna eventos JSON para o FullCalendar.
    Parâmetros: tecnico_id (opcional), start, end (ISO 8601)
    """
    db = get_db()
    tecnico_id = request.args.get('tecnico_id', type=int)
    start_str  = request.args.get('start', '')
    end_str    = request.args.get('end', '')

    where = ["so.active = TRUE", "so.status != 'canceled'"]
    params = []

    if tecnico_id:
        where.append("so.technician_id = %s")
        params.append(tecnico_id)

    if start_str:
        try:
            start_dt = datetime.strptime(start_str[:10], '%Y-%m-%d').date()
            where.append("COALESCE(so.agendado_para, so.open_date) >= %s")
            params.append(start_dt)
        except Exception:
            pass

    if end_str:
        try:
            end_dt = datetime.strptime(end_str[:10], '%Y-%m-%d').date()
            where.append("COALESCE(so.agendado_para, so.open_date) <= %s")
            params.append(end_dt)
        except Exception:
            pass

    where_clause = ' AND '.join(where)

    try:
        orders = db.fetch_all(f"""
            SELECT so.id, so.order_number, so.status, so.open_date,
                   so.agendado_para, so.hora_inicio, so.hora_fim,
                   so.completion_date, so.total_geral,
                   c.name  as customer_name,
                   e.name  as equipment_name,
                   e.serial_number as placa,
                   t.name  as technician_name
            FROM service_orders so
            LEFT JOIN customers   c ON c.id = so.customer_id
            LEFT JOIN equipment   e ON e.id = so.equipment_id
            LEFT JOIN technicians t ON t.id = so.technician_id
            WHERE {where_clause}
            ORDER BY COALESCE(so.agendado_para, so.open_date) ASC
        """, tuple(params))
    except Exception as ex:
        return jsonify({'error': str(ex)}), 500

    eventos = [_os_to_event(o) for o in (orders or [])]
    return jsonify(eventos)


# ─────────────────────────────────────────────────────────────
# API — agendar / reagendar OS
# ─────────────────────────────────────────────────────────────

@agenda_bp.route('/agenda/agendar/<int:order_id>', methods=['POST'])
@login_required
def agenda_agendar(order_id):
    """
    Agenda uma OS para data/hora específica e opcionalmente atribui técnico.
    Body JSON: { data: 'YYYY-MM-DD', hora_inicio: 'HH:MM', hora_fim: 'HH:MM', tecnico_id: int }
    """
    db = get_db()
    data = request.get_json() or {}

    agendado_para = data.get('data', '')
    hora_inicio   = data.get('hora_inicio', '08:00')
    hora_fim      = data.get('hora_fim', '09:00')
    tecnico_id    = data.get('tecnico_id') or None

    if not agendado_para:
        return jsonify({'ok': False, 'erro': 'Data obrigatória'}), 400

    try:
        datetime.strptime(agendado_para, '%Y-%m-%d')
    except ValueError:
        return jsonify({'ok': False, 'erro': 'Data inválida'}), 400

    try:
        fields = "agendado_para=%s, hora_inicio=%s, hora_fim=%s"
        params = [agendado_para, hora_inicio, hora_fim]
        if tecnico_id:
            fields += ", technician_id=%s"
            params.append(tecnico_id)
        params.append(order_id)
        db.execute_query(f"UPDATE service_orders SET {fields} WHERE id=%s", tuple(params))
        return jsonify({'ok': True, 'msg': 'OS agendada com sucesso!'})
    except Exception as ex:
        return jsonify({'ok': False, 'erro': str(ex)}), 500


# ─────────────────────────────────────────────────────────────
# Carga de trabalho semanal por técnico
# ─────────────────────────────────────────────────────────────

@agenda_bp.route('/agenda/carga-semanal')
@login_required
def agenda_carga_semanal():
    """Retorna JSON com quantidade de OS por técnico na semana atual."""
    db = get_db()
    hoje = date.today()
    inicio_semana = hoje - timedelta(days=hoje.weekday())
    fim_semana    = inicio_semana + timedelta(days=6)

    try:
        rows = db.fetch_all("""
            SELECT t.id, t.name as tecnico, t.specialty,
                   COUNT(so.id) as total_os,
                   SUM(so.status IN ('open','in_progress')) as os_abertas,
                   SUM(so.status = 'completed') as os_concluidas
            FROM technicians t
            LEFT JOIN service_orders so
                   ON so.technician_id = t.id
                  AND so.active = TRUE
                  AND COALESCE(so.agendado_para, so.open_date)
                      BETWEEN %s AND %s
            WHERE t.active = TRUE AND t.status = 'active'
            GROUP BY t.id, t.name, t.specialty
            ORDER BY os_abertas DESC, t.name ASC
        """, (inicio_semana, fim_semana))
    except Exception as ex:
        return jsonify({'error': str(ex)}), 500

    return jsonify({
        'semana_inicio': str(inicio_semana),
        'semana_fim':    str(fim_semana),
        'tecnicos':      [dict(r) for r in (rows or [])]
    })


# ─────────────────────────────────────────────────────────────
# Preventivo automático — chamado após concluir OS
# ─────────────────────────────────────────────────────────────

def calcular_proximo_preventivo(order_id: int, km_saida: int = None, intervalo_dias: int = 180):
    """
    Calcula e agenda próximo preventivo do veículo ao concluir OS.
    Define equipment.next_maintenance = hoje + intervalo_dias.
    Retorna dict com resultado.
    """
    try:
        from database import get_db as _get_db
        db = _get_db()

        order = db.fetch_one("""
            SELECT so.equipment_id, so.order_number,
                   e.serial_number as placa, e.next_maintenance,
                   c.name as customer_name, c.phone as customer_phone
            FROM service_orders so
            LEFT JOIN equipment e ON e.id = so.equipment_id
            LEFT JOIN customers c ON c.id = so.customer_id
            WHERE so.id = %s
        """, (order_id,))

        if not order or not order.get('equipment_id'):
            return {'ok': False, 'msg': 'OS ou equipamento não encontrado'}

        proximo = date.today() + timedelta(days=intervalo_dias)

        db.execute_query(
            "UPDATE equipment SET next_maintenance=%s WHERE id=%s",
            (proximo, order['equipment_id'])
        )

        return {
            'ok': True,
            'placa': order.get('placa'),
            'proximo_preventivo': str(proximo),
            'equipment_id': order['equipment_id'],
        }
    except Exception as e:
        print(f'[AGENDA] Erro ao calcular preventivo OS {order_id}: {e}')
        return {'ok': False, 'msg': str(e)}


@agenda_bp.route('/agenda/preventivo/<int:order_id>', methods=['POST'])
@login_required
def agenda_preventivo(order_id):
    """Endpoint manual para calcular preventivo de uma OS concluída."""
    data = request.get_json() or {}
    intervalo = int(data.get('intervalo_dias', 180))
    resultado = calcular_proximo_preventivo(order_id, intervalo_dias=intervalo)
    return jsonify(resultado)


# ─────────────────────────────────────────────────────────────
# OS sem técnico atribuído (painel de distribuição)
# ─────────────────────────────────────────────────────────────

@agenda_bp.route('/agenda/api/os-sem-tecnico')
@login_required
def agenda_os_sem_tecnico():
    """Retorna OS abertas sem técnico atribuído para distribuição na agenda."""
    db = get_db()
    try:
        rows = db.fetch_all("""
            SELECT so.id, so.order_number, so.open_date, so.agendado_para,
                   so.status, so.total_geral,
                   c.name as customer_name,
                   e.name as equipment_name, e.serial_number as placa
            FROM service_orders so
            LEFT JOIN customers c ON c.id = so.customer_id
            LEFT JOIN equipment e ON e.id = so.equipment_id
            WHERE so.active = TRUE
              AND so.technician_id IS NULL
              AND so.status IN ('open', 'in_progress')
            ORDER BY so.open_date ASC
            LIMIT 50
        """)
    except Exception as ex:
        return jsonify({'error': str(ex)}), 500

    return jsonify([dict(r) for r in (rows or [])])
