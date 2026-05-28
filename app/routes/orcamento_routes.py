# -*- coding: utf-8 -*-
"""
Rotas do Módulo de Orçamentos
Gerencia criação, aprovação e conversão de orçamentos em pedidos
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session, make_response
from datetime import datetime, timedelta
from decimal import Decimal
import json

# Importações do projeto
try:
    from app.database import get_db
    from app.utils.auth import login_required, get_usuario_logado
    from app.utils.search_utils import parse_star_search, build_multi_part_like_where
    from app.utils.permissoes_helper import tem_permissao
    from app.services.exchange_rate_service import ExchangeRateService
except ImportError:
    from database import get_db
    from utils.search_utils import parse_star_search, build_multi_part_like_where
    from utils.permissoes_helper import tem_permissao
    from services.exchange_rate_service import ExchangeRateService
from functools import wraps
from flask import flash

# Decorators para permissões granulares de orçamentos
def orcamento_visualizar_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('Por favor, faça login para acessar esta página.', 'danger')
            return redirect(url_for('login'))
        if not tem_permissao('vendas.orcamentos', 'visualizar'):
            flash('Você não tem permissão para visualizar orçamentos.', 'danger')
            return redirect(url_for('bem_vindo'))
        return f(*args, **kwargs)
    return decorated_function

def orcamento_criar_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('Por favor, faça login para acessar esta página.', 'danger')
            return redirect(url_for('login'))
        if not tem_permissao('vendas.orcamentos', 'criar'):
            flash('Você não tem permissão para criar orçamentos.', 'danger')
            return redirect(url_for('orcamentos.lista'))
        return f(*args, **kwargs)
    return decorated_function

def orcamento_editar_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('Por favor, faça login para acessar esta página.', 'danger')
            return redirect(url_for('login'))
        if not tem_permissao('vendas.orcamentos', 'editar'):
            flash('Você não tem permissão para editar orçamentos.', 'danger')
            return redirect(url_for('orcamentos.lista'))
        return f(*args, **kwargs)
    return decorated_function

def orcamento_excluir_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('Por favor, faça login para acessar esta página.', 'danger')
            return redirect(url_for('login'))
        if not tem_permissao('vendas.orcamentos', 'excluir'):
            flash('Você não tem permissão para excluir orçamentos.', 'danger')
            return redirect(url_for('orcamentos.lista'))
        return f(*args, **kwargs)
    return decorated_function

# Criar Blueprint
orcamento_bp = Blueprint('orcamentos', __name__, url_prefix='/orcamentos')


# =====================================================
# FUNÇÕES AUXILIARES
# =====================================================

def get_usuario_logado():
    """Retorna o ID do usuário logado"""
    return session.get('user_id', 1)

def formatar_data(data):
    """Formata data para o padrão brasileiro"""
    if data is None:
        return ""
    if isinstance(data, str):
        try:
            data = datetime.strptime(data, "%Y-%m-%d")
        except:
            return data
    return data.strftime("%d/%m/%Y")

def get_empresa_padrao():
    """Retorna o ID da empresa padrão"""
    return session.get('empresa_id', 1)


def calcular_fx_para_empresa(db, empresa_id):
    """Calcula a taxa de câmbio base -> moeda funcional da empresa.

    Usa o ExchangeRateService configurado no sistema. Retorna um dict com:
      - base_currency
      - target_currency
      - rate_date (datetime.date)
      - rate_value (float)
      - rate_source (str)

    Em caso de erro ou se a empresa não tiver moeda funcional, retorna None.
    """
    if not empresa_id:
        return None

    try:
        empresa = db.fetch_one(
            "SELECT moeda_funcional FROM empresas WHERE id = %s",
            (empresa_id,),
        )
    except Exception as e:
        print(f"[ORCAMENTO FX] Erro ao buscar empresa {empresa_id}: {e}")
        return None

    if not empresa:
        return None

    moeda_funcional = (empresa.get('moeda_funcional') or '').strip().upper()[:3]
    if not moeda_funcional:
        return None

    try:
        svc = ExchangeRateService()
        rate_date = datetime.now().date()
        rate_value = svc.get_rate(rate_date, moeda_funcional)
        return {
            'base_currency': svc.base_currency.upper(),
            'target_currency': moeda_funcional,
            'rate_date': rate_date,
            'rate_value': float(rate_value),
            'rate_source': 'ExchangeRatesAPI.io',
        }
    except Exception as e:
        # Não impedir o salvamento do orçamento por falha de câmbio; apenas registrar aviso
        print(f"[ORCAMENTO FX] Erro ao obter taxa de câmbio para empresa {empresa_id} ({moeda_funcional}): {e}")
        return None

def formatar_moeda(valor):
    """Formata valor para moeda brasileira"""
    if valor is None:
        return "R$ 0,00"
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _buscar_template_ativo_produto(db, produto_id):
    return db.fetch_one("""
        SELECT id, versao, nome_template, custo_total_base, tempo_producao_horas
        FROM produto_templates_producao
        WHERE produto_id = %s AND ativo = 1
        LIMIT 1
    """, (produto_id,))


def _copiar_itens_template_para_op(db, op_id, template_id, quantidade_produto_final):
    """Copia os itens do template para a OP, multiplicando pela quantidade do produto final."""
    itens_template = db.fetch_all("""
        SELECT
            ti.tipo_item,
            ti.produto_id,
            ti.descricao,
            ti.quantidade,
            ti.unidade_medida,
            ti.custo_unitario_base
        FROM produto_template_itens ti
        WHERE ti.template_id = %s
        ORDER BY ti.tipo_item, ti.id
    """, (template_id,)) or []

    custo_total_atual = Decimal('0')

    for it in itens_template:
        prod = db.fetch_one("SELECT name, unit_measure, cost_price FROM products WHERE id = %s", (it['produto_id'],))
        if not prod:
            continue

        qtd_base = Decimal(str(it.get('quantidade') or 0))
        qtd_final = (qtd_base * Decimal(str(quantidade_produto_final or 0))).quantize(Decimal('0.0001'))
        custo_unit_atual = Decimal(str(prod.get('cost_price') or 0))
        custo_total_item = (qtd_final * custo_unit_atual).quantize(Decimal('0.01'))

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
            str(qtd_final),
            (it.get('unidade_medida') or prod.get('unit_measure')),
            it.get('custo_unitario_base'),
            str(custo_unit_atual),
            str(custo_total_item)
        ))

    db.execute_query("""
        UPDATE ordens_producao
        SET custo_total_atual = %s
        WHERE id = %s
    """, (str(custo_total_atual), op_id))

    return custo_total_atual


def _gerar_contas_receber_para_orcamento(db, orcamento_id):
    """Gera uma conta a receber e suas parcelas a partir de um orçamento aprovado.

    Regras principais:
    - Usa as duplicatas de orcamento_duplicatas como base para as parcelas.
    - Define a moeda do título como a moeda funcional da empresa (empresas.moeda_funcional)
      quando existir; caso contrário, usa BRL.
    - Grava também valores convertidos para a moeda base do sistema (ExchangeRateService.base_currency).
    - Seleciona a conta bancária a partir da forma de pagamento (payment_methods_config.bank_account_id)
      e, em último caso, da empresa (empresas.bank_account_id).
    """
    # Verificar se a coluna bank_account_id existe na tabela empresas
    has_empresas_bank_account = False
    try:
        col_info = db.fetch_one(
            """
            SELECT COUNT(*) AS cnt
            FROM information_schema.columns
            WHERE table_schema = DATABASE()
              AND table_name = 'empresas'
              AND column_name = 'bank_account_id'
            """
        )
        has_empresas_bank_account = bool(col_info and int(col_info.get('cnt') or 0) > 0)
    except Exception:
        has_empresas_bank_account = False

    try:
        if has_empresas_bank_account:
            orc = db.fetch_one(
                """
                SELECT 
                    o.id,
                    o.numero,
                    o.cliente_id,
                    o.empresa_id,
                    o.valor_total,
                    o.data_emissao,
                    o.data_validade,
                    o.forma_pagamento_id,
                    e.moeda_funcional,
                    e.bank_account_id AS empresa_bank_account_id
                FROM orcamentos o
                LEFT JOIN empresas e ON o.empresa_id = e.id
                WHERE o.id = %s
                """,
                [orcamento_id],
            )
        else:
            orc = db.fetch_one(
                """
                SELECT 
                    o.id,
                    o.numero,
                    o.cliente_id,
                    o.empresa_id,
                    o.valor_total,
                    o.data_emissao,
                    o.data_validade,
                    o.forma_pagamento_id,
                    e.moeda_funcional,
                    NULL AS empresa_bank_account_id
                FROM orcamentos o
                LEFT JOIN empresas e ON o.empresa_id = e.id
                WHERE o.id = %s
                """,
                [orcamento_id],
            )
    except Exception as e:
        print(f"[ORCAMENTO->CR] Erro ao buscar dados do orcamento {orcamento_id}: {e}")
        return

    if not orc:
        print(f"[ORCAMENTO->CR] Orcamento {orcamento_id} não encontrado, não gerando contas a receber.")
        return

    if not orc.get('cliente_id'):
        print(f"[ORCAMENTO->CR] Orcamento {orcamento_id} sem cliente, não gerando contas a receber.")
        return

    # Buscar duplicatas (parcelas) do orçamento
    try:
        duplicatas = db.fetch_all(
            """
            SELECT numero, vencimento, valor
            FROM orcamento_duplicatas
            WHERE orcamento_id = %s AND status <> 'cancelado'
            ORDER BY numero
            """,
            [orcamento_id],
        ) or []
    except Exception as e:
        print(f"[ORCAMENTO->CR] Erro ao buscar duplicatas do orcamento {orcamento_id}: {e}")
        duplicatas = []

    from datetime import date as _date

    if not duplicatas:
        # Fallback: criar uma única parcela com o valor total
        duplicatas = [{
            'numero': 1,
            'vencimento': orc.get('data_validade') or orc.get('data_emissao') or _date.today(),
            'valor': orc.get('valor_total') or 0,
        }]

    installments = len(duplicatas)

    # Forma de pagamento / conta bancária
    forma_pagamento_id = orc.get('forma_pagamento_id')
    pm_config = None
    if forma_pagamento_id:
        try:
            pm_config = db.fetch_one(
                "SELECT id, code, name, bank_account_id FROM payment_methods_config WHERE id = %s",
                [forma_pagamento_id],
            )
        except Exception as e:
            print(f"[ORCAMENTO->CR] Erro ao buscar payment_methods_config {forma_pagamento_id}: {e}")

    bank_account_id = None
    if pm_config and pm_config.get('bank_account_id'):
        bank_account_id = pm_config['bank_account_id']
    if not bank_account_id:
        bank_account_id = orc.get('empresa_bank_account_id')

    if not bank_account_id:
        print(f"[ORCAMENTO->CR] Orcamento {orcamento_id} sem conta bancária vinculada, não gerando contas a receber.")
        return

    pm_code = (pm_config.get('code') if pm_config else '') or ''
    pm_code_lower = pm_code.lower()
    allowed_pm = {'cash', 'credit_card', 'debit_card', 'pix', 'boleto', 'transfer', 'check'}
    if pm_code_lower in allowed_pm:
        payment_method = pm_code_lower
    else:
        payment_method = 'other'

    # Moeda e câmbio
    from decimal import Decimal

    moeda_funcional = (orc.get('moeda_funcional') or '').strip().upper()[:3]
    try:
        svc = ExchangeRateService()
        base_currency = svc.base_currency.upper()
    except Exception as e:
        print(f"[ORCAMENTO->CR] Aviso: falha ao instanciar ExchangeRateService: {e}")
        svc = None
        base_currency = 'BRL'

    currency_code = moeda_funcional or base_currency or 'BRL'

    # Precisamos apenas da taxa fx_rate_to_base; os valores em moeda serão calculados por parcela
    total_amount_currency = Decimal(str(orc.get('valor_total') or 0))
    fx_rate_to_base = Decimal('1')
    total_amount_base = total_amount_currency

    rate_date = orc.get('data_emissao') or _date.today()

    if svc and currency_code != base_currency:
        try:
            rate_base_to_target = Decimal(str(svc.get_rate(rate_date, currency_code)))
            if rate_base_to_target != 0:
                # 1 target = 1 / rate_base_to_target base
                fx_rate_to_base = (Decimal('1') / rate_base_to_target).quantize(Decimal('0.00000001'))
                total_amount_base = (total_amount_currency * fx_rate_to_base).quantize(Decimal('0.01'))
        except Exception as e:
            print(f"[ORCAMENTO->CR] Erro ao obter taxa de câmbio para {currency_code} em {rate_date}: {e}")
            fx_rate_to_base = Decimal('1')
            total_amount_base = total_amount_currency

    issue_date = orc.get('data_emissao') or rate_date

    # Gerar UMA conta a receber para CADA duplicata (parcela), com installments=1
    generated_ids = []
    descricao_base = f"Orçamento {orc.get('numero') or orcamento_id}"
    observacao_base = f"Gerado automaticamente a partir do orçamento {orc.get('numero') or orcamento_id}."

    for dup in duplicatas:
        try:
            numero_parcela = int(dup.get('numero') or 1)
        except Exception:
            numero_parcela = 1

        valor_parcela = Decimal(str(dup.get('valor') or 0))
        amount_currency = valor_parcela
        amount_base = (amount_currency * fx_rate_to_base).quantize(Decimal('0.01'))
        vencimento = dup.get('vencimento') or rate_date

        descricao = f"{descricao_base} - Parcela {numero_parcela}"
        observacao = observacao_base

        # Criar o título principal (conta a receber) para esta parcela
        try:
            receivable_id = db.insert(
                """
                INSERT INTO accounts_receivable (
                    customer_id, invoice_number, description, total_amount,
                    installments, issue_date, due_date, payment_method,
                    bank_account_id, status, notes, origin,
                    company_id, total_amount_currency, fx_rate_to_base, total_amount_base, currency_code
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    orc['cliente_id'],
                    orc.get('numero'),
                    descricao,
                    str(amount_currency),
                    1,  # cada título representa uma única parcela
                    issue_date,
                    vencimento,
                    payment_method,
                    bank_account_id,
                    'pending',
                    observacao,
                    'sale',
                    orc.get('empresa_id'),
                    str(amount_currency),
                    str(fx_rate_to_base),
                    str(amount_base),
                    currency_code,
                ),
            )
        except Exception as e:
            print(f"[ORCAMENTO->CR] Erro ao criar conta a receber (parcela {numero_parcela}) para orcamento {orcamento_id}: {e}")
            continue

        if not receivable_id:
            print(f"[ORCAMENTO->CR] Falha ao criar conta a receber (parcela {numero_parcela}) para orcamento {orcamento_id}.")
            continue

        generated_ids.append(receivable_id)

        # Criar a parcela vinculada a este título (sempre 1/1)
        try:
            db.insert(
                """
                INSERT INTO receivable_installments (
                    receivable_id, installment_number, amount,
                    amount_currency, fx_rate_to_base, amount_base,
                    due_date, status
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    receivable_id,
                    1,
                    str(amount_currency),
                    str(amount_currency),
                    str(fx_rate_to_base),
                    str(amount_base),
                    vencimento,
                    'pending',
                ),
            )
        except Exception as e:
            print(f"[ORCAMENTO->CR] Erro ao criar parcela (1/1) para conta a receber {receivable_id} do orcamento {orcamento_id}: {e}")

    if generated_ids:
        print(f"[ORCAMENTO->CR] {len(generated_ids)} conta(s) a receber geradas para orcamento {orcamento_id}: IDs {generated_ids}.")
    else:
        print(f"[ORCAMENTO->CR] Nenhuma conta a receber gerada para orcamento {orcamento_id} apesar de existirem duplicatas.")


def _verificar_estoque_disponivel(db, produto_id, quantidade_necessaria):
    """
    Verifica estoque disponível para um produto (próprio + DNA similar).
    Retorna dict com estoque encontrado e quantidades.
    """
    resultado = {
        'estoque_proprio': 0,
        'estoque_similar': [],
        'total_disponivel': 0,
        'quantidade_necessaria': float(quantidade_necessaria or 0),
        'atende_total': False,
        'quantidade_faltante': float(quantidade_necessaria or 0)
    }
    
    # 1. Buscar estoque próprio do produto
    estoque_proprio = db.fetch_one("""
        SELECT 
            COALESCE(p.stock_quantity, 0) AS estoque_total,
            COALESCE(
                (SELECT SUM(er.quantidade) FROM estoque_reservas er 
                 WHERE er.produto_id = p.id AND er.status IN ('ativo', 'confirmado')), 0
            ) AS reservado
        FROM products p
        WHERE p.id = %s
    """, (produto_id,))
    
    if estoque_proprio:
        disp = float(estoque_proprio['estoque_total'] or 0) - float(estoque_proprio['reservado'] or 0)
        resultado['estoque_proprio'] = max(0, disp)
        resultado['total_disponivel'] = resultado['estoque_proprio']
    
    # 2. Buscar especificações do produto para match DNA
    esp = db.fetch_one("""
        SELECT codigo_dna, tipo_correia_id, material_base_id, largura_mm, comprimento_mm
        FROM produto_especificacoes_tecnicas
        WHERE produto_id = %s
    """, (produto_id,))
    
    # 3. Se tem especificação, buscar produtos similares com estoque
    if esp and esp.get('tipo_correia_id'):
        similares = db.fetch_all("""
            SELECT 
                p.id AS produto_id,
                p.name AS produto_nome,
                p.internal_code AS codigo_interno,
                COALESCE(p.stock_quantity, 0) - COALESCE(
                    (SELECT SUM(er.quantidade) FROM estoque_reservas er 
                     WHERE er.produto_id = p.id AND er.status IN ('ativo', 'confirmado')), 0
                ) AS estoque_disponivel,
                pet.codigo_dna,
                pet.largura_mm,
                pet.comprimento_mm,
                CASE 
                    WHEN pet.codigo_dna = %s THEN 'EXATO'
                    WHEN pet.largura_mm >= %s AND pet.comprimento_mm >= %s THEN 'DERIVAVEL'
                    ELSE 'SIMILAR'
                END AS tipo_match
            FROM products p
            INNER JOIN produto_especificacoes_tecnicas pet ON pet.produto_id = p.id
            WHERE p.id != %s
              AND p.active = 1
              AND pet.tipo_correia_id = %s
              AND pet.material_base_id = %s
              AND COALESCE(p.stock_quantity, 0) > 0
            HAVING estoque_disponivel > 0
            ORDER BY 
                CASE WHEN pet.codigo_dna = %s THEN 1 ELSE 2 END,
                pet.largura_mm DESC, pet.comprimento_mm DESC
            LIMIT 10
        """, (
            esp['codigo_dna'],
            esp['largura_mm'] or 0,
            esp['comprimento_mm'] or 0,
            produto_id,
            esp['tipo_correia_id'],
            esp['material_base_id'],
            esp['codigo_dna']
        ))
        
        for s in (similares or []):
            est_disp = float(s['estoque_disponivel'] or 0)
            if est_disp > 0:
                resultado['estoque_similar'].append({
                    'produto_id': s['produto_id'],
                    'produto_nome': s['produto_nome'],
                    'codigo_interno': s['codigo_interno'],
                    'estoque_disponivel': est_disp,
                    'codigo_dna': s['codigo_dna'],
                    'tipo_match': s['tipo_match'],
                    'largura_mm': float(s['largura_mm'] or 0),
                    'comprimento_mm': float(s['comprimento_mm'] or 0)
                })
                resultado['total_disponivel'] += est_disp
    
    # 4. Calcular se atende
    resultado['atende_total'] = resultado['total_disponivel'] >= resultado['quantidade_necessaria']
    resultado['quantidade_faltante'] = max(0, resultado['quantidade_necessaria'] - resultado['total_disponivel'])
    
    return resultado


def _criar_reserva_estoque(db, produto_id, quantidade, orcamento_id, observacao=""):
    """Cria uma reserva de estoque e BAIXA o estoque do produto."""
    try:
        # 1. Buscar estoque atual
        produto = db.fetch_one("SELECT stock_quantity FROM products WHERE id = %s", (produto_id,))
        estoque_anterior = float(produto['stock_quantity'] or 0) if produto else 0
        estoque_posterior = estoque_anterior - float(quantidade)
        
        # 2. Criar reserva
        reserva_id = db.insert("""
            INSERT INTO estoque_reservas (
                produto_id, quantidade, tipo_origem, origem_id,
                status, created_by, observacao, data_expiracao
            ) VALUES (%s, %s, 'orcamento', %s, 'confirmado', %s, %s, DATE_ADD(NOW(), INTERVAL 30 DAY))
        """, (produto_id, quantidade, orcamento_id, get_usuario_logado(), observacao))
        
        # 3. BAIXAR estoque do produto
        db.execute("""
            UPDATE products SET stock_quantity = stock_quantity - %s WHERE id = %s
        """, (quantidade, produto_id))
        
        # 4. Registrar movimentação de estoque
        try:
            db.insert("""
                INSERT INTO estoque_movimentacoes (
                    produto_id, tipo, quantidade, estoque_anterior, estoque_posterior,
                    referencia_tipo, referencia_id, observacao, created_by
                ) VALUES (%s, 'saida', %s, %s, %s, 'orcamento', %s, %s, %s)
            """, (
                produto_id, quantidade, estoque_anterior, estoque_posterior,
                orcamento_id, f"Reserva para orçamento #{orcamento_id}: {observacao}", get_usuario_logado()
            ))
        except Exception as e_mov:
            print(f"[MOVIMENTACAO] Aviso ao registrar: {e_mov}")
        
        print(f"[ESTOQUE] Produto {produto_id}: {estoque_anterior} -> {estoque_posterior} (-{quantidade})")
        return reserva_id
    except Exception as e:
        print(f"[RESERVA] Erro ao criar reserva: {e}")
        return None


def _gerar_ops_para_orcamento(db, orcamento_id, etapas_por_item=None):
    """
    Gera OPs para itens do orçamento com verificação inteligente de estoque.
    
    NOVO FLUXO:
    1. Para cada item, verifica estoque disponível (próprio + DNA similar)
    2. Se há estoque suficiente: cria OP de "Separação/Embalagem" + reserva estoque
    3. Se há estoque parcial: cria OP mista (parte separa, parte produz)
    4. Se não há estoque: cria OP de "Produção" normal
    
    Args:
        db: Conexão com banco de dados
        orcamento_id: ID do orçamento
        etapas_por_item: Dict {item_id: etapa_id} com etapas selecionadas pelo usuário
    
    Returns:
        dict: Informações detalhadas sobre OPs criadas e alocações
    """
    if etapas_por_item is None:
        etapas_por_item = {}
    resultado = {
        'ops_producao': 0,
        'ops_separacao': 0,
        'reservas_criadas': 0,
        'itens_processados': 0,
        'detalhes': []
    }
    
    orc = db.fetch_one("SELECT * FROM orcamentos WHERE id = %s", (orcamento_id,))
    if not orc:
        raise Exception("Orçamento não encontrado")

    grupo = db.fetch_one("SELECT id FROM orcamento_op_grupos WHERE orcamento_id = %s", (orcamento_id,))
    if grupo:
        grupo_id = grupo['id']
    else:
        grupo_id = db.insert("""
            INSERT INTO orcamento_op_grupos (
                orcamento_id, empresa_id, cliente_id, criado_por
            ) VALUES (%s, %s, %s, %s)
        """, (
            orcamento_id,
            orc.get('empresa_id'),
            orc.get('cliente_id'),
            get_usuario_logado()
        ))

    itens_orc = db.fetch_all("""
        SELECT
            oi.id,
            oi.produto_id,
            oi.quantidade,
            oi.unidade,
            oi.observacao,
            p.name AS produto_nome,
            pc.categoria_fiscal
        FROM orcamento_itens oi
        INNER JOIN products p ON p.id = oi.produto_id
        LEFT JOIN product_categories pc ON pc.id = p.category_id
        WHERE oi.orcamento_id = %s
        ORDER BY oi.sequencia, oi.id
    """, (orcamento_id,)) or []

    # Buscar etapas
    etapa_producao = db.fetch_one("""
        SELECT id FROM producao_etapas
        WHERE ativo = 1 AND (tipo_etapa = 'producao' OR tipo_etapa IS NULL)
        ORDER BY ordem, id LIMIT 1
    """)
    etapa_producao_id = etapa_producao.get('id') if etapa_producao else None
    
    etapa_separacao = db.fetch_one("""
        SELECT id FROM producao_etapas
        WHERE ativo = 1 AND tipo_etapa = 'separacao'
        ORDER BY id DESC LIMIT 1
    """)
    etapa_separacao_id = etapa_separacao.get('id') if etapa_separacao else etapa_producao_id

    for item in itens_orc:
        item_id = item['id']
        
        # Se há etapas selecionadas, só processar itens selecionados
        if etapas_por_item and item_id not in etapas_por_item:
            continue
        
        # Verificar se já processado
        ja = db.fetch_one("""
            SELECT id FROM orcamento_op_itens WHERE orcamento_item_id = %s
        """, (item_id,))
        if ja:
            continue

        produto_id = item['produto_id']
        quantidade_total = float(item.get('quantidade') or 0)
        produto_nome = item.get('produto_nome', '')
        categoria_fiscal = (item.get('categoria_fiscal') or '').strip().lower()
        
        # PRIMEIRO: Verificar estoque disponível para decidir o tipo de OP
        estoque = _verificar_estoque_disponivel(db, produto_id, quantidade_total)
        
        # Só gera OP para produtos de PRODUÇÃO (categoria_fiscal específica)
        # Categorias que geram OP: produto_producao, produto_final
        # NÃO gera OP para: revenda, materia_prima, servico, insumo, etc.
        if categoria_fiscal not in ('produto_producao', 'produto_final'):
            continue
        
        detalhe_item = {
            'produto_id': produto_id,
            'produto_nome': produto_nome,
            'quantidade': quantidade_total,
            'estoque_usado': 0,
            'quantidade_producao': 0,
            'tipo_op': None,
            'ops': []
        }
        
        data_solicitacao = datetime.now().date()
        data_prevista = None
        try:
            prazo = orc.get('prazo_entrega')
            if prazo:
                data_prevista = data_solicitacao + timedelta(days=int(prazo))
            else:
                data_prevista = orc.get('data_validade')
        except Exception:
            data_prevista = orc.get('data_validade')

        obs_base = f"Orçamento {orc.get('numero')}"
        
        template = _buscar_template_ativo_produto(db, produto_id)
        tem_template = 1 if template else 0
        template_id = template['id'] if template else None
        custo_total_template = float(template.get('custo_total_base') or 0) if template else 0

        quantidade_alocada_estoque = 0
        quantidade_a_produzir = quantidade_total

        # CASO 1: Há estoque suficiente - Criar OP de SEPARAÇÃO
        if estoque['total_disponivel'] >= quantidade_total:
            # Alocar do estoque próprio primeiro
            if estoque['estoque_proprio'] > 0:
                qtd_proprio = min(estoque['estoque_proprio'], quantidade_total - quantidade_alocada_estoque)
                if qtd_proprio > 0:
                    _criar_reserva_estoque(db, produto_id, qtd_proprio, orcamento_id,
                        f"Reserva estoque próprio para {obs_base}")
                    quantidade_alocada_estoque += qtd_proprio
                    resultado['reservas_criadas'] += 1
            
            # Alocar de produtos similares se necessário
            for similar in estoque['estoque_similar']:
                if quantidade_alocada_estoque >= quantidade_total:
                    break
                qtd_similar = min(similar['estoque_disponivel'], quantidade_total - quantidade_alocada_estoque)
                if qtd_similar > 0:
                    _criar_reserva_estoque(db, similar['produto_id'], qtd_similar, orcamento_id,
                        f"Reserva DNA similar ({similar['tipo_match']}) para {obs_base}")
                    quantidade_alocada_estoque += qtd_similar
                    resultado['reservas_criadas'] += 1
            
            quantidade_a_produzir = 0
            detalhe_item['estoque_usado'] = quantidade_alocada_estoque
            detalhe_item['tipo_op'] = 'separacao'
            
            # Usar etapa selecionada pelo usuário ou etapa padrão de separação
            etapa_usar = etapas_por_item.get(item_id, etapa_separacao_id)
            
            # Criar OP de Separação/Embalagem
            obs_estoque = f"PRODUTO EM ESTOQUE - Apenas separar e embalar. Reservado {quantidade_alocada_estoque} unidades."
            
            op_id = db.insert("""
                INSERT INTO ordens_producao (
                    empresa_id, cliente_id, produto_id, quantidade,
                    template_usado_id, usou_template, custo_total_template,
                    data_solicitacao, data_prevista, observacoes,
                    etapa_atual_id, status, created_by, tipo_op, obs_estoque
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'pendente', %s, 'separacao', %s)
            """, (
                orc.get('empresa_id'),
                orc.get('cliente_id'),
                produto_id,
                quantidade_total,
                template_id,
                tem_template,
                custo_total_template,
                data_solicitacao,
                data_prevista,
                f"{obs_base} | {obs_estoque}",
                etapa_usar,
                get_usuario_logado(),
                obs_estoque
            ))
            
            detalhe_item['ops'].append({'op_id': op_id, 'tipo': 'separacao', 'quantidade': quantidade_total})
            resultado['ops_separacao'] += 1

        # CASO 2: Não há estoque - Criar OP de PRODUÇÃO normal
        else:
            # Mesmo sem estoque suficiente, reservar o que tem
            if estoque['estoque_proprio'] > 0:
                _criar_reserva_estoque(db, produto_id, estoque['estoque_proprio'], orcamento_id,
                    f"Reserva parcial estoque próprio para {obs_base}")
                quantidade_alocada_estoque += estoque['estoque_proprio']
                resultado['reservas_criadas'] += 1
            
            for similar in estoque['estoque_similar']:
                if quantidade_alocada_estoque >= quantidade_total:
                    break
                qtd_similar = min(similar['estoque_disponivel'], quantidade_total - quantidade_alocada_estoque)
                if qtd_similar > 0:
                    _criar_reserva_estoque(db, similar['produto_id'], qtd_similar, orcamento_id,
                        f"Reserva parcial DNA similar para {obs_base}")
                    quantidade_alocada_estoque += qtd_similar
                    resultado['reservas_criadas'] += 1
            
            quantidade_a_produzir = quantidade_total - quantidade_alocada_estoque
            detalhe_item['estoque_usado'] = quantidade_alocada_estoque
            detalhe_item['quantidade_producao'] = quantidade_a_produzir
            
            if quantidade_alocada_estoque > 0 and quantidade_a_produzir > 0:
                detalhe_item['tipo_op'] = 'mista'
                obs_estoque = f"OP MISTA: {quantidade_alocada_estoque} un. do estoque + {quantidade_a_produzir} un. a produzir"
            else:
                detalhe_item['tipo_op'] = 'producao'
                obs_estoque = f"Produção total: {quantidade_a_produzir} unidades"
            
            # Usar etapa selecionada pelo usuário ou etapa padrão de produção
            etapa_usar = etapas_por_item.get(item_id, etapa_producao_id)
            
            # Criar OP de Produção
            op_id = db.insert("""
                INSERT INTO ordens_producao (
                    empresa_id, cliente_id, produto_id, quantidade,
                    template_usado_id, usou_template, custo_total_template,
                    data_solicitacao, data_prevista, observacoes,
                    etapa_atual_id, status, created_by, tipo_op, obs_estoque
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'pendente', %s, %s, %s)
            """, (
                orc.get('empresa_id'),
                orc.get('cliente_id'),
                produto_id,
                quantidade_a_produzir if quantidade_a_produzir > 0 else quantidade_total,
                template_id,
                tem_template,
                custo_total_template,
                data_solicitacao,
                data_prevista,
                f"{obs_base} | {obs_estoque}",
                etapa_usar,
                get_usuario_logado(),
                'mista' if quantidade_alocada_estoque > 0 else 'producao',
                obs_estoque
            ))
            
            detalhe_item['ops'].append({'op_id': op_id, 'tipo': detalhe_item['tipo_op'], 'quantidade': quantidade_a_produzir or quantidade_total})
            resultado['ops_producao'] += 1

        # Criar lote inicial com etapa selecionada
        try:
            db.insert(
                "INSERT INTO op_lotes (ordem_producao_id, sequencia, quantidade, etapa_atual_id, align_side, status) VALUES (%s, 1, %s, %s, 'full', 'pendente')",
                (op_id, quantidade_total, etapa_usar)
            )
        except Exception:
            pass

        # Para OPs que envolvem PRODUÇÃO (producao ou mista), copiar itens da ficha técnica
        if tem_template and detalhe_item['tipo_op'] in ('producao', 'mista'):
            _copiar_itens_template_para_op(db, op_id, template_id, quantidade_a_produzir or quantidade_total)

        # Vincular OP ao orçamento
        db.insert("""
            INSERT INTO orcamento_op_itens (
                grupo_id, orcamento_id, orcamento_item_id,
                produto_id, quantidade, ordem_producao_id,
                tem_template, template_usado_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            grupo_id,
            orcamento_id,
            item['id'],
            produto_id,
            quantidade_total,
            op_id,
            tem_template,
            template_id
        ))

        # Atualizar status do item do orçamento
        try:
            status_alocacao = 'alocado' if detalhe_item['tipo_op'] == 'separacao' else ('parcial' if quantidade_alocada_estoque > 0 else 'op_gerada')
            db.execute_query("""
                UPDATE orcamento_itens 
                SET qtd_estoque_alocada = %s, qtd_a_produzir = %s, status_alocacao = %s
                WHERE id = %s
            """, (quantidade_alocada_estoque, quantidade_a_produzir, status_alocacao, item['id']))
        except Exception:
            pass

        resultado['itens_processados'] += 1
        resultado['detalhes'].append(detalhe_item)

    return resultado


