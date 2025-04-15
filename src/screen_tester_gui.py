# --- START OF FILE screen_tester_gui ---
import datetime
import json
import logging
import os
import subprocess
import sys
import time
import tkinter as tk
from tkinter import font
from tkinter import ttk, messagebox, simpledialog  # Añadido simpledialog

# Importar CV2 solo si es estrictamente necesario aquí (para tk_select_roi)
# Si tk_select_roi solo usa PIL/ImageTk, no es necesario. Parece que usa cv2.cvtColor.
import cv2
from PIL import Image, ImageTk  # Solo para tk_select_roi si se mantiene aquí

# --- Importar lo necesario desde screen_recognizer ---
from screen_recognizer import (
    ScreenRecognizer,
    save_json_mapping,
    load_json_mapping,
    OCR_MAPPING_FILE,
    STATE_ROIS_FILE,
    DEFAULT_FONT_SIZE,
    PROJECT_DIR,
    IMAGES_DIR,
    CONFIG_DIR
)

# --- Definir constantes locales ---
# DEFAULT_FONT_SIZE = 11 # Usar el importado
MIN_WINDOW_WIDTH = 850
MIN_WINDOW_HEIGHT = 750
MIN_CANVAS_WIDTH = 300 # No hay canvas aquí, pero mantenido por si acaso
MIN_CANVAS_HEIGHT = 200
LOG_FILE_TESTER = os.path.join(PROJECT_DIR, "logs", "tester_log.log") # Guardar en subcarpeta logs
os.makedirs(os.path.dirname(LOG_FILE_TESTER), exist_ok=True)

CONFIDENCE_COLOR_DEFAULT = "lime"
CONFIDENCE_COLOR_ERROR = "red"

# --- Configuración del Logging ---
# Configuración principal (igual que antes, pero con la nueva ruta)
logging.basicConfig(
   level=logging.INFO,
   format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
   handlers=[
       logging.FileHandler(LOG_FILE_TESTER, encoding='utf-8'),
       logging.StreamHandler()
   ]
)

# Ruta al script de la GUI de gestión de plantillas
TEMPLATE_MANAGER_SCRIPT_PATH = os.path.join(PROJECT_DIR, "src", "template_manager_gui.py")


# --- Clase para el Diálogo de Selección de Estado (para ROI) ---
class SelectStateDialog(simpledialog.Dialog):
    """Diálogo personalizado para seleccionar un estado de una lista."""
    def __init__(self, parent, title, prompt, states_list):
        self.prompt = prompt
        self.states = states_list
        self.result = None
        super().__init__(parent, title)

    def body(self, master):
        ttk.Label(master, text=self.prompt, justify=tk.LEFT).pack(pady=5)
        self.combo_var = tk.StringVar()
        self.combobox = ttk.Combobox(master, textvariable=self.combo_var, values=self.states, width=40, state="readonly")
        if self.states:
            self.combobox.current(0) # Seleccionar el primero por defecto
        self.combobox.pack(pady=5, padx=10)
        return self.combobox # Establecer foco inicial

    def apply(self):
        self.result = self.combo_var.get()


