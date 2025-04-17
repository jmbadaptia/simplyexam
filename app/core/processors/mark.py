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
        self._thresholds = {}  # Umbrales específicos por campo
        self._calibration_data = {}  # Datos de calibración por tipo de formulario
        
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
                
            # Normalizar el tamaño si es muy pequeña
            h, w = gray.shape
            if h < 20 or w < 20:
                scale = max(20/h, 20/w)
                gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_LINEAR)
                
            # Mejorar contraste con CLAHE
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4,4))
            equalized = clahe.apply(gray)
            
            # Reducir ruido con filtro bilateral
            denoised = cv2.bilateralFilter(equalized, 5, 75, 75)
            
            # Aplicar umbral adaptativo con ventana más pequeña
            binary = cv2.adaptiveThreshold(
                denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY_INV, 9, 3
            )
            
            # Operaciones morfológicas para limpiar ruido
            kernel = np.ones((2,2), np.uint8)
            cleaned = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
            
            # Cerrar pequeños huecos
            kernel_close = np.ones((3,3), np.uint8)
            cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_CLOSE, kernel_close)
            
            # Guardar las etapas intermedias si estamos en modo debug
            if self._debug_folder and field_name:
                base_filename = f"{field_name}_"
                cv2.imwrite(os.path.join(self._debug_folder, f"{base_filename}1_gray.png"), gray)
                cv2.imwrite(os.path.join(self._debug_folder, f"{base_filename}2_equalized.png"), equalized)
                cv2.imwrite(os.path.join(self._debug_folder, f"{base_filename}3_denoised.png"), denoised)
                cv2.imwrite(os.path.join(self._debug_folder, f"{base_filename}4_binary.png"), binary)
                cv2.imwrite(os.path.join(self._debug_folder, f"{base_filename}5_cleaned.png"), cleaned)
                
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
                
            # Detectar círculos usando HoughCircles con parámetros más estrictos
            circles = cv2.HoughCircles(
                gray, cv2.HOUGH_GRADIENT, dp=1, minDist=20,
                param1=50, param2=25, 
                minRadius=min(gray.shape) // 6,  # Al menos 1/6 del tamaño menor
                maxRadius=min(gray.shape) // 2   # Como máximo 1/2 del tamaño menor
            )
            
            if circles is not None:
                return 'circle', circles[0]
            
            # Si no se detectan círculos, buscar rectángulos
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            # Encontrar contornos
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if not contours:
                return 'square', []
                
            # Analizar el contorno más grande
            largest_contour = max(contours, key=cv2.contourArea)
            perimeter = cv2.arcLength(largest_contour, True)
            approx = cv2.approxPolyDP(largest_contour, 0.04 * perimeter, True)
            
            # Calcular área y relación de aspecto
            area = cv2.contourArea(largest_contour)
            x, y, w, h = cv2.boundingRect(largest_contour)
            aspect_ratio = float(w)/h if h > 0 else 0
            
            # Criterios más estrictos para cuadrados
            if (len(approx) == 4 and 
                0.8 <= aspect_ratio <= 1.2 and 
                area > 0.4 * (w * h)):  # Al menos 40% del área del rectángulo delimitador
                return 'square', contours
            else:
                return 'circle', contours
                
        except Exception as e:
            logger.error(f"Error en detección de forma: {e}")
            # Por defecto, asumir cuadrado
            return 'square', []
    
    def process_mark(self, roi, field_name: str = None) -> Tuple[bool, float, Dict[str, Any]]:
        metadata = {}
        
        try:
            # Obtener tipo de marca
            shape_type, contours = self.detect_shape(roi, field_name)
            metadata['shape_type'] = shape_type
            
            # Guardar tamaño original
            h, w = roi.shape[:2]
            metadata['original_size'] = (w, h)
            
            # Preprocesar ROI
            processed_roi = self.preprocess_roi(roi, field_name)
            if processed_roi is None:
                return False, 0.0, metadata
            
            # Calcular área marcada según el tipo
            if shape_type == 'circle':
                # Para círculos, analizar principalmente el centro
                center_x, center_y = w // 2, h // 2
                radius = min(w, h) // 2
                
                # Área de análisis del 55% (punto medio entre 50% y 60%)
                center_radius = int(radius * 0.55)
                
                # Crear máscara circular
                mask = np.zeros_like(processed_roi)
                cv2.circle(mask, (center_x, center_y), center_radius, 255, -1)
                
                # Aplicar máscara
                center_roi = cv2.bitwise_and(processed_roi, mask)
                
                # Calcular porcentaje en área central
                center_pixels = np.count_nonzero(mask)
                marked_pixels = np.count_nonzero(center_roi)
                mark_percentage = (marked_pixels / center_pixels) * 100 if center_pixels > 0 else 0
                
                # Validar distribución
                if marked_pixels > 0:
                    y_indices, x_indices = np.where(center_roi > 0)
                    if len(x_indices) > 0 and len(y_indices) > 0:
                        # Calcular distancia al centro y dispersión
                        distances = np.sqrt(
                            (x_indices - center_x)**2 + 
                            (y_indices - center_y)**2
                        )
                        avg_distance = np.mean(distances)
                        std_distance = np.std(distances)
                        
                        # Penalizaciones más moderadas
                        if std_distance > center_radius * 0.35:  # Más de 35% del radio
                            mark_percentage *= 0.85  # Penalización más suave
                        if avg_distance > center_radius * 0.6:  # Marca más descentrada
                            mark_percentage *= 0.9
                        
                        metadata.update({
                            'center_deviation': avg_distance / radius,
                            'distance_std': std_distance / radius
                        })
                
                # Validar conectividad de componentes
                num_labels, labels = cv2.connectedComponents(center_roi)
                if num_labels > 4:  # Más de 3 regiones separadas (más permisivo)
                    mark_percentage *= 0.85
                
            else:  # Cuadrado
                # Calcular área total y marcada
                total_pixels = processed_roi.size
                marked_pixels = np.count_nonzero(processed_roi)
                mark_percentage = (marked_pixels / total_pixels) * 100
                
                # Validar distribución espacial
                if marked_pixels > 0:
                    y_indices, x_indices = np.where(processed_roi > 0)
                    if len(x_indices) > 0 and len(y_indices) > 0:
                        # Calcular dispersión normalizada
                        x_std = np.std(x_indices) / w
                        y_std = np.std(y_indices) / h
                        
                        # Penalizaciones más moderadas
                        if x_std < 0.12 or y_std < 0.12:  # Muy concentrado (más permisivo)
                            mark_percentage *= 0.8
                        elif x_std > 0.4 or y_std > 0.4:  # Muy disperso
                            mark_percentage *= 0.85
                            
                        # Calcular centro de masa y desviación del centro
                        center_mass_x = np.mean(x_indices)
                        center_mass_y = np.mean(y_indices)
                        center_deviation = np.sqrt(
                            ((center_mass_x - w/2)/(w/2))**2 + 
                            ((center_mass_y - h/2)/(h/2))**2
                        )
                        
                        if center_deviation > 0.35:  # Marca descentrada (más permisivo)
                            mark_percentage *= 0.9
                            
                        metadata['spatial_distribution'] = (x_std, y_std)
                        metadata['center_deviation'] = center_deviation
                
                # Validar conectividad
                num_labels, labels = cv2.connectedComponents(processed_roi)
                if num_labels > 4:  # Más de 3 regiones separadas
                    mark_percentage *= 0.85
            
            # Determinar umbral
            if field_name in self._thresholds:
                threshold = self._thresholds[field_name]
            elif shape_type == 'circle':
                threshold = getattr(settings, 'CIRCLE_MARK_THRESHOLD', 30)  # Punto medio entre 25 y 35
            else:
                threshold = getattr(settings, 'MARK_THRESHOLD', 35)  # Punto medio entre 30 y 40
            
            # Ajuste dinámico del umbral
            area = w * h
            if area < 400:  # ROI pequeña
                threshold *= 0.9  # Reducción moderada
            elif area > 2000:  # ROI grande
                threshold *= 1.1  # Aumento moderado
            
            # Decisión final
            is_marked = mark_percentage > threshold
            
            # Metadata adicional
            metadata.update({
                'total_pixels': processed_roi.size,
                'marked_pixels': marked_pixels,
                'mark_percentage': mark_percentage,
                'threshold': threshold,
                'area': area,
                'num_components': num_labels - 1
            })
            
            # Debug
            if self._debug_folder and field_name:
                cv2.imwrite(os.path.join(self._debug_folder, f"{field_name}_final.png"), processed_roi)
                if contours and len(roi.shape) == 3:
                    roi_with_contours = roi.copy()
                    cv2.drawContours(roi_with_contours, contours, -1, (0, 255, 0), 2)
                    cv2.imwrite(os.path.join(self._debug_folder, f"{field_name}_contours.png"), roi_with_contours)
            
            # Logging detallado
            logger.info(f"Procesamiento de marca {field_name}:")
            logger.info(f"- Tipo: {shape_type}")
            logger.info(f"- Tamaño: {w}x{h}")
            logger.info(f"- Total píxeles: {processed_roi.size}")
            logger.info(f"- Píxeles marcados: {marked_pixels}")
            logger.info(f"- Porcentaje: {mark_percentage:.2f}%")
            logger.info(f"- Umbral: {threshold}%")
            logger.info(f"- Componentes conectados: {num_labels-1}")
            if 'center_deviation' in metadata:
                logger.info(f"- Desviación del centro: {metadata['center_deviation']:.3f}")
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
        
    def set_field_threshold(self, field_name: str, threshold: float):
        """
        Establecer un umbral personalizado para un campo específico
        
        Args:
            field_name: Nombre del campo
            threshold: Umbral personalizado (porcentaje)
        """
        self._thresholds[field_name] = threshold
        logger.info(f"Umbral personalizado para {field_name}: {threshold}%")