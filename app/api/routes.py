import os
from flask import Blueprint, render_template, send_from_directory
from app.config import settings

routes_bp = Blueprint('routes', __name__)

@routes_bp.route('/')
def index():
    """Página principal"""
    return render_template('index.html')

@routes_bp.route('/static/<path:path>')
def serve_static(path):
    """Servir archivos estáticos"""
    return send_from_directory(settings.STATIC_FOLDER, path)

@routes_bp.route('/results/ocr/<path:filename>')
def download_ocr_file(filename):
    """Descargar archivo de resultados OCR"""
    return send_from_directory(settings.OCR_RESULTS_FOLDER, filename)

@routes_bp.route('/uploads/<path:filename>')
def download_upload_file(filename):
    """Descargar archivo subido"""
    return send_from_directory(settings.UPLOAD_FOLDER, filename)

@routes_bp.route('/results/<path:filename>')
def download_result_file(filename):
    """Descargar archivo de resultados"""
    return send_from_directory(settings.RESULTS_FOLDER, filename)
