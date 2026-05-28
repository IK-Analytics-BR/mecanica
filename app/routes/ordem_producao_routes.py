"""
Blueprint para Gestão de Ordens de Produção Industrial
Módulo Indústria - Sistema de Templates Inteligentes
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify

try:
    from app.database import get_db
    from app.utils.auth import login_required
    from app.utils.search_utils import parse_star_search, build_multi_part_like_where
except ImportError:
    # Execução no modo main_mysql.py (imports relativos ao diretório /app)
    from database import get_db
    from functools import wraps

    def login_required(f):
        """Requer login para acessar (modo main_mysql.py / sem app.utils.auth)."""
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'username' not in session:
                return redirect(url_for('login'))
            return f(*args, **kwargs)
        return decorated_function
    from utils.search_utils import parse_star_search, build_multi_part_like_where

from functools import wraps
try:
    from utils.permissoes_helper import tem_permissao
except ImportError:
    from app.utils.permissoes_helper import tem_permissao

try:
    from app.services.exchange_rate_service import ExchangeRateService
except ImportError:
    from services.exchange_rate_service import ExchangeRateService

def _is_lider():
    """Verifica se o usuário logado é líder de equipe.
    Consulta o banco como fallback para sessões anteriores à criação da coluna."""
    if session.get('role') == 'admin':
        return True
    val = session.get('eh_lider_equipe')
    if val is not None:
        return bool(val)
    # Fallback: consultar banco e atualizar sessão
    try:
        db = get_db()
        u = db.fetch_one("SELECT eh_lider_equipe FROM users WHERE id=%s", (session.get('user_id'),))
        v = bool(u.get('eh_lider_equipe')) if u else False
        session['eh_lider_equipe'] = v
        return v
    except Exception:
        return False


def _is_operador():
    """Verifica se o usuário logado é operador.
    Consulta o banco como fallback para sessões anteriores à criação da coluna."""
    if session.get('role') == 'admin':
        return True
    val = session.get('eh_operador')
    if val is not None:
        return bool(val)
    try:
        db = get_db()
        u = db.fetch_one("SELECT eh_operador FROM users WHERE id=%s", (session.get('user_id'),))
        v = bool(u.get('eh_operador')) if u else False
        session['eh_operador'] = v
        return v
    except Exception:
        return False


# Decorators para permissões granulares de Indústria
def industria_ops_visualizar_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('Por favor, faça login para acessar esta página.', 'danger')
            return redirect(url_for('login'))
        if not tem_permissao('industria.ops', 'visualizar'):
            flash('Você não tem permissão para visualizar ordens de produção.', 'danger')
            return redirect(url_for('bem_vindo'))
        return f(*args, **kwargs)
    return decorated_function

def industria_ops_criar_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('Por favor, faça login para acessar esta página.', 'danger')
            return redirect(url_for('login'))
        if not tem_permissao('industria.ops', 'criar'):
            flash('Você não tem permissão para criar ordens de produção.', 'danger')
            return redirect(url_for('ordem_producao.listar_ops'))
        return f(*args, **kwargs)
    return decorated_function

def industria_ops_editar_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('Por favor, faça login para acessar esta página.', 'danger')
            return redirect(url_for('login'))
        if not tem_permissao('industria.ops', 'editar'):
            flash('Você não tem permissão para editar ordens de produção.', 'danger')
            return redirect(url_for('ordem_producao.listar_ops'))
        return f(*args, **kwargs)
    return decorated_function

def industria_ops_excluir_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('Por favor, faça login para acessar esta página.', 'danger')
            return redirect(url_for('login'))
        if not tem_permissao('industria.ops', 'excluir'):
            flash('Você não tem permissão para excluir ordens de produção.', 'danger')
            return redirect(url_for('ordem_producao.listar_ops'))
        return f(*args, **kwargs)
    return decorated_function
from datetime import datetime, date, timedelta
from decimal import Decimal
from decimal import InvalidOperation
import random

# Helper Kardex
try:
    from utils.estoque_helper import registrar_movimentacao
except ImportError:
    registrar_movimentacao = None

# Criar blueprint
ordem_producao_bp = Blueprint('ordem_producao', __name__, url_prefix='/industria/ordem-producao')


def calcular_fx_para_empresa(db, empresa_id):
    if not empresa_id:
        return None
    try:
        empresa = db.fetch_one(
            "SELECT moeda_funcional FROM empresas WHERE id = %s",
            (empresa_id,),
        )
    except Exception as e:
        print(f"[INDUSTRIA FX] Erro ao buscar empresa {empresa_id}: {e}")
        return None
    if not empresa:
        return None
    moeda_funcional = (empresa.get('moeda_funcional') or '').strip().upper()[:3]
    if not moeda_funcional:
        return None
    try:
        svc = ExchangeRateService()
        rate_date = date.today()
        rate_value = svc.get_rate(rate_date, moeda_funcional)
        return {
            'base_currency': svc.base_currency.upper(),
            'target_currency': moeda_funcional,
            'rate_date': rate_date,
            'rate_value': float(rate_value),
            'rate_source': 'ExchangeRatesAPI.io',
        }
    except Exception as e:
        print(f"[INDUSTRIA FX] Erro ao obter taxa de câmbio para empresa {empresa_id} ({moeda_funcional}): {e}")
        return None


@ordem_producao_bp.route('/producao/gantt')
@login_required
def producao_gantt():
    """Tela de produção estilo Kanban (cards) com troca de etapa."""
    db = get_db()

    status_filtro = (request.args.get('status') or '').strip()
    etapa_filtro = (request.args.get('etapa_id') or '').strip()
    grupo_etapas_filtro = (request.args.get('grupo_etapas_id') or '').strip()
    q_filtro = (request.args.get('q') or '').strip()
    etapas_visiveis_raw = request.args.getlist('etapas')
    etapas_visiveis = []
    for v in etapas_visiveis_raw:
        try:
            etapas_visiveis.append(int(v))
        except Exception:
            pass

    grupos_etapas = db.fetch_all("""
        SELECT id, nome, ordem, ativo, cor_hex, descricao
        FROM producao_etapas_grupos
        WHERE ativo = 1
        ORDER BY ordem, id
    """) or []

    etapas_params = []
    etapas_where = "WHERE e.ativo = 1"
    if grupo_etapas_filtro:
        etapas_where += " AND e.grupo_etapas_id = %s"
        etapas_params.append(grupo_etapas_filtro)

    etapas = db.fetch_all(f"""
        SELECT e.id, e.nome, e.ordem, e.cor_hex, e.icone, e.descricao,
               e.grupo_etapas_id,
               g.nome AS grupo_etapas_nome,
               g.ordem AS grupo_etapas_ordem,
               g.cor_hex AS grupo_etapas_cor_hex,
               g.descricao AS grupo_etapas_descricao
        FROM producao_etapas e
        LEFT JOIN producao_etapas_grupos g ON g.id = e.grupo_etapas_id
        {etapas_where}
        ORDER BY e.ordem, e.id
    """, tuple(etapas_params) if etapas_params else None) or []

    # Lista completa (para dropdown de colunas) também respeita filtro de grupo
    etapas_todas = etapas

    try:
        query = """
            SELECT
                v.id,
                v.numero_op,
                v.cliente_nome,
                v.produto_nome,
                v.status,
                v.data_solicitacao,
                v.data_prevista,
                v.created_at,
                op.data_inicio_producao,
                op.data_conclusao,
                op.etapa_atual_id,
                e.nome AS etapa_nome,
                e.cor_hex AS etapa_cor_hex,
                e.icone AS etapa_icone
            FROM vw_ordens_producao_resumo v
            INNER JOIN ordens_producao op ON op.id = v.id
            LEFT JOIN producao_etapas e ON e.id = op.etapa_atual_id
            WHERE 1=1
        """
        params = []

        if status_filtro:
            query += " AND v.status = %s"
            params.append(status_filtro)
        else:
            # Padrão: não exibir concluídas/canceladas no Gantt (apenas se filtrar explicitamente)
            query += " AND v.status NOT IN ('concluida', 'cancelada')"

        if etapa_filtro:
            query += " AND op.etapa_atual_id = %s"
            params.append(etapa_filtro)

        # Filtro de colunas visíveis do Kanban (multi-seleção)
        # 0 = Sem Etapa (NULL)
        if etapas_visiveis:
            etapas_sem = [x for x in etapas_visiveis if x != 0]
            inclui_sem_etapa = 0 in etapas_visiveis

            if etapas_sem and inclui_sem_etapa:
                placeholders = ','.join(['%s'] * len(etapas_sem))
                query += f" AND (op.etapa_atual_id IN ({placeholders}) OR op.etapa_atual_id IS NULL)"
                params.extend(etapas_sem)
            elif etapas_sem:
                placeholders = ','.join(['%s'] * len(etapas_sem))
                query += f" AND op.etapa_atual_id IN ({placeholders})"
                params.extend(etapas_sem)
            elif inclui_sem_etapa:
                query += " AND op.etapa_atual_id IS NULL"

        if q_filtro:
            query += " AND (v.cliente_nome LIKE %s OR v.produto_nome LIKE %s OR v.numero_op LIKE %s)"
            like = f"%{q_filtro}%"
            params.extend([like, like, like])

        query += " ORDER BY COALESCE(v.data_prevista, v.data_solicitacao, v.created_at) ASC, v.id DESC"

        # Buscar lotes (subdivisões) para permitir avanço parcial entre etapas
        query2 = """
            SELECT
                l.id AS lote_id,
                l.sequencia AS lote_sequencia,
                l.quantidade AS lote_quantidade,
                l.align_side AS lote_align_side,
                l.etapa_atual_id AS lote_etapa_atual_id,
                l.status_operador,
                l.arara,
                l.data_atribuicao,
                l.data_inicio_operador,
                l.data_fim_operador,
                u_lider.name AS lider_nome,
                u_operador.name AS operador_nome,
                u_atribuidor.name AS atribuido_por_nome,
                v.id AS op_id,
                v.numero_op,
                v.cliente_nome,
                v.produto_nome,
                v.status,
                v.data_solicitacao,
                v.data_prevista,
                v.created_at,
                op.data_inicio_producao,
                op.data_conclusao,
                op.quantidade AS op_quantidade_total,
                e.nome AS etapa_nome,
                e.cor_hex AS etapa_cor_hex,
                e.icone AS etapa_icone,
                og.id AS grupo_id,
                o.id AS orcamento_id,
                o.numero AS orcamento_numero,
                op.planejamento_id,
                ps.codigo AS planejamento_codigo,
                (SELECT MAX(log.created_at) 
                 FROM op_lotes_etapas_log log 
                 WHERE log.lote_id = l.id 
                   AND log.etapa_nova_id = l.etapa_atual_id) AS data_chegada_etapa,
                pp.id AS pausa_id,
                pp.inicio AS pausa_inicio,
                ppm.nome AS pausa_motivo,
                ppm.tipo AS pausa_tipo,
                ppm.icone AS pausa_icone,
                ppm.cor_hex AS pausa_cor
            FROM op_lotes l
            INNER JOIN ordens_producao op ON op.id = l.ordem_producao_id
            INNER JOIN vw_ordens_producao_resumo v ON v.id = op.id
            LEFT JOIN producao_etapas e ON e.id = l.etapa_atual_id
            LEFT JOIN orcamento_op_itens oi ON oi.ordem_producao_id = v.id
            LEFT JOIN orcamento_op_grupos og ON og.id = oi.grupo_id
            LEFT JOIN orcamentos o ON o.id = og.orcamento_id
            LEFT JOIN lider_operadores lo ON lo.operador_id = l.operador_id
            LEFT JOIN users u_lider ON u_lider.id = lo.lider_id
            LEFT JOIN users u_operador ON u_operador.id = l.operador_id
            LEFT JOIN users u_atribuidor ON u_atribuidor.id = l.atribuido_por_id
            LEFT JOIN producao_pausas pp ON pp.lote_id = l.id AND pp.fim IS NULL
            LEFT JOIN producao_pausas_motivos ppm ON ppm.id = pp.motivo_id
            WHERE 1=1
        """

        # reutilizar filtros já aplicados
        # (montar novamente para manter o mesmo comportamento)
        params2 = []

        if status_filtro:
            query2 += " AND v.status = %s"
            params2.append(status_filtro)
        else:
            # Padrão: não exibir concluídas/canceladas no Gantt (apenas se filtrar explicitamente)
            query2 += " AND v.status NOT IN ('concluida', 'cancelada')"

        if etapa_filtro:
            query2 += " AND l.etapa_atual_id = %s"
            params2.append(etapa_filtro)

        if etapas_visiveis:
            etapas_sem = [x for x in etapas_visiveis if x != 0]
            if etapas_sem:
                placeholders = ','.join(['%s'] * len(etapas_sem))
                query2 += f" AND l.etapa_atual_id IN ({placeholders})"
                params2.extend(etapas_sem)

        if q_filtro:
            query2 += " AND (v.cliente_nome LIKE %s OR v.produto_nome LIKE %s OR v.numero_op LIKE %s)"
            like = f"%{q_filtro}%"
            params2.extend([like, like, like])

        query2 += " ORDER BY COALESCE(o.numero, '') DESC, v.id DESC"

        lotes = db.fetch_all(query2, tuple(params2) if params2 else None) or []

        # Filtrar lista de etapas (colunas) para renderização
        if etapas_visiveis:
            etapas_render = [e for e in etapas if int(e.get('id')) in etapas_visiveis]
        else:
            etapas_render = etapas

        # Cabeçalho agrupado (Grupo de Etapas -> qtd de colunas)
        grupos_header = []
        atual = None
        for e in etapas_render:
            gid = e.get('grupo_etapas_id')
            gnome = e.get('grupo_etapas_nome') or 'Sem Grupo'
            gcor = e.get('grupo_etapas_cor_hex')
            gdesc = e.get('grupo_etapas_descricao')
            key = str(gid) if gid else '0'
            if (not atual) or (atual.get('key') != key):
                atual = {'key': key, 'nome': gnome, 'cor_hex': gcor, 'descricao': gdesc, 'count': 0}
                grupos_header.append(atual)
            atual['count'] += 1

        # Montar grupos (linhas) e matriz grupo x etapa
        # Grupos podem vir de orçamentos OU de planejamentos semanais
        grupos = {}
        for it in lotes:
            gid = it.get('grupo_id')
            plan_id = it.get('planejamento_id')

            if gid:
                # Grupo de orçamento
                if gid not in grupos:
                    grupos[gid] = {
                        'grupo_id': gid,
                        'orcamento_id': it.get('orcamento_id'),
                        'orcamento_numero': it.get('orcamento_numero'),
                        'cliente_nome': it.get('cliente_nome'),
                        'planejamento_id': None,
                        'planejamento_codigo': None,
                    }
            elif plan_id:
                # Grupo virtual de planejamento (usa ID negativo para não colidir)
                vkey = -plan_id
                if vkey not in grupos:
                    grupos[vkey] = {
                        'grupo_id': vkey,
                        'orcamento_id': None,
                        'orcamento_numero': None,
                        'cliente_nome': 'Produção p/ Estoque',
                        'planejamento_id': plan_id,
                        'planejamento_codigo': it.get('planejamento_codigo') or f'PL-{plan_id}',
                    }
                # Marcar o lote com o grupo virtual para o loop abaixo
                it['grupo_id'] = vkey
            else:
                # OP avulsa sem orçamento nem planejamento — grupo "Avulso"
                avulso_key = 0
                if avulso_key not in grupos:
                    grupos[avulso_key] = {
                        'grupo_id': avulso_key,
                        'orcamento_id': None,
                        'orcamento_numero': None,
                        'cliente_nome': it.get('cliente_nome') or 'Avulso',
                        'planejamento_id': None,
                        'planejamento_codigo': None,
                    }
                it['grupo_id'] = avulso_key

        grupos_lista = list(grupos.values())
        grupos_lista.sort(key=lambda x: (x.get('orcamento_numero') or '', x.get('planejamento_codigo') or ''), reverse=True)

        ops_por_grupo_etapa = {}
        for g in grupos_lista:
            ops_por_grupo_etapa[g['grupo_id']] = {}
            for et in etapas_render:
                ops_por_grupo_etapa[g['grupo_id']][et['id']] = []

        for it in lotes:
            gid = it.get('grupo_id')
            etid = it.get('lote_etapa_atual_id')
            if gid is None or not etid:
                continue
            if gid not in ops_por_grupo_etapa:
                continue
            if etid not in ops_por_grupo_etapa[gid]:
                continue
            ops_por_grupo_etapa[gid][etid].append(it)

        return render_template(
            'industria/producao_gantt.html',
            lotes=lotes,
            etapas=etapas_render,
            etapas_todas=etapas_todas,
            etapas_visiveis=etapas_visiveis,
            grupos_etapas=grupos_etapas,
            grupo_etapas_filtro=grupo_etapas_filtro,
            grupos_header=grupos_header,
            grupos=grupos_lista,
            ops_por_grupo_etapa=ops_por_grupo_etapa,
            status_filtro=status_filtro,
            etapa_filtro=etapa_filtro,
            q_filtro=q_filtro,
            full_width=True,
            menu_collapsed=True,
        )

    except Exception as e:
        flash(f'Erro ao carregar produção: {str(e)}', 'danger')
        return render_template(
            'industria/producao_gantt.html',
            lotes=[],
            etapas=etapas,
            etapas_todas=etapas,
            etapas_visiveis=etapas_visiveis,
            grupos_etapas=grupos_etapas,
            grupo_etapas_filtro=grupo_etapas_filtro,
            grupos_header=[],
            grupos=[],
            ops_por_grupo_etapa={},
            status_filtro=status_filtro,
            etapa_filtro=etapa_filtro,
            q_filtro=q_filtro,
            full_width=True,
            menu_collapsed=True,
        )


@ordem_producao_bp.route('/producao/gantt-v2')
@login_required
def producao_gantt_v2():
    db = get_db()

    status_filtro = (request.args.get('status') or '').strip()
    etapa_filtro = (request.args.get('etapa_id') or '').strip()
    grupo_etapas_filtro = (request.args.get('grupo_etapas_id') or '').strip()
    q_filtro = (request.args.get('q') or '').strip()
    etapas_visiveis_raw = request.args.getlist('etapas')
    etapas_visiveis = []
    for v in etapas_visiveis_raw:
        try:
            etapas_visiveis.append(int(v))
        except Exception:
            pass

    grupos_etapas = db.fetch_all("""
        SELECT id, nome, ordem, ativo, cor_hex, descricao
        FROM producao_etapas_grupos
        WHERE ativo = 1
        ORDER BY ordem, id
    """) or []

    etapas_params = []
    etapas_where = "WHERE e.ativo = 1"
    if grupo_etapas_filtro:
        etapas_where += " AND e.grupo_etapas_id = %s"
        etapas_params.append(grupo_etapas_filtro)

    etapas = db.fetch_all(f"""
        SELECT e.id, e.nome, e.ordem, e.cor_hex, e.icone, e.descricao,
               e.grupo_etapas_id,
               g.nome AS grupo_etapas_nome,
               g.ordem AS grupo_etapas_ordem,
               g.cor_hex AS grupo_etapas_cor_hex,
               g.descricao AS grupo_etapas_descricao
        FROM producao_etapas e
        LEFT JOIN producao_etapas_grupos g ON g.id = e.grupo_etapas_id
        {etapas_where}
        ORDER BY e.ordem, e.id
    """, tuple(etapas_params) if etapas_params else None) or []

    etapas_todas = etapas

    try:
        query2 = """
            SELECT
                l.id AS lote_id,
                l.sequencia AS lote_sequencia,
                l.quantidade AS lote_quantidade,
                l.align_side AS lote_align_side,
                l.etapa_atual_id AS lote_etapa_atual_id,
                v.id AS op_id,
                v.numero_op,
                v.cliente_nome,
                v.produto_nome,
                v.status,
                v.data_solicitacao,
                v.data_prevista,
                v.created_at,
                op.data_inicio_producao,
                op.data_conclusao,
                op.quantidade AS op_quantidade_total,
                e.nome AS etapa_nome,
                e.cor_hex AS etapa_cor_hex,
                e.icone AS etapa_icone,
                og.id AS grupo_id,
                o.id AS orcamento_id,
                o.numero AS orcamento_numero,
                op.planejamento_id
            FROM op_lotes l
            INNER JOIN ordens_producao op ON op.id = l.ordem_producao_id
            INNER JOIN vw_ordens_producao_resumo v ON v.id = op.id
            LEFT JOIN producao_etapas e ON e.id = l.etapa_atual_id
            LEFT JOIN orcamento_op_itens oi ON oi.ordem_producao_id = v.id
            LEFT JOIN orcamento_op_grupos og ON og.id = oi.grupo_id
            LEFT JOIN orcamentos o ON o.id = og.orcamento_id
            WHERE 1=1
        """

        params2 = []
        if status_filtro:
            query2 += " AND v.status = %s"
            params2.append(status_filtro)
        else:
            query2 += " AND v.status NOT IN ('concluida', 'cancelada')"

        if etapa_filtro:
            query2 += " AND l.etapa_atual_id = %s"
            params2.append(etapa_filtro)

        if etapas_visiveis:
            etapas_sem = [x for x in etapas_visiveis if x != 0]
            if etapas_sem:
                placeholders = ','.join(['%s'] * len(etapas_sem))
                query2 += f" AND l.etapa_atual_id IN ({placeholders})"
                params2.extend(etapas_sem)

        if q_filtro:
            query2 += " AND (v.cliente_nome LIKE %s OR v.produto_nome LIKE %s OR v.numero_op LIKE %s)"
            like = f"%{q_filtro}%"
            params2.extend([like, like, like])

        query2 += " ORDER BY COALESCE(o.numero, '') DESC, v.id DESC"

        lotes = db.fetch_all(query2, tuple(params2) if params2 else None) or []

        if etapas_visiveis:
            etapas_render = [e for e in etapas if int(e.get('id')) in etapas_visiveis]
        else:
            etapas_render = etapas

        grupos_header = []
        atual = None
        for e in etapas_render:
            gid = e.get('grupo_etapas_id')
            gnome = e.get('grupo_etapas_nome') or 'Sem Grupo'
            gcor = e.get('grupo_etapas_cor_hex')
            gdesc = e.get('grupo_etapas_descricao')
            key = str(gid) if gid else '0'
            if (not atual) or (atual.get('key') != key):
                atual = {'key': key, 'nome': gnome, 'cor_hex': gcor, 'descricao': gdesc, 'count': 0}
                grupos_header.append(atual)
            atual['count'] += 1

        grupos = {}
        for it in lotes:
            gid = it.get('grupo_id')
            plan_id = it.get('planejamento_id')

            if gid:
                if gid not in grupos:
                    grupos[gid] = {
                        'grupo_id': gid,
                        'orcamento_id': it.get('orcamento_id'),
                        'orcamento_numero': it.get('orcamento_numero'),
                        'cliente_nome': it.get('cliente_nome'),
                        'planejamento_id': None,
                        'planejamento_codigo': None,
                    }
            elif plan_id:
                vkey = -plan_id
                if vkey not in grupos:
                    grupos[vkey] = {
                        'grupo_id': vkey,
                        'orcamento_id': None,
                        'orcamento_numero': None,
                        'cliente_nome': 'Produção p/ Estoque',
                        'planejamento_id': plan_id,
                        'planejamento_codigo': it.get('planejamento_codigo') or f'PL-{plan_id}',
                    }
                it['grupo_id'] = vkey
            else:
                avulso_key = 0
                if avulso_key not in grupos:
                    grupos[avulso_key] = {
                        'grupo_id': avulso_key,
                        'orcamento_id': None,
                        'orcamento_numero': None,
                        'cliente_nome': it.get('cliente_nome') or 'Avulso',
                        'planejamento_id': None,
                        'planejamento_codigo': None,
                    }
                it['grupo_id'] = avulso_key

        grupos_lista = list(grupos.values())
        grupos_lista.sort(key=lambda x: (x.get('orcamento_numero') or '', x.get('planejamento_codigo') or ''), reverse=True)

        etapa_pos = {int(e.get('id')): idx for idx, e in enumerate(etapas_render)}

        ops_por_grupo = {}
        for it in lotes:
            gid = it.get('grupo_id')
            etid = it.get('lote_etapa_atual_id')
            op_id = it.get('op_id')
            if gid is None or not etid or not op_id:
                continue
            try:
                etid_int = int(etid)
            except Exception:
                continue
            if etid_int not in etapa_pos:
                continue

            if gid not in ops_por_grupo:
                ops_por_grupo[gid] = {}
            if op_id not in ops_por_grupo[gid]:
                ops_por_grupo[gid][op_id] = {
                    'op_id': op_id,
                    'numero_op': it.get('numero_op'),
                    'cliente_nome': it.get('cliente_nome'),
                    'produto_nome': it.get('produto_nome'),
                    'status': it.get('status'),
                    'op_quantidade_total': it.get('op_quantidade_total'),
                    'op_url': url_for('ordem_producao.visualizar_op', id=op_id),
                    'etapas_data': {},
                    'span_inicio': etapa_pos[etid_int],
                    'span_fim': etapa_pos[etid_int],
                }

            opref = ops_por_grupo[gid][op_id]
            if etid_int not in opref['etapas_data']:
                opref['etapas_data'][etid_int] = {
                    'qty_total': Decimal('0'),
                    'lotes': []
                }

            try:
                qtd = Decimal(str(it.get('lote_quantidade') or 0))
            except Exception:
                qtd = Decimal('0')

            opref['etapas_data'][etid_int]['qty_total'] += qtd
            opref['etapas_data'][etid_int]['lotes'].append(it)

            pos = etapa_pos[etid_int]
            if pos < opref['span_inicio']:
                opref['span_inicio'] = pos
            if pos > opref['span_fim']:
                opref['span_fim'] = pos

        for gid, opsmap in (ops_por_grupo or {}).items():
            ops_por_grupo[gid] = list(opsmap.values())

        return render_template(
            'industria/producao_gantt_v2.html',
            lotes=lotes,
            etapas=etapas_render,
            etapas_todas=etapas_todas,
            etapas_visiveis=etapas_visiveis,
            grupos_etapas=grupos_etapas,
            grupo_etapas_filtro=grupo_etapas_filtro,
            grupos_header=grupos_header,
            grupos=grupos_lista,
            ops_por_grupo=ops_por_grupo,
            status_filtro=status_filtro,
            etapa_filtro=etapa_filtro,
            q_filtro=q_filtro,
            full_width=True,
            menu_collapsed=True,
        )

    except Exception as e:
        flash(f'Erro ao carregar produção: {str(e)}', 'danger')
        return render_template(
            'industria/producao_gantt_v2.html',
            lotes=[],
            etapas=etapas,
            etapas_todas=etapas,
            etapas_visiveis=etapas_visiveis,
            grupos_etapas=grupos_etapas,
            grupo_etapas_filtro=grupo_etapas_filtro,
            grupos_header=[],
            grupos=[],
            ops_por_grupo={},
            status_filtro=status_filtro,
            etapa_filtro=etapa_filtro,
            q_filtro=q_filtro,
            full_width=True,
            menu_collapsed=True,
        )


@ordem_producao_bp.route('/etapas')
@login_required
def etapas_lista():
    """Lista etapas de produção (CRUD básico)."""
    db = get_db()
    try:
        etapas = db.fetch_all("""
            SELECT e.id, e.nome, e.ordem, e.ativo, e.cor_hex, e.icone, e.descricao, e.grupo_etapas_id,
                   g.nome AS grupo_nome,
                   e.operador_padrao_id,
                   u.name AS operador_nome
            FROM producao_etapas e
            LEFT JOIN producao_etapas_grupos g ON g.id = e.grupo_etapas_id
            LEFT JOIN users u ON u.id = e.operador_padrao_id
            ORDER BY e.ordem, e.id
        """) or []
        return render_template('industria/producao_etapas_lista.html', etapas=etapas)
    except Exception as e:
        flash(f'Erro ao carregar etapas: {str(e)}', 'danger')
        return render_template('industria/producao_etapas_lista.html', etapas=[])


@ordem_producao_bp.route('/etapas/grupos')
@login_required
def etapas_grupos_lista():
    """Lista grupos de etapas (CRUD básico)."""
    db = get_db()
    try:
        grupos = db.fetch_all("""
            SELECT id, nome, ordem, ativo, cor_hex, descricao
            FROM producao_etapas_grupos
            ORDER BY ordem, id
        """) or []
        return render_template('industria/producao_etapas_grupos_lista.html', grupos=grupos)
    except Exception as e:
        flash(f'Erro ao carregar grupos: {str(e)}', 'danger')
        return render_template('industria/producao_etapas_grupos_lista.html', grupos=[])


@ordem_producao_bp.route('/etapas/grupos/novo', methods=['GET', 'POST'])
@login_required
def etapas_grupos_novo():
    """Cria um novo grupo de etapas."""
    db = get_db()
    if request.method == 'POST':
        try:
            nome = (request.form.get('nome') or '').strip()
            ordem = request.form.get('ordem') or 0
            ativo = 1 if (request.form.get('ativo') or '1') == '1' else 0
            cor_hex = (request.form.get('cor_hex') or '').strip() or None
            descricao = (request.form.get('descricao') or '').strip() or None

            if not nome:
                flash('Nome é obrigatório.', 'warning')
                return render_template('industria/producao_etapas_grupos_form.html', grupo=None)

            db.insert(
                "INSERT INTO producao_etapas_grupos (nome, ordem, ativo, cor_hex, descricao) VALUES (%s, %s, %s, %s, %s)",
                (nome, ordem, ativo, cor_hex, descricao)
            )
            flash('Grupo criado com sucesso!', 'success')
            return redirect(url_for('ordem_producao.etapas_grupos_lista'))
        except Exception as e:
            flash(f'Erro ao criar grupo: {str(e)}', 'danger')

    return render_template('industria/producao_etapas_grupos_form.html', grupo=None)


@ordem_producao_bp.route('/etapas/grupos/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def etapas_grupos_editar(id):
    """Edita um grupo de etapas."""
    db = get_db()
    grupo = db.fetch_one("SELECT id, nome, ordem, ativo, cor_hex, descricao FROM producao_etapas_grupos WHERE id = %s", (id,))
    if not grupo:
        flash('Grupo não encontrado.', 'warning')
        return redirect(url_for('ordem_producao.etapas_grupos_lista'))

    if request.method == 'POST':
        try:
            nome = (request.form.get('nome') or '').strip()
            ordem = request.form.get('ordem') or 0
            ativo = 1 if (request.form.get('ativo') or '1') == '1' else 0
            cor_hex = (request.form.get('cor_hex') or '').strip() or None
            descricao = (request.form.get('descricao') or '').strip() or None

            if not nome:
                flash('Nome é obrigatório.', 'warning')
                return render_template('industria/producao_etapas_grupos_form.html', grupo=grupo)

            db.update(
                "UPDATE producao_etapas_grupos SET nome=%s, ordem=%s, ativo=%s, cor_hex=%s, descricao=%s, updated_at=NOW() WHERE id=%s",
                (nome, ordem, ativo, cor_hex, descricao, id)
            )
            flash('Grupo atualizado com sucesso!', 'success')
            return redirect(url_for('ordem_producao.etapas_grupos_lista'))
        except Exception as e:
            flash(f'Erro ao atualizar grupo: {str(e)}', 'danger')

    return render_template('industria/producao_etapas_grupos_form.html', grupo=grupo)


@ordem_producao_bp.route('/etapas/grupos/toggle/<int:id>', methods=['POST'])
@login_required
def etapas_grupos_toggle(id):
    """Ativa/desativa um grupo de etapas."""
    db = get_db()
    try:
        grupo = db.fetch_one("SELECT id, ativo FROM producao_etapas_grupos WHERE id=%s", (id,))
        if not grupo:
            flash('Grupo não encontrado.', 'warning')
            return redirect(url_for('ordem_producao.etapas_grupos_lista'))

        novo_ativo = 0 if int(grupo.get('ativo') or 0) == 1 else 1
        db.execute_query("UPDATE producao_etapas_grupos SET ativo=%s, updated_at=NOW() WHERE id=%s", (novo_ativo, id))
        flash('Grupo atualizado!', 'success')
    except Exception as e:
        flash(f'Erro ao alterar grupo: {str(e)}', 'danger')
    return redirect(url_for('ordem_producao.etapas_grupos_lista'))


@ordem_producao_bp.route('/etapas/nova', methods=['GET', 'POST'])
@login_required
def etapas_nova():
    """Cria uma nova etapa."""
    db = get_db()
    grupos_etapas = db.fetch_all("""
        SELECT id, nome
        FROM producao_etapas_grupos
        WHERE ativo = 1
        ORDER BY ordem, id
    """) or []
    if request.method == 'POST':
        try:
            nome = (request.form.get('nome') or '').strip()
            ordem = request.form.get('ordem') or 0
            ativo = 1 if (request.form.get('ativo') or '1') == '1' else 0
            cor_hex = (request.form.get('cor_hex') or '').strip() or None
            icone = (request.form.get('icone') or '').strip() or None
            descricao = (request.form.get('descricao') or '').strip() or None
            grupo_etapas_id = (request.form.get('grupo_etapas_id') or '').strip() or None

            if not nome:
                flash('Nome é obrigatório.', 'warning')
                return render_template('industria/producao_etapas_form.html', etapa=None, grupos_etapas=grupos_etapas)

            db.insert(
                "INSERT INTO producao_etapas (nome, ordem, ativo, cor_hex, icone, descricao, grupo_etapas_id) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (nome, ordem, ativo, cor_hex, icone, descricao, grupo_etapas_id)
            )
            flash('Etapa criada com sucesso!', 'success')
            return redirect(url_for('ordem_producao.etapas_lista'))
        except Exception as e:
            flash(f'Erro ao criar etapa: {str(e)}', 'danger')

    return render_template('industria/producao_etapas_form.html', etapa=None, grupos_etapas=grupos_etapas)


@ordem_producao_bp.route('/etapas/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def etapas_editar(id):
    """Edita uma etapa."""
    db = get_db()
    etapa = db.fetch_one("SELECT id, nome, ordem, ativo, cor_hex, icone, descricao, grupo_etapas_id, operador_padrao_id FROM producao_etapas WHERE id = %s", (id,))
    if not etapa:
        flash('Etapa não encontrada.', 'warning')
        return redirect(url_for('ordem_producao.etapas_lista'))

    grupos_etapas = db.fetch_all("""
        SELECT id, nome
        FROM producao_etapas_grupos
        WHERE ativo = 1
        ORDER BY ordem, id
    """) or []
    
    # Buscar operadores (usuários com eh_operador = 1)
    operadores = db.fetch_all("""
        SELECT id, name FROM users 
        WHERE eh_operador = 1 AND status = 'active'
        ORDER BY name
    """) or []

    if request.method == 'POST':
        try:
            nome = (request.form.get('nome') or '').strip()
            ordem = request.form.get('ordem') or 0
            ativo = 1 if (request.form.get('ativo') or '1') == '1' else 0
            cor_hex = (request.form.get('cor_hex') or '').strip() or None
            icone = (request.form.get('icone') or '').strip() or None
            grupo_etapas_id = (request.form.get('grupo_etapas_id') or '').strip() or None
            descricao = (request.form.get('descricao') or '').strip() or None
            operador_padrao_id = (request.form.get('operador_padrao_id') or '').strip() or None

            if not nome:
                flash('Nome é obrigatório.', 'warning')
                return render_template('industria/producao_etapas_form.html', etapa=etapa, grupos_etapas=grupos_etapas, operadores=operadores)

            db.update(
                "UPDATE producao_etapas SET nome=%s, ordem=%s, ativo=%s, cor_hex=%s, icone=%s, descricao=%s, grupo_etapas_id=%s, operador_padrao_id=%s WHERE id=%s",
                (nome, ordem, ativo, cor_hex, icone, descricao, grupo_etapas_id, operador_padrao_id, id)
            )
            flash('Etapa atualizada com sucesso!', 'success')
            return redirect(url_for('ordem_producao.etapas_lista'))
        except Exception as e:
            flash(f'Erro ao atualizar etapa: {str(e)}', 'danger')

    return render_template('industria/producao_etapas_form.html', etapa=etapa, grupos_etapas=grupos_etapas, operadores=operadores)


@ordem_producao_bp.route('/etapas/toggle/<int:id>', methods=['POST'])
@login_required
def etapas_toggle(id):
    """Ativa/desativa uma etapa."""
    db = get_db()
    try:
        etapa = db.fetch_one("SELECT id, ativo FROM producao_etapas WHERE id=%s", (id,))
        if not etapa:
            flash('Etapa não encontrada.', 'warning')
            return redirect(url_for('ordem_producao.etapas_lista'))

        novo_ativo = 0 if int(etapa.get('ativo') or 0) == 1 else 1
        db.execute_query("UPDATE producao_etapas SET ativo=%s WHERE id=%s", (novo_ativo, id))
        flash('Etapa atualizada!', 'success')
    except Exception as e:
        flash(f'Erro ao alterar etapa: {str(e)}', 'danger')
    return redirect(url_for('ordem_producao.etapas_lista'))


def _aplicar_template_em_op(db, op_id, template_id):
    """Aplica um template na OP: limpa itens atuais, copia itens do template multiplicando pela quantidade do produto final."""
    op = db.fetch_one("SELECT id, produto_id, quantidade FROM ordens_producao WHERE id = %s", (op_id,))
    if not op:
        raise Exception('OP não encontrada')

    qtd_final = Decimal(str(op.get('quantidade') or 0))
    if qtd_final <= 0:
        qtd_final = Decimal('1')

    # Buscar itens do template
    itens = db.fetch_all("""
        SELECT tipo_item, produto_id, descricao, quantidade, unidade_medida, custo_unitario_base
        FROM produto_template_itens
        WHERE template_id = %s
        ORDER BY tipo_item, id
    """, (template_id,)) or []

    # Limpar itens atuais
    db.execute_query("DELETE FROM ordem_producao_itens WHERE ordem_producao_id = %s", (op_id,))

    custo_total_atual = Decimal('0')
    for it in itens:
        prod = db.fetch_one("SELECT name, unit_measure, cost_price FROM products WHERE id = %s", (it['produto_id'],))
        if not prod:
            continue

        qtd_base = Decimal(str(it.get('quantidade') or 0))
        qtd_item = (qtd_base * qtd_final).quantize(Decimal('0.0001'))
        custo_unit_atual = Decimal(str(prod.get('cost_price') or 0))
        custo_total_item = (qtd_item * custo_unit_atual).quantize(Decimal('0.01'))
        custo_total_atual += custo_total_item

        db.insert("""
            INSERT INTO ordem_producao_itens (
                ordem_producao_id, tipo_item, produto_id, descricao,
                quantidade, unidade_medida, custo_unitario_template,
                custo_unitario_atual, custo_total, veio_template
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 1)
        """, (
            op_id,
            it['tipo_item'],
            it['produto_id'],
            (it.get('descricao') or prod.get('name')),
            str(qtd_item),
            (it.get('unidade_medida') or prod.get('unit_measure')),
            it.get('custo_unitario_base'),
            str(custo_unit_atual),
            str(custo_total_item)
        ))

    template = db.fetch_one("""
        SELECT id, custo_total_base
        FROM produto_templates_producao
        WHERE id = %s
    """, (template_id,))

    db.execute_query("""
        UPDATE ordens_producao
        SET usou_template = 1,
            template_usado_id = %s,
            custo_total_template = %s,
            custo_total_atual = %s
        WHERE id = %s
    """, (
        template_id,
        str((template or {}).get('custo_total_base') or 0),
        str(custo_total_atual),
        op_id
    ))


def _criar_template_a_partir_op(db, op_id):
    """Cria um template (ativo) a partir dos itens atuais da OP e retorna o template_id."""
    op = db.fetch_one("SELECT id, produto_id, quantidade, numero_op FROM ordens_producao WHERE id = %s", (op_id,))
    if not op:
        raise Exception('OP não encontrada')

    produto_id = op.get('produto_id')
    if not produto_id:
        raise Exception('OP sem produto final')

    qtd_final = Decimal(str(op.get('quantidade') or 0))
    if qtd_final <= 0:
        qtd_final = Decimal('1')

    # Itens atuais da OP
    itens = db.fetch_all("""
        SELECT tipo_item, produto_id, descricao, quantidade, unidade_medida, custo_unitario_atual
        FROM ordem_producao_itens
        WHERE ordem_producao_id = %s
        ORDER BY tipo_item, id
    """, (op_id,)) or []

    if not itens:
        raise Exception('A OP não possui itens para gerar um template.')

    # Próxima versão
    versao_atual = db.fetch_one(
        "SELECT MAX(versao) AS v FROM produto_templates_producao WHERE produto_id = %s",
        (produto_id,)
    )
    prox_versao = int((versao_atual or {}).get('v') or 0) + 1

    # Desativar template ativo anterior (se existir)
    db.execute_query(
        "UPDATE produto_templates_producao SET ativo = 0 WHERE produto_id = %s AND ativo = 1",
        (produto_id,)
    )

    nome_template = f"Template (OP {op.get('numero_op')})" if op.get('numero_op') else "Template gerado da OP"

    # Custo base: soma dos custos base por 1 unidade do produto final
    custo_total_base = Decimal('0')
    itens_normalizados = []
    for it in itens:
        qtd_op = Decimal(str(it.get('quantidade') or 0))
        qtd_base = (qtd_op / qtd_final).quantize(Decimal('0.0001'))
        custo_unit = Decimal(str(it.get('custo_unitario_atual') or 0))
        custo_total_item = (qtd_base * custo_unit).quantize(Decimal('0.01'))
        custo_total_base += custo_total_item
        itens_normalizados.append((it, qtd_base, custo_unit, custo_total_item))

    template_id = db.insert("""
        INSERT INTO produto_templates_producao (
            produto_id, versao, nome_template, custo_total_base, ativo, created_by
        ) VALUES (%s, %s, %s, %s, 1, %s)
    """, (
        produto_id,
        prox_versao,
        nome_template,
        str(custo_total_base),
        session.get('user_id')
    ))

    for it, qtd_base, custo_unit, custo_total_item in itens_normalizados:
        prod = db.fetch_one("SELECT unit_measure FROM products WHERE id = %s", (it['produto_id'],))
        unidade = it.get('unidade_medida') or (prod or {}).get('unit_measure')
        db.insert("""
            INSERT INTO produto_template_itens (
                template_id, tipo_item, produto_id, descricao,
                quantidade, unidade_medida, custo_unitario_base, custo_total_base
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            template_id,
            it['tipo_item'],
            it['produto_id'],
            it.get('descricao'),
            str(qtd_base),
            unidade,
            str(custo_unit),
            str(custo_total_item)
        ))

    return template_id


