import os
import json
import re # Para limpiar texto OCR
import time # Para medir tiempo
import cv2
import numpy as np
import mss
import pytesseract
from enum import Enum
import logging

# --- Configuración del Logging ---
# Se configura aquí para que el módulo tenga logging si se usa solo,
# pero si se importa, la configuración de la app principal (tester) prevalecerá.
if not logging.getLogger().hasHandlers():
    logging.basicConfig(
        level=logging.INFO, # Cambia a DEBUG para ver detalles de matching/OCR
        format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
        handlers=[
            logging.FileHandler("recognizer.log", encoding='utf-8'),
            logging.StreamHandler()
        ]
    )

# --- Constantes Globales (Exportables) ---
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_DIR = os.path.join(PROJECT_DIR, "config")
IMAGES_DIR = os.path.join(PROJECT_DIR, "images")
TEMPLATE_MAPPING_FILE = os.path.join(CONFIG_DIR, "templates_mapping.json")
OCR_MAPPING_FILE = os.path.join(CONFIG_DIR, "ocr_regions.json")
STATE_TRANSITIONS_FILE = os.path.join(CONFIG_DIR, "state_transitions.json")
STATE_ROIS_FILE = os.path.join(CONFIG_DIR, "state_rois.json")

DEFAULT_TEMPLATE_THRESHOLD = 0.75
OCR_FALLBACK_THRESHOLD = 0.60 # Umbral más bajo para considerar OCR
MIN_OCR_TEXT_LEN = 3
DEFAULT_FONT_SIZE = 11 # Aunque principalmente para GUI, mantenido por importación previa


# --- Funciones de Carga/Guardado de Mappings ---
def load_json_mapping(file_path, file_desc="mapping"):
    """Carga un mapping JSON desde un archivo con manejo de errores."""
    if not os.path.exists(file_path):
        logging.warning(f"Archivo de {file_desc} '{file_path}' no encontrado. Usando diccionario vacío.")
        return {}
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            # Permitir archivo vacío devolviendo diccionario vacío
            content = f.read()
            if not content:
                logging.warning(f"Archivo de {file_desc} '{file_path}' está vacío. Usando diccionario vacío.")
                return {}
            mapping = json.loads(content)
            if not isinstance(mapping, dict):
                logging.error(f"El contenido de {file_path} no es un diccionario JSON válido.")
                return {}
            return mapping
    except json.JSONDecodeError:
        logging.error(f"El archivo {file_path} está malformado o vacío.")
        return {}
    except Exception as e:
        logging.error(f"Error inesperado al cargar {file_path}: {e}")
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
        return False


