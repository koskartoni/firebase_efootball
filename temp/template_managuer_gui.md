
---

**Documento Técnico: Módulo `template_manager_gui.py` (Refactorizado)**

**Versión:** 2.0 (Propuesta de Refactorización)
**Fecha:** 2024-04-15

**1. Introducción y Propósito**

El módulo `template_manager_gui.py` proporciona una Interfaz Gráfica de Usuario (GUI) completa para la gestión integral de plantillas de reconocimiento de pantalla y sus correspondientes zonas OCR. Su propósito es permitir a los usuarios:

*   Crear nuevas plantillas capturando imágenes de pantalla (completa o región).
*   Asociar múltiples imágenes a una misma plantilla lógica.
*   Visualizar y seleccionar plantillas e imágenes existentes.
*   Definir, editar y eliminar zonas de reconocimiento óptico de caracteres (OCR) asociadas a una plantilla específica.
*   Gestionar los textos esperados para cada zona OCR.
*   Renombrar y eliminar plantillas existentes, actualizando las configuraciones asociadas.
*   Gestionar (eliminar) las imágenes individuales asociadas a una plantilla.

La GUI interactúa principalmente con los archivos `config/templates_mapping.json`, `config/ocr_regions.json` y los archivos de imagen en `images/`. Esta refactorización busca una estructura modular, un código más mantenible y una experiencia de usuario coherente y robusta.

**2. Objetivos Funcionales Clave**

*   **Captura:**
    *   Capturar el monitor completo seleccionado por el usuario.
    *   Capturar una región específica del monitor seleccionada visualmente por el usuario.
*   **Gestión de Plantillas (Nombres y Mapeo):**
    *   Listar nombres de plantillas existentes (`templates_mapping.json`).
    *   Seleccionar una plantilla existente.
    *   Guardar una nueva plantilla (asignando un nombre a una imagen capturada y actualizando `templates_mapping.json`).
    *   Añadir una nueva imagen capturada a una plantilla *existente*.
    *   Renombrar una plantilla existente (actualizando claves en `templates_mapping.json` y `ocr_regions.json`).
    *   Eliminar una plantilla existente (eliminando entradas de ambos JSON y, opcionalmente, los archivos de imagen asociados).
*   **Gestión de Imágenes:**
    *   Listar los nombres de archivo de imagen asociados a la plantilla seleccionada.
    *   Seleccionar una imagen específica de la lista para previsualizarla y trabajar con sus OCR.
    *   Eliminar una imagen específica de la lista de una plantilla (actualizando `templates_mapping.json` y, opcionalmente, el archivo físico).
*   **Gestión de Zonas OCR:**
    *   Visualizar las zonas OCR definidas para la plantilla seleccionada sobre la imagen previsualizada (con numeración).
    *   Mostrar los detalles (índice, textos esperados) de las zonas OCR en una vista tabular (`ttk.Treeview`).
    *   Marcar una nueva zona OCR visualmente sobre la imagen previsualizada.
    *   Asociar una lista de textos esperados (separados por `|`) a una nueva zona OCR marcada.
    *   Editar los textos esperados de una zona OCR *existente* (seleccionada en el Treeview).
    *   Redibujar/modificar las coordenadas de una zona OCR *existente* (seleccionada en el Treeview).
    *   Eliminar una o más zonas OCR *existentes* (seleccionadas en el Treeview).
    *   Guardar el conjunto actual de zonas OCR (añadidas, editadas, eliminadas) para la plantilla seleccionada en `ocr_regions.json`.
    *   Limpiar las zonas OCR marcadas en la sesión actual *sin* guardar.
*   **Previsualización:**
    *   Mostrar la imagen capturada o seleccionada en un área de previsualización redimensionable.
    *   Superponer las zonas OCR numeradas sobre la imagen.
    *   **Resaltar visualmente** la(s) zona(s) OCR seleccionada(s) en el Treeview sobre la imagen previsualizada.
