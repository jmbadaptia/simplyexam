# SimplyExam v1.0.0

Sistema de corrección automática de exámenes mediante reconocimiento de marcas OMR.

## Requisitos
- Python 3.8 o superior
- pip (gestor de paquetes de Python)
- Navegador web moderno (Chrome, Firefox, Edge)

## Instalación

1. Clonar el repositorio:
```bash
git clone https://github.com/jmbadaptia/simplyexam.git
cd simplyexam
git checkout v1.0.0
```

2. Crear un entorno virtual (recomendado):
```bash
python -m venv venv
# En Windows:
venv\Scripts\activate
# En Linux/Mac:
source venv/bin/activate
```

3. Instalar dependencias:
```bash
pip install -r requirements.txt
```

4. Configurar variables de entorno:
- Crear archivo `.env` en la raíz del proyecto
- Añadir las siguientes variables:
  ```
  CLAUDE_API_KEY=tu_api_key_aqui
  ```

## Ejecución

1. Activar el entorno virtual si no está activo:
```bash
# En Windows:
venv\Scripts\activate
# En Linux/Mac:
source venv/bin/activate
```

2. Iniciar la aplicación:
```bash
python app.py
```

3. Abrir en el navegador:
```
http://localhost:5000
```

## Características principales
- Detección de marcas OMR
- Procesamiento de PDFs
- Interfaz web intuitiva
- Logging detallado
- Validación de zonas

## Soporte
Para soporte técnico, contactar con: [tu_email@dominio.com]
