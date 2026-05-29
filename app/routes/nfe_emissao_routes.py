"""
ROTAS FLASK PARA EMISSÃO DE NF-e
- Vendas pendentes de NF-e
- Emissão manual (do zero)
- Histórico de NF-e emitidas
- Download de XML e DANFE
- Cancelamento de NF-e
"""

from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for, flash, send_file
from datetime import datetime
import json
import os

# Imports do sistema
try:
    from database import get_db
from utils.auth import login_required
    from services.nfe_service import NFeService
    from services.sefaz_service import SefazService
except ImportError:
    # Fallback para imports absolutos
    import sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
    from app.database import get_db
    from app.services.nfe_service import NFeService
    from app.services.sefaz_service import SefazService

# Blueprint
nfe_emissao_bp = Blueprint('nfe_emissao', __name__)




# ========================================
# ROTA DE TESTE
# ========================================

@nfe_emissao_bp.route('/nfe/teste')
def teste():
    """Rota de teste para verificar se blueprint está funcionando"""
    return "<h1>Blueprint NF-e funcionando!</h1><p>Se você está vendo isso, o blueprint está registrado corretamente.</p>"


@nfe_emissao_bp.route('/nfe/teste-db')
@login_required
def teste_db():
    """Testa conexão com banco de dados"""
    try:
        db = get_db()
        vendas = db.fetch_all("SELECT COUNT(*) as total FROM sales WHERE numero_nfe IS NULL")
        return f"<h1>Teste DB OK!</h1><p>Vendas sem NF-e: {vendas[0]['total'] if vendas else 0}</p>"
    except Exception as e:
        return f"<h1>Erro no DB!</h1><p>{str(e)}</p>"


@nfe_emissao_bp.route('/nfe/teste-template')
@login_required
def teste_template():
    """Testa renderização de template"""
    try:
        return render_template('nfe/vendas_pendentes.html',
                             vendas=[],
                             clientes=[],
                             empresas=[],
                             filtros={})
    except Exception as e:
        return f"<h1>Erro no Template!</h1><p>{str(e)}</p>"


# ========================================
# VENDAS PENDENTES DE NF-e
# ========================================

@nfe_emissao_bp.route('/nfe/vendas-pendentes')
@login_required
def vendas_pendentes():
    """
    Lista vendas finalizadas que ainda não possuem NF-e emitida
    Permite filtros por data, cliente e empresa
    """
    print("\n[NFE] Acessando rota /nfe/vendas-pendentes")
    try:
        print("[NFE] Iniciando get_db()")
        db = get_db()
        print("[NFE] Conexão com banco OK")
        
        # Filtros da URL
        data_inicio = request.args.get('data_inicio', '')
        data_fim = request.args.get('data_fim', '')
        cliente_id = request.args.get('cliente_id', '')
        empresa_id = request.args.get('empresa_id', '')
        
        # Query base
        query = """
            SELECT 
                s.id,
                s.sale_date,
                s.net_total as total_amount,
                s.payment_method,
                c.id as cliente_id,
                c.name as cliente_nome,
                COALESCE(c.cnpj, c.cpf) as cliente_documento,
                c.email,
                e.id as empresa_id,
                e.nome_fantasia as empresa_nome,
                e.cnpj as empresa_cnpj,
                COUNT(si.id) as qtd_itens
            FROM sales s
            LEFT JOIN customers c ON s.customer_id = c.id
            LEFT JOIN empresas e ON s.empresa_id = e.id
            LEFT JOIN sale_items si ON s.id = si.sale_id
            WHERE s.numero_nfe IS NULL
              AND s.status IN ('completed', 'confirmed')
        """
        
        params = []
        
        # Aplicar filtros
        if data_inicio:
            query += " AND s.sale_date >= %s"
            params.append(data_inicio)
        
        if data_fim:
            query += " AND s.sale_date <= %s"
            params.append(data_fim)
        
        if cliente_id:
            query += " AND s.customer_id = %s"
            params.append(cliente_id)
        
        if empresa_id:
            query += " AND s.empresa_id = %s"
            params.append(empresa_id)
        
        query += """
            GROUP BY s.id
            ORDER BY s.sale_date DESC
            LIMIT 100
        """
        
        # Buscar vendas
        vendas = db.fetch_all(query, tuple(params) if params else None)
        
        # Buscar clientes para filtro
        clientes = db.fetch_all("""
            SELECT DISTINCT c.id, c.name 
            FROM customers c
            INNER JOIN sales s ON c.id = s.customer_id
            WHERE s.numero_nfe IS NULL
            ORDER BY c.name
        """)
        
        # Buscar empresas para filtro
        empresas = db.fetch_all("""
            SELECT id, nome_fantasia 
            FROM empresas 
            WHERE usar_no_pdv = 1
            ORDER BY nome_fantasia
        """)
        
        return render_template('nfe/vendas_pendentes.html',
                             vendas=vendas,
                             clientes=clientes,
                             empresas=empresas,
                             filtros={
                                 'data_inicio': data_inicio,
                                 'data_fim': data_fim,
                                 'cliente_id': cliente_id,
                                 'empresa_id': empresa_id
                             })
    
    except Exception as e:
        import traceback
        print(f"\n[NFE] ERRO ao carregar vendas pendentes:")
        print(f"[NFE] Tipo: {type(e).__name__}")
        print(f"[NFE] Mensagem: {str(e)}")
        print(f"[NFE] Traceback:")
        traceback.print_exc()
        flash(f'Erro ao carregar vendas pendentes: {str(e)}', 'danger')
        return redirect(url_for('dashboard'))


@nfe_emissao_bp.route('/nfe/preview-venda/<int:venda_id>')
@login_required
def preview_venda(venda_id):
    """
    Retorna dados da venda em JSON para preview antes de emitir
    """
    try:
        db = get_db()
        
        # Buscar dados da venda
        venda = db.fetch_one("""
            SELECT 
                s.*,
                c.name as cliente_nome,
                COALESCE(c.cnpj, c.cpf) as cnpj_cpf,
                c.email,
                c.phone,
                c.address,
                c.city,
                c.state,
                c.cep as zip_code,
                e.nome_fantasia as empresa_nome,
                e.razao_social as empresa_razao,
                e.cnpj as empresa_cnpj,
                e.inscricao_estadual as empresa_ie
            FROM sales s
            LEFT JOIN customers c ON s.customer_id = c.id
            LEFT JOIN empresas e ON s.empresa_id = e.id
            WHERE s.id = %s
        """, (venda_id,))
        
        if not venda:
            return jsonify({'success': False, 'message': 'Venda não encontrada'}), 404
        
        # Buscar itens da venda
        itens = db.fetch_all("""
            SELECT 
                si.*,
                p.name as produto_nome,
                p.internal_code as produto_codigo,
                p.ncm,
                p.cfop_out as cfop,
                p.unit_measure
            FROM sale_items si
            JOIN products p ON si.product_id = p.id
            WHERE si.sale_id = %s
        """, (venda_id,))
        
        return jsonify({
            'success': True,
            'venda': dict(venda),
            'itens': [dict(item) for item in itens]
        })
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


# ========================================
# EMISSÃO MANUAL (DO ZERO)
# ========================================

@nfe_emissao_bp.route('/nfe/emitir-manual')
@login_required
def emitir_manual():
    """
    Formulário para emitir NF-e do zero (sem venda prévia)
    """
    try:
        db = get_db()
        
        # Buscar empresas ativas (igual ao editar)
        empresas = db.fetch_all("SELECT * FROM empresas WHERE ativo = 1")
        
        # Buscar clientes ativos
        clientes = db.fetch_all("""
            SELECT id, name, cnpj, cpf, ie, address, number, neighborhood, 
                   city, state, cep, codigo_municipio, email, phone
            FROM customers 
            WHERE active = 1
            ORDER BY name
        """)
        
        # Buscar produtos ativos (igual ao editar)
        produtos = db.fetch_all("SELECT * FROM products WHERE active = 1 ORDER BY name")
        
        return render_template('nfe/emitir_manual.html',
                             empresas=empresas,
                             clientes=clientes,
                             produtos=produtos)
    
    except Exception as e:
        flash(f'Erro ao carregar formulário: {str(e)}', 'danger')
        return redirect(url_for('nfe_emissao.vendas_pendentes'))


