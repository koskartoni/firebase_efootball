# --- START OF FILE src/panels/preview_panel.py ---
import os
import tkinter as tk
from tkinter import ttk
import logging
from PIL import Image, ImageTk, ImageDraw, ImageFont # Pillow para manejo avanzado de imágenes
import cv2 # OpenCV para posible conversión inicial BGR -> RGB
import numpy as np

class PreviewPanel(ttk.LabelFrame):
    """
    Panel para mostrar una previsualización de imagen (captura o plantilla),
    ajustándola al tamaño del canvas disponible.
    """
    def __init__(self, master, main_app, **kwargs):
        """
        Inicializa el Panel de Previsualización.

        Args:
            master: El widget padre (normalmente el frame de la columna derecha).
            main_app: Una referencia a la instancia principal de ScreenTesterGUI.
            **kwargs: Argumentos adicionales para ttk.LabelFrame.
        """
        kwargs['text'] = kwargs.get('text', "Previsualización Estado")
        super().__init__(master, **kwargs)
        self.main_app = main_app
        logging.debug("Inicializando PreviewPanel.")

        # --- Estado Interno ---
        self.current_image_pil = None # Imagen original en formato PIL (para redimensionar)
        self.current_image_tk = None  # Imagen convertida para Tkinter (¡NECESARIO MANTENER REFERENCIA!)
        self.current_canvas_image_id = None # ID del item imagen en el canvas
        self.info_label_var = tk.StringVar(value="-")

        # --- Widgets ---
        self._create_widgets()

        # --- Bindings ---
        # Redibujar la imagen cuando el tamaño del canvas cambie
        self.preview_canvas.bind("<Configure>", self._on_canvas_configure)

    def _create_widgets(self):
        """Crea el canvas y la etiqueta de información."""
        logging.debug("Creando widgets para PreviewPanel.")

        # Canvas para la imagen
        # Usar un color de fondo distintivo para ver el área del canvas
        self.preview_canvas = tk.Canvas(self, bg="#E0E0E0", relief="sunken", borderwidth=1)
        self.preview_canvas.grid(row=0, column=0, sticky="nsew")

        # Etiqueta para información adicional debajo del canvas
        self.preview_info_label = ttk.Label(self, textvariable=self.info_label_var, anchor="center")
        self.preview_info_label.grid(row=1, column=0, sticky="ew", pady=(5, 0), padx=5)

        # Configurar grid para que el canvas se expanda
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        logging.debug("Widgets de PreviewPanel creados.")

    def update_preview(self, image_source, info_text="-"):
        """
        Muestra una imagen en el canvas, redimensionándola para ajustarse.

        Args:
            image_source: La fuente de la imagen. Puede ser:
                          - numpy.ndarray (BGR, como de cv2 o mss)
                          - str (ruta a un archivo de imagen)
                          - PIL.Image.Image
                          - None (para limpiar la previsualización)
            info_text (str): Texto opcional para mostrar en la etiqueta de información.
        """
        logging.debug(f"Actualizando previsualización. Fuente: {type(image_source)}, Info: '{info_text}'")
        # Limpiar previsualización anterior antes de cargar una nueva
        self._clear_canvas_image()
        self.info_label_var.set("-") # Resetear info por defecto

        if image_source is None:
            self.current_image_pil = None # Asegurar que no hay imagen guardada
            logging.debug("Fuente de imagen es None, limpiando previsualización.")
            return # Ya se limpió el canvas

        # --- Cargar la imagen a formato PIL ---
        img_pil = None
        original_size = (0, 0)
        try:
            if isinstance(image_source, np.ndarray):
                # Asumir BGR de OpenCV/MSS y convertir a RGB para PIL
                if image_source.ndim == 3 and image_source.shape[2] == 3:
                    img_pil = Image.fromarray(cv2.cvtColor(image_source, cv2.COLOR_BGR2RGB))
                    original_size = (image_source.shape[1], image_source.shape[0]) # (width, height)
                else:
                     logging.warning(f"Formato numpy array inesperado: {image_source.shape}. No se puede mostrar.")
                     self.info_label_var.set("Error: Formato NumPy inválido")
                     return
            elif isinstance(image_source, str):
                # Es una ruta de archivo
                try:
                    img_pil = Image.open(image_source)
                    # Convertir a RGB si es RGBA u otros modos para evitar problemas con Tkinter
                    if img_pil.mode != 'RGB':
                        logging.debug(f"Convirtiendo imagen '{image_source}' de modo {img_pil.mode} a RGB.")
                        img_pil = img_pil.convert('RGB')
                    original_size = img_pil.size # (width, height)
                except FileNotFoundError:
                    logging.error(f"Archivo de imagen no encontrado: {image_source}")
                    self.info_label_var.set(f"Error: Archivo no encontrado\n{os.path.basename(image_source)}")
                    return
                except Exception as e:
                    logging.exception(f"Error al abrir imagen '{image_source}': {e}")
                    self.info_label_var.set(f"Error: No se pudo abrir imagen\n{os.path.basename(image_source)}")
                    return
            elif isinstance(image_source, Image.Image):
                img_pil = image_source
                if img_pil.mode != 'RGB':
                    logging.debug(f"Convirtiendo imagen PIL de modo {img_pil.mode} a RGB.")
                    img_pil = img_pil.convert('RGB')
                original_size = img_pil.size
            else:
                logging.error(f"Tipo de fuente de imagen no soportado: {type(image_source)}")
                self.info_label_var.set("Error: Tipo de imagen no soportado")
                return

            # Guardar la imagen PIL original para redimensionamientos posteriores
            self.current_image_pil = img_pil
            # Actualizar info (si no se proporcionó una específica)
            if info_text == "-":
                 self.info_label_var.set(f"Original: {original_size[0]}x{original_size[1]}px")
            else:
                 self.info_label_var.set(info_text)

            # Forzar un evento <Configure> para dibujar la imagen con el tamaño actual del canvas
            # O llamar directamente a _draw_image_on_canvas si el canvas ya tiene tamaño
            if self.preview_canvas.winfo_width() > 1 and self.preview_canvas.winfo_height() > 1:
                self._draw_image_on_canvas()
            else:
                # El canvas aún no tiene tamaño, se dibujará en el primer <Configure>
                logging.debug("Canvas aún sin tamaño, la imagen se dibujará en el primer evento Configure.")

        except Exception as e:
            logging.exception(f"Error inesperado procesando la fuente de imagen: {e}")
            self.current_image_pil = None
            self.info_label_var.set("Error procesando imagen")

    def _draw_image_on_canvas(self):
        """Redimensiona y dibuja la imagen PIL actual en el canvas."""
        if not self.current_image_pil:
            return # No hay imagen para dibujar

        canvas_width = self.preview_canvas.winfo_width()
        canvas_height = self.preview_canvas.winfo_height()

        # Evitar división por cero o dibujar si el canvas es minúsculo
        if canvas_width <= 1 or canvas_height <= 1:
            # logging.debug("Canvas demasiado pequeño para dibujar.")
            return

        img_width, img_height = self.current_image_pil.size

        # Calcular relación de aspecto
        img_ratio = img_width / img_height
        canvas_ratio = canvas_width / canvas_height

        # Determinar dimensiones de escalado manteniendo relación de aspecto
        if canvas_ratio > img_ratio:
            # El canvas es más ancho que la imagen (relativamente) -> ajustar por altura
            new_height = canvas_height
            new_width = int(new_height * img_ratio)
        else:
            # El canvas es más alto que la imagen (relativamente) -> ajustar por anchura
            new_width = canvas_width
            new_height = int(new_width / img_ratio)

        # Asegurarse de que las nuevas dimensiones no sean cero
        new_width = max(1, new_width)
        new_height = max(1, new_height)

        try:
            # Redimensionar la imagen original usando Pillow
            # Usar LANCZOS (o ANTIALIAS) para mejor calidad de redimensionado
            resized_img_pil = self.current_image_pil.resize((new_width, new_height), Image.Resampling.LANCZOS)

            # Convertir a formato Tkinter PhotoImage
            # ¡¡Guardar la referencia en self.current_image_tk es VITAL!!
            self.current_image_tk = ImageTk.PhotoImage(resized_img_pil)

            # Limpiar imagen anterior del canvas si existe
            self._clear_canvas_image()

            # Dibujar la nueva imagen en el centro del canvas
            x_pos = (canvas_width - new_width) // 2
            y_pos = (canvas_height - new_height) // 2
            self.current_canvas_image_id = self.preview_canvas.create_image(
                x_pos, y_pos, anchor=tk.NW, image=self.current_image_tk
            )
            # logging.debug(f"Imagen redibujada en canvas. Tamaño: {new_width}x{new_height}")

        except Exception as e:
            logging.exception(f"Error al redimensionar o dibujar imagen en canvas: {e}")
            self._clear_canvas_image()
            self.info_label_var.set("Error dibujando imagen")

    def _clear_canvas_image(self):
        """Elimina la imagen actual del canvas si existe."""
        if self.current_canvas_image_id:
            try:
                self.preview_canvas.delete(self.current_canvas_image_id)
            except tk.TclError as e:
                 # Puede pasar si el widget ya fue destruido o el ID es inválido
                 logging.warning(f"Error menor al intentar borrar imagen del canvas (ID: {self.current_canvas_image_id}): {e}")
            self.current_canvas_image_id = None
        # No borramos self.current_image_tk aquí, PhotoImage debe mantenerse vivo
        # No borramos self.current_image_pil aquí, se necesita para redibujar

    def clear_preview(self):
        """Limpia completamente la previsualización (imagen y texto)."""
        logging.debug("Limpiando previsualización completa.")
        self._clear_canvas_image()
        self.current_image_pil = None
        self.current_image_tk = None # Liberar referencia a PhotoImage anterior
        self.info_label_var.set("-")

    def _on_canvas_configure(self, event):
        """
        Se llama cuando el tamaño del canvas cambia. Redibuja la imagen actual
        para que se ajuste al nuevo tamaño.
        """
        # Comprobar si tenemos una imagen PIL cargada para redibujar
        if self.current_image_pil:
            # logging.debug(f"Canvas redimensionado a {event.width}x{event.height}. Redibujando imagen.")
            self._draw_image_on_canvas()
        # else:
            # logging.debug(f"Canvas redimensionado a {event.width}x{event.height}. No hay imagen para redibujar.")

# --- END OF FILE src/panels/preview_panel.py ---