#!/usr/bin/env python3
"""
seed_dados_demo.py — Popula o banco com dados fictícios para demonstração.

Executar:
    cd C:\\Users\\aritana\\CascadeProjects\\IKFlow-Mecanica
    py scripts\\seed_dados_demo.py

Cria:
    - 15 clientes fictícios
    - 25 veículos vinculados
    - 8 mecânicos/técnicos
    - 60 peças em estoque
    - 40 ordens de serviço (em vários status)
    - Movimentações financeiras
    - Vendas PDV
    
AVISO: Execute apenas em banco de TESTE/DEMO. Não use em produção.
"""
import sys
import os
import random
from datetime import datetime, timedelta, date
from decimal import Decimal

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

from main_mysql import app, get_db


def generate_cpf():
    """Gera CPF fictício válido."""
    n = [random.randint(0, 9) for _ in range(9)]
    # Calcula dígitos verificadores (simplificado)
    d1 = sum((i+1) * v for i, v in enumerate(n)) % 11
    d1 = 0 if d1 < 2 else 11 - d1
    d2 = sum(i * v for i, v in enumerate(n[1:] + [d1])) % 11
    d2 = 0 if d2 < 2 else 11 - d2
    return f"{n[0]}{n[1]}{n[2]}.{n[3]}{n[4]}{n[5]}.{n[6]}{n[7]}{n[8]}-{d1}{d2}"


