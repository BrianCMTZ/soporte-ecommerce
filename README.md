# TechShell — Plataforma E-Commerce con Soporte IA Multi-Agente

Aplicación de escritorio para tienda de e-comerce (**TechShell** / atención al cliente **La Esquina Tech**) construida en Python con **CustomTkinter** y un chatbot de soporte basado en una arquitectura **multi-agente** impulsada por la API de **Google Gemini** (`google-genai`). También incluye una interfaz alternativa en línea de comandos.

---

## Arquitectura Multi-Agente

El flujo conversacional está desacoplado de la interfaz gráfica y se orquesta desde `agentes.py` mediante `procesar_mensaje()`:

```text
Mensaje del cliente (+ historial y contexto en vivo)
        │
        ▼
┌───────────────────────────────────────────────────────────┐
│  Agente 1 — Analista de Base de Datos (temperature = 0.0) │
│  • Consulta base_datos.json (recargado desde disco)       │
│  • Lee catálogo y carrito en vivo (desde interfaz_tienda) │
│  • Extrae hechos exactos sin inventar datos               │
└───────────────────────────────────────────────────────────┘
        │  Datos crudos verificados
        ▼
┌───────────────────────────────────────────────────────────┐
│  Agente 2 — Atención al Cliente (temperature = 0.7)       │
│  • Redacta una respuesta empática, clara y en texto plano │
│  • Controla saludos según inicio o conversación en curso  │
│  • Protege privacidad (no expone nombres de titulares)    │
└───────────────────────────────────────────────────────────┘
        │
        ▼
Respuesta final al cliente
```

- `IA.py` actúa como puente entre `interfaz_tienda.py` y `agentes.py`, traduciendo el historial de la UI (`"usuario"` / `"bot"`) al formato esperado por los agentes (`"user"` / `"assistant"`) y pasando el catálogo y carrito en vivo.

---

## Características principales

- **Catálogo de productos**: tarjetas con categoría, etiqueta promocional, imagen, precio y botón para agregar al carrito.
- **Carrito de compras**: agrupación automática de artículos repetidos, cálculo de subtotales/total, eliminación de productos y flujo de pago simulado.
- **Modo Oscuro / Claro**: cambio dinámico de tema desde la barra superior.
- **Chatbot asíncrono**: consultas a la API en segundo plano (`threading` + `queue.Queue`) sin bloquear la interfaz gráfica.
- **Panel colapsable de Preguntas Frecuentes**: cargado dinámicamente desde `base_datos.json` junto con botones de sugerencias rápidas (`Ver catálogo`, `¿Qué ofertas hay?`, `Costo de envío`, `¿Qué hay en mi carrito?`).
- **Seguimiento de pedidos y políticas**: consultas sobre envíos, pagos, devoluciones, facturación, garantías y estado de pedidos registrados en `base_datos.json` (por ejemplo `#432`, `#105`, `#189`).
- **Modo consola**: ejecución independiente en terminal mediante `main_consola.py`.

---

## Estructura del proyecto

```text
soporte-ecommerce/
├── interfaz_tienda.py   # Aplicación principal de escritorio (CustomTkinter + Pillow)
├── main_consola.py      # Interfaz alternativa de chat en consola
├── IA.py                # Adaptador entre la interfaz gráfica y los agentes
├── agentes.py           # Orquestador y lógica multi-agente con Google Gemini
├── base_datos.json      # Base de conocimiento (FAQ) e índice de pedidos
├── img/                 # Recursos gráficos (logo, ícono del bot e imágenes de productos)
├── requirements.txt     # Dependencias de Python del proyecto
├── .env.example         # Plantilla de variables de entorno
├── .gitignore           # Exclusión de secretos (.env), entorno virtual y caché
└── README.md            # Documentación del proyecto
```

---

## Requisitos previos

- **Python 3.10 o superior** (con soporte para `tkinter` incluido en la instalación estándar de Python en Windows).
- Una **API Key de Google Gemini** (puedes generarla en [Google AI Studio](https://aistudio.google.com/apikey)).

---

## Instalación y configuración

1. **Clonar el repositorio**

   ```bash
   git clone https://github.com/BrianCMTZ/soporte-ecommerce.com
   cd soporte-ecommerce
   ```

2. **Crear y activar un entorno virtual**

   En Windows (PowerShell):
   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```

   En Windows (CMD):
   ```cmd
   python -m venv venv
   venv\Scripts\activate.bat
   ```

   En macOS / Linux:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Instalar dependencias**

   ```bash
   pip install -r requirements.txt
   ```

4. **Configurar variables de entorno**

   Copia `.env.example` a `.env` y coloca tu clave real de Gemini:

   ```bash
   # Windows PowerShell
   Copy-Item .env.example .env

   # macOS / Linux
   cp .env.example .env
   ```

   Edita `.env`:
   ```env
   GEMINI_API_KEY=tu_clave_real_de_gemini
   # GEMINI_MODEL=gemini-3.5-flash-lite
   ```

---

## Ejecución

### Interfaz gráfica (Tienda TechShell + Chatbot)

```bash
python interfaz_tienda.py
```

### Interfaz de consola (solo chatbot de soporte)

```bash
python main_consola.py
```

*(En consola no se envía catálogo ni carrito en vivo; las consultas se responden usando `base_datos.json`.)*

---

## Personalización

- **Base de conocimiento y pedidos (`base_datos.json`)**: `agentes.py` lee el archivo desde disco en cada consulta (`cargar_base_datos()` y `obtener_preguntas_frecuentes()`), por lo que cualquier modificación en las preguntas frecuentes o en `indice_pedidos` se refleja de inmediato sin reiniciar la aplicación.
- **Preguntas frecuentes destacadas**: puedes editar la lista `PREGUNTAS_FRECUENTES_IDS` (actualmente `[1, 101, 3, 2, 12]`) en `agentes.py`, o agregar un campo numérico `"frecuencia"` a las entradas de `base_datos.json` para ordenarlas automáticamente.
- **Modelo de Gemini**: por defecto se utiliza `gemini-3.5-flash-lite`. Puedes cambiarlo sin modificar el código definiendo `GEMINI_MODEL` en tu archivo `.env`.
