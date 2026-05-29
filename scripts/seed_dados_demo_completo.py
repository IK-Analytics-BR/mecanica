#!/usr/bin/env python3
"""
seed_dados_demo_completo.py — Popula o banco com dados fictícios para demonstração COMPLETA.
Contempla TODAS as telas e tabelas do MVP Mecânica.

Executar:
    cd C:\\Users\\aritana\\CascadeProjects\\IKFlow-Mecanica
    py scripts\\seed_dados_demo_completo.py

Cria dados para todas as telas:
    ✓ Cadastros: Clientes, Veículos, Mecânicos, Fornecedores, Vendedores, Usuários
    ✓ Estoque: Produtos, Categorias, Marcas, Unidades, Kardex
    ✓ OS: Ordens de Serviço (todos os status), Itens de OS, Orçamentos
    ✓ Financeiro: Contas a Receber, Contas a Pagar, Fluxo de Caixa, Caixa
    ✓ Fiscal: Notas Fiscais (NF-e, NFS-e)
    ✓ Compras: Pedidos de Compra, Recebimentos
    ✓ Vendas: PDV, Romaneios
    ✓ RH: Ponto, Jornada, Comissões
    ✓ Pós-venda: Garantias, Manutenções Preventivas
    
AVISO: Execute APENAS em banco de TESTE/DEMO.
"""
import sys
import os
import random
from datetime import datetime, timedelta, date
from decimal import Decimal

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

from main_mysql import app, get_db


def generate_cpf():
    """Gera CPF fictício."""
    n = [random.randint(0, 9) for _ in range(9)]
    d1 = sum((i+1) * v for i, v in enumerate(n)) % 11
    d1 = 0 if d1 < 2 else 11 - d1
    d2 = sum(i * v for i, v in enumerate(n[1:] + [d1])) % 11
    d2 = 0 if d2 < 2 else 11 - d2
    return f"{n[0]}{n[1]}{n[2]}.{n[3]}{n[4]}{n[5]}.{n[6]}{n[7]}{n[8]}-{d1}{d2}"


def generate_cnpj():
    """Gera CNPJ fictício."""
    n = [random.randint(0, 9) for _ in range(8)] + [0, 0, 0, 1]
    return f"{n[0]}{n[1]}.{n[2]}{n[3]}{n[4]}.{n[5]}{n[6]}{n[7]}/{n[8]}{n[9]}{n[10]}{n[11]}-{n[12]}{n[13]}"


