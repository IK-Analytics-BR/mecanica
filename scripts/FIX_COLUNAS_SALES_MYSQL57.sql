-- ============================================================
-- FIX_COLUNAS_SALES_MYSQL57.sql
-- Adiciona colunas faltantes na tabela SALES (compatível MySQL 5.7+)
-- ============================================================

-- Verifica e adiciona coluna chave_acesso_nfe
SET @col_exists = (SELECT COUNT(*) FROM information_schema.columns 
                   WHERE table_schema = DATABASE() 
                   AND table_name = 'sales' 
                   AND column_name = 'chave_acesso_nfe');

SET @sql = IF(@col_exists = 0, 
              'ALTER TABLE sales ADD COLUMN chave_acesso_nfe VARCHAR(44) DEFAULT NULL', 
              'SELECT "Coluna chave_acesso_nfe já existe"');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Verifica e adiciona coluna numero_nfe
SET @col_exists = (SELECT COUNT(*) FROM information_schema.columns 
                   WHERE table_schema = DATABASE() 
                   AND table_name = 'sales' 
                   AND column_name = 'numero_nfe');

SET @sql = IF(@col_exists = 0, 
              'ALTER TABLE sales ADD COLUMN numero_nfe VARCHAR(20) DEFAULT NULL', 
              'SELECT "Coluna numero_nfe já existe"');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Verifica e adiciona coluna status_nfe
SET @col_exists = (SELECT COUNT(*) FROM information_schema.columns 
                   WHERE table_schema = DATABASE() 
                   AND table_name = 'sales' 
                   AND column_name = 'status_nfe');

SET @sql = IF(@col_exists = 0, 
              'ALTER TABLE sales ADD COLUMN status_nfe VARCHAR(20) DEFAULT NULL', 
              'SELECT "Coluna status_nfe já existe"');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Verifica e adiciona coluna chave_acesso_nfce
SET @col_exists = (SELECT COUNT(*) FROM information_schema.columns 
                   WHERE table_schema = DATABASE() 
                   AND table_name = 'sales' 
                   AND column_name = 'chave_acesso_nfce');

SET @sql = IF(@col_exists = 0, 
              'ALTER TABLE sales ADD COLUMN chave_acesso_nfce VARCHAR(44) DEFAULT NULL', 
              'SELECT "Coluna chave_acesso_nfce já existe"');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Verifica e adiciona coluna numero_nfce
SET @col_exists = (SELECT COUNT(*) FROM information_schema.columns 
                   WHERE table_schema = DATABASE() 
                   AND table_name = 'sales' 
                   AND column_name = 'numero_nfce');

SET @sql = IF(@col_exists = 0, 
              'ALTER TABLE sales ADD COLUMN numero_nfce VARCHAR(20) DEFAULT NULL', 
              'SELECT "Coluna numero_nfce já existe"');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Verifica e adiciona coluna seller_id
SET @col_exists = (SELECT COUNT(*) FROM information_schema.columns 
                   WHERE table_schema = DATABASE() 
                   AND table_name = 'sales' 
                   AND column_name = 'seller_id');

SET @sql = IF(@col_exists = 0, 
              'ALTER TABLE sales ADD COLUMN seller_id INT DEFAULT NULL', 
              'SELECT "Coluna seller_id já existe"');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Adiciona índice para seller_id se não existir
SET @idx_exists = (SELECT COUNT(*) FROM information_schema.statistics 
                   WHERE table_schema = DATABASE() 
                   AND table_name = 'sales' 
                   AND index_name = 'idx_seller');

SET @sql = IF(@idx_exists = 0, 
              'ALTER TABLE sales ADD INDEX idx_seller (seller_id)', 
              'SELECT "Índice idx_seller já existe"');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SELECT 'Colunas da tabela SALES atualizadas com sucesso!' AS resultado;
