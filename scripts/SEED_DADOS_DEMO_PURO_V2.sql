-- ============================================================
-- SEED_DADOS_DEMO_PURO_V2.sql
-- Script SQL puro para popular dados fictícios - VERSÃO CORRIGIDA
-- ============================================================

USE supply_chain_mecanica;

-- ============================================================
-- 1. CATEGORIAS DE PRODUTOS
-- ============================================================
INSERT INTO product_categories (name, active) VALUES
('Motor', 1), ('Transmissão', 1), ('Freios', 1), ('Suspensão', 1), 
('Elétrica', 1), ('Arrefecimento', 1), ('Filtros', 1), ('Óleos', 1),
('Pneus', 1), ('Acessórios', 1)
ON DUPLICATE KEY UPDATE name = VALUES(name);

-- ============================================================
-- 2. MARCAS
-- ============================================================
INSERT INTO product_brands (name, active) VALUES
('Original', 1), ('Bosch', 1), ('Fram', 1), ('NGK', 1), ('Acdelco', 1),
('Wega', 1), ('Maxxi', 1), ('Valeo', 1), ('SKF', 1), ('Dayco', 1), ('Gates', 1)
ON DUPLICATE KEY UPDATE name = VALUES(name);

-- ============================================================
-- 3. UNIDADES
-- ============================================================
INSERT INTO product_units (name, abbreviation) VALUES
('Unidade', 'UN'), ('Peça', 'PC'), ('Litro', 'LT'), ('Par', 'PR'), ('Metro', 'MT')
ON DUPLICATE KEY UPDATE name = VALUES(name);

-- ============================================================
-- 4. FORNECEDORES (ajustado para estrutura real)
-- ============================================================
INSERT INTO suppliers (name, cnpj, email, phone, address, city, state, razao_social, neighborhood, active, created_at) VALUES
('AutoPeças Nacional Ltda', '12345678000190', 'contato@autopecasnacional.com', '1130000001', 'Av. Industrial, 500', 'São Paulo', 'SP', 'AutoPeças Nacional Ltda', 'Centro', 1, NOW()),
('Distribuidora de Óleos SP', '23456789000101', 'vendas@oleossp.com', '1130000002', 'Rua do Óleo, 100', 'São Paulo', 'SP', 'Distribuidora de Óleos SP', 'Vila Olímpia', 1, NOW()),
('Bosch Automotive Brasil', '34567890000112', 'pedidos@bosch.com.br', '1130000003', 'Av. Bosch, 1000', 'São Paulo', 'SP', 'Bosch Automotive Brasil', 'Santo Amaro', 1, NOW()),
('Filtros & Cia', '45678901000123', 'comercial@filtros.com', '1130000004', 'Rua dos Filtros, 200', 'São Paulo', 'SP', 'Filtros & Cia', 'Ipiranga', 1, NOW()),
('Freios Master', '56789012000134', 'vendas@freiosmaster.com', '1130000005', 'Av. dos Freios, 300', 'São Paulo', 'SP', 'Freios Master', 'Mooca', 1, NOW()),
('Pneus Sul', '67890123000145', 'contato@pneussul.com', '1130000006', 'Rua dos Pneus, 400', 'São Paulo', 'SP', 'Pneus Sul', 'Sacomã', 1, NOW()),
('Acessórios Automotivos', '78901234000156', 'vendas@acessorios.com', '1130000007', 'Av. Acessórios, 150', 'São Paulo', 'SP', 'Acessórios Automotivos Ltda', 'Morumbi', 1, NOW()),
('Suspensão Pro', '89012345000167', 'pedidos@suspensaopro.com', '1130000008', 'Rua da Suspensão, 250', 'São Paulo', 'SP', 'Suspensão Pro', 'Barra Funda', 1, NOW()),
('Arrefecimento Plus', '90123456000178', 'comercial@arrefecimento.com', '1130000009', 'Av. Arrefecimento, 350', 'São Paulo', 'SP', 'Arrefecimento Plus', 'Butantã', 1, NOW()),
('Transmissão & Cia', '01234567000189', 'vendas@transmissao.com', '1130000010', 'Rua da Transmissão, 450', 'São Paulo', 'SP', 'Transmissão & Cia', 'Jabaquara', 1, NOW())
ON DUPLICATE KEY UPDATE name = VALUES(name);

