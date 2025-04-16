import os
import json
import logging
from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
import uuid
from pdf2image import convert_from_path
import tempfile
from app.config import settings
from app.session import create_session
from app.core.processors.handwriting import HandwritingProcessor
from app.core.processors.mark import MarkProcessor
from PIL import Image

logger = logging.getLogger(__name__)

uploads_bp = Blueprint('uploads', __name__)

def allowed_file(filename, allowed_extensions):
    """Verificar si un archivo tiene una extensión permitida"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions

def is_text_field(field_name):
    """Determina si un campo es de texto basado en su nombre"""
    return field_name == "DNI" or len(field_name) >= 4

@uploads_bp.route('/api/upload-json', methods=['POST'])
def upload_json():
    """Endpoint para subir archivo JSON de zonas"""
    try:
        # Verificar si se envió un archivo
        if 'json_file' not in request.files:
            return jsonify({'success': False, 'error': 'No se envió archivo JSON'}), 400
            
        file = request.files['json_file']
        
        # Verificar si el nombre del archivo es válido
        if file.filename == '':
            return jsonify({'success': False, 'error': 'Nombre de archivo vacío'}), 400
            
        # Verificar si es un JSON
        if not file.filename.lower().endswith('.json'):
            return jsonify({'success': False, 'error': 'El archivo debe ser JSON'}), 400
            
        # Crear una nueva sesión
        session = create_session()
        
        # Crear nombre de archivo seguro
        filename = f"{session.id}_{secure_filename(file.filename)}"
        
        # Crear la carpeta de uploads si no existe
        os.makedirs(current_app.config['UPLOAD_FOLDER'], exist_ok=True)
        
        # Guardar el archivo
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        logger.info(f"Archivo JSON guardado: {filepath}")
        
        # Leer el contenido del JSON
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                zones_info = json.load(f)
        except Exception as e:
            return jsonify({'success': False, 'error': f'Error al leer JSON: {str(e)}'}), 400
            
        # Extraer campos de texto y marca
        text_fields = []
        mark_fields = []
        
        try:
            text_processor = HandwritingProcessor()
            mark_processor = MarkProcessor()
            
            # Función para extraer campos de forma recursiva
            def extract_fields(data, prefix=""):
                if isinstance(data, dict):
                    if 'name' in data:
                        field_name = data['name']
                        # Clasificar como texto o marca
                        if is_text_field(field_name):
                            text_fields.append(field_name)
                        else:
                            mark_fields.append(field_name)
                    else:
                        for key, value in data.items():
                            new_prefix = f"{prefix}.{key}" if prefix else key
                            extract_fields(value, new_prefix)
                elif isinstance(data, list):
                    for i, item in enumerate(data):
                        new_prefix = f"{prefix}[{i}]"
                        extract_fields(item, new_prefix)
            
            # Extraer campos según la estructura del JSON
            if isinstance(zones_info, list):
                for zone in zones_info:
                    extract_fields(zone)
            else:
                extract_fields(zones_info)
                
            logger.info(f"Campos de texto identificados: {text_fields}")
            logger.info(f"Campos de marca identificados: {mark_fields}")
            
        except Exception as e:
            logger.error(f"Error al procesar zonas: {str(e)}", exc_info=True)
            
        # Actualizar información de la sesión
        session.json_path = filepath
        session.zones_info = zones_info
        session.text_fields = text_fields
        session.mark_fields = mark_fields
        session.add_completed_step('json_upload')
        
        # Establecer campos de texto para procesadores
        text_processor.set_text_fields(set(text_fields))
        
        return jsonify({
            'success': True,
            'message': 'Archivo JSON cargado correctamente',
            'session_id': session.id,
            'text_fields': text_fields,
            'mark_fields': mark_fields
        })
        
    except Exception as e:
        logger.error(f"Error al procesar archivo JSON: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

@uploads_bp.route('/api/upload-pdf', methods=['POST'])
def upload_pdf():
    """Endpoint para subir archivo PDF o imagen"""
    try:
        # Verificar si se envió el ID de sesión
        if 'session_id' not in request.form:
            return jsonify({'success': False, 'error': 'No se proporcionó ID de sesión'}), 400
            
        session_id = request.form['session_id']
        from app.session import get_session
        
        # Obtener la sesión
        session = get_session(session_id)
        if not session:
            return jsonify({'success': False, 'error': 'Sesión no válida o expirada'}), 400
            
        # Verificar si se envió un archivo
        if 'pdf_file' not in request.files:
            return jsonify({'success': False, 'error': 'No se envió archivo PDF/imagen'}), 400
            
        file = request.files['pdf_file']
        
        # Verificar si el nombre del archivo es válido
        if file.filename == '':
            return jsonify({'success': False, 'error': 'Nombre de archivo vacío'}), 400
            
        # Verificar si es un tipo de archivo permitido
        if not allowed_file(file.filename, current_app.config['ALLOWED_EXTENSIONS']):
            return jsonify({'success': False, 'error': 'Tipo de archivo no permitido'}), 400
            
        # Crear nombre de archivo seguro
        filename = f"{session_id}_{secure_filename(file.filename)}"
        
        # Crear la carpeta de uploads si no existe
        os.makedirs(current_app.config['UPLOAD_FOLDER'], exist_ok=True)
        
        # Guardar el archivo
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        logger.info(f"Archivo subido: {filepath}")
        
        # Determinar si es PDF
        is_pdf = file.filename.lower().endswith('.pdf')
        
        if is_pdf:
            # Guardar la ruta del PDF original en la sesión
            session.pdf_path = filepath
            session.is_pdf = True
            logger.info(f"PDF guardado: {filepath}")
            
            # Convertir PDF a imagen
            try:
                # Crear carpeta temporal para las imágenes
                with tempfile.TemporaryDirectory() as temp_dir:
                    # Configurar Poppler según el sistema operativo
                    if os.name == 'nt':  # Windows
                        poppler_path = r"C:\Python312\poppler-24.08.0\Library\bin"
                        logger.info(f"Windows: Usando Poppler desde: {poppler_path}")
                        conversion_args = {'poppler_path': poppler_path}
                    else:  # Linux/Unix
                        logger.info("Linux: Usando Poppler del sistema")
                        conversion_args = {}
                    
                    # Convertir primera página del PDF a imagen con alta resolución
                    images = convert_from_path(
                        filepath, 
                        first_page=1, 
                        last_page=1,
                        dpi=200,
                        output_folder=temp_dir,
                        thread_count=4,
                        grayscale=False,
                        fmt='jpeg',
                        jpegopt={'quality': 95},
                        **conversion_args
                    )
                    
                    if not images:
                        return jsonify({'success': False, 'error': 'No se pudo convertir el PDF a imagen'}), 500
                    
                    # Obtener la primera imagen
                    image = images[0]
                    
                    # Redimensionar la imagen al tamaño exacto requerido
                    target_size = (1786, 2526)
                    image = image.resize(target_size, Image.Resampling.LANCZOS)
                    
                    # Verificar tamaño después del redimensionamiento
                    width, height = image.size
                    if width != target_size[0] or height != target_size[1]:
                        logger.error(f"Error al redimensionar: {width}x{height} (debería ser {target_size[0]}x{target_size[1]})")
                        return jsonify({'success': False, 'error': 'Error al redimensionar la imagen'}), 400
                    
                    logger.info(f"Imagen redimensionada correctamente a {width}x{height}")
                    
                    # Guardar la imagen convertida
                    image_filename = f"{session_id}_converted.jpg"
                    image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], image_filename)
                    image.save(image_path, 'JPEG', quality=95)
                    logger.info(f"Imagen convertida guardada: {image_path}")
                    
                    # Guardar ruta de la imagen en la sesión
                    session.image_path = image_path
                    
            except Exception as e:
                logger.error(f"Error al convertir PDF: {str(e)}", exc_info=True)
                return jsonify({'success': False, 'error': f'Error al procesar PDF: {str(e)}'}), 500
        else:
            # Es una imagen
            session.image_path = filepath
            session.is_pdf = False
            logger.info(f"Imagen guardada: {filepath}")
            
        # Marcar paso como completado
        session.add_completed_step('pdf_upload')
        
        # Construir URL relativa para la imagen
        if session.image_path:
            relative_path = os.path.relpath(session.image_path, settings.STATIC_FOLDER)
            image_url = f"/static/{relative_path.replace(os.sep, '/')}"
        else:
            image_url = None
            
        return jsonify({
            'success': True,
            'message': 'Archivo procesado correctamente',
            'is_pdf': is_pdf,
            'image_url': image_url
        })
        
    except Exception as e:
        logger.error(f"Error al procesar archivo: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500