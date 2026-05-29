"""
Rotas para interface mobile do Mecânico/Auxiliar
Focado em: Agenda, OS atribuídas, Diagnóstico, Ponto, Comissões
"""
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, session
from functools import wraps
from datetime import datetime, timedelta
import calendar

from app.database import get_db
from app.utils.auth import login_required
from app.utils.tenant import get_company_id

mecanico_bp = Blueprint('mecanico', __name__, url_prefix='/mecanico')


def mecanico_required(f):
    """Decorator para garantir que apenas mecânicos/auxiliares acessem."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login'))
        # Aqui pode adicionar verificação de role/permissão específica
        return f(*args, **kwargs)
    return decorated_function


@mecanico_bp.route('/')
@login_required
@mecanico_required
def index():
    """Redireciona para a agenda do mecânico."""
    return redirect(url_for('mecanico.minha_agenda'))


@mecanico_bp.route('/agenda')
@login_required
@mecanico_required
def minha_agenda():
    """Agenda diária do mecânico com OS atribuídas."""
    db = get_db()
    technician_id = session.get('technician_id') or session.get('user_id')
    company_id = get_company_id()
    
    # Data selecionada (padrão: hoje)
    data_param = request.args.get('data')
    if data_param:
        data_selecionada = datetime.strptime(data_param, '%Y-%m-%d').date()
    else:
        data_selecionada = datetime.now().date()
    
    # Buscar OS do dia para o mecânico
    query = """
        SELECT so.*, 
               c.name as customer_name,
               e.name as equipment_name,
               e.plate as equipment_plate
        FROM service_orders so
        JOIN customers c ON so.customer_id = c.id
        LEFT JOIN equipments e ON so.equipment_id = e.id
        WHERE so.technician_id = %s
          AND so.company_id = %s
          AND DATE(so.scheduled_date) = %s
          AND so.status IN ('open', 'in_progress', 'completed')
        ORDER BY so.scheduled_time, so.priority DESC
    """
    
    ordens = db.fetch_all(query, (technician_id, company_id, data_selecionada))
    
    # Processar status para exibição
    for os in ordens:
        status_map = {
            'open': {'text': 'Aberta', 'color': '#3b82f6', 'class': ''},
            'in_progress': {'text': 'Andamento', 'color': '#f59e0b', 'class': 'andamento'},
            'completed': {'text': 'Concluída', 'color': '#10b981', 'class': 'concluida'},
            'cancelled': {'text': 'Cancelada', 'color': '#ef4444', 'class': 'urgente'}
        }
        status_info = status_map.get(os['status'], status_map['open'])
        os['status_text'] = status_info['text']
        os['status_color'] = status_info['color']
        os['status_class'] = status_info['class']
        os['priority'] = os.get('priority', 'normal')
    
    # Estatísticas
    stats = {
        'hoje': len(ordens),
        'andamento': sum(1 for o in ordens if o['status'] == 'in_progress'),
        'concluidas': sum(1 for o in ordens if o['status'] == 'completed')
    }
    
    # Dias da semana para navegação
    hoje = datetime.now().date()
    dias = []
    for i in range(-3, 4):  # 3 dias antes e 3 depois
        dia = hoje + timedelta(days=i)
        dias.append({
            'data': dia.strftime('%Y-%m-%d'),
            'dia': dia.strftime('%d'),
            'semana': calendar.day_abbr[dia.weekday()],
            'selecionado': dia == data_selecionada
        })
    
    return render_template('mobile/mecanico/minha_agenda.html',
                         ordens=ordens,
                         stats=stats,
                         dias=dias,
                         os_pendentes_count=sum(1 for o in ordens if o['status'] == 'open'))


@mecanico_bp.route('/minhas-os')
@login_required
@mecanico_required
def minhas_os():
    """Lista todas as OS atribuídas ao mecânico."""
    db = get_db()
    technician_id = session.get('technician_id') or session.get('user_id')
    company_id = get_company_id()
    
    status_filter = request.args.get('status', 'all')
    
    query = """
        SELECT so.*, 
               c.name as customer_name,
               e.name as equipment_name
        FROM service_orders so
        JOIN customers c ON so.customer_id = c.id
        LEFT JOIN equipments e ON so.equipment_id = e.id
        WHERE so.technician_id = %s
          AND so.company_id = %s
    """
    params = [technician_id, company_id]
    
    if status_filter != 'all':
        query += " AND so.status = %s"
        params.append(status_filter)
    
    query += " ORDER BY so.opened_at DESC LIMIT 50"
    
    ordens = db.fetch_all(query, tuple(params))
    
    return render_template('mobile/mecanico/minhas_os.html', 
                         ordens=ordens,
                         status_filter=status_filter)


@mecanico_bp.route('/os/<int:os_id>')
@login_required
@mecanico_required
def os_detalhe(os_id):
    """Detalhe da OS para diagnóstico."""
    db = get_db()
    technician_id = session.get('technician_id') or session.get('user_id')
    
    # Buscar OS
    os = db.fetch_one("""
        SELECT so.*,
               c.name as customer_name,
               c.phone as customer_phone,
               e.name as equipment_name,
               e.plate as equipment_plate,
               e.brand as equipment_brand,
               e.model as equipment_model
        FROM service_orders so
        JOIN customers c ON so.customer_id = c.id
        LEFT JOIN equipments e ON so.equipment_id = e.id
        WHERE so.id = %s AND so.technician_id = %s
    """, (os_id, technician_id))
    
    if not os:
        flash('OS não encontrada ou não atribuída a você.', 'danger')
        return redirect(url_for('mecanico.minha_agenda'))
    
    # Status info
    status_map = {
        'open': {'text': 'Aberta', 'color': '#3b82f6', 'class': ''},
        'in_progress': {'text': 'Andamento', 'color': '#f59e0b', 'class': 'andamento'},
        'completed': {'text': 'Concluída', 'color': '#10b981', 'class': 'concluida'}
    }
    status_info = status_map.get(os['status'], status_map['open'])
    os['status_text'] = status_info['text']
    os['status_color'] = status_info['color']
    os['status_class'] = status_info['class']
    
    # Checklist padrão de diagnóstico
    checklist = [
        {'id': 1, 'nome': 'Inspeção Visual Geral', 'checked': False},
        {'id': 2, 'nome': 'Teste de Funcionamento', 'checked': False},
        {'id': 3, 'nome': 'Verificação de Fluidos', 'checked': False},
        {'id': 4, 'nome': 'Diagnóstico por Scanner', 'checked': False},
        {'id': 5, 'nome': 'Teste de Rodagem', 'checked': False},
        {'id': 6, 'nome': 'Limpeza e Organização', 'checked': False},
    ]
    
    # Buscar peças e serviços já adicionados
    pecas = db.fetch_all("""
        SELECT p.*, soi.quantity, soi.unit_price, (soi.quantity * soi.unit_price) as total
        FROM service_order_items soi
        JOIN products p ON soi.product_id = p.id
        WHERE soi.service_order_id = %s AND soi.item_type = 'part'
    """, (os_id,))
    
    servicos = db.fetch_all("""
        SELECT s.*, soi.quantity, soi.unit_price, (soi.quantity * soi.unit_price) as total
        FROM service_order_items soi
        JOIN services s ON soi.service_id = s.id
        WHERE soi.service_order_id = %s AND soi.item_type = 'service'
    """, (os_id,))
    
    return render_template('mobile/mecanico/os_detalhe.html',
                         os=os,
                         checklist=checklist,
                         pecas=pecas or [],
                         servicos=servicos or [])


@mecanico_bp.route('/os/<int:os_id>/iniciar', methods=['POST'])
@login_required
@mecanico_required
def os_iniciar(os_id):
    """Iniciar trabalho na OS."""
    db = get_db()
    technician_id = session.get('technician_id') or session.get('user_id')
    
    # Verificar se OS pertence ao mecânico
    os = db.fetch_one("""
        SELECT id, status FROM service_orders 
        WHERE id = %s AND technician_id = %s
    """, (os_id, technician_id))
    
    if not os:
        return jsonify({'success': False, 'error': 'OS não encontrada'})
    
    if os['status'] not in ['open', 'in_progress']:
        return jsonify({'success': False, 'error': 'OS não pode ser iniciada'})
    
    # Atualizar status e registrar início
    now = datetime.now()
    db.execute("""
        UPDATE service_orders 
        SET status = 'in_progress', 
            started_at = COALESCE(started_at, %s),
            updated_at = %s
        WHERE id = %s
    """, (now, now, os_id))
    
    # Registrar ponto de início
    db.execute("""
        INSERT INTO time_entries (user_id, service_order_id, entry_type, started_at, company_id)
        VALUES (%s, %s, 'work', %s, %s)
    """, (session.get('user_id'), os_id, now, get_company_id()))
    
    return jsonify({'success': True})


@mecanico_bp.route('/os/<int:os_id>/pausar', methods=['POST'])
@login_required
@mecanico_required
def os_pausar(os_id):
    """Pausar trabalho na OS."""
    db = get_db()
    technician_id = session.get('technician_id') or session.get('user_id')
    
    # Fechar entrada de tempo aberta
    now = datetime.now()
    db.execute("""
        UPDATE time_entries 
        SET ended_at = %s,
            duration_minutes = TIMESTAMPDIFF(MINUTE, started_at, %s)
        WHERE service_order_id = %s 
          AND user_id = %s 
          AND ended_at IS NULL
    """, (now, now, os_id, session.get('user_id')))
    
    return jsonify({'success': True})


@mecanico_bp.route('/os/<int:os_id>/finalizar', methods=['POST'])
@login_required
@mecanico_required
def os_finalizar(os_id):
    """Finalizar OS."""
    db = get_db()
    technician_id = session.get('technician_id') or session.get('user_id')
    
    now = datetime.now()
    
    # Fechar entrada de tempo
    db.execute("""
        UPDATE time_entries 
        SET ended_at = %s,
            duration_minutes = TIMESTAMPDIFF(MINUTE, started_at, %s)
        WHERE service_order_id = %s 
          AND user_id = %s 
          AND ended_at IS NULL
    """, (now, now, os_id, session.get('user_id')))
    
    # Atualizar OS
    db.execute("""
        UPDATE service_orders 
        SET status = 'completed',
            completed_at = %s,
            updated_at = %s
        WHERE id = %s AND technician_id = %s
    """, (now, now, os_id, technician_id))
    
    # Calcular comissão (exemplo: 10% dos serviços)
    servicos = db.fetch_one("""
        SELECT SUM(total_price) as total FROM service_order_items
        WHERE service_order_id = %s AND item_type = 'service'
    """, (os_id,))
    
    if servicos and servicos['total']:
        comissao = servicos['total'] * 0.10  # 10% comissão
        db.execute("""
            INSERT INTO commissions (technician_id, service_order_id, amount, created_at, company_id)
            VALUES (%s, %s, %s, %s, %s)
        """, (technician_id, os_id, comissao, now, get_company_id()))
    
    return jsonify({'success': True})


@mecanico_bp.route('/os/<int:os_id>/diagnostico', methods=['GET', 'POST'])
@login_required
@mecanico_required
def salvar_diagnostico(os_id):
    """Salvar diagnóstico da OS."""
    db = get_db()
    technician_id = session.get('technician_id') or session.get('user_id')
    
    if request.method == 'POST':
        diagnostico = request.form.get('diagnostico', '')
        
        # Salvar diagnóstico
        db.execute("""
            UPDATE service_orders 
            SET diagnostico = %s,
                technical_report = %s,
                updated_at = %s
            WHERE id = %s AND technician_id = %s
        """, (diagnostico, diagnostico, datetime.now(), os_id, technician_id))
        
        flash('Diagnóstico salvo com sucesso!', 'success')
        return redirect(url_for('mecanico.os_detalhe', os_id=os_id))
    
    return redirect(url_for('mecanico.os_detalhe', os_id=os_id))


@mecanico_bp.route('/ponto')
@login_required
@mecanico_required
def ponto():
    """Tela de registro de ponto."""
    db = get_db()
    user_id = session.get('user_id')
    
    hoje = datetime.now().date()
    
    # Verificar se há ponto aberto
    ponto_aberto = db.fetch_one("""
        SELECT started_at FROM time_entries
        WHERE user_id = %s AND entry_type = 'clock_in' AND ended_at IS NULL
        ORDER BY started_at DESC LIMIT 1
    """, (user_id,))
    
    # Resumo do dia
    resumo = db.fetch_one("""
        SELECT 
            MIN(started_at) as entrada,
            MAX(ended_at) as saida,
            SUM(duration_minutes) as total_minutos
        FROM time_entries
        WHERE user_id = %s 
          AND DATE(started_at) = %s
          AND entry_type = 'clock_in'
    """, (user_id, hoje))
    
    if resumo:
        total_horas = resumo['total_minutos'] // 60 if resumo['total_minutos'] else 0
        total_min = resumo['total_minutos'] % 60 if resumo['total_minutos'] else 0
        resumo['total'] = f"{total_horas:02d}:{total_min:02d}"
        resumo['entrada'] = resumo['entrada'].strftime('%H:%M') if resumo['entrada'] else None
        resumo['saida'] = resumo['saida'].strftime('%H:%M') if resumo['saida'] else None
    
    # Histórico dos últimos 7 dias
    historico = []
    for i in range(7):
        dia = hoje - timedelta(days=i)
        dia_dados = db.fetch_one("""
            SELECT 
                MIN(started_at) as entrada,
                MAX(ended_at) as saida,
                SUM(duration_minutes) as total_minutos
            FROM time_entries
            WHERE user_id = %s 
              AND DATE(started_at) = %s
              AND entry_type = 'clock_in'
        """, (user_id, dia))
        
        if dia_dados and dia_dados['total_minutos']:
            horas = dia_dados['total_minutos'] // 60
            mins = dia_dados['total_minutos'] % 60
            historico.append({
                'data': dia.strftime('%d/%m'),
                'entrada': dia_dados['entrada'].strftime('%H:%M') if dia_dados['entrada'] else None,
                'saida': dia_dados['saida'].strftime('%H:%M') if dia_dados['saida'] else None,
                'horas': f"{horas:02d}:{mins:02d}",
                'status': 'Completo' if horas >= 8 else 'Parcial'
            })
    
    # OS com tempo registrado hoje
    os_tempo = db.fetch_all("""
        SELECT so.id, so.order_number, c.name as customer_name,
               SUM(te.duration_minutes) as tempo_minutos
        FROM time_entries te
        JOIN service_orders so ON te.service_order_id = so.id
        JOIN customers c ON so.customer_id = c.id
        WHERE te.user_id = %s AND DATE(te.started_at) = %s
        GROUP BY so.id, so.order_number, c.name
    """, (user_id, hoje))
    
    for os in os_tempo:
        mins = os['tempo_minutos'] or 0
        os['tempo'] = f"{mins // 60:02d}:{mins % 60:02d}"
    
    return render_template('mobile/mecanico/ponto.html',
                         ponto_aberto=ponto_aberto['started_at'] if ponto_aberto else None,
                         resumo=resumo or {},
                         historico=historico,
                         os_tempo=os_tempo or [],
                         data_atual=hoje.strftime('%A, %d de %B'))


@mecanico_bp.route('/ponto/registrar', methods=['POST'])
@login_required
@mecanico_required
def registrar_ponto():
    """Registrar entrada ou saída de ponto."""
    db = get_db()
    user_id = session.get('user_id')
    now = datetime.now()
    
    # Verificar se há ponto aberto
    ponto_aberto = db.fetch_one("""
        SELECT id FROM time_entries
        WHERE user_id = %s AND entry_type = 'clock_in' AND ended_at IS NULL
        LIMIT 1
    """, (user_id,))
    
    if ponto_aberto:
        # Registrar saída
        db.execute("""
            UPDATE time_entries 
            SET ended_at = %s,
                duration_minutes = TIMESTAMPDIFF(MINUTE, started_at, %s)
            WHERE id = %s
        """, (now, now, ponto_aberto['id']))
        return jsonify({'success': True, 'tipo': 'saida'})
    else:
        # Registrar entrada
        db.execute("""
            INSERT INTO time_entries (user_id, entry_type, started_at, company_id)
            VALUES (%s, 'clock_in', %s, %s)
        """, (user_id, now, get_company_id()))
        return jsonify({'success': True, 'tipo': 'entrada'})


@mecanico_bp.route('/comissoes')
@login_required
@mecanico_required
def comissoes():
    """Visualização de comissões do mecânico."""
    db = get_db()
    technician_id = session.get('technician_id') or session.get('user_id')
    
    # Período
    periodo = request.args.get('periodo', 'mes')
    hoje = datetime.now()
    
    if periodo == 'dia':
        inicio = hoje.date()
        fim = hoje.date()
    elif periodo == 'semana':
        inicio = (hoje - timedelta(days=hoje.weekday())).date()
        fim = hoje.date()
    elif periodo == 'mes_passado':
        primeiro_dia_mes = hoje.replace(day=1)
        ultimo_dia_mes = primeiro_dia_mes - timedelta(days=1)
        inicio = ultimo_dia_mes.replace(day=1)
        fim = ultimo_dia_mes
    else:  # mes
        inicio = hoje.replace(day=1).date()
        fim = hoje.date()
    
    # Total do período
    total = db.fetch_one("""
        SELECT SUM(amount) as total FROM commissions
        WHERE technician_id = %s 
          AND DATE(created_at) BETWEEN %s AND %s
    """, (technician_id, inicio, fim))
    
    # Resumo
    resumo = db.fetch_one("""
        SELECT 
            COUNT(DISTINCT service_order_id) as os_concluidas,
            SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END) as comissao_total
        FROM commissions
        WHERE technician_id = %s 
          AND DATE(created_at) BETWEEN %s AND %s
    """, (technician_id, inicio, fim))
    
    # Ordens com comissão
    ordens = db.fetch_all("""
        SELECT 
            so.id, so.order_number, so.completed_at,
            c.name as customer_name,
            e.name as equipment_name,
            SUM(com.amount) as comissao_total
        FROM commissions com
        JOIN service_orders so ON com.service_order_id = so.id
        JOIN customers c ON so.customer_id = c.id
        LEFT JOIN equipments e ON so.equipment_id = e.id
        WHERE com.technician_id = %s 
          AND DATE(com.created_at) BETWEEN %s AND %s
        GROUP BY so.id, so.order_number, so.completed_at, c.name, e.name
        ORDER BY so.completed_at DESC
    """, (technician_id, inicio, fim))
    
    for os in ordens:
        os['data'] = os['completed_at'].strftime('%d/%m/%Y') if os['completed_at'] else '-'
        os['comissao_servicos'] = os['comissao_total'] * 0.9  # 90% estimado de serviços
        os['comissao_pecas'] = os['comissao_total'] * 0.1     # 10% estimado de peças
    
    # Dados para gráfico (últimos 7 dias)
    grafico_dados = []
    for i in range(6, -1, -1):
        dia = hoje.date() - timedelta(days=i)
        dia_comissao = db.fetch_one("""
            SELECT SUM(amount) as total FROM commissions
            WHERE technician_id = %s AND DATE(created_at) = %s
        """, (technician_id, dia))
        
        valor = dia_comissao['total'] or 0
        grafico_dados.append({
            'dia': dia.strftime('%d/%m'),
            'valor': f"{valor:.0f}",
            'altura': min(100, max(10, valor * 5))  # Escala para altura
        })
    
    return render_template('mobile/mecanico/comissoes.html',
                         total_periodo=total['total'] or 0,
                         periodo={'inicio': inicio.strftime('%d/%m'), 'fim': fim.strftime('%d/%m')},
                         resumo={
                             'os_concluidas': resumo['os_concluidas'] or 0,
                             'horas_trabalhadas': '160:00',  # Placeholder
                             'comissao_servicos': (total['total'] or 0) * 0.9,
                             'comissao_pecas': (total['total'] or 0) * 0.1
                         },
                         ordens=ordens or [],
                         grafico_dados=grafico_dados)