@ordem_producao_bp.route('/')
@industria_ops_visualizar_required
def listar_ops():
    """Lista todas as ordens de produção"""
    db = get_db()
    
    # Filtros
    status_filtro = request.args.get('status', '')
    cliente_filtro = request.args.get('cliente', '')
    
    try:
        query = """
            SELECT
                v.*,
                op.empresa_id,
                op.prioridade,
                op.tipo_op,
                o.numero AS orcamento_numero,
                og.id AS grupo_id,
                og.orcamento_id
            FROM vw_ordens_producao_resumo v
            INNER JOIN ordens_producao op ON op.id = v.id
            LEFT JOIN orcamento_op_itens oi ON oi.ordem_producao_id = v.id
            LEFT JOIN orcamento_op_grupos og ON og.id = oi.grupo_id
            LEFT JOIN orcamentos o ON o.id = og.orcamento_id
            WHERE 1=1
        """
        params = []
        
        if status_filtro:
            query += " AND status = %s"
            params.append(status_filtro)
        
        if cliente_filtro:
            query += " AND cliente_nome LIKE %s"
            params.append(f'%{cliente_filtro}%')
        
        query += " ORDER BY created_at DESC"
        
        ops = db.fetch_all(query, tuple(params) if params else None)
        
        fx_cache = {}
        for op in ops or []:
            empresa_id = op.get('empresa_id')
            if not empresa_id:
                op['custo_total_fx'] = None
                op['fx_currency_code'] = None
                continue
            if empresa_id not in fx_cache:
                fx_cache[empresa_id] = calcular_fx_para_empresa(db, empresa_id)
            fx_info = fx_cache.get(empresa_id)
            if fx_info and op.get('custo_total_atual') is not None:
                try:
                    valor_brl = float(op.get('custo_total_atual') or 0)
                except (TypeError, ValueError):
                    valor_brl = 0.0
                rate = fx_info.get('rate_value') or 0
                if rate:
                    op['custo_total_fx'] = valor_brl * rate
                    op['fx_currency_code'] = fx_info.get('target_currency')
                else:
                    op['custo_total_fx'] = None
                    op['fx_currency_code'] = None
            else:
                op['custo_total_fx'] = None
                op['fx_currency_code'] = None
        
        # Buscar clientes para filtro
        clientes = db.fetch_all("SELECT id, name FROM customers WHERE active = TRUE ORDER BY name")
        
        return render_template('industria/ordem_producao_lista.html',
                             ops=ops,
                             clientes=clientes,
                             status_filtro=status_filtro,
                             cliente_filtro=cliente_filtro)
    except Exception as e:
        flash(f'Erro ao carregar ordens de produção: {str(e)}', 'danger')
        return render_template('industria/ordem_producao_lista.html', ops=[], clientes=[])