# --- Función tk_select_roi (Modificada para usar recognizer.capture_screen) ---
def tk_select_roi(root, recognizer_instance, state_name):
   """
   Permite al usuario seleccionar una Región de Interés (ROI) para un estado.
   Usa la instancia del recognizer para capturar la pantalla y obtener info del monitor.
   Devuelve las coordenadas ROI absolutas de pantalla.
   """
   logging.info(f"Solicitando captura de pantalla completa para definir ROI de '{state_name}'")
   # Usar el método capture_screen del recognizer para asegurar que usa el monitor correcto
   # Pasar None como región para capturar el monitor completo configurado en recognizer
   full_screen_image = recognizer_instance.capture_screen(region=None)
   if full_screen_image is None:
       messagebox.showerror("Error de Captura", "No se pudo capturar la pantalla completa para definir ROI.")
       return None

   # Obtener información del monitor DESDE la instancia del recognizer
   monitor_info = recognizer_instance._get_monitor_region()
   if not monitor_info:
       logging.error("No se pudo obtener información del monitor desde recognizer para calcular ROI absoluto.")
       messagebox.showerror("Error Interno", "No se pudo obtener información del monitor para calcular el ROI.")
       return None

   orig_height, orig_width = full_screen_image.shape[:2]

   # --- Lógica de redimensionamiento para mostrar (similar a template_manager) ---
   scale = 1.0
   max_display_width = root.winfo_screenwidth() * 0.85
   max_display_height = root.winfo_screenheight() * 0.85
   scale_w = max_display_width / orig_width if orig_width > max_display_width else 1.0
   scale_h = max_display_height / orig_height if orig_height > max_display_height else 1.0
   scale = min(scale_w, scale_h, 1.0) # No escalar más grande que 1.0

   new_width = int(orig_width * scale)
   new_height = int(orig_height * scale)

   if new_width < 1 or new_height < 1:
       messagebox.showerror("Error de Imagen", "La imagen capturada tiene tamaño inválido después de redimensionar.")
       return None

   try: # Usar LANCZOS si está disponible y se reduce tamaño
       interpolation = cv2.INTER_LANCZOS4 if scale < 1.0 and hasattr(cv2, 'INTER_LANCZOS4') else cv2.INTER_AREA
       resized_img = cv2.resize(full_screen_image, (new_width, new_height), interpolation=interpolation)
   except Exception as e:
       logging.error(f"Error redimensionando imagen para ROI: {e}")
       messagebox.showerror("Error de Redimensionamiento", f"No se pudo redimensionar la imagen capturada:\n{e}")
       return None

   # --- Ventana Toplevel, Canvas, Selección (adaptada de tk_select_region_base) ---
   try:
        img_rgb = cv2.cvtColor(resized_img, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(img_rgb)
        tk_img = ImageTk.PhotoImage(pil_img)
   except Exception as e:
       logging.error(f"Error convirtiendo imagen ROI para Tkinter: {e}")
       messagebox.showerror("Error de Imagen", f"No se pudo convertir la imagen capturada para mostrar:\n{e}")
       return None

   sel_win = tk.Toplevel(root)
   sel_win.title(f"Seleccione ROI para Estado: '{state_name}'")
   sel_win.grab_set()
   # Ajustar geometría y posición
   win_w, win_h = tk_img.width() + 40, tk_img.height() + 90 # Más margen
   sel_win.geometry(f"{win_w}x{win_h}+{root.winfo_x()+60}+{root.winfo_y()+60}")
   sel_win.minsize(max(400, win_w//2), max(300, win_h//2))

   canvas = tk.Canvas(sel_win, width=tk_img.width(), height=tk_img.height(), cursor="cross", bg="black")
   canvas.pack(padx=10, pady=10, fill="both", expand=True)
   canvas.create_image(0, 0, anchor="nw", image=tk_img)
   canvas.image = tk_img # Guardar referencia

   selection = {"x1": None, "y1": None, "x2": None, "y2": None}
   rect = None
   confirmed_roi_absolute = None # Almacenará el ROI absoluto final

   def on_button_press(event):
       selection["x1"] = canvas.canvasx(event.x)
       selection["y1"] = canvas.canvasy(event.y)
       nonlocal rect
       if rect: canvas.delete(rect)
       rect = canvas.create_rectangle(selection["x1"], selection["y1"], selection["x1"], selection["y1"],
                                      outline="cyan", width=3, dash=(5, 3)) # Color diferente para ROI
   def on_move_press(event):
       if rect and selection["x1"] is not None:
            cur_x = canvas.canvasx(event.x)
            cur_y = canvas.canvasy(event.y)
            canvas.coords(rect, selection["x1"], selection["y1"], cur_x, cur_y)
   def on_button_release(event):
       if rect and selection["x1"] is not None:
            selection["x2"] = canvas.canvasx(event.x)
            selection["y2"] = canvas.canvasy(event.y)
            # Normalizar coords (x1,y1 arriba-izq, x2,y2 abajo-der)
            x1, y1 = min(selection["x1"], selection["x2"]), min(selection["y1"], selection["y2"])
            x2, y2 = max(selection["x1"], selection["x2"]), max(selection["y1"], selection["y2"])
            selection["x1"], selection["y1"] = x1, y1
            selection["x2"], selection["y2"] = x2, y2
            canvas.coords(rect, x1, y1, x2, y2) # Actualizar visual

   canvas.bind("<ButtonPress-1>", on_button_press)
   canvas.bind("<B1-Motion>", on_move_press)
   canvas.bind("<ButtonRelease-1>", on_button_release)

   button_frame = ttk.Frame(sel_win)
   button_frame.pack(pady=10)

   def confirm_selection():
       nonlocal confirmed_roi_absolute
       if None not in (selection["x1"], selection["y1"], selection["x2"], selection["y2"]):
           # Coords relativas a la imagen redimensionada (canvas)
           left_r, top_r = selection["x1"], selection["y1"]
           width_r = selection["x2"] - left_r
           height_r = selection["y2"] - top_r

           # Convertir a coords relativas a la imagen ORIGINAL (pantalla completa capturada)
           left_orig = int((left_r / scale) + 0.5)
           top_orig = int((top_r / scale) + 0.5)
           width_orig = int((width_r / scale) + 0.5)
           height_orig = int((height_r / scale) + 0.5)

           # Asegurar ancho/alto mínimo 1 y dentro de límites de la captura original
           width_orig = max(1, min(width_orig, orig_width - left_orig))
           height_orig = max(1, min(height_orig, orig_height - top_orig))
           left_orig = max(0, min(left_orig, orig_width - 1))
           top_orig = max(0, min(top_orig, orig_height - 1))

           if width_orig > 0 and height_orig > 0:
               # Convertir a coordenadas ABSOLUTAS de pantalla sumando offset del monitor
               left_abs = monitor_info['left'] + left_orig
               top_abs = monitor_info['top'] + top_orig
               # Width y Height son dimensiones, no necesitan offset
               confirmed_roi_absolute = {"left": left_abs, "top": top_abs, "width": width_orig, "height": height_orig}
               logging.info(f"ROI seleccionado (Absoluto): {confirmed_roi_absolute}")
           else:
                logging.warning("Selección de ROI resultó en región inválida.")
                messagebox.showwarning("Selección Inválida", "La región ROI seleccionada es inválida (ancho/alto <= 0).")
       else:
            logging.warning("Intento de confirmar ROI sin selección completa.")
            messagebox.showwarning("Sin Selección", "No se ha completado la selección del rectángulo ROI.")

       sel_win.destroy()

   def cancel_selection():
        logging.info("Selección de ROI cancelada por el usuario.")
        sel_win.destroy()

   confirm_btn = ttk.Button(button_frame, text="Guardar ROI", command=confirm_selection)
   confirm_btn.pack(side="left", padx=5)
   cancel_btn = ttk.Button(button_frame, text="Cancelar", command=cancel_selection)
   cancel_btn.pack(side="left", padx=5)
   sel_win.bind("<Escape>", lambda e: cancel_selection()) # Cancelar con Escape

   root.wait_window(sel_win) # Esperar cierre
   return confirmed_roi_absolute


class ScreenTesterGUI(tk.Tk):
   def __init__(self):
       super().__init__()
       self.title("Tester Interactivo - Screen Recognizer")
       self.configure(background="#333333")  # Color de fondo oscuro
       self.minsize(MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT)

       # No necesita ocr_regions aquí, usa las del recognizer indirectamente
       # self.ocr_regions = []

       self.current_template_name = None # Usado internamente al corregir/definir ROI
       self.last_recognition_result = None # Almacena el resultado completo del último test
       self.preview_canvas = None # Canvas para dibujar en la imagen de preview

       # Inicializar el Recognizer (podría hacerse configurable)
       self.recognizer = ScreenRecognizer(monitor=1, threshold=0.75, ocr_fallback_threshold=0.65)
       self.monitors_info = self.recognizer.monitors_info # Obtener de la instancia

       # Configurar fuentes y estilos
       self.setup_fonts_and_styles()
       # Crear widgets
       self.create_widgets()
       # Poblar combobox de corrección después de crear widgets
       self._populate_correction_combobox()
       logging.info("Tester GUI inicializado.")


   def setup_fonts_and_styles(self):
       """Configura la fuente y los estilos ttk."""
       self.default_font = font.nametofont("TkDefaultFont")
       self.default_font.configure(size=DEFAULT_FONT_SIZE)
       style = ttk.Style(self)
       style.configure('.', font=self.default_font, padding=(3, 1))
       style.configure('TLabelframe.Label', font=(self.default_font.actual()['family'], DEFAULT_FONT_SIZE, 'bold'))
       # Estilos específicos para botones y etiquetas de resultado
       style.configure("Result.TLabel", font=(self.default_font.actual()['family'], DEFAULT_FONT_SIZE + 1, 'bold'),background="#333333")
       style.configure("Confirm.TButton", foreground="green", font=self.default_font)
       style.configure("Deny.TButton", foreground="red", font=self.default_font)
       style.configure("Action.TButton", padding=(5, 3)) # Padding estándar para otros botones
       style.configure("Treeview.Heading", font=(self.default_font.actual()['family'], DEFAULT_FONT_SIZE, 'bold'))
       style.configure("TCheckbutton", background="#333333")
       style.configure("TFrame", background="#333333")
       style.configure("TLabel", background="#333333", foreground='white')
       style.configure("TLabelframe", background="#333333", foreground='white')


   def create_widgets(self):
       """Crea todos los widgets de la interfaz."""
       self.grid_rowconfigure(4, weight=1) # Fila OCR/Corrección se expande
       self.grid_columnconfigure(0, weight=1)
       self.create_preview_frame()
       self.create_control_frame()
       self.create_result_frame()
       self.create_correction_frame() # Se crea pero no se muestra inicialmente
       self.create_ocr_details_frame() # Se crea pero no se muestra inicialmente
       self.create_status_label()


   def create_preview_frame(self):
       """Crea el frame que contiene el Canvas para dibujar el preview."""
       self.preview_frame = ttk.LabelFrame(self, text="Preview Captura", padding=(10, 5))
       self.preview_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
       self.preview_frame.grid_columnconfigure(0, weight=1)
       self.preview_frame.grid_rowconfigure(0, weight=1)
       self.preview_canvas = tk.Canvas(self.preview_frame, bg="gray", highlightthickness=0)
       self.preview_canvas.grid(row=0, column=0, padx=0, pady=0, sticky="nsew")


   def create_control_frame(self):
       self.ocr_threshold = tk.DoubleVar(value=0.65)
       self.template_threshold = tk.DoubleVar(value=0.75)
       self.debug_log_var = tk.BooleanVar(value=False)

       """Crea el frame con los botones de control principales."""
       control_frame = ttk.LabelFrame(self, text="Control", padding=(10, 5))
       control_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
       # Centrar botones usando pack dentro de un frame interno
       button_container = ttk.Frame(control_frame)
       button_container.pack(pady=5)

       self.test_button = ttk.Button(button_container, text="Reconocer Pantalla Actual", command=self.run_test, style="Action.TButton")
       self.test_button.pack(side="left", padx=10)
       self.reload_button = ttk.Button(button_container, text="Recargar Datos Reconocedor", command=self.reload_recognizer_data, style="Action.TButton")
       self.reload_button.pack(side="left", padx=10)

       # --- Checkbox Debug Log ---
       self.debug_checkbox = ttk.Checkbutton(
           control_frame,
           text="Debug Log",
           variable=self.debug_log_var,
           command=self.toggle_debug_logging
       )
       self.debug_checkbox.pack(pady=5)

       # --- Slider de Umbral Template ---
       ttk.Label(control_frame, text="Umbral Template:").pack(pady=(5, 0))
       self.template_threshold_slider = tk.Scale(control_frame, from_=0.1, to=1.0, resolution=0.01, orient="horizontal", variable=self.template_threshold)
       self.template_threshold_slider.pack()

       # --- Slider de Umbral OCR ---
       ttk.Label(control_frame, text="Umbral OCR:").pack(pady=(5, 0))
       self.ocr_threshold_slider = tk.Scale(control_frame, from_=0.1, to=1.0, resolution=0.01, orient="horizontal", variable=self.ocr_threshold)
       self.ocr_threshold_slider.pack()

       self.apply_thresholds_button = ttk.Button(control_frame, text="Aplicar Umbrales", command=self.apply_thresholds)
       self.apply_thresholds_button.pack(pady=5)


   def create_result_frame(self):
       """Crea el frame para mostrar los resultados y botones de acción relacionados."""
       result_frame = ttk.LabelFrame(self, text="Resultado del Reconocimiento", padding=(10, 10))
       result_frame.grid(row=1, column=0, padx=10, pady=5, sticky="ew")
       result_frame.grid_columnconfigure(1, weight=1) # Columna de valores se expande

       # --- Etiquetas de Resultados ---
       row_idx = 0
       ttk.Label(result_frame, text="Método:").grid(row=row_idx, column=0, padx=5, pady=3, sticky="w")
       self.method_var = tk.StringVar(value="N/A")
       ttk.Label(result_frame, textvariable=self.method_var, style="Result.TLabel").grid(row=row_idx, column=1, padx=5, pady=3, sticky="w")
       row_idx += 1

       ttk.Label(result_frame, text="Estado Detectado:").grid(row=row_idx, column=0, padx=5, pady=3, sticky="w")
       self.state_var = tk.StringVar(value="N/A")
       ttk.Label(result_frame, textvariable=self.state_var, style="Result.TLabel").grid(row=row_idx, column=1, padx=5, pady=3, sticky="w")
       row_idx += 1

       ttk.Label(result_frame, text="Confianza (Template):").grid(row=row_idx, column=0, padx=5, pady=3, sticky="w")
       self.confidence_var = tk.StringVar(value="N/A")
       ttk.Label(result_frame, textvariable=self.confidence_var).grid(row=row_idx, column=1, padx=5, pady=3, sticky="w")
       row_idx += 1

       ttk.Label(result_frame, text="Tiempo Detección:").grid(row=row_idx, column=0, padx=5, pady=3, sticky="w")
       self.time_var = tk.StringVar(value="N/A")
       ttk.Label(result_frame, textvariable=self.time_var).grid(row=row_idx, column=1, padx=5, pady=3, sticky="w")
       row_idx += 1

       ttk.Label(result_frame, text="ROI Definido:").grid(row=row_idx, column=0, padx=5, pady=3, sticky="w")
       self.roi_defined_var = tk.StringVar(value="N/A")
       ttk.Label(result_frame, textvariable=self.roi_defined_var).grid(row=row_idx, column=1, padx=5, pady=3, sticky="w")
       row_idx += 1

       # --- Frame para Botones de Acción ---
       action_frame = ttk.Frame(result_frame)
       action_frame.grid(row=row_idx, column=0, columnspan=2, pady=(10, 5)) # Un poco más de espacio arriba

       self.confirm_button = ttk.Button(action_frame, text="👍 Confirmar Detección", style="Confirm.TButton", command=self.confirm_detection, state="disabled")
       self.confirm_button.pack(side="left", padx=5)
       self.deny_button = ttk.Button(action_frame, text="👎 Negar Detección", style="Deny.TButton", command=self.deny_detection, state="disabled")
       self.deny_button.pack(side="left", padx=5)
       self.roi_button = ttk.Button(action_frame, text="Definir/Editar ROI", command=self.define_roi_for_state, state="disabled", style="Action.TButton")
       self.roi_button.pack(side="left", padx=5)
       self.remove_roi_button = ttk.Button(action_frame, text="Eliminar ROI", command=self.remove_roi_for_state, state="disabled", style="Action.TButton") # Nuevo botón
       self.remove_roi_button.pack(side="left", padx=5)
       self.launch_capture_button = ttk.Button(action_frame, text="Abrir Gestor Plantillas", command=self.launch_template_manager, state="disabled", style="Action.TButton")
       self.launch_capture_button.pack(side="left", padx=5)


       self.save_result_button = ttk.Button(action_frame, text="💾 Guardar Resultados", command=self.save_recognition_result, state="normal", style="Action.TButton")
       self.save_result_button.pack(side="left", padx=5)

   def create_correction_frame(self):
       """Crea el frame para la corrección manual (inicialmente oculto)."""
       self.correction_frame = ttk.LabelFrame(self, text="Corrección Manual", padding=(10, 5))
       # No hacer grid aquí, se hará dinámicamente
       self.correction_frame.grid_columnconfigure(1, weight=1) # Permitir que el combobox se expanda

       ttk.Label(self.correction_frame, text="Estado Correcto:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
       self.correct_state_var = tk.StringVar()
       self.correct_state_combo = ttk.Combobox(self.correction_frame, textvariable=self.correct_state_var, width=35, state="readonly", style="TCombobox")
       self.correct_state_combo.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
       self.log_correction_button = ttk.Button(self.correction_frame, text="Registrar Corrección (Log)", command=self.log_correct_state, style="Action.TButton")
       self.log_correction_button.grid(row=0, column=2, padx=10, pady=5)


   def create_ocr_details_frame(self):
       """Crea el frame para detalles y edición OCR (inicialmente oculto)."""
       self.ocr_frame = ttk.LabelFrame(self, text="Detalles y Edición OCR", padding=(10, 5))
       # No hacer grid aquí
       self.ocr_frame.grid_rowconfigure(1, weight=1) # Permitir que el Treeview se expanda verticalmente
       self.ocr_frame.grid_columnconfigure(0, weight=1) # Permitir que el Treeview se expanda horizontalmente

       ttk.Label(self.ocr_frame, text="Resultados OCR por Región:").grid(row=0, column=0, columnspan=3, padx=5, pady=2, sticky="w")

       # --- Treeview para mostrar resultados OCR ---
       tree_frame = ttk.Frame(self.ocr_frame)
       tree_frame.grid(row=1, column=0, columnspan=3, padx=5, pady=5, sticky="nsew")
       tree_frame.grid_rowconfigure(0, weight=1)
       tree_frame.grid_columnconfigure(0, weight=1)

       self.ocr_tree = ttk.Treeview(tree_frame, columns=("RegionIdx", "Extracted", "Expected", "Match"), show="headings", height=5)
       self.ocr_tree.heading("RegionIdx", text="#", anchor="center")
       self.ocr_tree.column("RegionIdx", width=40, anchor="center", stretch=tk.NO)
       self.ocr_tree.heading("Extracted", text="Texto Extraído")
       self.ocr_tree.column("Extracted", width=250, stretch=tk.YES)
       self.ocr_tree.heading("Expected", text="Texto Esperado (JSON)")
       self.ocr_tree.column("Expected", width=250, stretch=tk.YES)
       self.ocr_tree.heading("Match", text="Coincide", anchor="center")
       self.ocr_tree.column("Match", width=60, anchor="center", stretch=tk.NO)
       self.ocr_tree.grid(row=0, column=0, sticky="nsew")

       ocr_scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.ocr_tree.yview)
       ocr_scrollbar.grid(row=0, column=1, sticky="ns")
       self.ocr_tree['yscrollcommand'] = ocr_scrollbar.set

       # Evento para cargar texto en el Entry al seleccionar fila
       self.ocr_tree.bind("<<TreeviewSelect>>", self.on_ocr_tree_select)

       # --- Entry y Botones de Edición OCR ---
       ttk.Label(self.ocr_frame, text="Texto Esperado (p/ Selección, separar con '|'):").grid(row=2, column=0, columnspan=3, padx=5, pady=(10, 2), sticky="w")
       self.ocr_edit_var = tk.StringVar()
       self.ocr_edit_entry = ttk.Entry(self.ocr_frame, textvariable=self.ocr_edit_var, width=60, state="disabled")
       self.ocr_edit_entry.grid(row=3, column=0, columnspan=3, padx=5, pady=5, sticky="ew")

       ocr_button_frame = ttk.Frame(self.ocr_frame)
       ocr_button_frame.grid(row=4, column=0, columnspan=3, pady=5)
       self.confirm_ocr_button = ttk.Button(ocr_button_frame, text="Confirmar Texto(s) Extraído(s) p/ Selección", command=self.confirm_ocr_text, state="disabled", style="Action.TButton")
       self.confirm_ocr_button.pack(side="left", padx=10)
       self.save_edited_button = ttk.Button(ocr_button_frame, text="Guardar Texto Editado p/ Selección", command=self.save_edited_ocr_text, state="disabled", style="Action.TButton")
       self.save_edited_button.pack(side="left", padx=10)


   def create_status_label(self):
       """Crea el label para mensajes de estado en la parte inferior."""
       self.status_label_var = tk.StringVar(value="Listo. Inicia el juego y pulsa 'Reconocer Pantalla'.")
       status_frame = ttk.Frame(self, height=25) # Frame contenedor
       status_frame.grid(row=4, column=0, padx=10, pady=(5, 10), sticky="ew")
       status_frame.pack_propagate(False) # Evitar que se encoja
       status_label = ttk.Label(status_frame, textvariable=self.status_label_var, anchor="w")
       status_label.pack(side="left", padx=5, pady=2)
       self.status_label_frame = status_frame # Guardar referencia al frame para moverlo

   def _populate_correction_combobox(self):
       """Llena el combobox de corrección con los nombres de estado ordenados."""
       try:
           # Usar el mapping cargado por el recognizer
           mapping = self.recognizer.template_names_mapping
           template_names = sorted(list(mapping.keys()))
           self.correct_state_combo['values'] = template_names
           if template_names:
               self.correct_state_var.set("") # No seleccionar ninguno por defecto
           logging.info(f"Combobox de corrección poblado con {len(template_names)} estados.")
       except Exception as e:
           logging.error(f"Error al poblar combobox de corrección: {e}")
           self.correct_state_combo['values'] = []


   def reload_recognizer_data(self):
       """Llama al método de recarga del reconocedor y actualiza la GUI."""
       self.status_message("Recargando datos del reconocedor...")
       try:
           self.recognizer.reload_data() # Llama al método de la instancia
           self._populate_correction_combobox() # Actualizar lista de estados
           self.status_message("Datos del reconocedor recargados correctamente.")
           logging.info("Datos del reconocedor recargados manualmente por el usuario.")
           # Resetear la interfaz a un estado inicial podría ser útil aquí
           self.reset_ui_state()
       except AttributeError:
            logging.error("Intento de recarga fallido: método reload_data() no encontrado en ScreenRecognizer.")
            messagebox.showerror("Error de Código", "La clase ScreenRecognizer parece no tener el método 'reload_data'.")
            self.status_message("Error al recargar: método no encontrado.")
       except RuntimeError as re:
           if "dictionary changed size during iteration" in str(re):
               logging.error(f"Error de tamaño de diccionario al recargar datos: {re}. Esto sugiere que las claves del diccionario config.json han sido modificadas manualmente de forma incorrecta.")
               messagebox.showerror(
                   "Error de Configuración",
                   "Se ha detectado una modificación incorrecta en las claves del archivo config.json.\n"
                   "Por favor, revise el archivo y asegúrese de que las claves estén bien formadas y sin duplicados.\n"
                   "Si ha editado manualmente el archivo, es posible que deba revertir los cambios o corregirlos.\n"
                   f"Detalle del error: {re}"
               )
               self.status_message("Error al recargar: claves config.json modificadas.")
           else:
               logging.error(f"Error inesperado al recargar datos: {re}", exc_info=True)
               messagebox.showerror("Error Inesperado", f"Ocurrió un error al recargar los datos:\n{re}")
               self.status_message("Error al recargar datos.")
       except Exception as e:
            logging.error(f"Error inesperado al recargar datos: {e}", exc_info=True)
            messagebox.showerror("Error Inesperado", f"Ocurrió un error al recargar los datos:\n{e}")
            self.status_message("Error al recargar datos.")

   def reset_ui_state(self):
        """Resetea la UI a un estado inicial después de recargar o al inicio."""
        self.method_var.set("N/A")
        self.state_var.set("N/A")
        self.confidence_var.set("N/A")
        self.time_var.set("N/A")
        self.roi_defined_var.set("N/A")
        self.last_recognition_result = None
        self.current_template_name = None

        # Deshabilitar botones de acción
        self.confirm_button.config(state="disabled")
        self.deny_button.config(state="disabled")
        self.roi_button.config(state="disabled")
        self.remove_roi_button.config(state="disabled")
        self.launch_capture_button.config(state="disabled")
        self.save_result_button.config(state="normal")

        # Ocultar frames adicionales
        self.correction_frame.grid_forget()
        self.ocr_frame.grid_forget()

        # Limpiar Treeview y Entry OCR
        for item in self.ocr_tree.get_children(): self.ocr_tree.delete(item)
        self.ocr_edit_var.set("")
        self.ocr_edit_entry.config(state="disabled")
        self.confirm_ocr_button.config(state="disabled")
        self.save_edited_button.config(state="disabled")

        # Resetear combobox de corrección
        self.correct_state_var.set("")

        # Mover barra de estado a su posición por defecto (debajo de resultados)
        self.status_label_frame.grid(row=2, column=0, padx=10, pady=(5, 10), sticky="ew")


   def run_test(self):
       """Ejecuta el reconocimiento y actualiza la GUI con los resultados."""
       self.status_message("Reconociendo pantalla...")
       # Deshabilitar botones mientras se procesa y resetear estado previo
       self.reset_ui_state() # Llama a la función que limpia y deshabilita
       self.test_button.config(state="disabled") # Deshabilitar botón de test también
       self.reload_button.config(state="disabled")
       self.apply_thresholds_button.config(state="disabled")
       self.update_idletasks() # Forzar actualización visual

       start_time = time.time()
       try:
            self.last_recognition_result = self.recognizer.recognize_screen_for_test()
       except Exception as e:
           logging.error(f"Error crítico durante recognize_screen_for_test: {e}", exc_info=True)
           messagebox.showerror("Error de Reconocimiento", f"Ocurrió un error grave durante el reconocimiento:\n{e}")
           self.last_recognition_result = {'method': 'error', 'state': 'error', 'confidence': None, 'ocr_results': None, 'detection_time_s': 0.0}
       finally:
           # Habilitar botones de control de nuevo
           self.test_button.config(state="normal")
           self.reload_button.config(state="normal")
           self.apply_thresholds_button.config(state="normal")

       end_time = time.time()
       # Usar el tiempo del resultado si está disponible, si no, calcularlo
       detection_time = self.last_recognition_result.get('detection_time_s', end_time - start_time)

       result = self.last_recognition_result
       method = str(result.get('method', 'unknown')).upper()
       state = str(result.get('state', 'unknown'))
       confidence_val = result.get('confidence')
       confidence_str = f"{confidence_val:.3f}" if confidence_val is not None else "N/A"
       time_str = f"{detection_time:.3f} seg"

       # Actualizar etiquetas de resultado
       self.update_preview_image(result)



       self.method_var.set(method)
       self.state_var.set(state if state != 'unknown' else 'N/A')
       self.confidence_var.set(confidence_str)
       self.time_var.set(time_str)

       # Loggear el resultado
       log_data = result.copy()
       log_data['detection_time_s'] = detection_time # Asegurar que el tiempo esté en el log
       logging.info(f"Resultado Reconocimiento: {json.dumps(log_data, ensure_ascii=False)}")

       # Determinar qué botones y frames mostrar/habilitar
       status_row = 2 # Fila por defecto para status (debajo de resultados)

       if state != 'unknown' and state != 'error':
           self.current_template_name = state # Guardar estado detectado
           # Habilitar botones de validación y ROI
           self.confirm_button.config(state="normal")
           self.deny_button.config(state="normal")
           self.roi_button.config(state="normal")

           # Comprobar y mostrar si hay ROI definido, habilitar botón de eliminar
           if state in self.recognizer.state_rois:
               self.roi_defined_var.set(f"Sí {self.recognizer.state_rois[state]}")
               self.remove_roi_button.config(state="normal") # Habilitar eliminar
           else:
               self.roi_defined_var.set("No")
               self.remove_roi_button.config(state="disabled") # No se puede eliminar si no existe

           if result.get('method') == 'ocr':
                # Mostrar y poblar frame OCR
                self.ocr_frame.grid(row=2, column=0, padx=10, pady=5, sticky="nsew")
                status_row = 3 # Mover status debajo de OCR
                self.populate_ocr_tree(result.get('ocr_results'))
                # Habilitar controles OCR (Entry se habilita al seleccionar fila)
                self.confirm_ocr_button.config(state="normal")
                self.save_edited_button.config(state="normal")
                self.status_message(f"Reconocido por OCR como '{state}'. Valida, edita texto esperado o gestiona ROI.")
           else: # Template o método desconocido pero con estado
               self.status_message(f"Reconocido por Template como '{state}'. Valida o gestiona ROI.")
               # Ocultar frames extras
               self.ocr_frame.grid_forget()
               self.correction_frame.grid_forget()
               # status_row se queda en 2
       else: # Estado 'unknown' o 'error'
           self.current_template_name = None
           self.roi_defined_var.set("N/A")
           # Habilitar corrección y gestor
           self.correction_frame.grid(row=2, column=0, padx=10, pady=5, sticky="ew")
           self.launch_capture_button.config(state="normal")
           status_row = 3 # Mover status debajo de corrección
           if state == 'error':
               self.status_message("ERROR durante el reconocimiento. Revisa logs. Puedes intentar corregir o abrir el gestor.")
           else:
               self.status_message("Pantalla NO RECONOCIDA. Selecciona estado correcto, define ROI o abre el gestor.")
           # Deshabilitar botones de validación y ROI ya que no hay estado detectado
           self.confirm_button.config(state="disabled")
           self.deny_button.config(state="disabled")
           self.roi_button.config(state="disabled") # Se habilita después de corregir si es necesario
           self.remove_roi_button.config(state="disabled")
           self.ocr_frame.grid_forget()


       # Ajustar posición final de la barra de estado
       self.status_label_frame.grid(row=status_row, column=0, padx=10, pady=(5, 10), sticky="ew")


   def populate_ocr_tree(self, ocr_results):
       """Llena el Treeview con los resultados detallados del OCR."""
       # Limpiar contenido anterior
       for item in self.ocr_tree.get_children(): self.ocr_tree.delete(item)

       if ocr_results and isinstance(ocr_results, dict):
           for idx, data in sorted(ocr_results.items()): # Ordenar por índice
               if isinstance(data, dict):
                   extracted = data.get('text', "")
                   expected_list = data.get('expected', [])
                   expected_str = "|".join(expected_list) if expected_list else ""
                   match_str = "Sí" if data.get('match_expected') else "No"
                   # Insertar fila en el treeview
                   self.ocr_tree.insert("", tk.END, iid=idx, values=(idx, extracted, expected_str, match_str))
               else:
                    logging.warning(f"Formato inesperado para resultado OCR índice {idx}: {data}")
       else:
           self.ocr_tree.insert("", tk.END, values=("N/A", "No hay resultados OCR detallados.", "", "N/A"))


   def on_ocr_tree_select(self, event=None):
        """Callback cuando se selecciona una fila en el Treeview OCR."""
        selected_items = self.ocr_tree.selection()
        if selected_items:
            # Tomar el primer item seleccionado
            first_item_id = selected_items[0]
            values = self.ocr_tree.item(first_item_id, 'values')
            if values:
                # Poner el texto esperado actual en el Entry para fácil edición
                expected_text = values[2] # Índice 2 es 'Expected'
                self.ocr_edit_var.set(expected_text)
                self.ocr_edit_entry.config(state="normal") # Habilitar entry
            else:
                 self.ocr_edit_entry.config(state="disabled")
                 self.ocr_edit_var.set("")
        else:
            # No hay selección, deshabilitar entry
            self.ocr_edit_entry.config(state="disabled")
            self.ocr_edit_var.set("")


   def confirm_detection(self):
       """Registra la confirmación del usuario para el estado detectado."""
       detected_state = self.state_var.get()
       if detected_state != "N/A" and self.last_recognition_result and self.last_recognition_result.get('state') != 'unknown':
           actual_state = self.last_recognition_result['state']
           logging.info(f"CONFIRMACIÓN USUARIO: Detección de '{actual_state}' es CORRECTA.")
           self.status_message(f"Detección de '{actual_state}' confirmada.")
           # Deshabilitar botones de acción principales después de confirmar
           self.confirm_button.config(state="disabled")
           self.deny_button.config(state="disabled")
           # Mantener ROI habilitado si es aplicable
           # self.roi_button.config(state="disabled")
           # self.remove_roi_button.config(state="disabled")
           self.launch_capture_button.config(state="disabled")
           # Ocultar frames adicionales si estaban visibles
           self.correction_frame.grid_forget()
           if self.method_var.get() != "OCR": # Ocultar OCR si no fue el método
                self.ocr_frame.grid_forget()
           # Mover barra de estado a su posición base
           self.status_label_frame.grid(row=2, column=0, padx=10, pady=(5, 10), sticky="ew")
       else:
            messagebox.showwarning("Acción Inválida", "No hay una detección válida para confirmar.")


   def deny_detection(self):
       """Registra negación, muestra opciones de corrección/gestión."""
       detected_state = self.last_recognition_result['state'] if self.last_recognition_result and self.last_recognition_result['state'] != 'unknown' else "unknown"
       logging.warning(f"NEGACIÓN USUARIO: Detección de '{detected_state}' es INCORRECTA.")
       self.status_message(f"Detección de '{detected_state}' negada. Selecciona estado correcto, define ROI o abre el gestor.")

       # Deshabilitar botones de confirmar/negar
       self.confirm_button.config(state="disabled")
       self.deny_button.config(state="disabled")

       # Mostrar frame de corrección
       self.correction_frame.grid(row=2, column=0, padx=10, pady=5, sticky="ew")
       self._populate_correction_combobox() # Asegurar que esté actualizado
       self.correct_state_var.set("") # Limpiar selección previa

       # Habilitar botones relevantes
       self.launch_capture_button.config(state="normal")
       self.roi_button.config(state="normal") # Permitir definir ROI para el estado correcto
       self.remove_roi_button.config(state="normal") # Permitir eliminar ROI si se selecciona uno que lo tenga

       # Ocultar frame OCR si estaba visible
       self.ocr_frame.grid_forget()
       # Mover barra de estado debajo de corrección
       self.status_label_frame.grid(row=3, column=0, padx=10, pady=(5, 10), sticky="ew")


   def log_correct_state(self):
       """Registra el estado correcto indicado por el usuario en el log."""
       correct_state = self.correct_state_var.get()
       last_detected = self.last_recognition_result['state'] if self.last_recognition_result and self.last_recognition_result['state'] != 'unknown' else "unknown"

       if not correct_state:
            messagebox.showwarning("Selección Vacía", "Por favor, selecciona el estado correcto en la lista desplegable.")
            return

       logging.info(f"CORRECCIÓN USUARIO: Detección fue '{last_detected}', estado correcto indicado: '{correct_state}'.")
       self.status_message(f"Corrección registrada en log: '{correct_state}'.")
       self.current_template_name = correct_state # Actualizar estado actual para definir/eliminar ROI

       # Deshabilitar botón después de registrar, pero mantener frame visible
       # self.log_correction_button.config(state="disabled") # Podría quererse registrar varias veces? Mejor no deshabilitar.
       # Podríamos actualizar el label de ROI aquí si el estado corregido tiene uno
       self.update_roi_label(correct_state)


   def update_roi_label(self, state_name):
        """Actualiza la etiqueta y el botón de eliminar ROI basado en el estado."""
        if state_name and state_name in self.recognizer.state_rois:
            self.roi_defined_var.set(f"Sí {self.recognizer.state_rois[state_name]}")
            self.remove_roi_button.config(state="normal")
        else:
            self.roi_defined_var.set("No")
            self.remove_roi_button.config(state="disabled")


   def define_roi_for_state(self):
       """Permite al usuario definir o editar el ROI para el estado actual (detectado o corregido)."""
       state_to_edit = None
       # Determinar para qué estado definir ROI
       if self.last_recognition_result and self.last_recognition_result.get('state') not in ['unknown', 'error', None]:
            # Hay un estado detectado válido
            state_to_edit = self.last_recognition_result['state']
            if not messagebox.askyesno("Confirmar Estado", f"¿Definir o sobrescribir ROI para el estado detectado '{state_to_edit}'?"):
                 # Permitir seleccionar otro si niega el detectado
                 state_to_edit = self.ask_for_state_selection("Seleccione el estado para el cual definir el ROI:")
       else:
            # No hubo detección válida, preguntar por el estado
            state_to_edit = self.ask_for_state_selection("La detección falló o fue negada.\nSeleccione el estado para el cual desea definir/editar el ROI:")

       if not state_to_edit:
           self.status_message("Definición de ROI cancelada (no se seleccionó estado).")
           return

       logging.info(f"Iniciando definición de ROI para: '{state_to_edit}'")
       self.status_message(f"Capturando pantalla para definir ROI de '{state_to_edit}'...")
       self.update_idletasks()

       # Ocultar ventana principal para la captura y selección
       self.withdraw()
       selected_roi = tk_select_roi(self, self.recognizer, state_to_edit)
       self.deiconify() # Mostrar de nuevo

       # Procesar el ROI seleccionado
       if selected_roi:
            logging.info(f"ROI seleccionado para '{state_to_edit}': {selected_roi}")
            all_rois = load_json_mapping(STATE_ROIS_FILE, "ROIs de estado")
            all_rois[state_to_edit] = selected_roi # Añadir o sobrescribir
            if save_json_mapping(all_rois, STATE_ROIS_FILE, "ROIs de estado"):
                 self.recognizer.reload_data() # ¡Importante! Recargar para que el recognizer use el nuevo ROI
                 messagebox.showinfo("Éxito", f"ROI guardado correctamente para '{state_to_edit}'.")
                 self.status_message(f"ROI guardado para '{state_to_edit}'.")
                 # Actualizar label y botón de eliminar en la GUI
                 self.update_roi_label(state_to_edit)
            else:
                # Mensaje de error ya mostrado por save_json_mapping
                logging.error(f"Fallo al guardar el archivo {STATE_ROIS_FILE} con el nuevo ROI.")
                self.status_message(f"Error al guardar ROI para '{state_to_edit}'.")
       else:
           self.status_message(f"Definición de ROI para '{state_to_edit}' cancelada o fallida.")
           logging.info(f"Definición de ROI para '{state_to_edit}' cancelada o sin selección.")


   def remove_roi_for_state(self):
        """Elimina la definición de ROI para el estado actual (detectado o corregido)."""
        state_to_modify = None
        # Determinar para qué estado eliminar ROI
        if self.last_recognition_result and self.last_recognition_result.get('state') not in ['unknown', 'error', None]:
             state_to_modify = self.last_recognition_result['state']
        elif self.current_template_name: # Usar el corregido si existe
             state_to_modify = self.current_template_name

        if not state_to_modify:
            messagebox.showwarning("Sin Estado", "No hay un estado detectado o corregido seleccionado para eliminar su ROI.")
            return

        # Verificar que realmente tenga un ROI definido
        all_rois = load_json_mapping(STATE_ROIS_FILE, "ROIs de estado")
        if state_to_modify not in all_rois:
             messagebox.showinfo("Información", f"El estado '{state_to_modify}' no tiene un ROI definido para eliminar.")
             self.update_roi_label(state_to_modify) # Asegurar que la UI esté correcta
             return

        if messagebox.askyesno("Confirmar Eliminación", f"¿Está seguro de que desea eliminar la definición de ROI para el estado '{state_to_modify}'?"):
             logging.info(f"Solicitando eliminación de ROI para '{state_to_modify}'.")
             del all_rois[state_to_modify] # Eliminar la entrada

             if save_json_mapping(all_rois, STATE_ROIS_FILE, "ROIs de estado"):
                 self.recognizer.reload_data() # Recargar para que el recognizer deje de usarlo
                 messagebox.showinfo("Éxito", f"ROI eliminado correctamente para '{state_to_modify}'.")
                 self.status_message(f"ROI eliminado para '{state_to_modify}'.")
                 # Actualizar label y botón en la GUI
                 self.update_roi_label(state_to_modify)
             else:
                 logging.error(f"Fallo al guardar {STATE_ROIS_FILE} después de eliminar ROI.")
                 self.status_message(f"Error al guardar cambios tras eliminar ROI para '{state_to_modify}'.")
        else:
             self.status_message("Eliminación de ROI cancelada.")


   def ask_for_state_selection(self, prompt_message):
        """Muestra un diálogo para seleccionar un estado de la lista."""
        available_states = sorted(list(self.recognizer.template_names_mapping.keys()))
        if not available_states:
            messagebox.showerror("Error", "No hay plantillas definidas. Abre el Gestor de Plantillas primero.")
            return None

        dialog = SelectStateDialog(self, title="Seleccionar Estado", prompt=prompt_message, states_list=available_states)
        # dialog.result contendrá el estado seleccionado o None si se cancela
        return dialog.result


   def launch_template_manager(self):
       """Lanza la GUI template_manager_gui.py en un proceso separado."""
       logging.info(f"Intentando lanzar el Gestor de Plantillas: {TEMPLATE_MANAGER_SCRIPT_PATH}")
       self.status_message("Abriendo Gestor de Plantillas...")
       self.update_idletasks()
       try:
           # Usar sys.executable para asegurar que se use el mismo intérprete Python
           process = subprocess.Popen([sys.executable, TEMPLATE_MANAGER_SCRIPT_PATH])
           logging.info(f"Gestor de Plantillas lanzado con PID: {process.pid}")
           # Mensaje mejorado con recordatorio
           self.status_message("Gestor de Plantillas abierto. **Recuerda 'Recargar Datos' aquí después de hacer cambios en el gestor.**")
       except FileNotFoundError:
           logging.error(f"Script del Gestor no encontrado en: {TEMPLATE_MANAGER_SCRIPT_PATH}")
           messagebox.showerror("Error de Archivo", f"No se encontró el script del gestor:\n{TEMPLATE_MANAGER_SCRIPT_PATH}")
           self.status_message("Error: Script del gestor no encontrado.")
       except Exception as e:
           logging.error(f"Error inesperado al lanzar el gestor: {e}", exc_info=True)
           messagebox.showerror("Error Inesperado", f"Ocurrió un error al intentar abrir el gestor:\n{e}")
           self.status_message("Error al abrir el gestor.")


   def confirm_ocr_text(self):
       """
       Confirma el texto extraído por OCR para la(s) región(es) seleccionada(s)
       en el Treeview, añadiéndolo a la lista 'expected_text' en ocr_regions.json.
       """
       if not self.last_recognition_result or self.last_recognition_result.get('method') != 'ocr' or not self.last_recognition_result.get('ocr_results'):
            messagebox.showwarning("Acción Inválida", "Esta acción solo está disponible después de un reconocimiento OCR exitoso.")
            return

       selected_items = self.ocr_tree.selection() # Obtiene los IDs de los items seleccionados
       if not selected_items:
           messagebox.showwarning("Sin Selección", "Selecciona una o más filas en la tabla OCR cuyo texto extraído quieras confirmar como válido.")
           return

       state_name = self.last_recognition_result.get('state')
       if not state_name or state_name == 'unknown':
           messagebox.showerror("Error Interno", "No se pudo determinar el estado asociado a los resultados OCR.")
           return

       ocr_results_map = self.last_recognition_result.get('ocr_results', {})
       target_updates = {} # { region_index: texto_extraido }

       for item_id in selected_items:
           try:
               # El item_id es el índice de la región que pusimos al insertar
               region_index = int(item_id)
               if region_index in ocr_results_map:
                   extracted_text = ocr_results_map[region_index].get('text', "").strip()
                   if extracted_text: # Solo añadir si no está vacío
                       target_updates[region_index] = extracted_text
                   else:
                       logging.warning(f"Texto extraído para región {region_index} está vacío, no se añadirá.")
               else:
                   logging.warning(f"Índice de región {region_index} seleccionado no encontrado en los resultados OCR.")
           except (ValueError, TypeError):
                logging.error(f"ID de item inválido en Treeview: {item_id}")

       if not target_updates:
           messagebox.showinfo("Información", "No se encontró texto extraído válido en las filas seleccionadas para confirmar.")
           return

       if not messagebox.askyesno("Confirmar Acción",
                                  f"¿Añadir los textos extraídos de las {len(target_updates)} regiones seleccionadas "
                                  f"a la lista de 'textos esperados' para el estado '{state_name}' en el archivo JSON?"):
            self.status_message("Confirmación de texto OCR cancelada.")
            return

       # --- Proceder a actualizar el JSON ---
       all_ocr_mappings = load_json_mapping(OCR_MAPPING_FILE, "regiones OCR")
       if state_name not in all_ocr_mappings or not isinstance(all_ocr_mappings.get(state_name), list):
           logging.warning(f"Creando/corrigiendo entrada de lista para '{state_name}' en {OCR_MAPPING_FILE}")
           all_ocr_mappings[state_name] = []

       updated_count = 0
       regions_list_for_state = all_ocr_mappings[state_name]

       for region_idx, text_to_add in target_updates.items():
           region_coords = ocr_results_map[region_idx].get('region')
           if not region_coords: continue # Seguridad

           entry_found_and_updated = False
           for i, entry in enumerate(regions_list_for_state):
               # Buscar la entrada correspondiente por coordenadas de región
               if isinstance(entry, dict) and entry.get('region') == region_coords:
                   # Asegurar que 'expected_text' exista y sea una lista
                   if 'expected_text' not in entry or not isinstance(entry['expected_text'], list):
                       entry['expected_text'] = []
                   # Añadir solo si no existe ya (insensible a mayúsculas/minúsculas)
                   if not any(existing.lower() == text_to_add.lower() for existing in entry['expected_text']):
                       entry['expected_text'].append(text_to_add)
                       logging.info(f"Añadido texto '{text_to_add}' a expected_text para región {region_idx} del estado '{state_name}'.")
                       updated_count += 1
                   else:
                        logging.info(f"Texto '{text_to_add}' ya existía para región {region_idx} del estado '{state_name}'.")
                   entry_found_and_updated = True
                   break # Salir del bucle de entries

           # Si no se encontró una entrada existente para estas coordenadas (raro, pero posible si el JSON se editó manualmente)
           if not entry_found_and_updated:
                logging.warning(f"No se encontró entrada existente para coords {region_coords} de región {region_idx} en '{state_name}'. Creando nueva entrada.")
                regions_list_for_state.append({'region': region_coords, 'expected_text': [text_to_add]})
                updated_count += 1

       # Guardar si hubo cambios
       if updated_count > 0:
           if save_json_mapping(all_ocr_mappings, OCR_MAPPING_FILE, "regiones OCR"):
               self.recognizer.reload_data() # Recargar datos en el recognizer
               logging.info(f"Actualizados {updated_count} textos esperados para '{state_name}' en {OCR_MAPPING_FILE}.")
               messagebox.showinfo("Éxito", f"Se añadieron/actualizaron {updated_count} textos esperados para '{state_name}'.")
               self.status_message(f"Textos esperados OCR actualizados para '{state_name}'.")
               # Refrescar la tabla para mostrar los cambios
               self.refresh_ocr_tree_display()
           else:
               logging.error(f"Fallo al guardar {OCR_MAPPING_FILE} después de confirmar texto OCR.")
               self.status_message("Error al guardar los textos esperados OCR.")
       else:
           messagebox.showinfo("Sin Cambios", "Los textos extraídos seleccionados ya estaban presentes o estaban vacíos. No se realizaron cambios.")
           self.status_message("No se requirieron cambios en los textos esperados OCR.")


   def save_edited_ocr_text(self):
       """
       Guarda el texto introducido en el Entry como la NUEVA lista
       'expected_text' para la(s) región(es) seleccionada(s) en el Treeview,
       SOBREESCRIBIENDO la lista anterior en ocr_regions.json.
       """
       if not self.last_recognition_result or self.last_recognition_result.get('method') != 'ocr':
            messagebox.showwarning("Acción Inválida", "Esta acción requiere un resultado de reconocimiento OCR previo.")
            return

       selected_items = self.ocr_tree.selection()
       if not selected_items:
           messagebox.showwarning("Sin Selección", "Selecciona una o más filas en la tabla OCR para las cuales deseas guardar el texto editado.")
           return

       state_name = self.last_recognition_result.get('state')
       if not state_name or state_name == 'unknown':
           messagebox.showerror("Error Interno", "No se pudo determinar el estado asociado a los resultados OCR.")
           return

       # Obtener y procesar el texto del Entry
       edited_text_str = self.ocr_edit_var.get().strip()
       if not edited_text_str:
           # Preguntar si realmente quiere guardar una lista vacía (eliminar textos esperados)
           if not messagebox.askyesno("Confirmar Vacío", "El campo de texto está vacío.\n¿Está seguro de que desea ELIMINAR TODOS los textos esperados para las regiones seleccionadas?"):
                self.status_message("Guardado de texto editado cancelado.")
                return
           expected_texts = [] # Lista vacía si confirma
           logging.info(f"Usuario confirma eliminar textos esperados para regiones seleccionadas de '{state_name}'.")
       else:
            # Dividir por '|', quitar espacios y filtrar vacíos
            expected_texts = [text.strip() for text in edited_text_str.split('|') if text.strip()]
            if not expected_texts: # Si solo eran espacios o '|'
                messagebox.showwarning("Entrada Inválida", "El texto introducido no contiene textos válidos después de procesar.")
                return

       # --- Obtener coordenadas de las regiones seleccionadas ---
       ocr_results_map = self.last_recognition_result.get('ocr_results', {})
       target_regions_coords = []
       valid_indices = []
       for item_id in selected_items:
            try:
                region_index = int(item_id)
                if region_index in ocr_results_map and 'region' in ocr_results_map[region_index]:
                    target_regions_coords.append(ocr_results_map[region_index]['region'])
                    valid_indices.append(region_index)
                else:
                    logging.warning(f"Índice {region_index} seleccionado no válido o sin coordenadas.")
            except (ValueError, TypeError):
                 logging.error(f"ID de item inválido en Treeview: {item_id}")

       if not target_regions_coords:
           messagebox.showerror("Error", "No se pudieron obtener las coordenadas de las regiones seleccionadas.")
           return

       action_desc = f"establecer la lista de textos esperados a [{', '.join(expected_texts)}]" if expected_texts else "eliminar la lista de textos esperados"
       if not messagebox.askyesno("Confirmar Sobrescritura",
                                  f"¿Está seguro de que desea {action_desc} "
                                  f"para las {len(target_regions_coords)} regiones seleccionadas del estado '{state_name}'? "
                                  f"Esto SOBREESCRIBIRÁ los textos anteriores."):
            self.status_message("Guardado de texto editado cancelado.")
            return

       # --- Actualizar el JSON ---
       all_ocr_mappings = load_json_mapping(OCR_MAPPING_FILE, "regiones OCR")
       if state_name not in all_ocr_mappings or not isinstance(all_ocr_mappings.get(state_name), list):
           logging.warning(f"Creando/corrigiendo entrada de lista para '{state_name}' en {OCR_MAPPING_FILE}")
           all_ocr_mappings[state_name] = []

       updated_count = 0
       regions_list_for_state = all_ocr_mappings[state_name]

       # Iterar sobre las entradas del JSON para el estado actual
       for i, entry in enumerate(regions_list_for_state):
           # Si la región de esta entrada coincide con una de las seleccionadas
           if isinstance(entry, dict) and entry.get('region') in target_regions_coords:
                try:
                    entry['expected_text'] = expected_texts # Sobrescribir la lista
                    logging.info(f"Texto esperado actualizado para región con coords {entry.get('region')} del estado '{state_name}' a: {expected_texts}")
                    updated_count += 1
                except Exception as e:
                     logging.error(f"Error al actualizar entrada {i} para '{state_name}': {e}")
                     messagebox.showerror("Error Interno", f"Error al actualizar la entrada para una región:\n{e}")
                     return # Abortar si hay un error

       # Guardar si se actualizó algo
       if updated_count > 0:
           if save_json_mapping(all_ocr_mappings, OCR_MAPPING_FILE, "regiones OCR"):
               self.recognizer.reload_data() # Recargar datos
               logging.info(f"Se sobrescribieron los textos esperados para {updated_count} regiones de '{state_name}'.")
               messagebox.showinfo("Éxito", f"Texto(s) esperado(s) guardado(s) para {updated_count} region(es) de '{state_name}'.")
               self.status_message(f"Texto(s) esperado(s) OCR guardado(s) para '{state_name}'.")
               # Limpiar el entry y refrescar la tabla
               self.ocr_edit_var.set("")
               self.ocr_edit_entry.config(state="disabled")
               self.ocr_tree.selection_remove(self.ocr_tree.selection()) # Deseleccionar filas
               self.refresh_ocr_tree_display()
           else:
               logging.error(f"Fallo al guardar {OCR_MAPPING_FILE} después de editar texto OCR.")
               self.status_message("Error al guardar los textos esperados OCR editados.")
       else:
           # Esto no debería ocurrir si target_regions_coords no estaba vacío, pero por si acaso
           logging.warning(f"No se encontró ninguna entrada en el JSON que coincidiera con las regiones seleccionadas para '{state_name}'.")
           messagebox.showwarning("Sin Cambios", f"No se encontraron las regiones seleccionadas en el archivo JSON para '{state_name}'. No se realizaron cambios.")


   def refresh_ocr_tree_display(self):
       """
       Actualiza el contenido del Treeview OCR basado en el último resultado
       de reconocimiento Y los datos actualizados cargados desde ocr_regions.json.
       """
       if not self.last_recognition_result or not self.last_recognition_result.get('ocr_results'):
           # No hay datos OCR para mostrar (o no fue método OCR)
           self.populate_ocr_tree(None) # Limpiar la tabla
           return

       state_name = self.last_recognition_result.get('state')
       if not state_name or state_name == 'unknown':
            self.populate_ocr_tree(None)
            return

       # Cargar los datos más recientes del JSON
       current_ocr_mappings = load_json_mapping(OCR_MAPPING_FILE, "regiones OCR")
       current_regions_data_list = current_ocr_mappings.get(state_name, [])
       # Crear un mapa de coordenadas a texto esperado para búsqueda rápida
       expected_text_map = {json.dumps(entry.get('region', {})): entry.get('expected_text', [])
                           for entry in current_regions_data_list if isinstance(entry, dict)}

       # Limpiar tabla
       for item in self.ocr_tree.get_children(): self.ocr_tree.delete(item)

       # Iterar sobre los resultados del *último reconocimiento*
       last_ocr_results = self.last_recognition_result.get('ocr_results', {})
       if last_ocr_results:
            for idx, data in sorted(last_ocr_results.items()):
                if isinstance(data, dict):
                    extracted = data.get('text', "")
                    region_coords = data.get('region')
                    region_coords_key = json.dumps(region_coords) if region_coords else None

                    # Buscar el texto esperado ACTUALIZADO del JSON
                    expected_list = expected_text_map.get(region_coords_key, []) if region_coords_key else []
                    expected_str = "|".join(expected_list) if expected_list else ""

                    # Recalcular si coincide con el texto esperado ACTUAL
                    match_expected = False
                    if extracted and expected_list:
                        extracted_lower = extracted.lower()
                        if any(expected.lower() == extracted_lower for expected in expected_list):
                            match_expected = True
                    match_str = "Sí" if match_expected else "No"

                    # Insertar fila actualizada
                    self.ocr_tree.insert("", tk.END, iid=idx, values=(idx, extracted, expected_str, match_str))
                else:
                     logging.warning(f"Formato inesperado para resultado OCR índice {idx} al refrescar: {data}")
       else:
            # Insertar fila de "no resultados" si no había nada en el último test
            self.ocr_tree.insert("", tk.END, values=("N/A", "No hay resultados OCR detallados.", "", "N/A"))


   def status_message(self, message):
       """Actualiza el mensaje en el label de estado y lo loggea."""
       logging.info(f"Status GUI: {message}")
       self.status_label_var.set(message)
       self.update_idletasks() # Forzar actualización inmediata

   def toggle_debug_logging(self):
       """Cambia el nivel de log en tiempo de ejecución."""
       if self.debug_log_var.get():
           logging.getLogger().setLevel(logging.DEBUG)
           logging.debug("Nivel de logging cambiado a DEBUG en GUI.")
       else:
           logging.getLogger().setLevel(logging.INFO)
           logging.info("Nivel de logging cambiado a INFO en GUI.")

   def apply_thresholds(self):
       """Aplica los umbrales seleccionados a la instancia del recognizer."""
       new_template_threshold = self.template_threshold.get()
       new_ocr_threshold = self.ocr_threshold.get()
       self.recognizer.threshold = new_template_threshold
       self.recognizer.ocr_fallback_threshold = new_ocr_threshold
       logging.info(f"Umbral de template actualizado a {new_template_threshold:.2f}.")
       logging.info(f"Umbral de OCR actualizado a {new_ocr_threshold:.2f}.")
       messagebox.showinfo("Umbrales Actualizados", f"Umbral de template: {new_template_threshold:.2f}\nUmbral de OCR: {new_ocr_threshold:.2f}")


   def update_preview_image(self, result):
       """Dibuja la imagen de preview en el canvas."""
       # Borrar cualquier elemento previo en el canvas
       self.preview_canvas.delete("all")

       if result is None or result.get('screenshot') is None:
           logging.warning("No se proporcionó captura de pantalla para el preview.")
           self.status_message("No hay preview disponible.")
           return

       # Obtener la imagen del resultado
       preview_image_cv = result['screenshot']

       if preview_image_cv is None or preview_image_cv.size == 0:
           logging.error("La captura de pantalla para el preview es inválida.")
           self.status_message("Error en la captura de pantalla.")
           return

       try:
           # Convertir a RGB y PIL
           preview_image_rgb = cv2.cvtColor(preview_image_cv, cv2.COLOR_BGR2RGB)
           preview_image_pil = Image.fromarray(preview_image_rgb)

           # Redimensionar si es necesario
           canvas_width = self.preview_canvas.winfo_width()
           canvas_height = self.preview_canvas.winfo_height()

           if canvas_width > 0 and canvas_height > 0:
               preview_width, preview_height = preview_image_pil.size
               if preview_width > canvas_width or preview_height > canvas_height:
                   scale = min(canvas_width / preview_width, canvas_height / preview_height)
                   new_width = int(preview_width * scale)
                   new_height = int(preview_height * scale)
                   preview_image_pil = preview_image_pil.resize((new_width, new_height), Image.LANCZOS)

           # Convertir a ImageTk
           self.preview_image_tk = ImageTk.PhotoImage(preview_image_pil)

           # Dibujar en el canvas, centrado
           x_offset = (canvas_width - self.preview_image_tk.width()) // 2 if canvas_width > self.preview_image_tk.width() else 0
           y_offset = (canvas_height - self.preview_image_tk.height()) // 2 if canvas_height > self.preview_image_tk.height() else 0
           self.preview_canvas.create_image(x_offset, y_offset, anchor=tk.NW, image=self.preview_image_tk)

           # Dibujar rectángulos si hay resultados
           if result.get('method') == 'template' and result.get('template_matches'):
               matches = result['template_matches']
               for match in matches:
                    # Obtener datos del match
                    template_name = match['name']
                    rect = match['rectangle']
                    confidence = match['confidence']
                    # Calcular coords en la imagen de preview escalada
                    left = int(rect['left'] * self.preview_image_tk.width() / preview_image_pil.width) + x_offset
                    top = int(rect['top'] * self.preview_image_tk.height() / preview_image_pil.height) + y_offset
                    width = int(rect['width'] * self.preview_image_tk.width() / preview_image_pil.width)
                    height = int(rect['height'] * self.preview_image_tk.height() / preview_image_pil.height)
                    # Determinar el color en función de la confianza
                    color = CONFIDENCE_COLOR_DEFAULT if confidence >= self.recognizer.threshold else CONFIDENCE_COLOR_ERROR

                    # Dibujar el rectángulo y la etiqueta
                    self.preview_canvas.create_rectangle(left, top, left + width, top + height, outline=color, width=2)
                    label_x, label_y = left, top - 15  # Encima del rectángulo
                    if label_y < 0:
                        label_y = top + height + 5
                    self.preview_canvas.create_text(label_x, label_y, text=f"{template_name}: {confidence:.2f}", fill=color, anchor=tk.NW, font=("Arial", 8))
           elif result.get('method') == 'ocr' and result.get('ocr_results'):
               # Si hay resultados OCR, dibujar los rectángulos de las regiones
               ocr_results = result['ocr_results']
               for ocr_data in ocr_results.values():
                   rect = ocr_data['region']
                   extracted_text = ocr_data['text']
                   # Calcular coords en la imagen de preview escalada
                   left = int(rect['left'] * self.preview_image_tk.width() / preview_image_pil.width) + x_offset
                   top = int(rect['top'] * self.preview_image_tk.height() / preview_image_pil.height) + y_offset
                   width = int(rect['width'] * self.preview_image_tk.width() / preview_image_pil.width)
                   height = int(rect['height'] * self.preview_image_tk.height() / preview_image_pil.height)
                   # Dibujar el rectángulo
                   rect_color = "light blue"  # Puedes ajustar el color aquí
                   self.preview_canvas.create_rectangle(left, top, left + width, top + height, outline=rect_color, width=2)
                   
                   rect_color = "light green" if ocr_data.get('match_expected') else "lightcoral"  # Highlight matches
                   self.preview_canvas.create_rectangle(left, top, left + width, top + height, outline=rect_color, width=2)
                   self.preview_canvas.create_text(left + width + 5, top + height // 2,
                                                        text=f"Conf: {ocr_data.get('confidence', 'N/A'):.2f}",  # Show confidence
                                                        fill=rect_color, anchor=tk.W)
                   # --- Dibujar el texto extraído ---
                   text_color = "black"
                   font_size = 8 # Ajustable
                   text_x, text_y = left + 3, top - font_size - 2  # Ajusta la posición del texto
                   if text_y < 0:
                       text_y = top + height + 5

                   # Crear el fondo para el texto
                   self.preview_canvas.create_rectangle(text_x - 2, text_y - 2, text_x + len(extracted_text) * font_size // 2, text_y + font_size + 2, fill="lightyellow", outline="lightyellow")
                   # Dibujar el texto
                   self.preview_canvas.create_text(text_x, text_y, text=extracted_text, fill=text_color, anchor=tk.NW, font=("Arial", font_size))
       except Exception as e:
           logging.error(f"Error al dibujar imagen de preview: {e}", exc_info=True)

   def save_recognition_result(self):
       """Guarda los resultados detallados del último reconocimiento en un archivo JSON."""
       if not self.last_recognition_result:
           self.status_message("No hay resultados de reconocimiento para guardar.")
           messagebox.showwarning("Sin Resultados", "No hay resultados de reconocimiento para guardar.")
           return

       # Crear un timestamp para el nombre del archivo
       timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
       filename = f"recognition_result_{timestamp}.json"
       filepath = os.path.join(PROJECT_DIR, "logs", filename)

       # Prepara los datos a guardar
       data_to_save = {
           "timestamp": timestamp,
           "recognition_result": self.last_recognition_result,  # Todos los datos de reconocimiento
           "recognizer_config": {
               "threshold": self.recognizer.threshold,
               "ocr_fallback_threshold": self.recognizer.ocr_fallback_threshold,
               "monitor": self.recognizer.monitor,
               "monitors_info": self.recognizer.monitors_info
           }
       }

       # Convertir la imagen a base64 para incluirla en el JSON
       screenshot = self.last_recognition_result.get("screenshot")
       if screenshot is not None and screenshot.size > 0:
           try:
               screenshot_pil = Image.fromarray(cv2.cvtColor(screenshot, cv2.COLOR_BGR2RGB))
               import base64
               from io import BytesIO
               buffered = BytesIO()
               screenshot_pil.save(buffered, format="PNG")
               screenshot_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
               data_to_save["screenshot_base64"] = screenshot_base64
           except Exception as e:
               logging.error(f"Error al convertir captura a base64: {e}")
               messagebox.showwarning("Error", "No se pudo convertir la captura a base64 para guardar.")

       # Guardar los datos en el archivo JSON
       try:
           with open(filepath, "w", encoding="utf-8") as f:
               json.dump(data_to_save, f, ensure_ascii=False, indent=4)
           self.status_message(f"Resultados guardados en: {filepath}")
           logging.info(f"Resultados de reconocimiento guardados en: {filepath}")
       except Exception as e:
           logging.error(f"Error al guardar los resultados en {filepath}: {e}")
           self.status_message(f"Error al guardar los resultados en: {filepath}")
           messagebox.showerror("Error", f"No se pudieron guardar los resultados en:\n{filepath}")


if __name__ == "__main__":
   # Asegurar que existan los directorios config, images y logs al inicio
   for dir_path in [CONFIG_DIR, IMAGES_DIR, os.path.dirname(LOG_FILE_TESTER)]:
       if not os.path.exists(dir_path):
           logging.info(f"Creando directorio necesario: {dir_path}")
           os.makedirs(dir_path)

   app = ScreenTesterGUI()
   app.mainloop()

# --- END OF FILE screen_tester_gui ---