# --- START OF FILE src/template_manager_utils.py ---
# --- CORREGIDO: Añadido nonlocal y corregido typo 'sel' ---

import os
import json
import shutil
import logging
import tkinter as tk
from tkinter import ttk, messagebox
import cv2
import numpy as np
from PIL import Image, ImageTk
import mss

# --- Constantes ---
SCRIPT_DIR_UTIL = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR_UTIL = os.path.dirname(SCRIPT_DIR_UTIL)
IMAGES_DIR = os.path.join(PROJECT_DIR_UTIL, "images")
CONFIG_DIR = os.path.join(PROJECT_DIR_UTIL, "config")
OCR_MAPPING_FILE_PATH = os.path.join(CONFIG_DIR, "ocr_regions.json")
TEMPLATE_MAPPING_FILE_PATH = os.path.join(CONFIG_DIR, "templates_mapping.json")

# --- Funciones JSON (Sin cambios lógicos) ---
def load_json_mapping(file_path, file_desc="mapping"):
    if not os.path.exists(file_path): return {}
    try:
        with open(file_path, "r", encoding="utf-8") as f: content = f.read()
        if not content: logging.warning(f"Archivo {file_desc} '{file_path}' vacío."); return {}
        mapping = json.loads(content);
        if not isinstance(mapping, dict): raise TypeError("Contenido no es dict JSON")
        return mapping
    except (json.JSONDecodeError, TypeError) as e: logging.error(f"{file_desc} '{file_path}' inválido: {e}"); messagebox.showerror("Error Archivo", f"JSON inválido:\n{os.path.basename(file_path)}\nError: {e}", icon='warning'); return {}
    except Exception as e: logging.exception(f"Err cargando {file_desc} {file_path}: {e}"); messagebox.showerror("Error", f"Error cargando {file_desc}:\n{os.path.basename(file_path)}\n{e}", icon='error'); return {}

def save_json_mapping(mapping, file_path, file_desc="mapping"):
    backup_path = file_path + ".bak";
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        if os.path.exists(file_path): shutil.copy2(file_path, backup_path); logging.debug(f"Backup: {backup_path}")
        with open(file_path, "w", encoding="utf-8") as f: json.dump(mapping, f, indent=4, ensure_ascii=False)
        logging.info(f"{file_desc} guardado: {file_path}");
        if os.path.exists(backup_path):
            try: os.remove(backup_path); logging.debug("Backup eliminado.")
            except OSError as rm_err: logging.warning(f"No se pudo eliminar backup: {rm_err}")
        return True
    except Exception as e:
        logging.exception(f"Err guardando {file_desc} en {file_path}: {e}"); messagebox.showerror("Error Guardando", f"No se pudo guardar {file_desc}:\n{os.path.basename(file_path)}\nError: {e}", icon='error')
        if os.path.exists(backup_path):
            try: shutil.move(backup_path, file_path); logging.info(f"Backup restaurado: {backup_path}")
            except Exception as bk_err: logging.error(f"Fallo restaurar backup! {bk_err}")
        return False

def load_ocr_data(): return load_json_mapping(OCR_MAPPING_FILE_PATH, "regiones OCR")
def save_ocr_data(mapping): return save_json_mapping(mapping, OCR_MAPPING_FILE_PATH, "regiones OCR")
def load_template_data(): return load_json_mapping(TEMPLATE_MAPPING_FILE_PATH, "plantillas")
def save_template_data(mapping): return save_json_mapping(mapping, TEMPLATE_MAPPING_FILE_PATH, "plantillas")

# --- Funciones Captura/Selección (Sin cambios lógicos) ---
def detect_monitors():
    try:
        with mss.mss() as sct: monitors = sct.monitors; logging.info(f"Monitores: {monitors}"); return monitors
    except Exception as e: logging.exception("Error detectando monitores."); return [{}]

def capture_screen(region=None, monitor=1):
    try:
        with mss.mss() as sct:
            monitors = sct.monitors;
            if monitor < 0 or monitor >= len(monitors): logging.error(f"Monitor inválido: {monitor}"); return None
            target = monitors[monitor]; area = region if region else target
            if region:
                cl=max(region['left'],target['left']); ct=max(region['top'],target['top']); mr=target['left']+target['width']; mb=target['top']+target['height']
                cr=min(region['left']+region['width'],mr); cb=min(region['top']+region['height'],mb); cw=cr-cl; ch=cb-ct
                if cw<=0 or ch<=0: logging.error(f"Región calc inválida: {cl},{ct},{cw},{ch}"); return None
                area = {'left':cl,'top':ct,'width':cw,'height':ch}
            logging.info(f"Captura: {area}"); sct_img = sct.grab(area); img = np.array(sct_img)
            if img.shape[2]==4: img_bgr=cv2.cvtColor(img,cv2.COLOR_BGRA2BGR)
            elif img.shape[2]==3: img_bgr=img
            else: logging.error(f"Formato MSS inesperado: {img.shape}"); return None
            return img_bgr
    except mss.ScreenShotError as e: logging.error(f"MSS Error: {e}"); return None
    except Exception as e: logging.exception("Error captura"); return None

