"""
Rotas do Portal de Desenvolvimento Econômico Municipal - MS
Blueprint Flask integrado ao IK Flow / SupplyChainSystem
"""
from flask import Blueprint, render_template, request, jsonify, session, g
import json

dev_economico_bp = Blueprint('dev_economico', __name__, url_prefix='/dev-economico')

# ============================================================
# Helpers
# ============================================================

def get_db():
    """Retorna conexão MySQL usando o padrão do IK Flow"""
    from db_config import get_db_connection
    return get_db_connection()

def _convert_decimals(row):
    """Converte Decimal do MySQL para float para serialização JSON correta"""
    from decimal import Decimal
    if row is None:
        return None
    if isinstance(row, dict):
        return {k: (float(v) if isinstance(v, Decimal) else v) for k, v in row.items()}
    return row

def query_db(sql, params=None, fetchone=False):
    """Executa query e retorna resultados como dicionários"""
    conn = get_db()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(sql, params or ())
        if fetchone:
            result = cursor.fetchone()
            return _convert_decimals(result)
        else:
            result = cursor.fetchall()
            return [_convert_decimals(r) for r in result]
    except Exception as e:
        print(f"[DEV_ECONOMICO] Erro na query: {e}")
        return [] if not fetchone else None
    finally:
        conn.close()

def _nearby_ids(mun_id, limit=4):
    """Retorna lista de IDs: o município selecionado + N vizinhos mais próximos (por lat/lng)"""
    mun = query_db("SELECT latitude, longitude FROM dev_eco_municipios WHERE id = %s", (mun_id,), fetchone=True)
    if not mun or not mun.get('latitude') or not mun.get('longitude'):
        return [mun_id]
    vizinhos = query_db("""
        SELECT id FROM dev_eco_municipios
        WHERE ativo = TRUE AND id != %s AND latitude IS NOT NULL AND longitude IS NOT NULL
        ORDER BY POW(latitude - %s, 2) + POW(longitude - %s, 2) ASC
        LIMIT %s
    """, (mun_id, mun['latitude'], mun['longitude'], limit))
    ids = [mun_id] + [v['id'] for v in vizinhos]
    return ids

# ============================================================
# Filtro global de município (propagado entre abas)
# ============================================================
@dev_economico_bp.before_request
def load_municipio_filtro():
    """Carrega município filtrado da URL para disponibilizar em todos os templates"""
    g.municipio_id = request.args.get('municipio_id', type=int)
    g.municipio_filtrado = None
    if g.municipio_id:
        g.municipio_filtrado = query_db(
            "SELECT * FROM dev_eco_municipios WHERE id = %s AND ativo = TRUE",
            (g.municipio_id,), fetchone=True
        )

@dev_economico_bp.context_processor
def inject_municipio_filtro():
    """Injeta dados do município filtrado em todos os templates do blueprint"""
    return {
        'municipio_id': getattr(g, 'municipio_id', None),
        'municipio_filtrado': getattr(g, 'municipio_filtrado', None)
    }

# ============================================================
# Páginas do Portal
# ============================================================

@dev_economico_bp.route('/')
@login_required
def dashboard():
    """Dashboard principal do portal — versão dinâmica interativa"""
    municipios = query_db("""
        SELECT m.id, m.codigo_ibge, m.nome, m.regiao_macro, m.mesorregiao,
               m.populacao, m.pib_total, m.pib_per_capita, m.idhm,
               m.pib_agropecuaria, m.pib_industria, m.pib_servicos, m.pib_administracao,
               m.vocacao_principal, m.latitude, m.longitude,
               COALESCE(i.iaem_score, 0.0) as iaem_score,
               COALESCE(i.iaem_classificacao, 'N/D') as iaem_classificacao,
               COALESCE(i.prob_crescimento_6m, 0.0) as prob_6m,
               COALESCE(i.prob_crescimento_12m, 0.0) as prob_12m,
               COALESCE(i.prob_crescimento_24m, 0.0) as prob_24m,
               COALESCE(i.tendencia, 'N/D') as tendencia,
               COALESCE(i.score_pix, 0.0) as score_pix,
               COALESCE(i.score_empresas, 0.0) as score_empresas,
               COALESCE(i.score_emprego, 0.0) as score_emprego,
               COALESCE(i.score_uso_solo, 0.0) as score_uso_solo,
               COALESCE(i.score_exportacao, 0.0) as score_exportacao,
               COALESCE(i.score_logistica, 0.0) as score_logistica,
               COALESCE(i.setor_destaque, '') as setor_destaque
        FROM dev_eco_municipios m
        LEFT JOIN dev_eco_iaem i ON m.id = i.municipio_id
        WHERE m.ativo = TRUE
        ORDER BY m.nome
    """)
    return render_template('dev_economico/dashboard_dinamico.html',
                           municipios_json=json.dumps(municipios, ensure_ascii=False, default=str))

