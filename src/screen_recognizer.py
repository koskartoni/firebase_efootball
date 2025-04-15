# --- START OF FILE screen_recognizer ---

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
# Ajuste para que funcione correctamente desde src/
# __file__ será la ruta a screen_recognizer.py dentro de src/
# os.path.dirname(__file__) será el directorio src/
# os.path.dirname(os.path.dirname(__file__)) será el directorio raíz del proyecto (efootball_automation/)
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
       logging.error(f"Error de formato JSON en el archivo {file_path}. Verifique la sintaxis.")
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
   """
   Clase responsable de reconocer el estado actual de la pantalla mediante
   template matching y OCR fallback, utilizando optimizaciones de ROI y contexto.
   """
   def __init__(self, monitor=1, resolution='4K', threshold=DEFAULT_TEMPLATE_THRESHOLD,
                ocr_fallback_threshold=OCR_FALLBACK_THRESHOLD,
                ocr_lang='spa+eng', ocr_config='', ocr_apply_thresholding=True):
       """
       Inicializa el reconocedor.

       Args:
           monitor (int): Índice del monitor a capturar (1-based).
           resolution (str): Resolución objetivo para cargar plantillas (e.g., '4K').
           threshold (float): Umbral de confianza para template matching.
           ocr_fallback_threshold (float): Umbral mínimo para considerar OCR.
           ocr_lang (str): Cadena de idiomas para Tesseract (ej. 'spa+eng').
           ocr_config (str): Opciones de configuración adicionales para Tesseract (ej. '--psm 6').
           ocr_apply_thresholding (bool): Si aplicar umbralización Otsu antes de OCR.
       """
       self.monitor_index = monitor # Índice del monitor físico (1-based)
       self.resolution = resolution   # Resolución configurada (e.g., '4K', '1080p')
       self.threshold = threshold
       self.ocr_fallback_threshold = ocr_fallback_threshold
       self.ocr_lang = ocr_lang
       self.ocr_config = ocr_config
       self.ocr_apply_thresholding = ocr_apply_thresholding

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
               monitors = sct.monitors
               logging.info(f"Monitores detectados: {len(monitors) - 1}") # No contar 'all screens'
               # Quitar el monitor 'all' (índice 0) para simplificar la lógica 1-based
               if monitors:
                   return monitors[1:]
               else:
                    logging.error("MSS no devolvió información de monitores.")
                    return [] # Lista vacía si no hay monitores
       except Exception as e:
           logging.exception(f"Error detectando monitores: {e}")
           return [] # Fallback a lista vacía

   def _get_monitor_region(self):
       """Obtiene la geometría del monitor seleccionado (usando lista 0-based internamente)."""
       monitor_zero_based_index = self.monitor_index - 1 # Convertir a 0-based
       if 0 <= monitor_zero_based_index < len(self.monitors_info):
           return self.monitors_info[monitor_zero_based_index]
       else:
           num_monitors = len(self.monitors_info)
           logging.warning(
               f"Monitor {self.monitor_index} no válido (detectados: {num_monitors}). "
               f"Usando monitor primario (índice 1)."
           )
           if num_monitors > 0:
               # Devolver el primer monitor de la lista (que es el primario usualmente)
               return self.monitors_info[0]
           else:
               logging.error("No se encontraron monitores válidos para capturar.")
               return None # No hay monitor válido

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
       missing_files = [] # Para seguimiento/logging
       corrupt_files = [] # Para seguimiento/logging

       # Determinar directorio de imágenes según resolución
       resolution_dir = os.path.join(IMAGES_DIR, self.resolution)
       if not os.path.exists(resolution_dir):
           # Intentar con directorio base como fallback si el específico no existe
           logging.warning(f"Directorio de resolución '{self.resolution}' ({resolution_dir}) no encontrado. Usando base: {IMAGES_DIR}")
           templates_dir = IMAGES_DIR
           if not os.path.exists(templates_dir):
                logging.error(f"Directorio base de imágenes tampoco encontrado: {IMAGES_DIR}. No se pueden cargar plantillas.")
                return # Salir si no hay directorio de imágenes
       else:
           templates_dir = resolution_dir
           logging.info(f"Cargando plantillas desde: {templates_dir} (Resolución: {self.resolution})")

       for state, file_list in self.template_names_mapping.items():
           if not isinstance(file_list, list):
               logging.warning(f"Valor para '{state}' en {TEMPLATE_MAPPING_FILE} no es una lista válida. Saltando.")
               error_count += 1
               continue # Saltar a la siguiente entrada del mapping

           loaded_images = []
           for file_name in file_list:
               if not isinstance(file_name, str):
                   logging.warning(f"Nombre de archivo no es string para estado '{state}': {file_name}. Saltando.")
                   error_count += 1
                   continue # Saltar al siguiente archivo en la lista
               template_path = os.path.join(templates_dir, file_name)

               if os.path.exists(template_path):
                   try:
                       img = cv2.imread(template_path, cv2.IMREAD_GRAYSCALE)
                       if img is not None:
                           loaded_images.append(img)
                           loaded_count += 1
                       else:
                           # cv2.imread devuelve None si el archivo no es una imagen válida o está corrupto
                           logging.error(f"Error al leer (formato inválido o corrupta?): {template_path}")
                           corrupt_files.append(template_path)
                           error_count += 1
                   except Exception as e:
                       logging.exception(f"Excepción inesperada al cargar plantilla {template_path}: {e}")
                       corrupt_files.append(template_path)
                       error_count += 1
               else: # Archivo no existe
                   logging.warning(f"Plantilla faltante: {template_path}")
                   missing_files.append(template_path)
                   error_count += 1

           if loaded_images:
               self.templates[state] = loaded_images
           elif file_list: # Solo loguear si se esperaban plantillas pero no se cargó ninguna
                logging.warning(f"No se cargó ninguna plantilla válida para el estado '{state}'.")


       logging.info(f"Carga de plantillas completada. {loaded_count} cargadas, {error_count} errores (faltantes/corruptas).")

       # Logging de resumen de errores (más conciso)
       # Crear archivos de log solo si hay errores
       log_dir = os.path.join(PROJECT_DIR, "logs") # Guardar logs en carpeta logs/
       os.makedirs(log_dir, exist_ok=True)
       if missing_files:
           missing_log_path = os.path.join(log_dir, "missing_templates.log")
           logging.warning(f"Plantillas faltantes: {len(missing_files)} (ver '{missing_log_path}' para detalles).")
           try:
               with open(missing_log_path, "w", encoding="utf-8") as f:
                   for path in missing_files: f.write(path + "\n")
           except Exception as e:
               logging.error(f"No se pudo escribir el log de plantillas faltantes: {e}")
       if corrupt_files:
           corrupt_log_path = os.path.join(log_dir, "corrupt_templates.log")
           logging.error(f"Plantillas corruptas/inválidas: {len(corrupt_files)} (ver '{corrupt_log_path}' para detalles).")
           try:
               with open(corrupt_log_path, "w", encoding="utf-8") as f:
                   for path in corrupt_files: f.write(path + "\n")
           except Exception as e:
               logging.error(f"No se pudo escribir el log de plantillas corruptas: {e}")


   def capture_screen(self, region=None):
       """
       Captura la pantalla completa o una región específica del monitor configurado.

       Args:
           region (dict, optional): Diccionario con {'left', 'top', 'width', 'height'}
                                    para capturar solo esa área. Si es None, captura
                                    el monitor completo. Coordenadas absolutas.

       Returns:
           numpy.ndarray: Imagen capturada en formato BGR, o None si falla.
       """
       monitor_geom = self._get_monitor_region() # Obtener la geometría del monitor seleccionado
       if monitor_geom is None:
            logging.error("No se pudo obtener la geometría del monitor para capturar.")
            return None

       # Si se pide una región, usarla. Si no, usar la del monitor entero.
       capture_area = region if region is not None else monitor_geom

       # Validación y ajuste de la región de captura para que esté DENTRO del monitor físico
       # Esto es crucial porque mss puede fallar si la región sale de los límites
       if region:
            mon_left, mon_top = monitor_geom['left'], monitor_geom['top']
            mon_right = mon_left + monitor_geom['width']
            mon_bottom = mon_top + monitor_geom['height']

            # Ajustar coordenadas relativas al monitor si es necesario
            # Asegurar que la región solicitada está dentro del monitor
            cap_left = max(region['left'], mon_left)
            cap_top = max(region['top'], mon_top)
            cap_right = min(region['left'] + region['width'], mon_right)
            cap_bottom = min(region['top'] + region['height'], mon_bottom)

            # Recalcular width y height válidos
            cap_width = max(0, cap_right - cap_left)
            cap_height = max(0, cap_bottom - cap_top)

            if cap_width == 0 or cap_height == 0:
                logging.warning(f"La región solicitada {region} queda fuera o es inválida dentro del monitor {monitor_geom}. No se puede capturar.")
                return None

            capture_area = {'left': cap_left, 'top': cap_top, 'width': cap_width, 'height': cap_height}
            # logging.debug(f"Región ajustada para captura: {capture_area}")


       try:
           with mss.mss() as sct: # Usar un contexto 'with' asegura liberación de recursos
               # logging.debug(f"Capturando área: {capture_area}")
               sct_img = sct.grab(capture_area)
               # Convertir a numpy array
               img = np.array(sct_img)
               # Convertir de BGRA a BGR (formato común para OpenCV y otras libs)
               # Si la imagen no tiene canal alfa, `cvtColor` podría fallar o no hacer nada.
               # Es más seguro chequear los canales. MSS usualmente captura en BGRA.
               if img.shape[2] == 4:
                  img_bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
               elif img.shape[2] == 3:
                  img_bgr = img # Ya está en BGR (o RGB, mss es inconsistente a veces)
               else:
                   logging.error(f"Formato de imagen inesperado capturado por MSS (canales={img.shape[2]}).")
                   return None
               return img_bgr
       except mss.ScreenShotError as e:
           logging.error(f"Error MSS al capturar {capture_area}: {e}")
           return None
       except Exception as e:
           logging.exception(f"Error inesperado durante captura ({capture_area}): {e}")
           return None

   def find_template_on_screen(self, screen_gray, template_gray):
       """
       Busca una única plantilla en la imagen de pantalla (o ROI) en escala de grises.

       Args:
           screen_gray (numpy.ndarray): Imagen de la pantalla o ROI en escala de grises.
           template_gray (numpy.ndarray): Imagen de la plantilla en escala de grises.

       Returns:
           tuple: (max_loc, max_val) donde max_loc es la esquina superior izquierda
                  de la mejor coincidencia y max_val es la confianza (0.0 a 1.0),
                  o (None, 0.0) si hay error o no se encuentra.
       """
       if template_gray is None or screen_gray is None:
           logging.warning("Se pasó None a find_template_on_screen para screen o template.")
           return None, 0.0
       if template_gray.size == 0 or screen_gray.size == 0:
            logging.warning("Se pasó una imagen vacía (size 0) a find_template_on_screen.")
            return None, 0.0

       # Comprobar dimensiones antes de llamar a matchTemplate
       h_screen, w_screen = screen_gray.shape[:2]
       h_template, w_template = template_gray.shape[:2]

       # Si la plantilla es más grande que la pantalla/ROI, no se puede encontrar
       if h_template > h_screen or w_template > w_screen:
           # logging.debug("Plantilla más grande que pantalla/ROI.") # Puede ser muy verboso
           return None, 0.0 # Coincidencia imposible

       try:
           result = cv2.matchTemplate(screen_gray, template_gray, cv2.TM_CCOEFF_NORMED)
           # minMaxLoc devuelve: minVal, maxVal, minLoc, maxLoc
           _, max_val, _, max_loc = cv2.minMaxLoc(result)
           return max_loc, float(max_val) # Asegurar que max_val es float estándar
       except cv2.error as e:
            # Común si uno de los tamaños es 0 o inválido después del slicing ROI,
            # o si los tipos de datos no coinciden (aunque IMREAD_GRAYSCALE debería prevenirlo)
            logging.warning(f"Error en cv2.matchTemplate (probablemente tamaño inválido o tipo de dato): {e}")
            return None, 0.0
       except Exception as e:
           logging.exception(f"Error inesperado en find_template_on_screen: {e}")
           return None, 0.0

   def recognize_screen_for_test(self):
       """
       Intenta reconocer la pantalla actual con optimizaciones (ROI, contexto)
       y fallback a OCR, devolviendo información detallada para el tester.
       Optimizado para extraer regiones OCR de una única captura inicial.

       Returns:
           dict: Un diccionario con los resultados:
               'method': 'template', 'ocr', 'error', o 'unknown'.
               'state': Nombre del estado detectado o 'unknown'/'error'.
               'confidence': Confianza del template matching (si aplica, float).
               'ocr_results': Diccionario con detalles OCR por región (si aplica).
                   { region_idx: {'region':..., 'text':..., 'expected':..., 'match_expected':...}}
               'error_message': Mensaje de error si method es 'error'.
               'detection_time_s': Tiempo total de detección en segundos (float).
               'captured_image': Imagen BGR completa capturada (numpy.ndarray), o None si falló.
       """
       logging.info(f"--- Iniciando Reconocimiento (Último estado: {self.last_recognized_state}) ---")
       start_time = time.time()

       # Inicializar resultado con valores por defecto
       result = {
           'method': 'unknown', 'state': 'unknown',
           'confidence': None, 'ocr_results': None, 'error_message': None,
           'detection_time_s': 0.0, 'captured_image': None
       }

       # --- 0. Captura ÚNICA de Pantalla Completa ---
       monitor_region = self._get_monitor_region()
       if monitor_region is None:
           logging.error("No se pudo obtener la región del monitor. Abortando reconocimiento.")
           result.update({
               'method': 'error', 'state': 'error',
               'error_message': "No se pudo obtener la región del monitor."
           })
           result['detection_time_s'] = time.time() - start_time
           return result

       # Usar la geometría del monitor para la captura completa
       screen_bgr_full = self.capture_screen(region=monitor_region)
       if screen_bgr_full is None:
           logging.error("Fallo captura inicial de pantalla completa.")
           result.update({
               'method': 'error', 'state': 'error',
               'error_message': "Fallo la captura inicial de pantalla completa."
           })
           result['detection_time_s'] = time.time() - start_time
           return result

       # Guardar la imagen capturada en el resultado para la GUI
       result['captured_image'] = screen_bgr_full.copy() # Copiar para evitar modificaciones accidentales

       try:
           screen_gray_full = cv2.cvtColor(screen_bgr_full, cv2.COLOR_BGR2GRAY)
           h_screen, w_screen = screen_gray_full.shape[:2] # Dimensiones de la imagen capturada
       except cv2.error as cv_err:
            logging.error(f"Error al convertir la captura a escala de grises: {cv_err}")
            result.update({
               'method': 'error', 'state': 'error',
               'error_message': f"Error al convertir la captura a escala de grises: {cv_err}"
            })
            result['detection_time_s'] = time.time() - start_time
            return result


       # --- Determinar Orden de Estados (Contexto) ---
       states_to_check = list(self.templates.keys())
       prioritized_states = []
       if self.last_recognized_state and self.last_recognized_state in self.state_transitions:
           possible_next = self.state_transitions[self.last_recognized_state]
           if isinstance(possible_next, list):
               # Filtrar solo estados que realmente existen en las plantillas cargadas
               prioritized_states = [s for s in possible_next if s in self.templates]
               if prioritized_states:
                   logging.info(f"Aplicando contexto. Priorizados: {prioritized_states}")
                   # Asegurarse que los priorizados estén al inicio, seguidos del resto sin duplicados
                   other_states = [s for s in states_to_check if s not in prioritized_states]
                   states_to_check = prioritized_states + other_states
               else:
                   logging.info(f"Contexto encontrado para '{self.last_recognized_state}', pero sin plantillas válidas para los estados siguientes.")
           elif possible_next is not None: # Permitir None, pero no otros tipos
               logging.warning(f"Transiciones para '{self.last_recognized_state}' no es una lista válida (es {type(possible_next)}). Ignorando contexto.")

       if not prioritized_states:
           logging.info("No se aplica contexto (sin estado previo válido o sin transiciones/plantillas válidas).")

       # --- 1. Template Matching (con ROI si está definido) ---
       best_match_state = "unknown"
       best_match_val = 0.0
       potential_ocr_states = [] # Almacena tuplas (state, confidence)

       logging.debug(f"Orden de chequeo de plantillas: {states_to_check}")
       for state in states_to_check:
           if state not in self.templates: # Seguridad extra
               logging.warning(f"Estado '{state}' listado para chequeo pero sin plantillas cargadas. Saltando.")
               continue

           template_list = self.templates[state]
           if not template_list: # Si la lista está vacía por alguna razón
                logging.warning(f"Lista de plantillas vacía para el estado '{state}'. Saltando.")
                continue

           # --- Determinar ROI para este estado ---
           search_roi_coords = self.state_rois.get(state)
           target_screen_gray = screen_gray_full # Por defecto, buscar en toda la pantalla capturada
           roi_info_for_log = "Full Screen" # Para logging
           using_roi = False

           if search_roi_coords and isinstance(search_roi_coords, dict) and all(k in search_roi_coords for k in ('left', 'top', 'width', 'height')):
               # Extraer ROI de la CAPTURA COMPLETA (screen_gray_full)
               x_abs, y_abs = search_roi_coords['left'], search_roi_coords['top']
               w_roi, h_roi = search_roi_coords['width'], search_roi_coords['height']

               # Calcular coords relativas a la imagen capturada (screen_gray_full)
               # Usando la geometría del monitor capturado como referencia
               x_rel = max(0, x_abs - monitor_region['left'])
               y_rel = max(0, y_abs - monitor_region['top'])
               # Ajustar ancho/alto para no salirse de la pantalla capturada
               w_rel = min(w_roi, w_screen - x_rel)
               h_rel = min(h_roi, h_screen - y_rel)

               if w_rel > 0 and h_rel > 0:
                   try:
                       target_screen_gray = screen_gray_full[y_rel : y_rel + h_rel, x_rel : x_rel + w_rel]
                       roi_info_for_log = f"ROI Abs={search_roi_coords} -> Rel=[{x_rel}:{x_rel+w_rel}, {y_rel}:{y_rel+h_rel}]"
                       using_roi = True
                       # logging.debug(f"  Usando {roi_info_for_log} para '{state}'") # Verboso
                   except Exception as roi_slice_error:
                       logging.error(f"Error al extraer ROI para '{state}' ({roi_info_for_log}): {roi_slice_error}. Usando pantalla completa.")
                       target_screen_gray = screen_gray_full # Fallback
                       roi_info_for_log = "Full Screen (ROI Slice Error)"
                       using_roi = False
               else:
                   logging.warning(f"  ROI para '{state}' resulta en tamaño 0 o negativo relativo a la captura. Usando pantalla completa. ROI Abs={search_roi_coords}")
                   target_screen_gray = screen_gray_full # Fallback a pantalla completa
                   roi_info_for_log = "Full Screen (Invalid ROI Dims)"
                   using_roi = False
           # else: logging.debug(f"  Sin ROI definida o inválida para '{state}'.") # Puede ser verboso

           # --- Buscar TODAS las plantillas para este estado dentro del target_screen_gray ---
           current_state_best_val = 0.0
           current_state_best_loc = None
           for i, template_gray in enumerate(template_list):
               if template_gray is None or template_gray.size == 0:
                    logging.warning(f"Plantilla inválida (None o vacía) encontrada para estado '{state}', índice {i}. Saltando.")
                    continue

               # find_template_on_screen opera sobre la imagen que le pases (ROI o full)
               loc, match_val = self.find_template_on_screen(target_screen_gray, template_gray)

               # logging.debug(f"    Comparando '{state}' (tpl {i+1}/{len(template_list)}) en {roi_info_for_log}: Conf={match_val:.4f}") # Verboso

               if match_val > current_state_best_val:
                   current_state_best_val = match_val
                   current_state_best_loc = loc # Guardar posición por si se necesita

           # --- Evaluar resultado agregado para este estado ---
           if current_state_best_val >= self.threshold:
               # Si es mejor que el mejor global encontrado hasta ahora
               if current_state_best_val > best_match_val:
                   best_match_val = current_state_best_val
                   best_match_state = state
                   logging.info(f"  ¡Nuevo mejor match TEMPLATE! Estado: '{state}', Confianza: {best_match_val:.4f} (en {roi_info_for_log})")
           # Si no alcanza el umbral principal, pero sí el de fallback OCR Y *no tenemos ya un match claro*
           elif best_match_state == "unknown" and current_state_best_val >= self.ocr_fallback_threshold:
                 # Almacenar estado y su *mejor* confianza de template (aunque baja)
                 potential_ocr_states.append((state, current_state_best_val))
                 # logging.debug(f"    Candidato OCR añadido: '{state}' con conf. template {current_state_best_val:.4f}") # Verboso


           # Early exit si encontramos un match claro Y estábamos en la lista priorizada por contexto
           # Comprobar si best_match_state ha cambiado en esta iteración y si estaba priorizado
           if best_match_state == state and state in prioritized_states:
               logging.info(f"Match de template encontrado en estado priorizado ('{best_match_state}' con {best_match_val:.4f}). Deteniendo búsqueda temprana de plantillas.")
               break # Salir del bucle FOR de estados

       # --- Resultado del Template Matching ---
       if best_match_state != "unknown":
           result.update({
               'method': 'template',
               'state': best_match_state,
               'confidence': best_match_val
           })
           logging.info(f"Estado final detectado (Template): '{result['state']}' (Confianza: {result['confidence']:.4f})")
           self.last_recognized_state = best_match_state
           result['detection_time_s'] = time.time() - start_time
           return result

       # --- 2. OCR Fallback (Si no hubo match claro por template) ---
       if not potential_ocr_states:
           logging.warning("No se encontró coincidencia de plantilla por encima del umbral y no hay candidatos para OCR fallback.")
           self.last_recognized_state = None # Resetear estado si no se reconoce nada
           result['detection_time_s'] = time.time() - start_time
           return result # Devuelve 'unknown'

       logging.info(f"No se encontró match claro por plantilla (mejor < {self.threshold}). Intentando OCR fallback con {len(potential_ocr_states)} candidatos...")
       # Ordenar candidatos OCR por su confianza de template matching (descendente)
       potential_ocr_states.sort(key=lambda item: item[1], reverse=True)
       logging.debug(f"Candidatos OCR ordenados por conf. template: {[(s, f'{c:.3f}') for s, c in potential_ocr_states]}")

       for state_candidate, template_score in potential_ocr_states:
           # Verificar si hay regiones OCR definidas para este candidato
           if state_candidate in self.ocr_regions_mapping:
               regions_data_list = self.ocr_regions_mapping[state_candidate]

               # Validar que sea una lista
               if not isinstance(regions_data_list, list):
                   logging.warning(f"Regiones OCR para '{state_candidate}' en {OCR_MAPPING_FILE} no son una lista válida. Saltando candidato.")
                   continue
               if not regions_data_list:
                    logging.info(f"  Candidato '{state_candidate}' tiene una lista vacía de regiones OCR. Saltando.")
                    continue


               ocr_results_for_state = {} # Guardará los resultados OCR para este candidato {idx: details}
               at_least_one_region_matched = False # Flag para saber si encontramos un texto esperado

               logging.info(f"  Probando OCR para candidato: '{state_candidate}' (Score Template: {template_score:.3f}) con {len(regions_data_list)} regiones...")

               for idx, region_data in enumerate(regions_data_list):
                   # Validar formato de cada entrada de la región
                   if not (isinstance(region_data, dict) and
                           'region' in region_data and isinstance(region_data['region'], dict) and
                           all(k in region_data['region'] for k in ('left', 'top', 'width', 'height')) and
                           'expected_text' in region_data and isinstance(region_data['expected_text'], list)):
                       logging.warning(f"    Formato inválido o falta 'expected_text' en región OCR '{state_candidate}', índice {idx}. Saltando esta región: {region_data}")
                       # Guardar info de error para la GUI si se desea
                       ocr_results_for_state[idx] = {
                           'region': region_data.get('region', 'INVALID'),
                           'text': 'ERROR_INVALID_REGION_FORMAT',
                           'expected': region_data.get('expected_text', []),
                           'match_expected': False
                       }
                       continue # Saltar a la siguiente región

                   region_coords = region_data['region'] # Coordenadas ABSOLUTAS de pantalla
                   expected_texts = region_data['expected_text'] # Lista de textos esperados

                   # --- **OPTIMIZACIÓN**: Extraer región de la captura completa (screen_bgr_full) ---
                   x_abs, y_abs = region_coords['left'], region_coords['top']
                   w_ocr, h_ocr = region_coords['width'], region_coords['height']

                   # Mapear coords absolutas a relativas de la imagen capturada (screen_bgr_full)
                   x_rel = max(0, x_abs - monitor_region['left'])
                   y_rel = max(0, y_abs - monitor_region['top'])
                   # Calcular fin relativo, asegurando que no exceda las dimensiones de screen_bgr_full
                   x_rel_end = min(x_rel + w_ocr, w_screen) # w_screen es de la imagen gray
                   y_rel_end = min(y_rel + h_ocr, h_screen) # h_screen es de la imagen gray

                   region_img_bgr = None
                   if x_rel < x_rel_end and y_rel < y_rel_end: # Comprobar tamaño válido
                       try:
                            # Extraer de la imagen BGR original capturada
                            region_img_bgr = screen_bgr_full[y_rel:y_rel_end, x_rel:x_rel_end]
                            # logging.debug(f"    Extrayendo Región OCR {idx} para '{state_candidate}': Abs={region_coords} -> Rel=[{x_rel}:{x_rel_end}, {y_rel}:{y_rel_end}]")
                       except Exception as slice_err:
                            logging.error(f"Error al extraer slice para región OCR {idx} ('{state_candidate}'): {slice_err}. Saltando OCR para esta región.")
                            region_img_bgr = None # Asegurar que es None
                   else:
                       logging.warning(f"    Región OCR {idx} para '{state_candidate}' resulta en tamaño 0 o negativo relativo a la captura. Saltando OCR para esta región. Abs={region_coords}")
                   # -----------------------------------------------------------------------------

                   # Extraer texto (maneja None internamente)
                   extracted_text = self._extract_and_clean_text(region_img_bgr)

                   # --- Comparación ---
                   match_expected = False # Por defecto no hay match
                   if extracted_text: # Solo comparar si se extrajo algo
                       # Comparación insensible a mayúsculas/minúsculas y espacios extra
                       extracted_clean = extracted_text.lower().strip()
                       if extracted_clean: # No comparar si solo son espacios
                           for expected in expected_texts:
                               if isinstance(expected, str):
                                   # Comparar ignorando case y espacios al inicio/fin
                                   if expected.lower().strip() == extracted_clean:
                                       match_expected = True
                                       at_least_one_region_matched = True # Marcar que al menos una coincidió
                                       break # Suficiente con encontrar uno esperado
                               else:
                                    logging.warning(f"Texto esperado no es string en región {idx} de '{state_candidate}': {expected}. Ignorando.")

                   # --- Log detallado ---
                   logging.info(f"    Región OCR {idx} ({region_coords}): Texto='{extracted_text}', Esperado={expected_texts}, Coincide={match_expected}")

                   # Guardar resultados detallados para esta región (para la GUI)
                   ocr_results_for_state[idx] = {
                       'region': region_coords,
                       'text': extracted_text,
                       'expected': expected_texts,
                       'match_expected': match_expected
                   }
                   # Fin del bucle FOR de regiones

               # --- Decisión para el ESTADO CANDIDATO ---
               # Si AL MENOS UNA región OCR coincidió con su texto esperado para este estado
               if at_least_one_region_matched:
                   result.update({
                       'method': 'ocr',
                       'state': state_candidate,
                       'confidence': None, # Confianza de template no es relevante para decisión OCR
                       'ocr_results': ocr_results_for_state
                   })
                   logging.info(f"Estado final detectado (OCR Fallback Verificado): '{result['state']}' (al menos una región coincidió)")
                   self.last_recognized_state = state_candidate
                   result['detection_time_s'] = time.time() - start_time
                   return result # ¡Éxito! Salir del bucle de candidatos

               else:
                   logging.info(f"  Candidato '{state_candidate}': Ninguna región OCR coincidió con el texto esperado.")

           else: # El estado candidato no tenía regiones OCR definidas en el mapping
               logging.debug(f"  Candidato '{state_candidate}' no tiene regiones OCR definidas en {OCR_MAPPING_FILE}. Saltando.")
           # Fin del bucle FOR de candidatos OCR

       # --- Resultado Final: No se pudo identificar ---
       logging.warning("No se pudo detectar el estado mediante template ni OCR verificado.")
       self.last_recognized_state = None # Resetear estado si no se reconoce
       result['detection_time_s'] = time.time() - start_time
       # Devuelve el 'result' inicial que tiene method='unknown', state='unknown'
       return result


   def _extract_and_clean_text(self, image_bgr):
       """
       Extrae texto de una imagen BGR usando Tesseract, lo limpia y aplica
       preprocesamiento opcional.

       Args:
           image_bgr (numpy.ndarray): Imagen en formato BGR o None.

       Returns:
           str: Texto extraído y limpiado, o "" si la imagen es None o falla el OCR.
       """
       # Variable para el texto, inicializada a cadena vacía
       text = ""
       if image_bgr is None or image_bgr.size == 0:
           # logging.debug("Imagen vacía o None pasada a _extract_and_clean_text.")
           return text # Devuelve ""

       try:
           # Convertir a escala de grises para preprocesamiento y OCR
           gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)

           # --- Preprocesamiento Opcional ---
           if self.ocr_apply_thresholding:
               try:
                   # Usar THRESH_OTSU para determinar automáticamente el umbral
                   # THRESH_BINARY_INV puede funcionar mejor para texto oscuro sobre fondo claro
                   #_, gray_processed = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                   _, gray_processed = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
                   # logging.debug("Aplicando umbralización Otsu Inversa a la región OCR.")
               except Exception as thresh_error:
                   logging.warning(f"Error aplicando umbralización Otsu: {thresh_error}. Usando escala de grises original.")
                   gray_processed = gray # Fallback a la imagen en grises original
           else:
               gray_processed = gray # Usar la imagen en grises sin umbralizar
           # --------------------------------

           # Ejecutar Tesseract
           # Asegurarse de que la imagen procesada no sea None (aunque no debería serlo aquí)
           if gray_processed is not None:
               text = pytesseract.image_to_string(
                   gray_processed,
                   lang=self.ocr_lang,
                   config=self.ocr_config
               )

               # Limpieza básica del texto (realizarla incluso si Tesseract devuelve vacío)
               text = text.replace('\n', ' ').replace('\r', '') # Reemplazar saltos de línea por espacios
               # Eliminar caracteres no deseados (ajustar regex según necesidad)
               # Permite letras (con acentos comunes, ñ, ü), números, espacios, y símbolos .-:%,()
               # Nota: Puede ser necesario ajustar esta regex si se esperan otros símbolos
               text = re.sub(r'[^a-zA-Z0-9ñÑáéíóúÁÉÍÓÚüÜ\s\.\-:,%()]+', '', text)
               text = re.sub(r'\s+', ' ', text).strip() # Normalizar espacios múltiples y quitar
           else:
                logging.warning("La imagen preprocesada para OCR era None.")
                text = "" # Asegurar que sea cadena vacía


           # --- CORRECCIÓN DE INDENTACIÓN ---
           # Esta línea debe estar fuera del bloque 'if gray_processed is not None:' si queremos
           # que se loguee incluso si la imagen preprocesada era None (aunque el texto será "")
           # Pero lógicamente, pertenece al final del bloque 'try', antes de los 'except'.
           # Aseguramos que esté al mismo nivel que el 'if gray_processed...'
           logging.debug(f"Texto OCR extraído y limpiado: '{text}'") # <- INDENTACIÓN CORREGIDA

       except pytesseract.TesseractError as e:
           # Error específico de Tesseract (ej. idioma no encontrado, error interno)
           logging.error(f"Error de Tesseract durante el OCR: {e}")
           text = "" # Devolver cadena vacía en caso de error
       except pytesseract.TesseractNotFoundError:
           # Error grave: Tesseract no está instalado o no en el PATH
           logging.error("Error Crítico: Ejecutable de Tesseract no encontrado o no está en el PATH.")
           # Considerar lanzar una excepción aquí o manejarlo en un nivel superior,
           # ya que sin Tesseract, el OCR no funcionará en absoluto.
           text = "" # Devolver cadena vacía
       except cv2.error as cv_err:
           # Error durante operaciones de OpenCV (cvtColor, threshold)
           logging.error(f"Error de OpenCV durante preprocesamiento OCR: {cv_err}")
           text = "" # Devolver cadena vacía
       except Exception as e:
           # Otros errores inesperados
           logging.exception(f"Error inesperado durante OCR o limpieza: {e}")
           text = "" # Devolver cadena vacía

       # Devolver el texto resultante (será "" si hubo error o no se encontró texto)
       return text

