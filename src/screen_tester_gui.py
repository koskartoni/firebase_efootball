# --- START OF FILE screen_tester_gui.py ---

import os
import json
import datetime
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog # Añadido simpledialog
# No necesitamos importar cv2, numpy, mss aquí directamente si ScreenRecognizer los maneja
# Importar solo lo necesario para las GUIs y tk_select_roi si se mantiene aquí
import cv2
import numpy as np
from PIL import Image, ImageTk, ImageDraw, ImageFont # Necesarios para preview y tk_select_roi
from tkinter import font
import time
import logging
import subprocess
import sys
import re # Importar re

# --- Importar lo necesario desde screen_recognizer ---
# Asegúrate de que estas importaciones sean correctas y los archivos existan
try:
    from screen_recognizer import (
       ScreenRecognizer,
       save_json_mapping,
       load_json_mapping,
       OCR_MAPPING_FILE,
       TEMPLATE_MAPPING_FILE,
       STATE_ROIS_FILE,
       DEFAULT_FONT_SIZE,
       PROJECT_DIR,
       IMAGES_DIR,
       CONFIG_DIR
    )
except ImportError as e:
    # Intentar crear una ventana de Tkinter para mostrar el error
    try:
        root_err = tk.Tk()
        root_err.withdraw() # Ocultar ventana principal de Tkinter
        messagebox.showerror("Error Crítico de Importación",
                             f"No se pudo importar 'ScreenRecognizer' o sus constantes.\n"
                             f"Asegúrate de que 'screen_recognizer.py' existe en la carpeta 'src' "
                             f"y que no hay errores de sintaxis en él.\n\nDetalle: {e}")
    except Exception as tk_err:
        print(f"ERROR CRÍTICO: No se pudo importar ScreenRecognizer Y falló al mostrar messagebox: {tk_err}") # Fallback a print
        print(f"Detalle Import Error: {e}")
    sys.exit(f"Error Crítico: {e}") # Salir si no se puede importar lo esencial

# --- Definir constantes locales ---
MIN_WINDOW_WIDTH = 1200 # Más ancho para preview
MIN_WINDOW_HEIGHT = 750
MIN_PREVIEW_WIDTH = 350 # Tamaño mínimo para canvas de preview
MIN_PREVIEW_HEIGHT = 250
PREVIEW_NUMBER_FONT_SIZE = 10 # Para texto OCR en preview
LOG_FILE_TESTER = os.path.join(PROJECT_DIR, "logs", "tester_log.log") # Guardar en subcarpeta logs
os.makedirs(os.path.dirname(LOG_FILE_TESTER), exist_ok=True)

# --- Configuración del Logging ---
# Limpiar handlers existentes antes de configurar para evitar duplicados si se re-ejecuta
root_logger = logging.getLogger()
if root_logger.hasHandlers():
    for handler in root_logger.handlers[:]: root_logger.removeHandler(handler)

logging.basicConfig(
   level=logging.INFO,
   format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
   handlers=[
       logging.FileHandler(LOG_FILE_TESTER, encoding='utf-8'),
       logging.StreamHandler(sys.stdout) # Usar stdout para asegurar salida en IDEs
   ]
)

# Ruta al script de la GUI de gestión de plantillas
TEMPLATE_MANAGER_SCRIPT_PATH = os.path.join(PROJECT_DIR, "src", "template_manager_gui.py")

# --- Clase para el Diálogo de Selección de Estado (para ROI) ---
class SelectStateDialog(simpledialog.Dialog):
    """Diálogo personalizado para seleccionar un estado de una lista."""
    # (Sin cambios respecto a versión anterior funcional)
    def __init__(self, parent, title, prompt, states_list):
        self.prompt = prompt
        self.states = states_list
        self.result = None
        super().__init__(parent, title)

    def body(self, master):
        try:
            ttk.Label(master, text=self.prompt, justify=tk.LEFT).pack(pady=5)
            self.combo_var = tk.StringVar()
            self.combobox = ttk.Combobox(master, textvariable=self.combo_var, values=self.states, width=40, state="readonly")
            if self.states:
                self.combobox.current(0) # Seleccionar el primero por defecto
            self.combobox.pack(pady=5, padx=10)
            return self.combobox # Establecer foco inicial
        except tk.TclError as e:
             logging.error(f"Error creando cuerpo del diálogo (posible problema ttk): {e}")
             # Fallback a widgets tk estándar si ttk falla
             tk.Label(master, text=self.prompt, justify=tk.LEFT).pack(pady=5)
             self.combo_var = tk.StringVar()
             # Usar OptionMenu como fallback si Combobox falla
             if self.states: self.combo_var.set(self.states[0])
             self.option_menu = tk.OptionMenu(master, self.combo_var, *self.states if self.states else ["(No hay estados)"])
             self.option_menu.config(width=35)
             self.option_menu.pack(pady=5, padx=10)
             return self.option_menu


    def apply(self):
        self.result = self.combo_var.get()
        if self.result == "(No hay estados)": self.result = None


