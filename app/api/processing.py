
import os
import json
import logging
import base64
import cv2
from flask import Blueprint, request, jsonify
from app.config import settings
from app.core.utils.image_utils import overlay_zones_on_image
from app.session import get_session

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
    """Procesar texto y marcas en la imagen"""
    try:
        session_id = request.form.get('session_id')
        if not session_id:
            return jsonify({'error': 'Falta ID de sesión'}), 400

        session = get_session(session_id)
        if not session:
            return jsonify({'error': 'Sesión no válida'}), 400

        if 'json_upload' not in session.completed_steps:
            return jsonify({'error': 'Debe subir el JSON primero'}), 400

        # Obtener campos seleccionados
        selected_fields = request.form.getlist('selected_fields[]')
        if not selected_fields:
            return jsonify({'error': 'Debe seleccionar campos'}), 400

        # Leer la imagen
        image_path = session.image_path
        if not image_path or not os.path.exists(image_path):
            return jsonify({'error': 'Imagen no encontrada'}), 400

        image = cv2.imread(image_path)
        if image is None:
            return jsonify({'error': 'Error al leer la imagen'}), 500

        # Extraer ROIs
        rois = []
        field_names = []

        for zone in session.zones_info:
            if zone['name'] not in selected_fields:
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

        # Importar procesadores solo cuando son necesarios
        from app.core.processors.handwriting import HandwritingProcessor
        from app.core.processors.mark import MarkProcessor

        # Obtener instancias de procesadores
        handwriting_processor = HandwritingProcessor()
        mark_processor = MarkProcessor()
        mark_processor.set_debug_folder(settings.OCR_RESULTS_FOLDER)

        # Configurar campos
        handwriting_processor.set_text_fields(set(session.text_fields))
        mark_processor.set_mark_fields(set(session.mark_fields))

        # Procesar ROIs
        text_results = handwriting_processor.process_batch(rois, field_names)
        mark_results, mark_details = mark_processor.process_batch(rois, field_names)

        # Combinar resultados
        results = {**text_results, **mark_results}
        results['marks'] = mark_details

        # Guardar resultados
        results_filename = f"{session_id}_results.json"
        results_path = os.path.join(settings.OCR_RESULTS_FOLDER, results_filename)

        with open(results_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        return jsonify({
            'success': True,
            'results': results
        })

    except Exception as e:
        logger.error(f"Error en reconocimiento: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
