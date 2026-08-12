# 📊 Productivity Analysis Dashboard

Aplicación interactiva construida con **Streamlit** para analizar la productividad de equipos a través de distintos modelos según el cliente o tipo de servicio:

| Modelo | Cliente | Métrica | Lógica |
|---|---|---|---|
| 🟢 **Galderma** | Galderma | Story Points | More is Best |
| 🔵 **AMS** | AMS / Softtek | Horas de Esfuerzo | Less is Best |
| 🟠 **ITIS** | ITIS | Duración del Ticket (Horas) | Less is Best |

---

# 🚀 Cómo ejecutar

### Opción A — Línea de comandos
```bash
# Instalar dependencias
pip install -r requirements.txt

# Ejecutar
python -m streamlit run main.py
```
#### 🛠️ Dependencias

```
streamlit
pandas
numpy
plotly
openpyxl
```

### Opción B — Streamlit Cloud
```
https://appcopygit-wvg8kuvbnjb2spu2pco42l.streamlit.app/
```

---

## 📂 Formato del archivo Excel

La app detecta automáticamente el modelo seleccionado y busca columnas clave. La hoja de datos debe llamarse **`RawData`** o **`Data Template`** (o ser la primera hoja del archivo).

### Modelo AMS — Columnas requeridas
| Columna | Descripción | Requerida |
|---|---|---|
| `Assigned To` | Nombre completo del recurso | ✅ Sí |
| `IS` | Siglas del recurso (ej: `CFPN1`) | No |
| `Group` | Grupo o equipo | ✅ Sí |
| `WBS` | Código del proyecto WBS | ✅ Sí |
| `EndDate` | Fecha de cierre del ticket | ✅ Sí |
| `Effort` | Horas invertidas en el ticket | ✅ Sí |
| `Service Type` | Tipo de servicio (Change / Service) | No |
| `Category` | Categoría del ticket | No |

> El sistema también acepta variantes: `Assignee`, `Resource` en lugar de `Assigned To`; `End Date` en lugar de `EndDate`.

### Modelo Galderma — Columnas requeridas
| Columna | Descripción | Requerida |
|---|---|---|
| `Developer` | Nombre del desarrollador (acepta múltiples con `/`) | ✅ Sí (o QA Tester) |
| `QA Tester` | Tester asignado | No |
| `Points` | Story points entregados (se dividen entre Devs) | ✅ Sí |
| `Period` | Período del mes (fecha) | ✅ Sí |
| `Status` | Estado del ticket (ej: `Closed`, `Ready to Deploy`) | ✅ Sí |

### Modelo ITIS — Columnas requeridas
| Columna | Descripción | Requerida |
|---|---|---|
| `Assignee` | Nombre del recurso asignado | ✅ Sí |
| `Ticket Type` | Tipo de ticket | ✅ Sí |
| `Ticket Closed/Resolved Date` | Fecha de cierre del ticket | ✅ Sí |
| `Ticket Duration` | Tiempo invertido en minutos | ✅ Sí |

### Controles del panel lateral
| Control | Descripción |
|---|---|
| **Select productivity model** | Alterna entre Galderma (Points), AMS (Effort) e ITIS (Duration) |
| **Upload Excel file** | Carga el archivo `.xlsx` con los datos |
| **Analyze by** | Dimensión de análisis (ej: `Assigned To`, `Ticket Type`, `Developer`, etc.) |
| **Select values** | Filtra qué recursos o categorías incluir en el análisis |
| **Analysis mode** | `Individual`: una línea por valor. `Global`: todos combinados en una sola serie de equipo |
| **Charts to show** | Selecciona cuáles gráficas renderizar en pantalla |
| **Rango de Fechas** | Slider interactivo para filtrar el período visualizado. *(El filtro se aplica al final del proceso para no afectar el historial matemático del baseline)*. |

---

## ⚙️ Controles del panel lateral

| Control | Descripción |
|---|---|
| **Select productivity model** | Alterna entre Galderma (Points) y AMS (Effort) |
| **Upload Excel file** | Carga el archivo `.xlsx` con los datos |
| **Analyze by** | Dimensión de análisis: `Assigned To`, `IS`, `Group`, `WBS`, `Service Type`, etc. |
| **Select values** | Filtra qué recursos o grupos mostrar en los gráficos |
| **Analysis mode** | `Individual`: una línea por recurso. `Global`: todos combinados en una sola serie |
| **Charts to show** | Selecciona cuáles gráficas renderizar |

---

## 📐 Lógica de cálculo

El motor de productividad compara el desempeño actual contra una línea base histórica mediante ventanas deslizantes. El sistema ahora permite calcular métricas en paralelo con ventanas de 3 Meses y 1 Mes.

### Parámetros de ventana

