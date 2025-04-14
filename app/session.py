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

class SessionManager:
    """Gestiona el almacenamiento y recuperación de sesiones"""
    
    _sessions: Dict[str, Session] = {}
    
    @classmethod
    def create_session(cls) -> Session:
        """Crea una nueva sesión"""
        session = Session()
        cls._sessions[session.id] = session
        logger.info(f"Sesión creada: {session.id}")
        logger.debug(f"Total de sesiones activas: {len(cls._sessions)}")
        logger.debug(f"IDs de sesiones activas: {list(cls._sessions.keys())}")
        return session
    
    @classmethod
    def get_session(cls, session_id: str) -> Optional[Session]:
        """Obtiene una sesión existente"""
        session = cls._sessions.get(session_id)
        if session is None:
            logger.warning(f"Sesión no encontrada: {session_id}")
            logger.debug(f"Total de sesiones activas: {len(cls._sessions)}")
            logger.debug(f"IDs de sesiones activas: {list(cls._sessions.keys())}")
        else:
            logger.debug(f"Sesión encontrada: {session_id}")
        return session
    
    @classmethod
    def cleanup_sessions(cls, max_age=3600):
        """Limpia sesiones antiguas"""
        now = time.time()
        to_delete = []
        
        for session_id, session in cls._sessions.items():
            if (now - session.created_at) > max_age:
                to_delete.append(session_id)
                
        for session_id in to_delete:
            del cls._sessions[session_id]
            
        if to_delete:
            logger.info(f"Limpiadas {len(to_delete)} sesiones antiguas")
            logger.debug(f"Sesiones eliminadas: {to_delete}")
            logger.debug(f"Sesiones restantes: {list(cls._sessions.keys())}")

# Para compatibilidad con el código original
sessions = SessionManager._sessions
create_session = SessionManager.create_session
get_session = SessionManager.get_session
cleanup_sessions = SessionManager.cleanup_sessions
