import os
import sys
import mysql.connector
import json
from datetime import datetime
import requests
import time

# Carregar .env se disponível
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# =========================================
# CONFIGURAÇÕES — lê do ambiente (.env / config.py)
# =========================================
MYSQL_CONFIG = {
    "host":     os.getenv('DB_HOST', 'localhost'),
    "user":     os.getenv('DB_USER', 'root'),
    "password": os.getenv('DB_PASSWORD', 'Root@1234!'),
    "database": os.getenv('DB_NAME', 'supply_chain_mecanica'),
}

STATUS_FILE = os.path.join(os.path.dirname(__file__), 'geocodificacao_status.json')

# =========================================
# CONFIGURAÇÃO DA API DE GEOCODIFICAÇÃO
# =========================================
# ⚠️ COLE SUA API KEY DO HERE MAPS AQUI:
HERE_MAPS_API_KEY = "elCXcTWBwxAD1S9YY1ZgiBXDO3v7cfHHqg_VyJCgOak"

# =========================================
# 🗺️ VALIDAÇÃO GEOGRÁFICA - BOUNDING BOX POR ESTADO
# =========================================
# Limites geográficos aproximados dos estados brasileiros
# Usado para VALIDAR se as coordenadas retornadas estão dentro do estado correto
ESTADOS_BBOX = {
    'AC': {'min_lat': -11.2, 'max_lat': -7.0, 'min_lng': -74.0, 'max_lng': -66.5},
    'AL': {'min_lat': -10.5, 'max_lat': -8.8, 'min_lng': -38.3, 'max_lng': -35.1},
    'AP': {'min_lat': -4.5, 'max_lat': 2.5, 'min_lng': -54.9, 'max_lng': -49.8},
    'AM': {'min_lat': -9.8, 'max_lat': 2.3, 'min_lng': -73.8, 'max_lng': -56.1},
    'BA': {'min_lat': -18.5, 'max_lat': -8.5, 'min_lng': -46.6, 'max_lng': -37.3},
    'CE': {'min_lat': -7.9, 'max_lat': -2.8, 'min_lng': -41.4, 'max_lng': -37.3},
    'DF': {'min_lat': -16.1, 'max_lat': -15.5, 'min_lng': -48.3, 'max_lng': -47.3},
    'ES': {'min_lat': -21.3, 'max_lat': -17.9, 'min_lng': -41.9, 'max_lng': -39.7},
    'GO': {'min_lat': -19.5, 'max_lat': -12.4, 'min_lng': -53.3, 'max_lng': -45.9},
    'MA': {'min_lat': -10.3, 'max_lat': -1.0, 'min_lng': -48.6, 'max_lng': -41.8},
    'MT': {'min_lat': -18.1, 'max_lat': -7.3, 'min_lng': -61.6, 'max_lng': -50.2},
    'MS': {'min_lat': -24.1, 'max_lat': -17.2, 'min_lng': -58.2, 'max_lng': -50.9},
    'MG': {'min_lat': -22.9, 'max_lat': -14.2, 'min_lng': -51.1, 'max_lng': -39.9},
    'PA': {'min_lat': -9.9, 'max_lat': 2.6, 'min_lng': -58.9, 'max_lng': -46.0},
    'PB': {'min_lat': -8.3, 'max_lat': -6.0, 'min_lng': -38.8, 'max_lng': -34.8},
    'PR': {'min_lat': -26.7, 'max_lat': -22.5, 'min_lng': -54.6, 'max_lng': -48.0},
    'PE': {'min_lat': -9.5, 'max_lat': -7.2, 'min_lng': -41.4, 'max_lng': -34.8},
    'PI': {'min_lat': -10.9, 'max_lat': -2.7, 'min_lng': -45.9, 'max_lng': -40.4},
    'RJ': {'min_lat': -23.4, 'max_lat': -20.8, 'min_lng': -44.9, 'max_lng': -40.9},
    'RN': {'min_lat': -6.9, 'max_lat': -4.8, 'min_lng': -38.6, 'max_lng': -34.9},
    'RS': {'min_lat': -33.8, 'max_lat': -27.1, 'min_lng': -57.6, 'max_lng': -49.7},
    'RO': {'min_lat': -13.7, 'max_lat': -7.9, 'min_lng': -66.0, 'max_lng': -59.8},
    'RR': {'min_lat': -5.3, 'max_lat': 5.3, 'min_lng': -64.8, 'max_lng': -59.0},
    'SC': {'min_lat': -29.4, 'max_lat': -25.9, 'min_lng': -53.8, 'max_lng': -48.3},
    'SP': {'min_lat': -25.3, 'max_lat': -19.8, 'min_lng': -53.1, 'max_lng': -44.2},
    'SE': {'min_lat': -11.6, 'max_lat': -9.5, 'min_lng': -38.2, 'max_lng': -36.4},
    'TO': {'min_lat': -13.5, 'max_lat': -5.2, 'min_lng': -50.8, 'max_lng': -45.7}
}

