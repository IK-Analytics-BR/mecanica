"""
test_integracao_completa.py — Testes de integração end-to-end.
Simula um dia produtivo completo com dados relacionados entre todos os módulos.

Fluxo testado:
1. Cadastro cliente → 2. Cadastro veículo (vinculado ao cliente)
3. Cadastro mecânico → 4. Cadastro peça no estoque
5. Abertura de OS (cliente + veículo + mecânico)
6. Adição de item de serviço e peça na OS
7. Início do serviço pelo mecânico
8. Aprovação do orçamento → geração de C/R
9. Conclusão da OS → baixa automática no estoque
10. Verificação: estoque baixou, C/R criado com valor correto

Executar:
    cd C:\\Users\\aritana\\CascadeProjects\\IKFlow-Mecanica
    py -m pytest tests/test_integracao_completa.py -v -s
"""
import pytest
import json
import sys
import os
from datetime import datetime, date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

from main_mysql import app, get_db


@pytest.fixture(scope='module')
def client():
    """Fixture que loga como admin e disponibiliza o client de teste."""
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    
    with app.test_client() as c:
        with app.app_context():
            # Login
            resp = c.post('/login', data={
                'username': 'admin',
                'password': 'admin123',
            }, follow_redirects=True)
            assert resp.status_code == 200
            
            yield c


@pytest.fixture(scope='module')
def db():
    """Fixture que retorna conexão com o banco para asserts."""
    with app.app_context():
        yield get_db()


