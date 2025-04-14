import os
import re
import logging
from app.config import settings

logger = logging.getLogger(__name__)

def allowed_file(filename, allowed_extensions=None):
    """Verificar si el archivo tiene una extensión permitida
    
    Args:
        filename: Nombre del archivo a verificar
        allowed_extensions: Conjunto de extensiones permitidas. Si es None,
                           se usa ALLOWED_EXTENSIONS de la configuración.
    
    Returns:
        bool: True si la extensión está permitida, False en caso contrario
    """
    if allowed_extensions is None:
        allowed_extensions = settings.ALLOWED_EXTENSIONS
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

def is_mark_field(field_name):
    """Determinar si un campo es una marca de respuesta
    
    Args:
        field_name: Nombre del campo a verificar
        
    Returns:
        bool: True si el campo es una marca de respuesta, False en caso contrario
    """
    pattern = r'^\d+[A-Z]$'
    return bool(re.match(pattern, field_name.upper()))

def create_unique_filename(original_filename, prefix=''):
    """Crear un nombre de archivo único con un prefijo opcional
    
    Args:
        original_filename: Nombre original del archivo
        prefix: Prefijo para el nuevo nombre (opcional)
        
    Returns:
        str: Nombre de archivo único
    """
    import uuid
    filename = f"{prefix}_{original_filename}" if prefix else original_filename
    return f"{uuid.uuid4()}_{filename}"