# --- Función tk_select_roi (Revisada y Corregida) ---
def tk_select_roi(root, recognizer_instance, state_name):
    """
    Permite al usuario seleccionar una Región de Interés (ROI) para un estado.
    Usa la instancia del recognizer para capturar la pantalla y obtener info del monitor.
    Devuelve las coordenadas ROI absolutas de pantalla.
    """
    logging.info(f"Solicitando captura de pantalla completa para definir ROI de '{state_name}'")
    full_screen_image = recognizer_instance.capture_screen(region=None)
    if full_screen_image is None: messagebox.showerror("Error de Captura", "No se pudo capturar la pantalla completa para definir ROI."); return None
    monitor_info = recognizer_instance._get_monitor_region()
    if not monitor_info: logging.error("No se pudo obtener información del monitor desde recognizer."); messagebox.showerror("Error Interno", "No se pudo obtener información del monitor."); return None
    orig_height, orig_width = full_screen_image.shape[:2]; scale = 1.0
    try: screen_w, screen_h = root.winfo_screenwidth(), root.winfo_screenheight()
    except tk.TclError: screen_w, screen_h = 1280, 720 # Fallback
    max_dw=screen_w*0.85; max_dh=screen_h*0.85
    if orig_width > max_dw: scale_w = max_dw / orig_width
    else: scale_w = 1.0
    if orig_height > max_dh: scale_h = max_dh / orig_height
    else: scale_h = 1.0
    scale = min(scale_w, scale_h, 1.0)
    nw=int(orig_width*scale); nh=int(orig_height*scale)
    if nw<1 or nh<1: messagebox.showerror("Error Imagen", "Imagen capturada inválida."); return None
    try:
        interpolation = cv2.INTER_LANCZOS4 if scale<1.0 and hasattr(cv2,'INTER_LANCZOS4') else cv2.INTER_AREA
        resized_img = cv2.resize(full_screen_image, (nw, nh), interpolation=interpolation)
    except Exception as e: logging.error(f"Error resize ROI: {e}"); messagebox.showerror("Error Resize", f"No resize:\n{e}"); return None
    try:
        img_rgb = cv2.cvtColor(resized_img, cv2.COLOR_BGR2RGB); pil_img=Image.fromarray(img_rgb); tk_img=ImageTk.PhotoImage(pil_img)
    except Exception as e: logging.error(f"Error convirtiendo ROI: {e}"); messagebox.showerror("Error Imagen", f"No convertir:\n{e}"); return None

    sel_win = tk.Toplevel(root); sel_win.title(f"Seleccione ROI para: '{state_name}'"); sel_win.grab_set()
    win_w, win_h = tk_img.width()+40, tk_img.height()+90
    try: root_x, root_y = root.winfo_x(), root.winfo_y()
    except tk.TclError: root_x, root_y = 50, 50
    sel_win.geometry(f"{win_w}x{win_h}+{root_x+60}+{root_y+60}"); sel_win.minsize(max(400,win_w//2), max(300,win_h//2))
    canvas = tk.Canvas(sel_win, width=tk_img.width(), height=tk_img.height(), cursor="cross", bg="black")
    canvas.pack(padx=10, pady=10, fill="both", expand=True); canvas.create_image(0, 0, anchor="nw", image=tk_img); canvas.image=tk_img
    selection={"x1": None, "y1": None, "x2": None, "y2": None}; rect=None; confirmed_roi_absolute=None

    def on_button_press(event):
        nonlocal rect # Declarar nonlocal
        selection["x1"] = canvas.canvasx(event.x); selection["y1"] = canvas.canvasy(event.y)
        if rect: canvas.delete(rect)
        rect = canvas.create_rectangle(selection["x1"], selection["y1"], selection["x1"], selection["y1"], outline="cyan", width=3, dash=(5, 3))

    def on_move_press(event):
        if rect and selection["x1"] is not None: cur_x = canvas.canvasx(event.x); cur_y = canvas.canvasy(event.y); canvas.coords(rect, selection["x1"], selection["y1"], cur_x, cur_y)

    def on_button_release(event):
        if rect and selection["x1"] is not None:
            selection["x2"]=canvas.canvasx(event.x); selection["y2"]=canvas.canvasy(event.y); x1,y1=min(selection["x1"],selection["x2"]),min(selection["y1"],selection["y2"]); x2,y2=max(selection["x1"],selection["x2"]),max(selection["y1"],selection["y2"])
            selection["x1"],selection["y1"],selection["x2"],selection["y2"]=x1,y1,x2,y2; canvas.coords(rect,x1,y1,x2,y2)

    canvas.bind("<ButtonPress-1>", on_button_press); canvas.bind("<B1-Motion>", on_move_press); canvas.bind("<ButtonRelease-1>", on_button_release)
    bframe = ttk.Frame(sel_win); bframe.pack(pady=10)

    def confirm_sel():
        nonlocal confirmed_roi_absolute
        if None not in (selection["x1"], selection["y1"], selection["x2"], selection["y2"]):
            lr,tr=selection["x1"],selection["y1"]; wr,hr=selection["x2"]-lr,selection["y2"]-tr
            lo,to=int((lr/scale)+0.5),int((tr/scale)+0.5); wo,ho=int((wr/scale)+0.5),int((hr/scale)+0.5)
            wo=max(1,min(wo,orig_width-lo)); ho=max(1,min(ho,orig_height-to)); lo=max(0,min(lo,orig_width-1)); to=max(0,min(to,orig_height-1))
            if wo>0 and ho>0: la,ta=monitor_info['left']+lo,monitor_info['top']+to; confirmed_roi_absolute={"left":la,"top":ta,"width":wo,"height":ho}; logging.info(f"ROI sel(Abs):{confirmed_roi_absolute}")
            else: logging.warning("ROI inválido."); messagebox.showwarning("Inválido","ROI inválido.")
        else: logging.warning("ROI no completo."); messagebox.showwarning("Sin Selección","No selección completa.")
        sel_win.destroy()
    def cancel_sel(): logging.info("ROI cancelado."); sel_win.destroy()
    try: ttk.Button(bframe,text="Guardar ROI",command=confirm_sel).pack(side="left",padx=5); ttk.Button(bframe,text="Cancelar",command=cancel_sel).pack(side="left",padx=5)
    except tk.TclError: tk.Button(bframe,text="Guardar ROI",command=confirm_sel).pack(side="left",padx=5); tk.Button(bframe,text="Cancelar",command=cancel_sel).pack(side="left",padx=5)
    sel_win.bind("<Escape>",lambda e:cancel_sel()); root.wait_window(sel_win); return confirmed_roi_absolute


# --- Clase Principal GUI Tester ---
class ScreenTesterGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Tester Interactivo - Screen Recognizer")
        self.minsize(MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT)
        self.current_template_name = None
        self.last_recognition_result = None
        self.current_preview_image_cv = None
        self.tk_img_preview = None
        try: self.recognizer = ScreenRecognizer(monitor=1, threshold=0.75, ocr_fallback_threshold=0.65)
        except Exception as e: logging.error(f"Error init Recognizer: {e}", exc_info=True); messagebox.showerror("Error Crítico", f"No init Recognizer:\n{e}"); sys.exit(1)
        self.monitors_info = self.recognizer.monitors_info
        self.setup_fonts_and_styles()
        self.configure(background="#333333")
        self.preview_font = self._get_preview_font()
        self.create_widgets()
        self._populate_correction_combobox()
        self.reset_ui_state()
        logging.info("Tester GUI inicializado.")

    def _get_preview_font(self):
        try: return ImageFont.truetype("consola.ttf", PREVIEW_NUMBER_FONT_SIZE)
        except IOError:
            try: return ImageFont.truetype("cour.ttf", PREVIEW_NUMBER_FONT_SIZE)
            except IOError: logging.warning("Fuentes Consolas/Courier no.");
                 try: info=font.nametofont("TkDefaultFont").actual(); return ImageFont.truetype(f"{info['family'].lower()}.ttf", PREVIEW_NUMBER_FONT_SIZE)
                 except Exception: return ImageFont.load_default()

    def setup_fonts_and_styles(self):
        self.default_font = font.nametofont("TkDefaultFont"); self.default_font.configure(size=DEFAULT_FONT_SIZE); style = ttk.Style(self)
        try: style.theme_use('clam')
        except tk.TclError: try: style.theme_use('alt')
                          except tk.TclError: pass
        dark_bg="#333333"; light_fg="#FFFFFF"; entry_bg="#555555"; select_bg='#0078D7'
        style.configure('.', font=self.default_font, padding=(3, 1), background=dark_bg, foreground=light_fg, bordercolor="#666666")
        style.configure('TLabelframe', background=dark_bg, bordercolor=light_fg); style.configure('TLabelframe.Label', font=(self.default_font.actual()['family'], DEFAULT_FONT_SIZE, 'bold'), background=dark_bg, foreground=light_fg)
        style.map('TEntry', fieldbackground=[('!disabled', entry_bg)], foreground=[('!disabled', light_fg)], insertcolor=light_fg)
        style.map('TCombobox', fieldbackground=[('readonly', entry_bg)], foreground=[('readonly', light_fg)], selectbackground=[('focus', select_bg)], selectforeground=[('focus', light_fg)], background=entry_bg); style.configure('TCombobox', arrowcolor=light_fg)
        style.configure("Treeview", background=entry_bg, fieldbackground=entry_bg, foreground=light_fg); style.map("Treeview", background=[('selected', select_bg)])
        style.configure("Treeview.Heading", font=(self.default_font.actual()['family'], DEFAULT_FONT_SIZE, 'bold'), background="#444444", foreground=light_fg, relief="flat"); style.map("Treeview.Heading", relief=[('active','groove'),('pressed','sunken')])
        style.configure("Result.TLabel", font=(self.default_font.actual()['family'], DEFAULT_FONT_SIZE + 1, 'bold'), background=dark_bg, foreground="lime")
        style.configure("Confirm.TButton", foreground="green", font=self.default_font); style.map("Confirm.TButton", background=[('active', '#005000')])
        style.configure("Deny.TButton", foreground="red", font=self.default_font); style.map("Deny.TButton", background=[('active', '#500000')])
        style.configure("Action.TButton", padding=(5, 3)); style.map("Action.TButton", background=[('active', '#444444')])
        style.configure("TCheckbutton", background=dark_bg, foreground=light_fg); style.map("TCheckbutton", indicatorcolor=[('selected', select_bg), ('!selected', entry_bg)])
        style.configure("TFrame", background=dark_bg); style.configure("TLabel", background=dark_bg, foreground=light_fg); style.configure('Horizontal.TScale', background=dark_bg)
        self.option_add("*Font", self.default_font); self.option_add("*background", dark_bg); self.option_add("*foreground", light_fg); self.option_add("*selectBackground", select_bg); self.option_add("*selectForeground", light_fg)
        self.option_add("*Canvas.background", "#404040"); self.option_add("*Scale.background", dark_bg); self.option_add("*Scale.foreground", light_fg); self.option_add("*Scale.troughColor", entry_bg)

    def create_widgets(self):
        # (Layout 2 columnas, ajustado grid)
        self.grid_rowconfigure(0, weight=0) # Fila control fija
        self.grid_rowconfigure(1, weight=0) # Fila resultado fija
        self.grid_rowconfigure(2, weight=1) # Fila expandible para OCR/Corrección
        self.grid_rowconfigure(3, weight=0) # Fila status fija
        self.grid_columnconfigure(0, weight=1, minsize=550) # Columna izquierda
        self.grid_columnconfigure(1, weight=1, minsize=MIN_PREVIEW_WIDTH) # Columna derecha (preview)

        # --- Columna Izquierda ---
        left_panel = ttk.Frame(self); left_panel.grid(row=0, column=0, rowspan=4, padx=(10,5), pady=10, sticky="nsew"); left_panel.grid_rowconfigure(2, weight=1); left_panel.grid_columnconfigure(0, weight=1)
        self.create_control_frame(left_panel)    # row 0
        self.create_result_frame(left_panel)     # row 1
        # Frames ocultos se añadirán a row 2
        self.create_correction_frame(left_panel)
        self.create_ocr_details_frame(left_panel)
        self.create_status_label(left_panel)     # row 3

        # --- Columna Derecha ---
        self.create_preview_frame(self) # Pasa self como padre, se coloca en col 1

    def create_preview_frame(self, parent):
        # (Ahora se coloca en columna 1, rowspan 4)
        preview_frame = ttk.LabelFrame(parent, text="Previsualización Estado", padding=(5, 5)); preview_frame.grid(row=0, column=1, rowspan=4, padx=(5, 10), pady=10, sticky="nsew"); preview_frame.grid_rowconfigure(0, weight=1); preview_frame.grid_columnconfigure(0, weight=1)
        canvas_container = ttk.Frame(preview_frame); canvas_container.grid(row=0, column=0, sticky="nsew"); canvas_container.grid_rowconfigure(0, weight=1); canvas_container.grid_columnconfigure(0, weight=1)
        self.preview_canvas = tk.Canvas(canvas_container, bg="#404040", highlightthickness=0); self.preview_canvas.grid(row=0, column=0, padx=0, pady=0, sticky="nsew"); canvas_container.bind("<Configure>", self.on_preview_resize)

    def create_control_frame(self, parent):
        # (Se coloca en row 0 del panel izquierdo)
        control_frame = ttk.LabelFrame(parent, text="Control", padding=(10, 5)); control_frame.grid(row=0, column=0, padx=0, pady=(0, 5), sticky="ew")
        button_container = ttk.Frame(control_frame); button_container.pack(pady=5, fill="x", expand=True)
        self.test_button = ttk.Button(button_container, text="Reconocer Pantalla", command=self.run_test, style="Action.TButton"); self.test_button.pack(side="left", padx=5, expand=True, fill='x')
        self.reload_button = ttk.Button(button_container, text="Recargar Datos", command=self.reload_recognizer_data, style="Action.TButton"); self.reload_button.pack(side="left", padx=5, expand=True, fill='x')

    def create_result_frame(self, parent):
        # (Se coloca en row 1 del panel izquierdo)
        result_frame = ttk.LabelFrame(parent, text="Resultado Reconocimiento", padding=(10, 5)); result_frame.grid(row=1, column=0, padx=0, pady=5, sticky="ew"); result_frame.grid_columnconfigure(1, weight=1)
        row_idx=0; ttk.Label(result_frame, text="Método:").grid(row=row_idx, column=0, padx=5, pady=2, sticky="w"); self.method_var = tk.StringVar(value="N/A"); ttk.Label(result_frame, textvariable=self.method_var, style="Result.TLabel").grid(row=row_idx, column=1, padx=5, pady=2, sticky="w"); row_idx += 1
        ttk.Label(result_frame, text="Estado:").grid(row=row_idx, column=0, padx=5, pady=2, sticky="w"); self.state_var = tk.StringVar(value="N/A"); ttk.Label(result_frame, textvariable=self.state_var, style="Result.TLabel").grid(row=row_idx, column=1, padx=5, pady=2, sticky="w"); row_idx += 1
        ttk.Label(result_frame, text="Confianza:").grid(row=row_idx, column=0, padx=5, pady=2, sticky="w"); self.confidence_var = tk.StringVar(value="N/A"); ttk.Label(result_frame, textvariable=self.confidence_var).grid(row=row_idx, column=1, padx=5, pady=2, sticky="w"); row_idx += 1
        ttk.Label(result_frame, text="Tiempo:").grid(row=row_idx, column=0, padx=5, pady=2, sticky="w"); self.time_var = tk.StringVar(value="N/A"); ttk.Label(result_frame, textvariable=self.time_var).grid(row=row_idx, column=1, padx=5, pady=2, sticky="w"); row_idx += 1
        ttk.Label(result_frame, text="ROI Def.:").grid(row=row_idx, column=0, padx=5, pady=2, sticky="w"); self.roi_defined_var = tk.StringVar(value="N/A"); ttk.Label(result_frame, textvariable=self.roi_defined_var).grid(row=row_idx, column=1, padx=5, pady=2, sticky="w"); row_idx += 1
        action_frame = ttk.Frame(result_frame); action_frame.grid(row=row_idx, column=0, columnspan=2, pady=(5, 5)); action_frame.grid_columnconfigure((0,1,2,3,4), weight=1) # Distribuir botones
        self.confirm_button = ttk.Button(action_frame, text="👍", style="Confirm.TButton", command=self.confirm_detection, state="disabled", width=4); self.confirm_button.pack(side="left", padx=2, fill='x', expand=True)
        self.deny_button = ttk.Button(action_frame, text="👎", style="Deny.TButton", command=self.deny_detection, state="disabled", width=4); self.deny_button.pack(side="left", padx=2, fill='x', expand=True)
        self.roi_button = ttk.Button(action_frame, text="ROI+", command=self.define_roi_for_state, state="disabled", style="Action.TButton", width=4); self.roi_button.pack(side="left", padx=2, fill='x', expand=True)
        self.remove_roi_button = ttk.Button(action_frame, text="ROI-", command=self.remove_roi_for_state, state="disabled", style="Action.TButton", width=4); self.remove_roi_button.pack(side="left", padx=2, fill='x', expand=True)
        self.launch_capture_button = ttk.Button(action_frame, text="Gestor", command=self.launch_template_manager, state="disabled", style="Action.TButton", width=4); self.launch_capture_button.pack(side="left", padx=2, fill='x', expand=True)

    def create_correction_frame(self, parent):
        # (Se colocará en row 2 del panel izquierdo)
        self.correction_frame = ttk.LabelFrame(parent, text="Corrección Manual", padding=(10, 5)); self.correction_frame.grid_columnconfigure(1, weight=1)
        ttk.Label(self.correction_frame, text="Estado Correcto:").grid(row=0, column=0, padx=5, pady=5, sticky="w"); self.correct_state_var = tk.StringVar()
        self.correct_state_combo = ttk.Combobox(self.correction_frame, textvariable=self.correct_state_var, width=30, state="readonly", style="TCombobox")
        self.correct_state_combo.grid(row=0, column=1, padx=5, pady=5, sticky="ew"); self.correct_state_combo.bind("<<ComboboxSelected>>", self.on_correct_state_selected)
        self.log_correction_button = ttk.Button(self.correction_frame, text="Reg. Log", command=self.log_correct_state, style="Action.TButton"); self.log_correction_button.grid(row=0, column=2, padx=5, pady=5)

    def create_ocr_details_frame(self, parent):
        # (Se colocará en row 2 del panel izquierdo)
        self.ocr_frame = ttk.LabelFrame(parent, text="Detalles y Edición OCR", padding=(10, 5)); self.ocr_frame.grid_rowconfigure(1, weight=1); self.ocr_frame.grid_columnconfigure(0, weight=1)
        ttk.Label(self.ocr_frame, text="Resultados OCR:").grid(row=0, column=0, columnspan=3, padx=5, pady=2, sticky="w")
        tree_frame = ttk.Frame(self.ocr_frame); tree_frame.grid(row=1, column=0, columnspan=3, padx=5, pady=5, sticky="nsew"); tree_frame.grid_rowconfigure(0, weight=1); tree_frame.grid_columnconfigure(0, weight=1)
        self.ocr_tree = ttk.Treeview(tree_frame, columns=("RegionIdx", "Extracted", "Expected", "Match"), show="headings", height=4); self.ocr_tree.heading("RegionIdx", text="#", anchor="c"); self.ocr_tree.column("RegionIdx", width=30, anchor="c", stretch=tk.NO)
        self.ocr_tree.heading("Extracted", text="Extraído"); self.ocr_tree.column("Extracted", width=150, stretch=tk.YES); self.ocr_tree.heading("Expected", text="Esperado"); self.ocr_tree.column("Expected", width=150, stretch=tk.YES)
        self.ocr_tree.heading("Match", text="OK?", anchor="c"); self.ocr_tree.column("Match", width=30, anchor="c", stretch=tk.NO); self.ocr_tree.grid(row=0, column=0, sticky="nsew")
        ocr_scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.ocr_tree.yview); ocr_scrollbar.grid(row=0, column=1, sticky="ns"); self.ocr_tree['yscrollcommand'] = ocr_scrollbar.set; self.ocr_tree.bind("<<TreeviewSelect>>", self.on_ocr_tree_select)
        ttk.Label(self.ocr_frame, text="Texto Esperado (p/ Sel, '|'):").grid(row=2, column=0, columnspan=3, padx=5, pady=(5, 2), sticky="w"); self.ocr_edit_var = tk.StringVar()
        self.ocr_edit_entry = ttk.Entry(self.ocr_frame, textvariable=self.ocr_edit_var, width=40, state="disabled"); self.ocr_edit_entry.grid(row=3, column=0, columnspan=3, padx=5, pady=2, sticky="ew")
        ocr_button_frame = ttk.Frame(self.ocr_frame); ocr_button_frame.grid(row=4, column=0, columnspan=3, pady=2); ocr_button_frame.grid_columnconfigure((0,1), weight=1)
        self.confirm_ocr_button = ttk.Button(ocr_button_frame, text="Confirmar Extraído", command=self.confirm_ocr_text, state="disabled", style="Action.TButton"); self.confirm_ocr_button.pack(side="left", padx=5, expand=True, fill='x')
        self.save_edited_button = ttk.Button(ocr_button_frame, text="Guardar Editado", command=self.save_edited_ocr_text, state="disabled", style="Action.TButton"); self.save_edited_button.pack(side="left", padx=5, expand=True, fill='x')

    def create_status_label(self, parent):
        # (Se coloca en row 3 del panel izquierdo)
        self.status_label_var = tk.StringVar(value="Listo."); status_frame = ttk.Frame(parent, height=25); status_frame.grid(row=3, column=0, padx=0, pady=(5, 0), sticky="ew"); status_frame.pack_propagate(False)
        status_label = ttk.Label(status_frame, textvariable=self.status_label_var, anchor="w"); status_label.pack(side="left", padx=5, pady=2); self.status_label_frame = status_frame

    def on_preview_resize(self, event=None):
        # (Llama a show_tester_preview)
        self.show_tester_preview(state_name=self.current_template_name) # Mostrar el estado actual

    def _populate_correction_combobox(self):
        # (Sin cambios)
        try: mapping=self.recognizer.template_names_mapping; names=sorted(list(mapping.keys())); self.correct_state_combo['values']=names;
             if names: self.correct_state_var.set(""); logging.info(f"Combo corrección: {len(names)} st.")
        except Exception as e: logging.error(f"Error poblar combo: {e}"); self.correct_state_combo['values']=[]

    def reload_recognizer_data(self):
        # (Llama a show_tester_preview para limpiar)
        self.status_message("Recargando datos..."); self.update_idletasks()
        try: self.recognizer.reload_data(); self._populate_correction_combobox(); self.status_message("Datos recargados."); logging.info("Datos recargados OK.")
             self.reset_ui_state() # Resetear UI
        except Exception as e: logging.error(f"Error recarga: {e}", exc_info=True); messagebox.showerror("Error", f"Error recarga:\n{e}"); self.status_message("Error recarga.")

    def reset_ui_state(self):
        # (Controla visibilidad de frames en row 2 del panel izquierdo)
        self.method_var.set("N/A"); self.state_var.set("N/A"); self.confidence_var.set("N/A"); self.time_var.set("N/A"); self.roi_defined_var.set("N/A")
        self.last_recognition_result = None; self.current_template_name = None; self.confirm_button.config(state="disabled"); self.deny_button.config(state="disabled")
        self.roi_button.config(state="disabled"); self.remove_roi_button.config(state="disabled"); self.launch_capture_button.config(state="disabled")
        self.correction_frame.grid_forget(); self.ocr_frame.grid_forget() # Ocultar frames en row 2
        for item in self.ocr_tree.get_children(): self.ocr_tree.delete(item)
        self.ocr_edit_var.set(""); self.ocr_edit_entry.config(state="disabled"); self.confirm_ocr_button.config(state="disabled"); self.save_edited_button.config(state="disabled")
        self.correct_state_var.set("")
        self.show_tester_preview(clear=True) # Limpiar preview

    def run_test(self):
        self.status_message("Reconociendo..."); self.reset_ui_state(); self.test_button.config(state="disabled"); self.reload_button.config(state="disabled"); self.update_idletasks();
        start_time = time.time(); result = None;

        # Capturar pantalla una vez para preview
        current_screenshot = self.recognizer.capture_screen()
        if current_screenshot is None: messagebox.showerror("Error Captura","No captura para rec."); self.status_message("Error captura."); self.test_button.config(state="normal"); self.reload_button.config(state="normal"); return
        self.current_preview_image_cv = current_screenshot

        try:
            # *** NOTA: Idealmente modificar ScreenRecognizer para aceptar imagen ***
            result = self.recognizer.recognize_screen_for_test() # Aún hace captura interna
            self.last_recognition_result = result
            # Añadir la captura hecha para preview al resultado
            if result: result['screenshot'] = self.current_preview_image_cv
            else: result = {'screenshot': self.current_preview_image_cv} # Si result es None

        except Exception as e: logging.error(f"Error test: {e}", exc_info=True); messagebox.showerror("Error", f"Error Rec:\n{e}"); result = {'method': 'error', 'state': 'error', 'screenshot': self.current_preview_image_cv}
        finally: self.test_button.config(state="normal"); self.reload_button.config(state="normal")

        detection_time = result.get('detection_time_s', time.time() - start_time); method = str(result.get('method', 'unknown')).upper(); state = str(result.get('state', 'unknown'))
        conf_val = result.get('confidence'); conf_str = f"{conf_val:.3f}" if conf_val is not None else "N/A"; time_str = f"{detection_time:.3f} seg"
        self.method_var.set(method); self.state_var.set(state if state != 'unknown' else 'N/A'); self.confidence_var.set(conf_str); self.time_var.set(time_str)
        log_data = result.copy(); log_data.pop('screenshot', None); logging.info(f"Resultado: {json.dumps(log_data, ensure_ascii=False)}")

        self.correction_frame.grid_forget(); self.ocr_frame.grid_forget() # Ocultar por defecto
        if state != 'unknown' and state != 'error':
            self.current_template_name = state; self.confirm_button.config(state="normal"); self.deny_button.config(state="normal"); self.roi_button.config(state="normal"); self.update_roi_label(state)
            if result.get('method') == 'ocr':
                 self.ocr_frame.grid(row=2, column=0, padx=0, pady=5, sticky="nsew"); self.populate_ocr_tree(result.get('ocr_results')); self.confirm_ocr_button.config(state="normal"); self.save_edited_button.config(state="normal")
                 self.status_message(f"OCR: '{state}'. Valida/Edita/ROI.")
            else: self.status_message(f"Template: '{state}'. Valida/ROI.")
        else:
            self.current_template_name = None; self.roi_defined_var.set("N/A")
            self.correction_frame.grid(row=2, column=0, padx=0, pady=5, sticky="ew"); self.launch_capture_button.config(state="normal")
            msg = "ERROR." if state == 'error' else "NO RECONOCIDO."; self.status_message(f"{msg} Corrige/ROI/Gestor.")
            self.confirm_button.config(state="disabled"); self.deny_button.config(state="disabled"); self.roi_button.config(state="normal"); self.remove_roi_button.config(state="disabled") # Habilitar ROI para corregido

        # Actualizar preview con el resultado completo (incluye screenshot)
        self.show_tester_preview(result=result, state_name=state if state not in ['unknown', 'error'] else None)


    # --- MÉTODO PREVIEW ACTUALIZADO Y CORREGIDO ---
    def show_tester_preview(self, result=None, state_name=None, clear=False):
        """Muestra imagen de plantilla (si state_name) o captura (si result) y datos."""
        self.preview_canvas.delete("all"); self.tk_img_preview = None
        preview_image_cv = None
        is_template_preview = False # Flag para saber si mostramos plantilla o captura

        if clear:
            self.current_preview_image_cv = None # Limpiar imagen base
        elif state_name: # Priorizar mostrar plantilla si se pide estado específico
             # --- Cargar imagen de plantilla ---
             template_image_rgb = None; filename_used = None
             img_files = self.recognizer.template_names_mapping.get(state_name, [])
             if img_files:
                 filename_used = img_files[0]
                 res_dir = os.path.join(IMAGES_DIR, self.recognizer.resolution)
                 img_path = os.path.join(res_dir if os.path.exists(res_dir) else IMAGES_DIR, filename_used)
                 if os.path.exists(img_path):
                     try: img_bgr = cv2.imread(img_path);
                         if img_bgr is not None: template_image_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
                         else: raise Exception(f"imread None: {img_path}")
                     except Exception as e: logging.error(f"Error cargando preview '{img_path}': {e}")
                 else: logging.warning(f"Preview no encontrado: {img_path}")
             else: logging.warning(f"No imágenes para '{state_name}'.")

             if template_image_rgb is not None:
                  preview_image_cv = cv2.cvtColor(template_image_rgb, cv2.COLOR_RGB2BGR) # Convertir a BGR para consistencia
                  self.current_preview_image_cv = preview_image_cv # Guardar imagen base
                  is_template_preview = True
             else:
                  # Si no se pudo cargar la plantilla, limpiar
                  clear = True
        elif result and result.get('screenshot') is not None: # Mostrar captura si no se pidió plantilla
            preview_image_cv = result.get('screenshot')
            self.current_preview_image_cv = preview_image_cv
        elif self.current_preview_image_cv is not None: # Reusar la última captura si no hay nada nuevo
             preview_image_cv = self.current_preview_image_cv
        else: # Si no hay nada que mostrar
            clear = True

        # --- Dibujar ---
        canvas_w=self.preview_canvas.winfo_width(); canvas_h=self.preview_canvas.winfo_height(); canvas_w=max(canvas_w,MIN_PREVIEW_WIDTH); canvas_h=max(canvas_h,MIN_PREVIEW_HEIGHT)
        self.preview_canvas.config(width=canvas_w,height=canvas_h)

        if clear or preview_image_cv is None:
            self.preview_canvas.create_text(canvas_w/2, canvas_h/2, text="Sin Preview" if clear else "Error Imagen", fill="darkgrey", font=self.default_font); return

        try:
            monitor_info = self.recognizer._get_monitor_region();
            if not monitor_info: raise Exception("No monitor info.")
            img_rgb = cv2.cvtColor(preview_image_cv, cv2.COLOR_BGR2RGB); img_pil = Image.fromarray(img_rgb); img_w, img_h = img_pil.size
            scale = min(canvas_w / img_w, canvas_h / img_h, 1.0); nw = int(img_w*scale); nh = int(img_h*scale); nw=max(1,nw); nh=max(1,nh)
            try: resample = Image.Resampling.LANCZOS
            except AttributeError: resample = Image.ANTIALIAS
            img_pil_resized = img_pil.resize((nw, nh), resample); draw = ImageDraw.Draw(img_pil_resized, "RGBA")

            # --- Dibujar overlays (Solo si tenemos un resultado válido) ---
            if result:
                # Dibujar Regiones OCR (si el método fue OCR)
                if result.get('method') == 'ocr' and result.get('ocr_results'):
                    for ocr_data in result['ocr_results'].values():
                        if not isinstance(ocr_data,dict): continue
                        ocr_rect_abs = ocr_data.get('region'); if not ocr_rect_abs: continue
                        # Calcular relativo a la captura (asumiendo que preview_image_cv es captura completa)
                        rel_l=max(0,ocr_rect_abs['left']-monitor_info['left']); rel_t=max(0,ocr_rect_abs['top']-monitor_info['top'])
                        rel_w=ocr_rect_abs['width']; rel_h=ocr_rect_abs['height']; rel_w=min(rel_w,img_w-rel_l); rel_h=min(rel_h,img_h-rel_t)
                        if rel_w<=0 or rel_h<=0: continue
                        # Escalar a canvas
                        c_l=int(rel_l*scale); c_t=int(rel_t*scale); c_w=int(rel_w*scale); c_h=int(rel_h*scale); c_l=max(0,c_l); c_t=max(0,c_t)
                        color="cyan" if ocr_data.get('match_expected') else "magenta"; draw.rectangle([c_l,c_t,c_l+c_w,c_t+c_h],outline=color,width=2)
                        text=ocr_data.get('text','');
                        if text: tx,ty=c_l+2,c_t-PREVIEW_NUMBER_FONT_SIZE-2; if ty<0: ty=c_t+c_h+2
                            try: bbox=draw.textbbox((tx,ty),text[:30],font=self.preview_font); draw.rectangle(bbox,fill=(64,64,64,180)); draw.text((tx,ty),text[:30],fill="yellow",font=self.preview_font)
                            except Exception as de: logging.warning(f"Error draw text: {de}")

                # Dibujar ROI (si está definido para el estado detectado/corregido)
                current_display_state = state_name if state_name else self.current_template_name # Estado que estamos mostrando
                if current_display_state and current_display_state in self.recognizer.state_rois:
                     roi_abs = self.recognizer.state_rois[current_display_state]
                     rel_l=max(0,roi_abs['left']-monitor_info['left']); rel_t=max(0,roi_abs['top']-monitor_info['top'])
                     rel_w=roi_abs['width']; rel_h=roi_abs['height']; rel_w=min(rel_w,img_w-rel_l); rel_h=min(rel_h,img_h-rel_t)
                     if rel_w > 0 and rel_h > 0:
                         c_l=int(rel_l*scale); c_t=int(rel_t*scale); c_w=int(rel_w*scale); c_h=int(rel_h*scale)
                         # Solo dibujar si estamos mostrando la captura, no sobre la plantilla
                         if not is_template_preview:
                              draw.rectangle([c_l,c_t,c_l+c_w,c_t+c_h],outline="yellow",width=3,dash=(4,2))
                              try: draw.text((c_l+2,c_t+2),"ROI",fill="yellow",font=self.preview_font)
                              except Exception: pass
            # -----------------------------------------------------------

            # Mostrar imagen final
            self.tk_img_preview=ImageTk.PhotoImage(img_pil_resized); xo=(canvas_w-nw)//2; yo=(canvas_h-nh)//2
            self.preview_canvas.create_image(xo,yo,anchor="nw",image=self.tk_img_preview); self.preview_canvas.image=self.tk_img_preview

        except Exception as e:
            logging.error(f"Error al actualizar preview: {e}", exc_info=True); self.status_message("Error generando preview.")
            cw=self.preview_canvas.winfo_width(); ch=self.preview_canvas.winfo_height(); cw=max(cw,MIN_PREVIEW_WIDTH); ch=max(ch,MIN_PREVIEW_HEIGHT)
            self.preview_canvas.create_text(cw/2,ch/2,text="Error Preview",fill="red",font=self.default_font)

    # --- Resto de métodos (pegados y verificados) ---
    def on_correct_state_selected(self, event=None):
        selected_state = self.correct_state_var.get()
        if selected_state: self.current_template_name=selected_state; self.update_roi_label(selected_state); self.show_tester_preview(state_name=selected_state)
        else: self.show_tester_preview(clear=True)

    def populate_ocr_tree(self, ocr_results):
       for item in self.ocr_tree.get_children(): self.ocr_tree.delete(item)
       if ocr_results and isinstance(ocr_results, dict):
           for idx, data in sorted(ocr_results.items()):
               if isinstance(data,dict): extracted=data.get('text',"");exp_list=data.get('expected',[]);exp_str="|".join(exp_list) if exp_list else "";match_str="Sí" if data.get('match_expected') else "No"; self.ocr_tree.insert("",tk.END,iid=idx,values=(idx,extracted,exp_str,match_str))
               else: logging.warning(f"Formato OCR idx {idx}: {data}")
       else: self.ocr_tree.insert("",tk.END,values=("N/A","No res. OCR.","","N/A"))

    def on_ocr_tree_select(self, event=None):
        sel=self.ocr_tree.selection();
        if sel: item=sel[0];vals=self.ocr_tree.item(item,'values');
            if vals: self.ocr_edit_var.set(vals[2]);self.ocr_edit_entry.config(state="normal")
            else: self.ocr_edit_entry.config(state="disabled");self.ocr_edit_var.set("")
        else: self.ocr_edit_entry.config(state="disabled");self.ocr_edit_var.set("")

    def confirm_detection(self):
       state=self.state_var.get();
       if state!="N/A" and self.last_recognition_result and self.last_recognition_result.get('state') not in ['unknown','error']:
           actual=self.last_recognition_result['state'];logging.info(f"CONFIRMACIÓN: '{actual}' OK.");self.status_message(f"Detectado '{actual}' OK.")
           self.confirm_button.config(state="disabled");self.deny_button.config(state="disabled");self.launch_capture_button.config(state="disabled")
           self.correction_frame.grid_forget();
           if self.method_var.get()!="OCR": self.ocr_frame.grid_forget()
       else: messagebox.showwarning("Inválido","No detección válida.")

    def deny_detection(self):
       state=self.last_recognition_result['state'] if self.last_recognition_result and self.last_recognition_result['state']!='unknown' else "unknown"
       logging.warning(f"NEGACIÓN: '{state}' INCORRECTA.");self.status_message(f"Negada '{state}'. Corrige/ROI/Gestor.")
       self.confirm_button.config(state="disabled");self.deny_button.config(state="disabled")
       self.correction_frame.grid(row=2, column=0, padx=0, pady=5, sticky="ew");self._populate_correction_combobox();self.correct_state_var.set("")
       self.launch_capture_button.config(state="normal");self.roi_button.config(state="normal");self.remove_roi_button.config(state="normal")
       self.ocr_frame.grid_forget()
       self.show_tester_preview(clear=True) # Limpiar preview

    def log_correct_state(self):
       correct=self.correct_state_var.get();last=self.last_recognition_result['state'] if self.last_recognition_result and self.last_recognition_result['state']!='unknown' else "unknown"
       if not correct: messagebox.showwarning("Vacío","Selecciona estado."); return
       logging.info(f"CORRECCIÓN: Detectado '{last}', Correcto: '{correct}'.");self.status_message(f"Corrección log: '{correct}'.");self.current_template_name=correct
       self.update_roi_label(correct)
       self.show_tester_preview(state_name=correct) # Actualizar preview

    def update_roi_label(self, state_name):
       if state_name and state_name in self.recognizer.state_rois: self.roi_defined_var.set(f"Sí"); self.remove_roi_button.config(state="normal")
       else: self.roi_defined_var.set("No"); self.remove_roi_button.config(state="disabled")

    def define_roi_for_state(self):
       # (Lógica de selección de estado corregida)
       state_to_edit=None;failed_or_denied=(not self.last_recognition_result or self.last_recognition_result.get('state') in ['unknown','error',None] or self.correction_frame.winfo_viewable())
       if failed_or_denied:
           state_to_edit=self.correct_state_var.get()
           if not state_to_edit: messagebox.showinfo("Requerido","Selecciona estado correcto primero."); return
           if not messagebox.askyesno("Confirmar",f"Definir ROI para estado corregido '{state_to_edit}'?"): self.status_message("ROI cancelado."); return
       else:
           state_to_edit=self.last_recognition_result['state']
           if not messagebox.askyesno("Confirmar",f"Def/Sobrescribir ROI para detectado '{state_to_edit}'?"): self.status_message("ROI cancelado."); return
       if not state_to_edit: self.status_message("Error: No estado para ROI."); return
       logging.info(f"Def ROI para: '{state_to_edit}'");self.status_message(f"Capturando ROI '{state_to_edit}'...");self.update_idletasks()
       self.withdraw();selected_roi=tk_select_roi(self,self.recognizer,state_to_edit);self.deiconify()
       if selected_roi:
            logging.info(f"ROI sel: {selected_roi}");all_rois=load_json_mapping(STATE_ROIS_FILE,"ROIs");all_rois[state_to_edit]=selected_roi
            if save_json_mapping(all_rois,STATE_ROIS_FILE,"ROIs"):
                 self.recognizer.reload_data();messagebox.showinfo("Éxito",f"ROI guardado '{state_to_edit}'.");self.status_message(f"ROI guardado '{state_to_edit}'.")
                 self.update_roi_label(state_to_edit);self.show_tester_preview(state_name=state_to_edit) # Actualizar preview
            else: logging.error(f"Fallo guardando {STATE_ROIS_FILE}");self.status_message(f"Error guardando ROI.")
       else: self.status_message(f"ROI cancelado/fallido.");logging.info(f"ROI cancelado/fallido.")

    def remove_roi_for_state(self):
        # (Llama a show_tester_preview para actualizar)
        state_mod=None;
        if self.last_recognition_result and self.last_recognition_result.get('state') not in ['unknown','error',None]: state_mod=self.last_recognition_result['state']
        elif self.current_template_name: state_mod=self.current_template_name
        if not state_mod: messagebox.showwarning("Sin Estado","No estado para eliminar ROI."); return
        all_rois=load_json_mapping(STATE_ROIS_FILE,"ROIs");
        if state_mod not in all_rois: messagebox.showinfo("Info",f"'{state_mod}' no tiene ROI.");self.update_roi_label(state_mod); return
        if messagebox.askyesno("Confirmar",f"¿Eliminar ROI para '{state_mod}'?"):
             logging.info(f"Eliminando ROI '{state_mod}'.");del all_rois[state_mod]
             if save_json_mapping(all_rois,STATE_ROIS_FILE,"ROIs"):
                 self.recognizer.reload_data();messagebox.showinfo("Éxito",f"ROI eliminado '{state_mod}'.");self.status_message(f"ROI eliminado '{state_mod}'.")
                 self.update_roi_label(state_mod);self.show_tester_preview(state_name=state_mod) # Actualizar preview
             else: logging.error(f"Fallo guardando {STATE_ROIS_FILE}");self.status_message(f"Error guardando tras elim ROI.")
        else: self.status_message("Elim ROI cancelada.")

    def ask_for_state_selection(self, prompt_message):
        # (Sin cambios)
        states=sorted(list(self.recognizer.template_names_mapping.keys()));
        if not states: messagebox.showerror("Error","No plantillas."); return None
        dialog=SelectStateDialog(self,title="Seleccionar Estado",prompt=prompt_message,states_list=states); return dialog.result

    def launch_template_manager(self):
        # (Sin cambios)
       logging.info(f"Lanzando Gestor: {TEMPLATE_MANAGER_SCRIPT_PATH}");self.status_message("Abriendo Gestor...");self.update_idletasks()
       try: process=subprocess.Popen([sys.executable,TEMPLATE_MANAGER_SCRIPT_PATH]);logging.info(f"Gestor PID: {process.pid}");self.status_message("Gestor abierto. **Recuerda 'Recargar Datos' aquí.**")
       except FileNotFoundError: logging.error(f"No script: {TEMPLATE_MANAGER_SCRIPT_PATH}");messagebox.showerror("Error",f"No script:\n{TEMPLATE_MANAGER_SCRIPT_PATH}");self.status_message("Error: script gestor falta.")
       except Exception as e: logging.error(f"Error lanzar gestor: {e}",exc_info=True);messagebox.showerror("Error",f"Error abrir gestor:\n{e}");self.status_message("Error abrir gestor.")

    def confirm_ocr_text(self):
        # (Sin cambios funcionales)
       if not self.last_recognition_result or self.last_recognition_result.get('method')!='ocr': messagebox.showwarning("Inválido","Acción solo OCR."); return
       selected=self.ocr_tree.selection(); state=self.last_recognition_result.get('state')
       if not selected: messagebox.showwarning("Vacío","Selecciona filas."); return
       if not state or state=='unknown': messagebox.showerror("Error","Estado OCR desconocido."); return
       results_map=self.last_recognition_result.get('ocr_results',{}); updates={};
       for item in selected:
           try: idx=int(item);
               if idx in results_map: txt=results_map[idx].get('text',"").strip();
                   if txt: updates[idx]=txt
                   else: logging.warning(f"Texto OCR vacío {idx}.")
               else: logging.warning(f"Índice {idx} no en res.")
           except(ValueError,TypeError): logging.error(f"ID inválido: {item}")
       if not updates: messagebox.showinfo("Info","No texto válido."); return
       if not messagebox.askyesno("Confirmar",f"¿Añadir {len(updates)} textos a esperados para '{state}'?"): self.status_message("Conf. OCR cancelada."); return
       all_ocr=load_json_mapping(OCR_MAPPING_FILE,"OCR"); count=0
       if state not in all_ocr or not isinstance(all_ocr.get(state),list): all_ocr[state]=[]
       r_list=all_ocr[state]
       for idx,txt in updates.items():
           coords=results_map[idx].get('region'); if not coords: continue
           found=False
           for i,entry in enumerate(r_list):
               if isinstance(entry,dict) and entry.get('region')==coords:
                   if 'expected_text' not in entry or not isinstance(entry['expected_text'],list): entry['expected_text']=[]
                   if not any(ex.lower()==txt.lower() for ex in entry['expected_text']): entry['expected_text'].append(txt); logging.info(f"Añadido '{txt}' r{idx}."); count+=1
                   else: logging.info(f"Texto '{txt}' ya existía r{idx}.")
                   found=True; break
           if not found: logging.warning(f"No entrada {coords}. Creando."); r_list.append({'region':coords,'expected_text':[txt]}); count+=1
       if count>0:
           if save_json_mapping(all_ocr,OCR_MAPPING_FILE,"OCR"): self.recognizer.reload_data(); logging.info(f"Actualizados {count} textos."); messagebox.showinfo("Éxito",f"Añadidos {count} textos."); self.status_message(f"Textos OCR actualizados."); self.refresh_ocr_tree_display()
           else: logging.error(f"Fallo {OCR_MAPPING_FILE}"); self.status_message("Error guardando OCR.")
       else: messagebox.showinfo("Sin Cambios","Textos ya presentes."); self.status_message("No cambios OCR.")

    def save_edited_ocr_text(self):
        # (Sin cambios funcionales)
       if not self.last_recognition_result or self.last_recognition_result.get('method')!='ocr': messagebox.showwarning("Inválido","Acción solo OCR."); return
       selected=self.ocr_tree.selection(); state=self.last_recognition_result.get('state')
       if not selected: messagebox.showwarning("Vacío","Selecciona filas."); return
       if not state or state=='unknown': messagebox.showerror("Error","Estado OCR desconocido."); return
       edited=self.ocr_edit_var.get().strip(); expected=[]
       if not edited:
           if not messagebox.askyesno("Confirmar Vacío","¿ELIMINAR textos esperados?"): self.status_message("Guardado editado cancelado."); return
           logging.info(f"Eliminando textos '{state}'.")
       else:
            expected=[t.strip() for t in edited.split('|') if t.strip()]
            if not expected: messagebox.showwarning("Inválido","Texto no válido."); return
       results_map=self.last_recognition_result.get('ocr_results',{}); coords_list=[]
       for item in selected:
            try: idx=int(item);
                if idx in results_map and 'region' in results_map[idx]: coords_list.append(results_map[idx]['region'])
                else: logging.warning(f"Índice {idx} inválido.")
            except(ValueError,TypeError): logging.error(f"ID inválido: {item}")
       if not coords_list: messagebox.showerror("Error","No coords."); return
       act_desc=f"poner textos a [{', '.join(expected)}]" if expected else "eliminar textos"
       if not messagebox.askyesno("Confirmar",f"¿{act_desc} para {len(coords_list)} regiones de '{state}'? (SOBREESCRIBE)"): self.status_message("Guardado editado cancelado."); return
       all_ocr=load_json_mapping(OCR_MAPPING_FILE,"OCR"); count=0
       if state not in all_ocr or not isinstance(all_ocr.get(state),list): all_ocr[state]=[]
       r_list=all_ocr[state]
       for i,entry in enumerate(r_list):
           if isinstance(entry,dict) and entry.get('region') in coords_list:
                try: entry['expected_text']=expected; logging.info(f"Actualizado texto coords {entry.get('region')} a {expected}"); count+=1
                except Exception as e: logging.error(f"Error update {i}: {e}"); messagebox.showerror("Error",f"Error update:\n{e}"); return
       if count>0:
           if save_json_mapping(all_ocr,OCR_MAPPING_FILE,"OCR"):
               self.recognizer.reload_data(); logging.info(f"Sobrescritos {count} textos."); messagebox.showinfo("Éxito",f"Textos guardados {count} regs."); self.status_message(f"Textos guardados.");
               self.ocr_edit_var.set(""); self.ocr_edit_entry.config(state="disabled"); self.ocr_tree.selection_remove(self.ocr_tree.selection()); self.refresh_ocr_tree_display()
           else: logging.error(f"Fallo {OCR_MAPPING_FILE}"); self.status_message("Error guardando textos editados.")
       else: logging.warning(f"No entradas para update."); messagebox.showwarning("Sin Cambios",f"No encontradas regiones sel.");

    def refresh_ocr_tree_display(self):
        # (Sin cambios funcionales)
       if not self.last_recognition_result or not self.last_recognition_result.get('ocr_results'): self.populate_ocr_tree(None); return
       state=self.last_recognition_result.get('state'); last_results=self.last_recognition_result.get('ocr_results',{})
       if not state or state=='unknown': self.populate_ocr_tree(None); return
       current_map=load_json_mapping(OCR_MAPPING_FILE,"OCR"); current_list=current_map.get(state,[])
       expected_map={json.dumps(e.get('region',{})):e.get('expected_text',[]) for e in current_list if isinstance(e,dict)}
       for item in self.ocr_tree.get_children(): self.ocr_tree.delete(item)
       if last_results:
            for idx, data in sorted(last_results.items()):
                if isinstance(data,dict):
                    extracted=data.get('text',""); coords=data.get('region'); key=json.dumps(coords) if coords else None
                    exp_list=expected_map.get(key,[]) if key else []; exp_str="|".join(exp_list) if exp_list else ""
                    match=False;
                    if extracted and exp_list:
                        if any(ex.lower()==extracted.lower() for ex in exp_list): match=True
                    match_str="Sí" if match else "No"
                    self.ocr_tree.insert("", tk.END, iid=idx, values=(idx, extracted, exp_str, match_str))
                else: logging.warning(f"Formato inesperado refresh: {data}")
       else: self.ocr_tree.insert("", tk.END, values=("N/A", "No res. OCR.", "", "N/A"))

    def status_message(self, message):
        # (Sin cambios)
       logging.info(f"Status GUI: {message}"); self.status_label_var.set(message); self.update_idletasks()


if __name__ == "__main__":
   try:
       for dir_path in [CONFIG_DIR, IMAGES_DIR, os.path.dirname(LOG_FILE_TESTER)]:
           if not os.path.exists(dir_path): logging.info(f"Creando: {dir_path}"); os.makedirs(dir_path)
       app = ScreenTesterGUI()
       app.mainloop()
   except Exception as main_e:
        logging.exception("Error fatal al iniciar ScreenTesterGUI.")
        try: messagebox.showerror("Error Fatal", f"No se pudo iniciar la aplicación:\n{main_e}")
        except: print(f"ERROR FATAL (no messagebox): {main_e}")

# --- END OF FILE screen_tester_gui ---