@ordem_producao_bp.route('/planejamento', methods=['GET', 'POST'])
@industria_ops_visualizar_required
def planejamento_producao_semana():
    """Tela de planejamento de produção por período (simulação de consumo).

    O usuário informa quantidades planejadas para produtos finais e o sistema
    calcula o consumo total estimado de:
      - Itens da ficha técnica (incluindo MASSA/RECHEIO e embalagens)
      - Matérias-primas (agrupadas por produto)

    Não cria OPs, apenas retorna os cálculos em tela.
    """
    db = get_db()

    # Filtros básicos (apenas referência visual por enquanto)
    data_inicio = (request.args.get('data_inicio') or '').strip()
    data_fim = (request.args.get('data_fim') or '').strip()

    # Buscar apenas PACOTES de PRODUTOS FINAIS que possuem template ativo
    # Cada linha representará um pacote comercial específico (unidade de planejamento)
    try:
        produtos = db.fetch_all(
            """
            SELECT
                pp.id AS id,                 -- identificador do pacote (usado no formulário)
                pp.produto_id,               -- produto final ao qual o pacote pertence
                p.internal_code AS codigo,
                p.name AS nome,
                p.unit_measure AS unidade,
                p.category AS grupo_nome,
                COALESCE(p.stock_quantity, 0) AS estoque_unidades,
                COALESCE(cs.min_stock, 0) AS min_estoque_unidades,
                COALESCE(cs.max_stock, 0) AS max_estoque_unidades,
                pp.descricao AS pacote_descricao,
                pp.unidade_comercial AS pacote_unidade_comercial,
                pp.unidades_por_pacote AS pacote_unidades_por_pacote,
                pp.padrao_planejamento
            FROM produto_pacotes pp
            INNER JOIN products p
                    ON p.id = pp.produto_id
            LEFT JOIN current_stock cs
                   ON cs.product_id = p.id
                  AND cs.location_id = 1
            INNER JOIN produto_templates_producao t
                    ON t.produto_id = p.id
                   AND t.ativo = 1
            WHERE pp.ativo = 1
              AND (p.category IS NULL OR p.category <> 'Semiacabado (Massa/Recheio/Caldo)')
              AND p.name NOT LIKE 'MASSA - %%'
              AND p.name NOT LIKE 'RECHEIO - %%'
            ORDER BY p.name, pp.descricao
            """
        ) or []
    except Exception:
        # Fallback defensivo: caso tabela de pacotes não exista, volta para visão por produto
        produtos = db.fetch_all(
            """
            SELECT DISTINCT
                p.id AS id,
                p.id AS produto_id,
                p.internal_code AS codigo,
                p.name AS nome,
                p.unit_measure AS unidade,
                p.category AS grupo_nome,
                COALESCE(p.stock_quantity, 0) AS estoque_unidades,
                COALESCE(cs.min_stock, 0) AS min_estoque_unidades,
                COALESCE(cs.max_stock, 0) AS max_estoque_unidades,
                NULL AS pacote_descricao,
                NULL AS pacote_unidade_comercial,
                1 AS pacote_unidades_por_pacote,
                0 AS padrao_planejamento
            FROM products p
            LEFT JOIN current_stock cs
                   ON cs.product_id = p.id
                  AND cs.location_id = 1
            INNER JOIN produto_templates_producao t ON t.produto_id = p.id AND t.ativo = 1
            WHERE (p.category IS NULL OR p.category <> 'Semiacabado (Massa/Recheio/Caldo)')
              AND p.name NOT LIKE 'MASSA - %%'
              AND p.name NOT LIKE 'RECHEIO - %%'
            ORDER BY p.name
            """
        ) or []

    # Estoque atual em PACOTES (calculado a partir do estoque em unidades do produto)
    estoque_pacotes = {}
    min_pacotes = {}
    max_pacotes = {}
    for prod in produtos:
        try:
            estoque_un = float(prod.get('estoque_unidades') or 0.0)
        except (TypeError, ValueError):
            estoque_un = 0.0
        try:
            unidades_por_pacote = float(prod.get('pacote_unidades_por_pacote') or 1.0) or 1.0
        except (TypeError, ValueError):
            unidades_por_pacote = 1.0
        if unidades_por_pacote <= 0:
            unidades_por_pacote = 1.0

        # Estoque atual em pacotes
        estoque_pk = estoque_un / unidades_por_pacote if unidades_por_pacote > 0 else 0.0
        prod['estoque_pacotes'] = estoque_pk
        estoque_pacotes[prod['id']] = estoque_pk

        # Estoque mínimo / máximo convertidos para pacotes
        try:
            min_un = float(prod.get('min_estoque_unidades') or 0.0)
        except (TypeError, ValueError):
            min_un = 0.0
        try:
            max_un = float(prod.get('max_estoque_unidades') or 0.0)
        except (TypeError, ValueError):
            max_un = 0.0

        min_pk = min_un / unidades_por_pacote if unidades_por_pacote > 0 else 0.0
        max_pk = max_un / unidades_por_pacote if unidades_por_pacote > 0 else 0.0

        prod['min_pacotes'] = min_pk
        prod['max_pacotes'] = max_pk
        min_pacotes[prod['id']] = min_pk
        max_pacotes[prod['id']] = max_pk

    # Previsão de vendas semanais por PACOTE
    # 1) Tenta ler da tabela fixa produto_pacotes_previsao (valores já em pacotes/semana)
    # 2) Para os pacotes sem previsão fixa (ou se a tabela não existir), usa fallback
    #    calculando a média das últimas 4 semanas em estoque_movimentacoes
    previsao_pacotes = {}
    if produtos:
        # 1) Previsão fixa por pacote
        pacote_ids = sorted({p.get('id') for p in produtos if p.get('id') is not None})
        if pacote_ids:
            try:
                ids_tuple = tuple(pacote_ids)
                placeholders_ids = ','.join(['%s'] * len(ids_tuple))
                rows_prev = db.fetch_all(
                    f"""
                    SELECT
                        pacote_id,
                        previsao_semanal_pacotes
                    FROM produto_pacotes_previsao
                    WHERE pacote_id IN ({placeholders_ids})
                    """,
                    ids_tuple,
                ) or []
                for r in rows_prev:
                    pid = r.get('pacote_id')
                    try:
                        prev_pk = float(r.get('previsao_semanal_pacotes') or 0.0)
                    except (TypeError, ValueError):
                        prev_pk = 0.0
                    if pid is not None:
                        previsao_pacotes[pid] = prev_pk
            except Exception as e:
                # Se a tabela não existir ou der erro, apenas loga e segue para o fallback
                print(f"[PLANEJAMENTO] Aviso ao ler produto_pacotes_previsao: {e}")

        # 2) Fallback: calcular previsão a partir de vendas para os pacotes ainda sem previsão
        pacotes_sem_prev = [p for p in produtos if p.get('id') not in previsao_pacotes]
        if pacotes_sem_prev:
            produto_ids = sorted({p.get('produto_id') or p.get('id') for p in pacotes_sem_prev})
            vendas = []
            try:
                ids_tuple = tuple(produto_ids)
                placeholders_ids = ','.join(['%s'] * len(ids_tuple))
                vendas = db.fetch_all(
                    f"""
                    SELECT
                        em.produto_id,
                        COALESCE(SUM(em.quantidade), 0) AS qtd_total
                    FROM estoque_movimentacoes em
                    WHERE em.tipo = 'venda'
                      AND em.produto_id IN ({placeholders_ids})
                      AND em.created_at >= DATE_SUB(CURDATE(), INTERVAL 28 DAY)
                    GROUP BY em.produto_id
                    """,
                    ids_tuple,
                ) or []
            except Exception as e:
                # Em caso de erro, apenas loga e segue com previsão zero
                print(f"[PLANEJAMENTO] Aviso ao calcular previsão semanal (fallback vendas): {e}")
                vendas = []

            previsao_unidades = {}
            num_semanas_base = 4.0  # média das últimas 4 semanas
            for v in vendas:
                pid = v.get('produto_id')
                try:
                    qtd_total = float(v.get('qtd_total') or 0.0)
                except (TypeError, ValueError):
                    qtd_total = 0.0
                if pid is not None and num_semanas_base > 0:
                    previsao_unidades[pid] = qtd_total / num_semanas_base

            # Converter previsão em unidades -> pacotes para os pacotes SEM previsão fixa
            for prod in pacotes_sem_prev:
                produto_id = prod.get('produto_id') or prod.get('id')
                try:
                    unidades_por_pacote = float(prod.get('pacote_unidades_por_pacote') or 1.0) or 1.0
                except (TypeError, ValueError):
                    unidades_por_pacote = 1.0
                if unidades_por_pacote <= 0:
                    unidades_por_pacote = 1.0
                prev_un = float(previsao_unidades.get(produto_id, 0.0) or 0.0)
                prev_pk = prev_un / unidades_por_pacote if unidades_por_pacote > 0 else 0.0
                previsao_pacotes[prod['id']] = prev_pk

        # Garantir que todos os produtos tenham o campo previsao_pacotes preenchido
        for prod in produtos:
            pacote_id = prod.get('id')
            prod['previsao_pacotes'] = float(previsao_pacotes.get(pacote_id, 0.0) or 0.0)

    # Sugestão de produção em pacotes
    # Regras acordadas:
    #   1) Se houver faixa min/max configurada, calcular uma quantidade que, APÓS as vendas
    #      previstas, mantenha o estoque no início da faixa VERDE (entre min e max, mais
    #      próximo do máximo) – nunca deixando o saldo zerar ou encostar no mínimo.
    #   2) Se não houver faixa min/max, usar a regra simples: sugestão = previsão - estoque
    #      (mínimo 0).
    sugestao_pacotes = {}
    for prod in produtos:
        pacote_id = prod.get('id')
        prev_pk = float(previsao_pacotes.get(pacote_id, 0.0) or 0.0)
        estoque_pk = float(estoque_pacotes.get(pacote_id, 0.0) or 0.0)
        min_pk = float(min_pacotes.get(pacote_id, 0.0) or 0.0)
        max_pk = float(max_pacotes.get(pacote_id, 0.0) or 0.0)

        if max_pk > min_pk:
            # Faixa configurada -> queremos que o saldo APÓS vendas fique no início da faixa verde
            faixa = max_pk - min_pk
            alvo_verde = min_pk + (2.0 / 3.0) * faixa

            # Produção mínima para:
            #   - Cobrir a previsão de vendas; e
            #   - Manter um saldo alvo_verde após vender a previsão.
            #   saldo_final = estoque_pk + sugestao - prev_pk >= alvo_verde
            #   => sugestao >= alvo_verde + prev_pk - estoque_pk
            sug = alvo_verde + prev_pk - estoque_pk
        else:
            # Sem faixa configurada, aplica-se apenas a previsão vs estoque (não zera estoque
            # se já houver mais do que a previsão)
            sug = prev_pk - estoque_pk

        if sug < 0:
            sug = 0.0

        sugestao_pacotes[pacote_id] = sug
        prod['sugestao_pacotes'] = sug

    # Classificação de urgência por faixa de estoque (min/max) em pacotes
    #  - estoque <= 33% do intervalo -> danger
    #  - entre 33% e 66% -> warning
    #  - acima de 66% -> success
    for prod in produtos:
        pacote_id = prod.get('id')
        estoque_pk = float(estoque_pacotes.get(pacote_id, 0.0) or 0.0)
        min_pk = float(min_pacotes.get(pacote_id, 0.0) or 0.0)
        max_pk = float(max_pacotes.get(pacote_id, 0.0) or 0.0)
        sug = float(sugestao_pacotes.get(pacote_id, 0.0) or 0.0)

        classe = 'success'
        if max_pk > min_pk:
            faixa = max_pk - min_pk
            nivel = (estoque_pk - min_pk) / faixa
            if nivel < (1.0 / 3.0):
                classe = 'danger'
            elif nivel < (2.0 / 3.0):
                classe = 'warning'
            else:
                classe = 'success'
        else:
            # Se não houver range configurado, usar sugestão como fallback
            if sug > 0:
                classe = 'warning'
            else:
                classe = 'success'

        prod['classe_urgencia'] = classe

    # Ordenar produtos pela sugestão de produção (maior urgência primeiro)
    produtos.sort(key=lambda p: float(p.get('sugestao_pacotes') or 0.0), reverse=True)

    resultados = None

    if request.method == 'POST':
        # Manter datas preenchidas após o POST
        data_inicio = (request.form.get('data_inicio') or data_inicio).strip()
        data_fim = (request.form.get('data_fim') or data_fim).strip()

        # Quantidades planejadas por PACOTE (campo nome: qtd_<pacote_id>)
        # Regra: se o usuário NÃO informar nada para o pacote, usar automaticamente
        # a sugestão calculada para aquele item. Assim, ao clicar em "Calcular
        # planejamento" sem editar os campos, o sistema usa 100% das sugestões.
        quantidades_planejadas = {}
        for prod in produtos:
            pacote_id = prod['id']
            key = f"qtd_{pacote_id}"
            raw = (request.form.get(key) or '').strip()

            if raw:
                try:
                    q = float(raw.replace(',', '.'))
                except ValueError:
                    q = 0.0
                # Se o usuário digitou explicitamente, respeitamos o valor digitado
                if q > 0:
                    quantidades_planejadas[pacote_id] = q
            else:
                # Campo em branco -> usar sugestão padrão da linha, se houver
                try:
                    q_sug = float(sugestao_pacotes.get(pacote_id, 0.0) or 0.0)
                except (TypeError, ValueError):
                    q_sug = 0.0
                if q_sug > 0:
                    quantidades_planejadas[pacote_id] = q_sug

        # Mapa de unidades por PACOTE (por pacote_id)
        unidades_por_pacote_map = {}
        for prod in produtos:
            try:
                unidades_por_pacote = float(prod.get('pacote_unidades_por_pacote') or 1)
            except (TypeError, ValueError):
                unidades_por_pacote = 1.0
            unidades_por_pacote_map[prod['id']] = unidades_por_pacote

        # Converter planejamento em pacotes -> unidades por PRODUTO FINAL
        quantidades_planejadas_unidades = {}
        for prod in produtos:
            pacote_id = prod.get('id')
            produto_id = prod.get('produto_id') or prod.get('id')
            qtd_pacotes = quantidades_planejadas.get(pacote_id, 0.0)
            if qtd_pacotes <= 0:
                continue
            unidades_por_pacote = unidades_por_pacote_map.get(pacote_id, 1.0)
            qtd_unidades = qtd_pacotes * unidades_por_pacote
            quantidades_planejadas_unidades[produto_id] = (
                quantidades_planejadas_unidades.get(produto_id, 0.0) + qtd_unidades
            )

        if quantidades_planejadas_unidades:
            # Carregar itens de template por PRODUTO FINAL para evitar N consultas
            ids_tuple = tuple(quantidades_planejadas_unidades.keys())
            placeholders = ','.join(['%s'] * len(ids_tuple))

            itens = db.fetch_all(
                f"""
                SELECT
                    p.id              AS produto_final_id,
                    p.name            AS produto_final_nome,
                    ti.tipo_item,
                    ti.quantidade,
                    ti.unidade_medida,
                    ip.id             AS item_produto_id,
                    ip.name           AS item_produto_nome,
                    ip.category       AS item_categoria,
                    ti.descricao
                FROM produto_templates_producao t
                INNER JOIN products p       ON p.id = t.produto_id
                INNER JOIN produto_template_itens ti ON ti.template_id = t.id
                INNER JOIN products ip      ON ip.id = ti.produto_id
                WHERE t.ativo = 1
                  AND t.versao = 1
                  AND p.id IN ({placeholders})
                """,
                ids_tuple,
            ) or []

            # Agregadores
            consumo_ft = []             # todos os itens (para debug futuro)
            consumo_massa = []          # itens MASSA
            consumo_recheio = []        # itens RECHEIO
            consumo_embalagem = []      # itens de empacotamento / consumo interno
            consumo_outros = []         # demais seções não classificadas
            mp_detalhado = []           # matérias-primas detalhadas por produto (nível 1)
            mp_totais = {}              # matérias-primas agrupadas (explodidas, geral)
            mp_massa_totais = {}        # MP usadas em MASSAS (explodidas)
            mp_recheio_totais = {}      # MP usadas em RECHEIOS (explodidas)
            mp_embalagem_totais = {}    # MP usadas em EMBALAGENS (explodidas)
            embalagem_totais_map = {}   # totais por item de embalagem

            template_cache = {}
            produto_cache = {}

            def _explodir_materia_prima(produto_id, qtd_unidades, acc_dict, visitados=None):
                if not produto_id or qtd_unidades <= 0:
                    return
                if visitados is None:
                    visitados = set()
                if produto_id in visitados:
                    return
                visitados.add(produto_id)

                template_id = template_cache.get(produto_id)
                if template_id is None:
                    tpl = db.fetch_one(
                        """
                        SELECT id
                        FROM produto_templates_producao
                        WHERE produto_id = %s AND ativo = 1
                        ORDER BY versao DESC
                        LIMIT 1
                        """,
                        (produto_id,),
                    )
                    template_id = tpl['id'] if tpl else 0
                    template_cache[produto_id] = template_id

                if template_id:
                    itens_tpl = db.fetch_all(
                        """
                        SELECT produto_id, quantidade
                        FROM produto_template_itens
                        WHERE template_id = %s
                        """,
                        (template_id,),
                    ) or []
                    for it_tpl in itens_tpl:
                        filho_id = it_tpl.get('produto_id')
                        if not filho_id:
                            continue
                        try:
                            qtd_por_un_filho = float(it_tpl.get('quantidade') or 0)
                        except (TypeError, ValueError):
                            qtd_por_un_filho = 0.0
                        if qtd_por_un_filho <= 0:
                            continue
                        qtd_total_filho = qtd_por_un_filho * qtd_unidades
                        _explodir_materia_prima(filho_id, qtd_total_filho, acc_dict, visitados)
                else:
                    prod_info = produto_cache.get(produto_id)
                    if prod_info is None:
                        prod_info = db.fetch_one(
                            "SELECT id, name, unit_measure FROM products WHERE id = %s",
                            (produto_id,),
                        )
                        produto_cache[produto_id] = prod_info
                    if not prod_info:
                        visitados.remove(produto_id)
                        return
                    key = prod_info['id']
                    mp = acc_dict.get(key) or {
                        'produto_id': prod_info['id'],
                        'nome': prod_info['name'],
                        'unidade': prod_info.get('unit_measure'),
                        'qtd_total': 0.0,
                    }
                    mp['qtd_total'] += qtd_unidades
                    acc_dict[key] = mp

                visitados.remove(produto_id)

            for it in itens:
                prod_final_id = it['produto_final_id']
                qtd_planejada_unidades = quantidades_planejadas_unidades.get(prod_final_id, 0)
                if qtd_planejada_unidades <= 0:
                    continue

                qtd_por_un = float(it.get('quantidade') or 0)
                if qtd_por_un <= 0:
                    continue

                qtd_total = qtd_por_un * qtd_planejada_unidades

                # Identificar seção (MASSA / RECHEIO / EMBALAGEM / MP / OUTROS)
                descricao = (it.get('descricao') or '').strip()
                item_nome = (it.get('item_produto_nome') or '').strip()
                tipo_item = (it.get('tipo_item') or '').strip().lower()
                item_categoria = (it.get('item_categoria') or '').strip().upper()

                texto_nome_desc = f"{descricao} {item_nome}".upper()
                texto_cat_nome = f"{item_categoria} {item_nome}".upper()

                secao = 'OUTROS'
                # MASSA / RECHEIO priorizando o nome/descrição do item
                if 'RECHEIO' in texto_nome_desc:
                    secao = 'RECHEIO'
                elif 'MASSA' in texto_nome_desc:
                    secao = 'MASSA'
                # EMBALAGENS / EMPACOTAMENTO / rótulos
                elif any(k in texto_cat_nome for k in ('EMBALAGEM', 'EMBALAG', 'EMPACOTAMENTO', 'ETIQUETA', 'RÓTULO', 'ROTULO')):
                    secao = 'EMBALAGEM'
                # Matérias-primas em geral (quando não são claramente massa/recheio)
                elif tipo_item == 'materia_prima' or any(
                    k in texto_cat_nome for k in ('MATERIA-PRIMA', 'MATÉRIA-PRIMA', 'MP ')
                ):
                    secao = 'MP'
                else:
                    # Fallback: usar prefixo da descrição, se existir
                    if descricao and '-' in descricao:
                        prefix = descricao.split('-', 1)[0].strip().upper()
                        if prefix in ('MASSA', 'RECHEIO'):
                            secao = prefix
                        elif prefix in ('EMPACOTAMENTO', 'EMBALAGEM'):
                            secao = 'EMBALAGEM'

                row = {
                    'produto_final_nome': it['produto_final_nome'],
                    'tipo_item': it['tipo_item'],
                    'item_nome': it['item_produto_nome'],
                    'descricao': descricao,
                    'unidade': it.get('unidade_medida'),
                    'qtd_por_unidade': qtd_por_un,
                    'qtd_planejada': qtd_planejada_unidades,
                    'qtd_total': qtd_total,
                    'secao': secao,
                }

                consumo_ft.append(row)

                if secao == 'MASSA':
                    consumo_massa.append(row)
                elif secao == 'RECHEIO':
                    consumo_recheio.append(row)
                elif secao == 'EMBALAGEM':
                    consumo_embalagem.append(row)

                    # Totais por item de embalagem (independente do produto final)
                    key_emb = (row['item_nome'], row.get('unidade'))
                    emb = embalagem_totais_map.get(key_emb) or {
                        'item_nome': row['item_nome'],
                        'unidade': row.get('unidade'),
                        'qtd_total': 0.0,
                    }
                    emb['qtd_total'] += qtd_total
                    embalagem_totais_map[key_emb] = emb
                else:
                    consumo_outros.append(row)

                # Matéria-prima:
                # - itens marcados como tipo_item = 'materia_prima'
                # - e também itens classificados na seção EMBALAGEM (mesmo que sejam consumo_interno)
                is_mp_tipo = (it['tipo_item'] == 'materia_prima')
                is_mp_embalagem = (secao == 'EMBALAGEM')

                if is_mp_tipo:
                    mp_detalhado.append(row)

                    key_mp = it['item_produto_id']
                    if not key_mp:
                        continue

                    template_id = template_cache.get(key_mp)
                    if template_id is None:
                        tpl = db.fetch_one(
                            """
                            SELECT id
                            FROM produto_templates_producao
                            WHERE produto_id = %s AND ativo = 1
                            ORDER BY versao DESC
                            LIMIT 1
                            """,
                            (key_mp,),
                        )
                        template_id = tpl['id'] if tpl else 0
                        template_cache[key_mp] = template_id

                    # Se o item tem template próprio, tratamos como semiacabado
                    # e explodimos até chegar nas MPs reais
                    if template_id:
                        if secao == 'MASSA':
                            _explodir_materia_prima(key_mp, qtd_total, mp_massa_totais)
                            _explodir_materia_prima(key_mp, qtd_total, mp_totais)
                        elif secao == 'RECHEIO':
                            _explodir_materia_prima(key_mp, qtd_total, mp_recheio_totais)
                            _explodir_materia_prima(key_mp, qtd_total, mp_totais)
                        elif secao == 'EMBALAGEM':
                            _explodir_materia_prima(key_mp, qtd_total, mp_embalagem_totais)
                            _explodir_materia_prima(key_mp, qtd_total, mp_totais)
                        else:
                            _explodir_materia_prima(key_mp, qtd_total, mp_totais)
                    else:
                        # Sem template próprio: trata como MP folha
                        mp = mp_totais.get(key_mp) or {
                            'produto_id': it['item_produto_id'],
                            'nome': it['item_produto_nome'],
                            'unidade': it.get('unidade_medida'),
                            'qtd_total': 0.0,
                        }
                        mp['qtd_total'] += qtd_total
                        mp_totais[key_mp] = mp

                        if secao == 'MASSA':
                            mp_m = mp_massa_totais.get(key_mp) or {
                                'produto_id': it['item_produto_id'],
                                'nome': it['item_produto_nome'],
                                'unidade': it.get('unidade_medida'),
                                'qtd_total': 0.0,
                            }
                            mp_m['qtd_total'] += qtd_total
                            mp_massa_totais[key_mp] = mp_m

                        if secao == 'RECHEIO':
                            mp_r = mp_recheio_totais.get(key_mp) or {
                                'produto_id': it['item_produto_id'],
                                'nome': it['item_produto_nome'],
                                'unidade': it.get('unidade_medida'),
                                'qtd_total': 0.0,
                            }
                            mp_r['qtd_total'] += qtd_total
                            mp_recheio_totais[key_mp] = mp_r

                        if secao == 'EMBALAGEM':
                            mp_e = mp_embalagem_totais.get(key_mp) or {
                                'produto_id': it['item_produto_id'],
                                'nome': it['item_produto_nome'],
                                'unidade': it.get('unidade_medida'),
                                'qtd_total': 0.0,
                            }
                            mp_e['qtd_total'] += qtd_total
                            mp_embalagem_totais[key_mp] = mp_e

                elif is_mp_embalagem:
                    # Itens de EMBALAGEM que não são marcados como materia_prima
                    # (geralmente consumo_interno) também devem ser tratados como MP
                    key_mp = it['item_produto_id']
                    if not key_mp:
                        continue

                    mp = mp_totais.get(key_mp) or {
                        'produto_id': it['item_produto_id'],
                        'nome': it['item_produto_nome'],
                        'unidade': it.get('unidade_medida'),
                        'qtd_total': 0.0,
                    }
                    mp['qtd_total'] += qtd_total
                    mp_totais[key_mp] = mp

                    mp_e = mp_embalagem_totais.get(key_mp) or {
                        'produto_id': it['item_produto_id'],
                        'nome': it['item_produto_nome'],
                        'unidade': it.get('unidade_medida'),
                        'qtd_total': 0.0,
                    }
                    mp_e['qtd_total'] += qtd_total
                    mp_embalagem_totais[key_mp] = mp_e

            # Completar dados de estoque para todas as matérias-primas agregadas
            mp_ids = set(mp_totais.keys())
            mp_estoque_map = {}
            if mp_ids:
                try:
                    ids_tuple = tuple(mp_ids)
                    placeholders_ids = ','.join(['%s'] * len(ids_tuple))
                    rows_mp_stock = db.fetch_all(
                        f"""
                        SELECT
                            p.id,
                            COALESCE(cs.quantity, p.stock_quantity, 0) AS estoque_atual
                        FROM products p
                        LEFT JOIN current_stock cs
                               ON cs.product_id = p.id
                              AND cs.location_id = 1
                        WHERE p.id IN ({placeholders_ids})
                        """,
                        ids_tuple,
                    ) or []
                except Exception as e:
                    print(f"[PLANEJAMENTO] Aviso ao buscar estoque de MP: {e}")
                    rows_mp_stock = []

                for r in rows_mp_stock:
                    try:
                        estoque = float(r.get('estoque_atual') or 0.0)
                    except (TypeError, ValueError):
                        estoque = 0.0
                    mp_estoque_map[r['id']] = estoque

                # Se todos os estoques de MP vierem zerados, simular valores
                # apenas para esta tela de planejamento (não grava no banco).
                if mp_estoque_map and all((v or 0.0) <= 0.0 for v in mp_estoque_map.values()):
                    for pid in mp_ids:
                        mp_info = mp_totais.get(pid)
                        if not mp_info:
                            continue
                        try:
                            qtd_total_mp = float(mp_info.get('qtd_total') or 0.0)
                        except (TypeError, ValueError):
                            qtd_total_mp = 0.0
                        if qtd_total_mp <= 0:
                            estoque_simulado = 0.0
                        else:
                            fator = random.uniform(0.0, 1.5)
                            estoque_simulado = qtd_total_mp * fator
                        mp_estoque_map[pid] = estoque_simulado

                def _aplicar_estoque_mp(mp_map):
                    for v in mp_map.values():
                        pid = v.get('produto_id')
                        try:
                            qtd_total_mp = float(v.get('qtd_total') or 0.0)
                        except (TypeError, ValueError):
                            qtd_total_mp = 0.0
                        estoque_atual_mp = float(mp_estoque_map.get(pid, 0.0))
                        v['estoque_atual'] = estoque_atual_mp
                        v['saldo_estoque'] = estoque_atual_mp - qtd_total_mp
                        v['tem_saldo_suficiente'] = estoque_atual_mp >= qtd_total_mp

                _aplicar_estoque_mp(mp_totais)
                _aplicar_estoque_mp(mp_massa_totais)
                _aplicar_estoque_mp(mp_recheio_totais)
                _aplicar_estoque_mp(mp_embalagem_totais)

            # Agregados específicos de MASSA / RECHEIO
            # - Total de massa/recheio por produto final (soma de ingredientes)
            # - Total de cada ingrediente por tipo de massa/recheio
            massa_totais_map = {}
            massa_ingredientes_map = {}
            for row in consumo_massa:
                # Considerar apenas matérias-primas na agregação
                if row.get('tipo_item') != 'materia_prima':
                    continue

                prod_nome = row['produto_final_nome']
                qtd_total = float(row.get('qtd_total') or 0)

                # Total de massa por produto
                mt = massa_totais_map.get(prod_nome) or {
                    'produto_final_nome': prod_nome,
                    'qtd_total': 0.0,
                }
                mt['qtd_total'] += qtd_total
                massa_totais_map[prod_nome] = mt

                # Ingredientes por tipo de massa
                key_ing = (prod_nome, row['item_nome'], row.get('unidade'))
                ing = massa_ingredientes_map.get(key_ing) or {
                    'produto_final_nome': prod_nome,
                    'item_nome': row['item_nome'],
                    'unidade': row.get('unidade'),
                    'qtd_total': 0.0,
                }
                ing['qtd_total'] += qtd_total
                massa_ingredientes_map[key_ing] = ing

            recheio_totais_map = {}
            recheio_ingredientes_map = {}
            for row in consumo_recheio:
                if row.get('tipo_item') != 'materia_prima':
                    continue

                prod_nome = row['produto_final_nome']
                qtd_total = float(row.get('qtd_total') or 0)

                rt = recheio_totais_map.get(prod_nome) or {
                    'produto_final_nome': prod_nome,
                    'qtd_total': 0.0,
                }
                rt['qtd_total'] += qtd_total
                recheio_totais_map[prod_nome] = rt

                key_ing = (prod_nome, row['item_nome'], row.get('unidade'))
                ing = recheio_ingredientes_map.get(key_ing) or {
                    'produto_final_nome': prod_nome,
                    'item_nome': row['item_nome'],
                    'unidade': row.get('unidade'),
                    'qtd_total': 0.0,
                }
                ing['qtd_total'] += qtd_total
                recheio_ingredientes_map[key_ing] = ing

            massa_totais = sorted(
                massa_totais_map.values(),
                key=lambda x: x['produto_final_nome'],
            )

            massa_ingredientes = sorted(
                massa_ingredientes_map.values(),
                key=lambda x: (x['produto_final_nome'], x['item_nome']),
            )

            recheio_totais = sorted(
                recheio_totais_map.values(),
                key=lambda x: x['produto_final_nome'],
            )

            recheio_ingredientes = sorted(
                recheio_ingredientes_map.values(),
                key=lambda x: (x['produto_final_nome'], x['item_nome']),
            )

            # Totais de MASSA/RECHEIO por tipo de ingrediente (independente do produto final)
            massa_por_tipo_map = {}
            for row in massa_ingredientes:
                key = (row['item_nome'], row.get('unidade'))
                reg = massa_por_tipo_map.get(key) or {
                    'item_nome': row['item_nome'],
                    'unidade': row.get('unidade'),
                    'qtd_total': 0.0,
                }
                reg['qtd_total'] += float(row.get('qtd_total') or 0.0)
                massa_por_tipo_map[key] = reg

            recheio_por_tipo_map = {}
            for row in recheio_ingredientes:
                key = (row['item_nome'], row.get('unidade'))
                reg = recheio_por_tipo_map.get(key) or {
                    'item_nome': row['item_nome'],
                    'unidade': row.get('unidade'),
                    'qtd_total': 0.0,
                }
                reg['qtd_total'] += float(row.get('qtd_total') or 0.0)
                recheio_por_tipo_map[key] = reg

            massa_por_tipo = sorted(
                massa_por_tipo_map.values(),
                key=lambda x: x['item_nome'],
            )

            recheio_por_tipo = sorted(
                recheio_por_tipo_map.values(),
                key=lambda x: x['item_nome'],
            )

            # Ordenar resultados detalhados para exibição em cada seção
            def _sort_key(x):
                return (
                    x['produto_final_nome'],
                    x['tipo_item'],
                    x['item_nome'],
                )

            consumo_massa.sort(key=_sort_key)
            consumo_recheio.sort(key=_sort_key)
            consumo_embalagem.sort(key=_sort_key)
            consumo_outros.sort(key=_sort_key)
            mp_detalhado.sort(key=_sort_key)

            embalagem_totais = sorted(
                embalagem_totais_map.values(),
                key=lambda x: x['item_nome'],
            )

            mp_ordenadas = sorted(
                mp_totais.values(),
                key=lambda x: x['nome'],
            )

            mp_massa_ordenadas = sorted(
                mp_massa_totais.values(),
                key=lambda x: x['nome'],
            )

            mp_recheio_ordenadas = sorted(
                mp_recheio_totais.values(),
                key=lambda x: x['nome'],
            )

            mp_embalagem_ordenadas = sorted(
                mp_embalagem_totais.values(),
                key=lambda x: x['nome'],
            )

            resultados = {
                'consumo_massa': consumo_massa,
                'consumo_recheio': consumo_recheio,
                'consumo_embalagem': consumo_embalagem,
                'consumo_outros': consumo_outros,
                'massa_totais': massa_totais,
                'massa_ingredientes': massa_ingredientes,
                'massa_por_tipo': massa_por_tipo,
                'recheio_totais': recheio_totais,
                'recheio_ingredientes': recheio_ingredientes,
                'recheio_por_tipo': recheio_por_tipo,
                'embalagem_totais': embalagem_totais,
                'mp_detalhado': mp_detalhado,
                'mp_totais': mp_ordenadas,
                'mp_massa_totais': mp_massa_ordenadas,
                'mp_recheio_totais': mp_recheio_ordenadas,
                'mp_embalagem_totais': mp_embalagem_ordenadas,
                # quantidade de pacotes digitada pelo usuário
                'quantidades_planejadas': quantidades_planejadas,
                # quantidade equivalente em unidades de produto final (para consumo de ficha técnica)
                'quantidades_planejadas_unidades': quantidades_planejadas_unidades,
            }

    return render_template(
        'industria/planejamento_producao_semana_v2.html',
        produtos=produtos,
        data_inicio=data_inicio,
        data_fim=data_fim,
        resultados=resultados,
        estoque_pacotes=estoque_pacotes,
        previsao_pacotes=previsao_pacotes,
        sugestao_pacotes=sugestao_pacotes,
        min_pacotes=min_pacotes,
        max_pacotes=max_pacotes,
    )