-- ============================================================
-- 5. PRODUTOS (40 produtos)
-- ============================================================
INSERT INTO products (sku, name, category_id, brand_id, unit_id, cost_price, sale_price, stock_quantity, min_stock, supplier_id, active, created_at) VALUES
('OLFLTR001', 'Filtro de Óleo - Nacional', 7, 1, 1, 25.00, 55.00, 20, 5, 1, 1, NOW()),
('ARFLTR001', 'Filtro de Ar - Bosch', 7, 2, 1, 35.00, 75.00, 15, 5, 2, 1, NOW()),
('CBFLTR001', 'Filtro de Combustível - Fram', 7, 3, 1, 45.00, 95.00, 12, 3, 3, 1, NOW()),
('CBNFLTR001', 'Filtro de Cabine - Wega', 7, 6, 1, 40.00, 85.00, 18, 5, 4, 1, NOW()),
('FRPD001', 'Pastilha Freio Dianteira - Acdelco', 3, 5, 1, 80.00, 180.00, 25, 8, 5, 1, NOW()),
('FRPT001', 'Pastilha Freio Traseira - Valeo', 3, 8, 1, 70.00, 160.00, 20, 6, 5, 1, NOW()),
('FRDS001', 'Disco de Freio - Bosch', 3, 2, 1, 120.00, 280.00, 15, 5, 5, 1, NOW()),
('OLEO5W001', 'Óleo 5W30 - Castrol', 8, 1, 3, 28.00, 60.00, 50, 15, 2, 1, NOW()),
('OLEO10W001', 'Óleo 10W40 - Shell', 8, 1, 3, 26.00, 55.00, 45, 12, 2, 1, NOW()),
('VELA001', 'Vela de Ignição - NGK', 5, 4, 4, 22.00, 48.00, 30, 10, 3, 1, NOW()),
('BATERIA60', 'Bateria 60Ah - Moura', 5, 1, 1, 280.00, 450.00, 8, 3, 3, 1, NOW()),
('CORREIA001', 'Correia Dentada - Dayco', 1, 10, 1, 65.00, 140.00, 12, 4, 10, 1, NOW()),
('TENSOR001', 'Tensor Correia - Gates', 1, 11, 1, 85.00, 190.00, 10, 3, 10, 1, NOW()),
('BOMBADAGUA', 'Bomba D\'água - SKF', 6, 9, 1, 120.00, 280.00, 8, 3, 9, 1, NOW()),
('AMORTDIANT', 'Amortecedor Dianteiro - Monroe', 4, 1, 4, 180.00, 380.00, 12, 4, 8, 1, NOW()),
('AMORTTRAS', 'Amortecedor Traseiro - Cofap', 4, 1, 4, 150.00, 320.00, 10, 3, 8, 1, NOW()),
('ROLAMENTO', 'Rolamento de Roda - SKF', 2, 9, 1, 45.00, 95.00, 20, 6, 1, 1, NOW()),
('COXIM001', 'Coxim do Motor - Maxxi', 1, 7, 1, 65.00, 145.00, 15, 5, 1, 1, NOW()),
('TERMINAL', 'Terminal de Direção - TRW', 4, 1, 4, 55.00, 120.00, 18, 6, 8, 1, NOW()),
('BIELETA', 'Bieleta da Suspensão - Axios', 4, 1, 4, 35.00, 78.00, 22, 7, 8, 1, NOW()),
('PIVO', 'Pivô da Suspensão - Nakata', 4, 1, 1, 42.00, 95.00, 25, 8, 8, 1, NOW()),
('PALHADIANT', 'Palheta Dianteira - Bosch', 5, 2, 4, 35.00, 75.00, 30, 10, 6, 1, NOW()),
('PALHATRAS', 'Palheta Traseira - Valeo', 5, 8, 1, 25.00, 55.00, 20, 6, 6, 1, NOW()),
('LAMPADA001', 'Lâmpada Farol - Philips', 5, 1, 1, 18.00, 40.00, 40, 12, 3, 1, NOW()),
('LAMPADA002', 'Lâmpada Lanterna - Osram', 5, 1, 1, 12.00, 28.00, 35, 10, 3, 1, NOW()),
('LIMPADOR', 'Limpador de Para-brisa - Michelin', 5, 1, 4, 28.00, 65.00, 25, 8, 6, 1, NOW()),
('ADITIVO001', 'Aditivo Radiador - Prestone', 6, 1, 3, 18.00, 42.00, 30, 10, 9, 1, NOW()),
('FLUIDOFREIO', 'Fluido de Freio DOT4 - Bosch', 3, 2, 3, 15.00, 35.00, 35, 12, 5, 1, NOW()),
('GRAXA001', 'Graxa de Rolamento - Lubrax', 1, 1, 3, 22.00, 48.00, 20, 6, 1, 1, NOW()),
('SILICONE', 'Silicone de Junta - 3M', 1, 1, 3, 25.00, 58.00, 25, 8, 1, 1, NOW()),
('JUNTAMOTOR', 'Jogo de Juntas do Motor - Sabó', 1, 1, 1, 120.00, 280.00, 8, 3, 1, 1, NOW()),
('RETENTOR', 'Retentor de Motor - Corteco', 1, 1, 1, 18.00, 42.00, 30, 10, 1, 1, NOW()),
('FILTROARREF', 'Filtro do Ar Condicionado - Wega', 6, 6, 1, 32.00, 72.00, 22, 7, 4, 1, NOW()),
('COMPRESAR', 'Compressor do Ar - Denso', 6, 1, 1, 450.00, 950.00, 5, 2, 9, 1, NOW()),
('CONDENSADOR', 'Condensador do Ar - Valeo', 6, 8, 1, 280.00, 580.00, 6, 2, 9, 1, NOW()),
('FILTROOLEO', 'Refil Filtro Óleo - Mann', 7, 1, 1, 18.00, 42.00, 40, 12, 4, 1, NOW()),
('BOMBACOMB', 'Bomba Combustível - Delphi', 1, 1, 1, 165.00, 350.00, 10, 3, 3, 1, NOW()),
('SENSOROXIG', 'Sonda Lambda - Bosch', 5, 2, 1, 185.00, 380.00, 8, 3, 3, 1, NOW()),
('BOBINA', 'Bobina de Ignição - NGK', 5, 4, 1, 95.00, 210.00, 12, 4, 3, 1, NOW()),
('INJETOR', 'Bico Injetor - Bosch', 1, 2, 1, 220.00, 480.00, 6, 2, 3, 1, NOW())
ON DUPLICATE KEY UPDATE sku = VALUES(sku);

-- ============================================================
-- 6. CLIENTES (15)
-- ============================================================
INSERT INTO customers (name, email, phone, cpf_cnpj, address, city, state, zip, active, created_at) VALUES
('João Silva', 'joao.silva@demo.com', '11999990001', '123.456.789-01', 'Rua das Flores, 100', 'São Paulo', 'SP', '01001-000', 1, NOW()),
('Maria Santos', 'maria.santos@demo.com', '11999990002', '123.456.789-02', 'Av. Brasil, 200', 'São Paulo', 'SP', '02002-000', 1, NOW()),
('Pedro Costa', 'pedro.costa@demo.com', '11999990003', '123.456.789-03', 'Rua Boa Vista, 300', 'São Paulo', 'SP', '03003-000', 1, NOW()),
('Ana Oliveira', 'ana.oliveira@demo.com', '11999990004', '123.456.789-04', 'Av. Paulista, 1000', 'São Paulo', 'SP', '04004-000', 1, NOW()),
('Carlos Lima', 'carlos.lima@demo.com', '11999990005', '123.456.789-05', 'Rua XV de Novembro, 50', 'São Paulo', 'SP', '05005-000', 1, NOW()),
('Fernanda Souza', 'fernanda.souza@demo.com', '11999990006', '123.456.789-06', 'Av. Beira Mar, 200', 'São Paulo', 'SP', '06006-000', 1, NOW()),
('Lucas Mendes', 'lucas.mendes@demo.com', '11999990007', '123.456.789-07', 'Rua das Palmeiras, 88', 'São Paulo', 'SP', '07007-000', 1, NOW()),
('Juliana Rocha', 'juliana.rocha@demo.com', '11999990008', '123.456.789-08', 'Av. Ipiranga, 333', 'São Paulo', 'SP', '08008-000', 1, NOW()),
('Roberto Almeida', 'roberto.almeida@demo.com', '11999990009', '123.456.789-09', 'Rua dos Três Irmãos, 45', 'São Paulo', 'SP', '09009-000', 1, NOW()),
('Patrícia Ferreira', 'patricia.ferreira@demo.com', '11999990010', '123.456.789-10', 'Av. Presidente Vargas, 1200', 'São Paulo', 'SP', '10010-000', 1, NOW()),
('Marcelo Dias', 'marcelo.dias@demo.com', '11999990011', '123.456.789-11', 'Rua Augusta, 77', 'São Paulo', 'SP', '11011-000', 1, NOW()),
('Camila Barbosa', 'camila.barbosa@demo.com', '11999990012', '123.456.789-12', 'Av. Atlântica, 500', 'São Paulo', 'SP', '12012-000', 1, NOW()),
('Ricardo Nunes', 'ricardo.nunes@demo.com', '11999990013', '123.456.789-13', 'Rua Oscar Freire, 200', 'São Paulo', 'SP', '13013-000', 1, NOW()),
('Aline Martins', 'aline.martins@demo.com', '11999990014', '123.456.789-14', 'Av. Rebouças, 150', 'São Paulo', 'SP', '14014-000', 1, NOW()),
('Bruno Ribeiro', 'bruno.ribeiro@demo.com', '11999990015', '123.456.789-15', 'Rua da Consolação, 80', 'São Paulo', 'SP', '15015-000', 1, NOW())
ON DUPLICATE KEY UPDATE name = VALUES(name);

