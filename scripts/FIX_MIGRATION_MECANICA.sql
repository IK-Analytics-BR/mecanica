-- ============================================================
-- FIX_MIGRATION_MECANICA.sql
-- Corrige tabelas e colunas faltantes para o MVP Mecânica
-- ============================================================

-- 1. CORRIGIR TABELA SALES (adicionar campos de NF-e)
-- ============================================================
ALTER TABLE sales 
ADD COLUMN IF NOT EXISTS chave_acesso_nfe VARCHAR(44) DEFAULT NULL,
ADD COLUMN IF NOT EXISTS numero_nfe VARCHAR(20) DEFAULT NULL,
ADD COLUMN IF NOT EXISTS status_nfe VARCHAR(20) DEFAULT NULL,
ADD COLUMN IF NOT EXISTS chave_acesso_nfce VARCHAR(44) DEFAULT NULL,
ADD COLUMN IF NOT EXISTS numero_nfce VARCHAR(20) DEFAULT NULL,
ADD COLUMN IF NOT EXISTS seller_id INT DEFAULT NULL;

-- 2. CRIAR TABELA DE GARANTIAS (warranties)
-- ============================================================
CREATE TABLE IF NOT EXISTS warranties (
    id INT AUTO_INCREMENT PRIMARY KEY,
    service_order_id INT NOT NULL,
    customer_id INT NOT NULL,
    product_id INT DEFAULT NULL,
    warranty_type VARCHAR(50) NOT NULL COMMENT 'peça, serviço, mão_de_obra',
    warranty_period_days INT NOT NULL DEFAULT 90,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    status VARCHAR(20) DEFAULT 'active' COMMENT 'active, expired, claimed',
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_service_order (service_order_id),
    INDEX idx_customer (customer_id),
    INDEX idx_status (status),
    INDEX idx_end_date (end_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 3. CRIAR TABELA DE COMISSÕES (commissions)
-- ============================================================
CREATE TABLE IF NOT EXISTS commissions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    technician_id INT NOT NULL,
    reference_month INT NOT NULL,
    reference_year INT NOT NULL,
    total_services INT DEFAULT 0,
    total_commission DECIMAL(10,2) DEFAULT 0.00,
    status VARCHAR(20) DEFAULT 'pending' COMMENT 'pending, paid',
    payment_date DATE DEFAULT NULL,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_technician (technician_id),
    INDEX idx_period (reference_year, reference_month),
    INDEX idx_status (status),
    UNIQUE KEY unique_commission_period (technician_id, reference_month, reference_year)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 4. CRIAR TABELA DE LEITURAS DE HORÍMETRO/QUILOMETRAGEM
-- ============================================================
CREATE TABLE IF NOT EXISTS hour_meter_readings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    equipment_id INT NOT NULL,
    reading_date DATE NOT NULL,
    current_reading INT NOT NULL COMMENT 'Quilometragem ou horímetro atual',
    previous_reading INT DEFAULT 0,
    difference INT DEFAULT 0,
    notes TEXT,
    created_by INT DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_equipment (equipment_id),
    INDEX idx_reading_date (reading_date),
    FOREIGN KEY (equipment_id) REFERENCES equipment(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 5. CRIAR TABELA DE PONTO/JORNADA (time_entries)
-- ============================================================
CREATE TABLE IF NOT EXISTS time_entries (
    id INT AUTO_INCREMENT PRIMARY KEY,
    technician_id INT NOT NULL,
    entry_date DATE NOT NULL,
    check_in TIME DEFAULT NULL,
    check_out TIME DEFAULT NULL,
    lunch_start TIME DEFAULT NULL,
    lunch_end TIME DEFAULT NULL,
    work_location VARCHAR(100) DEFAULT NULL COMMENT 'Local onde trabalhou',
    notes TEXT,
    status VARCHAR(20) DEFAULT 'present' COMMENT 'present, absent, late, early_leave',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_technician_date (technician_id, entry_date),
    INDEX idx_date (entry_date),
    FOREIGN KEY (technician_id) REFERENCES technicians(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 6. CRIAR VIEW vw_estabelecimentos_completos
-- ============================================================
CREATE OR REPLACE VIEW vw_estabelecimentos_completos AS
SELECT 
    c.id,
    c.name,
    c.email,
    c.phone,
    c.cpf_cnpj,
    c.address,
    c.city,
    c.state,
    c.zip,
    c.segment,
    c.active,
    c.created_at,
    COUNT(DISTINCT e.id) as total_equipamentos,
    COUNT(DISTINCT so.id) as total_os,
    SUM(CASE WHEN so.status = 'open' THEN 1 ELSE 0 END) as os_abertas,
    SUM(CASE WHEN so.status = 'completed' THEN 1 ELSE 0 END) as os_concluidas
FROM customers c
LEFT JOIN equipment e ON e.customer_id = c.id
LEFT JOIN service_orders so ON so.customer_id = c.id
WHERE c.segment IN ('oficina', 'mecanica', 'auto_center', 'concessionaria', 'fornecedor_pecas', 'fornecedor_oleo')
   OR c.segment IS NULL
GROUP BY c.id;

-- 7. CRIAR TABELA DE INSUMOS/SERVIÇOS (services_catalog)
-- ============================================================
CREATE TABLE IF NOT EXISTS services_catalog (
    id INT AUTO_INCREMENT PRIMARY KEY,
    service_code VARCHAR(20) NOT NULL UNIQUE,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    category VARCHAR(100) DEFAULT NULL,
    standard_hours DECIMAL(5,2) DEFAULT 1.00,
    standard_price DECIMAL(10,2) DEFAULT 0.00,
    cost_price DECIMAL(10,2) DEFAULT 0.00,
    active TINYINT(1) DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_category (category),
    INDEX idx_active (active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 8. INSERIR SERVIÇOS PADRÃO NA TABELA DE SERVIÇOS
-- ============================================================
INSERT INTO services_catalog (service_code, name, description, category, standard_hours, standard_price, cost_price) VALUES
('SRV001', 'Troca de Óleo', 'Troca de óleo do motor e filtro', 'Revisão', 0.5, 120.00, 45.00),
('SRV002', 'Troca de Filtro de Ar', 'Substituição do filtro de ar do motor', 'Revisão', 0.25, 75.00, 35.00),
('SRV003', 'Troca de Filtro de Combustível', 'Substituição do filtro de combustível', 'Revisão', 0.5, 95.00, 45.00),
('SRV004', 'Troca de Pastilha de Freio', 'Substituição das pastilhas de freio dianteiras', 'Freios', 1.0, 180.00, 80.00),
('SRV005', 'Reparo de Suspensão', 'Reparo no sistema de suspensão', 'Suspensão', 2.0, 350.00, 120.00),
('SRV006', 'Diagnóstico Eletrônico', 'Diagnóstico completo via scanner', 'Elétrica', 1.0, 150.00, 0.00),
('SRV007', 'Troca de Bateria', 'Substituição da bateria do veículo', 'Elétrica', 0.5, 85.00, 0.00),
('SRV008', 'Alinhamento e Balanceamento', 'Alinhamento de direção e balanceamento', 'Pneus', 1.5, 120.00, 0.00),
('SRV009', 'Revisão Preventiva 10.000km', 'Revisão completa de 10.000 km', 'Revisão', 2.0, 450.00, 150.00),
('SRV010', 'Revisão Preventiva 20.000km', 'Revisão completa de 20.000 km', 'Revisão', 3.0, 650.00, 220.00),
('SRV011', 'Troca de Correia Dentada', 'Substituição da correia dentada', 'Motor', 3.0, 450.00, 180.00),
('SRV012', 'Limpeza de Bicos Injetores', 'Limpeza e regulagem de bicos injetores', 'Motor', 2.0, 280.00, 80.00),
('SRV013', 'Higienização Ar Condicionado', 'Limpeza do sistema de ar condicionado', 'Ar Condicionado', 1.0, 150.00, 40.00),
('SRV014', 'Troca de Amortecedores', 'Substituição dos amortecedores', 'Suspensão', 2.5, 380.00, 140.00),
('SRV015', 'Reparo no Câmbio', 'Reparos no sistema de transmissão', 'Transmissão', 4.0, 850.00, 300.00)
ON DUPLICATE KEY UPDATE 
    name = VALUES(name),
    standard_price = VALUES(standard_price);

-- 9. CRIAR/ATUALIZAR TABELA DE MANUTENÇÕES PREVENTIVAS
-- ============================================================
CREATE TABLE IF NOT EXISTS maintenance_plans (
    id INT AUTO_INCREMENT PRIMARY KEY,
    customer_id INT NOT NULL,
    equipment_id INT NOT NULL,
    plan_name VARCHAR(200) NOT NULL,
    km_interval INT DEFAULT 10000,
    days_interval INT DEFAULT 180,
    last_km INT DEFAULT 0,
    next_km INT DEFAULT 0,
    last_date DATE DEFAULT NULL,
    next_date DATE DEFAULT NULL,
    status VARCHAR(20) DEFAULT 'active' COMMENT 'active, completed, overdue',
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_customer (customer_id),
    INDEX idx_equipment (equipment_id),
    INDEX idx_next_date (next_date),
    INDEX idx_status (status),
    FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE,
    FOREIGN KEY (equipment_id) REFERENCES equipment(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 10. CORRIGIR A TABELA SERVICE_ORDERS (adicionar campos faltantes)
-- ============================================================
ALTER TABLE service_orders 
ADD COLUMN IF NOT EXISTS seller_id INT DEFAULT NULL AFTER technician_id,
ADD COLUMN IF NOT EXISTS data_inicio_servico DATETIME DEFAULT NULL,
ADD COLUMN IF NOT EXISTS data_fim_servico DATETIME DEFAULT NULL,
ADD INDEX IF NOT EXISTS idx_seller (seller_id);

-- 11. CRIAR TABELA KARDEX SE NÃO EXISTIR
-- ============================================================
CREATE TABLE IF NOT EXISTS kardex (
    id INT AUTO_INCREMENT PRIMARY KEY,
    product_id INT NOT NULL,
    movement_type VARCHAR(20) NOT NULL COMMENT 'input, output, adjustment',
    quantity DECIMAL(10,3) NOT NULL,
    unit_price DECIMAL(10,2) DEFAULT 0.00,
    document_number VARCHAR(50) DEFAULT NULL,
    reference_type VARCHAR(50) DEFAULT NULL COMMENT 'purchase_order, service_order, adjustment, sale',
    reference_id INT DEFAULT NULL,
    notes TEXT,
    created_by INT DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_product (product_id),
    INDEX idx_movement_type (movement_type),
    INDEX idx_created_at (created_at),
    INDEX idx_reference (reference_type, reference_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 12. CRIAR TABELA DE ROMANEIOS SE NÃO EXISTIR
-- ============================================================
CREATE TABLE IF NOT EXISTS sales_manifests (
    id INT AUTO_INCREMENT PRIMARY KEY,
    manifest_number VARCHAR(20) NOT NULL UNIQUE,
    seller_id INT DEFAULT NULL,
    route_id INT DEFAULT NULL,
    date DATE NOT NULL,
    total_amount DECIMAL(10,2) DEFAULT 0.00,
    status VARCHAR(20) DEFAULT 'open' COMMENT 'open, closed, cancelled',
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_seller (seller_id),
    INDEX idx_date (date),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS sales_manifest_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    manifest_id INT NOT NULL,
    customer_id INT NOT NULL,
    sale_id INT DEFAULT NULL,
    order_number INT DEFAULT NULL,
    product_id INT DEFAULT NULL,
    quantity DECIMAL(10,3) DEFAULT 0,
    unit_price DECIMAL(10,2) DEFAULT 0.00,
    total_price DECIMAL(10,2) DEFAULT 0.00,
    status VARCHAR(20) DEFAULT 'pending',
    delivery_sequence INT DEFAULT 0,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_manifest (manifest_id),
    INDEX idx_customer (customer_id),
    FOREIGN KEY (manifest_id) REFERENCES sales_manifests(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 13. CRIAR TABELA DE ROTAS DE VENDA SE NÃO EXISTIR
-- ============================================================
CREATE TABLE IF NOT EXISTS sales_routes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(20) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    seller_id INT DEFAULT NULL,
    active TINYINT(1) DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_seller (seller_id),
    INDEX idx_active (active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 14. INSERIR ROTAS DE VENDA PADRÃO
-- ============================================================
INSERT INTO sales_routes (code, name, description) VALUES
('R001', 'Zona Norte SP', 'Rota de vendas na zona norte de São Paulo'),
('R002', 'Zona Sul SP', 'Rota de vendas na zona sul de São Paulo'),
('R003', 'Zona Leste SP', 'Rota de vendas na zona leste de São Paulo'),
('R004', 'Zona Oeste SP', 'Rota de vendas na zona oeste de São Paulo'),
('R005', 'ABC Paulista', 'Rota de vendas no ABC Paulista'),
('R006', 'Grande SP', 'Rota de vendas na Grande São Paulo')
ON DUPLICATE KEY UPDATE name = VALUES(name);

-- 15. CRIAR TABELA DE CAIXA/REGISTRADORA SE NÃO EXISTIR
-- ============================================================
CREATE TABLE IF NOT EXISTS cash_register (
    id INT AUTO_INCREMENT PRIMARY KEY,
    opening_amount DECIMAL(10,2) NOT NULL,
    closing_amount DECIMAL(10,2) DEFAULT NULL,
    status VARCHAR(20) DEFAULT 'open' COMMENT 'open, closed',
    opening_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    closing_date DATETIME DEFAULT NULL,
    opened_by INT DEFAULT NULL,
    closed_by INT DEFAULT NULL,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_status (status),
    INDEX idx_opening_date (opening_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 16. CRIAR TABELA DE FLUXO DE CAIXA SE NÃO EXISTIR
-- ============================================================
CREATE TABLE IF NOT EXISTS cash_flow (
    id INT AUTO_INCREMENT PRIMARY KEY,
    type VARCHAR(20) NOT NULL COMMENT 'income, expense',
    category VARCHAR(50) NOT NULL,
    description VARCHAR(200) NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    date DATE NOT NULL,
    cash_register_id INT DEFAULT NULL,
    reference_type VARCHAR(50) DEFAULT NULL,
    reference_id INT DEFAULT NULL,
    created_by INT DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_type (type),
    INDEX idx_date (date),
    INDEX idx_category (category)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 17. MENSAGEM DE CONCLUSÃO
-- ============================================================
SELECT 'Migração concluída! Tabelas e colunas criadas/atualizadas.' AS message;
