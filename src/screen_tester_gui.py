# --- START OF FILE src/screen_tester_gui.py ---
import tkinter as tk
from tkinter import ttk
from tkinter import font as tkFont
from tkinter import messagebox, simpledialog, filedialog
from utils import tk_select_roi
import os
import sys
import subprocess # Para lanzar el gestor de plantillas
import logging
import time # Para medir tiempo de ejecución
from PIL import Image, ImageTk, ImageDraw, ImageFont # Necesario para PreviewPanel

# --- Configuración de Rutas e Importaciones ---
# Asumiendo que este script está en efootball_automation/src/
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir) # Directorio efootball_automation/

# Añadir el directorio raíz al sys.path para asegurar imports
if project_root not in sys.path:
    sys.path.insert(0, project_root)
# Añadir src al path también puede ser útil si se ejecutan tests desde fuera
if current_dir not in sys.path:
    sys.path.insert(1, current_dir)

try:
    # Importar desde el módulo principal del recognizer
    from screen_recognizer import (
        ScreenRecognizer,
        load_json_mapping,
        save_json_mapping,
        OCR_MAPPING_FILE,
        STATE_ROIS_FILE,
        TEMPLATE_MAPPING_FILE,
        STATE_TRANSITIONS_FILE,
        IMAGES_DIR, # Necesario para cargar plantillas en preview
        CONFIG_DIR,
        PROJECT_DIR # Usar PROJECT_DIR de screen_recognizer
    )
    # Importar paneles desde el subdirectorio 'panels' dentro de 'src'
    from panels.control_panel import ControlPanel
    from panels.result_panel import ResultPanel
    from panels.preview_panel import PreviewPanel
    from panels.correction_panel import CorrectionPanel
    from panels.ocr_panel import OcrPanel # <-- Descomentado
    # from utils import tk_select_roi # <-- Se añadirá/creará después

except ImportError as e:
    # Intentar mostrar error de forma gráfica antes de salir
    try:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "Error Crítico de Importación",
            f"No se pudo importar un módulo necesario.\n"
            f"Asegúrese de que 'screen_recognizer.py' y los archivos en 'src/panels/' existan y sean accesibles.\n"
            f"Verifique también las dependencias (Pillow, OpenCV, etc.).\n\n"
            f"Error: {e}\n\n"
            f"Ruta de búsqueda actual:\n{sys.path}"
        )
    except Exception as tk_err:
        print(f"Error crítico de importación Y error al mostrar messagebox: {e}, {tk_err}")
    sys.exit(1)

# --- Configuración del Logging para la GUI ---
log_dir = os.path.join(PROJECT_DIR, "logs") # Usar PROJECT_DIR del recognizer
os.makedirs(log_dir, exist_ok=True)
log_file_path = os.path.join(log_dir, "tester_gui.log") # Nombre de log cambiado

logging.basicConfig(
    level=logging.INFO, # Nivel base para la GUI (DEBUG para más detalle)
    format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.FileHandler(log_file_path, encoding='utf-8', mode='a'), # Usar 'a' para append
        logging.StreamHandler() # Mostrar logs también en consola
    ]
)
logging.info(f"\n{'='*20} Iniciando Screen Tester GUI {'='*20}")

# --- Constantes de la GUI ---
APP_TITLE = "Screen Tester GUI v1.1" # Versión incrementada
MIN_WIDTH = 1000
MIN_HEIGHT = 700
DEFAULT_FONT_SIZE_GUI = 10 # Tamaño fuente base para la GUI
DEFAULT_THEME = 'clam' # Temas posibles: 'clam', 'alt', 'default', 'classic', 'vista', 'xpnative'

