"""
Talaba.py — Talaba kompyuterida ishlaydigan kiosk-launcher.

MUHIM TUZATISHLAR (eski versiyaga nisbatan):

1) Win/Alt+Tab tugmalarini yoqish-o'chirish XATOSI tuzatildi.
   Avvalgi kodda faqat "win=True" kelganda hotkey OLIB TASHLANARDI,
   lekin keyinchalik "win=False" kelganda QAYTADAN BLOKLANMAS edi -
   shu sababli bir marta yoqilgan Win tugmasi abadiy ochiq qolib
   ketardi. ENDI: har safar konfiguratsiya kelganda, avval BARCHA
   xavfsizlik hotkey'lari batamom OLIB TASHLANADI (keyboard.unhook_all),
   so'ngra joriy konfiguratsiyaga mos ravishda QAYTADAN TO'LIQ
   QURILADI. Shu "clean slate" usuli tufayli True->False->True kabi
   qaytarishlar tartibi endi muhim emas - har doim to'g'ri natija
   chiqadi.

2) Kiosk rejimi (block) o'chirilganda - BARCHA maxsus tugmalarga
   (Win, Alt+Tab, Ctrl+Esc va h.k.) ruxsat beriladi, alohida
   sozlamalardan qat'iy nazar.

3) Alt+Tab uchun alohida "alt_tab" konfiguratsiya kaliti qo'shildi
   (Win tugmasi kabi, mustaqil yoqilib-o'chiriladi).

4) Dasturni orqaga tushirish (F11 -> root.lower()) uchun alohida
   "lower" konfiguratsiya kaliti qo'shildi.

5) Dastur ishga tushganda CTkInputDialog orqali talabaning ismi
   so'raladi, server bilan aloqada kompyuter nomi o'rniga shu ism
   ishlatiladi.
"""

import os
import sys
import json
import ctypes
import platform
import subprocess
from dataclasses import dataclass
from itertools import cycle
from threading import Thread

import customtkinter as ctk
import keyboard
import pywinstyles

from client_agent import ClientAgent
from rasm_tahrir import get_program_icon, get_wallpaper

CONFIG_PATH = "config.json"


# ---------------------------------------------------------------------------
# KONSOL OYNASINI YASHIRISH
# ---------------------------------------------------------------------------
# Talaba kompyuterida qora konsol oynasi ko'rinib turmasligi uchun.
# DIQQAT: bu faqat OYNANI yashiradi, print() funksiyasi baribir
# ishlayveradi (faqat ko'rinmas konsolga yoziladi) - shu sababli
# log faylga alohida yo'naltirish shart emas, debugging uchun kerak
# bo'lsa, konsolni vaqtincha qaytadan ko'rsatish (ShowWindow(hwnd, 1))
# orqali tekshirish mumkin.
if platform.system() == "Windows":
    try:
        _console_hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if _console_hwnd:
            ctypes.windll.user32.ShowWindow(_console_hwnd, 0)  # SW_HIDE
    except Exception:
        pass


# ---------------------------------------------------------------------------
# MA'LUMOTLAR MODELI
# ---------------------------------------------------------------------------

@dataclass
class ProgramEntry:
    name: str
    path: str
    allowed: bool = False
    icon: str = ""


# ---------------------------------------------------------------------------
# ASOSIY OYNA VA TALABA ISMINI SO'RASH
# ---------------------------------------------------------------------------

root = ctk.CTk()
root.withdraw()  # ism so'ralguncha to'liq ekran ochilmasin

_ism_oynasi = ctk.CTkInputDialog(text="Ismingizni kiriting:", title="Talaba")
TALABA_ISMI = (_ism_oynasi.get_input() or "").strip() or platform.node() or "Noma'lum"

root.deiconify()
root.attributes("-fullscreen", True)
root.attributes("-topmost", True)

olcham = root.winfo_screenwidth(), root.winfo_screenheight()


# ---------------------------------------------------------------------------
# FON RASMI (wallpaper, Alt+F5 orqali aylanadi)
# ---------------------------------------------------------------------------

