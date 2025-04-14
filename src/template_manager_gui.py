# --- START OF FILE template_manager_gui ---

import os
import json
import datetime
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import cv2
import numpy as np
from PIL import Image, ImageTk, ImageDraw, ImageFont # Añadido ImageDraw y ImageFont
import mss
from tkinter import font
import logging
import re # Importado para validación nombre plantilla

# --- Constantes del proyecto ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
IMAGES_DIR = os.path.join(PROJECT_DIR, "images")
CONFIG_DIR = os.path.join(PROJECT_DIR, "config")
OCR_MAPPING_FILE_PATH = os.path.join(CONFIG_DIR, "ocr_regions.json")
TEMPLATE_MAPPING_FILE_PATH = os.path.join(CONFIG_DIR, "templates_mapping.json")
MAX_PREVIEW_WIDTH = 800

# --- Ajustes de UI ---
DEFAULT_FONT_SIZE = 12
MIN_WINDOW_WIDTH = 950 # Ligeramente más ancho para el Treeview
MIN_WINDOW_HEIGHT = 750
MIN_CANVAS_WIDTH = 400
MIN_CANVAS_HEIGHT = 300
PREVIEW_NUMBER_FONT_SIZE = 14
TREEVIEW_ROW_HEIGHT = 25 # Ajustar según fuente

# --- Configuración de Logging ---
log_file_path = os.path.join(PROJECT_DIR, "logs", "template_manager.log")
os.makedirs(os.path.dirname(log_file_path), exist_ok=True)