*   **Interfaz y Usabilidad:**
    *   Proporcionar una interfaz clara y organizada, preferiblemente modularizada en paneles.
    *   Ofrecer feedback continuo a través de una barra de estado y logging.
    *   Utilizar diálogos de confirmación para acciones destructivas (eliminar, sobrescribir).
    *   Validar entradas del usuario (nombres de plantilla, etc.).
    *   Deshabilitar/habilitar controles contextualmente para guiar al usuario y prevenir errores.
    *   Mantener coherencia visual y funcional con `screen_tester_gui.py`.

**3. Filosofía de Diseño y Arquitectura**

*   **Modularidad:** La GUI se dividirá en componentes lógicos (paneles), cada uno encapsulado en su propia clase y, preferiblemente, en su propio archivo dentro de un subdirectorio `panels/` (similar a `screen_tester_gui`). Esto mejora la organización y mantenibilidad.
*   **Separación de Responsabilidades:** La clase principal `TemplateManagerGUI` coordinará las acciones y el estado general, mientras que los paneles manejarán sus propios widgets y eventos internos, comunicándose con la clase principal cuando sea necesario. La lógica de manipulación de archivos JSON y captura/selección de regiones residirá en funciones auxiliares o en la clase principal.
*   **Robustez:** Incluir manejo de errores exhaustivo (carga/guardado de archivos, captura, validaciones) y proporcionar feedback claro al usuario. Utilizar backups al guardar JSONs críticos.
*   **Estado Claro:** Mantener un estado interno consistente (plantilla seleccionada, imagen seleccionada, regiones OCR en memoria) y asegurar que la UI siempre refleje este estado.
*   **UI Moderna y Coherente:** Usar `tkinter.ttk` para widgets, aplicar estilos consistentes y asegurar un layout que se adapte razonablemente al redimensionamiento.

**4. Dependencias**

*   **Bibliotecas Externas:**
    *   `tkinter` (y `tkinter.ttk`, `tkinter.font`, `tkinter.filedialog`, `tkinter.messagebox`, `tkinter.simpledialog`)
    *   `PIL` (Pillow: `Image`, `ImageTk`, `ImageDraw`, `ImageFont`)
    *   `cv2` (OpenCV-Python)
    *   `numpy`
    *   `mss`
*   **Módulos Internos:**
    *   (Potencial) `utils.py`: Para funciones auxiliares como `tk_select_region_base`, `capture_screen`, `load_json_mapping`, `save_json_mapping` (si se decide moverlas desde este archivo).

**5. Estructura de la GUI y Layout Propuesto (Ejemplo)**

Se propone un layout principal de **tres columnas** o una combinación que logre una separación clara:

*   **Columna Izquierda (Gestión Plantillas/Imágenes):**
    *   `ttk.LabelFrame` ("Capturar Nueva Plantilla"): Controles para tipo de captura, monitor, botón "Capturar". Entry para nombre, botón "Guardar Nueva/Añadir Imagen".
    *   `ttk.LabelFrame` ("Gestión Existentes"):
        *   `ttk.Combobox` para seleccionar nombre de plantilla. Botón "Refrescar".
        *   `tk.Listbox` con scrollbar para mostrar los nombres de archivo de imagen asociados a la plantilla seleccionada.
        *   Botones de acción para plantillas/imágenes: "Usar Imagen Selecc.", "Eliminar Imagen Selecc.", "Renombrar Plantilla", "Eliminar Plantilla".
*   **Columna Central (Previsualización):**
    *   `ttk.LabelFrame` ("Previsualización"):
        *   `tk.Canvas` grande y redimensionable para mostrar la imagen.
*   **Columna Derecha (Configuración OCR):**
    *   `ttk.LabelFrame` ("Configuración OCR"):
        *   Botón "Marcar Nueva Región OCR".
        *   `ttk.Entry` para "Texto Esperado (NUEVA región)".
        *   `ttk.Label` con contador de zonas.
        *   `ttk.Treeview` con scrollbar para mostrar detalles de zonas (Índice, Textos Esperados).
        *   Botones de acción para zonas OCR seleccionadas: "Editar Texto", "Redibujar Región", "Eliminar Región(es)".
        *   Botones generales OCR: "Limpiar Zonas Marcadas (Sesión)", "Guardar Zonas OCR (para Plantilla)".