@dev_economico_bp.route('/diagnostico')
@login_required
def diagnostico():
    """Diagnóstico Econômico Municipal"""
    mun_id = g.municipio_id
    municipios = query_db("SELECT * FROM dev_eco_municipios WHERE ativo = TRUE ORDER BY nome")
    
    # PIB por setor (filtrado ou agregado)
    if mun_id:
        pib_setorial = query_db("""
            SELECT pib_agropecuaria as agropecuaria, pib_industria as industria,
                   pib_servicos as servicos, pib_administracao as administracao, pib_total as total
            FROM dev_eco_municipios WHERE id = %s AND ativo = TRUE
        """, (mun_id,), fetchone=True)
    else:
        pib_setorial = query_db("""
            SELECT SUM(pib_agropecuaria) as agropecuaria, SUM(pib_industria) as industria,
                   SUM(pib_servicos) as servicos, SUM(pib_administracao) as administracao, SUM(pib_total) as total
            FROM dev_eco_municipios WHERE ativo = TRUE
        """, fetchone=True)
    
    cadeias = query_db("SELECT * FROM dev_eco_cadeias_produtivas WHERE ativo = TRUE ORDER BY participacao_pib DESC")
    
    if mun_id:
        # Município selecionado + 4 vizinhos geográficos
        ids = _nearby_ids(mun_id, 4)
        placeholders = ','.join(['%s'] * len(ids))
        top_pib = query_db(f"""
            SELECT *, (id = %s) as is_selected
            FROM dev_eco_municipios 
            WHERE ativo = TRUE AND id IN ({placeholders})
            ORDER BY pib_total DESC
        """, tuple([mun_id] + ids))
        
        top_percapita = query_db(f"""
            SELECT *, (id = %s) as is_selected
            FROM dev_eco_municipios 
            WHERE ativo = TRUE AND id IN ({placeholders})
            ORDER BY pib_per_capita DESC
        """, tuple([mun_id] + ids))
    else:
        # Top municípios por PIB (visão estadual)
        top_pib = query_db("SELECT * FROM dev_eco_municipios WHERE ativo = TRUE ORDER BY pib_total DESC LIMIT 10")
        top_percapita = query_db("SELECT * FROM dev_eco_municipios WHERE ativo = TRUE ORDER BY pib_per_capita DESC LIMIT 10")
    
    return render_template('dev_economico/diagnostico.html',
        municipios=municipios,
        pib_setorial=pib_setorial,
        cadeias=cadeias,
        top_pib=top_pib,
        top_percapita=top_percapita
    )

@dev_economico_bp.route('/agroindustria')
@login_required
def agroindustria():
    """Fortalecimento da Agroindustrialização Local"""
    mun_id = g.municipio_id
    cadeias_agro = query_db("""
        SELECT * FROM dev_eco_cadeias_produtivas 
        WHERE setor = 'Agropecuária' AND ativo = TRUE 
        ORDER BY participacao_pib DESC
    """)
    programas = query_db("""
        SELECT * FROM dev_eco_programas 
        WHERE eixo = 'Agroindustrialização' 
        ORDER BY status, progresso DESC
    """)
    if mun_id:
        ids = _nearby_ids(mun_id, 4)
        placeholders = ','.join(['%s'] * len(ids))
        municipios_agro = query_db(f"""
            SELECT *, (id = %s) as is_selected
            FROM dev_eco_municipios 
            WHERE ativo = TRUE AND id IN ({placeholders})
            ORDER BY is_selected DESC, pib_agropecuaria DESC
        """, tuple([mun_id] + ids))
        # Encadeamentos do município + vizinhos
        encadeamentos = query_db(f"""
            SELECT e.*, m.nome as municipio_nome,
                   (e.municipio_id = %s) as is_selected
            FROM dev_eco_encadeamento_latente e
            JOIN dev_eco_municipios m ON e.municipio_id = m.id
            WHERE e.municipio_id IN ({placeholders})
            ORDER BY is_selected DESC, e.gap_valor DESC
        """, tuple([mun_id] + ids))
    else:
        municipios_agro = query_db("""
            SELECT * FROM dev_eco_municipios 
            WHERE vocacao_principal LIKE '%%Agro%%' OR vocacao_principal LIKE '%%Pecuária%%' OR vocacao_principal LIKE '%%Sucro%%'
            ORDER BY pib_agropecuaria DESC LIMIT 15
        """)
        encadeamentos = query_db("""
            SELECT e.*, m.nome as municipio_nome
            FROM dev_eco_encadeamento_latente e
            JOIN dev_eco_municipios m ON e.municipio_id = m.id
            WHERE e.prioridade IN ('Crítica', 'Alta')
            ORDER BY e.gap_valor DESC LIMIT 10
        """)
    return render_template('dev_economico/agroindustria.html',
        cadeias=cadeias_agro,
        programas=programas,
        municipios=municipios_agro,
        encadeamentos=encadeamentos
    )

