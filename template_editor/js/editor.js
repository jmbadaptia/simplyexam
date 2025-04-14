// Elementos DOM
const canvas = new fabric.Canvas('canvas');
const imageLoader = document.getElementById('imageLoader');
const jsonLoader = document.getElementById('jsonLoader');
const zoneList = document.getElementById('zoneList');
const tooltip = document.getElementById('tooltip');
const undoBtn = document.getElementById('undoBtn');

// Variables de estado
let zones = [];
let isDrawing = false;
let rect, startX, startY;
let selectedZones = new Set(); // Para selección múltiple
let isCtrlKeyPressed = false;  // Para detectar tecla Ctrl

// Historial
const history = [];
const maxHistoryLength = 20;

// Inicializar canvas
canvas.setWidth(800);
canvas.setHeight(600);

// Eventos
imageLoader.addEventListener('change', handleImage);
jsonLoader.addEventListener('change', handleJson);

// Para selección múltiple con tecla Ctrl
document.addEventListener('keydown', function(e) {
  if (e.key === 'Control' || e.key === 'Meta') {
    isCtrlKeyPressed = true;
  }
});

document.addEventListener('keyup', function(e) {
  if (e.key === 'Control' || e.key === 'Meta') {
    isCtrlKeyPressed = false;
  }
});

// Función para cargar imágenes - versión simplificada
function handleImage(e) {
  const file = e.target.files[0];
  if (!file) return;
  
  const reader = new FileReader();
  reader.onload = function(event) {
    const img = new Image();
    img.onload = function() {
      // Configurar canvas
      canvas.setWidth(img.width);
      canvas.setHeight(img.height);
      
      // Limpiar canvas
      canvas.clear();
      
      // Crear objeto fabric.Image
      const fabricImg = new fabric.Image(img, {
        selectable: false,
        evented: false
      });
      
      // Establecer como fondo
      canvas.setBackgroundImage(fabricImg, canvas.renderAll.bind(canvas));
      
      showTooltip("Imagen cargada correctamente");
    };
    img.src = event.target.result;
  };
  reader.readAsDataURL(file);
}

function handleJson(e) {
  const file = e.target.files[0];
  if (!file) return;
  
  const reader = new FileReader();
  reader.onload = function(event) {
    try {
      saveToHistory();
      const loadedZones = JSON.parse(event.target.result);
      
      // Limpiar canvas primero
      clearAllZones();
      
      // Cargar zonas
      loadedZones.forEach(z => addZone(z.name, z.left, z.top, z.width, z.height, false));
      
      updateUndoButton();
      showTooltip(`${loadedZones.length} zonas cargadas`);
    } catch (error) {
      alert("Error al cargar el archivo JSON: " + error.message);
    }
  };
  reader.readAsText(file);
}

// Eventos del canvas para dibujar
canvas.on('mouse:down', function(opt) {
  if (opt.target) {
    // Si se hace clic en un objeto con la tecla Ctrl presionada
    if (isCtrlKeyPressed && opt.target.name && !opt.target.name.includes('_label')) {
      toggleZoneSelection(opt.target.name);
      return;
    }
    return;
  }
  
  isDrawing = true;
  const pointer = canvas.getPointer(opt.e);
  startX = pointer.x;
  startY = pointer.y;
  
  rect = new fabric.Rect({
    left: startX,
    top: startY,
    width: 1,
    height: 1,
    fill: 'rgba(0,255,0,0.3)',
    stroke: 'green',
    strokeWidth: 1,
    selectable: false
  });
  
  canvas.add(rect);
});

canvas.on('mouse:move', function(opt) {
  if (!isDrawing) return;
  
  const pointer = canvas.getPointer(opt.e);
  const width = pointer.x - startX;
  const height = pointer.y - startY;
  
  rect.set({
    width: Math.abs(width),
    height: Math.abs(height)
  });
  
  if (width < 0) rect.set({ left: pointer.x });
  if (height < 0) rect.set({ top: pointer.y });
  
  canvas.renderAll();
});

