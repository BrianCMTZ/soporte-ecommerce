"""
agentes.py
==========
Lógica de la arquitectura Multi-Agente (sin ninguna dependencia de interfaz).

Flujo:
    Mensaje del usuario
        └─► Agente 1 (Analista de BD, temp 0.0) ── consulta base_datos.json
                └─► Agente 2 (Atención al Cliente, temp 0.7) ── redacta la respuesta

Punto de entrada público para cualquier interfaz (consola, Tkinter, web...):
    procesar_mensaje(mensaje_usuario: str, historial: list) -> str
"""

import json
import os
import re
from collections import Counter

from dotenv import load_dotenv
from google import genai
from google.genai import types

# ---------------------------------------------------------------------------
# CONFIGURACIÓN GENERAL
# ---------------------------------------------------------------------------

# Carga las variables del archivo .env (GEMINI_API_KEY)
load_dotenv()

# Modelo a utilizar por ambos agentes.
# Por defecto gemini-2.5-flash; puedes cambiarlo sin tocar el código agregando
# GEMINI_MODEL=nombre-del-modelo en tu archivo .env
MODELO = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")

# Ruta del JSON, siempre relativa a este archivo (funciona desde cualquier carpeta)
RUTA_BASE_DATOS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "base_datos.json")

# Cantidad máxima de mensajes recientes del historial que se envían a los agentes
MAX_MENSAJES_HISTORIAL = 6

# Nombre de la tienda (lo usa el Agente 2 para presentarse)
NOMBRE_TIENDA = "La Esquina Tech"

# Preguntas frecuentes que se muestran al abrir la interfaz.
# Tu base de datos no incluye un contador de frecuencia, así que se eligen por "id".
# Cambia estos números por los id de las preguntas que quieras mostrar.
# (Si algún día agregas un campo numérico "frecuencia" a las entradas del JSON,
#  se usará ese campo automáticamente para elegir las más frecuentes.)
PREGUNTAS_FRECUENTES_IDS = [1, 101, 3, 2, 12]
CANTIDAD_PREGUNTAS_FRECUENTES = 5

# Valores centinela que devuelve el Agente 1
DATO_NO_ENCONTRADO = "DATO_NO_ENCONTRADO"
SIN_CONSULTA_DE_DATOS = "SIN_CONSULTA_DE_DATOS"
REQUIERE_NUMERO_PEDIDO = "REQUIERE_NUMERO_PEDIDO"

# Cliente de Gemini (se crea una sola vez, la primera vez que se necesita)
_cliente = None


def _obtener_cliente() -> genai.Client:
    """Crea (o reutiliza) el cliente de la API de Gemini leyendo la key del .env."""
    global _cliente
    if _cliente is None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key or api_key == "tu_api_key_aqui":
            raise RuntimeError(
                "No se encontró GEMINI_API_KEY. Crea un archivo .env con tu API Key "
                "(consulta .env.example)."
            )
        _cliente = genai.Client(api_key=api_key)
    return _cliente


# ---------------------------------------------------------------------------
# UTILIDADES
# ---------------------------------------------------------------------------

def cargar_base_datos() -> str:
    """
    Lee base_datos.json DESDE DISCO en cada llamada, de modo que cualquier cambio
    al archivo se refleje de inmediato sin reiniciar la aplicación.
    Devuelve el contenido como texto JSON formateado.
    """
    with open(RUTA_BASE_DATOS, "r", encoding="utf-8") as archivo:
        datos = json.load(archivo)
    return json.dumps(datos, ensure_ascii=False, indent=1)


def obtener_preguntas_frecuentes(cantidad: int = CANTIDAD_PREGUNTAS_FRECUENTES) -> list:
    """
    Devuelve una lista con los textos de las preguntas más frecuentes para mostrarlas
    en la interfaz. Lee el JSON desde disco, así que respeta cualquier cambio de base.

    Criterio:
      1) Si las entradas tienen un campo numérico "frecuencia", usa las de mayor valor.
      2) Si no, usa los id definidos en PREGUNTAS_FRECUENTES_IDS.
      3) Si faltan, completa con las primeras preguntas de la base de datos.
    Nunca lanza excepciones: si algo falla devuelve una lista vacía.
    """
    try:
        with open(RUTA_BASE_DATOS, "r", encoding="utf-8") as archivo:
            datos = json.load(archivo)
    except (OSError, json.JSONDecodeError):
        return []

    if not isinstance(datos, list):
        return []
    entradas = [e for e in datos if isinstance(e, dict) and e.get("pregunta")]

    con_frecuencia = [e for e in entradas if isinstance(e.get("frecuencia"), (int, float))]
    if con_frecuencia:
        con_frecuencia.sort(key=lambda e: e["frecuencia"], reverse=True)
        return [e["pregunta"] for e in con_frecuencia[:cantidad]]

    por_id = {e.get("id"): e for e in entradas}
    elegidas = [por_id[i]["pregunta"] for i in PREGUNTAS_FRECUENTES_IDS if i in por_id]
    for entrada in entradas:
        if len(elegidas) >= cantidad:
            break
        if entrada["pregunta"] not in elegidas:
            elegidas.append(entrada["pregunta"])
    return elegidas[:cantidad]