@dev_economico_bp.route('/investimentos')
@login_required
def investimentos():
    """Política de Atração de Investimentos"""
    mun_id = g.municipio_id
    if mun_id:
        ids = _nearby_ids(mun_id, 4)
        placeholders = ','.join(['%s'] * len(ids))
        investimentos_list = query_db(f"""
            SELECT i.*, m.nome as municipio_nome,
                   (i.municipio_id = %s) as is_selected
            FROM dev_eco_investimentos i
            LEFT JOIN dev_eco_municipios m ON i.municipio_id = m.id
            WHERE i.municipio_id IN ({placeholders})
            ORDER BY is_selected DESC, i.ano DESC, i.valor DESC
        """, tuple([mun_id] + ids))
    else:
        investimentos_list = query_db("""
            SELECT i.*, m.nome as municipio_nome 
            FROM dev_eco_investimentos i
            LEFT JOIN dev_eco_municipios m ON i.municipio_id = m.id
            ORDER BY i.ano DESC, i.valor DESC
        """)
    programas = query_db("""
        SELECT * FROM dev_eco_programas 
        WHERE eixo = 'Investimentos' 
        ORDER BY status, progresso DESC
    """)
    return render_template('dev_economico/investimentos.html',
        investimentos=investimentos_list,
        programas=programas
    )

@dev_economico_bp.route('/logistica')
@login_required
def logistica():
    """Logística e Integração Regional"""
    infraestrutura = query_db("SELECT * FROM dev_eco_infraestrutura ORDER BY tipo, nome")
    rodovias = [i for i in infraestrutura if i['tipo'] == 'Rodovia']
    ferrovias = [i for i in infraestrutura if i['tipo'] == 'Ferrovia']
    aeroportos = [i for i in infraestrutura if i['tipo'] == 'Aeroporto']
    portos = [i for i in infraestrutura if i['tipo'] == 'Porto']
    
    programas = query_db("""
        SELECT * FROM dev_eco_programas 
        WHERE eixo = 'Logística' 
        ORDER BY status, progresso DESC
    """)
    return render_template('dev_economico/logistica.html',
        rodovias=rodovias,
        ferrovias=ferrovias,
        aeroportos=aeroportos,
        portos=portos,
        programas=programas
    )

@dev_economico_bp.route('/turismo')
@login_required
def turismo():
    """Turismo como Vetor Econômico"""
    mun_id = g.municipio_id
    if mun_id:
        ids = _nearby_ids(mun_id, 4)
        placeholders = ','.join(['%s'] * len(ids))
        destinos = query_db(f"""
            SELECT t.*, m.nome as municipio_nome,
                   (t.municipio_id = %s) as is_selected
            FROM dev_eco_turismo t
            LEFT JOIN dev_eco_municipios m ON t.municipio_id = m.id
            WHERE t.municipio_id IN ({placeholders})
            ORDER BY is_selected DESC, t.visitantes_ano DESC
        """, tuple([mun_id] + ids))
    else:
        destinos = query_db("""
            SELECT t.*, m.nome as municipio_nome 
            FROM dev_eco_turismo t
            LEFT JOIN dev_eco_municipios m ON t.municipio_id = m.id
            ORDER BY t.visitantes_ano DESC
        """)
    municipios_turismo = query_db("""
        SELECT * FROM dev_eco_municipios 
        WHERE vocacao_principal LIKE '%%Turismo%%' OR vocacao_principal LIKE '%%Eco%%'
        ORDER BY nome
    """)
    programas = query_db("""
        SELECT * FROM dev_eco_programas 
        WHERE eixo = 'Turismo' 
        ORDER BY status, progresso DESC
    """)
    return render_template('dev_economico/turismo.html',
        destinos=destinos,
        municipios=municipios_turismo,
        programas=programas
    )