@ordem_producao_bp.route('/planejamento/gerar-ops', methods=['POST'])
@industria_ops_criar_required
def gerar_ops_planejamento():
    """Gera OPs automaticamente a partir do planejamento semanal confirmado.

    Fluxo:
    1. Cria registro em planejamentos_semanais
    2. Salva itens planejados em planejamento_semanal_itens
    3. Identifica semiacabados (MASSA / RECHEIO) necessários
    4. Cria OPs separadas:
       - 1 OP por tipo de MASSA (agrupando todos os produtos que usam aquela massa)
       - 1 OP por tipo de RECHEIO (idem)
       - 1 OP de MONTAGEM por produto final (vinculada à linha de produção)
    5. Cria fases (op_fases_producao) distribuídas na semana
    6. Redireciona para a tela de cronograma semanal
    """
    db = get_db()

    try:
        # ── 1. Ler dados do formulário ──
        data_inicio = (request.form.get('data_inicio') or '').strip()
        data_fim = (request.form.get('data_fim') or '').strip()

        if not data_inicio or not data_fim:
            flash('Informe as datas de início e fim do planejamento.', 'warning')
            return redirect(url_for('ordem_producao.planejamento_producao_semana'))

        try:
            dt_inicio = datetime.strptime(data_inicio, '%Y-%m-%d').date()
            dt_fim = datetime.strptime(data_fim, '%Y-%m-%d').date()
        except ValueError:
            flash('Datas inválidas.', 'danger')
            return redirect(url_for('ordem_producao.planejamento_producao_semana'))

        semana_iso = dt_inicio.isocalendar()[1]
        ano = dt_inicio.year

        # Verificar se já existe planejamento para esta semana
        existente = db.fetch_one(
            "SELECT id, codigo FROM planejamentos_semanais WHERE ano = %s AND semana_ano = %s AND status != 'cancelado'",
            (ano, semana_iso)
        )
        if existente:
            flash(f'Já existe planejamento para esta semana: {existente["codigo"]}. Cancele-o primeiro se quiser refazer.', 'warning')
            return redirect(url_for('ordem_producao.planejamento_producao_semana'))

        # ── 2. Buscar produtos planejados (mesma lógica do GET) ──
        produtos = db.fetch_all("""
            SELECT
                pp.id AS id, pp.produto_id, p.name AS nome,
                pp.unidades_por_pacote AS pacote_unidades_por_pacote
            FROM produto_pacotes pp
            INNER JOIN products p ON p.id = pp.produto_id
            INNER JOIN produto_templates_producao t ON t.produto_id = p.id AND t.ativo = 1
            WHERE pp.ativo = 1
              AND (p.category IS NULL OR p.category <> 'Semiacabado (Massa/Recheio/Caldo)')
              AND p.name NOT LIKE 'MASSA - %%'
              AND p.name NOT LIKE 'RECHEIO - %%'
            ORDER BY p.name
        """) or []

        if not produtos:
            flash('Nenhum produto encontrado para gerar OPs.', 'warning')
            return redirect(url_for('ordem_producao.planejamento_producao_semana'))

        # Ler filtro de urgência (danger/warning/ok/all)
        filtro_urgencia = (request.form.get('filtro_urgencia') or 'all').strip()
        filtro_map = {'danger': 'danger', 'warning': 'warning', 'ok': 'ok'}

        # Ler quantidades e urgências do formulário
        quantidades = {}  # pacote_id -> qtd_pacotes
        urgencias = {}    # pacote_id -> classe_urgencia (danger/warning/ok)
        for prod in produtos:
            pid = prod['id']
            urg = (request.form.get(f'urg_{pid}') or 'ok').strip()
            urgencias[pid] = urg

            # Filtrar: se há filtro ativo, pular produtos que não correspondem
            if filtro_urgencia != 'all' and urg != filtro_urgencia:
                continue

            raw = (request.form.get(f'qtd_{pid}') or '').strip()
            if raw:
                try:
                    q = float(raw.replace(',', '.'))
                except ValueError:
                    q = 0.0
                if q > 0:
                    quantidades[pid] = q

        if not quantidades:
            flash('Nenhuma quantidade informada. Preencha ao menos um item.', 'warning')
            return redirect(url_for('ordem_producao.planejamento_producao_semana'))

        # ── 3. Criar planejamento semanal ──
        codigo = f"PL-{ano}-S{semana_iso:02d}"
        planejamento_id = db.insert("""
            INSERT INTO planejamentos_semanais
                (codigo, semana_ano, ano, data_inicio, data_fim, status, created_by, confirmado_por, confirmado_em)
            VALUES (%s, %s, %s, %s, %s, 'confirmado', %s, %s, NOW())
        """, (codigo, semana_iso, ano, data_inicio, data_fim,
              session.get('user_id'), session.get('user_id')))

        # ── 4. Salvar itens e converter pacotes -> unidades ──
        quantidades_unidades = {}  # produto_id -> qtd_unidades
        produto_map = {}  # produto_id -> product info

        for prod in produtos:
            pid = prod['id']
            qtd_pk = quantidades.get(pid, 0.0)
            if qtd_pk <= 0:
                continue

            produto_id = prod['produto_id']
            try:
                un_por_pk = float(prod.get('pacote_unidades_por_pacote') or 1) or 1.0
            except (TypeError, ValueError):
                un_por_pk = 1.0
            qtd_un = qtd_pk * un_por_pk

            # Buscar linha de produção para este produto
            linha = db.fetch_one(
                "SELECT linha_id FROM linha_producao_produtos WHERE produto_id = %s LIMIT 1",
                (produto_id,)
            )
            linha_id = linha['linha_id'] if linha else None

            db.insert("""
                INSERT INTO planejamento_semanal_itens
                    (planejamento_id, pacote_id, produto_id, qtd_pacotes, qtd_unidades, linha_producao_id)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (planejamento_id, pid, produto_id, qtd_pk, qtd_un, linha_id))

            quantidades_unidades[produto_id] = quantidades_unidades.get(produto_id, 0.0) + qtd_un
            # Mapear urgência: danger->urgente, warning->atencao, ok->normal
            urg_classe = urgencias.get(pid, 'ok')
            prioridade_op = 'urgente' if urg_classe == 'danger' else ('atencao' if urg_classe == 'warning' else 'normal')
            if produto_id not in produto_map:
                produto_map[produto_id] = {
                    'nome': prod['nome'],
                    'linha_id': linha_id,
                    'prioridade': prioridade_op,
                }

        # ── 5. Identificar semiacabados (MASSA / RECHEIO) necessários ──
        # Para cada produto final planejado, buscar itens do template
        ids_tuple = tuple(quantidades_unidades.keys())
        placeholders = ','.join(['%s'] * len(ids_tuple))

        itens_template = db.fetch_all(f"""
            SELECT
                t.produto_id AS produto_final_id,
                ti.produto_id AS item_id,
                ti.quantidade AS qtd_por_unidade,
                ti.descricao,
                ip.name AS item_nome,
                ip.category AS item_categoria
            FROM produto_templates_producao t
            INNER JOIN produto_template_itens ti ON ti.template_id = t.id
            INNER JOIN products ip ON ip.id = ti.produto_id
            WHERE t.ativo = 1 AND t.produto_id IN ({placeholders})
        """, ids_tuple) or []

        # Agrupar semiacabados por tipo
        massa_necessaria = {}   # item_id -> {nome, qtd_total, prioridade}
        recheio_necessario = {}  # item_id -> {nome, qtd_total, prioridade}

        # Mapa de prioridade: urgente > atencao > normal
        _prio_rank = {'urgente': 3, 'atencao': 2, 'normal': 1}
        def _maior_prio(a, b):
            return a if _prio_rank.get(a, 0) >= _prio_rank.get(b, 0) else b

        for it in itens_template:
            prod_final_id = it['produto_final_id']
            qtd_planejada = quantidades_unidades.get(prod_final_id, 0)
            if qtd_planejada <= 0:
                continue

            qtd_por_un = float(it.get('qtd_por_unidade') or 0)
            if qtd_por_un <= 0:
                continue

            qtd_total = qtd_por_un * qtd_planejada
            item_id = it['item_id']
            item_nome = (it.get('item_nome') or '').upper()
            descricao = (it.get('descricao') or '').upper()
            texto = f"{item_nome} {descricao}"

            # Herdar prioridade do produto final que demanda este semiacabado
            prio_prod = produto_map.get(prod_final_id, {}).get('prioridade', 'normal')

            if 'MASSA' in texto or item_nome.startswith('MASSA'):
                m = massa_necessaria.get(item_id) or {'id': item_id, 'nome': it['item_nome'], 'qtd_total': 0.0, 'prioridade': 'normal'}
                m['qtd_total'] += qtd_total
                m['prioridade'] = _maior_prio(m['prioridade'], prio_prod)
                massa_necessaria[item_id] = m
            elif 'RECHEIO' in texto or item_nome.startswith('RECHEIO'):
                r = recheio_necessario.get(item_id) or {'id': item_id, 'nome': it['item_nome'], 'qtd_total': 0.0, 'prioridade': 'normal'}
                r['qtd_total'] += qtd_total
                r['prioridade'] = _maior_prio(r['prioridade'], prio_prod)
                recheio_necessario[item_id] = r

        # ── 6. Buscar empresa padrão ──
        empresa = db.fetch_one("SELECT id FROM empresas WHERE ativo = 1 ORDER BY id LIMIT 1")
        empresa_id = empresa['id'] if empresa else 1

        # ── 7. Preparar dias da semana e buscar etapas do sistema existente ──
        ops_criadas = []
        dias_semana = []
        d = dt_inicio
        while d <= dt_fim:
            if d.weekday() < 6:  # Seg a Sáb
                dias_semana.append(d)
            d += timedelta(days=1)

        # Buscar etapas iniciais por nome (criadas no script 070)
        # Reutiliza o sistema existente de producao_etapas + op_lotes + Kanban
        def _buscar_etapa(nome):
            et = db.fetch_one(
                "SELECT id FROM producao_etapas WHERE nome = %s AND ativo = 1 LIMIT 1",
                (nome,)
            )
            return et['id'] if et else None

        etapa_preparar_massa = _buscar_etapa('Preparar Massa')
        etapa_preparar_recheio = _buscar_etapa('Preparar Recheio')
        etapa_montagem = _buscar_etapa('Montagem / Modelagem')
        # Fallback: primeira etapa ativa
        if not etapa_preparar_massa or not etapa_preparar_recheio or not etapa_montagem:
            fallback = db.fetch_one(
                "SELECT id FROM producao_etapas WHERE ativo = 1 ORDER BY ordem, id LIMIT 1"
            )
            fallback_id = fallback['id'] if fallback else None
            etapa_preparar_massa = etapa_preparar_massa or fallback_id
            etapa_preparar_recheio = etapa_preparar_recheio or fallback_id
            etapa_montagem = etapa_montagem or fallback_id

        def _criar_op_com_lote(produto_id, quantidade, tipo_op, etapa_id,
                               linha_id=None, tpl_id=None, prioridade='normal'):
            """Cria OP + lote inicial (reutiliza sistema existente de op_lotes/etapas)."""
            op_id = db.insert("""
                INSERT INTO ordens_producao
                    (empresa_id, produto_id, quantidade, tipo_op, status,
                     data_solicitacao, data_prevista, planejamento_id,
                     linha_producao_id, etapa_atual_id,
                     template_usado_id, usou_template, prioridade, created_by)
                VALUES (%s, %s, %s, %s, 'pendente', %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                empresa_id, produto_id, quantidade, tipo_op,
                data_inicio, data_fim, planejamento_id,
                linha_id, etapa_id,
                tpl_id, 1 if tpl_id else 0,
                prioridade,
                session.get('user_id')
            ))

            # Aplicar template se existir
            if tpl_id:
                try:
                    _aplicar_template_em_op(db, op_id, tpl_id)
                except Exception:
                    pass

            # Criar lote inicial (100%) — integra com Kanban/operador/líder existente
            try:
                db.insert(
                    "INSERT INTO op_lotes (ordem_producao_id, sequencia, quantidade, etapa_atual_id, align_side, status) VALUES (%s, 1, %s, %s, 'full', 'pendente')",
                    (op_id, quantidade, etapa_id)
                )
            except Exception:
                pass

            return op_id

        # ── 8. Gerar OPs de MASSA ──
        for item_id, massa in massa_necessaria.items():
            tpl = db.fetch_one(
                "SELECT id FROM produto_templates_producao WHERE produto_id = %s AND ativo = 1 LIMIT 1",
                (item_id,)
            )

            op_id = _criar_op_com_lote(
                produto_id=item_id,
                quantidade=massa['qtd_total'],
                tipo_op='massa',
                etapa_id=etapa_preparar_massa,
                tpl_id=tpl['id'] if tpl else None,
                prioridade=massa.get('prioridade', 'normal'),
            )

            # Vincular ao planejamento
            db.insert("""
                INSERT INTO planejamento_semanal_ops
                    (planejamento_id, ordem_producao_id, tipo_op_planejamento, produto_semiacabado_id)
                VALUES (%s, %s, 'massa', %s)
            """, (planejamento_id, op_id, item_id))

            # Cronograma sugerido (op_fases_producao): Preparação (dia 1) + Cozimento (dia 1) + Resfriamento (dia 2)
            dia_prep = dias_semana[0] if dias_semana else dt_inicio
            dia_resf = dias_semana[1] if len(dias_semana) > 1 else dia_prep

            db.insert("""
                INSERT INTO op_fases_producao
                    (ordem_producao_id, fase_nome, fase_tipo, sequencia, dia_semana, quantidade, status)
                VALUES (%s, %s, 'preparacao', 1, %s, %s, 'pendente')
            """, (op_id, f"Preparar {massa['nome']}", dia_prep, massa['qtd_total']))

            fase_coz_id = db.insert("""
                INSERT INTO op_fases_producao
                    (ordem_producao_id, fase_nome, fase_tipo, sequencia, dia_semana, quantidade, status)
                VALUES (%s, %s, 'cozimento', 2, %s, %s, 'pendente')
            """, (op_id, f"Cozinhar {massa['nome']}", dia_prep, massa['qtd_total']))

            db.insert("""
                INSERT INTO op_fases_producao
                    (ordem_producao_id, fase_nome, fase_tipo, sequencia, dia_semana, quantidade, status, dependencia_fase_id)
                VALUES (%s, %s, 'resfriamento', 3, %s, %s, 'pendente', %s)
            """, (op_id, f"Resfriar {massa['nome']}", dia_resf, massa['qtd_total'], fase_coz_id))

            ops_criadas.append({'op_id': op_id, 'tipo': 'massa', 'produto': massa['nome']})

        # ── 9. Gerar OPs de RECHEIO ──
        for item_id, recheio in recheio_necessario.items():
            tpl = db.fetch_one(
                "SELECT id FROM produto_templates_producao WHERE produto_id = %s AND ativo = 1 LIMIT 1",
                (item_id,)
            )

            op_id = _criar_op_com_lote(
                produto_id=item_id,
                quantidade=recheio['qtd_total'],
                tipo_op='recheio',
                etapa_id=etapa_preparar_recheio,
                tpl_id=tpl['id'] if tpl else None,
                prioridade=recheio.get('prioridade', 'normal'),
            )

            db.insert("""
                INSERT INTO planejamento_semanal_ops
                    (planejamento_id, ordem_producao_id, tipo_op_planejamento, produto_semiacabado_id)
                VALUES (%s, %s, 'recheio', %s)
            """, (planejamento_id, op_id, item_id))

            # Cronograma sugerido: Preparação (dia 1) + Cozimento (dia 1)
            dia_rech = dias_semana[0] if dias_semana else dt_inicio

            db.insert("""
                INSERT INTO op_fases_producao
                    (ordem_producao_id, fase_nome, fase_tipo, sequencia, dia_semana, quantidade, status)
                VALUES (%s, %s, 'preparacao', 1, %s, %s, 'pendente')
            """, (op_id, f"Preparar {recheio['nome']}", dia_rech, recheio['qtd_total']))

            db.insert("""
                INSERT INTO op_fases_producao
                    (ordem_producao_id, fase_nome, fase_tipo, sequencia, dia_semana, quantidade, status)
                VALUES (%s, %s, 'cozimento', 2, %s, %s, 'pendente')
            """, (op_id, f"Cozinhar {recheio['nome']}", dia_rech, recheio['qtd_total']))

            ops_criadas.append({'op_id': op_id, 'tipo': 'recheio', 'produto': recheio['nome']})

        # ── 10. Gerar OPs de MONTAGEM por produto final ──
        for produto_id, qtd_un in quantidades_unidades.items():
            info = produto_map.get(produto_id, {})
            linha_id = info.get('linha_id')

            tpl = db.fetch_one(
                "SELECT id FROM produto_templates_producao WHERE produto_id = %s AND ativo = 1 LIMIT 1",
                (produto_id,)
            )

            op_id = _criar_op_com_lote(
                produto_id=produto_id,
                quantidade=qtd_un,
                tipo_op='montagem',
                etapa_id=etapa_montagem,
                linha_id=linha_id,
                tpl_id=tpl['id'] if tpl else None,
                prioridade=info.get('prioridade', 'normal'),
            )

            db.insert("""
                INSERT INTO planejamento_semanal_ops
                    (planejamento_id, ordem_producao_id, tipo_op_planejamento, linha_producao_id)
                VALUES (%s, %s, 'montagem', %s)
            """, (planejamento_id, op_id, linha_id))

            # Cronograma sugerido: Montagem (dia 3) + Empacotamento (dia 4)
            dia_mont = dias_semana[2] if len(dias_semana) > 2 else (dias_semana[-1] if dias_semana else dt_inicio)
            dia_emb = dias_semana[3] if len(dias_semana) > 3 else dia_mont

            fase_mont_id = db.insert("""
                INSERT INTO op_fases_producao
                    (ordem_producao_id, fase_nome, fase_tipo, sequencia, dia_semana,
                     quantidade, status, linha_producao_id)
                VALUES (%s, %s, 'montagem', 1, %s, %s, 'pendente', %s)
            """, (op_id, f"Montar {info.get('nome', '')}", dia_mont, qtd_un, linha_id))

            db.insert("""
                INSERT INTO op_fases_producao
                    (ordem_producao_id, fase_nome, fase_tipo, sequencia, dia_semana,
                     quantidade, status, linha_producao_id, dependencia_fase_id)
                VALUES (%s, %s, 'empacotamento', 2, %s, %s, 'pendente', %s, %s)
            """, (op_id, f"Empacotar {info.get('nome', '')}", dia_emb, qtd_un, linha_id, fase_mont_id))

            ops_criadas.append({'op_id': op_id, 'tipo': 'montagem', 'produto': info.get('nome', '')})

        # ── 10. Atualizar status do planejamento ──
        db.execute_query(
            "UPDATE planejamentos_semanais SET status = 'em_producao' WHERE id = %s",
            (planejamento_id,)
        )

        n_massa = sum(1 for o in ops_criadas if o['tipo'] == 'massa')
        n_recheio = sum(1 for o in ops_criadas if o['tipo'] == 'recheio')
        n_montagem = sum(1 for o in ops_criadas if o['tipo'] == 'montagem')

        flash(
            f'Planejamento {codigo} confirmado! '
            f'{len(ops_criadas)} OPs geradas: '
            f'{n_massa} de massa, {n_recheio} de recheio, {n_montagem} de montagem.',
            'success'
        )

        return redirect(url_for('ordem_producao.visualizar_planejamento', id=planejamento_id))

    except Exception as e:
        flash(f'Erro ao gerar OPs: {str(e)}', 'danger')
        import traceback
        traceback.print_exc()
        return redirect(url_for('ordem_producao.planejamento_producao_semana'))


@ordem_producao_bp.route('/planejamentos')
@industria_ops_visualizar_required
def listar_planejamentos():
    """Lista todos os planejamentos semanais com status e ações."""
    db = get_db()
    try:
        planejamentos = db.fetch_all("""
            SELECT ps.*, u.name AS criado_por_nome,
                   (SELECT COUNT(*) FROM planejamento_semanal_ops pso WHERE pso.planejamento_id = ps.id) AS total_ops,
                   (SELECT COUNT(*) FROM planejamento_semanal_itens psi WHERE psi.planejamento_id = ps.id) AS total_itens
            FROM planejamentos_semanais ps
            LEFT JOIN users u ON u.id = ps.created_by
            ORDER BY ps.data_inicio DESC, ps.id DESC
        """) or []
        return render_template('industria/planejamentos_lista.html', planejamentos=planejamentos)
    except Exception as e:
        flash(f'Erro ao listar planejamentos: {str(e)}', 'danger')
        return render_template('industria/planejamentos_lista.html', planejamentos=[])


@ordem_producao_bp.route('/planejamento/<int:id>/cancelar', methods=['POST'])
@industria_ops_editar_required
def cancelar_planejamento(id):
    """Cancela um planejamento e todas as OPs pendentes vinculadas."""
    db = get_db()
    try:
        plan = db.fetch_one("SELECT id, codigo, status FROM planejamentos_semanais WHERE id = %s", (id,))
        if not plan:
            flash('Planejamento não encontrado.', 'warning')
            return redirect(url_for('ordem_producao.listar_planejamentos'))

        if plan['status'] == 'cancelado':
            flash('Planejamento já está cancelado.', 'info')
            return redirect(url_for('ordem_producao.listar_planejamentos'))

        # Cancelar OPs pendentes vinculadas
        ops_vinculadas = db.fetch_all("""
            SELECT pso.ordem_producao_id
            FROM planejamento_semanal_ops pso
            INNER JOIN ordens_producao op ON op.id = pso.ordem_producao_id
            WHERE pso.planejamento_id = %s AND op.status = 'pendente'
        """, (id,)) or []

        for op_row in ops_vinculadas:
            op_id = op_row['ordem_producao_id']
            db.execute_query("UPDATE ordens_producao SET status = 'cancelada' WHERE id = %s", (op_id,))
            db.execute_query("UPDATE op_lotes SET status = 'cancelado' WHERE ordem_producao_id = %s AND status = 'pendente'", (op_id,))

        # Cancelar o planejamento
        db.execute_query(
            "UPDATE planejamentos_semanais SET status = 'cancelado' WHERE id = %s", (id,)
        )

        flash(f'Planejamento {plan["codigo"]} cancelado. {len(ops_vinculadas)} OPs pendentes foram canceladas.', 'success')
        return redirect(url_for('ordem_producao.listar_planejamentos'))

    except Exception as e:
        flash(f'Erro ao cancelar planejamento: {str(e)}', 'danger')
        return redirect(url_for('ordem_producao.listar_planejamentos'))


@ordem_producao_bp.route('/planejamento/<int:id>')
@industria_ops_visualizar_required
def visualizar_planejamento(id):
    """Redireciona para a versão v2 do cronograma semanal."""
    return redirect(url_for('ordem_producao.visualizar_planejamento_v2', id=id))