# --- Ejemplo de Uso ---
if __name__ == "__main__":
   logging.info("Ejecutando prueba interna de ScreenRecognizer...")
   log_dir = os.path.join(PROJECT_DIR, "logs")
   # Crear directorios necesarios
   os.makedirs(CONFIG_DIR, exist_ok=True)
   os.makedirs(IMAGES_DIR, exist_ok=True) # Asegurar que images/ existe
   os.makedirs(os.path.join(IMAGES_DIR, '4K'), exist_ok=True) # Asegurar que images/4K/ existe para el ejemplo
   os.makedirs(log_dir, exist_ok=True)

   # Crear archivos JSON de ejemplo si no existen (sin sobreescribir)
   if not os.path.exists(TEMPLATE_MAPPING_FILE):
       logging.info(f"Creando archivo vacío: {TEMPLATE_MAPPING_FILE}"); save_json_mapping({}, TEMPLATE_MAPPING_FILE)
   if not os.path.exists(OCR_MAPPING_FILE):
       logging.info(f"Creando archivo vacío: {OCR_MAPPING_FILE}"); save_json_mapping({}, OCR_MAPPING_FILE)
   if not os.path.exists(STATE_TRANSITIONS_FILE):
       logging.info(f"Creando archivo vacío: {STATE_TRANSITIONS_FILE}"); save_json_mapping({}, STATE_TRANSITIONS_FILE)
   if not os.path.exists(STATE_ROIS_FILE):
       logging.info(f"Creando archivo vacío: {STATE_ROIS_FILE}"); save_json_mapping({}, STATE_ROIS_FILE)

   # Añadir un bloque try-except más robusto para la prueba
   try:
       # Crear instancia del reconocedor
       recognizer = ScreenRecognizer(
           monitor=1, resolution='4K', # Usar la resolución configurada
           threshold=0.75, # Umbral estándar
           ocr_fallback_threshold=0.60,
           ocr_lang='spa+eng',
           ocr_config='--psm 6', # Ejemplo: Asumir bloque de texto uniforme
           ocr_apply_thresholding=True
       )

       # Simular estado previo si se desea probar contexto
       # recognizer.last_recognized_state = "algun_estado_previo"

       logging.info(">>> Iniciando recognize_screen_for_test()...")
       start_test = time.time()
       detected_state_info = recognizer.recognize_screen_for_test()
       end_test = time.time()
       logging.info(f"<<< recognize_screen_for_test() finalizado en {end_test - start_test:.3f} seg.")

       logging.info("--- Resultado Detallado ---")
       # Imprimir resultado de forma legible, manejando la imagen
       result_to_print = detected_state_info.copy()
       captured_img = result_to_print.pop('captured_image', None) # Extraer imagen para no imprimirla entera

       # Imprimir el resto del diccionario
       try:
           logging.info(json.dumps(result_to_print, indent=4, ensure_ascii=False, default=str)) # default=str por si hay tipos no serializables
       except Exception as json_e:
            logging.error(f"No se pudo serializar el resultado a JSON: {json_e}")
            logging.info(f"Resultado (raw): {result_to_print}")

       # Mostrar información sobre la imagen capturada
       if captured_img is not None:
           logging.info(f"Imagen capturada: Sí (dimensiones: {captured_img.shape})")
           # Opcional: Guardar imagen capturada para revisión
           try:
               ts = time.strftime("%Y%m%d_%H%M%S")
               capture_filename = os.path.join(log_dir, f"test_capture_{ts}.png")
               cv2.imwrite(capture_filename, captured_img)
               logging.info(f"Imagen de prueba guardada en: {capture_filename}")
           except Exception as imwrite_e:
               logging.error(f"No se pudo guardar la imagen de prueba: {imwrite_e}")
       else:
           logging.info("Imagen capturada: No")

       logging.info("---------------------------")

   except pytesseract.TesseractNotFoundError:
        logging.error("="*60)
        logging.error(" ERROR CRÍTICO: TESSERACT NO ENCONTRADO ")
        logging.error(" Asegúrese de que Tesseract OCR esté instalado y que su ejecutable")
        logging.error(" esté en la variable de entorno PATH del sistema.")
        logging.error(" Descarga: https://github.com/tesseract-ocr/tesseract")
        logging.error("="*60)
   except ImportError as ie:
        logging.exception(f"Error de importación. ¿Faltan dependencias? ({ie}). Instale con 'pip install -r requirements.txt'")
   except Exception as e:
        # Captura cualquier otra excepción durante la inicialización o prueba
        logging.exception("Error inesperado durante la prueba interna de ScreenRecognizer.")

# --- END OF FILE screen_recognizer ---