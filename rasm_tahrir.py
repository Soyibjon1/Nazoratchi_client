import os
from typing import Optional

from PIL import Image, ImageTk
import customtkinter as ctk

try:
    import win32gui
    import win32ui
    PYWIN32_AVAILABLE = True
except ImportError:
    PYWIN32_AVAILABLE = False

DEFAULT_ICON_SIZE = (35, 35)


def extract_icon_from_exe(exe_path: str, size=DEFAULT_ICON_SIZE) -> Optional[Image.Image]:
    """
    .exe faylning ichidan ikonkasini ajratib oladi va PIL Image qaytaradi.
    Agar pywin32 o'rnatilmagan bo'lsa yoki xatolik yuzaga kelsa, None qaytaradi.
    """
    if not PYWIN32_AVAILABLE or not os.path.exists(exe_path):
        return None

    try:
        large, small = win32gui.ExtractIconEx(exe_path, 0)
        if not large and not small:
            return None
        hicon = large[0] if large else small[0]

        hdc = win32ui.CreateDCFromHandle(win32gui.GetDC(0))
        hbmp = win32ui.CreateBitmap()
        hbmp.CreateCompatibleBitmap(hdc, size[0], size[1])
        hdc_mem = hdc.CreateCompatibleDC()
        hdc_mem.SelectObject(hbmp)
        hdc_mem.DrawIcon((0, 0), hicon)

        bmpinfo = hbmp.GetInfo()
        bmpstr = hbmp.GetBitmapBits(True)
        img = Image.frombuffer(
            "RGBA",
            (bmpinfo["bmWidth"], bmpinfo["bmHeight"]),
            bmpstr, "raw", "BGRA", 0, 1,
        )

        for h in large:
            win32gui.DestroyIcon(h)
        for h in small:
            win32gui.DestroyIcon(h)

        return img.resize(size)
    except Exception:
        return None
def get_wallpaper(path:str, size:tuple[int, int]):
    im=Image.open(path)
    im=im.resize(size)
    return ImageTk.PhotoImage(im)

def make_placeholder_icon(size=DEFAULT_ICON_SIZE) -> Image.Image:
    """Ikonka topilmasa, oddiy kvadrat placeholder yaratadi."""
    return Image.new("RGBA", size, (90, 90, 90, 255))


def get_program_icon(program) -> "ctk.CTkImage":
    """
    Dastur uchun ikonka tayyorlaydi (launcher.py'dagi bilan bir xil mantiq):
      1) program.icon - alohida belgilangan rasm fayli (agar mavjud bo'lsa)
      2) program.path - exe ichidagi ikonka (Windows'da avtomatik olinadi)
      3) hech narsa topilmasa - placeholder kvadrat

    `program` - .icon va .path atributlariga ega har qanday obyekt
    (odatda ProgramEntry dataclass'i, lekin majburiy emas).
    """
    img = None

    if program.icon and os.path.exists(program.icon):
        try:
            img = Image.open(program.icon).convert("RGBA").resize(DEFAULT_ICON_SIZE)
        except Exception:
            img = None

    if img is None:
        img = extract_icon_from_exe(program.path)

    if img is None:
        img = make_placeholder_icon()

    return ctk.CTkImage(light_image=img, dark_image=img, size=DEFAULT_ICON_SIZE)