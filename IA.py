"""
IA.py
=====
Puente entre la interfaz de la tienda (interfaz_tienda.py) y los agentes (agentes.py).

La interfaz espera una función con esta firma:
    responder_chatbot(mensaje: str, contexto: dict) -> str

donde `contexto` contiene:
    "catalogo":  lista de productos (dicts) que se muestran en la tienda
    "carrito":   lista de productos (dicts) que el cliente tiene en el carrito
    "historial": lista de tuplas ("usuario" | "bot", texto), INCLUYENDO el mensaje actual

Este módulo solo traduce formatos; toda la lógica vive en agentes.py.
"""

from agentes import obtener_preguntas_frecuentes, procesar_mensaje  # noqa: F401 (se re-exporta)

# La interfaz usa "usuario"/"bot"; los agentes usan "user"/"assistant"
_ROLES = {"usuario": "user", "bot": "assistant"}


def _convertir_historial(historial_ui: list, mensaje: str) -> list:
    """Traduce el historial de la interfaz al formato de los agentes."""
    historial = []
    for elemento in historial_ui or []:
        try:
            remitente, texto = elemento
        except (TypeError, ValueError):
            continue
        historial.append({"role": _ROLES.get(remitente, "assistant"), "content": str(texto)})

    # La interfaz ya agregó el mensaje actual al final del historial; se quita
    # porque procesar_mensaje() lo recibe por separado (evita duplicarlo).
    if historial and historial[-1]["role"] == "user" and historial[-1]["content"] == mensaje:
        historial.pop()
    return historial


def responder_chatbot(mensaje: str, contexto: dict) -> str:
    """Punto de entrada que llama la interfaz de la tienda."""
    contexto = contexto or {}
    historial = _convertir_historial(contexto.get("historial", []), mensaje)

    # Datos en vivo de la tienda para que el Agente 1 pueda hablar de productos y carrito
    contexto_extra = {k: contexto[k] for k in ("catalogo", "carrito") if k in contexto}

    return procesar_mensaje(mensaje, historial, contexto_extra)
