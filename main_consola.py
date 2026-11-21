"""
main_consola.py
===============
Interfaz de consola para el chatbot de soporte.
Ejecutar con:  python main_consola.py
"""

from agentes import procesar_mensaje


def main():
    print("=" * 60)
    print("  SOPORTE AL CLIENTE - Chat en consola")
    print("  Escribe 'salir' para terminar.")
    print("=" * 60)

    # Historial en formato [{"role": "user"|"assistant", "content": "..."}]
    historial = []

    while True:
        try:
            mensaje = input("\nTú: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n¡Hasta luego!")
            break

        if not mensaje:
            continue
        if mensaje.lower() in ("salir", "exit", "quit"):
            print("Asistente: ¡Gracias por contactarnos! Que tengas un excelente día.")
            break

        print("Asistente: (escribiendo...)", end="\r")
        respuesta = procesar_mensaje(mensaje, historial)
        print(" " * 40, end="\r")  # Limpia la línea "escribiendo..."
        print(f"Asistente: {respuesta}")

        # Guardamos el intercambio en el historial para dar contexto a los agentes
        historial.append({"role": "user", "content": mensaje})
        historial.append({"role": "assistant", "content": respuesta})


if __name__ == "__main__":
    main()
