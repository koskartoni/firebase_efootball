# --- START OF FILE src/template_manager_gui.py ---
# --- VERSIÓN REFACTORIZADA - LÓGICA IMPLEMENTADA ---

import tkinter as tk
from tkinter import ttk, font as tkFont, messagebox, simpledialog, filedialog # Asegurar simpledialog
import os
import sys
import logging
import time
import cv2
import re # Necesario para validar nombres
import datetime # Necesario para timestamp en save_template

# --- Configuración de Rutas e Importaciones ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
if PROJECT_DIR not in sys.path: sys.path.insert(0, PROJECT_DIR)
if SCRIPT_DIR not in sys.path: sys.path.insert(1, SCRIPT_DIR)

try:
    from template_manager_utils import (
        load_json_mapping, save_json_mapping,
        load_ocr_data, save_ocr_data,
        load_template_data, save_template_data,
        capture_screen, tk_select_region_base,
        tk_select_ocr_region, tk_select_monitor_region,
        detect_monitors,
        IMAGES_DIR, CONFIG_DIR, OCR_MAPPING_FILE_PATH, TEMPLATE_MAPPING_FILE_PATH
    )
    from panels.template_panel import TemplatePanel
    from panels.image_preview_panel import ImagePreviewPanel # Importar el correcto
    from panels.ocr_definition_panel import OcrDefinitionPanel # Importar el correcto

except ImportError as e:
    try: root = tk.Tk(); root.withdraw(); messagebox.showerror("Error Crítico Importación", f"No se pudo importar módulo.\n{e}\nVerifique utils y panels.")
    except Exception: pass
    print(f"Error crítico importación: {e}\nPython Path: {sys.path}"); sys.exit(1)

# --- Configuración Logging ---
# (Sin cambios)
log_file_path = os.path.join(PROJECT_DIR, "logs", "template_manager.log")
os.makedirs(os.path.dirname(log_file_path), exist_ok=True)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s [%(filename)s:%(lineno)d] - %(message)s', handlers=[logging.FileHandler(log_file_path, encoding='utf-8', mode='a'), logging.StreamHandler()])
logging.info(f"\n{'='*20} Iniciando Template Manager GUI (Refactorizado v1.3 - Lógica) {'='*20}")

# --- Constantes GUI ---
# (Sin cambios)
APP_TITLE = "Template Manager GUI v2.0"
MIN_WINDOW_WIDTH = 1200
MIN_WINDOW_HEIGHT = 750
DEFAULT_FONT_SIZE_GUI = 10
DEFAULT_THEME = 'clam'

