# --- START OF FILE src/panels/result_panel.py ---

import tkinter as tk
from tkinter import ttk
import logging

class ResultPanel(ttk.LabelFrame):
    """
    Panel para mostrar los resultados de la detección de pantalla y
    ofrecer botones de acción contextuales (Confirmar, Negar, ROI).
    """
    def __init__(self, master, main_app, **kwargs):
        """
        Inicializa el Panel de Resultados.

        Args:
            master: El widget padre (normalmente el frame de la columna izquierda).
            main_app: Una referencia a la instancia principal de ScreenTesterGUI.
            **kwargs: Argumentos adicionales para ttk.LabelFrame.
        """
        kwargs['text'] = kwargs.get('text', "Resultados Detección")
        super().__init__(master, **kwargs)
        self.main_app = main_app
        logging.debug("Inicializando ResultPanel.")

        # --- Variables para las etiquetas ---
        self.method_var = tk.StringVar(value="-")
        self.state_var = tk.StringVar(value="-")
        self.confidence_var = tk.StringVar(value="-")
        self.time_var = tk.StringVar(value="-")
        self.roi_status_var = tk.StringVar(value="ROI: -")

        # --- Referencias a botones para control de estado ---
        self.confirm_button = None
        self.deny_button = None
        self.define_roi_button = None
        self.remove_roi_button = None

        self._create_widgets()
        self.clear_results() # Establecer estado inicial limpio

    def _create_widgets(self):
        """Crea las etiquetas y botones dentro del panel."""
        logging.debug("Creando widgets para ResultPanel.")

        # --- Configuración del Grid ---
        # 2 columnas principales: Etiquetas a la izquierda (0), Valores a la derecha (1)
        self.columnconfigure(0, weight=0) # Etiquetas no se expanden
        self.columnconfigure(1, weight=1) # Valores sí se expanden horizontalmente

        # --- Etiquetas de Resultados ---
        row_idx = 0
        ttk.Label(self, text="Método:").grid(row=row_idx, column=0, sticky="w", padx=5, pady=2)
        ttk.Label(self, textvariable=self.method_var, anchor="w").grid(row=row_idx, column=1, sticky="ew", padx=5, pady=2)
        row_idx += 1

        ttk.Label(self, text="Estado:").grid(row=row_idx, column=0, sticky="w", padx=5, pady=2)
        ttk.Label(self, textvariable=self.state_var, anchor="w").grid(row=row_idx, column=1, sticky="ew", padx=5, pady=2)
        row_idx += 1

        ttk.Label(self, text="Confianza:").grid(row=row_idx, column=0, sticky="w", padx=5, pady=2)
        ttk.Label(self, textvariable=self.confidence_var, anchor="w").grid(row=row_idx, column=1, sticky="ew", padx=5, pady=2)
        row_idx += 1

        ttk.Label(self, text="Tiempo (s):").grid(row=row_idx, column=0, sticky="w", padx=5, pady=2)
        ttk.Label(self, textvariable=self.time_var, anchor="w").grid(row=row_idx, column=1, sticky="ew", padx=5, pady=2)
        row_idx += 1

        # Etiqueta de estado del ROI (ocupando ambas columnas para centrar o alinear)
        self.roi_status_label = ttk.Label(self, textvariable=self.roi_status_var, anchor="w", font=self.main_app.status_font) # Usar fuente más pequeña
        self.roi_status_label.grid(row=row_idx, column=0, columnspan=2, sticky="ew", padx=5, pady=(5, 10))
        row_idx += 1

        # --- Frame para los botones de acción ---
        # Agrupar botones para mejor organización visual y de layout
        button_frame = ttk.Frame(self)
        button_frame.grid(row=row_idx, column=0, columnspan=2, sticky="ew", pady=(5, 0))
        # Permitir que los botones se distribuyan equitativamente
        button_frame.columnconfigure(0, weight=1)
        button_frame.columnconfigure(1, weight=1)
        button_frame.columnconfigure(2, weight=1)
        button_frame.columnconfigure(3, weight=1)


        # --- Botones de Acción ---
        self.confirm_button = ttk.Button(
            button_frame, text="✅ Confirmar", command=self.main_app.confirm_detection
        )
        self.confirm_button.grid(row=0, column=0, padx=2, pady=2, sticky="ew")

        self.deny_button = ttk.Button(
            button_frame, text="❌ Negar", command=self.main_app.deny_detection
        )
        self.deny_button.grid(row=0, column=1, padx=2, pady=2, sticky="ew")

        self.define_roi_button = ttk.Button(
            button_frame, text="🎯 Definir/Editar ROI", command=self.main_app.define_roi_for_state
        )
        self.define_roi_button.grid(row=1, column=0, padx=2, pady=2, sticky="ew")

        self.remove_roi_button = ttk.Button(
            button_frame, text="🗑️ Eliminar ROI", command=self.main_app.remove_roi_for_state
        )
        self.remove_roi_button.grid(row=1, column=1, padx=2, pady=2, sticky="ew")

        logging.debug("Widgets de ResultPanel creados.")


    def update_results(self, result_dict):
        """
        Actualiza las etiquetas y el estado de los botones basado en el
        diccionario de resultados del reconocimiento.

        Args:
            result_dict (dict): El diccionario devuelto por recognize_screen_for_test.
                                Puede ser None si no hay resultado.
        """
        logging.debug(f"Actualizando ResultPanel con: {result_dict}")
        if not result_dict:
            self.clear_results()
            return

        method = result_dict.get('method', 'unknown')
        state = result_dict.get('state', 'unknown')
        confidence = result_dict.get('confidence') # Puede ser None
        detection_time = result_dict.get('detection_time_s')
        error_msg = result_dict.get('error_message')

        self.method_var.set(method.capitalize())
        self.state_var.set(state)

        if confidence is not None:
            self.confidence_var.set(f"{confidence:.4f}")
        else:
            self.confidence_var.set("-")

        if detection_time is not None:
            self.time_var.set(f"{detection_time:.3f}")
        else:
            self.time_var.set("-")

        # Actualizar etiqueta ROI para el estado detectado
        if state != 'unknown' and state != 'error':
            self.update_roi_label(state)
        else:
            self.roi_status_var.set("ROI: -")

        # --- Lógica de habilitación de botones ---
        is_valid_detection = (method in ['template', 'ocr'] and state != 'unknown')

        if is_valid_detection:
            self.confirm_button.config(state=tk.NORMAL)
            self.deny_button.config(state=tk.NORMAL)
            # Botones ROI habilitados SÓLO si se ha negado O si el estado ya existe
            # Se habilitarán explícitamente al negar o seleccionar corrección.
            # Aquí se deshabilitan inicialmente tras una detección VÁLIDA.
            self.define_roi_button.config(state=tk.DISABLED)
            self.remove_roi_button.config(state=tk.DISABLED)
            # Si el estado detectado YA tiene ROI, habilitar 'Eliminar ROI'
            if self.main_app.recognizer and state in self.main_app.recognizer.state_rois:
                 self.define_roi_button.config(state=tk.NORMAL) # Habilitar editar si ya existe
                 self.remove_roi_button.config(state=tk.NORMAL)

        elif method == 'error':
            self.state_var.set(f"Error: {error_msg or state}")
            self.clear_results() # Limpiar campos y deshabilitar botones en caso de error
            self.method_var.set(method.capitalize()) # Mostrar que fue un error
            self.time_var.set(f"{detection_time:.3f}" if detection_time is not None else "-") # Mantener tiempo si está

        else: # Caso 'unknown' u otro inesperado
            self.clear_results() # Limpiar y deshabilitar todo
            # Aún podemos mostrar el método 'Unknown' y el tiempo
            self.method_var.set(method.capitalize())
            self.time_var.set(f"{detection_time:.3f}" if detection_time is not None else "-")
            # Habilitar definir ROI en caso de 'unknown'? Quizás sí.
            self.define_roi_button.config(state=tk.NORMAL) # Permitir definir ROI si no se reconoció nada
            self.remove_roi_button.config(state=tk.DISABLED)

        logging.debug("ResultPanel actualizado.")

    def clear_results(self):
        """Limpia todas las etiquetas y deshabilita los botones de acción."""
        logging.debug("Limpiando ResultPanel.")
        self.method_var.set("-")
        self.state_var.set("-")
        self.confidence_var.set("-")
        self.time_var.set("-")
        self.roi_status_var.set("ROI: -")

        # Deshabilitar todos los botones por defecto al limpiar
        if self.confirm_button: self.confirm_button.config(state=tk.DISABLED)
        if self.deny_button: self.deny_button.config(state=tk.DISABLED)
        if self.define_roi_button: self.define_roi_button.config(state=tk.DISABLED)
        if self.remove_roi_button: self.remove_roi_button.config(state=tk.DISABLED)

    def update_roi_label(self, state_name):
        """
        Comprueba si el estado dado tiene un ROI definido en el recognizer
        y actualiza la etiqueta correspondiente.
        """
        if not state_name or state_name in ['unknown', 'error']:
            self.roi_status_var.set("ROI: -")
            return

        has_roi = False
        if self.main_app.recognizer and state_name in self.main_app.recognizer.state_rois:
             # Podríamos añadir una verificación más si state_rois[state_name] es un dict válido
             roi_data = self.main_app.recognizer.state_rois[state_name]
             if isinstance(roi_data, dict) and all(k in roi_data for k in ('left', 'top', 'width', 'height')):
                 has_roi = True

        if has_roi:
            self.roi_status_var.set(f"ROI: Definido para '{state_name}'")
            # Si actualizamos porque se seleccionó un estado (detectado o corregido)
            # que tiene ROI, habilitamos los botones de edición/eliminación
            if self.define_roi_button: self.define_roi_button.config(state=tk.NORMAL)
            if self.remove_roi_button: self.remove_roi_button.config(state=tk.NORMAL)
        else:
            self.roi_status_var.set(f"ROI: No definido para '{state_name}'")
            # Si el estado no tiene ROI, solo habilitamos definir/editar
            if self.define_roi_button: self.define_roi_button.config(state=tk.NORMAL)
            if self.remove_roi_button: self.remove_roi_button.config(state=tk.DISABLED) # No se puede eliminar lo que no existe

    def enable_roi_buttons(self):
        """Habilita los botones de gestión de ROI explícitamente."""
        if self.define_roi_button: self.define_roi_button.config(state=tk.NORMAL)
        # Habilitar eliminar solo si el estado actual tiene ROI (se chequea en update_roi_label)
        # if self.remove_roi_button: self.remove_roi_button.config(state=tk.NORMAL)
        logging.debug("Botones ROI habilitados (Definir/Editar seguro, Eliminar depende del estado).")

    def disable_confirm_deny(self):
        """Deshabilita los botones de Confirmar y Negar."""
        if self.confirm_button: self.confirm_button.config(state=tk.DISABLED)
        if self.deny_button: self.deny_button.config(state=tk.DISABLED)
        logging.debug("Botones Confirmar/Negar deshabilitados.")

# --- END OF FILE src/panels/result_panel.py ---