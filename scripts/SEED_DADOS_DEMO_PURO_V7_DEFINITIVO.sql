-- ============================================================
-- SEED_DADOS_DEMO_PURO_V7_DEFINITIVO.sql
-- Versão corrigida com base na estrutura REAL das tabelas
-- ============================================================

USE supply_chain_mecanica;

SET FOREIGN_KEY_CHECKS = 0;

-- ============================================================
-- 1. CATEGORIAS DE PRODUTOS
-- ============================================================
DELETE FROM product_categories WHERE id <= 10;
ALTER TABLE product_categories AUTO_INCREMENT = 1;

INSERT INTO product_categories (id, name, active) VALUES
(1, 'Motor', 1),
(2, 'Transmissão', 1),
(3, 'Freios', 1),
(4, 'Suspensão', 1),
(5, 'Elétrica', 1),
(6, 'Arrefecimento', 1),
(7, 'Filtros', 1),
(8, 'Óleos', 1),
(9, 'Pneus', 1),
(10, 'Acessórios', 1)
ON DUPLICATE KEY UPDATE name = VALUES(name);

-- ============================================================
-- 2. MARCAS
-- ============================================================
DELETE FROM product_brands WHERE id <= 11;
ALTER TABLE product_brands AUTO_INCREMENT = 1;

INSERT INTO product_brands (id, name, active) VALUES
(1, 'Original', 1),
(2, 'Bosch', 1),
(3, 'Fram', 1),
(4, 'NGK', 1),
(5, 'Acdelco', 1),
(6, 'Wega', 1),
(7, 'Maxxi', 1),
(8, 'Valeo', 1),
(9, 'SKF', 1),
(10, 'Dayco', 1),
(11, 'Gates', 1)
ON DUPLICATE KEY UPDATE name = VALUES(name);

-- ============================================================
-- 3. FORNECEDORES
-- ============================================================
INSERT INTO suppliers (name, cnpj, email, phone, address, city, state, razao_social, neighborhood, active, created_at) VALUES
('AutoPeças Nacional Ltda', '12345678000190', 'contato@autopecasnacional.com', '1130000001', 'Av. Industrial, 500', 'São Paulo', 'SP', 'AutoPeças Nacional Ltda', 'Centro', 1, NOW()),
('Distribuidora de Óleos SP', '23456789000101', 'vendas@oleossp.com', '1130000002', 'Rua do Óleo, 100', 'São Paulo', 'SP', 'Distribuidora de Óleos SP', 'Vila Olímpia', 1, NOW()),
('Bosch Automotive Brasil', '34567890000112', 'pedidos@bosch.com.br', '1130000003', 'Av. Bosch, 1000', 'São Paulo', 'SP', 'Bosch Automotive Brasil', 'Santo Amaro', 1, NOW()),
('Filtros & Cia', '45678901000123', 'comercial@filtros.com', '1130000004', 'Rua dos Filtros, 200', 'São Paulo', 'SP', 'Filtros & Cia', 'Ipiranga', 1, NOW()),
('Freios Master', '56789012000134', 'vendas@freiosmaster.com', '1130000005', 'Av. dos Freios, 300', 'São Paulo', 'SP', 'Freios Master', 'Mooca', 1, NOW())
ON DUPLICATE KEY UPDATE name = VALUES(name);