canvas.on('mouse:up', function() {
  if (!isDrawing) return;
  isDrawing = false;
  
  const name = prompt('Nombre de la zona (ej: 1A, D00, etc):');
  if (!name) {
    canvas.remove(rect);
    canvas.renderAll();
    return;
  }
  
  // Verificar si ya existe
  const existingZone = zones.find(z => z.name === name);
  if (existingZone && !confirm(`Ya existe una zona con el nombre "${name}". ¿Quieres sobrescribirla?`)) {
    canvas.remove(rect);
    canvas.renderAll();
    return;
  }
  
  // Guardar historial
  saveToHistory();
  
  // Eliminar zona anterior si existe
  zones = zones.filter(z => z.name !== name);
  canvas.getObjects().forEach(obj => {
    if (obj.name === name || obj.name === name + '_label') {
      canvas.remove(obj);
    }
  });
  
  // Añadir la nueva zona
  addZone(name, rect.left, rect.top, rect.width, rect.height, true);
});

// Función para añadir una zona
function addZone(name, left, top, width, height, updateHistory = true) {
  // Eliminar si ya existe
  canvas.getObjects().forEach(obj => {
    if (obj.name === name || obj.name === name + '_label') {
      canvas.remove(obj);
    }
  });
  
  // Crear rectángulo
  const newRect = new fabric.Rect({
    left, top, width, height,
    fill: 'rgba(0,255,0,0.3)',
    stroke: 'green',
    strokeWidth: 1,
    selectable: true,
    name
  });
  
  // Crear etiqueta
  const newLabel = new fabric.Text(name, {
    left: left + 4,
    top: top + 4,
    fontSize: 12,
    fill: 'black',
    selectable: false,
    name: name + '_label'
  });
  
  // Añadir evento para gestionar la zona
  newRect.on('mousedown', function(e) {
    // Selección múltiple con Ctrl
    if (isCtrlKeyPressed) {
      toggleZoneSelection(name);
      e.e.stopPropagation();
      return;
    }
    
    const action = prompt(`Zona: "${name}"\n1. Escribe nuevo nombre\n2. Deja en blanco para eliminar`);
    if (action === null) return;
    
    saveToHistory();
    
    if (action.trim() === '') {
      // Eliminar
      canvas.remove(newRect);
      canvas.remove(newLabel);
      zones = zones.filter(z => z.name !== name);
    } else {
      // Renombrar
      zones = zones.map(z => z.name === name ? { ...z, name: action } : z);
      newRect.name = action;
      newLabel.set({
        text: action,
        name: action + '_label'
      });
    }
    
    updateZoneList();
    canvas.renderAll();
    updateUndoButton();
  });
  
  // Actualizar etiqueta cuando se mueve el rectángulo
  newRect.on('moving', function() {
    newLabel.set({
      left: newRect.left + 4,
      top: newRect.top + 4
    });
  });
  
  // Añadir al canvas
  canvas.add(newRect);
  canvas.add(newLabel);
  
  // Actualizar lista de zonas
  zones = zones.filter(z => z.name !== name);
  zones.push({ name, left, top, width, height });
  
  updateZoneList();
  canvas.renderAll();
  
  if (updateHistory) {
    updateUndoButton();
  }
  
  return { rect: newRect, label: newLabel };
}

// Guardar zonas en JSON
function downloadZones() {
  const blob = new Blob([JSON.stringify(zones, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'plantilla_zonas.json';
  a.click();
  URL.revokeObjectURL(url);
}

// Mostrar tooltip
function showTooltip(message) {
  tooltip.innerHTML = message;
  tooltip.style.display = 'block';
  
  tooltip.style.left = '50%';
  tooltip.style.top = '20px';
  tooltip.style.transform = 'translateX(-50%)';
  
  setTimeout(() => {
    tooltip.style.display = 'none';
  }, 3000);
}

// Funciones para historial (deshacer)
function saveToHistory() {
  const currentState = {
    zones: JSON.parse(JSON.stringify(zones))
  };
  
  history.push(currentState);
  
  if (history.length > maxHistoryLength) {
    history.shift();
  }
  
  updateUndoButton();
}

function undoLastAction() {
  if (history.length === 0) return;
  
  const lastState = history.pop();
  
  clearAllZones();
  clearSelections();
  zones = lastState.zones;
  
  zones.forEach(z => {
    addZone(z.name, z.left, z.top, z.width, z.height, false);
  });
  
  updateZoneList();
  updateUndoButton();
  showTooltip("Acción deshecha");
}

function clearAllZones() {
  const objectsToRemove = [];
  canvas.getObjects().forEach(obj => {
    if (obj !== canvas.backgroundImage) {
      objectsToRemove.push(obj);
    }
  });
  
  for (const obj of objectsToRemove) {
    canvas.remove(obj);
  }
  
  canvas.renderAll();
}

function updateUndoButton() {
  undoBtn.disabled = history.length === 0;
}
