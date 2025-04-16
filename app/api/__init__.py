# app/api/__init__.py

# Importar blueprints
from .routes import bp as routes_bp
from .uploads import bp as uploads_bp
from .processing import processing_bp

# Exportar todos los blueprints
__all__ = ['routes_bp', 'uploads_bp', 'processing_bp']