def registrar_historico(orcamento_id, acao, descricao, dados_anteriores=None, dados_novos=None):
    """
    Registra uma ação no histórico do orçamento
    
    Ações possíveis:
    - CRIACAO: Orçamento criado
    - EDICAO: Orçamento editado
    - ITEM_ADICIONADO: Item adicionado
    - ITEM_REMOVIDO: Item removido
    - ITEM_ALTERADO: Item alterado
    - STATUS_ALTERADO: Status alterado (pendente, aprovado, etc)
    - APROVACAO: Orçamento aprovado
    - REJEICAO: Orçamento rejeitado
    - CONVERSAO: Convertido em pedido
    - ENVIO_EMAIL: Email enviado ao cliente
    - VISUALIZACAO: Orçamento visualizado
    - IMPRESSAO: Orçamento impresso/PDF gerado
    """
    try:
        db = get_db()
        usuario_id = session.get('user_id')
        usuario_nome = session.get('username', 'Sistema')
        ip_address = request.remote_addr if request else None
        
        db.execute_query("""
            INSERT INTO orcamento_historico 
            (orcamento_id, acao, descricao, dados_anteriores, dados_novos, 
             usuario_id, usuario_nome, ip_address)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, [
            orcamento_id,
            acao,
            descricao,
            json.dumps(dados_anteriores, default=str) if dados_anteriores else None,
            json.dumps(dados_novos, default=str) if dados_novos else None,
            usuario_id,
            usuario_nome,
            ip_address
        ])
        return True
    except Exception as e:
        print(f"[HISTORICO] Erro ao registrar: {e}")
        return False


def obter_historico(orcamento_id):
    """Obtém o histórico completo de um orçamento"""
    db = get_db()
    return db.fetch_all("""
        SELECT * FROM orcamento_historico 
        WHERE orcamento_id = %s 
        ORDER BY created_at DESC
    """, [orcamento_id]) or []


def gerar_descricao_alteracoes(dados_anteriores, dados_novos):
    """
    Gera uma descrição detalhada das alterações entre dois estados do orçamento.
    Compara campo a campo e gera texto legível das mudanças.
    
    Args:
        dados_anteriores: Dict com valores antes da alteração
        dados_novos: Dict com valores após a alteração
    
    Returns:
        String com descrição das alterações
    """
    if not dados_anteriores:
        return "Orçamento criado"
    
    alteracoes = []
    
    # Mapeamento de campos para nomes legíveis (organizados por aba)
    campos = {
        # Aba Dados
        'cliente_id': 'Cliente',
        'vendedor_id': 'Vendedor',
        'vendedor2_id': 'Vendedor 2',
        'contato': 'Contato',
        'tipo_pedido': 'Tipo de Pedido',
        'canal_relacionamento': 'Canal',
        'empresa_id': 'Empresa',
        'forma_pagamento_id': 'Forma de Pagamento',
        # Aba Transporte
        'transportadora_id': 'Transportadora',
        'frete_por_conta': 'Frete por Conta',
        'obs_frete': 'Obs. Frete',
        'perfil_transporte': 'Perfil Transporte',
        'especie': 'Espécie Volume',
        'volumes_quantidade': 'Qtde Volumes',
        'peso_bruto': 'Peso Bruto',
        'peso_liquido': 'Peso Líquido',
        # Valores
        'valor_total': 'Valor Total',
        'percentual_desconto': 'Desconto %',
        'valor_frete': 'Valor Frete',
        # Observações
        'observacoes': 'Observações',
        'observacoes_internas': 'Obs. Internas',
        'status': 'Status'
    }
    
    for campo, nome_legivel in campos.items():
        valor_ant = dados_anteriores.get(campo)
        valor_novo = dados_novos.get(campo)
        
        # Converter para string para comparação
        str_ant = str(valor_ant) if valor_ant is not None else ''
        str_novo = str(valor_novo) if valor_novo is not None else ''
        
        if str_ant != str_novo:
            if campo in ['valor_total', 'valor_frete']:
                # Formatar valores monetários
                ant_fmt = f"R$ {float(valor_ant or 0):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                novo_fmt = f"R$ {float(valor_novo or 0):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                alteracoes.append(f"{nome_legivel}: {ant_fmt} → {novo_fmt}")
            elif campo == 'percentual_desconto':
                alteracoes.append(f"{nome_legivel}: {valor_ant or 0}% → {valor_novo or 0}%")
            elif valor_ant and valor_novo:
                alteracoes.append(f"{nome_legivel}: '{valor_ant}' → '{valor_novo}'")
            elif valor_novo:
                alteracoes.append(f"{nome_legivel}: (vazio) → '{valor_novo}'")
            elif valor_ant:
                alteracoes.append(f"{nome_legivel}: '{valor_ant}' → (removido)")
    
    if not alteracoes:
        return "Edição sem alterações detectadas"
    
    return " | ".join(alteracoes)


# =====================================================
# LISTAGEM DE ORÇAMENTOS
# =====================================================

@orcamento_bp.route('/')
@orcamento_bp.route('/lista')
@orcamento_visualizar_required
def lista():
    """Lista todos os orçamentos com filtros"""
    db = get_db()
    
    # Parâmetros de filtro
    cliente_id = request.args.get('cliente_id', '')
    vendedor_id = request.args.get('vendedor_id', '')
    status = request.args.get('status', '')
    data_inicio = request.args.get('data_inicio', '')
    data_fim = request.args.get('data_fim', '')
    busca = request.args.get('busca', '')
    
    # Query base
    query = """
        SELECT 
            o.id,
            o.numero,
            o.data_emissao,
            o.data_validade,
            o.status,
            o.valor_total,
            o.fx_target_currency_code,
            o.prazo_entrega,
            o.empresa_id,
            c.name AS cliente_nome,
            c.cnpj AS cliente_documento,
            c.email AS cliente_email,
            s.name AS vendedor_nome,
            o.pedido_id,
            DATEDIFF(o.data_validade, CURRENT_DATE) AS dias_para_vencer,
            (SELECT COUNT(*) FROM orcamento_itens WHERE orcamento_id = o.id) AS qtd_itens
        FROM orcamentos o
        LEFT JOIN customers c ON o.cliente_id = c.id
        LEFT JOIN users s ON o.vendedor_id = s.id
        WHERE 1=1
    """
    params = []
    
    # Aplicar filtros
    if cliente_id:
        query += " AND o.cliente_id = %s"
        params.append(cliente_id)
    
    if vendedor_id:
        query += " AND o.vendedor_id = %s"
        params.append(vendedor_id)
    
    if status:
        query += " AND o.status = %s"
        params.append(status)
    
    if data_inicio:
        query += " AND DATE(o.data_emissao) >= %s"
        params.append(data_inicio)
    
    if data_fim:
        query += " AND DATE(o.data_emissao) <= %s"
        params.append(data_fim)
    
    if busca:
        query += " AND (o.numero LIKE %s OR c.name LIKE %s)"
        params.extend([f'%{busca}%', f'%{busca}%'])
    
    query += " ORDER BY o.data_emissao DESC LIMIT 500"
    
    orcamentos = db.fetch_all(query, params)
    
    # Buscar listas para filtros
    clientes = db.fetch_all("SELECT id, name FROM customers WHERE active = 1 ORDER BY name LIMIT 500")
    vendedores = db.fetch_all("SELECT id, name FROM users WHERE is_seller = 1 AND status = 'active' ORDER BY name")
    
    # Estatísticas
    stats_query = """
        SELECT 
            COUNT(*) AS total,
            SUM(CASE WHEN status = 'rascunho' THEN 1 ELSE 0 END) AS rascunhos,
            SUM(CASE WHEN status = 'enviado' THEN 1 ELSE 0 END) AS enviados,
            SUM(CASE WHEN status = 'aprovado' THEN 1 ELSE 0 END) AS aprovados,
            SUM(CASE WHEN status = 'reprovado' THEN 1 ELSE 0 END) AS reprovados,
            SUM(CASE WHEN status = 'convertido' THEN 1 ELSE 0 END) AS convertidos,
            SUM(CASE WHEN status = 'enviado' AND data_validade < CURRENT_DATE THEN 1 ELSE 0 END) AS vencidos,
            SUM(valor_total) AS valor_total
        FROM orcamentos
        WHERE data_emissao >= DATE_SUB(CURRENT_DATE, INTERVAL 30 DAY)
    """
    stats_result = db.fetch_all(stats_query)
    stats = stats_result[0] if stats_result else {'total': 0, 'rascunhos': 0, 'enviados': 0, 'aprovados': 0, 'reprovados': 0, 'convertidos': 0, 'vencidos': 0, 'valor_total': 0}
    
    return render_template('comercial/orcamento_list.html',
        orcamentos=orcamentos or [],
        clientes=clientes or [],
        vendedores=vendedores or [],
        stats=stats,
        filtros={
            'cliente_id': cliente_id,
            'vendedor_id': vendedor_id,
            'status': status,
            'data_inicio': data_inicio,
            'data_fim': data_fim,
            'busca': busca
        }
    )


# =====================================================
# NOVO ORÇAMENTO
# =====================================================

@orcamento_bp.route('/novo')
@orcamento_criar_required
def novo():
    """Formulário para criar novo orçamento"""
    db = get_db()
    
    # Pré-carregar cliente se vier por parâmetro
    cliente_id = request.args.get('cliente_id', '')
    cliente = None
    if cliente_id:
        cliente = db.fetch_all("SELECT * FROM customers WHERE id = %s", [cliente_id])
        cliente = cliente[0] if cliente else None
    
    # Buscar dados necessários
    clientes = db.fetch_all("""
        SELECT id, name, cnpj AS document, phone, email 
        FROM customers 
        WHERE active = 1 
        ORDER BY name 
        LIMIT 1000
    """)
    
    # Buscar vendedores da tabela users (onde is_seller = 1)
    vendedores = db.fetch_all("""
        SELECT id, name 
        FROM users 
        WHERE is_seller = 1 AND status = 'active'
        ORDER BY name
    """)
    
    empresas = db.fetch_all("""
        SELECT id, razao_social, nome_fantasia 
        FROM empresas 
        WHERE ativo = 1 
        ORDER BY razao_social
    """)
    
    # Formas de pagamento (tabela completa com integrações)
    formas_pagamento = db.fetch_all("""
        SELECT id, name, code, 
               max_installments, days_between_installments, days_to_receive,
               allow_installments, generate_boleto, requires_approval,
               financial_behavior, operator_fee_percent
        FROM payment_methods_config 
        WHERE active = 1 
        ORDER BY name
    """)
    
    # Transportadoras
    transportadoras = db.fetch_all("""
        SELECT id, nome AS name 
        FROM transportadoras 
        WHERE active = 1 
        ORDER BY nome
        LIMIT 50
    """)
    
    # Listas de Preço
    listas_preco = db.fetch_all("""
        SELECT id, nome, codigo, tipo, percentual_padrao 
        FROM listas_preco 
        WHERE ativo = TRUE 
        ORDER BY prioridade, nome
    """)
    
    # Validade padrão: 15 dias
    data_validade_padrao = (datetime.now() + timedelta(days=15)).strftime('%Y-%m-%d')
    
    # Vendedor padrão (usuário logado ou primeiro)
    vendedor_padrao = session.get('seller_id', vendedores[0]['id'] if vendedores else None)
    empresa_padrao = get_empresa_padrao()
    
    return render_template('comercial/orcamento_form_v2.html',
        orcamento=None,
        cliente=cliente,
        clientes=clientes or [],
        vendedores=vendedores or [],
        empresas=empresas or [],
        formas_pagamento=formas_pagamento or [],
        transportadoras=transportadoras or [],
        listas_preco=listas_preco or [],
        data_validade_padrao=data_validade_padrao,
        vendedor_padrao=vendedor_padrao,
        empresa_padrao=empresa_padrao,
        hoje=datetime.now().strftime('%Y-%m-%d'),
        itens=[],
        duplicatas=[],
        historico=[],
        modo='novo'
    )


# =====================================================
# EDITAR ORÇAMENTO
# =====================================================

@orcamento_bp.route('/<int:id>/editar')
@orcamento_editar_required
def editar(id):
    """Formulário para editar orçamento existente"""
    db = get_db()
    
    # Buscar orçamento
    orcamento = db.fetch_all("""
        SELECT o.*, c.name AS cliente_nome, s.name AS vendedor_nome
        FROM orcamentos o
        LEFT JOIN customers c ON o.cliente_id = c.id
        LEFT JOIN users s ON o.vendedor_id = s.id
        WHERE o.id = %s
    """, [id])
    
    if not orcamento:
        flash('Orçamento não encontrado.', 'error')
        return redirect(url_for('orcamentos.lista'))
    
    orcamento = orcamento[0]
    
    # Debug log
    print(f"[ORCAMENTO EDITAR] ID={id}")
    print(f"[ORCAMENTO EDITAR] forma_pagamento_id={orcamento.get('forma_pagamento_id')} (tipo: {type(orcamento.get('forma_pagamento_id'))})")
    print(f"[ORCAMENTO EDITAR] vendedor_id={orcamento.get('vendedor_id')}")
    print(f"[ORCAMENTO EDITAR] cliente_id={orcamento.get('cliente_id')}")
    print(f"[ORCAMENTO EDITAR] contato={orcamento.get('contato')}")
    print(f"[ORCAMENTO EDITAR] tipo_pedido={orcamento.get('tipo_pedido')}")
    
    # Verificar se pode editar (apenas rascunho ou enviado)
    if orcamento['status'] not in ['rascunho', 'enviado']:
        flash('Este orçamento não pode mais ser editado.', 'warning')
        return redirect(url_for('orcamentos.visualizar', id=id))
    
    # Buscar itens do orçamento
    itens = db.fetch_all("""
        SELECT oi.*, p.name AS produto_nome, p.internal_code AS produto_codigo, p.price AS sale_price
        FROM orcamento_itens oi
        LEFT JOIN products p ON oi.produto_id = p.id
        WHERE oi.orcamento_id = %s
        ORDER BY oi.sequencia
    """, [id])
    
    # Buscar cliente
    cliente = db.fetch_all("SELECT * FROM customers WHERE id = %s", [orcamento['cliente_id']])
    cliente = cliente[0] if cliente else None
    
    # Buscar dados para selects
    clientes = db.fetch_all("SELECT id, name, cnpj AS document FROM customers WHERE active = 1 ORDER BY name LIMIT 1000")
    vendedores = db.fetch_all("SELECT id, name FROM users WHERE is_seller = 1 AND status = 'active' ORDER BY name")
    empresas = db.fetch_all("SELECT id, razao_social, nome_fantasia FROM empresas WHERE ativo = 1")
    formas_pagamento = db.fetch_all("""
        SELECT id, name, code, max_installments, days_between_installments, 
               days_to_receive, allow_installments, generate_boleto
        FROM payment_methods_config WHERE active = 1 ORDER BY name
    """)
    transportadoras = db.fetch_all("SELECT id, name FROM suppliers WHERE active = 1 ORDER BY name LIMIT 50")
    listas_preco = db.fetch_all("SELECT id, nome, codigo, tipo, percentual_padrao FROM listas_preco WHERE ativo = TRUE ORDER BY prioridade, nome")
    
    # Buscar duplicatas/parcelas do orçamento
    duplicatas = db.fetch_all("""
        SELECT id, numero, vencimento, valor, forma_pagamento, forma_pagamento_id, status
        FROM orcamento_duplicatas
        WHERE orcamento_id = %s
        ORDER BY numero
    """, [id])
    
    print(f"[ORCAMENTO EDITAR] Duplicatas encontradas: {len(duplicatas) if duplicatas else 0}")
    
    # Buscar histórico do orçamento
    historico = obter_historico(id)
    print(f"[ORCAMENTO EDITAR] Histórico encontrado: {len(historico) if historico else 0} registros")
    
    # Buscar dados da transportadora se houver
    transportadora_dados = None
    if orcamento.get('transportadora_id'):
        transportadora_dados = db.fetch_one("""
            SELECT id, nome, razao_social, cnpj, cpf, inscricao_estadual,
                   endereco, numero, bairro, cidade, estado
            FROM transportadoras 
            WHERE id = %s
        """, [orcamento['transportadora_id']])
    
    return render_template('comercial/orcamento_form_v2.html',
        orcamento=orcamento,
        itens=itens or [],
        cliente=cliente,
        clientes=clientes or [],
        vendedores=vendedores or [],
        empresas=empresas or [],
        formas_pagamento=formas_pagamento or [],
        transportadoras=transportadoras or [],
        listas_preco=listas_preco or [],
        hoje=datetime.now().strftime('%Y-%m-%d'),
        duplicatas=duplicatas or [],
        historico=historico or [],
        transportadora_dados=transportadora_dados,
        modo='editar'
    )


# =====================================================
# VISUALIZAR ORÇAMENTO
# =====================================================

@orcamento_bp.route('/<int:id>')
def visualizar(id):
    """Visualização completa do orçamento"""
    db = get_db()
    
    # Buscar orçamento com dados relacionados
    orcamento = db.fetch_all("""
        SELECT o.*,
            c.name AS cliente_nome,
            c.cnpj AS cliente_documento,
            c.phone AS cliente_telefone,
            c.email AS cliente_email,
            c.address AS cliente_endereco,
            c.city AS cliente_cidade,
            c.state AS cliente_estado,
            c.cep AS cliente_cep,
            s.name AS vendedor_nome,
            s.phone AS vendedor_telefone,
            s2.name AS vendedor2_nome,
            s2.phone AS vendedor2_telefone,
            e.razao_social AS empresa_nome,
            e.cnpj AS empresa_cnpj,
            CONCAT(e.logradouro, ', ', COALESCE(e.numero, 's/n')) AS empresa_endereco,
            e.cidade AS empresa_cidade,
            e.estado AS empresa_estado,
            t.name AS transportadora_nome
        FROM orcamentos o
        LEFT JOIN customers c ON o.cliente_id = c.id
        LEFT JOIN users s ON o.vendedor_id = s.id
        LEFT JOIN users s2 ON o.vendedor2_id = s2.id
        LEFT JOIN empresas e ON o.empresa_id = e.id
        LEFT JOIN suppliers t ON o.transportadora_id = t.id
        WHERE o.id = %s
    """, [id])
    
    if not orcamento:
        flash('Orçamento não encontrado.', 'error')
        return redirect(url_for('orcamentos.lista'))
    
    orcamento = orcamento[0]

    # Buscar itens
    itens = db.fetch_all("""
        SELECT oi.*, 
            p.name AS produto_nome, 
            p.internal_code AS produto_codigo,
            p.description AS produto_descricao
        FROM orcamento_itens oi
        LEFT JOIN products p ON oi.produto_id = p.id
        WHERE oi.orcamento_id = %s
        ORDER BY oi.sequencia
    """, [id])
    
    # Buscar duplicatas / parcelas
    duplicatas = db.fetch_all("""
        SELECT numero, vencimento, valor, forma_pagamento, status
        FROM orcamento_duplicatas
        WHERE orcamento_id = %s
        ORDER BY vencimento, numero
    """, [id])

    # Buscar taxa oficial do dia para comparação (se houver dados de FX no orçamento)
    fx_oficial = None
    try:
        fx_rate_date = orcamento.get('fx_rate_date') if isinstance(orcamento, dict) else orcamento['fx_rate_date']
        fx_base_code = orcamento.get('fx_base_currency_code') if isinstance(orcamento, dict) else orcamento['fx_base_currency_code']
        fx_target_code = orcamento.get('fx_target_currency_code') if isinstance(orcamento, dict) else orcamento['fx_target_currency_code']
    except Exception:
        fx_rate_date = None
        fx_base_code = None
        fx_target_code = None

    if fx_rate_date and fx_base_code and fx_target_code:
        try:
            fx_oficial = db.fetch_one(
                """
                SELECT rate, source
                FROM exchange_rates
                WHERE rate_date = %s
                  AND base_currency_code = %s
                  AND target_currency_code = %s
                """,
                [fx_rate_date, fx_base_code, fx_target_code],
            )
        except Exception as e:
            print(f"[ORCAMENTO FX] Aviso ao buscar taxa oficial para visualização: {e}")

    # Buscar histórico
    historico = db.fetch_all("""
        SELECT h.id, h.orcamento_id, h.acao, h.descricao, h.dados_anteriores, h.dados_novos,
               h.usuario_id, h.ip_address, 
               COALESCE(h.created_at, h.data_evento) AS created_at,
               COALESCE(h.usuario_nome, u.username, 'Sistema') AS nome_usuario
        FROM orcamento_historico h
        LEFT JOIN users u ON h.usuario_id = u.id
        WHERE h.orcamento_id = %s
        ORDER BY COALESCE(h.created_at, h.data_evento) DESC
    """, [id])

    producao_ops = []
    try:
        producao_ops = db.fetch_all("""
            SELECT
                oi.id AS vinculo_id,
                oi.ordem_producao_id,
                oi.orcamento_item_id,
                oi.produto_id,
                oi.quantidade AS quantidade_orcamento,
                oi.tem_template,
                oi.template_usado_id,
                op.numero_op,
                op.status,
                op.data_prevista,
                op.usou_template,
                op.template_usado_id AS op_template_usado_id,
                p.name AS produto_nome
            FROM orcamento_op_itens oi
            INNER JOIN ordens_producao op ON oi.ordem_producao_id = op.id
            INNER JOIN products p ON oi.produto_id = p.id
            WHERE oi.orcamento_id = %s
            ORDER BY oi.id
        """, (id,)) or []
    except Exception as e:
        print(f"[ORCAMENTO PRODUCAO] Aviso ao buscar OPs: {e}")
    
    return render_template('comercial/orcamento_view.html',
        orcamento=orcamento,
        itens=itens or [],
        duplicatas=duplicatas or [],
        historico=historico or [],
        producao_ops=producao_ops or [],
        fx_oficial=fx_oficial,
        today=datetime.now().date()
    )


# =====================================================
# SALVAR ORÇAMENTO
# =====================================================

@orcamento_bp.route('/salvar', methods=['POST'])
@orcamento_criar_required
def salvar():
    """Salva novo orçamento ou atualiza existente"""
    db = get_db()
    
    try:
        # Dados do formulário
        orcamento_id = request.form.get('id') or request.form.get('orcamento_id') or ''
        cliente_id = request.form.get('cliente_id')
        cliente_id = int(cliente_id) if cliente_id and cliente_id not in ('', 'None') else None
        
        vendedor_id = request.form.get('vendedor_id')
        vendedor_id = int(vendedor_id) if vendedor_id and vendedor_id not in ('', 'None') else None
        
        vendedor2_id = request.form.get('vendedor2_id')
        vendedor2_id = int(vendedor2_id) if vendedor2_id and vendedor2_id not in ('', 'None') else None
        
        contato = request.form.get('contato', '') or ''
        tipo_pedido = request.form.get('tipo_pedido', '') or ''
        canal_relacionamento = request.form.get('canal_relacionamento', '') or ''
        
        empresa_id = request.form.get('empresa_id')
        empresa_id = int(empresa_id) if empresa_id and empresa_id not in ('', 'None') else None
        
        data_validade = request.form.get('data_validade') or None
        condicao_pagamento = request.form.get('condicao_pagamento', '')
        
        # Tratar campos que podem vir vazios ou com 'None' como string
        # Forma de pagamento pode vir de dois campos diferentes
        forma_pagamento_id = request.form.get('pagamento_method_id') or request.form.get('forma_pagamento_id')
        forma_pagamento_id = int(forma_pagamento_id) if forma_pagamento_id and forma_pagamento_id not in ('', 'None') else None
        
        prazo_entrega = request.form.get('prazo_entrega')
        prazo_entrega = int(prazo_entrega) if prazo_entrega and prazo_entrega not in ('', 'None') else None
        
        # =====================================================
        # CAMPOS DA ABA TRANSPORTE
        # =====================================================
        frete_por_conta = request.form.get('frete_por_conta', 'emitente')
        obs_frete = request.form.get('obs_frete', '') or ''  # Observação do frete
        perfil_transporte = request.form.get('perfil_transporte', '') or ''  # CIF, FOB, etc
        
        transportadora_id = request.form.get('transportadora_id')
        transportadora_id = int(transportadora_id) if transportadora_id and transportadora_id not in ('', 'None') else None
        
        # Campos de volumes
        especie = request.form.get('especie', '') or ''  # Caixa, Saco, Fardo, etc
        volumes_quantidade = request.form.get('volumes_quantidade', '0') or '0'
        volumes_quantidade = int(volumes_quantidade) if volumes_quantidade else 0
        peso_bruto = request.form.get('peso_bruto', '0') or '0'
        peso_bruto = peso_bruto.replace(',', '.')
        peso_liquido = request.form.get('peso_liquido', '0') or '0'
        peso_liquido = peso_liquido.replace(',', '.')
        
        # Campos de veículo (opcional)
        veiculo_placa = request.form.get('veiculo_placa', '') or ''
        veiculo_uf = request.form.get('veiculo_uf', '') or ''
        veiculo_rntc = request.form.get('veiculo_rntc', '') or ''
        
        # =====================================================
        # CAMPOS INFORMAÇÕES ADICIONAIS (Aba Transporte)
        # =====================================================
        referencia_cliente = request.form.get('referencia_cliente', '') or ''
        obs_validade = request.form.get('obs_validade', '') or ''
        obs_entrega = request.form.get('obs_entrega', '') or ''
        obs_embalagem = request.form.get('obs_embalagem', '') or ''
        obs_garantia = request.form.get('obs_garantia', '') or ''
        obs_certificado = request.form.get('obs_certificado', '') or ''
        icms_incluso = 1 if request.form.get('icms_incluso') else 0
        ipi_incluso = 1 if request.form.get('ipi_incluso') else 0
        
        # =====================================================
        # CAMPOS DE PREVISÃO (Aba Dados)
        # =====================================================
        data_previsao_producao = request.form.get('data_previsao_producao') or None
        data_previsao_entrega = request.form.get('data_previsao_entrega') or None
        dias_transporte = request.form.get('dias_transporte', '0') or '0'
        dias_transporte = int(dias_transporte) if dias_transporte.isdigit() else 0
        previsao_manual = 1 if request.form.get('previsao_manual') else 0
        
        # =====================================================
        # CAMPOS DE COMISSÃO (Aba Comissão)
        # =====================================================
        comissao_vendedor1_percent_raw = request.form.get('comissao_vendedor1_aliquota', '0') or '0'
        comissao_vendedor1_percent = comissao_vendedor1_percent_raw.replace(',', '.')
        comissao_vendedor1_valor_raw = request.form.get('comissao_valor_v1', '0') or '0'
        comissao_vendedor1_valor = comissao_vendedor1_valor_raw.replace(',', '.')
        
        comissao_vendedor2_percent_raw = request.form.get('comissao_vendedor2_aliquota', '0') or '0'
        comissao_vendedor2_percent = comissao_vendedor2_percent_raw.replace(',', '.')
        comissao_vendedor2_valor_raw = request.form.get('comissao_valor_v2', '0') or '0'
        comissao_vendedor2_valor = comissao_vendedor2_valor_raw.replace(',', '.')
        
        # =====================================================
        # VALORES NUMÉRICOS
        # =====================================================
        valor_frete_raw = request.form.get('valor_frete', '0') or '0'
        percentual_desconto_raw = request.form.get('percentual_desconto', '0') or '0'
        
        # Se vier com ponto como decimal (formato americano), usar direto
        valor_frete = valor_frete_raw.replace(',', '.')
        percentual_desconto = percentual_desconto_raw.replace(',', '.')
        observacoes = request.form.get('observacoes', '')
        observacoes_internas = request.form.get('observacoes_internas', '')
        acao = request.form.get('acao', 'salvar')  # salvar ou enviar

        # =====================================================
        # CAMPOS DE CÂMBIO (FX) - base -> moeda funcional da empresa
        # =====================================================
        fx_info = calcular_fx_para_empresa(db, empresa_id)
        if fx_info:
            fx_base_currency_code = fx_info['base_currency']
            fx_target_currency_code = fx_info['target_currency']
            fx_rate_date = fx_info['rate_date']
            fx_rate_value = fx_info['rate_value']
            fx_rate_source = fx_info['rate_source']
        else:
            fx_base_currency_code = None
            fx_target_currency_code = None
            fx_rate_date = None
            fx_rate_value = None
            fx_rate_source = None
        
        # Itens (JSON)
        itens_json = request.form.get('itens', '[]')
        itens = json.loads(itens_json)
        
        # Duplicatas/Parcelas (JSON)
        duplicatas_json = request.form.get('duplicatas', '[]')
        duplicatas = json.loads(duplicatas_json) if duplicatas_json else []
        num_parcelas = request.form.get('num_parcelas', '1')
        num_parcelas = int(num_parcelas) if num_parcelas and num_parcelas not in ('', 'None') else 1
        
        # Log resumido (pode ser removido em produção)
        print(f"[ORCAMENTO] Salvando: cliente={cliente_id}, vendedor={vendedor_id}, itens={len(itens)}")
        
        # Validações - Campos obrigatórios
        erros = []
        
        if not cliente_id:
            erros.append('Cliente é obrigatório')
        
        if not vendedor_id:
            erros.append('Vendedor é obrigatório')
        
        if not itens or len(itens) == 0:
            erros.append('Adicione pelo menos um item ao orçamento')
        
        if not forma_pagamento_id:
            erros.append('Forma de Pagamento é obrigatória')
        
        if erros:
            for erro in erros:
                flash(erro, 'error')
            return redirect(request.referrer or url_for('orcamentos.novo'))
        
        # Calcular valores
        valor_produtos = sum(Decimal(str(item.get('valor_total', 0))) for item in itens)
        valor_desconto = valor_produtos * (Decimal(percentual_desconto) / 100)
        valor_total = valor_produtos - valor_desconto + Decimal(valor_frete or '0')
        
        usuario_id = get_usuario_logado()
        
        # =====================================================
        # BUSCAR DADOS ANTERIORES PARA HISTÓRICO
        # =====================================================
        dados_anteriores = None
        if orcamento_id:
            dados_anteriores = db.fetch_one("""
                SELECT 
                    cliente_id, vendedor_id, vendedor2_id, contato, tipo_pedido, canal_relacionamento,
                    empresa_id, fx_base_currency_code, fx_target_currency_code, fx_rate_date, fx_rate_value, fx_rate_source,
                    forma_pagamento_id, 
                    transportadora_id, frete_por_conta, obs_frete, perfil_transporte,
                    especie, volumes_quantidade, peso_bruto, peso_liquido,
                    valor_total, percentual_desconto, valor_frete, 
                    observacoes, observacoes_internas, status
                FROM orcamentos WHERE id = %s
            """, [orcamento_id])
        
        if orcamento_id:
            # =====================================================
            # ATUALIZAR ORÇAMENTO EXISTENTE
            # =====================================================
            db.execute_query("""
                UPDATE orcamentos SET
                    -- Dados principais (Aba Dados)
                    cliente_id = %s,
                    vendedor_id = %s,
                    vendedor2_id = %s,
                    contato = %s,
                    tipo_pedido = %s,
                    canal_relacionamento = %s,
                    empresa_id = %s,
                    data_validade = %s,
                    condicao_pagamento = %s,
                    forma_pagamento_id = %s,
                    prazo_entrega = %s,
                    fx_base_currency_code = %s,
                    fx_target_currency_code = %s,
                    fx_rate_date = %s,
                    fx_rate_value = %s,
                    fx_rate_source = %s,
                    -- Dados de transporte (Aba Transporte)
                    frete_por_conta = %s,
                    obs_frete = %s,
                    perfil_transporte = %s,
                    transportadora_id = %s,
                    especie = %s,
                    volumes_quantidade = %s,
                    peso_bruto = %s,
                    peso_liquido = %s,
                    veiculo_placa = %s,
                    veiculo_uf = %s,
                    veiculo_rntc = %s,
                    -- Informações adicionais (Aba Transporte)
                    referencia_cliente = %s,
                    obs_validade = %s,
                    obs_entrega = %s,
                    obs_embalagem = %s,
                    obs_garantia = %s,
                    obs_certificado = %s,
                    icms_incluso = %s,
                    ipi_incluso = %s,
                    -- Valores calculados
                    valor_frete = %s,
                    valor_produtos = %s,
                    percentual_desconto = %s,
                    valor_desconto = %s,
                    valor_total = %s,
                    -- Observações (Aba Outros)
                    observacoes = %s,
                    observacoes_internas = %s,
                    -- Comissão (Aba Comissão)
                    comissao_vendedor1_percent = %s,
                    comissao_vendedor1_valor = %s,
                    comissao_vendedor2_percent = %s,
                    comissao_vendedor2_valor = %s,
                    -- Previsões
                    data_previsao_producao = %s,
                    data_previsao_entrega = %s,
                    dias_transporte = %s,
                    previsao_manual = %s,
                    -- Status e controle
                    status = %s,
                    updated_at = NOW()
                WHERE id = %s
            """, [
                # Dados principais
                cliente_id, vendedor_id, vendedor2_id, contato, tipo_pedido, canal_relacionamento,
                empresa_id, data_validade, condicao_pagamento, forma_pagamento_id, prazo_entrega,
                fx_base_currency_code, fx_target_currency_code, fx_rate_date, fx_rate_value, fx_rate_source,
                # Transporte
                frete_por_conta, obs_frete, perfil_transporte, transportadora_id,
                especie, volumes_quantidade, peso_bruto, peso_liquido,
                veiculo_placa, veiculo_uf, veiculo_rntc,
                # Informações adicionais
                referencia_cliente, obs_validade, obs_entrega, obs_embalagem,
                obs_garantia, obs_certificado, icms_incluso, ipi_incluso,
                # Valores
                valor_frete, valor_produtos, percentual_desconto, valor_desconto, valor_total,
                # Observações
                observacoes, observacoes_internas,
                # Comissão
                comissao_vendedor1_percent, comissao_vendedor1_valor,
                comissao_vendedor2_percent, comissao_vendedor2_valor,
                # Previsões
                data_previsao_producao, data_previsao_entrega, dias_transporte, previsao_manual,
                # Status
                'enviado' if acao == 'enviar' else 'rascunho',
                orcamento_id,
            ])

            print(f"[ORCAMENTO] UPDATE executado para ID={orcamento_id}")
            
            # Deletar itens antigos
            db.execute_query("DELETE FROM orcamento_itens WHERE orcamento_id = %s", [orcamento_id])
            
        else:
            # =====================================================
            # INSERIR NOVO ORÇAMENTO
            # =====================================================
            db.execute_query("""
                INSERT INTO orcamentos (
                    -- Dados principais (Aba Dados)
                    cliente_id, vendedor_id, vendedor2_id, contato, tipo_pedido, canal_relacionamento,
                    empresa_id, data_validade, condicao_pagamento, forma_pagamento_id, prazo_entrega,
                    fx_base_currency_code, fx_target_currency_code, fx_rate_date, fx_rate_value, fx_rate_source,
                    -- Dados de transporte (Aba Transporte)
                    frete_por_conta, obs_frete, perfil_transporte, transportadora_id,
                    especie, volumes_quantidade, peso_bruto, peso_liquido,
                    veiculo_placa, veiculo_uf, veiculo_rntc,
                    -- Informações adicionais
                    referencia_cliente, obs_validade, obs_entrega, obs_embalagem,
                    obs_garantia, obs_certificado, icms_incluso, ipi_incluso,
                    -- Valores calculados
                    valor_frete, valor_produtos, percentual_desconto, valor_desconto, valor_total,
                    -- Observações (Aba Outros)
                    observacoes, observacoes_internas,
                    -- Comissão
                    comissao_vendedor1_percent, comissao_vendedor1_valor,
                    comissao_vendedor2_percent, comissao_vendedor2_valor,
                    -- Previsões
                    data_previsao_producao, data_previsao_entrega, dias_transporte, previsao_manual,
                    -- Status e controle
                    status, created_by
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s
                )
            """, [
                # Dados principais
                cliente_id, vendedor_id, vendedor2_id, contato, tipo_pedido, canal_relacionamento,
                empresa_id, data_validade, condicao_pagamento, forma_pagamento_id, prazo_entrega,
                fx_base_currency_code, fx_target_currency_code, fx_rate_date, fx_rate_value, fx_rate_source,
                # Transporte
                frete_por_conta, obs_frete, perfil_transporte, transportadora_id,
                especie, volumes_quantidade, peso_bruto, peso_liquido,
                veiculo_placa, veiculo_uf, veiculo_rntc,
                # Informações adicionais
                referencia_cliente, obs_validade, obs_entrega, obs_embalagem,
                obs_garantia, obs_certificado, icms_incluso, ipi_incluso,
                # Valores
                valor_frete, valor_produtos, percentual_desconto, valor_desconto, valor_total,
                # Observações
                observacoes, observacoes_internas,
                # Comissão
                comissao_vendedor1_percent, comissao_vendedor1_valor,
                comissao_vendedor2_percent, comissao_vendedor2_valor,
                # Previsões
                data_previsao_producao, data_previsao_entrega, dias_transporte, previsao_manual,
                # Status
                'enviado' if acao == 'enviar' else 'rascunho',
                usuario_id
            ])
            
            # Pegar ID inserido
            result = db.fetch_one("SELECT LAST_INSERT_ID() AS id")
            orcamento_id = result['id']
        
        # Inserir itens
        for seq, item in enumerate(itens, 1):
            db.execute_query("""
                INSERT INTO orcamento_itens (
                    orcamento_id, produto_id, quantidade, unidade,
                    preco_tabela, preco_unitario, percentual_desconto,
                    valor_desconto, valor_total,
                    largura, comprimento, espessura, tipo_correia, material,
                    observacao, sequencia
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
            """, [
                orcamento_id,
                item.get('produto_id'),
                item.get('quantidade', 1),
                item.get('unidade', 'UN'),
                item.get('preco_tabela', item.get('preco_unitario')),
                item.get('preco_unitario'),
                item.get('percentual_desconto', 0),
                item.get('valor_desconto', 0),
                item.get('valor_total'),
                item.get('largura'),
                item.get('comprimento'),
                item.get('espessura'),
                item.get('tipo_correia'),
                item.get('material'),
                item.get('observacao'),
                seq
            ])
        
        # Salvar duplicatas/parcelas
        # Primeiro deletar as existentes
        db.execute_query("DELETE FROM orcamento_duplicatas WHERE orcamento_id = %s", [orcamento_id])
        
        # Inserir novas duplicatas
        for dup in duplicatas:
            db.execute_query("""
                INSERT INTO orcamento_duplicatas (
                    orcamento_id, numero, vencimento, valor, 
                    forma_pagamento, forma_pagamento_id, status
                ) VALUES (%s, %s, %s, %s, %s, %s, 'pendente')
            """, [
                orcamento_id,
                dup.get('numero'),
                dup.get('vencimento'),
                dup.get('valor'),
                dup.get('forma_pagamento'),
                forma_pagamento_id
            ])
        
        print(f"[ORCAMENTO] Salvas {len(duplicatas)} duplicatas para orcamento {orcamento_id}")
        
        # =====================================================
        # REGISTRAR HISTÓRICO COM DETALHES DAS ALTERAÇÕES
        # =====================================================
        dados_novos_hist = {
            # Aba Dados
            'cliente_id': cliente_id,
            'vendedor_id': vendedor_id,
            'vendedor2_id': vendedor2_id,
            'contato': contato,
            'tipo_pedido': tipo_pedido,
            'canal_relacionamento': canal_relacionamento,
            'empresa_id': empresa_id,
            'fx_base_currency_code': fx_base_currency_code,
            'fx_target_currency_code': fx_target_currency_code,
            'fx_rate_date': fx_rate_date.isoformat() if fx_rate_date else None,
            'fx_rate_value': float(fx_rate_value) if fx_rate_value is not None else None,
            'fx_rate_source': fx_rate_source,
            'forma_pagamento_id': forma_pagamento_id,
            # Aba Transporte
            'transportadora_id': transportadora_id,
            'frete_por_conta': frete_por_conta,
            'obs_frete': obs_frete,
            'perfil_transporte': perfil_transporte,
            'especie': especie,
            'volumes_quantidade': volumes_quantidade,
            'peso_bruto': peso_bruto,
            'peso_liquido': peso_liquido,
            # Valores
            'valor_total': float(valor_total),
            'percentual_desconto': percentual_desconto,
            'valor_frete': valor_frete,
            # Observações
            'observacoes': observacoes,
            'observacoes_internas': observacoes_internas,
            'status': 'enviado' if acao == 'enviar' else 'rascunho'
        }
        
        if request.form.get('id'):
            # Gerar descrição detalhada das alterações
            descricao = gerar_descricao_alteracoes(dados_anteriores, dados_novos_hist)
            registrar_historico(
                orcamento_id, 
                'EDICAO', 
                descricao,
                dados_anteriores=dict(dados_anteriores) if dados_anteriores else None,
                dados_novos=dados_novos_hist
            )
        else:
            registrar_historico(
                orcamento_id, 
                'CRIACAO', 
                f'Orçamento criado com {len(itens)} itens - Total: R$ {valor_total:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.'),
                dados_novos=dados_novos_hist
            )
        
        if acao == 'enviar':
            registrar_historico(orcamento_id, 'STATUS_ALTERADO', 'Status alterado para: Enviado')
            flash('Orçamento salvo e enviado com sucesso!', 'success')
        else:
            flash('Orçamento salvo como rascunho.', 'success')
        
        return redirect(url_for('orcamentos.visualizar', id=orcamento_id))
        
    except Exception as e:
        import traceback
        print(f"[ERRO ORCAMENTO] {str(e)}")
        print(traceback.format_exc())
        flash(f'Erro ao salvar orçamento: {str(e)}', 'error')
        return redirect(request.referrer or url_for('orcamentos.lista'))


# =====================================================
# ALTERAR STATUS
# =====================================================

@orcamento_bp.route('/<int:id>/enviar', methods=['POST'])
def enviar(id):
    """Muda status para 'enviado'"""
    db = get_db()
    
    db.execute_query("""
        UPDATE orcamentos 
        SET status = 'enviado', updated_at = NOW(), created_by = %s
        WHERE id = %s AND status = 'rascunho'
    """, [get_usuario_logado(), id])
    
    registrar_historico(id, 'STATUS_ALTERADO', 'Status alterado de Rascunho para Enviado')
    
    flash('Orçamento enviado para o cliente!', 'success')
    return redirect(url_for('orcamentos.visualizar', id=id))


# =====================================================
# PRÉ-APROVAÇÃO - TELA DE SELEÇÃO DE ETAPAS
# =====================================================

@orcamento_bp.route('/<int:id>/pre-aprovar', methods=['GET'])
def pre_aprovar(id):
    """Tela de pré-aprovação com seleção de etapas para cada item"""
    db = get_db()
    
    # Buscar orçamento
    orc = db.fetch_one("""
        SELECT o.*, c.name as cliente_nome, e.nome_fantasia as empresa_nome
        FROM orcamentos o
        LEFT JOIN customers c ON c.id = o.cliente_id
        LEFT JOIN empresas e ON e.id = o.empresa_id
        WHERE o.id = %s
    """, (id,))
    
    if not orc:
        flash('Orçamento não encontrado', 'error')
        return redirect(url_for('orcamentos.lista'))
    
    if orc['status'] not in ('enviado', 'rascunho'):
        flash('Este orçamento não pode ser aprovado', 'warning')
        return redirect(url_for('orcamentos.visualizar', id=id))
    
    # Buscar itens do orçamento com informações de estoque e categoria
    itens = db.fetch_all("""
        SELECT
            oi.id as item_id,
            oi.produto_id,
            oi.quantidade,
            oi.preco_unitario,
            oi.valor_total,
            oi.unidade,
            p.name AS produto_nome,
            p.stock_quantity AS estoque_atual,
            pc.name AS categoria_nome,
            pc.categoria_fiscal,
            COALESCE(
                (SELECT SUM(er.quantidade) FROM estoque_reservas er 
                 WHERE er.produto_id = oi.produto_id AND er.status = 'confirmado'),
                0
            ) AS estoque_reservado
        FROM orcamento_itens oi
        INNER JOIN products p ON p.id = oi.produto_id
        LEFT JOIN product_categories pc ON pc.id = p.category_id
        WHERE oi.orcamento_id = %s
        ORDER BY oi.sequencia, oi.id
    """, (id,)) or []
    
    # Processar cada item
    itens_processados = []
    algum_item_gera_op = False  # Flag para verificar se algum item precisa de OP
    
    for item in itens:
        estoque_atual = float(item['estoque_atual'] or 0)
        estoque_reservado = float(item['estoque_reservado'] or 0)
        estoque_disponivel = estoque_atual - estoque_reservado
        quantidade = float(item['quantidade'])
        categoria_fiscal = (item['categoria_fiscal'] or '').strip().lower()
        
        # Determinar se vai gerar OP
        gera_op = False
        tipo_sugerido = None
        
        # Regra: só gera OP para produtos de PRODUÇÃO (categoria_fiscal específica)
        # Categorias que geram OP: produto_producao, produto_final
        # NÃO gera OP para: revenda, materia_prima, servico, insumo, etc.
        if categoria_fiscal in ('produto_producao', 'produto_final'):
            gera_op = True
            if estoque_disponivel >= quantidade:
                tipo_sugerido = 'separacao'
            elif estoque_disponivel > 0:
                tipo_sugerido = 'mista'
            else:
                tipo_sugerido = 'producao'
        
        if gera_op:
            algum_item_gera_op = True
        
        itens_processados.append({
            'item_id': item['item_id'],
            'produto_id': item['produto_id'],
            'produto_nome': item['produto_nome'],
            'quantidade': quantidade,
            'unidade': item['unidade'],
            'preco_unitario': float(item['preco_unitario'] or 0),
            'valor_total': float(item['valor_total'] or 0),
            'categoria_nome': item['categoria_nome'],
            'categoria_fiscal': categoria_fiscal,
            'estoque_atual': estoque_atual,
            'estoque_reservado': estoque_reservado,
            'estoque_disponivel': estoque_disponivel,
            'quantidade_abater': min(estoque_disponivel, quantidade) if estoque_disponivel > 0 else 0,
            'gera_op': gera_op,
            'tipo_sugerido': tipo_sugerido
        })
    
    # Se NENHUM item precisa gerar OP, aprovar direto sem mostrar tela de seleção de etapas
    if not algum_item_gera_op:
        # Aprovar diretamente
        db.execute_query("""
            UPDATE orcamentos
            SET status = 'aprovado', data_aprovacao = NOW(), updated_at = NOW(), created_by = %s
            WHERE id = %s AND status IN ('enviado', 'rascunho')
        """, [get_usuario_logado(), id])
        
        registrar_historico(id, 'APROVACAO', 'Orçamento aprovado (sem itens para produção)')
        # Gerar contas a receber a partir das duplicatas do orçamento
        try:
            _gerar_contas_receber_para_orcamento(db, id)
        except Exception as e:
            print(f"[ORCAMENTO->CR] Aviso: falha ao gerar contas a receber para orcamento {id}: {e}")
        flash('Orçamento aprovado com sucesso! Nenhum item requer ordem de produção.', 'success')
        return redirect(url_for('orcamentos.visualizar', id=id))
    
    # Buscar etapas disponíveis
    etapas = db.fetch_all("""
        SELECT id, nome, tipo_etapa, ordem
        FROM producao_etapas
        WHERE ativo = 1
        ORDER BY ordem, id
    """) or []
    
    return render_template(
        'comercial/orcamento_pre_aprovar.html',
        orcamento=orc,
        itens=itens_processados,
        etapas=etapas
    )


@orcamento_bp.route('/<int:id>/aprovar', methods=['POST'])
def aprovar(id):
    """Aprova o orçamento com etapas selecionadas"""
    db = get_db()
    
    # Coletar etapas selecionadas do formulário
    itens_selecionados = request.form.getlist('item_selecionado[]')
    etapas_por_item = {}
    for item_id in itens_selecionados:
        etapa_id = request.form.get(f'etapa_{item_id}')
        if etapa_id:
            etapas_por_item[int(item_id)] = int(etapa_id)

    db.execute_query("""
        UPDATE orcamentos
        SET status = 'aprovado', data_aprovacao = NOW(), updated_at = NOW(), created_by = %s
        WHERE id = %s AND status IN ('enviado', 'rascunho')
    """, [get_usuario_logado(), id])

    registrar_historico(id, 'APROVACAO', 'Orcamento aprovado pelo cliente/usuario')

    # =====================================================
    # GERAR OPs COM ETAPAS SELECIONADAS
    # =====================================================
    try:
        resultado_ops = _gerar_ops_para_orcamento(db, id, etapas_por_item)
        
        # Extrair informações do resultado
        ops_producao = resultado_ops.get('ops_producao', 0)
        ops_separacao = resultado_ops.get('ops_separacao', 0)
        reservas = resultado_ops.get('reservas_criadas', 0)
        total_ops = ops_producao + ops_separacao

        if total_ops > 0:
            registrar_historico(
                id,
                'GEROU_OP',
                f'Gerou {total_ops} OP(s): {ops_producao} produção, {ops_separacao} separação. {reservas} reservas de estoque.'
            )

        # Montar mensagem detalhada para o usuário
        msg_parts = [f'Orçamento aprovado!']
        if ops_separacao > 0:
            msg_parts.append(f'{ops_separacao} OP(s) de SEPARAÇÃO (produto em estoque)')
        if ops_producao > 0:
            msg_parts.append(f'{ops_producao} OP(s) de PRODUÇÃO')
        if reservas > 0:
            msg_parts.append(f'{reservas} reserva(s) de estoque criadas')
        if total_ops == 0:
            msg_parts.append('Nenhuma OP necessária.')
        
        # Gerar contas a receber a partir das duplicatas do orçamento
        try:
            _gerar_contas_receber_para_orcamento(db, id)
        except Exception as e:
            print(f"[ORCAMENTO->CR] Aviso: falha ao gerar contas a receber para orcamento {id}: {e}")

        flash(' | '.join(msg_parts), 'success')
        return redirect(url_for('ordem_producao.grupo_orcamento', orcamento_id=id))

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[ORCAMENTO->OP] Erro ao gerar OPs: {e}")
        flash('Orçamento aprovado, mas ocorreu um erro ao gerar as OPs. Verifique a migração e as tabelas de produção.', 'warning')
        return redirect(url_for('orcamentos.visualizar', id=id))


@orcamento_bp.route('/<int:id>/reprovar', methods=['POST'])
def reprovar(id):
    """Reprova o orçamento"""
    db = get_db()
    motivo = request.form.get('motivo', '')
    
    db.execute_query("""
        UPDATE orcamentos 
        SET status = 'reprovado', data_reprovacao = NOW(), updated_at = NOW(), created_by = %s
        WHERE id = %s AND status IN ('enviado', 'rascunho', 'aprovado')
    """, [get_usuario_logado(), id])
    
    registrar_historico(
        id, 'REJEICAO', 
        f'Orcamento reprovado. Motivo: {motivo}' if motivo else 'Orcamento reprovado',
        dados_novos={'motivo': motivo} if motivo else None
    )
    
    flash('Orçamento reprovado.', 'warning')
    return redirect(url_for('orcamentos.visualizar', id=id))


@orcamento_bp.route('/<int:id>/cancelar', methods=['POST'])
def cancelar(id):
    """Cancela o orçamento"""
    db = get_db()
    
    db.execute_query("""
        UPDATE orcamentos 
        SET status = 'cancelado', updated_at = NOW(), created_by = %s
        WHERE id = %s AND status IN ('rascunho', 'enviado')
    """, [get_usuario_logado(), id])
    
    registrar_historico(id, 'STATUS_ALTERADO', 'Orcamento cancelado')
    
    flash('Orçamento cancelado.', 'warning')
    return redirect(url_for('orcamentos.lista'))


# =====================================================
# CONVERTER EM PEDIDO
# =====================================================

@orcamento_bp.route('/<int:id>/converter', methods=['POST'])
def converter_em_pedido(id):
    """Gera OPs para o orçamento aprovado (substitui o antigo fluxo de pedido)."""
    db = get_db()
    
    try:
        orc = db.fetch_one("SELECT id, status FROM orcamentos WHERE id = %s", (id,))
        if not orc or orc.get('status') != 'aprovado':
            flash('Orçamento não encontrado ou não está aprovado.', 'error')
            return redirect(url_for('orcamentos.visualizar', id=id))

        resultado_ops = _gerar_ops_para_orcamento(db, id)
        
        ops_producao = resultado_ops.get('ops_producao', 0)
        ops_separacao = resultado_ops.get('ops_separacao', 0)
        reservas = resultado_ops.get('reservas_criadas', 0)
        total_ops = ops_producao + ops_separacao
        
        if total_ops > 0:
            registrar_historico(
                id,
                'GEROU_OP',
                f'Gerou {total_ops} OP(s): {ops_producao} produção, {ops_separacao} separação. {reservas} reservas.'
            )

        # Mensagem detalhada
        msg_parts = []
        if ops_separacao > 0:
            msg_parts.append(f'{ops_separacao} OP(s) SEPARAÇÃO (estoque)')
        if ops_producao > 0:
            msg_parts.append(f'{ops_producao} OP(s) PRODUÇÃO')
        if reservas > 0:
            msg_parts.append(f'{reservas} reserva(s) estoque')
        
        flash(' | '.join(msg_parts) if msg_parts else 'Nenhuma OP gerada.', 'success' if total_ops > 0 else 'info')
        return redirect(url_for('ordem_producao.grupo_orcamento', orcamento_id=id))
        
    except Exception as e:
        flash(f'Erro ao gerar OPs do orçamento: {str(e)}', 'error')
        return redirect(url_for('orcamentos.visualizar', id=id))


# =====================================================
# DUPLICAR ORÇAMENTO
# =====================================================

@orcamento_bp.route('/<int:id>/duplicar', methods=['POST'])
def duplicar(id):
    """
    Cria uma cópia completa do orçamento incluindo:
    - Todos os dados principais
    - Dados de transporte e volumes
    - Itens do orçamento
    - Duplicatas/Parcelas de pagamento
    """
    db = get_db()
    
    try:
        # Buscar orçamento original com todos os campos
        original = db.fetch_one("SELECT * FROM orcamentos WHERE id = %s", [id])
        if not original:
            flash('Orçamento não encontrado.', 'error')
            return redirect(url_for('orcamentos.lista'))
        
        # Nova validade (15 dias a partir de hoje)
        nova_validade = (datetime.now() + timedelta(days=15)).strftime('%Y-%m-%d')
        
        # Criar cópia com TODOS os campos
        db.execute_query("""
            INSERT INTO orcamentos (
                -- Dados principais (Aba Dados)
                cliente_id, vendedor_id, vendedor2_id, contato, tipo_pedido, canal_relacionamento,
                empresa_id, data_validade, condicao_pagamento, forma_pagamento_id, prazo_entrega,
                -- Dados de transporte (Aba Transporte)
                frete_por_conta, obs_frete, perfil_transporte, transportadora_id,
                especie, volumes_quantidade, peso_bruto, peso_liquido,
                veiculo_placa, veiculo_uf, veiculo_rntc,
                -- Informações adicionais
                referencia_cliente, obs_validade, obs_entrega, obs_embalagem,
                obs_garantia, obs_certificado, icms_incluso, ipi_incluso,
                -- Valores calculados
                valor_frete, valor_produtos, percentual_desconto, valor_desconto, valor_total,
                -- Observações
                observacoes, observacoes_internas,
                -- Comissão
                comissao_vendedor1_percent, comissao_vendedor1_valor,
                comissao_vendedor2_percent, comissao_vendedor2_valor,
                -- Status e controle
                status, created_by
            ) VALUES (
                -- Dados principais
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                -- Transporte
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                -- Informações adicionais
                %s, %s, %s, %s, %s, %s, %s, %s,
                -- Valores
                %s, %s, %s, %s, %s,
                -- Observações
                %s, %s,
                -- Comissão
                %s, %s, %s, %s,
                -- Status
                'rascunho', %s
            )
        """, [
            # Dados principais
            original.get('cliente_id'), original.get('vendedor_id'), original.get('vendedor2_id'),
            original.get('contato'), original.get('tipo_pedido'), original.get('canal_relacionamento'),
            original.get('empresa_id'), nova_validade, original.get('condicao_pagamento'),
            original.get('forma_pagamento_id'), original.get('prazo_entrega'),
            # Transporte
            original.get('frete_por_conta'), original.get('obs_frete'), original.get('perfil_transporte'),
            original.get('transportadora_id'), original.get('especie'), original.get('volumes_quantidade'),
            original.get('peso_bruto'), original.get('peso_liquido'),
            original.get('veiculo_placa'), original.get('veiculo_uf'), original.get('veiculo_rntc'),
            # Informações adicionais
            original.get('referencia_cliente'), original.get('obs_validade'), original.get('obs_entrega'),
            original.get('obs_embalagem'), original.get('obs_garantia'), original.get('obs_certificado'),
            original.get('icms_incluso'), original.get('ipi_incluso'),
            # Valores
            original.get('valor_frete'), original.get('valor_produtos'), original.get('percentual_desconto'),
            original.get('valor_desconto'), original.get('valor_total'),
            # Observações
            original.get('observacoes'), original.get('observacoes_internas'),
            # Comissão
            original.get('comissao_vendedor1_percent'), original.get('comissao_vendedor1_valor'),
            original.get('comissao_vendedor2_percent'), original.get('comissao_vendedor2_valor'),
            # Usuario
            get_usuario_logado()
        ])
        
        # Pegar ID da cópia
        result = db.fetch_one("SELECT LAST_INSERT_ID() AS id")
        novo_id = result['id']
        
        # Copiar itens do orçamento
        db.execute_query("""
            INSERT INTO orcamento_itens (
                orcamento_id, produto_id, quantidade, unidade,
                preco_tabela, preco_unitario, percentual_desconto,
                valor_desconto, valor_total,
                largura, comprimento, espessura, tipo_correia, material,
                observacao, sequencia
            )
            SELECT 
                %s, produto_id, quantidade, unidade,
                preco_tabela, preco_unitario, percentual_desconto,
                valor_desconto, valor_total,
                largura, comprimento, espessura, tipo_correia, material,
                observacao, sequencia
            FROM orcamento_itens
            WHERE orcamento_id = %s
        """, [novo_id, id])
        
        # Copiar duplicatas/parcelas de pagamento
        db.execute_query("""
            INSERT INTO orcamento_duplicatas (
                orcamento_id, numero, vencimento, valor,
                forma_pagamento, forma_pagamento_id, status
            )
            SELECT 
                %s, numero, 
                DATE_ADD(vencimento, INTERVAL DATEDIFF(%s, %s) DAY),
                valor, forma_pagamento, forma_pagamento_id, 'pendente'
            FROM orcamento_duplicatas
            WHERE orcamento_id = %s
        """, [novo_id, nova_validade, original.get('data_validade') or datetime.now().strftime('%Y-%m-%d'), id])
        
        # Registrar no histórico
        registrar_historico(novo_id, 'CRIACAO', f'Orçamento duplicado do #{original.get("numero", id)}')
        
        flash(f'Orçamento duplicado com sucesso!', 'success')
        return redirect(url_for('orcamentos.editar', id=novo_id))
        
    except Exception as e:
        print(f"[DUPLICAR] Erro: {e}")
        flash(f'Erro ao duplicar orçamento: {str(e)}', 'error')
        return redirect(url_for('orcamentos.visualizar', id=id))


# =====================================================
# API: FX POR EMPRESA
# =====================================================

@orcamento_bp.route('/api/fx-empresa')
def api_fx_empresa():
    """Retorna informações de câmbio (FX) para a empresa selecionada."""
    db = get_db()
    empresa_id = request.args.get('empresa_id')

    try:
        empresa_id_int = int(empresa_id) if empresa_id else None
    except (TypeError, ValueError):
        empresa_id_int = None

    if not empresa_id_int:
        return jsonify({'success': False, 'error': 'empresa_id inválido'}), 400

    empresa = db.fetch_one(
        "SELECT id, moeda_funcional FROM empresas WHERE id = %s",
        (empresa_id_int,),
    )
    if not empresa:
        return jsonify({'success': False, 'error': 'Empresa não encontrada'}), 404

    fx_info = calcular_fx_para_empresa(db, empresa_id_int)
    if not fx_info:
        # Retorna apenas a moeda funcional (se houver), sem taxa
        return jsonify({
            'success': True,
            'empresa_id': empresa['id'],
            'moeda_funcional': empresa.get('moeda_funcional'),
            'fx_base_currency_code': None,
            'fx_target_currency_code': None,
            'fx_rate_value': None,
            'fx_rate_date': None,
            'fx_rate_source': None,
        })

    return jsonify({
        'success': True,
        'empresa_id': empresa['id'],
        'moeda_funcional': empresa.get('moeda_funcional'),
        'fx_base_currency_code': fx_info['base_currency'],
        'fx_target_currency_code': fx_info['target_currency'],
        'fx_rate_value': fx_info['rate_value'],
        'fx_rate_date': fx_info['rate_date'].isoformat() if fx_info['rate_date'] else None,
        'fx_rate_source': fx_info['rate_source'],
    })


# =====================================================
# API: BUSCAR PRODUTOS
# =====================================================

@orcamento_bp.route('/api/buscar-produtos')
def api_buscar_produtos():
    """API para buscar produtos por código ou nome"""
    db = get_db()
    termo = request.args.get('q', '')

    modo_all, parts = parse_star_search(termo)

    if not modo_all and (not parts or len(''.join(parts)) < 2):
        return jsonify([])

    where_parts = []
    params = []

    where_parts.append('active = 1')

    if modo_all:
        limit = 200
    else:
        clause, clause_params = build_multi_part_like_where(
            parts,
            ['internal_code', 'name', 'barcode']
        )
        if clause:
            where_parts.append(f"({clause})")
            params.extend(clause_params)
        limit = 50

    where_sql = " AND ".join(where_parts)

    produtos = db.fetch_all(f"""
        SELECT
            id, internal_code AS codigo, name AS nome,
            price AS preco, unit_measure AS unidade,
            stock_quantity AS estoque
        FROM products
        WHERE {where_sql}
        ORDER BY name
        LIMIT {limit}
    """, params)

    return jsonify(produtos or [])


# =====================================================
# API: BUSCAR CLIENTES
# =====================================================

@orcamento_bp.route('/api/buscar-clientes')
def api_buscar_clientes():
    """API para buscar clientes por nome ou documento"""
    db = get_db()
    termo = request.args.get('q', '')
    
    if len(termo) < 2:
        return jsonify([])
    
    clientes = db.fetch_all("""
        SELECT 
            id, name AS nome, cnpj AS documento,
            phone AS telefone, email, city AS cidade, state AS estado
        FROM customers
        WHERE active = 1
        AND (name LIKE %s OR cnpj LIKE %s)
        ORDER BY name
        LIMIT 20
    """, [f'%{termo}%', f'%{termo}%'])
    
    return jsonify(clientes or [])


# =====================================================
# API - BUSCAR TRANSPORTADORAS
# =====================================================

@orcamento_bp.route('/api/buscar-transportadoras')
def api_buscar_transportadoras():
    """Busca transportadoras para autocomplete"""
    termo = request.args.get('q', '')
    
    if len(termo) < 2:
        return jsonify([])
    
    db = get_db()
    
    # Buscar na tabela de transportadoras
    transportadoras = db.fetch_all("""
        SELECT 
            id, nome, cnpj AS documento,
            telefone, email, cidade, estado
        FROM transportadoras
        WHERE active = 1
        AND (nome LIKE %s OR cnpj LIKE %s OR codigo LIKE %s)
        ORDER BY nome
        LIMIT 20
    """, [f'%{termo}%', f'%{termo}%', f'%{termo}%'])
    
    return jsonify(transportadoras or [])


# =====================================================
# GERAR PDF
# =====================================================

@orcamento_bp.route('/<int:id>/pdf')
def gerar_pdf(id):
    """Gera PDF do orçamento"""
    db = get_db()
    
    # Buscar orçamento com dados do cliente e vendedor
    orcamento = db.fetch_one("""
        SELECT o.*, 
               c.name AS cliente_nome,
               c.cnpj AS cliente_documento,
               c.address AS cliente_endereco,
               c.number AS cliente_numero,
               c.neighborhood AS cliente_bairro,
               c.city AS cliente_cidade,
               c.state AS cliente_estado,
               c.cep AS cliente_cep,
               c.phone AS cliente_telefone,
               c.email AS cliente_email,
               c.ie AS cliente_ie,
               u.name AS vendedor_nome,
               u.phone AS vendedor_telefone,
               u.email AS vendedor_email,
               t.nome AS transportadora_nome,
               t.cnpj AS transportadora_cnpj
        FROM orcamentos o
        LEFT JOIN customers c ON o.cliente_id = c.id
        LEFT JOIN users u ON o.vendedor_id = u.id
        LEFT JOIN transportadoras t ON o.transportadora_id = t.id
        WHERE o.id = %s
    """, [id])
    
    if not orcamento:
        flash('Orcamento nao encontrado.', 'error')
        return redirect(url_for('orcamentos.lista'))
    
    # Buscar itens
    itens = db.fetch_all("""
        SELECT oi.*, 
               p.name AS produto_nome, 
               p.internal_code AS produto_codigo,
               p.description AS produto_descricao
        FROM orcamento_itens oi
        LEFT JOIN products p ON oi.produto_id = p.id
        WHERE oi.orcamento_id = %s
        ORDER BY oi.sequencia
    """, [id])
    
    # Buscar dados da empresa (tabela empresas)
    empresa_id = orcamento.get('empresa_id', 1)
    empresa = db.fetch_one("""
        SELECT id, razao_social, nome_fantasia, cnpj, inscricao_estadual,
               logradouro, numero, bairro, cidade, estado, cep,
               telefone, email, logo_path
        FROM empresas WHERE id = %s
    """, [empresa_id]) or {}
    
    # Gerar PDF
    try:
        from app.services.orcamento_pdf import gerar_pdf_orcamento
        
        pdf_buffer = gerar_pdf_orcamento(orcamento, itens, empresa)
        
        # Registrar no histórico
        registrar_historico(id, 'IMPRESSAO', f"PDF do orcamento gerado")
        
        # Retornar PDF
        response = make_response(pdf_buffer.getvalue())
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'inline; filename=orcamento_{orcamento.get("numero", id)}.pdf'
        return response
        
    except Exception as e:
        print(f"[PDF] Erro ao gerar PDF: {e}")
        flash(f'Erro ao gerar PDF: {str(e)}', 'error')
        return redirect(url_for('orcamentos.visualizar', id=id))


@orcamento_bp.route('/<int:id>/pdf/download')
def download_pdf(id):
    """Download do PDF do orçamento"""
    db = get_db()
    
    # Buscar orçamento com dados completos
    orcamento = db.fetch_one("""
        SELECT o.*, 
               c.name AS cliente_nome,
               c.cnpj AS cliente_documento,
               c.address AS cliente_endereco,
               c.number AS cliente_numero,
               c.neighborhood AS cliente_bairro,
               c.city AS cliente_cidade,
               c.state AS cliente_estado,
               c.cep AS cliente_cep,
               c.phone AS cliente_telefone,
               c.email AS cliente_email,
               c.ie AS cliente_ie,
               u.name AS vendedor_nome,
               t.nome AS transportadora_nome
        FROM orcamentos o
        LEFT JOIN customers c ON o.cliente_id = c.id
        LEFT JOIN users u ON o.vendedor_id = u.id
        LEFT JOIN transportadoras t ON o.transportadora_id = t.id
        WHERE o.id = %s
    """, [id])
    
    if not orcamento:
        flash('Orcamento nao encontrado.', 'error')
        return redirect(url_for('orcamentos.lista'))
    
    # Buscar itens
    itens = db.fetch_all("""
        SELECT oi.*, p.name AS produto_nome, p.internal_code AS produto_codigo
        FROM orcamento_itens oi
        LEFT JOIN products p ON oi.produto_id = p.id
        WHERE oi.orcamento_id = %s
        ORDER BY oi.sequencia
    """, [id])
    
    # Buscar empresa
    empresa_id = orcamento.get('empresa_id', 1)
    empresa = db.fetch_one("""
        SELECT id, razao_social, nome_fantasia, cnpj, inscricao_estadual,
               logradouro, numero, bairro, cidade, estado, cep,
               telefone, email, logo_path
        FROM empresas WHERE id = %s
    """, [empresa_id]) or {}
    
    try:
        from app.services.orcamento_pdf import gerar_pdf_orcamento
        
        pdf_buffer = gerar_pdf_orcamento(orcamento, itens, empresa)
        
        response = make_response(pdf_buffer.getvalue())
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename=orcamento_{orcamento.get("numero", id)}.pdf'
        return response
        
    except Exception as e:
        flash(f'Erro ao gerar PDF: {str(e)}', 'error')
        return redirect(url_for('orcamentos.visualizar', id=id))


# =====================================================
# ENVIAR EMAIL
# =====================================================

@orcamento_bp.route('/<int:id>/enviar-email', methods=['POST'])
def enviar_email(id):
    """Envia orçamento por email"""
    db = get_db()
    
    # Buscar orçamento com dados completos
    orcamento = db.fetch_one("""
        SELECT o.*, 
               c.name AS cliente_nome,
               c.email AS cliente_email,
               c.cnpj AS cliente_documento,
               c.address AS cliente_endereco,
               c.number AS cliente_numero,
               c.neighborhood AS cliente_bairro,
               c.city AS cliente_cidade,
               c.state AS cliente_estado,
               c.cep AS cliente_cep,
               c.phone AS cliente_telefone,
               c.ie AS cliente_ie,
               u.name AS vendedor_nome,
               t.nome AS transportadora_nome
        FROM orcamentos o
        LEFT JOIN customers c ON o.cliente_id = c.id
        LEFT JOIN users u ON o.vendedor_id = u.id
        LEFT JOIN transportadoras t ON o.transportadora_id = t.id
        WHERE o.id = %s
    """, [id])
    
    if not orcamento:
        flash('Orcamento nao encontrado.', 'error')
        return redirect(url_for('orcamentos.lista'))
    
    # Obter email do destinatário
    email_destino = request.form.get('email') or orcamento.get('cliente_email')
    assunto = request.form.get('assunto', f"Orcamento {orcamento.get('numero')}")
    mensagem = request.form.get('mensagem', '')
    
    if not email_destino:
        flash('Email do cliente nao informado.', 'error')
        return redirect(url_for('orcamentos.visualizar', id=id))
    
    # Buscar itens
    itens = db.fetch_all("""
        SELECT oi.*, p.name AS produto_nome, p.internal_code AS produto_codigo
        FROM orcamento_itens oi
        LEFT JOIN products p ON oi.produto_id = p.id
        WHERE oi.orcamento_id = %s
        ORDER BY oi.sequencia
    """, [id])
    
    # Buscar empresa
    empresa_id = orcamento.get('empresa_id', 1)
    empresa = db.fetch_one("""
        SELECT id, razao_social, nome_fantasia, cnpj, inscricao_estadual,
               logradouro, numero, bairro, cidade, estado, cep,
               telefone, email, logo_path
        FROM empresas WHERE id = %s
    """, [empresa_id]) or {}
    
    try:
        from app.services.orcamento_pdf import gerar_pdf_orcamento
        from app.services.email_service import enviar_email_com_anexo
        
        # Gerar PDF
        pdf_buffer = gerar_pdf_orcamento(orcamento, itens, empresa)
        
        # Formatar mensagem (substituir quebras de linha por <br>)
        mensagem_html = (mensagem or 'Segue em anexo o orçamento solicitado.').replace('\n', '<br>')
        
        # Nome da empresa
        nome_empresa = empresa.get('nome_fantasia') or empresa.get('razao_social', '')
        telefone_empresa = empresa.get('telefone', '')
        
        # Montar corpo do email
        corpo_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #0d7377; border-bottom: 2px solid #0d7377; padding-bottom: 10px;">
                    Orçamento {orcamento.get('numero')}
                </h2>
                <p>Prezado(a) <strong>{orcamento.get('cliente_nome', 'Cliente')}</strong>,</p>
                <p>{mensagem_html}</p>
                <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
                    <p style="margin: 5px 0;"><strong>Valor Total:</strong> 
                        <span style="color: #0d7377; font-size: 18px;">{formatar_moeda(orcamento.get('valor_total'))}</span>
                    </p>
                    <p style="margin: 5px 0;"><strong>Validade:</strong> {formatar_data(orcamento.get('data_validade'))}</p>
                </div>
                <hr style="border: none; border-top: 1px solid #ddd;">
                <p style="color: #666; font-size: 12px;">
                    Este email foi enviado automaticamente pelo sistema.<br>
                    <strong>{nome_empresa}</strong><br>
                    {telefone_empresa}
                </p>
            </div>
        </body>
        </html>
        """
        
        # Enviar email com configurações da empresa
        resultado = enviar_email_com_anexo(
            destinatario=email_destino,
            assunto=assunto,
            corpo_html=corpo_html,
            anexo=pdf_buffer.getvalue(),
            nome_anexo=f"orcamento_{orcamento.get('numero', id)}.pdf",
            empresa_id=empresa_id
        )
        
        if resultado:
            # Registrar no histórico
            registrar_historico(id, 'ENVIO_EMAIL', f"Orcamento enviado por email para {email_destino}")
            
            # Atualizar status para enviado se ainda estiver como rascunho
            if orcamento.get('status') == 'rascunho':
                db.execute_query("UPDATE orcamentos SET status = 'enviado' WHERE id = %s", [id])
            
            flash(f'Orcamento enviado com sucesso para {email_destino}!', 'success')
        else:
            flash('Erro ao enviar email. Verifique as configuracoes.', 'error')
        
    except ImportError:
        flash('Servico de email nao configurado. Configure as credenciais SMTP.', 'warning')
    except Exception as e:
        print(f"[EMAIL] Erro ao enviar: {e}")
        flash(f'Erro ao enviar email: {str(e)}', 'error')
    
    return redirect(url_for('orcamentos.visualizar', id=id))


# =====================================================
# API: INSUMOS DO PRODUTO (para aba Outros)
# =====================================================

@orcamento_bp.route('/api/produto/<int:produto_id>/insumos')
def api_insumos_produto(produto_id):
    """
    Retorna os insumos/componentes de um produto para fabricação.
    Busca do template de produção cadastrado (produto_templates_producao).
    Usado na aba "Outros" do orçamento para mostrar o template de produção.
    """
    db = get_db()
    
    try:
        # Buscar dados do produto
        produto = db.fetch_one("""
            SELECT id, internal_code as code, name, description, unit_measure, cost_price 
            FROM products 
            WHERE id = %s
        """, [produto_id])
        
        if not produto:
            return jsonify({'error': 'Produto não encontrado', 'insumos': []})
        
        # Buscar template de produção ativo para este produto
        template = db.fetch_one("""
            SELECT id, nome_template, custo_total_base, tempo_producao_horas
            FROM produto_templates_producao 
            WHERE produto_id = %s AND ativo = 1
            ORDER BY versao DESC
            LIMIT 1
        """, [produto_id])
        
        if not template:
            return jsonify({
                'produto': {
                    'id': produto['id'],
                    'codigo': produto['code'],
                    'nome': produto['name'],
                    'custo': float(produto['cost_price'] or 0)
                },
                'template': None,
                'insumos': [],
                'servicos': [],
                'materias_primas': [],
                'consumo_interno': [],
                'mensagem': 'Produto sem template de produção cadastrado'
            })
        
        # Buscar todos os itens do template agrupados por tipo
        itens = db.fetch_all("""
            SELECT 
                pti.id,
                pti.tipo_item,
                pti.produto_id,
                pti.descricao,
                pti.quantidade,
                pti.unidade_medida,
                pti.custo_unitario_base,
                pti.custo_total_base,
                p.internal_code as produto_codigo,
                p.name as produto_nome,
                p.cost_price as custo_atual
            FROM produto_template_itens pti
            LEFT JOIN products p ON pti.produto_id = p.id
            WHERE pti.template_id = %s
            ORDER BY pti.tipo_item, pti.id
        """, [template['id']])
        
        # Separar por tipo
        servicos = []
        materias_primas = []
        consumo_interno = []
        todos_insumos = []
        
        for item in (itens or []):
            insumo = {
                'id': item['id'],
                'tipo': item['tipo_item'],
                'codigo': item['produto_codigo'] or '',
                'nome': item['produto_nome'] or item['descricao'] or '',
                'descricao': item['descricao'] or '',
                'quantidade': float(item['quantidade'] or 0),
                'unidade': item['unidade_medida'] or 'UN',
                'custo_unitario': float(item['custo_unitario_base'] or item['custo_atual'] or 0),
                'custo_total': float(item['custo_total_base'] or 0)
            }
            
            todos_insumos.append(insumo)
            
            if item['tipo_item'] == 'servico':
                servicos.append(insumo)
            elif item['tipo_item'] == 'materia_prima':
                materias_primas.append(insumo)
            elif item['tipo_item'] == 'consumo_interno':
                consumo_interno.append(insumo)
        
        # Calcular totais
        total_servicos = sum(i['custo_total'] for i in servicos)
        total_materias = sum(i['custo_total'] for i in materias_primas)
        total_consumo = sum(i['custo_total'] for i in consumo_interno)
        total_geral = total_servicos + total_materias + total_consumo
        
        return jsonify({
            'produto': {
                'id': produto['id'],
                'codigo': produto['code'],
                'nome': produto['name'],
                'custo': float(produto['cost_price'] or 0)
            },
            'template': {
                'id': template['id'],
                'nome': template['nome_template'],
                'custo_base': float(template['custo_total_base'] or 0),
                'tempo_horas': float(template['tempo_producao_horas'] or 0)
            },
            'insumos': todos_insumos,
            'servicos': servicos,
            'materias_primas': materias_primas,
            'consumo_interno': consumo_interno,
            'totais': {
                'servicos': total_servicos,
                'materias_primas': total_materias,
                'consumo_interno': total_consumo,
                'total': total_geral
            }
        })
        
    except Exception as e:
        print(f"[API INSUMOS] Erro: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e), 'insumos': []})


# =====================================================
# API: COMISSÃO PADRÃO DO VENDEDOR
# =====================================================

@orcamento_bp.route('/api/vendedor/<int:vendedor_id>/comissao')
def api_comissao_vendedor(vendedor_id):
    """
    Retorna a comissão padrão do vendedor.
    Usado na aba Comissão para preencher automaticamente a alíquota.
    Campo: commission (cadastro de usuário)
    """
    db = get_db()
    
    try:
        vendedor = db.fetch_one("""
            SELECT id, name, commission 
            FROM users 
            WHERE id = %s AND is_seller = 1
        """, [vendedor_id])
        
        if not vendedor:
            return jsonify({'error': 'Vendedor não encontrado', 'comissao_padrao': 0})
        
        comissao = float(vendedor['commission'] or 0)
        print(f"[API COMISSAO] Vendedor ID={vendedor_id}, Nome={vendedor['name']}, Comissao={comissao}%")
        
        return jsonify({
            'id': vendedor['id'],
            'nome': vendedor['name'],
            'comissao_padrao': comissao
        })
        
    except Exception as e:
        print(f"[API COMISSAO] Erro: {e}")
        return jsonify({'error': str(e), 'comissao_padrao': 0})
