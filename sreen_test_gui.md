¡Excelente idea! Crear un documento técnico detallado antes de reescribir el código es el enfoque correcto para asegurar claridad, evitar errores y tener una referencia sólida.

Aquí tienes una propuesta de documento técnico para `screen_tester_gui.py`, explicando su estructura, funcionalidades y componentes auxiliares:

---

**Documento Técnico: Módulo `screen_tester_gui.py`**

**Versión:** 1.0
**Fecha:** 2024-04-14

**1. Introducción y Propósito**

El módulo `screen_tester_gui.py` proporciona una Interfaz Gráfica de Usuario (GUI) interactiva diseñada para probar, validar y refinar el sistema de reconocimiento de pantalla implementado en `screen_recognizer.py`. Su propósito principal es permitir a un usuario ejecutar el reconocimiento sobre la pantalla actual del juego (eFootball), visualizar los resultados detallados, confirmar o negar la precisión de la detección, y facilitar el ajuste fino de los datos de configuración (textos esperados OCR, Regiones de Interés - ROI) para mejorar la robustez y precisión del `ScreenRecognizer`.

**2. Objetivos Funcionales**

*   Ejecutar el reconocimiento de pantalla bajo demanda.
*   Mostrar de forma clara el resultado del reconocimiento: método utilizado (Template, OCR, Unknown, Error), estado detectado, confianza (si aplica) y tiempo de ejecución.
*   Permitir al usuario confirmar la validez de una detección exitosa.
*   Permitir al usuario negar una detección incorrecta y seleccionar el estado correcto manualmente.
*   Visualizar detalles específicos cuando la detección se realiza mediante OCR, incluyendo el texto extraído y el esperado para cada región definida.
*   Facilitar la actualización del archivo `ocr_regions.json` añadiendo textos extraídos como válidos o guardando textos editados manualmente por el usuario.
*   Proporcionar una interfaz visual para definir, editar y eliminar las Regiones de Interés (ROI) asociadas a cada estado en `state_rois.json`.
*   Ofrecer una previsualización visual del estado detectado o corregido, mostrando la imagen de plantilla base y superponiendo indicadores para el ROI y/o las regiones OCR definidas.
*   Permitir la recarga dinámica de todos los datos de configuración (`templates_mapping.json`, `ocr_regions.json`, `state_rois.json`, `state_transitions.json`) utilizados por el `ScreenRecognizer` sin reiniciar la aplicación.
*   Permitir lanzar la GUI de gestión de plantillas (`template_manager_gui.py`) como un proceso separado.
*   Proporcionar retroalimentación continua al usuario a través de una barra de estado.
*   Registrar acciones y resultados relevantes en un archivo de log (`tester_log.log`).

**3. Dependencias**

*   **Bibliotecas Externas:**
    *   `tkinter` (y `tkinter.ttk`, `tkinter.font`, `tkinter.filedialog`, `tkinter.messagebox`, `tkinter.simpledialog`)
    *   `PIL` (Pillow: `Image`, `ImageTk`, `ImageDraw`, `ImageFont`)
    *   `cv2` (OpenCV-Python) - Principalmente para `tk_select_roi` y manejo de imágenes.
    *   `numpy` - Para manipulación de imágenes con OpenCV.
*   **Módulos Internos:**
    *   `screen_recognizer`: Necesita importar la clase `ScreenRecognizer` y las funciones `save_json_mapping`, `load_json_mapping`, así como las constantes de ruta (OCR\_MAPPING\_FILE, STATE\_ROIS\_FILE, etc.).
    *   (Potencial) `panels.*`: Si se implementa la refactorización en paneles separados.
    *   (Potencial) `utils.py`: Para funciones auxiliares como `tk_select_roi`.

**4. Estructura de la GUI y Layout**

La interfaz principal se organizará preferentemente en un layout de **dos columnas**:

*   **Columna Izquierda (Panel de Control y Datos):**
    *   Contendrá la mayoría de los controles interactivos y la información textual.
    *   Se estructurará verticalmente usando `ttk.LabelFrame` para agrupar funcionalidades:
        *   **Panel de Control:** Botones "Reconocer Pantalla", "Recargar Datos". (Podrían incluirse aquí sliders de umbrales y checkbox de debug si se desea).
        *   **Panel de Resultados:** Etiquetas para mostrar Método, Estado, Confianza, Tiempo, Estado del ROI. Botones de acción contextual (Confirmar, Negar, ROI+, ROI-, Abrir Gestor).
        *   **Panel de Corrección Manual:** (Oculto inicialmente) ComboBox para seleccionar el estado correcto, botón "Registrar Log".
        *   **Panel de Detalles OCR:** (Oculto inicialmente) `ttk.Treeview` para mostrar resultados OCR, `ttk.Entry` para edición, botones "Confirmar Extraído", "Guardar Editado".
    *   **Barra de Estado:** Una etiqueta en la parte inferior para mostrar mensajes al usuario.
