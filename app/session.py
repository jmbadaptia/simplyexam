import uuid
import time
import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

class Session:
    """Gestiona datos de sesión para un proceso de análisis OMR"""
    
    def __init__(self, id=None):
        self.id = id or str(uuid.uuid4())
        self.created_at = time.time()
        self.json_path = None
        self.zones_info = None
        self.text_fields = []
        self.mark_fields = []
        self.image_path = None
        self.pdf_path = None  # Añadido atributo pdf_path
        self.is_pdf = False
        self.overlay_path = None
        self.completed_steps = []
        self.results = {}
        self.rois = {}  # Diccionario para almacenar las ROIs
        logger.debug(f"Nueva sesión inicializada con ID: {self.id}")
        
    def update(self, **kwargs):
        """Actualiza atributos de la sesión"""
        logger.debug(f"Actualizando sesión {self.id} con: {kwargs}")
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
                
    def add_completed_step(self, step):
        """Añade un paso completado"""
        if step not in self.completed_steps:
            self.completed_steps.append(step)
            logger.debug(f"Paso '{step}' completado en sesión {self.id}")
    
    def is_step_completed(self, step):
        """Verifica si un paso está completado"""
        completed = step in self.completed_steps
        logger.debug(f"Verificando paso '{step}' en sesión {self.id}: {'completado' if completed else 'pendiente'}")
        return completed
        
    def to_dict(self):
        """Convierte la sesión a diccionario"""
        return {
            'id': self.id,
            'created_at': self.created_at,
            'text_fields': self.text_fields,
            'mark_fields': self.mark_fields,
            'completed_steps': self.completed_steps,
            'rois': self.rois
        }