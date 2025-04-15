# --- START OF FILE src/panels/image_preview_panel.py ---

import tkinter as tk
from tkinter import ttk, font as tkFont # <--- Añadido tkFont aquí
import logging
from PIL import Image, ImageTk, ImageDraw, ImageFont # Pillow para manejo avanzado de imágenes
import cv2 # OpenCV para conversión inicial BGR -> RGB
import numpy as np

# Importar constantes de color y tamaño desde el módulo principal o definirlas aquí
# Es mejor si se pueden importar para consistencia. Asumiremos que existen en main_app
# o las definimos aquí como fallback.
try:
    # Intenta importar desde donde estén definidas (ajusta la ruta si es necesario)
    # from ..template_manager_gui import ( # Si estuvieran en el __init__.py o main
    #     OCR_RECT_NORMAL_COLOR, OCR_RECT_NO_TEXT_COLOR, OCR_RECT_SELECTED_COLOR,
    #     OCR_RECT_SELECTED_WIDTH, PREVIEW_NUMBER_FONT_SIZE
    # )
    # Por ahora, las definimos aquí como fallback/ejemplo:
    OCR_RECT_NORMAL_COLOR = "purple"
    OCR_RECT_NO_TEXT_COLOR = "red"
    OCR_RECT_SELECTED_COLOR = "yellow"
    OCR_RECT_SELECTED_WIDTH = 3
    PREVIEW_NUMBER_FONT_SIZE = 14
except ImportError:
    # Definir valores por defecto si la importación falla
    logging.warning("No se pudieron importar constantes de color/tamaño, usando defaults.")
    OCR_RECT_NORMAL_COLOR = "purple"
    OCR_RECT_NO_TEXT_COLOR = "red"
    OCR_RECT_SELECTED_COLOR = "yellow"
    OCR_RECT_SELECTED_WIDTH = 3
    PREVIEW_NUMBER_FONT_SIZE = 14


