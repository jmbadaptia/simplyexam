// Función para generar rejilla DNI con nomenclatura de matriz
function generateDNIGrid() {
  // Verificar zonas de referencia
  const d00 = zones.find(z => z.name === 'D00');
  const d10 = zones.find(z => z.name === 'D10');
  const d01 = zones.find(z => z.name === 'D01');
  
  if (!d00 || !d10 || !d01) {
    alert("Por favor, primero crea manualmente las tres zonas D00, D10 y D01");
    return;
  }
  
  saveToHistory();
  
  // Calcular espaciados
  const horizontalSpacing = d01.left - d00.left;
  const verticalSpacing = d10.top - d00.top;
  const cellWidth = d00.width;
  const cellHeight = d00.height;
  
  // Generar rejilla con mejor precisión
  const numRows = 10;    // Filas (dígitos 0-9)
  const numCols = 8;     // Columnas (posiciones 0-7)
  
  for (let row = 0; row < numRows; row++) {
    for (let col = 0; col < numCols; col++) {
      // Calcular posición exacta para esta casilla
      const left = d00.left + (col * horizontalSpacing);
      const top = d00.top + (row * verticalSpacing);
      const name = `D${row}${col}`;
      
      // Saltar las zonas de referencia que ya existen
      if ((row === 0 && col === 0) || 
          (row === 1 && col === 0) || 
          (row === 0 && col === 1)) {
        continue;
      }
      
      addZone(name, left, top, cellWidth, cellHeight, false);
    }
  }
  
  showTooltip("Rejilla DNI generada correctamente");
}

// Función para visualizar un DNI específico
function visualizeDNI() {
  const dniValue = prompt("Introduce un DNI de 8 dígitos:", "12345678");
  
  if (!dniValue || dniValue.length !== 8 || !/^\d+$/.test(dniValue)) {
    alert("Por favor, introduce un DNI válido de 8 dígitos");
    return;
  }
  
  // Resetear colores de todas las casillas DNI
  canvas.getObjects().forEach(obj => {
    if (obj.name && obj.name.match(/^D\d\d$/) && !obj.name.includes('_label')) {
      obj.set({
        fill: 'rgba(0,255,0,0.3)',
        stroke: 'green'
      });
    }
  });
  
  // Colorear las casillas correspondientes al DNI
  for (let i = 0; i < dniValue.length; i++) {
    const digit = parseInt(dniValue.charAt(i));
    const name = `D${digit}${i}`;
    
    // Buscar y colorear la casilla
    canvas.getObjects().forEach(obj => {
      if (obj.name === name) {
        obj.set({
          fill: 'rgba(255,0,0,0.5)',
          stroke: 'red'
        });
      }
    });
  }
  
  canvas.renderAll();
  showTooltip(`Visualizando DNI: ${dniValue}`);
}

// Función para generar rejilla de respuestas
function generateAnswersGrid() {
  // Verificar zonas de referencia
  const zone1A = zones.find(z => z.name === '1A');
  const zone1B = zones.find(z => z.name === '1B');
  const zone1C = zones.find(z => z.name === '1C');
  const zone2A = zones.find(z => z.name === '2A');
  
  if (!zone1A || !zone1B || !zone1C || !zone2A) {
    alert("Por favor, primero crea manualmente las zonas 1A, 1B, 1C y 2A");
    return;
  }
  
  saveToHistory();
  
  // Calcular espaciados
  const horizontalSpacing = zone1B.left - zone1A.left;
  const verticalSpacing = zone2A.top - zone1A.top;
  const cellWidth = zone1A.width;
  const cellHeight = zone1A.height;
  
  // Parámetros
  const numQuestions = parseInt(document.getElementById('numQuestions').value) || 10;
  const options = ['A', 'B', 'C'];
  
  // Generar rejilla
  for (let question = 1; question <= numQuestions; question++) {
    for (let o = 0; o < options.length; o++) { // Máximo 5 opciones (A-E)
      const optionLetter = options[o];
      const name = `${question}${optionLetter}`;
      
      // Saltar zonas de referencia
      if ((question === 1 && optionLetter === 'A') || 
          (question === 1 && optionLetter === 'B') ||
          (question === 1 && optionLetter === 'C') ||
          (question === 2 && optionLetter === 'A')) {
        continue;
      }
      
      const left = zone1A.left + (o * horizontalSpacing);
      const top = zone1A.top + ((question - 1) * verticalSpacing);
      
      addZone(name, left, top, cellWidth, cellHeight, false);
    }
  }
  
  showTooltip("Rejilla de respuestas generada correctamente");
}