-- ============================================================
-- 4. CLIENTES - CORREÇÃO: zip → cep
-- ============================================================
INSERT INTO customers (name, email, phone, cpf, cnpj, address, city, state, cep, active, created_at) VALUES
('João Silva', 'joao.silva@demo.com', '11999990001', '123.456.789-01', '', 'Rua das Flores, 100', 'São Paulo', 'SP', '01001-000', 1, NOW()),
('Maria Santos', 'maria.santos@demo.com', '11999990002', '123.456.789-02', '', 'Av. Brasil, 200', 'São Paulo', 'SP', '02002-000', 1, NOW()),
('Pedro Costa', 'pedro.costa@demo.com', '11999990003', '123.456.789-03', '', 'Rua Boa Vista, 300', 'São Paulo', 'SP', '03003-000', 1, NOW()),
('Ana Oliveira', 'ana.oliveira@demo.com', '11999990004', '123.456.789-04', '', 'Av. Paulista, 1000', 'São Paulo', 'SP', '04004-000', 1, NOW()),
('Carlos Lima', 'carlos.lima@demo.com', '11999990005', '123.456.789-05', '', 'Rua XV de Novembro, 50', 'São Paulo', 'SP', '05005-000', 1, NOW())
ON DUPLICATE KEY UPDATE name = VALUES(name);

-- ============================================================
-- 5. VEÍCULOS - ESTRUTURA REAL
-- ============================================================
INSERT INTO equipment (name, serial_number, model, manufacturer, accumulated_hours, customer_id, active, created_at) VALUES
('Honda Civic 2020', 'ABC1234', 'Civic', 'Honda', 35000, 1, 1, NOW()),
('Toyota Corolla 2019', 'ABC1235', 'Corolla', 'Toyota', 42000, 2, 1, NOW()),
('VW Gol 2018', 'ABC1236', 'Gol', 'Volkswagen', 55000, 3, 1, NOW()),
('Chevrolet Onix 2021', 'ABC1237', 'Onix', 'Chevrolet', 28000, 4, 1, NOW()),
('Ford Ka 2017', 'ABC1238', 'Ka', 'Ford', 62000, 5, 1, NOW())
ON DUPLICATE KEY UPDATE serial_number = VALUES(serial_number);

-- ============================================================
-- 6. TÉCNICOS - CORREÇÃO: specialization → specialty (ENUM)
-- ============================================================
INSERT INTO technicians (name, email, phone, specialty, active, created_at) VALUES
('João das Peças', 'joao.pecas@demo.com', '11988880001', 'mechanical', 1, NOW()),
('Pedro Elétrica', 'pedro.elec@demo.com', '11988880002', 'electrical', 1, NOW()),
('Carlos Funilaria', 'carlos.fun@demo.com', '11988880003', 'general', 1, NOW()),
('Marcos Arrefecimento', 'marcos.ar@demo.com', '11988880004', 'mechanical', 1, NOW()),
('Ricardo Suspensão', 'ricardo.sus@demo.com', '11988880005', 'mechanical', 1, NOW())
ON DUPLICATE KEY UPDATE name = VALUES(name);

-- ============================================================
-- 7. VENDEDORES - CORREÇÃO: remover seller_type e commission_percent
-- ============================================================
INSERT INTO sellers (name, cpf, region, phone, email, active, created_at) VALUES
('Roberto Vendas', '987.654.321-01', 'Zona Norte', '11977770001', 'roberto.vendas@demo.com', 1, NOW()),
('Sandra Atendimento', '987.654.321-02', 'Zona Sul', '11977770002', 'sandra.atend@demo.com', 1, NOW()),
('Thiago Peças', '987.654.321-03', 'Centro', '11977770003', 'thiago.pecas@demo.com', 1, NOW()),
('Patricia Pós-venda', '987.654.321-04', 'Zona Leste', '11977770004', 'patricia.pos@demo.com', 1, NOW()),
('Marcelo Frotas', '987.654.321-05', 'ABC', '11977770005', 'marcelo.frotas@demo.com', 1, NOW())
ON DUPLICATE KEY UPDATE name = VALUES(name);

