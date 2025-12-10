# workers/inmediato.py
import sys
import psycopg2
import json
import time
import logging
import os
import pika
sys.path.insert(0, '/app')

from config import RABBITMQ_URL, DB_HOST, DB_PORT, DB_USER, DB_PASS, DB_NAME
from inventario.client import InventarioClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ===========================================
# FUNCIONES DE CONEXIÓN
# ===========================================
def get_db_connection():
    """Obtener conexión a PostgreSQL"""
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        port=DB_PORT
    )

def wait_for_database(max_retries=10, retry_delay=5):
    """Esperar a que la base de datos esté disponible"""
    logger.info("⏳ Esperando conexión a base de datos...")
    
    for attempt in range(max_retries):
        try:
            conn = get_db_connection()
            conn.close()
            logger.info(f"✅ Conectado a la base de datos (intento {attempt+1}/{max_retries})")
            return True
        except psycopg2.OperationalError as e:
            if attempt < max_retries - 1:
                logger.warning(f"⏳ BD no disponible, reintentando en {retry_delay}s...")
                time.sleep(retry_delay)
            else:
                logger.error(f"❌ Máximos reintentos de BD alcanzados: {e}")
                return False
    
    return False

def wait_for_inventory(max_retries=float('inf'), retry_delay=30):
    """Esperar a que el inventario esté disponible"""
    logger.info("⏳ Verificando conexión a inventario...")
    
    inventario = InventarioClient()
    retries = 0
    
    while retries < max_retries:
        try:
            if inventario.check_health():
                logger.info("✅ Inventario disponible")
                return True
        except Exception as e:
            logger.debug(f"Health check falló: {e}")
        
        retries += 1
        logger.warning(f"⏳ Inventario no disponible (intento {retries}), reintentando en {retry_delay}s...")
        time.sleep(retry_delay)
    
    logger.error("❌ No se pudo conectar al inventario")
    return False

def create_rabbitmq_connection(max_retries=10, retry_delay=5):
    """Crear conexión a RabbitMQ con reintentos"""
    logger.info("⏳ Esperando 15s para inicialización de RabbitMQ...")
    time.sleep(15)
    
    logger.info("⏳ Intentando conectar a RabbitMQ...")
    
    for attempt in range(max_retries):
        try:
            logger.info(f"🔌 Intentando conectar a RabbitMQ (intento {attempt + 1}/{max_retries})...")
            
            connection = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
            channel = connection.channel()
            
            # Configurar queue y exchange
            channel.queue_declare(queue='ordenes_inmediatas', durable=True)
            channel.exchange_declare(
                exchange='despacho.inmediatas',
                exchange_type='direct',
                durable=True
            )
            
            channel.basic_qos(prefetch_count=1)
            
            logger.info("✅ Conectado a RabbitMQ exitosamente")
            return connection, channel
            
        except pika.exceptions.ProbableAccessDeniedError as e:
            error_msg = str(e)
            
            if "vhost not found" in error_msg:
                logger.warning("⚠️ RabbitMQ creando vhost, reintentando en 10s...")
                time.sleep(10)
                continue
            
            elif "access to vhost" in error_msg:
                logger.warning("⚠️ RabbitMQ configurando permisos, reintentando en 10s...")
                time.sleep(10)
                continue
            
            else:
                logger.error(f"❌ Error de permisos/vhost permanente: {e}")
                raise
                
        except (pika.exceptions.AMQPConnectionError, pika.exceptions.AMQPChannelError) as e:
            if attempt < max_retries - 1:
                logger.warning(f"⚠️ Conexión fallada, reintentando en {retry_delay}s...")
                time.sleep(retry_delay)
            else:
                logger.error(f"❌ Máximos reintentos alcanzados: {e}")
                raise
    
    raise Exception("No se pudo conectar a RabbitMQ después de todos los intentos")

# ===========================================
# PROCESAMIENTO DE MENSAJES
# ===========================================
def procesar_mensaje(ch, method, properties, body):
    """Callback para procesar mensajes de RabbitMQ"""
    conn = None
    cursor = None
    
    try:
        # 1. Parsear mensaje
        orden = json.loads(body)
        orden_id = orden.get('orden_id')
        id_venta = orden.get('id_venta', 'N/A')
        
        if not orden_id:
            logger.error("❌ Mensaje sin ID de orden")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            return
        
        logger.info(f"🔍 Procesando orden: {id_venta} (ID: {orden_id})")
        
        # 2. Verificar orden en base de datos
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT 1 FROM ordenes WHERE id = %s AND estado != 'despachada' FOR UPDATE SKIP LOCKED",
            (orden_id,)
        )
        
        if not cursor.fetchone():
            logger.warning(f"⚠️ Orden {orden_id} no encontrada o ya despachada")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            return
        
        # 3. Procesar inventario
        inventario = InventarioClient()
        detalles = orden.get('detalles', [])
        
        if not detalles:
            logger.error(f"❌ Orden {orden_id} sin detalles")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            return
        
        for detalle in detalles:
            producto_id = detalle.get('id_producto')
            cantidad = detalle.get('cantidad', 0)
            
            if not producto_id or cantidad <= 0:
                logger.error(f"❌ Detalle inválido en orden {orden_id}")
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
                return
            
            if not inventario.restar_stock_despacho(producto_id, cantidad):
                logger.error(f"❌ Error en inventario para producto {producto_id}")
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
                return
        
        # 4. Marcar como despachada
        cursor.execute(
            "UPDATE ordenes SET estado = 'despachada' WHERE id = %s",
            (orden_id,)
        )
        conn.commit()
        
        logger.info(f"✅ Orden {id_venta} despachada exitosamente")
        ch.basic_ack(delivery_tag=method.delivery_tag)
        
    except json.JSONDecodeError as e:
        logger.error(f"❌ Error decodificando JSON: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
    except Exception as e:
        logger.error(f"❌ Error procesando mensaje: {e}", exc_info=True)
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# ===========================================
# FUNCIÓN PRINCIPAL
# ===========================================
def main():
    """Worker principal - Punto de entrada"""
    logger.info("🚀 Iniciando worker inmediato...")
    
    # 1. Esperar por base de datos
    if not wait_for_database():
        logger.error("❌ No se pudo conectar a la base de datos. Saliendo.")
        return
    
    # 2. Esperar por inventario
    if not wait_for_inventory(max_retries=10, retry_delay=10):
        logger.error("❌ No se pudo conectar al inventario. Saliendo.")
        return
    
    # 3. Crear conexión a RabbitMQ
    try:
        connection, channel = create_rabbitmq_connection()
    except Exception as e:
        logger.error(f"❌ Error conectando a RabbitMQ: {e}")
        return
    
    # 4. Configurar consumo
    channel.basic_consume(
        queue='ordenes_inmediatas',
        on_message_callback=procesar_mensaje,
        auto_ack=False
    )
    
    logger.info("✅ Worker inmediato iniciado y listo para procesar órdenes")
    logger.info("📊 Esperando mensajes. Presiona Ctrl+C para salir.")
    
    # 5. Iniciar consumo
    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        logger.info("👋 Interrupción recibida, cerrando worker...")
    except Exception as e:
        logger.error(f"❌ Error en consumo: {e}", exc_info=True)
    finally:
        if connection and not connection.is_closed:
            connection.close()
            logger.info("🔌 Conexión cerrada")

if __name__ == '__main__':
    main()