@ordem_producao_bp.route('/planejamento/<int:id>/v2')
@industria_ops_visualizar_required
def visualizar_planejamento_v2(id):
    """Visualiza cronograma semanal v2 — agrupado por dia com horários sugeridos."""
    db = get_db()
    try:
        planejamento = db.fetch_one("""
            SELECT ps.*, u.name AS criado_por_nome
            FROM planejamentos_semanais ps
            LEFT JOIN users u ON u.id = ps.created_by
            WHERE ps.id = %s
        """, (id,))

        if not planejamento:
            flash('Planejamento não encontrado.', 'warning')
            return redirect(url_for('ordem_producao.listar_planejamentos'))

        itens = db.fetch_all("""
            SELECT psi.*, p.name AS produto_nome, lp.nome AS linha_nome, lp.cor_hex AS linha_cor
            FROM planejamento_semanal_itens psi
            INNER JOIN products p ON p.id = psi.produto_id
            LEFT JOIN linhas_producao lp ON lp.id = psi.linha_producao_id
            WHERE psi.planejamento_id = %s
            ORDER BY p.name
        """, (id,)) or []

        ops = db.fetch_all("""
            SELECT pso.*, op.numero_op, op.status AS op_status, op.quantidade,
                   p.name AS produto_nome, op.tipo_op,
                   lp.nome AS linha_nome, lp.cor_hex AS linha_cor
            FROM planejamento_semanal_ops pso
            INNER JOIN ordens_producao op ON op.id = pso.ordem_producao_id
            INNER JOIN products p ON p.id = op.produto_id
            LEFT JOIN linhas_producao lp ON lp.id = COALESCE(pso.linha_producao_id, op.linha_producao_id)
            WHERE pso.planejamento_id = %s
            ORDER BY pso.tipo_op_planejamento, p.name
        """, (id,)) or []

        op_ids = [o['ordem_producao_id'] for o in ops]
        fases = []
        if op_ids:
            ph = ','.join(['%s'] * len(op_ids))
            fases = db.fetch_all(f"""
                SELECT f.*, op.numero_op, p.name AS produto_nome, op.tipo_op,
                       lp.nome AS linha_nome, lp.cor_hex AS linha_cor
                FROM op_fases_producao f
                INNER JOIN ordens_producao op ON op.id = f.ordem_producao_id
                INNER JOIN products p ON p.id = op.produto_id
                LEFT JOIN linhas_producao lp ON lp.id = f.linha_producao_id
                WHERE f.ordem_producao_id IN ({ph})
                ORDER BY f.dia_semana, f.sequencia
            """, tuple(op_ids)) or []

        linhas = db.fetch_all(
            "SELECT * FROM linhas_producao WHERE ativo = 1 ORDER BY ordem"
        ) or []

        # Dias da semana
        dias = []
        d = planejamento['data_inicio']
        while d <= planejamento['data_fim']:
            if d.weekday() < 6:
                dias.append(d)
            d += timedelta(days=1)

        # ── Auto-sugestão de horários ──
        # Jornada: 08:00 às 17:00 com pausa 12:00-13:00 = 8h úteis = 480 min
        JORNADA_INICIO = 8 * 60   # 08:00 em minutos
        PAUSA_INICIO = 12 * 60    # 12:00
        PAUSA_FIM = 13 * 60       # 13:00
        JORNADA_FIM = 17 * 60     # 17:00
        DURACAO_MIN_FASE = 30     # mínimo 30 min por fase

        # Agrupar fases por dia
        fases_por_dia = {}
        fases_sem_dia = []
        for f in fases:
            dia_key = f.get('dia_semana')
            if dia_key:
                fases_por_dia.setdefault(dia_key, []).append(f)
            else:
                fases_sem_dia.append(f)

        # Distribuir fases sem dia uniformemente entre os dias disponíveis
        if fases_sem_dia and dias:
            for i, f in enumerate(fases_sem_dia):
                dia_destino = dias[i % len(dias)]
                f['dia_semana'] = dia_destino
                f['_sugerido'] = True
                fases_por_dia.setdefault(dia_destino, []).append(f)

        # Para cada dia, sugerir horários se não definidos
        fases_sugeridas = []
        for dia in dias:
            dia_fases = fases_por_dia.get(dia, [])
            if not dia_fases:
                continue

            # Contar quantas fases precisam de horário
            total_fases = len(dia_fases)
            if total_fases == 0:
                continue

            # Calcular tempo disponível (em minutos)
            tempo_total = (PAUSA_INICIO - JORNADA_INICIO) + (JORNADA_FIM - PAUSA_FIM)  # 480 min
            duracao_por_fase = max(DURACAO_MIN_FASE, tempo_total // total_fases)

            cursor_min = JORNADA_INICIO  # começa 08:00
            for f in dia_fases:
                hi = f.get('hora_inicio')
                hf = f.get('hora_fim')

                # Se já tem horário definido, usar e avançar cursor
                if hi and hf:
                    try:
                        td_hi = hi
                        td_hf = hf
                        if hasattr(hi, 'total_seconds'):
                            hi_min = int(hi.total_seconds()) // 60
                            hf_min = int(hf.total_seconds()) // 60
                        else:
                            parts = str(hi).split(':')
                            hi_min = int(parts[0]) * 60 + int(parts[1])
                            parts = str(hf).split(':')
                            hf_min = int(parts[0]) * 60 + int(parts[1])
                        f['_hi_min'] = hi_min
                        f['_hf_min'] = hf_min
                        f['_hi_str'] = f"{hi_min // 60:02d}:{hi_min % 60:02d}"
                        f['_hf_str'] = f"{hf_min // 60:02d}:{hf_min % 60:02d}"
                        f['_sugerido'] = False
                        cursor_min = max(cursor_min, hf_min)
                        fases_sugeridas.append(f)
                        continue
                    except Exception:
                        pass

                # Pular pausa de almoço
                if cursor_min >= PAUSA_INICIO and cursor_min < PAUSA_FIM:
                    cursor_min = PAUSA_FIM

                fim_min = min(cursor_min + duracao_por_fase, JORNADA_FIM)
                # Se cruzar almoço, dividir
                if cursor_min < PAUSA_INICIO and fim_min > PAUSA_INICIO:
                    fim_min = PAUSA_INICIO

                f['_hi_min'] = cursor_min
                f['_hf_min'] = fim_min
                f['_hi_str'] = f"{cursor_min // 60:02d}:{cursor_min % 60:02d}"
                f['_hf_str'] = f"{fim_min // 60:02d}:{fim_min % 60:02d}"
                f['_sugerido'] = True
                fases_sugeridas.append(f)

                cursor_min = fim_min

        # Ordenar fases sugeridas por dia + hora início
        fases_sugeridas.sort(key=lambda x: (x.get('dia_semana') or '', x.get('_hi_min', 0)))

        # Reagrupar por dia para o template
        cronograma = {}
        for dia in dias:
            cronograma[dia] = [f for f in fases_sugeridas if f.get('dia_semana') == dia]

        # ── Calcular sobreposições horizontais (column packing) ──
        for dia in dias:
            dia_fases = cronograma.get(dia, [])
            if not dia_fases:
                continue

            # Ordenar por hora início, depois por hora fim
            dia_fases.sort(key=lambda x: (x.get('_hi_min', 0), x.get('_hf_min', 0)))

            # Atribuir colunas usando algoritmo greedy
            # columns[i] = fim da última fase na coluna i
            columns = []
            for f in dia_fases:
                hi = f.get('_hi_min', 0)
                hf = f.get('_hf_min', 0)
                placed = False
                for ci, col_end in enumerate(columns):
                    if hi >= col_end:  # não sobrepõe
                        f['_col_index'] = ci
                        columns[ci] = hf
                        placed = True
                        break
                if not placed:
                    f['_col_index'] = len(columns)
                    columns.append(hf)

            total_cols = len(columns) if columns else 1

            # Para cada fase, calcular quantas colunas realmente se sobrepõem
            # com ela (para dar a largura correta)
            for f in dia_fases:
                hi = f.get('_hi_min', 0)
                hf = f.get('_hf_min', 0)
                # Contar fases que se sobrepõem com esta
                overlapping_cols = set()
                for f2 in dia_fases:
                    hi2 = f2.get('_hi_min', 0)
                    hf2 = f2.get('_hf_min', 0)
                    if hi < hf2 and hf > hi2:  # se sobrepõem
                        overlapping_cols.add(f2.get('_col_index', 0))
                f['_col_total'] = max(len(overlapping_cols), 1)

        return render_template(
            'industria/planejamento_semanal_view_v2.html',
            planejamento=planejamento,
            itens=itens,
            ops=ops,
            fases=fases,
            fases_sugeridas=fases_sugeridas,
            cronograma=cronograma,
            linhas=linhas,
            dias=dias,
        )

    except Exception as e:
        flash(f'Erro ao carregar planejamento: {str(e)}', 'danger')
        import traceback
        traceback.print_exc()
        return redirect(url_for('ordem_producao.listar_planejamentos'))


@ordem_producao_bp.route('/planejamento/fase/<int:fase_id>/atualizar', methods=['POST'])
@industria_ops_editar_required
def atualizar_fase(fase_id):
    """Atualiza dia, horário ou status de uma fase de produção (AJAX)."""
    db = get_db()

    try:
        data = request.get_json() or request.form
        updates = []
        params = []

        if 'dia_semana' in data and data['dia_semana']:
            updates.append("dia_semana = %s")
            params.append(data['dia_semana'])
        if 'hora_inicio' in data and data['hora_inicio']:
            updates.append("hora_inicio = %s")
            params.append(data['hora_inicio'])
        if 'hora_fim' in data and data['hora_fim']:
            updates.append("hora_fim = %s")
            params.append(data['hora_fim'])
        if 'status' in data and data['status']:
            updates.append("status = %s")
            params.append(data['status'])
        if 'quantidade' in data:
            updates.append("quantidade = %s")
            params.append(data['quantidade'])
        if 'quantidade_realizada' in data:
            updates.append("quantidade_realizada = %s")
            params.append(data['quantidade_realizada'])

        if not updates:
            return jsonify({'erro': 'Nenhum campo para atualizar'}), 400

        params.append(fase_id)
        db.execute_query(
            f"UPDATE op_fases_producao SET {', '.join(updates)} WHERE id = %s",
            tuple(params)
        )

        return jsonify({'ok': True})

    except Exception as e:
        return jsonify({'erro': str(e)}), 500


@ordem_producao_bp.route('/planejamento/fase/<int:fase_id>/dividir', methods=['POST'])
@industria_ops_editar_required
def dividir_fase(fase_id):
    """Divide/move quantidade de uma fase. Se já existe fase irmã no destino, soma."""
    db = get_db()
    try:
        data = request.get_json() or {}
        qtd_mover = float(data.get('quantidade', 0))
        novo_dia = data.get('dia_semana', '')
        nova_hora_inicio = data.get('hora_inicio', '')
        nova_hora_fim = data.get('hora_fim', '')

        if qtd_mover <= 0 or not novo_dia:
            return jsonify({'erro': 'Quantidade e dia são obrigatórios'}), 400

        fase = db.fetch_one("SELECT * FROM op_fases_producao WHERE id = %s", (fase_id,))
        if not fase:
            return jsonify({'erro': 'Fase não encontrada'}), 404

        qtd_atual = float(fase.get('quantidade') or 0)
        qtd_restante = qtd_atual - qtd_mover
        if qtd_restante < 0:
            qtd_restante = 0
            qtd_mover = qtd_atual

        # Verificar se já existe fase irmã no dia destino (mesma OP + mesmo fase_nome, diferente desta)
        irma = db.fetch_one("""
            SELECT id, quantidade FROM op_fases_producao
            WHERE ordem_producao_id = %s AND fase_nome = %s AND dia_semana = %s AND id != %s
            LIMIT 1
        """, (fase['ordem_producao_id'], fase['fase_nome'], novo_dia, fase_id))

        if irma:
            # ── MERGE: somar quantidade na fase irmã existente ──
            nova_qtd_irma = float(irma.get('quantidade') or 0) + qtd_mover
            db.execute_query(
                "UPDATE op_fases_producao SET quantidade = %s WHERE id = %s",
                (nova_qtd_irma, irma['id'])
            )

            if qtd_restante <= 0:
                # Fase original ficou vazia → remover
                db.execute_query("DELETE FROM op_fases_producao WHERE id = %s", (fase_id,))
                return jsonify({'ok': True, 'modo': 'merged_removido',
                                'fase_removida': fase_id, 'fase_destino': irma['id'],
                                'qtd_destino': nova_qtd_irma})
            else:
                # Reduzir fase original
                db.execute_query(
                    "UPDATE op_fases_producao SET quantidade = %s WHERE id = %s",
                    (qtd_restante, fase_id)
                )
                return jsonify({'ok': True, 'modo': 'merged',
                                'fase_original_id': fase_id, 'fase_destino': irma['id'],
                                'qtd_restante': qtd_restante, 'qtd_destino': nova_qtd_irma})
        else:
            # ── Não existe irmã → criar nova ou mover ──
            if qtd_restante <= 0:
                # Mover tudo — apenas atualiza o dia
                updates = ["dia_semana = %s"]
                params = [novo_dia]
                if nova_hora_inicio:
                    updates.append("hora_inicio = %s")
                    params.append(nova_hora_inicio)
                if nova_hora_fim:
                    updates.append("hora_fim = %s")
                    params.append(nova_hora_fim)
                params.append(fase_id)
                db.execute_query(f"UPDATE op_fases_producao SET {', '.join(updates)} WHERE id = %s", tuple(params))
                return jsonify({'ok': True, 'modo': 'movido', 'fase_id': fase_id})

            # Reduzir quantidade da fase original
            db.execute_query(
                "UPDATE op_fases_producao SET quantidade = %s WHERE id = %s",
                (qtd_restante, fase_id)
            )

            # Criar nova fase no dia destino
            nova_id = db.insert("""
                INSERT INTO op_fases_producao
                    (ordem_producao_id, fase_nome, fase_tipo, sequencia, dia_semana,
                     hora_inicio, hora_fim, quantidade, status, linha_producao_id, observacoes)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'pendente', %s, %s)
            """, (
                fase['ordem_producao_id'], fase['fase_nome'], fase['fase_tipo'],
                fase['sequencia'], novo_dia,
                nova_hora_inicio or None, nova_hora_fim or None,
                qtd_mover, fase.get('linha_producao_id'),
                f"Dividido da fase #{fase_id}"
            ))

            return jsonify({'ok': True, 'modo': 'dividido', 'fase_original_id': fase_id,
                            'nova_fase_id': nova_id, 'qtd_restante': qtd_restante, 'qtd_movida': qtd_mover})

    except Exception as e:
        return jsonify({'erro': str(e)}), 500


@ordem_producao_bp.route('/planejamento/<int:id>/redistribuir', methods=['POST'])
@industria_ops_editar_required
def redistribuir_fases(id):
    """Redistribui todas as fases do planejamento uniformemente entre seg-sex, agrupando por tipo."""
    db = get_db()
    try:
        planejamento = db.fetch_one("SELECT * FROM planejamentos_semanais WHERE id = %s", (id,))
        if not planejamento:
            return jsonify({'erro': 'Planejamento não encontrado'}), 404

        # Dias úteis do planejamento
        dias = []
        d = planejamento['data_inicio']
        while d <= planejamento['data_fim']:
            if d.weekday() < 5:  # seg-sex
                dias.append(d)
            d += timedelta(days=1)

        if not dias:
            return jsonify({'erro': 'Nenhum dia útil no período'}), 400

        # Buscar OPs do planejamento
        ops = db.fetch_all(
            "SELECT ordem_producao_id FROM planejamento_semanal_ops WHERE planejamento_id = %s", (id,))
        op_ids = [o['ordem_producao_id'] for o in ops] if ops else []
        if not op_ids:
            return jsonify({'erro': 'Nenhuma OP encontrada'}), 400

        ph = ','.join(['%s'] * len(op_ids))
        fases = db.fetch_all(f"""
            SELECT f.id, f.fase_tipo, f.ordem_producao_id, op.tipo_op
            FROM op_fases_producao f
            INNER JOIN ordens_producao op ON op.id = f.ordem_producao_id
            WHERE f.ordem_producao_id IN ({ph})
            ORDER BY op.tipo_op, f.fase_tipo, f.id
        """, tuple(op_ids)) or []

        if not fases:
            return jsonify({'erro': 'Nenhuma fase encontrada'}), 400

        # Agrupar por tipo de processo para distribuir de forma lógica:
        # massa (preparacao, cozimento, resfriamento) → primeiros dias
        # recheio (preparacao, cozimento) → primeiros dias
        # montagem → dias do meio/fim
        # empacotamento → dias do fim
        grupos = {'massa': [], 'recheio': [], 'montagem': [], 'empacotamento': []}
        for f in fases:
            ft = f.get('fase_tipo', '')
            to = f.get('tipo_op', '')
            if ft == 'empacotamento':
                grupos['empacotamento'].append(f)
            elif ft == 'montagem':
                grupos['montagem'].append(f)
            elif to == 'recheio':
                grupos['recheio'].append(f)
            else:
                grupos['massa'].append(f)

        # Distribuir cada grupo uniformemente entre os dias
        num_dias = len(dias)
        updates = []
        for grupo_nome, grupo_fases in grupos.items():
            if not grupo_fases:
                continue
            for i, f in enumerate(grupo_fases):
                dia_idx = i % num_dias
                updates.append((dias[dia_idx], f['id']))

        # Executar updates: resetar dia e limpar horários para auto-sugestão
        for dia, fase_id in updates:
            db.execute_query(
                "UPDATE op_fases_producao SET dia_semana = %s, hora_inicio = NULL, hora_fim = NULL WHERE id = %s",
                (dia, fase_id)
            )

        return jsonify({'ok': True, 'total_fases': len(fases), 'dias': len(dias)})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'erro': str(e)}), 500


@ordem_producao_bp.route('/lotes/<int:lote_id>/consumo', methods=['GET'])
@login_required
def listar_consumo_lote(lote_id):
    """Lista os insumos já registrados para um lote (AJAX)."""
    db = get_db()
    try:
        consumos = db.fetch_all("""
            SELECT c.*, p.name AS insumo_nome, u.name AS operador_nome
            FROM lote_consumo_insumos c
            INNER JOIN products p ON p.id = c.insumo_produto_id
            INNER JOIN users u ON u.id = c.operador_id
            WHERE c.lote_id = %s
            ORDER BY c.registrado_em DESC
        """, (lote_id,)) or []

        # Serializar decimais e datetimes
        for c in consumos:
            for k, v in c.items():
                if isinstance(v, Decimal):
                    c[k] = float(v)
                elif hasattr(v, 'isoformat'):
                    c[k] = v.isoformat()

        return jsonify(consumos)
    except Exception as e:
        return jsonify({'erro': str(e)}), 500


@ordem_producao_bp.route('/lotes/<int:lote_id>/consumo/registrar', methods=['POST'])
@login_required
def registrar_consumo_insumo(lote_id):
    """Operador registra retirada de insumo durante produção de um lote.

    Fluxo: operador pega 1 caixa de hambúrguer (100un) → registra aqui.
    Ao finalizar o lote, compara total retirado vs produzido → perda.
    """
    db = get_db()

    try:
        data = request.get_json() or request.form

        insumo_produto_id = data.get('insumo_produto_id')
        quantidade_retirada = data.get('quantidade_retirada')
        unidade_medida = (data.get('unidade_medida') or '').strip() or 'UN'
        unidades_por_embalagem = data.get('unidades_por_embalagem', 1)
        motivo = data.get('motivo', 'producao')
        observacao = (data.get('observacao') or '').strip() or None

        if not insumo_produto_id or not quantidade_retirada:
            return jsonify({'erro': 'Insumo e quantidade são obrigatórios'}), 400

        # Validar lote existe
        lote = db.fetch_one(
            "SELECT id, ordem_producao_id, operador_id FROM op_lotes WHERE id = %s",
            (lote_id,)
        )
        if not lote:
            return jsonify({'erro': 'Lote não encontrado'}), 404

        try:
            qtd = float(str(quantidade_retirada).replace(',', '.'))
            un_emb = float(str(unidades_por_embalagem).replace(',', '.')) if unidades_por_embalagem else 1.0
        except (ValueError, TypeError):
            return jsonify({'erro': 'Quantidade inválida'}), 400

        if qtd <= 0:
            return jsonify({'erro': 'Quantidade deve ser maior que zero'}), 400

        consumo_id = db.insert("""
            INSERT INTO lote_consumo_insumos
                (lote_id, ordem_producao_id, insumo_produto_id,
                 quantidade_retirada, unidade_medida, unidades_por_embalagem,
                 motivo, observacao, operador_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            lote_id, lote['ordem_producao_id'], insumo_produto_id,
            qtd, unidade_medida, un_emb,
            motivo, observacao,
            session.get('user_id')
        ))

        # Buscar total acumulado
        total = db.fetch_one("""
            SELECT COALESCE(SUM(total_unidades), 0) AS total
            FROM lote_consumo_insumos
            WHERE lote_id = %s
        """, (lote_id,))

        return jsonify({
            'ok': True,
            'consumo_id': consumo_id,
            'total_unidades_acumulado': float(total['total']) if total else 0
        })

    except Exception as e:
        return jsonify({'erro': str(e)}), 500


@ordem_producao_bp.route('/lotes/<int:lote_id>/consumo/<int:consumo_id>/excluir', methods=['POST'])
@login_required
def excluir_consumo_insumo(lote_id, consumo_id):
    """Remove um registro de consumo de insumo (correção)."""
    db = get_db()
    try:
        db.execute_query(
            "DELETE FROM lote_consumo_insumos WHERE id = %s AND lote_id = %s",
            (consumo_id, lote_id)
        )
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'erro': str(e)}), 500


@ordem_producao_bp.route('/lotes/<int:lote_id>/conferencia', methods=['POST'])
@login_required
def conferir_lote(lote_id):
    """Conferência final do lote: compara insumos retirados vs quantidade produzida.

    Se não bater → registra perda. Líder pode avaliar operador.
    Fluxo:
    1. Soma total_unidades de lote_consumo_insumos para este lote
    2. Recebe total_produzido do formulário
    3. Calcula perda = retirado - produzido
    4. Calcula percentual_perda
    5. Compara com tolerância → perda_aceitavel
    6. Salva em lote_consumo_conferencia
    """
    db = get_db()

    try:
        data = request.get_json() or request.form

        total_produzido_raw = data.get('total_produzido')
        avaliacao_lider = data.get('avaliacao_lider')  # aprovado/atencao/reprovado
        observacao_lider = (data.get('observacao_lider') or '').strip() or None
        tolerancia = float(data.get('tolerancia_percentual', 2.0))

        if total_produzido_raw is None:
            return jsonify({'erro': 'Informe a quantidade produzida'}), 400

        try:
            total_produzido = float(str(total_produzido_raw).replace(',', '.'))
        except (ValueError, TypeError):
            return jsonify({'erro': 'Quantidade produzida inválida'}), 400

        # Validar lote
        lote = db.fetch_one(
            "SELECT id, ordem_producao_id, operador_id FROM op_lotes WHERE id = %s",
            (lote_id,)
        )
        if not lote:
            return jsonify({'erro': 'Lote não encontrado'}), 404

        # Verificar se já tem conferência
        existente = db.fetch_one(
            "SELECT id FROM lote_consumo_conferencia WHERE lote_id = %s",
            (lote_id,)
        )
        if existente:
            return jsonify({'erro': 'Este lote já foi conferido'}), 400

        # Somar insumos retirados
        soma = db.fetch_one("""
            SELECT COALESCE(SUM(total_unidades), 0) AS total
            FROM lote_consumo_insumos
            WHERE lote_id = %s
        """, (lote_id,))
        total_retirado = float(soma['total']) if soma else 0.0

        # Calcular perda
        total_perda = max(0, total_retirado - total_produzido)
        percentual_perda = (total_perda / total_retirado * 100) if total_retirado > 0 else 0.0
        perda_aceitavel = 1 if percentual_perda <= tolerancia else 0

        conferencia_id = db.insert("""
            INSERT INTO lote_consumo_conferencia
                (lote_id, ordem_producao_id,
                 total_insumos_retirados, total_produzido, total_perda,
                 percentual_perda, perda_aceitavel, tolerancia_percentual,
                 avaliacao_lider, observacao_lider,
                 operador_id, conferido_por, conferido_em)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """, (
            lote_id, lote['ordem_producao_id'],
            total_retirado, total_produzido, total_perda,
            percentual_perda, perda_aceitavel, tolerancia,
            avaliacao_lider, observacao_lider,
            lote.get('operador_id'),
            session.get('user_id')
        ))

        return jsonify({
            'ok': True,
            'conferencia_id': conferencia_id,
            'total_retirado': total_retirado,
            'total_produzido': total_produzido,
            'total_perda': total_perda,
            'percentual_perda': round(percentual_perda, 2),
            'perda_aceitavel': bool(perda_aceitavel),
        })

    except Exception as e:
        return jsonify({'erro': str(e)}), 500


@ordem_producao_bp.route('/lotes/<int:lote_id>/conferencia', methods=['GET'])
@login_required
def ver_conferencia_lote(lote_id):
    """Retorna dados da conferência de um lote (AJAX)."""
    db = get_db()
    try:
        conf = db.fetch_one("""
            SELECT c.*, u_op.name AS operador_nome, u_conf.name AS conferente_nome
            FROM lote_consumo_conferencia c
            LEFT JOIN users u_op ON u_op.id = c.operador_id
            LEFT JOIN users u_conf ON u_conf.id = c.conferido_por
            WHERE c.lote_id = %s
        """, (lote_id,))

        if not conf:
            return jsonify({'conferido': False})

        for k, v in conf.items():
            if isinstance(v, Decimal):
                conf[k] = float(v)
            elif hasattr(v, 'isoformat'):
                conf[k] = v.isoformat()

        conf['conferido'] = True
        return jsonify(conf)
    except Exception as e:
        return jsonify({'erro': str(e)}), 500


@ordem_producao_bp.route('/relatorio/perdas')
@login_required
def relatorio_perdas():
    """Relatório de perdas por operador (para o líder avaliar desempenho)."""
    db = get_db()
    try:
        periodo = request.args.get('periodo', '30')  # dias
        try:
            dias = int(periodo)
        except ValueError:
            dias = 30

        perdas = db.fetch_all("""
            SELECT
                c.operador_id,
                u.name AS operador_nome,
                COUNT(c.id) AS total_lotes,
                SUM(c.total_insumos_retirados) AS total_retirado,
                SUM(c.total_produzido) AS total_produzido,
                SUM(c.total_perda) AS total_perda,
                AVG(c.percentual_perda) AS media_perda_pct,
                SUM(CASE WHEN c.perda_aceitavel = 0 THEN 1 ELSE 0 END) AS lotes_acima_tolerancia,
                SUM(CASE WHEN c.avaliacao_lider = 'reprovado' THEN 1 ELSE 0 END) AS lotes_reprovados
            FROM lote_consumo_conferencia c
            INNER JOIN users u ON u.id = c.operador_id
            WHERE c.conferido_em >= DATE_SUB(NOW(), INTERVAL %s DAY)
            GROUP BY c.operador_id, u.name
            ORDER BY media_perda_pct DESC
        """, (dias,)) or []

        for p in perdas:
            for k, v in p.items():
                if isinstance(v, Decimal):
                    p[k] = float(v)

        if request.headers.get('Accept') == 'application/json':
            return jsonify(perdas)

        return render_template(
            'industria/relatorio_perdas.html',
            perdas=perdas,
            periodo=dias,
        )
    except Exception as e:
        flash(f'Erro ao gerar relatório: {str(e)}', 'danger')
        return redirect(url_for('ordem_producao.listar_ops'))


@ordem_producao_bp.route('/grupo/orcamento/<int:orcamento_id>')
def grupo_orcamento(orcamento_id):
    """Tela agrupadora das OPs geradas a partir de um orçamento."""
    db = get_db()

    try:
        grupo = db.fetch_one("""
            SELECT og.id, og.orcamento_id, og.empresa_id, og.cliente_id, og.criado_em,
                   o.numero AS orcamento_numero, o.status AS orcamento_status,
                   c.name AS cliente_nome,
                   e.nome_fantasia AS empresa_nome
            FROM orcamento_op_grupos og
            INNER JOIN orcamentos o ON o.id = og.orcamento_id
            INNER JOIN customers c ON c.id = og.cliente_id
            INNER JOIN empresas e ON e.id = og.empresa_id
            WHERE og.orcamento_id = %s
            LIMIT 1
        """, (orcamento_id,))

        if not grupo:
            flash('Nenhum romaneio de produção encontrado para este orçamento.', 'warning')
            return redirect(url_for('orcamentos.visualizar', id=orcamento_id))

        ops = db.fetch_all("""
            SELECT
                oi.id AS vinculo_id,
                oi.ordem_producao_id,
                oi.orcamento_item_id,
                oi.tem_template,
                op.numero_op,
                op.status,
                op.data_prevista,
                op.usou_template,
                op.tipo_op,
                op.obs_estoque,
                p.name AS produto_nome,
                oi.quantidade AS quantidade_orcamento
            FROM orcamento_op_itens oi
            INNER JOIN ordens_producao op ON op.id = oi.ordem_producao_id
            INNER JOIN products p ON p.id = oi.produto_id
            WHERE oi.orcamento_id = %s
            ORDER BY oi.id
        """, (orcamento_id,)) or []

        return render_template(
            'industria/ordem_producao_grupo.html',
            grupo=grupo,
            ops=ops
        )

    except Exception as e:
        flash(f'Erro ao carregar romaneio de produção: {str(e)}', 'danger')
        return redirect(url_for('orcamentos.visualizar', id=orcamento_id))


@ordem_producao_bp.route('/nova', methods=['GET'])
@industria_ops_criar_required
def nova_op():
    """Formulário para criar nova ordem de produção"""
    db = get_db()
    
    try:
        # Buscar empresas
        empresas = db.fetch_all("SELECT id, nome_fantasia FROM empresas WHERE ativo = TRUE ORDER BY nome_fantasia")
        
        # Buscar clientes
        clientes = db.fetch_all("SELECT id, name FROM customers WHERE active = TRUE ORDER BY name")

        return render_template('industria/ordem_producao_form.html',
                             empresas=empresas,
                             clientes=clientes,
                             produto_selecionado=None,
                             op=None)
    except Exception as e:
        flash(f'Erro ao carregar formulário: {str(e)}', 'danger')
        return redirect(url_for('ordem_producao.listar_ops'))


@ordem_producao_bp.route('/api/buscar-produtos-producao', methods=['GET'])
def api_buscar_produtos_producao():
    """API para buscar produtos finais (categoria_fiscal=produto_producao ou legado produto)."""
    db = get_db()
    termo = request.args.get('q', '')

    modo_all, parts = parse_star_search(termo)

    if not modo_all and (not parts or len(''.join(parts)) < 2):
        return jsonify([])

    try:
        where_parts = [
            "p.active = 1",
            "pc.categoria_fiscal IN ('produto_producao', 'produto')"
        ]
        params = []

        if modo_all:
            limit = 200
        else:
            clause, clause_params = build_multi_part_like_where(
                parts,
                ['p.internal_code', 'p.name', 'p.barcode']
            )
            if clause:
                where_parts.append(f"({clause})")
                params.extend(clause_params)
            limit = 50

        where_sql = " AND ".join(where_parts)

        produtos = db.fetch_all(f"""
            SELECT
                p.id,
                p.internal_code AS codigo,
                p.name AS nome,
                p.unit_measure AS unidade,
                p.cost_price AS custo
            FROM products p
            INNER JOIN product_categories pc ON p.category_id = pc.id
            WHERE {where_sql}
            ORDER BY p.name
            LIMIT {limit}
        """, params)

        return jsonify(produtos or [])
    except Exception as e:
        return jsonify({'erro': str(e)}), 500


@ordem_producao_bp.route('/lotes/<int:lote_id>/mover', methods=['POST'])
@login_required
def mover_lote(lote_id):
    """Move um lote entre etapas. Se quantidade for menor que a do lote, divide (remanescente fica na etapa anterior)."""
    db = get_db()

    try:
        def _recalcular_align_sides(ordem_producao_id):
            itens = db.fetch_all(
                """
                SELECT l.id, l.etapa_atual_id, e.ordem
                FROM op_lotes l
                INNER JOIN producao_etapas e ON e.id = l.etapa_atual_id
                WHERE l.ordem_producao_id = %s AND l.etapa_atual_id IS NOT NULL
                """,
                (ordem_producao_id,)
            ) or []

            if not itens:
                return

            ordens = [int(i.get('ordem') or 0) for i in itens]
            min_ord = min(ordens)
            max_ord = max(ordens)

            # Se tudo estiver na mesma etapa, manter full
            if min_ord == max_ord:
                for it in itens:
                    db.update(
                        "UPDATE op_lotes SET align_side = 'full', updated_at = NOW() WHERE id = %s",
                        (it.get('id'),)
                    )
                return

            for it in itens:
                o = int(it.get('ordem') or 0)
                if o == min_ord:
                    side = 'right'
                elif o == max_ord:
                    side = 'left'
                else:
                    side = 'full'
                db.update(
                    "UPDATE op_lotes SET align_side = %s, updated_at = NOW() WHERE id = %s",
                    (side, it.get('id'))
                )

        etapa_nova_id = request.form.get('etapa_nova_id')
        qtd_raw = request.form.get('quantidade')
        observacao = (request.form.get('observacao') or '').strip()

        if not etapa_nova_id:
            return jsonify({'erro': 'Etapa não informada'}), 400

        def _normalizar_decimal(valor):
            v = ('' if valor is None else str(valor)).strip()
            if not v:
                raise InvalidOperation('empty')
            # aceita formatos pt-BR (1.234,56) e en-US (1234.56)
            if ',' in v and '.' in v:
                v = v.replace('.', '').replace(',', '.')
            elif ',' in v:
                v = v.replace(',', '.')
            return Decimal(v)

        try:
            qtd_mov = _normalizar_decimal(qtd_raw)
        except Exception:
            return jsonify({'erro': 'Quantidade inválida'}), 400

        if qtd_mov <= 0:
            return jsonify({'erro': 'Quantidade inválida'}), 400

        lote = db.fetch_one("""
            SELECT id, ordem_producao_id, sequencia, quantidade, etapa_atual_id
            FROM op_lotes
            WHERE id = %s
            LIMIT 1
        """, (lote_id,))
        if not lote:
            return jsonify({'erro': 'Lote não encontrado'}), 404

        op = db.fetch_one("SELECT id, quantidade, status FROM ordens_producao WHERE id = %s", (lote.get('ordem_producao_id'),))
        if not op:
            return jsonify({'erro': 'OP não encontrada'}), 404

        etapa_nova = db.fetch_one("SELECT id FROM producao_etapas WHERE id = %s AND ativo = 1", (etapa_nova_id,))
        if not etapa_nova:
            return jsonify({'erro': 'Etapa inválida'}), 400

        qtd_atual = Decimal(str(lote.get('quantidade') or 0))
        if qtd_mov > qtd_atual:
            return jsonify({'erro': 'Quantidade maior que a disponível no lote'}), 400

        etapa_anterior_id = lote.get('etapa_atual_id')

        # Se já existir lote da mesma OP na etapa destino, faz merge (soma) ao invés de criar duplicado
        lote_destino = db.fetch_one(
            """
            SELECT id, quantidade
            FROM op_lotes
            WHERE ordem_producao_id = %s AND etapa_atual_id = %s AND id <> %s
            ORDER BY id
            LIMIT 1
            """,
            (op.get('id'), etapa_nova_id, lote_id)
        )

        # Movimento total
        if qtd_mov == qtd_atual:
            if lote_destino:
                qtd_dest = Decimal(str(lote_destino.get('quantidade') or 0))
                qtd_nova = qtd_dest + qtd_mov
                db.update(
                    "UPDATE op_lotes SET quantidade = %s, align_side = 'full', updated_at = NOW() WHERE id = %s",
                    (str(qtd_nova), lote_destino.get('id'))
                )
                db.update("DELETE FROM op_lotes WHERE id = %s", (lote_id,))
                lote_movido_id = lote_destino.get('id')
            else:
                db.update(
                    "UPDATE op_lotes SET etapa_atual_id = %s, align_side = 'full', updated_at = NOW() WHERE id = %s",
                    (etapa_nova_id, lote_id)
                )
                lote_movido_id = lote_id
        else:
            # Movimento parcial: reduz lote atual e envia quantidade ao destino (merge se possível)
            qtd_restante = qtd_atual - qtd_mov
            db.update(
                "UPDATE op_lotes SET quantidade = %s, align_side = 'right', updated_at = NOW() WHERE id = %s",
                (str(qtd_restante), lote_id)
            )

            if lote_destino:
                qtd_dest = Decimal(str(lote_destino.get('quantidade') or 0))
                qtd_nova = qtd_dest + qtd_mov
                db.update(
                    "UPDATE op_lotes SET quantidade = %s, align_side = 'left', updated_at = NOW() WHERE id = %s",
                    (str(qtd_nova), lote_destino.get('id'))
                )
                lote_movido_id = lote_destino.get('id')
            else:
                prox_seq = db.fetch_one(
                    "SELECT COALESCE(MAX(sequencia), 0) + 1 AS s FROM op_lotes WHERE ordem_producao_id = %s",
                    (op.get('id'),)
                )
                seq = int((prox_seq or {}).get('s') or 1)

                lote_movido_id = db.insert(
                    "INSERT INTO op_lotes (ordem_producao_id, sequencia, quantidade, etapa_atual_id, align_side, status) VALUES (%s, %s, %s, %s, 'left', %s)",
                    (op.get('id'), seq, str(qtd_mov), etapa_nova_id, op.get('status'))
                )

        # Log do lote
        db.insert("""
            INSERT INTO op_lotes_etapas_log (
                lote_id, ordem_producao_id, quantidade_movida,
                etapa_anterior_id, etapa_nova_id,
                observacao, usuario_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            lote_movido_id,
            op.get('id'),
            str(qtd_mov),
            etapa_anterior_id,
            etapa_nova_id,
            observacao if observacao else None,
            session.get('user_id')
        ))

        # Compatibilidade: etapa_atual_id da OP = etapa com maior soma de quantidade
        dominante = db.fetch_one("""
            SELECT etapa_atual_id, SUM(quantidade) AS qtd
            FROM op_lotes
            WHERE ordem_producao_id = %s
            GROUP BY etapa_atual_id
            ORDER BY qtd DESC
            LIMIT 1
        """, (op.get('id'),))
        if dominante and dominante.get('etapa_atual_id'):
            db.update(
                "UPDATE ordens_producao SET etapa_atual_id = %s WHERE id = %s",
                (dominante.get('etapa_atual_id'), op.get('id'))
            )

        # Ajustar alinhamentos para refletir: origem (mais antiga)=direita, intermediárias=full, destino mais avançado=esquerda
        _recalcular_align_sides(op.get('id'))

        return jsonify({'sucesso': True})

    except Exception as e:
        return jsonify({'erro': str(e)}), 500