def _precio_a_numero(precio) -> float:
    """Convierte precios como '$18,500' o 1200 a número (0.0 si no se puede)."""
    if isinstance(precio, (int, float)):
        return float(precio)
    texto = re.sub(r"[^\d.]", "", str(precio))
    try:
        return float(texto) if texto else 0.0
    except ValueError:
        return 0.0


def formatear_contexto_extra(contexto_extra: dict) -> str:
    """
    Convierte los datos EN VIVO de la tienda (catálogo y carrito, que envía la interfaz)
    en texto para el Agente 1. El total del carrito se calcula aquí en Python para que
    el modelo no tenga que hacer aritmética.
    """
    if not contexto_extra:
        return ""

    secciones = []

    catalogo = contexto_extra.get("catalogo")
    if catalogo is not None:
        lineas = [
            f"- {p.get('nombre')} | precio: {p.get('precio')} | categoría: {p.get('categoria')} "
            f"| etiqueta: {p.get('tag') or 'ninguna'}"
            for p in catalogo if isinstance(p, dict)
        ]
        secciones.append("CATÁLOGO ACTUAL DE LA TIENDA:\n" + ("\n".join(lineas) or "(vacío)"))

    carrito = contexto_extra.get("carrito")
    if carrito is not None:
        items = [p for p in carrito if isinstance(p, dict)]
        if not items:
            texto = "Carrito vacío (0 artículos)."
        else:
            cuenta = Counter(p.get("nombre") for p in items)
            precios = {p.get("nombre"): p.get("precio") for p in items}
            lineas = [f"- {n} x {c} (precio unitario: {precios[n]})" for n, c in cuenta.items()]
            total = sum(_precio_a_numero(p.get("precio")) for p in items)
            texto = (
                "\n".join(lineas)
                + f"\nTotal de artículos: {len(items)}"
                + f"\nTotal calculado del carrito: ${total:,.0f}"
            )
        secciones.append("CARRITO ACTUAL DEL CLIENTE:\n" + texto)

    return "\n\n".join(secciones)


def formatear_historial(historial: list) -> str:
    """
    Convierte el historial (lista de dicts {"role": "user"|"assistant", "content": str})
    en texto plano, limitado a los últimos MAX_MENSAJES_HISTORIAL mensajes.
    """
    if not historial:
        return "(Sin historial previo)"

    lineas = []
    for mensaje in historial[-MAX_MENSAJES_HISTORIAL:]:
        autor = "Cliente" if mensaje.get("role") == "user" else "Asistente"
        lineas.append(f"{autor}: {mensaje.get('content', '')}")
    return "\n".join(lineas)


# ---------------------------------------------------------------------------
# AGENTE 1: ANALISTA DE BASE DE DATOS (temperatura 0.0)
# ---------------------------------------------------------------------------