@dev_economico_bp.route('/inovacao')
@login_required
def inovacao():
    """Economia Digital e Inovação"""
    programas = query_db("""
        SELECT * FROM dev_eco_programas 
        WHERE eixo = 'Digital' 
        ORDER BY status, progresso DESC
    """)
    return render_template('dev_economico/inovacao.html', programas=programas)

@dev_economico_bp.route('/qualificacao')
@login_required
def qualificacao():
    """Qualificação Profissional"""
    mun_id = g.municipio_id
    programas = query_db("""
        SELECT * FROM dev_eco_programas 
        WHERE eixo = 'Qualificação' 
        ORDER BY status, progresso DESC
    """)
    if mun_id:
        ids = _nearby_ids(mun_id, 4)
        placeholders = ','.join(['%s'] * len(ids))
        empregos = query_db(f"""
            SELECT setor_descricao, SUM(saldo) as saldo_total, SUM(estoque) as estoque_total,
                   AVG(salario_medio) as salario_medio
            FROM dev_eco_empregos 
            WHERE ano = YEAR(CURDATE()) AND municipio_id IN ({placeholders})
            GROUP BY setor_descricao
            ORDER BY estoque_total DESC
            LIMIT 10
        """, tuple(ids))
    else:
        empregos = query_db("""
            SELECT setor_descricao, SUM(saldo) as saldo_total, SUM(estoque) as estoque_total,
                   AVG(salario_medio) as salario_medio
            FROM dev_eco_empregos 
            WHERE ano = YEAR(CURDATE())
            GROUP BY setor_descricao
            ORDER BY estoque_total DESC
            LIMIT 10
        """)
    return render_template('dev_economico/qualificacao.html',
        programas=programas,
        empregos=empregos
    )

@dev_economico_bp.route('/infraestrutura')
@login_required
def infraestrutura():
    """Infraestrutura Estratégica"""
    projetos = query_db("SELECT * FROM dev_eco_infraestrutura ORDER BY status, tipo")
    programas = query_db("""
        SELECT * FROM dev_eco_programas 
        WHERE eixo = 'Infraestrutura' 
        ORDER BY status, progresso DESC
    """)
    return render_template('dev_economico/infraestrutura.html',
        projetos=projetos,
        programas=programas
    )

@dev_economico_bp.route('/compras')
@login_required
def compras():
    """Compras Governamentais como Fomento"""
    programas = query_db("""
        SELECT * FROM dev_eco_programas 
        WHERE eixo = 'Compras' 
        ORDER BY status, progresso DESC
    """)
    return render_template('dev_economico/compras.html', programas=programas)

@dev_economico_bp.route('/governanca')
@login_required
def governanca():
    """Governança e Indicadores"""
    indicadores = query_db("SELECT * FROM dev_eco_indicadores ORDER BY categoria, nome")
    programas = query_db("SELECT * FROM dev_eco_programas ORDER BY eixo, status")
    
    # Resumo por eixo
    resumo_eixos = query_db("""
        SELECT eixo, 
               COUNT(*) as total,
               SUM(CASE WHEN status = 'Concluído' THEN 1 ELSE 0 END) as concluidos,
               SUM(CASE WHEN status = 'Em Andamento' THEN 1 ELSE 0 END) as em_andamento,
               AVG(progresso) as progresso_medio
        FROM dev_eco_programas
        GROUP BY eixo
        ORDER BY eixo
    """)
    return render_template('dev_economico/governanca.html',
        indicadores=indicadores,
        programas=programas,
        resumo_eixos=resumo_eixos
    )

@dev_economico_bp.route('/metodologia')
@login_required
def metodologia():
    """Metodologia — como são calculados o IAEM e os Gaps"""
    return render_template('dev_economico/metodologia.html')

# ============================================================
# APIs JSON para gráficos dinâmicos
# ============================================================

@dev_economico_bp.route('/api/municipios')
@login_required
def api_municipios():
    """API: Lista de municípios com dados econômicos"""
    municipios = query_db("SELECT * FROM dev_eco_municipios WHERE ativo = TRUE ORDER BY nome")
    return jsonify(municipios)