```
CURRENT_SIZE  = 3  → Meses más recientes que se evalúan
GAP_SIZE      = 3  → Meses de separación entre ventanas (amortiguador)
BASELINE_SIZE = 3  → Meses históricos usados como referencia
```

**Representación en el tiempo (del más reciente al más antiguo):**
```
[ Mes-1, Mes-2, Mes-3 ] → Ventana ACTUAL   (lo que medimos)
[ Mes-4, Mes-5, Mes-6 ] → GAP              (se ignora)
[ Mes-7, Mes-8, Mes-9 ] → Ventana BASELINE (la referencia)
```

> Si el recurso tiene **menos de 9 períodos** de historia, el baseline se toma de los últimos registros disponibles sin respetar el GAP (modo degradado).

---

### Paso 1 — Agregación mensual

Para cada combinación de `(Período, Dimensión)` se calculan tres valores:

| Campo | Descripción |
|---|---|
| `n` | Cantidad de tickets en ese mes |
| `Sum` | Suma total de la métrica (Effort, Duration/Hrs o Points) |
| `Mean` | Promedio matemático de la métrica por ticket |

**Ejemplo AMS:**

| Period | Assigned To | n | Sum (Effort) | Mean |
|---|---|---|---|---|
| Ene-2025 | Juan Pérez | 12 | 96 h | 8.0 h |
| Feb-2025 | Juan Pérez | 15 | 105 h | 7.0 h |
| Mar-2025 | Juan Pérez | 10 | 90 h | 9.0 h |

---

### Paso 2 — EpU de Baseline (Esfuerzo por Unidad)

Mide cuánto esfuerzo/puntos requería en promedio **cada ticket** durante el período de referencia histórica.

```
EpU_BL = Sum_baseline / n_baseline
```

**Ejemplo:**
```
Baseline (Meses 7-8-9):  Sum = 291 h,  n = 37 tickets
EpU_BL = 291 / 37 = 7.86 h por ticket
```

---

### Paso 3 — Esfuerzo Esperado (Base Equivalent)

¿Cuánto esfuerzo habría consumido el volumen actual **si se mantuviera la eficiencia del baseline?**

```
Base_Equiv = EpU_BL × n_actual
```

**Ejemplo:**
```
Ventana actual: n = 37 tickets
Base_Equiv = 7.86 × 37 = 290.8 h  ← lo que "debería" haber tomado
```

---

### Paso 4 — Índice de Productividad

```
Productividad = ((Effort_actual - Base_Equiv) / Base_Equiv) × σ
```

Donde **σ** depende del modelo:

| Modelo | σ | Razón |
|---|---|---|
| AMS / ITIS — Less is Best | **-1** | Menos horas = bueno → el resultado se invierte para que positivo = mejora |
| Galderma — More is Best | **+1** | Más puntos = bueno → sin inversión |


**Ejemplo AMS (Less is Best):**
```
Effort_actual = 270 h   → gastó menos de lo esperado ✅
Base_Equiv    = 290.8 h

Productividad = ((270 - 290.8) / 290.8) × (-1)
              = (-0.0715) × (-1)
              = +0.0715  →  +7.15%  ← mejora de productividad
```

**Ejemplo con deterioro:**
```
Effort_actual = 320 h   → gastó más de lo esperado ❌
Base_Equiv    = 290.8 h

Productividad = ((320 - 290.8) / 290.8) × (-1)
              = (0.1003) × (-1)
              = -0.1003  →  -10.03%  ← deterioro
```

---

### Cómo leer los gráficos

| Valor | Significado |
|---|---|
| **> 0%** | Mejora respecto al baseline (consume menos o entrega más) |
| **= 0%** | Igual al baseline |
| **< 0%** | Deterioro respecto al baseline |

La **línea punteada negra** en los gráficos marca el 0% (nivel de baseline).

---

### Modo Individual vs Global

| Modo | Comportamiento |
|---|---|
| **Individual** | Calcula productividad por separado para cada recurso. Permite ver quién mejora y quién no. |
| **Global** | Agrega todos los recursos seleccionados en una sola serie. Refleja el desempeño del equipo completo. |

---

### Gráficos disponibles
| Gráfico | Descripción |
|---|---|
| **Productivity Over Time** | Índice de productividad en % vs el baseline (Ventana de 3 Meses). |
| **Velocity 3M** | Compara la métrica Real vs Esperada evaluada en bloques móviles de 3 meses. |
| **Velocity per Month** | Compara la métrica Real vs Esperada evaluada mes a mes (Ventana de 1 Mes). |
| **Count Over Time** | Cantidad de tickets procesados en el período. |
| **Mean Over Time** | Promedio (`Mean`) de la métrica calculada por ticket en el mes. |

