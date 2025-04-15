# --- START OF FILE src/utils.py ---

import tkinter as tk
from tkinter import ttk, messagebox
import logging
import mss # Para captura de pantalla
import numpy as np
import cv2 # Para conversión de color
from PIL import Image, ImageTk # Para mostrar imagen en Tkinter

# Variable global temporal para almacenar el resultado (alternativa a clases)
# Se usa porque wait_window() bloquea y necesitamos pasar el resultado fuera
_roi_result_holder = None

def tk_select_roi(parent_widget, window_title="Seleccionar Región (ROI)"):
    """
    Abre una ventana Toplevel que muestra una captura del monitor primario
    y permite al usuario seleccionar una región rectangular (ROI) con el ratón.

    Args:
        parent_widget: El widget Tkinter padre para la ventana Toplevel.
        window_title (str): Título para la ventana de selección.

    Returns:
        dict: Un diccionario con las coordenadas absolutas de la pantalla del ROI
              seleccionado {'left', 'top', 'width', 'height'}, o None si se cancela.
    """
    global _roi_result_holder
    _roi_result_holder = None # Resetear resultado anterior

    try:
        with mss.mss() as sct:
            # Obtener geometría del monitor primario (generalmente el índice 1 en la lista completa)
            monitors = sct.monitors
            if len(monitors) < 2:
                logging.error("No se detectó un monitor primario.")
                messagebox.showerror("Error de Monitor", "No se pudo detectar el monitor primario.", parent=parent_widget)
                return None
            primary_monitor = monitors[1] # El índice 0 es 'all', el 1 suele ser el primario
            mon_left, mon_top = primary_monitor["left"], primary_monitor["top"]
            mon_width, mon_height = primary_monitor["width"], primary_monitor["height"]
            logging.info(f"Monitor primario detectado: {primary_monitor}")

            # Capturar el monitor primario
            logging.debug("Capturando pantalla del monitor primario...")
            sct_img = sct.grab(primary_monitor)
            logging.debug("Captura realizada.")

            # Convertir a formato utilizable por PIL/Tkinter
            img_np = np.array(sct_img)
            img_bgr = cv2.cvtColor(img_np, cv2.COLOR_BGRA2BGR)
            img_pil = Image.fromarray(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB))

    except mss.ScreenShotError as e:
        logging.error(f"Error MSS al capturar pantalla: {e}")
        messagebox.showerror("Error de Captura", f"No se pudo capturar la pantalla:\n{e}", parent=parent_widget)
        return None
    except Exception as e:
        logging.exception("Error inesperado durante captura o conversión de imagen.")
        messagebox.showerror("Error Inesperado", f"Ocurrió un error:\n{e}", parent=parent_widget)
        return None

    # --- Crear Ventana Toplevel ---
    roi_window = tk.Toplevel(parent_widget)
    roi_window.title(window_title)
    roi_window.transient(parent_widget) # Mantener encima del padre
    roi_window.grab_set() # Hacerla modal (bloquear interacción con padre)
    roi_window.resizable(False, False) # No permitir redimensionar

    # Guardar referencia a PhotoImage para evitar garbage collection
    try:
        tk_photo = ImageTk.PhotoImage(img_pil)
        roi_window.tk_photo_ref = tk_photo # Guardar referencia en la ventana misma
    except Exception as e:
         logging.exception("Error creando PhotoImage.")
         messagebox.showerror("Error de Imagen", f"No se pudo mostrar la captura:\n{e}", parent=roi_window)
         roi_window.destroy()
         return None


    # --- Canvas para mostrar imagen y dibujar ---
    canvas = tk.Canvas(roi_window, width=mon_width, height=mon_height, cursor="cross")
    canvas.create_image(0, 0, anchor=tk.NW, image=tk_photo)
    canvas.pack(fill=tk.BOTH, expand=True)

    # --- Variables para el dibujo del rectángulo ---
    rect_coords = {"x1": 0, "y1": 0, "x2": 0, "y2": 0}
    rect_id = None # ID del rectángulo en el canvas

    # --- Funciones de Eventos del Ratón ---
    def on_press(event):
        nonlocal rect_id, rect_coords
        # Guardar punto de inicio
        rect_coords["x1"] = event.x
        rect_coords["y1"] = event.y
        rect_coords["x2"] = event.x # Inicializar x2,y2
        rect_coords["y2"] = event.y

        # Eliminar rectángulo anterior si existe
        if rect_id:
            canvas.delete(rect_id)
            rect_id = None

        # Crear nuevo rectángulo (inicialmente un punto) con borde discontinuo
        rect_id = canvas.create_rectangle(
            rect_coords["x1"], rect_coords["y1"],
            rect_coords["x2"], rect_coords["y2"],
            outline='red', width=2, dash=(4, 4)
        )
        # Deshabilitar botón confirmar hasta que se suelte el ratón
        confirm_button.config(state=tk.DISABLED)

    def on_drag(event):
        nonlocal rect_id, rect_coords
        # Actualizar punto final y redibujar rectángulo
        rect_coords["x2"] = event.x
        rect_coords["y2"] = event.y
        if rect_id:
            canvas.coords(rect_id,
                          rect_coords["x1"], rect_coords["y1"],
                          rect_coords["x2"], rect_coords["y2"])

    def on_release(event):
        nonlocal rect_coords
        # Actualizar coordenadas finales (asegurar x1<x2, y1<y2)
        x1, y1 = min(rect_coords["x1"], rect_coords["x2"]), min(rect_coords["y1"], rect_coords["y2"])
        x2, y2 = max(rect_coords["x1"], rect_coords["x2"]), max(rect_coords["y1"], rect_coords["y2"])

        # Validar tamaño mínimo (opcional)
        min_size = 5
        if (x2 - x1) < min_size or (y2 - y1) < min_size:
             logging.warning("ROI seleccionado demasiado pequeño.")
             # Podríamos mostrar un aviso o simplemente ignorarlo
             if rect_id: canvas.delete(rect_id); # Borrar rectángulo pequeño
             confirm_button.config(state=tk.DISABLED) # Mantener deshabilitado
             rect_coords = {"x1": 0, "y1": 0, "x2": 0, "y2": 0} # Resetear
             return

        rect_coords["x1"], rect_coords["y1"] = x1, y1
        rect_coords["x2"], rect_coords["y2"] = x2, y2
        logging.debug(f"Rectángulo final (canvas coords): {rect_coords}")
        # Habilitar botón de confirmar
        confirm_button.config(state=tk.NORMAL)


    # --- Bindings de eventos del ratón al canvas ---
    canvas.bind("<ButtonPress-1>", on_press)
    canvas.bind("<B1-Motion>", on_drag)
    canvas.bind("<ButtonRelease-1>", on_release)

    # --- Botones Confirmar / Cancelar ---
    button_frame = ttk.Frame(roi_window)
    button_frame.pack(fill=tk.X, padx=10, pady=10)
    button_frame.columnconfigure(0, weight=1)
    button_frame.columnconfigure(1, weight=1)

    def confirm_action():
        global _roi_result_holder
        # Calcular coordenadas absolutas
        abs_left = rect_coords["x1"] + mon_left
        abs_top = rect_coords["y1"] + mon_top
        width = rect_coords["x2"] - rect_coords["x1"]
        height = rect_coords["y2"] - rect_coords["y1"]

        # Asegurar que width y height sean positivos (ya hecho en on_release)
        if width > 0 and height > 0:
             _roi_result_holder = {
                 "left": abs_left,
                 "top": abs_top,
                 "width": width,
                 "height": height
             }
             logging.info(f"ROI seleccionado (Absoluto): {_roi_result_holder}")
             roi_window.destroy()
        else:
             # Esto no debería pasar si on_release valida tamaño mínimo
             logging.error("Intento de confirmar ROI con tamaño inválido.")
             messagebox.showwarning("Tamaño Inválido", "El ROI seleccionado tiene tamaño cero o negativo.", parent=roi_window)


    confirm_button = ttk.Button(button_frame, text="Confirmar ROI", command=confirm_action, state=tk.DISABLED)
    confirm_button.grid(row=0, column=0, padx=5, sticky="ew")

    cancel_button = ttk.Button(button_frame, text="Cancelar", command=roi_window.destroy)
    cancel_button.grid(row=0, column=1, padx=5, sticky="ew")

    # --- Centrar ventana y esperar ---
    # Centrar respecto al padre (aproximado)
    roi_window.update_idletasks() # Asegurar que las dimensiones iniciales estén calculadas
    parent_x = parent_widget.winfo_rootx()
    parent_y = parent_widget.winfo_rooty()
    parent_width = parent_widget.winfo_width()
    parent_height = parent_widget.winfo_height()
    win_width = roi_window.winfo_width()
    win_height = roi_window.winfo_height()
    x = parent_x + (parent_width // 2) - (win_width // 2)
    y = parent_y + (parent_height // 2) - (win_height // 2)
    # Asegurarse que no se salga de la pantalla (simple check)
    x = max(0, x)
    y = max(0, y)
    roi_window.geometry(f'+{x}+{y}')

    roi_window.wait_window() # Bloquear hasta que la ventana se cierre

    # Devolver el resultado guardado (será None si se canceló)
    return _roi_result_holder

# --- Ejemplo de uso (requiere una ventana Tkinter padre) ---
if __name__ == "__main__":
    # Crear una ventana principal simple para probar
    root = tk.Tk()
    root.title("Ventana Principal (Test ROI)")
    root.geometry("300x200")

    def test_roi_selection():
        print("Abriendo selector de ROI...")
        # Pasar 'root' como padre
        selected_roi = tk_select_roi(root, "Prueba de Selección ROI")
        if selected_roi:
            print("ROI Seleccionado (Absoluto):", selected_roi)
            result_label.config(text=f"Seleccionado:\n{selected_roi}")
        else:
            print("Selección de ROI cancelada.")
            result_label.config(text="Cancelado")

    # Botón en la ventana principal para lanzar el selector
    select_button = ttk.Button(root, text="Seleccionar ROI", command=test_roi_selection)
    select_button.pack(pady=20)
    result_label = ttk.Label(root, text="Resultado aparecerá aquí")
    result_label.pack(pady=10)

    # Configurar logging básico si se ejecuta directamente
    if not logging.getLogger().hasHandlers():
          logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    root.mainloop()

# --- END OF FILE src/utils.py ---