@nfe_emissao_bp.route('/nfe/proximo-numero', methods=['GET'])
@login_required
def proximo_numero():
    """Busca o próximo número de NF-e para a empresa e série"""
    try:
        db = get_db()
        empresa_id = int(request.args.get('empresa_id'))
        serie = int(request.args.get('serie', 1))
        
        # Detectar ambiente da empresa
        empresa = db.fetch_one("SELECT ambiente_nfe FROM empresas WHERE id = %s", (empresa_id,))
        ambiente = 'producao' if empresa and str(empresa.get('ambiente_nfe')) == '1' else 'homologacao'
        
        # 1. Buscar configuração da tabela de controle de numeração (por ambiente)
        config_num = db.fetch_one("""
            SELECT ultimo_numero FROM nfe_numeracao
            WHERE empresa_id = %s AND serie = %s AND ambiente = %s
        """, (empresa_id, serie, ambiente))
        
        # 2. Se existe configuração para este ambiente, usar ela como base
        # (mesmo que seja 0, significa que o usuário quer começar do 1)
        if config_num is not None:
            ultimo_config = int(config_num['ultimo_numero'])
            
            # Buscar se já emitiu alguma nota NESTE AMBIENTE após a configuração
            # (verificamos pela data de criação da config vs data de emissão da venda)
            resultado = db.fetch_one("""
                SELECT MAX(CAST(s.numero_nfe AS UNSIGNED)) as ultimo_numero
                FROM sales s
                JOIN nfe_numeracao n ON s.empresa_id = n.empresa_id 
                    AND s.serie_nfe = n.serie 
                    AND n.ambiente = %s
                WHERE s.empresa_id = %s 
                AND s.serie_nfe = %s
                AND s.numero_nfe IS NOT NULL
                AND s.numero_nfe REGEXP '^[0-9]+$'
                AND s.chave_acesso_nfe IS NOT NULL
                AND s.created_at >= n.created_at
                AND CAST(s.numero_nfe AS UNSIGNED) > %s
            """, (ambiente, empresa_id, serie, ultimo_config))
            
            ultimo_vendas_pos_config = resultado['ultimo_numero'] if resultado and resultado['ultimo_numero'] else 0
            
            # O próximo é o maior entre: config ou vendas após config
            ultimo_numero = max(ultimo_config, int(ultimo_vendas_pos_config))
            print(f"[NFE] Usando configuração de numeração - Ambiente: {ambiente}, Config: {ultimo_config}, Vendas pós-config: {ultimo_vendas_pos_config}")
        else:
            # 3. Se não existe configuração, usar último das vendas
            resultado = db.fetch_one("""
                SELECT MAX(CAST(numero_nfe AS UNSIGNED)) as ultimo_numero
                FROM sales
                WHERE empresa_id = %s 
                AND serie_nfe = %s
                AND numero_nfe IS NOT NULL
                AND numero_nfe REGEXP '^[0-9]+$'
                AND chave_acesso_nfe IS NOT NULL
            """, (empresa_id, serie))
            
            ultimo_numero = resultado['ultimo_numero'] if resultado and resultado['ultimo_numero'] else 0
            print(f"[NFE] Sem configuração de numeração para {ambiente} - Usando vendas: {ultimo_numero}")
        
        proximo = int(ultimo_numero) + 1
        
        print(f"[NFE] Próximo número para empresa {empresa_id}, série {serie}, ambiente {ambiente}: {proximo}")
        
        return jsonify({
            'success': True,
            'proximo_numero': proximo,
            'ultimo_numero': ultimo_numero
        })
    
    except Exception as e:
        print(f"[NFE] Erro ao buscar próximo número: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


# ========================================
# CONTROLE DE NUMERAÇÃO
# ========================================

@nfe_emissao_bp.route('/nfe/numeracao')
@login_required
def numeracao_config():
    """Página de configuração de numeração de NF-e"""
    try:
        db = get_db()
        
        # Buscar empresas
        empresas = db.fetch_all("SELECT id, nome_fantasia, razao_social FROM empresas WHERE ativo = 1 ORDER BY nome_fantasia")
        
        # Buscar configurações existentes
        numeracoes = db.fetch_all("""
            SELECT n.*, e.nome_fantasia 
            FROM nfe_numeracao n
            JOIN empresas e ON n.empresa_id = e.id
            ORDER BY e.nome_fantasia, n.serie, n.ambiente
        """)
        
        return render_template('nfe/numeracao_config.html', 
                             empresas=empresas, 
                             numeracoes=numeracoes)
    except Exception as e:
        flash(f'Erro ao carregar configurações: {str(e)}', 'danger')
        return redirect(url_for('nfe_emissao.historico'))


@nfe_emissao_bp.route('/nfe/numeracao/salvar', methods=['POST'])
@login_required
def numeracao_salvar():
    """Salva configuração de numeração"""
    try:
        db = get_db()
        data = request.json
        
        empresa_id = int(data.get('empresa_id'))
        serie = int(data.get('serie', 1))
        ambiente = data.get('ambiente', 'producao')
        ultimo_numero = int(data.get('ultimo_numero', 0))
        observacao = data.get('observacao', '')
        
        # Validar ambiente
        if ambiente not in ['homologacao', 'producao']:
            return jsonify({'success': False, 'message': 'Ambiente inválido'}), 400
        
        # Inserir ou atualizar
        existente = db.fetch_one("""
            SELECT id FROM nfe_numeracao 
            WHERE empresa_id = %s AND serie = %s AND ambiente = %s
        """, (empresa_id, serie, ambiente))
        
        if existente:
            db.execute_query("""
                UPDATE nfe_numeracao 
                SET ultimo_numero = %s, observacao = %s, updated_at = NOW()
                WHERE empresa_id = %s AND serie = %s AND ambiente = %s
            """, (ultimo_numero, observacao, empresa_id, serie, ambiente))
        else:
            db.execute_query("""
                INSERT INTO nfe_numeracao (empresa_id, serie, ambiente, ultimo_numero, observacao)
                VALUES (%s, %s, %s, %s, %s)
            """, (empresa_id, serie, ambiente, ultimo_numero, observacao))
        
        return jsonify({
            'success': True, 
            'message': f'Numeração configurada! Próxima NF-e será {ultimo_numero + 1}'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@nfe_emissao_bp.route('/nfe/numeracao/excluir/<int:id>', methods=['DELETE'])
@login_required
def numeracao_excluir(id):
    """Exclui configuração de numeração"""
    try:
        db = get_db()
        db.execute_query("DELETE FROM nfe_numeracao WHERE id = %s", (id,))
        return jsonify({'success': True, 'message': 'Configuração excluída!'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@nfe_emissao_bp.route('/nfe/configuracoes-empresa', methods=['GET'])
@login_required
def configuracoes_empresa():
    """
    Busca configurações de NF-e da empresa selecionada
    Retorna: ambiente_nfe (1=producao, 2=homologacao) e modelo_nfe (antigo/reforma)
    """
    try:
        db = get_db()
        empresa_id = int(request.args.get('empresa_id'))
        
        # Buscar configurações da empresa
        empresa = db.fetch_one("""
            SELECT 
                id,
                nome_fantasia,
                ambiente_nfe,
                modelo_nfe
            FROM empresas
            WHERE id = %s
        """, (empresa_id,))
        
        if not empresa:
            return jsonify({
                'success': False,
                'message': 'Empresa não encontrada'
            }), 404
        
        # Converter ambiente numérico para texto
        ambiente_nfe = empresa.get('ambiente_nfe', '2')  # Default: homologação
        ambiente_texto = 'producao' if ambiente_nfe == '1' else 'homologacao'
        
        # Modelo NFe
        modelo_nfe = empresa.get('modelo_nfe', 'antigo')  # Default: antigo
        
        return jsonify({
            'success': True,
            'empresa_id': empresa['id'],
            'nome_fantasia': empresa['nome_fantasia'],
            'ambiente_nfe': ambiente_nfe,
            'ambiente_texto': ambiente_texto,
            'modelo_nfe': modelo_nfe
        })
    
    except Exception as e:
        print(f"[NFE] Erro ao buscar configurações da empresa: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@nfe_emissao_bp.route('/nfe/salvar-manual', methods=['POST'])
@login_required
def salvar_manual():
    """
    Salva NF-e criada manualmente
    1. Cria venda no banco
    2. Adiciona itens
    3. Emite NF-e
    """
    try:
        db = get_db()
        data = request.json
        
        # Validações básicas
        if not data.get('empresa_id'):
            return jsonify({'success': False, 'message': 'Empresa é obrigatória'}), 400
        
        if not data.get('cliente_id'):
            return jsonify({'success': False, 'message': 'Cliente é obrigatório'}), 400
        
        if not data.get('itens') or len(data['itens']) == 0:
            return jsonify({'success': False, 'message': 'Adicione pelo menos um item'}), 400
        
        # Verificar se é edição ou criação
        venda_id = data.get('venda_id')
        
        # Somar desconto dos produtos + desconto adicional
        desconto_total = data.get('totais', {}).get('valor_desconto', 0) + data.get('totais', {}).get('valor_desconto_adicional', 0)
        
        if venda_id:
            # EDIÇÃO: Atualizar venda existente
            db.execute("""
                UPDATE sales SET
                    empresa_id = %s,
                    customer_id = %s,
                    sale_date = %s,
                    numero_nfe = %s,
                    serie_nfe = %s,
                    data_emissao_nfe = %s,
                    net_total = %s,
                    gross_total = %s,
                    discount_total = %s,
                    freight_total = %s,
                    payment_method = %s,
                    updated_at = NOW()
                WHERE id = %s
            """, (
                data['empresa_id'],
                data['cliente_id'],
                data.get('data_emissao'),
                data.get('numero_nfe'),
                data.get('serie'),
                data.get('data_emissao'),
                data.get('totais', {}).get('valor_total', data.get('total', 0)),
                data.get('totais', {}).get('valor_produtos', 0),
                desconto_total,
                data.get('totais', {}).get('valor_frete', 0),
                data.get('forma_pagamento', data.get('payment_method', 'dinheiro')),
                venda_id
            ))
            
            # Excluir itens antigos
            db.execute("DELETE FROM sale_items WHERE sale_id = %s", (venda_id,))
        else:
            # CRIAÇÃO: Criar nova venda
            venda_id = db.execute("""
            INSERT INTO sales (
                empresa_id, 
                customer_id, 
                sale_date, 
                numero_nfe,
                serie_nfe,
                data_emissao_nfe,
                net_total,
                gross_total,
                discount_total,
                freight_total,
                payment_method, 
                status, 
                created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'confirmed', NOW())
        """, (
            data['empresa_id'],
            data['cliente_id'],
            data.get('data_emissao'),
            data.get('numero_nfe'),
            data.get('serie'),
            data.get('data_emissao'),
            data.get('totais', {}).get('valor_total', data.get('total', 0)),
            data.get('totais', {}).get('valor_produtos', 0),
            desconto_total,
            data.get('totais', {}).get('valor_frete', 0),
            data.get('forma_pagamento', data.get('payment_method', 'dinheiro'))
        ))
        
        print(f"[NFE] Venda criada: ID {venda_id}")
        
        # 2. Adicionar itens
        for item in data['itens']:
            # Calcular desconto percentual
            subtotal = item['quantidade'] * item['valor_unitario']
            desconto_valor = item.get('desconto', 0)
            desconto_percent = (desconto_valor / subtotal * 100) if subtotal > 0 else 0
            total_price = subtotal - desconto_valor
            
            db.execute("""
                INSERT INTO sale_items (
                    sale_id, 
                    product_id, 
                    quantity, 
                    unit_price, 
                    discount_percent,
                    discount_value,
                    total_price,
                    ncm,
                    cfop,
                    unit_measure,
                    aliquota_icms,
                    aliquota_ipi
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                venda_id,
                item['produto_id'],
                item['quantidade'],
                item['valor_unitario'],
                desconto_percent,
                desconto_valor,
                total_price,
                item.get('ncm', ''),
                item.get('cfop', ''),
                item.get('unidade', 'UN'),
                item.get('aliq_icms', 0),
                item.get('aliq_ipi', 0)
            ))
        
        print(f"[NFE] {len(data['itens'])} itens adicionados")
        
        # 3. Emitir NF-e (se solicitado)
        if data.get('emitir_agora', True):
            nfe_service = NFeService(db=db)
            resultado = nfe_service.gerar_nfe(
                venda_id=venda_id,
                empresa_id=data['empresa_id'],
                serie=int(data.get('serie', 1)),
                numero=int(data.get('numero_nfe')) if data.get('numero_nfe') else None,
                enviar_para_sefaz=True
            )
            
            if resultado.get('sucesso'):
                # ========================================
                # ENVIO AUTOMÁTICO DE EMAIL
                # ========================================
                email_enviado = False
                try:
                    try:
                        from services.email_nfe_service import EmailNFeService
                    except ImportError:
                        from app.services.email_nfe_service import EmailNFeService
                    
                    print(f"[EMAIL-NFe] Iniciando envio de email para venda {venda_id}")
                    
                    # Buscar dados do cliente para email
                    dados_email = db.fetch_one("""
                        SELECT 
                            s.empresa_id,
                            c.email as cliente_email,
                            c.name as cliente_nome,
                            e.nome_fantasia as empresa_nome
                        FROM sales s
                        LEFT JOIN customers c ON s.customer_id = c.id
                        LEFT JOIN empresas e ON s.empresa_id = e.id
                        WHERE s.id = %s
                    """, (venda_id,))
                    
                    print(f"[EMAIL-NFe] Dados do cliente: {dados_email}")
                    
                    if dados_email and dados_email.get('cliente_email'):
                        email_service = EmailNFeService(dados_email['empresa_id'])
                        print(f"[EMAIL-NFe] Servico configurado: {email_service.esta_configurado()}")
                        
                        if email_service.esta_configurado():
                            nfe_data = {
                                'numero': resultado.get('numero'),
                                'serie': resultado.get('serie'),
                                'chave': resultado.get('chave_acesso'),
                                'cliente_email': dados_email['cliente_email'],
                                'cliente_nome': dados_email['cliente_nome'],
                                'empresa_nome': dados_email['empresa_nome'],
                                'data_emissao': resultado.get('data_emissao'),
                                'valor_total': data.get('totais', {}).get('valor_total', 0)
                            }
                            
                            xml_content = resultado.get('xml_assinado')
                            danfe_pdf = None
                            
                            try:
                                try:
                                    from services.danfe_generator_profissional import DanfeGeneratorProfissional
                                except ImportError:
                                    from app.services.danfe_generator_profissional import DanfeGeneratorProfissional
                                gerador = DanfeGeneratorProfissional()
                                danfe_pdf = gerador.gerar_pdf_simplificado(xml_content)
                            except Exception as e:
                                print(f"[EMAIL-NFe] Erro ao gerar DANFE para email: {e}")
                            
                            resultado_email = email_service.enviar_nfe_autorizada(
                                nfe_data=nfe_data,
                                xml_content=xml_content,
                                danfe_pdf=danfe_pdf
                            )
                            
                            if resultado_email.get('sucesso'):
                                email_enviado = True
                                print(f"[EMAIL-NFe] Email enviado para {dados_email['cliente_email']}")
                            else:
                                print(f"[EMAIL-NFe] Falha: {resultado_email.get('erro')}")
                        else:
                            print("[EMAIL-NFe] Email não configurado para esta empresa")
                    else:
                        print("[EMAIL-NFe] Cliente não possui email cadastrado")
                except Exception as e:
                    print(f"[EMAIL-NFe] Erro ao enviar email: {e}")
                
                return jsonify({
                    'success': True,
                    'message': 'NF-e emitida com sucesso!' + (' Email enviado ao cliente.' if email_enviado else ''),
                    'venda_id': venda_id,
                    'nfe_numero': resultado.get('numero'),
                    'nfe_serie': resultado.get('serie'),
                    'nfe_chave': resultado.get('chave_acesso'),
                    'nfe_protocolo': resultado.get('protocolo'),
                    'xml_assinado': resultado.get('xml_assinado'),
                    'envio_sefaz': resultado.get('envio_sefaz'),
                    'email_enviado': email_enviado
                })
            else:
                # Venda foi criada mas NF-e falhou
                erro_txt = (
                    resultado.get('erro')
                    or resultado.get('mensagem')
                    or resultado.get('message')
                )
                erros_lista = resultado.get('erros') or resultado.get('erros_xsd') or []
                if not erro_txt and isinstance(erros_lista, list) and erros_lista:
                    erro_txt = '; '.join(str(e) for e in erros_lista)
                if not erro_txt:
                    erro_txt = 'Erro desconhecido ao emitir NF-e'

                return jsonify({
                    'success': False,
                    'message': f"Venda criada mas erro ao emitir NF-e: {erro_txt}",
                    'venda_id': venda_id,
                    'detalhes': erros_lista
                }), 400
        else:
            # Apenas salvar sem emitir
            return jsonify({
                'success': True,
                'message': 'Venda salva com sucesso! Emita a NF-e quando desejar.',
                'venda_id': venda_id
            })
    
    except Exception as e:
        print(f"[NFE] Erro ao salvar manual: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Erro ao processar: {str(e)}'
        }), 500


# ========================================
# EMISSÃO DE NF-e (A PARTIR DE VENDA)
# ========================================

@nfe_emissao_bp.route('/nfe/emitir/<int:venda_id>', methods=['POST'])
@login_required
def emitir_nfe(venda_id):
    """
    Emite NF-e a partir de uma venda existente
    """
    try:
        db = get_db()
        
        # Verificar se venda existe
        venda = db.fetch_one("SELECT * FROM sales WHERE id = %s", (venda_id,))
        
        if not venda:
            return jsonify({'success': False, 'message': 'Venda não encontrada'}), 404
        
        # Verificar se já tem NF-e
        if venda['numero_nfe']:
            return jsonify({
                'success': False, 
                'message': f'Esta venda já possui NF-e: {venda["numero_nfe"]}'
            }), 400
        
        # Inicializar serviço
        nfe_service = NFeService(db=db)
        
        # Gerar e enviar NF-e
        print(f"[NFE] Iniciando emissão para venda {venda_id} (Empresa: {venda['empresa_id']})")
        resultado = nfe_service.gerar_nfe(venda_id=venda_id, enviar_para_sefaz=True)
        
        if resultado.get('sucesso'):
            chave = resultado.get('chave_acesso')
            numero = resultado.get('numero')
            serie = resultado.get('serie')
            
            print(f"[NFE] Sucesso! Número: {numero}, Chave: {chave}")
            
            # Salvar XML na venda
            try:
                db.execute("""
                    UPDATE sales 
                    SET numero_nfe = %s,
                        serie_nfe = %s,
                        chave_acesso_nfe = %s,
                        xml_nfe = %s,
                        status_nfe = 'autorizada'
                    WHERE id = %s
                """, (numero, serie, chave, resultado.get('xml_assinado'), venda_id))
                print(f"[NFE] XML salvo na venda {venda_id}")
            except Exception as e:
                print(f"[NFE] Erro ao salvar XML: {e}")
            
            # ========================================
            # ENVIO AUTOMÁTICO DE EMAIL
            # ========================================
            email_enviado = False
            try:
                try:
                    from services.email_nfe_service import EmailNFeService
                except ImportError:
                    from app.services.email_nfe_service import EmailNFeService
                
                print(f"[EMAIL-NFe] Iniciando envio de email para venda {venda_id}")
                
                # Buscar dados do cliente para email
                dados_email = db.fetch_one("""
                    SELECT 
                        s.empresa_id,
                        c.email as cliente_email,
                        c.name as cliente_nome,
                        e.nome_fantasia as empresa_nome
                    FROM sales s
                    LEFT JOIN customers c ON s.customer_id = c.id
                    LEFT JOIN empresas e ON s.empresa_id = e.id
                    WHERE s.id = %s
                """, (venda_id,))
                
                print(f"[EMAIL-NFe] Dados do cliente: {dados_email}")
                
                if dados_email and dados_email.get('cliente_email'):
                    email_service = EmailNFeService(dados_email['empresa_id'])
                    print(f"[EMAIL-NFe] Servico configurado: {email_service.esta_configurado()}")
                    
                    if email_service.esta_configurado():
                        # Preparar dados da NF-e
                        nfe_data = {
                            'numero': numero,
                            'serie': serie,
                            'chave': chave,
                            'cliente_email': dados_email['cliente_email'],
                            'cliente_nome': dados_email['cliente_nome'],
                            'empresa_nome': dados_email['empresa_nome'],
                            'data_emissao': resultado.get('data_emissao'),
                            'valor_total': venda.get('net_total', 0)
                        }
                        
                        # Buscar XML e gerar DANFE
                        xml_content = resultado.get('xml_assinado')
                        danfe_pdf = None
                        
                        try:
                            try:
                                from services.danfe_generator_profissional import DanfeGeneratorProfissional
                            except ImportError:
                                from app.services.danfe_generator_profissional import DanfeGeneratorProfissional
                            gerador = DanfeGeneratorProfissional()
                            danfe_pdf = gerador.gerar_pdf_simplificado(xml_content)
                        except Exception as e:
                            print(f"[EMAIL-NFe] Erro ao gerar DANFE para email: {e}")
                        
                        # Enviar email
                        resultado_email = email_service.enviar_nfe_autorizada(
                            nfe_data=nfe_data,
                            xml_content=xml_content,
                            danfe_pdf=danfe_pdf
                        )
                        
                        if resultado_email.get('sucesso'):
                            email_enviado = True
                            print(f"[EMAIL-NFe] Email enviado para {dados_email['cliente_email']}")
                        else:
                            print(f"[EMAIL-NFe] Falha: {resultado_email.get('erro')}")
                    else:
                        print("[EMAIL-NFe] Email não configurado para esta empresa")
                else:
                    print("[EMAIL-NFe] Cliente não possui email cadastrado")
            except Exception as e:
                print(f"[EMAIL-NFe] Erro ao enviar email: {e}")
            
            return jsonify({
                'success': True,
                'message': 'NF-e emitida e autorizada com sucesso!' + (' Email enviado ao cliente.' if email_enviado else ''),
                'nfe_numero': numero,
                'nfe_serie': serie,
                'nfe_chave': chave,
                'nfe_protocolo': resultado.get('protocolo'),
                'nfe_data': resultado.get('data_emissao'),
                'venda_id': venda_id,
                'email_enviado': email_enviado
            })
        else:
            print(f"[NFE] Erro: {resultado.get('erro')}")
            return jsonify({
                'success': False,
                'message': resultado.get('erro', 'Erro ao emitir NF-e'),
                'detalhes': resultado.get('erros_xsd', []),
                'xml': resultado.get('xml', '')
            }), 400
    
    except Exception as e:
        print(f"[NFE] Exceção: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Erro ao emitir NF-e: {str(e)}'
        }), 500


# ========================================
# HISTÓRICO DE NF-e
# ========================================

@nfe_emissao_bp.route('/nfe/historico')
@login_required
def historico():
    """
    Lista todas as NF-e emitidas
    Permite filtros por data, cliente, número, status
    """
    print("\n[NFE-HISTORICO] Acessando rota /nfe/historico")
    try:
        db = get_db()
        print("[NFE-HISTORICO] Conexão com banco OK")
        
        # Filtros
        data_inicio = request.args.get('data_inicio', '')
        data_fim = request.args.get('data_fim', '')
        cliente_id = request.args.get('cliente_id', '')
        numero_nfe = request.args.get('numero_nfe', '')
        status = request.args.get('status', '')
        
        # Query base
        query = """
            SELECT 
                s.id,
                s.numero_nfe,
                s.serie_nfe,
                s.chave_acesso_nfe,
                s.protocolo_nfe,
                s.data_emissao_nfe,
                s.protocolo_cancelamento_nfe,
                s.data_cancelamento_nfe,
                s.net_total as total_amount,
                s.sale_date,
                c.name as cliente_nome,
                COALESCE(c.cnpj, c.cpf) as cnpj_cpf,
                e.nome_fantasia as empresa_nome,
                CASE 
                    WHEN s.status_nfe = 'cancelada' THEN 'Cancelada'
                    WHEN s.status_nfe = 'autorizada' OR (s.chave_acesso_nfe IS NOT NULL AND s.chave_acesso_nfe != '') THEN 'Autorizada'
                    ELSE 'Gravada'
                END as status_nfe
            FROM sales s
            LEFT JOIN customers c ON s.customer_id = c.id
            LEFT JOIN empresas e ON s.empresa_id = e.id
            WHERE s.numero_nfe IS NOT NULL
        """
        
        params = []
        
        # Aplicar filtros
        if data_inicio:
            query += " AND s.data_emissao_nfe >= %s"
            params.append(data_inicio)
        
        if data_fim:
            query += " AND s.data_emissao_nfe <= %s"
            params.append(data_fim)
        
        if cliente_id:
            query += " AND s.customer_id = %s"
            params.append(cliente_id)
        
        if numero_nfe:
            query += " AND s.numero_nfe LIKE %s"
            params.append(f"%{numero_nfe}%")
        
        if status:
            if status == 'Gravada':
                query += " AND (s.chave_acesso_nfe IS NULL OR s.chave_acesso_nfe = '')"
            elif status == 'Autorizada':
                query += " AND s.chave_acesso_nfe IS NOT NULL AND s.chave_acesso_nfe != ''"
        
        query += " ORDER BY COALESCE(s.data_emissao_nfe, s.created_at) DESC LIMIT 200"
        
        # Buscar NF-e
        nfes = db.fetch_all(query, tuple(params) if params else None)
        
        # Buscar clientes para filtro
        clientes = db.fetch_all("""
            SELECT DISTINCT c.id, c.name 
            FROM customers c
            INNER JOIN sales s ON c.id = s.customer_id
            WHERE s.numero_nfe IS NOT NULL
            ORDER BY c.name
        """)
        
        return render_template('nfe/historico.html',
                             nfes=nfes,
                             clientes=clientes,
                             filtros={
                                 'data_inicio': data_inicio,
                                 'data_fim': data_fim,
                                 'cliente_id': cliente_id,
                                 'numero_nfe': numero_nfe,
                                 'status': status
                             })
    
    except Exception as e:
        print(f"[NFE-HISTORICO] ERRO: {type(e).__name__}: {str(e)}")
        import traceback
        print(f"[NFE-HISTORICO] Traceback:\n{traceback.format_exc()}")
        flash(f'Erro ao carregar histórico: {str(e)}', 'danger')
        return redirect(url_for('dashboard'))


@nfe_emissao_bp.route('/nfe/detalhes/<int:nfe_id>')
@login_required
def detalhes(nfe_id):
    """
    Exibe detalhes completos de uma NF-e
    """
    try:
        db = get_db()
        
        # Buscar dados da NF-e
        nfe = db.fetch_one("""
            SELECT 
                s.*,
                s.discount_total as desconto,
                s.freight_total as frete,
                s.gross_total as subtotal_produtos,
                s.net_total as total_amount,
                s.numero_nfe as nfe_numero,
                s.serie_nfe as nfe_serie,
                s.protocolo_nfe as nfe_protocolo,
                s.chave_acesso_nfe as nfe_chave_acesso,
                s.data_emissao_nfe,
                c.name as cliente_nome,
                COALESCE(c.cnpj, c.cpf) as cnpj_cpf,
                c.email as cliente_email,
                c.phone,
                c.address,
                c.city,
                c.state,
                c.cep as zip_code,
                e.nome_fantasia as empresa_nome,
                e.razao_social as empresa_razao,
                e.cnpj as empresa_cnpj,
                e.inscricao_estadual as empresa_ie,
                e.logradouro as empresa_endereco,
                e.cidade as empresa_cidade,
                e.estado as empresa_uf
            FROM sales s
            LEFT JOIN customers c ON s.customer_id = c.id
            LEFT JOIN empresas e ON s.empresa_id = e.id
            WHERE s.id = %s
        """, (nfe_id,))
        
        if not nfe:
            flash('NF-e não encontrada', 'danger')
            return redirect(url_for('nfe_emissao.historico'))
        
        # Buscar itens
        itens = db.fetch_all("""
            SELECT 
                si.*,
                si.total_price as subtotal,
                COALESCE(si.discount_value, 0) as desconto,
                p.name as produto_nome,
                p.internal_code as produto_codigo,
                p.ncm,
                p.cfop_out as cfop,
                p.unit_measure
            FROM sale_items si
            JOIN products p ON si.product_id = p.id
            WHERE si.sale_id = %s
        """, (nfe_id,))
        
        # Buscar eventos (CC-e, Cancelamento, etc)
        eventos = []
        try:
            eventos = db.fetch_all("""
                SELECT 
                    tipo_evento,
                    codigo_evento,
                    sequencial_evento,
                    numero_protocolo,
                    data_evento,
                    justificativa,
                    status_sefaz,
                    codigo_status,
                    motivo_status
                FROM nfe_eventos 
                WHERE chave_nfe = %s
                ORDER BY data_evento DESC
            """, (nfe.get('chave_acesso_nfe'),))
        except Exception as e:
            print(f"[AVISO] Erro ao buscar eventos: {e}")
        
        return render_template('nfe/detalhes.html',
                             nfe=nfe,
                             itens=itens,
                             eventos=eventos)
    
    except Exception as e:
        flash(f'Erro ao carregar detalhes: {str(e)}', 'danger')
        return redirect(url_for('nfe_emissao.historico'))


# ========================================
# DOWNLOADS (XML e DANFE)
# ========================================

@nfe_emissao_bp.route('/nfe/download-xml/<int:nfe_id>')
@login_required
def download_xml(nfe_id):
    """
    Download do XML assinado da NF-e (do banco de dados)
    """
    try:
        db = get_db()
        
        nfe = db.fetch_one("""
            SELECT xml_nfe, numero_nfe, chave_acesso_nfe 
            FROM sales 
            WHERE id = %s
        """, (nfe_id,))
        
        if not nfe:
            flash('NF-e não encontrada', 'danger')
            return redirect(url_for('nfe_emissao.historico'))
        
        if not nfe['xml_nfe']:
            flash('XML não encontrado. A NFe pode não ter sido emitida ainda.', 'warning')
            return redirect(url_for('nfe_emissao.detalhes', nfe_id=nfe_id))
        
        # Nome do arquivo para download
        numero = nfe['numero_nfe'] or 'SEM_NUMERO'
        chave = nfe['chave_acesso_nfe'] or 'SEM_CHAVE'
        filename = f"NFe_{numero}_{chave[:8]}.xml"
        
        # Criar resposta com XML do banco
        from flask import Response
        return Response(
            nfe['xml_nfe'],
            mimetype='application/xml',
            headers={
                'Content-Disposition': f'attachment; filename={filename}'
            }
        )
    
    except Exception as e:
        print(f"[NFE-XML] Erro ao baixar XML: {e}")
        flash(f'Erro ao baixar XML: {str(e)}', 'danger')
        return redirect(url_for('nfe_emissao.historico'))


@nfe_emissao_bp.route('/nfe/download-danfe/<int:nfe_id>')
@login_required
def download_danfe(nfe_id):
    """
    Download do DANFE (PDF) da NF-e
    Gera DANFE simplificado a partir do XML
    """
    try:
        db = get_db()
        
        # Buscar XML da NFe
        nfe = db.fetch_one("""
            SELECT xml_nfe, numero_nfe, chave_acesso_nfe 
            FROM sales 
            WHERE id = %s
        """, (nfe_id,))
        
        if not nfe or not nfe['xml_nfe']:
            flash('XML não encontrado. A NFe pode não ter sido emitida ainda.', 'warning')
            return redirect(url_for('nfe_emissao.detalhes', nfe_id=nfe_id))
        
        # Importar gerador de DANFE
        try:
            # Tentar usar o gerador profissional com ReportLab
            from app.services.danfe_generator_profissional import DanfeGeneratorProfissional
            print("[NFE-DANFE] [OK] Usando gerador PROFISSIONAL (ReportLab)")
            danfe = DanfeGeneratorProfissional()
            pdf_bytes = danfe.gerar_pdf_simplificado(nfe['xml_nfe'])
            print("[NFE-DANFE] [OK] PDF gerado com sucesso (layout profissional baseado no template oficial)")
        except Exception as e:
            # Fallback para gerador simples
            print(f"[NFE-DANFE] [AVISO] Erro no gerador profissional: {e}")
            print("[NFE-DANFE] [DOC] Usando gerador simples (fallback)")
            from app.services.danfe_generator import DanfeGenerator
            danfe = DanfeGenerator()
            pdf_bytes = danfe.gerar_pdf_simplificado(nfe['xml_nfe'])
            print("[NFE-DANFE] [OK] PDF gerado com sucesso (layout simples)")
        
        # Nome do arquivo
        numero = nfe['numero_nfe'] or 'SEM_NUMERO'
        chave = nfe['chave_acesso_nfe'] or 'SEM_CHAVE'
        filename = f"DANFE_{numero}_{chave[:8]}.pdf"
        
        # Retornar PDF
        from flask import Response
        return Response(
            pdf_bytes,
            mimetype='application/pdf',
            headers={
                'Content-Disposition': f'attachment; filename={filename}'
            }
        )
    
    except Exception as e:
        print(f"[NFE-DANFE] Erro ao gerar DANFE: {e}")
        flash(f'Erro ao gerar DANFE: {str(e)}', 'danger')
        return redirect(url_for('nfe_emissao.historico'))


# ========================================
# EMITIR NFe GRAVADA
# ========================================

@nfe_emissao_bp.route('/nfe/editar/<int:nfe_id>')
@login_required
def editar_nfe(nfe_id):
    """
    Carrega NFe gravada no formulário de emissão manual para edição
    """
    try:
        db = get_db()
        
        # Buscar venda
        venda = db.fetch_one("SELECT * FROM sales WHERE id = %s", (nfe_id,))
        
        if not venda:
            flash('Venda não encontrada.', 'danger')
            return redirect(url_for('nfe_emissao.historico'))
        
        # Verificar se já foi emitida
        if venda.get('chave_acesso_nfe'):
            flash('NFe já foi emitida e não pode ser editada.', 'warning')
            return redirect(url_for('nfe_emissao.detalhes', nfe_id=nfe_id))
        
        # Buscar itens da venda com nome e dados fiscais do produto
        itens = db.fetch_all("""
            SELECT si.*, 
                   COALESCE(si.product_name_snapshot, p.name) as product_name,
                   COALESCE(si.ncm, p.ncm) as ncm,
                   COALESCE(si.cfop, p.cfop_out) as cfop,
                   COALESCE(si.unit_measure, p.unit_measure) as unit_measure
            FROM sale_items si
            LEFT JOIN products p ON si.product_id = p.id
            WHERE si.sale_id = %s
        """, (nfe_id,))
        
        # Buscar empresas
        empresas = db.fetch_all("SELECT * FROM empresas WHERE ativo = 1")
        
        # Buscar clientes com todos os campos necessários
        clientes = db.fetch_all("""
            SELECT id, name, cnpj, cpf, ie, address, number, neighborhood, 
                   city, state, cep, codigo_municipio, email, phone
            FROM customers 
            WHERE active = 1 
            ORDER BY name
        """)
        
        # Buscar produtos
        produtos = db.fetch_all("SELECT * FROM products WHERE active = 1 ORDER BY name")
        
        # Renderizar formulário com dados preenchidos
        return render_template('nfe/emitir_manual.html',
                             venda_existente=venda,
                             itens_existentes=itens,
                             empresas=empresas,
                             clientes=clientes,
                             produtos=produtos,
                             modo_edicao=True)
    
    except Exception as e:
        print(f"[NFE-EDITAR] Erro: {e}")
        flash(f'Erro ao carregar NFe para edição: {str(e)}', 'danger')
        return redirect(url_for('nfe_emissao.historico'))


@nfe_emissao_bp.route('/nfe/emitir-gravada/<int:nfe_id>', methods=['POST'])
@login_required
def emitir_gravada(nfe_id):
    """
    Emite uma NFe que foi apenas gravada (sem transmissão)
    """
    try:
        db = get_db()
        
        # Buscar venda
        venda = db.fetch_one("SELECT * FROM sales WHERE id = %s", (nfe_id,))
        
        if not venda:
            return jsonify({'success': False, 'message': 'Venda não encontrada'}), 404
        
        # Verificar se já foi emitida
        if venda.get('chave_acesso_nfe'):
            return jsonify({'success': False, 'message': 'NFe já foi emitida anteriormente'}), 400
        
        # Emitir NFe
        nfe_service = NFeService(db=db)
        resultado = nfe_service.gerar_nfe(venda_id=nfe_id, enviar_para_sefaz=True)
        
        if resultado.get('sucesso'):
            return jsonify({
                'success': True,
                'message': 'NFe emitida com sucesso!',
                'chave_acesso': resultado.get('chave_acesso')
            })
        else:
            return jsonify({
                'success': False,
                'message': resultado.get('mensagem', 'Erro ao emitir NFe')
            }), 400
    
    except Exception as e:
        print(f"[NFE-EMITIR] Erro: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@nfe_emissao_bp.route('/nfe/excluir/<int:nfe_id>', methods=['DELETE'])
@login_required
def excluir_nfe(nfe_id):
    """
    Exclui uma NFe que foi apenas gravada (não emitida)
    """
    try:
        db = get_db()
        
        # Buscar venda
        venda = db.fetch_one("SELECT * FROM sales WHERE id = %s", (nfe_id,))
        
        if not venda:
            return jsonify({'success': False, 'message': 'Venda não encontrada'}), 404
        
        # Verificar se já foi emitida
        if venda.get('chave_acesso_nfe'):
            return jsonify({'success': False, 'message': 'NFe já foi emitida. Use a opção Cancelar.'}), 400
        
        # Excluir itens
        db.execute("DELETE FROM sale_items WHERE sale_id = %s", (nfe_id,))
        
        # Excluir venda
        db.execute("DELETE FROM sales WHERE id = %s", (nfe_id,))
        
        return jsonify({'success': True, 'message': 'NFe excluída com sucesso!'})
    
    except Exception as e:
        print(f"[NFE-EXCLUIR] Erro: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


# ========================================
# REENVIAR EMAIL DA NF-e
# ========================================

@nfe_emissao_bp.route('/nfe/reenviar-email/<int:nfe_id>', methods=['POST'])
@login_required
def reenviar_email_nfe(nfe_id):
    """
    Reenvia email da NF-e para o destinatário
    """
    try:
        db = get_db()
        data = request.json
        email_destino = data.get('email', '').strip()
        
        if not email_destino or '@' not in email_destino:
            return jsonify({'success': False, 'message': 'Email inválido'}), 400
        
        # Buscar dados da NF-e
        nfe = db.fetch_one("""
            SELECT 
                s.id, s.empresa_id, s.numero_nfe, s.serie_nfe, 
                s.chave_acesso_nfe, s.xml_nfe, s.net_total,
                s.data_emissao_nfe, s.status_nfe,
                c.name as cliente_nome,
                e.nome_fantasia as empresa_nome
            FROM sales s
            LEFT JOIN customers c ON s.customer_id = c.id
            LEFT JOIN empresas e ON s.empresa_id = e.id
            WHERE s.id = %s AND s.chave_acesso_nfe IS NOT NULL
        """, (nfe_id,))
        
        if not nfe:
            return jsonify({'success': False, 'message': 'NF-e não encontrada'}), 404
        
        # Importar serviço
        try:
            from services.email_nfe_service import EmailNFeService
        except ImportError:
            from app.services.email_nfe_service import EmailNFeService
        
        email_service = EmailNFeService(nfe['empresa_id'])
        
        if not email_service.esta_configurado():
            return jsonify({
                'success': False, 
                'message': 'Email não configurado para esta empresa. Configure em Administração > Config. Email NF-e'
            }), 400
        
        # Preparar dados
        nfe_data = {
            'numero': nfe['numero_nfe'],
            'serie': nfe['serie_nfe'],
            'chave': nfe['chave_acesso_nfe'],
            'cliente_email': email_destino,
            'cliente_nome': nfe['cliente_nome'],
            'empresa_nome': nfe['empresa_nome'],
            'data_emissao': str(nfe['data_emissao_nfe']) if nfe['data_emissao_nfe'] else '',
            'valor_total': float(nfe['net_total']) if nfe['net_total'] else 0
        }
        
        # Gerar DANFE
        danfe_pdf = None
        xml_content = nfe.get('xml_nfe')
        
        if xml_content:
            try:
                from services.danfe_generator_profissional import DanfeGeneratorProfissional
            except ImportError:
                from app.services.danfe_generator_profissional import DanfeGeneratorProfissional
            
            try:
                gerador = DanfeGeneratorProfissional()
                danfe_pdf = gerador.gerar_pdf_simplificado(xml_content)
            except Exception as e:
                print(f"[REENVIAR-EMAIL] Erro ao gerar DANFE: {e}")
        
        # Enviar email
        resultado = email_service.enviar_nfe_autorizada(
            nfe_data=nfe_data,
            xml_content=xml_content,
            danfe_pdf=danfe_pdf
        )
        
        if resultado.get('sucesso'):
            return jsonify({
                'success': True,
                'message': f'Email enviado com sucesso para {email_destino}'
            })
        else:
            return jsonify({
                'success': False,
                'message': f"Erro ao enviar: {resultado.get('erro')}"
            }), 400
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Erro: {str(e)}'
        }), 500


# ========================================
# CANCELAMENTO DE NF-e
# ========================================

@nfe_emissao_bp.route('/nfe/cancelar/<int:nfe_id>', methods=['POST'])
@login_required
def cancelar_nfe(nfe_id):
    """
    Cancela uma NF-e autorizada
    """
    try:
        db = get_db()
        data = request.json
        
        # Validar justificativa
        justificativa = data.get('justificativa', '').strip()
        if not justificativa or len(justificativa) < 15:
            return jsonify({
                'success': False,
                'message': 'Justificativa deve ter no mínimo 15 caracteres'
            }), 400
        
        # Buscar NF-e
        nfe = db.fetch_one("""
            SELECT 
                s.chave_acesso_nfe,
                s.protocolo_nfe,
                s.empresa_id as company_id,
                s.numero_nfe
            FROM sales s
            WHERE s.id = %s AND s.numero_nfe IS NOT NULL
        """, (nfe_id,))
        
        if not nfe:
            return jsonify({
                'success': False,
                'message': 'NF-e não encontrada ou não emitida'
            }), 404
        
        # Inicializar serviço SEFAZ
        sefaz_service = SefazService(empresa_id=nfe['company_id'])
        
        # Enviar cancelamento
        resultado = sefaz_service.cancelar_nfe(
            chave_acesso=nfe['chave_acesso_nfe'],
            protocolo=nfe['protocolo_nfe'],
            justificativa=justificativa
        )
        
        if resultado.get('sucesso'):
            # Atualizar status no banco
            print(f"[CANCELAMENTO] Atualizando banco - NF-e ID: {nfe_id}, Protocolo: {resultado.get('protocolo_cancelamento')}")
            db.execute_query("""
                UPDATE sales 
                SET status_nfe = 'cancelada',
                    protocolo_cancelamento_nfe = %s,
                    data_cancelamento_nfe = NOW(),
                    justificativa_cancelamento_nfe = %s
                WHERE id = %s
            """, (
                resultado.get('protocolo_cancelamento'),
                justificativa,
                nfe_id
            ))
            print(f"[CANCELAMENTO] Banco atualizado com sucesso!")
            
            # ========================================
            # ENVIO DE EMAIL - CANCELAMENTO
            # ========================================
            email_enviado = False
            try:
                try:
                    from services.email_nfe_service import EmailNFeService
                except ImportError:
                    from app.services.email_nfe_service import EmailNFeService
                
                dados_email = db.fetch_one("""
                    SELECT 
                        s.empresa_id, s.numero_nfe, s.serie_nfe, s.chave_acesso_nfe,
                        c.email as cliente_email, c.name as cliente_nome,
                        e.nome_fantasia as empresa_nome
                    FROM sales s
                    LEFT JOIN customers c ON s.customer_id = c.id
                    LEFT JOIN empresas e ON s.empresa_id = e.id
                    WHERE s.id = %s
                """, (nfe_id,))
                
                if dados_email and dados_email.get('cliente_email'):
                    email_service = EmailNFeService(dados_email['empresa_id'])
                    
                    if email_service.esta_configurado():
                        nfe_data = {
                            'numero': dados_email['numero_nfe'],
                            'serie': dados_email['serie_nfe'],
                            'chave': dados_email['chave_acesso_nfe'],
                            'cliente_email': dados_email['cliente_email'],
                            'cliente_nome': dados_email['cliente_nome'],
                            'empresa_nome': dados_email['empresa_nome'],
                            'protocolo_cancelamento': resultado.get('protocolo_cancelamento')
                        }
                        
                        resultado_email = email_service.enviar_nfe_cancelada(nfe_data)
                        email_enviado = resultado_email.get('sucesso', False)
                        print(f"[EMAIL-NFe] Cancelamento - Email enviado: {email_enviado}")
            except Exception as e:
                print(f"[EMAIL-NFe] Erro ao enviar email de cancelamento: {e}")
            
            return jsonify({
                'success': True,
                'message': 'NF-e cancelada com sucesso!' + (' Email enviado ao cliente.' if email_enviado else ''),
                'protocolo_cancelamento': resultado.get('protocolo_cancelamento'),
                'data_cancelamento': resultado.get('data_cancelamento'),
                'email_enviado': email_enviado
            })
        else:
            return jsonify({
                'success': False,
                'message': resultado.get('erro', 'Erro ao cancelar NF-e')
            }), 400
    
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Erro ao cancelar: {str(e)}'
        }), 500


# ========================================
# STATUS SEFAZ
# ========================================

@nfe_emissao_bp.route('/nfe/status-sefaz')
@login_required
def status_sefaz():
    """
    Consulta status do serviço SEFAZ
    """
    try:
        empresa_id = session.get('empresa_id', 9)
        sefaz_service = SefazService(empresa_id=empresa_id)
        
        resultado = sefaz_service.consultar_status_servico()
        
        return jsonify({
            'success': True,
            'status': resultado.get('status'),
            'mensagem': resultado.get('mensagem'),
            'uf': resultado.get('uf'),
            'ambiente': resultado.get('ambiente')
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Erro ao consultar status: {str(e)}'
        }), 500


# ========================================
# CONSULTA NF-e NA SEFAZ
# ========================================

@nfe_emissao_bp.route('/nfe/consultar-sefaz/<int:nfe_id>')
@login_required
def consultar_nfe_sefaz(nfe_id):
    """
    Consulta situação da NF-e na SEFAZ
    """
    try:
        db = get_db()
        
        # Buscar chave de acesso da NF-e
        nfe = db.fetch_one("""
            SELECT chave_acesso_nfe, empresa_id, numero_nfe
            FROM sales
            WHERE id = %s AND chave_acesso_nfe IS NOT NULL
        """, (nfe_id,))
        
        if not nfe:
            return jsonify({
                'success': False,
                'message': 'NF-e não encontrada ou sem chave de acesso'
            }), 404
        
        # Consultar na SEFAZ
        sefaz_service = SefazService(empresa_id=nfe['empresa_id'])
        resultado = sefaz_service.consultar_nfe(nfe['chave_acesso_nfe'])
        
        return jsonify({
            'success': resultado.get('sucesso', False),
            'numero_nfe': nfe['numero_nfe'],
            'chave': resultado.get('chave'),
            'codigo': resultado.get('codigo'),
            'motivo': resultado.get('motivo'),
            'protocolo': resultado.get('protocolo'),
            'data_autorizacao': resultado.get('data_autorizacao'),
            'cancelada': resultado.get('cancelada'),
            'data_cancelamento': resultado.get('data_cancelamento'),
            'motivo_cancelamento': resultado.get('motivo_cancelamento'),
            'ambiente': resultado.get('ambiente')
        })
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Erro ao consultar: {str(e)}'
        }), 500


# ========================================
# CARTA DE CORREÇÃO ELETRÔNICA (CC-e)
# ========================================

@nfe_emissao_bp.route('/nfe/carta-correcao/<int:nfe_id>', methods=['POST'])
@login_required
def carta_correcao_nfe(nfe_id):
    """
    Envia Carta de Correção Eletrônica (CC-e) para uma NF-e autorizada.
    
    A CC-e permite corrigir informações da NF-e sem cancelá-la.
    NÃO pode corrigir: valores, quantidades, dados fiscais, dados do emitente/destinatário.
    """
    try:
        db = get_db()
        data = request.json
        
        # Validar texto da correção
        correcao = data.get('correcao', '').strip()
        if not correcao or len(correcao) < 15:
            return jsonify({
                'success': False,
                'message': 'Texto da correção deve ter no mínimo 15 caracteres'
            }), 400
        
        if len(correcao) > 1000:
            return jsonify({
                'success': False,
                'message': 'Texto da correção deve ter no máximo 1000 caracteres'
            }), 400
        
        # Buscar NF-e
        nfe = db.fetch_one("""
            SELECT 
                s.chave_acesso_nfe,
                s.empresa_id as company_id,
                s.numero_nfe,
                s.status_nfe,
                (SELECT COUNT(*) FROM nfe_eventos WHERE chave_nfe COLLATE utf8mb4_unicode_ci = s.chave_acesso_nfe AND tipo_evento = '110110') as qtd_cce
            FROM sales s
            WHERE s.id = %s AND s.numero_nfe IS NOT NULL
        """, (nfe_id,))
        
        if not nfe:
            return jsonify({
                'success': False,
                'message': 'NF-e não encontrada ou não emitida'
            }), 404
        
        if nfe.get('status_nfe') == 'cancelada':
            return jsonify({
                'success': False,
                'message': 'Não é possível emitir CC-e para NF-e cancelada'
            }), 400
        
        # Verificar limite de CC-e (máximo 20)
        sequencia = (nfe.get('qtd_cce') or 0) + 1
        if sequencia > 20:
            return jsonify({
                'success': False,
                'message': 'Limite de 20 Cartas de Correção atingido para esta NF-e'
            }), 400
        
        # Inicializar serviço SEFAZ
        sefaz_service = SefazService(empresa_id=nfe['company_id'])
        
        # Enviar CC-e
        resultado = sefaz_service.carta_correcao(
            chave_acesso=nfe['chave_acesso_nfe'],
            correcao=correcao,
            sequencia=sequencia
        )
        
        if resultado.get('sucesso'):
            # Registrar evento no banco
            try:
                db.execute_query("""
                    INSERT INTO nfe_eventos (
                        tipo_evento, codigo_evento, chave_nfe, 
                        numero_protocolo, data_evento, sequencial_evento,
                        justificativa, cnpj_emitente, status_sefaz,
                        codigo_status, motivo_status, data_autorizacao
                    ) VALUES (%s, %s, %s, %s, NOW(), %s, %s, %s, %s, %s, %s, %s)
                """, (
                    'CC-e',
                    '110110',
                    nfe['chave_acesso_nfe'],
                    resultado.get('protocolo'),
                    sequencia,
                    correcao,
                    nfe['chave_acesso_nfe'][6:20],  # CNPJ da chave
                    'autorizado',
                    resultado.get('codigo'),
                    resultado.get('motivo'),
                    resultado.get('data_registro')
                ))
                print(f"[CC-e] Evento registrado: Protocolo {resultado.get('protocolo')}, Sequência {sequencia}")
            except Exception as e:
                # Tabela pode não existir ainda, apenas loga
                print(f"[AVISO] Não foi possível registrar evento: {e}")
            
            # ========================================
            # ENVIO DE EMAIL - CC-e
            # ========================================
            email_enviado = False
            try:
                try:
                    from services.email_nfe_service import EmailNFeService, GerarPDFCCe
                except ImportError:
                    from app.services.email_nfe_service import EmailNFeService, GerarPDFCCe
                
                dados_email = db.fetch_one("""
                    SELECT 
                        s.empresa_id, s.numero_nfe, s.serie_nfe, s.chave_acesso_nfe,
                        c.email as cliente_email, c.name as cliente_nome,
                        e.nome_fantasia as empresa_nome, e.razao_social, e.cnpj as empresa_cnpj
                    FROM sales s
                    LEFT JOIN customers c ON s.customer_id = c.id
                    LEFT JOIN empresas e ON s.empresa_id = e.id
                    WHERE s.id = %s
                """, (nfe_id,))
                
                if dados_email and dados_email.get('cliente_email'):
                    email_service = EmailNFeService(dados_email['empresa_id'])
                    
                    if email_service.esta_configurado():
                        nfe_data = {
                            'numero': dados_email['numero_nfe'],
                            'serie': dados_email['serie_nfe'],
                            'chave': dados_email['chave_acesso_nfe'],
                            'cliente_email': dados_email['cliente_email'],
                            'cliente_nome': dados_email['cliente_nome'],
                            'empresa_nome': dados_email['empresa_nome']
                        }
                        
                        cce_data = {
                            'sequencia': sequencia,
                            'correcao': correcao,
                            'protocolo': resultado.get('protocolo'),
                            'data_registro': resultado.get('data_registro')
                        }
                        
                        empresa_data = {
                            'razao_social': dados_email.get('razao_social'),
                            'cnpj': dados_email.get('empresa_cnpj')
                        }
                        
                        # Gerar PDF da CC-e
                        pdf_cce = GerarPDFCCe.gerar(nfe_data, cce_data, empresa_data)
                        
                        resultado_email = email_service.enviar_cce(nfe_data, cce_data, pdf_cce)
                        email_enviado = resultado_email.get('sucesso', False)
                        print(f"[EMAIL-NFe] CC-e - Email enviado: {email_enviado}")
            except Exception as e:
                print(f"[EMAIL-NFe] Erro ao enviar email de CC-e: {e}")
            
            return jsonify({
                'success': True,
                'message': f'Carta de Correção #{sequencia} enviada com sucesso!' + (' Email enviado ao cliente.' if email_enviado else ''),
                'protocolo': resultado.get('protocolo'),
                'data_registro': resultado.get('data_registro'),
                'sequencia': sequencia,
                'email_enviado': email_enviado
            })
        else:
            return jsonify({
                'success': False,
                'message': resultado.get('erro', 'Erro ao enviar Carta de Correção')
            }), 400
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Erro ao enviar CC-e: {str(e)}'
        }), 500


# ========================================
# INUTILIZAÇÃO DE NUMERAÇÃO
# ========================================

@nfe_emissao_bp.route('/nfe/inutilizar', methods=['GET', 'POST'])
@login_required
def inutilizar_nfe():
    """
    GET: Exibe formulário de inutilização
    POST: Processa inutilização de numeração
    """
    if request.method == 'GET':
        try:
            db = get_db()
            
            # Buscar empresas ativas
            empresas = db.fetch_all("""
                SELECT id, razao_social, nome_fantasia, cnpj
                FROM empresas 
                WHERE usar_no_pdv = 1 AND ativo = 1
                ORDER BY nome_fantasia
            """)
            
            return render_template('nfe/inutilizar.html', empresas=empresas)
        
        except Exception as e:
            flash(f'Erro ao carregar formulário: {str(e)}', 'danger')
            return redirect(url_for('nfe_emissao.historico'))
    
    # POST - Processar inutilização
    try:
        db = get_db()
        data = request.json
        
        empresa_id = data.get('empresa_id')
        serie = int(data.get('serie', 1))
        numero_inicial = int(data.get('numero_inicial'))
        numero_final = int(data.get('numero_final'))
        justificativa = data.get('justificativa', '').strip()
        ano = int(data.get('ano')) if data.get('ano') else None
        
        # Validações
        if not empresa_id:
            return jsonify({'success': False, 'message': 'Empresa é obrigatória'}), 400
        
        if not justificativa or len(justificativa) < 15:
            return jsonify({'success': False, 'message': 'Justificativa deve ter no mínimo 15 caracteres'}), 400
        
        if numero_inicial > numero_final:
            return jsonify({'success': False, 'message': 'Número inicial deve ser menor ou igual ao final'}), 400
        
        if numero_final - numero_inicial > 999:
            return jsonify({'success': False, 'message': 'Máximo de 1000 números por inutilização'}), 400
        
        # Buscar CNPJ da empresa
        empresa = db.fetch_one("SELECT cnpj FROM empresas WHERE id = %s", (empresa_id,))
        if not empresa:
            return jsonify({'success': False, 'message': 'Empresa não encontrada'}), 404
        
        cnpj = ''.join(c for c in empresa['cnpj'] if c.isdigit())
        
        # Inicializar serviço SEFAZ
        sefaz_service = SefazService(empresa_id=empresa_id)
        
        # Enviar inutilização
        print(f"[INUTILIZAÇÃO] Empresa: {empresa_id}, Série: {serie}, Números: {numero_inicial}-{numero_final}")
        resultado = sefaz_service.inutilizar_numeracao(
            cnpj=cnpj,
            serie=serie,
            numero_inicial=numero_inicial,
            numero_final=numero_final,
            justificativa=justificativa,
            ano=ano
        )
        
        if resultado.get('sucesso'):
            # Registrar inutilização no banco
            try:
                db.execute_query("""
                    INSERT INTO nfe_inutilizacoes (
                        empresa_id, serie, numero_inicial, numero_final,
                        ano, justificativa, protocolo, data_inutilizacao
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                """, (
                    empresa_id, serie, numero_inicial, numero_final,
                    resultado.get('ano'), justificativa, resultado.get('protocolo')
                ))
            except Exception as e:
                # Tabela pode não existir
                print(f"[AVISO] Não foi possível registrar inutilização: {e}")
            
            return jsonify({
                'success': True,
                'message': f'Numeração {numero_inicial}-{numero_final} inutilizada com sucesso!',
                'protocolo': resultado.get('protocolo'),
                'data_inutilizacao': resultado.get('data_inutilizacao'),
                'chave_inutilizacao': resultado.get('chave_inutilizacao')
            })
        else:
            return jsonify({
                'success': False,
                'message': resultado.get('erro', 'Erro ao inutilizar numeração')
            }), 400
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Erro ao inutilizar: {str(e)}'
        }), 500


# ========================================
# CONFIGURAÇÃO DE EMAIL PARA NF-e
# ========================================

@nfe_emissao_bp.route('/nfe/config-email', methods=['GET', 'POST'])
@login_required
def config_email_nfe():
    """
    GET: Exibe formulário de configuração de email
    POST: Salva configuração de email
    """
    db = get_db()
    
    if request.method == 'GET':
        try:
            # Buscar empresas
            empresas = db.fetch_all("""
                SELECT id, razao_social, nome_fantasia, cnpj
                FROM empresas 
                WHERE usar_no_pdv = 1 AND ativo = 1
                ORDER BY nome_fantasia
            """)
            
            # Buscar configurações existentes
            configs = db.fetch_all("""
                SELECT e.*, emp.nome_fantasia as empresa_nome
                FROM email_config_nfe e
                JOIN empresas emp ON e.empresa_id = emp.id
                ORDER BY emp.nome_fantasia
            """)
            
            return render_template('nfe/config_email.html', 
                                 empresas=empresas, 
                                 configs=configs)
        
        except Exception as e:
            flash(f'Erro ao carregar configurações: {str(e)}', 'danger')
            return redirect(url_for('nfe_emissao.historico'))
    
    # POST - Salvar configuração
    try:
        data = request.json
        
        empresa_id = data.get('empresa_id')
        if not empresa_id:
            return jsonify({'success': False, 'message': 'Empresa é obrigatória'}), 400
        
        # Verificar se já existe configuração
        existente = db.fetch_one(
            "SELECT id FROM email_config_nfe WHERE empresa_id = %s", 
            (empresa_id,)
        )
        
        if existente:
            # Atualizar
            db.execute_query("""
                UPDATE email_config_nfe SET
                    smtp_server = %s,
                    smtp_port = %s,
                    smtp_ssl = %s,
                    email_usuario = %s,
                    email_senha = %s,
                    email_remetente = %s,
                    nome_remetente = %s,
                    enviar_nfe_autorizada = %s,
                    enviar_nfe_cancelada = %s,
                    enviar_cce = %s,
                    anexar_xml = %s,
                    anexar_danfe = %s,
                    email_copia = %s,
                    assunto_nfe_autorizada = %s,
                    assunto_nfe_cancelada = %s,
                    assunto_cce = %s,
                    ativo = %s,
                    updated_at = NOW()
                WHERE empresa_id = %s
            """, (
                data.get('smtp_server'),
                data.get('smtp_port', 587),
                1 if data.get('smtp_ssl') else 0,
                data.get('email_usuario'),
                data.get('email_senha'),
                data.get('email_remetente'),
                data.get('nome_remetente'),
                1 if data.get('enviar_nfe_autorizada') else 0,
                1 if data.get('enviar_nfe_cancelada') else 0,
                1 if data.get('enviar_cce') else 0,
                1 if data.get('anexar_xml') else 0,
                1 if data.get('anexar_danfe') else 0,
                data.get('email_copia'),
                data.get('assunto_nfe_autorizada', 'NF-e Autorizada - {numero}/{serie}'),
                data.get('assunto_nfe_cancelada', 'NF-e Cancelada - {numero}/{serie}'),
                data.get('assunto_cce', 'Carta de Correção - NF-e {numero}/{serie}'),
                1 if data.get('ativo', True) else 0,
                empresa_id
            ))
            msg = 'Configuração atualizada com sucesso!'
        else:
            # Inserir
            db.execute_query("""
                INSERT INTO email_config_nfe (
                    empresa_id, smtp_server, smtp_port, smtp_ssl,
                    email_usuario, email_senha, email_remetente, nome_remetente,
                    enviar_nfe_autorizada, enviar_nfe_cancelada, enviar_cce,
                    anexar_xml, anexar_danfe, email_copia,
                    assunto_nfe_autorizada, assunto_nfe_cancelada, assunto_cce, ativo
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                empresa_id,
                data.get('smtp_server'),
                data.get('smtp_port', 587),
                1 if data.get('smtp_ssl') else 0,
                data.get('email_usuario'),
                data.get('email_senha'),
                data.get('email_remetente'),
                data.get('nome_remetente'),
                1 if data.get('enviar_nfe_autorizada') else 0,
                1 if data.get('enviar_nfe_cancelada') else 0,
                1 if data.get('enviar_cce') else 0,
                1 if data.get('anexar_xml') else 0,
                1 if data.get('anexar_danfe') else 0,
                data.get('email_copia'),
                data.get('assunto_nfe_autorizada', 'NF-e Autorizada - {numero}/{serie}'),
                data.get('assunto_nfe_cancelada', 'NF-e Cancelada - {numero}/{serie}'),
                data.get('assunto_cce', 'Carta de Correção - NF-e {numero}/{serie}'),
                1 if data.get('ativo', True) else 0
            ))
            msg = 'Configuração criada com sucesso!'
        
        return jsonify({'success': True, 'message': msg})
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Erro ao salvar: {str(e)}'
        }), 500


@nfe_emissao_bp.route('/nfe/config-email/<int:empresa_id>', methods=['GET'])
@login_required
def get_config_email(empresa_id):
    """Busca configuração de email de uma empresa"""
    try:
        db = get_db()
        config = db.fetch_one("""
            SELECT * FROM email_config_nfe WHERE empresa_id = %s
        """, (empresa_id,))
        
        if config:
            # Não retornar a senha completa por segurança
            if config.get('email_senha'):
                config['email_senha'] = '********'
            return jsonify({'success': True, 'config': config})
        else:
            return jsonify({'success': True, 'config': None})
            
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@nfe_emissao_bp.route('/nfe/testar-email', methods=['POST'])
@login_required
def testar_email_nfe():
    """Envia email de teste"""
    try:
        data = request.json
        empresa_id = data.get('empresa_id')
        email_teste = data.get('email_teste')
        
        if not empresa_id or not email_teste:
            return jsonify({
                'success': False,
                'message': 'Empresa e email de teste são obrigatórios'
            }), 400
        
        # Importar serviço
        try:
            from services.email_nfe_service import EmailNFeService
        except ImportError:
            from app.services.email_nfe_service import EmailNFeService
        
        email_service = EmailNFeService(empresa_id)
        
        if not email_service.esta_configurado():
            return jsonify({
                'success': False,
                'message': 'Email não configurado para esta empresa'
            }), 400
        
        # Enviar email de teste
        resultado = email_service._enviar_email(
            destinatario=email_teste,
            nome_dest='Teste',
            assunto='[TESTE] Configuração de Email NF-e',
            corpo_html="""
            <html>
            <body style="font-family: Arial, sans-serif;">
                <h2>[OK] Teste de Configuração de Email</h2>
                <p>Se você recebeu este email, a configuração está funcionando corretamente!</p>
                <p><strong>Sistema NF-e</strong></p>
            </body>
            </html>
            """,
            tipo_documento='nfe'
        )
        
        if resultado.get('sucesso'):
            return jsonify({
                'success': True,
                'message': f'Email de teste enviado para {email_teste}'
            })
        else:
            return jsonify({
                'success': False,
                'message': f"Erro: {resultado.get('erro')}"
            }), 400
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Erro: {str(e)}'
        }), 500