-- ============================================================
-- 7. VEÍCULOS (20)
-- ============================================================
INSERT INTO equipment (name, serial_number, brand, model, year, fuel_type, accumulated_hours, customer_id, active, created_at) VALUES
('Honda Civic 2020', 'ABC1234', 'Honda', 'Civic', 2020, 'flex', 35000, 1, 1, NOW()),
('Toyota Corolla 2019', 'ABC1235', 'Toyota', 'Corolla', 2019, 'flex', 42000, 2, 1, NOW()),
('VW Gol 2018', 'ABC1236', 'Volkswagen', 'Gol', 2018, 'flex', 55000, 3, 1, NOW()),
('Chevrolet Onix 2021', 'ABC1237', 'Chevrolet', 'Onix', 2021, 'flex', 28000, 4, 1, NOW()),
('Ford Ka 2017', 'ABC1238', 'Ford', 'Ka', 2017, 'flex', 62000, 5, 1, NOW()),
('Fiat Uno 2016', 'ABC1239', 'Fiat', 'Uno', 2016, 'flex', 78000, 6, 1, NOW()),
('Hyundai HB20 2020', 'ABC1240', 'Hyundai', 'HB20', 2020, 'flex', 33000, 7, 1, NOW()),
('Renault Sandero 2019', 'ABC1241', 'Renault', 'Sandero', 2019, 'flex', 45000, 8, 1, NOW()),
('Jeep Compass 2021', 'ABC1242', 'Jeep', 'Compass', 2021, 'flex', 25000, 9, 1, NOW()),
('Nissan Kicks 2020', 'ABC1243', 'Nissan', 'Kicks', 2020, 'flex', 38000, 10, 1, NOW()),
('Peugeot 208 2019', 'ABC1244', 'Peugeot', '208', 2019, 'flex', 41000, 11, 1, NOW()),
('Citroën C3 2018', 'ABC1245', 'Citroën', 'C3', 2018, 'flex', 52000, 12, 1, NOW()),
('Honda Fit 2017', 'ABC1246', 'Honda', 'Fit', 2017, 'flex', 58000, 13, 1, NOW()),
('Toyota Yaris 2020', 'ABC1247', 'Toyota', 'Yaris', 2020, 'flex', 32000, 14, 1, NOW()),
('VW Polo 2021', 'ABC1248', 'Volkswagen', 'Polo', 2021, 'flex', 22000, 15, 1, NOW()),
('Chevrolet Tracker 2020', 'ABC1249', 'Chevrolet', 'Tracker', 2020, 'flex', 30000, 1, 1, NOW()),
('Ford EcoSport 2019', 'ABC1250', 'Ford', 'EcoSport', 2019, 'flex', 48000, 2, 1, NOW()),
('Fiat Strada 2021', 'ABC1251', 'Fiat', 'Strada', 2021, 'flex', 20000, 3, 1, NOW()),
('Hyundai Creta 2020', 'ABC1252', 'Hyundai', 'Creta', 2020, 'flex', 36000, 4, 1, NOW()),
('Renault Duster 2018', 'ABC1253', 'Renault', 'Duster', 2018, 'flex', 65000, 5, 1, NOW())
ON DUPLICATE KEY UPDATE serial_number = VALUES(serial_number);

-- ============================================================
-- 8. MECÂNICOS/TÉCNICOS (8)
-- ============================================================
INSERT INTO technicians (name, email, phone, specialization, hourly_rate, active, created_at) VALUES
('João das Peças', 'joao.pecas@demo.com', '11988880001', 'motor_transmissao', 85.00, 1, NOW()),
('Pedro Elétrica', 'pedro.elec@demo.com', '11988880002', 'eletrica', 90.00, 1, NOW()),
('Carlos Funilaria', 'carlos.fun@demo.com', '11988880003', 'funilaria', 75.00, 1, NOW()),
('Marcos Arrefecimento', 'marcos.ar@demo.com', '11988880004', 'arrefecimento', 80.00, 1, NOW()),
('Ricardo Suspensão', 'ricardo.sus@demo.com', '11988880005', 'suspensao', 82.00, 1, NOW()),
('André Freios', 'andre.fre@demo.com', '11988880006', 'freios', 78.00, 1, NOW()),
('Bruno Injeção', 'bruno.inj@demo.com', '11988880007', 'injeção', 95.00, 1, NOW()),
('Fernando Geral', 'fernando.g@demo.com', '11988880008', 'revisao_geral', 70.00, 1, NOW())
ON DUPLICATE KEY UPDATE name = VALUES(name);

-- ============================================================
-- 9. VENDEDORES (5)
-- ============================================================
INSERT INTO sellers (name, email, phone, cpf, seller_type, commission_percent, active, created_at) VALUES
('Roberto Vendas', 'roberto.vendas@demo.com', '11977770001', '987.654.321-01', 'vendas_balcao', 3.0, 1, NOW()),
('Sandra Atendimento', 'sandra.atend@demo.com', '11977770002', '987.654.321-02', 'vendas_externas', 5.0, 1, NOW()),
('Thiago Peças', 'thiago.pecas@demo.com', '11977770003', '987.654.321-03', 'pecas_acessorios', 2.5, 1, NOW()),
('Patricia Pós-venda', 'patricia.pos@demo.com', '11977770004', '987.654.321-04', 'pos_venda', 4.0, 1, NOW()),
('Marcelo Frotas', 'marcelo.frotas@demo.com', '11977770005', '987.654.321-05', 'venda_empresas', 2.0, 1, NOW())
ON DUPLICATE KEY UPDATE name = VALUES(name);

-- ============================================================
-- 10. ROTAS DE VENDA
-- ============================================================
INSERT INTO sales_routes (code, name, description, active, created_at) VALUES
('R001', 'Zona Norte SP', 'Rota de vendas na zona norte', 1, NOW()),
('R002', 'Zona Sul SP', 'Rota de vendas na zona sul', 1, NOW()),
('R003', 'Zona Leste SP', 'Rota de vendas na zona leste', 1, NOW()),
('R004', 'Zona Oeste SP', 'Rota de vendas na zona oeste', 1, NOW()),
('R005', 'ABC Paulista', 'Rota no ABC Paulista', 1, NOW()),
('R006', 'Grande SP', 'Rota na Grande São Paulo', 1, NOW())
ON DUPLICATE KEY UPDATE name = VALUES(name);

