# workers/pendiente.py
import sys
import psycopg2
import time
import logging
import os
sys.path.insert(0, '/app')
from inventario.client import InventarioClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('fifo-worker')

def get_db_connection():
    """Obtener conexión a PostgreSQL"""
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'postgres'),
        database=os.getenv('DB_NAME', 'despachos_db'),
        user=os.getenv('DB_USER', 'despachos_user123'),
        password=os.getenv('DB_PASS', '@SecurePassword5826'),  # Corrige: quita el @
        port=os.getenv('DB_PORT', '5432')
    )

class WorkerFIFO:
    def __init__(self):
        self.inventario = InventarioClient()
        self.intervalo = 30  # segundos
    
    def wait_for_database(self, max_retries=10, retry_delay=5):
        """Esperar a que la base de datos esté disponible"""
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
                    logger.error(f"❌ Máximos reintentos alcanzados: {e}")
                    return False
        return False
    
    def wait_for_inventory(self, max_retries=10, retry_delay=10):
        """Esperar a que el inventario esté disponible"""
        logger.info("⏳ Verificando conexión a inventario...")
        
        for attempt in range(max_retries):
            try:
                if self.inventario.check_health():
                    logger.info("✅ Inventario disponible")
                    return True
            except Exception as e:
                logger.debug(f"Health check falló: {e}")
            
            if attempt < max_retries - 1:
                logger.warning(f"⏳ Inventario no disponible (intento {attempt+1}/{max_retries}), reintentando en {retry_delay}s...")
                time.sleep(retry_delay)
            else:
                logger.error(f"❌ Máximos reintentos de inventario alcanzados")
                return False
        
        return False
    
    def obtener_orden_mas_antigua(self):
        """Obtener la orden pendiente más antigua con sus detalles"""
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, id_venta 
                FROM ordenes 
                WHERE estado = 'pendiente' 
                ORDER BY fecha_creacion ASC 
                LIMIT 1 FOR UPDATE SKIP LOCKED
            """)
            orden_row = cursor.fetchone()
            
            if not orden_row:
                return None
            
            orden_id, id_venta = orden_row
            
            cursor.execute("""
                SELECT id_producto, nombre_productos, cantidad 
                FROM ordenes_detalles 
                WHERE id_orden = %s
            """, (orden_id,))
            detalles = cursor.fetchall()
            
            return {
                'id': orden_id,
                'id_venta': id_venta,
                'detalles': [
                    {
                        'id_producto': det[0],
                        'nombre_producto': det[1],
                        'cantidad': det[2]
                    }
                    for det in detalles
                ]
            }
        finally:
            conn.close()
    
    def consultar_stock_pendiente(self):
        """Consultar stock para productos pendientes"""
        try:
            return self.inventario.consultar_stock_pendiente()
        except Exception as e:
            logger.error(f"❌ Error consultando stock: {e}")
            return {}
    
    def verificar_stock_orden(self, orden, stock):
        """Verificar si hay stock para esta orden"""
        for detalle in orden['detalles']:
            producto_id = detalle['id_producto']
            cantidad_necesaria = detalle['cantidad']
            
            if stock.get(producto_id, 0) < cantidad_necesaria:
                logger.debug(f"   ⏳ {producto_id}: necesita {cantidad_necesaria}, hay {stock.get(producto_id, 0)}")
                return False
        return True
    
    def procesar_orden(self, orden):
        """Procesar una orden individual"""
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # 1. Restar del inventario
            for detalle in orden['detalles']:
                if not self.inventario.restar_stock_pendiente(
                    producto_id=detalle['id_producto'],
                    cantidad=detalle['cantidad']
                ):
                    logger.error(f"❌ Fallo restando {detalle['id_producto']}")
                    conn.rollback()
                    return False
            
            # 2. Marcar como despachada
            cursor.execute("""
                UPDATE ordenes 
                SET estado = 'despachada'
                WHERE id = %s
            """, (orden['id'],))
            
            conn.commit()
            logger.info(f"✅ Orden {orden['id']} de venta {orden['id_venta']} despachada")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error procesando orden: {e}")
            if conn:
                conn.rollback()
            return False
        finally:
            if conn:
                conn.close()
    
    def ejecutar_ciclo(self):
        """Ejecutar un ciclo de procesamiento"""
        logger.info("🔄 Ciclo FIFO")
        
        # 1. Verificar inventario disponible
        try:
            if not self.inventario.check_health():
                logger.warning("⏳ Inventario no disponible, saltando ciclo...")
                return
        except Exception as e:
            logger.warning(f"⏳ Error verificando inventario: {e}, saltando ciclo...")
            return
        
        # 2. Obtener stock disponible
        stock = self.consultar_stock_pendiente()
        if not stock:
            logger.info("📭 Sin stock pendiente")
            return
        
        # 3. Procesar órdenes mientras haya stock
        procesadas = 0
        while stock:
            orden = self.obtener_orden_mas_antigua()
            if not orden:
                break
            
            logger.info(f"🔍 Revisando orden {orden['id']} de venta {orden['id_venta']}")
            
            if not self.verificar_stock_orden(orden, stock):
                logger.info(f"⏳ Sin stock para {orden['id_venta']}")
                break  # FIFO estricto
            
            if self.procesar_orden(orden):
                procesadas += 1
                for detalle in orden['detalles']:
                    producto_id = detalle['id_producto']
                    if producto_id in stock:
                        stock[producto_id] -= detalle['cantidad']
            else:
                logger.warning(f"⚠️ Falló procesamiento de {orden['id_venta']}")
                break
        
        if procesadas > 0:
            logger.info(f"📦 Despachadas: {procesadas} órdenes")
    
    def run(self):
        """Loop principal"""
        logger.info("🚀 Worker FIFO iniciado")
        
        # Esperar por BD antes de empezar
        if not self.wait_for_database():
            logger.error("❌ No se pudo conectar a BD. Saliendo.")
            return
        
        # Esperar por inventario antes de empezar
        if not self.wait_for_inventory():
            logger.error("❌ No se pudo conectar al inventario. Saliendo.")
            return
        
        # Ciclo principal
        logger.info("✅ Servicios disponibles, iniciando ciclo principal...")
        while True:
            try:
                self.ejecutar_ciclo()
            except Exception as e:
                logger.error(f"❌ Error en ciclo: {e}")
            
            time.sleep(self.intervalo)

if __name__ == "__main__":
    worker = WorkerFIFO()
    worker.run()