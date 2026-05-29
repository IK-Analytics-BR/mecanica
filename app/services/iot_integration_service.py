"""
Serviço para integração com dispositivos IoT.

Este serviço fornece métodos para integrar o CMMS com dispositivos IoT,
permitindo a coleta automática de dados de equipamentos, como leituras de horímetro,
temperatura, vibração e outros parâmetros de monitoramento.
"""

import json
import requests
import logging
from datetime import datetime

try:
    import paho.mqtt.client as mqtt
    _MQTT_AVAILABLE = True
except ImportError:
    mqtt = None
    _MQTT_AVAILABLE = False
    logging.getLogger(__name__).warning("[IoT] paho-mqtt não instalado — integração MQTT desativada")
from database import get_db
from utils.config_manager import ConfigManager
from services.wear_service import WearService

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class IoTIntegrationService:
    """Serviço para integração com dispositivos IoT."""
    
    def __init__(self):
        """Inicializa o serviço de integração com IoT."""
        self.config = ConfigManager().get_config('iot_integration')
        self.mqtt_broker = self.config.get('mqtt_broker', '')
        self.mqtt_port = self.config.get('mqtt_port', 1883)
        self.mqtt_username = self.config.get('mqtt_username', '')
        self.mqtt_password = self.config.get('mqtt_password', '')
        self.mqtt_topic_prefix = self.config.get('mqtt_topic_prefix', 'cmms/equipment/')
        self.rest_api_url = self.config.get('rest_api_url', '')
        self.rest_api_key = self.config.get('rest_api_key', '')
        self.enabled = self.config.get('enabled', False)
        self.integration_type = self.config.get('integration_type', 'mqtt')  # mqtt ou rest
        self.mqtt_client = None
        self.device_mappings = self.config.get('device_mappings', {})
    
    def is_enabled(self):
        """Verifica se a integração está habilitada."""
        if not self.enabled:
            return False
        
        if self.integration_type == 'mqtt':
            return bool(self.mqtt_broker)
        elif self.integration_type == 'rest':
            return bool(self.rest_api_url)
        
        return False
    
    def connect_mqtt(self):
        """Conecta ao broker MQTT."""
        if not self.is_enabled() or self.integration_type != 'mqtt':
            return {'success': False, 'message': 'Integração MQTT não está configurada.'}
        if not _MQTT_AVAILABLE:
            return {'success': False, 'message': 'paho-mqtt não instalado no servidor.'}
        
        try:
            # Criar cliente MQTT
            client_id = f'cmms-{datetime.now().timestamp()}'
            self.mqtt_client = mqtt.Client(client_id)
            
            # Configurar callbacks
            self.mqtt_client.on_connect = self._on_connect
            self.mqtt_client.on_message = self._on_message
            self.mqtt_client.on_disconnect = self._on_disconnect
            
            # Configurar autenticação se necessário
            if self.mqtt_username and self.mqtt_password:
                self.mqtt_client.username_pw_set(self.mqtt_username, self.mqtt_password)
            
            # Conectar ao broker
            self.mqtt_client.connect(self.mqtt_broker, self.mqtt_port, 60)
            
            # Iniciar loop em segundo plano
            self.mqtt_client.loop_start()
            
            return {'success': True, 'message': 'Conectado ao broker MQTT com sucesso.'}
        
        except Exception as e:
            logger.error(f"Erro ao conectar ao broker MQTT: {str(e)}")
            return {'success': False, 'message': f'Erro ao conectar ao broker MQTT: {str(e)}'}
    
    def disconnect_mqtt(self):
        """Desconecta do broker MQTT."""
        if self.mqtt_client:
            try:
                self.mqtt_client.loop_stop()
                self.mqtt_client.disconnect()
                self.mqtt_client = None
                return {'success': True, 'message': 'Desconectado do broker MQTT com sucesso.'}
            except Exception as e:
                logger.error(f"Erro ao desconectar do broker MQTT: {str(e)}")
                return {'success': False, 'message': f'Erro ao desconectar do broker MQTT: {str(e)}'}
        
        return {'success': True, 'message': 'Não estava conectado ao broker MQTT.'}
    
    def _on_connect(self, client, userdata, flags, rc):
        """Callback para quando a conexão MQTT é estabelecida."""
        if rc == 0:
            logger.info("Conectado ao broker MQTT")
            
            # Inscrever-se nos tópicos relevantes
            topic = f"{self.mqtt_topic_prefix}+/data"
            client.subscribe(topic)
            logger.info(f"Inscrito no tópico: {topic}")
        else:
            logger.error(f"Falha ao conectar ao broker MQTT, código de retorno: {rc}")
    
    def _on_message(self, client, userdata, msg):
        """Callback para quando uma mensagem MQTT é recebida."""
        try:
            logger.info(f"Mensagem recebida no tópico {msg.topic}")
            
            # Extrair ID do equipamento do tópico
            # Formato esperado: cmms/equipment/{equipment_id}/data
            topic_parts = msg.topic.split('/')
            if len(topic_parts) >= 3:
                device_id = topic_parts[2]
                
                # Verificar se o dispositivo está mapeado para um equipamento
                equipment_id = self.device_mappings.get(device_id)
                
                if equipment_id:
                    # Processar dados
                    payload = json.loads(msg.payload.decode())
                    self._process_equipment_data(equipment_id, payload)
                else:
                    logger.warning(f"Dispositivo não mapeado: {device_id}")
            
        except Exception as e:
            logger.error(f"Erro ao processar mensagem MQTT: {str(e)}")
    
    def _on_disconnect(self, client, userdata, rc):
        """Callback para quando a conexão MQTT é perdida."""
        if rc != 0:
            logger.warning("Desconexão inesperada do broker MQTT")
            # Tentar reconectar após um tempo
            # Isso seria implementado em um ambiente de produção
    
    def _process_equipment_data(self, equipment_id, data):
        """
        Processa dados recebidos de um equipamento.
        
        Args:
            equipment_id (int): ID do equipamento no CMMS
            data (dict): Dados recebidos do dispositivo IoT
        """
        try:
            db = get_db()
            
            # Verificar se o equipamento existe
            equipment = db.fetch_one("SELECT id FROM equipment WHERE id = %s", (equipment_id,))
            if not equipment:
                logger.warning(f"Equipamento não encontrado: {equipment_id}")
                return
            
            # Processar leitura de horímetro
            if 'hour_meter' in data:
                hour_meter_value = data['hour_meter']
                
                # Registrar leitura de horímetro
                db.insert("""
                    INSERT INTO hour_meter_readings
                    (equipment_id, reading_value, reading_date, source)
                    VALUES (%s, %s, NOW(), 'iot')
                """, (equipment_id, hour_meter_value))
                
                # Atualizar desgaste do equipamento
                WearService.update_equipment_wear(equipment_id)
                
                logger.info(f"Leitura de horímetro registrada para equipamento {equipment_id}: {hour_meter_value}")
            
            # Processar leituras de sensores
            if 'sensors' in data:
                sensors = data['sensors']
                
                for sensor_type, value in sensors.items():
                    # Registrar leitura de sensor
                    db.insert("""
                        INSERT INTO sensor_readings
                        (equipment_id, sensor_type, sensor_value, reading_date)
                        VALUES (%s, %s, %s, NOW())
                    """, (equipment_id, sensor_type, value))
                
                logger.info(f"Leituras de sensores registradas para equipamento {equipment_id}")
            
            # Processar alertas
            if 'alerts' in data:
                alerts = data['alerts']
                
                for alert in alerts:
                    alert_type = alert.get('type')
                    message = alert.get('message')
                    priority = alert.get('priority', 'medium')
                    
                    # Criar alerta no sistema
                    db.insert("""
                        INSERT INTO alerts
                        (equipment_id, alert_type, status, message, priority, created_at)
                        VALUES (%s, %s, 'active', %s, %s, NOW())
                    """, (equipment_id, alert_type, message, priority))
                
                logger.info(f"Alertas registrados para equipamento {equipment_id}")
            
        except Exception as e:
            logger.error(f"Erro ao processar dados do equipamento {equipment_id}: {str(e)}")
    
    def fetch_data_from_api(self):
        """Busca dados da API REST de IoT."""
        if not self.is_enabled() or self.integration_type != 'rest':
            return {'success': False, 'message': 'Integração REST API não está configurada.'}
        
        try:
            headers = {'Authorization': f'Bearer {self.rest_api_key}'} if self.rest_api_key else {}
            response = requests.get(f"{self.rest_api_url}/devices/data", headers=headers, timeout=30)
            
            if response.status_code != 200:
                return {
                    'success': False, 
                    'message': f'Erro ao obter dados da API IoT. Status: {response.status_code}',
                    'details': response.text
                }
            
            devices_data = response.json()
            
            # Processar dados de cada dispositivo
            processed_count = 0
            for device_data in devices_data:
                device_id = device_data.get('device_id')
                equipment_id = self.device_mappings.get(device_id)
                
                if equipment_id:
                    self._process_equipment_data(equipment_id, device_data)
                    processed_count += 1
            
            return {
                'success': True, 
                'message': f'Dados de {processed_count} dispositivos IoT processados com sucesso.'
            }
            
        except Exception as e:
            logger.error(f"Erro ao buscar dados da API IoT: {str(e)}")
            return {'success': False, 'message': f'Erro ao buscar dados da API IoT: {str(e)}'}
    
    def register_device(self, device_id, equipment_id):
        """
        Registra um dispositivo IoT para um equipamento.
        
        Args:
            device_id (str): ID do dispositivo IoT
            equipment_id (int): ID do equipamento no CMMS
            
        Returns:
            dict: Resultado do registro
        """
        try:
            # Verificar se o equipamento existe
            db = get_db()
            equipment = db.fetch_one("SELECT id FROM equipment WHERE id = %s", (equipment_id,))
            
            if not equipment:
                return {'success': False, 'message': f'Equipamento não encontrado: {equipment_id}'}
            
            # Atualizar mapeamento de dispositivos
            device_mappings = self.device_mappings.copy()
            device_mappings[device_id] = equipment_id
            
            # Salvar configuração
            ConfigManager().update_config('iot_integration', {'device_mappings': device_mappings})
            
            # Atualizar mapeamento local
            self.device_mappings = device_mappings
            
            return {
                'success': True, 
                'message': f'Dispositivo {device_id} registrado para o equipamento {equipment_id}.'
            }
            
        except Exception as e:
            logger.error(f"Erro ao registrar dispositivo: {str(e)}")
            return {'success': False, 'message': f'Erro ao registrar dispositivo: {str(e)}'}
    
    def unregister_device(self, device_id):
        """
        Remove o registro de um dispositivo IoT.
        
        Args:
            device_id (str): ID do dispositivo IoT
            
        Returns:
            dict: Resultado da remoção
        """
        try:
            # Atualizar mapeamento de dispositivos
            device_mappings = self.device_mappings.copy()
            
            if device_id in device_mappings:
                del device_mappings[device_id]
                
                # Salvar configuração
                ConfigManager().update_config('iot_integration', {'device_mappings': device_mappings})
                
                # Atualizar mapeamento local
                self.device_mappings = device_mappings
                
                return {
                    'success': True, 
                    'message': f'Registro do dispositivo {device_id} removido com sucesso.'
                }
            else:
                return {'success': False, 'message': f'Dispositivo {device_id} não encontrado.'}
            
        except Exception as e:
            logger.error(f"Erro ao remover registro de dispositivo: {str(e)}")
            return {'success': False, 'message': f'Erro ao remover registro de dispositivo: {str(e)}'}
    
    def get_registered_devices(self):
        """
        Retorna a lista de dispositivos IoT registrados.
        
        Returns:
            list: Lista de dispositivos registrados
        """
        devices = []
        
        try:
            db = get_db()
            
            for device_id, equipment_id in self.device_mappings.items():
                # Buscar informações do equipamento
                equipment = db.fetch_one("""
                    SELECT id, name, model, serial_number
                    FROM equipment
                    WHERE id = %s
                """, (equipment_id,))
                
                if equipment:
                    devices.append({
                        'device_id': device_id,
                        'equipment_id': equipment_id,
                        'equipment_name': equipment['name'],
                        'equipment_model': equipment['model'],
                        'equipment_serial': equipment['serial_number']
                    })
            
            return devices
            
        except Exception as e:
            logger.error(f"Erro ao buscar dispositivos registrados: {str(e)}")
            return []
    
    def test_connection(self):
        """
        Testa a conexão com o sistema IoT.
        
        Returns:
            dict: Resultado do teste
        """
        if not self.is_enabled():
            return {'success': False, 'message': 'Integração com IoT não está configurada.'}
        
        try:
            if self.integration_type == 'mqtt':
                # Testar conexão MQTT
                client_id = f'cmms-test-{datetime.now().timestamp()}'
                client = mqtt.Client(client_id)
                
                if self.mqtt_username and self.mqtt_password:
                    client.username_pw_set(self.mqtt_username, self.mqtt_password)
                
                client.connect(self.mqtt_broker, self.mqtt_port, 5)
                client.disconnect()
                
                return {'success': True, 'message': 'Conexão MQTT testada com sucesso.'}
                
            elif self.integration_type == 'rest':
                # Testar conexão REST API
                headers = {'Authorization': f'Bearer {self.rest_api_key}'} if self.rest_api_key else {}
                response = requests.get(f"{self.rest_api_url}/status", headers=headers, timeout=10)
                
                if response.status_code == 200:
                    return {'success': True, 'message': 'Conexão REST API testada com sucesso.'}
                else:
                    return {
                        'success': False, 
                        'message': f'Erro ao conectar à API IoT. Status: {response.status_code}',
                        'details': response.text
                    }
            
            return {'success': False, 'message': f'Tipo de integração não suportado: {self.integration_type}'}
            
        except Exception as e:
            logger.error(f"Erro ao testar conexão com IoT: {str(e)}")
            return {'success': False, 'message': f'Erro ao testar conexão com IoT: {str(e)}'}
    
    def get_iot_status(self):
        """
        Retorna o status da integração com IoT.
        
        Returns:
            dict: Status da integração
        """
        return {
            'enabled': self.is_enabled(),
            'integration_type': self.integration_type,
            'mqtt_broker': self.mqtt_broker if self.integration_type == 'mqtt' else None,
            'mqtt_port': self.mqtt_port if self.integration_type == 'mqtt' else None,
            'rest_api_url': self.rest_api_url if self.integration_type == 'rest' else None,
            'device_count': len(self.device_mappings)
        }
    
    def update_config(self, config_data):
        """
        Atualiza a configuração da integração com IoT.
        
        Args:
            config_data (dict): Novos dados de configuração
            
        Returns:
            dict: Resultado da atualização
        """
        try:
            # Validar configuração
            if 'integration_type' in config_data:
                if config_data['integration_type'] not in ['mqtt', 'rest']:
                    return {'success': False, 'message': 'Tipo de integração inválido. Deve ser mqtt ou rest.'}
            
            # Desconectar MQTT se estiver conectado
            if self.mqtt_client:
                self.disconnect_mqtt()
            
            # Atualizar configuração
            ConfigManager().update_config('iot_integration', config_data)
            
            # Recarregar configuração
            self.__init__()
            
            # Reconectar MQTT se necessário
            if self.is_enabled() and self.integration_type == 'mqtt':
                self.connect_mqtt()
            
            return {'success': True, 'message': 'Configuração da integração com IoT atualizada com sucesso.'}
        
        except Exception as e:
            logger.error(f"Erro ao atualizar configuração da integração com IoT: {str(e)}")
            return {'success': False, 'message': f'Erro ao atualizar configuração: {str(e)}'}
    
    def start_integration(self):
        """
        Inicia a integração com IoT.
        
        Returns:
            dict: Resultado da inicialização
        """
        if not self.is_enabled():
            return {'success': False, 'message': 'Integração com IoT não está configurada.'}
        
        try:
            if self.integration_type == 'mqtt':
                return self.connect_mqtt()
            elif self.integration_type == 'rest':
                return {'success': True, 'message': 'Integração REST API iniciada. Use fetch_data_from_api() para buscar dados.'}
            else:
                return {'success': False, 'message': f'Tipo de integração não suportado: {self.integration_type}'}
        
        except Exception as e:
            logger.error(f"Erro ao iniciar integração com IoT: {str(e)}")
            return {'success': False, 'message': f'Erro ao iniciar integração com IoT: {str(e)}'}
    
    def stop_integration(self):
        """
        Para a integração com IoT.
        
        Returns:
            dict: Resultado da parada
        """
        if self.integration_type == 'mqtt':
            return self.disconnect_mqtt()
        else:
            return {'success': True, 'message': 'Integração parada com sucesso.'}
