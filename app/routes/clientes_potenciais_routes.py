from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from functools import wraps
from datetime import datetime
import sys
import os

# Adicionar o diretório pai ao path para importar database
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from database import get_db
from utils.auth import login_required

# Criar um Blueprint para as rotas de clientes em potencial
clientes_potenciais_bp = Blueprint('clientes_potenciais', __name__)


# Rota para listar todos os clientes em potencial
@clientes_potenciais_bp.route('/clientes-potenciais')
@login_required
def lista():
    try:
        db = get_db()
        
        # Paginação
        page = request.args.get('page', 1, type=int)
        per_page = 20
        offset = (page - 1) * per_page
        
        # Busca
        search_term = request.args.get('search_term', '').strip()
        search_field = request.args.get('search_field', 'all')
        
        # Query base - usando VIEW com nome do município
        # Inclui JOIN com tabela de CNAE para permitir busca por descrição
        base_query = """
            FROM vw_estabelecimentos_completos ef
            LEFT JOIN cnae20 c ON c.subclasse_codigo = ef.CNAE_FISCAL_PRINCIPAL
            WHERE 1=1
        """
        
        # Adicionar filtro de busca (suporta múltiplos termos separados por espaço)
        where_clauses = []
        params = []

        if search_term:
            tokens = [t.strip() for t in search_term.split() if t.strip()]

            if search_field == 'all':
                # Cada termo gera um bloco de OR em todos os campos relevantes, combinados com AND entre si
                for token in tokens:
                    search_param = f"%{token}%"
                    where_clauses.append("""(
                        ef.RAZAO_SOCIAL LIKE %s OR
                        ef.CNPJ_COMPLETO LIKE %s OR
                        ef.MUNICIPIO LIKE %s OR
                        ef.UF LIKE %s OR
                        ef.CNAE_FISCAL_PRINCIPAL LIKE %s OR
                        c.subclasse_descricao LIKE %s OR
                        ef.LOGRADOURO LIKE %s OR
                        ef.BAIRRO LIKE %s OR
                        ef.PORTE_EMPRESA LIKE %s
                    )""")
                    params.extend([search_param] * 9)
            elif search_field == 'razao_social':
                for token in tokens:
                    where_clauses.append("ef.RAZAO_SOCIAL LIKE %s")
                    params.append(f"%{token}%")
            elif search_field == 'cnpj':
                for token in tokens:
                    where_clauses.append("ef.CNPJ_COMPLETO LIKE %s")
                    params.append(f"%{token}%")
            elif search_field == 'municipio':
                for token in tokens:
                    where_clauses.append("ef.MUNICIPIO LIKE %s")
                    params.append(f"%{token}%")
            elif search_field == 'uf':
                for token in tokens:
                    where_clauses.append("ef.UF LIKE %s")
                    params.append(f"%{token}%")
            elif search_field == 'cnae':
                for token in tokens:
                    search_param = f"%{token}%"
                    where_clauses.append("(ef.CNAE_FISCAL_PRINCIPAL LIKE %s OR c.subclasse_descricao LIKE %s)")
                    params.extend([search_param, search_param])

        where_clause = ""
        if where_clauses:
            where_clause = " AND " + " AND ".join(where_clauses)
        
        # Contar total de registros
        count_query = f"SELECT COUNT(*) as total {base_query} {where_clause}"
        total_result = db.fetch_one(count_query, params)
        total = total_result['total'] if total_result else 0
        total_pages = (total + per_page - 1) // per_page
        
        # Buscar registros paginados
        data_query = f"""
            SELECT 
                id,
                CNPJ_COMPLETO as CNPJ,
                RAZAO_SOCIAL,
                NOME_FANTASIA,
                CNAE_FISCAL_PRINCIPAL,
                MUNICIPIO,
                UF,
                DDD1 as DDD_1,
                TELEFONE1 as TELEFONE_1,
                DDD2 as DDD_2,
                TELEFONE2 as TELEFONE_2,
                EMAIL,
                LATITUDE,
                LONGITUDE,
                LOGRADOURO,
                NUMERO,
                COMPLEMENTO,
                BAIRRO,
                CEP,
                PORTE_EMPRESA as PORTE,
                CAPITAL_SOCIAL
            {base_query} {where_clause}
            ORDER BY RAZAO_SOCIAL
            LIMIT %s OFFSET %s
        """
        params.extend([per_page, offset])
        clientes = db.fetch_all(data_query, params)
        
        return render_template(
            'clientes_potenciais_list.html',
            clientes=clientes,
            page=page,
            per_page=per_page,
            total=total,
            total_pages=total_pages,
            search_term=search_term,
            search_field=search_field
        )
    
    except Exception as e:
        flash(f'Erro ao carregar clientes em potencial: {str(e)}', 'danger')
        return redirect(url_for('dashboard'))

