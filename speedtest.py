import ttkbootstrap as tb
from ttkbootstrap.constants import *
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk, ImageGrab, ImageDraw
import pytesseract
import psutil
import threading
import time
import re
import requests
import pygetwindow as gw
import win32gui
import win32ui
import win32con
import numpy as np
import cv2
import ctypes
import matplotlib
matplotlib.use("Agg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# OCR yöntemleri
def capture_with_printwindow(hwnd, crop_rect=None):
    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    width, height = right - left, bottom - top
    hwindc = win32gui.GetWindowDC(hwnd)
    srcdc = win32ui.CreateDCFromHandle(hwindc)
    memdc = srcdc.CreateCompatibleDC()
    bmp = win32ui.CreateBitmap()
    bmp.CreateCompatibleBitmap(srcdc, width, height)
    memdc.SelectObject(bmp)
    PW_RENDERFULLCONTENT = 0x00000002
    result = ctypes.windll.user32.PrintWindow(hwnd, memdc.GetSafeHdc(), PW_RENDERFULLCONTENT)
    bmpinfo = bmp.GetInfo()
    bmpstr = bmp.GetBitmapBits(True)
    img = np.frombuffer(bmpstr, dtype='uint8')
    img.shape = (height, width, 4)
    img = img[..., :3]
    srcdc.DeleteDC()
    memdc.DeleteDC()
    win32gui.ReleaseDC(hwnd, hwindc)
    win32gui.DeleteObject(bmp.GetHandle())
    if crop_rect:
        x1, y1, x2, y2 = crop_rect
        img = img[y1:y2, x1:x2]
    return img, result

def capture_with_bitblt(hwnd, crop_rect=None):
    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    width, height = right - left, bottom - top
    hwindc = win32gui.GetWindowDC(hwnd)
    srcdc = win32ui.CreateDCFromHandle(hwindc)
    memdc = srcdc.CreateCompatibleDC()
    bmp = win32ui.CreateBitmap()
    bmp.CreateCompatibleBitmap(srcdc, width, height)
    memdc.SelectObject(bmp)
    try:
        memdc.BitBlt((0, 0), (width, height), srcdc, (0, 0), win32con.SRCCOPY)
    except Exception:
        srcdc.DeleteDC()
        memdc.DeleteDC()
        win32gui.ReleaseDC(hwnd, hwindc)
        win32gui.DeleteObject(bmp.GetHandle())
        return None
    bmpinfo = bmp.GetInfo()
    bmpstr = bmp.GetBitmapBits(True)
    img = np.frombuffer(bmpstr, dtype='uint8')
    img.shape = (height, width, 4)
    img = img[..., :3]
    srcdc.DeleteDC()
    memdc.DeleteDC()
    win32gui.ReleaseDC(hwnd, hwindc)
    win32gui.DeleteObject(bmp.GetHandle())
    if crop_rect:
        x1, y1, x2, y2 = crop_rect
        img = img[y1:y2, x1:x2]
    return img

def capture_with_imagegrab(hwnd, crop_rect=None):
    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    if crop_rect:
        x1, y1, x2, y2 = crop_rect
        bbox = (left + x1, top + y1, left + x2, top + y2)
    else:
        bbox = (left, top, right, bottom)
    img_pil = ImageGrab.grab(bbox=bbox)
    img_np = np.array(img_pil)
    img_np = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
    return img_np

def capture_with_dwm(hwnd, crop_rect=None):
    raise NotImplementedError("DWM capture yöntemi bu sürümde desteklenmemektedir.")

def parse_float(text):
    if not text:
        return 0.0
    text = str(text).replace(",", ".").replace(" ", "")
    try:
        return float(re.findall(r"[\d.]+", text)[0])
    except Exception:
        return 0.0

def time_format(secs):
    try:
        secs = int(round(secs))
    except Exception:
        return "--:--:--"
    if secs < 0:
        secs = 0
    m, s = divmod(secs, 60)
    h, m = divmod(m, 60)
    return f"{h:02}:{m:02}:{s:02}"

def list_all_windows():
    windows = []
    def enum_handler(hwnd, lParam):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if title:
                windows.append((title, hwnd))
    win32gui.EnumWindows(enum_handler, None)
    return windows

def ocr_from_image(img_np):
    gray = cv2.cvtColor(img_np, cv2.COLOR_BGR2GRAY)
    text = pytesseract.image_to_string(gray, lang="eng+tur")
    return text

class Cropper(tk.Toplevel):
    def __init__(self, parent, img_pil, callback):
        super().__init__(parent)
        self.title("Alan Seç (Snapshot)")
        self.callback = callback
        self.img_pil = img_pil
        self.img_w, self.img_h = img_pil.size
        self.canvas = tk.Canvas(self, width=self.img_w, height=self.img_h, cursor="cross")
        self.canvas.pack()
        self.tk_img = ImageTk.PhotoImage(img_pil)
        self.canvas.create_image(0, 0, image=self.tk_img, anchor="nw")
        self.start = None
        self.rect = None
        self.bind_events()
        self.grab_set()
        self.focus_force()
    def bind_events(self):
        self.canvas.bind("<Button-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
    def on_press(self, event):
        self.start = (event.x, event.y)
        if self.rect:
            self.canvas.delete(self.rect)
        self.rect = self.canvas.create_rectangle(event.x, event.y, event.x, event.y, outline="red", width=2)
    def on_drag(self, event):
        if self.start and self.rect:
            self.canvas.coords(self.rect, self.start[0], self.start[1], event.x, event.y)
    def on_release(self, event):
        if self.start:
            x1, y1 = self.start
            x2, y2 = event.x, event.y
            x1, x2 = sorted((x1, x2))
            y1, y2 = sorted((y1, y2))
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(self.img_w, x2), min(self.img_h, y2)
            self.callback((x1, y1, x2, y2))
            self.destroy()

class OcrTestWindow(tk.Toplevel):
    def __init__(self, parent, test_img_pil, crop_rect, ocr_value, error_text, method):
        super().__init__(parent)
        self.title(f"OCR Test Görüntü ({method})")
        self.geometry("+250+250")
        self.resizable(False, False)
        draw = ImageDraw.Draw(test_img_pil)
        if crop_rect:
            x1, y1, x2, y2 = crop_rect
            draw.rectangle([x1, y1, x2, y2], outline="red", width=3)
            draw.text((x1+2, y1+2), f"{x1},{y1}", fill="yellow")
            draw.text((x2-35, y2-18), f"{x2},{y2}", fill="yellow")
        self.tkimg = ImageTk.PhotoImage(test_img_pil)
        lbl_img = tk.Label(self, image=self.tkimg)
        lbl_img.pack(padx=5, pady=5)
        ttk.Label(self, text=f"OCR Sonucu:", font=("Consolas", 11, "bold")).pack()
        ttk.Label(self, text=ocr_value, foreground="blue", font=("Consolas", 14, "bold")).pack()
        ttk.Label(self, text=f"Kullanılan metod: {method}", font=("Consolas", 10, "italic")).pack()
        if error_text:
            ttk.Label(self, text="Hata:", font=("Consolas", 11, "bold"), foreground="red").pack()
            ttk.Label(self, text=error_text, wraplength=430, foreground="red", font=("Consolas", 10)).pack()

class TumIndirmeIzleyici(tb.Window):
    OCR_METHODS = [
        ("PrintWindow (PW_RENDERFULLCONTENT)", "printwindow"),
        ("BitBlt", "bitblt"),
        ("Ekran Görüntüsü (ImageGrab)", "imagegrab"),
        ("(Eksperimental) DWM", "dwm"),
    ]
    def __init__(self):
        super().__init__(themename="darkly")
        self.title("Akıllı Tüm İndirme İzleyici (OCR Multi-Method)")
        self.geometry("900x980")
        self.resizable(True, True)
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.scroll_canvas = tk.Canvas(self, borderwidth=0, bg="#222831", highlightthickness=0)
        self.scroll_canvas.pack(side="left", fill="both", expand=True)
        yscroll = ttk.Scrollbar(self, orient="vertical", command=self.scroll_canvas.yview)
        yscroll.pack(side="right", fill="y")
        self.scroll_canvas.configure(yscrollcommand=yscroll.set)
        self.frm = ttk.Frame(self.scroll_canvas)
        self.frm_id = self.scroll_canvas.create_window((0, 0), window=self.frm, anchor="nw")
        self.scroll_canvas.bind("<Configure>", lambda e: self.scroll_canvas.configure(scrollregion=self.scroll_canvas.bbox("all")))
        self.frm.bind("<Configure>", lambda e: self.scroll_canvas.configure(scrollregion=self.scroll_canvas.bbox("all")))
        self.scroll_canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.all_windows = list_all_windows()
        self.selected_hwnd = None
        self.selected_window_title = tk.StringVar(value=self.all_windows[0][0] if self.all_windows else "")
        self.crop_rect = None
        self.ocr_value = tk.StringVar(value="0")
        self.selected_ocr_method = tk.StringVar(value=self.OCR_METHODS[0][1])
        self.ethernet_list = self.get_ethernet_list()
        self.selected_eth = tk.StringVar(value=self.ethernet_list[0] if self.ethernet_list else "")
        self.kota_var = tk.StringVar(value="Kalan Kota: ...")
        self.kota_timer_var = tk.StringVar(value="Yenilemeye: 60 sn")
        self.kalan_kota = None
        self.kota_son_cekilis = 0
        self.kota_sayac = 60
        self.down_data = [0.0]*60
        self.up_data = [0.0]*60
        self.down_stats = {"min": 0.0, "max": 0.0, "avg": 0.0}
        self.up_stats = {"min": 0.0, "max": 0.0, "avg": 0.0}
        self.last_counters = None
        self.unit_mode = tk.StringVar(value="mb")
        self.otomatik_gecis = tk.BooleanVar(value=False)
        self.toplam_boyut = tk.StringVar(value="")
        self.toplam_birim = tk.StringVar(value="mb")
        self.progress_value = tk.DoubleVar(value=0)
        self.percent_text = tk.StringVar(value="%0")
        self.bitirme_tahmini = tk.StringVar(value="--:--:--")
        self.hiz_tahmini = tk.StringVar(value="--:--:--")
        self.hiz_olcum_sonuc = tk.StringVar(value="--")
        self.hiz_olcum_sure = tk.IntVar(value=10)
        self.hiz_olcum_aktif = tk.BooleanVar(value=False)
        self.hiz_olcum_geri_sayim = tk.StringVar(value="")
        self.hiz_olcum_gecmis = []
        self.hiz_olcum_min = tk.StringVar(value="--")
        self.hiz_olcum_max = tk.StringVar(value="--")
        self.hiz_olcum_avg = tk.StringVar(value="--")
        self.hiz_olcum_ilk_deger = 0.0
        self.hiz_olcum_son_deger = 0.0
        self.ocr_thread_run = False
        self.mini = None
        self._build_ui()
        self.after(1000, self.update_speed)
        self.after(1000, self.update_kota_timer)
        self.after(1000, self.update_progress)
    def _on_mousewheel(self, event):
        self.scroll_canvas.yview_scroll(-1 * int(event.delta / 120), "units")
    def _build_ui(self):
        main = self.frm
        penceref = ttk.Labelframe(main, text=" Pencere Seçimi (OCR için) ", padding=8, bootstyle="primary")
        penceref.pack(fill="x", pady=(0,6))
        ttk.Label(penceref, text="Pencere:", font=("Segoe UI", 10, "bold")).pack(side="left", padx=(2,8))
        self.pencere_combo = ttk.Combobox(penceref, values=[w[0] for w in self.all_windows], textvariable=self.selected_window_title, state="readonly", width=70)
        self.pencere_combo.pack(side="left", padx=4)
        ttk.Button(penceref, text="Pencereyi Seç", command=self.set_selected_hwnd).pack(side="left", padx=8)
        ttk.Button(penceref, text="Alan Seç (Snapshot)", command=self.select_crop_area_snapshot).pack(side="left", padx=8)
        ttk.Button(penceref, text="Pencereyi Yenile", command=self.refresh_windows).pack(side="left", padx=8)
        ttk.Button(penceref, text="OCR Test", command=self.do_ocr_test, bootstyle="success-outline").pack(side="left", padx=8)
        metodf = ttk.Labelframe(main, text=" OCR Metod Seçimi ", padding=8, bootstyle="secondary")
        metodf.pack(fill="x", pady=(0,6))
        for label, val in self.OCR_METHODS:
            ttk.Radiobutton(metodf, text=label, variable=self.selected_ocr_method, value=val, bootstyle="info").pack(side="left", padx=8)
        self.img_preview = ttk.Label(main)
        self.img_preview.pack(pady=(2,6))
        row2 = ttk.Frame(main)
        row2.pack(fill="x")
        ttk.Label(row2, text="Son Okunan:", font=("Segoe UI", 10)).pack(side="left", padx=(2,3))
        ttk.Label(row2, textvariable=self.ocr_value, font=("Consolas", 16, "bold"), bootstyle="info").pack(side="left", padx=(0,12))
        ag_frame = ttk.Labelframe(main, text=" Ağ Takibi ", padding=8, bootstyle="primary")
        ag_frame.pack(fill="x", pady=(0,6))
        ttk.Label(ag_frame, text="Ethernet Arayüzü:", font=("Segoe UI", 10, "bold")).pack(side="left", padx=(2,8))
        eth_combo = ttk.Combobox(ag_frame, values=self.ethernet_list, textvariable=self.selected_eth, state="readonly", width=20)
        eth_combo.pack(side="left", padx=4)
        eth_combo.bind("<<ComboboxSelected>>", lambda e: self.reset_speed())
        kota_lbl = ttk.Label(ag_frame, textvariable=self.kota_var, font=("Segoe UI", 11, "bold"), bootstyle="warning")
        kota_lbl.pack(side="left", padx=(24, 6))
        ttk.Label(ag_frame, textvariable=self.kota_timer_var, font=("Segoe UI", 10), bootstyle="info").pack(side="left", padx=(2,8))
        ttk.Button(ag_frame, text="Kota Yenile", command=self.refresh_kota, bootstyle="outline-secondary").pack(side="right", padx=8)
        speed_frame = ttk.Frame(main)
        speed_frame.pack(fill="x")
        fig = Figure(figsize=(8.5, 2.3), dpi=100, facecolor="#23272E")
        self.ax_down = fig.add_subplot(211)
        self.ax_up = fig.add_subplot(212)
        self.ax_down.set_facecolor("#23272E")
        self.ax_up.set_facecolor("#23272E")
        self.down_line, = self.ax_down.plot(self.down_data, color="#00b894", linewidth=2)
        self.ax_down.set_title("İndirme (Mbps)", color="#00b894", fontsize=10)
        self.ax_down.set_ylim(0, 100)
        self.ax_down.set_xticks([])
        self.up_line, = self.ax_up.plot(self.up_data, color="#0984e3", linewidth=2)
        self.ax_up.set_title("Yükleme (Mbps)", color="#0984e3", fontsize=10)
        self.ax_up.set_ylim(0, 20)
        self.ax_up.set_xticks([])
        fig.tight_layout()
        canvas = FigureCanvasTkAgg(fig, master=speed_frame)
        canvas.get_tk_widget().pack(fill="x", pady=2)
        self.speed_canvas = canvas
        statf = ttk.Frame(main)
        statf.pack(fill="x")
        ttk.Label(statf, text="İndirme Hızları | ", bootstyle="info", font=("Segoe UI", 10, "bold")).pack(side="left")
        self.lbl_down_stats = ttk.Label(statf, text="Min: --  Max: --  Ortalama: --", font=("Consolas", 10))
        self.lbl_down_stats.pack(side="left", padx=(0, 18))
        ttk.Label(statf, text="Yükleme Hızları | ", bootstyle="info", font=("Segoe UI", 10, "bold")).pack(side="left")
        self.lbl_up_stats = ttk.Label(statf, text="Min: --  Max: --  Ortalama: --", font=("Consolas", 10))
        self.lbl_up_stats.pack(side="left")
        ind_frame = ttk.Labelframe(main, text=" İndirme Takip ve İlerleme ", padding=8, bootstyle="success")
        ind_frame.pack(fill="x", pady=(16,8))
        row = ttk.Frame(ind_frame)
        row.pack(fill="x", pady=(2,0))
        ttk.Button(row, text="OCR Başlat", command=self.toggle_ocr, bootstyle="success").pack(side="left", padx=(2,6))
        ttk.Button(row, text="OCR Durdur", command=self.stop_ocr, bootstyle="danger").pack(side="left")
        self.lbl_ocr_status = ttk.Label(row, text="", font=("Segoe UI", 9, "italic"))
        self.lbl_ocr_status.pack(side="left", padx=(10,0))
        row2 = ttk.Frame(ind_frame)
        row2.pack(fill="x")
        ttk.Label(row2, text="Son Okunan:", font=("Segoe UI", 10)).pack(side="left", padx=(2,3))
        ttk.Label(row2, textvariable=self.ocr_value, font=("Consolas", 16, "bold"), bootstyle="info").pack(side="left", padx=(0,12))
        ttk.Checkbutton(ind_frame, text="Otomatik MB/GB Geçiş", variable=self.otomatik_gecis, command=self.otomatik_toggle, bootstyle="success-round-toggle").pack(anchor="w", padx=2, pady=(0,3))
        secimf = ttk.Frame(ind_frame)
        secimf.pack(anchor="w")
        ttk.Label(secimf, text="Birim:", font=("Segoe UI", 10)).pack(side="left")
        ttk.Radiobutton(secimf, text="MB", variable=self.unit_mode, value="mb", bootstyle="info").pack(side="left")
        ttk.Radiobutton(secimf, text="GB", variable=self.unit_mode, value="gb", bootstyle="info").pack(side="left", padx=(8, 0))
        row3 = ttk.Frame(ind_frame)
        row3.pack(anchor="w", pady=(6, 0))
        ttk.Label(row3, text="Toplam Boyut:", font=("Segoe UI", 10)).pack(side="left")
        ttk.Entry(row3, textvariable=self.toplam_boyut, width=10).pack(side="left", padx=(2,4))
        ttk.Radiobutton(row3, text="MB", variable=self.toplam_birim, value="mb", bootstyle="info").pack(side="left")
        ttk.Radiobutton(row3, text="GB", variable=self.toplam_birim, value="gb", bootstyle="info").pack(side="left", padx=(8, 0))
        ttk.Label(ind_frame, text="İlerleme:", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(6,0))
        ttk.Progressbar(ind_frame, variable=self.progress_value, maximum=100, bootstyle="striped info", length=800).pack(fill="x", padx=2, pady=(0,2))
        ttk.Label(ind_frame, textvariable=self.percent_text, font=("Consolas", 12)).pack(anchor="w", padx=2)
        ttk.Label(ind_frame, text="Ortalama Hıza Göre Bitiş:", font=("Segoe UI", 10)).pack(anchor="w")
        ttk.Label(ind_frame, textvariable=self.bitirme_tahmini, font=("Consolas", 10)).pack(anchor="w")
        ttk.Label(ind_frame, text="Anlık Hıza Göre Bitiş:", font=("Segoe UI", 10)).pack(anchor="w", pady=(3, 0))
        ttk.Label(ind_frame, textvariable=self.hiz_tahmini, font=("Consolas", 10)).pack(anchor="w", pady=(0, 8))
        olcumf = ttk.Labelframe(main, text=" OCR Tabanlı Hız Ölçümü ", padding=8, bootstyle="info")
        olcumf.pack(fill="x", pady=(0,8))
        row4 = ttk.Frame(olcumf)
        row4.pack(anchor="w")
        ttk.Label(row4, text="Süre:", font=("Segoe UI", 10)).pack(side="left")
        ttk.Entry(row4, textvariable=self.hiz_olcum_sure, width=4).pack(side="left", padx=(2, 4))
        ttk.Button(row4, text="Ölç", command=self.olcum_baslat).pack(side="left")
        ttk.Label(row4, textvariable=self.hiz_olcum_geri_sayim, font=("Segoe UI", 10, "bold"), bootstyle="warning").pack(side="left", padx=(8,0))
        ttk.Label(olcumf, text="Sonuç (MB):", font=("Segoe UI", 10)).pack(anchor="w", pady=(2,0))
        ttk.Label(olcumf, textvariable=self.hiz_olcum_sonuc, font=("Consolas", 12, "bold")).pack(anchor="w")
        hzf = ttk.Frame(olcumf)
        hzf.pack(anchor="w", pady=(0,2))
        ttk.Label(hzf, text="Min:", font=("Segoe UI", 10)).pack(side="left")
        ttk.Label(hzf, textvariable=self.hiz_olcum_min, font=("Consolas", 10)).pack(side="left", padx=(2, 12))
        ttk.Label(hzf, text="Max:", font=("Segoe UI", 10)).pack(side="left")
        ttk.Label(hzf, textvariable=self.hiz_olcum_max, font=("Consolas", 10)).pack(side="left", padx=(2, 12))
        ttk.Label(hzf, text="Ortalama:", font=("Segoe UI", 10)).pack(side="left")
        ttk.Label(hzf, textvariable=self.hiz_olcum_avg, font=("Consolas", 10)).pack(side="left", padx=(2, 0))
        ttk.Button(main, text="Mini Overlay Göster", command=self.mini_overlay_goster, bootstyle="info").pack(pady=8)
    # ... (devamı aşağıda)
    def refresh_windows(self):
        self.all_windows = list_all_windows()
        sel = self.selected_window_title.get()
        self.pencere_combo['values'] = [w[0] for w in self.all_windows]
        if sel in [w[0] for w in self.all_windows]:
            self.pencere_combo.set(sel)
        else:
            self.pencere_combo.current(0)
    def set_selected_hwnd(self):
        idx = self.pencere_combo.current()
        if idx == -1:
            messagebox.showerror("Hata", "Bir pencere seçmelisiniz.")
            return
        self.selected_hwnd = self.all_windows[idx][1]
        messagebox.showinfo("Başarılı", f"Pencere seçildi: {self.all_windows[idx][0]}")
        self.preview_window_image_snapshot()
    def preview_window_image_snapshot(self):
        if not self.selected_hwnd:
            return
        left, top, right, bottom = win32gui.GetWindowRect(self.selected_hwnd)
        try:
            img_pil = ImageGrab.grab(bbox=(left, top, right, bottom))
            img_pil.thumbnail((400, 250))
            self.tk_img = ImageTk.PhotoImage(img_pil)
            self.img_preview.config(image=self.tk_img)
        except Exception:
            self.img_preview.config(text="Pencere alınamadı!", image="")
    def select_crop_area_snapshot(self):
        if not self.selected_hwnd:
            messagebox.showerror("Hata", "Önce pencere seçmelisiniz!")
            return
        left, top, right, bottom = win32gui.GetWindowRect(self.selected_hwnd)
        try:
            img_pil = ImageGrab.grab(bbox=(left, top, right, bottom))
            Cropper(self, img_pil, self.on_crop_selected)
        except Exception:
            messagebox.showerror("Hata", "Pencere alınamadı!")
    def on_crop_selected(self, crop_rect):
        self.crop_rect = crop_rect
        messagebox.showinfo("Alan Seçildi", f"Seçilen alan: {self.crop_rect}")
    def do_ocr_test(self):
        error_text = ""
        ocr_val = ""
        img_np = None
        img_pil = None
        method = self.selected_ocr_method.get()
        if not self.selected_hwnd or not self.crop_rect:
            messagebox.showerror("Hata", "Pencere ve alan seçmelisiniz!")
            return
        try:
            if method == "printwindow":
                img_np, result = capture_with_printwindow(self.selected_hwnd, self.crop_rect)
                if not result:
                    error_text = "PrintWindow başarısız oldu."
                if img_np is not None and img_np.size > 0 and np.mean(img_np) > 10:
                    ocr_val = ocr_from_image(img_np)
                    try:
                        img_pil = Image.fromarray(cv2.cvtColor(img_np, cv2.COLOR_BGR2RGB))
                    except Exception:
                        img_pil = Image.new("RGB", (100, 40), color=(220,0,0))
                else:
                    error_text += " Görüntü yok veya siyah."
            elif method == "bitblt":
                img_np = capture_with_bitblt(self.selected_hwnd, self.crop_rect)
                if img_np is not None and img_np.size > 0 and np.mean(img_np) > 10:
                    ocr_val = ocr_from_image(img_np)
                    try:
                        img_pil = Image.fromarray(cv2.cvtColor(img_np, cv2.COLOR_BGR2RGB))
                    except Exception:
                        img_pil = Image.new("RGB", (100, 40), color=(220,0,0))
                else:
                    error_text = "BitBlt ile alınan görüntü yok veya siyah."
            elif method == "imagegrab":
                img_np = capture_with_imagegrab(self.selected_hwnd, self.crop_rect)
                if img_np is not None and img_np.size > 0:
                    ocr_val = ocr_from_image(img_np)
                    try:
                        img_pil = Image.fromarray(cv2.cvtColor(img_np, cv2.COLOR_BGR2RGB))
                    except Exception:
                        img_pil = Image.new("RGB", (100, 40), color=(220,0,0))
                else:
                    error_text = "Ekran görüntüsü alınamadı."
            elif method == "dwm":
                try:
                    img_np = capture_with_dwm(self.selected_hwnd, self.crop_rect)
                    if img_np is not None and img_np.size > 0:
                        ocr_val = ocr_from_image(img_np)
                        img_pil = Image.fromarray(cv2.cvtColor(img_np, cv2.COLOR_BGR2RGB))
                    else:
                        error_text = "DWM ile alınan görüntü yok."
                except Exception as e:
                    error_text = f"DWM yöntemi desteklenmiyor. {str(e)}"
            else:
                error_text = "Tanımsız metod."
        except Exception as e:
            error_text += f" Hata: {str(e)}"
        if img_pil is None:
            img_pil = Image.new("RGB", (200, 80), color=(220,0,0))
        crop_draw_rect = (0, 0, img_pil.width-1, img_pil.height-1)
        OcrTestWindow(self, img_pil.copy(), crop_draw_rect, ocr_val, error_text, method)
        self.ocr_value.set(ocr_val if ocr_val else "0")
    def get_ethernet_list(self):
        nics = psutil.net_if_stats()
        return [i for i in nics if nics[i].isup and not i.lower().startswith("lo")]
    def reset_speed(self):
        self.down_data = [0.0]*60
        self.up_data = [0.0]*60
        self.last_counters = None
    def update_speed(self):
        iface = self.selected_eth.get()
        counters = psutil.net_io_counters(pernic=True).get(iface)
        now = time.time()
        if counters is None:
            self.after(1000, self.update_speed)
            return
        if self.last_counters is None:
            self.last_counters = (counters.bytes_recv, counters.bytes_sent, now)
            self.after(1000, self.update_speed)
            return
        prev_recv, prev_sent, prev_time = self.last_counters
        delta_t = now - prev_time
        down_bps = (counters.bytes_recv - prev_recv) / delta_t if delta_t > 0 else 0
        up_bps = (counters.bytes_sent - prev_sent) / delta_t if delta_t > 0 else 0
        down_mbps = down_bps * 8 / 1_000_000
        up_mbps = up_bps * 8 / 1_000_000
        self.down_data = self.down_data[1:] + [max(0.0, down_mbps)]
        self.up_data = self.up_data[1:] + [max(0.0, up_mbps)]
        self.down_stats = {
            "min": min(self.down_data),
            "max": max(self.down_data),
            "avg": sum(self.down_data)/len(self.down_data)
        }
        self.up_stats = {
            "min": min(self.up_data),
            "max": max(self.up_data),
            "avg": sum(self.up_data)/len(self.up_data)
        }
        self.down_line.set_ydata(self.down_data)
        self.up_line.set_ydata(self.up_data)
        self.ax_down.set_ylim(0, max(60, max(self.down_data)+10))
        self.ax_up.set_ylim(0, max(10, max(self.up_data)+2))
        self.speed_canvas.draw_idle()
        self.lbl_down_stats.config(
            text=f"Min: {self.down_stats['min']:.2f}  Max: {self.down_stats['max']:.2f}  Ortalama: {self.down_stats['avg']:.2f} Mbps"
        )
        self.lbl_up_stats.config(
            text=f"Min: {self.up_stats['min']:.2f}  Max: {self.up_stats['max']:.2f}  Ortalama: {self.up_stats['avg']:.2f} Mbps"
        )
        self.last_counters = (counters.bytes_recv, counters.bytes_sent, now)
        self.after(1000, self.update_speed)
    def refresh_kota(self):
        threading.Thread(target=self.kota_cek, daemon=True).start()
    def kota_cek(self):
        try:
            self.kota_var.set("Kalan Kota: Bağlanıyor...")
            resp = requests.get("https://wifi.gsb.gov.tr/", timeout=10, verify=False)
            match = re.search(r'Total Remaining Quota \(MB\):<\/label><\/td>\s*<td><label[^>]*>([\d\.]+)<', resp.text)
            if match:
                self.kalan_kota = float(match.group(1))
                self.kota_var.set(f"Kalan Kota: {self.kalan_kota:.2f} MB")
            else:
                self.kota_var.set("Kota bulunamadı!")
        except Exception:
            self.kota_var.set("Kota alınamadı!")
        self.kota_son_cekilis = time.time()
        self.kota_sayac = 60
    def update_kota_timer(self):
        now = time.time()
        if self.kota_son_cekilis:
            elapsed = int(now - self.kota_son_cekilis)
            kalan = max(0, 60 - elapsed)
            self.kota_sayac = kalan
            self.kota_timer_var.set(f"Yenilemeye: {kalan:02d} sn")
            if kalan <= 0:
                self.refresh_kota()
        self.after(1000, self.update_kota_timer)
    def otomatik_toggle(self):
        if self.otomatik_gecis.get():
            self.unit_mode.set("mb")
    def update_progress(self):
        indirilen = parse_float(self.ocr_value.get())
        toplam = parse_float(self.toplam_boyut.get())
        unit = self.unit_mode.get()
        toplam_unit = self.toplam_birim.get()
        if self.otomatik_gecis.get():
            if indirilen >= 1024:
                unit = "gb"
                indirilen = indirilen / 1024
        if unit != toplam_unit:
            if unit == "mb" and toplam_unit == "gb":
                indirilen = indirilen / 1024
            elif unit == "gb" and toplam_unit == "mb":
                indirilen = indirilen * 1024
        percent = (indirilen / toplam * 100) if toplam > 0 else 0
        percent = min(100, max(0, percent))
        self.progress_value.set(percent)
        self.percent_text.set(f"%{percent:.2f}")
        ort_hiz = self.down_stats["avg"] / 8 * 1_000_000 / 1024 / 1024
        hiz_son = self.down_data[-1] / 8 * 1_000_000 / 1024 / 1024
        kalan = max(0, toplam - indirilen)
        self.bitirme_tahmini.set(time_format(kalan / ort_hiz) if ort_hiz > 0 else "--:--:--")
        self.hiz_tahmini.set(time_format(kalan / hiz_son) if hiz_son > 0 else "--:--:--")
        self.after(1000, self.update_progress)
    def toggle_ocr(self):
        if self.ocr_thread_run:
            self.ocr_thread_run = False
            self.lbl_ocr_status.config(text="Durduruldu.")
        else:
            if not self.selected_hwnd or not self.crop_rect:
                messagebox.showerror("Hata", "Pencere ve alan seçmelisiniz!")
                return
            self.ocr_thread_run = True
            self.lbl_ocr_status.config(text="Çalışıyor...")
            threading.Thread(target=self.ocr_loop, daemon=True).start()
    def stop_ocr(self):
        self.ocr_thread_run = False
        self.lbl_ocr_status.config(text="Durduruldu.")
    def ocr_loop(self):
        while self.ocr_thread_run:
            try:
                method = self.selected_ocr_method.get()
                img_np = None
                if method == "printwindow":
                    img_np, result = capture_with_printwindow(self.selected_hwnd, self.crop_rect)
                elif method == "bitblt":
                    img_np = capture_with_bitblt(self.selected_hwnd, self.crop_rect)
                elif method == "imagegrab":
                    img_np = capture_with_imagegrab(self.selected_hwnd, self.crop_rect)
                elif method == "dwm":
                    try:
                        img_np = capture_with_dwm(self.selected_hwnd, self.crop_rect)
                    except Exception:
                        img_np = None
                if img_np is not None and img_np.size > 0:
                    text = ocr_from_image(img_np)
                    val = parse_float(text)
                    self.ocr_value.set(str(val))
                else:
                    self.ocr_value.set("0")
            except Exception as e:
                self.ocr_value.set("0")
            time.sleep(2)
    def olcum_baslat(self):
        if self.hiz_olcum_aktif.get():
            return
        self.hiz_olcum_aktif.set(True)
        self.hiz_olcum_geri_sayim.set(f" Ölçülüyor... [{self.hiz_olcum_sure.get()}]")
        self.hiz_olcum_ilk_deger = parse_float(self.ocr_value.get())
        self.hiz_olcum_son_deger = None
        self.lbl_ocr_status.config(text=f"Başlangıç: {self.hiz_olcum_ilk_deger:.2f}")
        threading.Thread(target=self.olcum_thread, daemon=True).start()
    def olcum_thread(self):
        sure = self.hiz_olcum_sure.get()
        for i in range(sure, 0, -1):
            self.hiz_olcum_geri_sayim.set(f" Ölçülüyor... [{i}]")
            time.sleep(1)
        self.hiz_olcum_son_deger = parse_float(self.ocr_value.get())
        delta = max(0, self.hiz_olcum_son_deger - self.hiz_olcum_ilk_deger)
        self.hiz_olcum_sonuc.set(f"{delta:.2f} MB")
        try:
            toplam = parse_float(self.toplam_boyut.get())
            kalan = max(0, toplam - self.hiz_olcum_son_deger)
            if delta > 0:
                kalan_oran = kalan / delta
                tahmini_saniye = kalan_oran * sure
                self.bitirme_tahmini.set(time_format(tahmini_saniye))
                self.lbl_ocr_status.config(
                    text=f"Başlangıç: {self.hiz_olcum_ilk_deger:.2f} | Son: {self.hiz_olcum_son_deger:.2f} | "
                         f"Fark: {delta:.2f} | Tahmini bitiş: {time_format(tahmini_saniye)}"
                )
            else:
                self.bitirme_tahmini.set("--:--:--")
                self.lbl_ocr_status.config(text="İlerleme yok, tahmin yapılamıyor.")
        except Exception:
            self.bitirme_tahmini.set("--:--:--")
        self.hiz_olcum_aktif.set(False)
        self.hiz_olcum_geri_sayim.set("")
    def mini_overlay_goster(self):
        if self.mini and self.mini.winfo_exists():
            return
        self.mini = tk.Toplevel(self)
        self.mini.title("Mini Takip")
        self.mini.attributes("-topmost", True)
        self.mini.geometry("320x170+100+100")
        self.mini.resizable(False, False)
        ttk.Label(self.mini, text="İndirme Hızı (Mbps):", font=("Segoe UI", 10)).pack()
        ttk.Label(self.mini, textvariable=self.lbl_down_stats["text"], font=("Consolas", 11)).pack()
        ttk.Label(self.mini, text="İlerleme:", font=("Segoe UI", 10)).pack()
        ttk.Progressbar(self.mini, variable=self.progress_value, maximum=100, length=200).pack()
        ttk.Label(self.mini, textvariable=self.percent_text, font=("Consolas", 11)).pack()
        ttk.Label(self.mini, text="Kalan Süre:", font=("Segoe UI", 10)).pack()
        ttk.Label(self.mini, textvariable=self.bitirme_tahmini, font=("Consolas", 11)).pack()
        self.mini.bind("<Button-1>", lambda e: self.mini_pencere_kapat())
    def mini_pencere_kapat(self):
        if self.mini:
            self.mini.destroy()
            self.deiconify()
    def on_close(self):
        self.ocr_thread_run = False
        self.destroy()

if __name__ == "__main__":
    app = TumIndirmeIzleyici()
    app.mainloop()