-- ============================================================
-- 8. PRODUTOS
-- ============================================================
INSERT INTO products (sku, internal_code, name, category, category_id, brand_id, unit_measure, cost_price, price, stock_quantity, min_stock, main_supplier_id, active, created_at, ncm) VALUES
('OLFLTR001', 'P001', 'Filtro de Óleo - Nacional', 'Filtros', 7, 1, 'UN', 25.00, 55.00, 20, 5, 1, 1, NOW(), '8421.23.10'),
('ARFLTR001', 'P002', 'Filtro de Ar - Bosch', 'Filtros', 7, 2, 'UN', 35.00, 75.00, 15, 5, 2, 1, NOW(), '8421.23.20'),
('CBFLTR001', 'P003', 'Filtro de Combustível - Fram', 'Filtros', 7, 3, 'UN', 45.00, 95.00, 12, 3, 3, 1, NOW(), '8421.23.30'),
('FRPD001', 'P004', 'Pastilha Freio Dianteira - Acdelco', 'Freios', 3, 5, 'UN', 80.00, 180.00, 25, 8, 4, 1, NOW(), '8708.30.10'),
('OLEO5W001', 'P005', 'Óleo 5W30 - Castrol', 'Óleos', 8, 1, 'LT', 28.00, 60.00, 50, 15, 2, 1, NOW(), '2710.19.20')
ON DUPLICATE KEY UPDATE sku = VALUES(sku);

-- ============================================================
-- 9. ROTAS DE VENDA - CORREÇÃO: adicionar seller_id e frequency
-- ============================================================
INSERT INTO sales_routes (code, name, seller_id, frequency, active, created_at) VALUES
('R001', 'Zona Norte SP', 1, 'weekly', 1, NOW()),
('R002', 'Zona Sul SP', 2, 'weekly', 1, NOW()),
('R003', 'Zona Leste SP', 3, 'weekly', 1, NOW()),
('R004', 'Zona Oeste SP', 4, 'weekly', 1, NOW()),
('R005', 'ABC Paulista', 5, 'weekly', 1, NOW())
ON DUPLICATE KEY UPDATE name = VALUES(name);

-- ============================================================
-- 10. ORDENS DE SERVIÇO - CORREÇÃO: ESTRUTURA REAL
-- ============================================================
INSERT INTO service_orders (order_number, customer_id, equipment_id, type, status, technician_id, observations, active, created_at) VALUES
('OS202500001', 1, 1, 'corrective', 'open', 1, 'Troca de óleo e filtros', 1, NOW()),
('OS202500002', 2, 2, 'corrective', 'in_progress', 2, 'Reparo sistema elétrico', 1, NOW()),
('OS202500003', 3, 3, 'preventive', 'completed', 3, 'Revisão preventiva 20.000km', 1, NOW()),
('OS202500004', 4, 4, 'corrective', 'open', 4, 'Reparo no freio', 1, NOW()),
('OS202500005', 5, 5, 'preventive', 'open', 5, 'Troca de pastilhas', 1, NOW())
ON DUPLICATE KEY UPDATE order_number = VALUES(order_number);

-- ============================================================
-- 11. ITENS DE SERVIÇO - CORREÇÃO: supply_id (não product_id)
-- ============================================================
INSERT INTO service_order_items (service_order_id, supply_id, quantity, unit_cost, descricao, quantidade, valor_unitario, valor_total, created_at) VALUES
(1, 1, 1, 25.00, 'Filtro de óleo', 1.000, 55.00, 55.00, NOW()),
(2, 2, 1, 35.00, 'Filtro de ar', 1.000, 75.00, 75.00, NOW()),
(3, 3, 1, 45.00, 'Filtro combustível', 1.000, 95.00, 95.00, NOW()),
(4, 4, 1, 80.00, 'Pastilha freio', 1.000, 180.00, 180.00, NOW()),
(5, 5, 2, 28.00, 'Óleo 5W30', 2.000, 60.00, 120.00, NOW());