-- ============================================================
-- 11. ORDENS DE SERVIÇO (25)
-- ============================================================
INSERT INTO service_orders (order_number, customer_id, equipment_id, technician_id, status, priority, description, problem_description, entry_date, estimated_completion, created_at) VALUES
('OS202500001', 1, 1, 1, 'open', 'medium', 'Troca de óleo e filtros', 'Cliente solicitou revisão preventiva', DATE_SUB(NOW(), INTERVAL 5 DAY), DATE_ADD(NOW(), INTERVAL 2 DAY), NOW()),
('OS202500002', 2, 2, 2, 'in_progress', 'high', 'Reparo sistema elétrico', 'Luz de bateria acesa no painel', DATE_SUB(NOW(), INTERVAL 3 DAY), DATE_ADD(NOW(), INTERVAL 1 DAY), NOW()),
('OS202500003', 3, 3, 3, 'completed', 'medium', 'Revisão preventiva 20.000km', 'Troca de óleo e verificação geral', DATE_SUB(NOW(), INTERVAL 10 DAY), DATE_SUB(NOW(), INTERVAL 7 DAY), NOW()),
('OS202500004', 4, 4, 4, 'approved', 'urgent', 'Reparo no freio', 'Barulho ao frear', DATE_SUB(NOW(), INTERVAL 2 DAY), DATE_ADD(NOW(), INTERVAL 1 DAY), NOW()),
('OS202500005', 5, 5, 5, 'open', 'low', 'Troca de pastilhas', 'Manutenção preventiva', DATE_SUB(NOW(), INTERVAL 1 DAY), DATE_ADD(NOW(), INTERVAL 3 DAY), NOW()),
('OS202500006', 6, 6, 6, 'in_progress', 'medium', 'Reparo na suspensão', 'Carro balançando muito', DATE_SUB(NOW(), INTERVAL 4 DAY), DATE_ADD(NOW(), INTERVAL 2 DAY), NOW()),
('OS202500007', 7, 7, 7, 'completed', 'medium', 'Limpeza de bicos', 'Consumo elevado de combustível', DATE_SUB(NOW(), INTERVAL 15 DAY), DATE_SUB(NOW(), INTERVAL 12 DAY), NOW()),
('OS202500008', 8, 8, 8, 'open', 'high', 'Troca de correia dentada', 'Preventiva recomendada', DATE_SUB(NOW(), INTERVAL 2 DAY), DATE_ADD(NOW(), INTERVAL 5 DAY), NOW()),
('OS202500009', 9, 9, 1, 'in_progress', 'medium', 'Revisão completa', 'Cliente viajando amanhã', DATE_SUB(NOW(), INTERVAL 1 DAY), DATE_ADD(NOW(), INTERVAL 1 DAY), NOW()),
('OS202500010', 10, 10, 2, 'completed', 'low', 'Troca de óleo', 'Manutenção periódica', DATE_SUB(NOW(), INTERVAL 20 DAY), DATE_SUB(NOW(), INTERVAL 18 DAY), NOW()),
('OS202500011', 11, 11, 3, 'approved', 'medium', 'Reparo ar condicionado', 'Não está gelando', DATE_SUB(NOW(), INTERVAL 3 DAY), DATE_ADD(NOW(), INTERVAL 2 DAY), NOW()),
('OS202500012', 12, 12, 4, 'open', 'urgent', 'Reparo na injeção', 'Falhando ao acelerar', DATE_SUB(NOW(), INTERVAL 1 DAY), DATE_ADD(NOW(), INTERVAL 1 DAY), NOW()),
('OS202500013', 13, 13, 5, 'in_progress', 'medium', 'Troca de amortecedores', 'Carro muito mole', DATE_SUB(NOW(), INTERVAL 6 DAY), DATE_ADD(NOW(), INTERVAL 3 DAY), NOW()),
('OS202500014', 14, 14, 6, 'completed', 'high', 'Reparo elétrico', 'Partida falhando', DATE_SUB(NOW(), INTERVAL 12 DAY), DATE_SUB(NOW(), INTERVAL 10 DAY), NOW()),
('OS202500015', 15, 15, 7, 'open', 'low', 'Alinhamento', 'Desgaste irregular pneus', DATE_SUB(NOW(), INTERVAL 3 DAY), DATE_ADD(NOW(), INTERVAL 4 DAY), NOW()),
('OS202500016', 1, 16, 8, 'in_progress', 'medium', 'Higienização ar', 'Cheiro ruim no ar', DATE_SUB(NOW(), INTERVAL 2 DAY), DATE_ADD(NOW(), INTERVAL 2 DAY), NOW()),
('OS202500017', 2, 17, 1, 'approved', 'medium', 'Revisão 30.000km', 'Manutenção preventiva', DATE_SUB(NOW(), INTERVAL 4 DAY), DATE_ADD(NOW(), INTERVAL 3 DAY), NOW()),
('OS202500018', 3, 18, 2, 'open', 'high', 'Troca de bateria', 'Não está segurando carga', DATE_SUB(NOW(), INTERVAL 1 DAY), DATE_ADD(NOW(), INTERVAL 1 DAY), NOW()),
('OS202500019', 4, 19, 3, 'completed', 'medium', 'Reparo câmbio', 'Travando marchas', DATE_SUB(NOW(), INTERVAL 25 DAY), DATE_SUB(NOW(), INTERVAL 20 DAY), NOW()),
('OS202500020', 5, 20, 4, 'in_progress', 'urgent', 'Vazamento de óleo', 'Mancha na garagem', DATE_SUB(NOW(), INTERVAL 1 DAY), DATE_ADD(NOW(), INTERVAL 1 DAY), NOW()),
('OS202500021', 6, 1, 5, 'open', 'medium', 'Troca velas', 'Consumo alto', DATE_SUB(NOW(), INTERVAL 4 DAY), DATE_ADD(NOW(), INTERVAL 2 DAY), NOW()),
('OS202500022', 7, 2, 6, 'approved', 'low', 'Revisão geral', 'Cliente viajando', DATE_SUB(NOW(), INTERVAL 5 DAY), DATE_ADD(NOW(), INTERVAL 5 DAY), NOW()),
('OS202500023', 8, 3, 7, 'completed', 'medium', 'Reparo freio traseiro', 'Barulho ao frear', DATE_SUB(NOW(), INTERVAL 8 DAY), DATE_SUB(NOW(), INTERVAL 5 DAY), NOW()),
('OS202500024', 9, 4, 8, 'open', 'high', 'Diagnóstico completo', 'Luzes no painel', DATE_SUB(NOW(), INTERVAL 2 DAY), DATE_ADD(NOW(), INTERVAL 3 DAY), NOW()),
('OS202500025', 10, 5, 1, 'in_progress', 'medium', 'Troca filtros', 'Revisão periódica', DATE_SUB(NOW(), INTERVAL 3 DAY), DATE_ADD(NOW(), INTERVAL 2 DAY), NOW())
ON DUPLICATE KEY UPDATE order_number = VALUES(order_number);

