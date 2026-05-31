-- =====================================================
-- Alterar coluna role para aceitar mecanico, atendente, auxiliar
-- =====================================================

-- Verificar a estrutura atual primeiro
DESCRIBE users;

-- Alterar a coluna role para ENUM expandido (se for ENUM)
ALTER TABLE users 
MODIFY COLUMN role ENUM('admin','manager','user','mecanico','atendente','auxiliar') 
NOT NULL DEFAULT 'user';

-- Ou, se preferir VARCHAR (mais flexível para futuras funções):
-- ALTER TABLE users 
-- MODIFY COLUMN role VARCHAR(20) 
-- NOT NULL DEFAULT 'user';

-- Verificar se a alteração foi aplicada
SELECT COLUMN_TYPE 
FROM INFORMATION_SCHEMA.COLUMNS 
WHERE TABLE_SCHEMA = DATABASE() 
  AND TABLE_NAME = 'users' 
  AND COLUMN_NAME = 'role';

-- Atualizar usuários de teste (opcional)
-- UPDATE users SET role = 'mecanico' WHERE username = 'mecanico1' AND role = 'user';
-- UPDATE users SET role = 'atendente' WHERE username = 'atendente1' AND role = 'user';
