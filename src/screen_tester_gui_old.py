import os
import json
import datetime
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import cv2
# No necesitamos importar cv2, numpy, mss aquí directamente
from PIL import Image, ImageTk # Solo para tk_select_roi si se mantiene aquí
from tkinter import font
import time
import logging
import subprocess
import sys
import re # Importar re

# --- Importar lo necesario desde screen_recognizer ---
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
    CONFIG_DIR # Importar si es necesario para tk_select_roi
)

# --- Definir constantes locales ---
# DEFAULT_FONT_SIZE = 11 # Usar el importado
MIN_WINDOW_WIDTH = 850
MIN_WINDOW_HEIGHT = 750
MIN_CANVAS_WIDTH = 300
MIN_CANVAS_HEIGHT = 200
LOG_FILE = "tester_log.log"

# --- Configuración del Logging ---
# Configuración principal (igual que antes)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# Ruta al script de la GUI de gestión de plantillas
TEMPLATE_MANAGER_SCRIPT_PATH = os.path.join(PROJECT_DIR, "src", "template_manager_gui.py")


# --- Función tk_select_roi (Modificada para usar recognizer.capture_screen) ---
def tk_select_roi(root, recognizer_instance, state_name):
    """
    Permite al usuario seleccionar una Región de Interés (ROI) para un estado.
    Usa la instancia del recognizer para capturar la pantalla.
    """
    logging.info(f"Solicitando captura para definir ROI de '{state_name}'")
    # Usar el método capture_screen del recognizer para asegurar que usa el monitor correcto
    full_screen_image = recognizer_instance.capture_screen()
    if full_screen_image is None:
        messagebox.showerror("Error de Captura", "No se pudo capturar la pantalla completa para definir ROI.")
        return None

    orig_height, orig_width = full_screen_image.shape[:2]
    scale = 1.0
    max_display_width = root.winfo_screenwidth() * 0.8
    max_display_height = root.winfo_screenheight() * 0.8
    scale_w = max_display_width / orig_width if orig_width > max_display_width else 1.0
    scale_h = max_display_height / orig_height if orig_height > max_display_height else 1.0
    scale = min(scale_w, scale_h, 1.0) # No escalar más grande que 1.0

    if scale < 1.0:
         new_width = int(orig_width * scale)
         new_height = int(orig_height * scale)
         try: # Usar LANCZOS si está disponible
             resample_method = Image.Resampling.LANCZOS
             resized_img = cv2.resize(full_screen_image, (new_width, new_height), interpolation=cv2.INTER_LANCZOS4)
         except AttributeError:
             resample_method = Image.ANTIALIAS # Fallback
             resized_img = cv2.resize(full_screen_image, (new_width, new_height), interpolation=cv2.INTER_AREA) # INTER_AREA es bueno para reducir
    else:
        resized_img = full_screen_image.copy()

    # --- Resto de tk_select_roi (Ventana Toplevel, Canvas, Selección) ---
    # (Sin cambios significativos en la lógica interna, pero usando la imagen capturada)
    img_rgb = cv2.cvtColor(resized_img, cv2.COLOR_BGR2RGB)
    pil_img = Image.fromarray(img_rgb)
    tk_img = ImageTk.PhotoImage(pil_img)
    sel_win = tk.Toplevel(root)
    sel_win.title(f"Seleccione ROI para Estado: '{state_name}'")
    sel_win.grab_set()
    sel_win.geometry(f"{tk_img.width()+20}x{tk_img.height()+80}")
    canvas = tk.Canvas(sel_win, width=tk_img.width(), height=tk_img.height(), cursor="cross")
    canvas.pack(padx=5, pady=5, fill="both", expand=True)
    canvas.create_image(0, 0, anchor="nw", image=tk_img)
    selection = {"x1": None, "y1": None, "x2": None, "y2": None}
    rect = None
    confirmed_roi = None
    def on_button_press(event):
        selection["x1"] = event.x; selection["y1"] = event.y
        nonlocal rect
        if rect: canvas.delete(rect)
        rect = canvas.create_rectangle(event.x, event.y, event.x, event.y, outline="orange", width=3)
    def on_move_press(event):
        if rect: canvas.coords(rect, selection["x1"], selection["y1"], event.x, event.y)
    def on_button_release(event):
        if rect: selection["x2"] = event.x; selection["y2"] = event.y
    canvas.bind("<ButtonPress-1>", on_button_press)
    canvas.bind("<B1-Motion>", on_move_press)
    canvas.bind("<ButtonRelease-1>", on_button_release)
    button_frame = ttk.Frame(sel_win)
    button_frame.pack(pady=10)
    def confirm_selection():
        nonlocal confirmed_roi
        if None not in (selection["x1"], selection["y1"], selection["x2"], selection["y2"]):
            x1, y1, x2, y2 = selection["x1"], selection["y1"], selection["x2"], selection["y2"]
            left_r, top_r, w_r, h_r = int(min(x1, x2)), int(min(y1, y2)), int(abs(x2-x1)), int(abs(y2-y1))
            # Convertir a coords originales - OBTENER monitor_info DESDE LA INSTANCIA DEL RECOGNIZER
            monitor_info = recognizer_instance.monitors_info[recognizer_instance.monitor_index]
            left_orig = monitor_info['left'] + int(left_r / scale)
            top_orig = monitor_info['top'] + int(top_r / scale)
            width_orig = int(w_r / scale)
            height_orig = int(h_r / scale)
            # Asegurar que las coordenadas no sean negativas o el ancho/alto cero
            width_orig = max(1, width_orig)
            height_orig = max(1, height_orig)
            confirmed_roi = {"left": left_orig, "top": top_orig, "width": width_orig, "height": height_orig}
        sel_win.destroy()
    def cancel_selection(): sel_win.destroy()
    confirm_btn = ttk.Button(button_frame, text="Guardar ROI", command=confirm_selection)
    confirm_btn.pack(side="left", padx=5)
    cancel_btn = ttk.Button(button_frame, text="Cancelar", command=cancel_selection)
    cancel_btn.pack(side="left", padx=5)
    sel_win.bind("<Escape>", lambda e: cancel_selection()) # Cancelar con Escape
    root.wait_window(sel_win)
    return confirmed_roi


class ScreenTesterGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Tester Interactivo - Screen Recognizer")
        self.minsize(MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT)
        self.ocr_regions = [] # El tester no maneja esto directamente
        self.ocr_region_rects = []
        self.current_template_name = None
        self.last_recognition_result = None

        self.recognizer = ScreenRecognizer(monitor=1, threshold=0.75, ocr_fallback_threshold=0.65)
        self.monitors_info = self.recognizer.monitors_info # Obtener de la instancia

        self.setup_fonts_and_styles()
        self.create_widgets()
        # self.load_last_image_source() # Ya no es necesario aquí
        self._populate_correction_combobox() # Poblar después de crear widgets
        logging.info("Tester GUI inicializado.")

    def setup_fonts_and_styles(self):
        """Configura la fuente y los estilos ttk."""
        self.default_font = font.nametofont("TkDefaultFont")
        self.default_font.configure(size=DEFAULT_FONT_SIZE)
        style = ttk.Style(self)
        style.configure('.', font=self.default_font)
        style.configure('TLabelframe.Label', font=(self.default_font.actual()['family'], DEFAULT_FONT_SIZE, 'bold'))
        style.configure("Result.TLabel", font=(self.default_font.actual()['family'], DEFAULT_FONT_SIZE + 1, 'bold'))
        style.configure("Confirm.TButton", font=self.default_font)
        style.configure("Deny.TButton", font=self.default_font)

    def create_widgets(self):
        """Crea todos los widgets de la interfaz."""
        self.grid_rowconfigure(3, weight=1) # Fila OCR/Corrección se expande
        self.grid_columnconfigure(0, weight=1)

        self.create_control_frame()
        self.create_result_frame()
        self.create_correction_frame()
        self.create_ocr_details_frame()
        self.create_status_label()

    def create_control_frame(self):
        """Crea el frame con los botones de control."""
        control_frame = ttk.LabelFrame(self, text="Control", padding=(10, 5))
        control_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        control_frame.grid_columnconfigure(0, weight=1); control_frame.grid_columnconfigure(1, weight=1)

        self.test_button = ttk.Button(control_frame, text="Reconocer Pantalla Actual", command=self.run_test)
        self.test_button.grid(row=0, column=0, pady=5, padx=5, sticky="e")
        self.reload_button = ttk.Button(control_frame, text="Recargar Datos Reconocedor", command=self.reload_recognizer_data)
        self.reload_button.grid(row=0, column=1, pady=5, padx=5, sticky="w")

    def create_result_frame(self):
        """Crea el frame para mostrar los resultados y botones de acción."""
        result_frame = ttk.LabelFrame(self, text="Resultado del Reconocimiento", padding=(10, 5))
        result_frame.grid(row=1, column=0, padx=10, pady=5, sticky="ew")
        result_frame.grid_columnconfigure(1, weight=1)

        ttk.Label(result_frame, text="Método:").grid(row=0, column=0, padx=5, pady=2, sticky="w")
        self.method_var = tk.StringVar(value="N/A")
        ttk.Label(result_frame, textvariable=self.method_var, style="Result.TLabel").grid(row=0, column=1, padx=5, pady=2, sticky="w")
        ttk.Label(result_frame, text="Estado Detectado:").grid(row=1, column=0, padx=5, pady=2, sticky="w")
        self.state_var = tk.StringVar(value="N/A")
        ttk.Label(result_frame, textvariable=self.state_var, style="Result.TLabel").grid(row=1, column=1, padx=5, pady=2, sticky="w")
        ttk.Label(result_frame, text="Confianza (Template):").grid(row=2, column=0, padx=5, pady=2, sticky="w")
        self.confidence_var = tk.StringVar(value="N/A")
        ttk.Label(result_frame, textvariable=self.confidence_var).grid(row=2, column=1, padx=5, pady=2, sticky="w")
        ttk.Label(result_frame, text="Tiempo Detección:").grid(row=3, column=0, padx=5, pady=2, sticky="w")
        self.time_var = tk.StringVar(value="N/A")
        ttk.Label(result_frame, textvariable=self.time_var).grid(row=3, column=1, padx=5, pady=2, sticky="w")
        ttk.Label(result_frame, text="ROI Definido:").grid(row=4, column=0, padx=5, pady=2, sticky="w")
        self.roi_defined_var = tk.StringVar(value="N/A")
        ttk.Label(result_frame, textvariable=self.roi_defined_var).grid(row=4, column=1, padx=5, pady=2, sticky="w")

        validation_frame = ttk.Frame(result_frame)
        validation_frame.grid(row=5, column=0, columnspan=2, pady=5)
        self.confirm_button = ttk.Button(validation_frame, text="👍 Confirmar", style="Confirm.TButton", command=self.confirm_detection, state="disabled")
        self.confirm_button.pack(side="left", padx=5)
        self.deny_button = ttk.Button(validation_frame, text="👎 Negar", style="Deny.TButton", command=self.deny_detection, state="disabled")
        self.deny_button.pack(side="left", padx=5)
        self.roi_button = ttk.Button(validation_frame, text="Definir/Editar ROI", command=self.define_roi_for_state, state="disabled")
        self.roi_button.pack(side="left", padx=5)
        self.launch_capture_button = ttk.Button(validation_frame, text="Abrir Gestor", command=self.launch_template_manager, state="disabled")
        self.launch_capture_button.pack(side="left", padx=5)

    def create_correction_frame(self):
        """Crea el frame para la corrección manual (inicialmente oculto)."""
        self.correction_frame = ttk.LabelFrame(self, text="Corrección Manual", padding=(10, 5))
        self.correction_frame.grid_columnconfigure(1, weight=1)
        # No hacer grid aquí

        ttk.Label(self.correction_frame, text="Estado Correcto:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.correct_state_var = tk.StringVar()
        self.correct_state_combo = ttk.Combobox(self.correction_frame, textvariable=self.correct_state_var, width=35, state="readonly")
        self.correct_state_combo.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        self.log_correction_button = ttk.Button(self.correction_frame, text="Registrar Corrección", command=self.log_correct_state)
        self.log_correction_button.grid(row=0, column=2, padx=10, pady=5)

    def create_ocr_details_frame(self):
        """Crea el frame para detalles y edición OCR (inicialmente oculto)."""
        self.ocr_frame = ttk.LabelFrame(self, text="Detalles y Edición OCR", padding=(10, 5))
        self.ocr_frame.grid_rowconfigure(1, weight=1)
        self.ocr_frame.grid_columnconfigure(0, weight=1)
        # No hacer grid aquí

        ttk.Label(self.ocr_frame, text="Resultados OCR por Región:").grid(row=0, column=0, columnspan=3, padx=5, pady=2, sticky="w")
        self.ocr_tree = ttk.Treeview(self.ocr_frame, columns=("RegionIdx", "Extracted", "Expected", "Match"), show="headings", height=5)
        self.ocr_tree.heading("RegionIdx", text="#"); self.ocr_tree.column("RegionIdx", width=40, anchor="center", stretch=tk.NO)
        self.ocr_tree.heading("Extracted", text="Texto Extraído"); self.ocr_tree.column("Extracted", width=200)
        self.ocr_tree.heading("Expected", text="Texto Esperado"); self.ocr_tree.column("Expected", width=200)
        self.ocr_tree.heading("Match", text="Coincide"); self.ocr_tree.column("Match", width=60, anchor="center", stretch=tk.NO)
        self.ocr_tree.grid(row=1, column=0, columnspan=2, padx=5, pady=5, sticky="nsew")
        ocr_scrollbar = ttk.Scrollbar(self.ocr_frame, orient="vertical", command=self.ocr_tree.yview)
        ocr_scrollbar.grid(row=1, column=2, sticky="ns")
        self.ocr_tree['yscrollcommand'] = ocr_scrollbar.set

        ttk.Label(self.ocr_frame, text="Texto Esperado (p/ Selección, separar con '|'):").grid(row=2, column=0, columnspan=3, padx=5, pady=2, sticky="w")
        self.ocr_edit_var = tk.StringVar()
        self.ocr_edit_entry = ttk.Entry(self.ocr_frame, textvariable=self.ocr_edit_var, width=60)
        self.ocr_edit_entry.grid(row=3, column=0, columnspan=3, padx=5, pady=5, sticky="ew")

        ocr_button_frame = ttk.Frame(self.ocr_frame)
        ocr_button_frame.grid(row=4, column=0, columnspan=3, pady=5)
        self.confirm_ocr_button = ttk.Button(ocr_button_frame, text="Confirmar Texto(s) Extraído(s) p/ Selección", command=self.confirm_ocr_text)
        self.confirm_ocr_button.pack(side="left", padx=10)
        self.save_edited_button = ttk.Button(ocr_button_frame, text="Guardar Texto Editado p/ Selección", command=self.save_edited_ocr_text)
        self.save_edited_button.pack(side="left", padx=10)

    def create_status_label(self):
        """Crea el label para mensajes de estado."""
        self.status_label_var = tk.StringVar(value="Listo. Inicia el juego y pulsa 'Reconocer Pantalla'.")
        self.status_label = ttk.Label(self, textvariable=self.status_label_var, anchor="w")
        self.status_label.grid(row=4, column=0, padx=10, pady=(5, 10), sticky="ew") # Fila 4 inicial

    def _populate_correction_combobox(self):
        """Llena el combobox de corrección con los nombres ordenados."""
        try:
            mapping = self.recognizer.template_names_mapping
            template_names = sorted(list(mapping.keys()))
            self.correct_state_combo['values'] = template_names
        except Exception as e:
            logging.error(f"Error al poblar combobox de corrección: {e}")
            self.correct_state_combo['values'] = []

    def reload_recognizer_data(self):
        """Llama al método de recarga del reconocedor."""
        self.status_message("Recargando datos del reconocedor...")
        try:
            self.recognizer.reload_data()
            self._populate_correction_combobox()
            self.status_message("Datos del reconocedor recargados.")
            logging.info("Datos del reconocedor recargados manualmente.")
        except AttributeError:
             logging.error("Intento de recarga fallido: método reload_data() no encontrado en ScreenRecognizer.")
             messagebox.showerror("Error", "La clase ScreenRecognizer no tiene el método 'reload_data'.")
        except Exception as e:
             logging.error(f"Error al recargar datos: {e}")
             messagebox.showerror("Error", f"Error al recargar datos: {e}")

    def run_test(self):
        """Ejecuta el reconocimiento y actualiza la GUI."""
        self.status_message("Reconociendo pantalla...")
        self.confirm_button.config(state="disabled")
        self.deny_button.config(state="disabled")
        self.roi_button.config(state="disabled")
        self.launch_capture_button.config(state="disabled")
        self.ocr_frame.grid_forget()
        self.correction_frame.grid_forget()
        self.roi_defined_var.set("N/A")

        start_time = time.time()
        self.last_recognition_result = self.recognizer.recognize_screen_for_test()
        end_time = time.time()
        detection_time = end_time - start_time

        result = self.last_recognition_result
        method = result['method'].upper() if result['method'] != 'unknown' else 'Desconocido'
        state = result['state'] if result['state'] != 'unknown' else 'N/A'
        confidence = f"{result['confidence']:.3f}" if result['confidence'] is not None else "N/A"
        time_str = f"{detection_time:.3f} seg"

        self.method_var.set(method)
        self.state_var.set(state)
        self.confidence_var.set(confidence)
        self.time_var.set(time_str)

        log_data = result.copy(); log_data['detection_time_s'] = detection_time
        logging.info(f"Resultado Reconocimiento: {log_data}")

        for item in self.ocr_tree.get_children(): self.ocr_tree.delete(item)
        self.ocr_edit_var.set("")

        status_row = 2 # Fila por defecto para status

        if result['state'] != 'unknown':
            self.confirm_button.config(state="normal")
            self.deny_button.config(state="normal")
            self.roi_button.config(state="normal")

            roi_status = "Sí" if state in self.recognizer.state_rois else "No"
            self.roi_defined_var.set(roi_status)

            if result['method'] == 'ocr':
                 self.ocr_frame.grid(row=2, column=0, padx=10, pady=5, sticky="nsew")
                 status_row = 3
                 self.populate_ocr_tree(result['ocr_results'])
                 self.confirm_ocr_button.config(state="normal")
                 self.save_edited_button.config(state="normal")
                 self.ocr_edit_entry.config(state="normal")
                 self.status_message("Reconocido por OCR. Valida, edita texto o define/edita ROI.")
            else: # Template
                self.status_message(f"Reconocido por Template. Valida o define/edita ROI.")
                # status_row se queda en 2
        else: # No reconocido
            self.launch_capture_button.config(state="normal")
            self.correction_frame.grid(row=2, column=0, padx=10, pady=5, sticky="ew")
            status_row = 3
            self.status_message("Pantalla NO RECONOCIDA. Selecciona la correcta o abre el gestor.")

        self.status_label.grid(row=status_row, column=0, padx=10, pady=(5, 10), sticky="ew")

    def populate_ocr_tree(self, ocr_results):
        """Llena el Treeview con los resultados detallados del OCR."""
        for item in self.ocr_tree.get_children(): self.ocr_tree.delete(item)
        if ocr_results:
            for idx, data in ocr_results.items():
                extracted = data['text']; expected_list = data.get('expected', [])
                expected_str = "|".join(expected_list)
                match_str = "Sí" if data.get('match_expected') else "No"
                self.ocr_tree.insert("", tk.END, values=(idx, extracted, expected_str, match_str))
        else: self.ocr_tree.insert("", tk.END, values=("N/A", "No resultados.", "", "N/A"))

    def confirm_detection(self):
        """Registra la confirmación del usuario."""
        detected_state = self.state_var.get()
        if detected_state != "N/A":
            logging.info(f"CONFIRMACIÓN USUARIO: Detección de '{detected_state}' es CORRECTA.")
            self.status_message(f"Detección de '{detected_state}' confirmada.")
            # Deshabilitar botones de acción
            self.confirm_button.config(state="disabled")
            self.deny_button.config(state="disabled")
            self.roi_button.config(state="disabled")
            self.launch_capture_button.config(state="disabled")
            # Ocultar frames adicionales
            self.correction_frame.grid_forget()
            self.ocr_frame.grid_forget()
            self.status_label.grid(row=2, column=0, padx=10, pady=(5, 10), sticky="ew") # Status debajo de resultados
        else: messagebox.showwarning("Advertencia", "No hay detección para confirmar.")

    def deny_detection(self):
        """Registra negación, muestra corrección y habilita gestor/ROI."""
        detected_state = self.state_var.get() if self.state_var.get() != "N/A" else "unknown"
        logging.warning(f"NEGACIÓN USUARIO: Detección de '{detected_state}' es INCORRECTA.")
        self.status_message(f"Detección negada. Selecciona estado correcto, define ROI o abre el gestor.")
        self.confirm_button.config(state="disabled")
        self.deny_button.config(state="disabled")
        # Mostrar frame de corrección y habilitar botones relevantes
        self.correction_frame.grid(row=2, column=0, padx=10, pady=5, sticky="ew")
        self.launch_capture_button.config(state="normal")
        self.roi_button.config(state="normal") # Habilitar ROI también al negar
        self.ocr_frame.grid_forget()
        self.status_label.grid(row=3, column=0, padx=10, pady=(5, 10), sticky="ew") # Status debajo de corrección
        self._populate_correction_combobox()

    def log_correct_state(self):
        """Registra el estado correcto indicado por el usuario."""
        correct_state = self.correct_state_var.get()
        last_detected = self.state_var.get() if self.state_var.get() != "N/A" else "unknown"
        if not correct_state: messagebox.showwarning("Selección Vacía", "Selecciona estado correcto."); return

        logging.info(f"CORRECCIÓN USUARIO: Detección fue '{last_detected}', estado correcto indicado: '{correct_state}'.")
        self.status_message(f"Corrección registrada: '{correct_state}'.")
        # Deshabilitar botones de corrección pero mantener el frame visible
        self.log_correction_button.config(state="disabled")
        # self.correction_frame.grid_forget() # No ocultar inmediatamente

    def define_roi_for_state(self):
        """Permite al usuario definir o editar el ROI para el estado actual."""
        state_to_edit = self.state_var.get()
        if state_to_edit == "N/A": # Si la detección inicial fue "unknown"
             correct_state_selected = self.correct_state_var.get() # Ver si se seleccionó uno en corrección
             if correct_state_selected:
                  if messagebox.askyesno("Usar Estado Corregido", f"La detección falló.\n¿Definir ROI para estado corregido '{correct_state_selected}'?"):
                       state_to_edit = correct_state_selected
                  else: return # Cancelar
             else: messagebox.showwarning("Sin Estado", "Selecciona un estado correcto en la sección 'Corrección Manual' primero."); return
        elif not messagebox.askyesno("Confirmar Estado", f"¿Definir/Sobrescribir ROI para el estado detectado '{state_to_edit}'?"):
             return # Cancelar si no confirma el estado detectado

        logging.info(f"Iniciando definición de ROI para: '{state_to_edit}'")

        # --- Usar tk_select_roi pasando la instancia del recognizer ---
        selected_roi = tk_select_roi(self, self.recognizer, state_to_edit)

        if selected_roi:
             logging.info(f"ROI seleccionado para '{state_to_edit}': {selected_roi}")
             all_rois = load_json_mapping(STATE_ROIS_FILE, "ROIs de estado")
             all_rois[state_to_edit] = selected_roi
             if save_json_mapping(all_rois, STATE_ROIS_FILE, "ROIs de estado"):
                  self.recognizer.reload_data() # Recargar para que el recognizer use el nuevo ROI
                  messagebox.showinfo("Éxito", f"ROI guardado para '{state_to_edit}'.")
                  self.status_message(f"ROI guardado para '{state_to_edit}'.")
                  self.roi_defined_var.set("Sí") # Actualizar indicador
             else: messagebox.showerror("Error", f"No se pudo guardar {STATE_ROIS_FILE}."); logging.error(f"Fallo al guardar {STATE_ROIS_FILE}")
        else: self.status_message("Definición de ROI cancelada."); logging.info(f"Definición ROI para '{state_to_edit}' cancelada.")

    def launch_template_manager(self):
        """Lanza la GUI template_manager_gui.py."""
        # ... (sin cambios) ...
        logging.info(f"Intentando lanzar: {TEMPLATE_MANAGER_SCRIPT_PATH}")
        self.status_message("Abriendo Gestor de Plantillas...")
        try:
            process = subprocess.Popen([sys.executable, TEMPLATE_MANAGER_SCRIPT_PATH])
            logging.info(f"Gestor de Plantillas lanzado con PID: {process.pid}")
            self.status_message("Gestor de Plantillas abierto. Recarga datos cuando termines.")
        except FileNotFoundError: logging.error(f"Script no encontrado: {TEMPLATE_MANAGER_SCRIPT_PATH}"); messagebox.showerror("Error", f"Script no encontrado:\n{TEMPLATE_MANAGER_SCRIPT_PATH}"); self.status_message("Error al abrir gestor.")
        except Exception as e: logging.error(f"Error al lanzar gestor: {e}"); messagebox.showerror("Error", f"Error al abrir gestor:\n{e}"); self.status_message("Error al abrir gestor.")

    def confirm_ocr_text(self):
        """Confirma texto extraído para región(es) seleccionada(s)."""
        # ... (lógica sin cambios significativos, usa load/save_json_mapping) ...
        if not self.last_recognition_result or self.last_recognition_result['method'] != 'ocr' or not self.last_recognition_result['ocr_results']: messagebox.showwarning("Advertencia", "."); return
        selected_items = self.ocr_tree.selection()
        if not selected_items:
            if not messagebox.askyesno("Confirmar Todas", "No hay región seleccionada.\n¿Confirmar texto para TODAS las regiones con texto extraído?"): return
            target_indices = [int(self.ocr_tree.item(item, 'values')[0]) for item in self.ocr_tree.get_children() if self.ocr_tree.item(item, 'values')[1]]
        else: target_indices = [int(self.ocr_tree.item(item_id, 'values')[0]) for item_id in selected_items if self.ocr_tree.item(item_id, 'values')[1]]
        if not target_indices: messagebox.showinfo("Información", "."); return
        state_name = self.last_recognition_result['state']; ocr_results_map = self.last_recognition_result['ocr_results']
        all_ocr_mappings = load_json_mapping(OCR_MAPPING_FILE, "regiones OCR")
        if state_name not in all_ocr_mappings or not isinstance(all_ocr_mappings[state_name], list):
            if state_name not in all_ocr_mappings: all_ocr_mappings[state_name] = []
            else: messagebox.showerror("Error", f"."); logging.error(f"."); return
        updated = False
        for idx in target_indices:
            if idx in ocr_results_map:
                extracted_text = ocr_results_map[idx]['text']; region_coords = ocr_results_map[idx]['region']
                if extracted_text:
                    try:
                        entry_found = False
                        for i, entry in enumerate(all_ocr_mappings[state_name]):
                            if isinstance(entry, dict) and entry.get('region') == region_coords:
                                if 'expected_text' not in entry or not isinstance(entry['expected_text'], list): entry['expected_text'] = []
                                if extracted_text not in entry['expected_text']: entry['expected_text'].append(extracted_text); updated = True; logging.info(f".")
                                entry_found = True; break
                        if not entry_found: logging.warning(f"."); all_ocr_mappings[state_name].append({'region': region_coords, 'expected_text': [extracted_text]}); updated = True
                    except Exception as e: messagebox.showerror("Error", f"."); logging.error(f"."); return
        if updated:
            if save_json_mapping(all_ocr_mappings, OCR_MAPPING_FILE, "regiones OCR"):
                self.recognizer.reload_data(); logging.info(f"."); messagebox.showinfo("Éxito", "."); self.status_message("."); self.refresh_ocr_tree_display()
            else: logging.error(f"."); messagebox.showerror("Error", f".")
        else: messagebox.showinfo("Información", "."); self.status_message(".")

    def save_edited_ocr_text(self):
        """Guarda texto editado para región(es) seleccionada(s)."""
        # ... (lógica sin cambios significativos, usa load/save_json_mapping) ...
        if not self.last_recognition_result or self.last_recognition_result['method'] != 'ocr': messagebox.showwarning("Advertencia", "."); return
        selected_items = self.ocr_tree.selection()
        if not selected_items: messagebox.showwarning("Selección Vacía", "."); return
        state_name = self.last_recognition_result['state']; edited_text_str = self.ocr_edit_var.get().strip()
        if not edited_text_str: messagebox.showwarning("Entrada Vacía", "."); return
        expected_texts = [text.strip() for text in edited_text_str.split('|') if text.strip()]
        if not expected_texts: messagebox.showwarning("Entrada Vacía", "."); return
        all_ocr_mappings = load_json_mapping(OCR_MAPPING_FILE, "regiones OCR")
        if state_name not in all_ocr_mappings or not isinstance(all_ocr_mappings[state_name], list):
             if state_name not in all_ocr_mappings: all_ocr_mappings[state_name] = []
             else: messagebox.showerror("Error", f"."); logging.error(f"."); return
        updated = False; target_regions_coords = []
        for item_id in selected_items:
             values = self.ocr_tree.item(item_id, 'values');
             if values and values[0] != "N/A" and self.last_recognition_result.get('ocr_results'):
                 idx = int(values[0]);
                 if idx in self.last_recognition_result['ocr_results']: target_regions_coords.append(self.last_recognition_result['ocr_results'][idx]['region'])
        if not target_regions_coords: messagebox.showinfo("Información", "."); return
        for entry in all_ocr_mappings[state_name]:
             if isinstance(entry, dict) and entry.get('region') in target_regions_coords:
                  try: entry['expected_text'] = expected_texts; updated = True; logging.info(f".")
                  except Exception as e: messagebox.showerror("Error", f"."); logging.error(f"."); return
        if updated:
            if save_json_mapping(all_ocr_mappings, OCR_MAPPING_FILE, "regiones OCR"):
                self.recognizer.reload_data(); logging.info(f"."); messagebox.showinfo("Éxito", "."); self.status_message("."); self.ocr_edit_var.set(""); self.refresh_ocr_tree_display()
            else: logging.error(f"."); messagebox.showerror("Error", f".")
        else: logging.warning(f"."); messagebox.showinfo("Información", f".")


    def refresh_ocr_tree_display(self):
        """Actualiza el Treeview con los datos del último resultado OCR y los datos guardados."""
        # ... (sin cambios) ...
        if not self.last_recognition_result or self.last_recognition_result['method'] != 'ocr': return
        for item in self.ocr_tree.get_children(): self.ocr_tree.delete(item)
        state_name = self.last_recognition_result['state']
        current_ocr_mappings = load_json_mapping(OCR_MAPPING_FILE, "regiones OCR")
        current_regions_data_list = current_ocr_mappings.get(state_name, [])
        if self.last_recognition_result['ocr_results']:
            for idx, data in self.last_recognition_result['ocr_results'].items():
                extracted = data['text']; region_coords = data['region']; expected_list = []
                for entry in current_regions_data_list:
                     if isinstance(entry, dict) and entry.get('region') == region_coords: expected_list = entry.get('expected_text', []); break
                expected_str = "|".join(expected_list); match_expected = False
                if extracted and expected_list:
                    for expected in expected_list:
                        if expected.lower() == extracted.lower(): match_expected = True; break
                match_str = "Sí" if match_expected else "No"
                self.ocr_tree.insert("", tk.END, values=(idx, extracted, expected_str, match_str))
        else: self.ocr_tree.insert("", tk.END, values=("N/A", "No resultados.", "", "N/A"))


    def status_message(self, message):
        """Actualiza el mensaje en el label de estado."""
        self.status_label_var.set(message)
        self.update_idletasks()

if __name__ == "__main__":
    # Asegurar que existan los directorios config e images
    if not os.path.exists(CONFIG_DIR): os.makedirs(CONFIG_DIR)
    if not os.path.exists(IMAGES_DIR): os.makedirs(IMAGES_DIR)

    app = ScreenTesterGUI()
    app.mainloop()