*   **Inferior:**
    *   Barra de Estado (`ttk.Label`).

**6. Componentes Modulares Clave (Clases/Archivos Propuestos)**

*   **`TemplateManagerGUI(tk.Tk)` (en `template_manager_gui.py`):**
    *   Clase principal de la aplicación.
    *   Inicializa la ventana, estilos, carga inicial de datos.
    *   Instancia y organiza los paneles.
    *   Mantiene el estado principal (`current_template_name`, `captured_image`, `ocr_regions`, etc.).
    *   Contiene los **métodos coordinadores** que implementan la lógica principal de las acciones (capturar, guardar plantilla, guardar OCR, renombrar, eliminar, etc.) y manejan la interacción entre paneles.
    *   Maneja la barra de estado y el logging principal.
*   **`TemplatePanel(ttk.LabelFrame)` (en `panels/template_panel.py`):**
    *   Combina la captura y la gestión de plantillas/imágenes (Columnna Izquierda).
    *   Contiene los widgets: Radiobuttons, Spinbox, Entries, Combobox, Listbox, y todos los botones relacionados con captura, guardado de plantilla/imagen, renombrado/eliminación de plantilla/imagen.
    *   Llama a métodos de `main_app` al pulsar botones.
    *   Métodos internos para poblar Combobox/Listbox, obtener valores, etc.
*   **`PreviewPanel(ttk.LabelFrame)` (en `panels/preview_panel.py`):**
    *   Responsable únicamente de mostrar la imagen y las superposiciones.
    *   Contiene el `tk.Canvas`.
    *   Método `update_preview(image, ocr_regions_data, selected_indices)`: recibe la imagen a mostrar, la lista de diccionarios de regiones OCR, y los índices de las regiones seleccionadas para resaltarlas. Maneja redimensionamiento y dibujo.
    *   Método `clear_preview()`.
*   **`OcrPanel(ttk.LabelFrame)` (en `panels/ocr_panel.py`):**
    *   Maneja la sección de configuración OCR (Columna Derecha).
    *   Contiene el botón "Marcar", Entry de texto esperado, Label contador, Treeview, y los botones de acción OCR (Editar, Redibujar, Eliminar, Limpiar Sesión, Guardar JSON).
    *   Métodos para poblar/limpiar Treeview, obtener selección, etc.
    *   Llama a métodos de `main_app` al pulsar botones de acción.
*   **`utils.py` (Opcional, o mantener funciones en `template_manager_gui.py`):**
    *   `load_json_mapping`, `save_json_mapping`
    *   `capture_screen`
    *   `tk_select_region_base` (y sus variantes `tk_select_ocr_region`, `tk_select_monitor_region`)

**7. Descripción Detallada de Funcionalidades Clave (Flujo Lógico)**

*   **Inicialización (`TemplateManagerGUI.__init__`):**
    *   Crea ventana, estilos.
    *   Llama a `detect_monitors`.
    *   Instancia los paneles (`TemplatePanel`, `PreviewPanel`, `OcrPanel`).
    *   Llama a `load_template_names_from_json`, `load_ocr_regions_from_json`.
    *   Configura estado inicial UI (botones deshabilitados, etc.).
*   **Seleccionar Plantilla (`TemplatePanel.on_template_name_selected` -> `main_app.handle_template_selection`):**
    *   `main_app`: Actualiza `current_template_name`. Limpia estado anterior (`ocr_regions`, `captured_image`). Carga lista de imágenes asociadas desde `template_names_mapping`. Llama a `TemplatePanel.populate_image_listbox`. Carga la *primera* imagen (`main_app.load_image`). Carga las regiones OCR desde `ocr_regions_mapping`. Llama a `OcrPanel.populate_treeview`. Actualiza botones y status.