-- ============================================================
-- 12. CONTAS A RECEBER - CORREÇÃO: ESTRUTURA REAL
-- ============================================================
INSERT INTO accounts_receivable (customer_id, description, total_amount, installments, issue_date, due_date, payment_method, bank_account_id, status, origin, service_order_id, active, created_at) VALUES
(1, 'Pagamento OS #1', 140.00, 1, DATE_SUB(NOW(), INTERVAL 5 DAY), DATE_ADD(NOW(), INTERVAL 2 DAY), 'pix', 1, 'pending', 'service', 1, 1, NOW()),
(2, 'Pagamento OS #2', 180.00, 1, DATE_SUB(NOW(), INTERVAL 3 DAY), DATE_ADD(NOW(), INTERVAL 1 DAY), 'credit_card', 1, 'pending', 'service', 2, 1, NOW()),
(3, 'Pagamento OS #3', 255.00, 1, DATE_SUB(NOW(), INTERVAL 10 DAY), DATE_SUB(NOW(), INTERVAL 7 DAY), 'pix', 1, 'received', 'service', 3, 1, NOW()),
(4, 'Pagamento OS #4', 156.00, 1, DATE_SUB(NOW(), INTERVAL 2 DAY), DATE_ADD(NOW(), INTERVAL 1 DAY), 'cash', 1, 'pending', 'service', 4, 1, NOW()),
(5, 'Pagamento OS #5', 180.00, 1, DATE_SUB(NOW(), INTERVAL 1 DAY), DATE_ADD(NOW(), INTERVAL 3 DAY), 'debit_card', 1, 'pending', 'service', 5, 1, NOW())
ON DUPLICATE KEY UPDATE description = VALUES(description);

-- ============================================================
-- 13. CONTAS A PAGAR - CORREÇÃO: ESTRUTURA REAL
-- ============================================================
INSERT INTO accounts_payable (supplier_id, description, amount, issue_date, due_date, status, active, created_at) VALUES
(1, 'Pagamento Fornecedor AutoPeças', 1500.00, DATE_SUB(NOW(), INTERVAL 5 DAY), DATE_ADD(NOW(), INTERVAL 10 DAY), 'pending', 1, NOW()),
(2, 'Pagamento Distribuidora Óleos', 2000.00, DATE_SUB(NOW(), INTERVAL 3 DAY), DATE_ADD(NOW(), INTERVAL 5 DAY), 'pending', 1, NOW()),
(3, 'Pagamento Bosch', 3500.00, DATE_SUB(NOW(), INTERVAL 7 DAY), DATE_ADD(NOW(), INTERVAL 15 DAY), 'pending', 1, NOW()),
(4, 'Pagamento Filtros & Cia', 800.00, DATE_SUB(NOW(), INTERVAL 2 DAY), DATE_ADD(NOW(), INTERVAL 8 DAY), 'pending', 1, NOW()),
(5, 'Pagamento Freios Master', 1200.00, DATE_SUB(NOW(), INTERVAL 4 DAY), DATE_ADD(NOW(), INTERVAL 12 DAY), 'pending', 1, NOW())
ON DUPLICATE KEY UPDATE description = VALUES(description);

-- ============================================================
-- 14. VENDAS PDV
-- ============================================================
INSERT INTO sales (customer_id, seller_id, sale_date, payment_method, status, gross_total, discount_total, net_total, created_at) VALUES
(1, 1, DATE_SUB(NOW(), INTERVAL 5 DAY), 'money', 'confirmed', 110.00, 0.00, 110.00, NOW()),
(2, 1, DATE_SUB(NOW(), INTERVAL 4 DAY), 'credit', 'confirmed', 180.00, 10.00, 170.00, NOW()),
(3, 2, DATE_SUB(NOW(), INTERVAL 3 DAY), 'debit', 'confirmed', 95.00, 0.00, 95.00, NOW()),
(4, 1, DATE_SUB(NOW(), INTERVAL 2 DAY), 'money', 'confirmed', 55.00, 0.00, 55.00, NOW()),
(5, 3, DATE_SUB(NOW(), INTERVAL 1 DAY), 'pix', 'confirmed', 280.00, 20.00, 260.00, NOW())
ON DUPLICATE KEY UPDATE created_at = VALUES(created_at);

