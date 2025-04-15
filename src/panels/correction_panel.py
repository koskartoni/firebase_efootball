# --- START OF FILE src/panels/correction_panel.py ---

import tkinter as tk
from tkinter import ttk
import logging

class CorrectionPanel(ttk.LabelFrame):
    """
    Panel que se muestra cuando una detección es negada, permitiendo
    al usuario seleccionar el estado correcto y registrarlo en el log.
    """
    def __init__(self, master, main_app, **kwargs):
        """
        Inicializa el Panel de Corrección.

        Args:
            master: El widget padre (normalmente el frame de la columna izquierda).
            main_app: Una referencia a la instancia principal de ScreenTesterGUI.
            **kwargs: Argumentos adicionales para ttk.LabelFrame.
        """
        kwargs['text'] = kwargs.get('text', "Corrección Manual")
        super().__init__(master, **kwargs)
        self.main_app = main_app
        logging.debug("Inicializando CorrectionPanel.")

        # --- Variables y Referencias ---
        self.selected_state_var = tk.StringVar()
        self.correct_state_combo = None
        self.log_button = None

        # --- Widgets ---
        self._create_widgets()
        self.hide() # Oculto por defecto

    def _create_widgets(self):
        """Crea los widgets del panel: etiqueta, combobox y botón."""
        logging.debug("Creando widgets para CorrectionPanel.")

        # Configurar grid interno
        self.columnconfigure(0, weight=1) # Permitir que el combobox se expanda

        # --- Etiqueta de Instrucción ---
        instruction_label = ttk.Label(
            self,
            text="Seleccione el estado correcto:",
            anchor="w"
        )
        instruction_label.grid(row=0, column=0, sticky="ew", padx=5, pady=(0, 5))

        # --- Combobox de Estados ---
        self.correct_state_combo = ttk.Combobox(
            self,
            textvariable=self.selected_state_var,
            state="readonly", # Evitar entrada manual
            # Se poblará dinámicamente
        )
        self.correct_state_combo.grid(row=1, column=0, sticky="ew", padx=5, pady=(0, 10))
        # Binding para detectar selección
        self.correct_state_combo.bind("<<ComboboxSelected>>", self._on_state_selected_event)

        # --- Botón de Registro ---
        self.log_button = ttk.Button(
            self,
            text="Registrar Corrección (Log)",
            command=self.main_app.log_correct_state, # Llama al método en la app principal
            state="disabled" # Deshabilitado hasta que se seleccione un estado
        )
        self.log_button.grid(row=2, column=0, sticky="ew", padx=5)

        logging.debug("Widgets de CorrectionPanel creados.")

    def populate_combobox(self, state_list):
        """
        Llena el Combobox con la lista de estados disponibles.

        Args:
            state_list (list): Lista de strings con los nombres de los estados.
        """
        logging.debug(f"Poblando Combobox de corrección con {len(state_list)} estados.")
        # Ordenar alfabéticamente para facilitar la búsqueda
        sorted_states = sorted(state_list)
        if self.correct_state_combo:
            self.correct_state_combo['values'] = sorted_states
            self.reset() # Limpiar selección anterior al repoblar
        else:
            logging.warning("Intento de poblar Combobox antes de su creación.")

    def get_selected_state(self):
        """
        Devuelve el estado actualmente seleccionado en el Combobox.

        Returns:
            str: El nombre del estado seleccionado, o None si no hay selección.
        """
        selected = self.selected_state_var.get()
        return selected if selected else None

    def reset(self):
        """Limpia la selección actual del Combobox y deshabilita el botón."""
        logging.debug("Reseteando CorrectionPanel.")
        if self.correct_state_combo:
            self.correct_state_combo.set('') # Limpiar valor mostrado y variable
        if self.log_button:
            self.log_button.config(state="disabled")

    def show(self):
        """Muestra el panel en la grid."""
        logging.debug("Mostrando CorrectionPanel.")
        # Asegurarse de que está en la posición correcta de la grid (debajo de resultados)
        self.grid(row=2, column=0, sticky="nsew", padx=0, pady=(0, 10))
        # Es posible que necesitemos repoblar o verificar la población aquí
        # self.populate_combobox(list(self.main_app.recognizer.templates.keys()))
        self.update_idletasks() # Forzar actualización de la UI

    def hide(self):
        """Oculta el panel."""
        logging.debug("Ocultando CorrectionPanel.")
        self.grid_remove()
        self.reset() # Limpiar selección al ocultar

    def _on_state_selected_event(self, event=None):
        """
        Callback cuando se selecciona un estado en el Combobox.
        Habilita el botón de log y notifica a la aplicación principal.
        """
        selected_state = self.get_selected_state()
        if selected_state:
            logging.debug(f"Estado seleccionado en CorrectionPanel: {selected_state}")
            if self.log_button:
                self.log_button.config(state="normal")
            # Notificar a la aplicación principal para que actualice la preview, etc.
            # La aplicación principal debe tener un método como 'on_correct_state_selected'
            if hasattr(self.main_app, 'on_correct_state_selected'):
                self.main_app.on_correct_state_selected(selected_state)
            else:
                logging.warning("El método 'on_correct_state_selected' no existe en main_app.")
        else:
            # Esto no debería ocurrir con 'readonly', pero por si acaso
            if self.log_button:
                self.log_button.config(state="disabled")

# --- END OF FILE src/panels/correction_panel.py ---