@ordem_producao_bp.route('/<int:id>/template/criar', methods=['POST'])
def criar_template_da_op(id):
    """Cria um template a partir da OP e aplica na OP."""
    db = get_db()

    try:
        template_id = _criar_template_a_partir_op(db, id)
        _aplicar_template_em_op(db, id, template_id)
        flash('Ficha Técnica criada e aplicada na OP com sucesso!', 'success')
        return redirect(url_for('ordem_producao.visualizar_op', id=id))
    except Exception as e:
        flash(f'Erro ao criar Ficha Técnica a partir da OP: {str(e)}', 'danger')
        return redirect(url_for('ordem_producao.visualizar_op', id=id))


@ordem_producao_bp.route('/<int:id>/template/importar', methods=['GET', 'POST'])
def importar_template_para_op(id):
    """Importa um template de outro produto e aplica na OP."""
    db = get_db()

    try:
        op = db.fetch_one("SELECT id, produto_id, numero_op, usou_template FROM ordens_producao WHERE id = %s", (id,))
        if not op:
            flash('OP não encontrada!', 'danger')
            return redirect(url_for('ordem_producao.listar_ops'))

        if request.method == 'GET':
            templates = db.fetch_all("""
                SELECT t.id AS template_id, t.produto_id, t.versao, t.nome_template,
                       p.name AS produto_nome
                FROM produto_templates_producao t
                INNER JOIN products p ON p.id = t.produto_id
                WHERE t.ativo = 1
                ORDER BY p.name, t.versao DESC
            """) or []

            return render_template('industria/ordem_producao_importar_template.html', op=op, templates=templates)

        template_origem_id = request.form.get('template_origem_id')
        if not template_origem_id:
            flash('Selecione uma Ficha Técnica de origem.', 'warning')
            return redirect(url_for('ordem_producao.importar_template_para_op', id=id))

        # Copiar template de origem para o produto final desta OP
        origem = db.fetch_one("""
            SELECT id, produto_id, versao, nome_template, custo_total_base
            FROM produto_templates_producao
            WHERE id = %s
        """, (template_origem_id,))
        if not origem:
            flash('Ficha Técnica de origem não encontrada.', 'danger')
            return redirect(url_for('ordem_producao.importar_template_para_op', id=id))

        # Próxima versão para o produto da OP
        versao_atual = db.fetch_one(
            "SELECT MAX(versao) AS v FROM produto_templates_producao WHERE produto_id = %s",
            (op['produto_id'],)
        )
        prox_versao = int((versao_atual or {}).get('v') or 0) + 1

        # Desativar template ativo anterior do produto
        db.execute_query(
            "UPDATE produto_templates_producao SET ativo = 0 WHERE produto_id = %s AND ativo = 1",
            (op['produto_id'],)
        )

        novo_template_id = db.insert("""
            INSERT INTO produto_templates_producao (
                produto_id, versao, nome_template, custo_total_base, ativo, created_by
            ) VALUES (%s, %s, %s, %s, 1, %s)
        """, (
            op['produto_id'],
            prox_versao,
            f"Importado: {origem.get('nome_template') or 'Template'}",
            str(origem.get('custo_total_base') or 0),
            session.get('user_id')
        ))

        itens_origem = db.fetch_all("""
            SELECT tipo_item, produto_id, descricao, quantidade, unidade_medida, custo_unitario_base, custo_total_base
            FROM produto_template_itens
            WHERE template_id = %s
            ORDER BY tipo_item, id
        """, (template_origem_id,)) or []

        for it in itens_origem:
            db.insert("""
                INSERT INTO produto_template_itens (
                    template_id, tipo_item, produto_id, descricao,
                    quantidade, unidade_medida, custo_unitario_base, custo_total_base
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                novo_template_id,
                it['tipo_item'],
                it['produto_id'],
                it.get('descricao'),
                it.get('quantidade'),
                it.get('unidade_medida'),
                it.get('custo_unitario_base'),
                it.get('custo_total_base')
            ))

        _aplicar_template_em_op(db, id, novo_template_id)
        flash('Ficha Técnica importada e aplicada na OP com sucesso!', 'success')
        return redirect(url_for('ordem_producao.visualizar_op', id=id))

    except Exception as e:
        flash(f'Erro ao importar Ficha Técnica: {str(e)}', 'danger')
        return redirect(url_for('ordem_producao.visualizar_op', id=id))


@ordem_producao_bp.route('/verificar-template/<int:produto_id>', methods=['GET'])
def verificar_template(produto_id):
    """Verifica se existe template ativo para o produto"""
    db = get_db()
    
    try:
        template = db.fetch_one("""
            SELECT 
                t.id,
                t.versao,
                t.nome_template,
                t.custo_total_base,
                t.tempo_producao_horas,
                t.observacoes,
                p.name as produto_nome
            FROM produto_templates_producao t
            INNER JOIN products p ON t.produto_id = p.id
            WHERE t.produto_id = %s AND t.ativo = 1
        """, (produto_id,))
        
        if template:
            # Buscar itens do template
            itens = db.fetch_all("""
                SELECT 
                    ti.id,
                    ti.tipo_item,
                    ti.produto_id,
                    p.name as produto_nome,
                    ti.descricao,
                    ti.quantidade,
                    ti.unidade_medida,
                    ti.custo_unitario_base,
                    ti.custo_total_base,
                    p.cost_price as custo_atual,
                    CASE 
                        WHEN ti.custo_unitario_base > 0 THEN
                            ((p.cost_price - ti.custo_unitario_base) / ti.custo_unitario_base) * 100
                        ELSE 0
                    END as variacao_percentual
                FROM produto_template_itens ti
                INNER JOIN products p ON ti.produto_id = p.id
                WHERE ti.template_id = %s
                ORDER BY ti.tipo_item, p.name
            """, (template['id'],))
            
            # Calcular custo total atual
            custo_total_atual = sum(
                float(item['quantidade']) * float(item['custo_atual'] or 0)
                for item in itens
            )
            
            # Calcular variação total
            variacao_total = 0
            if template['custo_total_base'] and template['custo_total_base'] > 0:
                variacao_total = ((custo_total_atual - float(template['custo_total_base'])) / 
                                float(template['custo_total_base'])) * 100
            
            return jsonify({
                'existe': True,
                'template': {
                    'id': template['id'],
                    'versao': template['versao'],
                    'nome': template['nome_template'],
                    'custo_base': float(template['custo_total_base'] or 0),
                    'custo_atual': custo_total_atual,
                    'variacao_percentual': round(variacao_total, 2),
                    'tempo_horas': float(template['tempo_producao_horas'] or 0),
                    'observacoes': template['observacoes']
                },
                'itens': [
                    {
                        'id': item['id'],
                        'tipo_item': item['tipo_item'],
                        'produto_id': item['produto_id'],
                        'produto_nome': item['produto_nome'],
                        'descricao': item['descricao'],
                        'quantidade': float(item['quantidade']),
                        'unidade_medida': item['unidade_medida'],
                        'custo_unitario_base': float(item['custo_unitario_base'] or 0),
                        'custo_unitario_atual': float(item['custo_atual'] or 0),
                        'custo_total_base': float(item['custo_total_base'] or 0),
                        'custo_total_atual': float(item['quantidade']) * float(item['custo_atual'] or 0),
                        'variacao_percentual': round(float(item['variacao_percentual'] or 0), 2)
                    }
                    for item in itens
                ]
            })
        else:
            return jsonify({'existe': False})
            
    except Exception as e:
        return jsonify({'erro': str(e)}), 500


@ordem_producao_bp.route('/buscar-produtos-por-tipo', methods=['GET'])
def buscar_produtos_por_tipo():
    """Busca produtos filtrados por categoria_fiscal"""
    db = get_db()
    tipo = request.args.get('tipo', '')
    
    try:
        # Mapear tipo_item para categoria_fiscal
        mapa_tipos = {
            'servico': 'servico',
            'materia_prima': 'materia_prima',
            'consumo_interno': 'consumo_interno'
        }
        
        categoria_fiscal = mapa_tipos.get(tipo)
        
        if not categoria_fiscal:
            return jsonify([])
        
        produtos = db.fetch_all("""
            SELECT 
                p.id,
                p.name,
                p.cost_price,
                p.unit_measure,
                pc.name as categoria_nome
            FROM products p
            INNER JOIN product_categories pc ON p.category_id = pc.id
            WHERE p.active = TRUE 
              AND pc.categoria_fiscal = %s
            ORDER BY p.name
        """, (categoria_fiscal,))
        
        return jsonify([
            {
                'id': p['id'],
                'name': p['name'],
                'cost_price': float(p['cost_price'] or 0),
                'unit_measure': p['unit_measure'],
                'categoria': p['categoria_nome']
            }
            for p in produtos
        ])
        
    except Exception as e:
        return jsonify({'erro': str(e)}), 500


@ordem_producao_bp.route('/salvar', methods=['POST'])
def salvar_op():
    """Salva nova ordem de produção ou atualiza existente"""
    db = get_db()
    
    try:
        # Verificar se é edição
        op_id = request.form.get('op_id')
        is_edicao = bool(op_id)
        
        # Dados gerais
        empresa_id = request.form.get('empresa_id')
        cliente_id = request.form.get('cliente_id')
        produto_id = request.form.get('produto_id')
        quantidade = request.form.get('quantidade')
        data_solicitacao = request.form.get('data_solicitacao')
        data_prevista = request.form.get('data_prevista')
        observacoes = request.form.get('observacoes', '')
        
        # Template
        usou_template = request.form.get('usou_template', '0')
        template_usado_id = request.form.get('template_usado_id')
        custo_total_template = request.form.get('custo_total_template', '0')
        
        # Validações
        if not all([empresa_id, cliente_id, produto_id, quantidade, data_solicitacao]):
            flash('Preencha todos os campos obrigatórios!', 'danger')
            return redirect(url_for('ordem_producao.nova_op'))
        
        # Se data_prevista não foi informada, calcular automaticamente
        if not data_prevista and not is_edicao:
            try:
                from app.services.previsao_producao_service import PrevisaoProducaoService
                service = PrevisaoProducaoService()
                tempo_produto = service.get_tempo_total_produto(int(produto_id))
                tempo_total = int(tempo_produto * float(quantidade))
                previsao = service.adicionar_minutos_uteis(datetime.now(), tempo_total, int(empresa_id) if empresa_id else None)
                data_prevista = previsao.strftime('%Y-%m-%d') if previsao else None
            except Exception as e:
                print(f"[OP] Erro ao calcular previsão: {e}")
        
        if is_edicao:
            # Atualizar OP existente
            db.execute_query("""
                UPDATE ordens_producao SET
                    empresa_id = %s, cliente_id = %s, produto_id = %s, quantidade = %s,
                    template_usado_id = %s, usou_template = %s, custo_total_template = %s,
                    data_solicitacao = %s, data_prevista = %s, observacoes = %s
                WHERE id = %s
            """, (
                empresa_id, cliente_id, produto_id, quantidade,
                template_usado_id if usou_template == '1' else None,
                usou_template, custo_total_template,
                data_solicitacao, data_prevista, observacoes, op_id
            ))
            
            # Excluir itens antigos
            db.execute_query("DELETE FROM ordem_producao_itens WHERE ordem_producao_id = %s", (op_id,))
        else:
            etapa_inicial = db.fetch_one("""
                SELECT id
                FROM producao_etapas
                WHERE ativo = 1
                ORDER BY ordem, id
                LIMIT 1
            """)
            etapa_inicial_id = etapa_inicial.get('id') if etapa_inicial else None

            # Inserir nova OP (número gerado automaticamente por trigger)
            op_id = db.insert("""
                INSERT INTO ordens_producao (
                    empresa_id, cliente_id, produto_id, quantidade,
                    template_usado_id, usou_template, custo_total_template,
                    data_solicitacao, data_prevista, observacoes,
                    etapa_atual_id,
                    status
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'pendente')
            """, (
                empresa_id, cliente_id, produto_id, quantidade,
                template_usado_id if usou_template == '1' else None,
                usou_template, custo_total_template,
                data_solicitacao, data_prevista, observacoes,
                etapa_inicial_id
            ))

            # Criar lote inicial (100%)
            try:
                db.insert(
                    "INSERT INTO op_lotes (ordem_producao_id, sequencia, quantidade, etapa_atual_id, align_side, status) VALUES (%s, 1, %s, %s, 'full', 'pendente')",
                    (op_id, quantidade, etapa_inicial_id)
                )
            except Exception:
                pass
        
        # Inserir itens
        custo_total_atual = Decimal('0')
        
        # Processar itens de serviço
        servico_ids = request.form.getlist('servico_produto_id[]')
        for i, prod_id in enumerate(servico_ids):
            if prod_id:
                qtd = request.form.getlist('servico_quantidade[]')[i]
                custo_unit = request.form.getlist('servico_custo_unitario[]')[i]
                custo_template = request.form.getlist('servico_custo_template[]')[i] or None
                veio_template = request.form.getlist('servico_veio_template[]')[i] or '0'
                
                custo_total_item = Decimal(qtd) * Decimal(custo_unit)
                custo_total_atual += custo_total_item
                
                # Buscar dados do produto
                prod = db.fetch_one("SELECT name, unit_measure FROM products WHERE id = %s", (prod_id,))
                
                db.insert("""
                    INSERT INTO ordem_producao_itens (
                        ordem_producao_id, tipo_item, produto_id, descricao,
                        quantidade, unidade_medida, custo_unitario_template,
                        custo_unitario_atual, custo_total, veio_template
                    ) VALUES (%s, 'servico', %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    op_id, prod_id, prod['name'], qtd, prod['unit_measure'],
                    custo_template, custo_unit, custo_total_item, veio_template
                ))
        
        # Processar itens de matéria prima
        materia_ids = request.form.getlist('materia_produto_id[]')
        for i, prod_id in enumerate(materia_ids):
            if prod_id:
                qtd = request.form.getlist('materia_quantidade[]')[i]
                custo_unit = request.form.getlist('materia_custo_unitario[]')[i]
                custo_template = request.form.getlist('materia_custo_template[]')[i] or None
                veio_template = request.form.getlist('materia_veio_template[]')[i] or '0'
                
                custo_total_item = Decimal(qtd) * Decimal(custo_unit)
                custo_total_atual += custo_total_item
                
                prod = db.fetch_one("SELECT name, unit_measure FROM products WHERE id = %s", (prod_id,))
                
                db.insert("""
                    INSERT INTO ordem_producao_itens (
                        ordem_producao_id, tipo_item, produto_id, descricao,
                        quantidade, unidade_medida, custo_unitario_template,
                        custo_unitario_atual, custo_total, veio_template
                    ) VALUES (%s, 'materia_prima', %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    op_id, prod_id, prod['name'], qtd, prod['unit_measure'],
                    custo_template, custo_unit, custo_total_item, veio_template
                ))
        
        # Processar itens de consumo interno
        consumo_ids = request.form.getlist('consumo_produto_id[]')
        for i, prod_id in enumerate(consumo_ids):
            if prod_id:
                qtd = request.form.getlist('consumo_quantidade[]')[i]
                custo_unit = request.form.getlist('consumo_custo_unitario[]')[i]
                custo_template = request.form.getlist('consumo_custo_template[]')[i] or None
                veio_template = request.form.getlist('consumo_veio_template[]')[i] or '0'
                
                custo_total_item = Decimal(qtd) * Decimal(custo_unit)
                custo_total_atual += custo_total_item
                
                prod = db.fetch_one("SELECT name, unit_measure FROM products WHERE id = %s", (prod_id,))
                
                db.insert("""
                    INSERT INTO ordem_producao_itens (
                        ordem_producao_id, tipo_item, produto_id, descricao,
                        quantidade, unidade_medida, custo_unitario_template,
                        custo_unitario_atual, custo_total, veio_template
                    ) VALUES (%s, 'consumo_interno', %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    op_id, prod_id, prod['name'], qtd, prod['unit_measure'],
                    custo_template, custo_unit, custo_total_item, veio_template
                ))
        
        # Atualizar custo total da OP
        db.execute_query("""
            UPDATE ordens_producao 
            SET custo_total_atual = %s
            WHERE id = %s
        """, (custo_total_atual, op_id))
        
        # Buscar número da OP
        op = db.fetch_one("SELECT numero_op FROM ordens_producao WHERE id = %s", (op_id,))
        
        if is_edicao:
            flash(f'Ordem de Produção {op["numero_op"]} atualizada com sucesso!', 'success')
        else:
            flash(f'Ordem de Produção {op["numero_op"]} criada com sucesso!', 'success')
        
        return redirect(url_for('ordem_producao.visualizar_op', id=op_id))
        
    except Exception as e:
        flash(f'Erro ao salvar ordem de produção: {str(e)}', 'danger')
        return redirect(url_for('ordem_producao.nova_op'))


@ordem_producao_bp.route('/editar/<int:id>', methods=['GET'])
@industria_ops_editar_required
def editar_op(id):
    """Formulário para editar ordem de produção"""
    db = get_db()
    
    try:
        # Buscar OP
        op = db.fetch_one("SELECT * FROM ordens_producao WHERE id = %s", (id,))
        
        if not op:
            flash('Ordem de produção não encontrada!', 'danger')
            return redirect(url_for('ordem_producao.listar_ops'))
        
        if op['status'] != 'pendente':
            flash('Apenas OPs pendentes podem ser editadas!', 'warning')
            return redirect(url_for('ordem_producao.visualizar_op', id=id))
        
        # Buscar dados para formulário
        empresas = db.fetch_all("SELECT id, nome_fantasia FROM empresas WHERE ativo = TRUE ORDER BY nome_fantasia")
        clientes = db.fetch_all("SELECT id, name FROM customers WHERE active = TRUE ORDER BY name")

        produto_selecionado = None
        if op.get('produto_id'):
            produto_selecionado = db.fetch_one(
                "SELECT id, internal_code AS codigo, name AS nome FROM products WHERE id = %s",
                (op['produto_id'],)
            )
        
        # Buscar itens da OP
        itens = db.fetch_all("""
            SELECT * FROM ordem_producao_itens 
            WHERE ordem_producao_id = %s
            ORDER BY tipo_item, id
        """, (id,))
        
        return render_template('industria/ordem_producao_form.html',
                             empresas=empresas,
                             clientes=clientes,
                             produto_selecionado=produto_selecionado,
                             op=op,
                             itens=itens)
        
    except Exception as e:
        flash(f'Erro ao carregar formulário: {str(e)}', 'danger')
        return redirect(url_for('ordem_producao.listar_ops'))


@ordem_producao_bp.route('/visualizar/<int:id>')
def visualizar_op(id):
    """Visualiza detalhes de uma ordem de produção"""
    db = get_db()
    
    try:
        # Buscar OP
        op = db.fetch_one("SELECT * FROM vw_ordens_producao_resumo WHERE id = %s", (id,))
        
        if not op:
            flash('Ordem de produção não encontrada!', 'danger')
            return redirect(url_for('ordem_producao.listar_ops'))

        empresa_row = db.fetch_one("SELECT empresa_id FROM ordens_producao WHERE id = %s", (id,))
        empresa_id = empresa_row['empresa_id'] if empresa_row else None
        fx_info = calcular_fx_para_empresa(db, empresa_id) if empresa_id else None

        # Etapas de chão de fábrica
        etapa_atual = db.fetch_one("""
            SELECT e.id, e.nome, e.ordem
            FROM ordens_producao op
            LEFT JOIN producao_etapas e ON e.id = op.etapa_atual_id
            WHERE op.id = %s
            LIMIT 1
        """, (id,))

        etapas = db.fetch_all("""
            SELECT id, nome, ordem
            FROM producao_etapas
            WHERE ativo = 1
            ORDER BY ordem, id
        """) or []

        # Unificar histórico: log antigo (op_etapas_log) + log de lotes (op_lotes_etapas_log)
        # Inclui líder, operador, etapa, data, status
        etapas_log = db.fetch_all("""
            SELECT
                x.id,
                x.created_at,
                x.observacao,
                x.etapa_anterior,
                x.etapa_nova,
                x.usuario_nome,
                x.lote_info,
                x.quantidade_movida,
                x.lider_nome,
                x.operador_nome,
                x.status_anterior,
                x.status_novo,
                x.arara
            FROM (
                SELECT
                    CONCAT('op_', l.id) AS id,
                    l.created_at,
                    l.observacao,
                    ea.nome AS etapa_anterior,
                    en.nome AS etapa_nova,
                    u.name AS usuario_nome,
                    NULL AS lote_info,
                    NULL AS quantidade_movida,
                    NULL AS lider_nome,
                    NULL AS operador_nome,
                    NULL AS status_anterior,
                    NULL AS status_novo,
                    NULL AS arara
                FROM op_etapas_log l
                LEFT JOIN producao_etapas ea ON ea.id = l.etapa_anterior_id
                INNER JOIN producao_etapas en ON en.id = l.etapa_nova_id
                LEFT JOIN users u ON u.id = l.usuario_id
                WHERE l.ordem_producao_id = %s

                UNION ALL

                SELECT
                    CONCAT('lote_', ll.id) AS id,
                    ll.created_at,
                    ll.observacao,
                    ea2.nome AS etapa_anterior,
                    en2.nome AS etapa_nova,
                    u2.name AS usuario_nome,
                    CONCAT('Lote ', COALESCE(lo.sequencia, '-')) AS lote_info,
                    ll.quantidade_movida AS quantidade_movida,
                    ulider.name AS lider_nome,
                    uop.name AS operador_nome,
                    ll.status_anterior,
                    ll.status_novo,
                    ll.arara
                FROM op_lotes_etapas_log ll
                LEFT JOIN op_lotes lo ON lo.id = ll.lote_id
                LEFT JOIN producao_etapas ea2 ON ea2.id = ll.etapa_anterior_id
                LEFT JOIN producao_etapas en2 ON en2.id = ll.etapa_nova_id
                LEFT JOIN users u2 ON u2.id = ll.usuario_id
                LEFT JOIN users ulider ON ulider.id = ll.lider_id
                LEFT JOIN users uop ON uop.id = ll.operador_origem_id
                WHERE ll.ordem_producao_id = %s
            ) x
            ORDER BY x.created_at DESC
            LIMIT 200
        """, (id, id)) or []
        
        # Buscar itens
        itens = db.fetch_all("""
            SELECT * FROM vw_ordem_producao_itens_detalhado 
            WHERE ordem_producao_id = %s
            ORDER BY tipo_item, produto_nome
        """, (id,))
        
        # Agrupar itens por tipo
        itens_por_tipo = {
            'servico': [],
            'materia_prima': [],
            'consumo_interno': []
        }
        
        for item in itens:
            itens_por_tipo[item['tipo_item']].append(item)
        
        # Calcular totais por tipo
        totais = {
            'servico': sum(float(i['custo_total']) for i in itens_por_tipo['servico']),
            'materia_prima': sum(float(i['custo_total']) for i in itens_por_tipo['materia_prima']),
            'consumo_interno': sum(float(i['custo_total']) for i in itens_por_tipo['consumo_interno'])
        }
        
        totais_fx = None
        fx_currency_code = None
        if fx_info:
            target_code = (fx_info.get('target_currency') or '').upper()
            rate = fx_info.get('rate_value') or 0
            if target_code and target_code != 'BRL' and rate:
                fx_currency_code = target_code
                totais_fx = {
                    'servico': totais['servico'] * rate,
                    'materia_prima': totais['materia_prima'] * rate,
                    'consumo_interno': totais['consumo_interno'] * rate,
                }
        
        return render_template('industria/ordem_producao_visualizar.html',
                             op=op,
                             etapa_atual=etapa_atual,
                             etapas=etapas,
                             etapas_log=etapas_log,
                             itens_por_tipo=itens_por_tipo,
                             totais=totais,
                             fx_currency_code=fx_currency_code,
                             totais_fx=totais_fx)
        
    except Exception as e:
        flash(f'Erro ao carregar ordem de produção: {str(e)}', 'danger')
        return redirect(url_for('ordem_producao.listar_ops'))