-- ============================================================
-- 15. KARDEX
-- ============================================================
INSERT INTO kardex (product_id, movement_type, quantity, unit_price, document_number, reference_type, reference_id, notes, created_at) VALUES
(1, 'input', 20.000, 25.00, 'NF001', 'purchase', 1, 'Entrada inicial', NOW()),
(2, 'input', 15.000, 35.00, 'NF002', 'purchase', 2, 'Entrada inicial', NOW()),
(3, 'input', 12.000, 45.00, 'NF003', 'purchase', 3, 'Entrada inicial', NOW()),
(4, 'output', 2.000, 80.00, 'OS001', 'service_order', 1, 'Saída para OS', DATE_SUB(NOW(), INTERVAL 5 DAY)),
(5, 'output', 2.000, 28.00, 'OS002', 'service_order', 2, 'Saída para OS', DATE_SUB(NOW(), INTERVAL 3 DAY));

-- ============================================================
-- 16. PLANO DE CONTAS
-- ============================================================
INSERT INTO chart_of_accounts (code, name, type, is_analytical, active, created_at) VALUES
('1.1.01', 'Caixa', 'asset', 1, 1, NOW()),
('1.1.02', 'Banco Conta Corrente', 'asset', 1, 1, NOW()),
('1.2.01', 'Clientes', 'asset', 1, 1, NOW()),
('1.2.02', 'Estoque', 'asset', 1, 1, NOW()),
('2.1.01', 'Fornecedores', 'liability', 1, 1, NOW()),
('2.1.02', 'Impostos a Pagar', 'liability', 1, 1, NOW()),
('3.1.01', 'Capital Social', 'equity', 1, 1, NOW()),
('4.1.01', 'Receita de Serviços', 'revenue', 1, 1, NOW()),
('4.1.02', 'Receita de Vendas', 'revenue', 1, 1, NOW()),
('5.1.01', 'Custo de Mercadorias', 'expense', 1, 1, NOW()),
('5.1.02', 'Custo de Serviços', 'expense', 1, 1, NOW())
ON DUPLICATE KEY UPDATE name = VALUES(name);

-- ============================================================
-- 17. CAIXA
-- ============================================================
INSERT INTO cash_register (register_number, user_id, cashier_name, opened_at, closed_at, opening_balance, status, created_at) VALUES
('CX001', 1, 'Operador 1', DATE_SUB(NOW(), INTERVAL 30 DAY), DATE_SUB(NOW(), INTERVAL 30 DAY), 500.00, 'closed', NOW()),
('CX002', 1, 'Operador 1', DATE_SUB(NOW(), INTERVAL 25 DAY), DATE_SUB(NOW(), INTERVAL 25 DAY), 600.00, 'closed', NOW()),
('CX003', 1, 'Operador 1', DATE_SUB(NOW(), INTERVAL 20 DAY), DATE_SUB(NOW(), INTERVAL 20 DAY), 550.00, 'closed', NOW()),
('CX004', 1, 'Operador 1', DATE_SUB(NOW(), INTERVAL 15 DAY), DATE_SUB(NOW(), INTERVAL 15 DAY), 700.00, 'closed', NOW()),
('CX005', 1, 'Operador 1', DATE_SUB(NOW(), INTERVAL 10 DAY), DATE_SUB(NOW(), INTERVAL 10 DAY), 650.00, 'closed', NOW()),
('CX006', 1, 'Operador 1', DATE_SUB(NOW(), INTERVAL 5 DAY), NULL, 800.00, 'open', NOW());

-- ============================================================
-- 18. FLUXO DE CAIXA
-- ============================================================
INSERT INTO cash_flow (date, type, description, amount, bank_account_id, reference_type, created_at) VALUES
(DATE_SUB(NOW(), INTERVAL 10 DAY), 'income', 'Recebimento OS #3', 70.00, 1, 'receivable', NOW()),
(DATE_SUB(NOW(), INTERVAL 9 DAY), 'income', 'Venda PDV #1', 110.00, 1, 'manual', NOW()),
(DATE_SUB(NOW(), INTERVAL 8 DAY), 'income', 'Venda PDV #2', 170.00, 1, 'manual', NOW()),
(DATE_SUB(NOW(), INTERVAL 5 DAY), 'expense', 'Pagamento Fornecedor', 1500.00, 1, 'payable', NOW()),
(DATE_SUB(NOW(), INTERVAL 3 DAY), 'expense', 'Energia Elétrica', 800.00, 1, 'manual', NOW());

