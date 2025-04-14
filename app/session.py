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
        self.is_pdf = False
        self.overlay_path = None
        self.completed_steps = []
        self.results = {}
        
    def update(self, **kwargs):
        """Actualiza atributos de la sesión"""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
                
    def add_completed_step(self, step):
        """Añade un paso completado"""
        if step not in self.completed_steps:
            self.completed_steps.append(step)
    
    def is_step_completed(self, step):
        """Verifica si un paso está completado"""
        return step in self.completed_steps
        
    def to_dict(self):
        """Convierte la sesión a diccionario"""
        return {
            'id': self.id,
            'created_at': self.created_at,
            'text_fields': self.text_fields,
            'mark_fields': self.mark_fields,
            'completed_steps': self.completed_steps
        }

# Almacén de sesiones
_sessions: Dict[str, Session] = {}

def create_session() -> Session:
    """Crea una nueva sesión"""
    session = Session()
    _sessions[session.id] = session
    logger.info(f"Sesión creada: {session.id}")
    return session

def get_session(session_id: str) -> Optional[Session]:
    """Obtiene una sesión existente"""
    return _sessions.get(session_id)

def cleanup_sessions(max_age=3600):
    """Limpia sesiones antiguas"""
    now = time.time()
    to_delete = []
    
    for session_id, session in _sessions.items():
        if (now - session.created_at) > max_age:
            to_delete.append(session_id)
            
    for session_id in to_delete:
        del _sessions[session_id]
        
    if to_delete:
        logger.info(f"Limpiadas {len(to_delete)} sesiones antiguas")

# Para compatibilidad con el código original
sessions = _sessions