# --- Clase Principal de la GUI ---
class ScreenTesterGUI(tk.Tk):
    """
    Clase principal para la Interfaz Gráfica de Usuario del Screen Tester.
    Gestiona la ventana, los paneles y la interacción con ScreenRecognizer.
    """
    def __init__(self):
        super().__init__()
        logging.info("Inicializando la ventana principal de la GUI.")

        # --- Configuración Inicial de la Ventana ---
        self.title(APP_TITLE)
        self.minsize(MIN_WIDTH, MIN_HEIGHT)
        try:
            screen_width = self.winfo_screenwidth()
            screen_height = self.winfo_screenheight()
            x_coord = (screen_width // 2) - (MIN_WIDTH // 2)
            y_coord = (screen_height // 2) - (MIN_HEIGHT // 2)
            self.geometry(f"{MIN_WIDTH}x{MIN_HEIGHT}+{x_coord}+{y_coord}")
        except tk.TclError:
            logging.warning("No se pudo obtener información de pantalla para centrar ventana.")
            self.geometry(f"{MIN_WIDTH}x{MIN_HEIGHT}")
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # --- Estado Interno ---
        self.recognizer = None
        self.last_recognition_result = None
        self.current_template_name = None # Estado detectado o corregido actual
        self.status_label_var = tk.StringVar(value="Inicializando...")

        # --- Referencias a Paneles ---
        self.control_panel = None
        self.results_panel = None
        self.preview_panel = None
        self.correction_panel = None
        self.ocr_panel = None # <-- Ahora se usará

        # --- Inicializar ScreenRecognizer ---
        try:
            self.recognizer = ScreenRecognizer(
                monitor=1, resolution='4K', threshold=0.75,
                ocr_fallback_threshold=0.60, ocr_lang='spa+eng',
                ocr_config='--psm 6', ocr_apply_thresholding=True
            )
            logging.info("Instancia de ScreenRecognizer creada.")
        except Exception as e:
            logging.exception("Error crítico al inicializar ScreenRecognizer.")
            messagebox.showerror("Error Inicialización", f"No se pudo inicializar ScreenRecognizer:\n{e}")
            self._on_close(force=True)
            return

        # --- Configuración Estilos y Fuentes ---
        self._setup_styles_and_fonts()

        # --- Creación Widgets (Paneles) ---
        self._create_widgets()

        # --- Poblar datos iniciales (ComboBox) ---
        try:
            all_states = list(self.recognizer.templates.keys())
            if self.correction_panel:
                self.correction_panel.populate_combobox(all_states)
            else:
                logging.error("CorrectionPanel no creado antes de poblarlo.")
        except Exception as e:
            logging.exception("Error al obtener/poblar lista inicial de estados.")
            messagebox.showerror("Error", "No se pudo obtener lista inicial de estados.")

        # --- Estado Inicial UI ---
        self._reset_ui_state()

        logging.info("Inicialización de la GUI completada.")
        self.status_message("Listo.")

    def _setup_styles_and_fonts(self):
        """Configura los estilos ttk y las fuentes estándar."""
        logging.debug("Configurando estilos y fuentes.")
        self.style = ttk.Style()
        try:
            available_themes = self.style.theme_names()
            logging.debug(f"Temas ttk disponibles: {available_themes}")
            if DEFAULT_THEME in available_themes:
                self.style.theme_use(DEFAULT_THEME)
                logging.info(f"Usando tema ttk: '{DEFAULT_THEME}'")
            else:
                logging.warning(f"Tema '{DEFAULT_THEME}' no encontrado, usando tema por defecto: {self.style.theme_use()}")
        except tk.TclError as e:
             logging.warning(f"No se pudo establecer el tema ttk '{DEFAULT_THEME}', usando el predeterminado: {e}")

        self.default_font = tkFont.nametofont("TkDefaultFont")
        self.default_font.configure(size=DEFAULT_FONT_SIZE_GUI)
        self.heading_font = tkFont.Font(family=self.default_font['family'], size=DEFAULT_FONT_SIZE_GUI + 1, weight="bold")
        self.status_font = tkFont.Font(family=self.default_font['family'], size=DEFAULT_FONT_SIZE_GUI -1)
        self.bold_font = tkFont.Font(family=self.default_font['family'], size=DEFAULT_FONT_SIZE_GUI, weight="bold")

        self.option_add("*Font", self.default_font)
        self.style.configure("TLabelFrame", padding=8)
        self.style.configure("TLabelFrame.Label", font=self.heading_font, padding=(0, 0, 0, 5))
        self.style.configure("TButton", padding=5)
        self.style.configure("Status.TLabel", font=self.status_font, padding=5)
        self.style.configure("Result.TLabel", anchor="w")

    def _create_widgets(self):
        """Crea contenedores, instancia paneles y crea barra de estado."""
        logging.debug("Creando widgets principales y paneles.")
        main_frame = ttk.Frame(self, padding="10")
        main_frame.grid(row=0, column=0, sticky="nsew")
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        left_column = ttk.Frame(main_frame)
        left_column.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        main_frame.grid_columnconfigure(0, weight=1, minsize=350)

        right_column = ttk.Frame(main_frame)
        right_column.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        main_frame.grid_columnconfigure(1, weight=3)
        main_frame.grid_rowconfigure(0, weight=1)

        # --- Instanciación Paneles ---
        self.control_panel = ControlPanel(left_column, self, padding=10)
        self.control_panel.grid(row=0, column=0, sticky="new", pady=(0, 10))
        left_column.grid_rowconfigure(0, weight=0)
        left_column.grid_columnconfigure(0, weight=1)

        self.results_panel = ResultPanel(left_column, self, padding=10)
        self.results_panel.grid(row=1, column=0, sticky="new", pady=(0, 10))
        left_column.grid_rowconfigure(1, weight=0)

        self.correction_panel = CorrectionPanel(left_column, self, padding=10)
        # NO .grid() aquí
        left_column.grid_rowconfigure(2, weight=0)

        # Instanciar OcrPanel (sin grid)
        self.ocr_panel = OcrPanel(left_column, self, padding=10)
        # Esta fila SÍ debe expandirse si OcrPanel es visible
        left_column.grid_rowconfigure(3, weight=1)

        self.preview_panel = PreviewPanel(right_column, self, padding=10)
        self.preview_panel.grid(row=0, column=0, sticky="nsew")
        right_column.grid_rowconfigure(0, weight=1)
        right_column.grid_columnconfigure(0, weight=1)

        # --- Barra de Estado ---
        self.status_bar = ttk.Label(main_frame, textvariable=self.status_label_var, style="Status.TLabel", anchor="w", relief="sunken", borderwidth=1)
        self.status_bar.grid(row=1, column=0, columnspan=2, sticky="sew", pady=(10, 0))
        main_frame.grid_rowconfigure(1, weight=0)

        logging.debug("Paneles instanciados y colocados en la grid.")

    def _reset_ui_state(self):
        """Restablece la interfaz a su estado inicial."""
        logging.debug("Reseteando estado de la UI.")
        self.last_recognition_result = None
        self.current_template_name = None

        if self.results_panel: self.results_panel.clear_results()
        if self.preview_panel: self.preview_panel.clear_preview()
        if self.correction_panel: self.correction_panel.hide()
        if self.ocr_panel: self.ocr_panel.hide() # <-- Ocultar OCR

        if self.control_panel: self.control_panel.enable_buttons()
        self.status_message("Listo.")
        self.update_idletasks()

    def status_message(self, message, level=logging.INFO):
        """Actualiza barra de estado y log."""
        # (Implementación sin cambios respecto a la anterior)
        foreground_color = "black"
        try:
            if level == logging.ERROR: foreground_color = "red"; logging.error(message)
            elif level == logging.WARNING: foreground_color = "orange"; logging.warning(message)
            else: logging.info(message)
            if hasattr(self, 'status_label_var') and self.status_label_var: self.status_label_var.set(message)
            if hasattr(self, 'status_bar') and self.status_bar: self.status_bar.config(foreground=foreground_color)
            self.update_idletasks()
        except Exception as e: print(f"[ERROR EN STATUS] {message} ({e})")

    def run_test(self):
        """Ejecuta el reconocimiento de pantalla."""
        logging.info("Botón 'Reconocer Pantalla' presionado.")
        self.status_message("Reconociendo pantalla...", level=logging.DEBUG)

        # 1. Deshabilitar botones y limpiar paneles contextuales
        if self.control_panel: self.control_panel.disable_buttons()
        if self.results_panel: self.results_panel.clear_results()
        if self.correction_panel: self.correction_panel.hide()
        if self.ocr_panel: self.ocr_panel.hide() # <-- Ocultar OCR
        self.update()

        # 2. Ejecutar reconocimiento
        start_rec_time = time.time()
        try:
            result = self.recognizer.recognize_screen_for_test()
            self.last_recognition_result = result
            rec_time = result.get('detection_time_s', time.time() - start_rec_time)
            logging.info(f"Reconocimiento completado en {rec_time:.3f}s.")

            # 3. Actualizar paneles con resultado
            if self.results_panel: self.results_panel.update_results(result)
            if self.preview_panel:
                capture = result.get('captured_image')
                state_name = result.get('state', 'N/A')
                method = result.get('method', 'N/A')
                info = f"Captura ({method} -> {state_name})"
                self.preview_panel.update_preview(capture, info_text=info)

            # 4. Mostrar/Ocultar panel OCR según el método <--- MODIFICADO
            if result.get('method') == 'ocr' and self.ocr_panel:
                ocr_data = result.get('ocr_results')
                self.ocr_panel.populate_ocr_tree(ocr_data)
                self.ocr_panel.show()
                if self.correction_panel: self.correction_panel.hide() # Ocultar corrección
            # No necesitamos ocultar explícitamente aquí, _reset_ui_state lo hace al inicio

            self.status_message(f"Reconocimiento finalizado: {result.get('state', 'Error')}")

        except Exception as e:
            rec_time = time.time() - start_rec_time
            logging.exception("Error durante recognize_screen_for_test.")
            messagebox.showerror("Error Reconocimiento", f"Ocurrió un error:\n{e}")
            error_result = {'method': 'error', 'state': 'error', 'error_message': str(e), 'detection_time_s': rec_time, 'captured_image': None}
            self.last_recognition_result = error_result
            if self.results_panel: self.results_panel.update_results(error_result)
            if self.preview_panel: self.preview_panel.clear_preview()
            self.status_message(f"Error durante el reconocimiento: {e}", level=logging.ERROR)

        finally:
            # 5. Habilitar botones de control
            if self.control_panel: self.control_panel.enable_buttons()

    def reload_recognizer_data(self):
        """Recarga datos de configuración."""
        # (Implementación sin cambios)
        logging.info("Botón 'Recargar Datos' presionado.")
        self.status_message("Recargando datos...", level=logging.DEBUG)
        try:
            if self.control_panel: self.control_panel.disable_buttons()
            self.update()
            self.recognizer.reload_data()
            all_states = list(self.recognizer.templates.keys())
            if self.correction_panel: self.correction_panel.populate_combobox(all_states)
            self._reset_ui_state()
            self.status_message("Datos recargados exitosamente.")
            messagebox.showinfo("Recarga Exitosa", "Datos recargados.")
        except Exception as e:
            logging.exception("Error durante la recarga de datos.")
            self.status_message(f"Error al recargar datos: {e}", level=logging.ERROR)
            messagebox.showerror("Error Recarga", f"Ocurrió un error:\n{e}")
        finally:
             if self.control_panel: self.control_panel.enable_buttons()

    def confirm_detection(self):
        """Confirma la detección actual."""
        # (Añadir ocultar ocr_panel)
        logging.info("Botón 'Confirmar Detección' presionado.")
        if not self.last_recognition_result or self.last_recognition_result.get('state', 'unknown') in ['unknown', 'error']:
             messagebox.showwarning("Sin Detección", "No hay detección válida para confirmar.")
             return
        detected_state = self.last_recognition_result.get('state')
        logging.info(f"CONFIRMACIÓN: Estado '{detected_state}' detectado correctamente.")
        self.status_message(f"Detección '{detected_state}' confirmada.")
        if self.results_panel: self.results_panel.disable_confirm_deny()
        if self.correction_panel: self.correction_panel.hide()
        if self.ocr_panel: self.ocr_panel.hide() # <-- Ocultar OCR

    def deny_detection(self):
        """Niega la detección y muestra panel corrección."""
        # (Añadir ocultar ocr_panel)
        logging.info("Botón 'Negar Detección' presionado.")
        if not self.last_recognition_result or self.last_recognition_result.get('state', 'unknown') in ['unknown', 'error']:
             messagebox.showwarning("Sin Detección", "No hay detección válida para negar.")
             return
        original_state = self.last_recognition_result.get('state')
        logging.info(f"NEGACIÓN: Detección '{original_state}' incorrecta.")
        self.status_message(f"Detección '{original_state}' negada. Seleccione corrección.")

        if self.results_panel:
            self.results_panel.disable_confirm_deny()
            self.results_panel.enable_roi_buttons()
            self.results_panel.update_roi_label(original_state)

        if self.correction_panel:
             all_states = list(self.recognizer.templates.keys())
             self.correction_panel.populate_combobox(all_states)
             self.correction_panel.show()

        if self.ocr_panel: self.ocr_panel.hide() # <-- Ocultar OCR
        if self.preview_panel: self.preview_panel.clear_preview()
        self.current_template_name = None

    def on_correct_state_selected(self, selected_state):
        """Callback cuando se selecciona estado en CorrectionPanel."""
        # (Implementación sin cambios)
        if not selected_state: return
        logging.info(f"Estado corregido seleccionado: {selected_state}")
        self.current_template_name = selected_state
        self.status_message(f"Estado corregido: '{selected_state}'. Mostrando plantilla.")
        if self.results_panel: self.results_panel.update_roi_label(selected_state)
        template_path = None
        first_template_file = "N/A"
        if self.recognizer and selected_state in self.recognizer.template_names_mapping:
            template_files = self.recognizer.template_names_mapping[selected_state]
            if template_files and isinstance(template_files, list) and len(template_files) > 0:
                first_template_file = template_files[0]
                res_dir = os.path.join(IMAGES_DIR, self.recognizer.resolution)
                potential_path = os.path.join(res_dir, first_template_file)
                if os.path.exists(potential_path): template_path = potential_path
                else:
                     template_path_base = os.path.join(IMAGES_DIR, first_template_file)
                     if os.path.exists(template_path_base): template_path = template_path_base; logging.debug(f"Plantilla base: {template_path}")
                     else: logging.warning(f"No se encontró plantilla '{first_template_file}' ni en '{res_dir}' ni en '{IMAGES_DIR}'")
        if self.preview_panel:
            if template_path: self.preview_panel.update_preview(template_path, info_text=f"Plantilla: {selected_state}\n({first_template_file})")
            else: self.preview_panel.update_preview(None, info_text=f"Plantilla no encontrada para\n{selected_state}")

    def log_correct_state(self):
        """Registra la corrección manual en log."""
        # (Implementación sin cambios)
        logging.info("Botón 'Registrar Corrección (Log)' presionado.")
        selected_state = None
        if self.correction_panel: selected_state = self.correction_panel.get_selected_state()
        original_state = self.last_recognition_result.get('state', 'N/A') if self.last_recognition_result else 'N/A'
        if selected_state:
            log_message = f"CORRECCIÓN MANUAL: Detección original '{original_state}' -> Corregido a '{selected_state}'"
            logging.info(log_message)
            self.status_message(f"Corrección a '{selected_state}' registrada en log.")
        else:
            messagebox.showwarning("Sin Selección", "Seleccione un estado correcto antes de registrar.")
            self.status_message("Seleccione un estado para registrar.", level=logging.WARNING)

    # --- Métodos OCR (IMPLEMENTADOS) ---

    def confirm_ocr_text(self, selected_details):
        """Confirma el texto OCR extraído y lo añade a ocr_regions.json."""
        logging.info("Procesando confirmación de texto OCR extraído...")
        if not selected_details:
            messagebox.showwarning("Sin Selección", "No hay regiones seleccionadas para confirmar.")
            return
        if not self.last_recognition_result or self.last_recognition_result.get('method') != 'ocr':
            messagebox.showerror("Error", "No hay un resultado OCR válido activo para modificar.")
            return

        current_state = self.last_recognition_result.get('state')
        texts_to_add = {detail['index']: detail['extracted_text'] for detail in selected_details if detail.get('extracted_text')}

        if not texts_to_add:
             messagebox.showinfo("Nada que Añadir", "Ninguna de las regiones seleccionadas tiene texto extraído para añadir.")
             return

        # Pedir confirmación al usuario
        num_regions = len(texts_to_add)
        msg = f"¿Añadir el texto extraído como válido para {num_regions} región(es) del estado '{current_state}'?\n\n"
        for idx, text in texts_to_add.items():
            msg += f"  - Región {idx}: '{text}'\n"
        msg += f"\nEsto modificará '{os.path.basename(OCR_MAPPING_FILE)}'."

        if not messagebox.askyesno("Confirmar Texto Extraído", msg):
            self.status_message("Confirmación de texto OCR cancelada.")
            return

        self.status_message(f"Guardando textos extraídos para '{current_state}'...", level=logging.DEBUG)

        try:
            # Cargar el mapeo OCR actual
            ocr_mapping = load_json_mapping(OCR_MAPPING_FILE, "regiones OCR")

            if current_state not in ocr_mapping or not isinstance(ocr_mapping[current_state], list):
                logging.error(f"Estado '{current_state}' no encontrado o formato inválido en {OCR_MAPPING_FILE}")
                messagebox.showerror("Error de Datos", f"El estado '{current_state}' no se encontró o tiene formato incorrecto en el archivo OCR.")
                return

            modified = False
            state_regions = ocr_mapping[current_state]

            # Modificar el diccionario cargado
            for region_data in state_regions:
                 # Usar el índice original guardado en el resultado OCR (si existe)
                 # Necesitamos una forma fiable de mapear el índice del Treeview (o del dict original)
                 # a la entrada correcta en la lista `state_regions`.
                 # ASUMCIÓN: El índice `idx` en `texts_to_add` corresponde al índice
                 # en la lista original `self.recognizer.ocr_regions_mapping[current_state]`
                 # y por tanto a la lista `state_regions` cargada aquí. ¡Esto es FRÁGIL si el orden cambia!
                 # Una forma más robusta sería buscar por coordenadas, pero es más complejo.
                 # Por simplicidad, usaremos el índice, asumiendo que el orden se mantiene.

                 try:
                    # Necesitamos el índice real de la lista `state_regions`
                    # No podemos usar directamente el `idx` de `texts_to_add` si no coincide
                    # con la posición en la lista `state_regions`.
                    # REVISAR: ¿Cómo asegurar que el `idx` del resultado mapea a la entrada correcta?
                    # El `idx` en `ocr_results` SÍ corresponde al índice de la lista en el mapping original.
                    current_region_idx = state_regions.index(region_data) # Obtener índice actual

                    if current_region_idx in texts_to_add:
                        text_to_add = texts_to_add[current_region_idx].strip()
                        if text_to_add: # No añadir vacío
                            if 'expected_text' not in region_data or not isinstance(region_data['expected_text'], list):
                                region_data['expected_text'] = [] # Inicializar si no existe o es inválida

                            # Añadir solo si no existe ya (insensible a mayúsculas/espacios)
                            existing_lower = {t.lower().strip() for t in region_data['expected_text']}
                            if text_to_add.lower().strip() not in existing_lower:
                                region_data['expected_text'].append(text_to_add)
                                logging.info(f"  Añadido texto '{text_to_add}' a región {current_region_idx} de '{current_state}'.")
                                modified = True
                            else:
                                logging.debug(f"  Texto '{text_to_add}' ya existe en región {current_region_idx}. No se añade.")

                 except ValueError:
                     # Esto pasaría si `region_data` no estuviera en la lista, lo cual no debería ocurrir
                     logging.error(f"Error interno: region_data no encontrada en state_regions.")
                     continue
                 except KeyError:
                      # Esto pasaría si un índice de texts_to_add no es válido
                      logging.error(f"Índice de región {idx} inválido.")
                      continue


            # Guardar si hubo modificaciones
            if modified:
                if save_json_mapping(ocr_mapping, OCR_MAPPING_FILE, "regiones OCR"):
                    logging.info(f"Archivo {OCR_MAPPING_FILE} actualizado con textos confirmados.")
                    self.status_message(f"Textos confirmados guardados para '{current_state}'. Recargando...")
                    # Recargar datos y refrescar vista
                    self.recognizer.reload_data()
                    # Necesitamos el NUEVO ocr_results para refrescar la vista
                    # Podríamos re-ejecutar el reconocimiento o simularlo
                    # Por ahora, solo limpiamos la selección para evitar inconsistencias
                    if self.ocr_panel: self.ocr_panel.clear_selection_and_entry()
                    self.status_message(f"Textos confirmados guardados y datos recargados.")
                else:
                    messagebox.showerror("Error Guardando", f"No se pudo guardar el archivo {OCR_MAPPING_FILE}.")
                    self.status_message(f"Error al guardar {OCR_MAPPING_FILE}.", level=logging.ERROR)
            else:
                 self.status_message("No se realizaron nuevos añadidos (textos ya existían o estaban vacíos).")

        except Exception as e:
            logging.exception("Error procesando la confirmación de texto OCR.")
            messagebox.showerror("Error", f"Ocurrió un error al confirmar texto OCR:\n{e}")
            self.status_message("Error al confirmar texto OCR.", level=logging.ERROR)


    def save_edited_ocr_text(self, selected_detail, edited_text):
        """Guarda el texto OCR editado manualmente en ocr_regions.json."""
        logging.info("Procesando guardado de texto OCR editado...")
        if not selected_detail:
            messagebox.showerror("Error", "No hay región seleccionada para guardar el texto editado.")
            return
        if not self.last_recognition_result or self.last_recognition_result.get('method') != 'ocr':
             messagebox.showerror("Error", "No hay un resultado OCR válido activo para modificar.")
             return

        current_state = self.last_recognition_result.get('state')
        region_idx_to_edit = selected_detail['index'] # Índice original

        # Procesar texto editado: separar por '|' y limpiar
        new_expected_texts = [text.strip() for text in edited_text.split('|') if text.strip()]

        # Pedir confirmación
        msg = (f"¿Reemplazar los textos esperados para la región {region_idx_to_edit} del estado '{current_state}' "
               f"con:\n\n  {new_expected_texts}\n\n"
               f"Esto SOBRESCRIBIRÁ los valores anteriores en '{os.path.basename(OCR_MAPPING_FILE)}'.")

        if not messagebox.askyesno("Confirmar Guardar Texto Editado", msg):
            self.status_message("Guardado de texto editado cancelado.")
            return

        self.status_message(f"Guardando texto editado para región {region_idx_to_edit} de '{current_state}'...", level=logging.DEBUG)

        try:
            # Cargar el mapeo OCR actual
            ocr_mapping = load_json_mapping(OCR_MAPPING_FILE, "regiones OCR")

            if current_state not in ocr_mapping or not isinstance(ocr_mapping[current_state], list):
                logging.error(f"Estado '{current_state}' no encontrado o formato inválido en {OCR_MAPPING_FILE}")
                messagebox.showerror("Error de Datos", f"El estado '{current_state}' no se encontró o tiene formato incorrecto en el archivo OCR.")
                return

            state_regions = ocr_mapping[current_state]

            # Encontrar la región correcta usando el índice (asumiendo orden consistente)
            if 0 <= region_idx_to_edit < len(state_regions):
                region_to_update = state_regions[region_idx_to_edit]

                # Actualizar la lista 'expected_text'
                region_to_update['expected_text'] = new_expected_texts
                logging.info(f"  Actualizado 'expected_text' para región {region_idx_to_edit} de '{current_state}' a: {new_expected_texts}")

                # Guardar el mapeo modificado
                if save_json_mapping(ocr_mapping, OCR_MAPPING_FILE, "regiones OCR"):
                    logging.info(f"Archivo {OCR_MAPPING_FILE} actualizado con texto editado.")
                    self.status_message(f"Texto editado guardado para región {region_idx_to_edit}. Recargando...")
                    # Recargar datos y refrescar vista
                    self.recognizer.reload_data()
                    # Limpiar selección para reflejar cambio
                    if self.ocr_panel: self.ocr_panel.clear_selection_and_entry()
                    self.status_message(f"Texto editado guardado y datos recargados.")
                else:
                    messagebox.showerror("Error Guardando", f"No se pudo guardar el archivo {OCR_MAPPING_FILE}.")
                    self.status_message(f"Error al guardar {OCR_MAPPING_FILE}.", level=logging.ERROR)
            else:
                 logging.error(f"Índice de región {region_idx_to_edit} fuera de rango para el estado '{current_state}'.")
                 messagebox.showerror("Error de Índice", f"El índice de la región ({region_idx_to_edit}) parece ser inválido.")
                 self.status_message("Error: Índice de región inválido.", level=logging.ERROR)


        except Exception as e:
            logging.exception("Error procesando el guardado de texto OCR editado.")
            messagebox.showerror("Error", f"Ocurrió un error al guardar texto OCR editado:\n{e}")
            self.status_message("Error al guardar texto OCR editado.", level=logging.ERROR)


    # --- Métodos ROI (Stubs - Implementación futura) ---

    # (Asegúrate de tener 'from utils import tk_select_roi' al principio)
    # (Asegúrate de tener 'from screen_recognizer import STATE_ROIS_FILE, load_json_mapping, save_json_mapping' al principio)

    def define_roi_for_state(self):
        """Abre el selector visual para definir/editar el ROI de un estado."""
        logging.info("Botón 'Definir/Editar ROI' presionado.")

        # 1. Determinar para qué estado se define el ROI
        state_to_edit = self.current_template_name  # Usar el estado corregido si existe
        if not state_to_edit and self.last_recognition_result:
            state_to_edit = self.last_recognition_result.get('state')  # Usar el detectado si no hay corrección

        if not state_to_edit or state_to_edit in ['unknown', 'error']:
            messagebox.showwarning("Seleccionar Estado",
                                   "Por favor, primero seleccione o detecte un estado válido "
                                   "para definir/editar su ROI.", parent=self)  # Especificar padre para messagebox
            self.status_message("Seleccione un estado para definir/editar ROI.", level=logging.WARNING)
            return

        self.status_message(f"Abriendo selector de ROI para '{state_to_edit}'...")
        self.update_idletasks()  # Actualizar UI antes de bloquear

        # --- Llamar a la función de selección ---
        # Pasar 'self' (la ventana principal) como padre para tk_select_roi
        roi_coords = tk_select_roi(self, window_title=f"Definir ROI para: {state_to_edit}")

        # --- Procesar el resultado ---
        if roi_coords:
            logging.info(f"ROI seleccionado para '{state_to_edit}': {roi_coords}")
            self.status_message(f"ROI seleccionado para '{state_to_edit}'. Guardando...", level=logging.DEBUG)

            # Cargar, modificar y guardar state_rois.json
            try:
                all_rois = load_json_mapping(STATE_ROIS_FILE, "ROIs de estado")
                all_rois[state_to_edit] = roi_coords  # Añadir o actualizar la entrada

                if save_json_mapping(all_rois, STATE_ROIS_FILE, "ROIs de estado"):
                    logging.info(f"Archivo {STATE_ROIS_FILE} actualizado con ROI para '{state_to_edit}'.")
                    self.status_message(f"ROI para '{state_to_edit}' guardado. Recargando datos...")
                    # Recargar datos en recognizer y actualizar UI
                    self.recognizer.reload_data()
                    if self.results_panel:
                        self.results_panel.update_roi_label(state_to_edit)  # Actualizar etiqueta
                    # Opcional: Actualizar previsualización para mostrar el indicador ROI
                    # self.preview_panel.draw_roi_indicator(roi_coords) # Necesitaría implementación en PreviewPanel
                    self.status_message(f"ROI para '{state_to_edit}' guardado y datos recargados.")
                else:
                    messagebox.showerror("Error Guardando", f"No se pudo guardar el archivo {STATE_ROIS_FILE}.",
                                         parent=self)
                    self.status_message(f"Error al guardar archivo JSON con ROI para '{state_to_edit}'.",
                                        level=logging.ERROR)

            except Exception as e:
                logging.exception(f"Error al guardar ROI para '{state_to_edit}'")
                messagebox.showerror("Error Guardando ROI", f"Ocurrió un error al guardar el ROI:\n{e}", parent=self)
                self.status_message(f"Error al guardar ROI para '{state_to_edit}': {e}", level=logging.ERROR)

        else:  # roi_coords es None (cancelado)
            logging.info(f"Selección de ROI para '{state_to_edit}' cancelada.")
            self.status_message(f"Definición de ROI para '{state_to_edit}' cancelada.")

    # --- Dentro de la clase ScreenTesterGUI en screen_tester_gui.py ---

    # (Asegúrate de tener las importaciones necesarias: os, logging, messagebox,
    #  y desde screen_recognizer: STATE_ROIS_FILE, load_json_mapping, save_json_mapping)

    def remove_roi_for_state(self):
        """Elimina el ROI asociado a un estado del archivo state_rois.json."""
        logging.info("Botón 'Eliminar ROI' presionado.")

        # 1. Determinar estado a modificar
        state_to_modify = self.current_template_name  # Priorizar estado corregido seleccionado
        if not state_to_modify and self.last_recognition_result:
            # Si no hay corrección, usar el último estado detectado (si es válido)
            state_to_modify = self.last_recognition_result.get('state')

        # 2. Validar Estado
        if not state_to_modify or state_to_modify in ['unknown', 'error']:
            messagebox.showwarning("Seleccionar Estado",
                                   "Por favor, primero seleccione o detecte un estado válido "
                                   "para poder eliminar su ROI.", parent=self)
            self.status_message("Seleccione un estado para eliminar ROI.", level=logging.WARNING)
            return

        # 3. Verificar si existe ROI para ese estado en la instancia actual del recognizer
        #    (Esta es la forma más rápida de saber si hay algo que eliminar)
        if not (self.recognizer and state_to_modify in self.recognizer.state_rois):
            messagebox.showinfo("Sin ROI",
                                f"El estado '{state_to_modify}' no tiene actualmente un ROI definido "
                                f"en la configuración cargada.", parent=self)
            self.status_message(f"No hay ROI definido para '{state_to_modify}'.", level=logging.INFO)
            # Asegurar que la etiqueta ROI esté actualizada
            if self.results_panel: self.results_panel.update_roi_label(state_to_modify)
            return

        # 4. Pedir confirmación al usuario
        if not messagebox.askyesno("Confirmar Eliminación",
                                   f"¿Está seguro de que desea eliminar permanentemente el ROI "
                                   f"para el estado '{state_to_modify}' del archivo "
                                   f"'{os.path.basename(STATE_ROIS_FILE)}'?", parent=self):
            self.status_message(f"Eliminación de ROI para '{state_to_modify}' cancelada.")
            logging.info(f"Eliminación de ROI para '{state_to_modify}' cancelada por el usuario.")
            return

        # 5. Proceder con la eliminación
        self.status_message(f"Eliminando ROI para '{state_to_modify}'...", level=logging.DEBUG)
        try:
            # Cargar el archivo JSON actual
            all_rois = load_json_mapping(STATE_ROIS_FILE, "ROIs de estado")

            # Verificar si la clave existe en el archivo (doble chequeo)
            if state_to_modify in all_rois:
                # Eliminar la entrada del diccionario
                del all_rois[state_to_modify]
                logging.info(f"Entrada para '{state_to_modify}' eliminada del diccionario ROIs.")

                # Guardar el diccionario modificado de nuevo en el archivo JSON
                if save_json_mapping(all_rois, STATE_ROIS_FILE, "ROIs de estado"):
                    logging.info(f"Archivo {STATE_ROIS_FILE} guardado sin ROI para '{state_to_modify}'.")
                    self.status_message(f"ROI para '{state_to_modify}' eliminado. Recargando datos...")

                    # Recargar datos en el recognizer para aplicar el cambio
                    self.recognizer.reload_data()

                    # Actualizar la etiqueta de estado del ROI en la GUI
                    if self.results_panel:
                        self.results_panel.update_roi_label(state_to_modify)

                    # Opcional: Actualizar la previsualización si mostraba un indicador ROI
                    # if self.preview_panel:
                    #     # Necesitaríamos saber si la preview actual es de este estado
                    #     # y quitar el indicador. Podría requerir más lógica.
                    #     pass

                    self.status_message(f"ROI para '{state_to_modify}' eliminado y datos recargados.")
                else:
                    # Error al guardar el archivo
                    messagebox.showerror("Error Guardando",
                                         f"No se pudo guardar el archivo {STATE_ROIS_FILE} sin el ROI.", parent=self)
                    self.status_message(f"Error al guardar archivo JSON sin ROI para '{state_to_modify}'.",
                                        level=logging.ERROR)
            else:
                # La clave no estaba en el archivo (quizás se eliminó manualmente?)
                logging.warning(
                    f"Se intentó eliminar ROI para '{state_to_modify}', pero no se encontró en {STATE_ROIS_FILE}.")
                messagebox.showwarning("ROI No Encontrado",
                                       f"El ROI para '{state_to_modify}' no se encontró en el archivo "
                                       f"'{os.path.basename(STATE_ROIS_FILE)}' al intentar eliminarlo.", parent=self)
                # Aún así, recargar datos podría ser bueno por si acaso y actualizar UI
                self.recognizer.reload_data()
                if self.results_panel: self.results_panel.update_roi_label(state_to_modify)
                self.status_message(f"ROI para '{state_to_modify}' no encontrado en archivo.", level=logging.WARNING)

        except Exception as e:
            # Error durante carga, eliminación o guardado
            logging.exception(f"Error al eliminar ROI para '{state_to_modify}'")
            messagebox.showerror("Error Eliminando ROI", f"Ocurrió un error al eliminar el ROI:\n{e}", parent=self)
            self.status_message(f"Error al eliminar ROI para '{state_to_modify}': {e}", level=logging.ERROR)


    def launch_template_manager(self):
        """Lanza la GUI del gestor de plantillas."""
        # (Implementación sin cambios)
        logging.info("Botón 'Abrir Gestor Plantillas' presionado.")
        manager_script = os.path.join(current_dir, "template_manager_gui.py")
        if not os.path.exists(manager_script):
             logging.error(f"No se encontró 'template_manager_gui.py' en {current_dir}")
             messagebox.showerror("Error", f"Script no encontrado:\n{manager_script}")
             self.status_message("Error: No se encontró template_manager_gui.py", level=logging.ERROR)
             return
        try:
            python_executable = sys.executable
            logging.info(f"Lanzando '{manager_script}' con '{python_executable}'...")
            subprocess.Popen([python_executable, manager_script])
            self.status_message("Gestor lanzado. Recargue datos si realiza cambios.")
            messagebox.showinfo("Gestor Lanzado", "Gestor de Plantillas iniciado.\nRecuerde 'Recargar Datos Config.' aquí si hace cambios.")
        except Exception as e:
            logging.exception("Error al lanzar el gestor de plantillas.")
            messagebox.showerror("Error al Lanzar", f"No se pudo lanzar:\n{e}")
            self.status_message(f"Error al lanzar gestor: {e}", level=logging.ERROR)

    def _on_close(self, force=False):
        """Acciones al cerrar la ventana."""
        # (Implementación sin cambios)
        logging.info("Solicitud de cierre...")
        if force or messagebox.askokcancel("Salir", "¿Está seguro de que desea salir?"):
            logging.info(f"{'='*20} Aplicación cerrada {'='*20}")
            self.destroy()

# --- Punto de Entrada Principal ---
if __name__ == "__main__":
    # (Implementación sin cambios)
    def handle_exception(exc_type, exc_value, exc_traceback):
        logging.error("Excepción Tkinter:", exc_info=(exc_type, exc_value, exc_traceback))
        messagebox.showerror("Error GUI", f"Error interno:\n{exc_value}\nConsulte {log_file_path}.")
    tk.Tk.report_callback_exception = handle_exception
    try:
        app = ScreenTesterGUI()
        if app.recognizer: app.mainloop()
        else: logging.critical("App no iniciada por fallo en Recognizer.")
    except Exception as e:
        logging.exception("Error fatal no controlado.")
        try:
             root = tk.Tk(); root.withdraw()
             messagebox.showerror("Error Fatal", f"Error inesperado:\n{e}\nConsulte {log_file_path}.")
        except: pass
        sys.exit(1)

# --- END OF FILE src/screen_tester_gui.py ---