// Función para generar rejilla completa de respuestas (4 columnas, en grupos de 3 filas)
function generateCompleteAnswersGrid() {
  // Verificar zonas de anclaje necesarias
  // Necesitamos más puntos de anclaje para mayor precisión
  
  // Primera columna: verificamos puntos de anclaje para cada grupo de 3 filas
  const anchors = [
    { start: 1, anchors: ['1A', '1B', '4A'] },      // Filas 1-3
    { start: 4, anchors: ['4A', '4B', '7A'] },      // Filas 4-6
    { start: 7, anchors: ['7A', '7B', '10A'] },     // Filas 7-9
    { start: 10, anchors: ['10A', '10B', '13A'] },  // Filas 10-12
    { start: 13, anchors: ['13A', '13B', '16A'] },  // Filas 13-15
    
    // Segunda columna
    { start: 16, anchors: ['16A', '16B', '19A'] },  // Filas 16-18
    { start: 19, anchors: ['19A', '19B', '22A'] },  // Filas 19-21
    { start: 22, anchors: ['22A', '22B', '25A'] },  // Filas 22-24
    { start: 25, anchors: ['25A', '25B', '28A'] },  // Filas 25-27
    { start: 28, anchors: ['28A', '28B', '31A'] },  // Filas 28-30
    
    // Tercera columna
    { start: 31, anchors: ['31A', '31B', '34A'] },  // Filas 31-33
    { start: 34, anchors: ['34A', '34B', '37A'] },  // Filas 34-36
    { start: 37, anchors: ['37A', '37B', '40A'] },  // Filas 37-39
    { start: 40, anchors: ['40A', '40B', '43A'] },  // Filas 40-42
    { start: 43, anchors: ['43A', '43B', '46A'] },  // Filas 43-45
    
    // Cuarta columna
    { start: 46, anchors: ['46A', '46B', '49A'] },  // Filas 46-48
    { start: 49, anchors: ['49A', '49B', null] }    // Filas 49-50 (solo 2 filas)
  ];
  
  // Verificar que existan todos los puntos de anclaje necesarios
  for (const group of anchors) {
    // El tercer punto puede ser null en el último grupo
    if (group.anchors[2] === null && group.start === 49) {
      // Para el último grupo, solo verificamos los primeros dos puntos
      const zone1 = zones.find(z => z.name === group.anchors[0]);
      const zone2 = zones.find(z => z.name === group.anchors[1]);
      
      if (!zone1 || !zone2) {
        alert(`Por favor, crea manualmente los puntos de anclaje ${group.anchors[0]} y ${group.anchors[1]} para las preguntas ${group.start}-${group.start+1}`);
        return;
      }
    } else {
      // Para el resto de grupos, verificamos los tres puntos
      const zone1 = zones.find(z => z.name === group.anchors[0]);
      const zone2 = zones.find(z => z.name === group.anchors[1]);
      const zone3 = zones.find(z => z.name === group.anchors[2]);
      
      if (!zone1 || !zone2 || !zone3) {
        alert(`Por favor, crea manualmente los puntos de anclaje ${group.anchors[0]}, ${group.anchors[1]} y ${group.anchors[2]} para las preguntas ${group.start}-${group.start+2}`);
        return;
      }
    }
  }
  
  saveToHistory();
  
  // Generar cada grupo de 3 filas
  for (const group of anchors) {
    const zone1 = zones.find(z => z.name === group.anchors[0]);
    const zone2 = zones.find(z => z.name === group.anchors[1]);
    
    // El último grupo solo tiene 2 filas
    if (group.start === 49) {
      generateSmallGrid(group.start, group.start + 1, zone1, zone2);
    } else {
      const zone3 = zones.find(z => z.name === group.anchors[2]);
      generateSmallGrid(group.start, group.start + 2, zone1, zone2, zone3);
    }
  }
  
  showTooltip("Rejilla completa de 50 preguntas generada correctamente");
}

