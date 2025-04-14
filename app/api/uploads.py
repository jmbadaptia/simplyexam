import os
import json
import logging
import base64
import uuid
from flask import Blueprint, request, jsonify
from app.config import settings
from app.core.utils.file_utils import allowed_file, is_mark_field
from app.session import create_session, get_session
from pdf2image import convert_from_path
import tempfile

logger = logging.getLogger(__name__)

uploads_bp = Blueprint('uploads', __name__)

@uploads_bp.route('/api/upload-json', methods=['POST'])
def upload_json():
    """Subir y procesar archivo JSON con definición de zonas"""
    if 'json_file' not in request.files:
        return jsonify({'error': 'Falta archivo JSON'}), 400
    
    json_file = request.files['json_file']
    if json_file.filename == '':
        return jsonify({'error': 'Nombre de archivo inválido'}), 400
    
    if not allowed_file(json_file.filename, {'json'}):
        return jsonify({'error': 'Tipo de archivo no permitido'}), 400
    
    try:
        session = create_session()
        session_id = session.id
        json_filename = f"{session_id}_{json_file.filename}"
        json_path = os.path.join(settings.UPLOAD_FOLDER, json_filename)
        
        json_file.save(json_path)
        logger.info(f"Archivo JSON guardado: {json_path}")
        
        # Cargar y procesar el JSON
        with open(json_path, 'r') as f:
            zones_info = json.load(f)
        
        # Clasificar campos
        text_fields = set()
        mark_fields = set()
        
        for zone in zones_info:
            if not isinstance(zone, dict) or 'name' not in zone:
                continue
                
            field_name = zone['name']
            if is_mark_field(field_name):
                mark_fields.add(field_name)
            else:
                text_fields.add(field_name)
        
        # Actualizar sesión
        session.json_path = json_path
        session.zones_info = zones_info
        session.text_fields = list(text_fields)
        session.mark_fields = list(mark_fields)
        session.add_completed_step('json_upload')
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'text_fields': sorted(text_fields),
            'mark_fields': sorted(mark_fields)
        })
        
    except Exception as e:
        logger.error(f"Error al procesar JSON: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@uploads_bp.route('/api/upload-pdf', methods=['POST'])
def upload_pdf():
    """Subir y procesar archivo PDF o imagen"""
    session_id = request.form.get('session_id')
    if not session_id:
        return jsonify({'error': 'Falta ID de sesión'}), 400
    
    session = get_session(session_id)
    if not session:
        return jsonify({'error': 'Sesión no válida'}), 400
    
    if 'json_upload' not in session.completed_steps:
        return jsonify({'error': 'Debe subir el JSON primero'}), 400
    
    if 'pdf_file' not in request.files:
        return jsonify({'error': 'Falta archivo PDF o imagen'}), 400
    
    pdf_file = request.files['pdf_file']
    if pdf_file.filename == '':
        return jsonify({'error': 'Nombre de archivo inválido'}), 400
    
    if not allowed_file(pdf_file.filename, {'pdf', 'png', 'jpg', 'jpeg'}):
        return jsonify({'error': 'Tipo de archivo no permitido'}), 400
    
    try:
        file_extension = pdf_file.filename.rsplit('.', 1)[1].lower()
        is_pdf = file_extension == 'pdf'
        
        # Guardar archivo
        pdf_filename = f"{session_id}_{pdf_file.filename}"
        pdf_path = os.path.join(settings.UPLOAD_FOLDER, pdf_filename)
        pdf_file.save(pdf_path)
        
        # Si es PDF, convertir a imagen
        if is_pdf:
            try:
                # Convertir primera página del PDF a imagen
                images = convert_from_path(pdf_path, first_page=1, last_page=1)
                if not images:
                    return jsonify({'error': 'No se pudo extraer imagen del PDF'}), 500
                
                # Guardar la primera página como imagen
                image_filename = pdf_filename.rsplit('.', 1)[0] + '.jpg'
                image_path = os.path.join(settings.UPLOAD_FOLDER, image_filename)
                images[0].save(image_path, 'JPEG')
                
                # Eliminar el PDF original ya que tenemos la imagen
                os.remove(pdf_path)
                
            except Exception as e:
                logger.error(f"Error al convertir PDF: {e}", exc_info=True)
                return jsonify({'error': 'Error al procesar el PDF'}), 500
        else:
            image_path = pdf_path
        
        # Actualizar datos de sesión
        session.update(
            pdf_path=pdf_path if not is_pdf else None,
            image_path=image_path,
            is_pdf=is_pdf
        )
        session.add_completed_step('pdf_upload')
        
        # Leer la imagen para enviarla como base64
        with open(image_path, 'rb') as img_file:
            image_base64 = base64.b64encode(img_file.read()).decode('utf-8')
        
        return jsonify({
            'success': True,
            'message': f"{'PDF convertido' if is_pdf else 'Imagen procesada'} correctamente",
            'image_base64': image_base64,
            'image_filename': os.path.basename(image_path),
            'ready_for_overlay': True
        })
        
    except Exception as e:
        logger.error(f"Error al procesar archivo: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