-- ============================================================
-- 12. ITENS DE SERVIÇO NAS OS
-- ============================================================
INSERT INTO service_order_items (service_order_id, item_type, description, quantity, unit_price, total_price, technician_id) VALUES
(1, 'service', 'Mão de obra - Troca de óleo', 1, 85.00, 85.00, 1),
(1, 'service', 'Filtro de óleo', 1, 55.00, 55.00, NULL),
(2, 'service', 'Diagnóstico elétrico', 2, 90.00, 180.00, 2),
(3, 'service', 'Revisão completa', 3, 85.00, 255.00, 3),
(4, 'service', 'Reparo freio', 2, 78.00, 156.00, 5),
(5, 'service', 'Pastilhas de freio', 1, 180.00, 180.00, NULL),
(6, 'service', 'Reparo suspensão', 4, 82.00, 328.00, 4),
(7, 'service', 'Limpeza bicos', 3, 95.00, 285.00, 7),
(8, 'service', 'Troca correia', 4, 70.00, 280.00, 8),
(9, 'service', 'Revisão viagem', 5, 85.00, 425.00, 1),
(10, 'service', 'Troca óleo', 1, 70.00, 70.00, 8),
(11, 'service', 'Reparo ar', 3, 80.00, 240.00, 3),
(12, 'service', 'Reparo injeção', 5, 95.00, 475.00, 7),
(13, 'service', 'Troca amortecedores', 4, 85.00, 340.00, 4),
(14, 'service', 'Reparo elétrico', 3, 90.00, 270.00, 2),
(15, 'service', 'Alinhamento', 2, 75.00, 150.00, 8),
(16, 'service', 'Higienização', 2, 70.00, 140.00, 8),
(17, 'service', 'Revisão 30k', 5, 85.00, 425.00, 1),
(18, 'service', 'Bateria 60Ah', 1, 450.00, 450.00, NULL),
(19, 'service', 'Reparo câmbio', 6, 85.00, 510.00, 3),
(20, 'service', 'Reparo vazamento', 4, 85.00, 340.00, 4),
(21, 'service', 'Velas de ignição', 4, 48.00, 192.00, NULL),
(22, 'service', 'Revisão geral', 4, 70.00, 280.00, 6),
(23, 'service', 'Reparo freio traseiro', 3, 78.00, 234.00, 5),
(24, 'service', 'Diagnóstico', 2, 95.00, 190.00, 7),
(25, 'service', 'Troca filtros', 2, 85.00, 170.00, 1);

-- ============================================================
-- 13. CONTAS A RECEBER (15)
-- ============================================================
INSERT INTO accounts_receivable (origin, reference_id, description, amount, due_date, status, created_at) VALUES
('service', 3, 'Pagamento OS #3', 255.00, DATE_ADD(NOW(), INTERVAL 5 DAY), 'pending', NOW()),
('service', 7, 'Pagamento OS #7', 285.00, DATE_ADD(NOW(), INTERVAL 3 DAY), 'pending', NOW()),
('service', 10, 'Pagamento OS #10', 70.00, DATE_ADD(NOW(), INTERVAL 10 DAY), 'paid', NOW()),
('service', 14, 'Pagamento OS #14', 270.00, DATE_ADD(NOW(), INTERVAL 2 DAY), 'pending', NOW()),
('service', 19, 'Pagamento OS #19', 510.00, DATE_ADD(NOW(), INTERVAL 8 DAY), 'pending', NOW()),
('service', 23, 'Pagamento OS #23', 234.00, DATE_ADD(NOW(), INTERVAL 12 DAY), 'pending', NOW()),
('service', 1, 'Pagamento OS #1', 140.00, DATE_ADD(NOW(), INTERVAL 2 DAY), 'pending', NOW()),
('service', 5, 'Pagamento OS #5', 180.00, DATE_ADD(NOW(), INTERVAL 7 DAY), 'pending', NOW()),
('service', 9, 'Pagamento OS #9', 425.00, DATE_ADD(NOW(), INTERVAL 1 DAY), 'pending', NOW()),
('service', 11, 'Pagamento OS #11', 240.00, DATE_ADD(NOW(), INTERVAL 4 DAY), 'paid', NOW()),
('service', 15, 'Pagamento OS #15', 150.00, DATE_ADD(NOW(), INTERVAL 15 DAY), 'pending', NOW()),
('service', 17, 'Pagamento OS #17', 425.00, DATE_ADD(NOW(), INTERVAL 6 DAY), 'pending', NOW()),
('service', 20, 'Pagamento OS #20', 340.00, DATE_ADD(NOW(), INTERVAL 1 DAY), 'pending', NOW()),
('service', 22, 'Pagamento OS #22', 280.00, DATE_ADD(NOW(), INTERVAL 8 DAY), 'pending', NOW()),
('service', 25, 'Pagamento OS #25', 170.00, DATE_ADD(NOW(), INTERVAL 5 DAY), 'pending', NOW());

-- ============================================================
-- 14. CONTAS A PAGAR (10)
-- ============================================================
INSERT INTO accounts_payable (supplier_id, description, amount, due_date, status, created_at) VALUES
(1, 'Pagamento Fornecedor AutoPeças', 1500.00, DATE_ADD(NOW(), INTERVAL 10 DAY), 'pending', NOW()),
(2, 'Pagamento Distribuidora Óleos', 2000.00, DATE_ADD(NOW(), INTERVAL 5 DAY), 'pending', NOW()),
(3, 'Pagamento Bosch', 3500.00, DATE_ADD(NOW(), INTERVAL 15 DAY), 'pending', NOW()),
(4, 'Pagamento Filtros & Cia', 800.00, DATE_ADD(NOW(), INTERVAL 8 DAY), 'pending', NOW()),
(5, 'Pagamento Freios Master', 1200.00, DATE_ADD(NOW(), INTERVAL 12 DAY), 'pending', NOW()),
(1, 'Aluguel do mês', 2500.00, DATE_ADD(NOW(), INTERVAL 5 DAY), 'pending', NOW()),
(2, 'Energia Elétrica', 800.00, DATE_ADD(NOW(), INTERVAL 3 DAY), 'paid', NOW()),
(3, 'Internet/Telefone', 350.00, DATE_ADD(NOW(), INTERVAL 7 DAY), 'pending', NOW()),
(4, 'Salários', 8500.00, DATE_ADD(NOW(), INTERVAL 1 DAY), 'pending', NOW()),
(5, 'Impostos', 1200.00, DATE_ADD(NOW(), INTERVAL 20 DAY), 'pending', NOW());

