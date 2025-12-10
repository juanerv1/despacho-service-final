# database/models.py
from .base import Base, db_session
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

class Orden(Base):
    __tablename__ = "ordenes"
    
    id = Column(Integer, primary_key=True) 
    id_venta = Column(String(50), nullable=False)  # Sin db.
    cliente_nombre = Column(String(100), nullable=False)
    cliente_telefono = Column(String(20), nullable=False)
    direccion_entrega = Column(Text, nullable=False) 
    estado = Column(String(50), default='pendiente')
    fecha_entrega_estimada = Column(DateTime, nullable=True)
    fecha_creacion = Column(DateTime, default=datetime.utcnow)
    
    # Relación con detalles
    detalles = relationship(
        "OrdenDetalle",
        backref="orden",
        cascade="all, delete-orphan",
        lazy=True
    )
    
    def __repr__(self):
        return f'<Orden {self.id_venta} - {self.estado}>'


class OrdenDetalle(Base):
    __tablename__ = "ordenes_detalles"
    
    id = Column(Integer, primary_key=True)  
    id_orden = Column(Integer, ForeignKey('ordenes.id'), nullable=False)
    id_producto = Column(String(50), nullable=False)
    nombre_productos = Column(String(100), nullable=False) 
    cantidad = Column(Integer, nullable=False)
    
    def __repr__(self):
        return f'<OrdenDetalle {self.id_producto} x{self.cantidad}>'