import os
import logging
import sys
from pathlib import Path

# Configuración de directorios
ROOT_DIR = Path(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
STATIC_FOLDER = ROOT_DIR / 'static'
UPLOAD_FOLDER = STATIC_FOLDER / 'uploads'
RESULTS_FOLDER = STATIC_FOLDER / 'results'
OCR_RESULTS_FOLDER = RESULTS_FOLDER / 'ocr'
MODELS_FOLDER = ROOT_DIR / 'models'
TEMPLATE_FOLDER = ROOT_DIR / 'templates'

# Para asegurar que los directorios existan
for folder in [STATIC_FOLDER, UPLOAD_FOLDER, RESULTS_FOLDER, OCR_RESULTS_FOLDER, MODELS_FOLDER, TEMPLATE_FOLDER]:
    os.makedirs(folder, exist_ok=True)

# Configuración de la aplicación
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf', 'json'}
MAX_CONTENT_LENGTH = 16 * 1024 * 1024

# Configuración de Claude
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-3-7-sonnet-20250219")
CLAUDE_MAX_TOKENS = int(os.getenv("CLAUDE_MAX_TOKENS", "1000"))
CLAUDE_TIMEOUT = 30

# Configuración de procesamiento
MARK_THRESHOLD = 25  # Porcentaje de píxeles marcados para detección

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
