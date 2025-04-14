import os
import json
import datetime
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import cv2
import numpy as np
from PIL import Image, ImageTk
import mss
from tkinter import font
import logging

from src.screen_recognizer import TEMPLATE_MAPPING_FILE

# --- Constantes del proyecto ---
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMAGES_DIR = os.path.join(PROJECT_DIR, "images")
CONFIG_DIR = os.path.join(PROJECT_DIR, "config")
OCR_MAPPING_FILE_PATH = os.path.join(CONFIG_DIR, "ocr_regions.json")
TEMPLATE_MAPPING_FILE_PATH = os.path.join(CONFIG_DIR, "templates_mapping.json")
MAX_PREVIEW_WIDTH = 800 # Ancho máximo para la imagen en ventanas de selección
# --- Ajusta estos tamaños según tu preferencia ---
DEFAULT_FONT_SIZE = 12
MIN_WINDOW_WIDTH = 900 # Aumentado
MIN_WINDOW_HEIGHT = 750 # Aumentado
MIN_CANVAS_WIDTH = 400 # Tamaño mínimo del canvas de preview
MIN_CANVAS_HEIGHT = 300

# --- Configuración de Logging ---
# Configuración básica si este script se ejecuta solo
if not logging.getLogger().hasHandlers():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Funciones Auxiliares (Carga/Guardado/Captura) ---
def load_json_mapping(file_path, file_desc="mapping"):
    """Carga un mapping JSON desde un archivo con manejo de errores."""
    if not os.path.exists(file_path):
        logging.warning(f"Archivo de {file_desc} '{file_path}' no encontrado. Usando diccionario vacío.")
        return {}
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            if not content:
                logging.warning(f"Archivo de {file_desc} '{file_path}' está vacío.")
                return {}
            mapping = json.loads(content)
            if not isinstance(mapping, dict):
                logging.error(f"El contenido de {file_path} no es un diccionario JSON válido.")
                return {}
            return mapping
    except json.JSONDecodeError:
        logging.error(f"El archivo {file_path} está malformado o vacío.")
        messagebox.showerror("Error de Archivo", f"Error al leer el archivo JSON:\n{file_path}\nPuede estar corrupto o vacío.")
        return {}
    except Exception as e:
        logging.error(f"Error inesperado al cargar {file_path}: {e}")
        messagebox.showerror("Error", f"Error inesperado al cargar {file_desc}:\n{e}")
        return {}

def save_json_mapping(mapping, file_path, file_desc="mapping"):
    """Guarda un diccionario de mapping en un archivo JSON."""
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(mapping, f, indent=4, ensure_ascii=False)
        logging.info(f"Archivo de {file_desc} guardado en: {file_path}")
        return True
    except Exception as e:
        logging.error(f"Error al guardar {file_desc} en {file_path}: {e}")
        messagebox.showerror("Error", f"Error al guardar {file_desc}:\n{e}")
        return False

# Renombrar para claridad, ahora carga el mapping OCR completo
def load_ocr_data():
    return load_json_mapping(OCR_MAPPING_FILE_PATH, "regiones OCR")

# Renombrar para claridad
def save_ocr_data(mapping):
    return save_json_mapping(mapping, OCR_MAPPING_FILE_PATH, "regiones OCR")

# Renombrar para claridad
def load_template_data():
     return load_json_mapping(TEMPLATE_MAPPING_FILE_PATH, "plantillas")

# Renombrar para claridad
def save_template_data(mapping):
    return save_json_mapping(mapping, TEMPLATE_MAPPING_FILE_PATH, "plantillas")


def capture_screen(region=None, monitor=1):
    """Captura la pantalla (o una región específica) usando mss."""
    try:
        with mss.mss() as sct:
            monitors = sct.monitors
            if monitor < 1 or monitor >= len(monitors):
                 messagebox.showerror("Error", f"Monitor {monitor} no válido. Monitores disponibles: 1 a {len(monitors)-1}")
                 return None
            capture_area = region if region is not None else monitors[monitor]
            sct_img = sct.grab(capture_area)
            img = np.array(sct_img)
            img_bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            return img_bgr
    except mss.ScreenShotError as e:
         logging.error(f"Error MSS capturando {region or 'monitor '+str(monitor)}: {e}")
         messagebox.showerror("Error de Captura", f"No se pudo capturar la pantalla/región:\n{e}")
         return None
    except Exception as e:
        logging.error(f"Error inesperado en captura: {e}")
        messagebox.showerror("Error", f"Error inesperado durante la captura:\n{e}")
        return None