-- ============================================================
-- 15. VENDAS PDV (20)
-- ============================================================
INSERT INTO sales (customer_id, seller_id, sale_date, payment_method, status, gross_total, discount_total, net_total, created_at) VALUES
(1, 1, DATE_SUB(NOW(), INTERVAL 5 DAY), 'money', 'confirmed', 110.00, 0.00, 110.00, NOW()),
(2, 1, DATE_SUB(NOW(), INTERVAL 4 DAY), 'credit', 'confirmed', 180.00, 10.00, 170.00, NOW()),
(3, 2, DATE_SUB(NOW(), INTERVAL 3 DAY), 'debit', 'confirmed', 95.00, 0.00, 95.00, NOW()),
(4, 1, DATE_SUB(NOW(), INTERVAL 2 DAY), 'money', 'confirmed', 55.00, 0.00, 55.00, NOW()),
(5, 3, DATE_SUB(NOW(), INTERVAL 1 DAY), 'pix', 'confirmed', 280.00, 20.00, 260.00, NOW()),
(6, 1, DATE_SUB(NOW(), INTERVAL 6 DAY), 'credit', 'confirmed', 75.00, 0.00, 75.00, NOW()),
(7, 2, DATE_SUB(NOW(), INTERVAL 7 DAY), 'debit', 'confirmed', 120.00, 0.00, 120.00, NOW()),
(8, 1, DATE_SUB(NOW(), INTERVAL 8 DAY), 'pix', 'confirmed', 48.00, 0.00, 48.00, NOW()),
(9, 3, DATE_SUB(NOW(), INTERVAL 9 DAY), 'money', 'confirmed', 450.00, 0.00, 450.00, NOW()),
(10, 1, DATE_SUB(NOW(), INTERVAL 10 DAY), 'credit', 'confirmed', 140.00, 15.00, 125.00, NOW()),
(11, 2, DATE_SUB(NOW(), INTERVAL 11 DAY), 'debit', 'confirmed', 95.00, 0.00, 95.00, NOW()),
(12, 1, DATE_SUB(NOW(), INTERVAL 12 DAY), 'pix', 'confirmed', 60.00, 0.00, 60.00, NOW()),
(13, 3, DATE_SUB(NOW(), INTERVAL 13 DAY), 'money', 'confirmed', 280.00, 0.00, 280.00, NOW()),
(14, 1, DATE_SUB(NOW(), INTERVAL 14 DAY), 'credit', 'confirmed', 75.00, 5.00, 70.00, NOW()),
(15, 2, DATE_SUB(NOW(), INTERVAL 15 DAY), 'debit', 'confirmed', 55.00, 0.00, 55.00, NOW()),
(1, 1, DATE_SUB(NOW(), INTERVAL 16 DAY), 'pix', 'confirmed', 380.00, 30.00, 350.00, NOW()),
(2, 1, DATE_SUB(NOW(), INTERVAL 17 DAY), 'credit', 'confirmed', 95.00, 0.00, 95.00, NOW()),
(3, 3, DATE_SUB(NOW(), INTERVAL 18 DAY), 'money', 'confirmed', 140.00, 0.00, 140.00, NOW()),
(4, 2, DATE_SUB(NOW(), INTERVAL 19 DAY), 'debit', 'confirmed', 48.00, 0.00, 48.00, NOW()),
(5, 1, DATE_SUB(NOW(), INTERVAL 20 DAY), 'pix', 'confirmed', 450.00, 50.00, 400.00, NOW());

-- ============================================================
-- 16. KARDEX - Movimentações
-- ============================================================
INSERT INTO kardex (product_id, movement_type, quantity, unit_price, document_number, reference_type, reference_id, notes, created_at) VALUES
(1, 'input', 20, 25.00, 'NF001', 'purchase_order', 1, 'Entrada inicial', NOW()),
(2, 'input', 15, 35.00, 'NF002', 'purchase_order', 2, 'Entrada inicial', NOW()),
(3, 'input', 12, 45.00, 'NF003', 'purchase_order', 3, 'Entrada inicial', NOW()),
(5, 'output', 2, 180.00, 'OS1', 'service_order', 1, 'Saída para OS', DATE_SUB(NOW(), INTERVAL 5 DAY)),
(9, 'output', 4, 60.00, 'OS1', 'service_order', 1, 'Saída para OS', DATE_SUB(NOW(), INTERVAL 5 DAY)),
(10, 'output', 4, 48.00, 'OS21', 'service_order', 21, 'Saída para OS', DATE_SUB(NOW(), INTERVAL 4 DAY)),
(11, 'output', 1, 450.00, 'OS18', 'service_order', 18, 'Saída para OS', DATE_SUB(NOW(), INTERVAL 1 DAY)),
(1, 'output', 1, 55.00, 'OS1', 'service_order', 1, 'Saída para OS', DATE_SUB(NOW(), INTERVAL 5 DAY));

-- ============================================================
-- 17. PLANO DE CONTAS
-- ============================================================
INSERT INTO chart_of_accounts (code, name, account_type, nature, active, created_at) VALUES
('1.1.01', 'Caixa', 'asset', 'debit', 1, NOW()),
('1.1.02', 'Banco Conta Corrente', 'asset', 'debit', 1, NOW()),
('1.2.01', 'Clientes', 'asset', 'debit', 1, NOW()),
('1.2.02', 'Estoque', 'asset', 'debit', 1, NOW()),
('2.1.01', 'Fornecedores', 'liability', 'credit', 1, NOW()),
('2.1.02', 'Impostos a Pagar', 'liability', 'credit', 1, NOW()),
('3.1.01', 'Capital Social', 'equity', 'credit', 1, NOW()),
('4.1.01', 'Receita de Serviços', 'revenue', 'credit', 1, NOW()),
('4.1.02', 'Receita de Vendas', 'revenue', 'credit', 1, NOW()),
('5.1.01', 'Custo de Mercadorias', 'expense', 'debit', 1, NOW()),
('5.1.02', 'Custo de Serviços', 'expense', 'debit', 1, NOW()),
('5.2.01', 'Salários', 'expense', 'debit', 1, NOW()),
('5.2.02', 'Aluguel', 'expense', 'debit', 1, NOW()),
('5.2.03', 'Energia', 'expense', 'debit', 1, NOW()),
('5.2.04', 'Internet/Telefone', 'expense', 'debit', 1, NOW())
ON DUPLICATE KEY UPDATE name = VALUES(name);

-- ============================================================
-- 18. CAIXA
-- ============================================================
INSERT INTO cash_register (opening_amount, closing_amount, status, opening_date, closing_date, created_at) VALUES
(500.00, 1850.00, 'closed', DATE_SUB(NOW(), INTERVAL 30 DAY), DATE_SUB(NOW(), INTERVAL 30 DAY), NOW()),
(600.00, 2100.00, 'closed', DATE_SUB(NOW(), INTERVAL 25 DAY), DATE_SUB(NOW(), INTERVAL 25 DAY), NOW()),
(550.00, 1950.00, 'closed', DATE_SUB(NOW(), INTERVAL 20 DAY), DATE_SUB(NOW(), INTERVAL 20 DAY), NOW()),
(700.00, 2300.00, 'closed', DATE_SUB(NOW(), INTERVAL 15 DAY), DATE_SUB(NOW(), INTERVAL 15 DAY), NOW()),
(650.00, 2200.00, 'closed', DATE_SUB(NOW(), INTERVAL 10 DAY), DATE_SUB(NOW(), INTERVAL 10 DAY), NOW()),
(800.00, NULL, 'open', DATE_SUB(NOW(), INTERVAL 5 DAY), NULL, NOW());

