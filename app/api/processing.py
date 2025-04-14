import os
import json
import logging
import base64
import cv2
from typing import List
from fastapi import APIRouter, Request, Form, HTTPException, Depends
from fastapi.responses import JSONResponse
from app.config import settings
from app.core.utils.image_utils import overlay_zones_on_image
from app.session import get_session, Session
from app.core.processors.handwriting import HandwritingProcessor
from fastapi import File, UploadFile
from fastapi.encoders import jsonable_encoder

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post('/api/overlay-zones')
async def overlay_zones(
    request: Request,
    session_id: str = Form(...),
    opacity: float = Form(0.4),
    draw_labels: bool = Form(True)
):
    """Superponer zonas sobre la imagen"""
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=400, detail='Sesión no válida')

    required_steps = ['json_upload', 'pdf_upload']
    if not all(step in session.completed_steps for step in required_steps):
        raise HTTPException(status_code=400, detail='Debe completar los pasos anteriores')

    try:
        image_path = session.image_path
        zones_info = session.zones_info

        # Asegurarnos de que el directorio de resultados existe
        os.makedirs(settings.RESULTS_FOLDER, exist_ok=True)

        # Generar nombre único para la imagen de resultados
        result_filename = f"overlay_{session_id}.png"
        result_path = os.path.join(settings.RESULTS_FOLDER, result_filename)

        # Generar imagen con zonas superpuestas
        result_path = overlay_zones_on_image(
            image_path,
            zones_info,
            opacity=opacity,
            draw_labels=draw_labels,
            output_path=result_path
        )

        # Guardar las ROIs en la sesión
        rois = {}
        for zone in zones_info:
            if not isinstance(zone, dict) or 'name' not in zone:
                continue
                
            field_name = zone['name']
            x = int(zone.get('left', 0))
            y = int(zone.get('top', 0))
            w = int(zone.get('width', 0))
            h = int(zone.get('height', 0))
            
            if x < 0 or y < 0 or w <= 0 or h <= 0:
                continue
                
            rois[field_name] = [x, y, w, h]

        # Guardar la ruta y las ROIs en la sesión
        session.overlay_path = result_path
        session.rois = rois
        session.add_completed_step('overlay')

        # Construir la URL para acceder a la imagen
        # La URL debe ser relativa a /static
        relative_path = os.path.relpath(result_path, settings.STATIC_FOLDER)
        image_url = f"/static/{relative_path.replace(os.sep, '/')}"

        logger.info(f"Imagen generada en: {result_path}")
        logger.info(f"URL de la imagen: {image_url}")
        logger.info(f"ROIs guardadas: {list(rois.keys())}")

        return {
            'success': True,
            'message': "Zonas superpuestas correctamente",
            'image_url': image_url,
            'result_filename': result_filename
        }

    except Exception as e:
        logger.error(f"Error al superponer zonas: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post('/api/get-fields')
async def get_fields(
    request: Request,
    session_id: str = Form(...)
):
    """Obtener la lista de campos disponibles del JSON"""
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=400, detail='Sesión no válida o expirada.')

    try:
        zones_info = session.zones_info
        fields = []
        
        if isinstance(zones_info, dict):
            for key, value in zones_info.items():
                if isinstance(value, dict):
                    for subkey, subvalue in value.items():
                        if isinstance(subvalue, dict) and 'name' in subvalue:
                            fields.append(subvalue['name'])
                        elif isinstance(subvalue, dict):
                            for k, v in subvalue.items():
                                if isinstance(v, dict) and 'name' in v:
                                    fields.append(v['name'])

        logger.info(f"Campos encontrados en el JSON: {fields}")

        if not fields:
            logger.warning("No se encontraron campos en el JSON")
            return {'success': False, 'error': 'No se encontraron campos en el JSON'}

        return {
            'success': True,
            'fields': sorted(fields)
        }

    except Exception as e:
        logger.error(f"Error al obtener campos: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error al obtener campos: {str(e)}")

@router.post('/api/recognize-text')
async def recognize_text(
    request: Request,
    session_id: str = Form(...),
    fields: str = Form(...)  # Recibimos los campos como un string JSON
):
    """Reconocer texto en las ROIs seleccionadas"""
    try:
        # Convertir el string JSON de campos a lista
        try:
            fields_list = json.loads(fields)
            if not isinstance(fields_list, list):
                fields_list = [fields_list]
        except json.JSONDecodeError:
            # Si no es JSON válido, asumimos que es un solo campo
            fields_list = [fields]

        logger.info(f"Campos recibidos: {fields_list}")

        # Validar sesión y estado
        session = get_session(session_id)
        if not session:
            raise HTTPException(status_code=400, detail="Sesión no válida")
            
        if not session.image_path:
            raise HTTPException(status_code=400, detail="No hay imagen cargada")

        if not fields_list:
            raise HTTPException(status_code=400, detail="No se seleccionaron campos")

        # Leer imagen
        image_path = session.image_path
        if not os.path.exists(image_path):
            raise HTTPException(status_code=400, detail="Imagen no encontrada")

        image = cv2.imread(image_path)
        if image is None:
            raise HTTPException(status_code=400, detail="Error al leer la imagen")

        # Obtener ROIs
        rois = []
        roi_images = {}  # Diccionario para almacenar las imágenes en base64
        
        if not hasattr(session, 'rois'):
            raise HTTPException(status_code=400, detail="No hay ROIs definidas en la sesión")

        logger.info(f"ROIs disponibles en sesión: {session.rois.keys()}")
        
        for field in fields_list:
            if field in session.rois:
                roi_coords = session.rois[field]
                x, y, w, h = map(int, roi_coords)
                roi = image[y:y+h, x:x+w]
                if roi is not None and roi.size > 0:
                    rois.append(roi)
                    # Convertir ROI a base64
                    _, buffer = cv2.imencode('.png', roi)
                    roi_base64 = base64.b64encode(buffer).decode('utf-8')
                    roi_images[field] = f"data:image/png;base64,{roi_base64}"
                else:
                    logger.warning(f"ROI inválida para el campo {field}")
            else:
                logger.warning(f"Campo {field} no encontrado en las ROIs disponibles")

        if not rois:
            raise HTTPException(status_code=400, detail="No se encontraron ROIs válidas")

        # Procesar texto
        processor = HandwritingProcessor()
        results = processor.process_batch(rois, fields_list)

        # Agregar las imágenes al resultado
        response_data = {
            "success": True,
            "results": results,
            "roi_images": roi_images,  # Incluir las imágenes de las ROIs
            "debug_info": {
                "fields_received": fields_list,
                "rois_found": list(roi_images.keys())
            }
        }

        return JSONResponse(content=jsonable_encoder(response_data))

    except Exception as e:
        logger.error(f"Error en reconocimiento de texto: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
