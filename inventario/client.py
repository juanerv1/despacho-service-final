# inventario/client.py
import os
import requests
from typing import Dict, List, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class InventarioClient:
    
    base_url = os.getenv('INVENTARIO_URL', 'http://localhost:8001')

    def check_health(self, timeout: int = 5) -> bool:
        """Verificar si el servicio de inventario está disponible"""
        try:
            response = requests.get(
                f"{self.base_url}/health",
                timeout=timeout
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("status") == "ok"
            return False
        except requests.exceptions.RequestException as e:
            logger.debug(f"Health check fallido para inventario: {e}")
            return False

    def consultar_stock_pendiente(self) -> Dict[str, int]:
        """Consultar stock pendiente para todos los productos"""
        try:
            response = requests.get(f"{self.base_url}/api/productos", timeout=5)
            if response.status_code == 200:
                data = response.json()
                
                # Para el formato específico de tu JSON
                if isinstance(data, list):
                    stock_pendiente = {}
                    for item in data:
                        if (isinstance(item, dict) and 
                            item.get('estado') == 'Pendiente' and 
                            item.get('id_producto')):
                            
                            producto_id = item['id_producto']
                            cantidad = item.get('cantidad', 0)
                            
                            # SOBREESCRIBE (no suma), incluye incluso si cantidad es 0
                            stock_pendiente[producto_id] = cantidad
                    
                    return stock_pendiente
                
                # Mantener compatibilidad con formato anterior
                elif isinstance(data, dict) and 'productos' in data:
                    return {
                        p['producto_id']: p['cantidad'] 
                        for p in data['productos'] 
                        if 'producto_id' in p and 'cantidad' in p
                    }
                
                return {}
            
            logger.error(f"Error {response.status_code} al consultar stock pendiente")
            return {}
            
        except Exception as e:
            logger.error(f"Error al consultar stock pendiente: {e}")
            return {}
        
    def restar_stock_despacho(self, producto_id: str, cantidad: int) -> bool:
        """Endpoint específico para restar stock en despachos"""
        try:
            payload = {
                "id_producto": producto_id,
                "cantidad": cantidad            
                }
            
            response = requests.post(
                f"{self.base_url}/api/productos/despachos/descontar",
                json=payload,
                timeout=5
            )
            
            if response.status_code == 200:
                return True
                
            # Si no hay stock suficiente
            elif response.status_code == 409:
                logger.warning(f"Stock insuficiente para cubrir orden")
                return False
                
            else:
                logger.error(f"Error {response.status_code} al despachar")
                return False
                
        except Exception as e:
            logger.error(f"Error de conexión: {e}")
            return False
        
    def restar_stock_pendiente(self, producto_id: str, cantidad: int) -> bool:
        """Endpoint específico para restar stock en despachos"""
        try:
            payload = {
                "id_producto": producto_id,
                "cantidad": cantidad
            }
            
            response = requests.post(
                f"{self.base_url}/api/productos/pendientes/descontar",
                json=payload,
                timeout=5
            )
            
            if response.status_code == 200:
                return True
                
            # Si no hay stock suficiente
            elif response.status_code == 409:
                logger.warning(f"Stock insuficiente para cubrir orden")
                return False
                
            else:
                logger.error(f"Error {response.status_code} al despachar")
                return False
                
        except Exception as e:
            logger.error(f"Error de conexión: {e}")
            return False