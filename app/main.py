import os
import sys
import logging
from flask import Flask
from dotenv import load_dotenv

# Cargar variables de entorno antes de importar otros módulos
load_dotenv()

# Configurar logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Importaciones internas
from app.config import settings
from app.api import routes_bp, uploads_bp, processing_bp
from app.core.processors.handwriting import HandwritingProcessor
from app.core.processors.mark import MarkProcessor

def create_app():
    """Crear y configurar la aplicación Flask"""
    app = Flask(__name__, 
                static_folder=str(settings.STATIC_FOLDER),
                template_folder=str(settings.TEMPLATE_FOLDER))
    
    # Configuración de la aplicación
    app.config['UPLOAD_FOLDER'] = str(settings.UPLOAD_FOLDER)
    app.config['RESULTS_FOLDER'] = str(settings.RESULTS_FOLDER)
    app.config['OCR_RESULTS_FOLDER'] = str(settings.OCR_RESULTS_FOLDER)
    app.config['MODELS_FOLDER'] = str(settings.MODELS_FOLDER)
    app.config['MAX_CONTENT_LENGTH'] = settings.MAX_CONTENT_LENGTH
    app.config['ALLOWED_EXTENSIONS'] = settings.ALLOWED_EXTENSIONS
    
    # Registrar blueprints
    app.register_blueprint(routes_bp)
    app.register_blueprint(uploads_bp)
    app.register_blueprint(processing_bp)
    
    return app

def initialize_processors():
    """Inicializar procesadores para que estén listos"""
    try:
        logger.info("Inicializando procesadores...")
        handwriting_processor = HandwritingProcessor()
        mark_processor = MarkProcessor()
        
        handwriting_processor.initialize()
        mark_processor.initialize()
        mark_processor.set_debug_folder(str(settings.OCR_RESULTS_FOLDER))
        
        logger.info("Procesadores inicializados correctamente")
    except Exception as e:
        logger.error(f"Error al inicializar procesadores: {e}", exc_info=True)
        raise

def main():
    """Función principal para ejecutar la aplicación"""
    try:
        # Inicializar procesadores
        initialize_processors()
        
        # Crear aplicación Flask
        app = create_app()
        
        # Configuración del puerto
        port = int(os.environ.get('PORT', 5000))
        
        # Iniciar el servidor de desarrollo Flask
        app.run(host='0.0.0.0', port=port, debug=True, use_reloader=False)
        
    except Exception as e:
        logger.error(f"Error al iniciar la aplicación: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
