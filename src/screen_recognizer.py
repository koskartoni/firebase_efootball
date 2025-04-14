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
               return sct.monitors
       except Exception as e:
           logging.error(f"Error detectando monitores: {e}")
           return [{}] # Fallback

   def _get_monitor_region(self):
       """Obtiene la geometría del monitor seleccionado."""
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
       missing_files = [] # Para seguimiento/logging
       corrupt_files = [] # Para seguimiento/logging

       # Determinar directorio de imágenes según resolución
       resolution_dir = os.path.join(IMAGES_DIR, self.resolution)
       if not os.path.exists(resolution_dir):
           logging.warning(f"Directorio de resolución '{self.resolution}' no encontrado. Usando base: {IMAGES_DIR}")
           templates_dir = IMAGES_DIR
       else:
           templates_dir = resolution_dir
           logging.info(f"Cargando plantillas desde: {templates_dir} (Resolución: {self.resolution})")

       for state, file_list in self.template_names_mapping.items():
           if not isinstance(file_list, list):
               logging.warning(f"Valor para '{state}' en {TEMPLATE_MAPPING_FILE} no es una lista. Saltando.")
               error_count += 1
               continue # Saltar a la siguiente entrada del mapping

           loaded_images = []
           for file_name in file_list:
               if not isinstance(file_name, str):
                   logging.warning(f"Nombre de archivo no string para estado '{state}': {file_name}. Saltando.")
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
                           logging.error(f"Corrupta/inválida: {template_path}")
                           corrupt_files.append(template_path)
                           error_count += 1
                   except Exception as e:
                       logging.error(f"Excepción al cargar {template_path}: {e}")
                       corrupt_files.append(template_path)
                       error_count += 1
               else: # Archivo no existe
                   logging.warning(f"Plantilla faltante: {template_path}")
                   missing_files.append(template_path)
                   error_count += 1

           if loaded_images:
               self.templates[state] = loaded_images

       logging.info(f"Plantillas: {loaded_count} cargadas, {error_count} errores/faltantes.")

       # Logging de resumen de errores (más conciso)
       if missing_files:
           logging.warning(f"Plantillas faltantes: {len(missing_files)} (ver 'missing.log' para detalles).")
           with open("missing.log", "w", encoding="utf-8") as f:
               for path in missing_files: f.write(path + "\n") # Cada ruta en una línea
       if corrupt_files:
           logging.error(f"Plantillas corruptas/inválidas: {len(corrupt_files)} (ver 'corrupt.log').")
           with open("corrupt.log", "w", encoding="utf-8") as f:
               for path in corrupt_files: f.write(path + "\n")

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
       monitor_region = self._get_monitor_region() # Obtener la región del monitor primario/seleccionado
       if monitor_region is None: return None

       # Si se pide una región, usarla. Si no, usar la del monitor entero.
       capture_area = region if region is not None else monitor_region
       # Validar que la región no sea más grande que la pantalla física (puede causar error en mss)
       # Nota: mss podría manejar esto internamente, pero una comprobación extra puede prevenir errores.
       if region:
           capture_area['width'] = min(region['width'], monitor_region['width'] - (region['left'] - monitor_region['left']))
           capture_area['height'] = min(region['height'], monitor_region['height'] - (region['top'] - monitor_region['top']))
           capture_area['left'] = max(region['left'], monitor_region['left'])
           capture_area['top'] = max(region['top'], monitor_region['top'])

       try:
           with mss.mss() as sct: # Usar un contexto 'with' asegura liberación de recursos
               sct_img = sct.grab(capture_area)
               img = np.array(sct_img)
               # Convertir de BGRA a BGR (formato común para OpenCV)
               img_bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
               return img_bgr
       except mss.ScreenShotError as e:
           logging.error(f"Error MSS al capturar {capture_area}: {e}")
           return None
       except Exception as e:
           logging.error(f"Error inesperado durante captura ({capture_area}): {e}")
           return None # Propagar error devolviendo None

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
       if template_gray is None or screen_gray is None: return None, 0.0
       # Si la plantilla es más grande que la pantalla/ROI, no se puede encontrar
       if template_gray.shape[0] > screen_gray.shape[0] or template_gray.shape[1] > screen_gray.shape[1]:
           # logging.debug("Plantilla más grande que pantalla/ROI.") # Puede ser muy verboso
           return None, 0.0 # Coincidencia imposible, retornar sin error
       try:
           result = cv2.matchTemplate(screen_gray, template_gray, cv2.TM_CCOEFF_NORMED)
           _, max_val, _, max_loc = cv2.minMaxLoc(result)
           return max_loc, max_val
       except cv2.error as e:
            # Común si uno de los tamaños es 0 o inválido después del slicing ROI
            logging.warning(f"Error en matchTemplate (probablemente tamaño inválido): {e}")
            return None, 0.0
       except Exception as e:
           logging.error(f"Error inesperado en find_template_on_screen: {e}")
           return None, 0.0

   def recognize_screen_for_test(self):
       """
       Intenta reconocer la pantalla actual con optimizaciones (ROI, contexto)
       y fallback a OCR, devolviendo información detallada para el tester.
       Optimizado para extraer regiones OCR de una única captura inicial.

       Returns:
           dict: Un diccionario con los resultados:
               'method': 'template', 'ocr', o 'unknown'.
               'state': Nombre del estado detectado o 'unknown'.
               'confidence': Confianza del template matching (si aplica).
               'ocr_results': Diccionario con detalles OCR por región (si aplica).
                   { region_idx: {'region':..., 'text':..., 'expected':..., 'match_expected':...}}
               'detection_time_s': Tiempo total de detección en segundos.
       """
       logging.info(f"--- Iniciando Reconocimiento (Último estado: {self.last_recognized_state}) ---")
       start_time = time.time()

       result = {
           'method': 'unknown', 'state': 'unknown',
           'confidence': None, 'ocr_results': None, 'detection_time_s': 0.0
       }

       # --- 0. Captura ÚNICA de Pantalla Completa ---
       monitor_region = self._get_monitor_region()
       if monitor_region is None:
           logging.error("No se pudo obtener la región del monitor. Abortando reconocimiento.")
           result['detection_time_s'] = time.time() - start_time
           return result

       screen_bgr_full = self.capture_screen() # Usa la región del monitor por defecto
       if screen_bgr_full is None:
           logging.error("Fallo captura inicial de pantalla completa.")
           result['detection_time_s'] = time.time() - start_time
           return result

       screen_gray_full = cv2.cvtColor(screen_bgr_full, cv2.COLOR_BGR2GRAY)
       h_screen, w_screen = screen_gray_full.shape # Dimensiones de la imagen capturada

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
                   other_states = [s for s in states_to_check if s not in prioritized_states]
                   states_to_check = prioritized_states + other_states
               else:
                    logging.info(f"Contexto encontrado para '{self.last_recognized_state}', pero sin plantillas válidas para los estados siguientes.")
           else:
                logging.warning(f"Transiciones para '{self.last_recognized_state}' no es una lista válida.")

       if not prioritized_states:
           logging.info("No se aplica contexto (sin estado previo válido o sin transiciones/plantillas).")

       # --- 1. Template Matching (con ROI si está definido) ---
       best_match_state = "unknown"
       best_match_val = 0.0
       potential_ocr_states = [] # Almacena tuplas (state, confidence)

       logging.debug(f"Orden de chequeo: {states_to_check}")
       for state in states_to_check:
           if state not in self.templates: # Seguridad extra
               continue

           template_list = self.templates[state]
           state_best_val = 0.0

           # --- Determinar ROI ---
           search_roi_coords = self.state_rois.get(state)
           target_screen_gray = screen_gray_full # Por defecto, buscar en toda la pantalla capturada
           roi_offset = {'left': 0, 'top': 0} # Offset relativo a la pantalla completa
           using_roi = False

           if search_roi_coords and isinstance(search_roi_coords, dict) and all(k in search_roi_coords for k in ('left', 'top', 'width', 'height')):
               # Extraer ROI de la CAPTURA COMPLETA (más eficiente que recapturar)
               # Coordenadas ROI son absolutas, hay que mapearlas a la imagen capturada
               x_abs, y_abs = search_roi_coords['left'], search_roi_coords['top']
               w_roi, h_roi = search_roi_coords['width'], search_roi_coords['height']

               # Calcular coords relativas a la imagen capturada (screen_gray_full)
               x_rel = max(0, x_abs - monitor_region['left'])
               y_rel = max(0, y_abs - monitor_region['top'])
               # Ajustar ancho/alto para no salirse de la pantalla capturada
               w_rel = min(w_roi, w_screen - x_rel)
               h_rel = min(h_roi, h_screen - y_rel)

               if w_rel > 0 and h_rel > 0:
                   target_screen_gray = screen_gray_full[y_rel : y_rel + h_rel, x_rel : x_rel + w_rel]
                   # El offset es importante si necesitas coordenadas absolutas del match más tarde
                   roi_offset = {'left': x_rel, 'top': y_rel}
                   using_roi = True
                   logging.debug(f"  Usando ROI para '{state}': Abs={search_roi_coords} -> Rel={x_rel},{y_rel},{w_rel},{h_rel}")
               else:
                    logging.warning(f"  ROI para '{state}' resulta en tamaño 0 o negativo relativo a la captura. Usando pantalla completa. ROI Abs={search_roi_coords}")
                    target_screen_gray = screen_gray_full # Fallback a pantalla completa
                    using_roi = False # Asegurar que se marque como no usando ROI
           # else: logging.debug(f"  Sin ROI definida para '{state}'.") # Puede ser verboso

           # --- Buscar plantillas dentro del target_screen_gray (ROI o Full) ---
           current_state_best_val = 0.0
           for i, template_gray in enumerate(template_list):
               # find_template_on_screen opera sobre la imagen que le pases (ROI o full)
               loc, match_val = self.find_template_on_screen(target_screen_gray, template_gray)
               # logging.debug(f"    Comparando '{state}' (tpl {i+1}) en {'ROI' if using_roi else 'Full'}: Conf={match_val:.3f}") # Verboso
               current_state_best_val = max(current_state_best_val, match_val)

           # --- Evaluar resultado para este estado ---
           if current_state_best_val >= self.threshold:
               # Si es mejor que el mejor global encontrado hasta ahora
               if current_state_best_val > best_match_val:
                   best_match_val = current_state_best_val
                   best_match_state = state
                   logging.debug(f"    ¡Nuevo mejor match TEMPLATE! Estado: {state}, Confianza: {best_match_val:.3f}")
           # Si no alcanza el umbral principal, pero sí el de fallback OCR
           elif current_state_best_val >= self.ocr_fallback_threshold:
                 # Solo considerar si no hay match claro aún (evita añadir si ya tenemos > threshold)
                 if best_match_state == "unknown":
                      potential_ocr_states.append((state, current_state_best_val))
                      logging.debug(f"    Candidato OCR añadido: {state} con {current_state_best_val:.3f}")

           # Early exit si encontramos un match claro Y estábamos en la lista priorizada por contexto
           if best_match_state != "unknown" and state in prioritized_states:
                logging.info(f"Match de template en estado priorizado ({best_match_state} con {best_match_val:.3f}), deteniendo búsqueda temprana.")
                break # Salir del bucle de estados

       # --- Resultado del Template Matching ---
       if best_match_state != "unknown":
           result['method'] = 'template'
           result['state'] = best_match_state
           result['confidence'] = best_match_val
           logging.info(f"Estado detectado (Template): {result['state']} (Confianza: {result['confidence']:.3f})")
           self.last_recognized_state = best_match_state
           result['detection_time_s'] = time.time() - start_time
           return result

       # --- 2. OCR Fallback (Si no hubo match claro por template) ---
       if not potential_ocr_states:
            logging.warning("No se encontró coincidencia de plantilla y no hay candidatos para OCR fallback.")
            self.last_recognized_state = None
            result['detection_time_s'] = time.time() - start_time
            return result # Devuelve 'unknown'

       logging.info("No se encontró coincidencia clara de plantilla. Intentando OCR fallback...")
       # Ordenar candidatos OCR por su confianza de template matching (descendente)
       potential_ocr_states.sort(key=lambda item: item[1], reverse=True)
       logging.debug(f"Candidatos OCR ordenados: {potential_ocr_states}")

       for state_candidate, match_score in potential_ocr_states:
           if state_candidate in self.ocr_regions_mapping:
               regions_data_list = self.ocr_regions_mapping[state_candidate]

               if not isinstance(regions_data_list, list):
                   logging.warning(f"Regiones OCR para '{state_candidate}' no son una lista válida en {OCR_MAPPING_FILE}. Saltando.")
                   continue

               ocr_results_for_state = {} # Guardará los resultados OCR para este candidato
               found_match_in_state = False # Flag para saber si encontramos un texto esperado

               logging.info(f"  Probando OCR para candidato: {state_candidate} (Score Template: {match_score:.3f}) con {len(regions_data_list)} regiones...")

               for idx, region_data in enumerate(regions_data_list):
                   # Validar formato de la región
                   if not (isinstance(region_data, dict) and 'region' in region_data and
                           isinstance(region_data['region'], dict) and
                           all(k in region_data['region'] for k in ('left', 'top', 'width', 'height'))):
                       logging.warning(f"    Formato inválido región OCR '{state_candidate}', índice {idx}. Saltando: {region_data}")
                       continue

                   region_coords = region_data['region'] # Coordenadas ABSOLUTAS de pantalla
                   expected_texts = region_data.get('expected_text', []) # Lista de textos esperados
                   if not isinstance(expected_texts, list):
                       logging.warning(f"    'expected_text' para región {idx} de '{state_candidate}' no es una lista. Tratando como vacía.")
                       expected_texts = []

                   # --- **OPTIMIZACIÓN**: Extraer región de la captura completa (screen_bgr_full) ---
                   x_abs, y_abs = region_coords['left'], region_coords['top']
                   w_ocr, h_ocr = region_coords['width'], region_coords['height']

                   # Mapear coords absolutas a relativas de la imagen capturada
                   x_rel = max(0, x_abs - monitor_region['left'])
                   y_rel = max(0, y_abs - monitor_region['top'])
                   # Calcular fin relativo, asegurando que no exceda las dimensiones de screen_bgr_full
                   x_rel_end = min(x_rel + w_ocr, w_screen)
                   y_rel_end = min(y_rel + h_ocr, h_screen)

                   region_img = None
                   if x_rel < x_rel_end and y_rel < y_rel_end: # Comprobar tamaño válido
                       region_img = screen_bgr_full[y_rel:y_rel_end, x_rel:x_rel_end]
                       logging.debug(f"    Extrayendo Región OCR {idx} para '{state_candidate}': Abs={region_coords} -> Rel={x_rel},{y_rel},{x_rel_end-x_rel},{y_rel_end-y_rel}")
                   else:
                       logging.warning(f"    Región OCR {idx} para '{state_candidate}' resulta en tamaño 0 o negativo relativo a la captura. Saltando OCR para esta región. Abs={region_coords}")
                   # -----------------------------------------------------------------------------

                   extracted_text = self._extract_and_clean_text(region_img) # Puede devolver "" si region_img es None

                   match_expected = False
                   if extracted_text and expected_texts:
                       # Comparación insensible a mayúsculas/minúsculas
                       extracted_lower = extracted_text.lower()
                       for expected in expected_texts:
                           if expected.lower() == extracted_lower:
                               match_expected = True
                               break # Suficiente con encontrar uno

                   logging.info(f"    Región {idx}: Texto='{extracted_text}', Esperado={expected_texts}, Coincide={match_expected}")

                   # Guardar resultados detallados para esta región
                   ocr_results_for_state[idx] = {
                       'region': region_coords,
                       'text': extracted_text,
                       'expected': expected_texts,
                       'match_expected': match_expected
                   }

                   # Si encontramos una coincidencia de texto esperado, marcamos el estado
                   if match_expected:
                       found_match_in_state = True

               # Si AL MENOS UNA región OCR coincidió con su texto esperado para este estado candidato
               if found_match_in_state:
                   result['method'] = 'ocr'
                   result['state'] = state_candidate
                   result['confidence'] = None # Confianza de template no es relevante aquí
                   result['ocr_results'] = ocr_results_for_state
                   logging.info(f"Estado detectado (OCR Fallback Verificado): {result['state']}")
                   self.last_recognized_state = state_candidate
                   result['detection_time_s'] = time.time() - start_time
                   return result # ¡Éxito! Salir

           # else: # El estado candidato no tenía regiones OCR definidas
               # logging.debug(f"  Candidato '{state_candidate}' no tiene regiones OCR definidas en {OCR_MAPPING_FILE}.")

       # --- Resultado Final: No se pudo identificar ---
       logging.warning("No se pudo detectar el estado mediante template ni OCR verificado.")
       self.last_recognized_state = None
       result['detection_time_s'] = time.time() - start_time
       return result # Devuelve 'unknown'


   def _extract_and_clean_text(self, image_bgr):
       """
       Extrae texto de una imagen BGR usando Tesseract, lo limpia y aplica
       preprocesamiento opcional.

       Args:
           image_bgr (numpy.ndarray): Imagen en formato BGR o None.

       Returns:
           str: Texto extraído y limpiado, o "" si la imagen es None o falla el OCR.
       """
       if image_bgr is None or image_bgr.size == 0:
            # logging.debug("Imagen vacía o None pasada a _extract_and_clean_text.")
            return ""
       try:
           gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)

           # --- Preprocesamiento Opcional ---
           if self.ocr_apply_thresholding:
               try:
                   # Usar THRESH_OTSU para determinar automáticamente el umbral
                   _, gray_processed = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                   logging.debug("Aplicando umbralización Otsu a la región OCR.")
               except Exception as thresh_error:
                   logging.warning(f"Error aplicando umbralización Otsu: {thresh_error}. Usando escala de grises original.")
                   gray_processed = gray # Fallback
           else:
               gray_processed = gray
           # --------------------------------

           # Ejecutar Tesseract
           text = pytesseract.image_to_string(
               gray_processed,
               lang=self.ocr_lang,
               config=self.ocr_config
           )

           # Limpieza básica del texto
           text = text.replace('\n', ' ').replace('\r', '') # Reemplazar saltos de línea
           # Eliminar caracteres no deseados (ajustar regex según necesidad)
           # Permite letras (con acentos, ñ, ü), números, espacios, y algunos símbolos comunes
           text = re.sub(r'[^a-zA-Z0-9ñÑáéíóúÁÉÍÓÚüÜ\s()\-.:]', '', text)
           text = re.sub(r'\s+', ' ', text).strip() # Normalizar espacios múltiples

           # logging.debug(f"Texto OCR extraído y limpiado: '{text}'")
           return text
       except pytesseract.TesseractNotFoundError:
           logging.error("Error de Tesseract: Ejecutable no encontrado o no está en el PATH.")
           # Considerar lanzar una excepción más específica o manejarla de otra forma
           return ""
       except Exception as e:
           logging.error(f"Error inesperado durante OCR o limpieza: {e}")
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
       # Ejemplo mostrando los nuevos parámetros de inicialización
       recognizer = ScreenRecognizer(
           monitor=1, resolution='4K', # Añadido resolución
           threshold=0.80, # Umbral un poco más alto
           ocr_fallback_threshold=0.65,
           ocr_lang='spa+eng',
           ocr_config='--psm 6', # Ejemplo: Asumir bloque de texto uniforme
           ocr_apply_thresholding=True
       )
       # recognizer.last_recognized_state = "pantalla_bienvenida" # Simular estado previo

       logging.info("Intentando reconocer pantalla actual (método de test)...")
       start_test = time.time()
       detected_state_info = recognizer.recognize_screen_for_test()
       end_test = time.time()

       logging.info(f"Tiempo total del test recognize_screen_for_test: {end_test - start_test:.3f} seg")
       logging.info("--- Resultado Detallado ---")
       # Usar ensure_ascii=False para mostrar correctamente caracteres españoles en el log/consola
       logging.info(json.dumps(detected_state_info, indent=4, ensure_ascii=False))
       logging.info("---------------------------")

   except Exception as e:
       logging.exception("Error durante la prueba interna de ScreenRecognizer.")

# --- END OF FILE screen_recognizer ---