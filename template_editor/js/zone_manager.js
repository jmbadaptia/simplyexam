// Función para selección múltiple
function toggleZoneSelection(zoneName) {
  const zoneObj = canvas.getObjects().find(obj => obj.name === zoneName);
  if (!zoneObj) return;
  
  if (selectedZones.has(zoneName)) {
    // Deseleccionar
    selectedZones.delete(zoneName);
    zoneObj.set({
      stroke: 'green',
      strokeWidth: 1
    });
  } else {
    // Seleccionar
    selectedZones.add(zoneName);
    zoneObj.set({
      stroke: 'blue',
      strokeWidth: 2
    });
  }
  
  updateZoneList();
  canvas.renderAll();
  
  // Mostrar acciones disponibles si hay zonas seleccionadas
  if (selectedZones.size > 0) {
    showTooltip(`${selectedZones.size} zonas seleccionadas. Usa Ctrl+C para copiar.`);
  }
}

// Actualizar la lista de zonas
function updateZoneList() {
  zoneList.innerHTML = '';
  
  zones.forEach(z => {
    const div = document.createElement('div');
    div.className = 'zone';
    
    // Destacar si está seleccionada
    if (selectedZones.has(z.name)) {
      div.style.backgroundColor = '#e6f7ff';
      div.style.padding = '3px';
      div.style.borderRadius = '3px';
    }
    
    div.innerHTML = `${z.name} → [${Math.round(z.left)}, ${Math.round(z.top)}] w:${Math.round(z.width)} h:${Math.round(z.height)}`;
    
    // Clic para seleccionar/deseleccionar
    div.onclick = () => {
      if (isCtrlKeyPressed) {
        toggleZoneSelection(z.name);
      }
    };
    
    zoneList.appendChild(div);
  });
}

// Limpiar selecciones
function clearSelections() {
  selectedZones.forEach(name => {
    const obj = canvas.getObjects().find(o => o.name === name);
    if (obj) {
      obj.set({
        stroke: 'green',
        strokeWidth: 1
      });
    }
  });
  
  selectedZones.clear();
  updateZoneList();
  canvas.renderAll();
}

// Teclas de acceso rápido para copiar/pegar
document.addEventListener('keydown', function(e) {
  // Ctrl+C para copiar zonas seleccionadas
  if (isCtrlKeyPressed && e.key === 'c' && selectedZones.size > 0) {
    copySelectedZones();
  }
  
  // Ctrl+V para pegar zonas copiadas
  if (isCtrlKeyPressed && e.key === 'v' && window.copiedZones && window.copiedZones.length > 0) {
    showTooltip("Haz clic en el canvas para pegar las zonas copiadas");
    prepareToPaste();
  }
});

// Función para copiar zonas seleccionadas
function copySelectedZones() {
  if (selectedZones.size === 0) return;
  
  // Guardar zonas seleccionadas
  window.copiedZones = [];
  selectedZones.forEach(name => {
    const zone = zones.find(z => z.name === name);
    if (zone) window.copiedZones.push({...zone});
  });
  
  showTooltip(`${window.copiedZones.length} zonas copiadas. Usa Ctrl+V para pegar.`);
}

// Función para preparar el pegado
function prepareToPaste() {
  if (!window.copiedZones || window.copiedZones.length === 0) return;
  
  // Guardar el manejador de eventos original
  const originalMouseDown = canvas.__eventListeners['mouse:down'];
  canvas.__eventListeners['mouse:down'] = [];
  
  canvas.once('mouse:down', function(opt) {
    const pointer = canvas.getPointer(opt.e);
    
    // Calcular el punto más alto a la izquierda de las zonas copiadas
    let minX = Infinity, minY = Infinity;
    window.copiedZones.forEach(zone => {
      minX = Math.min(minX, zone.left);
      minY = Math.min(minY, zone.top);
    });
    
    // Desplazamiento para las nuevas zonas
    const offsetX = pointer.x - minX;
    const offsetY = pointer.y - minY;
    
    saveToHistory();
    
    // Preguntar si se desea renumerar (para zonas de respuestas)
    let renumberingInfo = null;
    
    // Verificar si hay patrón numérico en la primera zona (ej: 1A, 2B)
    if (window.copiedZones.length > 0) {
      const firstZoneName = window.copiedZones[0].name;
      const match = firstZoneName.match(/^(\d+)([A-Za-z]+)$/);
      
      if (match && confirm("¿Deseas incrementar automáticamente los números de las zonas copiadas?")) {
        const currentNumber = parseInt(match[1]);
        const newNumber = prompt(`Número para las nuevas zonas (actual: ${currentNumber}):`, 
                                (currentNumber + 1).toString());
        
        if (newNumber && !isNaN(parseInt(newNumber))) {
          renumberingInfo = {
            pattern: match[0],
            currentNumber: match[1],
            newNumber: newNumber,
            suffix: match[2]
          };
        }
      }
    }
    
    // Pegar las zonas
    const newZones = [];
    
    window.copiedZones.forEach(zone => {
      let newName = zone.name;
      
      // Renombrar si es necesario
      if (renumberingInfo) {
        newName = zone.name.replace(
          new RegExp('^' + renumberingInfo.currentNumber),
          renumberingInfo.newNumber
        );
      }
      
      // Verificar si el nombre ya existe
      let counter = 1;
      let finalName = newName;
      while (zones.some(z => z.name === finalName)) {
        finalName = `${newName}_${counter}`;
        counter++;
      }
      
      // Crear la nueva zona
      newZones.push(addZone(
        finalName,
        zone.left + offsetX,
        zone.top + offsetY,
        zone.width,
        zone.height,
        false
      ));
    });
    
    // Restaurar el manejador de eventos original
    canvas.__eventListeners['mouse:down'] = originalMouseDown;
    
    showTooltip(`${window.copiedZones.length} zonas pegadas`);
    
    // Seleccionar las zonas recién pegadas
    clearSelections();
    newZones.forEach(zone => {
      if (zone && zone.rect) {
        toggleZoneSelection(zone.rect.name);
      }
    });
  });
}
