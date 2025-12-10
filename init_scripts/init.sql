CREATE TABLE IF NOT EXISTS ordenes (
    id SERIAL PRIMARY KEY,
    id_venta VARCHAR(50) NOT NULL,
    cliente_nombre VARCHAR(100) NOT NULL,
    cliente_telefono VARCHAR(20) NOT NULL,
    direccion_entrega TEXT NOT NULL,
    estado VARCHAR(50) DEFAULT 'pendiente',
    fecha_entrega_estimada TIMESTAMP,
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ordenes_detalles (
    id SERIAL PRIMARY KEY,
    id_orden INT NOT NULL,
    id_producto VARCHAR(50) NOT NULL,
    nombre_productos VARCHAR(100) NOT NULL,
    cantidad INT NOT NULL
);