# Rota para visualizar um cliente em potencial
@clientes_potenciais_bp.route('/clientes-potenciais/visualizar/<int:id>')
@login_required
def visualizar(id):
    try:
        db = get_db()
        
        # Buscar dados completos do cliente - usando VIEW com nome do município
        query = """
            SELECT *
            FROM vw_estabelecimentos_completos
            WHERE id = %s
        """
        
        cliente = db.fetch_one(query, [id])
        
        if not cliente:
            flash('Cliente em potencial não encontrado.', 'danger')
            return redirect(url_for('clientes_potenciais.lista'))
        
        return render_template('clientes_potenciais_view.html', cliente=cliente)
    
    except Exception as e:
        flash(f'Erro ao carregar dados do cliente: {str(e)}', 'danger')
        return redirect(url_for('clientes_potenciais.lista'))

# Rota para converter cliente potencial em cliente ativo
@clientes_potenciais_bp.route('/clientes-potenciais/tornar-cliente-ativo/<int:id>', methods=['POST'])
@login_required
def tornar_cliente_ativo(id):
    try:
        db = get_db()
        
        # Buscar dados completos do cliente potencial - usando VIEW com nome do município
        query = """
            SELECT *
            FROM vw_estabelecimentos_completos
            WHERE id = %s
        """
        
        cliente_potencial = db.fetch_one(query, [id])
        
        if not cliente_potencial:
            flash('Cliente em potencial não encontrado.', 'danger')
            return redirect(url_for('clientes_potenciais.lista'))
        
        # Verificar se já existe um cliente com este CNPJ
        existing_customer = db.fetch_one("""
            SELECT id FROM customers WHERE cnpj = %s
        """, [cliente_potencial['CNPJ_COMPLETO']])
        
        if existing_customer:
            flash(f'Já existe um cliente cadastrado com o CNPJ {cliente_potencial["CNPJ_COMPLETO"]}', 'warning')
            return redirect(url_for('clientes_potenciais.visualizar', id=id))
        
        # Preparar endereço
        address_parts = []
        if cliente_potencial.get('TIPO_LOGRADOURO'):
            address_parts.append(cliente_potencial['TIPO_LOGRADOURO'])
        if cliente_potencial.get('LOGRADOURO'):
            address_parts.append(cliente_potencial['LOGRADOURO'])
        
        address = ' '.join(address_parts) if address_parts else None
        number = cliente_potencial.get('NUMERO')
        complement = cliente_potencial.get('COMPLEMENTO')
        neighborhood = cliente_potencial.get('BAIRRO')
        
        # Preparar telefone principal
        phone = None
        if cliente_potencial.get('TELEFONE1'):
            ddd = cliente_potencial.get('DDD1', '')
            telefone = cliente_potencial['TELEFONE1']
            phone = f"({ddd}) {telefone}" if ddd else telefone
        
        # Preparar telefone secundário
        phone2 = None
        if cliente_potencial.get('TELEFONE2'):
            ddd2 = cliente_potencial.get('DDD2', '')
            telefone2 = cliente_potencial['TELEFONE2']
            phone2 = f"({ddd2}) {telefone2}" if ddd2 else telefone2
        
        # Inserir na tabela customers com TODOS os dados
        insert_query = """
            INSERT INTO customers (
                name,
                razao_social,
                cnpj,
                cnpj_basico,
                contact_name,
                phone,
                phone2,
                ddd,
                ddd2,
                email,
                address,
                number,
                complement,
                neighborhood,
                city,
                state,
                cep,
                tipo_logradouro,
                situacao_cadastral,
                data_situacao_cadastral,
                data_inicio_atividade,
                cnae_fiscal_principal,
                cnae_fiscal_secundaria,
                matriz_filial,
                porte_empresa,
                natureza_juridica,
                latitude,
                longitude,
                origem_cadastro,
                active
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
        """
        
        # Executar inserção
        customer_id = db.insert(insert_query, (
            cliente_potencial.get('RAZAO_SOCIAL'),  # name
            cliente_potencial.get('RAZAO_SOCIAL'),  # razao_social
            cliente_potencial.get('CNPJ_COMPLETO'),  # cnpj
            cliente_potencial.get('CNPJ_BASICO'),  # cnpj_basico
            cliente_potencial.get('NOME_FANTASIA'),  # contact_name
            phone,  # phone
            phone2,  # phone2
            cliente_potencial.get('DDD1'),  # ddd
            cliente_potencial.get('DDD2'),  # ddd2
            cliente_potencial.get('EMAIL'),  # email
            address,  # address
            number,  # number
            complement,  # complement
            neighborhood,  # neighborhood
            cliente_potencial.get('MUNICIPIO'),  # city
            cliente_potencial.get('UF'),  # state
            cliente_potencial.get('CEP'),  # cep
            cliente_potencial.get('TIPO_LOGRADOURO'),  # tipo_logradouro
            cliente_potencial.get('SITUACAO_CADASTRAL'),  # situacao_cadastral
            cliente_potencial.get('DATA_SITUACAO_CADASTRAL'),  # data_situacao_cadastral
            cliente_potencial.get('DATA_INICIO_ATIVIDADE'),  # data_inicio_atividade
            cliente_potencial.get('CNAE_FISCAL_PRINCIPAL'),  # cnae_fiscal_principal
            cliente_potencial.get('CNAE_FISCAL_SECUNDARIA'),  # cnae_fiscal_secundaria
            cliente_potencial.get('MATRIZ_FILIAL'),  # matriz_filial
            cliente_potencial.get('PORTE_EMPRESA'),  # porte_empresa
            cliente_potencial.get('NATUREZA_JURIDICA'),  # natureza_juridica
            cliente_potencial.get('LATITUDE'),  # latitude
            cliente_potencial.get('LONGITUDE'),  # longitude
            'receita_federal',  # origem_cadastro
            True  # active
        ))
        
        # Função para formatar CNAE (adicionar - e / se necessário)
        def formatar_cnae(cnae):
            """Formata CNAE para padrão XXXX-X/XX"""
            cnae_clean = cnae.replace('-', '').replace('/', '').strip()
            if len(cnae_clean) == 7:
                # Formato: 4711302 -> 4711-3/02
                return f"{cnae_clean[0:4]}-{cnae_clean[4]}/{cnae_clean[5:7]}"
            return cnae  # Se já estiver formatado ou tamanho diferente, retorna como está
        
        # Inserir CNAEs na tabela customer_cnae
        cnaes_inseridos = 0
        
        if cliente_potencial.get('CNAE_FISCAL_PRINCIPAL'):
            try:
                cnae_formatado = formatar_cnae(cliente_potencial['CNAE_FISCAL_PRINCIPAL'])
                db.insert("""
                    INSERT INTO customer_cnae (customer_id, subclasse_codigo, is_primary)
                    VALUES (%s, %s, TRUE)
                """, (customer_id, cnae_formatado))
                cnaes_inseridos += 1
            except Exception as e:
                flash(f'Aviso: CNAE principal não inserido: {str(e)}', 'warning')
        
        # Inserir CNAEs secundários (se houver)
        if cliente_potencial.get('CNAE_FISCAL_SECUNDARIA'):
            cnaes_secundarios = cliente_potencial['CNAE_FISCAL_SECUNDARIA'].split(',')
            for cnae in cnaes_secundarios:
                cnae = cnae.strip()
                if cnae:
                    try:
                        cnae_formatado = formatar_cnae(cnae)
                        db.insert("""
                            INSERT INTO customer_cnae (customer_id, subclasse_codigo, is_primary)
                            VALUES (%s, %s, FALSE)
                        """, (customer_id, cnae_formatado))
                        cnaes_inseridos += 1
                    except Exception as e:
                        flash(f'Aviso: CNAE secundário {cnae} não inserido: {str(e)}', 'warning')
        
        if cnaes_inseridos > 0:
            flash(f'Cliente "{cliente_potencial["RAZAO_SOCIAL"]}" convertido com sucesso! {cnaes_inseridos} CNAE(s) importado(s).', 'success')
        else:
            flash(f'Cliente "{cliente_potencial["RAZAO_SOCIAL"]}" convertido com sucesso! (Sem CNAEs)', 'success')
        
        # Redirecionar para a visualização do cliente na base de clientes
        return redirect(url_for('cliente.cliente_visualizar', id=customer_id))
    
    except Exception as e:
        flash(f'Erro ao converter cliente: {str(e)}', 'danger')
        return redirect(url_for('clientes_potenciais.visualizar', id=id))

