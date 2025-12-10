import os


# RabbitMQ
RABBITMQ_HOST = os.getenv('RABBITMQ_HOST', 'rabbitmq')
RABBITMQ_PORT = int(os.getenv('RABBITMQ_PORT', 5672))
RABBITMQ_USER = os.getenv('RABBITMQ_USER', 'despacho_user')
RABBITMQ_PASS = os.getenv('RABBITMQ_PASS', 'despacho_pass')
RABBITMQ_VHOST = os.getenv('RABBITMQ_VHOST', 'despacho_vhost')

RABBITMQ_URL = os.getenv(
    'RABBITMQ_URL',
    f'amqp://{RABBITMQ_USER}:{RABBITMQ_PASS}@{RABBITMQ_HOST}:{RABBITMQ_PORT}/{RABBITMQ_VHOST}'
)

# Queues y Exchanges
QUEUE_INMEDIATAS = 'ordenes_inmediatas'
EXCHANGE_INMEDIATAS = 'despacho.inmediatas'
ROUTING_KEY_INMEDIATA = 'inmediata'

# Base de datos
DB_HOST = os.getenv('DB_HOST', 'db')
DB_PORT = int(os.getenv('DB_PORT', 5432))
DB_USER = os.getenv('DB_USER', 'despachos_user123')
DB_PASS = os.getenv('DB_PASS', 'SecurePassword5826') 
DB_NAME = os.getenv('DB_NAME', 'despachos_db')
DB_URL = os.getenv(
    'DATABASE_URL','postgresql://despachos_user123:SecurePassword5826@db:5432/despachos_db'
)

# Inventario
INVENTARIO_URL = os.getenv('INVENTARIO_URL', 'http://host.docker.internal:8001')

# Flask
FLASK_DEBUG = os.getenv('FLASK_DEBUG', 'True').lower() in ('true', '1', 't')