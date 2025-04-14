# Importaciones para facilitar el uso de los blueprints y routers
from .routes import routes_bp
from .uploads import uploads_bp
from .processing import router as processing_router

# Para compatibilidad con el código existente
processing_bp = processing_router
