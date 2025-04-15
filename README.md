# eFootball Automation Suite - Versión Mejorada

## Descripción

Esta aplicación es una suite de herramientas diseñadas para automatizar diversas acciones dentro del juego eFootball. La solución utiliza técnicas de reconocimiento de pantalla, incluyendo:
- **Coincidencia de Plantillas Visuales:** Detección basada en imágenes de referencia (plantillas) cargadas dinámicamente desde `config/templates_mapping.json`.
- **Reconocimiento Óptico de Caracteres (OCR) como Fallback:** Cuando la coincidencia visual no es concluyente, se aplica OCR en regiones predefinidas (`config/ocr_regions.json`) para extraer texto y validar el estado de la pantalla, comparándolo con texto esperado si está definido.
- **Optimización por Contexto y ROI:** Utiliza archivos de configuración (`config/state_transitions.json`, `config/state_rois.json`) para limitar la búsqueda de plantillas a estados probables y regiones específicas, mejorando la velocidad.
- **Gestión Gráfica:** Incluye interfaces gráficas (GUIs) para facilitar la creación/gestión de plantillas, la definición de zonas OCR (con texto esperado) y el testeo interactivo del reconocimiento.

La suite está diseñada para facilitar la automatización de acciones como fichar jugadores, entrenar, jugar partidos (contra IA) y navegar por menús complejos.

## Características Clave

*   **Reconocimiento Híbrido:** Combina template matching con OCR y verificación de texto esperado para mayor robustez.
*   **Optimización de Velocidad:** Implementa contexto de estado y Regiones de Interés (ROI) para acelerar la detección.
*   **GUI de Gestión (`template_manager_gui.py`):**
    *   Captura nuevas plantillas (pantalla completa o región).
    *   Guarda nuevas capturas, actualizando automáticamente el mapping (`templates_mapping.json`).
    *   Permite seleccionar plantillas existentes para visualizar.
    *   Define interactivamente múltiples zonas OCR por plantilla.
    *   Permite asociar "texto esperado" (separado por '|') a cada zona OCR.
    *   Guarda las definiciones de zonas OCR y texto esperado en `config/ocr_regions.json`.
*   **GUI de Testeo (`screen_tester_gui.py`):**
    *   Prueba el `ScreenRecognizer` en tiempo real mientras juegas.
    *   Muestra el método de detección (Template/OCR/Unknown), estado, confianza y tiempo.
    *   Permite confirmar o negar la detección realizada.
    *   Si se niega, permite seleccionar el estado correcto de una lista para registrar la corrección en el log.
    *   Si la detección fue por OCR, muestra los detalles (texto extraído, esperado, si coincide) en una tabla.
    *   Permite confirmar el texto extraído por OCR para añadirlo como "texto esperado" al JSON.
    *   Permite editar y guardar manualmente el "texto esperado" para las regiones OCR seleccionadas.
    *   Permite definir/editar visualmente la Región de Interés (ROI) para un estado, guardándola en `config/state_rois.json`.
    *   Permite lanzar la GUI de Gestión (`template_manager_gui.py`) directamente.
    *   Permite recargar los datos del reconocedor (JSONs y plantillas) sin reiniciar.
*   **Logging Detallado:** Registra las operaciones de reconocimiento, testeo y errores en archivos `.log`.
*   **Control por Gamepad:** Diseñado para interactuar con el juego simulando un gamepad (Xbox/DualSense).
*   **Secuencias Personalizadas:** Utiliza un asistente (`sequence_wizard.py`) para crear secuencias de acciones automatizadas.

## Requisitos

*   Windows 10 o superior
*   Python 3.8 o superior
*   Tesseract OCR instalado y en el PATH del sistema (o configurar la ruta en el código si es necesario).
    *   Asegúrate de instalar los paquetes de idioma necesarios (ej., español `spa`, inglés `eng`).