*   **Seleccionar Imagen (`TemplatePanel.on_image_selected` -> `main_app.handle_image_selection` o `TemplatePanel.use_image` -> `main_app.load_image`):**
    *   `main_app`: Actualiza `selected_image_filename`. Llama a `main_app.load_image` con el nombre de archivo.
*   **Cargar Imagen (`main_app.load_image`):**
    *   Lee el archivo de imagen (`cv2.imread`). Actualiza `captured_image`. Llama a `PreviewPanel.update_preview`. Actualiza botones y status.
*   **Capturar (`TemplatePanel.capture_button` -> `main_app.capture_new_template`):**
    *   `main_app`: Determina tipo (monitor/región) y monitor. Llama a `capture_screen` (o `tk_select_monitor_region` + `capture_screen`). Actualiza `captured_image`. Limpia selecciones (`current_template_name`, `selected_image_filename`, `ocr_regions`). Llama a `PreviewPanel.update_preview`. Habilita Entry de nombre y botón guardar, deshabilita otros.
*   **Guardar Plantilla/Añadir Imagen (`TemplatePanel.save_button` -> `main_app.save_template_action`):**
    *   `main_app`: Obtiene nombre, valida. Determina si es nueva plantilla o añadir a existente. Genera nombre archivo único. Pide confirmación. Guarda imagen (`cv2.imwrite`). Carga `templates_mapping.json`. Modifica/Añade entrada. Guarda `templates_mapping.json`. Llama a `TemplatePanel.refresh_template_list`. Selecciona la plantilla/imagen guardada. Pregunta si guardar OCR si es nueva y hay regiones marcadas. Actualiza status.
*   **Marcar Región OCR (`OcrPanel.mark_button` -> `main_app.mark_new_ocr_region`):**
    *   `main_app`: Verifica que hay imagen. Obtiene texto esperado del `OcrPanel.get_expected_text`. Llama a `tk_select_ocr_region`. Si se obtiene región, añade `{"region": coords, "expected_text": texts}` a `self.ocr_regions`. Llama a `OcrPanel.populate_treeview`. Llama a `PreviewPanel.update_preview`. Actualiza contador y botones. Limpia `OcrPanel.expected_text_entry`.
*   **Editar Texto OCR (`OcrPanel.edit_text_button` -> `main_app.edit_ocr_text`):**
    *   `main_app`: Obtiene índice seleccionado del `OcrPanel`. Usa `simpledialog.askstring` con valor inicial. Si se confirma, actualiza `self.ocr_regions[index]['expected_text']`. Llama a `OcrPanel.populate_treeview`. Llama a `PreviewPanel.update_preview` (para color borde). Habilita botón "Guardar Zonas OCR".
*   **Redibujar Región OCR (`OcrPanel.redraw_button` -> `main_app.redraw_ocr_region`):**
    *   `main_app`: Obtiene índice seleccionado. Llama a `tk_select_ocr_region`. Si se obtiene región, actualiza `self.ocr_regions[index]['region']`. Llama a `PreviewPanel.update_preview`. Habilita botón "Guardar Zonas OCR".
*   **Eliminar Región OCR (`OcrPanel.delete_button` -> `main_app.delete_ocr_regions`):**
    *   `main_app`: Obtiene índices seleccionados. Pide confirmación. Elimina elementos de `self.ocr_regions` (iterando al revés). Llama a `OcrPanel.populate_treeview`. Llama a `PreviewPanel.update_preview`. Actualiza contador y botones. Habilita botón "Guardar Zonas OCR".
*   **Guardar Zonas OCR (`OcrPanel.save_button` -> `main_app.save_ocr_changes`):**
    *   `main_app`: Verifica plantilla seleccionada. Carga `ocr_regions.json`. Actualiza/Añade la entrada `ocr_mapping[current_template_name] = self.ocr_regions`. Guarda `ocr_regions.json`. Actualiza `self.ocr_regions_mapping`. Informa al usuario.