-- ============================================================
-- 19. FLUXO DE CAIXA
-- ============================================================
INSERT INTO cash_flow (type, category, description, amount, date, created_at) VALUES
('income', 'service', 'Recebimento OS #10', 70.00, DATE_SUB(NOW(), INTERVAL 10 DAY), NOW()),
('income', 'service', 'Recebimento OS #11', 240.00, DATE_SUB(NOW(), INTERVAL 9 DAY), NOW()),
('income', 'product_sale', 'Venda PDV #1', 110.00, DATE_SUB(NOW(), INTERVAL 5 DAY), NOW()),
('income', 'product_sale', 'Venda PDV #2', 170.00, DATE_SUB(NOW(), INTERVAL 4 DAY), NOW()),
('expense', 'supplier', 'Pagamento Fornecedor', 1500.00, DATE_SUB(NOW(), INTERVAL 3 DAY), NOW()),
('expense', 'salary', 'Folha de Pagamento', 8500.00, DATE_SUB(NOW(), INTERVAL 1 DAY), NOW()),
('expense', 'rent', 'Aluguel', 2500.00, DATE_SUB(NOW(), INTERVAL 5 DAY), NOW()),
('expense', 'utilities', 'Energia', 800.00, DATE_SUB(NOW(), INTERVAL 3 DAY), NOW());

-- ============================================================
-- 20. COMISSÕES (8)
-- ============================================================
INSERT INTO commissions (technician_id, reference_month, reference_year, total_services, total_commission, status, created_at) VALUES
(1, 5, 2026, 15, 450.00, 'pending', NOW()),
(2, 5, 2026, 12, 380.00, 'paid', NOW()),
(3, 5, 2026, 18, 520.00, 'pending', NOW()),
(4, 5, 2026, 10, 290.00, 'pending', NOW()),
(5, 5, 2026, 14, 410.00, 'pending', NOW()),
(6, 5, 2026, 11, 330.00, 'paid', NOW()),
(7, 5, 2026, 16, 480.00, 'pending', NOW()),
(8, 5, 2026, 9, 250.00, 'pending', NOW());

-- ============================================================
-- 21. GARANTIAS (5)
-- ============================================================
INSERT INTO warranties (service_order_id, customer_id, product_id, warranty_type, warranty_period_days, start_date, end_date, status, notes, created_at) VALUES
(3, 3, NULL, 'serviço', 90, DATE_SUB(NOW(), INTERVAL 10 DAY), DATE_ADD(NOW(), INTERVAL 80 DAY), 'active', 'Garantia revisão 20k km', NOW()),
(7, 7, NULL, 'serviço', 90, DATE_SUB(NOW(), INTERVAL 15 DAY), DATE_ADD(NOW(), INTERVAL 75 DAY), 'active', 'Garantia limpeza bicos', NOW()),
(10, 10, NULL, 'serviço', 90, DATE_SUB(NOW(), INTERVAL 20 DAY), DATE_ADD(NOW(), INTERVAL 70 DAY), 'active', 'Garantia troca óleo', NOW()),
(14, 14, NULL, 'serviço', 90, DATE_SUB(NOW(), INTERVAL 12 DAY), DATE_ADD(NOW(), INTERVAL 78 DAY), 'active', 'Garantia reparo elétrico', NOW()),
(19, 19, NULL, 'serviço', 180, DATE_SUB(NOW(), INTERVAL 25 DAY), DATE_ADD(NOW(), INTERVAL 155 DAY), 'active', 'Garantia reparo câmbio', NOW());

-- ============================================================
-- 22. MANUTENÇÕES PREVENTIVAS (6)
-- ============================================================
INSERT INTO maintenance_plans (customer_id, equipment_id, plan_name, km_interval, days_interval, last_km, next_km, last_date, next_date, status, notes, created_at) VALUES
(1, 1, 'Revisão 10.000 km', 10000, 180, 35000, 45000, DATE_SUB(NOW(), INTERVAL 30 DAY), DATE_ADD(NOW(), INTERVAL 150 DAY), 'active', 'Revisão preventiva Honda Civic', NOW()),
(2, 2, 'Revisão 10.000 km', 10000, 180, 42000, 52000, DATE_SUB(NOW(), INTERVAL 45 DAY), DATE_ADD(NOW(), INTERVAL 135 DAY), 'active', 'Revisão preventiva Corolla', NOW()),
(3, 3, 'Revisão 10.000 km', 10000, 180, 55000, 65000, DATE_SUB(NOW(), INTERVAL 60 DAY), DATE_ADD(NOW(), INTERVAL 120 DAY), 'active', 'Revisão preventiva Gol', NOW()),
(4, 4, 'Revisão 10.000 km', 10000, 180, 28000, 38000, DATE_SUB(NOW(), INTERVAL 90 DAY), DATE_ADD(NOW(), INTERVAL 90 DAY), 'active', 'Revisão preventiva Onix', NOW()),
(5, 5, 'Troca de Óleo', 5000, 90, 62000, 67000, DATE_SUB(NOW(), INTERVAL 15 DAY), DATE_ADD(NOW(), INTERVAL 75 DAY), 'active', 'Troca óleo preventiva', NOW()),
(6, 6, 'Revisão 10.000 km', 10000, 180, 78000, 88000, DATE_SUB(NOW(), INTERVAL 120 DAY), DATE_ADD(NOW(), INTERVAL 60 DAY), 'overdue', 'Revisão atrasada', NOW());

-- ============================================================
-- 23. LEITURAS DE QUILOMETRAGEM (10)
-- ============================================================
INSERT INTO hour_meter_readings (equipment_id, reading_date, current_reading, previous_reading, difference, notes, created_at) VALUES
(1, DATE_SUB(NOW(), INTERVAL 30 DAY), 35000, 34000, 1000, 'Revisão periódica', NOW()),
(1, DATE_SUB(NOW(), INTERVAL 60 DAY), 34000, 33000, 1000, 'Leitura mensal', NOW()),
(2, DATE_SUB(NOW(), INTERVAL 45 DAY), 42000, 41000, 1000, 'Revisão periódica', NOW()),
(3, DATE_SUB(NOW(), INTERVAL 60 DAY), 55000, 54000, 1000, 'Leitura trimestral', NOW()),
(4, DATE_SUB(NOW(), INTERVAL 90 DAY), 28000, 27000, 1000, 'Revisão periódica', NOW()),
(5, DATE_SUB(NOW(), INTERVAL 15 DAY), 62000, 61500, 500, 'Troca óleo', NOW()),
(6, DATE_SUB(NOW(), INTERVAL 120 DAY), 78000, 77000, 1000, 'Revisão atrasada', NOW()),
(7, DATE_SUB(NOW(), INTERVAL 30 DAY), 33000, 32000, 1000, 'Leitura mensal', NOW()),
(8, DATE_SUB(NOW(), INTERVAL 40 DAY), 45000, 44000, 1000, 'Revisão periódica', NOW()),
(9, DATE_SUB(NOW(), INTERVAL 25 DAY), 25000, 24000, 1000, 'Revisão periódica', NOW());