class TestFluxoCompletoOficina:
    """Testa o fluxo completo de uma oficina — integração entre todos os módulos."""
    
    def test_01_cadastrar_cliente_completo(self, client, db):
        """T01: Cadastra cliente com todos os dados (CNPJ, endereço, contato)."""
        timestamp = datetime.now().strftime('%H%M%S')
        self.cliente_data = {
            'name': f'Oficina Teste Integração {timestamp}',
            'email': f'teste{timestamp}@oficina.com',
            'phone': f'1199999{timestamp[-4:]}',
            'cpf_cnpj': f'12.345.678/{timestamp[:2]}00-01',
            'address': 'Rua das Oficinas, 1000',
            'city': 'São Paulo',
            'state': 'SP',
            'zip': '01001-000',
            'segment': 'oficina',
            'active': '1',
        }
        
        resp = client.post('/clientes/novo', data=self.cliente_data, follow_redirects=True)
        assert resp.status_code in (200, 302)
        
        # Verifica se cliente foi criado no banco
        cliente = db.fetch_one(
            "SELECT * FROM customers WHERE email = %s", 
            (self.cliente_data['email'],)
        )
        assert cliente is not None
        self.__class__.cliente_id = cliente['id']
        print(f"\n✅ Cliente criado: ID {cliente['id']} - {cliente['name']}")
    
    def test_02_cadastrar_veiculo_vinculado(self, client, db):
        """T02: Cadastra veículo vinculado ao cliente criado."""
        timestamp = datetime.now().strftime('%H%M%S')
        self.veiculo_data = {
            'name': 'Honda Civic 2020 EXL',
            'serial_number': f'ABC{timestamp[-4:]}',
            'model': 'Civic',
            'year': '2020',
            'fuel_type': 'flex',
            'accumulated_hours': '35000',
            'customer_id': str(self.__class__.cliente_id),
        }
        
        resp = client.post('/equipamentos/novo', data=self.veiculo_data, follow_redirects=True)
        assert resp.status_code in (200, 302)
        
        # Verifica veículo vinculado ao cliente
        veiculo = db.fetch_one(
            "SELECT * FROM equipment WHERE serial_number = %s AND customer_id = %s",
            (self.veiculo_data['serial_number'], self.__class__.cliente_id)
        )
        assert veiculo is not None
        assert veiculo['customer_id'] == self.__class__.cliente_id
        self.__class__.veiculo_id = veiculo['id']
        print(f"\n✅ Veículo criado: ID {veiculo['id']} - {veiculo['name']} (Cliente: {veiculo['customer_id']})")
    
    def test_03_cadastrar_mecanico(self, client, db):
        """T03: Cadastra técnico/mecânico no sistema."""
        timestamp = datetime.now().strftime('%H%M%S')
        self.mecanico_data = {
            'name': f'Mecânico João {timestamp}',
            'email': f'joao.mec{timestamp}@oficina.com',
            'phone': f'1198888{timestamp[-4:]}',
            'specialization': 'motor_transmissao',
            'hourly_rate': '85.00',
            'active': '1',
        }
        
        resp = client.post('/tecnicos/novo', data=self.mecanico_data, follow_redirects=True)
        assert resp.status_code in (200, 302)
        
        mecanico = db.fetch_one(
            "SELECT * FROM technicians WHERE email = %s",
            (self.mecanico_data['email'],)
        )
        assert mecanico is not None
        self.__class__.mecanico_id = mecanico['id']
        print(f"\n✅ Mecânico criado: ID {mecanico['id']} - {mecanico['name']} (R$ {mecanico['hourly_rate']}/h)")
    
    def test_04_cadastrar_peca_estoque(self, client, db):
        """T04: Cadastra peça no estoque com quantidade inicial."""
        timestamp = datetime.now().strftime('%H%M%S')
        self.peca_data = {
            'sku': f'OLFLTR{timestamp[-4:]}',
            'name': f'Filtro de Óleo Motor Teste {timestamp[-2:]}',
            'category_id': '1',  # Assume categoria 1 existe
            'brand_id': '1',     # Assume marca 1 existe
            'unit_id': '1',      # Assume unidade 1 existe
            'cost_price': '45.00',
            'sale_price': '89.90',
            'stock_quantity': '15',
            'min_stock': '5',
            'location': 'Prateleira A3',
            'active': '1',
        }
        
        resp = client.post('/produtos/novo', data=self.peca_data, follow_redirects=True)
        assert resp.status_code in (200, 302)
        
        peca = db.fetch_one(
            "SELECT * FROM products WHERE sku = %s",
            (self.peca_data['sku'],)
        )
        assert peca is not None
        assert float(peca['stock_quantity']) == 15.0
        self.__class__.peca_id = peca['id']
        self.__class__.peca_preco = float(peca['sale_price'])
        print(f"\n✅ Peça criada: ID {peca['id']} - {peca['name']} (Estoque: {peca['stock_quantity']}, R$ {peca['sale_price']})")
    
    def test_05_abrir_os_completa(self, client, db):
        """T05: Abre OS vinculando cliente, veículo e mecânico."""
        self.os_data = {
            'customer_id': str(self.__class__.cliente_id),
            'equipment_id': str(self.__class__.veiculo_id),
            'technician_id': str(self.__class__.mecanico_id),
            'priority': 'medium',
            'description': 'Troca de óleo e revisão preventiva de 35.000 km',
            'problem_description': 'Cliente reclama de barulho no motor ao acelerar',
            'estimated_completion': date.today().isoformat(),
        }
        
        resp = client.post('/service_orders/add', data=self.os_data, follow_redirects=True)
        assert resp.status_code in (200, 302)
        
        # Busca a OS mais recente deste cliente
        os_record = db.fetch_one(
            "SELECT * FROM service_orders WHERE customer_id = %s ORDER BY id DESC LIMIT 1",
            (self.__class__.cliente_id,)
        )
        assert os_record is not None
        assert os_record['customer_id'] == self.__class__.cliente_id
        assert os_record['equipment_id'] == self.__class__.veiculo_id
        assert os_record['technician_id'] == self.__class__.mecanico_id
        self.__class__.os_id = os_record['id']
        print(f"\n✅ OS criada: ID {os_record['id']} - Nº {os_record.get('order_number', 'N/A')} (Cliente: {os_record['customer_id']}, Veículo: {os_record['equipment_id']}, Mecânico: {os_record['technician_id']})")
    
    def test_06_adicionar_item_servico_os(self, client, db):
        """T06: Adiciona mão de obra (serviço) na OS."""
        item_servico = {
            'item_type': 'service',
            'description': 'Troca de óleo e filtros - revisão 35k km',
            'quantity': '1',
            'unit_price': '120.00',
            'technician_id': str(self.__class__.mecanico_id),
        }
        
        resp = client.post(f'/service_orders/add_item/{self.__class__.os_id}', 
                          data=item_servico, follow_redirects=True)
        assert resp.status_code in (200, 302)
        
        # Verifica item na OS
        item = db.fetch_one(
            "SELECT * FROM service_order_items WHERE service_order_id = %s AND item_type = 'service'",
            (self.__class__.os_id,)
        )
        assert item is not None
        assert float(item['total_price']) == 120.00
        print(f"\n✅ Item de serviço adicionado: {item['description']} - R$ {item['total_price']}")
    
    def test_07_adicionar_item_peca_os(self, client, db):
        """T07: Adiciona peça na OS."""
        item_peca = {
            'item_type': 'product',
            'product_id': str(self.__class__.peca_id),
            'description': self.peca_data['name'],
            'quantity': '2',
            'unit_price': str(self.__class__.peca_preco),
        }
        
        resp = client.post(f'/service_orders/add_item/{self.__class__.os_id}', 
                          data=item_peca, follow_redirects=True)
        assert resp.status_code in (200, 302)
        
        # Verifica peça na OS
        item = db.fetch_one(
            "SELECT * FROM service_order_items WHERE service_order_id = %s AND product_id = %s",
            (self.__class__.os_id, self.__class__.peca_id)
        )
        assert item is not None
        expected_total = 2 * self.__class__.peca_preco
        assert float(item['total_price']) == expected_total
        self.__class__.valor_pecas = expected_total
        print(f"\n✅ Item de peça adicionado: {item['description']} x2 = R$ {item['total_price']}")
    
    def test_08_iniciar_servico_mecanico(self, client, db):
        """T08: Mecânico inicia o serviço na OS."""
        resp = client.post(f'/service_orders/{self.__class__.os_id}/iniciar', 
                          follow_redirects=True)
        assert resp.status_code in (200, 302)
        
        # Verifica data_inicio_servico preenchida
        os_record = db.fetch_one(
            "SELECT * FROM service_orders WHERE id = %s",
            (self.__class__.os_id,)
        )
        assert os_record['data_inicio_servico'] is not None
        print(f"\n✅ Serviço iniciado em: {os_record['data_inicio_servico']}")
    
    def test_09_aprovar_orcamento_gerar_contas_receber(self, client, db):
        """T09: Aprova orçamento e verifica se gerou C/R automaticamente."""
        # Busca valor total da OS antes de aprovar
        items = db.fetch_all(
            "SELECT SUM(total_price) as total FROM service_order_items WHERE service_order_id = %s",
            (self.__class__.os_id,)
        )
        total_os = float(items[0]['total']) if items[0]['total'] else 0
        self.__class__.valor_total_os = total_os
        
        # Aprova orçamento
        resp = client.post(f'/service_orders/{self.__class__.os_id}/aprovar',
                          data={'approval_notes': 'Orçamento aprovado pelo cliente via WhatsApp'},
                          follow_redirects=True)
        assert resp.status_code in (200, 302)
        
        # Verifica se C/R foi criado
        cr = db.fetch_one(
            "SELECT * FROM accounts_receivable WHERE origin = 'service' AND reference_id = %s",
            (self.__class__.os_id,)
        )
        assert cr is not None, "Contas a Receber não foi gerada automaticamente!"
        assert float(cr['amount']) == total_os
        self.__class__.cr_id = cr['id']
        print(f"\n✅ C/R gerada: ID {cr['id']} - R$ {cr['amount']} (vencimento: {cr['due_date']})")
    
    def test_10_finalizar_os_baixa_estoque(self, client, db):
        """T10: Finaliza OS e verifica baixa automática no estoque."""
        # Estoque antes
        estoque_antes = db.fetch_one(
            "SELECT stock_quantity FROM products WHERE id = %s",
            (self.__class__.peca_id,)
        )
        qtd_antes = float(estoque_antes['stock_quantity'])
        
        # Finaliza OS
        resp = client.post(f'/service_orders/{self.__class__.os_id}/finalizar',
                          data={'completion_notes': 'Serviço concluído com sucesso'},
                          follow_redirects=True)
        assert resp.status_code in (200, 302)
        
        # Verifica OS concluída
        os_record = db.fetch_one(
            "SELECT * FROM service_orders WHERE id = %s",
            (self.__class__.os_id,)
        )
        assert os_record['status'] == 'completed'
        assert os_record['data_fim_servico'] is not None
        
        # Verifica baixa no estoque
        estoque_depois = db.fetch_one(
            "SELECT stock_quantity FROM products WHERE id = %s",
            (self.__class__.peca_id,)
        )
        qtd_depois = float(estoque_depois['stock_quantity'])
        
        assert qtd_depois == qtd_antes - 2, f"Estoque não foi baixado! Antes: {qtd_antes}, Depois: {qtd_depois}"
        
        print(f"\n✅ OS finalizada: ID {os_record['id']} - Status: {os_record['status']}")
        print(f"✅ Estoque baixado: {qtd_antes} → {qtd_depois} unidades")
    
    def test_11_verificar_integracao_financeira(self, client, db):
        """T11: Verifica se valores financeiros estão consistentes."""
        # Busca C/R novamente
        cr = db.fetch_one(
            "SELECT * FROM accounts_receivable WHERE id = %s",
            (self.__class__.cr_id,)
        )
        
        # Verifica se valor bate com OS
        assert float(cr['amount']) == self.__class__.valor_total_os
        
        # Verifica status da C/R
        assert cr['status'] in ('pending', 'open')
        
        print(f"\n✅ Integração financeira OK: OS R$ {self.__class__.valor_total_os} = C/R R$ {cr['amount']}")
    
    def test_12_verificar_kardex_movimentacao(self, client, db):
        """T12: Verifica se movimentação de estoque foi registrada no Kardex."""
        kardex = db.fetch_all(
            "SELECT * FROM kardex WHERE product_id = %s AND reference_id = %s AND movement_type = 'output'",
            (self.__class__.peca_id, self.__class__.os_id)
        )
        
        assert len(kardex) >= 1, "Movimentação de saída não registrada no Kardex!"
        
        mov = kardex[0]
        assert float(mov['quantity']) == 2.0
        assert mov['reference_type'] == 'service_order'
        
        print(f"\n✅ Kardex registrado: Saída de {mov['quantity']} unidades (OS #{mov['reference_id']})")
    
    def test_13_busca_global_encontra_os(self, client, db):
        """T13: Busca global encontra a OS criada."""
        # Pega número da OS
        os_record = db.fetch_one(
            "SELECT order_number FROM service_orders WHERE id = %s",
            (self.__class__.os_id,)
        )
        order_number = os_record['order_number'] if os_record else str(self.__class__.os_id)
        
        resp = client.get(f'/busca-global?q={order_number[:3]}', follow_redirects=True)
        assert resp.status_code == 200
        
        data = json.loads(resp.data)
        assert 'results' in data
        # Deve ter pelo menos um resultado (a OS)
        assert len(data['results']) >= 1
        
        print(f"\n✅ Busca global funcionando: {len(data['results'])} resultados encontrados")