INSTRUCCION_AGENTE_1 = f"""Eres un Analista de Base de Datos. Tu ÚNICA función es extraer hechos exactos
de los DATOS que se te proporcionan para responder a la consulta del cliente.

FUENTES DE DATOS:
A) BASE DE DATOS JSON: una lista de entradas. Casi todas son preguntas frecuentes con los campos
   "categoria", "pregunta" y "respuesta" (envíos, pagos, devoluciones, cupones, cuenta, tienda
   física, productos, facturación, garantía, etc.). Existe una entrada especial (categoría
   "Pedidos Realizados") con el campo "indice_pedidos": un diccionario donde cada CLAVE es el
   número de pedido (ej. "#432") y cada valor son los datos de ese pedido.
B) CATÁLOGO ACTUAL DE LA TIENDA (opcional): productos disponibles hoy, con precio, categoría y etiqueta.
C) CARRITO ACTUAL DEL CLIENTE (opcional): productos que el cliente tiene en su carrito ahora,
   con el total ya calculado.
Las secciones B y C solo existen si aparecen en el mensaje; si no aparecen, no tienes ese dato.

REGLAS ESTRICTAS:
1. Usa EXCLUSIVAMENTE la información presente en los DATOS. Jamás inventes, supongas ni completes datos.
2. CONSULTAS DE PEDIDOS: busca el número mencionado (con o sin "#") como clave EXACTA dentro de
   "indice_pedidos". Los números parecidos NO cuentan (#434 no es #432). Si la clave existe, devuelve
   SOLO los datos de ese pedido (todos sus campos). Si no existe, responde exactamente: {DATO_NO_ENCONTRADO}
3. Nunca devuelvas datos de pedidos distintos al consultado, ni el listado/índice rápido de pedidos
   que aparece en el campo "respuesta" de la entrada especial.
4. Si el cliente pregunta por el estado de un pedido pero NO da ningún número ni el historial lo
   contiene, responde exactamente: {REQUIERE_NUMERO_PEDIDO}
5. PRODUCTOS, PRECIOS Y OFERTAS: usa la sección CATÁLOGO ACTUAL. Devuelve los productos relevantes con
   nombre, precio, categoría y etiqueta. Las etiquetas (ej. "Envío gratis", "-15% OFF", "Más vendido")
   son las únicas promociones que existen: no inventes otras. Si la consulta es "ver el catálogo",
   devuelve todos los productos.
6. CARRITO: usa la sección CARRITO ACTUAL. Devuelve sus productos y el total tal como aparece
   (no recalcules). Si está vacío, devuelve: Carrito vacío.
7. CONSULTAS GENERALES (políticas, envíos, pagos, garantía, etc.): devuelve textualmente el campo
   "respuesta" de la(s) entrada(s) de preguntas frecuentes que respondan a la consulta (máximo 3),
   indicando su categoría. No mezcles información de entradas que no sean relevantes.
8. Usa el historial solo para resolver referencias (por ejemplo, "ese pedido", "¿y cuándo llega?").
9. Si ninguna fuente contiene la información solicitada (o falta la sección necesaria), responde
   exactamente: {DATO_NO_ENCONTRADO}
10. Si la consulta es un saludo o no requiere datos (ej. "hola", "gracias"), responde exactamente: {SIN_CONSULTA_DE_DATOS}
11. Responde en texto plano, con formato clave: valor, sin saludos, sin explicaciones y sin redacción amable.
    Tu salida será leída por otro sistema, no por el cliente."""


def agente_analista_bd(mensaje_usuario: str, historial: list, contexto_extra: dict = None) -> str:
    """
    Agente 1: consulta la base de datos (y, si se envían, el catálogo y carrito en vivo)
    con temperatura 0.0 y devuelve datos crudos.
    """
    base_datos = cargar_base_datos()
    extra = formatear_contexto_extra(contexto_extra)
    bloque_extra = f"{extra}\n\n" if extra else ""

    prompt = (
        f"BASE DE DATOS JSON:\n{base_datos}\n\n"
        f"{bloque_extra}"
        f"HISTORIAL RECIENTE:\n{formatear_historial(historial)}\n\n"
        f"CONSULTA ACTUAL DEL CLIENTE:\n{mensaje_usuario}\n\n"
        f"Extrae los datos exactos necesarios (o responde {DATO_NO_ENCONTRADO})."
    )

    respuesta = _obtener_cliente().models.generate_content(
        model=MODELO,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=INSTRUCCION_AGENTE_1,
            temperature=0.0,  # Determinista: cero creatividad, solo hechos
        ),
    )
    return (respuesta.text or DATO_NO_ENCONTRADO).strip()


# ---------------------------------------------------------------------------
# AGENTE 2: ATENCIÓN AL CLIENTE (temperatura 0.7)
# ---------------------------------------------------------------------------