*   **Columna Derecha (Panel de Previsualización):**
    *   Contendrá un `ttk.LabelFrame` titulado "Previsualización Estado".
    *   Dentro, un `tk.Canvas` ocupará la mayor parte del espacio para mostrar imágenes.
    *   (Opcional) Podría incluir una pequeña etiqueta debajo del canvas para mostrar información adicional (ej., nombre del archivo de plantilla visualizado).

**5. Componentes Clave (Clases y Funciones Auxiliares)**

*   **`ScreenTesterGUI(tk.Tk)`:**
    *   Clase principal de la aplicación.
    *   Inicializa la ventana, estilos, y la instancia de `ScreenRecognizer`.
    *   Crea e instancia los diferentes paneles (ya sea directamente o importando clases de `panels/`).
    *   Contiene los **métodos coordinadores** que implementan la lógica principal (ver Sección 6).
    *   Maneja el estado general de la aplicación (ej., `last_recognition_result`, `current_template_name`).
*   **`SelectStateDialog(simpledialog.Dialog)`:**
    *   Un diálogo emergente personalizado (hereda de `simpledialog.Dialog`) que muestra una lista desplegable (`ttk.Combobox`) de estados disponibles.
    *   Se utiliza para que el usuario seleccione un estado específico cuando sea necesario (ej., al definir ROI después de un fallo).
*   **`tk_select_roi(root, recognizer_instance, state_name)`:**
    *   Función auxiliar (podría moverse a `utils.py`).
    *   Se encarga de:
        *   Usar la `recognizer_instance` para capturar la pantalla completa del monitor configurado.
        *   Mostrar esta captura en una ventana `tk.Toplevel`.
        *   Permitir al usuario dibujar un rectángulo sobre la captura.
        *   Calcular las coordenadas **absolutas** del rectángulo seleccionado en la pantalla.
        *   Devolver el diccionario de coordenadas ROI (`{left, top, width, height}`) o `None` si se cancela.

**6. Descripción Detallada de Funcionalidades**

*   **6.1. Inicialización (`__init__`)**
    *   Crea la ventana principal (`tk.Tk`).
    *   Configura título, tamaño mínimo.
    *   Instancia `ScreenRecognizer`.
    *   Carga y aplica estilos (`setup_fonts_and_styles`).
    *   Llama a `create_widgets` (o `create_panels`).
    *   Puebla el ComboBox de corrección (`_populate_correction_combobox`).
    *   Establece el estado inicial de la UI (`reset_ui_state`).
*   **6.2. Reconocimiento (`run_test`)**
    *   *Trigger:* Botón "Reconocer Pantalla".
    *   *Acción:*
        *   Muestra mensaje "Reconociendo..." en la barra de estado.
        *   Llama a `reset_ui_state` para limpiar resultados anteriores.
        *   Deshabilita botones de control.
        *   **Captura la pantalla actual** (se guarda en `self.current_preview_image_cv`).
        *   Llama a `self.recognizer.recognize_screen_for_test()` (que internamente hará otra captura, idealmente se modificaría para aceptar la imagen ya capturada).
        *   Guarda el resultado en `self.last_recognition_result`.
        *   Añade la captura (`self.current_preview_image_cv`) al diccionario `result` si no está presente.
        *   Habilita botones de control.
        *   Actualiza el panel de resultados (`result_panel.update_results`) con la información del `result`.
        *   Gestiona la visibilidad de los paneles de Corrección y OCR basándose en si el reconocimiento fue exitoso, fallido o por OCR.
        *   Habilita/deshabilita los botones de acción (Confirmar, Negar, ROI, Gestor) según corresponda.
        *   Actualiza la barra de estado con un resumen.
        *   Llama a `preview_panel.update_preview` para mostrar la captura de pantalla y los overlays correspondientes (ROI, OCR).
*   **6.3. Recarga de Datos (`reload_recognizer_data`)**
    *   *Trigger:* Botón "Recargar Datos".
    *   *Acción:*
        *   Muestra mensaje "Recargando...".
        *   Llama a `self.recognizer.reload_data()`.
        *   Llama a `correction_panel.populate_combobox()` para actualizar la lista de estados.
        *   Llama a `reset_ui_state`.
        *   Muestra mensaje de éxito o error.
