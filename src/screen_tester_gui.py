# --- START OF FILE src/screen_tester_gui.py ---
import time
import tkinter as tk
from tkinter import ttk
from tkinter import font as tkFont
from tkinter import messagebox, simpledialog, filedialog
from src.panels.ocr_panel import OcrPanel
import os
import sys
import subprocess # Para lanzar el gestor de plantillas
import logging
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
    # from panels.ocr_panel import OcrPanel # <-- Se añadirá después
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
APP_TITLE = "Screen Tester GUI v1.0"
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
        # Centrar ventana al iniciar (aproximado)
        try:
            screen_width = self.winfo_screenwidth()
            screen_height = self.winfo_screenheight()
            x_coord = (screen_width // 2) - (MIN_WIDTH // 2)
            y_coord = (screen_height // 2) - (MIN_HEIGHT // 2)
            self.geometry(f"{MIN_WIDTH}x{MIN_HEIGHT}+{x_coord}+{y_coord}")
        except tk.TclError:
            logging.warning("No se pudo obtener información de pantalla para centrar ventana.")
            self.geometry(f"{MIN_WIDTH}x{MIN_HEIGHT}")

        self.protocol("WM_DELETE_WINDOW", self._on_close) # Manejar cierre

        # --- Estado Interno ---
        self.recognizer = None
        self.last_recognition_result = None # Guarda el último dict de resultado
        # self.current_preview_image_tk = None # Manejado por PreviewPanel
        # self.current_preview_image_pil = None # Manejado por PreviewPanel
        self.current_template_name = None # Estado detectado o corregido actualmente relevante
        self.status_label_var = tk.StringVar(value="Inicializando...")

        # --- Referencias a Paneles (se asignarán en _create_widgets) ---
        self.control_panel = None
        self.results_panel = None
        self.preview_panel = None
        self.correction_panel = None
        self.ocr_panel = None # Para futura implementación

        # --- Inicializar ScreenRecognizer ---
        try:
            # Configuración del recognizer (podría venir de un archivo de config de la GUI)
            self.recognizer = ScreenRecognizer(
                monitor=1,
                resolution='4K', # Asegúrate que esta resolución exista en images/
                threshold=0.75,
                ocr_fallback_threshold=0.60,
                ocr_lang='spa+eng',
                ocr_config='--psm 6',
                ocr_apply_thresholding=True
            )
            logging.info("Instancia de ScreenRecognizer creada exitosamente.")
        except Exception as e:
            logging.exception("Error crítico al inicializar ScreenRecognizer.")
            messagebox.showerror(
                "Error de Inicialización",
                f"No se pudo inicializar ScreenRecognizer.\n"
                f"Revise la configuración y los archivos necesarios (plantillas, JSONs).\nError: {e}"
            )
            self._on_close(force=True) # Cerrar la aplicación si el recognizer falla
            return

        # --- Configuración de Estilos y Fuentes ---
        self._setup_styles_and_fonts()

        # --- Creación de Widgets (Paneles principales) ---
        self._create_widgets()

        # --- Poblar datos iniciales ---
        try:
            all_states = list(self.recognizer.templates.keys())
            if self.correction_panel:
                self.correction_panel.populate_combobox(all_states)
            else:
                 logging.error("CorrectionPanel no fue creado antes de intentar poblarlo.")
        except Exception as e:
            logging.exception("Error al obtener o poblar lista inicial de estados.")
            messagebox.showerror("Error", "No se pudo obtener la lista inicial de estados del Recognizer.")


        # --- Estado Inicial de la UI ---
        self._reset_ui_state() # Establece estado limpio y visibilidad inicial

        logging.info("Inicialización de la GUI completada.")
        self.status_message("Listo.") # Mensaje final de inicialización

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

        # Fuentes estándar (usar un tamaño base para la GUI)
        self.default_font = tkFont.nametofont("TkDefaultFont")
        self.default_font.configure(size=DEFAULT_FONT_SIZE_GUI)
        # Crear otras fuentes basadas en la por defecto si es necesario
        self.heading_font = tkFont.Font(family=self.default_font['family'], size=DEFAULT_FONT_SIZE_GUI + 1, weight="bold")
        self.status_font = tkFont.Font(family=self.default_font['family'], size=DEFAULT_FONT_SIZE_GUI -1)
        self.bold_font = tkFont.Font(family=self.default_font['family'], size=DEFAULT_FONT_SIZE_GUI, weight="bold")

        # Aplicar fuente por defecto a widgets estándar
        self.option_add("*Font", self.default_font)

        # Estilos personalizados
        self.style.configure("TLabelFrame", padding=8)
        self.style.configure("TLabelFrame.Label", font=self.heading_font, padding=(0, 0, 0, 5)) # Espacio debajo del título
        self.style.configure("TButton", padding=5)
        self.style.configure("Status.TLabel", font=self.status_font, padding=5) # Estilo para la barra de estado
        # Estilo para etiquetas de resultados (por si queremos diferenciarlas)
        self.style.configure("Result.TLabel", anchor="w")

    def _create_widgets(self):
        """Crea los contenedores principales, instancia los paneles y crea la barra de estado."""
        logging.debug("Creando widgets principales y paneles.")

        # --- Contenedor Principal ---
        main_frame = ttk.Frame(self, padding="10")
        main_frame.grid(row=0, column=0, sticky="nsew")
        # Configurar redimensionamiento de la ventana principal
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # --- Columna Izquierda (Controles y Datos) ---
        left_column = ttk.Frame(main_frame)
        left_column.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        main_frame.grid_columnconfigure(0, weight=1, minsize=350) # Col izq. peso 1, ancho mínimo

        # --- Columna Derecha (Previsualización) ---
        right_column = ttk.Frame(main_frame)
        right_column.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        main_frame.grid_columnconfigure(1, weight=3) # Col der. más ancha

        # Fila principal se expande verticalmente
        main_frame.grid_rowconfigure(0, weight=1)

        # --- Instanciación de Paneles ---
        # Los paneles reciben 'self' (la app principal) para poder llamar a sus métodos

        # Panel de Control
        self.control_panel = ControlPanel(left_column, self, padding=10)
        self.control_panel.grid(row=0, column=0, sticky="new", pady=(0, 10))
        left_column.grid_rowconfigure(0, weight=0) # No expandir verticalmente
        left_column.grid_columnconfigure(0, weight=1) # Expandir horizontalmente

        # Panel de Resultados
        self.results_panel = ResultPanel(left_column, self, padding=10)
        self.results_panel.grid(row=1, column=0, sticky="new", pady=(0, 10))
        left_column.grid_rowconfigure(1, weight=0) # No expandir

        # Panel de Corrección Manual (Instanciar pero NO mostrar con grid aquí)
        self.correction_panel = CorrectionPanel(left_column, self, padding=10)
        # Se mostrará con .grid() en deny_detection()
        left_column.grid_rowconfigure(2, weight=0) # Fila para corrección, no expandir

        # Panel de Detalles OCR (Placeholder para el futuro, instanciar pero NO mostrar)
        self.ocr_panel = OcrPanel(left_column, self, padding=10)
        # Se mostrará con .grid() cuando sea necesario
        # Hacer que esta fila SÍ se expanda si el panel OCR es grande
        left_column.grid_rowconfigure(3, weight=1)



        # Panel de Previsualización
        self.preview_panel = PreviewPanel(right_column, self, padding=10)
        self.preview_panel.grid(row=0, column=0, sticky="nsew")
        right_column.grid_rowconfigure(0, weight=1) # Permitir expansión vertical
        right_column.grid_columnconfigure(0, weight=1) # Permitir expansión horizontal

        # --- Barra de Estado (Abajo del todo) ---
        self.status_bar = ttk.Label(
            main_frame,
            textvariable=self.status_label_var,
            style="Status.TLabel",
            anchor="w",
            relief="sunken",
            borderwidth=1
        )
        # Colocar después de la fila principal de contenido
        self.status_bar.grid(row=1, column=0, columnspan=2, sticky="sew", pady=(10, 0))
        main_frame.grid_rowconfigure(1, weight=0) # No expandir verticalmente

        logging.debug("Paneles instanciados y colocados en la grid.")


    def _reset_ui_state(self):
        """Restablece la interfaz a su estado inicial o después de una acción."""
        logging.debug("Reseteando estado de la UI.")
        # Resetear estado interno
        self.last_recognition_result = None
        self.current_template_name = None

        # Resetear/Limpiar paneles
        if self.results_panel:
            self.results_panel.clear_results()
        if self.preview_panel:
            self.preview_panel.clear_preview()
        if self.correction_panel:
            self.correction_panel.hide() # Asegurar que esté oculto y reseteado
        # if self.ocr_panel: self.ocr_panel.hide() # Futuro

        # Habilitar botones de control principal
        if self.control_panel:
            self.control_panel.enable_buttons()

        self.status_message("Listo.")
        self.update_idletasks()

    def status_message(self, message, level=logging.INFO):
        """Actualiza la barra de estado y registra el mensaje."""
        foreground_color = "black" # Color por defecto (ajustar según tema si es necesario)
        try:
            if level == logging.ERROR:
                foreground_color = "red"
                logging.error(message)
            elif level == logging.WARNING:
                foreground_color = "orange"
                logging.warning(message)
            else:
                logging.info(message)

            # Actualizar texto y color (si el widget existe)
            if hasattr(self, 'status_label_var') and self.status_label_var:
                self.status_label_var.set(message)
            if hasattr(self, 'status_bar') and self.status_bar:
                self.status_bar.config(foreground=foreground_color)

            # Forzar actualización inmediata de la UI para ver el mensaje
            self.update_idletasks()

        except Exception as e:
             # Evitar que un error en status_message detenga la app
             print(f"[ERROR EN STATUS] {message} ({e})")


    def run_test(self):
        """Ejecuta el reconocimiento de pantalla."""
        logging.info("Botón 'Reconocer Pantalla' presionado.")
        self.status_message("Reconociendo pantalla...", level=logging.DEBUG)

        # 1. Deshabilitar botones para evitar clics múltiples
        if self.control_panel: self.control_panel.disable_buttons()
        # Mantener botones de resultados deshabilitados (se habilitarán según resultado)
        if self.results_panel: self.results_panel.clear_results()
        if self.correction_panel: self.correction_panel.hide()
        # if self.ocr_panel: self.ocr_panel.hide() # Futuro

        # Forzar actualización UI para que el usuario vea el cambio
        self.update()

        # 2. Ejecutar reconocimiento en el Recognizer
        start_rec_time = tk.IntVar() # Usar variable Tkinter para tiempo si se hace en thread
        start_rec_time = time.time()
        try:
            # Esta llamada puede tardar
            result = self.recognizer.recognize_screen_for_test()
            self.last_recognition_result = result # Guardar resultado completo
            logging.info(f"Reconocimiento completado en {result.get('detection_time_s', 0):.3f}s.")

            # 3. Actualizar paneles con el resultado
            if self.results_panel:
                self.results_panel.update_results(result)

            if self.preview_panel:
                capture = result.get('captured_image')
                state_name = result.get('state', 'N/A')
                method = result.get('method', 'N/A')
                info = f"Captura ({method} -> {state_name})"
                self.preview_panel.update_preview(capture, info_text=info)

            # 4. Mostrar panel de detalles OCR si el método fue OCR (Futuro)
            if result.get('method') == 'ocr' and self.ocr_panel:
                ocr_data = result.get('ocr_results')
                self.ocr_panel.populate_ocr_tree(ocr_data)
                self.ocr_panel.show()
                if self.correction_panel: self.correction_panel.hide()  # Ocultar corrección si OCR es visible
            elif self.ocr_panel:
                self.ocr_panel.hide()  # Ocultar si el método no fue OCR

            self.status_message(f"Reconocimiento finalizado: {result.get('state', 'Error')}")

        except Exception as e:
            rec_time = time.time() - start_rec_time
            logging.exception("Error durante recognize_screen_for_test.")
            messagebox.showerror("Error de Reconocimiento", f"Ocurrió un error:\n{e}")
            # Crear un resultado de error simulado para mostrar en la GUI
            error_result = {'method': 'error', 'state': 'error', 'error_message': str(e), 'detection_time_s': rec_time, 'captured_image': None}
            self.last_recognition_result = error_result
            if self.results_panel: self.results_panel.update_results(error_result)
            if self.preview_panel: self.preview_panel.clear_preview()
            self.status_message(f"Error durante el reconocimiento: {e}", level=logging.ERROR)

        finally:
            # 5. Habilitar botones de control principal al finalizar (éxito o error)
            if self.control_panel: self.control_panel.enable_buttons()
            # Los botones de resultados ya se habilitaron/deshabilitaron en update_results


    def reload_recognizer_data(self):
        """Recarga los datos de configuración del ScreenRecognizer."""
        logging.info("Botón 'Recargar Datos' presionado.")
        self.status_message("Recargando datos...", level=logging.DEBUG)
        try:
            # Deshabilitar botones mientras recarga
            if self.control_panel: self.control_panel.disable_buttons()
            self.update()

            self.recognizer.reload_data()

            # Actualizar ComboBox de corrección
            all_states = list(self.recognizer.templates.keys())
            if self.correction_panel:
                self.correction_panel.populate_combobox(all_states)

            # Resetear UI después de recargar para limpiar estado anterior
            self._reset_ui_state()

            self.status_message("Datos recargados exitosamente.")
            messagebox.showinfo("Recarga Exitosa", "Los datos de configuración (JSONs, plantillas) han sido recargados.")

        except Exception as e:
            logging.exception("Error durante la recarga de datos.")
            self.status_message(f"Error al recargar datos: {e}", level=logging.ERROR)
            messagebox.showerror("Error de Recarga", f"Ocurrió un error al recargar los datos:\n{e}")
        finally:
             # Habilitar botones al finalizar
             if self.control_panel: self.control_panel.enable_buttons()


    def confirm_detection(self):
        """Confirma la detección actual como correcta."""
        logging.info("Botón 'Confirmar Detección' presionado.")
        if not self.last_recognition_result or self.last_recognition_result.get('state', 'unknown') in ['unknown', 'error']:
             messagebox.showwarning("Sin Detección Válida", "No hay una detección válida para confirmar.")
             return

        detected_state = self.last_recognition_result.get('state')
        # Lógica de confirmación (principalmente logging por ahora)
        logging.info(f"CONFIRMACIÓN: Estado '{detected_state}' detectado correctamente.")
        self.status_message(f"Detección '{detected_state}' confirmada.")

        # Deshabilitar botones Confirmar/Negar y ocultar paneles contextuales
        if self.results_panel: self.results_panel.disable_confirm_deny()
        if self.correction_panel: self.correction_panel.hide()
        # if self.ocr_panel: self.ocr_panel.hide() # Futuro


    def deny_detection(self):
        """Niega la detección actual y muestra el panel de corrección."""
        logging.info("Botón 'Negar Detección' presionado.")
        if not self.last_recognition_result or self.last_recognition_result.get('state', 'unknown') in ['unknown', 'error']:
             messagebox.showwarning("Sin Detección Válida", "No hay una detección válida para negar.")
             return

        original_state = self.last_recognition_result.get('state')
        logging.info(f"NEGACIÓN: Detección '{original_state}' marcada como incorrecta.")
        self.status_message(f"Detección '{original_state}' negada. Seleccione corrección manual.")

        # Deshabilitar Confirmar/Negar
        if self.results_panel:
            self.results_panel.disable_confirm_deny()
            # Habilitar botones ROI ya que estamos en modo corrección
            self.results_panel.enable_roi_buttons()
            # Asegurar que la etiqueta ROI refleje el estado original (por si tenía ROI)
            self.results_panel.update_roi_label(original_state)

        # Mostrar panel de Corrección
        if self.correction_panel:
             # Poblar por si acaso se recargaron datos mientras estaba oculto
             all_states = list(self.recognizer.templates.keys())
             self.correction_panel.populate_combobox(all_states)
             self.correction_panel.show()

        # Ocultar panel OCR (si estuviera visible)
        # if self.ocr_panel: self.ocr_panel.hide() # Futuro

        # Limpiar previsualización para que el usuario no se confunda
        if self.preview_panel: self.preview_panel.clear_preview()

        # Resetear el estado relevante actual, ya que el detectado fue negado
        self.current_template_name = None


    def on_correct_state_selected(self, selected_state):
        """
        Callback llamado cuando se selecciona un estado en el CorrectionPanel.
        Actualiza la previsualización para mostrar la plantilla de ese estado
        y actualiza la información de ROI.
        """
        if not selected_state: return # Salir si la selección se borra

        logging.info(f"Estado corregido seleccionado: {selected_state}")
        self.current_template_name = selected_state # Actualizar estado relevante actual
        self.status_message(f"Estado corregido seleccionado: '{selected_state}'. Mostrando plantilla base.")

        # Actualizar etiqueta ROI para el estado CORREGIDO seleccionado
        if self.results_panel:
            self.results_panel.update_roi_label(selected_state)

        # Intentar mostrar la primera plantilla asociada a este estado
        template_path = None
        first_template_file = "N/A"
        if self.recognizer and selected_state in self.recognizer.template_names_mapping:
            template_files = self.recognizer.template_names_mapping[selected_state]
            if template_files and isinstance(template_files, list) and len(template_files) > 0:
                first_template_file = template_files[0]
                # Construir la ruta completa a la plantilla
                res_dir = os.path.join(IMAGES_DIR, self.recognizer.resolution)
                potential_path = os.path.join(res_dir, first_template_file)
                # Comprobar si existe en el dir de resolución, si no, probar en el base
                if os.path.exists(potential_path):
                    template_path = potential_path
                else:
                     template_path_base = os.path.join(IMAGES_DIR, first_template_file)
                     if os.path.exists(template_path_base):
                         template_path = template_path_base
                         logging.debug(f"Plantilla encontrada en directorio base: {template_path}")
                     else:
                         logging.warning(f"No se encontró archivo de plantilla '{first_template_file}' ni en '{res_dir}' ni en '{IMAGES_DIR}'")

        # Actualizar previsualización
        if self.preview_panel:
            if template_path:
                self.preview_panel.update_preview(
                    template_path,
                    info_text=f"Plantilla: {selected_state}\n({first_template_file})"
                )
            else:
                self.preview_panel.update_preview(None, info_text=f"Plantilla no encontrada para\n{selected_state}")


    def log_correct_state(self):
        """Registra la corrección manual seleccionada en el log."""
        logging.info("Botón 'Registrar Corrección (Log)' presionado.")
        selected_state = None
        if self.correction_panel:
            selected_state = self.correction_panel.get_selected_state()

        original_state = self.last_recognition_result.get('state', 'N/A') if self.last_recognition_result else 'N/A'

        if selected_state:
            # Registrar la corrección
            log_message = f"CORRECCIÓN MANUAL: Detección original '{original_state}' -> Corregido a '{selected_state}'"
            logging.info(log_message)
            self.status_message(f"Corrección a '{selected_state}' registrada en log.")
            # Podríamos ocultar el panel de corrección aquí si quisiéramos
            # if self.correction_panel: self.correction_panel.hide()
        else:
            messagebox.showwarning("Sin Selección", "Por favor, seleccione un estado correcto del desplegable antes de registrar.")
            self.status_message("Seleccione un estado para registrar la corrección.", level=logging.WARNING)


    # --- Métodos OCR y ROI (Stubs - Implementación futura) ---

    def confirm_ocr_text(self):
        """Confirma el texto OCR extraído y lo añade a ocr_regions.json."""
        logging.info("Botón 'Confirmar Texto Extraído' presionado (NO IMPLEMENTADO).")
        messagebox.showinfo("WIP", "Funcionalidad 'Confirmar Texto Extraído' aún no implementada.")
        # self.status_message("Texto OCR confirmado y guardado (simulado).")

    def save_edited_ocr_text(self):
        """Guarda el texto OCR editado manualmente en ocr_regions.json."""
        logging.info("Botón 'Guardar Texto Editado' presionado (NO IMPLEMENTADO).")
        messagebox.showinfo("WIP", "Funcionalidad 'Guardar Texto Editado' aún no implementada.")
        # self.status_message("Texto OCR editado y guardado (simulado).")

    def define_roi_for_state(self):
        """Abre el selector visual para definir/editar el ROI de un estado."""
        logging.info("Botón 'Definir/Editar ROI' presionado (NO IMPLEMENTADO).")
        # 1. Determinar para qué estado se define el ROI
        state_to_edit = self.current_template_name # Usar el estado corregido si existe, si no el detectado
        if not state_to_edit and self.last_recognition_result:
             state_to_edit = self.last_recognition_result.get('state')

        if not state_to_edit or state_to_edit in ['unknown', 'error']:
            # Pedir al usuario que seleccione un estado primero
            # Podríamos usar un simpledialog o el combobox de corrección si está visible
             messagebox.showwarning("Seleccionar Estado", "Por favor, primero seleccione o detecte un estado válido para definir su ROI.")
             self.status_message("Seleccione un estado para definir ROI.", level=logging.WARNING)
             return

        # --- Lógica Futura con tk_select_roi ---
        messagebox.showinfo("WIP", f"Funcionalidad 'Definir/Editar ROI' para '{state_to_edit}' aún no implementada.\n"
                                  "Se necesitará la función 'tk_select_roi'.")
        # roi_coords = tk_select_roi(self, self.recognizer, state_to_edit)
        # if roi_coords:
        #    # Cargar, modificar, guardar state_rois.json
        #    # self.recognizer.reload_data()
        #    # self.results_panel.update_roi_label(state_to_edit)
        #    # self.preview_panel.update_preview(...) # Actualizar preview con indicador ROI
        #    self.status_message(f"ROI para '{state_to_edit}' definido/actualizado (simulado).")
        # else:
        #    self.status_message(f"Definición de ROI para '{state_to_edit}' cancelada.")

    def remove_roi_for_state(self):
        """Elimina el ROI asociado a un estado."""
        logging.info("Botón 'Eliminar ROI' presionado (NO IMPLEMENTADO).")
        # 1. Determinar estado a modificar
        state_to_modify = self.current_template_name # Priorizar estado corregido
        if not state_to_modify and self.last_recognition_result:
            state_to_modify = self.last_recognition_result.get('state')

        if not state_to_modify or state_to_modify in ['unknown', 'error']:
             messagebox.showwarning("Seleccionar Estado", "Por favor, primero seleccione o detecte un estado válido para eliminar su ROI.")
             self.status_message("Seleccione un estado para eliminar ROI.", level=logging.WARNING)
             return

        # 2. Verificar si existe ROI para ese estado
        if not (self.recognizer and state_to_modify in self.recognizer.state_rois):
            messagebox.showinfo("Sin ROI", f"El estado '{state_to_modify}' no tiene un ROI definido para eliminar.")
            self.status_message(f"No hay ROI definido para '{state_to_modify}'.", level=logging.WARNING)
            return

        # 3. Pedir confirmación
        if not messagebox.askyesno("Confirmar Eliminación", f"¿Está seguro de que desea eliminar el ROI para el estado '{state_to_modify}'?"):
             self.status_message(f"Eliminación de ROI para '{state_to_modify}' cancelada.")
             return

        # --- Lógica Futura de Eliminación ---
        messagebox.showinfo("WIP", f"Funcionalidad 'Eliminar ROI' para '{state_to_modify}' aún no implementada.\n"
                                  "Se necesita modificar 'state_rois.json'.")
        # try:
        #     all_rois = load_json_mapping(STATE_ROIS_FILE, "ROIs de estado")
        #     if state_to_modify in all_rois:
        #         del all_rois[state_to_modify]
        #         if save_json_mapping(all_rois, STATE_ROIS_FILE, "ROIs de estado"):
        #             logging.info(f"ROI para el estado '{state_to_modify}' eliminado de {STATE_ROIS_FILE}.")
        #             self.recognizer.reload_data() # Recargar datos en recognizer
        #             self.results_panel.update_roi_label(state_to_modify) # Actualizar etiqueta
        #             # self.preview_panel.update_preview(...) # Actualizar preview sin indicador ROI
        #             self.status_message(f"ROI para '{state_to_modify}' eliminado exitosamente.")
        #         else:
        #             messagebox.showerror("Error Guardando", f"No se pudo guardar el archivo {STATE_ROIS_FILE} sin el ROI.")
        #             self.status_message(f"Error al guardar archivo JSON sin ROI para '{state_to_modify}'.", level=logging.ERROR)
        #     else:
        #          # Esto no debería pasar por la comprobación inicial, pero por si acaso
        #          logging.warning(f"Se intentó eliminar ROI para '{state_to_modify}', pero ya no estaba en el archivo.")
        #          self.status_message(f"ROI para '{state_to_modify}' no encontrado en el archivo al intentar eliminar.", level=logging.WARNING)
        # except Exception as e:
        #      logging.exception(f"Error al eliminar ROI para '{state_to_modify}'")
        #      messagebox.showerror("Error Eliminando", f"Ocurrió un error al eliminar el ROI:\n{e}")
        #      self.status_message(f"Error al eliminar ROI para '{state_to_modify}': {e}", level=logging.ERROR)


    def launch_template_manager(self):
        """Lanza la GUI del gestor de plantillas en un proceso separado."""
        logging.info("Botón 'Abrir Gestor Plantillas' presionado.")
        # Asumir que template_manager_gui.py está en el mismo directorio 'src'
        manager_script = os.path.join(current_dir, "template_manager_gui.py")
        if not os.path.exists(manager_script):
             logging.error(f"No se encontró el script 'template_manager_gui.py' en {current_dir}")
             messagebox.showerror("Error", f"No se encontró el script del gestor:\n{manager_script}")
             self.status_message("Error: No se encontró template_manager_gui.py", level=logging.ERROR)
             return

        try:
            # Usar el ejecutable de Python actual para lanzar el script
            python_executable = sys.executable
            logging.info(f"Lanzando '{manager_script}' con el ejecutable '{python_executable}'...")
            # Usar Popen para no bloquear la GUI actual
            subprocess.Popen([python_executable, manager_script])
            self.status_message("Gestor de plantillas lanzado. Recargue datos si realiza cambios.")
            messagebox.showinfo(
                "Gestor Lanzado",
                "Se ha iniciado el Gestor de Plantillas.\n\n"
                "Si realiza cambios en plantillas, mappings o regiones OCR/ROI,\n"
                "recuerde usar el botón 'Recargar Datos Config.' en esta ventana\n"
                "al terminar para aplicar los cambios aquí."
            )
        except Exception as e:
            logging.exception("Error al lanzar el gestor de plantillas.")
            messagebox.showerror("Error al Lanzar", f"No se pudo lanzar 'template_manager_gui.py':\n{e}")
            self.status_message(f"Error al lanzar gestor: {e}", level=logging.ERROR)

    def _on_close(self, force=False):
        """Acciones a realizar al cerrar la ventana."""
        logging.info("Solicitud de cierre de ventana...")
        if force or messagebox.askokcancel("Salir", "¿Está seguro de que desea salir?"):
            logging.info(f"{'='*20} Aplicación cerrada {'='*20}")
            self.destroy()
            # Añadir sys.exit(0) puede ser más explícito para terminar el proceso
            # sys.exit(0)


# --- Punto de Entrada Principal ---
if __name__ == "__main__":
    # Configurar manejo de excepciones no capturadas de Tkinter
    def handle_exception(exc_type, exc_value, exc_traceback):
        logging.error("Excepción no controlada de Tkinter:", exc_info=(exc_type, exc_value, exc_traceback))
        messagebox.showerror("Error Inesperado de GUI", f"Ha ocurrido un error interno en la interfaz:\n{exc_value}\n\nConsulte {log_file_path} para detalles.")
    tk.Tk.report_callback_exception = handle_exception

    # Lanzar la aplicación principal
    try:
        app = ScreenTesterGUI()
        if app.recognizer: # Solo iniciar mainloop si el recognizer se inicializó
            app.mainloop()
        else:
             logging.critical("La aplicación no pudo iniciarse debido a un fallo en la inicialización del Recognizer.")
             # El error ya se mostró en __init__
    except Exception as e:
        logging.exception("Error fatal no controlado en el nivel principal de la aplicación.")
        try:
            # Intento desesperado de mostrar un mensaje final
             root = tk.Tk()
             root.withdraw()
             messagebox.showerror("Error Fatal", f"Ha ocurrido un error inesperado y la aplicación debe cerrarse.\nRevise {log_file_path} para detalles.\n\nError: {e}")
        except:
            pass # Si Tkinter falla completamente, al menos se registró el error.
        sys.exit(1)

# --- END OF FILE src/screen_tester_gui.py ---