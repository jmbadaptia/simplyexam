import os
import cv2
import logging
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Optional
from app.config import settings
from . import BaseProcessor

logger = logging.getLogger(__name__)

class ImageProcessor(BaseProcessor):
    """Procesador general de imágenes"""
    
    def __init__(self):
        """Inicializar el procesador de imágenes"""
        self._image_cache = {}
    
    def initialize(self):
        """Inicializa recursos necesarios"""
        # No requiere inicialización especial
        pass
    
    def load_image(self, image_path: str) -> Optional[np.ndarray]:
        """Cargar una imagen desde el disco
        
        Args:
            image_path: Ruta a la imagen
            
        Returns:
            np.ndarray: Imagen cargada o None si hubo un error
        """
        try:
            # Comprobar si ya está en caché
            if image_path in self._image_cache:
                return self._image_cache[image_path]
            
            # Cargar la imagen
            image = cv2.imread(image_path)
            if image is None:
                logger.error(f"No se pudo cargar la imagen: {image_path}")
                return None
            
            # Guardar en caché
            self._image_cache[image_path] = image
            return image
            
        except Exception as e:
            logger.error(f"Error al cargar imagen {image_path}: {e}", exc_info=True)
            return None
    
    def extract_rois(self, image: np.ndarray, zones: List[Dict[str, Any]], field_names: Optional[List[str]] = None) -> Dict[str, np.ndarray]:
        """Extraer regiones de interés de una imagen
        
        Args:
            image: Imagen de la que extraer ROIs
            zones: Lista de zonas (diccionarios con left, top, width, height, name)
            field_names: Lista opcional de nombres de campos a extraer. Si es None, se extraen todos.
            
        Returns:
            Dict[str, np.ndarray]: Diccionario de ROIs extraídas, con nombres de campos como claves
        """
        rois = {}
        
        for zone in zones:
            name = zone.get('name', '')
            
            # Si se especificaron field_names, comprobar si este campo está incluido
            if field_names and name not in field_names:
                continue
            
            # Extraer coordenadas
            x = int(zone.get('left', 0))
            y = int(zone.get('top', 0))
            w = int(zone.get('width', 0))
            h = int(zone.get('height', 0))
            
            # Comprobar validez
            if x < 0 or y < 0 or w <= 0 or h <= 0:
                logger.warning(f"Coordenadas inválidas para zona {name}: x={x}, y={y}, w={w}, h={h}")
                continue
            
            # Extraer ROI
            try:
                height, width = image.shape[:2]
                
                # Ajustar coordenadas si se salen de la imagen
                x = max(0, min(x, width - 1))
                y = max(0, min(y, height - 1))
                w = max(1, min(w, width - x))
                h = max(1, min(h, height - y))
                
                roi = image[y:y+h, x:x+w]
                if roi.size == 0:
                    logger.warning(f"ROI vacía para zona {name}")
                    continue
                
                rois[name] = roi
                
            except Exception as e:
                logger.error(f"Error al extraer ROI para zona {name}: {e}")
                continue
        
        return rois
    
    def process(self, image, zones):
        """Método de proceso general (implementación del método abstracto)
        
        Esta implementación básica extrae y devuelve todas las ROIs.
        Las subclases deben sobreescribir este método para procesamiento específico.
        
        Args:
            image: Imagen a procesar
            zones: Lista de zonas a extraer
            
        Returns:
            Dict[str, np.ndarray]: Diccionario de ROIs extraídas
        """
        return self.extract_rois(image, zones)