// Función auxiliar para generar un pequeño grupo de preguntas (3 filas max)
function generateSmallGrid(startQuestion, endQuestion, startZone, optionBZone, nextRowZone = null) {
  // Calcular espaciados
  const horizontalSpacing = optionBZone.left - startZone.left;
  let verticalSpacing = 0;
  
  if (nextRowZone) {
    verticalSpacing = (nextRowZone.top - startZone.top) / (endQuestion - startQuestion);
  } else {
    // Para el último grupo (49-50), estimamos el espaciado basado en el ancho
    // Normalmente, el alto de una celda es aprox. igual a su ancho
    verticalSpacing = horizontalSpacing;
  }
  
  const cellWidth = startZone.width;
  const cellHeight = startZone.height;
  
  // Opciones (A, B, C)
  const options = ['A', 'B', 'C']; 
  
  // Generar rejilla para este grupo
  for (let question = startQuestion; question <= endQuestion; question++) {
    for (let o = 0; o < options.length; o++) {
      const optionLetter = options[o];
      const name = `${question}${optionLetter}`;
      
      // Saltar si ya existe (punto de anclaje)
      if (zones.some(z => z.name === name)) {
        continue;
      }
      
      const left = startZone.left + (o * horizontalSpacing);
      const top = startZone.top + ((question - startQuestion) * verticalSpacing);
      
      addZone(name, left, top, cellWidth, cellHeight, false);
    }
  }
}

// Función auxiliar para generar cada columna de la rejilla
function generateColumnGrid(startQuestion, endQuestion, startZone, optionBZone = null, secondRowZone = null, referenceZoneA = null, referenceZoneB = null, referenceSecondRow = null) {
  // Si no tenemos zonas B y segunda fila para esta columna, calculamos basados en la referencia
  let horizontalSpacing, verticalSpacing, cellWidth, cellHeight;
  
  if (optionBZone && secondRowZone) {
    // Usamos las zonas propias de esta columna
    horizontalSpacing = optionBZone.left - startZone.left;
    verticalSpacing = secondRowZone.top - startZone.top;
    cellWidth = startZone.width;
    cellHeight = startZone.height;
  } else {
    // Calculamos basados en las zonas de referencia (normalmente de columna 1)
    horizontalSpacing = referenceZoneB.left - referenceZoneA.left;
    verticalSpacing = referenceSecondRow.top - referenceZoneA.top;
    cellWidth = startZone.width || referenceZoneA.width;
    cellHeight = startZone.height || referenceZoneA.height;
  }
  
  // Opciones (A, B, C)
  const options = ['A', 'B', 'C']; 
  
  // Generar rejilla para esta columna
  for (let question = startQuestion; question <= endQuestion; question++) {
    for (let o = 0; o < options.length; o++) {
      const optionLetter = options[o];
      const name = `${question}${optionLetter}`;
      
      // Saltar si ya existe (probablemente es una zona de anclaje)
      if (zones.some(z => z.name === name)) {
        continue;
      }
      
      const left = startZone.left + (o * horizontalSpacing);
      const top = startZone.top + ((question - startQuestion) * verticalSpacing);
      
      addZone(name, left, top, cellWidth, cellHeight, false);
    }
  }
}