-- ============================================================
-- 19. COMISSÕES
-- ============================================================
INSERT INTO commissions (technician_id, reference_month, reference_year, total_services, total_commission, status, created_at) VALUES
(1, 5, 2026, 15, 450.00, 'pending', NOW()),
(2, 5, 2026, 12, 380.00, 'paid', NOW()),
(3, 5, 2026, 18, 520.00, 'pending', NOW()),
(4, 5, 2026, 10, 290.00, 'pending', NOW()),
(5, 5, 2026, 14, 410.00, 'pending', NOW());

-- ============================================================
-- 20. GARANTIAS
-- ============================================================
INSERT INTO warranties (service_order_id, customer_id, warranty_type, warranty_period_days, start_date, end_date, status, notes, created_at) VALUES
(3, 3, 'service', 90, DATE_SUB(NOW(), INTERVAL 10 DAY), DATE_ADD(NOW(), INTERVAL 80 DAY), 'active', 'Garantia revisão 20k km', NOW()),
(1, 1, 'parts', 180, DATE_SUB(NOW(), INTERVAL 5 DAY), DATE_ADD(NOW(), INTERVAL 175 DAY), 'active', 'Garantia peças', NOW()),
(2, 2, 'service', 90, DATE_SUB(NOW(), INTERVAL 3 DAY), DATE_ADD(NOW(), INTERVAL 87 DAY), 'active', 'Garantia serviço', NOW()),
(4, 4, 'service', 90, DATE_SUB(NOW(), INTERVAL 2 DAY), DATE_ADD(NOW(), INTERVAL 88 DAY), 'active', 'Garantia freio', NOW()),
(5, 5, 'service', 90, DATE_SUB(NOW(), INTERVAL 1 DAY), DATE_ADD(NOW(), INTERVAL 89 DAY), 'active', 'Garantia pastilhas', NOW());

-- ============================================================
-- 21. PLANOS DE MANUTENÇÃO - CORREÇÃO: ESTRUTURA REAL
-- ============================================================
INSERT INTO maintenance_plans (customer_id, equipment_id, type, trigger_type, trigger_value, task, instructions, active, created_at) VALUES
(1, 1, 'preventive', 'hours', 10000, 'Revisão 10.000 km', 'Troca de óleo, filtros e verificação geral', 1, NOW()),
(2, 2, 'preventive', 'hours', 10000, 'Revisão 10.000 km', 'Revisão preventiva completa', 1, NOW()),
(3, 3, 'preventive', 'hours', 5000, 'Troca de Óleo', 'Troca óleo e filtro', 1, NOW()),
(4, 4, 'preventive', 'hours', 10000, 'Revisão 10.000 km', 'Revisão preventiva', 1, NOW()),
(5, 5, 'preventive', 'hours', 5000, 'Troca de Óleo', 'Troca óleo e revisão', 1, NOW());

-- ============================================================
-- 22. LEITURAS DE HORÍMETRO - CORREÇÃO: hours (não accumulated_hours)
-- ============================================================
INSERT INTO hour_meter_readings (equipment_id, reading_date, hours, reading_type, created_at) VALUES
(1, DATE_SUB(NOW(), INTERVAL 30 DAY), 35000, 'manual', NOW()),
(1, DATE_SUB(NOW(), INTERVAL 60 DAY), 34000, 'manual', NOW()),
(2, DATE_SUB(NOW(), INTERVAL 45 DAY), 42000, 'manual', NOW()),
(3, DATE_SUB(NOW(), INTERVAL 60 DAY), 55000, 'manual', NOW()),
(4, DATE_SUB(NOW(), INTERVAL 90 DAY), 28000, 'manual', NOW()),
(5, DATE_SUB(NOW(), INTERVAL 15 DAY), 62000, 'manual', NOW());