*   **6.4. Confirmación (`confirm_detection`)**
    *   *Trigger:* Botón "Confirmar Detección".
    *   *Acción:*
        *   Verifica que haya una detección válida (`current_template_name` no es None).
        *   Registra la confirmación en el log.
        *   Actualiza la barra de estado.
        *   Deshabilita los botones "Confirmar" y "Negar".
        *   Oculta los paneles de Corrección y OCR (si no fue OCR).
*   **6.5. Negación (`deny_detection`)**
    *   *Trigger:* Botón "Negar Detección".
    *   *Acción:*
        *   Registra la negación en el log.
        *   Actualiza la barra de estado.
        *   Deshabilita "Confirmar" y "Negar".
        *   Muestra el panel de Corrección (`correction_panel.show()`).
        *   Habilita los botones "Definir/Editar ROI", "Eliminar ROI" y "Abrir Gestor".
        *   Oculta el panel OCR.
        *   Limpia la previsualización (`preview_panel.clear_preview()`).
        *   Resetea `current_template_name`.
*   **6.6. Corrección Manual**
    *   **Selección en ComboBox (`on_correct_state_selected`):**
        *   *Trigger:* Usuario selecciona un estado en `correction_panel.correct_state_combo`.
        *   *Acción:*
            *   Actualiza `self.current_template_name` con el estado seleccionado.
            *   Llama a `result_panel.update_roi_label()` para mostrar si el estado *corregido* tiene ROI.
            *   Llama a `preview_panel.update_preview()` pasándole el `state_name` seleccionado para mostrar su imagen de plantilla y el indicador ROI.
    *   **Registro en Log (`log_correct_state`):**
        *   *Trigger:* Botón "Registrar Corrección (Log)" en `correction_panel`.
        *   *Acción:*
            *   Obtiene el estado seleccionado del ComboBox.
            *   Registra la corrección en el log.
            *   Actualiza la barra de estado.
            *   (Ya no necesita actualizar preview, se hace al seleccionar).
*   **6.7. Gestión OCR (Panel OCR)**
    *   **Poblado (`ocr_panel.populate_ocr_tree`):** Llena el Treeview con los datos de `result['ocr_results']`.
    *   **Selección en Treeview (`ocr_panel.on_tree_select`):** Carga el texto esperado de la fila seleccionada en el Entry de edición y habilita el Entry.
    *   **Confirmar Texto Extraído (`confirm_ocr_text` en GUI principal, llamado por `ocr_panel`):**
        *   Obtiene los índices y textos extraídos de las filas seleccionadas en el Treeview.
        *   Pide confirmación al usuario.
        *   Llama a `load_ocr_data()`.
        *   Modifica el diccionario cargado, añadiendo los textos extraídos a las listas `expected_text` correspondientes (buscando por coordenadas de región).
        *   Llama a `save_ocr_data()`.
        *   Llama a `self.recognizer.reload_data()`.
        *   Llama a `ocr_panel.refresh_tree_display()` para actualizar la tabla.
        *   Actualiza barra de estado.
    *   **Guardar Texto Editado (`save_edited_ocr_text` en GUI principal, llamado por `ocr_panel`):**
        *   Obtiene los índices de las filas seleccionadas y el texto del Entry de edición.
        *   Procesa el texto del Entry (divide por `|`).
        *   Pide confirmación para sobrescribir.
        *   Llama a `load_ocr_data()`.
        *   Modifica el diccionario cargado, reemplazando la lista `expected_text` de las regiones correspondientes con la nueva lista generada desde el Entry.
        *   Llama a `save_ocr_data()`.
        *   Llama a `self.recognizer.reload_data()`.
        *   Llama a `ocr_panel.clear_selection_and_entry()` y `ocr_panel.refresh_tree_display()`.
        *   Actualiza barra de estado.
*   **6.8. Gestión ROI**
    *   **Definir/Editar ROI (`define_roi_for_state`):**
        *   *Trigger:* Botón "Definir/Editar ROI".
        *   *Acción:*
            *   Determina el `state_to_edit` (ya sea el detectado o el corregido seleccionado, pidiendo confirmación).
            *   Llama a `tk_select_roi()` pasándole la instancia del recognizer y el `state_to_edit`.
            *   Si se obtiene un ROI válido:
                *   Llama a `load_roi_data()`.
                *   Añade/actualiza la entrada para `state_to_edit` en el diccionario.
                *   Llama a `save_roi_data()`.
                *   Llama a `self.recognizer.reload_data()`.
                *   Actualiza `result_panel.update_roi_label()`.
                *   Actualiza `preview_panel.update_preview()` para mostrar el indicador.
                *   Actualiza barra de estado.
    *   **Eliminar ROI (`remove_roi_for_state`):**
        *   *Trigger:* Botón "Eliminar ROI".
        *   *Acción:*
            *   Determina el `state_to_modify` (detectado o corregido).
            *   Verifica si existe ROI para ese estado.
            *   Pide confirmación al usuario.
            *   Llama a `load_roi_data()`.
            *   Elimina la entrada para `state_to_modify`.
            *   Llama a `save_roi_data()`.
            *   Llama a `self.recognizer.reload_data()`.
            *   Actualiza `result_panel.update_roi_label()`.
            *   Actualiza `preview_panel.update_preview()` para quitar el indicador.
            *   Actualiza barra de estado.
