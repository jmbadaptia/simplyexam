import os
import json
import logging
import anthropic
import cv2
import base64
from typing import Dict, Any, Optional
from app.config import settings
from app.core.utils.async_utils import process_with_timeout
from . import BaseProcessor

logger = logging.getLogger(__name__)

class HandwritingProcessor(BaseProcessor):
    def __init__(self):
        self._client = None
        self._text_fields = set()
        self._claude_results = None
        self._initialize_client()

    def _initialize_client(self):
        """Inicializar el cliente de Anthropic"""
        try:
            logger.info("Inicializando cliente de Anthropic")
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key or api_key == "your_api_key_here":
                raise ValueError("ANTHROPIC_API_KEY no está configurada en el archivo .env")
            self._client = anthropic.Anthropic(api_key=api_key)
        except Exception as e:
            logger.error(f"Error al inicializar cliente de Anthropic: {e}", exc_info=True)
            raise

    def initialize(self):
        """Inicializa el procesador"""
        # Ya se inicializa en el constructor
        pass

    def set_text_fields(self, fields: set):
        """Establecer los campos de texto a procesar"""
        self._text_fields = fields

    def process_text(self, roi) -> str:
        """Procesar una ROI para extraer texto manuscrito"""
        try:
            # Convertir ROI a base64
            _, buffer = cv2.imencode('.jpg', roi)
            base64_image = base64.b64encode(buffer).decode('utf-8')

            # Crear mensaje para Claude
            message = {
                "model": settings.CLAUDE_MODEL,
                "max_tokens": settings.CLAUDE_MAX_TOKENS,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Analiza esta imagen y extrae el texto manuscrito que contiene. La imagen muestra un número o texto manuscrito. Por favor, devuelve solo el texto reconocido, sin explicaciones adicionales."
                            },
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/jpeg",
                                    "data": base64_image
                                }
                            }
                        ]
                    }
                ]
            }

            # Llamar a Claude
            response = process_with_timeout(
                self._client.messages.create,
                args=message,
                timeout=settings.CLAUDE_TIMEOUT
            )

            if response and response.content:
                return response.content[0].text.strip()
            return "NO_RECONOCIDO"

        except Exception as e:
            logger.error(f"Error procesando texto: {e}", exc_info=True)
            return "ERROR"

    def process(self, image, zones):
        """Implementación del método abstracto"""
        # Extraer ROIs del texto
        rois = []
        field_names = []
        
        for zone in zones:
            if zone['name'] not in self._text_fields:
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
        return self.process_batch(rois, field_names)

    def process_batch(self, rois: list, field_names: list) -> Dict[str, Any]:
        """Procesar un lote de ROIs de texto"""
        results = {}
        
        if not self._text_fields:
            return results

        try:
            # Preparar el mensaje para Claude
            message = {
                "model": settings.CLAUDE_MODEL,
                "max_tokens": settings.CLAUDE_MAX_TOKENS,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Analiza el siguiente texto manuscrito y extrae los valores de los campos solicitados. Responde en formato JSON con la siguiente estructura: {\"campos\": [{\"nombre\": \"NOMBRE_DEL_CAMPO\", \"valor\": \"VALOR_RECONOCIDO\"}]}"
                            }
                        ]
                    }
                ]
            }

            # Llamar a Claude
            response = process_with_timeout(
                self._client.messages.create,
                args=message,
                timeout=settings.CLAUDE_TIMEOUT
            )

            if response and response.content:
                text = response.content[0].text.strip()
                logger.info(f"Respuesta de Claude recibida: {text}")

                try:
                    # Parsear respuesta JSON
                    result = json.loads(text)
                    self._claude_results = {}

                    for campo in result.get('campos', []):
                        nombre = campo.get('nombre', '').upper()
                        valor = campo.get('valor', 'NO_RECONOCIDO')
                        if nombre in self._text_fields:
                            self._claude_results[nombre] = valor
                            results[nombre] = valor

                    # Mostrar resultados
                    logger.info("\nRESULTADOS DE TEXTO (Claude):")
                    logger.info("=" * 50)
                    for nombre, valor in sorted(self._claude_results.items()):
                        logger.info(f"{nombre:<20}| {valor}")

                except json.JSONDecodeError as e:
                    logger.error(f"Error al parsear respuesta JSON: {e}")
                    self._claude_results = {}

        except Exception as e:
            logger.error(f"Error en procesamiento de texto: {e}")
            self._claude_results = {}

        return results