def tk_select_region_base(root, image, window_title, rect_outline="green", button_text="Confirmar Selección"):
    """Función base para seleccionar una región en una imagen con Tkinter."""
    if image is None:
         messagebox.showerror("Error Interno", "No se proporcionó imagen para la selección de región.")
         return None

    orig_height, orig_width = image.shape[:2]
    scale = 1.0
    max_display_width = root.winfo_screenwidth() * 0.8
    max_display_height = root.winfo_screenheight() * 0.8
    scale_w = max_display_width / orig_width if orig_width > max_display_width else 1.0
    scale_h = max_display_height / orig_height if orig_height > max_display_height else 1.0
    scale = min(scale_w, scale_h, 1.0)

    if scale < 1.0:
         new_width = int(orig_width * scale)
         new_height = int(orig_height * scale)
         try:
             interpolation = cv2.INTER_LANCZOS4 if hasattr(cv2, 'INTER_LANCZOS4') else cv2.INTER_AREA
             resized_img = cv2.resize(image, (new_width, new_height), interpolation=interpolation)
         except Exception as e:
              messagebox.showerror("Error de Redimensionamiento", f"No se pudo redimensionar la imagen: {e}")
              return None
    else:
        resized_img = image.copy()

    try:
        img_rgb = cv2.cvtColor(resized_img, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(img_rgb)
        tk_img = ImageTk.PhotoImage(pil_img)
    except Exception as e:
        messagebox.showerror("Error de Imagen", f"No se pudo convertir la imagen para mostrar: {e}")
        return None

    sel_win = tk.Toplevel(root)
    sel_win.title(window_title)
    sel_win.grab_set()
    sel_win.minsize(400, 300)

    canvas = tk.Canvas(sel_win, width=tk_img.width(), height=tk_img.height(), cursor="cross")
    canvas.pack(padx=5, pady=5, fill="both", expand=True)
    img_on_canvas = canvas.create_image(0, 0, anchor="nw", image=tk_img)
    # Guardar referencia a tk_img para evitar garbage collection
    canvas.image = tk_img

    selection = {"x1": None, "y1": None, "x2": None, "y2": None}
    rect = None
    confirmed_region_coords = None

    def on_button_press(event):
        selection["x1"] = canvas.canvasx(event.x) # Coordenadas del canvas
        selection["y1"] = canvas.canvasy(event.y)
        nonlocal rect
        if rect: canvas.delete(rect)
        rect = canvas.create_rectangle(selection["x1"], selection["y1"], selection["x1"], selection["y1"],
                                       outline=rect_outline, width=2, dash=(4, 2))

    def on_move_press(event):
        if rect:
            cur_x = canvas.canvasx(event.x)
            cur_y = canvas.canvasy(event.y)
            canvas.coords(rect, selection["x1"], selection["y1"], cur_x, cur_y)

    def on_button_release(event):
        if rect:
            selection["x2"] = canvas.canvasx(event.x)
            selection["y2"] = canvas.canvasy(event.y)

    canvas.bind("<ButtonPress-1>", on_button_press)
    canvas.bind("<B1-Motion>", on_move_press)
    canvas.bind("<ButtonRelease-1>", on_button_release)

    button_frame = ttk.Frame(sel_win)
    button_frame.pack(pady=10)

    def confirm_selection():
        nonlocal confirmed_region_coords
        if None not in (selection["x1"], selection["y1"], selection["x2"], selection["y2"]):
            x1, y1, x2, y2 = selection["x1"], selection["y1"], selection["x2"], selection["y2"]
            left_r, top_r = int(min(x1, x2)), int(min(y1, y2))
            width_r, height_r = int(abs(x2 - x1)), int(abs(y2 - y1))
            # Convertir a coordenadas originales
            left_orig = int(left_r / scale)
            top_orig = int(top_r / scale)
            width_orig = int(width_r / scale)
            height_orig = int(height_r / scale)
            # Asegurar ancho/alto mínimo 1
            width_orig = max(1, width_orig); height_orig = max(1, height_orig)
            confirmed_region_coords = {"left": left_orig, "top": top_orig, "width": width_orig, "height": height_orig}
        sel_win.destroy()

    def cancel_selection(): sel_win.destroy()

    confirm_btn = ttk.Button(button_frame, text=button_text, command=confirm_selection)
    confirm_btn.pack(side="left", padx=5)
    cancel_btn = ttk.Button(button_frame, text="Cancelar", command=cancel_selection)
    cancel_btn.pack(side="left", padx=5)
    sel_win.bind("<Escape>", lambda e: cancel_selection())

    root.wait_window(sel_win)
    return confirmed_region_coords


def tk_select_ocr_region(root, image):
    """Llama a la función base para seleccionar región OCR."""
    return tk_select_region_base(root, image, "Seleccione Región OCR", rect_outline="green", button_text="Confirmar Selección")


def tk_select_monitor_region(root, monitor_img, monitor_info):
    """Llama a la función base para seleccionar región del monitor."""
    coords_relative_to_resized = tk_select_region_base(root, monitor_img, "Seleccione Región del Monitor", rect_outline="blue", button_text="Confirmar Región")

    if coords_relative_to_resized:
        # Convertir a coordenadas absolutas de pantalla
        coords_absolute = coords_relative_to_resized.copy()
        coords_absolute['left'] += monitor_info['left']
        coords_absolute['top'] += monitor_info['top']
        return coords_absolute
    return None


class TemplateManagerGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Gestor de Zonas OCR y Plantillas")
        self.minsize(MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT)

        self.captured_image = None
        self.selected_image_path = None
        self.ocr_regions = [] # Lista de dicts: {"region": {...}, "expected_text": [...]}
        self.ocr_region_rects = []
        self.current_template_name = None
        self.template_names_mapping = {}
        self.ocr_regions_mapping = {}
        self.monitors_info = self.detect_monitors()

        self.setup_fonts_and_styles()
        self.create_widgets()
        self.load_template_names_from_json() # Carga inicial del Combobox
        self.load_ocr_regions_from_json() # Carga inicial de datos OCR

        logging.info("Template Manager GUI inicializado.")

    def setup_fonts_and_styles(self):
        """Configura la fuente y los estilos ttk."""
        self.default_font = font.nametofont("TkDefaultFont")
        self.default_font.configure(size=DEFAULT_FONT_SIZE)
        style = ttk.Style(self)
        # Intentar configurar estilo para todos los widgets ttk
        try:
             style.configure('.', font=self.default_font, padding=(3, 1)) # Añadir padding ligero
             style.configure('TLabelframe.Label', font=(self.default_font.actual()['family'], DEFAULT_FONT_SIZE, 'bold'))
             style.configure('TButton', padding=(6, 3)) # Padding para botones
             style.configure('TEntry', padding=(5, 3))
             style.configure('TCombobox', padding=(5, 3))
        except Exception as e:
             logging.warning(f"No se pudo configurar completamente el estilo ttk: {e}")
        # Forzar fuente en la raíz (afecta widgets tk estándar)
        self.option_add("*Font", self.default_font)


    def detect_monitors(self):
        """Detecta los monitores existentes usando mss."""
        try:
            with mss.mss() as sct:
                # Devolver lista completa (índice 0 es 'all screens')
                return sct.monitors
        except Exception as e:
            logging.error(f"Error detectando monitores: {e}")
            return [{}] # Fallback

    def load_ocr_regions_from_json(self):
        """Carga las regiones OCR desde ocr_regions.json."""
        self.ocr_regions_mapping = load_ocr_data() # Usar la función renombrada

    def create_widgets(self):
        """Crea y organiza los widgets principales."""
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.create_capture_frame()
        self.create_template_selection_frame()

        center_frame = ttk.Frame(self)
        center_frame.grid(row=2, column=0, padx=10, pady=10, sticky="nsew")
        center_frame.grid_rowconfigure(0, weight=1)
        center_frame.grid_columnconfigure(0, weight=1, minsize=MIN_CANVAS_WIDTH) # Peso y tamaño mínimo para preview
        center_frame.grid_columnconfigure(1, weight=0) # Config no necesita expandirse tanto

        self.create_preview_frame(center_frame)
        self.create_ocr_config_frame(center_frame)

        self.create_status_label()

    def create_capture_frame(self):
        """Crea el frame para capturar nuevas plantillas."""
        capture_frame = ttk.LabelFrame(self, text="Capturar Nueva Plantilla", padding=(10, 5))
        capture_frame.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="ew")

        # Definir variables antes de usarlas
        self.capture_type_var = tk.StringVar(value="monitor")
        self.monitor_var = tk.IntVar(value=1)
        self.new_template_name_var = tk.StringVar()

        capture_type_frame = ttk.Frame(capture_frame)
        capture_type_frame.pack(anchor="w", padx=5, pady=2)
        ttk.Radiobutton(capture_type_frame, text="Monitor Completo", variable=self.capture_type_var, value="monitor").pack(side="left", padx=5)
        ttk.Radiobutton(capture_type_frame, text="Región del Monitor", variable=self.capture_type_var, value="region").pack(side="left", padx=5)

        monitor_frame = ttk.Frame(capture_frame)
        monitor_frame.pack(anchor="w", padx=5, pady=2)
        ttk.Label(monitor_frame, text="Monitor:").pack(side="left", padx=5)
        num_monitors = len(self.monitors_info) - 1 if len(self.monitors_info) > 1 else 1
        self.monitor_spinbox = ttk.Spinbox(monitor_frame, from_=1, to=max(1, num_monitors), textvariable=self.monitor_var, width=5) # Asegurar que 'to' sea al menos 1
        self.monitor_spinbox.pack(side="left", padx=5)

        ttk.Button(capture_frame, text="Capturar Pantalla", command=self.capture_new_template).pack(anchor="w", padx=5, pady=5)

        name_frame = ttk.Frame(capture_frame)
        name_frame.pack(anchor="w", padx=5, pady=2)
        ttk.Label(name_frame, text="Nombre Nueva Plantilla:").pack(side="left", padx=5)
        ttk.Entry(name_frame, textvariable=self.new_template_name_var, width=30).pack(side="left", padx=5)

        ttk.Button(capture_frame, text="Guardar Nueva Plantilla", command=self.save_new_template).pack(anchor="w", padx=5, pady=5)


    def create_template_selection_frame(self):
        """Crea el frame para seleccionar plantillas existentes."""
        template_frame = ttk.LabelFrame(self, text="Seleccionar Plantilla Existente", padding=(10, 5))
        template_frame.grid(row=1, column=0, padx=10, pady=5, sticky="ew")

        combo_frame = ttk.Frame(template_frame)
        combo_frame.pack(fill="x", padx=5, pady=5)

        ttk.Label(combo_frame, text="Plantilla Existente:").pack(side="left", padx=5, pady=5)
        self.template_name_var = tk.StringVar()
        self.template_name_combobox = ttk.Combobox(combo_frame, textvariable=self.template_name_var, width=30, state="readonly") # readonly para evitar escritura
        self.template_name_combobox.pack(side="left", padx=5, pady=5, fill="x", expand=True)
        self.template_name_combobox.bind("<<ComboboxSelected>>", self.on_template_name_selected)

        ttk.Button(combo_frame, text="Refrescar Lista", command=self.load_template_names_from_json).pack(side="left", padx=5, pady=5)


    def create_preview_frame(self, parent_frame):
        """Crea el frame de previsualización de la imagen."""
        preview_frame = ttk.LabelFrame(parent_frame, text="Previsualización", padding=(10, 5))
        preview_frame.grid(row=0, column=0, padx=(0, 5), pady=5, sticky="nsew")
        preview_frame.grid_rowconfigure(0, weight=1)
        preview_frame.grid_columnconfigure(0, weight=1)

        # Frame interno para el canvas para controlar mejor el tamaño mínimo
        canvas_container = ttk.Frame(preview_frame)
        canvas_container.grid(row=0, column=0, sticky="nsew")
        canvas_container.grid_rowconfigure(0, weight=1)
        canvas_container.grid_columnconfigure(0, weight=1)

        self.preview_label = tk.Canvas(canvas_container, width=MIN_CANVAS_WIDTH, height=MIN_CANVAS_HEIGHT, bg="lightgrey", highlightthickness=0)
        self.preview_label.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")
        # Bind para redibujar al cambiar tamaño del *contenedor* del canvas
        canvas_container.bind("<Configure>", lambda event: self.show_preview())

    def create_ocr_config_frame(self, parent_frame):
        """Crea el frame para la configuración de zonas OCR."""
        config_frame = ttk.LabelFrame(parent_frame, text="Configuración OCR", padding=(10, 5))
        config_frame.grid(row=0, column=1, padx=(5, 0), pady=5, sticky="nsew")
        config_frame.grid_columnconfigure(0, weight=1) # Columna para widgets se expande horizontalmente

        # --- Widgets para marcar región ---
        mark_region_frame = ttk.Frame(config_frame)
        mark_region_frame.grid(row=0, column=0, pady=5, sticky="ew")
        # mark_region_frame.grid_columnconfigure(0, weight=1) # No necesita expandir columna interna

        ttk.Button(mark_region_frame, text="Marcar Región OCR", command=self.mark_ocr_region).pack(pady=2)

        # --- Entrada para Texto Esperado ---
        expected_text_frame = ttk.Frame(config_frame)
        expected_text_frame.grid(row=1, column=0, pady=5, sticky="ew")
        expected_text_frame.grid_columnconfigure(0, weight=1) # Permitir que Entry expanda

        ttk.Label(expected_text_frame, text="Texto Esperado (opcional, separar con '|'):").pack(anchor="w", padx=5)
        self.expected_text_var = tk.StringVar()
        ttk.Entry(expected_text_frame, textvariable=self.expected_text_var).pack(fill="x", padx=5, pady=2)

        # --- Label para mostrar zonas marcadas ---
        self.region_label = ttk.Label(config_frame, text="Zonas OCR: 0 definidas", anchor="center")
        self.region_label.grid(row=2, column=0, pady=5, sticky="ew")

        # --- Botones de acción ---
        action_frame = ttk.Frame(config_frame)
        action_frame.grid(row=3, column=0, pady=5, sticky="ew")
        # Centrar botones usando pack dentro de este frame
        ttk.Button(action_frame, text="Limpiar Zonas Marcadas", command=self.clear_ocr_regions).pack(side="left", padx=10, pady=5, expand=True)
        ttk.Button(action_frame, text="Guardar Zonas OCR", command=self.save_ocr_regions).pack(side="left", padx=10, pady=5, expand=True)


    def create_status_label(self):
        """Crea el label para mensajes de estado."""
        self.status_label_var = tk.StringVar(value="Listo.")
        status_frame = ttk.Frame(self, height=20) # Frame para darle espacio
        status_frame.grid(row=3, column=0, padx=10, pady=(5, 10), sticky="ew")
        status_frame.pack_propagate(False) # Evitar que el frame se encoja
        self.status_label = ttk.Label(status_frame, textvariable=self.status_label_var, anchor="w")
        self.status_label.pack(side="left", padx=5)


    def load_template_names_from_json(self):
        """Carga nombres de plantillas desde JSON y actualiza Combobox."""
        try:
            mapping = load_template_data() # Usar helper renombrado
            self.template_names_mapping = mapping
            template_names = sorted(list(self.template_names_mapping.keys()))
            self.template_name_combobox['values'] = template_names
            if template_names:
                 # Seleccionar el primero por defecto si la lista no está vacía
                 # self.template_name_var.set(template_names[0])
                 # self.on_template_name_selected(None) # Cargar datos del primero
                 pass # O dejar vacío hasta que el usuario seleccione
            else:
                 self.template_name_var.set("") # Limpiar si no hay plantillas
            self.status_message("Lista de plantillas refrescada.")
        except Exception as e:
            logging.error(f"Error inesperado al cargar nombres de plantillas: {e}")
            messagebox.showerror("Error", f"Error al cargar nombres de plantillas: {e}")


    def on_template_name_selected(self, event):
        """Se llama al seleccionar un nombre de plantilla del Combobox."""
        selected_name = self.template_name_var.get()
        if not selected_name: return # No hacer nada si la selección está vacía

        self.current_template_name = selected_name # Guardar nombre actual
        self.clear_ocr_regions() # Limpiar regiones al cambiar de plantilla

        image_files = self.template_names_mapping.get(selected_name, [])
        self.captured_image = None # Resetear imagen
        self.selected_image_path = None

        if image_files:
            # Intentar cargar la *primera* imagen de la lista para previsualización
            first_image_file = image_files[0]
            image_path = os.path.join(IMAGES_DIR, first_image_file)
            if os.path.exists(image_path):
                try:
                    self.selected_image_path = image_path
                    self.captured_image = cv2.imread(image_path)
                    if self.captured_image is None:
                        raise Exception(f"OpenCV no pudo leer '{first_image_file}'.")
                    logging.info(f"Imagen '{first_image_file}' cargada para '{selected_name}'.")
                except Exception as e:
                    logging.error(f"Error al cargar imagen para '{selected_name}': {e}")
                    messagebox.showerror("Error Carga Imagen", f"Error al cargar:\n{first_image_file}\n\n{e}")
            else:
                logging.warning(f"Archivo de imagen '{first_image_file}' no encontrado para '{selected_name}'.")
                messagebox.showwarning("Archivo Faltante", f"No se encontró la imagen:\n{first_image_file}\n\nAsociada a '{selected_name}'.")
        else:
             logging.warning(f"No hay archivos de imagen listados para '{selected_name}'.")
             messagebox.showwarning("Sin Imágenes", f"La plantilla '{selected_name}' no tiene archivos de imagen asociados en el JSON.")

        # Cargar regiones OCR para este estado (si existen)
        if selected_name in self.ocr_regions_mapping:
            # Asegurar que sea una lista de diccionarios válidos
            loaded_regions = self.ocr_regions_mapping[selected_name]
            if isinstance(loaded_regions, list):
                self.ocr_regions = [r for r in loaded_regions if isinstance(r, dict) and 'region' in r] # Filtrar inválidos
                if len(self.ocr_regions) != len(loaded_regions):
                     logging.warning(f"Se encontraron/eliminaron regiones OCR mal formadas para '{selected_name}'.")
            else:
                 logging.warning(f"Datos de región OCR para '{selected_name}' no son una lista. Ignorando.")
                 self.ocr_regions = []
            self.status_message(f"'{selected_name}' seleccionado. {len(self.ocr_regions)} zona(s) OCR cargada(s).")
        else:
            self.ocr_regions = []
            self.status_message(f"'{selected_name}' seleccionado. No hay zonas OCR definidas.")

        self.update_region_label()
        self.show_preview() # Actualizar previsualización (mostrará imagen o nada)


    def capture_new_template(self):
        """Captura una nueva plantilla desde la pantalla."""
        self.status_message("Capturando pantalla...")
        capture_type = self.capture_type_var.get()
        monitor_idx = self.monitor_var.get()

        # Validar índice del monitor (1-based)
        if monitor_idx < 1 or monitor_idx >= len(self.monitors_info):
            messagebox.showerror("Error", f"Monitor {monitor_idx} no válido.")
            self.status_message("Error: Índice de monitor inválido.")
            return

        target_monitor_info = self.monitors_info[monitor_idx] # Info del monitor seleccionado

        if capture_type == "monitor":
             # Esconder ventana principal temporalmente
             self.withdraw(); self.update_idletasks(); time.sleep(0.3) # Delay corto
             self.captured_image = capture_screen(monitor=monitor_idx)
             self.deiconify() # Volver a mostrar
        elif capture_type == "region":
            self.withdraw(); self.update_idletasks(); time.sleep(0.3)
            monitor_image = capture_screen(monitor=monitor_idx)
            self.deiconify()
            if monitor_image is not None:
                # Pasar info del monitor para cálculo correcto de coords absolutas
                region_absolute = tk_select_monitor_region(self, monitor_image, target_monitor_info)
                if region_absolute:
                    # Capturar usando las coordenadas absolutas
                    self.captured_image = capture_screen(region=region_absolute, monitor=monitor_idx)
                else: self.captured_image = None
            else: self.captured_image = None

        if self.captured_image is not None:
            self.selected_image_path = None
            self.template_name_var.set("") # Limpiar selección de plantilla existente
            self.clear_ocr_regions() # Limpiar regiones al capturar nueva imagen
            self.show_preview()
            self.status_message("Pantalla capturada. Introduce nombre y guarda.")
        else:
            self.status_message("Captura cancelada o fallida.")


    def save_new_template(self):
        """Guarda la nueva plantilla capturada y actualiza mappings."""
        if self.captured_image is None: messagebox.showerror("Error", "."); return
        template_name = self.new_template_name_var.get().strip()
        if not template_name: messagebox.showerror("Error", "."); return

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        image_filename = f"{template_name}_{timestamp}.png"
        image_path = os.path.join(IMAGES_DIR, image_filename)

        try:
            # Asegurar que el directorio de imágenes exista
            os.makedirs(IMAGES_DIR, exist_ok=True)
            cv2.imwrite(image_path, self.captured_image)
            logging.info(f"Plantilla guardada como '{image_filename}'.")
            self.status_message(f"Guardado: {image_filename}")

            # Actualizar templates_mapping.json
            mapping = load_template_data() # Cargar mapping actual
            if template_name in mapping:
                if isinstance(mapping[template_name], list):
                    mapping[template_name].append(image_filename) # Añadir a lista
                    logging.info(f"Añadida imagen {image_filename} a plantilla '{template_name}'.")
                else: # Corregir si no era lista
                    mapping[template_name] = [mapping[template_name], image_filename]
                    logging.warning(f"Entrada '{template_name}' no era lista, corregida y añadida {image_filename}.")
            else:
                mapping[template_name] = [image_filename] # Crear nueva
                logging.info(f"Creada nueva plantilla '{template_name}' con {image_filename}.")

            if save_template_data(mapping): # Guardar mapping actualizado
                self.load_template_names_from_json() # Recargar y ordenar combobox
                self.template_name_var.set(template_name) # Seleccionar la nueva/actualizada
                self.new_template_name_var.set("") # Limpiar campo
                self.status_message(f"Plantilla '{template_name}' guardada y añadida al mapping.")
                # Mantener la imagen capturada en preview, no llamar a on_template_selected
            else:
                 messagebox.showerror("Error Guardado", f"No se pudo guardar {TEMPLATE_MAPPING_FILE}")

        except Exception as e:
            logging.error(f"Error al guardar la plantilla: {e}")
            messagebox.showerror("Error", f"Error al guardar la plantilla:\n{e}")
            self.status_message("Error al guardar plantilla.")


    def load_image(self):
        """Carga una imagen desde archivo y la asocia a una plantilla si coincide."""
        # ... (Lógica similar a on_template_name_selected para cargar y asociar) ...
        file_path = filedialog.askopenfilename(initialdir=IMAGES_DIR, title="Seleccionar Imagen",
                                               filetypes=(("Archivos PNG", "*.png"), ("Todos los archivos", "*.*")))
        if file_path:
            self.clear_ocr_regions()
            self.captured_image = None
            self.selected_image_path = file_path
            try:
                self.captured_image = cv2.imread(file_path)
                if self.captured_image is None: raise Exception("OpenCV no pudo leer imagen.")
            except Exception as e:
                logging.error(f"Error cargando imagen {file_path}: {e}")
                messagebox.showerror("Error Carga", f"Error al cargar:\n{file_path}\n\n{e}")
                self.captured_image = None; self.selected_image_path = None
                self.show_preview(); return

            base_filename = os.path.basename(file_path)
            found_template_name = None
            for name, files in self.template_names_mapping.items():
                if base_filename in files: found_template_name = name; break

            if found_template_name:
                 self.template_name_var.set(found_template_name)
                 # Cargar regiones OCR asociadas
                 if found_template_name in self.ocr_regions_mapping:
                      self.ocr_regions = self.ocr_regions_mapping[found_template_name]
                 self.status_message(f"Imagen '{base_filename}' cargada (asociada a '{found_template_name}').")
            else:
                 self.template_name_var.set("") # No asociada
                 self.status_message(f"Imagen '{base_filename}' cargada (no asociada a plantilla existente).")

            self.update_region_label()
            self.show_preview()
        else:
            self.status_message("Carga cancelada.")

    def show_preview(self):
        """Muestra la imagen en el canvas y dibuja regiones OCR."""
        # ... (Lógica de redimensionamiento y dibujo igual que en tester) ...
        try:
            canvas_width = self.preview_label.winfo_width(); canvas_height = self.preview_label.winfo_height()
        except tk.TclError: canvas_width, canvas_height = MIN_CANVAS_WIDTH, MIN_CANVAS_HEIGHT
        if canvas_width < MIN_CANVAS_WIDTH: canvas_width = MIN_CANVAS_WIDTH
        if canvas_height < MIN_CANVAS_HEIGHT: canvas_height = MIN_CANVAS_HEIGHT

        self.preview_label.delete("all")

        if self.captured_image is None:
            self.preview_label.config(width=canvas_width, height=canvas_height)
            self.preview_label.create_text(canvas_width/2, canvas_height/2, text="Carga o Captura una Imagen", fill="grey", font=self.default_font)
            return

        # Redimensionar
        img_rgb = cv2.cvtColor(self.captured_image, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(img_rgb)
        img_aspect = pil_img.width / pil_img.height
        canvas_aspect = canvas_width / canvas_height
        if img_aspect > canvas_aspect: new_width = canvas_width; new_height = int(new_width / img_aspect)
        else: new_height = canvas_height; new_width = int(new_height * img_aspect)
        new_width = max(1, min(new_width, canvas_width)); new_height = max(1, min(new_height, canvas_height))
        try: resample_method = Image.Resampling.LANCZOS
        except AttributeError: resample_method = Image.ANTIALIAS
        pil_img = pil_img.resize((new_width, new_height), resample_method)
        self.tk_img = ImageTk.PhotoImage(pil_img)

        # Dibujar imagen y centrar
        x_offset = (canvas_width - new_width) // 2; y_offset = (canvas_height - new_height) // 2
        self.preview_label.create_image(x_offset, y_offset, anchor="nw", image=self.tk_img)
        self.preview_label.image = self.tk_img # Mantener referencia

        # Dibujar regiones
        scale_x = new_width / self.captured_image.shape[1]; scale_y = new_height / self.captured_image.shape[0]
        self.ocr_region_rects = []
        for region_data in self.ocr_regions:
            try:
                region = region_data['region']
                expected_texts = region_data.get('expected_text', [])
                x1, y1 = int(region['left'] * scale_x) + x_offset, int(region['top'] * scale_y) + y_offset
                x2, y2 = int((region['left'] + region['width']) * scale_x) + x_offset, int((region['top'] + region['height']) * scale_y) + y_offset
                outline_color = "purple" if expected_texts else "red"
                rect_id = self.preview_label.create_rectangle(x1, y1, x2, y2, outline=outline_color, width=2, tags="ocr_region")
                self.ocr_region_rects.append(rect_id)
            except (KeyError, TypeError) as e: logging.warning(f"Error dibujando región {region_data}: {e}")
            except Exception as e: logging.error(f"Error inesperado dibujando región {region_data}: {e}")
        self.preview_label.config(width=canvas_width, height=canvas_height)


    def mark_ocr_region(self):
        """Abre ventana para seleccionar región OCR y la añade a la lista."""
        if self.captured_image is None: messagebox.showerror("Error", "Carga o captura una imagen primero."); return
        region_coords = tk_select_ocr_region(self, self.captured_image) # Usar función base
        if region_coords:
            expected_text_str = self.expected_text_var.get().strip()
            expected_texts = [txt.strip() for txt in expected_text_str.split('|') if txt.strip()]
            self.ocr_regions.append({"region": region_coords, "expected_text": expected_texts})
            self.expected_text_var.set("")
            self.update_region_label()
            self.show_preview()
        else: messagebox.showinfo("Información", "No se seleccionó región.")

    def update_region_label(self):
        """Actualiza el label que muestra las zonas OCR."""
        self.region_label.config(text=f"Zonas OCR: {len(self.ocr_regions)} definida(s)")

    def clear_ocr_regions(self):
        """Limpia lista de regiones OCR, previsualización y label."""
        self.ocr_regions = []
        self.update_region_label()
        self.show_preview()

    def save_ocr_regions(self):
        """Guarda regiones OCR en ocr_regions.json para la plantilla seleccionada."""
        template_name = self.template_name_var.get().strip()
        if not template_name: messagebox.showerror("Error", "Selecciona plantilla existente del Combobox."); return

        if not self.ocr_regions:
            if messagebox.askyesno("Confirmar", f"No hay zonas marcadas.\n¿Eliminar TODAS las zonas OCR para '{template_name}'?"):
                 logging.info(f"Eliminando regiones OCR para '{template_name}'.")
            else: self.status_message("Guardado cancelado."); return

        mapping = load_ocr_data() # Cargar mapping actual
        mapping[template_name] = self.ocr_regions # Guardar/Sobreescribir
        if save_ocr_data(mapping): # Guardar
            self.ocr_regions_mapping = mapping # Actualizar en memoria
            messagebox.showinfo("Éxito", f"Zonas OCR guardadas para '{template_name}'.")
            self.status_message(f"Zonas OCR guardadas para '{template_name}'.")
            # Podríamos limpiar self.ocr_regions aquí si quisiéramos forzar recarga
        else: messagebox.showerror("Error", f"No se pudo guardar {OCR_MAPPING_FILE_PATH}")


    def status_message(self, message):
        """Actualiza el mensaje en el label de estado."""
        self.status_label_var.set(message)
        self.update_idletasks()

if __name__ == "__main__":
    # Asegurar que existan los directorios
    if not os.path.exists(IMAGES_DIR): os.makedirs(IMAGES_DIR)
    if not os.path.exists(CONFIG_DIR): os.makedirs(CONFIG_DIR)
    # No crear archivos JSON aquí, load_json_mapping los maneja si no existen

    app = TemplateManagerGUI()
    app.bind("<Configure>", lambda event: app.show_preview() if hasattr(app, 'preview_label') and app.preview_label.winfo_exists() else None)
    app.mainloop()