*   Gamepad compatible (Xbox o DualSense) conectado.
*   eFootball instalado y preferiblemente configurado en modo ventana sin bordes o pantalla completa con la resolución esperada.
*   Dependencias de Python (ver `requirements.txt`):
    *   `mss`
    *   `opencv-python`
    *   `pytesseract`
    *   `Pillow`
    *   `numpy`

## Instalación

1.  Clona o descarga el repositorio.
2.  (Recomendado) Crea y activa un entorno virtual de Python:
    ```bash
    python -m venv .venv
    .\.venv\Scripts\activate  # En Windows
    # source .venv/bin/activate # En Linux/macOS
    ```
3.  Instala las dependencias:
    ```bash
    pip install -r requirements.txt
    ```
    *Alternativamente, puedes ejecutar `install.bat` en Windows, que hace lo mismo.*
4.  Asegúrate de que Tesseract OCR esté correctamente instalado y accesible desde la línea de comandos (puedes probar escribiendo `tesseract --version`).

## Estructura del Proyecto

*   **efootball_automation/**
    *   **config/** `# Archivos de configuración principales`
        *   **profiles/** `# (Perfiles de usuario/automatización)`
        *   **sequences/** `# (Secuencias de acciones guardadas)`
        *   **templates/** `# (Plantillas de configuración - uso por definir)`
        *   `.gitkeep` `# Placeholder para Git`
        *   `ocr_regions.json` `# Definiciones de zonas OCR y texto esperado por estado`
        *   `package.json` `# (Posiblemente no usado para Python - verificar)`
        *   `state_rois.json` `# Definiciones de Regiones de Interés por estado`
        *   `state_transitions.json` `# Definiciones de transiciones probables entre estados`
        *   `templates_mapping.json` `# Mapeo de nombres de estado a archivos de imagen`
    *   **images/** `# Imágenes de plantilla (PNG)`
        *   `...`
    *   **src/** `# Código fuente principal de Python`
        *   **config/** `# (Posible módulo config interno)`
        *   **config_interface/** `# (Posible GUI config interna)`
        *    **panels/** `# (paneles)`
        *   `banner_skipper.py` `# Lógica específica para saltar banners`
        *   `config.json` `# (Configuración local de GUIs, como último origen)`
        *   `config_system.py` `# (Manejo de carga/guardado de configs)`
        *   `create_package.py` `# (Scripts utilitarios/desarrollo)`
        *   `create_package_improved.py`
        *   `cursor_navigator.py` `# Simulación de movimiento del cursor/navegación`
        *   `game_structure_analysis.py` `# (Análisis interno del juego)`
        *   `gamepad_controller.py` `# Interfaz para simular entradas de gamepad`
        *   `gamepad_research.py` `# (Investigación/pruebas de gamepad)`
        *   `main.py` `# Punto de entrada para la automatización principal (run.bat)`
        *   `match_player.py` `# Lógica específica para jugar partidos`
        *   `player_signer.py` `# Lógica específica para fichar jugadores`
        *   `player_trainer.py` `# Lógica específica para entrenar jugadores`
        *   `recognizer.log` `# Log del módulo ScreenRecognizer`
        *   `screen_recognizer.py` `# <<< Núcleo: Reconocimiento de pantalla (Template+OCR+Context+ROI) >>>`
        *   `screen_tester_gui.py` `# <<< GUI: Testeo interactivo y refinamiento OCR/ROI >>>`
        *   `sequence_wizard.py` `# Asistente para crear/gestionar secuencias (wizard.bat)`
        *   `template_manager.log` `# Log de la GUI de gestión`
        *   `template_manager_gui.py` `# <<< GUI: Gestión de plantillas y zonas OCR >>>`
        *   `tester_log.log` `# Log de la GUI de testeo`
        *   `tests.py` `# (Posibles tests unitarios/integración)`
    *   **temp/** `# (Carpeta temporal)`
        *   `...`
    *   **.venv/** `# (Entorno virtual - no incluir en Git)`
    *   `.gitattributes` `# (Configuración Git)`
    *   `.gitignore` `# (Archivos a ignorar por Git)`
    *   `install.bat` `# Script para instalar dependencias (Windows)`
    *   `QUICKSTART.md` `# (Guía rápida - opcional)`
    *   `README.md` `# Esta documentación`
    *   `requirements.txt` `# Lista de dependencias Python`
    *   `run.bat` `# Script para ejecutar la automatización principal (Windows)`
    *   `wizard.bat` `# Script para ejecutar el asistente de secuencias (Windows)`
## Uso

### 1. Configuración Inicial y Gestión (GUI Template Manager)

Es **fundamental** configurar correctamente las plantillas y las zonas OCR/ROI antes de ejecutar la automatización principal.

*   **Ejecutar:** Abre una terminal en la carpeta raíz del proyecto, activa tu entorno virtual (si usas uno) y ejecuta:
    ```bash
    python src/template_manager_gui.py
    ```
*   **Funciones:**
    *   **Capturar Nuevas Plantillas:** Usa la sección superior para capturar pantallas completas o regiones. Introduce un nombre descriptivo y guarda. Esto crea el archivo PNG en `images/` y actualiza `config/templates_mapping.json`.
    *   **Seleccionar Existentes:** Usa el Combobox para elegir una plantilla ya definida. La primera imagen asociada se mostrará.
    *   **Definir Zonas OCR:** Con una imagen cargada, introduce opcionalmente el "Texto Esperado" (varios separados por `|`) y pulsa "Marcar Región OCR". Dibuja el rectángulo sobre la previsualización. Repite para todas las zonas necesarias de esa plantilla. Pulsa "Guardar Zonas OCR" para actualizar `config/ocr_regions.json`.
    *   **Refrescar:** Actualiza la lista del Combobox si has añadido plantillas manualmente o con otro proceso.

### 2. Testeo y Refinamiento (GUI Tester)

Esta herramienta te permite verificar cómo funciona el `ScreenRecognizer` con el juego en ejecución y refinar las configuraciones OCR y ROI.

*   **Ejecutar:** Mientras eFootball está corriendo, abre otra terminal, activa el entorno virtual y ejecuta:
    ```bash
    python src/screen_tester_gui.py
    ```
*   **Funciones:**
    *   **Reconocer:** Pulsa el botón para que intente identificar la pantalla actual del juego.
    *   **Validar:** Usa "👍 Confirmar" o "👎 Negar" según si la detección es correcta.
    *   **Corregir (si se niega/falla):** Selecciona el estado correcto en el Combobox "Corrección Manual" y pulsa "Registrar Corrección" (esto solo escribe en el log).
    *   **Definir/Editar ROI:** Si una detección es válida (o si negaste), puedes pulsar este botón para dibujar un rectángulo en una captura actual y guardar/sobrescribir el ROI para ese estado en `config/state_rois.json`.
    *   **Refinar OCR:** Si la detección fue por OCR:
        *   Revisa la tabla de resultados.
        *   Selecciona una o más filas.
        *   Pulsa "Confirmar Texto Extraído" para añadir el texto leído por OCR a la lista de textos esperados para esas regiones en `config/ocr_regions.json`.
        *   O escribe el texto correcto (con `|` si hay varios) en el campo de edición y pulsa "Guardar Texto Editado" para *reemplazar* los textos esperados de las regiones seleccionadas.
    *   **Abrir Gestor:** Lanza `template_manager_gui.py` si necesitas añadir/modificar plantillas visuales.
    *   **Recargar Datos:** Pulsa este botón después de hacer cambios en los archivos JSON o en las imágenes (ej., usando el Gestor) para que el tester use la información actualizada.

### 3. Ejecutar Automatización Principal (`run.bat`)

Una vez configurado y testeado, puedes ejecutar las tareas automatizadas.

*   **Ejecutar:** Desde la terminal (con entorno activado si aplica):
    ```bash
    run.bat [comando] [opciones]
    ```
*   **Comandos Principales (Ejemplos):**
    *   `run.bat skip`: Salta banners iniciales.
    *   `run.bat sign --position Delantero`: Ficha jugadores.
    *   `run.bat train "NombreJugador"`: Entrena habilidades.
    *   `run.bat play --event`: Juega partidos de evento IA.
    *   `run.bat sequence "nombre_secuencia"`: Ejecuta una secuencia personalizada.
    *   Consulta `main.py` o ejecuta `run.bat --help` (si está implementado) para ver todos los comandos y opciones.

### 4. Crear Secuencias Personalizadas (`wizard.bat`)

*   **Ejecutar:**
    ```bash
    wizard.bat
    ```
*   Sigue las instrucciones del asistente en la consola para crear y guardar secuencias de acciones que luego puedes ejecutar con `run.bat sequence ...`.

## Flujo de Trabajo Recomendado para Configuración

1.  **Captura Inicial:** Usa `template_manager_gui.py` para capturar las pantallas principales y darles nombres claros (ej. `menu_principal_home`, `menu_contrato_base`, `popup_confirmar_fichaje`). Guarda.
2.  **Definir Regiones y ROIs Clave:** En el `template_manager_gui.py`, selecciona las plantillas de pop-ups o menús con texto crucial y define sus zonas OCR (puedes añadir texto esperado aquí o después con el tester). En el `screen_tester_gui.py`, define ROIs para elementos fijos (menús superiores, etc.).
3.  **Testeo Iterativo:** Usa `screen_tester_gui.py` mientras juegas.
    *   Pulsa "Reconocer".
    *   Si es correcto -> "Confirmar". Si fue OCR, selecciona filas y "Confirmar Texto Extraído". Si quieres, define ROI.
    *   Si es incorrecto -> "Negar". Selecciona el estado correcto -> "Registrar Corrección". Define ROI si aplica. Abre el Gestor si necesitas nuevas plantillas.
    *   Si fue OCR pero el texto es erróneo -> Selecciona fila -> Escribe texto correcto -> "Guardar Texto Editado".
4.  **Recargar Datos:** Después de usar el Gestor o editar JSONs manualmente, pulsa "Recargar Datos Reconocedor" en el Tester.
5.  **(Opcional Avanzado) Editar Transiciones:** Edita `config/state_transitions.json` manualmente para añadir más contexto de navegación.
6.  **Repetir:** Continúa testeando y refinando hasta que el reconocimiento sea fiable para tus secuencias deseadas.

## Troubleshooting

*   **Reconocimiento Lento:** Define ROIs (`state_rois.json`) y transiciones (`state_transitions.json`) para los estados más frecuentes. Revisa si tienes plantillas redundantes.
*   **Reconocimiento Incorrecto (Template):** La plantilla puede ser mala o muy similar a otra. Usa el Gestor para capturar una mejor o eliminar redundantes. Considera ajustar el `threshold` en `ScreenRecognizer`.
*   **Reconocimiento Incorrecto (OCR):** El texto esperado no está definido o es incorrecto. Usa el Tester para "Confirmar Texto Extraído" o "Guardar Texto Editado". Asegúrate de que la región OCR sea precisa. Verifica que los idiomas correctos (`spa+eng`) estén configurados en `_extract_and_clean_text`.
*   **Errores al Lanzar GUIs/Scripts:** Asegúrate de estar en el directorio raíz del proyecto y de tener el entorno virtual activado (si usas uno). Verifica las rutas en las constantes al principio de los scripts.
*   **Revisar Logs:** Los archivos `.log` (`recognizer.log`, `tester_log.log`, `template_manager.log`) contienen información detallada sobre las operaciones y errores.

## Contacto y Soporte

(Mantén tu información de contacto aquí si lo deseas)