INSTRUCCION_AGENTE_2 = f"""Eres un agente de atención al cliente de {NOMBRE_TIENDA}, un e-commerce. Eres empático,
claro, cordial y profesional. Escribes en español (o en el idioma en que te escriba el cliente).

REGLAS:
1. Basa tus respuestas ÚNICAMENTE en los "DATOS VERIFICADOS" que recibes. Nunca inventes estados de
   pedido, fechas, números de guía, precios ni políticas.
2. Si los datos dicen {DATO_NO_ENCONTRADO}, indica con amabilidad que no pudiste localizar esa
   información, pide al cliente que verifique el número de pedido o dato proporcionado y ofrécele
   contactar a un agente humano. No inventes alternativas.
3. Si los datos dicen {REQUIERE_NUMERO_PEDIDO}, pide amablemente al cliente su número de pedido
   (por ejemplo #432) para poder consultar el estado.
4. Si los datos dicen {SIN_CONSULTA_DE_DATOS}, responde de forma natural y breve (por ejemplo, si
   agradece, di que fue un gusto) y pregunta en qué más puedes ayudar.
SALUDOS (muy importante): el mensaje incluye "ESTADO DE LA CONVERSACIÓN".
   - Si es INICIO: puedes saludar una sola vez de forma breve.
   - Si es EN_CURSO: NUNCA saludes ni empieces con "Hola", "Buenos días" o similares, aunque el
     cliente te salude otra vez; ve directo al punto. Tampoco repitas la presentación ni los mismos
     ofrecimientos de ayuda en cada mensaje.
5. Redacta de forma natural y concisa: ve al punto, destaca lo importante (estado, paquetería,
   fecha estimada, qué sigue) y cierra ofreciendo más ayuda cuando sea apropiado.
6. Si el cliente muestra molestia o preocupación (por ejemplo, entrega fallida), reconoce sus
   sentimientos antes de dar la información.
7. Por privacidad, no menciones el nombre completo del titular del pedido; refiérete al producto.
8. Nunca menciones que existen "agentes", "bases de datos", "JSON" o procesos internos.
9. No uses formato Markdown (sin asteriscos, sin #, sin listas con guiones); escribe en texto plano
   con saltos de línea simples."""


def agente_atencion_cliente(mensaje_usuario: str, historial: list, datos_crudos: str,
                            es_inicio: bool = False) -> str:
    """Agente 2: redacta la respuesta final al cliente usando los datos del Agente 1."""
    estado = "INICIO" if es_inicio else "EN_CURSO"
    prompt = (
        f"ESTADO DE LA CONVERSACIÓN: {estado}\n\n"
        f"HISTORIAL RECIENTE:\n{formatear_historial(historial)}\n\n"
        f"MENSAJE ACTUAL DEL CLIENTE:\n{mensaje_usuario}\n\n"
        f"DATOS VERIFICADOS:\n{datos_crudos}\n\n"
        "Redacta la respuesta para el cliente."
    )

    respuesta = _obtener_cliente().models.generate_content(
        model=MODELO,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=INSTRUCCION_AGENTE_2,
            temperature=0.7,  # Algo de naturalidad en la redacción
        ),
    )
    return (respuesta.text or "Lo siento, no pude generar una respuesta. ¿Podrías intentarlo de nuevo?").strip()


# ---------------------------------------------------------------------------
# ORQUESTADOR (punto de entrada para cualquier interfaz)
# ---------------------------------------------------------------------------

def procesar_mensaje(mensaje_usuario: str, historial: list, contexto_extra: dict = None) -> str:
    """
    Orquesta la cadena completa de agentes y devuelve la respuesta final como texto.

    Parámetros:
        mensaje_usuario: texto que escribió el cliente.
        historial: lista de mensajes previos, cada uno como
                   {"role": "user" | "assistant", "content": "texto"}.
                   Esta función NO modifica el historial; cada interfaz decide
                   cuándo y cómo guardar los mensajes.
        contexto_extra: (opcional) datos en vivo de la tienda, por ejemplo
                   {"catalogo": [...], "carrito": [...]}. La consola no lo usa.

    Retorna:
        La respuesta final lista para mostrarse al cliente. Nunca lanza excepciones:
        los errores se devuelven como un mensaje amable.
    """
    mensaje_usuario = (mensaje_usuario or "").strip()
    if not mensaje_usuario:
        return "Por favor escribe tu consulta para poder ayudarte."

    try:
        # Paso 1: el Analista extrae los hechos exactos de la base de datos
        datos_crudos = agente_analista_bd(mensaje_usuario, historial, contexto_extra)

        # Paso 2: el agente de atención redacta la respuesta empática
        # Es "inicio" solo si no hay NINGÚN mensaje previo (se evalúa sobre el historial completo,
        # no sobre la ventana reciente, para que no vuelva a saludar al rotar mensajes viejos)
        es_inicio = not historial
        return agente_atencion_cliente(mensaje_usuario, historial, datos_crudos, es_inicio)

    except FileNotFoundError:
        return "Error interno: no se encontró el archivo base_datos.json."
    except json.JSONDecodeError as error:
        return f"Error interno: base_datos.json tiene un formato JSON inválido ({error})."
    except RuntimeError as error:
        # Por ejemplo, falta la API Key
        return f"Error de configuración: {error}"
    except Exception as error:  # Errores de red, cuota, API, etc.
        return (
            "Lo siento, tuve un problema técnico al procesar tu consulta. "
            f"Por favor intenta de nuevo en un momento. (Detalle: {error})"
        )