if not logging.getLogger().hasHandlers():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
        handlers=[
            logging.FileHandler(log_file_path, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )

# --- Funciones Auxiliares (Sin cambios) ---
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
               messagebox.showerror("Error de Archivo", f"El contenido de {file_path} no es un diccionario JSON válido.")
               return {}
           return mapping
   except json.JSONDecodeError as e:
       logging.error(f"El archivo {file_path} está malformado o vacío: {e}")
       messagebox.showerror("Error de Archivo", f"Error al leer el archivo JSON:\n{file_path}\nPuede estar corrupto o vacío.\nDetalle: {e}")
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
       messagebox.showerror("Error al Guardar", f"No se pudo guardar el archivo {file_desc}:\n{file_path}\nError: {e}")
       return False

def load_ocr_data():
   return load_json_mapping(OCR_MAPPING_FILE_PATH, "regiones OCR")

def save_ocr_data(mapping):
   return save_json_mapping(mapping, OCR_MAPPING_FILE_PATH, "regiones OCR")

def load_template_data():
    return load_json_mapping(TEMPLATE_MAPPING_FILE_PATH, "plantillas")

def save_template_data(mapping):
   return save_json_mapping(mapping, TEMPLATE_MAPPING_FILE_PATH, "plantillas")

def capture_screen(region=None, monitor=1):
   # (Sin cambios respecto a la versión anterior que te di)
   try:
       with mss.mss() as sct:
           monitors = sct.monitors
           if monitor < 1 or monitor >= len(monitors):
                messagebox.showerror("Error de Monitor", f"Monitor {monitor} no válido. Monitores disponibles: 1 a {len(monitors)-1}")
                return None
           target_monitor = monitors[monitor]
           capture_area = region if region is not None else target_monitor
           if region:
                capture_area['width'] = min(region['width'], target_monitor['width'] - (region['left'] - target_monitor['left']))
                capture_area['height'] = min(region['height'], target_monitor['height'] - (region['top'] - target_monitor['top']))
                capture_area['left'] = max(region['left'], target_monitor['left'])
                capture_area['top'] = max(region['top'], target_monitor['top'])
                if capture_area['width'] <= 0 or capture_area['height'] <= 0:
                    logging.error(f"Región calculada inválida: {capture_area}")
                    messagebox.showerror("Error de Región", f"La región especificada {region} resulta inválida o fuera de los límites del monitor {monitor}.")
                    return None
           logging.info(f"Capturando área: {capture_area}")
           sct_img = sct.grab(capture_area)
           img = np.array(sct_img)
           img_bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
           return img_bgr
   except mss.ScreenShotError as e:
        logging.error(f"Error MSS capturando {capture_area}: {e}")
        messagebox.showerror("Error de Captura", f"No se pudo capturar la pantalla/región:\n{e}")
        return None
   except Exception as e:
       logging.error(f"Error inesperado en captura: {e}")
       messagebox.showerror("Error Inesperado", f"Error inesperado durante la captura:\n{e}")
       return None

def tk_select_region_base(root, image, window_title, rect_outline="green", button_text="Confirmar Selección"):
    # (Sin cambios respecto a la versión anterior que te di)
   if image is None:
        messagebox.showerror("Error Interno", "No se proporcionó imagen para la selección de región.")
        return None
   orig_height, orig_width = image.shape[:2]
   scale = 1.0
   max_display_width = root.winfo_screenwidth() * 0.85
   max_display_height = root.winfo_screenheight() * 0.85
   scale_w = max_display_width / orig_width if orig_width > max_display_width else 1.0
   scale_h = max_display_height / orig_height if orig_height > max_display_height else 1.0
   scale = min(scale_w, scale_h, 1.0)
   new_width = int(orig_width * scale)
   new_height = int(orig_height * scale)
   if new_width < 1 or new_height < 1:
        messagebox.showerror("Error de Imagen", "La imagen original o redimensionada tiene tamaño inválido.")
        return None
   try:
       interpolation = cv2.INTER_LANCZOS4 if scale < 1.0 else cv2.INTER_AREA
       resized_img = cv2.resize(image, (new_width, new_height), interpolation=interpolation)
   except Exception as e:
        logging.error(f"Error redimensionando imagen: {e}")
        messagebox.showerror("Error de Redimensionamiento", f"No se pudo redimensionar la imagen:\n{e}")
        return None
   try:
       img_rgb = cv2.cvtColor(resized_img, cv2.COLOR_BGR2RGB)
       pil_img = Image.fromarray(img_rgb)
       tk_img = ImageTk.PhotoImage(pil_img)
   except Exception as e:
       logging.error(f"Error convirtiendo imagen para Tkinter: {e}")
       messagebox.showerror("Error de Imagen", f"No se pudo convertir la imagen para mostrar:\n{e}")
       return None
   sel_win = tk.Toplevel(root)
   sel_win.title(window_title)
   sel_win.grab_set()
   min_w = max(400, tk_img.width() // 2)
   min_h = max(300, tk_img.height() // 2)
   sel_win.minsize(min_w, min_h)
   sel_win.geometry(f"+{root.winfo_x()+50}+{root.winfo_y()+50}")
   canvas = tk.Canvas(sel_win, width=tk_img.width(), height=tk_img.height(), cursor="cross")
   canvas.pack(padx=10, pady=10, fill="both", expand=True)
   img_on_canvas = canvas.create_image(0, 0, anchor="nw", image=tk_img)
   canvas.image = tk_img
   selection = {"x1": None, "y1": None, "x2": None, "y2": None}
   rect = None
   confirmed_region_coords = None
   def on_button_press(event):
       selection["x1"] = canvas.canvasx(event.x)
       selection["y1"] = canvas.canvasy(event.y)
       nonlocal rect
       if rect: canvas.delete(rect)
       rect = canvas.create_rectangle(selection["x1"], selection["y1"], selection["x1"], selection["y1"],
                                      outline=rect_outline, width=2, dash=(4, 2))
   def on_move_press(event):
       if rect and selection["x1"] is not None:
           cur_x = canvas.canvasx(event.x)
           cur_y = canvas.canvasy(event.y)
           canvas.coords(rect, selection["x1"], selection["y1"], cur_x, cur_y)
   def on_button_release(event):
       if rect and selection["x1"] is not None:
           selection["x2"] = canvas.canvasx(event.x)
           selection["y2"] = canvas.canvasy(event.y)
           x1_final = min(selection["x1"], selection["x2"])
           y1_final = min(selection["y1"], selection["y2"])
           x2_final = max(selection["x1"], selection["x2"])
           y2_final = max(selection["y1"], selection["y2"])
           selection["x1"], selection["y1"] = x1_final, y1_final
           selection["x2"], selection["y2"] = x2_final, y2_final
           canvas.coords(rect, x1_final, y1_final, x2_final, y2_final)
   canvas.bind("<ButtonPress-1>", on_button_press)
   canvas.bind("<B1-Motion>", on_move_press)
   canvas.bind("<ButtonRelease-1>", on_button_release)
   button_frame = ttk.Frame(sel_win)
   button_frame.pack(pady=10)
   def confirm_selection():
       nonlocal confirmed_region_coords
       if None not in (selection["x1"], selection["y1"], selection["x2"], selection["y2"]):
           left_r, top_r = selection["x1"], selection["y1"]
           width_r = selection["x2"] - selection["x1"]
           height_r = selection["y2"] - selection["y1"]
           left_orig = int((left_r / scale) + 0.5)
           top_orig = int((top_r / scale) + 0.5)
           width_orig = int((width_r / scale) + 0.5)
           height_orig = int((height_r / scale) + 0.5)
           width_orig = max(1, min(width_orig, orig_width - left_orig))
           height_orig = max(1, min(height_orig, orig_height - top_orig))
           left_orig = max(0, min(left_orig, orig_width - 1))
           top_orig = max(0, min(top_orig, orig_height - 1))
           if width_orig > 0 and height_orig > 0:
                confirmed_region_coords = {"left": left_orig, "top": top_orig, "width": width_orig, "height": height_orig}
                logging.info(f"Región seleccionada (original): {confirmed_region_coords}")
           else:
                logging.warning("Selección resultó en región inválida (ancho/alto <= 0)")
                messagebox.showwarning("Selección Inválida", "La región seleccionada es demasiado pequeña o inválida.")
       sel_win.destroy()
   def cancel_selection():
        sel_win.destroy()
   confirm_btn = ttk.Button(button_frame, text=button_text, command=confirm_selection)
   confirm_btn.pack(side="left", padx=5)
   cancel_btn = ttk.Button(button_frame, text="Cancelar", command=cancel_selection)
   cancel_btn.pack(side="left", padx=5)
   sel_win.bind("<Escape>", lambda e: cancel_selection())
   root.wait_window(sel_win)
   return confirmed_region_coords

def tk_select_ocr_region(root, image):
   """Llama a la función base para seleccionar región OCR."""
   return tk_select_region_base(root, image, "Seleccione Región OCR", rect_outline="green", button_text="Confirmar Selección OCR")

def tk_select_monitor_region(root, monitor_img, monitor_info):
   # (Sin cambios respecto a la versión anterior que te di)
   coords_relative_to_monitor_img = tk_select_region_base(
       root, monitor_img, "Seleccione Región del Monitor",
       rect_outline="blue", button_text="Confirmar Región Monitor"
   )
   if coords_relative_to_monitor_img:
       coords_absolute = coords_relative_to_monitor_img.copy()
       coords_absolute['left'] += monitor_info['left']
       coords_absolute['top'] += monitor_info['top']
       logging.info(f"Región seleccionada (absoluta): {coords_absolute}")
       return coords_absolute
   return None


class TemplateManagerGUI(tk.Tk):
   def __init__(self):
       super().__init__()
       self.title("Gestor de Zonas OCR y Plantillas")
       self.minsize(MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT)

       self.captured_image = None
       self.tk_img_preview = None
       self.selected_image_path = None
       self.ocr_regions = [] # Lista de dicts: {"region": {...}, "expected_text": [...]} para la imagen actual
       # self.ocr_region_rect_ids = [] # Ya no se usa, se dibuja en Pillow
       self.current_template_name = None
       self.template_names_mapping = {}
       self.ocr_regions_mapping = {}
       self.monitors_info = self.detect_monitors()

       self.setup_fonts_and_styles()
       self.preview_font = self._get_preview_font()

       self.create_widgets()

       self.load_template_names_from_json()
       self.load_ocr_regions_from_json()

       logging.info("Template Manager GUI inicializado.")

   def _get_preview_font(self):
        # (Sin cambios respecto a la versión anterior que te di)
        try: return ImageFont.truetype("consola.ttf", PREVIEW_NUMBER_FONT_SIZE)
        except IOError:
            try: return ImageFont.truetype("cour.ttf", PREVIEW_NUMBER_FONT_SIZE)
            except IOError:
                 logging.warning("Fuentes Consolas/Courier no encontradas, usando fuente por defecto para números OCR.")
                 try:
                     tk_default_font_info = self.default_font.actual()
                     return ImageFont.truetype(f"{tk_default_font_info['family'].lower()}.ttf", PREVIEW_NUMBER_FONT_SIZE)
                 except Exception: return ImageFont.load_default()

   def setup_fonts_and_styles(self):
        # (Sin cambios respecto a la versión anterior que te di)
       self.default_font = font.nametofont("TkDefaultFont")
       self.default_font.configure(size=DEFAULT_FONT_SIZE)
       style = ttk.Style(self)
       try:
            style.configure('.', font=self.default_font, padding=(3, 1))
            style.configure('TLabelframe.Label', font=(self.default_font.actual()['family'], DEFAULT_FONT_SIZE, 'bold'))
            style.configure('TButton', padding=(6, 3))
            style.configure('TEntry', padding=(5, 3))
            style.configure('TCombobox', padding=(5, 3))
            style.configure('Treeview.Heading', font=(self.default_font.actual()['family'], DEFAULT_FONT_SIZE, 'bold')) # Estilo para cabeceras Treeview
            style.configure('Treeview', rowheight=TREEVIEW_ROW_HEIGHT) # Ajustar altura fila Treeview
       except Exception as e: logging.warning(f"No se pudo configurar completamente el estilo ttk: {e}")
       self.option_add("*Font", self.default_font)

   def detect_monitors(self):
        # (Sin cambios respecto a la versión anterior que te di)
       try:
           with mss.mss() as sct:
               logging.info(f"Monitores detectados: {sct.monitors}")
               return sct.monitors
       except Exception as e:
           logging.error(f"Error detectando monitores: {e}")
           messagebox.showerror("Error de Hardware", f"No se pudieron detectar los monitores:\n{e}")
           return [{}]

   def load_ocr_regions_from_json(self):
        # (Sin cambios respecto a la versión anterior que te di)
       self.ocr_regions_mapping = load_ocr_data()
       logging.info(f"Cargadas {len(self.ocr_regions_mapping)} entradas de regiones OCR desde JSON.")

   def create_widgets(self):
        # (Sin cambios respecto a la versión anterior que te di)
       self.grid_rowconfigure(2, weight=1)
       self.grid_columnconfigure(0, weight=1)
       self.create_capture_frame()
       self.create_template_selection_frame()
       center_frame = ttk.Frame(self)
       center_frame.grid(row=2, column=0, padx=10, pady=10, sticky="nsew")
       center_frame.grid_rowconfigure(0, weight=1)
       center_frame.grid_columnconfigure(0, weight=1, minsize=MIN_CANVAS_WIDTH)
       center_frame.grid_columnconfigure(1, weight=0, minsize=300) # Darle tamaño mínimo a columna OCR
       self.create_preview_frame(center_frame)
       self.create_ocr_config_frame(center_frame) # Modificado para añadir Treeview
       self.create_status_label()

   def create_capture_frame(self):
        # (Sin cambios respecto a la versión anterior que te di)
       capture_frame = ttk.LabelFrame(self, text="Capturar Nueva Plantilla", padding=(10, 5))
       capture_frame.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="ew")
       capture_options_frame = ttk.Frame(capture_frame)
       capture_options_frame.pack(anchor="w", fill="x", padx=5, pady=2)
       self.capture_type_var = tk.StringVar(value="monitor")
       ttk.Radiobutton(capture_options_frame, text="Monitor Completo", variable=self.capture_type_var, value="monitor").pack(side="left", padx=(0, 10))
       ttk.Radiobutton(capture_options_frame, text="Región del Monitor", variable=self.capture_type_var, value="region").pack(side="left", padx=(0, 10))
       ttk.Label(capture_options_frame, text="Monitor:").pack(side="left", padx=(10, 5))
       self.monitor_var = tk.IntVar(value=1)
       num_monitors = len(self.monitors_info) - 1 if len(self.monitors_info) > 1 else 1
       self.monitor_spinbox = ttk.Spinbox(capture_options_frame, from_=1, to=max(1, num_monitors), textvariable=self.monitor_var, width=5, wrap=True)
       self.monitor_spinbox.pack(side="left", padx=5)
       ttk.Button(capture_options_frame, text="Capturar Pantalla", command=self.capture_new_template).pack(side="left", padx=(10, 5))
       name_frame = ttk.Frame(capture_frame)
       name_frame.pack(anchor="w", fill="x", padx=5, pady=5)
       ttk.Label(name_frame, text="Nombre Nueva Plantilla:").pack(side="left", padx=(0, 5))
       self.new_template_name_var = tk.StringVar()
       self.new_template_entry = ttk.Entry(name_frame, textvariable=self.new_template_name_var, width=30)
       self.new_template_entry.pack(side="left", padx=5, fill="x", expand=True)
       self.new_template_entry.bind("<Return>", lambda event: self.save_new_template())
       ttk.Button(name_frame, text="Guardar Nueva Plantilla", command=self.save_new_template).pack(side="left", padx=(10, 5))

   def create_template_selection_frame(self):
        # (Sin cambios respecto a la versión anterior que te di)
       template_frame = ttk.LabelFrame(self, text="Seleccionar Plantilla Existente", padding=(10, 5))
       template_frame.grid(row=1, column=0, padx=10, pady=5, sticky="ew")
       combo_frame = ttk.Frame(template_frame)
       combo_frame.pack(fill="x", padx=5, pady=5)
       ttk.Label(combo_frame, text="Plantilla:").pack(side="left", padx=(0, 5))
       self.template_name_var = tk.StringVar()
       self.template_name_combobox = ttk.Combobox(combo_frame, textvariable=self.template_name_var, width=40, state="readonly")
       self.template_name_combobox.pack(side="left", padx=5, fill="x", expand=True)
       self.template_name_combobox.bind("<<ComboboxSelected>>", self.on_template_name_selected)
       ttk.Button(combo_frame, text="Refrescar Lista", command=self.load_template_names_from_json).pack(side="left", padx=(10, 5))

   def create_preview_frame(self, parent_frame):
        # (Sin cambios respecto a la versión anterior que te di)
       preview_frame = ttk.LabelFrame(parent_frame, text="Previsualización", padding=(10, 5))
       preview_frame.grid(row=0, column=0, padx=(0, 5), pady=5, sticky="nsew")
       preview_frame.grid_rowconfigure(0, weight=1)
       preview_frame.grid_columnconfigure(0, weight=1)
       canvas_container = ttk.Frame(preview_frame)
       canvas_container.grid(row=0, column=0, sticky="nsew")
       canvas_container.grid_rowconfigure(0, weight=1)
       canvas_container.grid_columnconfigure(0, weight=1)
       self.preview_canvas = tk.Canvas(canvas_container, width=MIN_CANVAS_WIDTH, height=MIN_CANVAS_HEIGHT, bg="lightgrey", highlightthickness=1, highlightbackground="gray")
       self.preview_canvas.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")
       canvas_container.bind("<Configure>", self.on_preview_resize)

   def on_preview_resize(self, event=None):
        # (Sin cambios respecto a la versión anterior que te di)
       self.show_preview()

   def create_ocr_config_frame(self, parent_frame):
       """Crea el frame para la configuración de zonas OCR (Ahora con Treeview)."""
       config_frame = ttk.LabelFrame(parent_frame, text="Configuración OCR", padding=(10, 5))
       config_frame.grid(row=0, column=1, padx=(5, 0), pady=5, sticky="nswe") # Expandir en todas direcciones
       config_frame.grid_columnconfigure(0, weight=1) # Permitir expansión horizontal interna
       config_frame.grid_rowconfigure(4, weight=1) # Permitir que el Treeview se expanda verticalmente

       # --- Botón para Marcar Región ---
       mark_region_frame = ttk.Frame(config_frame)
       mark_region_frame.grid(row=0, column=0, pady=(0,5), sticky="ew") # Menos padding abajo
       self.mark_region_button = ttk.Button(mark_region_frame, text="Marcar Región OCR", command=self.mark_ocr_region, state="disabled")
       self.mark_region_button.pack(pady=2)

       # --- Entrada para Texto Esperado ---
       expected_text_frame = ttk.Frame(config_frame)
       expected_text_frame.grid(row=1, column=0, pady=(0,2), sticky="ew")
       expected_text_frame.grid_columnconfigure(0, weight=1)
       ttk.Label(expected_text_frame, text="Texto Esperado (antes de marcar, separa con '|'):").pack(anchor="w", padx=5)
       self.expected_text_var = tk.StringVar()
       self.expected_text_entry = ttk.Entry(expected_text_frame, textvariable=self.expected_text_var)
       self.expected_text_entry.pack(fill="x", padx=5, pady=(0, 5))
       self.expected_text_entry.bind("<Return>", lambda event: self.mark_ocr_region())

       # --- Label contador de zonas ---
       self.region_label = ttk.Label(config_frame, text="Zonas OCR: 0 definida(s)", anchor="center")
       self.region_label.grid(row=2, column=0, pady=3, sticky="ew")

       # --- Treeview para mostrar textos esperados ---
       tree_label = ttk.Label(config_frame, text="Textos Esperados Guardados:")
       tree_label.grid(row=3, column=0, padx=5, pady=(5, 0), sticky="w")

       tree_frame = ttk.Frame(config_frame) # Frame para Treeview y Scrollbar
       tree_frame.grid(row=4, column=0, padx=5, pady=5, sticky="nsew")
       tree_frame.grid_rowconfigure(0, weight=1)
       tree_frame.grid_columnconfigure(0, weight=1)

       self.ocr_tree = ttk.Treeview(tree_frame, columns=("#", "Textos"), show="headings", height=6)
       self.ocr_tree.heading("#", text="#", anchor="center")
       self.ocr_tree.column("#", width=40, anchor="center", stretch=tk.NO)
       self.ocr_tree.heading("Textos", text="Texto(s) Esperado(s)")
       self.ocr_tree.column("Textos", width=200, stretch=tk.YES) # Columna de texto expandible
       self.ocr_tree.grid(row=0, column=0, sticky="nsew")

       ocr_scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.ocr_tree.yview)
       ocr_scrollbar.grid(row=0, column=1, sticky="ns")
       self.ocr_tree['yscrollcommand'] = ocr_scrollbar.set

       # --- Botones de Acción OCR ---
       action_frame = ttk.Frame(config_frame)
       action_frame.grid(row=5, column=0, pady=(5, 0), sticky="ew") # Pegado al Treeview
       self.clear_regions_button = ttk.Button(action_frame, text="Limpiar Zonas Marcadas", command=self.clear_ocr_regions, state="disabled")
       self.clear_regions_button.pack(side="left", padx=(5, 10), pady=5, expand=True)
       self.save_ocr_button = ttk.Button(action_frame, text="Guardar Zonas OCR", command=self.save_ocr_regions, state="disabled")
       self.save_ocr_button.pack(side="left", padx=10, pady=5, expand=True)

   def create_status_label(self):
        # (Sin cambios respecto a la versión anterior que te di)
       self.status_label_var = tk.StringVar(value="Listo.")
       status_frame = ttk.Frame(self, height=25)
       status_frame.grid(row=3, column=0, padx=10, pady=(5, 10), sticky="ew")
       status_frame.pack_propagate(False)
       status_label = ttk.Label(status_frame, textvariable=self.status_label_var, anchor="w")
       status_label.pack(side="left", padx=5, pady=2)

   def load_template_names_from_json(self):
        # (Sin cambios respecto a la versión anterior que te di)
       self.status_message("Cargando lista de plantillas...")
       try:
           mapping = load_template_data()
           self.template_names_mapping = mapping
           template_names = sorted(list(self.template_names_mapping.keys()))
           self.template_name_combobox['values'] = template_names
           if not template_names:
                self.template_name_var.set("")
                messagebox.showinfo("Sin Plantillas", "No se encontraron plantillas en el archivo de configuración.")
           self.status_message(f"Lista de plantillas refrescada ({len(template_names)} encontrada(s)). Seleccione una.")
           logging.info(f"Cargados {len(template_names)} nombres de plantillas en el Combobox.")
       except Exception as e:
           logging.error(f"Error inesperado al cargar nombres de plantillas: {e}")
           messagebox.showerror("Error Crítico", f"Error al cargar nombres de plantillas: {e}")
           self.status_message("Error al cargar lista de plantillas.")

   def on_template_name_selected(self, event=None):
       """Se llama al seleccionar plantilla. Carga imagen y datos OCR asociados."""
       selected_name = self.template_name_var.get()
       if not selected_name: return

       self.current_template_name = selected_name
       self.status_message(f"Cargando plantilla '{selected_name}'...")
       self.clear_ocr_regions() # Limpia regiones y Treeview de la sesión anterior

       image_files = self.template_names_mapping.get(selected_name, [])
       self.captured_image = None
       self.selected_image_path = None

       # --- Lógica de carga de imagen (sin cambios) ---
       if image_files:
           first_image_file = image_files[0]
           image_path = os.path.join(IMAGES_DIR, first_image_file)
           logging.info(f"Intentando cargar imagen: {image_path} para plantilla '{selected_name}'")
           if os.path.exists(image_path):
               try:
                   img_temp = cv2.imread(image_path)
                   if img_temp is None:
                       try:
                           pil_img = Image.open(image_path)
                           img_temp = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
                           if img_temp is None: raise Exception("Pillow también falló.")
                           logging.warning(f"OpenCV falló, pero Pillow leyó '{first_image_file}'.")
                       except Exception as pil_e:
                            raise Exception(f"OpenCV y Pillow fallaron. Pillow error: {pil_e}")
                   self.selected_image_path = image_path
                   self.captured_image = img_temp
                   logging.info(f"Imagen '{first_image_file}' cargada para '{selected_name}'.")
               except Exception as e:
                   logging.error(f"Error crítico al cargar imagen '{first_image_file}' para '{selected_name}': {e}")
                   messagebox.showerror("Error Carga Imagen", f"No se pudo cargar/procesar:\n{first_image_file}\nError: {e}")
           else:
               logging.warning(f"Archivo '{first_image_file}' no encontrado en {IMAGES_DIR}.")
               messagebox.showwarning("Archivo Faltante", f"No se encontró imagen:\n{first_image_file}\nAsociada a '{selected_name}'.")
       else:
            logging.warning(f"No hay archivos de imagen listados para '{selected_name}'.")
            messagebox.showwarning("Sin Imágenes Asociadas", f"Plantilla '{selected_name}' sin imágenes asociadas.")

       # --- Habilitar/Deshabilitar botones OCR ---
       can_mark = self.captured_image is not None
       self.mark_region_button.config(state="normal" if can_mark else "disabled")
       # Botones Limpiar/Guardar se habilitan si hay regiones *Y* se puede marcar
       self.clear_regions_button.config(state="disabled") # Se habilita si hay regiones
       self.save_ocr_button.config(state="disabled") # Se habilita si hay regiones

       # --- Cargar y mostrar regiones OCR existentes ---
       self.ocr_regions = [] # Empezar con lista vacía para este estado
       if selected_name in self.ocr_regions_mapping:
           loaded_regions = self.ocr_regions_mapping[selected_name]
           if isinstance(loaded_regions, list):
               valid_regions = []
               for r in loaded_regions:
                   if isinstance(r, dict) and 'region' in r and isinstance(r['region'], dict) and all(k in r['region'] for k in ('left', 'top', 'width', 'height')):
                       r['expected_text'] = r.get('expected_text', [])
                       if not isinstance(r['expected_text'], list):
                           logging.warning(f"Corrigiendo 'expected_text' inválido para '{selected_name}'.")
                           r['expected_text'] = []
                       valid_regions.append(r)
                   else:
                       logging.warning(f"Eliminada región OCR mal formada para '{selected_name}': {r}")
               self.ocr_regions = valid_regions
           else:
                logging.warning(f"Datos OCR para '{selected_name}' no son lista. Ignorando.")
           message_ocr = f"{len(self.ocr_regions)} zona(s) OCR cargada(s)."
       else:
           message_ocr = "No hay zonas OCR predefinidas."

       self.status_message(f"'{selected_name}' seleccionado. {message_ocr}")
       self._populate_ocr_treeview() # Llenar el Treeview con las regiones cargadas
       self.update_region_label()
       self.show_preview() # Actualizar previsualización (dibuja regiones cargadas)
       # Habilitar botones si hay regiones cargadas
       if self.ocr_regions:
           self.clear_regions_button.config(state="normal")
           self.save_ocr_button.config(state="normal")


   def _populate_ocr_treeview(self):
        """Limpia y rellena el Treeview con las regiones OCR actuales."""
        # Limpiar contenido anterior
        for item in self.ocr_tree.get_children():
            self.ocr_tree.delete(item)
        # Rellenar con las regiones actuales en memoria (self.ocr_regions)
        for i, region_data in enumerate(self.ocr_regions):
            region_index = i + 1
            expected_texts = region_data.get('expected_text', [])
            # Unir la lista con '|' para mostrarla en la columna
            text_display = "|".join(expected_texts) if expected_texts else ""
            self.ocr_tree.insert("", tk.END, values=(region_index, text_display))


   def capture_new_template(self):
        # (Sin cambios respecto a la versión anterior que te di)
       capture_type = self.capture_type_var.get()
       try: monitor_idx = self.monitor_var.get()
       except tk.TclError: messagebox.showerror("Error", "Valor de monitor inválido."); return
       if monitor_idx < 1 or monitor_idx >= len(self.monitors_info):
           messagebox.showerror("Error de Monitor", f"Monitor {monitor_idx} no válido."); return
       target_monitor_info = self.monitors_info[monitor_idx]
       self.withdraw(); self.update_idletasks(); time.sleep(0.4)
       logging.info(f"Iniciando captura tipo '{capture_type}' en monitor {monitor_idx}...")
       captured_img = None
       try:
            if capture_type == "monitor": captured_img = capture_screen(monitor=monitor_idx)
            elif capture_type == "region":
                 monitor_image = capture_screen(monitor=monitor_idx)
                 if monitor_image is not None:
                      self.deiconify(); self.update()
                      region_absolute = tk_select_monitor_region(self, monitor_image, target_monitor_info)
                      if region_absolute:
                          self.withdraw(); self.update_idletasks(); time.sleep(0.2)
                          captured_img = capture_screen(region=region_absolute, monitor=monitor_idx)
                      else: logging.info("Selección de región cancelada.")
                 else: logging.error("No se pudo capturar imagen del monitor.")
       finally:
           if self.state() == 'withdrawn': self.deiconify()
           self.status_message("Proceso de captura finalizado.")
       if captured_img is not None:
           self.captured_image = captured_img
           self.selected_image_path = None
           self.template_name_var.set("")
           self.current_template_name = None
           self.clear_ocr_regions() # Limpia lista y Treeview
           self.show_preview()
           self.status_message("Pantalla capturada. Introduce nombre y guarda.")
           self.mark_region_button.config(state="normal")
           self.clear_regions_button.config(state="disabled") # No hay regiones aún
           self.save_ocr_button.config(state="disabled")
           self.new_template_entry.focus_set()
       else: self.status_message("Captura cancelada o fallida.")

   def save_new_template(self):
        # (Sin cambios respecto a la versión anterior que te di, incluye la pregunta para guardar OCR)
       if self.captured_image is None: messagebox.showerror("Error", "No hay imagen capturada."); return
       template_name = self.new_template_name_var.get().strip()
       if not template_name: messagebox.showerror("Error", "Introduce nombre."); return
       if not re.match(r'^[a-zA-Z0-9_.-]+$', template_name): messagebox.showerror("Error", "Nombre inválido."); return
       timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
       safe_filename_base = re.sub(r'[^\w.-]', '_', template_name)
       image_filename = f"{safe_filename_base}_{timestamp}.png"
       image_path = os.path.join(IMAGES_DIR, image_filename)
       logging.info(f"Guardando plantilla '{template_name}' como '{image_filename}'")
       try:
           os.makedirs(IMAGES_DIR, exist_ok=True)
           success = cv2.imwrite(image_path, self.captured_image)
           if not success: raise Exception("cv2.imwrite falló.")
           logging.info(f"Imagen guardada: '{image_filename}'.")
           mapping = load_template_data()
           if template_name in mapping:
               if isinstance(mapping[template_name], list):
                   if image_filename not in mapping[template_name]: mapping[template_name].append(image_filename)
               else: mapping[template_name] = [mapping[template_name], image_filename]
           else: mapping[template_name] = [image_filename]
           if save_template_data(mapping):
               self.status_message(f"Plantilla '{template_name}' guardada.")
               self.template_names_mapping = mapping
               self.load_template_names_from_json()
               self.template_name_var.set(template_name)
               self.current_template_name = template_name
               if self.ocr_regions:
                    num_regions = len(self.ocr_regions)
                    if messagebox.askyesno("Guardar Regiones OCR",
                                           f"Hay {num_regions} region(es) OCR marcadas.\n"
                                           f"¿Guardarlas para la nueva plantilla '{template_name}'?"):
                         self.save_ocr_regions(force_template_name=template_name)
                    else: logging.info("Usuario no guardó regiones OCR con nueva plantilla.")
               self.new_template_name_var.set("")
           else: self.status_message(f"Error guardando mapeo de plantillas.")
       except Exception as e:
           logging.error(f"Error guardando plantilla '{template_name}': {e}", exc_info=True)
           messagebox.showerror("Error Crítico al Guardar", f"No se pudo guardar plantilla '{template_name}':\n{e}")
           self.status_message(f"Error al guardar plantilla '{template_name}'.")

   def show_preview(self):
        # (Sin cambios respecto a la versión anterior que te di, dibuja números)
        try:
            canvas_width = self.preview_canvas.winfo_width()
            canvas_height = self.preview_canvas.winfo_height()
        except tk.TclError:
            canvas_width, canvas_height = MIN_CANVAS_WIDTH, MIN_CANVAS_HEIGHT
            logging.warning("TclError obteniendo tamaño canvas.")
        canvas_width = max(canvas_width, MIN_CANVAS_WIDTH)
        canvas_height = max(canvas_height, MIN_CANVAS_HEIGHT)
        self.preview_canvas.delete("all")
        # self.ocr_region_rect_ids = [] # Ya no se usa

        if self.captured_image is None:
            self.preview_canvas.config(width=canvas_width, height=canvas_height)
            self.preview_canvas.create_text(canvas_width / 2, canvas_height / 2, text="Carga o Captura una Imagen", fill="darkgrey", font=self.default_font, anchor="center", justify="center", width=canvas_width*0.8)
            self.tk_img_preview = None
            return
        try:
            img_rgb = cv2.cvtColor(self.captured_image, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(img_rgb)
            img_aspect = pil_img.width / pil_img.height
            canvas_aspect = canvas_width / canvas_height
            if img_aspect > canvas_aspect: new_width = canvas_width; new_height = int(new_width / img_aspect)
            else: new_height = canvas_height; new_width = int(new_height * img_aspect)
            new_width = max(1, new_width); new_height = max(1, new_height)
            try: resample_method = Image.Resampling.LANCZOS
            except AttributeError: resample_method = Image.ANTIALIAS
            pil_img_resized = pil_img.resize((new_width, new_height), resample_method)
            draw = ImageDraw.Draw(pil_img_resized)
            scale_x = new_width / self.captured_image.shape[1]
            scale_y = new_height / self.captured_image.shape[0]
            for i, region_data in enumerate(self.ocr_regions):
                 try:
                     region = region_data['region']
                     x1_r = int(region['left'] * scale_x)
                     y1_r = int(region['top'] * scale_y)
                     x2_r = int((region['left'] + region['width']) * scale_x)
                     y2_r = int((region['top'] + region['height']) * scale_y)
                     outline_color = "purple" if region_data.get('expected_text') else "red"
                     draw.rectangle([x1_r, y1_r, x2_r, y2_r], outline=outline_color, width=2)
                     text_num = str(i + 1)
                     text_pos_x = x1_r + 3; text_pos_y = y1_r + 1
                     try: bbox = self.preview_font.getbbox(text_num)
                     except AttributeError: bbox = self.preview_font.getmask(text_num).getbbox() # Fallback older Pillow
                     text_width = bbox[2] - bbox[0]
                     text_height = bbox[3] - bbox[1]
                     draw.rectangle([text_pos_x - 2, text_pos_y -1, text_pos_x + text_width + 2, text_pos_y + text_height + 1], fill="white")
                     draw.text((text_pos_x, text_pos_y), text_num, fill=outline_color, font=self.preview_font)
                 except Exception as e: logging.error(f"Error dibujando región OCR {i}: {e}", exc_info=True)
            self.tk_img_preview = ImageTk.PhotoImage(pil_img_resized)
            x_offset = (canvas_width - new_width) // 2
            y_offset = (canvas_height - new_height) // 2
            self.preview_canvas.create_image(x_offset, y_offset, anchor="nw", image=self.tk_img_preview)
            self.preview_canvas.image = self.tk_img_preview
            self.preview_canvas.config(width=canvas_width, height=canvas_height)
        except Exception as e:
            logging.error(f"Error fatal durante show_preview: {e}", exc_info=True)
            self.preview_canvas.create_text(canvas_width / 2, canvas_height / 2, text=f"Error al mostrar previsualización:\n{e}", fill="red", font=self.default_font, anchor="center", justify="center", width=canvas_width*0.8)
            self.tk_img_preview = None

   def mark_ocr_region(self):
       """Marca región OCR, la asocia con texto esperado (si hay) y actualiza UI."""
       if self.captured_image is None:
            messagebox.showerror("Error", "Carga o captura una imagen primero.")
            return

       # Leer el texto ANTES de abrir la ventana de selección
       expected_text_str = self.expected_text_var.get().strip()
       expected_texts = [txt.strip() for txt in expected_text_str.split('|') if txt.strip()]

       logging.info(f"Solicitando selección OCR. Texto esperado a asociar: {expected_texts}")
       self.status_message("Selecciona la región OCR en la nueva ventana...")
       self.withdraw()
       region_coords = tk_select_ocr_region(self, self.captured_image)
       self.deiconify()

       if region_coords:
           new_region_data = {"region": region_coords, "expected_text": expected_texts}
           self.ocr_regions.append(new_region_data)
           region_index = len(self.ocr_regions)
           logging.info(f"Nueva región OCR {region_index} añadida: {new_region_data}")

           # Limpiar el campo de texto esperado DESPUÉS de usarlo
           self.expected_text_var.set("")

           # Actualizar UI
           self.update_region_label()
           self._populate_ocr_treeview() # Añadir al Treeview
           self.show_preview() # Redibujar preview

           # Habilitar botones de limpiar/guardar
           self.clear_regions_button.config(state="normal")
           if self.current_template_name: # Habilitar guardar solo si hay plantilla seleccionada
                self.save_ocr_button.config(state="normal")

           # Mensaje de estado más informativo
           status_msg = f"Región OCR {region_index} añadida"
           if expected_texts:
               status_msg += f" con texto esperado: {expected_texts}."
           else:
               status_msg += " (sin texto esperado asociado)."
           status_msg += " Marca más o guarda."
           self.status_message(status_msg)
       else:
           logging.info("Selección de región OCR cancelada.")
           messagebox.showinfo("Cancelado", "No se seleccionó ninguna región OCR.")
           self.status_message("Selección de región OCR cancelada.")


   def update_region_label(self):
        # (Sin cambios)
       count = len(self.ocr_regions)
       self.region_label.config(text=f"Zonas OCR: {count} definida(s)")


   def clear_ocr_regions(self):
       """Limpia lista de regiones OCR, previsualización, label y Treeview."""
       if not self.ocr_regions: return
       if messagebox.askyesno("Confirmar Limpieza", "¿Eliminar TODAS las regiones OCR marcadas actualmente para esta imagen?"):
            logging.info("Limpiando regiones OCR de la sesión actual.")
            self.ocr_regions = []
            self.update_region_label()
            self._populate_ocr_treeview() # Limpiar Treeview también
            self.show_preview()
            self.save_ocr_button.config(state="disabled")
            self.clear_regions_button.config(state="disabled") # Ya no hay nada que limpiar
            self.status_message("Regiones OCR marcadas eliminadas.")
       else:
            self.status_message("Limpieza de regiones cancelada.")


   def save_ocr_regions(self, force_template_name=None):
       # (Sin cambios respecto a la versión anterior que te di)
       template_name = force_template_name if force_template_name else self.template_name_var.get().strip()
       if not template_name:
            messagebox.showerror("Error", "No hay plantilla seleccionada para asociar las regiones OCR.")
            return
       if not self.ocr_regions:
           if messagebox.askyesno("Confirmar Borrado",
                                  f"No hay zonas OCR marcadas.\n"
                                  f"¿ELIMINAR TODAS las zonas OCR existentes para '{template_name}' del archivo JSON?"):
                logging.info(f"Confirmada eliminación de regiones OCR para '{template_name}'.")
           else:
                self.status_message("Guardado cancelado."); return
       mapping = load_ocr_data()
       mapping[template_name] = self.ocr_regions
       logging.info(f"Guardando {len(self.ocr_regions)} regiones OCR para '{template_name}'. JSON: {json.dumps(self.ocr_regions)}") # Log más detallado
       if save_ocr_data(mapping):
           self.ocr_regions_mapping = mapping
           messagebox.showinfo("Éxito", f"Zonas OCR guardadas para '{template_name}'.")
           self.status_message(f"Zonas OCR guardadas para '{template_name}'.")
           # El botón Guardar debería seguir habilitado si hay regiones y plantilla
           self.save_ocr_button.config(state="normal" if self.ocr_regions and self.current_template_name else "disabled")
       else:
           self.status_message(f"Error al guardar zonas OCR para '{template_name}'.")


   def status_message(self, message):
        # (Sin cambios respecto a la versión anterior que te di)
       logging.info(f"Status: {message}")
       self.status_label_var.set(message)
       self.update_idletasks()


if __name__ == "__main__":
    # (Sin cambios respecto a la versión anterior que te di)
   if not os.path.exists(IMAGES_DIR): os.makedirs(IMAGES_DIR)
   if not os.path.exists(CONFIG_DIR): os.makedirs(CONFIG_DIR)
   if not os.path.exists(os.path.dirname(log_file_path)): os.makedirs(os.path.dirname(log_file_path))
   app = TemplateManagerGUI()
   app.mainloop()

# --- END OF FILE template_manager_gui ---