# --- ScreenRecognizer Class ---
class ScreenRecognizer:
    def __init__(self, monitor=1, threshold=DEFAULT_TEMPLATE_THRESHOLD, ocr_fallback_threshold=OCR_FALLBACK_THRESHOLD):
        self.monitor_index = monitor
        self.threshold = threshold
        self.ocr_fallback_threshold = ocr_fallback_threshold
        self.templates = {}             # { state: [template_img_gray] }
        self.template_names_mapping = {}# { state: [filename1, filename2] } (cargado de JSON)
        self.ocr_regions_mapping = {}   # { state: [{"region": {...}, "expected_text": [...]}, ...] } (cargado de JSON)
        self.state_transitions = {}     # { state: [next_state1, next_state2] } (cargado de JSON)
        self.state_rois = {}            # { state: {"left":...} } (cargado de JSON)
        self.last_recognized_state = None # Estado anterior reconocido
        self.monitors_info = self._detect_monitors()
        self._load_all_data()

    def _detect_monitors(self):
        """Detecta los monitores existentes usando mss."""
        try:
            with mss.mss() as sct:
                # Devuelve la lista completa, el índice 0 es 'all screens'
                return sct.monitors
        except Exception as e:
            logging.error(f"Error detectando monitores: {e}")
            return [{}] # Fallback

    def _get_monitor_region(self):
        """Obtiene la geometría del monitor seleccionado (usa índice 1-based)."""
        monitor_real_index = self.monitor_index # El índice que pasamos es 1-based
        if monitor_real_index >= 1 and monitor_real_index < len(self.monitors_info):
            return self.monitors_info[monitor_real_index]
        else:
            logging.warning(f"Monitor {self.monitor_index} no válido (detectados: {len(self.monitors_info)}). Usando monitor primario (1).")
            if len(self.monitors_info) > 1:
                 return self.monitors_info[1]
            else:
                 logging.error("No se encontraron monitores válidos para capturar.")
                 return None

    def _load_all_data(self):
        """Carga o recarga todos los mappings JSON y las plantillas."""
        logging.info("Cargando/Recargando datos de reconocimiento...")
        self.template_names_mapping = load_json_mapping(TEMPLATE_MAPPING_FILE, "plantillas")
        self.ocr_regions_mapping = load_json_mapping(OCR_MAPPING_FILE, "regiones OCR")
        self.state_transitions = load_json_mapping(STATE_TRANSITIONS_FILE, "transiciones de estado")
        self.state_rois = load_json_mapping(STATE_ROIS_FILE, "ROIs de estado")
        self._load_templates()
        logging.info("Datos cargados/recargados.")

    def reload_data(self):
        """Interfaz pública para recargar los datos."""
        self._load_all_data()

    def _load_templates(self):
        """Carga las imágenes de plantilla en escala de grises."""
        self.templates = {}
        loaded_count = 0
        error_count = 0
        missing_files = []
        corrupt_files = []
        logging.info(f"Cargando plantillas desde: {IMAGES_DIR}")

        for state, file_list in self.template_names_mapping.items():
            if not isinstance(file_list, list):
                 logging.warning(f"Valor para '{state}' en {TEMPLATE_MAPPING_FILE} no es una lista. Saltando.")
                 error_count += 1
                 continue

            loaded_images = []
            for file_name in file_list:
                if not isinstance(file_name, str): # Verificar que sea string
                    logging.warning(f"Nombre de archivo no es string para estado '{state}': {file_name}. Saltando.")
                    error_count += 1
                    continue
                template_path = os.path.join(IMAGES_DIR, file_name)
                if os.path.exists(template_path):
                    try:
                        img = cv2.imread(template_path, cv2.IMREAD_GRAYSCALE)
                        if img is not None:
                            loaded_images.append(img)
                            loaded_count += 1
                        else:
                            logging.error(f"Corrupta/Inválida: {template_path}")
                            corrupt_files.append(template_path)
                            error_count += 1
                    except Exception as e:
                        logging.error(f"Excepción al cargar {template_path}: {e}")
                        corrupt_files.append(template_path)
                        error_count += 1
                else:
                    logging.warning(f"Faltante: {template_path}")
                    missing_files.append(template_path)
                    error_count += 1

            if loaded_images:
                self.templates[state] = loaded_images

        logging.info(f"Carga plantillas: {loaded_count} cargadas, {error_count} errores/faltantes.")
        if missing_files: logging.warning(f"Archivos faltantes: {len(missing_files)}")
        if corrupt_files: logging.error(f"Archivos corruptos/ilegibles: {len(corrupt_files)}")


    def capture_screen(self, region=None):
        """Captura la pantalla o una región específica del monitor configurado."""
        monitor_region = self._get_monitor_region()
        if monitor_region is None: return None

        capture_area = region if region is not None else monitor_region

        try:
            with mss.mss() as sct:
                sct_img = sct.grab(capture_area)
                img = np.array(sct_img)
                img_bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
                return img_bgr
        except mss.ScreenShotError as e:
            logging.error(f"Error MSS al capturar {capture_area}: {e}")
            return None
        except Exception as e:
            logging.error(f"Error durante captura ({capture_area}): {e}")
            return None


    def find_template_on_screen(self, screen_gray, template_gray):
        """Busca una única plantilla en la imagen de pantalla (o ROI)."""
        if template_gray is None or screen_gray is None: return None, 0.0
        if template_gray.shape[0] > screen_gray.shape[0] or template_gray.shape[1] > screen_gray.shape[1]:
            # logging.debug("Plantilla más grande que pantalla/ROI.") # Puede ser muy verboso
            return None, 0.0
        try:
            result = cv2.matchTemplate(screen_gray, template_gray, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)
            return max_loc, max_val
        except cv2.error as e:
             logging.warning(f"Error en matchTemplate (probablemente tamaño inválido): {e}")
             return None, 0.0
        except Exception as e:
            logging.error(f"Error inesperado en find_template_on_screen: {e}")
            return None, 0.0


    def recognize_screen_for_test(self):
        """
        Intenta reconocer la pantalla actual con optimizaciones y devuelve info detallada.
        """
        logging.info(f"--- Iniciando Reconocimiento (Último estado: {self.last_recognized_state}) ---")
        start_time = time.time()

        result = {
            'method': 'unknown', 'state': 'unknown',
            'confidence': None, 'ocr_results': None, 'detection_time_s': 0.0
        }
        screen_bgr_full = self.capture_screen()
        if screen_bgr_full is None:
            logging.error("Fallo captura inicial de pantalla completa.")
            result['detection_time_s'] = time.time() - start_time
            return result
        screen_gray_full = cv2.cvtColor(screen_bgr_full, cv2.COLOR_BGR2GRAY)

        # --- Determinar Orden de Estados (Contexto) ---
        states_to_check = list(self.templates.keys())
        prioritized_states = []
        if self.last_recognized_state and self.last_recognized_state in self.state_transitions:
            possible_next = self.state_transitions[self.last_recognized_state]
            if isinstance(possible_next, list):
                prioritized_states = [s for s in possible_next if s in self.templates] # Estados posibles que tienen plantillas
                if prioritized_states:
                    logging.info(f"Aplicando contexto. Priorizados: {prioritized_states}")
                    other_states = [s for s in states_to_check if s not in prioritized_states]
                    states_to_check = prioritized_states + other_states
                else:
                     logging.info(f"Contexto encontrado para '{self.last_recognized_state}', pero sin plantillas válidas para los estados siguientes.")
            else:
                 logging.warning(f"Transiciones para '{self.last_recognized_state}' no es una lista válida.")

        if not prioritized_states: logging.info("No se aplica contexto (sin estado previo válido o sin transiciones/plantillas).")


        # --- 1. Template Matching (con ROI si está definido) ---
        best_match_state = "unknown"
        best_match_val = 0.0
        potential_ocr_states = []

        logging.debug(f"Orden de chequeo: {states_to_check}")
        for state in states_to_check:
            # (Saltar si state no está en self.templates ya está implícito en la lista)
            template_list = self.templates[state]
            state_best_val = 0.0

            # --- Determinar ROI ---
            search_roi = self.state_rois.get(state)
            target_screen_gray = screen_gray_full
            roi_offset = {'left': 0, 'top': 0}
            using_roi = False

            if search_roi and isinstance(search_roi, dict) and all(k in search_roi for k in ('left', 'top', 'width', 'height')):
                # Extraer ROI de la captura completa (más eficiente que recapturar)
                x, y, w, h = search_roi['left'], search_roi['top'], search_roi['width'], search_roi['height']
                # Asegurar que las coordenadas ROI estén dentro de la pantalla
                h_screen, w_screen = screen_gray_full.shape
                x = max(0, x); y = max(0, y)
                w = min(w, w_screen - x); h = min(h, h_screen - y)
                if w > 0 and h > 0:
                    target_screen_gray = screen_gray_full[y:y+h, x:x+w]
                    roi_offset = {'left': x, 'top': y}
                    using_roi = True
                    logging.debug(f"  Usando ROI para '{state}': {search_roi} (ajustado a {x},{y},{w},{h})")
                else:
                     logging.warning(f"  ROI inválido o fuera de pantalla para '{state}': {search_roi}. Usando pantalla completa.")
            # else: logging.debug(f"  Sin ROI definida para '{state}'.") # Puede ser muy verboso

            # --- Buscar plantillas ---
            for i, template_gray in enumerate(template_list):
                # Pasar el offset del ROI a la función find_template (aunque no lo usa actualmente)
                loc, match_val = self.find_template_on_screen(target_screen_gray, template_gray)
                # logging.debug(f"    Comparando '{state}' (tpl {i+1}) en {'ROI' if using_roi else 'Full'}: Conf={match_val:.3f}")
                state_best_val = max(state_best_val, match_val)

            # --- Evaluar ---
            if state_best_val >= self.threshold:
                if state_best_val > best_match_val:
                    best_match_val = state_best_val
                    best_match_state = state
                    logging.debug(f"    ¡Nuevo mejor match TEMPLATE! Estado: {state}, Confianza: {best_match_val:.3f}")
            elif state_best_val >= self.ocr_fallback_threshold:
                 if best_match_state == "unknown": # Solo considerar si no hay match claro aún
                      potential_ocr_states.append((state, state_best_val))
                      logging.debug(f"    Candidato OCR añadido: {state} con {state_best_val:.3f}")

            # Early exit si hay match claro Y se usó contexto priorizado
            if best_match_state != "unknown" and state in prioritized_states:
                 logging.info(f"Match de template en estado priorizado ({best_match_state}), deteniendo búsqueda.")
                 break

        # --- Resultado Template ---
        if best_match_state != "unknown":
            result['method'] = 'template'; result['state'] = best_match_state
            result['confidence'] = best_match_val
            logging.info(f"Estado detectado (Template): {result['state']} (Confianza: {result['confidence']:.3f})")
            self.last_recognized_state = best_match_state
            result['detection_time_s'] = time.time() - start_time
            return result

        # --- 2. OCR Fallback ---
        logging.info("No se encontró coincidencia clara de plantilla. Intentando OCR fallback...")
        potential_ocr_states.sort(key=lambda item: item[1], reverse=True)

        for state_candidate, match_score in potential_ocr_states:
            if state_candidate in self.ocr_regions_mapping:
                regions_data_list = self.ocr_regions_mapping[state_candidate]
                if isinstance(regions_data_list, list):
                    ocr_results_for_state = {}
                    found_match_in_state = False
                    logging.info(f"  Probando OCR para candidato: {state_candidate} (Score: {match_score:.3f}) con {len(regions_data_list)} regiones...")

                    for idx, region_data in enumerate(regions_data_list):
                        if not (isinstance(region_data, dict) and 'region' in region_data and
                                isinstance(region_data['region'], dict) and
                                all(k in region_data['region'] for k in ('left', 'top', 'width', 'height'))):
                            logging.warning(f"    Formato inválido región OCR '{state_candidate}', índice {idx}. Saltando: {region_data}")
                            continue

                        region_coords = region_data['region']
                        expected_texts = region_data.get('expected_text', [])
                        if not isinstance(expected_texts, list): expected_texts = []

                        # Capturar solo la región OCR
                        region_img = self.capture_screen(region=region_coords)
                        extracted_text = self._extract_and_clean_text(region_img)

                        match_expected = False
                        if extracted_text and expected_texts:
                            for expected in expected_texts:
                                if expected.lower() == extracted_text.lower(): match_expected = True; break

                        logging.info(f"    Región {idx}: Texto='{extracted_text}', Esperado={expected_texts}, Coincide={match_expected}")
                        ocr_results_for_state[idx] = {'region': region_coords, 'text': extracted_text, 'expected': expected_texts, 'match_expected': match_expected}
                        if match_expected: found_match_in_state = True

                    if found_match_in_state:
                        result['method'] = 'ocr'; result['state'] = state_candidate
                        result['ocr_results'] = ocr_results_for_state
                        logging.info(f"Estado detectado (OCR Fallback Verificado): {result['state']}")
                        self.last_recognized_state = state_candidate
                        result['detection_time_s'] = time.time() - start_time
                        return result
                else:
                    logging.warning(f"Regiones OCR para '{state_candidate}' no son lista.")

        # --- Resultado Final ---
        logging.warning("No se pudo detectar el estado mediante template ni OCR verificado.")
        self.last_recognized_state = None
        result['detection_time_s'] = time.time() - start_time
        return result # Devuelve 'unknown'


    def _extract_and_clean_text(self, image_bgr):
        """Extrae texto de una imagen y lo limpia."""
        if image_bgr is None: return ""
        try:
            gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
            # Podrías experimentar con preprocesamiento aquí si el OCR falla a menudo
            # gray = cv2.GaussianBlur(gray, (3, 3), 0)
            # _, gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            text = pytesseract.image_to_string(gray, lang="spa+eng")
            text = text.replace('\n', ' ').replace('\r', '')
            # Permitir también ()- y . para números/fechas, etc. - ajustar según necesidad
            text = re.sub(r'[^a-zA-Z0-9ñÑáéíóúÁÉÍÓÚüÜ\s()\-.:]', '', text)
            text = re.sub(r'\s+', ' ', text).strip()
            return text
        except Exception as e:
            logging.error(f"Error durante OCR: {e}")
            return ""