-- ============================================================
-- 24. REGISTROS DE PONTO (15)
-- ============================================================
INSERT INTO time_entries (technician_id, entry_date, check_in, check_out, lunch_start, lunch_end, work_location, status, notes, created_at) VALUES
(1, DATE_SUB(NOW(), INTERVAL 1 DAY), '08:00', '18:00', '12:00', '13:00', 'Oficina Central', 'present', 'Dia normal', NOW()),
(2, DATE_SUB(NOW(), INTERVAL 1 DAY), '08:00', '18:00', '12:00', '13:00', 'Oficina Central', 'present', 'Dia normal', NOW()),
(3, DATE_SUB(NOW(), INTERVAL 1 DAY), '08:00', '17:30', '12:00', '13:00', 'Oficina Centro', 'present', 'Saída mais cedo', NOW()),
(4, DATE_SUB(NOW(), INTERVAL 1 DAY), '08:30', '18:00', '12:00', '13:00', 'Oficina Central', 'late', 'Atraso 30min', NOW()),
(5, DATE_SUB(NOW(), INTERVAL 1 DAY), '08:00', '18:00', '12:00', '13:00', 'Oficina Centro', 'present', 'Dia normal', NOW()),
(1, DATE_SUB(NOW(), INTERVAL 2 DAY), '08:00', '18:00', '12:00', '13:00', 'Oficina Central', 'present', 'Dia normal', NOW()),
(2, DATE_SUB(NOW(), INTERVAL 2 DAY), '08:00', '18:00', '12:00', '13:00', 'Oficina Central', 'present', 'Dia normal', NOW()),
(6, DATE_SUB(NOW(), INTERVAL 2 DAY), '08:00', '18:00', '12:00', '13:00', 'Oficina Centro', 'present', 'Dia normal', NOW()),
(7, DATE_SUB(NOW(), INTERVAL 2 DAY), '08:00', '18:00', '12:00', '13:00', 'Oficina Central', 'present', 'Dia normal', NOW()),
(8, DATE_SUB(NOW(), INTERVAL 2 DAY), '08:00', '18:00', '12:00', '13:00', 'Oficina Centro', 'present', 'Dia normal', NOW()),
(1, DATE_SUB(NOW(), INTERVAL 3 DAY), '08:00', '18:00', '12:00', '13:00', 'Oficina Central', 'present', 'Dia normal', NOW()),
(3, DATE_SUB(NOW(), INTERVAL 3 DAY), '00:00', '00:00', NULL, NULL, NULL, 'absent', 'Falta - atestado médico', NOW()),
(4, DATE_SUB(NOW(), INTERVAL 3 DAY), '08:00', '18:00', '12:00', '13:00', 'Oficina Centro', 'present', 'Dia normal', NOW()),
(5, DATE_SUB(NOW(), INTERVAL 3 DAY), '08:00', '18:00', '12:00', '13:00', 'Oficina Central', 'present', 'Dia normal', NOW()),
(6, DATE_SUB(NOW(), INTERVAL 3 DAY), '08:00', '16:00', '12:00', '13:00', 'Oficina Centro', 'early_leave', 'Saída mais cedo - compromisso', NOW());

-- ============================================================
-- 25. NOTAS FISCAIS (10)
-- ============================================================
INSERT INTO invoices (order_id, invoice_number, series, invoice_type, customer_id, amount, issue_date, status, notes, created_at) VALUES
(3, '35190610222758000152550010001234567812345678', '001', 'NF-e', 3, 255.00, DATE_SUB(NOW(), INTERVAL 10 DAY), 'issued', 'Nota fiscal OS #3', NOW()),
(7, '35190610222758000152550010001234567912345679', '001', 'NF-e', 7, 285.00, DATE_SUB(NOW(), INTERVAL 15 DAY), 'issued', 'Nota fiscal OS #7', NOW()),
(10, '35190610222758000152550010001234568012345680', '001', 'NF-e', 10, 70.00, DATE_SUB(NOW(), INTERVAL 20 DAY), 'issued', 'Nota fiscal OS #10', NOW()),
(14, '35190610222758000152550010001234568112345681', '001', 'NF-e', 14, 270.00, DATE_SUB(NOW(), INTERVAL 12 DAY), 'issued', 'Nota fiscal OS #14', NOW()),
(19, '35190610222758000152550010001234568212345682', '001', 'NF-e', 19, 510.00, DATE_SUB(NOW(), INTERVAL 25 DAY), 'issued', 'Nota fiscal OS #19', NOW()),
(1, 'S001', '001', 'NFS-e', 1, 140.00, DATE_SUB(NOW(), INTERVAL 5 DAY), 'issued', 'Nota serviço OS #1', NOW()),
(5, 'S002', '001', 'NFS-e', 5, 180.00, DATE_SUB(NOW(), INTERVAL 1 DAY), 'issued', 'Nota serviço OS #5', NOW()),
(9, 'S003', '001', 'NFS-e', 9, 425.00, DATE_SUB(NOW(), INTERVAL 1 DAY), 'issued', 'Nota serviço OS #9', NOW()),
(11, 'S004', '001', 'NFS-e', 11, 240.00, DATE_SUB(NOW(), INTERVAL 3 DAY), 'issued', 'Nota serviço OS #11', NOW()),
(15, 'S005', '001', 'NFS-e', 15, 150.00, DATE_SUB(NOW(), INTERVAL 3 DAY), 'issued', 'Nota serviço OS #15', NOW());

-- ============================================================
-- RESUMO
-- ============================================================
SELECT 'SEED V2 COMPLETO EXECUTADO!' AS RESULTADO;
SELECT CONCAT(
    'Dados criados: ',
    (SELECT COUNT(*) FROM customers), ' clientes, ',
    (SELECT COUNT(*) FROM equipment), ' veículos, ',
    (SELECT COUNT(*) FROM products), ' produtos, ',
    (SELECT COUNT(*) FROM service_orders), ' OS, ',
    (SELECT COUNT(*) FROM accounts_receivable), ' C/R, ',
    (SELECT COUNT(*) FROM accounts_payable), ' C/P, ',
    (SELECT COUNT(*) FROM sales), ' vendas, ',
    (SELECT COUNT(*) FROM warranties), ' garantias, ',
    (SELECT COUNT(*) FROM maintenance_plans), ' manutenções, ',
    (SELECT COUNT(*) FROM commissions), ' comissões, ',
    (SELECT COUNT(*) FROM time_entries), ' registros de ponto, ',
    (SELECT COUNT(*) FROM hour_meter_readings), ' leituras km'
) AS RESUMO;