@ordem_producao_bp.route('/<int:id>/mudar-etapa', methods=['POST'])
@login_required
def mudar_etapa(id):
    """Altera etapa atual da OP e registra log (data/hora + usuário)."""
    db = get_db()

    try:
        etapa_nova_id = request.form.get('etapa_nova_id')
        observacao = (request.form.get('observacao') or '').strip()

        if not etapa_nova_id:
            return jsonify({'erro': 'Etapa não informada'}), 400

        op = db.fetch_one("SELECT id, etapa_atual_id FROM ordens_producao WHERE id = %s", (id,))
        if not op:
            return jsonify({'erro': 'OP não encontrada'}), 404

        etapa_nova = db.fetch_one(
            "SELECT id FROM producao_etapas WHERE id = %s AND ativo = 1",
            (etapa_nova_id,)
        )
        if not etapa_nova:
            return jsonify({'erro': 'Etapa inválida'}), 400

        etapa_anterior_id = op.get('etapa_atual_id')

        # Atualizar etapa atual (persistência garantida)
        db.update(
            "UPDATE ordens_producao SET etapa_atual_id = %s WHERE id = %s",
            (etapa_nova_id, id)
        )

        # Regras mínimas: ao sair de "pendente" via etapa, marcar como "em_producao" e preencher data de início
        op_status = db.fetch_one("SELECT status, data_inicio_producao FROM ordens_producao WHERE id = %s", (id,))
        if op_status and op_status.get('status') == 'pendente':
            if op_status.get('data_inicio_producao') is None:
                db.update(
                    "UPDATE ordens_producao SET status = 'em_producao', data_inicio_producao = CURDATE() WHERE id = %s",
                    (id,)
                )
            else:
                db.update(
                    "UPDATE ordens_producao SET status = 'em_producao' WHERE id = %s",
                    (id,)
                )

        db.insert("""
            INSERT INTO op_etapas_log (
                ordem_producao_id, etapa_anterior_id, etapa_nova_id,
                observacao, usuario_id
            ) VALUES (%s, %s, %s, %s, %s)
        """, (
            id,
            etapa_anterior_id,
            etapa_nova_id,
            observacao if observacao else None,
            session.get('user_id')
        ))

        return jsonify({'sucesso': True})

    except Exception as e:
        return jsonify({'erro': str(e)}), 500


@ordem_producao_bp.route('/alterar-status/<int:id>', methods=['POST'])
def alterar_status(id):
    """Altera o status de uma ordem de produção"""
    db = get_db()
    
    try:
        novo_status = request.form.get('status')
        motivo_cancelamento = request.form.get('motivo_cancelamento', '')
        
        if novo_status not in ['pendente', 'em_producao', 'concluida', 'cancelada']:
            return jsonify({'erro': 'Status inválido'}), 400
        
        # Buscar dados da OP antes de atualizar
        op = db.fetch_one("""
            SELECT op.id, op.produto_id, op.quantidade, op.status, op.tipo_op
            FROM ordens_producao op
            WHERE op.id = %s
        """, (id,))
        
        if not op:
            return jsonify({'erro': 'OP não encontrada'}), 404
        
        # Atualizar datas conforme status
        updates = []
        params = [novo_status]
        
        if novo_status == 'em_producao':
            updates.append("data_inicio_producao = CURDATE()")
        elif novo_status == 'concluida':
            updates.append("data_conclusao = CURDATE()")
            
            # Se OP de PRODUÇÃO está sendo concluída, ADICIONAR ao estoque
            if op['tipo_op'] in ('producao', 'mista') and op['status'] != 'concluida':
                produto_id = op['produto_id']
                quantidade = float(op['quantidade'] or 0)
                
                if produto_id and quantidade > 0:
                    if registrar_movimentacao:
                        # Usar helper Kardex
                        resultado = registrar_movimentacao(
                            produto_id=produto_id,
                            tipo='entrada_producao',
                            quantidade=quantidade,
                            origem_tela='Ordem de Produção',
                            referencia_tipo='op',
                            referencia_id=id,
                            referencia_codigo=f'OP-{id}',
                            observacao=f'Entrada de produção - OP #{id}'
                        )
                        if resultado.get('success'):
                            print(f"[OP CONCLUÍDA] [KARDEX] Estoque: {resultado.get('estoque_anterior')} -> {resultado.get('estoque_posterior')}")
                        else:
                            print(f"[OP CONCLUÍDA] [KARDEX] Erro: {resultado.get('error')}")
                    else:
                        # Fallback: atualização direta
                        db.execute("""
                            UPDATE products 
                            SET stock_quantity = COALESCE(stock_quantity, 0) + %s
                            WHERE id = %s
                        """, (quantidade, produto_id))
                        
                        db.execute("""
                            INSERT INTO current_stock (product_id, location_id, quantity)
                            VALUES (%s, 1, %s)
                            ON DUPLICATE KEY UPDATE quantity = quantity + VALUES(quantity)
                        """, (produto_id, quantidade))
                    
                    print(f"[OP CONCLUÍDA] Estoque atualizado: Produto {produto_id} +{quantidade}")
                    
        elif novo_status == 'cancelada':
            updates.append("motivo_cancelamento = %s")
            params.append(motivo_cancelamento)
        
        query = f"UPDATE ordens_producao SET status = %s"
        if updates:
            query += ", " + ", ".join(updates)
        query += " WHERE id = %s"
        params.append(id)
        
        db.execute_query(query, tuple(params))
        
        flash('Status alterado com sucesso!', 'success')
        return jsonify({'sucesso': True})
        
    except Exception as e:
        return jsonify({'erro': str(e)}), 500


@ordem_producao_bp.route('/excluir/<int:id>', methods=['POST'])
@industria_ops_excluir_required
def excluir_op(id):
    """Exclui uma ordem de produção"""
    db = get_db()
    
    try:
        # Verificar se pode excluir
        op = db.fetch_one("SELECT status FROM ordens_producao WHERE id = %s", (id,))
        
        if not op:
            flash('Ordem de produção não encontrada!', 'danger')
            return redirect(url_for('ordem_producao.listar_ops'))
        
        if op['status'] in ['em_producao', 'concluida']:
            flash('Não é possível excluir OP em produção ou concluída!', 'warning')
            return redirect(url_for('ordem_producao.listar_ops'))
        
        # Excluir (CASCADE vai excluir itens automaticamente)
        db.execute_query("DELETE FROM ordens_producao WHERE id = %s", (id,))
        
        flash('Ordem de produção excluída com sucesso!', 'success')
        return redirect(url_for('ordem_producao.listar_ops'))
        
    except Exception as e:
        flash(f'Erro ao excluir ordem de produção: {str(e)}', 'danger')
        return redirect(url_for('ordem_producao.listar_ops'))


# =====================================================
# GANTT DO OPERADOR - Tela exclusiva para operadores
# =====================================================

@ordem_producao_bp.route('/meu-gantt')
@login_required
def meu_gantt():
    """Gantt exclusivo para operadores de chão de fábrica.
    Mostra apenas lotes vinculados ao operador logado.
    Status: Em Espera -> Em Produção -> Despachado
    """
    db = get_db()
    user_id = session.get('user_id')
    
    # Verificar se usuário tem permissão para esta tela
    from utils.permissoes_helper import tem_permissao
    if not tem_permissao('industria.minha_producao', 'visualizar'):
        flash('Você não tem permissão para acessar esta funcionalidade.', 'warning')
        return redirect(url_for('bem_vindo'))
    
    status_filtro = (request.args.get('status') or '').strip()
    
    # Buscar o líder do operador
    lider_info = db.fetch_one("""
        SELECT lo.lider_id, u.name AS lider_nome
        FROM lider_operadores lo
        INNER JOIN users u ON u.id = lo.lider_id
        WHERE lo.operador_id = %s
        LIMIT 1
    """, (user_id,))
    
    lider_id = lider_info.get('lider_id') if lider_info else None
    
    # Buscar etapas do líder do operador (apenas as que ele pode trabalhar)
    etapas_lider = []
    if lider_id:
        etapas_lider = db.fetch_all("""
            SELECT e.id, e.nome, e.ordem, e.cor_hex, e.icone, e.descricao,
                   e.grupo_etapas_id, e.operador_padrao_id,
                   g.nome AS grupo_etapas_nome
            FROM lider_etapas le
            INNER JOIN producao_etapas e ON e.id = le.etapa_id
            LEFT JOIN producao_etapas_grupos g ON g.id = e.grupo_etapas_id
            WHERE le.lider_id = %s AND e.ativo = 1
            ORDER BY e.ordem, e.id
        """, (lider_id,)) or []
    
    # Buscar todas etapas (para despacho externo)
    etapas = db.fetch_all("""
        SELECT e.id, e.nome, e.ordem, e.cor_hex, e.icone, e.descricao,
               e.grupo_etapas_id, e.operador_padrao_id,
               g.nome AS grupo_etapas_nome
        FROM producao_etapas e
        LEFT JOIN producao_etapas_grupos g ON g.id = e.grupo_etapas_id
        WHERE e.ativo = 1
        ORDER BY e.ordem, e.id
    """) or []
    
    try:
        # Buscar lotes do operador (atribuídos pelo líder OU vinculados à etapa)
        # Prioriza operador_designado_id (atribuição do líder)
        query = """
            SELECT
                l.id AS lote_id,
                l.sequencia AS lote_sequencia,
                l.quantidade AS lote_quantidade,
                l.etapa_atual_id,
                l.operador_id,
                l.operador_designado_id,
                l.prioridade,
                l.status_operador,
                l.arara,
                l.data_atribuicao,
                l.data_inicio_operador,
                l.data_fim_operador,
                op.data_inicio_producao,
                (SELECT MAX(log.created_at) 
                 FROM op_lotes_etapas_log log 
                 WHERE log.lote_id = l.id 
                   AND log.etapa_nova_id = l.etapa_atual_id) AS data_chegada_etapa,
                pp.id AS pausa_id,
                pp.inicio AS pausa_inicio,
                ppm.nome AS pausa_motivo,
                v.id AS op_id,
                v.numero_op,
                v.cliente_nome,
                v.produto_nome,
                v.status AS op_status,
                v.data_solicitacao,
                v.data_prevista,
                op.quantidade AS op_quantidade_total,
                e.nome AS etapa_nome,
                e.cor_hex AS etapa_cor_hex,
                e.icone AS etapa_icone,
                og.id AS grupo_id,
                o.numero AS orcamento_numero
            FROM op_lotes l
            INNER JOIN ordens_producao op ON op.id = l.ordem_producao_id
            INNER JOIN vw_ordens_producao_resumo v ON v.id = op.id
            LEFT JOIN producao_etapas e ON e.id = l.etapa_atual_id
            LEFT JOIN orcamento_op_itens oi ON oi.ordem_producao_id = v.id
            LEFT JOIN orcamento_op_grupos og ON og.id = oi.grupo_id
            LEFT JOIN orcamentos o ON o.id = og.orcamento_id
            LEFT JOIN producao_pausas pp ON pp.lote_id = l.id AND pp.fim IS NULL
            LEFT JOIN producao_pausas_motivos ppm ON ppm.id = pp.motivo_id
            WHERE v.status NOT IN ('concluida', 'cancelada')
              AND (l.operador_designado_id = %s OR l.operador_id = %s OR e.operador_padrao_id = %s)
        """
        params = [user_id, user_id, user_id]
        
        if status_filtro:
            query += " AND l.status_operador = %s"
            params.append(status_filtro)
        
        query += " AND l.status_operador IN ('em_espera', 'em_producao')"
        query += " ORDER BY l.prioridade, l.status_operador, v.data_prevista, v.id"
        
        lotes = db.fetch_all(query, tuple(params)) or []
        
        # Buscar lotes despachados HOJE pelo operador (com etapa destino e arara)
        lotes_despachados = db.fetch_all("""
            SELECT
                l.id AS lote_id,
                l.sequencia AS lote_sequencia,
                l.quantidade AS lote_quantidade,
                log.etapa_anterior_id AS etapa_atual_id,
                l.operador_id,
                l.operador_designado_id,
                l.prioridade,
                'despachado' AS status_operador,
                log.arara,
                l.data_inicio_operador,
                log.created_at AS data_fim_operador,
                v.id AS op_id,
                v.numero_op,
                v.cliente_nome,
                v.produto_nome,
                v.status AS op_status,
                v.data_solicitacao,
                v.data_prevista,
                op.quantidade AS op_quantidade_total,
                e_ant.nome AS etapa_nome,
                e_ant.cor_hex AS etapa_cor_hex,
                e_ant.icone AS etapa_icone,
                e_dest.nome AS etapa_destino_nome,
                e_dest.cor_hex AS etapa_destino_cor
            FROM op_lotes_etapas_log log
            INNER JOIN op_lotes l ON l.id = log.lote_id
            INNER JOIN ordens_producao op ON op.id = l.ordem_producao_id
            INNER JOIN vw_ordens_producao_resumo v ON v.id = op.id
            LEFT JOIN producao_etapas e_ant ON e_ant.id = log.etapa_anterior_id
            LEFT JOIN producao_etapas e_dest ON e_dest.id = log.etapa_nova_id
            WHERE log.status_novo = 'despachado'
              AND log.usuario_id = %s
              AND DATE(log.created_at) = CURDATE()
            ORDER BY log.created_at DESC
        """, (user_id,)) or []
        
        # Agrupar por status do operador
        lotes_por_status = {
            'em_espera': [],
            'em_producao': [],
            'despachado': lotes_despachados
        }
        
        for lote in lotes:
            status = lote.get('status_operador') or 'em_espera'
            if status in lotes_por_status:
                lotes_por_status[status].append(lote)
        
        return render_template(
            'industria/meu_gantt.html',
            lotes=lotes,
            lotes_por_status=lotes_por_status,
            etapas=etapas,
            etapas_lider=etapas_lider,
            lider_info=lider_info,
            status_filtro=status_filtro,
            full_width=True,
            menu_collapsed=True,
        )
        
    except Exception as e:
        flash(f'Erro ao carregar meu gantt: {str(e)}', 'danger')
        return render_template(
            'industria/meu_gantt.html',
            lotes=[],
            lotes_por_status={'em_espera': [], 'em_producao': [], 'despachado': []},
            etapas=etapas,
            etapas_lider=[],
            lider_info=None,
            status_filtro=status_filtro,
            full_width=True,
            menu_collapsed=True,
        )


@ordem_producao_bp.route('/meu-gantt/iniciar-producao', methods=['POST'])
@login_required
def meu_gantt_iniciar_producao():
    """Operador inicia produção de um lote, informando quantidade e etapa.
    Se quantidade parcial, divide o lote (parte em_producao, parte em_espera).
    Se já existe lote em_producao na mesma etapa, faz merge."""
    if not _is_operador():
        return jsonify({'success': False, 'error': 'Acesso restrito a operadores.'}), 403
    
    db = get_db()
    user_id = session.get('user_id')
    lote_id = request.form.get('lote_id')
    etapa_id = request.form.get('etapa_id')
    quantidade = request.form.get('quantidade')
    
    if not lote_id:
        return jsonify({'success': False, 'error': 'Lote não informado.'}), 400
    
    try:
        # Buscar lote atual
        lote = db.fetch_one("""
            SELECT id, ordem_producao_id, quantidade, etapa_atual_id, status 
            FROM op_lotes WHERE id = %s
        """, (lote_id,))
        if not lote:
            return jsonify({'success': False, 'error': 'Lote não encontrado.'}), 404
        
        etapa_anterior = lote.get('etapa_atual_id')
        ordem_producao_id = lote.get('ordem_producao_id')
        qtd_lote = Decimal(str(lote.get('quantidade') or 0))
        lote_status = lote.get('status')
        nova_etapa = etapa_id or etapa_anterior
        
        # Quantidade a iniciar
        qtd_iniciar = Decimal(str(quantidade)) if quantidade else qtd_lote
        
        # Buscar líder do operador
        lider_info = db.fetch_one("""
            SELECT lo.lider_id
            FROM lider_operadores lo
            WHERE lo.operador_id = %s
            LIMIT 1
        """, (user_id,))
        lider_id = lider_info.get('lider_id') if lider_info else None
        
        # Verificar se já existe lote em_producao na mesma etapa (para merge)
        lote_producao_existente = db.fetch_one("""
            SELECT id, quantidade 
            FROM op_lotes 
            WHERE ordem_producao_id = %s 
              AND etapa_atual_id = %s 
              AND id != %s
              AND status_operador = 'em_producao'
              AND operador_id = %s
            LIMIT 1
        """, (ordem_producao_id, nova_etapa, lote_id, user_id))
        
        if qtd_iniciar >= qtd_lote:
            # Quantidade total - iniciar lote inteiro
            if lote_producao_existente:
                # MERGE: Somar ao lote já em produção
                nova_qtd = Decimal(str(lote_producao_existente.get('quantidade') or 0)) + qtd_lote
                db.update("""
                    UPDATE op_lotes 
                    SET quantidade = %s, updated_at = NOW()
                    WHERE id = %s
                """, (str(nova_qtd), lote_producao_existente.get('id')))
                
                # Deletar lote atual (foi mergeado)
                db.update("DELETE FROM op_lotes WHERE id = %s", (lote_id,))
                
                # Log
                db.insert("""
                    INSERT INTO op_lotes_etapas_log 
                    (lote_id, ordem_producao_id, lider_id, quantidade_movida, etapa_anterior_id, etapa_nova_id,
                     operador_origem_id, status_anterior, status_novo, usuario_id, observacao, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 'em_espera', 'em_producao', %s, 'Iniciou e mergeou com lote existente', NOW())
                """, (lote_producao_existente.get('id'), ordem_producao_id, lider_id, str(qtd_lote), 
                      etapa_anterior, nova_etapa, user_id, user_id))
                
                return jsonify({'success': True, 'message': f'Produção iniciada e combinada! Total: {nova_qtd}'})
            else:
                # Iniciar normalmente
                db.update("""
                    UPDATE op_lotes 
                    SET status_operador = 'em_producao',
                        operador_id = %s,
                        etapa_atual_id = %s,
                        data_inicio_operador = NOW(),
                        updated_at = NOW()
                    WHERE id = %s
                """, (user_id, nova_etapa, lote_id))
                
                # Log
                db.insert("""
                    INSERT INTO op_lotes_etapas_log 
                    (lote_id, ordem_producao_id, lider_id, quantidade_movida, etapa_anterior_id, etapa_nova_id,
                     operador_origem_id, status_anterior, status_novo, usuario_id, observacao, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 'em_espera', 'em_producao', %s, 'Operador iniciou produção', NOW())
                """, (lote_id, ordem_producao_id, lider_id, str(qtd_lote), 
                      etapa_anterior, nova_etapa, user_id, user_id))
                
                return jsonify({'success': True, 'message': 'Produção iniciada!'})
        else:
            # Quantidade parcial - DIVIDIR LOTE
            qtd_restante = qtd_lote - qtd_iniciar
            
            # Atualizar lote original com quantidade restante (permanece em_espera)
            db.update("""
                UPDATE op_lotes 
                SET quantidade = %s,
                    updated_at = NOW()
                WHERE id = %s
            """, (str(qtd_restante), lote_id))
            
            if lote_producao_existente:
                # MERGE: Somar quantidade ao lote já em produção
                nova_qtd = Decimal(str(lote_producao_existente.get('quantidade') or 0)) + qtd_iniciar
                db.update("""
                    UPDATE op_lotes 
                    SET quantidade = %s, updated_at = NOW()
                    WHERE id = %s
                """, (str(nova_qtd), lote_producao_existente.get('id')))
                
                # Log para lote original (quantidade reduzida)
                db.insert("""
                    INSERT INTO op_lotes_etapas_log 
                    (lote_id, ordem_producao_id, lider_id, quantidade_movida, etapa_anterior_id, etapa_nova_id,
                     operador_origem_id, status_anterior, status_novo, usuario_id, observacao, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 'em_espera', 'em_espera', %s, 'Lote dividido - restante em espera', NOW())
                """, (lote_id, ordem_producao_id, lider_id, str(qtd_restante), 
                      etapa_anterior, etapa_anterior, user_id, user_id))
                
                # Log para lote em produção (mergeado)
                db.insert("""
                    INSERT INTO op_lotes_etapas_log 
                    (lote_id, ordem_producao_id, lider_id, quantidade_movida, etapa_anterior_id, etapa_nova_id,
                     operador_origem_id, status_anterior, status_novo, usuario_id, observacao, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 'em_espera', 'em_producao', %s, 'Quantidade adicionada (merge)', NOW())
                """, (lote_producao_existente.get('id'), ordem_producao_id, lider_id, str(qtd_iniciar), 
                      etapa_anterior, nova_etapa, user_id, user_id))
                
                return jsonify({'success': True, 'message': f'Lote dividido e combinado! {qtd_iniciar} somado ao em produção (total: {nova_qtd}), {qtd_restante} permanece em espera.'})
            else:
                # Criar novo lote em produção
                prox_seq = db.fetch_one("""
                    SELECT COALESCE(MAX(sequencia), 0) + 1 AS s 
                    FROM op_lotes WHERE ordem_producao_id = %s
                """, (ordem_producao_id,))
                seq = int((prox_seq or {}).get('s') or 1)
                
                novo_lote_id = db.insert("""
                    INSERT INTO op_lotes 
                    (ordem_producao_id, sequencia, quantidade, etapa_atual_id, 
                     operador_id, operador_designado_id, status_operador, 
                     data_inicio_operador, align_side, status, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, 'em_producao', NOW(), 'full', %s, NOW())
                """, (ordem_producao_id, seq, str(qtd_iniciar), 
                      nova_etapa, user_id, user_id, lote_status))
                
                # Log para lote original (quantidade reduzida, permanece em_espera)
                db.insert("""
                    INSERT INTO op_lotes_etapas_log 
                    (lote_id, ordem_producao_id, lider_id, quantidade_movida, etapa_anterior_id, etapa_nova_id,
                     operador_origem_id, status_anterior, status_novo, usuario_id, observacao, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 'em_espera', 'em_espera', %s, 'Lote dividido - restante em espera', NOW())
                """, (lote_id, ordem_producao_id, lider_id, str(qtd_restante), 
                      etapa_anterior, etapa_anterior, user_id, user_id))
                
                # Log para novo lote (em produção)
                db.insert("""
                    INSERT INTO op_lotes_etapas_log 
                    (lote_id, ordem_producao_id, lider_id, quantidade_movida, etapa_anterior_id, etapa_nova_id,
                     operador_origem_id, status_anterior, status_novo, usuario_id, observacao, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 'em_espera', 'em_producao', %s, 'Lote dividido - iniciou produção', NOW())
                """, (novo_lote_id, ordem_producao_id, lider_id, str(qtd_iniciar), 
                      etapa_anterior, nova_etapa, user_id, user_id))
                
                return jsonify({'success': True, 'message': f'Lote dividido! {qtd_iniciar} em produção, {qtd_restante} permanece em espera.'})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@ordem_producao_bp.route('/meu-gantt/alterar-etapa', methods=['POST'])
@login_required
def meu_gantt_alterar_etapa():
    """Operador altera a etapa do lote em produção. Se quantidade parcial, divide o lote."""
    if not _is_operador():
        return jsonify({'success': False, 'error': 'Acesso restrito a operadores.'}), 403
    
    db = get_db()
    user_id = session.get('user_id')
    lote_id = request.form.get('lote_id')
    nova_etapa_id = request.form.get('etapa_id')
    quantidade = request.form.get('quantidade')
    
    if not lote_id or not nova_etapa_id:
        return jsonify({'success': False, 'error': 'Lote e etapa são obrigatórios.'}), 400
    
    try:
        # Buscar lote
        lote = db.fetch_one("""
            SELECT id, ordem_producao_id, quantidade, etapa_atual_id, status 
            FROM op_lotes WHERE id = %s
        """, (lote_id,))
        if not lote:
            return jsonify({'success': False, 'error': 'Lote não encontrado.'}), 404
        
        etapa_anterior = lote.get('etapa_atual_id')
        ordem_producao_id = lote.get('ordem_producao_id')
        lote_status = lote.get('status')
        qtd_atual = Decimal(str(lote.get('quantidade') or 0))
        qtd_movida = Decimal(str(quantidade)) if quantidade else qtd_atual
        
        # Buscar líder do operador para registrar no log
        lider_info = db.fetch_one("""
            SELECT lo.lider_id
            FROM lider_operadores lo
            WHERE lo.operador_id = %s
            LIMIT 1
        """, (user_id,))
        lider_id = lider_info.get('lider_id') if lider_info else None
        
        # Verificar se já existe lote da mesma OP na etapa destino (para merge)
        lote_destino = db.fetch_one("""
            SELECT id, quantidade 
            FROM op_lotes 
            WHERE ordem_producao_id = %s 
              AND etapa_atual_id = %s 
              AND id != %s
              AND status_operador = 'em_producao'
            LIMIT 1
        """, (ordem_producao_id, nova_etapa_id, lote_id))
        
        if qtd_movida >= qtd_atual:
            # Quantidade total - mover lote inteiro para nova etapa
            if lote_destino:
                # MERGE: Somar quantidade ao lote existente na etapa destino
                nova_qtd = Decimal(str(lote_destino.get('quantidade') or 0)) + qtd_atual
                db.update("""
                    UPDATE op_lotes 
                    SET quantidade = %s, updated_at = NOW()
                    WHERE id = %s
                """, (str(nova_qtd), lote_destino.get('id')))
                
                # Deletar lote atual (foi mergeado)
                db.update("DELETE FROM op_lotes WHERE id = %s", (lote_id,))
                
                # Log
                db.insert("""
                    INSERT INTO op_lotes_etapas_log 
                    (lote_id, ordem_producao_id, quantidade_movida, etapa_anterior_id, etapa_nova_id,
                     lider_id, operador_origem_id, status_anterior, status_novo, usuario_id, 
                     observacao, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 'em_producao', 'em_producao', %s, 
                            'Lote mergeado com existente', NOW())
                """, (lote_destino.get('id'), ordem_producao_id, str(qtd_atual), 
                      etapa_anterior, nova_etapa_id, lider_id, user_id, user_id))
                
                return jsonify({'success': True, 'message': f'Lote combinado! Total na etapa: {nova_qtd}'})
            else:
                # Mover normalmente
                db.update("""
                    UPDATE op_lotes 
                    SET etapa_atual_id = %s,
                        updated_at = NOW()
                    WHERE id = %s
                """, (nova_etapa_id, lote_id))
                
                # Log
                db.insert("""
                    INSERT INTO op_lotes_etapas_log 
                    (lote_id, ordem_producao_id, quantidade_movida, etapa_anterior_id, etapa_nova_id,
                     lider_id, operador_origem_id, status_anterior, status_novo, usuario_id, 
                     observacao, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 'em_producao', 'em_producao', %s, 
                            'Alterou etapa (total)', NOW())
                """, (lote_id, ordem_producao_id, str(qtd_movida), 
                      etapa_anterior, nova_etapa_id, lider_id, user_id, user_id))
                
                return jsonify({'success': True, 'message': 'Etapa alterada!'})
        else:
            # Quantidade parcial - DIVIDIR LOTE
            qtd_restante = qtd_atual - qtd_movida
            
            # Atualizar lote original com quantidade restante (permanece na etapa atual)
            db.update("""
                UPDATE op_lotes 
                SET quantidade = %s,
                    updated_at = NOW()
                WHERE id = %s
            """, (str(qtd_restante), lote_id))
            
            if lote_destino:
                # MERGE: Somar quantidade ao lote existente na etapa destino
                nova_qtd = Decimal(str(lote_destino.get('quantidade') or 0)) + qtd_movida
                db.update("""
                    UPDATE op_lotes 
                    SET quantidade = %s, updated_at = NOW()
                    WHERE id = %s
                """, (str(nova_qtd), lote_destino.get('id')))
                
                # Log para lote original (quantidade reduzida)
                db.insert("""
                    INSERT INTO op_lotes_etapas_log 
                    (lote_id, ordem_producao_id, quantidade_movida, etapa_anterior_id, etapa_nova_id,
                     lider_id, operador_origem_id, status_anterior, status_novo, usuario_id, 
                     observacao, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 'em_producao', 'em_producao', %s, 
                            'Lote dividido - restante', NOW())
                """, (lote_id, ordem_producao_id, str(qtd_restante), 
                      etapa_anterior, etapa_anterior, lider_id, user_id, user_id))
                
                # Log para lote destino (mergeado)
                db.insert("""
                    INSERT INTO op_lotes_etapas_log 
                    (lote_id, ordem_producao_id, quantidade_movida, etapa_anterior_id, etapa_nova_id,
                     lider_id, operador_origem_id, status_anterior, status_novo, usuario_id, 
                     observacao, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 'em_producao', 'em_producao', %s, 
                            'Quantidade adicionada (merge)', NOW())
                """, (lote_destino.get('id'), ordem_producao_id, str(qtd_movida), 
                      etapa_anterior, nova_etapa_id, lider_id, user_id, user_id))
                
                return jsonify({'success': True, 'message': f'Lote dividido e combinado! {qtd_movida} somado ao existente (total: {nova_qtd}), {qtd_restante} permanece.'})
            else:
                # Criar novo lote com quantidade movida na nova etapa
                prox_seq = db.fetch_one("""
                    SELECT COALESCE(MAX(sequencia), 0) + 1 AS s 
                    FROM op_lotes WHERE ordem_producao_id = %s
                """, (ordem_producao_id,))
                seq = int((prox_seq or {}).get('s') or 1)
                
                novo_lote_id = db.insert("""
                    INSERT INTO op_lotes 
                    (ordem_producao_id, sequencia, quantidade, etapa_atual_id, 
                     operador_id, operador_designado_id, status_operador, 
                     data_inicio_operador, align_side, status, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, 'em_producao', NOW(), 'full', %s, NOW())
                """, (ordem_producao_id, seq, str(qtd_movida), 
                      nova_etapa_id, user_id, user_id, lote_status))
                
                # Log para lote original (quantidade reduzida)
                db.insert("""
                    INSERT INTO op_lotes_etapas_log 
                    (lote_id, ordem_producao_id, quantidade_movida, etapa_anterior_id, etapa_nova_id,
                     lider_id, operador_origem_id, status_anterior, status_novo, usuario_id, 
                     observacao, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 'em_producao', 'em_producao', %s, 
                            'Lote dividido - restante', NOW())
                """, (lote_id, ordem_producao_id, str(qtd_restante), 
                      etapa_anterior, etapa_anterior, lider_id, user_id, user_id))
                
                # Log para novo lote (movido para nova etapa)
                db.insert("""
                    INSERT INTO op_lotes_etapas_log 
                    (lote_id, ordem_producao_id, quantidade_movida, etapa_anterior_id, etapa_nova_id,
                     lider_id, operador_origem_id, status_anterior, status_novo, usuario_id, 
                     observacao, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 'em_producao', 'em_producao', %s, 
                            'Lote dividido - movido para nova etapa', NOW())
                """, (novo_lote_id, ordem_producao_id, str(qtd_movida), 
                      etapa_anterior, nova_etapa_id, lider_id, user_id, user_id))
                
                return jsonify({'success': True, 'message': f'Lote dividido! {qtd_movida} para nova etapa, {qtd_restante} permanece.'})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@ordem_producao_bp.route('/meu-gantt/despachar', methods=['POST'])
