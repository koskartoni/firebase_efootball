# --- START OF FILE src/panels/ocr_panel.py ---

import tkinter as tk
from tkinter import ttk
import logging
import json # Para formatear coordenadas en el treeview

class OcrPanel(ttk.LabelFrame):
    """
    Panel para mostrar detalles de resultados OCR y permitir la
    actualización del archivo ocr_regions.json.
    """
    def __init__(self, master, main_app, **kwargs):
        """
        Inicializa el Panel de Detalles OCR.

        Args:
            master: El widget padre (normalmente el frame de la columna izquierda).
            main_app: Una referencia a la instancia principal de ScreenTesterGUI.
            **kwargs: Argumentos adicionales para ttk.LabelFrame.
        """
        kwargs['text'] = kwargs.get('text', "Detalles OCR")
        super().__init__(master, **kwargs)
        self.main_app = main_app
        logging.debug("Inicializando OcrPanel.")

        # --- Variables y Referencias ---
        self.edited_text_var = tk.StringVar()
        self.ocr_tree = None
        self.edit_entry = None
        self.confirm_extracted_button = None
        self.save_edited_button = None
        # Guardar los datos actuales para refrescar la vista si es necesario
        self._current_ocr_results = None

        # --- Widgets ---
        self._create_widgets()
        self.hide() # Oculto por defecto

    def _create_widgets(self):
        """Crea el Treeview, Entry y botones para la gestión OCR."""
        logging.debug("Creando widgets para OcrPanel.")

        # --- Configuración del Grid ---
        self.columnconfigure(0, weight=1) # Permitir que Treeview y Entry se expandan
        self.rowconfigure(0, weight=1)    # Permitir que Treeview se expanda verticalmente

        # --- Treeview para Resultados OCR ---
        tree_frame = ttk.Frame(self) # Frame para contener Treeview y Scrollbar
        tree_frame.grid(row=0, column=0, columnspan=2, sticky="nsew", padx=5, pady=5)
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)

        # Definir columnas
        columns = ("region_idx", "coords", "expected", "extracted", "match")
        self.ocr_tree = ttk.Treeview(
            tree_frame,
            columns=columns,
            show="headings", # No mostrar la columna fantasma #0
            selectmode="extended" # Permitir seleccionar múltiples filas
        )

        # Definir cabeceras y ancho inicial
        self.ocr_tree.heading("region_idx", text="Idx", anchor=tk.W)
        self.ocr_tree.column("region_idx", width=30, stretch=tk.NO, anchor=tk.W)

        self.ocr_tree.heading("coords", text="Coords (L,T,W,H)", anchor=tk.W)
        self.ocr_tree.column("coords", width=120, stretch=tk.NO, anchor=tk.W)

        self.ocr_tree.heading("expected", text="Texto Esperado", anchor=tk.W)
        self.ocr_tree.column("expected", width=150, anchor=tk.W) # Permitir stretch

        self.ocr_tree.heading("extracted", text="Texto Extraído", anchor=tk.W)
        self.ocr_tree.column("extracted", width=150, anchor=tk.W) # Permitir stretch

        self.ocr_tree.heading("match", text="Match?", anchor=tk.CENTER)
        self.ocr_tree.column("match", width=50, stretch=tk.NO, anchor=tk.CENTER)

        self.ocr_tree.grid(row=0, column=0, sticky="nsew")

        # Scrollbar para el Treeview
        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.ocr_tree.yview)
        self.ocr_tree.configure(yscroll=scrollbar.set)
        scrollbar.grid(row=0, column=1, sticky="ns")

        # Binding para la selección de filas
        self.ocr_tree.bind("<<TreeviewSelect>>", self._on_tree_select)

        # --- Sección de Edición ---
        edit_frame = ttk.Frame(self)
        edit_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=5, pady=(5, 0))
        edit_frame.columnconfigure(1, weight=1) # Permitir que Entry se expanda

        edit_label = ttk.Label(edit_frame, text="Editar Esperado:")
        edit_label.grid(row=0, column=0, padx=(0, 5), pady=5, sticky="w")

        self.edit_entry = ttk.Entry(edit_frame, textvariable=self.edited_text_var, state="disabled")
        self.edit_entry.grid(row=0, column=1, sticky="ew", pady=5)
        # Info sobre cómo usar el pipe '|' para múltiples textos
        info_label = ttk.Label(edit_frame, text="Usar '|' para separar múltiples textos esperados.", font=self.main_app.status_font)
        info_label.grid(row=1, column=0, columnspan=2, sticky="w", padx=5, pady=(0,5))


        # --- Botones de Acción OCR ---
        button_frame = ttk.Frame(self)
        button_frame.grid(row=2, column=0, columnspan=2, sticky="ew", padx=5, pady=5)
        button_frame.columnconfigure(0, weight=1)
        button_frame.columnconfigure(1, weight=1)

        self.confirm_extracted_button = ttk.Button(
            button_frame,
            text="Confirmar Extraído como Esperado",
            command=self._confirm_extracted_action, # Llama a método interno que llama a main_app
            state="disabled"
        )
        self.confirm_extracted_button.grid(row=0, column=0, padx=(0, 2), sticky="ew")

        self.save_edited_button = ttk.Button(
            button_frame,
            text="Guardar Texto Editado",
            command=self._save_edited_action, # Llama a método interno que llama a main_app
            state="disabled"
        )
        self.save_edited_button.grid(row=0, column=1, padx=(2, 0), sticky="ew")

        logging.debug("Widgets de OcrPanel creados.")

    def populate_ocr_tree(self, ocr_results_dict):
        """
        Limpia y llena el Treeview con los resultados OCR.

        Args:
            ocr_results_dict (dict): El sub-diccionario 'ocr_results' del
                                     resultado del reconocimiento.
                                     Formato: { region_idx: {details} }
                                     Puede ser None.
        """
        logging.debug(f"Poblando OcrPanel Treeview con: {ocr_results_dict}")
        # Limpiar vista anterior
        for item in self.ocr_tree.get_children():
            self.ocr_tree.delete(item)
        self.clear_selection_and_entry() # Limpiar entry y deshabilitar botones

        self._current_ocr_results = ocr_results_dict # Guardar referencia

        if not ocr_results_dict:
            logging.debug("No hay datos OCR para mostrar.")
            # Podríamos insertar un mensaje en el Treeview
            # self.ocr_tree.insert("", tk.END, values=("", "", "No hay datos OCR", "", ""))
            return

        # Iterar sobre los resultados y añadirlos al Treeview
        for region_idx, details in ocr_results_dict.items():
            coords_dict = details.get('region', {})
            # Formatear coordenadas para visualización
            coords_str = ""
            if isinstance(coords_dict, dict):
                coords_str = f"{coords_dict.get('left','?')},{coords_dict.get('top','?')},{coords_dict.get('width','?')},{coords_dict.get('height','?')}"
            else:
                coords_str = str(coords_dict) # Mostrar lo que sea que haya

            expected_list = details.get('expected', [])
            # Unir lista de esperados con '|' para visualización
            expected_str = " | ".join(str(e) for e in expected_list if isinstance(e, str))

            extracted_str = details.get('text', '')
            match_bool = details.get('match_expected', False)
            match_str = "Sí" if match_bool else "No"

            # Insertar fila en el Treeview
            # Usar region_idx como iid (identificador único de item) puede ser útil
            try:
                self.ocr_tree.insert(
                    "", tk.END, iid=str(region_idx),
                    values=(
                        region_idx,
                        coords_str,
                        expected_str,
                        extracted_str,
                        match_str
                    )
                )
            except Exception as e:
                logging.error(f"Error insertando fila OCR en Treeview para idx {region_idx}: {e}. Datos: {details}")


    def _on_tree_select(self, event=None):
        """Callback cuando se selecciona una fila en el Treeview."""
        selected_items = self.ocr_tree.selection()

        if not selected_items:
            self.clear_selection_and_entry()
            return

        logging.debug(f"Selección en Treeview OCR: {selected_items}")

        # --- Lógica para habilitar botones ---
        # Habilitar siempre si hay selección
        if self.confirm_extracted_button: self.confirm_extracted_button.config(state="normal")
        if self.save_edited_button: self.save_edited_button.config(state="normal")
        if self.edit_entry: self.edit_entry.config(state="normal")

        # --- Lógica para poblar el Entry de edición ---
        # Si se selecciona UNA SOLA fila, llenar el Entry con su texto esperado
        if len(selected_items) == 1:
            item_id = selected_items[0]
            item_data = self.ocr_tree.item(item_id)
            if item_data and 'values' in item_data and len(item_data['values']) > 2:
                 expected_text_display = item_data['values'][2] # Índice 2 es 'Texto Esperado'
                 self.edited_text_var.set(expected_text_display)
                 self.edit_entry.icursor(tk.END) # Poner cursor al final
                 self.edit_entry.focus() # Poner foco en el entry
            else:
                 self.edited_text_var.set("") # Limpiar si hay error
        else:
            # Si hay MÚLTIPLES filas seleccionadas, limpiar el Entry
            self.edited_text_var.set("")
            if self.edit_entry: self.edit_entry.config(state="disabled") # Deshabilitar entry con múltiple selección

    def get_selected_region_details(self):
        """
        Devuelve una lista de diccionarios con detalles de las filas seleccionadas.
        Cada diccionario contiene: 'index', 'coordinates', 'expected_text', 'extracted_text'.
        """
        selected_items = self.ocr_tree.selection()
        details_list = []
        if not selected_items:
            return details_list

        for item_id in selected_items:
            item_data = self.ocr_tree.item(item_id)
            if item_data and 'values' in item_data:
                values = item_data['values']
                # Recuperar datos de las columnas
                try:
                    # El iid es el índice original que guardamos
                    region_idx = int(item_id)
                    coords_str = values[1] # Coords como string L,T,W,H
                    expected_str = values[2] # Texto esperado como string unido por |
                    extracted_str = values[3] # Texto extraído

                    details_list.append({
                        'index': region_idx,
                        'coordinates_str': coords_str, # Podríamos parsearlo si fuera necesario
                        'expected_text_str': expected_str,
                        'extracted_text': extracted_str
                    })
                except (ValueError, IndexError) as e:
                    logging.warning(f"Error recuperando datos de la fila seleccionada {item_id}: {e}. Datos: {values}")

        return details_list

    def get_edited_text(self):
        """Devuelve el texto del Entry de edición."""
        return self.edited_text_var.get()

    def clear_selection_and_entry(self):
        """Limpia la selección del Treeview y el Entry de edición."""
        if self.ocr_tree:
             # Deseleccionar todas las filas
             for item in self.ocr_tree.selection():
                 self.ocr_tree.selection_remove(item)
        self.edited_text_var.set("")
        if self.edit_entry: self.edit_entry.config(state="disabled")
        if self.confirm_extracted_button: self.confirm_extracted_button.config(state="disabled")
        if self.save_edited_button: self.save_edited_button.config(state="disabled")

    def show(self):
        """Muestra el panel en la grid."""
        logging.debug("Mostrando OcrPanel.")
        # Posición en la grid (debajo de corrección o resultados si corrección está oculta)
        self.grid(row=3, column=0, sticky="nsew", padx=0, pady=(0, 10))
        self.update_idletasks()

    def hide(self):
        """Oculta el panel."""
        logging.debug("Ocultando OcrPanel.")
        self.grid_remove()
        self.clear_selection_and_entry() # Limpiar al ocultar

    # --- Métodos de Acción Internos (Llaman a main_app) ---
    def _confirm_extracted_action(self):
        """Prepara datos y llama a main_app.confirm_ocr_text."""
        selected_details = self.get_selected_region_details()
        if not selected_details:
             logging.warning("Botón 'Confirmar Extraído' presionado sin selección.")
             # Podríamos mostrar un messagebox aquí
             return
        # Pasar la lista de detalles a la aplicación principal
        self.main_app.confirm_ocr_text(selected_details)

    def _save_edited_action(self):
        """Prepara datos y llama a main_app.save_edited_ocr_text."""
        selected_details = self.get_selected_region_details()
        edited_text = self.get_edited_text()

        if not selected_details:
             logging.warning("Botón 'Guardar Editado' presionado sin selección.")
             return
        if len(selected_details) > 1:
             logging.warning("Botón 'Guardar Editado' presionado con múltiple selección. No soportado por el Entry.")
             # Podríamos mostrar un messagebox
             return

        # Pasar el detalle de la única región seleccionada y el texto editado
        self.main_app.save_edited_ocr_text(selected_details[0], edited_text)

    def refresh_tree_display(self, ocr_results_dict):
         """Vuelve a poblar el treeview, útil después de guardar cambios."""
         logging.debug("Refrescando OcrPanel Treeview.")
         self.populate_ocr_tree(ocr_results_dict)


# --- END OF FILE src/panels/ocr_panel.py ---