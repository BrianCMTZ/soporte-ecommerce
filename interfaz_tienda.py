import os
import queue
import threading
import customtkinter as ct
from PIL import Image

# ==============================================================================
# PUENTE DE CONEXIÓN CON LOS AGENTES DE IA
# IA.py expone `responder_chatbot(mensaje, contexto)` y re-exporta
# `obtener_preguntas_frecuentes()`; ambos usan agentes.py y base_datos.json.
# Si IA.py no se puede importar (por ejemplo, falta instalar una librería), la
# interfaz sigue funcionando y muestra el motivo en el encabezado del chat.
# ==============================================================================
try:
    from IA import responder_chatbot as procesar_mensaje_ia
    from IA import obtener_preguntas_frecuentes

    error_modulo_ia = None
except Exception as _error:  # ImportError u otro fallo al cargar IA.py / agentes.py
    procesar_mensaje_ia = None
    error_modulo_ia = str(_error)
    print(f"[Aviso] No se pudo cargar IA.py: {_error}")

    def obtener_preguntas_frecuentes():
        return []


ct.set_appearance_mode("Dark")
ct.set_default_color_theme("blue")


class tienda(ct.CTk):

    def __init__(self):
        super().__init__()

        self.title("TechShell")
        self.geometry("1150x720")
        self.minsize(950, 600)
        self.configure(fg_color=("#F4F6F9", "#0F172A"))

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Ruta base del proyecto para localizar siempre la carpeta img/
        self.ruta_base = os.path.dirname(os.path.abspath(__file__))

        # Estado de la aplicación
        self.carrito = []
        self.vista_actual = "inicio"
        self.modo_oscuro = True
        self.botones_nav = {}
        self.scroll_activo = None
        self.esperando_ia = False
        self.faq_visible = True  # Panel de preguntas frecuentes desplegado al abrir
        self.cola_ia = queue.Queue()  # Respuestas que llegan del hilo de la IA
        self.historial_chat = [
            (
                "bot",
                "¡Hola! 👋 Soy el asistente virtual de TechShell. ¿En qué te puedo ayudar hoy?",
            )
        ]

        # Base de datos de productos (se envía como contexto a la IA)
        self.productos_catalogo = [
            {
                "nombre": 'Laptop Pro 15"',
                "precio": "$18,500",
                "categoria": "Cómputo",
                "tag": "Envío gratis",
                "image": "img/laptop.jpg",
            },
            {
                "nombre": "Audífonos Bluetooth",
                "precio": "$1,200",
                "categoria": "Audio",
                "tag": "Más vendido",
                "image": "img/audifonos.jpg",
            },
            {
                "nombre": "Teclado Mecánico RGB",
                "precio": "$1,650",
                "categoria": "Periféricos",
                "tag": "-15% OFF",
                "image": "img/teclado.jpg",
            },
            {
                "nombre": 'Monitor Curvo 27"',
                "precio": "$5,400",
                "categoria": "Monitores",
                "tag": "Nuevo",
                "image": "img/monitor.jpg",
            },
            {
                "nombre": "Mouse Inalámbrico Pro",
                "precio": "$850",
                "categoria": "Periféricos",
                "tag": "Envío gratis",
                "image": "img/mouse.jpg",
            },
            {
                "nombre": "Silla Ergonómica",
                "precio": "$4,300",
                "categoria": "Oficina",
                "tag": "Recomendado",
                "image": "img/silla.jpg",
            },
            {
                "nombre": "Cafetera Expreso Automática",
                "precio": "$6,800",
                "categoria": "Smart Home",
                "tag": "Nuevo",
                "image": "img/cafetera.jpg",
            },
        ]

        # Scroll fluido con la rueda del ratón en toda la ventana
        self.bind_all("<MouseWheel>", self._on_mousewheel)

        # Construir interfaz
        self.crear_header()

        # Contenedor principal
        self.contenedor_principal = ct.CTkFrame(self, fg_color="transparent")
        self.contenedor_principal.grid(
            row=1, column=0, sticky="nsew", padx=30, pady=(15, 25)
        )
        self.contenedor_principal.grid_columnconfigure(0, weight=1)
        self.contenedor_principal.grid_rowconfigure(0, weight=1)

        # Cargar imagen del bot (img/bot.png)
        ruta_bot = os.path.join(self.ruta_base, "img", "bot.png")
        self.img_bot_flotante = None
        self.img_bot_header = None

        if os.path.exists(ruta_bot):
            pil_bot = Image.open(ruta_bot)
            self.img_bot_flotante = ct.CTkImage(
                light_image=pil_bot, dark_image=pil_bot, size=(32, 32)
            )
            self.img_bot_header = ct.CTkImage(
                light_image=pil_bot, dark_image=pil_bot, size=(38, 38)
            )

        # Botón flotante único en la esquina inferior derecha
        self.btn_flotante_bot = ct.CTkButton(
            self,
            text="  ¿Te ayudo?" if self.img_bot_flotante else "🤖  ¿Te ayudo?",
            image=self.img_bot_flotante,
            compound="left",
            font=ct.CTkFont(size=14, weight="bold"),
            height=52,
            width=165,
            corner_radius=26,
            fg_color="#FFFFFF",
            hover_color="#EFF6FF",
            text_color="#1E3A8A",
            border_width=2,
            border_color="#3B82F6",
            command=lambda: self.cambiar_vista("chatbot"),
        )
        self.btn_flotante_bot.place(relx=0.97, rely=0.95, anchor="se")

        # Cargar vista inicial
        self.cambiar_vista("inicio")

        # Revisa cada 100 ms si la IA (hilo secundario) ya respondió
        self._id_after = self.after(100, self._revisar_cola_ia)
        self.protocol("WM_DELETE_WINDOW", self._cerrar)

    def _cerrar(self):
        """Cancela el sondeo pendiente antes de cerrar para evitar errores al salir."""
        try:
            self.after_cancel(self._id_after)
        except Exception:
            pass
        self.destroy()

    def _on_mousewheel(self, event):
        if (
            self.scroll_activo is not None
            and self.scroll_activo.winfo_exists()
        ):
            self.scroll_activo._parent_canvas.yview_scroll(
                int(-1 * (event.delta / 40)), "units"
            )

    def alternar_tema(self):
        self.modo_oscuro = not self.modo_oscuro
        if self.modo_oscuro:
            ct.set_appearance_mode("Dark")
            self.btn_tema.configure(text="☀️ Claro")
        else:
            ct.set_appearance_mode("Light")
            self.btn_tema.configure(text="🌙 Oscuro")

    def crear_header(self):
        self.header = ct.CTkFrame(
            self, height=82, corner_radius=0, fg_color=("#1E3A8A", "#1E293B")
        )
        self.header.grid(row=0, column=0, sticky="ew")
        self.header.grid_propagate(False)

        self.header.grid_columnconfigure(0, weight=1)
        self.header.grid_columnconfigure(1, weight=2)
        self.header.grid_columnconfigure(2, weight=1)

        # --- IZQUIERDA: Logo / Nombre de la tienda ---
        frame_logo = ct.CTkFrame(self.header, fg_color="transparent")
        frame_logo.grid(row=0, column=0, sticky="w", padx=25, pady=15)

        ruta_logo = os.path.join(self.ruta_base, "img", "logo.png")
        if os.path.exists(ruta_logo):
            pil_logo = Image.open(ruta_logo)
            ctk_logo = ct.CTkImage(
                light_image=pil_logo, dark_image=pil_logo, size=(32, 32)
            )
            ct.CTkLabel(
                frame_logo,
                text="  TechShell",
                image=ctk_logo,
                compound="left",
                font=ct.CTkFont(size=20, weight="bold"),
                text_color="white",
            ).pack(anchor="w")
        else:
            ct.CTkLabel(
                frame_logo,
                text="💻 TechShell",
                font=ct.CTkFont(size=20, weight="bold"),
                text_color="white",
            ).pack(anchor="w")

        ct.CTkLabel(
            frame_logo,
            text="Hardware y periféricos de alto rendimiento",
            font=ct.CTkFont(size=11),
            text_color=("#BFDBFE", "#94A3B8"),
        ).pack(anchor="w")

        # --- CENTRO: Botones de navegación ---
        self.frame_botones = ct.CTkFrame(self.header, fg_color="transparent")
        self.frame_botones.grid(row=0, column=1, pady=12)

        opciones_menu = [
            ("🏠\nInicio", "inicio"),
            ("🔔\nNotifica.", "notificaciones"),
            ("🏷️\nOfertas", "ofertas"),
            ("🛒\nCarrito (0)", "carrito"),
        ]

        for texto, vista in opciones_menu:
            boton = ct.CTkButton(
                self.frame_botones,
                text=texto,
                width=90,
                height=52,
                corner_radius=12,
                fg_color="transparent",
                hover_color=("#2563EB", "#334155"),
                text_color="white",
                font=ct.CTkFont(size=12, weight="bold"),
                command=lambda v=vista: self.cambiar_vista(v),
            )
            boton.pack(side="left", padx=8)
            self.botones_nav[vista] = boton

        # --- DERECHA: Botón Modo Claro/Oscuro + Perfil ---
        frame_derecha = ct.CTkFrame(self.header, fg_color="transparent")
        frame_derecha.grid(row=0, column=2, sticky="e", padx=25, pady=18)

        self.btn_tema = ct.CTkButton(
            frame_derecha,
            text="☀️ Claro",
            font=ct.CTkFont(size=12, weight="bold"),
            width=88,
            height=40,
            corner_radius=20,
            fg_color=("#1D4ED8", "#334155"),
            hover_color=("#2563EB", "#475569"),
            text_color="white",
            command=self.alternar_tema,
        )
        self.btn_tema.pack(side="left", padx=(0, 10))

        self.btn_perfil = ct.CTkButton(
            frame_derecha,
            text="👤  Mi Cuenta",
            font=ct.CTkFont(size=13, weight="bold"),
            width=120,
            height=40,
            corner_radius=20,
            fg_color=("#2563EB", "#3B82F6"),
            hover_color=("#1D4ED8", "#2563EB"),
            text_color="white",
            command=lambda: print("Clic en Perfil"),
        )
        self.btn_perfil.pack(side="left")

    def actualizar_estilo_nav(self, vista_activa):
        for vista, boton in self.botones_nav.items():
            if vista == vista_activa:
                boton.configure(fg_color=("#2563EB", "#3B82F6"))
            else:
                boton.configure(fg_color="transparent")

    def limpiar_contenido(self):
        self.scroll_activo = None
        for widget in self.contenedor_principal.winfo_children():
            widget.destroy()

    def cambiar_vista(self, vista):
        self.vista_actual = vista
        self.actualizar_estilo_nav(vista)
        self.limpiar_contenido()

        if vista == "chatbot":
            self.btn_flotante_bot.place_forget()
            self.mostrar_chatbot()
        else:
            self.btn_flotante_bot.place(relx=0.97, rely=0.95, anchor="se")
            self.btn_flotante_bot.lift()

            if vista == "inicio":
                self.mostrar_inicio()
            elif vista == "carrito":
                self.mostrar_carrito()
            else:
                self.mostrar_placeholder(vista)

    # ==========================================
    # VISTA: INICIO
    # ==========================================
    def mostrar_inicio(self):
        area_scroll = ct.CTkScrollableFrame(
            self.contenedor_principal, fg_color="transparent"
        )
        area_scroll.grid(row=0, column=0, sticky="nsew")
        area_scroll.grid_columnconfigure(0, weight=1)
        self.scroll_activo = area_scroll

        # 1. Banner promocional superior
        banner = ct.CTkFrame(
            area_scroll,
            corner_radius=16,
            fg_color=("#2563EB", "#1E3A8A"),
            height=130,
        )
        banner.grid(row=0, column=0, sticky="ew", pady=(0, 20))
        banner.grid_columnconfigure(0, weight=1)

        ct.CTkLabel(
            banner,
            text="⚡ ¡Semana Tech en TechShell!",
            font=ct.CTkFont(size=22, weight="bold"),
            text_color="white",
        ).grid(row=0, column=0, sticky="w", padx=25, pady=(20, 4))

        ct.CTkLabel(
            banner,
            text="Envío gratis y hasta 12 meses sin intereses en hardware seleccionado.",
            font=ct.CTkFont(size=13),
            text_color="#DBEAFE",
        ).grid(row=1, column=0, sticky="w", padx=25, pady=(0, 20))

        # 2. Barra de título + buscador
        barra_seccion = ct.CTkFrame(area_scroll, fg_color="transparent")
        barra_seccion.grid(row=1, column=0, sticky="ew", pady=(0, 15))
        barra_seccion.grid_columnconfigure(0, weight=1)

        ct.CTkLabel(
            barra_seccion,
            text="Catálogo Destacado",
            font=ct.CTkFont(size=18, weight="bold"),
            text_color=("#0F172A", "#F8FAFC"),
        ).grid(row=0, column=0, sticky="w")

        self.entrada_busqueda = ct.CTkEntry(
            barra_seccion,
            placeholder_text="🔍 Buscar producto...",
            width=260,
            height=36,
            corner_radius=10,
        )
        self.entrada_busqueda.grid(row=0, column=1, sticky="e")

        # 3. Cuadrícula de tarjetas de productos (3 columnas)
        grid_productos = ct.CTkFrame(area_scroll, fg_color="transparent")
        grid_productos.grid(row=2, column=0, sticky="nsew", pady=(0, 40))
        for col in range(3):
            grid_productos.grid_columnconfigure(col, weight=1, uniform="col")

        for idx, prod in enumerate(self.productos_catalogo):
            fila = idx // 3
            columna = idx % 3
            self.crear_tarjeta_producto(grid_productos, prod, fila, columna)

    def crear_tarjeta_producto(self, parent, prod, fila, columna):
        card = ct.CTkFrame(
            parent,
            corner_radius=16,
            fg_color=("#FFFFFF", "#1E293B"),
            border_width=1,
            border_color=("#E2E8F0", "#334155"),
        )
        card.grid(row=fila, column=columna, padx=10, pady=10, sticky="nsew")
        card.grid_columnconfigure(0, weight=1)

        top_row = ct.CTkFrame(card, fg_color="transparent")
        top_row.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 8))
        top_row.grid_columnconfigure(0, weight=1)

        ct.CTkLabel(
            top_row,
            text=prod["categoria"].upper(),
            font=ct.CTkFont(size=10, weight="bold"),
            text_color=("#64748B", "#94A3B8"),
        ).grid(row=0, column=0, sticky="w")

        badge = ct.CTkLabel(
            top_row,
            text=f" {prod['tag']} ",
            font=ct.CTkFont(size=10, weight="bold"),
            fg_color=("#DBEAFE", "#1E3A8A"),
            text_color=("#1D4ED8", "#93C5FD"),
            corner_radius=6,
        )
        badge.grid(row=0, column=1, sticky="e")

        espacio_img = ct.CTkFrame(
            card,
            height=155,
            corner_radius=12,
            fg_color="#FFFFFF",
        )
        espacio_img.grid(row=1, column=0, sticky="ew", padx=16, pady=6)
        espacio_img.grid_propagate(False)
        espacio_img.grid_columnconfigure(0, weight=1)
        espacio_img.grid_rowconfigure(0, weight=1)

        ruta_img = os.path.join(self.ruta_base, prod.get("image", ""))
        if prod.get("image") and os.path.exists(ruta_img):
            pil_img = Image.open(ruta_img)
            max_ancho, max_alto = 240, 140
            ratio = min(max_ancho / pil_img.width, max_alto / pil_img.height)
            nuevo_ancho = int(pil_img.width * ratio)
            nuevo_alto = int(pil_img.height * ratio)

            ctk_img = ct.CTkImage(
                light_image=pil_img,
                dark_image=pil_img,
                size=(nuevo_ancho, nuevo_alto),
            )
            ct.CTkLabel(espacio_img, text="", image=ctk_img).grid(
                row=0, column=0
            )
        else:
            ct.CTkLabel(
                espacio_img,
                text="📦",
                font=ct.CTkFont(size=34),
            ).grid(row=0, column=0)

        ct.CTkLabel(
            card,
            text=prod["nombre"],
            font=ct.CTkFont(size=15, weight="bold"),
            text_color=("#0F172A", "#F8FAFC"),
            anchor="w",
        ).grid(row=2, column=0, sticky="ew", padx=16, pady=(8, 2))

        ct.CTkLabel(
            card,
            text=prod["precio"],
            font=ct.CTkFont(size=18, weight="bold"),
            text_color=("#16A34A", "#4ADE80"),
            anchor="w",
        ).grid(row=3, column=0, sticky="ew", padx=16, pady=(0, 12))

        ct.CTkButton(
            card,
            text="+ Agregar al carrito",
            height=38,
            corner_radius=10,
            font=ct.CTkFont(size=13, weight="bold"),
            fg_color=("#2563EB", "#3B82F6"),
            hover_color=("#1D4ED8", "#2563EB"),
            command=lambda p=prod: self.agregar_al_carrito(p),
        ).grid(row=4, column=0, sticky="ew", padx=16, pady=(0, 16))

    # ==========================================
    # VISTA: CHATBOT
    # ==========================================
    def _estado_ia(self):
        """Devuelve (texto, color) del indicador de estado del chat."""
        if procesar_mensaje_ia is not None:
            return "● IA conectada y lista", ("#16A34A", "#4ADE80")
        detalle = f": {error_modulo_ia}" if error_modulo_ia else ""
        return (
            f"● IA no disponible{detalle}"[:110],
            ("#D97706", "#FBBF24"),
        )

    def mostrar_chatbot(self):
        card_chat = ct.CTkFrame(
            self.contenedor_principal,
            corner_radius=16,
            fg_color=("#FFFFFF", "#1E293B"),
            border_width=1,
            border_color=("#E2E8F0", "#334155"),
        )
        card_chat.grid(row=0, column=0, sticky="nsew")
        card_chat.grid_columnconfigure(0, weight=1)
        card_chat.grid_rowconfigure(2, weight=1)  # La fila 2 (mensajes) es la que crece

        # 1. Encabezado del Chatbot
        header_chat = ct.CTkFrame(
            card_chat,
            height=68,
            corner_radius=14,
            fg_color=("#EFF6FF", "#0F172A"),
        )
        header_chat.grid(row=0, column=0, sticky="ew", padx=14, pady=(14, 6))
        header_chat.grid_columnconfigure(1, weight=1)

        if self.img_bot_header:
            badge_bot = ct.CTkFrame(
                header_chat,
                width=46,
                height=46,
                corner_radius=12,
                fg_color="#FFFFFF",
            )
            badge_bot.grid(row=0, column=0, rowspan=2, padx=(16, 12), pady=10)
            badge_bot.grid_propagate(False)
            badge_bot.grid_columnconfigure(0, weight=1)
            badge_bot.grid_rowconfigure(0, weight=1)

            ct.CTkLabel(
                badge_bot, text="", image=self.img_bot_header
            ).grid(row=0, column=0)
        else:
            ct.CTkLabel(
                header_chat,
                text="🤖",
                font=ct.CTkFont(size=28),
            ).grid(row=0, column=0, rowspan=2, padx=(16, 12), pady=10)

        ct.CTkLabel(
            header_chat,
            text="Asistente Virtual — TechShell",
            font=ct.CTkFont(size=15, weight="bold"),
            text_color=("#0F172A", "#F8FAFC"),
        ).grid(row=0, column=1, sticky="sw", pady=(10, 0))

        estado_ia, color_estado = self._estado_ia()

        self.lbl_estado_chat = ct.CTkLabel(
            header_chat,
            text=estado_ia,
            font=ct.CTkFont(size=11),
            text_color=color_estado,
        )
        self.lbl_estado_chat.grid(row=1, column=1, sticky="nw", pady=(0, 10))

        ct.CTkButton(
            header_chat,
            text="Limpiar chat",
            width=95,
            height=30,
            corner_radius=8,
            font=ct.CTkFont(size=12),
            fg_color="transparent",
            border_width=1,
            border_color=("#CBD5E1", "#475569"),
            text_color=("#475569", "#CBD5E1"),
            hover_color=("#E2E8F0", "#334155"),
            command=self.reiniciar_chat,
        ).grid(row=0, column=2, rowspan=2, padx=16)

        # 1b. Panel colapsable de preguntas frecuentes (fila 1)
        self._construir_panel_faq(card_chat)

        # 2. Área scrollable de mensajes (fila 2)
        self.area_mensajes = ct.CTkScrollableFrame(
            card_chat, fg_color="transparent"
        )
        self.area_mensajes.grid(
            row=2, column=0, sticky="nsew", padx=16, pady=6
        )
        self.area_mensajes.grid_columnconfigure(0, weight=1)
        self.scroll_activo = self.area_mensajes

        for idx, (remitente, texto) in enumerate(self.historial_chat):
            self.renderizar_burbuja(remitente, texto, idx)

        # 3. Sugerencias rápidas (fila 3)
        frame_sugerencias = ct.CTkFrame(card_chat, fg_color="transparent")
        frame_sugerencias.grid(
            row=3, column=0, sticky="ew", padx=16, pady=(4, 6)
        )

        sugerencias = [
            "📋 Ver catálogo",
            "🏷️ ¿Qué ofertas hay?",
            "🚚 Costo de envío",
            "🛒 ¿Qué hay en mi carrito?",
        ]
        for sug in sugerencias:
            ct.CTkButton(
                frame_sugerencias,
                text=sug,
                height=28,
                corner_radius=14,
                font=ct.CTkFont(size=11, weight="bold"),
                fg_color=("#F1F5F9", "#334155"),
                text_color=("#1E293B", "#E2E8F0"),
                hover_color=("#DBEAFE", "#475569"),
                command=lambda s=sug: self.enviar_mensaje_chat(s),
            ).pack(side="left", padx=(0, 8))

        # 4. Barra inferior de escritura (fila 4)
        barra_input = ct.CTkFrame(card_chat, fg_color="transparent")
        barra_input.grid(row=4, column=0, sticky="ew", padx=16, pady=(4, 16))
        barra_input.grid_columnconfigure(0, weight=1)

        self.entrada_chat = ct.CTkEntry(
            barra_input,
            placeholder_text="Escribe tu pregunta aquí...",
            height=44,
            corner_radius=12,
            font=ct.CTkFont(size=13),
        )
        self.entrada_chat.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self.entrada_chat.bind(
            "<Return>", lambda event: self.enviar_mensaje_chat()
        )

        self.btn_enviar_chat = ct.CTkButton(
            barra_input,
            text="Enviar ➤",
            width=110,
            height=44,
            corner_radius=12,
            font=ct.CTkFont(size=13, weight="bold"),
            fg_color=("#2563EB", "#3B82F6"),
            hover_color=("#1D4ED8", "#2563EB"),
            command=self.enviar_mensaje_chat,
        )
        self.btn_enviar_chat.grid(row=0, column=1)

    # ------------------------------------------
    # Panel de preguntas frecuentes (colapsable)
    # ------------------------------------------
    def _titulo_faq(self):
        return ("▼  " if self.faq_visible else "▶  ") + "Preguntas frecuentes"

    def _construir_panel_faq(self, padre):
        """Lista colapsable con las preguntas más frecuentes de base_datos.json."""
        self.contenedor_faq = None
        preguntas = obtener_preguntas_frecuentes()
        if not preguntas:
            return  # Sin preguntas (IA no disponible o BD ilegible): no se muestra el panel

        marco = ct.CTkFrame(
            padre,
            corner_radius=12,
            fg_color=("#F8FAFC", "#162033"),
            border_width=1,
            border_color=("#E2E8F0", "#334155"),
        )
        marco.grid(row=1, column=0, sticky="ew", padx=16, pady=(4, 2))
        marco.grid_columnconfigure(0, weight=1)

        self.btn_toggle_faq = ct.CTkButton(
            marco,
            text=self._titulo_faq(),
            anchor="w",
            height=32,
            corner_radius=8,
            font=ct.CTkFont(size=13, weight="bold"),
            fg_color="transparent",
            hover_color=("#E2E8F0", "#334155"),
            text_color=("#0F172A", "#F8FAFC"),
            command=self._alternar_faq,
        )
        self.btn_toggle_faq.grid(row=0, column=0, sticky="ew", padx=6, pady=(4, 2))

        self.contenedor_faq = ct.CTkFrame(marco, fg_color="transparent")
        self.contenedor_faq.grid_columnconfigure(0, weight=1)
        for fila, pregunta in enumerate(preguntas):
            ct.CTkButton(
                self.contenedor_faq,
                text=pregunta,
                anchor="w",
                height=30,
                corner_radius=8,
                font=ct.CTkFont(size=12),
                fg_color=("#EFF6FF", "#1E293B"),
                text_color=("#1E293B", "#E2E8F0"),
                hover_color=("#DBEAFE", "#334155"),
                command=lambda q=pregunta: self._usar_pregunta_faq(q),
            ).grid(row=fila, column=0, sticky="ew", padx=6, pady=2)

        if self.faq_visible:
            self.contenedor_faq.grid(row=1, column=0, sticky="ew", padx=2, pady=(0, 6))

    def _alternar_faq(self):
        """Despliega u oculta la lista de preguntas frecuentes."""
        if self.contenedor_faq is None:
            return
        self.faq_visible = not self.faq_visible
        if self.faq_visible:
            self.contenedor_faq.grid(row=1, column=0, sticky="ew", padx=2, pady=(0, 6))
        else:
            self.contenedor_faq.grid_remove()
        self.btn_toggle_faq.configure(text=self._titulo_faq())

    def _usar_pregunta_faq(self, pregunta):
        """Envía la pregunta elegida y pliega el panel para dejar espacio a la conversación."""
        if self.esperando_ia:
            return
        if self.faq_visible:
            self._alternar_faq()
        self.enviar_mensaje_chat(pregunta)

    def renderizar_burbuja(self, remitente, texto, fila):
        es_usuario = remitente == "usuario"

        contenedor_fila = ct.CTkFrame(
            self.area_mensajes, fg_color="transparent"
        )
        contenedor_fila.grid(row=fila, column=0, sticky="ew", pady=5)
        contenedor_fila.grid_columnconfigure(0, weight=1)

        burbuja = ct.CTkFrame(
            contenedor_fila,
            corner_radius=14,
            fg_color=("#2563EB", "#2563EB")
            if es_usuario
            else ("#F1F5F9", "#0F172A"),
        )
        burbuja.grid(
            row=0,
            column=0,
            sticky="e" if es_usuario else "w",
            padx=(80, 4) if es_usuario else (4, 80),
        )

        ct.CTkLabel(
            burbuja,
            text=texto,
            font=ct.CTkFont(size=13),
            text_color="white" if es_usuario else ("#0F172A", "#F8FAFC"),
            wraplength=520,
            justify="left",
        ).pack(padx=14, pady=10)

    def enviar_mensaje_chat(self, texto_rapido=None):
        if self.esperando_ia:
            return

        mensaje = (
            texto_rapido
            if texto_rapido is not None
            else self.entrada_chat.get().strip()
        )
        if not mensaje:
            return

        if texto_rapido is None:
            self.entrada_chat.delete(0, "end")

        # Mostrar mensaje del usuario
        self.historial_chat.append(("usuario", mensaje))
        self.renderizar_burbuja(
            "usuario", mensaje, len(self.historial_chat) - 1
        )
        self._bajar_scroll_chat()

        # Bloquear envío mientras la IA responde en segundo plano
        self.esperando_ia = True
        self.btn_enviar_chat.configure(state="disabled", text="...")
        self.lbl_estado_chat.configure(text="● Pensando respuesta...")

        # Contexto que recibe IA.py (catálogo y carrito en vivo + historial)
        contexto = {
            "catalogo": self.productos_catalogo,
            "carrito": list(self.carrito),
            "historial": list(self.historial_chat),
        }

        hilo = threading.Thread(
            target=self._ejecutar_ia_en_segundo_plano,
            args=(mensaje, contexto),
            daemon=True,
        )
        hilo.start()

    def _ejecutar_ia_en_segundo_plano(self, mensaje, contexto):
        """Corre en un hilo secundario: NO toca widgets, solo deja la respuesta en la cola."""
        if procesar_mensaje_ia is not None:
            try:
                respuesta = procesar_mensaje_ia(mensaje, contexto)
            except Exception as e:
                respuesta = f"⚠️ Error en el módulo de IA: {e}"
        else:
            respuesta = (
                "🔌 [Modo Frontend] El módulo de IA no está disponible.\n"
                f"Motivo: {error_modulo_ia or 'no se encontró IA.py'}"
            )

        self.cola_ia.put(respuesta)

    def _revisar_cola_ia(self):
        """Corre en el hilo principal cada 100 ms y entrega las respuestas pendientes."""
        try:
            while True:
                self._recibir_respuesta_ia(self.cola_ia.get_nowait())
        except queue.Empty:
            pass
        finally:
            self._id_after = self.after(100, self._revisar_cola_ia)

    def _recibir_respuesta_ia(self, respuesta):
        self.esperando_ia = False
        # Siempre se guarda en el historial, aunque el usuario haya cambiado de vista
        self.historial_chat.append(("bot", respuesta))

        if self.vista_actual == "chatbot" and self.area_mensajes.winfo_exists():
            self.renderizar_burbuja(
                "bot", respuesta, len(self.historial_chat) - 1
            )
            self._bajar_scroll_chat()
            self.btn_enviar_chat.configure(state="normal", text="Enviar ➤")
            texto, color = self._estado_ia()
            self.lbl_estado_chat.configure(text=texto, text_color=color)

    def _bajar_scroll_chat(self):
        self.area_mensajes.update_idletasks()
        self.area_mensajes._parent_canvas.yview_moveto(1.0)

    def reiniciar_chat(self):
        self.historial_chat = [
            (
                "bot",
                "Chat reiniciado. 🔄 ¿En qué más te puedo ayudar hoy?",
            )
        ]
        self.mostrar_chatbot()

    # ==========================================
    # CARRITO Y OTRAS VISTAS
    # ==========================================
    def agregar_al_carrito(self, prod):
        self.carrito.append(prod)
        self.botones_nav["carrito"].configure(
            text=f"🛒\nCarrito ({len(self.carrito)})"
        )

    def eliminar_del_carrito(self, nombre_producto):
        for idx, item in enumerate(self.carrito):
            if item["nombre"] == nombre_producto:
                self.carrito.pop(idx)
                break
        self.botones_nav["carrito"].configure(
            text=f"🛒\nCarrito ({len(self.carrito)})"
        )
        self.mostrar_carrito()

    def pagar_carrito(self, total):
        self.carrito.clear()
        self.botones_nav["carrito"].configure(text="🛒\nCarrito (0)")
        self.limpiar_contenido()

        card_exito = ct.CTkFrame(
            self.contenedor_principal,
            corner_radius=16,
            fg_color=("#FFFFFF", "#1E293B"),
            border_width=1,
            border_color=("#E2E8F0", "#334155"),
        )
        card_exito.grid(row=0, column=0, sticky="ew", pady=20)
        card_exito.grid_columnconfigure(0, weight=1)

        ct.CTkLabel(
            card_exito,
            text="✅ ¡Pago realizado con éxito!",
            font=ct.CTkFont(size=22, weight="bold"),
            text_color=("#16A34A", "#4ADE80"),
        ).grid(row=0, column=0, pady=(35, 8))

        ct.CTkLabel(
            card_exito,
            text=f"Total pagado: ${total:,.2f} MXN — Gracias por comprar en TechShell.",
            font=ct.CTkFont(size=14),
            text_color=("#475569", "#CBD5E1"),
        ).grid(row=1, column=0, pady=(0, 20))

        ct.CTkButton(
            card_exito,
            text="Seguir comprando",
            height=40,
            corner_radius=10,
            font=ct.CTkFont(size=13, weight="bold"),
            fg_color=("#2563EB", "#3B82F6"),
            hover_color=("#1D4ED8", "#2563EB"),
            command=lambda: self.cambiar_vista("inicio"),
        ).grid(row=2, column=0, pady=(0, 35))

    def mostrar_carrito(self):
        area_scroll = ct.CTkScrollableFrame(
            self.contenedor_principal, fg_color="transparent"
        )
        area_scroll.grid(row=0, column=0, sticky="nsew")
        area_scroll.grid_columnconfigure(0, weight=1)
        self.scroll_activo = area_scroll

        ct.CTkLabel(
            area_scroll,
            text=f"🛒 Tu Carrito ({len(self.carrito)} artículos)",
            font=ct.CTkFont(size=22, weight="bold"),
            text_color=("#0F172A", "#F8FAFC"),
        ).grid(row=0, column=0, sticky="w", pady=(0, 15))

        if not self.carrito:
            ct.CTkLabel(
                area_scroll,
                text="Aún no has agregado productos. Ve a Inicio para explorar el catálogo.",
                font=ct.CTkFont(size=14),
                text_color="gray",
            ).grid(row=1, column=0, sticky="w")
            return

        # Agrupar productos repetidos por nombre y sumar cantidad y subtotal
        agrupados = {}
        total = 0.0

        for item in self.carrito:
            nombre = item["nombre"]
            precio_unit = float(
                item["precio"].replace("$", "").replace(",", "").strip()
            )
            total += precio_unit

            if nombre not in agrupados:
                agrupados[nombre] = {
                    "cantidad": 1,
                    "precio_unit": precio_unit,
                    "subtotal": precio_unit,
                }
            else:
                agrupados[nombre]["cantidad"] += 1
                agrupados[nombre]["subtotal"] += precio_unit

        for idx, (nombre, datos) in enumerate(agrupados.items()):
            fila = ct.CTkFrame(
                area_scroll,
                corner_radius=12,
                fg_color=("#FFFFFF", "#1E293B"),
                border_width=1,
                border_color=("#E2E8F0", "#334155"),
            )
            fila.grid(row=idx + 1, column=0, sticky="ew", pady=5)
            fila.grid_columnconfigure(0, weight=1)

            texto_fila = (
                f"{nombre}  (x{datos['cantidad']})  —  ${datos['subtotal']:,.2f}"
                if datos["cantidad"] > 1
                else f"{nombre}  —  ${datos['subtotal']:,.2f}"
            )

            ct.CTkLabel(
                fila,
                text=texto_fila,
                font=ct.CTkFont(size=14, weight="bold"),
                text_color=("#0F172A", "#F8FAFC"),
            ).grid(row=0, column=0, sticky="w", padx=16, pady=12)

            ct.CTkButton(
                fila,
                text="🗑️ Quitar",
                width=95,
                height=32,
                corner_radius=8,
                font=ct.CTkFont(size=12, weight="bold"),
                fg_color=("#EF4444", "#DC2626"),
                hover_color=("#DC2626", "#B91C1C"),
                text_color="white",
                command=lambda n=nombre: self.eliminar_del_carrito(n),
            ).grid(row=0, column=1, sticky="e", padx=16, pady=10)

        resumen = ct.CTkFrame(
            area_scroll,
            corner_radius=14,
            fg_color=("#FFFFFF", "#1E293B"),
            border_width=1,
            border_color=("#E2E8F0", "#334155"),
        )
        resumen.grid(
            row=len(agrupados) + 1, column=0, sticky="ew", pady=(18, 30)
        )
        resumen.grid_columnconfigure(0, weight=1)

        ct.CTkLabel(
            resumen,
            text=f"Total a pagar:  ${total:,.2f}",
            font=ct.CTkFont(size=20, weight="bold"),
            text_color=("#16A34A", "#4ADE80"),
        ).grid(row=0, column=0, sticky="w", padx=20, pady=18)

        ct.CTkButton(
            resumen,
            text="💳 Pagar",
            width=150,
            height=42,
            corner_radius=10,
            font=ct.CTkFont(size=14, weight="bold"),
            fg_color=("#16A34A", "#22C55E"),
            hover_color=("#15803D", "#16A34A"),
            text_color="white",
            command=lambda t=total: self.pagar_carrito(t),
        ).grid(row=0, column=1, sticky="e", padx=20, pady=18)

    def mostrar_placeholder(self, seccion):
        card = ct.CTkFrame(
            self.contenedor_principal,
            corner_radius=16,
            fg_color=("#FFFFFF", "#1E293B"),
            height=220,
        )
        card.grid(row=0, column=0, sticky="ew", pady=10)
        card.grid_columnconfigure(0, weight=1)

        ct.CTkLabel(
            card,
            text=f"Sección: {seccion.capitalize()}",
            font=ct.CTkFont(size=22, weight="bold"),
        ).grid(row=0, column=0, pady=(40, 8))

        ct.CTkLabel(
            card,
            text="Aquí conectaremos esta vista en el siguiente paso.",
            font=ct.CTkFont(size=13),
            text_color="gray",
        ).grid(row=1, column=0, pady=(0, 40))


if __name__ == "__main__":
    app = tienda()
    app.mainloop()