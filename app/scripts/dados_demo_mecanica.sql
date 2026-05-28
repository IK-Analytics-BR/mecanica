-- ============================================================
-- DADOS DEMO - IKFlow Mecânica
-- Execute: mysql -u root -p"Root@1234!" supply_chain_mecanica < dados_demo_mecanica.sql
-- ============================================================

USE supply_chain_mecanica;

-- ============================================================
-- CLIENTES
-- ============================================================
INSERT INTO customers (name, cpf_cnpj, phone, mobile, email, city, state, person_type, active, empresa_id)
VALUES
('João Silva Santos',      '123.456.789-01',    '(11) 3333-1111', '(11) 99999-1111', 'joao.silva@email.com',    'São Paulo',   'SP', 'PF', 1, 10),
('Maria Oliveira Costa',   '234.567.890-02',    '(11) 3333-2222', '(11) 99999-2222', 'maria.oliveira@email.com','São Paulo',   'SP', 'PF', 1, 10),
('Pedro Almeida Neto',     '345.678.901-03',    '(11) 3333-3333', '(11) 99999-3333', 'pedro.almeida@email.com', 'Guarulhos',   'SP', 'PF', 1, 10),
('Ana Paula Ferreira',     '456.789.012-04',    '(11) 3333-4444', '(11) 99999-4444', 'ana.ferreira@email.com',  'Osasco',      'SP', 'PF', 1, 10),
('Carlos Eduardo Lima',    '567.890.123-05',    '(11) 3333-5555', '(11) 99999-5555', 'carlos.lima@email.com',   'Santo André', 'SP', 'PF', 1, 10),
('Transporte Rápido Ltda', '12.345.678/0001-90','(11) 3333-6666', '(11) 99999-6666', 'contato@transrapido.com', 'São Paulo',   'SP', 'PJ', 1, 10),
('Distribuidora ABC Ltda', '23.456.789/0001-80','(11) 3333-7777', '(11) 99999-7777', 'contato@distrabcltda.com','Campinas',    'SP', 'PJ', 1, 10)
ON DUPLICATE KEY UPDATE name=VALUES(name);

-- ============================================================
-- EQUIPAMENTOS (VEÍCULOS)
-- ============================================================
INSERT INTO equipment (name, code, type, brand, model, year, serial_number, status, empresa_id, notes)
VALUES
('Honda Civic',   'VEI-001', 'Veículo Passeio', 'Honda',      'Civic 2.0',     2020, 'JOA-2345', 'active', 10, 'Placa JOA-2345 | Cliente: João Silva'),
('Toyota Corolla','VEI-002', 'Veículo Passeio', 'Toyota',     'Corolla 2.0',   2021, 'MBO-5678', 'active', 10, 'Placa MBO-5678 | Cliente: Maria Oliveira'),
('VW Gol',        'VEI-003', 'Veículo Passeio', 'Volkswagen', 'Gol 1.6',       2019, 'PNE-9012', 'active', 10, 'Placa PNE-9012 | Cliente: Pedro Almeida'),
('Ford Ka',       'VEI-004', 'Veículo Passeio', 'Ford',       'Ka 1.0',        2022, 'QRF-3456', 'active', 10, 'Placa QRF-3456 | Cliente: Ana Paula'),
('Fiat Uno',      'VEI-005', 'Veículo Passeio', 'Fiat',       'Uno 1.4',       2018, 'SLG-7890', 'active', 10, 'Placa SLG-7890 | Cliente: Carlos Lima'),
('Mercedes Sprinter','VEI-006','Van Carga',     'Mercedes',   'Sprinter 415',  2021, 'TRH-1234', 'active', 10, 'Placa TRH-1234 | Transporte Rápido'),
('VW Delivery',   'VEI-007', 'Caminhão',        'Volkswagen', 'Delivery 9.160',2020, 'UVI-5678', 'active', 10, 'Placa UVI-5678 | Distribuidora ABC')
ON DUPLICATE KEY UPDATE name=VALUES(name);