class TestFluxoPdvCaixa:
    """Testa fluxo de PDV e controle de caixa."""
    
    def test_14_abrir_caixa(self, client, db):
        """T14: Operador abre caixa do dia."""
        caixa_data = {
            'opening_amount': '500.00',
            'notes': 'Abertura caixa teste integração',
        }
        
        resp = client.post('/cash_register/open', data=caixa_data, follow_redirects=True)
        assert resp.status_code in (200, 302)
        
        # Verifica caixa aberto
        caixa = db.fetch_one(
            "SELECT * FROM cash_register WHERE status = 'open' ORDER BY id DESC LIMIT 1"
        )
        assert caixa is not None
        assert float(caixa['opening_amount']) == 500.00
        self.__class__.caixa_id = caixa['id']
        print(f"\n✅ Caixa aberto: ID {caixa['id']} - R$ {caixa['opening_amount']}")
    
    def test_15_registrar_venda_pdv(self, client, db):
        """T15: Registra venda no PDV."""
        # Busca uma peça para vender
        peca = db.fetch_one("SELECT id, sale_price FROM products WHERE stock_quantity > 0 LIMIT 1")
        if not peca:
            pytest.skip("Nenhuma peça em estoque para testar venda")
        
        venda_data = {
            'product_id': str(peca['id']),
            'quantity': '1',
            'payment_method': 'cash',
            'sale_price': str(peca['sale_price']),
        }
        
        resp = client.post('/vendas/pdv/sale', data=venda_data, follow_redirects=True)
        assert resp.status_code in (200, 302)
        print(f"\n✅ Venda PDV registrada: Peça {peca['id']} - R$ {peca['sale_price']}")
    
    def test_16_fechar_caixa(self, client, db):
        """T16: Fecha caixa e verifica saldo."""
        fechamento = {
            'closing_amount': '650.00',  # 500 abertura + 150 vendas
            'notes': 'Fechamento teste integração',
        }
        
        resp = client.post(f'/cash_register/close/{self.__class__.caixa_id}', 
                          data=fechamento, follow_redirects=True)
        assert resp.status_code in (200, 302)
        
        caixa = db.fetch_one(
            "SELECT * FROM cash_register WHERE id = %s",
            (self.__class__.caixa_id,)
        )
        assert caixa['status'] == 'closed'
        print(f"\n✅ Caixa fechado: R$ {caixa['opening_amount']} → R$ {caixa['closing_amount']}")


class TestRelatoriosDashboard:
    """Testa acesso aos relatórios e dashboards."""
    
    def test_17_dashboard_os(self, client):
        """T17: Dashboard de OS carrega com dados."""
        resp = client.get('/service_orders/dashboard', follow_redirects=True)
        assert resp.status_code == 200
        print("\n✅ Dashboard OS acessível")
    
    def test_18_relatorio_financeiro(self, client):
        """T18: Relatório financeiro gera sem erro."""
        resp = client.get('/cash_flow/report', follow_redirects=True)
        assert resp.status_code in (200, 302)
        print("\n✅ Relatório financeiro acessível")
    
    def test_19_relatorio_estoque(self, client):
        """T19: Relatório de estoque gera sem erro."""
        resp = client.get('/inventory/report', follow_redirects=True)
        assert resp.status_code in (200, 302)
        print("\n✅ Relatório estoque acessível")
    
    def test_20_relatorio_mecanicos(self, client):
        """T20: Relatório de produtividade dos mecânicos."""
        resp = client.get('/reports/relatorio_mecanicos', follow_redirects=True)
        assert resp.status_code in (200, 302)
        print("\n✅ Relatório mecânicos acessível")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