class ImagePreviewPanel(ttk.LabelFrame):
    """
    Panel dedicado a mostrar una imagen (plantilla/captura) y superponer
    regiones OCR numeradas, con capacidad de resaltar las seleccionadas.
    """
    def __init__(self, master, main_app, **kwargs):
        """
        Inicializa el Panel de Previsualización de Imagen.

        Args:
            master: El widget padre (frame de la columna central).
            main_app: Referencia a la instancia principal de TemplateManagerGUI.
            **kwargs: Argumentos adicionales para ttk.LabelFrame.
        """
        kwargs['text'] = kwargs.get('text', "Previsualización")
        super().__init__(master, **kwargs)
        self.main_app = main_app
        logging.debug("Inicializando ImagePreviewPanel.")

        # --- Estado Interno ---
        self.current_image_numpy = None # Imagen original NumPy BGR
        self.current_ocr_regions = []   # Lista de dicts de regiones [{region:{}, expected_text:[]}, ...]
        self.selected_indices = []      # Lista de índices (0-based) de regiones seleccionadas
        self.tk_img_preview = None      # Referencia a PhotoImage para Tkinter (¡VITAL!)
        self.display_scale = 1.0        # Escala actual de la imagen mostrada vs original
        self.image_offset = (0, 0)      # Offset (x, y) de la imagen en el canvas
        self.preview_font = self._get_preview_font() # Fuente para números OCR

        # --- Widgets ---
        self._create_widgets()

        # --- Bindings ---
        self.preview_canvas.bind("<Configure>", self._on_canvas_resize)
        # Podríamos añadir bindings de clic en el futuro para seleccionar regiones
        # self.preview_canvas.bind("<Button-1>", self._on_canvas_click)

    def _get_preview_font(self):
        """Obtiene una fuente adecuada para dibujar los números OCR."""
        # Intenta cargar fuentes comunes, con fallback a la default de PIL
        # (Misma lógica que antes)
        try: return ImageFont.truetype("consola.ttf", PREVIEW_NUMBER_FONT_SIZE)
        except IOError:
            try: return ImageFont.truetype("cour.ttf", PREVIEW_NUMBER_FONT_SIZE)
            except IOError:
                 logging.warning("Fuentes Consolas/Courier no encontradas para preview.")
                 try:
                     # Intentar obtener fuente del sistema si tkinter está disponible
                     tk_default_font = tkFont.nametofont("TkDefaultFont")
                     tk_font_info = tk_default_font.actual()
                     # Necesitamos encontrar la ruta del archivo .ttf o .otf
                     # Esto es complejo y dependiente del sistema operativo.
                     # Por simplicidad, recurrimos a la fuente default de PIL.
                     logging.warning("Usando fuente default de PIL para números OCR.")
                     return ImageFont.load_default()
                 except Exception:
                     return ImageFont.load_default() # Fallback final

    def _create_widgets(self):
        """Crea el canvas para la previsualización."""
        logging.debug("Creando widgets para ImagePreviewPanel.")
        # Configurar grid interno para que el canvas se expanda
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Canvas principal
        self.preview_canvas = tk.Canvas(self, bg="gray", highlightthickness=0) # Sin borde extra
        self.preview_canvas.grid(row=0, column=0, sticky="nsew", padx=1, pady=1)


    def update_preview(self, image_numpy, ocr_regions, selected_indices=None):
        """
        Actualiza la imagen mostrada, las regiones OCR y el resaltado.

        Args:
            image_numpy (np.ndarray | None): La imagen a mostrar (BGR) o None para limpiar.
            ocr_regions (list): Lista de diccionarios de regiones OCR actuales.
            selected_indices (list | None): Lista de índices (0-based) de las regiones
                                           en ocr_regions que deben resaltarse.
        """
        self.current_image_numpy = image_numpy
        self.current_ocr_regions = ocr_regions if ocr_regions else []
        self.selected_indices = selected_indices if selected_indices is not None else []
        logging.debug(f"Actualizando preview. Imagen: {'Sí' if image_numpy is not None else 'No'}, "
                      f"Regiones: {len(self.current_ocr_regions)}, Seleccionadas: {self.selected_indices}")

        # Redibujar todo el canvas
        self._draw_canvas_content()


    def _draw_canvas_content(self):
        """Limpia y redibuja completamente el canvas con imagen y regiones."""
        self.preview_canvas.delete("all") # Limpiar canvas
        self.tk_img_preview = None      # Resetear referencia Tk
        self.display_scale = 1.0
        self.image_offset = (0, 0)

        # --- 1. Dibujar Fondo (si no hay imagen) ---
        canvas_width = self.preview_canvas.winfo_width()
        canvas_height = self.preview_canvas.winfo_height()
        if canvas_width <= 1 or canvas_height <= 1: return # Canvas no visible aún

        if self.current_image_numpy is None:
            # Mostrar mensaje si no hay imagen
            self.preview_canvas.create_text(
                canvas_width / 2, canvas_height / 2,
                text="Sin Imagen Cargada", fill="white",
                font=self.main_app.heading_font, # Usar fuente de app principal
                anchor="center"
            )
            return

        # --- 2. Preparar Imagen para Tkinter (Redimensionar y Convertir) ---
        try:
            img_h, img_w = self.current_image_numpy.shape[:2]
            if img_h == 0 or img_w == 0: raise ValueError("Imagen NumPy vacía")

            # Calcular escala para ajustar al canvas manteniendo aspecto
            scale_w = canvas_width / img_w
            scale_h = canvas_height / img_h
            self.display_scale = min(scale_w, scale_h)

            # No escalar si la imagen ya es más pequeña que el canvas? (Opcional)
            # if self.display_scale > 1.0: self.display_scale = 1.0

            new_w = int(img_w * self.display_scale)
            new_h = int(img_h * self.display_scale)

            if new_w < 1 or new_h < 1: raise ValueError("Tamaño redimensionado inválido")

            # Redimensionar con OpenCV
            interpolation = cv2.INTER_AREA if self.display_scale < 1.0 else cv2.INTER_CUBIC
            resized_img = cv2.resize(self.current_image_numpy, (new_w, new_h), interpolation=interpolation)

            # Convertir a formato PIL RGB
            img_rgb = cv2.cvtColor(resized_img, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(img_rgb)

            # --- 3. Dibujar Regiones OCR sobre la imagen PIL redimensionada ---
            draw = ImageDraw.Draw(pil_img)
            for i, region_data in enumerate(self.current_ocr_regions):
                try:
                    region = region_data.get('region')
                    if not region: continue

                    # Calcular coordenadas en la imagen redimensionada
                    x1 = int(region['left'] * self.display_scale)
                    y1 = int(region['top'] * self.display_scale)
                    x2 = int((region['left'] + region['width']) * self.display_scale)
                    y2 = int((region['top'] + region['height']) * self.display_scale)

                    # Determinar estilo basado en selección y texto esperado
                    is_selected = i in self.selected_indices
                    has_text = bool(region_data.get('expected_text'))
                    outline_color = OCR_RECT_SELECTED_COLOR if is_selected else \
                                    (OCR_RECT_NORMAL_COLOR if has_text else OCR_RECT_NO_TEXT_COLOR)
                    outline_width = OCR_RECT_SELECTED_WIDTH if is_selected else 2

                    # Dibujar rectángulo
                    draw.rectangle([x1, y1, x2, y2], outline=outline_color, width=outline_width)

                    # Dibujar número de índice
                    text_num = str(i + 1)
                    text_pos_x = x1 + 3
                    text_pos_y = y1 + 1
                    try:
                        # Obtener bounding box para fondo blanco
                        bbox = self.preview_font.getbbox(text_num) # Pillow >= 9.2.0
                        text_width = bbox[2] - bbox[0]
                        text_height = bbox[3] - bbox[1]
                    except AttributeError: # Fallback para Pillow < 9.2.0
                        text_width, text_height = self.preview_font.getsize(text_num)
                        # Aproximar bbox (puede no ser perfecto)
                        bbox = (0, self.preview_font.getmetrics()[1] // 2 , text_width, text_height + self.preview_font.getmetrics()[1] // 2)


                    bg_x1 = text_pos_x - 2
                    bg_y1 = text_pos_y - 1
                    bg_x2 = text_pos_x + text_width + 2
                    bg_y2 = text_pos_y + text_height + 1
                    draw.rectangle([bg_x1, bg_y1, bg_x2, bg_y2], fill="white", width=0) # Fondo blanco
                    draw.text((text_pos_x, text_pos_y), text_num, fill=outline_color, font=self.preview_font)

                except Exception as draw_err:
                    logging.error(f"Error dibujando región OCR {i}: {draw_err}", exc_info=True)

            # --- 4. Convertir imagen PIL final a PhotoImage y mostrar en Canvas ---
            self.tk_img_preview = ImageTk.PhotoImage(pil_img)

            # Calcular offset para centrar la imagen
            self.image_offset = ((canvas_width - new_w) // 2, (canvas_height - new_h) // 2)

            # Dibujar imagen en canvas
            self.preview_canvas.create_image(
                self.image_offset[0], self.image_offset[1],
                anchor="nw", image=self.tk_img_preview
            )

        except Exception as e:
            logging.exception("Error crítico en _draw_canvas_content")
            # Mostrar mensaje de error en el canvas
            try:
                self.preview_canvas.create_text(
                    canvas_width / 2, canvas_height / 2,
                    text=f"Error al mostrar imagen:\n{e}", fill="red",
                    font=self.main_app.default_font, anchor="center", justify="center",
                    width=canvas_width*0.9
                )
            except Exception: pass # Evitar errores si el canvas falla

    def clear_preview(self):
        """Limpia el canvas y resetea el estado interno relacionado."""
        logging.debug("Limpiando previsualización.")
        self.current_image_numpy = None
        self.current_ocr_regions = []
        self.selected_indices = []
        self._draw_canvas_content() # Redibuja (mostrará "Sin Imagen")

    def _on_canvas_resize(self, event):
        """Se llama cuando el tamaño del canvas cambia, redibuja el contenido."""
        # Solo redibujar si realmente ha cambiado el tamaño para evitar bucles
        # y si tenemos una imagen cargada
        if (event.width > 1 and event.height > 1 and
                (event.width != self.preview_canvas.winfo_width() or
                 event.height != self.preview_canvas.winfo_height())):
             if self.current_image_numpy is not None:
                 logging.debug(f"Canvas redimensionado a {event.width}x{event.height}. Redibujando.")
                 self._draw_canvas_content()

    # --- Futuro: Manejo de Clics en Canvas para seleccionar región ---
    # def _on_canvas_click(self, event):
    #     if not self.current_image_numpy or not self.current_ocr_regions:
    #         return
    #
    #     # Convertir coordenadas del evento (canvas) a coordenadas de la imagen original
    #     canvas_x = self.preview_canvas.canvasx(event.x) - self.image_offset[0]
    #     canvas_y = self.preview_canvas.canvasy(event.y) - self.image_offset[1]
    #
    #     # Comprobar si el clic está dentro de la imagen mostrada
    #     if 0 <= canvas_x < (self.current_image_numpy.shape[1] * self.display_scale) and \
    #        0 <= canvas_y < (self.current_image_numpy.shape[0] * self.display_scale):
    #
    #         original_x = int(canvas_x / self.display_scale)
    #         original_y = int(canvas_y / self.display_scale)
    #
    #         # Buscar qué región OCR contiene este punto
    #         clicked_region_index = -1
    #         for i, region_data in enumerate(self.current_ocr_regions):
    #              r = region_data.get('region')
    #              if r and (r['left'] <= original_x < r['left'] + r['width']) and \
    #                       (r['top'] <= original_y < r['top'] + r['height']):
    #                  clicked_region_index = i
    #                  break # Encontrar la primera (o la más interna si se solapan)
    #
    #         if clicked_region_index != -1:
    #              logging.debug(f"Clic en región OCR {clicked_region_index+1}")
    #              # Notificar a la aplicación principal o al panel OCR para seleccionar la fila
    #              # self.main_app.select_ocr_region_by_index(clicked_region_index)
    #         else:
    #              logging.debug("Clic fuera de cualquier región OCR.")
    #              # Opcional: Deseleccionar todo
    #              # self.main_app.select_ocr_region_by_index(None)


# --- END OF FILE src/panels/image_preview_panel.py ---