-- ============================================================
-- FORNECEDORES
-- ============================================================
INSERT INTO suppliers (name, trade_name, cnpj, phone, email, city, state, active, empresa_id)
VALUES
('Auto Peças Brasil Ltda',   'Auto Peças Brasil','11.222.333/0001-44','(11) 4444-1111','vendas@autopecasbr.com','São Paulo','SP',1,10),
('Distribuidora Motor Parts','Motor Parts',       '22.333.444/0001-55','(11) 4444-2222','vendas@motorparts.com', 'São Paulo','SP',1,10),
('Rolamentos e Cia Ltda',    'Rolamentos & Cia',  '33.444.555/0001-66','(11) 4444-3333','contato@rolamentos.com','Guarulhos', 'SP',1,10)
ON DUPLICATE KEY UPDATE name=VALUES(name);

-- ============================================================
-- PRODUTOS (PEÇAS)
-- ============================================================
INSERT INTO products (name, sku, description, sale_price, cost_price, empresa_id)
VALUES
('Filtro de Óleo',           'FO-001', 'Filtro de óleo para motor',           45.90,  22.00, 10),
('Filtro de Ar',             'FA-002', 'Filtro de ar do motor',               38.50,  18.00, 10),
('Vela de Ignição NGK',      'VI-003', 'Vela de ignição NGK iridium',         32.00,  15.00, 10),
('Pastilha de Freio Diant.', 'PF-004', 'Pastilha de freio dianteira',         89.90,  45.00, 10),
('Óleo Motor 5W30 1L',       'OM-005', 'Óleo motor sintético 5W30',           35.00,  18.00, 10),
('Kit Correia Dentada',      'CD-006', 'Kit correia dentada completo',        185.00,  90.00, 10),
('Amortecedor Dianteiro Par','AM-007', 'Amortecedor dianteiro par',           320.00, 160.00, 10),
('Bateria 60Ah',             'BA-008', 'Bateria 60Ah selada',                 380.00, 200.00, 10),
('Fluido de Freio DOT4',     'FF-009', 'Fluido de freio DOT4 500ml',          28.00,  12.00, 10),
('Lâmpada Farol H4',         'LF-010', 'Lâmpada farol H4 55W',               25.00,  10.00, 10)
ON DUPLICATE KEY UPDATE name=VALUES(name);

-- ============================================================
-- ORDENS DE SERVIÇO (demonstração)
-- ============================================================
INSERT INTO service_orders (number, status, empresa_id, customer_id, equipment_id, description, created_at)
SELECT
    CONCAT('OS-', LPAD(ROW_NUMBER() OVER (), 4, '0')),
    status_val,
    10,
    c.id,
    e.id,
    descricao,
    data_criacao
FROM (
    SELECT 'open'       as status_val, 'Revisão 10.000 km - Troca de óleo e filtros'         as descricao, NOW() - INTERVAL 1 DAY  as data_criacao, 1 as ord UNION ALL
    SELECT 'open',       'Revisão dos freios - pastilhas e discos dianteiros',                NOW() - INTERVAL 2 DAY,  2 UNION ALL
    SELECT 'in_progress','Diagnóstico elétrico - sistema de partida com falha',               NOW() - INTERVAL 3 DAY,  3 UNION ALL
    SELECT 'in_progress','Troca de correia dentada e tensor',                                 NOW() - INTERVAL 4 DAY,  4 UNION ALL
    SELECT 'completed',  'Revisão completa 30.000 km - troca de velas, filtros e óleo',      NOW() - INTERVAL 7 DAY,  5 UNION ALL
    SELECT 'completed',  'Alinhamento e balanceamento',                                       NOW() - INTERVAL 10 DAY, 6 UNION ALL
    SELECT 'completed',  'Troca de bateria',                                                  NOW() - INTERVAL 14 DAY, 7
) vals
JOIN customers  c ON c.empresa_id = 10 ORDER BY vals.ord
LIMIT 7;

SELECT CONCAT('Clientes: ',     COUNT(*)) as resumo FROM customers  WHERE empresa_id=10
UNION ALL
SELECT CONCAT('Veículos: ',     COUNT(*))            FROM equipment  WHERE empresa_id=10
UNION ALL
SELECT CONCAT('Fornecedores: ', COUNT(*))            FROM suppliers  WHERE empresa_id=10
UNION ALL
SELECT CONCAT('Peças: ',        COUNT(*))            FROM products   WHERE empresa_id=10
UNION ALL
SELECT CONCAT('Ordens de Serv:',COUNT(*))            FROM service_orders WHERE empresa_id=10;
