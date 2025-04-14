import os
import cv2
import logging
import numpy as np
from app.config import settings

logger = logging.getLogger(__name__)

def overlay_zones_on_image(image_path, zones_info, opacity=0.4, draw_labels=True, output_path=None):
    """Superponer zonas sobre una imagen
    
    Args:
        image_path: Ruta a la imagen
        zones_info: Lista de diccionarios con información de zonas
        opacity: Opacidad de las zonas (0.0-1.0)
        draw_labels: Si se deben dibujar etiquetas con nombres de zonas
        output_path: Ruta donde guardar la imagen resultante
        
    Returns:
        str: Ruta a la imagen resultante con zonas superpuestas
    """
    try:
        # Leer la imagen
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError("No se pudo leer la imagen")

        # Crear una copia para dibujar
        overlay = image.copy()
        output = image.copy()

        # Color para las zonas (verde semi-transparente)
        color = (0, 255, 0)

        # Dibujar cada zona
        for zone in zones_info:
            x = int(zone.get('left', 0))
            y = int(zone.get('top', 0))
            w = int(zone.get('width', 0))
            h = int(zone.get('height', 0))
            name = zone.get('name', '')

            # Dibujar rectángulo
            cv2.rectangle(overlay, (x, y), (x + w, y + h), color, -1)
            cv2.rectangle(output, (x, y), (x + w, y + h), color, 2)

            # Añadir etiqueta si está activado
            if draw_labels and name:
                cv2.putText(output, name, (x, y - 10),
                          cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

        # Aplicar transparencia
        cv2.addWeighted(overlay, opacity, output, 1 - opacity, 0, output)

        # Usar la ruta de salida proporcionada o generar una por defecto
        if output_path is None:
            output_path = os.path.join(
                settings.RESULTS_FOLDER,
                f"overlay_{os.path.basename(image_path)}"
            )
        
        # Asegurarnos de que el directorio existe
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Guardar resultado
        cv2.imwrite(output_path, output)
        logger.info(f"Imagen guardada en: {output_path}")

        return output_path

    except Exception as e:
        logger.error(f"Error en overlay_zones_on_image: {e}", exc_info=True)
        raise