*   **6.9. Abrir Gestor (`launch_template_manager`)**
    *   *Trigger:* Botón "Abrir Gestor".
    *   *Acción:* Usa `subprocess.Popen` para ejecutar `template_manager_gui.py`. Muestra mensaje recordando recargar datos.
*   **6.10. Barra de Estado (`status_message`)**
    *   Método simple para actualizar el texto de `status_label_var` y registrar el mensaje.

**7. Flujo de Datos Simplificado**

```mermaid
graph LR
    subgraph GUI (screen_tester_gui.py)
        direction LR
        UserInput[Usuario Interacción (Botones, Selección)] --> GUIMain(Clase Principal ScreenTesterGUI);
        GUIMain -- Llama Métodos --> PanelControl(Panel Control);
        GUIMain -- Llama Métodos --> PanelResult(Panel Resultados);
        GUIMain -- Llama Métodos --> PanelCorrect(Panel Corrección);
        GUIMain -- Llama Métodos --> PanelOCR(Panel OCR);
        GUIMain -- Llama Métodos --> PanelPreview(Panel Preview);
        PanelControl -- Ejecuta Acción --> GUIMain;
        PanelResult -- Ejecuta Acción --> GUIMain;
        PanelCorrect -- Ejecuta Acción/Selección --> GUIMain;
        PanelOCR -- Ejecuta Acción --> GUIMain;
    end

    subgraph Recognizer (screen_recognizer.py)
        RecInstance(Instancia ScreenRecognizer);
    end

    subgraph Filesystem
        direction TB
        JSONs[JSON Files (config/)]
        Images[Images (images/)]
    end

    GUIMain -- Instancia y Llama --> RecInstance;
    RecInstance -- Lee --> JSONs;
    RecInstance -- Lee --> Images;
    GUIMain -- Llama tk_select_roi --> RecInstance; # Para captura en ROI
    GUIMain -- Llama save_json --> JSONs; # Guarda ROI y OCR


    GUIMain -- Actualiza --> StatusBar(Barra Estado);
    GUIMain -- Lanza --> TemplateManager(template_manager_gui.py);

```

**8. Manejo de Errores**

*   Errores de carga de archivos JSON deben ser capturados y notificados al usuario (posiblemente con `messagebox.showerror`), permitiendo continuar si es posible (ej., usando diccionarios vacíos).
*   Errores durante el reconocimiento (`recognize_screen_for_test`) deben ser capturados, registrados, notificados al usuario, y la interfaz debe reflejar el estado de error.
*   Errores de captura de pantalla deben ser manejados y notificados.
*   Errores al guardar archivos JSON deben ser notificados.
*   Errores de importación críticos deben prevenir la ejecución y mostrar un mensaje claro.

**9. Archivos de Configuración Utilizados**

*   **Lectura (vía `ScreenRecognizer`):**
    *   `config/templates_mapping.json`
    *   `config/ocr_regions.json`
    *   `config/state_transitions.json`
    *   `config/state_rois.json`
*   **Escritura (Directa o vía `save_json_mapping`):**
    *   `config/ocr_regions.json` (al confirmar/editar texto esperado OCR)
    *   `config/state_rois.json` (al definir/eliminar ROI)
*   **Escritura (Logs):**
    *   `logs/tester_log.log`

**10. Posibles Mejoras Futuras**

*   Implementar el dibujo exacto del ROI y/o regiones OCR en la previsualización (requiere manejo cuidadoso de coordenadas).
*   Permitir la edición directa de las coordenadas de regiones OCR o ROI desde la interfaz.
*   Añadir la capacidad de modificar `state_transitions.json` desde la GUI.
*   Modificar `ScreenRecognizer` para aceptar una imagen capturada y evitar la doble captura en `run_test`.
*   Mejorar el manejo de errores y proporcionar feedback más específico.

---

Este documento debería proporcionar una base sólida y detallada para reimplementar `screen_tester_gui.py` de forma modular o simplemente para tener claro el funcionamiento esperado de cada parte.