# --- Ejemplo de Uso ---
if __name__ == "__main__":
    logging.info("Ejecutando prueba interna de ScreenRecognizer...")
    # Crear directorios si no existen
    if not os.path.exists(CONFIG_DIR): os.makedirs(CONFIG_DIR)
    if not os.path.exists(IMAGES_DIR): os.makedirs(IMAGES_DIR)
    # Crear archivos JSON de ejemplo si no existen (sin sobreescribir)
    if not os.path.exists(TEMPLATE_MAPPING_FILE):
        logging.info(f"Creando {TEMPLATE_MAPPING_FILE}"); save_json_mapping({}, TEMPLATE_MAPPING_FILE)
    if not os.path.exists(OCR_MAPPING_FILE):
        logging.info(f"Creando {OCR_MAPPING_FILE}"); save_json_mapping({}, OCR_MAPPING_FILE)
    if not os.path.exists(STATE_TRANSITIONS_FILE):
        logging.info(f"Creando {STATE_TRANSITIONS_FILE}"); save_json_mapping({}, STATE_TRANSITIONS_FILE)
    if not os.path.exists(STATE_ROIS_FILE):
        logging.info(f"Creando {STATE_ROIS_FILE}"); save_json_mapping({}, STATE_ROIS_FILE)

    try:
        recognizer = ScreenRecognizer(monitor=1) # Usar monitor 1
        recognizer.last_recognized_state = "pantalla_bienvenida" # Simular estado previo

        logging.info("Intentando reconocer pantalla actual (método de test)...")
        start_test = time.time()
        detected_state_info = recognizer.recognize_screen_for_test()
        end_test = time.time()

        logging.info(f"Tiempo total del test recognize_screen_for_test: {end_test - start_test:.3f} seg")
        logging.info("--- Resultado Detallado ---")
        logging.info(json.dumps(detected_state_info, indent=4, ensure_ascii=False))
        logging.info("---------------------------")

    except Exception as e:
        logging.exception("Error durante la prueba interna de ScreenRecognizer.")