import os
import cv2
import numpy as np
import logging
from typing import Dict, Any, Tuple
from app.config import settings
from . import BaseProcessor

logger = logging.getLogger(__name__)

class MarkProcessor(BaseProcessor):
    def __init__(self):
        self._mark_fields = set()
        self._debug_folder = None

    def initialize(self):
        """Inicializar el procesador de marcas"""
        # No requiere inicialización especial
        pass

    def set_mark_fields(self, fields: set):
        """Establecer los campos de marca a procesar"""
        self._mark_fields = fields

    def set_debug_folder(self, folder: str):
        """Establecer la carpeta para guardar imágenes de debug"""
        self._debug_folder = folder
        os.makedirs(folder, exist_ok=True)

    def preprocess_roi(self, roi) -> np.ndarray:
        """Preprocesar una ROI para mejorar la detección de marcas"""
        try:
            # Convertir a escala de grises si es necesario
            if len(roi.shape) == 3:
                gray = cv2.cvtColor(roi, cv2.COLOR_RGB2GRAY)
            else:
                gray = roi

            # Aplicar umbral adaptativo
            binary = cv2.adaptiveThreshold(
                gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY_INV, 11, 2
            )

            return binary

        except Exception as e:
            logger.error(f"Error en preprocesamiento de ROI: {e}", exc_info=True)
            return None

    def process_mark(self, roi) -> Tuple[bool, float]:
        """Procesar una ROI para detectar si está marcada"""
        try:
            # Preprocesar ROI
            processed_roi = self.preprocess_roi(roi)
            if processed_roi is None:
                return False, 0.0

            # Guardar imagen binarizada para debug
            if self._debug_folder:
                debug_path = os.path.join(self._debug_folder, 'debug_mark.png')
                cv2.imwrite(debug_path, processed_roi)

            # Calcular el porcentaje de píxeles negros (marca)
            total_pixels = processed_roi.size
            marked_pixels = np.count_nonzero(processed_roi)
            mark_percentage = (marked_pixels / total_pixels) * 100

            # Determinar si está marcado (umbral del 30%)
            is_marked = mark_percentage > settings.MARK_THRESHOLD

            logger.info(f"Procesamiento de marca:")
            logger.info(f"- Total píxeles: {total_pixels}")
            logger.info(f"- Píxeles marcados: {marked_pixels}")
            logger.info(f"- Porcentaje: {mark_percentage:.2f}%")
            logger.info(f"- Estado: {'MARCADO' if is_marked else 'NO MARCADO'}")

            return is_marked, mark_percentage

        except Exception as e:
            logger.error(f"Error procesando marca: {e}", exc_info=True)
            return False, 0.0

    def process(self, image, zones):
        """Implementación del método abstracto"""
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
        """Procesar un lote de ROIs de marca"""
        results = {}
        mark_results = {}

        for roi, field_name in zip(rois, field_names):
            if field_name not in self._mark_fields:
                continue

            try:
                marked, percentage = self.process_mark(roi)
                mark_results[field_name] = {
                    'marked': marked,
                    'percentage': percentage
                }
                results[field_name] = marked

                logger.info(f"Resultado para marca {field_name}: {'MARCADO' if marked else 'NO MARCADO'} ({percentage:.2f}%)")

            except Exception as e:
                logger.error(f"Error procesando marca {field_name}: {e}")
                mark_results[field_name] = {
                    'marked': False,
                    'percentage': 0.0
                }
                results[field_name] = False

        # Mostrar resumen de resultados
        if mark_results:
            logger.info("\nRESULTADOS DE MARCAS:")
            logger.info("=" * 50)
            logger.info(f"{'CAMPO':<20}| {'ESTADO':<10}| {'PORCENTAJE'}")
            logger.info("-" * 50)
            for campo, info in mark_results.items():
                estado = "MARCADO" if info['marked'] else "NO MARCADO"
                logger.info(f"{campo:<20}| {estado:<10}| {info['percentage']:.2f}%")
            logger.info("=" * 50)

        return results, mark_results