*   **Eliminar Imagen (`TemplatePanel.delete_image_button` -> `main_app.delete_image_action`):**
    *   `main_app`: Obtiene plantilla e imagen seleccionadas. Pide confirmación mapeo. Pide confirmación borrado físico. Carga `templates_mapping.json`. Elimina filename de la lista. Si lista queda vacía, elimina clave de plantilla. Guarda `templates_mapping.json`. Si se confirmó, borra archivo (`os.remove`). Llama a `TemplatePanel.refresh_template_list`. Vuelve a seleccionar la plantilla (si aún existe).
*   **Renombrar Plantilla (`TemplatePanel.rename_button` -> `main_app.rename_template_action`):**
    *   `main_app`: Obtiene nombre viejo. Pide nuevo nombre (`simpledialog`). Valida. Carga `templates_mapping.json` y `ocr_regions.json`. Renombra clave en ambos diccionarios. Guarda ambos JSON. Llama a `TemplatePanel.refresh_template_list`. Selecciona nuevo nombre.
*   **Eliminar Plantilla (`TemplatePanel.delete_button` -> `main_app.delete_template_action`):**
    *   `main_app`: Obtiene nombre. Pide confirmación (config). Pide confirmación (archivos físicos). Carga ambos JSON. Elimina clave de ambos. Guarda ambos JSON. Si se confirmó, itera y borra archivos físicos. Llama a `TemplatePanel.refresh_template_list`. Limpia UI.

**8. Data Flow (Simplificado)**

```mermaid
graph LR
    subgraph GUI (template_manager_gui.py)
        UserInput[Usuario Interacción] --> GUIMain(Clase Principal);
        GUIMain -- Coordina --> PanelTpl(TemplatePanel);
        GUIMain -- Coordina --> PanelPrev(PreviewPanel);
        GUIMain -- Coordina --> PanelOCR(OcrPanel);
        PanelTpl -- Llama Acciones --> GUIMain;
        PanelOCR -- Llama Acciones --> GUIMain;
    end

    subgraph Filesystem
        direction TB
        TplJSON[templates_mapping.json]
        OcrJSON[ocr_regions.json]
        Images[images/*.png]
    end

    subgraph Utils (utils.py / internas)
       LoadSaveJSON[load/save_json_mapping]
       Capture[capture_screen]
       SelectRegion[tk_select_region_base]
    end

    GUIMain -- Llama --> LoadSaveJSON;
    GUIMain -- Llama --> Capture;
    GUIMain -- Llama --> SelectRegion;

    LoadSaveJSON -- Lee/Escribe --> TplJSON;
    LoadSaveJSON -- Lee/Escribe --> OcrJSON;
    GUIMain -- Guarda img --> Images;
    GUIMain -- Borra img --> Images;
    PanelPrev -- Lee --> Images;

    GUIMain -- Actualiza --> StatusBar;

```

**9. Manejo de Errores**

*   Capturar excepciones durante carga/guardado de JSONs y mostrar `messagebox.showerror`. Usar backups al guardar.
*   Capturar excepciones durante carga/guardado/borrado de imágenes y mostrar error.
*   Manejar errores de captura de pantalla (`mss.ScreenShotError`, otros).
*   Validar entradas de usuario (nombres de plantilla).
*   Manejar casos donde los archivos de configuración no existen o están vacíos al inicio.
*   Proporcionar mensajes claros en la barra de estado para errores y éxitos.
*   Utilizar logging extensivo para depuración.

**10. Archivos de Configuración Utilizados**

*   **Lectura/Escritura:**
    *   `config/templates_mapping.json`
    *   `config/ocr_regions.json`
*   **Escritura (Imágenes):**
    *   `images/` (Guarda nuevos archivos PNG)
*   **Lectura (Imágenes):**
    *   `images/` (Lee archivos PNG existentes para previsualización)
*   **Escritura (Logs):**
    *   `logs/template_manager.log`

**11. Posibles Mejoras Futuras (Post-Refactorización)**

*   Soporte para diferentes resoluciones de plantillas.
*   Funcionalidad de "probar" OCR sobre una región marcada.
*   Mejoras visuales en la previsualización (zoom, pan).
*   Integración más profunda con `ScreenRecognizer` si fuera necesario.

---
