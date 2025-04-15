# --- START OF FILE src/panels/ocr_definition_panel.py ---

import tkinter as tk
from tkinter import ttk, font as tkFont, messagebox  # Importar tkFont aquí también
import logging

class OcrDefinitionPanel(ttk.LabelFrame):
    """
    Panel para definir, visualizar y gestionar las zonas OCR y sus textos
    esperados asociados a una plantilla en el Template Manager.
    """
    def __init__(self, master, main_app, **kwargs):
        """
        Inicializa el Panel de Definición OCR.

        Args:
            master: El widget padre (frame columna derecha).
            main_app: Referencia a la instancia principal de TemplateManagerGUI.
            **kwargs: Argumentos adicionales para ttk.LabelFrame.
        """
        kwargs['text'] = kwargs.get('text', "Configuración OCR")
        super().__init__(master, **kwargs)
        self.main_app = main_app
        logging.debug("Inicializando OcrDefinitionPanel.")

        # --- Variables y Referencias ---
        self.expected_text_var = tk.StringVar() # Para el Entry de NUEVA región
        self.ocr_tree = None
        # Referencias a botones para control de estado
        self.mark_region_button = None
        self.edit_text_button = None
        self.redraw_region_button = None
        self.delete_region_button = None
        self.clear_session_button = None
        self.save_changes_button = None

        # Fuente para Treeview (puede heredar o definirse)
        self.tree_font = tkFont.Font(family=self.main_app.default_font['family'],
                                      size=self.main_app.default_font['size'])


        # --- Widgets ---
        self._create_widgets()
        self.reset_panel() # Estado inicial limpio

    def _create_widgets(self):
        """Crea los widgets del panel: botones acción, entry, treeview, etc."""
        logging.debug("Creando widgets para OcrDefinitionPanel.")
        self.grid_columnconfigure(0, weight=1) # Permitir expansión horizontal
        self.grid_rowconfigure(4, weight=1) # Permitir que Treeview se expanda

        # --- Frame para botones de acción principales ---
        top_action_frame = ttk.Frame(self)
        top_action_frame.grid(row=0, column=0, pady=(0,5), sticky="ew")
        top_action_frame.columnconfigure(0, weight=1)

        self.mark_region_button = ttk.Button(top_action_frame, text="Marcar Nueva Región OCR",
                                             command=self._on_mark_region_click, state="disabled")
        self.mark_region_button.grid(row=0, column=0, pady=2)

        # --- Entrada Texto Esperado (para NUEVAS regiones) ---
        expected_text_frame = ttk.Frame(self)
        expected_text_frame.grid(row=1, column=0, pady=(0,2), sticky="ew")
        expected_text_frame.grid_columnconfigure(0, weight=1)
        ttk.Label(expected_text_frame, text="Texto Esperado (NUEVA región, separa con '|'):").pack(anchor="w", padx=5)
        expected_text_entry = ttk.Entry(expected_text_frame, textvariable=self.expected_text_var)
        expected_text_entry.pack(fill="x", padx=5, pady=(0, 5))
        expected_text_entry.bind("<Return>", lambda e: self._on_mark_region_click()) # Enter en entry = marcar

        # --- Label contador de zonas ---
        self.region_label = ttk.Label(self, text="Zonas OCR: 0", anchor="center")
        self.region_label.grid(row=2, column=0, pady=3, sticky="ew")

        # --- Treeview para mostrar regiones y textos ---
        tree_label = ttk.Label(self, text="Zonas Definidas (Doble-clic p/Editar Texto):")
        tree_label.grid(row=3, column=0, padx=5, pady=(5, 0), sticky="w")

        tree_frame = ttk.Frame(self)
        tree_frame.grid(row=4, column=0, padx=5, pady=5, sticky="nsew")
        tree_frame.grid_rowconfigure(0, weight=1); tree_frame.grid_columnconfigure(0, weight=1)

        # Ajustar altura fila Treeview dinámicamente
        row_height = self.tree_font.metrics('linespace') + 6
        style_name = f"{self}.Treeview" # Nombre único para el estilo
        ttk.Style().configure(style_name, rowheight=row_height, font=self.tree_font)

        self.ocr_tree = ttk.Treeview(tree_frame, columns=("#", "Textos"), show="headings",
                                     height=6, selectmode="extended", style=style_name) # Aplicar estilo
        self.ocr_tree.heading("#", text="#", anchor="center"); self.ocr_tree.column("#", width=40, anchor="center", stretch=tk.NO)
        self.ocr_tree.heading("Textos", text="Texto(s) Esperado(s)"); self.ocr_tree.column("Textos", width=200, stretch=tk.YES)
        self.ocr_tree.grid(row=0, column=0, sticky="nsew")

        ocr_scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.ocr_tree.yview); ocr_scrollbar.grid(row=0, column=1, sticky="ns")
        self.ocr_tree['yscrollcommand'] = ocr_scrollbar.set

        self.ocr_tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.ocr_tree.bind("<Double-1>", self._on_tree_double_click)

        # --- Frame para botones de edición/eliminación ---
        edit_action_frame = ttk.Frame(self)
        edit_action_frame.grid(row=5, column=0, pady=(5, 0), sticky="ew")
        edit_action_frame.columnconfigure(0, weight=1); edit_action_frame.columnconfigure(1, weight=1); edit_action_frame.columnconfigure(2, weight=1)

        self.edit_text_button = ttk.Button(edit_action_frame, text="Editar Texto", command=self._on_edit_text_click, state="disabled"); self.edit_text_button.grid(row=0, column=0, padx=2, pady=2, sticky="ew")
        self.redraw_region_button = ttk.Button(edit_action_frame, text="Redibujar Región", command=self._on_redraw_click, state="disabled"); self.redraw_region_button.grid(row=0, column=1, padx=2, pady=2, sticky="ew")
        self.delete_region_button = ttk.Button(edit_action_frame, text="Eliminar Región(es)", command=self._on_delete_click, state="disabled"); self.delete_region_button.grid(row=0, column=2, padx=2, pady=2, sticky="ew")

        # --- Frame para botones generales ---
        general_action_frame = ttk.Frame(self)
        general_action_frame.grid(row=6, column=0, pady=(10, 0), sticky="ew")
        general_action_frame.columnconfigure(0, weight=1); general_action_frame.columnconfigure(1, weight=1)

        self.clear_session_button = ttk.Button(general_action_frame, text="Limpiar Sesión", command=self._on_clear_session_click, state="disabled"); self.clear_session_button.pack(side="left", padx=(5,5), pady=5, fill="x", expand=True)
        self.save_changes_button = ttk.Button(general_action_frame, text="Guardar Zonas OCR", command=self._on_save_click, state="disabled"); self.save_changes_button.pack(side="left", padx=(5,5), pady=5, fill="x", expand=True)

        logging.debug("Widgets de OcrDefinitionPanel creados.")

    def populate_treeview(self, ocr_regions_data):
        """Llena el Treeview con los datos de las regiones OCR."""
        # Guardar selección actual para intentar restaurarla
        selected_iids = self.ocr_tree.selection()
        # Limpiar Treeview
        for item in self.ocr_tree.get_children():
            self.ocr_tree.delete(item)

        # Insertar nuevos datos
        for i, region_data in enumerate(ocr_regions_data):
            region_index = i + 1 # Índice 1-based para mostrar
            expected_texts = region_data.get('expected_text', [])
            text_display = "|".join(expected_texts) if expected_texts else ""
            iid = str(region_index) # Usar índice+1 como ID único
            self.ocr_tree.insert("", tk.END, iid=iid, values=(region_index, text_display))

        # Intentar restaurar selección
        new_selection = [iid for iid in selected_iids if self.ocr_tree.exists(iid)]
        if new_selection:
            self.ocr_tree.selection_set(new_selection)
            # Asegurarse que el último seleccionado esté visible
            # self.ocr_tree.see(new_selection[-1]) # Podría ser útil
        else:
             self.ocr_tree.selection_set([]) # Limpiar si no hay coincidencias

        # Actualizar contador y botones
        self.update_region_label(len(ocr_regions_data))
        self._update_action_buttons_state() # Habilitar/deshabilitar botones


    def update_region_label(self, count):
        """Actualiza la etiqueta que muestra el número de zonas."""
        self.region_label.config(text=f"Zonas OCR: {count} definida(s)")

    def get_selected_indices(self):
        """Devuelve una lista de índices (0-based) de las filas seleccionadas."""
        selected_items = self.ocr_tree.selection()
        indices = []
        for item_iid in selected_items:
            try:
                # El IID es el índice+1
                list_index = int(item_iid) - 1
                # Validar índice contra la longitud de datos que debería tener main_app
                # Es más seguro si main_app pasa la longitud o si la guardamos aquí
                # Por ahora, asumimos que el índice es válido si existe en el Treeview
                indices.append(list_index)
            except (ValueError, TypeError):
                logging.warning(f"IID de Treeview inválido al obtener índice: {item_iid}")
        return sorted(indices)

    def reset_panel(self):
        """Resetea el panel a su estado inicial."""
        self.expected_text_var.set("")
        self.populate_treeview([]) # Limpia el treeview
        # El contador y los botones se actualizan en populate_treeview

    def _update_action_buttons_state(self):
        """Habilita/deshabilita botones según el estado y selección."""
        selected_indices = self.get_selected_indices()
        num_selected = len(selected_indices)
        # Depende del estado de la app principal (imagen cargada, plantilla seleccionada)
        has_image = bool(self.main_app.current_image_numpy is not None)
        has_template = bool(self.main_app.current_template_name)
        has_regions_in_session = bool(self.main_app.current_ocr_regions)

        # Marcar nueva: necesita imagen
        self.mark_region_button.config(state="normal" if has_image else "disabled")

        # Editar/Redibujar: necesita imagen Y selección ÚNICA
        can_edit_single = has_image and num_selected == 1
        edit_state = "normal" if can_edit_single else "disabled"
        self.edit_text_button.config(state=edit_state)
        self.redraw_region_button.config(state=edit_state)

        # Eliminar: necesita selección (una o más)
        delete_state = "normal" if num_selected > 0 else "disabled"
        self.delete_region_button.config(state=delete_state)

        # Limpiar sesión: necesita regiones en la sesión actual
        clear_state = "normal" if has_regions_in_session else "disabled"
        self.clear_session_button.config(state=clear_state)

        # Guardar cambios: necesita plantilla seleccionada (se guarda asociado a plantilla)
        save_state = "normal" if has_template else "disabled"
        self.save_changes_button.config(state=save_state)


    # --- Callbacks de Eventos (Notifican a main_app) ---
    def _on_tree_select(self, event=None):
        """Al seleccionar en Treeview, actualiza botones y notifica a main_app."""
        selected_indices = self.get_selected_indices()
        self._update_action_buttons_state()
        # Notificar a main_app para que actualice el resaltado en PreviewPanel
        if hasattr(self.main_app, 'handle_ocr_selection_change'):
            self.main_app.handle_ocr_selection_change(selected_indices)

    def _on_tree_double_click(self, event=None):
        """Al hacer doble clic, intenta editar el texto."""
        # Solo actuar si hay exactamente una fila seleccionada
        if len(self.ocr_tree.selection()) == 1:
            self._on_edit_text_click()

    def _on_mark_region_click(self):
        """Obtiene texto esperado y llama a la acción de marcar en main_app."""
        expected_text_str = self.expected_text_var.get().strip()
        expected_texts = [txt.strip() for txt in expected_text_str.split('|') if txt.strip()]
        # Limpiar el entry DESPUÉS de obtener el valor
        self.expected_text_var.set("")
        # Llamar a la acción principal
        if hasattr(self.main_app, 'mark_ocr_action'):
            self.main_app.mark_ocr_action(expected_texts)

    def _on_edit_text_click(self):
        """Llama a la acción de editar texto en main_app."""
        selected_indices = self.get_selected_indices()
        if len(selected_indices) == 1:
            if hasattr(self.main_app, 'edit_ocr_text_action_request'): # Usar un nombre distinto para la solicitud
                self.main_app.edit_ocr_text_action_request(selected_indices[0])
        else:
             messagebox.showwarning("Selección", "Seleccione UNA región para editar texto.", parent=self)


    def _on_redraw_click(self):
        """Llama a la acción de redibujar en main_app."""
        selected_indices = self.get_selected_indices()
        if len(selected_indices) == 1:
            if hasattr(self.main_app, 'redraw_ocr_action'):
                self.main_app.redraw_ocr_action(selected_indices[0])
        else:
            messagebox.showwarning("Selección", "Seleccione UNA región para redibujar.", parent=self)

    def _on_delete_click(self):
        """Llama a la acción de eliminar en main_app."""
        selected_indices = self.get_selected_indices()
        if selected_indices:
            if hasattr(self.main_app, 'delete_ocr_action'):
                self.main_app.delete_ocr_action(selected_indices)
        else:
             messagebox.showwarning("Selección", "Seleccione región(es) a eliminar.", parent=self)

    def _on_clear_session_click(self):
        """Llama a la acción de limpiar sesión en main_app (que pedirá confirmación)."""
        if hasattr(self.main_app, 'clear_ocr_session_action'):
             self.main_app.clear_ocr_session_action()

    def _on_save_click(self):
        """Llama a la acción de guardar en main_app."""
        if hasattr(self.main_app, 'save_ocr_action'):
             self.main_app.save_ocr_action()


# --- END OF FILE src/panels/ocr_definition_panel.py ---