# Rota API para buscar informações básicas (para uso futuro)
@clientes_potenciais_bp.route('/api/clientes-potenciais/<int:id>')
@login_required
def api_get_cliente(id):
    try:
        db = get_db()
        
        query = """
            SELECT 
                ef.id,
                ef.CNPJ_COMPLETO as CNPJ,
                ef.RAZAO_SOCIAL,
                ef.NOME_FANTASIA,
                ef.EMAIL,
                CONCAT(ef.DDD1, ef.TELEFONE1) as telefone,
                ef.MUNICIPIO,
                ef.UF,
                ef.LATITUDE,
                ef.LONGITUDE
            FROM vw_estabelecimentos_completos ef
            WHERE ef.id = %s
        """
        
        cliente = db.fetch_one(query, [id])
        
        if not cliente:
            return jsonify({'error': 'Cliente não encontrado'}), 404
        
        return jsonify(cliente)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Rota para estatísticas (opcional - para dashboard futuro)
@clientes_potenciais_bp.route('/clientes-potenciais/estatisticas')
@login_required
def estatisticas():
    try:
        db = get_db()
        
        # Total de clientes em potencial
        total_query = "SELECT COUNT(*) as total FROM vw_estabelecimentos_completos"
        total_result = db.fetch_one(total_query)
        total = total_result['total'] if total_result else 0
        
        # Por UF
        por_uf_query = """
            SELECT UF, COUNT(*) as total
            FROM vw_estabelecimentos_completos
            GROUP BY UF
            ORDER BY total DESC
            LIMIT 10
        """
        por_uf = db.fetch_all(por_uf_query)
        
        # Com geolocalização
        geo_query = """
            SELECT COUNT(*) as total
            FROM vw_estabelecimentos_completos
            WHERE LATITUDE IS NOT NULL
            AND LONGITUDE IS NOT NULL
        """
        geo_result = db.fetch_one(geo_query)
        com_geo = geo_result['total'] if geo_result else 0
        
        return jsonify({
            'total': total,
            'com_geolocalizacao': com_geo,
            'por_uf': por_uf
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500
