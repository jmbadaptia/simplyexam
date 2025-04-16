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
from app.core.processors.mark import MarkProcessor
from fastapi import File, UploadFile
from fastapi.encoders import jsonable_encoder

logger = logging.getLogger(__name__)

router = APIRouter()

def is_text_field(field_name):
    """Determina si un campo es de texto basado en su nombre"""
    return field_name == "DNI" or len(field_name) >= 4

def is_mark_field(field_name):
    """Determina si un campo es de marca basado en su nombre"""
    if not field_name:
        return False
    # Reglas para identificar campos de marca (R1A, R2B, etc.)
    if field_name.startswith(('R', 'M')) and len(field_name) <= 3:
        return True
    elif len(field_name) < 4 and field_name != "DNI":
        return True
    return False

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
        
        # Función para extraer zonas recursivamente
        def extract_zones(data, prefix=""):
            if isinstance(data, dict):
                if 'name' in data and all(k in data for k in ['left', 'top', 'width', 'height']):
                    field_name = data['name']
                    x = int(data.get('left', 0))
                    y = int(data.get('top', 0))
                    w = int(data.get('width', 0))
                    h = int(data.get('height', 0))
                    
                    if x >= 0 and y >= 0 and w > 0 and h > 0:
                        rois[field_name] = [x, y, w, h]
                else:
                    for key, value in data.items():
                        new_prefix = f"{prefix}.{key}" if prefix else key
                        extract_zones(value, new_prefix)
            elif isinstance(data, list):
                for i, item in enumerate(data):
                    new_prefix = f"{prefix}[{i}]"
                    extract_zones(item, new_prefix)
        
        # Procesar zonas según su formato
        if isinstance(zones_info, list):
            for zone in zones_info:
                extract_zones(zone)
        else:
            extract_zones(zones_info)
        
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
        # Usar los campos ya procesados en la sesión
        text_fields = session.text_fields
        mark_fields = session.mark_fields
        
        logger.info(f"Campos de texto: {text_fields}")
        logger.info(f"Campos de marca: {mark_fields}")

        if not text_fields and not mark_fields:
            logger.warning("No se encontraron campos en el JSON")
            return {'success': False, 'error': 'No se encontraron campos en el JSON'}

        return {
            'success': True,
            'text_fields': sorted(text_fields),
            'mark_fields': sorted(mark_fields),
            'fields': sorted(text_fields + mark_fields)
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

        # Verificar si se debe procesar primero el paso de overlay
        if 'overlay' not in session.completed_steps:
            logger.info("El paso overlay no se ha completado, ejecutándolo automáticamente...")
            # Ejecutar overlay automáticamente
            await overlay_zones(
                request=request,
                session_id=session_id,
                opacity=0.4,
                draw_labels=True
            )

        # Verificar que hay ROIs definidas
        if not hasattr(session, 'rois') or not session.rois:
            raise HTTPException(status_code=400, detail="No hay ROIs definidas en la sesión")

        logger.info(f"ROIs disponibles en sesión: {session.rois.keys()}")
        
        # Leer imagen para extraer ROIs
        image_path = session.image_path
        if not os.path.exists(image_path):
            raise HTTPException(status_code=400, detail="Imagen no encontrada")

        image = cv2.imread(image_path)
        if image is None:
            raise HTTPException(status_code=400, detail="Error al leer la imagen")

        # Filtrar solo campos de texto
        text_fields = []
        for field in fields_list:
            if field in session.text_fields or is_text_field(field):
                text_fields.append(field)
        
        if not text_fields:
            raise HTTPException(status_code=400, detail="No se seleccionaron campos de texto válidos")
        
        # Obtener ROIs para los campos de texto
        rois = []
        roi_fields = []
        roi_images = {}  # Diccionario para almacenar las imágenes en base64
        
        for field in text_fields:
            if field in session.rois:
                roi_coords = session.rois[field]
                x, y, w, h = map(int, roi_coords)
                roi = image[y:y+h, x:x+w]
                if roi is not None and roi.size > 0:
                    rois.append(roi)
                    roi_fields.append(field)
                    # Convertir ROI a base64
                    _, buffer = cv2.imencode('.png', roi)
                    roi_base64 = base64.b64encode(buffer).decode('utf-8')
                    roi_images[field] = f"data:image/png;base64,{roi_base64}"
                else:
                    logger.warning(f"ROI inválida para el campo {field}")
            else:
                logger.warning(f"Campo {field} no encontrado en las ROIs disponibles")

        if not rois:
            raise HTTPException(status_code=400, detail="No se encontraron ROIs válidas para los campos seleccionados")

        # Procesar texto con Claude
        processor = HandwritingProcessor()
        results = processor.process_batch(rois, roi_fields, session.id)

        # Agregar las imágenes al resultado
        response_data = {
            "success": True,
            "results": results,
            "roi_images": roi_images,  # Incluir las imágenes de las ROIs
            "debug_info": {
                "fields_received": fields_list,
                "text_fields_processed": roi_fields,
                "rois_found": list(roi_images.keys())
            }
        }

        return JSONResponse(content=jsonable_encoder(response_data))

    except Exception as e:
        logger.error(f"Error en reconocimiento de texto: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post('/api/recognize-marks')
async def recognize_marks(
    request: Request,
    session_id: str = Form(...),
    fields: str = Form(...)  # Recibimos los campos como un string JSON
):
    """Reconocer marcas OMR en las ROIs seleccionadas"""
    try:
        # Convertir el string JSON de campos a lista
        try:
            fields_list = json.loads(fields)
            if not isinstance(fields_list, list):
                fields_list = [fields_list]
        except json.JSONDecodeError:
            # Si no es JSON válido, asumimos que es un solo campo
            fields_list = [fields]

        logger.info(f"Campos recibidos para marcas: {fields_list}")

        # Validar sesión y estado
        session = get_session(session_id)
        if not session:
            raise HTTPException(status_code=400, detail="Sesión no válida")
            
        if not session.image_path:
            raise HTTPException(status_code=400, detail="No hay imagen cargada")

        if not fields_list:
            raise HTTPException(status_code=400, detail="No se seleccionaron campos")

        # Verificar si se debe procesar primero el paso de overlay
        if 'overlay' not in session.completed_steps:
            logger.info("El paso overlay no se ha completado, ejecutándolo automáticamente...")
            # Ejecutar overlay automáticamente
            await overlay_zones(
                request=request,
                session_id=session_id,
                opacity=0.4,
                draw_labels=True
            )

        # Verificar que hay ROIs definidas
        if not hasattr(session, 'rois') or not session.rois:
            raise HTTPException(status_code=400, detail="No hay ROIs definidas en la sesión")

        logger.info(f"ROIs disponibles en sesión: {session.rois.keys()}")
        
        # Leer imagen para extraer ROIs
        image_path = session.image_path
        if not os.path.exists(image_path):
            raise HTTPException(status_code=400, detail="Imagen no encontrada")

        image = cv2.imread(image_path)
        if image is None:
            raise HTTPException(status_code=400, detail="Error al leer la imagen")

        # Filtrar solo campos de marca
        mark_fields = []
        for field in fields_list:
            if field in session.mark_fields or is_mark_field(field):
                mark_fields.append(field)
        
        if not mark_fields:
            raise HTTPException(status_code=400, detail="No se seleccionaron campos de marca válidos")
        
        # Obtener ROIs para los campos de marca
        rois = []
        roi_fields = []
        roi_images = {}  # Diccionario para almacenar las imágenes en base64
        
        for field in mark_fields:
            if field in session.rois:
                roi_coords = session.rois[field]
                x, y, w, h = map(int, roi_coords)
                roi = image[y:y+h, x:x+w]
                if roi is not None and roi.size > 0:
                    rois.append(roi)
                    roi_fields.append(field)
                    # Convertir ROI a base64
                    _, buffer = cv2.imencode('.png', roi)
                    roi_base64 = base64.b64encode(buffer).decode('utf-8')
                    roi_images[field] = f"data:image/png;base64,{roi_base64}"
                else:
                    logger.warning(f"ROI inválida para el campo {field}")
            else:
                logger.warning(f"Campo {field} no encontrado en las ROIs disponibles")

        if not rois:
            raise HTTPException(status_code=400, detail="No se encontraron ROIs válidas para los campos seleccionados")

        # Preparar directorio para debug
        debug_dir = os.path.join(settings.RESULTS_FOLDER, f"debug_{session_id}")
        os.makedirs(debug_dir, exist_ok=True)
        
        # Configurar procesador de marcas
        processor = MarkProcessor()
        processor.set_mark_fields(set(roi_fields))
        processor.set_debug_folder(debug_dir)
        
        # Detectar automáticamente el tipo de marca según sus dimensiones
        mark_types = {}
        for field, roi in zip(roi_fields, rois):
            h, w = roi.shape[:2]
            aspect_ratio = w / h if h > 0 else 1
            
            if 0.8 <= aspect_ratio <= 1.2:  # Es casi cuadrado
                if max(w, h) < 30:  # Es pequeño
                    mark_types[field] = 'circle'
                else:
                    mark_types[field] = 'square'
            else:
                mark_types[field] = 'square'
                
        processor.set_mark_types(mark_types)
        
        # Procesar ROIs de marcas
        results_dict, details = processor.process_batch(rois, roi_fields)
        
        # Formatear resultados para el frontend
        formatted_results = {}
        for field_name, is_marked in results_dict.items():
            detail = details.get(field_name, {})
            percentage = detail.get('percentage', 0.0)
            
            formatted_results[field_name] = {
                'value': 'MARCADO' if is_marked else 'NO MARCADO',
                'marked': is_marked,
                'percentage': percentage,
                'confidence': percentage / 100.0,
                'metadata': detail.get('metadata', {})
            }
        
        # Agregar las imágenes al resultado
        response_data = {
            "success": True,
            "results": formatted_results,
            "roi_images": roi_images,  # Incluir las imágenes de las ROIs
            "debug_info": {
                "fields_received": fields_list,
                "mark_fields_processed": roi_fields,
                "rois_found": list(roi_images.keys())
            }
        }

        return JSONResponse(content=jsonable_encoder(response_data))

    except Exception as e:
        logger.error(f"Error en reconocimiento de marcas: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post('/api/recognize-all')
async def recognize_all(
    request: Request,
    session_id: str = Form(...),
    fields: str = Form(...)  # Recibimos los campos como un string JSON
):
    """Reconocer tanto texto como marcas en un solo endpoint"""
    try:
        # Convertir el string JSON de campos a lista
        try:
            fields_list = json.loads(fields)
            if not isinstance(fields_list, list):
                fields_list = [fields_list]
        except json.JSONDecodeError:
            # Si no es JSON válido, asumimos que es un solo campo
            fields_list = [fields]
            
        logger.info(f"Campos recibidos para reconocimiento completo: {fields_list}")
        
        # Separar campos en marcas y texto
        text_fields = []
        mark_fields = []
        
        for field in fields_list:
            if is_mark_field(field):
                mark_fields.append(field)
            else:
                text_fields.append(field)
                
        # Resultados combinados
        combined_results = {}
        
        # Procesar marcas si hay campos de ese tipo
        if mark_fields:
            try:
                # Crear una petición simulada para marcas
                mark_form = {
                    'session_id': session_id,
                    'fields': json.dumps(mark_fields)
                }
                
                # Llamar a la función de reconocimiento de marcas directamente
                mark_response = await recognize_marks(
                    request=request,
                    session_id=session_id,
                    fields=json.dumps(mark_fields)
                )
                
                # Extraer datos del response
                mark_data = mark_response
                
                if mark_data.get('success'):
                    # Integrar resultados de marcas
                    mark_results = mark_data.get('results', {})
                    for field, result in mark_results.items():
                        combined_results[field] = {
                            'type': 'mark',
                            'value': result.get('value'),
                            'marked': result.get('marked'),
                            'confidence': result.get('confidence', 0.0),
                            'percentage': result.get('percentage', 0.0)
                        }
            except Exception as e:
                logger.error(f"Error procesando marcas en reconocimiento combinado: {e}")
                # Continuar con el texto aunque las marcas fallen
        
        # Procesar texto si hay campos de ese tipo
        if text_fields:
            try:
                # Llamar a la función de reconocimiento de texto directamente
                text_response = await recognize_text(
                    request=request,
                    session_id=session_id,
                    fields=json.dumps(text_fields)
                )
                
                # Extraer datos del response
                text_data = text_response
                
                if text_data.get('success'):
                    # Integrar resultados de texto
                    text_results = text_data.get('results', {})
                    for field, value in text_results.items():
                        combined_results[field] = {
                            'type': 'text',
                            'value': value,
                            'confidence': 0.95  # Valor por defecto para Claude
                        }
            except Exception as e:
                logger.error(f"Error procesando texto en reconocimiento combinado: {e}")
                # Continuar aunque el texto falle
        
        # Construir respuesta final
        response_data = {
            "success": True,
            "results": combined_results,
            "fields_processed": {
                "text": text_fields,
                "mark": mark_fields
            }
        }
        
        return JSONResponse(content=jsonable_encoder(response_data))
        
    except Exception as e:
        logger.error(f"Error en reconocimiento combinado: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))