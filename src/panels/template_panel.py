# --- START OF FILE src/panels/template_panel.py ---
import re
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import logging
import os # Para basename en errores

class TemplatePanel(ttk.LabelFrame):
    """
    Panel para capturar nuevas plantillas y gestionar plantillas/imágenes existentes.
    """
    def __init__(self, master, main_app, **kwargs):
        kwargs['text'] = kwargs.get('text', "Gestión Plantillas")
        super().__init__(master, **kwargs)
        self.main_app = main_app # Referencia a la clase principal
        logging.debug("Inicializando TemplatePanel.")

        # Variables de control Tkinter
        self.capture_type_var = tk.StringVar(value="monitor")
        self.monitor_var = tk.IntVar(value=1)
        self.new_template_name_var = tk.StringVar()
        self.template_name_var = tk.StringVar()

        # Referencias a widgets importantes
        self.monitor_spinbox = None
        self.new_template_entry = None
        self.save_template_button = None
        self.template_name_combobox = None
        self.img_listbox = None
        self.use_image_button = None
        self.delete_image_button = None
        self.rename_template_button = None
        self.delete_template_button = None

        self._create_widgets()

    def _create_widgets(self):
        """Crea todos los widgets dentro del panel."""
        logging.debug("Creando widgets para TemplatePanel.")
        self.grid_columnconfigure(0, weight=1) # Permitir expansión horizontal

        # --- Sección Captura ---
        capture_frame = ttk.LabelFrame(self, text="Capturar Nueva Plantilla", padding=(10, 5))
        capture_frame.grid(row=0, column=0, padx=5, pady=(0, 10), sticky="ew")
        capture_frame.columnconfigure(1, weight=1) # Expandir entry

        # Opciones captura (Monitor/Región/Monitor Spinbox)
        capture_options_frame = ttk.Frame(capture_frame)
        capture_options_frame.grid(row=0, column=0, columnspan=3, sticky="ew", padx=5, pady=2)
        ttk.Radiobutton(capture_options_frame, text="Monitor", variable=self.capture_type_var, value="monitor").pack(side="left", padx=(0, 5))
        ttk.Radiobutton(capture_options_frame, text="Región", variable=self.capture_type_var, value="region").pack(side="left", padx=(0, 10))
        ttk.Label(capture_options_frame, text="Monitor #:").pack(side="left", padx=(5, 2))
        num_monitors = len(self.main_app.monitors_info) - 1 if len(self.main_app.monitors_info) > 1 else 1
        self.monitor_spinbox = ttk.Spinbox(capture_options_frame, from_=1, to=max(1, num_monitors), textvariable=self.monitor_var, width=4, wrap=True)
        self.monitor_spinbox.pack(side="left")
        # Botón Capturar
        ttk.Button(capture_options_frame, text="Capturar", style="Accent.TButton", # Estilo opcional
                   command=self._on_capture_click).pack(side="right", padx=(10, 0))

        # Nombre Nueva Plantilla
        ttk.Label(capture_frame, text="Nombre Plantilla:").grid(row=1, column=0, sticky="w", padx=5, pady=(5,0))
        self.new_template_entry = ttk.Entry(capture_frame, textvariable=self.new_template_name_var)
        self.new_template_entry.grid(row=1, column=1, sticky="ew", padx=5, pady=(5,0))
        self.new_template_entry.bind("<Return>", lambda e: self._on_save_template_click())
        # Botón Guardar
        self.save_template_button = ttk.Button(capture_frame, text="Guardar Nueva / Añadir Imagen",
                                               command=self._on_save_template_click)
        self.save_template_button.grid(row=1, column=2, sticky="e", padx=5, pady=(5,0))


        # --- Sección Gestión Existentes ---
        manage_frame = ttk.LabelFrame(self, text="Gestión Existentes", padding=(10, 5))
        manage_frame.grid(row=1, column=0, padx=5, pady=10, sticky="nsew")
        self.grid_rowconfigure(1, weight=1) # Permitir que esta sección crezca
        manage_frame.columnconfigure(1, weight=1) # Permitir que combobox/listbox se expandan
        manage_frame.rowconfigure(2, weight=1) # Permitir que listbox se expanda verticalmente

        # Selección de Plantilla
        ttk.Label(manage_frame, text="Plantilla:").grid(row=0, column=0, padx=(0, 5), pady=5, sticky="w")
        self.template_name_combobox = ttk.Combobox(manage_frame, textvariable=self.template_name_var, width=35, state="readonly")
        self.template_name_combobox.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        self.template_name_combobox.bind("<<ComboboxSelected>>", lambda e: self.main_app.handle_template_selection(self.template_name_var.get()))
        ttk.Button(manage_frame, text="Refrescar", command=self.main_app.load_mappings_from_json).grid(row=0, column=2, padx=(10, 5), pady=5)

        # Botones Acción Plantilla
        tpl_action_frame = ttk.Frame(manage_frame)
        tpl_action_frame.grid(row=1, column=0, columnspan=3, pady=(5,5), sticky="ew")
        self.rename_template_button = ttk.Button(tpl_action_frame, text="Renombrar", command=self._on_rename_template_click, state="disabled")
        self.rename_template_button.pack(side="left", padx=(0,5), expand=True, fill='x')
        self.delete_template_button = ttk.Button(tpl_action_frame, text="Eliminar Plantilla", command=self._on_delete_template_click, state="disabled")
        self.delete_template_button.pack(side="left", padx=(0,0), expand=True, fill='x')


        # Lista de Imágenes y sus botones
        ttk.Label(manage_frame, text="Imágenes:").grid(row=2, column=0, padx=(0, 5), pady=(5,0), sticky="nw")
        img_list_frame = ttk.Frame(manage_frame)
        img_list_frame.grid(row=2, column=1, padx=5, pady=(5,0), sticky="nsew")
        img_list_frame.rowconfigure(0, weight=1)
        img_list_frame.columnconfigure(0, weight=1)

        img_scrollbar = ttk.Scrollbar(img_list_frame, orient=tk.VERTICAL)
        self.img_listbox = tk.Listbox(img_list_frame, yscrollcommand=img_scrollbar.set, height=5, width=30, exportselection=False)
        img_scrollbar.config(command=self.img_listbox.yview)
        self.img_listbox.grid(row=0, column=0, sticky="nsew")
        img_scrollbar.grid(row=0, column=1, sticky="ns")
        self.img_listbox.bind("<<ListboxSelect>>", lambda e: self.main_app.handle_image_selection(self._get_selected_image_filename()))

        img_action_frame = ttk.Frame(manage_frame)
        img_action_frame.grid(row=2, column=2, padx=(10, 5), pady=(5,0), sticky="ns")
        self.use_image_button = ttk.Button(img_action_frame, text="Usar", command=lambda: self.main_app.handle_image_selection(self._get_selected_image_filename()), state="disabled")
        self.use_image_button.pack(pady=2, fill="x")
        self.delete_image_button = ttk.Button(img_action_frame, text="Eliminar", command=self._on_delete_image_click, state="disabled")
        self.delete_image_button.pack(pady=(10,2), fill="x")


        logging.debug("Widgets de TemplatePanel creados.")

    # --- Métodos para interactuar con la GUI ---
    def reset_panel(self):
        """Limpia todos los campos y selecciones del panel."""
        self.capture_type_var.set("monitor")
        # self.monitor_var.set(1) # No resetear monitor seleccionado
        self.new_template_name_var.set("")
        self.template_name_var.set("")
        self.img_listbox.delete(0, tk.END)
        self.update_action_button_states() # Deshabilitar botones

    def refresh_template_list(self, template_mapping):
        """Actualiza el Combobox de plantillas."""
        logging.debug("Refrescando lista de plantillas en Combobox.")
        template_names = sorted(list(template_mapping.keys()))
        self.template_name_combobox['values'] = template_names
        # No limpiar selección aquí, se hace en clear_all_selections o load_mappings

    def populate_image_listbox(self, image_filenames):
        """Llena el Listbox con nombres de archivo de imagen."""
        logging.debug(f"Poblando Listbox de imágenes con: {image_filenames}")
        self.img_listbox.delete(0, tk.END)
        if image_filenames:
            for filename in image_filenames:
                self.img_listbox.insert(tk.END, filename)
            self.img_listbox.selection_set(0) # Seleccionar el primero por defecto
        self.update_action_button_states() # Habilitar/deshabilitar botones imagen

    def _get_selected_image_filename(self):
        """Devuelve el nombre de archivo seleccionado en el Listbox o None."""
        selected_indices = self.img_listbox.curselection()
        if selected_indices:
            return self.img_listbox.get(selected_indices[0])
        return None

    def update_action_button_states(self):
        """Habilita/Deshabilita botones según el estado actual."""
        # Botón Guardar Nueva/Añadir: Habilitado si hay imagen capturada y nombre escrito
        can_save_new = bool(self.main_app.current_image_numpy is not None and self.new_template_name_var.get().strip())
        self.save_template_button.config(state="normal" if can_save_new else "disabled")

        # Botones de gestión de Plantilla: Habilitados si hay una plantilla seleccionada
        can_manage_template = bool(self.main_app.current_template_name)
        tpl_state = "normal" if can_manage_template else "disabled"
        self.rename_template_button.config(state=tpl_state)
        self.delete_template_button.config(state=tpl_state)

        # Botones de gestión de Imagen: Habilitados si hay plantilla Y imagen seleccionada en listbox
        can_manage_image = can_manage_template and bool(self.img_listbox.curselection())
        img_state = "normal" if can_manage_image else "disabled"
        self.use_image_button.config(state=img_state)
        self.delete_image_button.config(state=img_state)

    # --- Callbacks de Botones (Llaman a main_app) ---
    def _on_capture_click(self):
        capture_type = self.capture_type_var.get()
        try:
            monitor_idx = self.monitor_var.get()
            self.main_app.capture_template_action(capture_type, monitor_idx)
        except tk.TclError:
            messagebox.showerror("Error", "Número de monitor inválido.", parent=self)

    def _on_save_template_click(self):
        template_name = self.new_template_name_var.get().strip()
        if not template_name:
             messagebox.showerror("Error", "Introduzca nombre para la plantilla.", parent=self)
             return
        # Validación extra (opcional pero recomendada)
        if not re.match(r'^[a-zA-Z0-9_.-]+$', template_name):
            messagebox.showerror("Error", "Nombre inválido (solo letras, números, _, ., -).", parent=self)
            return
        if self.main_app.current_image_numpy is None:
             messagebox.showerror("Error", "Primero capture una imagen.", parent=self)
             return
        self.main_app.save_template_action(template_name)

    def _on_rename_template_click(self):
        old_name = self.template_name_var.get()
        if not old_name: return # Botón debería estar deshabilitado
        new_name = simpledialog.askstring("Renombrar Plantilla",
                                          f"Nuevo nombre para '{old_name}':",
                                          initialvalue=old_name, parent=self)
        if new_name is not None: # Si no se canceló
             new_name = new_name.strip()
             if not new_name: messagebox.showerror("Inválido", "Nombre vacío.", parent=self); return
             if not re.match(r'^[a-zA-Z0-9_.-]+$', new_name): messagebox.showerror("Inválido", "Nombre inválido.", parent=self); return
             if new_name == old_name: self.main_app.status_message("Nombre sin cambios."); return
             # Verificar si el nuevo nombre ya existe antes de llamar a la acción
             if new_name in self.main_app.template_names_mapping:
                  messagebox.showerror("Conflicto", f"Plantilla '{new_name}' ya existe.", parent=self); return
             self.main_app.rename_template_action(old_name, new_name)

    def _on_delete_template_click(self):
        template_name = self.template_name_var.get()
        if not template_name: return # Debería estar deshabilitado
        self.main_app.delete_template_action(template_name)

    def _on_delete_image_click(self):
        template_name = self.template_name_var.get()
        image_filename = self._get_selected_image_filename()
        if not template_name or not image_filename: return # Debería estar deshabilitado
        self.main_app.delete_image_action(template_name, image_filename)


# --- END OF FILE src/panels/template_panel.py ---