# =========================================
# 🛡️ LIMITE DE SEGURANÇA (PROTEÇÃO DE CUSTOS)
# =========================================
# Here Maps FREE: 250.000 geocodificações/mês GRÁTIS
# Defina quantas você quer processar POR EXECUÇÃO:

LIMITE_MAXIMO_GEOCODIFICACOES = 200000  # ← EDITE AQUI!
# 
# Exemplos:
#   100000 = Processar 100 mil (sobram 150k para o mês)
#   200000 = Processar 200 mil (sobram 50k para o mês) ✅ CONFIGURADO
#   250000 = Usar todo o limite FREE

# =========================================
# 📊 CONTADORES PERSISTENTES (salvos em arquivo)
# =========================================
CONTADOR_FILE = os.path.join(os.path.dirname(__file__), 'geocodificacao_contador.json')

def carregar_contador():
    """Carrega contador de requisições do arquivo com reset automático mensal"""
    if os.path.exists(CONTADOR_FILE):
        try:
            with open(CONTADOR_FILE, 'r') as f:
                data = json.load(f)
                
                # Verificar se passou 30 dias desde o último reset
                if 'data_inicio' in data:
                    from datetime import datetime, timedelta
                    data_inicio = datetime.fromisoformat(data['data_inicio'])
                    dias_passados = (datetime.now() - data_inicio).days
                    
                    if dias_passados >= 30:
                        print(f"[DEBUG] 🔄 RESET AUTOMÁTICO: {dias_passados} dias passados desde {data_inicio.strftime('%d/%m/%Y')}")
                        print(f"[DEBUG] ✅ Contador resetado! Novo ciclo de 30 dias iniciado.")
                        # Reset automático - novo mês
                        salvar_contador(0)
                        return 0
                
                return data.get('requisicoes_feitas', 0)
        except:
            return 0
    return 0

def salvar_contador(requisicoes):
    """Salva contador de requisições no arquivo"""
    # Preservar data_inicio se já existir
    data_inicio = datetime.now().isoformat()
    if os.path.exists(CONTADOR_FILE):
        try:
            with open(CONTADOR_FILE, 'r') as f:
                data_existente = json.load(f)
                if 'data_inicio' in data_existente:
                    data_inicio = data_existente['data_inicio']
        except:
            pass
    
    with open(CONTADOR_FILE, 'w') as f:
        json.dump({
            'requisicoes_feitas': requisicoes,
            'data_inicio': data_inicio,
            'ultima_atualizacao': datetime.now().isoformat()
        }, f, indent=2)

# Carregar contador do mês (persiste entre execuções)
requisicoes_feitas = carregar_contador()

# Contador de requisições economizadas (endereços inválidos filtrados)
requisicoes_economizadas = 0

# Contador de endereços duplicados (cache hits)
cache_hits = 0

# Cache de geocodificação (endereço completo → lat/lng)
geocode_cache = {}

# =========================================
# FUNÇÃO - ATUALIZAR STATUS
# =========================================
def update_status(status_data):
    """Atualiza arquivo JSON com status da geocodificação"""
    with open(STATUS_FILE, 'w', encoding='utf-8') as f:
        json.dump(status_data, f, ensure_ascii=False, indent=2)

