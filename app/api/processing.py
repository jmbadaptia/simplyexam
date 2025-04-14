import os
import json
import logging
import base64
import cv2
from flask import Blueprint, request, jsonify
from app.config import settings
from app.core.utils.image_utils import overlay_zones_on_image
from app.session import get_session
from fastapi import Request, HTTPException

logger = logging.getLogger(__name__)

processing_bp = Blueprint('processing', __name__)

@processing_bp.route('/api/overlay-zones', methods=['POST'])
def overlay_zones():
    """Superponer zonas sobre la imagen"""
    session_id = request.form.get('session_id')
    if not session_id:
        return jsonify({'error': 'Falta ID de sesión'}), 400

    session = get_session(session_id)
    if not session:
        return jsonify({'error': 'Sesión no válida'}), 400

    required_steps = ['json_upload', 'pdf_upload']
    if not all(step in session.completed_steps for step in required_steps):
        return jsonify({'error': 'Debe completar los pasos anteriores'}), 400

    try:
        image_path = session.image_path
        zones_info = session.zones_info

        opacity = float(request.form.get('opacity', 0.4))
        draw_labels = request.form.get('draw_labels', 'true').lower() == 'true'

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

        return jsonify({
            'success': True,
            'message': "Zonas superpuestas correctamente",
            'result_base64': result_base64,
            'result_filename': os.path.basename(result_path)
        })

    except Exception as e:
        logger.error(f"Error al superponer zonas: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@processing_bp.route('/api/get-fields', methods=['POST'])
def get_fields():
    """
    Obtener la lista de campos disponibles del JSON
    """
    # Verificar si hay una sesión activa
    session_id = request.form.get('session_id')
    if not session_id:
        return jsonify({'error': 'Falta ID de sesión'}), 400

    session = get_session(session_id)
    if not session:
        return jsonify({'error': 'Sesión no válida o expirada.'}), 400

    try:
        # Obtener datos de la sesión
        zones_info = session.zones_info

        # Extraer nombres de campos
        fields = []
        if isinstance(zones_info, dict):
            # Si es un diccionario, buscar campos dentro de cada tipo
            for key, value in zones_info.items():
                if isinstance(value, dict):
                    # Si el valor es un diccionario, buscar campos dentro
                    for subkey, subvalue in value.items():
                        if isinstance(subvalue, dict) and 'name' in subvalue:
                            fields.append(subvalue['name'])
                        elif isinstance(subvalue, dict):
                            # Si es otro diccionario, buscar campos recursivamente
                            for k, v in subvalue.items():
                                if isinstance(v, dict) and 'name' in v:
                                    fields.append(v['name'])

        logger.info(f"Campos encontrados en el JSON: {fields}")

        if not fields:
            logger.warning("No se encontraron campos en el JSON")
            return jsonify({
                'success': False,
                'error': 'No se encontraron campos en el JSON'
            })

        return jsonify({
            'success': True,
            'fields': sorted(fields)
        })

    except Exception as e:
        logger.error(f"Error al obtener campos: {e}", exc_info=True)
        return jsonify({'error': f"Error al obtener campos: {str(e)}"}), 500

@processing_bp.route('/api/recognize-text', methods=['POST'])
def recognize_text():
    """Reconocer texto en las ROIs seleccionadas"""
    try:
        # Verificar sesión
        session = request.session
        if not session.get("image_path"):
            raise HTTPException(status_code=400, detail="No hay imagen cargada")

        # Obtener campos seleccionados
        form = request.form
        selected_fields = form.getlist("fields[]")
        
        if not selected_fields:
            raise HTTPException(status_code=400, detail="No se seleccionaron campos")

        # Leer imagen
        image_path = session["image_path"]
        if not os.path.exists(image_path):
            raise HTTPException(status_code=400, detail="Imagen no encontrada")

        image = cv2.imread(image_path)
        if image is None:
            raise HTTPException(status_code=400, detail="Error al leer la imagen")

        # Obtener ROIs
        rois = []
        if session.get("rois"):
            for field in selected_fields:
                if field in session["rois"]:
                    roi_coords = session["rois"][field]
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
        results = processor.process_batch(rois, selected_fields)

        return {"success": True, "results": results}

    except Exception as e:
        logger.error(f"Error en reconocimiento de texto: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