@dev_economico_bp.route('/api/pib-setorial')
@login_required
def api_pib_setorial():
    """API: PIB por setor"""
    dados = query_db("""
        SELECT 
            SUM(pib_agropecuaria) as agropecuaria,
            SUM(pib_industria) as industria,
            SUM(pib_servicos) as servicos,
            SUM(pib_administracao) as administracao
        FROM dev_eco_municipios WHERE ativo = TRUE
    """, fetchone=True)
    return jsonify(dados)

@dev_economico_bp.route('/api/cadeias-produtivas')
@login_required
def api_cadeias():
    """API: Cadeias produtivas"""
    cadeias = query_db("SELECT * FROM dev_eco_cadeias_produtivas WHERE ativo = TRUE ORDER BY participacao_pib DESC")
    return jsonify(cadeias)

@dev_economico_bp.route('/api/indicadores')
@login_required
def api_indicadores():
    """API: Indicadores de governança"""
    indicadores = query_db("SELECT * FROM dev_eco_indicadores ORDER BY categoria")
    return jsonify(indicadores)

@dev_economico_bp.route('/api/municipio/<int:municipio_id>')
@login_required
def api_municipio_detalhe(municipio_id):
    """API: Detalhes de um município"""
    municipio = query_db("SELECT * FROM dev_eco_municipios WHERE id = %s", (municipio_id,), fetchone=True)
    if not municipio:
        return jsonify({'error': 'Município não encontrado'}), 404
    
    empregos = query_db("""
        SELECT * FROM dev_eco_empregos 
        WHERE municipio_id = %s 
        ORDER BY ano DESC, mes DESC
    """, (municipio_id,))
    
    investimentos = query_db("""
        SELECT * FROM dev_eco_investimentos 
        WHERE municipio_id = %s 
        ORDER BY ano DESC
    """, (municipio_id,))
    
    return jsonify({
        'municipio': municipio,
        'empregos': empregos,
        'investimentos': investimentos
    })

@dev_economico_bp.route('/api/ranking')
@login_required
def api_ranking():
    """API: Ranking de municípios"""
    criterio = request.args.get('criterio', 'pib_total')
    allowed = ['pib_total', 'pib_per_capita', 'populacao', 'idhm']
    if criterio not in allowed:
        criterio = 'pib_total'
    
    ranking = query_db(f"""
        SELECT nome, {criterio} as valor, regiao_macro
        FROM dev_eco_municipios 
        WHERE ativo = TRUE 
        ORDER BY {criterio} DESC 
        LIMIT 20
    """)
    return jsonify(ranking)

# ============================================================
# MÓDULOS PREMIUM
# ============================================================

@dev_economico_bp.route('/iaem')
@login_required
def iaem():
    """IAEM - Índice de Antecipação Econômica Municipal"""
    ranking = query_db("""
        SELECT i.*, m.nome, m.vocacao_principal, m.regiao_macro, m.populacao, m.pib_total
        FROM dev_eco_iaem i
        JOIN dev_eco_municipios m ON i.municipio_id = m.id
        ORDER BY i.iaem_score DESC
        LIMIT 20
    """)
    
    contagens = query_db("""
        SELECT iaem_classificacao, COUNT(*) as qtd
        FROM dev_eco_iaem
        GROUP BY iaem_classificacao
    """)
    
    classificacao = {r['iaem_classificacao']: r['qtd'] for r in contagens}
    
    medias = query_db("""
        SELECT AVG(prob_crescimento_6m) as m6, AVG(prob_crescimento_12m) as m12, AVG(prob_crescimento_24m) as m24
        FROM dev_eco_iaem
    """, fetchone=True)
    
    total = query_db("SELECT COUNT(*) as total FROM dev_eco_iaem", fetchone=True)
    data_calc = query_db("SELECT MAX(data_calculo) as dt FROM dev_eco_iaem", fetchone=True)
    
    return render_template('dev_economico/iaem.html',
        ranking=ranking,
        expansao_forte=classificacao.get('Expansão Forte', 0),
        expansao=classificacao.get('Expansão', 0),
        estavel=classificacao.get('Estável', 0),
        retracao=classificacao.get('Retração', 0) + classificacao.get('Retração Forte', 0),
        media_prob_6m=medias['m6'] or 0 if medias else 0,
        media_prob_12m=medias['m12'] or 0 if medias else 0,
        media_prob_24m=medias['m24'] or 0 if medias else 0,
        total_municipios=total['total'] if total else 0,
        data_calculo=data_calc['dt'] if data_calc else None
    )

