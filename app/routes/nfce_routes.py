"""
Rotas para NFC-e (Nota Fiscal de Consumidor Eletrônica)
"""

from flask import Blueprint, request, jsonify, render_template, session, redirect, url_for
from database import Database
from datetime import datetime

nfce_bp = Blueprint('nfce', __name__)




@nfce_bp.route('/nfce/emitir/<int:venda_id>', methods=['POST'])
@login_required
def emitir_nfce(venda_id):
    """
    Emite NFC-e para uma venda
    """
    try:
        # Importar aqui para evitar circular import
        from app.services.nfce_service import NFCeService
        
        # Buscar empresa da venda
        db = Database()
        venda = db.fetch_one("SELECT empresa_id FROM sales WHERE id = %s", (venda_id,))
        db.close()
        
        if not venda:
            return jsonify({'success': False, 'error': 'Venda não encontrada'}), 404
        
        # Emitir NFC-e
        service = NFCeService(venda['empresa_id'])
        resultado = service.emitir(venda_id)
        
        if resultado['sucesso']:
            return jsonify({
                'success': True,
                'message': f"NFC-e emitida com sucesso!",
                'numero': resultado.get('numero_nfce'),
                'chave': resultado.get('chave_acesso'),
                'protocolo': resultado.get('protocolo')
            })
        else:
            return jsonify({
                'success': False,
                'error': resultado.get('erro', 'Erro ao emitir NFC-e')
            }), 400
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@nfce_bp.route('/nfce/status', methods=['POST'])
@login_required
def consultar_status_nfce():
    """
    Consulta status do serviço NFC-e na SEFAZ
    Primeiro teste a fazer antes de emitir
    """
    try:
        from app.services.nfce_service import NFCeService
        
        data = request.json
        empresa_id = data.get('empresa_id')
        
        if not empresa_id:
            return jsonify({'success': False, 'error': 'empresa_id obrigatório'}), 400
        
        service = NFCeService(empresa_id)
        resultado = service.consultar_status()
        
        return jsonify({
            'success': resultado.get('sucesso', False),
            'cStat': resultado.get('cStat'),
            'mensagem': resultado.get('mensagem', resultado.get('erro'))
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@nfce_bp.route('/nfce/emitir/teste', methods=['POST'])
@login_required
def emitir_nfce_teste():
    """
    Emite NFC-e de teste para homologação
    Cria uma venda fictícia e emite a NFC-e
    """
    try:
        from app.services.nfce_service import NFCeService
        
        data = request.json
        empresa_id = data.get('empresa_id')
        valor = data.get('valor', 10.00)
        
        if not empresa_id:
            return jsonify({'success': False, 'error': 'empresa_id obrigatório'}), 400
        
        db = Database()
        
        # Verificar se empresa tem CSC configurado
        empresa = db.fetch_one("""
            SELECT id, nome_fantasia, csc_nfce, ambiente_nfce
            FROM empresas WHERE id = %s
        """, (empresa_id,))
        
        if not empresa:
            return jsonify({'success': False, 'error': 'Empresa não encontrada'}), 404
        
        if not empresa.get('csc_nfce'):
            return jsonify({'success': False, 'error': 'CSC não configurado para esta empresa'}), 400
        
        # Buscar um produto qualquer para usar no teste
        produto = db.fetch_one("""
            SELECT id, name, price, ncm, cfop_out, unit_measure
            FROM products WHERE price > 0 LIMIT 1
        """)
        
        if not produto:
            return jsonify({'success': False, 'error': 'Nenhum produto cadastrado'}), 400
        
        # Buscar um cliente qualquer para usar no teste
        cliente = db.fetch_one("SELECT id FROM customers LIMIT 1")
        cliente_id = cliente['id'] if cliente else 1
        
        # Criar venda de teste (status: draft, confirmed, invoiced, cancelled)
        venda_id = db.execute("""
            INSERT INTO sales (empresa_id, customer_id, gross_total, net_total, 
                              payment_method, sale_date, status, created_at)
            VALUES (%s, %s, %s, %s, '01', NOW(), 'confirmed', NOW())
        """, (empresa_id, cliente_id, valor, valor))
        
        # Criar item da venda
        db.execute("""
            INSERT INTO sale_items (sale_id, product_id, product_name_snapshot, 
                                   quantity, unit_price, total_price)
            VALUES (%s, %s, %s, 1, %s, %s)
        """, (venda_id, produto['id'], produto['name'], valor, valor))
        
        db.close()
        
        print(f"[NFC-e TESTE] Venda de teste criada: ID {venda_id}")
        
        # Emitir NFC-e (verificar se é contingência)
        service = NFCeService(empresa_id)
        
        # Verificar se está em modo contingência
        contingencia_flag = data.get('contingencia', False)
        status_cont = service.verificar_contingencia()
        
        if contingencia_flag or status_cont.get('contingencia'):
            print(f"[NFC-e TESTE] Emitindo em CONTINGÊNCIA...")
            resultado = service.emitir_contingencia(venda_id)
        else:
            resultado = service.emitir(venda_id)
        
        if resultado.get('sucesso'):
            return jsonify({
                'success': True,
                'message': 'NFC-e de teste emitida com sucesso!',
                'numero_nfce': resultado.get('numero_nfce'),
                'chave_acesso': resultado.get('chave_acesso'),
                'protocolo': resultado.get('protocolo'),
                'contingencia': resultado.get('contingencia', False),
                'venda_id': venda_id
            })
        else:
            return jsonify({
                'success': False,
                'error': resultado.get('erro', 'Erro ao emitir NFC-e')
            }), 400
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@nfce_bp.route('/nfce/status', methods=['GET'])
@login_required
def status_nfce():
    """
    Verifica status do serviço NFC-e na SEFAZ
    """
    empresa_id = request.args.get('empresa_id', type=int)
    
    if not empresa_id:
        return jsonify({'success': False, 'error': 'empresa_id obrigatório'}), 400
    
    try:
        # TODO: Implementar consulta de status
        return jsonify({
            'success': True,
            'status': 'online',
            'message': 'Serviço NFC-e operacional'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@nfce_bp.route('/nfce/inutilizar', methods=['POST'])
@login_required
def inutilizar_nfce():
    """
    Inutiliza numeração de NFC-e
    Necessário para teste de homologação
    """
    data = request.json
    empresa_id = data.get('empresa_id')
    serie = data.get('serie', 1)
    numero_ini = data.get('numero_ini')
    numero_fim = data.get('numero_fim')
    justificativa = data.get('justificativa', 'Erro na geracao da NFC-e')
    
    if not all([empresa_id, numero_ini, numero_fim]):
        return jsonify({'success': False, 'error': 'Dados incompletos'}), 400
    
    if len(justificativa) < 15:
        return jsonify({'success': False, 'error': 'Justificativa deve ter no mínimo 15 caracteres'}), 400
    
    try:
        from app.services.nfce_service import NFCeService
        service = NFCeService(empresa_id)
        resultado = service.inutilizar(serie, numero_ini, numero_fim, justificativa)
        
        if resultado and resultado.get('sucesso'):
            return jsonify({
                'success': True,
                'message': f"Numeração {numero_ini}-{numero_fim} inutilizada"
            })
        else:
            return jsonify({
                'success': False,
                'error': resultado.get('erro', 'Erro ao inutilizar')
            }), 400
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@nfce_bp.route('/nfce/contingencia/entrar', methods=['POST'])
@login_required
def entrar_contingencia():
    """Ativa modo de contingência offline"""
    data = request.json
    empresa_id = data.get('empresa_id')
    justificativa = data.get('justificativa', 'Problemas tecnicos - sem conexao com SEFAZ')
    
    if not empresa_id:
        return jsonify({'success': False, 'error': 'empresa_id obrigatório'}), 400
    
    if len(justificativa) < 15:
        return jsonify({'success': False, 'error': 'Justificativa deve ter no mínimo 15 caracteres'}), 400
    
    try:
        from app.services.nfce_service import NFCeService
        service = NFCeService(empresa_id)
        resultado = service.entrar_contingencia(justificativa)
        
        if resultado.get('sucesso'):
            return jsonify({
                'success': True,
                'message': 'Modo contingência ativado',
                'dhCont': resultado.get('dhCont'),
                'xJust': resultado.get('xJust')
            })
        else:
            return jsonify({'success': False, 'error': resultado.get('erro')}), 400
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@nfce_bp.route('/nfce/contingencia/sair', methods=['POST'])
@login_required
def sair_contingencia():
    """Desativa modo de contingência"""
    data = request.json
    empresa_id = data.get('empresa_id')
    
    if not empresa_id:
        return jsonify({'success': False, 'error': 'empresa_id obrigatório'}), 400
    
    try:
        from app.services.nfce_service import NFCeService
        service = NFCeService(empresa_id)
        resultado = service.sair_contingencia()
        
        if resultado.get('sucesso'):
            return jsonify({'success': True, 'message': 'Modo contingência desativado'})
        else:
            return jsonify({'success': False, 'error': resultado.get('erro')}), 400
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@nfce_bp.route('/nfce/contingencia/status', methods=['GET'])
@login_required
def status_contingencia():
    """Verifica status de contingência"""
    empresa_id = request.args.get('empresa_id', type=int)
    
    if not empresa_id:
        return jsonify({'success': False, 'error': 'empresa_id obrigatório'}), 400
    
    try:
        from app.services.nfce_service import NFCeService
        service = NFCeService(empresa_id)
        resultado = service.verificar_contingencia()
        
        return jsonify({
            'success': True,
            'contingencia': resultado.get('contingencia', False),
            'dhCont': resultado.get('dhCont').isoformat() if resultado.get('dhCont') else None,
            'xJust': resultado.get('xJust')
        })
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@nfce_bp.route('/nfce/contingencia/emitir', methods=['POST'])
@login_required
def emitir_contingencia():
    """Emite NFC-e em contingência offline"""
    data = request.json
    empresa_id = data.get('empresa_id')
    venda_id = data.get('venda_id')
    
    if not all([empresa_id, venda_id]):
        return jsonify({'success': False, 'error': 'empresa_id e venda_id obrigatórios'}), 400
    
    try:
        from app.services.nfce_service import NFCeService
        service = NFCeService(empresa_id)
        resultado = service.emitir_contingencia(venda_id)
        
        if resultado.get('sucesso'):
            return jsonify({
                'success': True,
                'numero_nfce': resultado.get('numero_nfce'),
                'chave_acesso': resultado.get('chave_acesso'),
                'contingencia': True,
                'message': resultado.get('mensagem')
            })
        else:
            return jsonify({'success': False, 'error': resultado.get('erro')}), 400
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@nfce_bp.route('/nfce/contingencia/transmitir', methods=['POST'])
@login_required
def transmitir_pendentes():
    """Transmite NFC-es pendentes de contingência"""
    data = request.json
    empresa_id = data.get('empresa_id')
    
    if not empresa_id:
        return jsonify({'success': False, 'error': 'empresa_id obrigatório'}), 400
    
    try:
        from app.services.nfce_service import NFCeService
        service = NFCeService(empresa_id)
        resultado = service.transmitir_pendentes()
        
        if resultado.get('sucesso'):
            return jsonify({
                'success': True,
                'transmitidas': resultado.get('transmitidas'),
                'total': resultado.get('total'),
                'erros': resultado.get('erros')
            })
        else:
            return jsonify({'success': False, 'error': resultado.get('erro')}), 400
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@nfce_bp.route('/nfce/configuracoes', methods=['GET'])
@login_required
def configuracoes_nfce():
    """
    Retorna configurações de NFC-e da empresa
    """
    empresa_id = request.args.get('empresa_id', type=int)
    
    if not empresa_id:
        return jsonify({'success': False, 'error': 'empresa_id obrigatório'}), 400
    
    try:
        db = Database()
        empresa = db.fetch_one("""
            SELECT id, nome_fantasia, csc_nfce, id_csc_nfce, ambiente_nfce
            FROM empresas WHERE id = %s
        """, (empresa_id,))
        db.close()
        
        if not empresa:
            return jsonify({'success': False, 'error': 'Empresa não encontrada'}), 404
        
        return jsonify({
            'success': True,
            'empresa': empresa['nome_fantasia'],
            'csc_configurado': bool(empresa['csc_nfce']),
            'ambiente': 'producao' if empresa['ambiente_nfce'] == 1 else 'homologacao'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@nfce_bp.route('/nfce/teste-homologacao', methods=['GET'])
@login_required
def pagina_teste_homologacao():
    """
    Página para realizar os testes de homologação NFC-e
    """
    db = Database()
    empresas = db.fetch_all("""
        SELECT id, nome_fantasia, csc_nfce, ambiente_nfce 
        FROM empresas 
        WHERE csc_nfce IS NOT NULL
        ORDER BY nome_fantasia
    """)
    db.close()
    
    return render_template('nfce/teste_homologacao.html', empresas=empresas)


@nfce_bp.route('/nfce/cancelar', methods=['POST'])
@login_required
def cancelar_nfce():
    """
    Cancela uma NFC-e
    Necessário para teste de homologação
    """
    data = request.json
    empresa_id = data.get('empresa_id')
    chave = data.get('chave')
    justificativa = data.get('justificativa', 'Cancelamento a pedido do cliente')
    
    if not all([empresa_id, chave]):
        return jsonify({'success': False, 'error': 'Dados incompletos'}), 400
    
    if len(justificativa) < 15:
        return jsonify({'success': False, 'error': 'Justificativa deve ter no mínimo 15 caracteres'}), 400
    
    try:
        from app.services.nfce_service import NFCeService
        service = NFCeService(empresa_id)
        resultado = service.cancelar_por_chave(chave, justificativa)
        
        if resultado and resultado.get('sucesso'):
            return jsonify({
                'success': True,
                'message': 'NFC-e cancelada com sucesso'
            })
        else:
            return jsonify({
                'success': False,
                'error': resultado.get('erro', 'Erro ao cancelar')
            }), 400
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@nfce_bp.route('/venda/<int:venda_id>/emitir-nfe', methods=['POST'])
@login_required
def emitir_nfe_da_venda(venda_id):
    """
    Emite NF-e a partir de uma venda existente (que pode já ter NFC-e)
    Segue o mesmo fluxo de emissão manual de NF-e
    """
    try:
        db = Database()
        
        # Buscar venda
        venda = db.fetch_one("""
            SELECT s.*, e.ambiente_nfe
            FROM sales s
            JOIN empresas e ON s.empresa_id = e.id
            WHERE s.id = %s
        """, (venda_id,))
        
        if not venda:
            return jsonify({'success': False, 'error': 'Venda não encontrada'}), 404
        
        # Verificar se já tem NF-e emitida
        if venda.get('chave_acesso_nfe') and venda.get('status_nfe') == 'autorizada':
            return jsonify({
                'success': False,
                'error': 'Esta venda já possui NF-e autorizada'
            }), 400
        
        db.close()
        
        # Usar o serviço de emissão de NF-e existente
        from app.services.nfe_service import NFeService
        
        nfe_service = NFeService()
        resultado = nfe_service.emitir_nfe_venda(venda_id)
        
        if resultado.get('sucesso'):
            return jsonify({
                'success': True,
                'message': 'NF-e emitida com sucesso!',
                'numero': resultado.get('numero_nfe'),
                'chave': resultado.get('chave_acesso'),
                'protocolo': resultado.get('protocolo')
            })
        else:
            return jsonify({
                'success': False,
                'error': resultado.get('erro', 'Erro ao emitir NF-e')
            }), 400
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# ROTAS DE IMPRESSÃO DANFCE
# ============================================================================

@nfce_bp.route('/nfce/imprimir/<int:venda_id>')
@login_required
def imprimir_danfce(venda_id):
    """
    Gera e retorna PDF do DANFCE para impressão
    Parâmetro opcional: ?formato=80mm|58mm|A4
    """
    try:
        from app.services.danfce_generator import DanfceGenerator
        from flask import Response
        
        # Formato pode ser passado como parâmetro
        formato = request.args.get('formato', '80mm')
        if formato not in ['80mm', '58mm', 'A4']:
            formato = '80mm'
        
        db = Database()
        
        # Buscar XML da NFC-e e logo da empresa
        venda = db.fetch_one("""
            SELECT s.xml_nfce, s.numero_nfce, s.chave_acesso_nfce, s.status_nfce,
                   e.logo_path as empresa_logo
            FROM sales s
            LEFT JOIN empresas e ON e.id = s.empresa_id
            WHERE s.id = %s
        """, (venda_id,))
        
        db.close()
        
        if not venda:
            return jsonify({'success': False, 'error': 'Venda não encontrada'}), 404
        
        if not venda.get('xml_nfce'):
            return jsonify({'success': False, 'error': 'NFC-e não emitida para esta venda'}), 400
        
        # Verificar logo da empresa
        logo_path = None
        if venda.get('empresa_logo'):
            import os
            # Logo pode estar em diferentes locais
            possiveis_paths = [
                venda.get('empresa_logo'),
                os.path.join('app', 'static', 'uploads', venda.get('empresa_logo')),
                os.path.join('app', 'static', 'logos', venda.get('empresa_logo')),
                os.path.join('static', 'uploads', venda.get('empresa_logo'))
            ]
            for path in possiveis_paths:
                if os.path.exists(path):
                    logo_path = path
                    break
        
        # Gerar PDF com formato especificado
        generator = DanfceGenerator()
        pdf_bytes = generator.gerar_pdf(venda['xml_nfce'], formato=formato, logo_path=logo_path)
        
        # Retornar como PDF
        response = Response(pdf_bytes, mimetype='application/pdf')
        response.headers['Content-Disposition'] = f'inline; filename=DANFCE_{venda.get("numero_nfce", venda_id)}.pdf'
        
        return response
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@nfce_bp.route('/nfce/imprimir-cupom/<int:venda_id>')
@login_required
def imprimir_danfce_cupom(venda_id):
    """
    Gera e retorna PDF do DANFCE em formato cupom 80mm
    """
    try:
        from app.services.danfce_generator import DanfceGenerator
        from flask import Response
        
        db = Database()
        
        venda = db.fetch_one("""
            SELECT xml_nfce, numero_nfce, chave_acesso_nfce
            FROM sales WHERE id = %s
        """, (venda_id,))
        
        db.close()
        
        if not venda or not venda.get('xml_nfce'):
            return jsonify({'success': False, 'error': 'NFC-e não encontrada'}), 404
        
        # Gerar PDF formato cupom
        generator = DanfceGenerator()
        pdf_bytes = generator.gerar_pdf(venda['xml_nfce'], formato='80mm')
        
        response = Response(pdf_bytes, mimetype='application/pdf')
        response.headers['Content-Disposition'] = f'inline; filename=DANFCE_CUPOM_{venda.get("numero_nfce", venda_id)}.pdf'
        
        return response
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# ROTAS DE CANCELAMENTO
# ============================================================================

@nfce_bp.route('/venda/cancelar/<int:venda_id>', methods=['POST'])
@login_required
def cancelar_venda(venda_id):
    """
    Cancela uma venda - identifica automaticamente o tipo (Venda, NFC-e, NF-e)
    """
    try:
        data = request.get_json() or {}
        justificativa = data.get('justificativa', 'Cancelamento solicitado pelo usuario')
        
        # Validar justificativa (mínimo 15 caracteres para SEFAZ)
        if len(justificativa) < 15:
            justificativa = justificativa + ' ' * (15 - len(justificativa))
        
        db = Database()
        
        # Buscar dados da venda
        venda = db.fetch_one("""
            SELECT id, empresa_id, status, 
                   numero_nfce, chave_acesso_nfce, status_nfce, protocolo_nfce,
                   numero_nfe, chave_acesso_nfe, status_nfe, protocolo_nfe,
                   net_total
            FROM sales WHERE id = %s
        """, (venda_id,))
        
        if not venda:
            db.close()
            return jsonify({'success': False, 'error': 'Venda não encontrada'}), 404
        
        # Verificar se já está cancelada
        if venda.get('status') == 'cancelled':
            db.close()
            return jsonify({'success': False, 'error': 'Venda já está cancelada'}), 400
        
        # Identificar tipo de documento
        tipo_documento = 'venda'
        cancelamento_fiscal = None
        
        # Verificar NFC-e
        if venda.get('chave_acesso_nfce') and venda.get('status_nfce') == 'autorizada':
            tipo_documento = 'nfce'
            
            # Cancelar NFC-e na SEFAZ
            from app.services.nfce_service import NFCeService
            nfce_service = NFCeService(venda['empresa_id'])
            cancelamento_fiscal = nfce_service.cancelar(venda_id, justificativa)
            
            if not cancelamento_fiscal.get('sucesso'):
                db.close()
                return jsonify({
                    'success': False,
                    'error': f"Erro ao cancelar NFC-e: {cancelamento_fiscal.get('erro', 'Erro')}",
                    'tipo': tipo_documento
                }), 400
        
        # Verificar NF-e
        elif venda.get('chave_acesso_nfe') and venda.get('status_nfe') == 'autorizada':
            tipo_documento = 'nfe'
            
            # Cancelar NF-e na SEFAZ
            from app.services.nfe_service import NFeService
            nfe_service = NFeService()
            cancelamento_fiscal = nfe_service.cancelar_nfe(venda['chave_acesso_nfe'], justificativa)
            
            if not cancelamento_fiscal.get('sucesso'):
                db.close()
                return jsonify({
                    'success': False,
                    'error': f"Erro ao cancelar NF-e: {cancelamento_fiscal.get('erro', 'Erro')}",
                    'tipo': tipo_documento
                }), 400
        
        # Atualizar status da venda para cancelada
        db.execute("""
            UPDATE sales SET 
                status = 'cancelled',
                updated_at = NOW()
            WHERE id = %s
        """, (venda_id,))
        
        # Reverter movimentação de estoque
        try:
            itens = db.fetch_all("""
                SELECT product_id, quantity FROM sale_items WHERE sale_id = %s
            """, (venda_id,))
            
            for item in itens:
                db.execute("""
                    INSERT INTO stock_movements 
                    (product_id, quantity, movement_type, reference_id, reference_type,
                     created_at, notes, created_by)
                    VALUES (%s, %s, 'cancel_sale', %s, 'sale', NOW(), %s, %s)
                """, (
                    item['product_id'],
                    abs(item['quantity']),
                    venda_id,
                    f'Estorno cancelamento venda #{venda_id}',
                    session.get('user_id', 1)
                ))
                
                db.execute("""
                    UPDATE current_stock 
                    SET quantity = quantity + %s
                    WHERE product_id = %s AND location_id = 1
                """, (abs(item['quantity']), item['product_id']))
            
            print(f"[CANCELAMENTO] Estoque revertido para {len(itens)} itens")
        except Exception as e:
            print(f"[CANCELAMENTO] Aviso estoque: {str(e)}")
        
        # Cancelar contas a receber
        try:
            db.execute("""
                UPDATE accounts_receivable 
                SET status = 'cancelled'
                WHERE sale_id = %s
            """, (venda_id,))
        except Exception as e:
            print(f"[CANCELAMENTO] Aviso contas: {str(e)}")
        
        db.close()
        
        resposta = {
            'success': True,
            'message': f'Venda #{venda_id} cancelada com sucesso!',
            'tipo': tipo_documento,
            'venda_id': venda_id
        }
        
        if cancelamento_fiscal:
            resposta['protocolo_cancelamento'] = cancelamento_fiscal.get('protocolo')
        
        return jsonify(resposta)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@nfce_bp.route('/venda/info-cancelamento/<int:venda_id>')
@login_required
def info_cancelamento(venda_id):
    """
    Retorna informações sobre a venda para o modal de cancelamento
    """
    try:
        db = Database()
        
        venda = db.fetch_one("""
            SELECT s.id, s.empresa_id, s.status, s.net_total,
                   s.numero_nfce, s.chave_acesso_nfce, s.status_nfce,
                   s.numero_nfe, s.chave_acesso_nfe, s.status_nfe,
                   s.sale_date, c.name as customer_name
            FROM sales s
            LEFT JOIN customers c ON s.customer_id = c.id
            WHERE s.id = %s
        """, (venda_id,))
        
        db.close()
        
        if not venda:
            return jsonify({'success': False, 'error': 'Venda não encontrada'}), 404
        
        # Identificar tipo
        tipo = 'venda'
        numero_documento = str(venda_id)
        aviso = ''
        
        if venda.get('chave_acesso_nfce') and venda.get('status_nfce') == 'autorizada':
            tipo = 'nfce'
            numero_documento = f"NFC-e {venda.get('numero_nfce', '')}"
            aviso = 'Esta venda possui NFC-e autorizada. O cancelamento será enviado à SEFAZ.'
        elif venda.get('chave_acesso_nfe') and venda.get('status_nfe') == 'autorizada':
            tipo = 'nfe'
            numero_documento = f"NF-e {venda.get('numero_nfe', '')}"
            aviso = 'Esta venda possui NF-e autorizada. O cancelamento será enviado à SEFAZ.'
        
        return jsonify({
            'success': True,
            'venda_id': venda_id,
            'tipo': tipo,
            'numero_documento': numero_documento,
            'status': venda.get('status'),
            'valor': float(venda.get('net_total', 0)),
            'cliente': venda.get('customer_name', 'Não identificado'),
            'data': str(venda.get('sale_date', '')),
            'aviso': aviso
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
