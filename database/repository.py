# database/repository.py
from datetime import datetime
from .models import Orden, OrdenDetalle
from .base import Session, db_session 
from sqlalchemy.orm import joinedload

class queries:

    def crear_orden(data):

        try:
            orden = Orden(
                id_venta=data["id_venta"],
                cliente_nombre=data["cliente_nombre"],
                cliente_telefono=data["cliente_telefono"],
                direccion_entrega=data["direccion_entrega"],
                fecha_entrega_estimada=datetime.strptime(data.get("fecha_estimada_envio"), '%Y-%m-%d') 
                if data.get("fecha_estimada_envio") else None,
                estado=data["estado"]
            )

            db_session.add(orden) 
            db_session.flush()

            for producto in data["productos"]:
                detalle = OrdenDetalle(
                    id_orden=orden.id,
                    id_producto=producto["id_producto"],
                    nombre_productos=producto["nombre"],
                    cantidad=producto["cantidad"]
                )
                db_session.add(detalle)

            db_session.commit()  
            return orden
        
        except Exception as e:
            db_session.rollback()  
            raise e
        finally:
            Session.remove()

    def actualizar_orden(orden_id, **campos):
        """Actualizar una orden existente"""

        try:
            orden = db_session.query(Orden).get(orden_id) 
            
            if not orden:
                return None
            
            for campo, valor in campos.items():
                if hasattr(orden, campo):
                    if campo == "fecha_entrega_estimada" and valor:
                        setattr(orden, campo, datetime.strptime(valor, '%Y-%m-%d'))
                    else:
                        setattr(orden, campo, valor)
            
            db_session.commit()
            return orden
        finally:
            db_session.remove()

    def obtener_ordenes(id_orden=None, **filtros):
        """Obtener órdenes siempre con sus detalles"""
        
        try:
            if id_orden is not None:
                orden = db_session.query(Orden).options(
                    joinedload(Orden.detalles)
                ).get(id_orden)
                db_session.commit()  # Si es solo lectura, igual es buena práctica
                return orden
            
            
            query = db_session.query(Orden).options(joinedload(Orden.detalles))  
            
            if "estado" in filtros:
                query = query.filter_by(estado=filtros["estado"])
            
            if "id_venta" in filtros:
                query = query.filter_by(id_venta=filtros["id_venta"])
            
            if "cliente_nombre" in filtros:
                query = query.filter(Orden.cliente_nombre.ilike(f"%{filtros['cliente_nombre']}%"))
            
            if "desde_fecha" in filtros:
                query = query.filter(Orden.fecha_creacion >= filtros["desde_fecha"])
            
            if "hasta_fecha" in filtros:
                query = query.filter(Orden.fecha_creacion <= filtros["hasta_fecha"])
            
            orden_por = filtros.get("orden_por", "fecha_creacion")
            direccion = filtros.get("direccion", "desc")
            
            if direccion == "asc":
                query = query.order_by(getattr(Orden, orden_por).asc())
            else:
                query = query.order_by(getattr(Orden, orden_por).desc())
            
            if "limite" in filtros:
                query = query.limit(filtros["limite"])
            
            resultados = query.all()
            db_session.commit()  # Confirmar transacción
            return resultados
        except Exception as e:
            db_session.rollback()  # Revertir en caso de error
            raise e
        finally:
            # Para scoped_session, debemos remover de esta forma:
            Session.remove()
    
    def obtener_ordenes_pendientes_fifo(limite=None):
        """Obtener órdenes pendientes ordenadas FIFO"""
        
        try:
            query = db_session.query(Orden).options(
                joinedload(Orden.detalles)
            ).filter_by(
                estado="pendiente"
            ).order_by(
                Orden.fecha_creacion.asc()
            )
            
            if limite:
                query = query.limit(limite)
            
            return query.all()
        finally:
            Session.remove()

    def actualizar_estado_orden(orden_id, nuevo_estado):
        """Actualizar solo el estado de una orden"""
        try:
            orden = db_session.query(Orden).get(orden_id)  
            if orden:
                orden.estado = nuevo_estado
                db_session.commit()
            return orden
        finally:
            Session.remove()