@dev_economico_bp.route('/encadeamento')
@login_required
def encadeamento():
    """Mapa de Encadeamento Produtivo Latente"""
    oportunidades = query_db("""
        SELECT e.*, m.nome as municipio_nome
        FROM dev_eco_encadeamento_latente e
        JOIN dev_eco_municipios m ON e.municipio_id = m.id
        ORDER BY e.prioridade = 'Crítica' DESC, e.viabilidade = 'Alta' DESC, e.gap_valor DESC
    """)
    
    totais = query_db("""
        SELECT 
            SUM(gap_valor) as gap_total,
            SUM(empregos_potenciais) as empregos_total,
            SUM(investimento_estimado) as investimento_total,
            SUM(CASE WHEN viabilidade = 'Alta' THEN 1 ELSE 0 END) as viab_alta,
            SUM(CASE WHEN prioridade = 'Crítica' THEN 1 ELSE 0 END) as prio_critica
        FROM dev_eco_encadeamento_latente
    """, fetchone=True)
    
    return render_template('dev_economico/encadeamento.html',
        oportunidades=oportunidades,
        gap_total=totais['gap_total'] or 0 if totais else 0,
        empregos_potenciais_total=totais['empregos_total'] or 0 if totais else 0,
        investimento_total=totais['investimento_total'] or 0 if totais else 0,
        viabilidade_alta=totais['viab_alta'] or 0 if totais else 0,
        prioridade_critica=totais['prio_critica'] or 0 if totais else 0
    )

@dev_economico_bp.route('/simulador')
@login_required
def simulador():
    """Simulador de Impacto Econômico"""
    municipios = query_db("""
        SELECT m.id, m.nome, m.pib_total, m.populacao,
               (SELECT COUNT(*) + 1 FROM dev_eco_municipios m2 WHERE m2.pib_total > m.pib_total AND m2.ativo = TRUE) as ranking
        FROM dev_eco_municipios m
        WHERE m.ativo = TRUE
        ORDER BY m.nome
    """)
    
    multiplicadores = query_db("SELECT * FROM dev_eco_multiplicadores ORDER BY setor")
    
    simulacoes = query_db("""
        SELECT s.*, m.nome as municipio_nome
        FROM dev_eco_simulacoes s
        JOIN dev_eco_municipios m ON s.municipio_id = m.id
        ORDER BY s.data_simulacao DESC
        LIMIT 10
    """)
    
    return render_template('dev_economico/simulador.html',
        municipios=municipios,
        multiplicadores=multiplicadores,
        simulacoes=simulacoes
    )

@dev_economico_bp.route('/api/simular', methods=['POST'])
@login_required
def api_simular():
    """API: Salvar resultado de simulação"""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Dados inválidos'}), 400
    
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO dev_eco_simulacoes 
            (municipio_id, usuario, tipo_empreendimento, setor, investimento_total, porte,
             empregos_diretos, empregos_indiretos, empregos_totais, impacto_pib_anual,
             impacto_renda_anual, impacto_tributos_anual, impacto_pix_mensal,
             variacao_pib_municipal, novo_ranking_estadual, ranking_anterior)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            data.get('municipio_id'), session.get('username', 'anon'),
            data.get('tipo_empreendimento', ''), data.get('setor', ''),
            data.get('investimento_total', 0), data.get('porte', 'Médio'),
            data.get('empregos_diretos', 0), data.get('empregos_indiretos', 0),
            data.get('empregos_totais', 0), data.get('impacto_pib_anual', 0),
            data.get('impacto_renda_anual', 0), data.get('impacto_tributos_anual', 0),
            data.get('impacto_pix_mensal', 0), data.get('variacao_pib_municipal', 0),
            data.get('novo_ranking_estadual', 0), data.get('ranking_anterior', 0)
        ))
        conn.commit()
        return jsonify({'success': True, 'id': cursor.lastrowid})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@dev_economico_bp.route('/api/iaem/ranking')
@login_required
def api_iaem_ranking():
    """API: Ranking IAEM completo"""
    ranking = query_db("""
        SELECT i.iaem_score, i.iaem_classificacao, i.prob_crescimento_6m, i.tendencia,
               i.score_pix, i.score_empresas, i.score_emprego, i.score_uso_solo,
               i.score_exportacao, i.score_logistica,
               m.nome, m.regiao_macro, m.vocacao_principal
        FROM dev_eco_iaem i
        JOIN dev_eco_municipios m ON i.municipio_id = m.id
        ORDER BY i.iaem_score DESC
    """)
    return jsonify(ranking)

# ============================================================
# APIs DINÂMICAS — Dashboard Interativo (estilo Tableau)
# ============================================================