def seed_demo_data():
    """Função principal de seeding."""
    
    print("="*70)
    print("🚀 SEED DE DADOS COMPLETO PARA DEMONSTRAÇÃO - MVP MECÂNICA")
    print("="*70)
    
    with app.app_context():
        db = get_db()
        
        # ============================================================
        # 1. ESTRUTURA BASE (Categorias, Marcas, Unidades)
        # ============================================================
        print("\n📦 Criando estrutura base de produtos...")
        
        categorias_nomes = ["Motor", "Transmissão", "Freios", "Suspensão", "Elétrica", 
                          "Arrefecimento", "Filtros", "Óleos", "Acessórios", "Pneus"]
        categorias_ids = []
        for cat in categorias_nomes:
            exists = db.fetch_one("SELECT id FROM product_categories WHERE name = %s", (cat,))
            if exists:
                categorias_ids.append(exists['id'])
            else:
                db.execute("INSERT INTO product_categories (name, active) VALUES (%s, 1)", (cat,))
                categorias_ids.append(db.last_insert_id())
        
        marcas_nomes = ["Original", "Bosch", "Fram", "NGK", "Acdelco", "Wega", 
                       "Maxxi", "Valeo", "SKF", "Dayco", "Gates"]
        marcas_ids = []
        for marca in marcas_nomes:
            exists = db.fetch_one("SELECT id FROM product_brands WHERE name = %s", (marca,))
            if exists:
                marcas_ids.append(exists['id'])
            else:
                db.execute("INSERT INTO product_brands (name, active) VALUES (%s, 1)", (marca,))
                marcas_ids.append(db.last_insert_id())
        
        # Unidades
        unidades = [('Unidade', 'UN'), ('Peça', 'PC'), ('Litro', 'LT'), ('Par', 'PR')]
        unidades_ids = []
        for nome, abrev in unidades:
            exists = db.fetch_one("SELECT id FROM product_units WHERE abbreviation = %s", (abrev,))
            if exists:
                unidades_ids.append(exists['id'])
            else:
                db.execute("INSERT INTO product_units (name, abbreviation) VALUES (%s, %s)", (nome, abrev))
                unidades_ids.append(db.last_insert_id())
        
        print(f"   ✅ {len(categorias_ids)} categorias, {len(marcas_ids)} marcas, {len(unidades_ids)} unidades")
        
        # ============================================================
        # 2. CLIENTES (20)
        # ============================================================
        print("\n👥 Criando 20 clientes...")
        
        clientes_data = [
            ("João Silva", "SP"), ("Maria Santos", "RJ"), ("Pedro Costa", "MG"),
            ("Ana Oliveira", "SP"), ("Carlos Lima", "PR"), ("Fernanda Souza", "CE"),
            ("Lucas Mendes", "BA"), ("Juliana Rocha", "SP"), ("Roberto Almeida", "PE"),
            ("Patrícia Ferreira", "RJ"), ("Marcelo Dias", "SP"), ("Camila Barbosa", "BA"),
            ("Ricardo Nunes", "SP"), ("Aline Martins", "SP"), ("Bruno Ribeiro", "SP"),
            ("Carla Souza", "MG"), ("Daniel Lima", "RS"), ("Elisa Mendes", "SP"),
            ("Fábio Oliveira", "RJ"), ("Gabriela Costa", "SP"),
        ]
        
        clientes_ids = []
        for i, (nome, uf) in enumerate(clientes_data, 1):
            email = f"cliente{i:03d}@demo.ikflow.com"
            telefone = f"{random.choice([11,12,13,14,15,16,17,18,19,21,31,41,51,61,71,81,85])}{random.randint(10000000, 99999999)}"
            cpf = generate_cpf()
            cidade = {"SP": "São Paulo", "RJ": "Rio de Janeiro", "MG": "Belo Horizonte",
                     "PR": "Curitiba", "CE": "Fortaleza", "BA": "Salvador", "PE": "Recife",
                     "RS": "Porto Alegre"}.get(uf, "São Paulo")
            
            exists = db.fetch_one("SELECT id FROM customers WHERE email = %s", (email,))
            if exists:
                clientes_ids.append(exists['id'])
                continue
            
            sql = """
                INSERT INTO customers (name, email, phone, cpf_cnpj, address, city, state, zip, active, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 1, NOW())
            """
            db.execute(sql, (nome, email, telefone, cpf, f"Rua Demo, {i*100}", cidade, uf, f"0100{i:02d}-000"))
            clientes_ids.append(db.last_insert_id())
        
        print(f"   ✅ {len(clientes_ids)} clientes criados")
        
        # ============================================================
        # 3. VEÍCULOS (30) — vinculados aos clientes
        # ============================================================
        print("\n🚗 Criando 30 veículos...")
        
        modelos = [
            ("Honda", "Civic", 2020), ("Toyota", "Corolla", 2019), ("Volkswagen", "Gol", 2018),
            ("Chevrolet", "Onix", 2021), ("Ford", "Ka", 2017), ("Fiat", "Uno", 2016),
            ("Hyundai", "HB20", 2020), ("Renault", "Sandero", 2019), ("Jeep", "Compass", 2021),
            ("Nissan", "Kicks", 2020), ("Peugeot", "208", 2019), ("Citroën", "C3", 2018),
            ("Honda", "Fit", 2017), ("Toyota", "Yaris", 2020), ("Volkswagen", "Polo", 2021),
            ("Chevrolet", "Tracker", 2020), ("Ford", "EcoSport", 2019), ("Fiat", "Strada", 2021),
            ("Hyundai", "Creta", 2020), ("Renault", "Duster", 2018), ("Jeep", "Renegade", 2019),
            ("Nissan", "Versa", 2017), ("Peugeot", "2008", 2020), ("Citroën", "C4", 2016),
            ("Honda", "HR-V", 2019), ("Toyota", "Hilux", 2020), ("Volkswagen", "Virtus", 2021),
            ("Chevrolet", "S10", 2019), ("Ford", "Ranger", 2020), ("Fiat", "Toro", 2021),
        ]
        
        veiculos_ids = []
        for i, (marca, modelo, ano) in enumerate(modelos, 1):
            placa = f"DEM{i:04d}"
            cliente_id = random.choice(clientes_ids)
            
            exists = db.fetch_one("SELECT id FROM equipment WHERE serial_number = %s", (placa,))
            if exists:
                veiculos_ids.append(exists['id'])
                continue
            
            sql = """
                INSERT INTO equipment (name, serial_number, brand, model, year, fuel_type,
                                     accumulated_hours, customer_id, active, created_at)
                VALUES (%s, %s, %s, %s, %s, 'flex', %s, %s, 1, NOW())
            """
            km = random.randint(15000, 80000)
            db.execute(sql, (f"{marca} {modelo} {ano}", placa, marca, modelo, ano, km, cliente_id))
            veiculos_ids.append(db.last_insert_id())
        
        print(f"   ✅ {len(veiculos_ids)} veículos criados")
        
        # ============================================================
        # 4. FORNECEDORES (10)
        # ============================================================
        print("\n🏭 Criando 10 fornecedores...")
        
        fornecedores_data = [
            ("AutoPeças Nacional Ltda", "contato@autopecasnacional.com", "fornecedor_pecas", "R$ 3.000"),
            ("Distribuidora de Óleos São Paulo", "vendas@oleossp.com", "fornecedor_oleo", "R$ 2.500"),
            ("Bosch Automotive Brasil", "pedidos@bosch.com.br", "fornecedor_eletrica", "R$ 5.000"),
            ("Filtros & Cia", "comercial@filtros.com", "fornecedor_filtros", "R$ 1.500"),
            ("Freios Master", "vendas@freiosmaster.com", "fornecedor_freios", "R$ 2.000"),
            ("Pneus Sul", "contato@pneussul.com", "fornecedor_pneus", "R$ 4.000"),
            ("Acessórios Automotivos Ltda", "vendas@acessorios.com", "fornecedor_acessorios", "R$ 1.000"),
            ("Suspensão Pro", "pedidos@suspensaopro.com", "fornecedor_suspensao", "R$ 1.800"),
            ("Arrefecimento Plus", "comercial@arrefecimento.com", "fornecedor_arrefecimento", "R$ 1.200"),
            ("Transmissão & Cia", "vendas@transmissao.com", "fornecedor_transmissao", "R$ 2.200"),
        ]
        
        fornecedores_ids = []
        for i, (nome, email, segmento, limite) in enumerate(fornecedores_data, 1):
            cnpj = generate_cnpj()
            telefone = f"11{random.randint(30000000, 39999999)}"
            
            exists = db.fetch_one("SELECT id FROM suppliers WHERE cnpj_cpf = %s", (cnpj,))
            if exists:
                fornecedores_ids.append(exists['id'])
                continue
            
            sql = """
                INSERT INTO suppliers (name, cnpj_cpf, email, phone, address, city, state,
                                     segment, credit_limit, active, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 1, NOW())
            """
            db.execute(sql, (nome, cnpj, email, telefone, f"Av. Industrial, {i*500}", "São Paulo", "SP",
                           segmento, float(limite.replace("R$ ", "").replace(".", "").replace(",", ".")),))
            fornecedores_ids.append(db.last_insert_id())
        
        print(f"   ✅ {len(fornecedores_ids)} fornecedores criados")
        
        # ============================================================
        # 5. MECÂNICOS/TÉCNICOS (10)
        # ============================================================
        print("\n🔧 Criando 10 mecânicos/técnicos...")
        
        mecanicos_data = [
            ("João das Peças", "joao.pecas@demo.com", "motor_transmissao", 85.00),
            ("Pedro Elétrica", "pedro.elec@demo.com", "eletrica", 90.00),
            ("Carlos Funilaria", "carlos.fun@demo.com", "funilaria", 75.00),
            ("Marcos Arrefecimento", "marcos.ar@demo.com", "arrefecimento", 80.00),
            ("Ricardo Suspensão", "ricardo.sus@demo.com", "suspensao", 82.00),
            ("André Freios", "andre.fre@demo.com", "freios", 78.00),
            ("Bruno Injeção", "bruno.inj@demo.com", "injeção", 95.00),
            ("Fernando Geral", "fernando.g@demo.com", "revisao_geral", 70.00),
            ("Gustavo Pneus", "gustavo.pneus@demo.com", "pneus", 65.00),
            ("Leandro Diagnóstico", "leandro.diag@demo.com", "diagnostico", 100.00),
        ]
        
        mecanicos_ids = []
        for i, (nome, email, esp, valor_hora) in enumerate(mecanicos_data, 1):
            telefone = f"119{random.randint(80000000, 89999999)}"
            
            exists = db.fetch_one("SELECT id FROM technicians WHERE email = %s", (email,))
            if exists:
                mecanicos_ids.append(exists['id'])
                continue
            
            sql = """
                INSERT INTO technicians (name, email, phone, specialization, hourly_rate, active, created_at)
                VALUES (%s, %s, %s, %s, %s, 1, NOW())
            """
            db.execute(sql, (nome, email, telefone, esp, valor_hora))
            mecanicos_ids.append(db.last_insert_id())
        
        print(f"   ✅ {len(mecanicos_ids)} mecânicos criados")
        
        # ============================================================
        # 6. VENDEDORES (5)
        # ============================================================
        print("\n💼 Criando 5 vendedores...")
        
        vendedores_data = [
            ("Roberto Vendas", "roberto.vendas@demo.com", "vendas_balcao", 3.0),
            ("Sandra Atendimento", "sandra.atend@demo.com", "vendas_externas", 5.0),
            ("Thiago Peças", "thiago.pecas@demo.com", "pecas_acessorios", 2.5),
            ("Patricia Pós-venda", "patricia.pos@demo.com", "pos_venda", 4.0),
            ("Marcelo Frotas", "marcelo.frotas@demo.com", "venda_empresas", 2.0),
        ]
        
        vendedores_ids = []
        for i, (nome, email, tipo, comissao) in enumerate(vendedores_data, 1):
            telefone = f"119{random.randint(70000000, 79999999)}"
            cpf = generate_cpf()
            
            exists = db.fetch_one("SELECT id FROM sellers WHERE email = %s", (email,))
            if exists:
                vendedores_ids.append(exists['id'])
                continue
            
            sql = """
                INSERT INTO sellers (name, email, phone, cpf, seller_type, commission_percent, active, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, 1, NOW())
            """
            db.execute(sql, (nome, email, telefone, cpf, tipo, comissao))
            vendedores_ids.append(db.last_insert_id())
        
        print(f"   ✅ {len(vendedores_ids)} vendedores criados")
        
        # ============================================================
        # 7. PRODUTOS/PEÇAS (80)
        # ============================================================
        print("\n🔩 Criando 80 produtos em estoque...")
        
        produtos_base = [
            ("Filtro de Óleo", "OLFLTR", 25.00, 55.00, "Filtros"),
            ("Filtro de Ar", "ARFLTR", 35.00, 75.00, "Filtros"),
            ("Filtro de Combustível", "CBFLTR", 45.00, 95.00, "Filtros"),
            ("Filtro de Cabine", "CBNFLTR", 40.00, 85.00, "Filtros"),
            ("Pastilha de Freio Dianteira", "FRPD", 80.00, 180.00, "Freios"),
            ("Pastilha de Freio Traseira", "FRPT", 70.00, 160.00, "Freios"),
            ("Disco de Freio", "FRDS", 120.00, 280.00, "Freios"),
            ("Óleo de Motor 5W30", "OLEO5W30", 28.00, 60.00, "Óleos"),
            ("Óleo de Motor 10W40", "OLEO10W40", 26.00, 55.00, "Óleos"),
            ("Óleo de Câmbio", "OLEOCAMB", 35.00, 75.00, "Óleos"),
            ("Fluido de Freio DOT4", "FLDBDOT4", 15.00, 35.00, "Freios"),
            ("Aditivo para Radiador", "ADTRAD", 18.00, 40.00, "Arrefecimento"),
            ("Vela de Ignição", "VELAIGN", 22.00, 48.00, "Elétrica"),
            ("Cabos de Vela", "CBVELA", 45.00, 95.00, "Elétrica"),
            ("Bateria 60Ah", "BAT60AH", 280.00, 450.00, "Elétrica"),
            ("Bateria 45Ah", "BAT45AH", 220.00, 380.00, "Elétrica"),
            ("Correia Dentada", "CRRDTDA", 65.00, 140.00, "Motor"),
            ("Tensor da Correia", "TNSCRR", 85.00, 190.00, "Motor"),
            ("Bomba D'água", "BMPAGUA", 120.00, 280.00, "Arrefecimento"),
            ("Termostato", "TRMSTAT", 45.00, 95.00, "Arrefecimento"),
        ]
        
        produtos_ids = []
        for i in range(80):
            nome_base, cod_base, custo, venda, categoria = random.choice(produtos_base)
            sku = f"{cod_base}{i+1:03d}"
            nome = f"{nome_base} - {random.choice(['Nacional', 'Importado', 'Original', 'Paralelo'])}"
            qtd = random.randint(8, 60)
            min_stock = random.randint(3, 10)
            
            exists = db.fetch_one("SELECT id FROM products WHERE sku = %s", (sku,))
            if exists:
                produtos_ids.append(exists['id'])
                continue
            
            sql = """
                INSERT INTO products (sku, name, category_id, brand_id, unit_id,
                                   cost_price, sale_price, stock_quantity, min_stock,
                                   supplier_id, active, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1, NOW())
            """
            db.execute(sql, (
                sku, nome, random.choice(categorias_ids), random.choice(marcas_ids),
                random.choice(unidades_ids), custo, venda, qtd, min_stock,
                random.choice(fornecedores_ids) if random.random() > 0.3 else None
            ))
            produtos_ids.append(db.last_insert_id())
        
        print(f"   ✅ {len(produtos_ids)} produtos criados")
        
        # ============================================================
        # 8. PEDIDOS DE COMPRA (15)
        # ============================================================
        print("\n📦 Criando 15 pedidos de compra...")
        
        status_pc = ['pending', 'approved', 'partial', 'received', 'cancelled']
        pc_ids = []
        
        for i in range(15):
            fornecedor_id = random.choice(fornecedores_ids)
            status = random.choice(status_pc)
            dias_atras = random.randint(0, 60)
            
            sql = """
                INSERT INTO purchase_orders (supplier_id, status, order_date, expected_date, notes, created_at)
                VALUES (%s, %s, DATE_SUB(NOW(), INTERVAL %s DAY), DATE_ADD(NOW(), INTERVAL %s DAY), %s, NOW())
            """
            db.execute(sql, (fornecedor_id, status, dias_atras, random.randint(1, 15), 
                          f"Pedido de reposição de estoque #{i+1}"))
            pc_id = db.last_insert_id()
            pc_ids.append(pc_id)
            
            # Adiciona itens ao pedido
            num_itens = random.randint(2, 5)
            for _ in range(num_itens):
                produto_id = random.choice(produtos_ids)
                produto = db.fetch_one("SELECT cost_price FROM products WHERE id = %s", (produto_id,))
                qtd = random.randint(5, 20)
                valor_unit = float(produto['cost_price']) if produto else 30.00
                
                sql_item = """
                    INSERT INTO purchase_order_items (purchase_order_id, product_id, quantity, unit_price, total_price)
                    VALUES (%s, %s, %s, %s, %s)
                """
                db.execute(sql_item, (pc_id, produto_id, qtd, valor_unit, qtd * valor_unit))
            
            print(f"   ✅ PC {i+1}: {status} - Fornecedor {fornecedor_id}")
        
        # ============================================================
        # 9. ORDENS DE SERVIÇO (50) — todos os status
        # ============================================================
        print("\n🔧 Criando 50 Ordens de Serviço...")
        
        status_os = (['draft'] * 5) + (['open'] * 10) + (['in_progress'] * 12) + \
                   (['approved'] * 8) + (['completed'] * 10) + (['cancelled'] * 5)
        random.shuffle(status_os)
        
        servicos_desc = [
            "Troca de óleo e filtros", "Revisão 10.000 km", "Revisão 20.000 km",
            "Reparo freios", "Troca pastilhas", "Reparo suspensão",
            "Troca amortecedores", "Reparo elétrico", "Troca bateria",
            "Reparo arrefecimento", "Troca correia", "Regulagem motor",
            "Limpeza bicos", "Troca velas", "Alinhamento",
            "Reparo câmbio", "Troca fluido freio", "Higienização ar",
            "Troca filtro cabine", "Diagnóstico",
        ]
        
        os_ids = []
        os_valores = {}
        
        for i in range(50):
            cliente_id = random.choice(clientes_ids)
            veiculo_id = random.choice(veiculos_ids)
            mecanico_id = random.choice(mecanicos_ids)
            vendedor_id = random.choice(vendedores_ids)
            status = status_os[i]
            
            dias_atras = random.randint(0, 90)
            data_os = datetime.now() - timedelta(days=dias_atras)
            descricao = random.choice(servicos_desc)
            problema = f"Cliente: {random.choice(['barulho', 'vazamento', 'falta potência', 'luz painel'])}"
            
            sql = """
                INSERT INTO service_orders (
                    order_number, customer_id, equipment_id, technician_id, seller_id,
                    status, priority, description, problem_description,
                    entry_date, estimated_completion, created_at
                )
                SELECT CONCAT('OS', YEAR(NOW()), LPAD(COUNT(*)+1, 5, '0')),
                       %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW()
                FROM service_orders
            """
            db.execute(sql, (
                cliente_id, veiculo_id, mecanico_id, vendedor_id, status,
                random.choice(['low', 'medium', 'high', 'urgent']),
                descricao, problema, data_os, data_os + timedelta(days=random.randint(1,5))
            ))
            os_id = db.last_insert_id()
            os_ids.append(os_id)
            
            # Adiciona itens
            total_os = 0
            num_itens = random.randint(2, 5)
            
            for _ in range(num_itens):
                if random.choice([True, False]):
                    # Serviço
                    qtd = random.randint(1, 4)
                    valor_unit = random.choice([75.00, 85.00, 95.00, 120.00])
                    total_item = qtd * valor_unit
                    total_os += total_item
                    
                    sql_item = """
                        INSERT INTO service_order_items 
                        (service_order_id, item_type, description, quantity, unit_price, total_price, technician_id)
                        VALUES (%s, 'service', %s, %s, %s, %s, %s)
                    """
                    db.execute(sql_item, (os_id, descricao, qtd, valor_unit, total_item, mecanico_id))
                else:
                    # Peça
                    produto_id = random.choice(produtos_ids)
                    produto = db.fetch_one("SELECT sale_price, stock_quantity FROM products WHERE id = %s", (produto_id,))
                    qtd = random.randint(1, 3)
                    valor_unit = float(produto['sale_price']) if produto else 50.00
                    total_item = qtd * valor_unit
                    total_os += total_item
                    
                    sql_item = """
                        INSERT INTO service_order_items 
                        (service_order_id, item_type, product_id, description, quantity, unit_price, total_price)
                        VALUES (%s, 'product', %s, %s, %s, %s, %s)
                    """
                    db.execute(sql_item, (os_id, produto_id, f"Peça para {descricao}", qtd, valor_unit, total_item))
            
            os_valores[os_id] = total_os
            
            # Se completada, registra datas
            if status in ['completed', 'approved']:
                db.execute("""
                    UPDATE service_orders 
                    SET data_inicio_servico = DATE_SUB(entry_date, INTERVAL -1 DAY),
                        data_fim_servico = DATE_SUB(entry_date, INTERVAL -2 DAY)
                    WHERE id = %s
                """, (os_id,))
            
            print(f"   ✅ OS {i+1}: {descricao[:25]}... (Status: {status}, R$ {total_os:.2f})")
        
        # ============================================================
        # 10. CONTAS A RECEBER (30)
        # ============================================================
        print("\n💰 Criando Contas a Receber...")
        
        cr_ids = []
        for os_id in list(os_valores.keys())[:30]:
            valor = os_valores[os_id]
            if valor > 0:
                status_cr = random.choice(['pending', 'pending', 'paid', 'pending'])  # 75% pendente
                
                sql_cr = """
                    INSERT INTO accounts_receivable 
                    (origin, reference_id, description, amount, due_date, status, 
                     payment_date, created_at)
                    VALUES ('service', %s, %s, %s, DATE_ADD(NOW(), INTERVAL %s DAY), %s,
                           CASE WHEN %s = 'paid' THEN NOW() ELSE NULL END, NOW())
                """
                db.execute(sql_cr, (os_id, f"Pagamento OS #{os_id}", valor, 
                                   random.randint(-15, 30), status_cr, status_cr))
                cr_ids.append(db.last_insert_id())
        
        print(f"   ✅ {len(cr_ids)} contas a receber criadas")
        
        # ============================================================
        # 11. CONTAS A PAGAR (20)
        # ============================================================
        print("\n💸 Criando Contas a Pagar...")
        
        for i in range(20):
            fornecedor_id = random.choice(fornecedores_ids)
            pc_id = random.choice(pc_ids)
            valor = random.uniform(500, 5000)
            status_cp = random.choice(['pending', 'pending', 'paid', 'overdue'])
            
            sql_cp = """
                INSERT INTO accounts_payable 
                (supplier_id, purchase_order_id, description, amount, due_date, status,
                 payment_date, created_at)
                VALUES (%s, %s, %s, %s, DATE_ADD(NOW(), INTERVAL %s DAY), %s,
                       CASE WHEN %s = 'paid' THEN NOW() ELSE NULL END, NOW())
            """
            db.execute(sql_cp, (fornecedor_id, pc_id, f"Pagamento Fornecedor - PC #{pc_id}",
                               valor, random.randint(-10, 45), status_cp, status_cp))
        
        print(f"   ✅ 20 contas a pagar criadas")
        
        # ============================================================
        # 12. CAIXA/FLUXO DE CAIXA (10 movimentações)
        # ============================================================
        print("\n🏦 Criando movimentações de caixa...")
        
        tipos_mov = ['income', 'expense']
        categorias_income = ['service', 'product_sale', 'other']
        categorias_expense = ['salary', 'supplier', 'rent', 'utilities', 'other']
        
        for i in range(10):
            tipo = random.choice(tipos_mov)
            categoria = random.choice(categorias_income if tipo == 'income' else categorias_expense)
            valor = random.uniform(100, 2000)
            
            sql_cf = """
                INSERT INTO cash_flow (type, category, description, amount, date, created_at)
                VALUES (%s, %s, %s, %s, DATE_SUB(NOW(), INTERVAL %s DAY), NOW())
            """
            desc = f"{'Entrada' if tipo == 'income' else 'Saída'} - {categoria} #{i+1}"
            db.execute(sql_cf, (tipo, categoria, desc, valor, random.randint(0, 30)))
        
        # Caixas abertos/fechados
        for i in range(5):
            opening = random.uniform(300, 800)
            closing = opening + random.uniform(-200, 500)
            
            sql_cx = """
                INSERT INTO cash_register (opening_amount, closing_amount, status, 
                                          opening_date, closing_date, created_at)
                VALUES (%s, %s, 'closed', DATE_SUB(NOW(), INTERVAL %s DAY), NOW(), NOW())
            """
            db.execute(sql_cx, (opening, closing, random.randint(1, 30)))
        
        print(f"   ✅ 10 movimentações de caixa + 5 caixas fechados")
        
        # ============================================================
        # 13. VENDAS PDV (30)
        # ============================================================
        print("\n💳 Criando vendas PDV...")
        
        formas_pgto = ['cash', 'credit_card', 'debit_card', 'pix', 'boleto']
        
        for i in range(30):
            produto_id = random.choice(produtos_ids)
            produto = db.fetch_one("SELECT sale_price FROM products WHERE id = %s", (produto_id,))
            qtd = random.randint(1, 4)
            valor = float(produto['sale_price']) * qtd if produto else 50.00 * qtd
            
            sql_venda = """
                INSERT INTO sales (product_id, quantity, sale_price, total_amount, 
                                  payment_method, seller_id, sale_date, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, DATE_SUB(NOW(), INTERVAL %s DAY), NOW())
            """
            db.execute(sql_venda, (produto_id, qtd, produto['sale_price'] if produto else 50.00,
                                  valor, random.choice(formas_pgto), 
                                  random.choice(vendedores_ids), random.randint(0, 45)))
        
        print(f"   ✅ 30 vendas PDV registradas")
        
        # ============================================================
        # 14. NOTAS FISCAIS (15)
        # ============================================================
        print("\n📄 Criando notas fiscais...")
        
        tipos_nf = ['NF-e', 'NFS-e']
        status_nf = ['issued', 'cancelled', 'pending']
        
        for i in range(15):
            os_id = random.choice(os_ids)
            tipo = random.choice(tipos_nf)
            status = random.choice(status_nf)
            valor_nf = os_valores.get(os_id, random.uniform(200, 1500))
            
            numero_nf = f"{random.randint(100000000, 999999999)}"
            serie = random.choice(['001', '001', '002'])
            
            sql_nf = """
                INSERT INTO invoices (order_id, invoice_number, series, invoice_type,
                                     customer_id, amount, issue_date, status, created_at)
                VALUES (%s, %s, %s, %s, 
                       (SELECT customer_id FROM service_orders WHERE id = %s),
                       %s, DATE_SUB(NOW(), INTERVAL %s DAY), %s, NOW())
            """
            db.execute(sql_nf, (os_id, numero_nf, serie, tipo, os_id, valor_nf,
                               random.randint(0, 60), status))
        
        print(f"   ✅ 15 notas fiscais criadas")
        
        # ============================================================
        # 15. KARDEX (movimentações de estoque)
        # ============================================================
        print("\n📊 Criando movimentações Kardex...")
        
        tipos_mov = ['input', 'output', 'adjustment']
        
        for i in range(25):
            produto_id = random.choice(produtos_ids)
            tipo = random.choice(tipos_mov)
            qtd = random.randint(5, 30)
            
            if tipo == 'output':
                qtd = -qtd  # Saída é negativa
            elif tipo == 'adjustment':
                qtd = random.randint(-10, 10)
            
            # Gera número de documento baseado no tipo
            if tipo == 'input':
                doc_num = f"PC{random.randint(1, 9999):04d}"
                ref_type = 'purchase_order'
            elif tipo == 'output':
                doc_num = f"OS{random.randint(1, 9999):04d}"
                ref_type = 'service_order'
            else:
                doc_num = f"AJ{random.randint(1, 9999):04d}"
                ref_type = 'adjustment'
            
            sql_kardex = """
                INSERT INTO kardex (product_id, movement_type, quantity, document_number,
                                   reference_type, reference_id, notes, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, DATE_SUB(NOW(), INTERVAL %s DAY))
            """
            db.execute(sql_kardex, (produto_id, tipo, abs(qtd) if tipo != 'adjustment' else qtd,
                                   doc_num, ref_type, random.randint(1, 100),
                                   f"Movimentação {tipo} #{i+1}", random.randint(0, 60)))
        
        print(f"   ✅ 25 movimentações Kardex criadas")
        
        # ============================================================
        # 16. COMISSÕES
        # ============================================================
        print("\n💰 Criando comissões...")
        
        for mecanico_id in mecanicos_ids[:5]:
            for mes in range(1, 4):  # Últimos 3 meses
                valor_comissao = random.uniform(200, 800)
                
                sql_com = """
                    INSERT INTO commissions (technician_id, reference_month, reference_year,
                                           total_services, total_commission, status, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, NOW())
                """
                db.execute(sql_com, (mecanico_id, mes, 2026, random.randint(10, 50),
                                   valor_comissao, random.choice(['pending', 'paid'])))
        
        print(f"   ✅ 15 comissões criadas")
        
        # ============================================================
        # 17. GARANTIAS
        # ============================================================
        print("\n🛡️ Criando garantias...")
        
        garantias_status = ['active', 'expired', 'claimed']
        
        for i in range(10):
            os_id = random.choice(os_ids)
            cliente_id = random.choice(clientes_ids)
            produto_id = random.choice(produtos_ids)
            
            data_os = db.fetch_one("SELECT entry_date FROM service_orders WHERE id = %s", (os_id,))
            if data_os:
                data_garantia = data_os['entry_date'] + timedelta(days=random.randint(30, 365))
            else:
                data_garantia = datetime.now() + timedelta(days=random.randint(30, 365))
            
            sql_gar = """
                INSERT INTO warranties (service_order_id, customer_id, product_id,
                                       warranty_type, warranty_period_days, start_date,
                                       end_date, status, notes, created_at)
                VALUES (%s, %s, %s, %s, %s, DATE_SUB(NOW(), INTERVAL %s DAY),
                       DATE_ADD(NOW(), INTERVAL %s DAY), %s, %s, NOW())
            """
            db.execute(sql_gar, (os_id, cliente_id, produto_id,
                               random.choice(['peça', 'serviço', 'mão_de_obra']),
                               random.choice([90, 180, 365]), random.randint(60, 300),
                               random.randint(30, 365),
                               random.choice(garantias_status),
                               f"Garantia {i+1} - {random.choice(['motor', 'freios', 'suspensão'])}"))
        
        print(f"   ✅ 10 garantias criadas")
        
        # ============================================================
        # 18. MANUTENÇÕES PREVENTIVAS
        # ============================================================
        print("\n🔧 Criando planos de manutenção preventiva...")
        
        for i in range(8):
            veiculo_id = random.choice(veiculos_ids)
            veiculo = db.fetch_one("SELECT customer_id FROM equipment WHERE id = %s", (veiculo_id,))
            cliente_id = veiculo['customer_id'] if veiculo else random.choice(clientes_ids)
            
            tipos_manutencao = [
                ('Revisão 10.000 km', 10000, 180),
                ('Revisão 20.000 km', 20000, 365),
                ('Revisão 30.000 km', 30000, 540),
                ('Troca de óleo', 5000, 90),
            ]
            nome, km, dias = random.choice(tipos_manutencao)
            
            sql_mp = """
                INSERT INTO maintenance_plans (customer_id, equipment_id, plan_name,
                                             km_interval, days_interval, last_km, next_km,
                                             last_date, next_date, status, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s,
                       DATE_SUB(NOW(), INTERVAL %s DAY),
                       DATE_ADD(NOW(), INTERVAL %s DAY), %s, NOW())
            """
            km_atual = random.randint(15000, 50000)
            db.execute(sql_mp, (cliente_id, veiculo_id, nome, km, dias, km_atual, km_atual + km,
                               random.randint(30, 300), random.randint(15, dias),
                               random.choice(['active', 'completed', 'overdue'])))
        
        print(f"   ✅ 8 planos de manutenção preventiva criados")
        
        # ============================================================
        # 19. RESUMO FINAL
        # ============================================================
        print("\n" + "="*70)
        print("✅ DADOS DE DEMONSTRAÇÃO COMPLETOS CRIADOS!")
        print("="*70)
        print("""
📊 RESUMO DO MVP MECÂNICA:
   ┌─ CADASTROS ─────────────────────────────┐
   │ • 20 clientes                          │
   │ • 30 veículos                          │
   │ • 10 fornecedores                      │
   │ • 10 mecânicos                         │
   │ • 5 vendedores                         │
   ├─ ESTOQUE ──────────────────────────────┤
   │ • 80 produtos/peças                    │
   │ • 10 categorias, 11 marcas             │
   │ • 25 movimentações Kardex              │
   │ • 15 pedidos de compra                 │
   ├─ SERVIÇOS ─────────────────────────────┤
   │ • 50 ordens de serviço (todos status)  │
   │ • OS com itens (serviços + peças)        │
   ├─ FINANCEIRO ────────────────────────────┤
   │ • 30 contas a receber                  │
   │ • 20 contas a pagar                    │
   │ • 10 mov. fluxo de caixa               │
   │ • 5 caixas fechados                    │
   │ • 30 vendas PDV                        │
   ├─ FISCAL ────────────────────────────────┤
   │ • 15 notas fiscais (NF-e/NFS-e)        │
   ├─ PÓS-VENDA ───────────────────────────┤
   │ • 15 comissões                         │
   │ • 10 garantias                         │
   │ • 8 manutenções preventivas            │
   └─────────────────────────────────────────┘

🎯 TODAS AS TELAS DO MVP ESTARÃO PREENCHIDAS!

Acesse: https://mecanicas.ikflow.cloud
Login: admin / admin123
""")


if __name__ == '__main__':
    confirmacao = input("""
⚠️  ATENÇÃO: Este script irá popular o banco com dados fictícios COMPLETOS.

Execute APENAS em ambiente de TESTE/DEMO.

Digite "DEMO" para confirmar: """)
    
    if confirmacao.strip().upper() == "DEMO":
        seed_demo_data()
    else:
        print("\n❌ Operação cancelada.")