-- ============================================================
-- 23. REGISTROS DE PONTO
-- ============================================================
INSERT INTO time_entries (technician_id, entry_date, check_in, check_out, lunch_start, lunch_end, work_location, status, notes, created_at) VALUES
(1, DATE_SUB(NOW(), INTERVAL 1 DAY), '08:00', '18:00', '12:00', '13:00', 'Oficina Central', 'present', 'Dia normal', NOW()),
(2, DATE_SUB(NOW(), INTERVAL 1 DAY), '08:00', '18:00', '12:00', '13:00', 'Oficina Central', 'present', 'Dia normal', NOW()),
(3, DATE_SUB(NOW(), INTERVAL 1 DAY), '08:00', '17:30', '12:00', '13:00', 'Oficina Centro', 'present', 'Saída mais cedo', NOW()),
(4, DATE_SUB(NOW(), INTERVAL 1 DAY), '08:30', '18:00', '12:00', '13:00', 'Oficina Central', 'present', 'Atraso 30min', NOW()),
(5, DATE_SUB(NOW(), INTERVAL 1 DAY), '08:00', '18:00', '12:00', '13:00', 'Oficina Centro', 'present', 'Dia normal', NOW()),
(1, DATE_SUB(NOW(), INTERVAL 2 DAY), '08:00', '18:00', '12:00', '13:00', 'Oficina Central', 'present', 'Dia normal', NOW()),
(2, DATE_SUB(NOW(), INTERVAL 2 DAY), '08:00', '18:00', '12:00', '13:00', 'Oficina Central', 'present', 'Dia normal', NOW()),
(3, DATE_SUB(NOW(), INTERVAL 2 DAY), '08:00', '18:00', '12:00', '13:00', 'Oficina Centro', 'present', 'Dia normal', NOW()),
(4, DATE_SUB(NOW(), INTERVAL 3 DAY), '00:00', '00:00', NULL, NULL, NULL, 'absent', 'Falta - atestado médico', NOW()),
(5, DATE_SUB(NOW(), INTERVAL 3 DAY), '08:00', '18:00', '12:00', '13:00', 'Oficina Central', 'present', 'Dia normal', NOW());

-- ============================================================
-- 24. NOTAS FISCAIS
-- ============================================================
INSERT INTO invoices (order_id, invoice_number, series, invoice_type, customer_id, amount, issue_date, status, notes, created_at) VALUES
(3, '35190610222758000152550010001234567812345678', '001', 'NF-e', 3, 255.00, DATE_SUB(NOW(), INTERVAL 10 DAY), 'issued', 'Nota fiscal OS #3', NOW()),
(1, '35190610222758000152550010001234567912345679', '001', 'NFS-e', 1, 140.00, DATE_SUB(NOW(), INTERVAL 5 DAY), 'issued', 'Nota serviço OS #1', NOW()),
(2, '35190610222758000152550010001234568012345680', '001', 'NFS-e', 2, 180.00, DATE_SUB(NOW(), INTERVAL 3 DAY), 'issued', 'Nota serviço OS #2', NOW()),
(4, '35190610222758000152550010001234568112345681', '001', 'NFS-e', 4, 156.00, DATE_SUB(NOW(), INTERVAL 2 DAY), 'issued', 'Nota serviço OS #4', NOW()),
(5, '35190610222758000152550010001234568212345682', '001', 'NFS-e', 5, 180.00, DATE_SUB(NOW(), INTERVAL 1 DAY), 'issued', 'Nota serviço OS #5', NOW());

SET FOREIGN_KEY_CHECKS = 1;

-- ============================================================
-- RESUMO
-- ============================================================
SELECT 'SEED V7 DEFINITIVO EXECUTADO!' AS RESULTADO;
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