@dev_economico_bp.route('/api/debug-iaem')
def api_debug_iaem():
    """Endpoint público: retorna todos os municípios com IAEM (sem login)"""
    municipios = query_db("""
        SELECT m.id, m.codigo_ibge, m.nome, m.regiao_macro, m.mesorregiao,
               m.populacao, m.pib_total, m.pib_per_capita, m.idhm,
               m.pib_agropecuaria, m.pib_industria, m.pib_servicos, m.pib_administracao,
               m.vocacao_principal, m.latitude, m.longitude,
               COALESCE(i.iaem_score, 0.0) as iaem_score,
               COALESCE(i.iaem_classificacao, 'N/D') as iaem_classificacao,
               COALESCE(i.prob_crescimento_6m, 0.0) as prob_6m,
               COALESCE(i.prob_crescimento_12m, 0.0) as prob_12m,
               COALESCE(i.prob_crescimento_24m, 0.0) as prob_24m,
               COALESCE(i.tendencia, 'N/D') as tendencia,
               COALESCE(i.score_pix, 0.0) as score_pix,
               COALESCE(i.score_empresas, 0.0) as score_empresas,
               COALESCE(i.score_emprego, 0.0) as score_emprego,
               COALESCE(i.score_uso_solo, 0.0) as score_uso_solo,
               COALESCE(i.score_exportacao, 0.0) as score_exportacao,
               COALESCE(i.score_logistica, 0.0) as score_logistica,
               COALESCE(i.setor_destaque, '') as setor_destaque
        FROM dev_eco_municipios m
        LEFT JOIN dev_eco_iaem i ON m.id = i.municipio_id
        WHERE m.ativo = TRUE
        ORDER BY m.nome
    """)
    return jsonify(municipios)

@dev_economico_bp.route('/api/municipios')
@login_required
def api_municipios_lista():
    """API: Lista completa de municípios para filtros"""
    municipios = query_db("""
        SELECT m.id, m.codigo_ibge, m.nome, m.regiao_macro, m.mesorregiao,
               m.populacao, m.pib_total, m.pib_per_capita, m.idhm,
               m.pib_agropecuaria, m.pib_industria, m.pib_servicos, m.pib_administracao,
               m.vocacao_principal, m.latitude, m.longitude,
               COALESCE(i.iaem_score, 0.0) as iaem_score,
               COALESCE(i.iaem_classificacao, 'N/D') as iaem_classificacao,
               COALESCE(i.prob_crescimento_6m, 0.0) as prob_6m,
               COALESCE(i.prob_crescimento_12m, 0.0) as prob_12m,
               COALESCE(i.prob_crescimento_24m, 0.0) as prob_24m,
               COALESCE(i.tendencia, 'N/D') as tendencia,
               COALESCE(i.score_pix, 0.0) as score_pix,
               COALESCE(i.score_empresas, 0.0) as score_empresas,
               COALESCE(i.score_emprego, 0.0) as score_emprego,
               COALESCE(i.score_uso_solo, 0.0) as score_uso_solo,
               COALESCE(i.score_exportacao, 0.0) as score_exportacao,
               COALESCE(i.score_logistica, 0.0) as score_logistica,
               COALESCE(i.setor_destaque, '') as setor_destaque
        FROM dev_eco_municipios m
        LEFT JOIN dev_eco_iaem i ON m.id = i.municipio_id
        WHERE m.ativo = TRUE
        ORDER BY m.nome
    """)
    # Debug: verificar primeiro resultado
    if municipios:
        m0 = municipios[0]
        print(f"[API /municipios] Primeiro: {m0.get('nome')} IAEM={m0.get('iaem_score')} tipo={type(m0.get('iaem_score')).__name__} Prob6m={m0.get('prob_6m')}")
        print(f"[API /municipios] Total: {len(municipios)} com IAEM>0: {sum(1 for m in municipios if m.get('iaem_score',0)>0)}")
    return jsonify(municipios)