def seed_demo_data():
    """Função principal de seeding."""
    
    print("="*60)
    print("🚀 SEED DE DADOS PARA DEMONSTRAÇÃO")
    print("="*60)
    
    with app.app_context():
        db = get_db()
        
        # ============================================================
        # 1. CLIENTES (15)
        # ============================================================
        print("\n📋 Criando 15 clientes fictícios...")
        
        nomes_clientes = [
            ("João Silva", "Rua das Flores, 123", "São Paulo", "SP"),
            ("Maria Santos", "Av. Brasil, 456", "Rio de Janeiro", "RJ"),
            ("Pedro Costa", "Rua Boa Vista, 789", "Belo Horizonte", "MG"),
            ("Ana Oliveira", "Av. Paulista, 1000", "São Paulo", "SP"),
            ("Carlos Lima", "Rua XV de Novembro, 50", "Curitiba", "PR"),
            ("Fernanda Souza", "Av. Beira Mar, 200", "Fortaleza", "CE"),
            ("Lucas Mendes", "Rua das Palmeiras, 88", "Salvador", "BA"),
            ("Juliana Rocha", "Av. Ipiranga, 333", "São Paulo", "SP"),
            ("Roberto Almeida", "Rua dos Três Irmãos, 45", "Recife", "PE"),
            ("Patrícia Ferreira", "Av. Presidente Vargas, 1200", "Rio de Janeiro", "RJ"),
            ("Marcelo Dias", "Rua Augusta, 77", "São Paulo", "SP"),
            ("Camila Barbosa", "Av. Atlântica, 500", "Salvador", "BA"),
            ("Ricardo Nunes", "Rua Oscar Freire, 200", "São Paulo", "SP"),
            ("Aline Martins", "Av. Rebouças, 150", "São Paulo", "SP"),
            ("Bruno Ribeiro", "Rua da Consolação, 80", "São Paulo", "SP"),
        ]
        
        clientes_ids = []
        for i, (nome, endereco, cidade, uf) in enumerate(nomes_clientes, 1):
            email = f"cliente{i}@demo.ikflow.com"
            telefone = f"119{random.randint(1000, 9999)}{random.randint(1000, 9999)}"
            cpf = generate_cpf()
            
            # Verifica se já existe
            exists = db.fetch_one("SELECT id FROM customers WHERE email = %s", (email,))
            if exists:
                clientes_ids.append(exists['id'])
                continue
            
            sql = """
                INSERT INTO customers (name, email, phone, cpf_cnpj, address, city, state, 
                                     active, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 1, NOW(), NOW())
            """
            db.execute(sql, (nome, email, telefone, cpf, endereco, cidade, uf))
            customer_id = db.last_insert_id()
            clientes_ids.append(customer_id)
            print(f"   ✅ Cliente {i}: {nome} (ID: {customer_id})")
        
        # ============================================================
        # 2. VEÍCULOS (25) — vinculados aos clientes
        # ============================================================
        print("\n🚗 Criando 25 veículos...")
        
        veiculos_data = [
            ("Honda Civic", "2020", "flex", 35000),
            ("Toyota Corolla", "2019", "flex", 42000),
            ("Volkswagen Gol", "2018", "flex", 55000),
            ("Chevrolet Onix", "2021", "flex", 28000),
            ("Ford Ka", "2017", "flex", 62000),
            ("Fiat Uno", "2016", "flex", 78000),
            ("Hyundai HB20", "2020", "flex", 33000),
            ("Renault Sandero", "2019", "flex", 45000),
            ("Jeep Compass", "2021", "flex", 25000),
            ("Nissan Kicks", "2020", "flex", 38000),
            ("Peugeot 208", "2019", "flex", 41000),
            ("Citroën C3", "2018", "flex", 52000),
            ("Honda Fit", "2017", "flex", 58000),
            ("Toyota Yaris", "2020", "flex", 32000),
            ("Volkswagen Polo", "2021", "flex", 22000),
            ("Chevrolet Tracker", "2020", "flex", 30000),
            ("Ford EcoSport", "2019", "flex", 48000),
            ("Fiat Strada", "2021", "flex", 20000),
            ("Hyundai Creta", "2020", "flex", 36000),
            ("Renault Duster", "2018", "flex", 65000),
            ("Jeep Renegade", "2019", "flex", 43000),
            ("Nissan Versa", "2017", "flex", 68000),
            ("Peugeot 2008", "2020", "flex", 31000),
            ("Citroën C4", "2016", "flex", 75000),
            ("Honda HR-V", "2019", "flex", 39000),
        ]
        
        veiculos_ids = []
        for i, (modelo, ano, combustivel, km) in enumerate(veiculos_data, 1):
            placa = f"ABC{i:04d}"
            cliente_id = random.choice(clientes_ids)
            
            exists = db.fetch_one("SELECT id FROM equipment WHERE serial_number = %s", (placa,))
            if exists:
                veiculos_ids.append(exists['id'])
                continue
            
            sql = """
                INSERT INTO equipment (name, serial_number, model, year, fuel_type, 
                                     accumulated_hours, customer_id, active, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 1, NOW())
            """
            db.execute(sql, (f"{modelo} {ano}", placa, modelo, ano, combustivel, km, cliente_id))
            veiculo_id = db.last_insert_id()
            veiculos_ids.append(veiculo_id)
            print(f"   ✅ Veículo {i}: {modelo} {ano} - Placa {placa} (Cliente: {cliente_id})")
        
        # ============================================================
        # 3. MECÂNICOS/TÉCNICOS (8)
        # ============================================================
        print("\n🔧 Criando 8 mecânicos/técnicos...")
        
        mecanicos_data = [
            ("João Mecânico", "joao.mec@demo.ikflow.com", "motor_transmissao", 85.00),
            ("Pedro Eletricista", "pedro.elec@demo.ikflow.com", "eletrica", 90.00),
            ("Carlos Funileiro", "carlos.fun@demo.ikflow.com", "funilaria", 75.00),
            ("Marcos Arrefecimento", "marcos.ar@demo.ikflow.com", "arrefecimento", 80.00),
            ("Ricardo Suspensão", "ricardo.sus@demo.ikflow.com", "suspensao", 82.00),
            ("André Freios", "andre.fre@demo.ikflow.com", "freios", 78.00),
            ("Bruno Injeção", "bruno.inj@demo.ikflow.com", "injeção", 95.00),
            ("Fernando Geral", "fernando.g@demo.ikflow.com", "revisao_geral", 70.00),
        ]
        
        mecanicos_ids = []
        for i, (nome, email, especialidade, valor_hora) in enumerate(mecanicos_data, 1):
            telefone = f"119{random.randint(1000, 9999)}{random.randint(1000, 9999)}"
            
            exists = db.fetch_one("SELECT id FROM technicians WHERE email = %s", (email,))
            if exists:
                mecanicos_ids.append(exists['id'])
                continue
            
            sql = """
                INSERT INTO technicians (name, email, phone, specialization, hourly_rate, active, created_at)
                VALUES (%s, %s, %s, %s, %s, 1, NOW())
            """
            db.execute(sql, (nome, email, telefone, especialidade, valor_hora))
            mecanico_id = db.last_insert_id()
            mecanicos_ids.append(mecanico_id)
            print(f"   ✅ Mecânico {i}: {nome} - R$ {valor_hora}/h")
        
        # ============================================================
        # 4. CATEGORIAS E MARCAS (se não existirem)
        # ============================================================
        print("\n📦 Verificando categorias e marcas...")
        
        # Categorias
        categorias = ["Motor", "Transmissão", "Freios", "Suspensão", "Elétrica", "Arrefecimento", "Filtros", "Óleos"]
        categorias_ids = []
        for cat in categorias:
            exists = db.fetch_one("SELECT id FROM product_categories WHERE name = %s", (cat,))
            if exists:
                categorias_ids.append(exists['id'])
            else:
                db.execute("INSERT INTO product_categories (name, active) VALUES (%s, 1)", (cat,))
                categorias_ids.append(db.last_insert_id())
        
        # Marcas
        marcas = ["Original", "Bosch", "Fram", "NGK", "Acdelco", "Wega", "Maxxi", "Valeo"]
        marcas_ids = []
        for marca in marcas:
            exists = db.fetch_one("SELECT id FROM product_brands WHERE name = %s", (marca,))
            if exists:
                marcas_ids.append(exists['id'])
            else:
                db.execute("INSERT INTO product_brands (name, active) VALUES (%s, 1)", (marca,))
                marcas_ids.append(db.last_insert_id())
        
        # Unidades
        exists_unit = db.fetch_one("SELECT id FROM product_units WHERE abbreviation = 'UN'")
        if exists_unit:
            unidade_id = exists_unit['id']
        else:
            db.execute("INSERT INTO product_units (name, abbreviation) VALUES ('Unidade', 'UN')")
            unidade_id = db.last_insert_id()
        
        print("   ✅ Estrutura de produtos pronta")
        
        # ============================================================
        # 5. PEÇAS EM ESTOQUE (60)
        # ============================================================
        print("\n🔩 Criando 60 peças em estoque...")
        
        pecas_base = [
            ("Filtro de Óleo", "OLFLTR", 25.00, 55.00),
            ("Filtro de Ar", "ARFLTR", 35.00, 75.00),
            ("Filtro de Combustível", "CBFLTR", 45.00, 95.00),
            ("Filtro de Cabine", "CBNFLTR", 40.00, 85.00),
            ("Pastilha de Freio Dianteira", "FREPADF", 80.00, 180.00),
            ("Pastilha de Freio Traseira", "FREPADT", 70.00, 160.00),
            ("Disco de Freio", "FREDSK", 120.00, 280.00),
            ("Óleo de Motor 5W30", "OLEO5W30", 28.00, 60.00),
            ("Óleo de Motor 10W40", "OLEO10W40", 26.00, 55.00),
            ("Óleo de Câmbio", "OLEOCAMB", 35.00, 75.00),
            ("Fluido de Freio DOT4", "FLDBDOT4", 15.00, 35.00),
            ("Aditivo para Radiador", "ADTRAD", 18.00, 40.00),
            ("Vela de Ignição", "VELAIGN", 22.00, 48.00),
            ("Cabos de Vela", "CBVELA", 45.00, 95.00),
            ("Bateria 60Ah", "BAT60AH", 280.00, 450.00),
            ("Bateria 45Ah", "BAT45AH", 220.00, 380.00),
            ("Correia Dentada", "CRRDTDA", 65.00, 140.00),
            ("Tensor da Correia", "TNSCRR", 85.00, 190.00),
            ("Bomba D'água", "BMPAGUA", 120.00, 280.00),
            ("Termostato", "TRMSTAT", 45.00, 95.00),
        ]
        
        pecas_ids = []
        for i in range(60):
            nome_base, cod_base, custo, venda = random.choice(pecas_base)
            sku = f"{cod_base}{i+1:03d}"
            nome = f"{nome_base} - {random.choice(['Nacional', 'Importado', 'Original'])}"
            qtd = random.randint(5, 50)
            min_stock = random.randint(3, 8)
            
            exists = db.fetch_one("SELECT id FROM products WHERE sku = %s", (sku,))
            if exists:
                pecas_ids.append(exists['id'])
                continue
            
            sql = """
                INSERT INTO products (sku, name, category_id, brand_id, unit_id,
                                   cost_price, sale_price, stock_quantity, min_stock,
                                   active, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 1, NOW())
            """
            db.execute(sql, (
                sku, nome, random.choice(categorias_ids), random.choice(marcas_ids),
                unidade_id, custo, venda, qtd, min_stock
            ))
            peca_id = db.last_insert_id()
            pecas_ids.append(peca_id)
        
        print(f"   ✅ {len(pecas_ids)} peças criadas")
        
        # ============================================================
        # 6. ORDENS DE SERVIÇO (40) — em vários status
        # ============================================================
        print("\n📋 Criando 40 Ordens de Serviço...")
        
        status_os = ['open', 'in_progress', 'completed', 'approved'] * 10
        random.shuffle(status_os)
        
        servicos_os = [
            "Troca de óleo e filtros",
            "Revisão preventiva 10.000 km",
            "Revisão preventiva 20.000 km",
            "Reparo no sistema de freios",
            "Troca de pastilhas e discos",
            "Reparo na suspensão",
            "Troca de amortecedores",
            "Reparo no sistema elétrico",
            "Troca de bateria",
            "Reparo no arrefecimento",
            "Troca de correia dentada",
            "Regulagem de motor",
            "Limpeza de bicos injetores",
            "Troca de velas e cabos",
            "Alinhamento e balanceamento",
            "Reparo no câmbio",
            "Troca de fluido de freio",
            "Higienização do ar-condicionado",
            "Troca de filtros de cabine",
            "Diagnóstico completo",
        ]
        
        os_ids = []
        for i in range(40):
            cliente_id = random.choice(clientes_ids)
            veiculo_id = random.choice(veiculos_ids)
            mecanico_id = random.choice(mecanicos_ids)
            status = status_os[i]
            
            # Datas
            dias_atras = random.randint(0, 90)
            data_os = datetime.now() - timedelta(days=dias_atras)
            
            # Descrição
            descricao = random.choice(servicos_os)
            problema = f"Cliente relatou: {random.choice(['barulho estranho', 'vazamento', 'falta de potência', 'luz acesa no painel', 'dificuldade para ligar'])}"
            
            sql = """
                INSERT INTO service_orders (
                    order_number, customer_id, equipment_id, technician_id,
                    status, priority, description, problem_description,
                    entry_date, estimated_completion, created_at, updated_at
                )
                SELECT 
                    CONCAT('OS', YEAR(NOW()), LPAD(COUNT(*)+1, 5, '0')),
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW()
                FROM service_orders
            """
            db.execute(sql, (
                cliente_id, veiculo_id, mecanico_id, status,
                random.choice(['low', 'medium', 'high', 'urgent']),
                descricao, problema, data_os, data_os + timedelta(days=3)
            ))
            os_id = db.last_insert_id()
            os_ids.append(os_id)
            
            # Adiciona itens à OS (serviço + peças)
            num_itens = random.randint(1, 4)
            for _ in range(num_itens):
                if random.choice([True, False]):
                    # Serviço
                    qtd = random.randint(1, 5)
                    valor_unit = random.choice([75.00, 85.00, 90.00, 120.00])
                    sql_item = """
                        INSERT INTO service_order_items 
                        (service_order_id, item_type, description, quantity, unit_price, total_price, technician_id)
                        VALUES (%s, 'service', %s, %s, %s, %s, %s)
                    """
                    db.execute(sql_item, (os_id, descricao, qtd, valor_unit, qtd * valor_unit, mecanico_id))
                else:
                    # Peça
                    peca_id = random.choice(pecas_ids)
                    qtd = random.randint(1, 3)
                    peca = db.fetch_one("SELECT sale_price FROM products WHERE id = %s", (peca_id,))
                    valor_unit = float(peca['sale_price']) if peca else 50.00
                    sql_item = """
                        INSERT INTO service_order_items 
                        (service_order_id, item_type, product_id, description, quantity, unit_price, total_price)
                        VALUES (%s, 'product', %s, %s, %s, %s, %s)
                    """
                    db.execute(sql_item, (os_id, peca_id, f"Peça para {descricao}", qtd, valor_unit, qtd * valor_unit))
            
            print(f"   ✅ OS {i+1}: {descricao[:30]}... (Status: {status})")
        
        # ============================================================
        # 7. CONTAS A RECEBER (relacionadas às OS)
        # ============================================================
        print("\n💰 Criando Contas a Receber...")
        
        for os_id in os_ids[:25]:  # 25 OS com C/R
            # Calcula total da OS
            total = db.fetch_one("""
                SELECT COALESCE(SUM(total_price), 0) as total 
                FROM service_order_items 
                WHERE service_order_id = %s
            """, (os_id,))
            valor = float(total['total'])
            
            if valor > 0:
                sql_cr = """
                    INSERT INTO accounts_receivable 
                    (origin, reference_id, description, amount, due_date, status, created_at)
                    VALUES ('service', %s, %s, %s, DATE_ADD(NOW(), INTERVAL %s DAY), 'pending', NOW())
                """
                db.execute(sql_cr, (os_id, f"Pagamento OS #{os_id}", valor, random.randint(1, 30)))
        
        print(f"   ✅ 25 contas a receber criadas")
        
        # ============================================================
        # 8. VENDAS PDV (20)
        # ============================================================
        print("\n💳 Criando vendas no PDV...")
        
        formas_pagamento = ['cash', 'credit_card', 'debit_card', 'pix']
        
        for i in range(20):
            peca_id = random.choice(pecas_ids)
            peca = db.fetch_one("SELECT sale_price, stock_quantity FROM products WHERE id = %s", (peca_id,))
            
            if peca and float(peca['stock_quantity']) > 0:
                qtd = random.randint(1, 3)
                valor = float(peca['sale_price']) * qtd
                
                sql_venda = """
                    INSERT INTO sales 
                    (product_id, quantity, sale_price, total_amount, payment_method, 
                     sale_date, created_at)
                    VALUES (%s, %s, %s, %s, %s, DATE_SUB(NOW(), INTERVAL %s DAY), NOW())
                """
                db.execute(sql_venda, (
                    peca_id, qtd, peca['sale_price'], valor,
                    random.choice(formas_pagamento),
                    random.randint(0, 30)
                ))
        
        print(f"   ✅ 20 vendas PDV registradas")
        
        # ============================================================
        # 9. RESUMO FINAL
        # ============================================================
        print("\n" + "="*60)
        print("✅ DADOS DE DEMONSTRAÇÃO CRIADOS COM SUCESSO!")
        print("="*60)
        print(f"""
📊 RESUMO:
   • {len(clientes_ids)} clientes
   • {len(veiculos_ids)} veículos
   • {len(mecanicos_ids)} mecânicos
   • {len(pecas_ids)} peças em estoque
   • {len(os_ids)} ordens de serviço
   • 25 contas a receber
   • 20 vendas PDV

🎯 SISTEMA PRONTO PARA APRESENTAÇÃO!

Acesse: http://127.0.0.1:8080 (local) ou https://mecanicas.ikflow.cloud
Login: admin / admin123
""")


if __name__ == '__main__':
    confirmacao = input("""
⚠️  ATENÇÃO: Este script irá popular o banco com dados fictícios.

Execute APENAS em ambiente de TESTE/DEMO.

Digite "DEMO" para confirmar: """)
    
    if confirmacao.strip().upper() == "DEMO":
        seed_demo_data()
    else:
        print("\n❌ Operação cancelada. Digite 'DEMO' para executar.")