@login_required
def meu_gantt_despachar():
    """Operador despacha lote para próxima etapa."""
    if not _is_operador():
        return jsonify({'success': False, 'error': 'Acesso restrito a operadores.'}), 403
    
    db = get_db()
    user_id = session.get('user_id')
    lote_id = request.form.get('lote_id')
    quantidade_enviada = request.form.get('quantidade')
    arara = request.form.get('arara', '').strip()
    proxima_etapa_id = request.form.get('proxima_etapa_id')
    observacao = request.form.get('observacao', '').strip()
    
    if not lote_id:
        return jsonify({'success': False, 'error': 'Lote não informado.'}), 400
    
    try:
        # Buscar lote atual
        lote = db.fetch_one("""
            SELECT l.id, l.ordem_producao_id, l.quantidade, l.etapa_atual_id, l.status, 
                   e.ordem AS etapa_ordem
            FROM op_lotes l
            LEFT JOIN producao_etapas e ON e.id = l.etapa_atual_id
            WHERE l.id = %s
        """, (lote_id,))
        
        if not lote:
            return jsonify({'success': False, 'error': 'Lote não encontrado.'}), 404
        
        etapa_atual_id = lote.get('etapa_atual_id')
        qtd_atual = Decimal(str(lote.get('quantidade') or 0))
        qtd_enviada = Decimal(str(quantidade_enviada or qtd_atual))
        
        # Se não informou próxima etapa, buscar a seguinte
        if not proxima_etapa_id:
            proxima = db.fetch_one("""
                SELECT id FROM producao_etapas 
                WHERE ativo = 1 AND ordem > %s
                ORDER BY ordem LIMIT 1
            """, (lote.get('etapa_ordem') or 0,))
            proxima_etapa_id = proxima.get('id') if proxima else None
        
        # Se NÃO há próxima etapa, é FINALIZAÇÃO - adicionar ao estoque
        if not proxima_etapa_id:
            # Buscar dados da OP para saber o produto
            op_data = db.fetch_one("""
                SELECT op.id, op.produto_id, op.tipo_op, p.name as produto_nome
                FROM ordens_producao op
                LEFT JOIN products p ON p.id = op.produto_id
                WHERE op.id = %s
            """, (lote.get('ordem_producao_id'),))
            
            if op_data and op_data.get('produto_id') and op_data.get('tipo_op') in ('producao', 'mista'):
                produto_id = op_data['produto_id']
                quantidade_finalizada = float(qtd_enviada)
                op_id = lote.get('ordem_producao_id')
                
                if registrar_movimentacao:
                    # Usar helper Kardex
                    resultado = registrar_movimentacao(
                        produto_id=produto_id,
                        tipo='entrada_producao',
                        quantidade=quantidade_finalizada,
                        origem_tela='Lote Produção',
                        referencia_tipo='op_lote',
                        referencia_id=lote_id,
                        referencia_codigo=f'OP-{op_id}/L-{lote_id}',
                        observacao=f'Produção finalizada - Lote #{lote_id} da OP #{op_id}'
                    )
                    if resultado.get('success'):
                        print(f"[LOTE FINALIZADO] [KARDEX] Estoque: {resultado.get('estoque_anterior')} -> {resultado.get('estoque_posterior')}")
                    else:
                        print(f"[LOTE FINALIZADO] [KARDEX] Erro: {resultado.get('error')}")
                else:
                    # Fallback: atualização direta
                    db.execute("""
                        UPDATE products 
                        SET stock_quantity = COALESCE(stock_quantity, 0) + %s
                        WHERE id = %s
                    """, (quantidade_finalizada, produto_id))
                    
                    db.execute("""
                        INSERT INTO current_stock (product_id, location_id, quantity)
                        VALUES (%s, 1, %s)
                        ON DUPLICATE KEY UPDATE quantity = quantity + VALUES(quantity)
                    """, (produto_id, quantidade_finalizada))
                
                print(f"[LOTE FINALIZADO] Estoque atualizado: Produto {produto_id} +{quantidade_finalizada}")
            
            # Marcar lote como concluído
            db.update("""
                UPDATE op_lotes 
                SET status = 'concluido',
                    data_fim_operador = NOW(),
                    updated_at = NOW()
                WHERE id = %s
            """, (lote_id,))
            
            # Log
            db.insert("""
                INSERT INTO op_lotes_etapas_log 
                (lote_id, ordem_producao_id, quantidade_movida, etapa_anterior_id, etapa_nova_id,
                 usuario_id, observacao, created_at)
                VALUES (%s, %s, %s, %s, NULL, %s, %s, NOW())
            """, (lote_id, lote.get('ordem_producao_id'), str(qtd_enviada), 
                  etapa_atual_id, user_id, 'Lote finalizado - entrada no estoque'))
            
            return jsonify({'success': True, 'message': 'Lote finalizado! Produto adicionado ao estoque.'})
        
        # Ao despachar para outra etapa, o lote NÃO vai para operador nenhum
        # Vai SOMENTE para o líder responsável pela etapa destino
        # O líder depois atribui a um operador
        
        if qtd_enviada >= qtd_atual:
            # Despacho total - mover lote para próxima etapa (sem operador)
            db.update("""
                UPDATE op_lotes 
                SET etapa_atual_id = %s,
                    operador_id = NULL,
                    operador_designado_id = NULL,
                    status_operador = NULL,
                    arara = %s,
                    data_fim_operador = NOW(),
                    updated_at = NOW()
                WHERE id = %s
            """, (proxima_etapa_id, arara, lote_id))
        else:
            # Despacho parcial - lote atual continua em produção com restante
            # Cria novo lote na próxima etapa (vai para líder)
            qtd_restante = qtd_atual - qtd_enviada
            ordem_producao_id = lote.get('ordem_producao_id')
            
            # Lote atual continua EM PRODUÇÃO com quantidade restante
            db.update("""
                UPDATE op_lotes 
                SET quantidade = %s,
                    updated_at = NOW()
                WHERE id = %s
            """, (str(qtd_restante), lote_id))
            
            # Criar novo lote na próxima etapa (sem operador - vai para líder)
            prox_seq = db.fetch_one("""
                SELECT COALESCE(MAX(sequencia), 0) + 1 AS s 
                FROM op_lotes WHERE ordem_producao_id = %s
            """, (ordem_producao_id,))
            seq = int((prox_seq or {}).get('s') or 1)
            
            db.insert("""
                INSERT INTO op_lotes 
                (ordem_producao_id, sequencia, quantidade, etapa_atual_id, 
                 operador_id, operador_designado_id, status_operador, align_side, status, arara, created_at)
                VALUES (%s, %s, %s, %s, NULL, NULL, NULL, 'full', %s, %s, NOW())
            """, (ordem_producao_id, seq, str(qtd_enviada), 
                  proxima_etapa_id, lote.get('status'), arara))
        
        # Log
        db.insert("""
            INSERT INTO op_lotes_etapas_log 
            (lote_id, ordem_producao_id, quantidade_movida, etapa_anterior_id, etapa_nova_id,
             operador_origem_id, operador_destino_id, arara, status_anterior, status_novo,
             usuario_id, observacao, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, NULL, %s, 'em_producao', 'despachado', %s, %s, NOW())
        """, (lote_id, lote.get('ordem_producao_id'), str(qtd_enviada), 
              etapa_atual_id, proxima_etapa_id, user_id,
              arara, user_id, observacao or 'Lote despachado para líder'))
        
        return jsonify({'success': True, 'message': 'Lote despachado com sucesso!'})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@ordem_producao_bp.route('/meu-gantt/corrigir-despacho', methods=['POST'])
@login_required
def meu_gantt_corrigir_despacho():
    """Operador corrige um despacho errado - altera etapa destino e/ou arara."""
    if not _is_operador():
        return jsonify({'success': False, 'error': 'Acesso restrito a operadores.'}), 403
    
    db = get_db()
    user_id = session.get('user_id')
    
    try:
        lote_id = request.form.get('lote_id')
        etapa_destino_id = request.form.get('etapa_destino_id')
        arara = (request.form.get('arara') or '').strip()
        observacao = (request.form.get('observacao') or '').strip()
        
        if not lote_id or not etapa_destino_id:
            return jsonify({'success': False, 'error': 'Lote e etapa destino são obrigatórios.'}), 400
        
        if not observacao:
            return jsonify({'success': False, 'error': 'Motivo da correção é obrigatório.'}), 400
        
        # Buscar último log de despacho deste lote feito pelo operador hoje
        log_despacho = db.fetch_one("""
            SELECT log.id, log.lote_id, log.etapa_anterior_id, log.etapa_nova_id, 
                   log.arara AS arara_anterior, l.etapa_atual_id
            FROM op_lotes_etapas_log log
            INNER JOIN op_lotes l ON l.id = log.lote_id
            WHERE log.lote_id = %s 
              AND log.status_novo = 'despachado'
              AND log.usuario_id = %s
              AND DATE(log.created_at) = CURDATE()
            ORDER BY log.created_at DESC
            LIMIT 1
        """, (lote_id, user_id))
        
        if not log_despacho:
            return jsonify({'success': False, 'error': 'Despacho não encontrado ou não foi feito por você hoje.'}), 404
        
        etapa_anterior_log = log_despacho.get('etapa_nova_id')
        etapa_atual_lote = log_despacho.get('etapa_atual_id')
        
        # Atualizar a etapa atual do lote para a nova etapa destino
        db.update("""
            UPDATE op_lotes 
            SET etapa_atual_id = %s,
                arara = %s,
                updated_at = NOW()
            WHERE id = %s
        """, (etapa_destino_id, arara or None, lote_id))
        
        # Atualizar o log de despacho original com a correção
        db.update("""
            UPDATE op_lotes_etapas_log 
            SET etapa_nova_id = %s,
                arara = %s,
                observacao = CONCAT(COALESCE(observacao, ''), ' | CORREÇÃO: ', %s)
            WHERE id = %s
        """, (etapa_destino_id, arara or None, observacao, log_despacho.get('id')))
        
        # Registrar log de correção
        db.insert("""
            INSERT INTO op_lotes_etapas_log 
            (lote_id, ordem_producao_id, quantidade_movida, etapa_anterior_id, etapa_nova_id,
             operador_origem_id, arara, status_anterior, status_novo,
             usuario_id, observacao, created_at)
            SELECT %s, ordem_producao_id, quantidade, %s, %s,
                   %s, %s, 'despachado', 'correcao_despacho',
                   %s, %s, NOW()
            FROM op_lotes WHERE id = %s
        """, (lote_id, etapa_anterior_log, etapa_destino_id,
              user_id, arara or None, user_id, 
              f'CORREÇÃO DE DESPACHO: {observacao}', lote_id))
        
        return jsonify({'success': True, 'message': 'Despacho corrigido com sucesso!'})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# =====================================================
# PAINEL DO LÍDER DE EQUIPE
# =====================================================

@ordem_producao_bp.route('/lider/painel')
@login_required
def lider_painel():
    """Painel do líder de equipe - visualiza lotes das etapas que controla."""
    db = get_db()
    user_id = session.get('user_id')
    
    # Verificar se é líder
    if not _is_lider():
        flash('Acesso restrito a líderes de equipe.', 'warning')
        return redirect(url_for('ordem_producao.producao_gantt'))
    
    try:
        # Buscar etapas que o líder controla
        etapas_lider = db.fetch_all("""
            SELECT e.id, e.nome, e.ordem, e.cor_hex, e.icone
            FROM lider_etapas le
            INNER JOIN producao_etapas e ON e.id = le.etapa_id
            WHERE le.lider_id = %s AND e.ativo = 1
            ORDER BY e.ordem
        """, (user_id,)) or []
        
        etapa_ids = [e['id'] for e in etapas_lider]
        
        # Buscar operadores da equipe
        operadores = db.fetch_all("""
            SELECT u.id, u.name, u.username
            FROM lider_operadores lo
            INNER JOIN users u ON u.id = lo.operador_id
            WHERE lo.lider_id = %s AND u.status = 'active'
            ORDER BY u.name
        """, (user_id,)) or []
        
        # Buscar lotes das etapas do líder (sem_atribuicao, em_espera, em_producao)
        # status_operador NULL = sem atribuição (lote disponível para líder atribuir)
        lotes = []
        if etapa_ids:
            placeholders = ','.join(['%s'] * len(etapa_ids))
            lotes = db.fetch_all(f"""
                SELECT
                    l.id AS lote_id,
                    l.sequencia,
                    l.quantidade,
                    l.prioridade,
                    COALESCE(l.status_operador, 'sem_atribuicao') AS status_operador,
                    l.operador_id,
                    l.operador_designado_id,
                    l.arara,
                    u_op.name AS operador_nome,
                    u_design.name AS operador_designado_nome,
                    l.etapa_atual_id,
                    e.nome AS etapa_nome,
                    e.cor_hex AS etapa_cor,
                    op.id AS op_id,
                    op.numero_op,
                    v.cliente_nome,
                    v.produto_nome,
                    v.data_prevista,
                    op.data_inicio_producao,
                    l.data_atribuicao,
                    l.data_inicio_operador,
                    (SELECT MAX(log.created_at) 
                     FROM op_lotes_etapas_log log 
                     WHERE log.lote_id = l.id 
                       AND log.etapa_nova_id = l.etapa_atual_id) AS data_chegada_etapa,
                    pp.id AS pausa_id,
                    pp.inicio AS pausa_inicio,
                    ppm.nome AS pausa_motivo,
                    ppm.tipo AS pausa_tipo
                FROM op_lotes l
                INNER JOIN ordens_producao op ON op.id = l.ordem_producao_id
                INNER JOIN vw_ordens_producao_resumo v ON v.id = op.id
                INNER JOIN producao_etapas e ON e.id = l.etapa_atual_id
                LEFT JOIN users u_op ON u_op.id = l.operador_id
                LEFT JOIN users u_design ON u_design.id = l.operador_designado_id
                LEFT JOIN producao_pausas pp ON pp.lote_id = l.id AND pp.fim IS NULL
                LEFT JOIN producao_pausas_motivos ppm ON ppm.id = pp.motivo_id
                WHERE v.status NOT IN ('concluida', 'cancelada')
                  AND l.etapa_atual_id IN ({placeholders})
                  AND (l.status_operador IS NULL 
                       OR l.status_operador IN ('em_espera', 'em_producao'))
                ORDER BY l.prioridade, v.data_prevista, l.id
            """, tuple(etapa_ids)) or []
            
            # REMOVIDO: Query de lotes despachados do log
            # Causava duplicidade - agora despachados são tratados apenas pelo operador
        
        # Estatísticas por operador
        stats_operadores = {}
        for op in operadores:
            stats = db.fetch_one("""
                SELECT 
                    COUNT(CASE WHEN status_operador = 'em_espera' THEN 1 END) AS em_espera,
                    COUNT(CASE WHEN status_operador = 'em_producao' THEN 1 END) AS em_producao,
                    COUNT(CASE WHEN status_operador = 'despachado' AND DATE(data_fim_operador) = CURDATE() THEN 1 END) AS despachados_hoje
                FROM op_lotes
                WHERE operador_designado_id = %s
            """, (op['id'],)) or {}
            stats_operadores[op['id']] = stats
        
        return render_template(
            'industria/lider_painel.html',
            etapas_lider=etapas_lider,
            operadores=operadores,
            lotes=lotes,
            stats_operadores=stats_operadores,
            full_width=True
        )
        
    except Exception as e:
        flash(f'Erro ao carregar painel: {str(e)}', 'danger')
        return render_template(
            'industria/lider_painel.html',
            etapas_lider=[],
            operadores=[],
            lotes=[],
            stats_operadores={},
            full_width=True
        )


@ordem_producao_bp.route('/lider/atribuir-lote', methods=['POST'])
@login_required
def lider_atribuir_lote():
    """Líder atribui lote (ou parte dele) a um operador com prioridade.
    Se quantidade < total do lote, divide o lote em dois.
    """
    if not _is_lider():
        return jsonify({'success': False, 'error': 'Acesso restrito a líderes.'}), 403
    
    db = get_db()
    user_id = session.get('user_id')
    lote_id = request.form.get('lote_id')
    operador_id = request.form.get('operador_id') or None
    prioridade = request.form.get('prioridade') or 3
    quantidade_atribuir = request.form.get('quantidade')
    arara = request.form.get('arara') or None
    
    if not lote_id:
        return jsonify({'success': False, 'error': 'Lote não informado.'}), 400
    
    try:
        # Buscar lote atual
        lote = db.fetch_one("""
            SELECT id, ordem_producao_id, quantidade, etapa_atual_id, status 
            FROM op_lotes WHERE id = %s
        """, (lote_id,))
        if not lote:
            return jsonify({'success': False, 'error': 'Lote não encontrado.'}), 404
        
        quantidade_total = float(lote.get('quantidade', 0))
        quantidade_atribuir = float(quantidade_atribuir) if quantidade_atribuir else quantidade_total
        
        if quantidade_atribuir <= 0:
            return jsonify({'success': False, 'error': 'Quantidade inválida.'}), 400
        
        if quantidade_atribuir > quantidade_total:
            return jsonify({'success': False, 'error': f'Quantidade maior que disponível ({quantidade_total}).'}), 400
        
        ordem_producao_id = lote.get('ordem_producao_id')
        etapa_atual_id = lote.get('etapa_atual_id')
        lote_status = lote.get('status')
        
        if quantidade_atribuir < quantidade_total:
            # DIVIDIR O LOTE: criar novo lote com o restante
            quantidade_restante = quantidade_total - quantidade_atribuir
            
            # Buscar próxima sequência
            max_seq = db.fetch_one("""
                SELECT MAX(sequencia) as max_seq FROM op_lotes 
                WHERE ordem_producao_id = %s
            """, (ordem_producao_id,))
            nova_sequencia = (max_seq.get('max_seq') or 0) + 1 if max_seq else 1
            
            # Criar lote com o restante (fica SEM ATRIBUIÇÃO - NULL)
            db.insert("""
                INSERT INTO op_lotes (
                    ordem_producao_id, sequencia, quantidade, etapa_atual_id,
                    status_operador, prioridade, status, created_at
                ) VALUES (%s, %s, %s, %s, NULL, 3, %s, NOW())
            """, (
                ordem_producao_id,
                nova_sequencia,
                quantidade_restante,
                etapa_atual_id,
                lote_status
            ))
            
            # Atualizar lote original com a quantidade atribuída
            db.update("""
                UPDATE op_lotes 
                SET quantidade = %s,
                    operador_designado_id = %s,
                    operador_id = %s,
                    status_operador = 'em_espera',
                    arara = %s,
                    prioridade = %s,
                    data_atribuicao = NOW(),
                    atribuido_por_id = %s,
                    updated_at = NOW()
                WHERE id = %s
            """, (quantidade_atribuir, operador_id, operador_id, arara, prioridade, user_id, lote_id))
            
            # Log da atribuição (lote dividido)
            db.insert("""
                INSERT INTO op_lotes_etapas_log 
                (lote_id, ordem_producao_id, lider_id, quantidade_movida, etapa_anterior_id, etapa_nova_id,
                 operador_destino_id, arara, status_anterior, status_novo, usuario_id, observacao, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'sem_atribuicao', 'em_espera', %s, 
                        'Líder atribuiu lote parcial ao operador', NOW())
            """, (lote_id, ordem_producao_id, user_id, quantidade_atribuir, etapa_atual_id, etapa_atual_id,
                  operador_id, arara, user_id))
            
            return jsonify({
                'success': True, 
                'message': f'Lote dividido! {quantidade_atribuir} atribuído ao operador, {quantidade_restante} disponível para atribuição.'
            })
        else:
            # Atribuir lote inteiro
            db.update("""
                UPDATE op_lotes 
                SET operador_designado_id = %s,
                    operador_id = %s,
                    status_operador = 'em_espera',
                    arara = %s,
                    prioridade = %s,
                    data_atribuicao = NOW(),
                    atribuido_por_id = %s,
                    updated_at = NOW()
                WHERE id = %s
            """, (operador_id, operador_id, arara, prioridade, user_id, lote_id))
            
            # Log da atribuição (lote inteiro)
            db.insert("""
                INSERT INTO op_lotes_etapas_log 
                (lote_id, ordem_producao_id, lider_id, quantidade_movida, etapa_anterior_id, etapa_nova_id,
                 operador_destino_id, arara, status_anterior, status_novo, usuario_id, observacao, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'sem_atribuicao', 'em_espera', %s, 
                        'Líder atribuiu lote ao operador', NOW())
            """, (lote_id, ordem_producao_id, user_id, quantidade_atribuir, etapa_atual_id, etapa_atual_id,
                  operador_id, arara, user_id))
            
            return jsonify({'success': True, 'message': 'Lote atribuído com sucesso!'})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@ordem_producao_bp.route('/lider/gerenciar-equipe')
@login_required
def lider_gerenciar_equipe():
    """Líder gerencia sua equipe e etapas."""
    db = get_db()
    user_id = session.get('user_id')
    
    if not _is_lider():
        flash('Acesso restrito a líderes de equipe.', 'warning')
        return redirect(url_for('ordem_producao.producao_gantt'))
    
    try:
        # Operadores da equipe
        operadores_equipe = db.fetch_all("""
            SELECT u.id, u.name, u.username
            FROM lider_operadores lo
            INNER JOIN users u ON u.id = lo.operador_id
            WHERE lo.lider_id = %s
            ORDER BY u.name
        """, (user_id,)) or []
        
        # Etapas do líder
        etapas_lider = db.fetch_all("""
            SELECT e.id, e.nome, e.ordem
            FROM lider_etapas le
            INNER JOIN producao_etapas e ON e.id = le.etapa_id
            WHERE le.lider_id = %s
            ORDER BY e.ordem
        """, (user_id,)) or []
        
        # Todos operadores disponíveis (para adicionar)
        todos_operadores = db.fetch_all("""
            SELECT id, name, username FROM users 
            WHERE eh_operador = 1 AND status = 'active'
            ORDER BY name
        """) or []
        
        # Todas etapas disponíveis (para adicionar)
        todas_etapas = db.fetch_all("""
            SELECT id, nome, ordem FROM producao_etapas 
            WHERE ativo = 1
            ORDER BY ordem
        """) or []
        
        return render_template(
            'industria/lider_gerenciar_equipe.html',
            operadores_equipe=operadores_equipe,
            etapas_lider=etapas_lider,
            todos_operadores=todos_operadores,
            todas_etapas=todas_etapas
        )
        
    except Exception as e:
        flash(f'Erro ao carregar configuração: {str(e)}', 'danger')
        return redirect(url_for('ordem_producao.lider_painel'))


@ordem_producao_bp.route('/lider/vincular-operador', methods=['POST'])
@login_required
def lider_vincular_operador():
    """Vincula operador à equipe do líder."""
    if not _is_lider():
        return jsonify({'success': False, 'error': 'Acesso restrito a líderes.'}), 403
    
    db = get_db()
    user_id = session.get('user_id')
    operador_id = request.form.get('operador_id')
    
    if not operador_id:
        return jsonify({'success': False, 'error': 'Operador não informado.'}), 400
    
    try:
        db.insert("""
            INSERT IGNORE INTO lider_operadores (lider_id, operador_id)
            VALUES (%s, %s)
        """, (user_id, operador_id))
        
        return jsonify({'success': True, 'message': 'Operador vinculado!'})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@ordem_producao_bp.route('/lider/desvincular-operador', methods=['POST'])
@login_required
def lider_desvincular_operador():
    """Remove operador da equipe do líder."""
    if not _is_lider():
        return jsonify({'success': False, 'error': 'Acesso restrito a líderes.'}), 403
    
    db = get_db()
    user_id = session.get('user_id')
    operador_id = request.form.get('operador_id')
    
    try:
        db.execute_query("""
            DELETE FROM lider_operadores 
            WHERE lider_id = %s AND operador_id = %s
        """, (user_id, operador_id))
        
        return jsonify({'success': True, 'message': 'Operador removido da equipe!'})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@ordem_producao_bp.route('/lider/vincular-etapa', methods=['POST'])
@login_required
def lider_vincular_etapa():
    """Vincula etapa ao controle do líder."""
    if not _is_lider():
        return jsonify({'success': False, 'error': 'Acesso restrito a líderes.'}), 403
    
    db = get_db()
    user_id = session.get('user_id')
    etapa_id = request.form.get('etapa_id')
    
    if not etapa_id:
        return jsonify({'success': False, 'error': 'Etapa não informada.'}), 400
    
    try:
        db.insert("""
            INSERT IGNORE INTO lider_etapas (lider_id, etapa_id)
            VALUES (%s, %s)
        """, (user_id, etapa_id))
        
        return jsonify({'success': True, 'message': 'Etapa vinculada!'})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@ordem_producao_bp.route('/lider/desvincular-etapa', methods=['POST'])
@login_required
def lider_desvincular_etapa():
    """Remove etapa do controle do líder."""
    if not _is_lider():
        return jsonify({'success': False, 'error': 'Acesso restrito a líderes.'}), 403
    
    db = get_db()
    user_id = session.get('user_id')
    etapa_id = request.form.get('etapa_id')
    
    try:
        db.execute_query("""
            DELETE FROM lider_etapas 
            WHERE lider_id = %s AND etapa_id = %s
        """, (user_id, etapa_id))
        
        return jsonify({'success': True, 'message': 'Etapa removida do controle!'})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