# --- tk_select_region_base CORREGIDO ---
def tk_select_region_base(root, image, window_title, rect_outline="green", button_text="Confirmar"):
    if image is None: logging.error("tk_select_region_base: No image."); return None
    try:
        h_orig, w_orig = image.shape[:2]; scale = 1.0; parent=root.winfo_toplevel()
        max_w=parent.winfo_screenwidth()*0.85; max_h=parent.winfo_screenheight()*0.85
        sw=max_w/w_orig if w_orig>max_w else 1.0; sh=max_h/h_orig if h_orig>max_h else 1.0; scale=min(sw,sh,1.0)
        nw,nh=int(w_orig*scale), int(h_orig*scale);
        if nw<1 or nh<1: logging.error("Imagen inválida post-resize."); return None
        interp=cv2.INTER_LANCZOS4 if scale<1.0 else cv2.INTER_AREA; resized=cv2.resize(image,(nw,nh),interpolation=interp)
        img_rgb=cv2.cvtColor(resized,cv2.COLOR_BGR2RGB); pil_img=Image.fromarray(img_rgb); tk_img=ImageTk.PhotoImage(pil_img)

        win=tk.Toplevel(root); win.title(window_title); win.grab_set(); win.minsize(max(400,tk_img.width()//2),max(300,tk_img.height()//2))
        win.update_idletasks(); px,py=parent.winfo_rootx(),parent.winfo_rooty(); pw,ph=parent.winfo_width(),parent.winfo_height()
        ww,wh=win.winfo_width(),win.winfo_height(); x=px+(pw//2)-(ww//2); y=py+(ph//2)-(wh//2); win.geometry(f'+{max(0,x)}+{max(0,y)}')
        canvas=tk.Canvas(win,width=tk_img.width(),height=tk_img.height(),cursor="cross"); canvas.pack(padx=10,pady=10,fill="both",expand=True)
        canvas.create_image(0,0,anchor="nw",image=tk_img); win.tk_img_ref=tk_img

        selection={"x1":None,"y1":None,"x2":None,"y2":None}; rect_id=None; confirmed_region=None

        def on_press(event):
            nonlocal rect_id, selection # <-- Añadido nonlocal selection
            selection["x1"]=canvas.canvasx(event.x); selection["y1"]=canvas.canvasy(event.y)
            selection["x2"]=selection["x1"]; selection["y2"]=selection["y1"]
            if rect_id: canvas.delete(rect_id)
            rect_id = canvas.create_rectangle(selection["x1"],selection["y1"],selection["x1"],selection["y1"],outline=rect_outline,width=2,dash=(4,2))
        def on_drag(event):
            nonlocal selection # <-- Añadido nonlocal selection
            if rect_id and selection["x1"] is not None: cx=canvas.canvasx(event.x); cy=canvas.canvasy(event.y); canvas.coords(rect_id,selection["x1"],selection["y1"],cx,cy)
        def on_release(event):
            nonlocal rect_id, selection # <-- Añadido nonlocal selection
            if rect_id and selection["x1"] is not None:
                selection["x2"]=canvas.canvasx(event.x); selection["y2"]=canvas.canvasy(event.y)
                x1f,y1f=min(selection["x1"],selection["x2"]),min(selection["y1"],selection["y2"]); x2f,y2f=max(selection["x1"],selection["x2"]),max(selection["y1"],selection["y2"])
                min_wh=2
                if (x2f-x1f)<min_wh or (y2f-y1f)<min_wh: logging.warning("Selección pequeña."); canvas.delete(rect_id); rect_id=None; selection={"x1":None,"y1":None,"x2":None,"y2":None}
                else: selection["x1"],selection["y1"],selection["x2"],selection["y2"]=x1f,y1f,x2f,y2f; canvas.coords(rect_id,x1f,y1f,x2f,y2f); logging.debug(f"Canvas Coords: {selection}")
        canvas.bind("<ButtonPress-1>",on_press); canvas.bind("<B1-Motion>",on_drag); canvas.bind("<ButtonRelease-1>",on_release)
        bf=ttk.Frame(win); bf.pack(pady=10)
        def confirm():
            nonlocal confirmed_region, selection # <-- Añadido nonlocal selection y corregido sel
            if None not in selection.values() and rect_id is not None: # Usar selection
                l,t,w,h=selection["x1"],selection["y1"],selection["x2"]-selection["x1"],selection["y2"]-selection["y1"]
                lo,to=int((l/scale)+0.5),int((t/scale)+0.5); wo,ho=int((w/scale)+0.5),int((h/scale)+0.5)
                lo=max(0,min(lo,w_orig-1)); to=max(0,min(to,h_orig-1)); wo=max(1,min(wo,w_orig-lo)); ho=max(1,min(ho,h_orig-to))
                if wo>0 and ho>0: confirmed_region={"left":lo,"top":to,"width":wo,"height":ho}; logging.info(f"Confirmado(orig): {confirmed_region}"); win.destroy()
                else: logging.warning("Inválido al confirmar."); messagebox.showwarning("Inválido","Región inválida.",parent=win)
            else: logging.warning("Confirm sin selección."); messagebox.showwarning("Sin Selección","No seleccionó región.",parent=win)
        def cancel(): win.destroy()
        ttk.Button(bf,text=button_text,command=confirm).pack(side="left",padx=5); ttk.Button(bf,text="Cancelar",command=cancel).pack(side="left",padx=5)
        win.bind("<Escape>",lambda e:cancel()); root.wait_window(win); return confirmed_region
    except Exception as e: logging.exception("Error tk_select_region_base"); messagebox.showerror("Error Display",f"Error ventana selección:\n{e}",parent=root); return None

def tk_select_ocr_region(root, image): return tk_select_region_base(root, image, "Seleccione Región OCR", "green", "Confirmar OCR")
def tk_select_monitor_region(root, monitor_img, monitor_info):
    coords_rel = tk_select_region_base(root, monitor_img, "Seleccione Región Monitor", "blue", "Confirmar Región")
    if coords_rel: coords_abs=coords_rel.copy(); coords_abs['left']+=monitor_info.get('left',0); coords_abs['top']+=monitor_info.get('top',0); logging.info(f"Región(abs): {coords_abs}"); return coords_abs
    return None

# --- END OF FILE src/template_manager_utils.py ---