# --- Clase Principal ---
class TemplateManagerGUI(tk.Tk):
    def __init__(self):
        # (Sin cambios)
        super().__init__(); logging.info("Inicializando..."); self.title(APP_TITLE); self.minsize(MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT)
        try: sw, sh = self.winfo_screenwidth(), self.winfo_screenheight(); x, y = (sw//2)-(MIN_WINDOW_WIDTH//2), (sh//2)-(MIN_WINDOW_HEIGHT//2); self.geometry(f"{MIN_WINDOW_WIDTH}x{MIN_WINDOW_HEIGHT}+{x}+{y}")
        except tk.TclError: self.geometry(f"{MIN_WINDOW_WIDTH}x{MIN_WINDOW_HEIGHT}")
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.monitors_info = detect_monitors(); self.template_names_mapping = {}; self.ocr_regions_mapping = {}; self.current_template_name = None; self.current_image_filename = None; self.current_image_path = None; self.current_image_numpy = None; self.current_ocr_regions = []; self.status_label_var = tk.StringVar(value="Inicializando...")
        self.template_panel = None; self.preview_panel = None; self.ocr_panel = None
        self._setup_styles_and_fonts(); self._create_widgets(); self.load_mappings_from_json(); self._reset_ui_state(); logging.info("GUI inicializada."); self.status_message("Listo.")

    def _setup_styles_and_fonts(self):
        logging.debug("Configurando estilos y fuentes.")
        self.style = ttk.Style(self)
        try:
            avail = self.style.theme_names()
            logging.debug(f"Temas disponibles: {avail}")
            if DEFAULT_THEME in avail:
                self.style.theme_use(DEFAULT_THEME)
                logging.info(f"Tema: {DEFAULT_THEME}")
            else:
                logging.warning(f"Tema '{DEFAULT_THEME}' no encontrado. Usando: {self.style.theme_use()}")
        except tk.TclError as e:  # <-- except al mismo nivel que try
            logging.warning(f"Error aplicando tema ttk: {e}")
        except Exception as e_gen:  # <-- Captura genérica por si acaso
            logging.error(f"Error inesperado configurando tema: {e_gen}")

        self.default_font = tkFont.nametofont("TkDefaultFont");
        self.default_font.configure(size=DEFAULT_FONT_SIZE_GUI)
        self.heading_font = tkFont.Font(family=self.default_font['family'], size=DEFAULT_FONT_SIZE_GUI + 1,
                                        weight="bold");
        self.status_font = tkFont.Font(family=self.default_font['family'], size=DEFAULT_FONT_SIZE_GUI - 1)
        self.option_add("*Font", self.default_font)
        self.style.configure("TLabelFrame", padding=8);
        self.style.configure("TLabelFrame.Label", font=self.heading_font, padding=(0, 0, 0, 5))
        self.style.configure("TButton", padding=5);
        self.style.configure("Status.TLabel", font=self.status_font, padding=5)
        try:  # Añadir try-except para configurar Treeview por si falla
            tree_font_family = self.default_font.actual()['family']
            tree_heading_font = (tree_font_family, DEFAULT_FONT_SIZE_GUI, 'bold')
            tree_row_height = tkFont.Font(font=self.default_font).metrics('linespace') + 4
            self.style.configure("Treeview.Heading", font=tree_heading_font)
            self.style.configure('Treeview', rowheight=tree_row_height)
        except Exception as e_tree:
            logging.warning(f"Error configurando estilo Treeview: {e_tree}")


    def _create_widgets(self):
        """Crea layout e instancia paneles reales."""
        logging.debug("Creando widgets (layout y paneles reales).")
        main_frame = ttk.Frame(self, padding="10"); main_frame.grid(row=0, column=0, sticky="nsew")
        self.grid_rowconfigure(0, weight=1); self.grid_columnconfigure(0, weight=1)
        left_column = ttk.Frame(main_frame); left_column.grid(row=0, column=0, sticky="nsew", padx=(0, 5)); main_frame.grid_columnconfigure(0, weight=2, minsize=380)
        center_column = ttk.Frame(main_frame); center_column.grid(row=0, column=1, sticky="nsew", padx=5); main_frame.grid_columnconfigure(1, weight=5, minsize=400)
        right_column = ttk.Frame(main_frame); right_column.grid(row=0, column=2, sticky="nsew", padx=(5, 0)); main_frame.grid_columnconfigure(2, weight=2, minsize=350)
        main_frame.grid_rowconfigure(0, weight=1)

        # --- Paneles Reales ---
        self.template_panel = TemplatePanel(left_column, self, padding=10); self.template_panel.grid(row=0, column=0, sticky="nsew"); left_column.grid_rowconfigure(0, weight=1); left_column.grid_columnconfigure(0, weight=1)
        self.preview_panel = ImagePreviewPanel(center_column, self, padding=5); self.preview_panel.grid(row=0, column=0, sticky="nsew"); center_column.grid_rowconfigure(0, weight=1); center_column.grid_columnconfigure(0, weight=1)
        self.ocr_panel = OcrDefinitionPanel(right_column, self, padding=10); self.ocr_panel.grid(row=0, column=0, sticky="nsew"); right_column.grid_rowconfigure(0, weight=1); right_column.grid_columnconfigure(0, weight=1)

        # Barra Estado
        self.status_bar = ttk.Label(main_frame, textvariable=self.status_label_var, style="Status.TLabel", anchor="w", relief="sunken", borderwidth=1); self.status_bar.grid(row=1, column=0, columnspan=3, sticky="sew", pady=(10, 0)); main_frame.grid_rowconfigure(1, weight=0)
        logging.debug("Layout y paneles reales creados.")

    def _reset_ui_state(self):
        """Resetea la UI a un estado limpio inicial."""
        logging.debug("Reseteando estado de la UI.")
        self.current_template_name = None
        self.current_image_filename = None
        self.current_image_path = None
        self.current_image_numpy = None
        self.current_ocr_regions = []

        if self.template_panel: self.template_panel.reset_panel()
        if self.preview_panel: self.preview_panel.clear_preview()
        if self.ocr_panel: self.ocr_panel.reset_panel()

        self.update_all_button_states() # Asegurar estado correcto de botones
        self.status_message("Listo.")
        self.update_idletasks()

    def load_mappings_from_json(self):
        # (Sin cambios lógicos, pero llama a refresh en panel)
        self.status_message("Cargando...", level=logging.DEBUG)
        self.template_names_mapping = load_template_data()
        self.ocr_regions_mapping = load_ocr_data()
        logging.info(f"Cargados {len(self.template_names_mapping)} tpls y {len(self.ocr_regions_mapping)} OCRs.")
        if self.template_panel:
            self.template_panel.refresh_template_list(self.template_names_mapping) # Llama a refresh del panel
        self.status_message("Configuraciones cargadas.")

    # --- Métodos Coordinadores ---
    def handle_template_selection(self, template_name):
        # (Sin cambios lógicos)
        logging.info(f"Selección TPL: {template_name}"); self.current_template_name = template_name; self._reset_ui_state_for_template_change()
        files = self.template_names_mapping.get(template_name, [])
        if self.template_panel: self.template_panel.populate_image_listbox(files)
        if files: self.load_image(files[0]); self.load_ocr_for_current_template() # Carga OCR aquí
        else: self.clear_preview_and_ocr()
        self.update_all_button_states()

    def handle_image_selection(self, image_filename):
        # (Sin cambios lógicos)
        if not image_filename: return # Evitar error si se deselecciona
        logging.info(f"Selección IMG: {image_filename}"); self.load_image(image_filename)
        # No recargar OCR aquí, ya asociado a la plantilla
        self.update_all_button_states()

    def load_image(self, filename):
        """Carga imagen y actualiza preview (con OCR y sin selección)."""
        # (Llama a update_preview del panel real)
        self.status_message(f"Cargando '{filename}'...", level=logging.DEBUG); self.current_image_numpy = None; self.current_image_path = None; self.current_image_filename = None
        if not filename: self.clear_preview_and_ocr(); return
        image_path = os.path.join(IMAGES_DIR, filename); logging.info(f"Cargando: {image_path}")
        if os.path.exists(image_path):
            try:
                img = cv2.imread(image_path);
                if img is None: raise ValueError(f"imread None: {filename}")
                self.current_image_numpy = img; self.current_image_path = image_path; self.current_image_filename = filename; logging.info(f"'{filename}' cargada.")
                # --- Actualizar PreviewPanel ---
                if self.preview_panel:
                    self.preview_panel.update_preview(self.current_image_numpy, self.current_ocr_regions, []) # Mostrar con OCR pero sin selección
                # -----------------------------
                self.status_message(f"Mostrando: {filename}")
            except Exception as e: logging.error(f"Err cargando '{filename}': {e}"); messagebox.showerror("Error", f"Err:\n{filename}\n{e}", parent=self); self.clear_preview_and_ocr()
        else: logging.warning(f"No existe: {image_path}"); messagebox.showwarning("Falta", f"No existe:\n{filename}", parent=self); self.clear_preview_and_ocr()

    def load_ocr_for_current_template(self):
        # (Llama a populate_treeview del panel real)
        self.current_ocr_regions = [];
        if self.current_template_name and self.current_template_name in self.ocr_regions_mapping:
            regions = self.ocr_regions_mapping[self.current_template_name];
            if isinstance(regions, list):
                 valid = [];
                 for r in regions:
                     if isinstance(r, dict) and 'region' in r and isinstance(r['region'], dict) and all(k in r['region'] for k in ('left','top','width','height')):
                         r['expected_text'] = r.get('expected_text',[]);
                         if not isinstance(r['expected_text'], list): r['expected_text']=[]
                         valid.append(r)
                     else: logging.warning(f"Región mal formada ign '{self.current_template_name}': {r}")
                 self.current_ocr_regions = valid
            else: logging.warning(f"Datos OCR para '{self.current_template_name}' no lista.")
        logging.debug(f"Cargadas {len(self.current_ocr_regions)} OCRs para '{self.current_template_name}'.")
        # --- Actualizar OcrPanel ---
        if self.ocr_panel:
            self.ocr_panel.populate_treeview(self.current_ocr_regions)
        # --------------------------

    def clear_preview_and_ocr(self):
        # (Llama a clear y reset de paneles reales)
        self.current_image_numpy = None; self.current_image_path = None; self.current_image_filename = None; self.current_ocr_regions = []
        if self.preview_panel: self.preview_panel.clear_preview()
        if self.ocr_panel: self.ocr_panel.reset_panel()

    def update_all_button_states(self):
        # (Llama a update de paneles reales)
        if self.template_panel: self.template_panel.update_action_button_states()
        if self.ocr_panel: self.ocr_panel._update_action_buttons_state() # Usar método interno del panel

    def _reset_ui_state_for_template_change(self):
        # (Llama a clear y reset de paneles reales)
         self.current_image_filename = None; self.current_image_path = None; self.current_image_numpy = None; self.current_ocr_regions = []
         if self.preview_panel: self.preview_panel.clear_preview()
         if self.ocr_panel: self.ocr_panel.reset_panel()


    # --- LÓGICA PRINCIPAL IMPLEMENTADA ---

    def capture_template_action(self, capture_type, monitor_idx):
        """Realiza la captura y actualiza la UI."""
        logging.info(f"Captura: {capture_type} Mon:{monitor_idx}")
        self.status_message("Capturando pantalla...")
        self.withdraw(); self.update(); time.sleep(0.3) # Ocultar ventana brevemente
        captured_img = None
        try:
            if capture_type == "monitor":
                captured_img = capture_screen(monitor=monitor_idx)
            elif capture_type == "region":
                 monitor_image = capture_screen(monitor=monitor_idx)
                 if monitor_image is not None:
                      self.deiconify(); self.update() # Mostrar para seleccionar
                      target_monitor_info = self.monitors_info[monitor_idx] if monitor_idx < len(self.monitors_info) else {}
                      region_absolute = tk_select_monitor_region(self, monitor_image, target_monitor_info)
                      if region_absolute:
                          self.withdraw(); self.update(); time.sleep(0.2) # Ocultar de nuevo
                          captured_img = capture_screen(region=region_absolute, monitor=monitor_idx)
                      else: logging.info("Selección de región cancelada.")
                 else: logging.error("No se pudo capturar imagen del monitor para seleccionar región.")
        finally:
            if self.state() == 'withdrawn': self.deiconify() # Asegurar que se muestre de nuevo
            self.status_message("Captura finalizada.")

        if captured_img is not None:
            # Limpiar estado anterior antes de poner la nueva captura
            self.clear_all_selections()
            self.current_image_numpy = captured_img
            self.current_image_path = None # No es de archivo
            self.current_image_filename = None
            if self.preview_panel: # Actualizar preview
                 self.preview_panel.update_preview(self.current_image_numpy, [], [])
            self.status_message("Pantalla capturada. Introduzca nombre y guarde.")
            if self.template_panel: self.template_panel.new_template_entry.focus_set()
            self.update_all_button_states() # Habilitar botones correspondientes
        else:
            self.status_message("Captura cancelada o fallida.", level=logging.WARNING)


    def save_template_action(self, template_name):
        """Guarda imagen capturada como NUEVA plantilla o AÑADE imagen a existente."""
        # (Lógica sin cambios significativos, ya estaba bastante completa)
        if self.current_image_numpy is None: messagebox.showerror("Error", "No hay imagen capturada.", parent=self); return
        # Validación de nombre ya hecha en el panel, pero doble check
        if not template_name or not re.match(r'^[a-zA-Z0-9_.-]+$', template_name): messagebox.showerror("Error", "Nombre inválido.", parent=self); return

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_filename_base = re.sub(r'[^\w.-]', '_', template_name)
        image_filename = f"{safe_filename_base}_{timestamp}.png"
        image_path = os.path.join(IMAGES_DIR, image_filename)
        logging.info(f"Intentando guardar '{template_name}' como '{image_filename}'")
        is_new = template_name not in self.template_names_mapping; action = "Guardar nueva plantilla" if is_new else f"Añadir imagen a '{template_name}'"
        if messagebox.askyesno("Confirmar", f"¿{action} como '{image_filename}'?", parent=self):
            try:
                os.makedirs(IMAGES_DIR, exist_ok=True); success = cv2.imwrite(image_path, self.current_image_numpy);
                if not success: raise Exception("cv2.imwrite falló."); logging.info(f"Img guardada: {image_path}")
                mapping = load_template_data();
                if template_name in mapping:
                    if isinstance(mapping[template_name], list):
                         if image_filename not in mapping[template_name]: mapping[template_name].append(image_filename)
                    else: mapping[template_name] = [mapping[template_name], image_filename]
                else: mapping[template_name] = [image_filename]
                if save_template_data(mapping):
                    self.status_message(f"Img '{image_filename}' guardada para '{template_name}'."); self.template_names_mapping = mapping
                    curr_sel = self.template_name_var.get() if hasattr(self, 'template_name_var') else None # Obtener del panel si existe
                    self.load_mappings_from_json() # Recargar todo y refrescar combobox
                    if template_name in self.template_names_mapping: # Si la plantilla existe (nueva o vieja)
                        if self.template_panel: self.template_panel.template_name_var.set(template_name) # Seleccionar en combobox
                        self.handle_template_selection(template_name) # Cargarla
                    elif curr_sel and curr_sel in self.template_names_mapping: # Volver a la anterior si se añadió imagen
                         if self.template_panel: self.template_panel.template_name_var.set(curr_sel)
                         self.handle_template_selection(curr_sel)
                    else: self.clear_all_selections()
                    if is_new and self.current_ocr_regions: # Usar self.current_ocr_regions
                        if messagebox.askyesno("Guardar OCR", f"Hay {len(self.current_ocr_regions)} region(es).\n¿Guardarlas para NUEVA plantilla '{template_name}'?", parent=self):
                             self.save_ocr_action(force_template_name=template_name) # Llamar a save_ocr_action
                    if self.template_panel: self.template_panel.new_template_name_var.set("") # Limpiar campo nombre
                else:
                    self.status_message(f"Error guardando mapeo.", level=logging.ERROR);
                    try: os.remove(image_path); logging.warning(f"Img '{image_filename}' eliminada por fallo mapeo.")
                    except OSError as e: logging.error(f"No se pudo borrar img tras fallo mapeo: {e}")
            except Exception as e: logging.exception(f"Error guardando '{template_name}': {e}"); messagebox.showerror("Error Guardando", f"Error:\n{e}", parent=self); self.status_message(f"Error guardando '{template_name}'.", level=logging.ERROR)
        else: self.status_message("Guardado cancelado.")


    def delete_image_action(self, template_name, image_filename):
        """Elimina una imagen específica de una plantilla."""
        # (Implementación sin cambios lógicos, ya estaba bien)
        msg1=f"¿Eliminar ref a '{image_filename}' de '{template_name}'?";
        if not messagebox.askyesno("Confirmar (Mapeo)", msg1, parent=self): self.status_message("Elim ref cancelada."); return
        fpath=os.path.join(IMAGES_DIR, image_filename)
        del_file=messagebox.askyesno("Eliminar Archivo", f"¿ELIMINAR archivo '{image_filename}'?\n¡NO SE PUEDE DESHACER!", icon='warning', parent=self)
        logging.info(f"Eliminando '{image_filename}' de '{template_name}'. Borrar archivo: {del_file}"); self.status_message(f"Eliminando '{image_filename}'...", level=logging.DEBUG)
        try:
            mapping=load_template_data();
            if template_name in mapping and isinstance(mapping[template_name], list):
                init_list = mapping[template_name];
                if image_filename in init_list:
                    initial_list.remove(image_filename);
                    if not initial_list: del mapping[template_name]; logging.info(f"Eliminada entrada completa para '{template_name}'.")
                    else: mapping[template_name] = initial_list
                    if save_template_data(mapping):
                        logging.info(f"Mapeo actualizado sin '{image_filename}'."); self.template_names_mapping = mapping
                        f_del_ok = False;
                        if del_file:
                            try:
                                if os.path.exists(fpath): os.remove(fpath); logging.info(f"Archivo físico borrado: {fpath}"); f_del_ok=True
                                else: logging.warning(f"Archivo no existe: {fpath}")
                            except OSError as e: logging.error(f"Error borrando {fpath}: {e}"); messagebox.showerror("Error Borrado", f"Error borrando:\n{image_filename}\n{e}", parent=self)
                        curr_sel = template_name; self.load_mappings_from_json() # Recarga combobox
                        if curr_sel in self.template_names_mapping: # Si la plantilla aún existe
                            if self.template_panel: self.template_panel.template_name_var.set(curr_sel)
                            self.handle_template_selection(curr_sel) # Recargarla
                        else: self.clear_all_selections() # Limpiar si la plantilla fue eliminada
                        msg = f"Imagen '{image_filename}' eliminada de '{template_name}'.";
                        if del_file and f_del_ok: msg += " Archivo borrado."
                        elif del_file and not f_del_ok: msg += " Error al borrar archivo."
                        self.status_message(msg)
                    else: self.status_message("Error guardando mapeo.", level=logging.ERROR)
                else: logging.warning(f"'{image_filename}' no en lista para '{template_name}'."); messagebox.showwarning("No Encontrado", f"'{image_filename}' no en lista.", parent=self); self.handle_template_selection(template_name) # Refrescar
            else: logging.error(f"Plantilla '{template_name}' inválida."); messagebox.showerror("Error Datos", f"Plantilla '{template_name}' inválida.", parent=self)
        except Exception as e: logging.exception(f"Error eliminando '{image_filename}': {e}"); messagebox.showerror("Error", f"Error:\n{e}", parent=self); self.status_message(f"Error eliminando '{image_filename}'.", level=logging.ERROR)


    def rename_template_action(self, old_name, new_name):
        """Renombra una plantilla en ambos JSON."""
        # (Implementación sin cambios lógicos, ya estaba bien)
        logging.info(f"Renombrando '{old_name}' a '{new_name}'"); self.status_message(f"Renombrando...", level=logging.DEBUG)
        try:
            tpl_map = load_template_data(); ocr_map = load_ocr_data()
            if old_name not in tpl_map: messagebox.showerror("Error", f"'{old_name}' no encontrada.", parent=self); self.load_mappings_from_json(); return
            # No necesitamos comprobar si new_name existe aquí porque el panel ya lo hizo
            tpl_map[new_name] = tpl_map.pop(old_name); logging.debug(f"Renombrado en tpl_map.")
            if old_name in ocr_map: ocr_map[new_name] = ocr_map.pop(old_name); logging.debug(f"Renombrado en ocr_map.")
            tpl_ok = save_template_data(tpl_map); ocr_ok = save_ocr_data(ocr_map)
            if tpl_ok and ocr_ok:
                logging.info(f"Renombrado a '{new_name}'."); self.template_names_mapping=tpl_map; self.ocr_regions_mapping=ocr_map
                self.load_mappings_from_json(); # Recargar combobox
                if self.template_panel: self.template_panel.template_name_var.set(new_name); # Seleccionar nuevo nombre
                self.handle_template_selection(new_name) # Cargar datos para nuevo nombre
                self.status_message(f"Plantilla renombrada a '{new_name}'.")
            else: messagebox.showerror("Error Guardando", "Error guardando mapeos.", parent=self); self.status_message("Error guardando tras renombrar.", level=logging.ERROR); self.load_mappings_from_json(); self.load_ocr_regions_from_json()
        except Exception as e: logging.exception(f"Error renombrando '{old_name}' a '{new_name}': {e}"); messagebox.showerror("Error", f"Error:\n{e}", parent=self); self.status_message(f"Error renombrando.", level=logging.ERROR)

    # --- Dentro de la clase TemplateManagerGUI ---

    def delete_template_action(self, template_name):
        """Elimina plantilla completa (mapeos y opcionalmente archivos)."""
        files = self.template_names_mapping.get(template_name, []);
        n_files = len(files)
        msg1 = f"¿Eliminar plantilla '{template_name}'?\n({n_files} imagen(es)).";
        if template_name in self.ocr_regions_mapping: msg1 += f"\nSe eliminarán sus {len(self.ocr_regions_mapping[template_name])} zona(s) OCR."
        if not messagebox.askyesno("Confirmar", msg1, parent=self): self.status_message(
            "Eliminación cancelada."); return
        del_files = False;
        if files: del_files = messagebox.askyesno("Eliminar Archivos",
                                                  f"¿ELIMINAR TAMBIÉN los {n_files} archivo(s)?\n{files}\n¡NO SE PUEDE DESHACER!",
                                                  icon='warning', parent=self)
        logging.info(f"Eliminando plantilla '{template_name}'. Borrar archivos: {del_files}");
        self.status_message(f"Eliminando '{template_name}'...", level=logging.DEBUG)
        try:
            tpl_map = load_template_data();
            ocr_map = load_ocr_data();
            mod_tpl = False;
            mod_ocr = False
            if template_name in tpl_map: del tpl_map[template_name]; mod_tpl = True; logging.debug(
                f"Eliminado de tpl_map.")
            if template_name in ocr_map: del ocr_map[template_name]; mod_ocr = True; logging.debug(
                f"Eliminado de ocr_map.")

            # --- SECCIÓN CORREGIDA ---
            tpl_saved = True  # Asumir éxito si no se modificó
            if mod_tpl:
                logging.debug("Guardando mapeo de plantillas modificado...")
                tpl_saved = save_template_data(tpl_map)  # Guardar si se modificó

            ocr_saved = True  # Asumir éxito si no se modificó
            if mod_ocr:
                logging.debug("Guardando mapeo OCR modificado...")
                ocr_saved = save_ocr_data(ocr_map)  # Guardar si se modificó
            # --- FIN SECCIÓN CORREGIDA ---

            if tpl_saved and ocr_saved:
                logging.info(f"Mapeos actualizados sin '{template_name}'.");
                self.template_names_mapping = tpl_map;
                self.ocr_regions_mapping = ocr_map
                f_ok = True;
                f_errs = [];
                if del_files and files:
                    logging.info(f"Eliminando archivos: {files}");
                    for fname in files:
                        fpath = os.path.join(IMAGES_DIR, fname);
                        try:
                            if os.path.exists(fpath):
                                os.remove(fpath); logging.info(f"  Archivo borrado: {fpath}")
                            else:
                                logging.warning(f"  Archivo no existe: {fpath}")
                        except OSError as e:
                            logging.error(f"  Error borrando {fpath}: {e}"); f_errs.append(fname); f_ok = False
                self.load_mappings_from_json();
                self.clear_all_selections()  # Recargar lista y limpiar UI
                msg = f"Plantilla '{template_name}' eliminada.";
                if del_files and f_ok:
                    msg += " Archivos borrados."
                elif del_files and not f_ok:
                    msg += f" Errores borrando: {f_errs}."
                self.status_message(msg)
            else:
                messagebox.showerror("Error Guardando", "Error guardando mapeos.", parent=self); self.status_message(
                    "Error guardando tras eliminar.",
                    level=logging.ERROR); self.load_mappings_from_json(); self.load_ocr_regions_from_json()
        except Exception as e:
            logging.exception(f"Error eliminando '{template_name}': {e}"); messagebox.showerror("Error", f"Error:\n{e}",
                                                                                                parent=self); self.status_message(
                f"Error eliminando '{template_name}'.", level=logging.ERROR)

    def mark_ocr_action(self, expected_text_list):
        """Marca una nueva región OCR y la añade a la lista en memoria."""
        if self.current_image_numpy is None:
            messagebox.showerror("Error", "Cargue o capture una imagen primero.", parent=self)
            return

        logging.info(f"Solicitando selección OCR. Texto a asociar: {expected_text_list}")
        self.status_message("Selecciona la región OCR en la nueva ventana...")
        self.withdraw(); self.update() # Ocultar mientras selecciona
        region_coords = tk_select_ocr_region(self, self.current_image_numpy)
        self.deiconify(); self.update() # Mostrar de nuevo

        if region_coords:
            new_region_data = {"region": region_coords, "expected_text": expected_text_list}
            self.current_ocr_regions.append(new_region_data) # Añadir a la lista en memoria
            new_index = len(self.current_ocr_regions) - 1 # Índice 0-based
            logging.info(f"Nueva región OCR {new_index+1} añadida (memoria): {new_region_data}")

            # Actualizar UI
            if self.ocr_panel: self.ocr_panel.populate_treeview(self.current_ocr_regions)
            if self.preview_panel: self.preview_panel.update_preview(self.current_image_numpy, self.current_ocr_regions, [new_index]) # Resaltar nueva
            self.update_all_button_states()
            self.status_message(f"Región OCR {new_index+1} añadida a sesión. Guarde para persistir.")
        else:
            logging.info("Selección OCR cancelada.")
            self.status_message("Marcado de región OCR cancelado.")

    def edit_ocr_text_action_prompt(self, region_index):
        """Pide nuevo texto y llama a la acción de edición."""
        if not (0 <= region_index < len(self.current_ocr_regions)):
             logging.error(f"Índice {region_index} inválido para editar texto.")
             messagebox.showerror("Error Interno", "Índice de región inválido.", parent=self)
             return
        try:
            current_texts = self.current_ocr_regions[region_index].get('expected_text', [])
            initial_text = "|".join(current_texts)
            new_text_str = simpledialog.askstring("Editar Texto Esperado",
                                                  f"Texto(s) para región {region_index+1} (separa con '|'):",
                                                  initialvalue=initial_text, parent=self)
            if new_text_str is not None:
                new_texts_list = [txt.strip() for txt in new_text_str.split('|') if txt.strip()]
                self.edit_ocr_text_action(region_index, new_texts_list) # Llamar a la lógica de actualización
            else:
                self.status_message("Edición cancelada.")
        except Exception as e:
             logging.exception(f"Error en prompt edición OCR idx {region_index}: {e}")
             messagebox.showerror("Error", f"Error editando texto:\n{e}", parent=self)


    def edit_ocr_text_action(self, region_index, new_text_list):
        """Edita el texto de una región OCR en memoria."""
        if not (0 <= region_index < len(self.current_ocr_regions)): return # Doble check
        logging.info(f"Actualizando texto OCR región {region_index+1} a: {new_text_list}")
        self.current_ocr_regions[region_index]['expected_text'] = new_text_list
        # Actualizar UI
        if self.ocr_panel: self.ocr_panel.populate_treeview(self.current_ocr_regions)
        if self.preview_panel: self.preview_panel.update_preview(self.current_image_numpy, self.current_ocr_regions, [region_index]) # Resaltar editada
        self.update_all_button_states()
        self.status_message(f"Texto región {region_index+1} actualizado. Guarde para persistir.")


    def redraw_ocr_action(self, region_index):
        """Permite redibujar una región OCR existente."""
        if not (0 <= region_index < len(self.current_ocr_regions)):
             logging.error(f"Índice {region_index} inválido para redibujar.")
             messagebox.showerror("Error Interno", "Índice de región inválido.", parent=self)
             return
        if self.current_image_numpy is None: messagebox.showerror("Error", "No hay imagen base.", parent=self); return

        logging.info(f"Redibujando región OCR {region_index+1}...")
        self.status_message(f"Redibujando región {region_index+1}...")
        self.withdraw(); self.update()
        new_coords = tk_select_ocr_region(self, self.current_image_numpy)
        self.deiconify(); self.update()

        if new_coords:
            logging.info(f"Región {region_index+1} redibujada a: {new_coords}")
            self.current_ocr_regions[region_index]['region'] = new_coords
            # Actualizar UI
            if self.ocr_panel: self.ocr_panel.populate_treeview(self.current_ocr_regions) # Repoblar por si cambia orden visual
            if self.preview_panel: self.preview_panel.update_preview(self.current_image_numpy, self.current_ocr_regions, [region_index]) # Resaltar
            self.update_all_button_states()
            self.status_message(f"Región {region_index+1} redibujada. Guarde para persistir.")
        else:
            self.status_message(f"Redibujado región {region_index+1} cancelado.")


    def delete_ocr_action(self, region_indices):
        """Elimina una o más regiones OCR de la lista en memoria."""
        if not region_indices: return # No hacer nada si la lista está vacía
        indices_to_remove = sorted(region_indices, reverse=True) # Ordenar descendente
        region_numbers = [i + 1 for i in region_indices]
        num_del = len(region_indices)

        if messagebox.askyesno("Confirmar", f"¿Eliminar {num_del} región(es) ({region_numbers}) de la sesión?\n(Guarde para persistir).", parent=self):
            logging.info(f"Eliminando regiones OCR (0-based): {indices_to_remove}")
            removed_count = 0
            for idx in indices_to_remove:
                if 0 <= idx < len(self.current_ocr_regions):
                    del self.current_ocr_regions[idx]
                    removed_count += 1
                else:
                    logging.warning(f"Índice {idx} inválido durante eliminación OCR.")
            # Actualizar UI
            if self.ocr_panel: self.ocr_panel.populate_treeview(self.current_ocr_regions)
            if self.preview_panel: self.preview_panel.update_preview(self.current_image_numpy, self.current_ocr_regions, []) # Limpiar selección
            self.update_all_button_states()
            self.status_message(f"{removed_count} región(es) eliminada(s) de la sesión.")
        else:
            self.status_message("Eliminación regiones cancelada.")


    def clear_ocr_session_action(self):
        """Limpia todas las regiones OCR de la sesión actual."""
        if not self.current_ocr_regions:
             self.status_message("No hay regiones en sesión para limpiar.")
             return
        # La confirmación la hace el panel, llamar directamente a clear_ocr_regions
        if self.ocr_panel: # Llamar al método del panel si existe
             self.ocr_panel.clear_ocr_regions(ask_confirm=True)
        else: # Fallback si el panel no existe
             if messagebox.askyesno("Confirmar", "¿Limpiar TODAS las regiones OCR marcadas en esta sesión?", parent=self):
                  self.current_ocr_regions = []
                  # Actualizar UI manualmente si no hay panel
                  if self.preview_panel: self.preview_panel.update_preview(self.current_image_numpy, [], [])
                  self.update_all_button_states()
                  self.status_message("Regiones OCR sesión eliminadas.")


    def save_ocr_action(self):
        """Guarda las regiones OCR actuales (en memoria) para la plantilla en JSON."""
        if not self.current_template_name:
            messagebox.showerror("Error", "Seleccione una plantilla primero.", parent=self)
            return

        num_regions_mem = len(self.current_ocr_regions)
        logging.info(f"Guardando {num_regions_mem} regiones OCR para plantilla '{self.current_template_name}'")
        self.status_message("Guardando zonas OCR...")

        # La confirmación de borrado si está vacío la hace el panel, pero podemos añadir una general
        if not messagebox.askyesno("Confirmar Guardado OCR",
                                  f"Se guardarán {num_regions_mem} zona(s) OCR para la plantilla '{self.current_template_name}'.\n"
                                  f"Esto SOBRESCRIBIRÁ las zonas previamente guardadas para esta plantilla en\n"
                                  f"'{os.path.basename(OCR_MAPPING_FILE_PATH)}'.\n\n¿Continuar?", parent=self):
            self.status_message("Guardado OCR cancelado.")
            return

        try:
            ocr_mapping = load_ocr_data()
            # Actualizar o añadir la entrada para la plantilla actual
            ocr_mapping[self.current_template_name] = self.current_ocr_regions

            if save_ocr_data(ocr_mapping):
                self.ocr_regions_mapping = ocr_mapping # Actualizar estado interno
                messagebox.showinfo("Éxito", f"Zonas OCR guardadas para '{self.current_template_name}'.", parent=self)
                self.status_message(f"Zonas OCR guardadas para '{self.current_template_name}'.")
                # Los botones deberían seguir habilitados si corresponde
                self.update_all_button_states()
            else:
                # save_ocr_data ya muestra error
                self.status_message(f"Error al guardar zonas OCR para '{self.current_template_name}'.", level=logging.ERROR)

        except Exception as e:
             logging.exception(f"Error en save_ocr_action para '{self.current_template_name}'")
             messagebox.showerror("Error Guardando", f"Error inesperado guardando OCR:\n{e}", parent=self)
             self.status_message("Error guardando OCR.", level=logging.ERROR)


    # --- Método Callback para Resaltado ---
    def handle_ocr_selection_change(self, selected_indices):
            """Actualiza la preview cuando cambia la selección en OcrPanel."""
            logging.debug(f"Actualizando resaltado preview para índices: {selected_indices}")
            if self.preview_panel:
                 self.preview_panel.update_preview(
                     self.current_image_numpy,
                     self.current_ocr_regions,
                     selected_indices # Pasar los índices seleccionados
                 )


    # --- Métodos Utilidad y Cierre ---
    def status_message(self, message, level=logging.INFO):
        # (Sin cambios)
        fg = "black";
        try:
            if level == logging.ERROR: fg = "red"; logging.error(message)
            elif level == logging.WARNING: fg = "orange"; logging.warning(message)
            else: logging.info(message)
            if hasattr(self, 'status_label_var') and self.status_label_var: self.status_label_var.set(message)
            if hasattr(self, 'status_bar') and self.status_bar: self.status_bar.config(foreground=fg)
            self.update_idletasks()
        except Exception as e: print(f"[ERR STATUS] {message} ({e})")
    def _on_close(self):
        # (Sin cambios)
        logging.info("Solicitud cierre.");
        if messagebox.askokcancel("Salir", "¿Seguro?", parent=self): logging.info(f"{'='*20} App cerrada {'='*20}"); self.destroy()

# --- Punto de Entrada ---
if __name__ == "__main__":
    # (Sin cambios)
    os.makedirs(IMAGES_DIR, exist_ok=True); os.makedirs(CONFIG_DIR, exist_ok=True); os.makedirs(os.path.dirname(log_file_path), exist_ok=True)
    def handle_exception(et, ev, etb): logging.error("Excep Tk:", exc_info=(et,ev,etb)); messagebox.showerror("Error GUI", f"Error:\n{ev}\nLog: {log_file_path}.")
    tk.Tk.report_callback_exception = handle_exception
    try: app = TemplateManagerGUI(); app.mainloop()
    except Exception as e:
        logging.critical("Error fatal", exc_info=True);
        try: root=tk.Tk(); root.withdraw(); messagebox.showerror("Error Fatal", f"Error crítico:\n{e}")
        except: pass
        sys.exit(1)

# --- END OF FILE src/template_manager_gui.py ---