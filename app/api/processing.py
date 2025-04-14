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

        result_path = overlay_zones_on_image(
            image_path,
            zones_info,
            opacity=opacity,
            draw_labels=draw_labels
        )

        with open(result_path, 'rb') as img_file:
            result_base64 = base64.b64encode(img_file.read()).decode('utf-8')

        session.overlay_path = result_path
        session.add_completed_step('overlay')

        return {
            'success': True,
            'message': "Zonas superpuestas correctamente",
            'result_base64': result_base64,
            'result_filename': os.path.basename(result_path)
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
    fields: List[str] = Form(...)
):
    """Reconocer texto en las ROIs seleccionadas"""
    try:
        session = get_session(session_id)
        if not session:
            raise HTTPException(status_code=400, detail="Sesión no válida")
            
        if not session.image_path:
            raise HTTPException(status_code=400, detail="No hay imagen cargada")

        if not fields:
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
        if hasattr(session, 'rois'):
            for field in fields:
                if field in session.rois:
                    roi_coords = session.rois[field]
                    x, y, w, h = map(int, roi_coords)
                    roi = image[y:y+h, x:x+w]
                    if roi is not None and roi.size > 0:
                        rois.append(roi)
                    else:
                        logger.warning(f"ROI inválida para el campo {field}")

        if not rois:
            raise HTTPException(status_code=400, detail="No se encontraron ROIs válidas")

        # Procesar texto
        processor = HandwritingProcessor()
        results = processor.process_batch(rois, fields)

        return {"success": True, "results": results}

    except Exception as e:
        logger.error(f"Error en reconocimiento de texto: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
