# rabbitmq_client.py
import json
import pika
from config import RABBITMQ_URL, QUEUE_INMEDIATAS
import logging

logger = logging.getLogger(__name__)

class RabbitMQClient:
    def __init__(self):
        self.connection = None
        self.channel = None
        
    def connect(self):
        """Establecer conexión a RabbitMQ"""
        try:
            parameters = pika.URLParameters(RABBITMQ_URL)
            self.connection = pika.BlockingConnection(parameters)
            self.channel = self.connection.channel()
            
            # Declarar exchange y queue para inmediatas
            self.channel.exchange_declare(
                exchange='despacho.inmediatas',
                exchange_type='direct',
                durable=True
            )
            self.channel.queue_declare(
                queue='ordenes_inmediatas',
                durable=True
            )
            self.channel.queue_bind(
                exchange='despacho.inmediatas',
                queue='ordenes_inmediatas',
                routing_key='inmediata'
            )
            
            logger.info("Conectado a RabbitMQ")
        except Exception as e:
            logger.error(f"Error conectando a RabbitMQ: {e}")
            raise
    
    def publish_orden_inmediata(self, orden_data):
        """Publicar una orden inmediata a la cola"""
        if not self.channel:
            self.connect()
            
        try:
            self.channel.basic_publish(
                exchange='despacho.inmediatas',
                routing_key='inmediata',
                body=json.dumps(orden_data),
                properties=pika.BasicProperties(
                    delivery_mode=2,  # Persistente
                    content_type='application/json'
                )
            )
            logger.info(f"Orden publicada: {orden_data.get('id_venta')}")
        except Exception as e:
            logger.error(f"Error publicando orden: {e}")
            self.reconnect()
            # Reintentar
            self.publish_orden_inmediata(orden_data)
    
    def reconnect(self):
        """Reconectar si hay problemas"""
        try:
            if self.connection and not self.connection.is_closed:
                self.connection.close()
        except:
            pass
        
        self.connect()
    
    def close(self):
        """Cerrar conexión"""
        if self.connection and not self.connection.is_closed:
            self.connection.close()