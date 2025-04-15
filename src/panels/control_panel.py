# --- START OF FILE src/panels/control_panel.py ---

import tkinter as tk
from tkinter import ttk
import logging

class ControlPanel(ttk.LabelFrame):
    """
    Panel que contiene los botones de control principales de la aplicación.
    Permite iniciar el reconocimiento, recargar datos y abrir el gestor de plantillas.
    """
    def __init__(self, master, main_app, **kwargs):
        """
        Inicializa el Panel de Control.

        Args:
            master: El widget padre (normalmente el frame de la columna izquierda).
            main_app: Una referencia a la instancia principal de ScreenTesterGUI
                      para poder llamar a sus métodos coordinadores.
            **kwargs: Argumentos adicionales para ttk.LabelFrame.
        """
        # Aseguramos que el texto del LabelFrame sea "Control"
        kwargs['text'] = kwargs.get('text', "Control")
        super().__init__(master, **kwargs)
        self.main_app = main_app
        logging.debug("Inicializando ControlPanel.")

        # Guardar referencias a los botones para poder habilitarlos/deshabilitarlos
        self.recognize_button = None
        self.reload_button = None
        self.manager_button = None

        self._create_widgets()

    def _create_widgets(self):
        """
        Crea los botones dentro del panel.
        """
        logging.debug("Creando widgets para ControlPanel.")

        # --- Botón Reconocer Pantalla ---
        self.recognize_button = ttk.Button(
            self,
            text="Reconocer Pantalla",
            command=self.main_app.run_test # Llama al método en la app principal
        )
        # Usamos pack para una disposición vertical simple.
        # fill='x' hace que el botón se expanda horizontalmente.
        # pady añade un pequeño espacio vertical entre botones.
        self.recognize_button.pack(fill='x', pady=(0, 5), padx=5)

        # --- Botón Recargar Datos ---
        self.reload_button = ttk.Button(
            self,
            text="Recargar Datos Config.",
            command=self.main_app.reload_recognizer_data # Llama al método en la app principal
        )
        self.reload_button.pack(fill='x', pady=5, padx=5)

        # --- Botón Abrir Gestor de Plantillas ---
        self.manager_button = ttk.Button(
            self,
            text="Abrir Gestor Plantillas",
            command=self.main_app.launch_template_manager # Llama al método en la app principal
        )
        self.manager_button.pack(fill='x', pady=(5, 0), padx=5) # pady diferente para el último

        logging.debug("Widgets de ControlPanel creados.")

    def enable_buttons(self):
        """Habilita todos los botones del panel."""
        if self.recognize_button:
            self.recognize_button.config(state=tk.NORMAL)
        if self.reload_button:
            self.reload_button.config(state=tk.NORMAL)
        if self.manager_button:
             self.manager_button.config(state=tk.NORMAL)
        logging.debug("Botones de ControlPanel habilitados.")

    def disable_buttons(self):
        """Deshabilita todos los botones del panel (útil durante operaciones largas)."""
        if self.recognize_button:
            self.recognize_button.config(state=tk.DISABLED)
        if self.reload_button:
            self.reload_button.config(state=tk.DISABLED)
        # Usualmente no deshabilitamos el botón de abrir el gestor, pero se puede añadir si se desea
        # if self.manager_button:
        #    self.manager_button.config(state=tk.DISABLED)
        logging.debug("Botones de ControlPanel deshabilitados (excepto quizás gestor).")

# --- END OF FILE src/panels/control_panel.py ---