@dev_economico_bp.route('/api/municipio/<int:mun_id>/completo')
def api_municipio_completo(mun_id):
    """API: Dados completos de um município (painel do secretário)"""
    mun = query_db("SELECT * FROM dev_eco_municipios WHERE id = %s", (mun_id,), fetchone=True)
    if not mun:
        return jsonify({'error': 'Município não encontrado'}), 404

    iaem = query_db("""
        SELECT * FROM dev_eco_iaem WHERE municipio_id = %s
        ORDER BY data_calculo DESC LIMIT 1
    """, (mun_id,), fetchone=True)

    encadeamentos = query_db("""
        SELECT * FROM dev_eco_encadeamento_latente WHERE municipio_id = %s
        ORDER BY prioridade = 'Crítica' DESC, gap_valor DESC
    """, (mun_id,))

    programas = query_db("""
        SELECT * FROM dev_eco_programas WHERE municipio_id = %s
        ORDER BY status, progresso DESC
    """, (mun_id,))

    # Ranking do município
    ranking_pib = query_db("""
        SELECT COUNT(*) + 1 as pos FROM dev_eco_municipios
        WHERE pib_total > (SELECT pib_total FROM dev_eco_municipios WHERE id = %s) AND ativo = TRUE
    """, (mun_id,), fetchone=True)

    ranking_iaem = query_db("""
        SELECT COUNT(*) + 1 as pos FROM dev_eco_iaem
        WHERE iaem_score > COALESCE((SELECT iaem_score FROM dev_eco_iaem WHERE municipio_id = %s ORDER BY data_calculo DESC LIMIT 1), 0)
    """, (mun_id,), fetchone=True)

    # PIB setorial do município vs estado
    estado = query_db("""
        SELECT SUM(pib_agropecuaria) as agro, SUM(pib_industria) as ind,
               SUM(pib_servicos) as serv, SUM(pib_administracao) as adm, SUM(pib_total) as total
        FROM dev_eco_municipios WHERE ativo = TRUE
    """, fetchone=True)

    # Municípios vizinhos (mesma mesorregião)
    vizinhos = query_db("""
        SELECT id, nome, pib_total, populacao, vocacao_principal,
               COALESCE((SELECT iaem_score FROM dev_eco_iaem WHERE municipio_id = m.id ORDER BY data_calculo DESC LIMIT 1), 0) as iaem_score
        FROM dev_eco_municipios m
        WHERE mesorregiao = %s AND id != %s AND ativo = TRUE
        ORDER BY pib_total DESC LIMIT 8
    """, (mun.get('mesorregiao'), mun_id))

    return jsonify({
        'municipio': mun,
        'iaem': iaem,
        'encadeamentos': encadeamentos,
        'programas': programas,
        'ranking_pib': ranking_pib['pos'] if ranking_pib else 0,
        'ranking_iaem': ranking_iaem['pos'] if ranking_iaem else 0,
        'estado_pib': estado,
        'vizinhos': vizinhos
    })

@dev_economico_bp.route('/api/oportunidades-estado')
def api_oportunidades_estado():
    """API: Top oportunidades de encadeamento produtivo do estado inteiro"""
    encs = query_db("""
        SELECT e.*, m.nome as municipio_nome
        FROM dev_eco_encadeamento_latente e
        JOIN dev_eco_municipios m ON e.municipio_id = m.id
        ORDER BY e.gap_valor DESC
        LIMIT 20
    """)
    return jsonify(encs)

@dev_economico_bp.route('/api/visao-geral')
@login_required
def api_visao_geral():
    """API: Dados agregados para visão geral do estado"""
    totais = query_db("""
        SELECT SUM(populacao) as pop, SUM(pib_total) as pib, AVG(pib_per_capita) as pib_pc,
               AVG(idhm) as idhm, COUNT(*) as qtd,
               SUM(pib_agropecuaria) as agro, SUM(pib_industria) as ind,
               SUM(pib_servicos) as serv, SUM(pib_administracao) as adm
        FROM dev_eco_municipios WHERE ativo = TRUE
    """, fetchone=True)

    iaem_dist = query_db("""
        SELECT iaem_classificacao as cls, COUNT(*) as qtd
        FROM dev_eco_iaem GROUP BY iaem_classificacao
    """)

    top_iaem = query_db("""
        SELECT m.nome, i.iaem_score, i.iaem_classificacao, i.tendencia, m.vocacao_principal
        FROM dev_eco_iaem i JOIN dev_eco_municipios m ON i.municipio_id = m.id
        ORDER BY i.iaem_score DESC LIMIT 10
    """)

    cadeias = query_db("""
        SELECT * FROM dev_eco_cadeias_produtivas WHERE ativo = TRUE ORDER BY participacao_pib DESC
    """)

    indicadores = query_db("SELECT * FROM dev_eco_indicadores ORDER BY categoria")

    return jsonify({
        'totais': totais,
        'iaem_distribuicao': iaem_dist,
        'top_iaem': top_iaem,
        'cadeias': cadeias,
        'indicadores': indicadores
    })