# =========================================
# FUNÇÃO - GEOCODIFICAR ENDEREÇO (HERE MAPS API)
# =========================================
def geocode_address(logradouro, numero, bairro, municipio, uf, cep):
    """
    Geocodifica um endereço usando Here Maps API
    
    Args:
        logradouro: Nome da rua
        numero: Número
        bairro: Bairro
        municipio: Cidade
        uf: Estado (sigla)
        cep: CEP
    
    Returns:
        tuple: (latitude, longitude) ou (None, None) se não encontrado
    """
    try:
        # Validar API Key
        if not HERE_MAPS_API_KEY or HERE_MAPS_API_KEY == "COLE_SUA_API_KEY_AQUI":
            print("[DEBUG] ⚠️ ERRO: API Key do Here Maps não configurada!")
            print("[DEBUG] Edite o arquivo geocodificar_empresas.py e cole sua API Key")
            return (None, None)
        
        # 🛡️ VALIDAÇÃO: Evitar desperdício de requisições em endereços incompletos
        # Endereço MÍNIMO precisa ter: (Município + UF) ou (CEP)
        tem_municipio = municipio and str(municipio) not in ['None', 'nan', '']
        tem_uf = uf and str(uf) not in ['None', 'nan', '']
        tem_cep = cep and str(cep) not in ['None', 'nan', '']
        
        # Se não tem nem (cidade+UF) nem CEP, NÃO chamar API (economizar requisição!)
        if not ((tem_municipio and tem_uf) or tem_cep):
            global requisicoes_economizadas
            requisicoes_economizadas += 1
            geocode_cache[f"INVALID_{logradouro}_{numero}"] = (None, None)
            return (None, None)
        
        # 🎯 MONTAR ENDEREÇO OTIMIZADO
        # Priorizar: MUNICÍPIO + UF primeiro (mais importante para desambiguação)
        # Depois: CEP (muito preciso)
        # Por último: Logradouro + número
        parts = []
        
        # 1. MUNICÍPIO + UF (obrigatório para contexto)
        if tem_municipio and tem_uf:
            parts.append(f"{str(municipio)}, {str(uf)}")
        
        # 2. CEP (alta precisão)
        if tem_cep:
            cep_limpo = str(cep).replace('-', '').replace('.', '')
            parts.append(f"CEP {cep_limpo}")
        
        # 3. LOGRADOURO + NÚMERO
        if logradouro and str(logradouro) not in ['None', 'nan', '']:
            if numero and str(numero) not in ['None', 'nan', '']:
                parts.append(f"{str(logradouro)}, {str(numero)}")
            else:
                parts.append(str(logradouro))
        
        # 4. BAIRRO (opcional, mas útil)
        if bairro and str(bairro) not in ['None', 'nan', '']:
            parts.append(str(bairro))
        
        full_address = ", ".join(parts) + ", Brasil"
        
        # Verificar cache (endereços duplicados)
        if full_address in geocode_cache:
            global cache_hits
            cache_hits += 1
            return geocode_cache[full_address]
        
        # 🛡️ VERIFICAR LIMITE DE SEGURANÇA
        global requisicoes_feitas
        if requisicoes_feitas >= LIMITE_MAXIMO_GEOCODIFICACOES:
            print(f"[DEBUG] 🛑 LIMITE ATINGIDO! {requisicoes_feitas}/{LIMITE_MAXIMO_GEOCODIFICACOES} requisições")
            print(f"[DEBUG] Parando para evitar custos. Edite LIMITE_MAXIMO_GEOCODIFICACOES se quiser processar mais.")
            return (None, None)
        
        # Chamar API Here Maps
        url = 'https://geocode.search.hereapi.com/v1/geocode'
        params = {
            'q': full_address,
            'apiKey': HERE_MAPS_API_KEY,
            'limit': 1
        }
        
        # Rate limiting: Here Maps permite 25 req/seg, mas vamos ser conservadores
        time.sleep(0.05)  # 20 req/seg = ~72.000 req/hora
        
        response = requests.get(url, params=params, timeout=10)
        
        # Incrementar contador de requisições
        requisicoes_feitas += 1
        
        # Salvar contador a cada 10 requisições (persistir progresso)
        if requisicoes_feitas % 10 == 0:
            salvar_contador(requisicoes_feitas)
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get('items') and len(data['items']) > 0:
                position = data['items'][0]['position']
                lat = position['lat']
                lng = position['lng']
                
                # 🗺️ VALIDAÇÃO BBOX: Verificar se coordenadas estão dentro do estado
                if tem_uf and uf in ESTADOS_BBOX:
                    bbox = ESTADOS_BBOX[uf]
                    
                    # Verificar se está dentro dos limites
                    dentro_bbox = (
                        bbox['min_lat'] <= lat <= bbox['max_lat'] and
                        bbox['min_lng'] <= lng <= bbox['max_lng']
                    )
                    
                    if not dentro_bbox:
                        print(f"[DEBUG] ⚠️ COORDENADAS FORA DE {uf}!")
                        print(f"        Endereço: {full_address}")
                        print(f"        Retornado: {lat}, {lng}")
                        print(f"        Esperado: lat [{bbox['min_lat']}, {bbox['max_lat']}], lng [{bbox['min_lng']}, {bbox['max_lng']}]")
                        # Rejeitar resultado (pode ser cidade homônima em outro estado)
                        geocode_cache[full_address] = (None, None)
                        return (None, None)
                
                # ✅ Coordenadas válidas
                result = (lat, lng)
                geocode_cache[full_address] = result
                return result
            else:
                # Endereço não encontrado
                geocode_cache[full_address] = (None, None)
                return (None, None)
        else:
            print(f"[DEBUG] ⚠️ Erro HTTP {response.status_code}: {response.text}")
            return (None, None)
            
    except requests.exceptions.Timeout:
        print(f"[DEBUG] ⚠️ Timeout ao geocodificar: {full_address}")
        return (None, None)
    except Exception as e:
        print(f"[DEBUG] ⚠️ Erro inesperado: {e}")
        return (None, None)

