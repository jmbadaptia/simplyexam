import os
import json
import logging
import anthropic
import cv2
import base64
import numpy as np
from typing import Dict, Any, Optional, List
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
        self._load_prompt()

    def _load_prompt(self):
        """Cargar el prompt desde el archivo"""
        try:
            # Corregir la ruta para buscar en app/core/prompt.txt
            prompt_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'prompt.txt')
            logger.info(f"Intentando cargar prompt desde: {prompt_path}")
            with open(prompt_path, 'r', encoding='utf-8') as f:
                self._prompt_template = f.read()
            logger.info("Prompt cargado exitosamente")
        except Exception as e:
            logger.error(f"Error al cargar el prompt: {e}", exc_info=True)
            raise

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

    def process(self, image, zones, session_id: str):
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
        return self.process_batch(rois, field_names, session_id)

    def process_batch(self, rois: List[np.ndarray], field_names: List[str], session_id: str) -> Dict[str, str]:
        """Procesa un lote de ROIs y extrae el texto usando Claude"""
        try:
            if not rois or not field_names:
                logger.warning("No hay ROIs o nombres de campos para procesar")
                return {}

            # Obtener la ruta del PDF de la sesión
            from app.session import get_session
            session = get_session(session_id)
            if not session or not session.image_path:
                logger.error("No hay PDF cargado en la sesión")
                return {field: "ERROR" for field in field_names}

            # Leer el PDF y convertirlo a base64
            try:
                with open(session.image_path, "rb") as pdf_file:
                    pdf_base64 = base64.b64encode(pdf_file.read()).decode('utf-8')
                logger.info(f"PDF convertido a base64, longitud: {len(pdf_base64)}")
            except Exception as e:
                logger.error(f"Error al leer el PDF: {e}", exc_info=True)
                return {field: "ERROR" for field in field_names}

            # Construir el contenido del mensaje
            message_content = [
                {
                    "type": "text",
                    "text": self._prompt_template.format(fields=", ".join(field_names))
                },
                {
                    "type": "document",
                    "source": {
                        "type": "base64",
                        "media_type": "application/pdf",
                        "data": pdf_base64
                    }
                }
            ]

            # Construir la petición completa
            request_data = {
                "model": "claude-3-7-sonnet-20250219",
                "max_tokens": 1000,
                "messages": [
                    {
                        "role": "user",
                        "content": message_content
                    }
                ]
            }

            logger.info("Enviando petición a Claude...")
            # Enviar mensaje a Claude
            response = self._client.messages.create(**request_data)

            # Procesar respuesta
            try:
                response_text = response.content[0].text
                logger.info(f"Respuesta de Claude: {response_text}")
                
                # Convertir la respuesta a JSON
                response_json = json.loads(response_text)
                
                # Convertir el formato de respuesta a un diccionario simple
                results = {}
                for campo in response_json.get("campos", []):
                    results[campo["nombre"]] = campo["valor"]
                
                return results
                
            except json.JSONDecodeError as e:
                logger.error(f"Error al decodificar JSON de Claude: {e}")
                return {field: "ERROR" for field in field_names}
            except Exception as e:
                logger.error(f"Error al procesar respuesta de Claude: {e}", exc_info=True)
                return {field: "ERROR" for field in field_names}

        except Exception as e:
            logger.error(f"Error en process_batch: {e}", exc_info=True)
            return {field: "ERROR" for field in field_names}
