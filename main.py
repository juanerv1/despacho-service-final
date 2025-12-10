# app.py - Archivo único con APIs y main
from flask import Flask, jsonify, request
from flask_cors import CORS
import os

# Importar tus módulos existentes
from database.models import Orden, OrdenDetalle
from database.repository import queries
from rabbitmq_client import RabbitMQClient
from datetime import datetime

# Inicializar Flask
app = Flask(__name__)
CORS(app)

# ---------------------------------------
# API: HEALTHCHECK
# ---------------------------------------
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "despachos-backend"}), 200

# ---------------------------------------
# API: CREAR ORDEN
# ---------------------------------------
@app.route("/api/ordenes", methods=["POST"])
def crear_orden_api():
    """API para crear una o múltiples órdenes"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No se proporcionaron datos JSON"}), 400
        
        # Determinar si es batch o individual
        if 'ordenes' in data:
            return procesar_ordenes_batch(data['ordenes'])
        else:
            return procesar_orden_unica(data)
            
    except Exception as e:
        return jsonify({"error": f"Error en la solicitud: {str(e)}"}), 500

def procesar_orden_unica(orden_data, indice=None):
    """Procesar una orden individual"""
    try:
        # Validar
        prefijo = f"Orden {indice}: " if indice is not None else ""
        validar_orden(orden_data, indice)
        
        # Crear orden
        orden = queries.crear_orden(orden_data)
        
        # Procesar según estado
        if orden.estado == "pendiente":
            print(f"Orden {orden.id_venta} creada con estado pendiente")
        elif orden.estado == "despacho":
            subir_orden_a_rabbitmq(orden)
            print(f"Orden {orden.id_venta} para despacho")
        
        return jsonify({
            "orden_id": orden.id,
            "id_venta": orden.id_venta,
            "estado": orden.estado,
            "mensaje": "Orden creada exitosamente"
        }), 201
        
    except ValueError as e:
        return jsonify({"error": f"{prefijo}{str(e)}"}), 400
    except Exception as e:
        return jsonify({"error": f"{prefijo}Error al crear orden: {str(e)}"}), 500

def validar_orden(orden_data, indice=None):
    """Validar datos de orden"""
    prefijo = f"Orden {indice}: " if indice is not None else ""
    
    required_fields = ['id_venta', 'cliente_nombre', 'direccion_entrega', 'productos']
    for field in required_fields:
        if field not in orden_data:
            raise ValueError(f"{prefijo}Campo requerido faltante: {field}")
    
    if not isinstance(orden_data['productos'], list) or len(orden_data['productos']) == 0:
        raise ValueError(f"{prefijo}Debe incluir al menos un producto")
    
    return True

def procesar_ordenes_batch(lista_ordenes):
    """Procesar múltiples órdenes"""
    try:
        if not isinstance(lista_ordenes, list):
            return jsonify({"error": "El campo 'ordenes' debe ser una lista"}), 400
        
        if len(lista_ordenes) == 0:
            return jsonify({"error": "La lista de órdenes está vacía"}), 400
        
        resultados = []
        errores = []
        
        for i, orden_data in enumerate(lista_ordenes):
            
            try:
                response, status_code = procesar_orden_unica(orden_data, i)
                
                if status_code == 201:
                    resultados.append({
                        "indice": i,
                        "orden_id": response.json["orden_id"],
                        "id_venta": response.json["id_venta"],
                        "estado": response.json["estado"],
                        "success": True
                    })
                else:
                    errores.append({
                        "indice": i,
                        "error": response.json["error"],
                        "id_venta": orden_data.get('id_venta', 'N/A')
                    })
                    
            except Exception as e:
                errores.append({
                    "indice": i,
                    "error": f"Error interno: {str(e)}",
                    "id_venta": orden_data.get('id_venta', 'N/A')
                })
        
        response = {
            "procesadas": len(resultados),
            "exitosas": [r["orden_id"] for r in resultados],
            "errores": len(errores)
        }
        
        if resultados:
            response["ordenes"] = resultados
        if errores:
            response["detalle_errores"] = errores
        
        status_code = 201 if resultados else 400
        return jsonify(response), status_code
        
    except Exception as e:
        return jsonify({"error": f"Error en procesamiento batch: {str(e)}"}), 500

def subir_orden_a_rabbitmq(orden):
    """Publicar orden a RabbitMQ"""
    try:
        rabbitmq = RabbitMQClient()
        
        orden_data = {
            'orden_id': orden.id,
            'id_venta': orden.id_venta,
            'detalles': [
                {
                    'id_producto': d.id_producto,
                    'cantidad': d.cantidad
                }
                for d in orden.detalles
            ]
        }
        
        rabbitmq.publish_orden_inmediata(orden_data)
        print(f"✅ Orden {orden.id_venta} publicada en RabbitMQ")
        
    except Exception as e:
        print(f"❌ Error publicando orden a RabbitMQ: {e}")

# ---------------------------------------
# API: CONSULTAR ORDENES
# ---------------------------------------
@app.route("/api/ordenes", methods=["GET"])
def obtener_ordenes_api():
    try:
        filtros = request.args.to_dict()
        ordenes = queries.obtener_ordenes(**filtros)

        resultado = []
        for orden in ordenes:
            orden_dict = {
                "id": orden.id,
                "id_venta": orden.id_venta,
                "cliente_nombre": orden.cliente_nombre,
                "cliente_telefono": orden.cliente_telefono,
                "direccion_entrega": orden.direccion_entrega,
                "estado": orden.estado,
                "fecha_creacion": orden.fecha_creacion.isoformat() if orden.fecha_creacion else None,
                "detalles": [
                    {
                        "id_producto": detalle.id_producto,
                        "nombre_productos": detalle.nombre_productos,
                        "cantidad": detalle.cantidad
                    }
                    for detalle in orden.detalles
                ]
            }
            resultado.append(orden_dict)

        return jsonify({
            "total": len(resultado),
            "ordenes": resultado
        }), 200
    
    except Exception as e:
        return jsonify({
            "error": f"Error al obtener órdenes: {str(e)}"
        }), 500

# ---------------------------------------
# MAIN: Punto de entrada
# ---------------------------------------
if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=(os.getenv("FLASK_DEBUG", "False") == "True")
    )