# =========================================
# FUNÇÃO PRINCIPAL - GEOCODIFICAR EMPRESAS
# =========================================
def geocodificar_empresas_existentes(table_name="empresas_filtradas", batch_size=100):
    """
    Geocodifica empresas que já estão na base de dados
    Processa em lotes e faz UPDATE
    
    Args:
        table_name: Nome da tabela
        batch_size: Quantidade de registros por lote
    """
    print(f"[DEBUG] Iniciando geocodificação de empresas existentes na tabela '{table_name}'")
    print(f"[DEBUG] 📊 Requisições já utilizadas este mês: {requisicoes_feitas}/{LIMITE_MAXIMO_GEOCODIFICACOES}")
    print(f"[DEBUG] 🛡️ Requisições restantes até o limite: {LIMITE_MAXIMO_GEOCODIFICACOES - requisicoes_feitas}")
    
    status = {
        'status': 'processando',
        'etapa': 'Conectando ao banco de dados...',
        'total_registros': 0,
        'registros_processados': 0,
        'registros_geocodificados': 0,
        'registros_falha': 0,
        'percentual': 0,
        'requisicoes_api': requisicoes_feitas,  # Iniciar com contador salvo
        'requisicoes_economizadas': 0,
        'cache_hits': 0,
        'limite_maximo': LIMITE_MAXIMO_GEOCODIFICACOES,
        'inicio': datetime.now().isoformat()
    }
    update_status(status)
    
    try:
        # Conectar ao MySQL
        conn = mysql.connector.connect(**MYSQL_CONFIG)
        cursor = conn.cursor()
        
        # Contar total de registros SEM geocodificação (APENAS ATIVAS - situacao_cadastral = 2)
        status['etapa'] = 'Contando registros sem geocodificação (apenas empresas ativas)...'
        update_status(status)
        
        cursor.execute(f"""
            SELECT COUNT(*) 
            FROM {table_name} 
            WHERE (LATITUDE IS NULL OR LONGITUDE IS NULL)
            AND SITUACAO_CADASTRAL = 2
        """)
        total = cursor.fetchone()[0]
        status['total_registros'] = total
        
        print(f"[DEBUG] Total de registros sem geocodificação: {total}")
        
        if total == 0:
            status['status'] = 'concluido'
            status['etapa'] = 'Nenhum registro para geocodificar'
            status['percentual'] = 100
            update_status(status)
            conn.close()
            return
        
        # Buscar registros em lotes
        status['etapa'] = 'Iniciando geocodificação...'
        update_status(status)
        
        offset = 0
        while offset < total:
            # Buscar lote
            cursor.execute(f"""
                SELECT id, LOGRADOURO, NUMERO, BAIRRO, MUNICIPIO, UF, CEP
                FROM {table_name}
                WHERE (LATITUDE IS NULL OR LONGITUDE IS NULL)
                AND SITUACAO_CADASTRAL = 2
                ORDER BY id
                LIMIT %s OFFSET %s
            """, (batch_size, offset))
            
            batch = cursor.fetchall()
            
            if not batch:
                break
            print(f"[DEBUG] Processando lote {offset}-{offset+len(batch)} de {total}")
            status['etapa'] = f'Geocodificando registros {offset+1}-{offset+len(batch)} de {total}'
            update_status(status)
            
            # Geocodificar cada registro do lote
            for row in batch:
                id_empresa, logradouro, numero, bairro, municipio, uf, cep = row
                
                # Geocodificar
                lat, lng = geocode_address(logradouro, numero, bairro, municipio, uf, cep)
                
                # UPDATE no banco
                if lat and lng:
                    cursor.execute(f"""
                        UPDATE {table_name}
                        SET LATITUDE = %s, LONGITUDE = %s
                        WHERE id = %s
                    """, (lat, lng, id_empresa))
                    status['registros_geocodificados'] += 1
                    print(f"[DEBUG] ✓ ID {id_empresa}: {lat}, {lng}")
                else:
                    status['registros_falha'] += 1
                    print(f"[DEBUG] ✗ ID {id_empresa}: Não geocodificado")
                
                status['registros_processados'] += 1
                status['percentual'] = int((status['registros_processados'] / total) * 100)
                status['requisicoes_api'] = requisicoes_feitas
                status['requisicoes_economizadas'] = requisicoes_economizadas
                status['cache_hits'] = cache_hits
                
                # 🛡️ Verificar se atingiu o limite
                if requisicoes_feitas >= LIMITE_MAXIMO_GEOCODIFICACOES:
                    print(f"[DEBUG] 🛑 LIMITE ATINGIDO! Parando geocodificação.")
                    status['status'] = 'limite_atingido'
                    status['etapa'] = f'🛑 Limite atingido: {requisicoes_feitas}/{LIMITE_MAXIMO_GEOCODIFICACOES} requisições. Geocodificados: {status["registros_geocodificados"]}'
                    update_status(status)
                    cursor.close()
                    conn.close()
                    return
                
                # Atualizar status a cada 10 registros
                if status['registros_processados'] % 10 == 0:
                    update_status(status)
            
            # Commit do lote
            conn.commit()
            print(f"[DEBUG] ✓ Lote {offset}-{offset+len(batch)} commitado")
            
            offset += batch_size
        
        # Finalizar
        cursor.close()
        conn.close()
        
        status['status'] = 'concluido'
        status['etapa'] = f'Geocodificação concluída! {status["registros_geocodificados"]} sucesso, {status["registros_falha"]} falhas'
        status['percentual'] = 100
        status['fim'] = datetime.now().isoformat()
        update_status(status)
        
        print(f"[DEBUG] ✓ Geocodificação concluída!")
        print(f"[DEBUG]   - Total processados: {status['registros_processados']}")
        print(f"[DEBUG]   - Geocodificados: {status['registros_geocodificados']}")
        print(f"[DEBUG]   - Falhas: {status['registros_falha']}")
        
    except Exception as e:
        print(f"[DEBUG] ✗ Erro na geocodificação: {e}")
        status['status'] = 'erro'
        status['erro'] = str(e)
        status['etapa'] = f'Erro: {str(e)}'
        update_status(status)
        raise

# =========================================
# EXECUTAR SE CHAMADO DIRETAMENTE
# =========================================
if __name__ == "__main__":
    geocodificar_empresas_existentes()