folder = "fon"
raslar = [
    os.path.join(folder, f) for f in os.listdir(folder)
    if os.path.splitext(f)[1].lower() in {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp"}
]
_rasm_aylanma = cycle(raslar) if raslar else cycle(["fon/dark.png"])

wp = ctk.CTkLabel(root, text="", image=get_wallpaper("fon/dark.png", olcham))
wp.place(x=0, y=0)


def keyingi_rasm():
    return next(_rasm_aylanma)


# ---------------------------------------------------------------------------
# DASTUR ISHGA TUSHIRISH
# ---------------------------------------------------------------------------

def launch_program(program: ProgramEntry):
    if not program.allowed:
        return
    if not os.path.exists(program.path):
        print(f"Dastur topilmadi: {program.path}")
        return
    try:
        subprocess.Popen([program.path])
        root.lower()  # dastur ochilganda launcher doim orqaga o'tadi (ruxsat shart emas)
    except Exception as e:
        print(f"Dasturni ishga tushirishda xatolik: {e}")


# ---------------------------------------------------------------------------
# TUGMALARNI BLOKLASH / OGOHLANTIRISH
# ---------------------------------------------------------------------------

def block_and_warn(combo):
    """Bloklangan kombinatsiya bosilganda chaqiriladi."""
    if combo == "alt+f5":
        wp.configure(image=get_wallpaper(keyingi_rasm(), olcham))
        return
    if combo in ("chiqish", "ctrl+alt+shift+break"):
        agent.stop()
        sys.exit(0)
    print(f"'{combo}' bloklangan - bu amal taqiqlangan!")


root.protocol("WM_DELETE_WINDOW", lambda: block_and_warn("chiqish"))

# Doim ishlaydigan, hech qachon bloklanmaydigan tugmalar:
#   alt+f5               - fon rasmini almashtirish
#   ctrl+alt+shift+break - admin uchun chiqish (kiosk rejimidan qat'iy nazar)
ALWAYS_ON_KEYS = ("alt+f5", "ctrl+alt+shift+break")

# SECURITY_KEYS - Win, Alt+Tab kabi xavfsizlik tugmalari (o'zgarishsiz qoladi)
SECURITY_KEYS = ("windows", "alt+f4", "alt+tab", "ctrl+esc",
                  "ctrl+alt+delete", "ctrl+shift+esc")


def apply_key_restrictions(cfg: dict):
    """
    Konfiguratsiya o'zgarganda (yoki dastur birinchi marta ishga
    tushganda) chaqiriladi.

    MUHIM: har safar AVVAL barcha hotkey'lar butunlay olib tashlanadi
    (keyboard.unhook_all), so'ngra joriy konfiguratsiyaga mos holda
    QAYTADAN boshidan quriladi. Shu sababli oldingi holatdan qat'iy
    nazar (avval True bo'lib, keyin False qilingan bo'lsa ham),
    natija har doim TO'G'RI bo'ladi.
    """
    keyboard.unhook_all()

    # 1) Doim ishlaydigan tugmalar - kiosk holatidan qat'iy nazar
    for combo in ALWAYS_ON_KEYS:
        keyboard.add_hotkey(combo, lambda c=combo: block_and_warn(c), suppress=True)

    block_mode = cfg.get("block", False)

    if not block_mode:
        # Kiosk rejimi O'CHIRILGAN - xavfsizlik tugmalarining HECH BIRI
        # bloklanmaydi, alohida sozlamalardan (win, alt_tab) qat'iy nazar
        return

    allow_win = cfg.get("win", False)
    allow_alt_tab = cfg.get("alt_tab", False)

    for combo in SECURITY_KEYS:
        if combo == "windows" and allow_win:
            continue  # ruxsat berilgan - bloklamaymiz
        if combo == "alt+tab" and allow_alt_tab:
            continue  # ruxsat berilgan - bloklamaymiz
        keyboard.add_hotkey(combo, lambda c=combo: block_and_warn(c), suppress=True)


# ---------------------------------------------------------------------------
# DASTURLAR PANELI
# ---------------------------------------------------------------------------

tugmalar = {}


def _setup_program_grid():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        raw = json.load(f)

    # Oyna ko'rinishini boshqarish (kiosk rejimi yoqilgan/o'chirilganiga qarab)
    if raw.get("block"):
        root.deiconify()
    else:
        root.withdraw()

    # Klaviatura cheklovlarini joriy konfiguratsiyaga mos ravishda
    # to'liq qaytadan quramiz (bug-fix - yuqoridagi izohga qarang)
    apply_key_restrictions(raw)

    dasturlar = [ProgramEntry(**item) for item in raw.get("programs", [])]
    allowed_programs = [i for i in dasturlar if i.allowed]

    if not allowed_programs:
        t = ctk.CTkLabel(
            root,
            text="Ruxsat etilgan dasturlar topilmadi.",
            font=("Arial", 22), text_color="white",
            bg_color="#4b3621",
        )
        t.pack(pady=30)
        tugmalar["0:0"] = t
        pywinstyles.set_opacity(t, color="#4b3621")
        return

    columns = 4
    for idx, program in enumerate(allowed_programs):
        col, row = divmod(idx, columns)  # chap→o'ng, keyin pastga
        icon = get_program_icon(program)

        btn = ctk.CTkButton(
            root,
            text=program.name,
            image=icon,
            compound="top",
            width=50, height=50,
            font=("Arial", 14),
            fg_color="#4b3621",
            bg_color="#4b3621",
            hover_color="#3b3b3b",
            command=lambda p=program: launch_program(p),
        )
        btn.grid(row=row, column=col, padx=10, pady=10, sticky="nw")
        tugmalar[f"{col}:{row}"] = btn
        pywinstyles.set_opacity(btn, color="#4b3621")


def yangilash():
    """Serverdan yangi konfiguratsiya kelganda chaqiriladi."""
    for key in list(tugmalar.keys()):
        tugmalar[key].destroy()
        del tugmalar[key]
    _setup_program_grid()


_setup_program_grid()


# ---------------------------------------------------------------------------
# SERVERGA ULANISH (talaba kiritgan ism bilan)
# ---------------------------------------------------------------------------

agent = ClientAgent(reload=yangilash, name=TALABA_ISMI,
                     on_lower=lambda: root.after(0, root.lower))
Thread(target=agent.run, daemon=True).start()


# ---------------------------------------------------------------------------
# F11 - DASTURNI ORQAGA TUSHIRISH (cheklovsiz, doim ishlaydi)
# ---------------------------------------------------------------------------

root.bind("<F11>", lambda e: root.lower())

root.mainloop()
