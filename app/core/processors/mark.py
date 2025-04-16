import os
import cv2
import numpy as np
import logging
from typing import Dict, Any, Tuple, List
from app.config import settings

logger = logging.getLogger(__name__)

class MarkProcessor:
    """
    Procesador mejorado para la detección de marcas OMR en formularios.
    """
    def __init__(self):
        self._mark_fields = set()
        self._debug_folder = None
        self._mark_types = {}  # Almacena tipos de marca (círculo, cuadrado)
        
    def initialize(self):
        """Inicializar el procesador de marcas"""
        logger.info("Inicializando procesador de marcas OMR")
        # No requiere inicialización especial más que logging
        
    def set_mark_fields(self, fields: set):
        """Establecer los campos de marca a procesar"""
        self._mark_fields = fields
        logger.info(f"Campos de marca configurados: {len(fields)} campos")
        
    def set_mark_types(self, mark_types: Dict[str, str]):
        """
        Establecer los tipos de marcas para cada campo
        
        Args:
            mark_types: Diccionario {nombre_campo: tipo_marca}
                       donde tipo_marca puede ser 'circle' o 'square'
        """
        self._mark_types = mark_types
        logger.info(f"Tipos de marca configurados para {len(mark_types)} campos")
        
    def set_debug_folder(self, folder: str):
        """Establecer la carpeta para guardar imágenes de debug"""
        self._debug_folder = folder
        os.makedirs(folder, exist_ok=True)
        logger.info(f"Carpeta de debug configurada: {folder}")
        
    def preprocess_roi(self, roi, field_name: str = None) -> np.ndarray:
        """
        Preprocesar una ROI para mejorar la detección de marcas
        
        Args:
            roi: Imagen ROI en formato numpy
            field_name: Nombre del campo para opciones específicas
            
        Returns:
            Imagen preprocesada
        """
        try:
            # Convertir a escala de grises si es necesario
            if len(roi.shape) == 3:
                gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            else:
                gray = roi
                
            # Normalizar la imagen para mejorar el contraste
            normalized = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX)
            
            # Reducir ruido con filtro gaussiano
            denoised = cv2.GaussianBlur(normalized, (3, 3), 0)
            
            # Aplicar umbral adaptativo (más sensible a marcas débiles)
            binary = cv2.adaptiveThreshold(
                denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY_INV, 11, 2
            )
            
            # Operaciones morfológicas para limpiar ruido
            kernel = np.ones((2, 2), np.uint8)
            cleaned = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
            
            # Guardar las etapas intermedias si estamos en modo debug
            if self._debug_folder and field_name:
                base_filename = f"{field_name}_"
                debug_path = os.path.join(self._debug_folder, f"{base_filename}processed.png")
                cv2.imwrite(debug_path, cleaned)
                
            return cleaned
            
        except Exception as e:
            logger.error(f"Error en preprocesamiento de ROI: {e}", exc_info=True)
            return None
    
    def detect_shape(self, roi, field_name: str = None) -> Tuple[str, List[Any]]:
        """
        Detecta la forma predominante en una ROI (círculo o cuadrado)
        
        Args:
            roi: Imagen ROI en formato numpy
            field_name: Nombre del campo
            
        Returns:
            Tupla (tipo_forma, contornos)
        """
        # Si el tipo ya está definido, usarlo
        if field_name and field_name in self._mark_types:
            return self._mark_types[field_name], []
        
        # De lo contrario, intentar detectar automáticamente
        try:
            # Preprocesar para detección de contornos
            if len(roi.shape) == 3:
                gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            else:
                gray = roi
                
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            _, thresh = cv2.threshold(blurred, 127, 255, cv2.THRESH_BINARY)
            
            # Encontrar contornos
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            # Si no hay contornos, asumir cuadrado
            if not contours:
                return 'square', []
                
            # Determinar si es un círculo o un cuadrado
            largest_contour = max(contours, key=cv2.contourArea)
            perimeter = cv2.arcLength(largest_contour, True)
            approx = cv2.approxPolyDP(largest_contour, 0.04 * perimeter, True)
            
            # Si tiene ~4 vértices, es un cuadrado/rectángulo
            if len(approx) <= 6:
                return 'square', contours
            else:
                return 'circle', contours
                
        except Exception as e:
            logger.error(f"Error en detección de forma: {e}")
            # Por defecto, asumir cuadrado
            return 'square', []
    
    def process_mark(self, roi, field_name: str = None) -> Tuple[bool, float, Dict[str, Any]]:
        """
        Procesar una ROI para detectar si está marcada
        
        Args:
            roi: Imagen ROI en formato numpy
            field_name: Nombre del campo
            
        Returns:
            Tupla (está_marcado, porcentaje, metadatos)
        """
        metadata = {}
        
        try:
            # Obtener tipo de marca (círculo o cuadrado)
            shape_type, contours = self.detect_shape(roi, field_name)
            metadata['shape_type'] = shape_type
            
            # Preprocesar ROI
            processed_roi = self.preprocess_roi(roi, field_name)
            if processed_roi is None:
                return False, 0.0, metadata
                
            # Calcular área marcada según el tipo de forma
            if shape_type == 'circle':
                # Para círculos, analizar principalmente el centro
                h, w = processed_roi.shape
                center_x, center_y = w // 2, h // 2
                
                # Definir una región de interés central (70% del área)
                radius = min(w, h) // 2
                center_radius = int(radius * 0.7)
                
                # Crear una máscara circular
                mask = np.zeros_like(processed_roi)
                cv2.circle(mask, (center_x, center_y), center_radius, 255, -1)
                
                # Aplicar la máscara
                center_roi = cv2.bitwise_and(processed_roi, mask)
                
                # Calcular porcentaje de píxeles marcados solo en el área central
                center_pixels = np.count_nonzero(mask)
                marked_pixels = np.count_nonzero(cv2.bitwise_and(processed_roi, mask))
                mark_percentage = (marked_pixels / center_pixels) * 100 if center_pixels > 0 else 0
                
                # Guardar máscara para debug
                if self._debug_folder and field_name:
                    cv2.imwrite(os.path.join(self._debug_folder, f"{field_name}_mask.png"), mask)
                    cv2.imwrite(os.path.join(self._debug_folder, f"{field_name}_center.png"), center_roi)
                
            else:  # Cuadrado/rectángulo
                # Calcular área total y píxeles marcados
                total_pixels = processed_roi.size
                marked_pixels = np.count_nonzero(processed_roi)
                mark_percentage = (marked_pixels / total_pixels) * 100
            
            # Determinar si está marcado según umbral correspondiente
            if shape_type == 'circle':
                # Los círculos suelen requerir un umbral más bajo
                threshold = getattr(settings, 'CIRCLE_MARK_THRESHOLD', 25)
            else:
                threshold = getattr(settings, 'MARK_THRESHOLD', 30)
                
            is_marked = mark_percentage > threshold
            
            # Guardar información en metadata
            metadata.update({
                'total_pixels': processed_roi.size,
                'marked_pixels': marked_pixels,
                'threshold': threshold
            })
            
            # Guardar imagen procesada para debug
            if self._debug_folder and field_name:
                cv2.imwrite(os.path.join(self._debug_folder, f"{field_name}_final.png"), processed_roi)
                
                # Si hay una imagen original, guardarla con contornos
                if contours and len(roi.shape) == 3:
                    roi_with_contours = roi.copy()
                    cv2.drawContours(roi_with_contours, contours, -1, (0, 255, 0), 2)
                    cv2.imwrite(os.path.join(self._debug_folder, f"{field_name}_contours.png"), roi_with_contours)
            
            # Loguear información
            logger.info(f"Procesamiento de marca {field_name}:")
            logger.info(f"- Tipo: {shape_type}")
            logger.info(f"- Total píxeles: {processed_roi.size}")
            logger.info(f"- Píxeles marcados: {marked_pixels}")
            logger.info(f"- Porcentaje: {mark_percentage:.2f}%")
            logger.info(f"- Umbral: {threshold}%")
            logger.info(f"- Estado: {'MARCADO' if is_marked else 'NO MARCADO'}")
            
            return is_marked, mark_percentage, metadata
            
        except Exception as e:
            logger.error(f"Error procesando marca: {e}", exc_info=True)
            return False, 0.0, metadata
    
    def process(self, image, zones):
        """
        Implementación del método abstracto para procesar la imagen
        
        Args:
            image: Imagen en formato numpy
            zones: Lista de zonas (dict con 'name', 'left', 'top', 'width', 'height')
            
        Returns:
            Dict con resultados
        """
        # Extraer ROIs de las marcas
        rois = []
        field_names = []
        
        for zone in zones:
            if zone['name'] not in self._mark_fields:
                continue
                
            x = int(zone.get('left', 0))
            y = int(zone.get('top', 0))
            w = int(zone.get('width', 0))
            h = int(zone.get('height', 0))
            
            if x < 0 or y < 0 or w <= 0 or h <= 0:
                continue
            
            roi = image[y:y+h, x:x+w]
            if roi.size == 0:
                continue
            
            rois.append(roi)
            field_names.append(zone['name'])
        
        # Procesar las ROIs
        results, details = self.process_batch(rois, field_names)
        return {"results": results, "details": details}
    
    def process_batch(self, rois: list, field_names: list) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Procesar un lote de ROIs de marca
        
        Args:
            rois: Lista de imágenes ROI
            field_names: Lista de nombres de campos
            
        Returns:
            Tupla (resultados_simples, resultados_detallados)
        """
        results = {}
        mark_results = {}
        
        for roi, field_name in zip(rois, field_names):
            if field_name not in self._mark_fields and self._mark_fields:
                continue
                
            try:
                marked, percentage, metadata = self.process_mark(roi, field_name)
                mark_results[field_name] = {
                    'marked': marked,
                    'percentage': percentage,
                    'metadata': metadata
                }
                results[field_name] = marked
                
                logger.info(f"Resultado para marca {field_name}: {'MARCADO' if marked else 'NO MARCADO'} ({percentage:.2f}%)")
                
            except Exception as e:
                logger.error(f"Error procesando marca {field_name}: {e}")
                mark_results[field_name] = {
                    'marked': False,
                    'percentage': 0.0,
                    'metadata': {'error': str(e)}
                }
                results[field_name] = False
        
        # Mostrar resumen de resultados
        if mark_results:
            logger.info("\nRESULTADOS DE MARCAS:")
            logger.info("=" * 60)
            logger.info(f"{'CAMPO':<15}| {'ESTADO':<10}| {'PORCENTAJE':<10}| {'TIPO':<8}")
            logger.info("-" * 60)
            for campo, info in mark_results.items():
                estado = "MARCADO" if info['marked'] else "NO MARCADO"
                tipo = info.get('metadata', {}).get('shape_type', 'n/a')
                logger.info(f"{campo:<15}| {estado:<10}| {info['percentage']:.2f}% | {tipo:<8}")
            logger.info("=" * 60)
            
        return results, mark_results