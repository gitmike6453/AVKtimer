import os
import sys
import time
import json
import threading
import subprocess
from tkinter import Tk, Label, Entry, Button, Frame

SISTEMA_MAC = (sys.platform == "darwin")

if getattr(sys, 'frozen', False):
    caminho_base = sys._MEIPASS
else:
    caminho_base = os.path.dirname(os.path.abspath(__file__))


def obter_pasta_dados_utilizador():
    """A mesma pasta de dados do AVKtimer principal, para partilhar o mesmo espaço gravável."""
    if SISTEMA_MAC:
        pasta = os.path.join(os.path.expanduser("~/Library/Application Support"), "AVKtimer")
    else:
        pasta = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "AVKtimer")
    os.makedirs(pasta, exist_ok=True)
    return pasta


CAMINHO_CONFIG = os.path.join(obter_pasta_dados_utilizador(), "vigia_slides_config.json")

vigia_ativo = False
ultimo_slide_enviado = None


def carregar_config():
    try:
        if os.path.exists(CAMINHO_CONFIG):
            with open(CAMINHO_CONFIG, "r", encoding="utf-8") as ficheiro:
                return json.load(ficheiro).get("ip_regie", "")
    except Exception:
        pass
    return ""


def gravar_config(ip):
    try:
        with open(CAMINHO_CONFIG, "w", encoding="utf-8") as ficheiro:
            json.dump({"ip_regie": ip}, ficheiro)
    except Exception:
        pass


def detetar_slide_powerpoint():
    """Lê o slide atual de uma apresentação em curso no PowerPoint (Windows, via COM)."""
    try:
        import win32com.client
        aplicacao_ppt = win32com.client.GetActiveObject("PowerPoint.Application")
        if aplicacao_ppt.SlideShowWindows.Count > 0:
            return int(aplicacao_ppt.SlideShowWindows(1).View.CurrentShowPosition)
    except Exception:
        pass
    return None


def detetar_slide_keynote():
    """Lê o slide atual de uma apresentação em curso no Keynote (macOS, via AppleScript)."""
    try:
        script_presente = 'tell application "System Events" to (name of processes) contains "Keynote"'
        resultado = subprocess.run(["osascript", "-e", script_presente], capture_output=True, text=True, timeout=1.5)
        if "true" not in resultado.stdout.strip().lower():
            return None

        script_slide = ('tell application "Keynote" to if playing then '
                         'return slide number of current slide of front document')
        resultado = subprocess.run(["osascript", "-e", script_slide], capture_output=True, text=True, timeout=1.5)
        saida = resultado.stdout.strip()
        if saida.isdigit():
            return int(saida)
    except Exception:
        pass
    return None


def loop_vigia():
    """Vigia em background o slide local e envia-o por HTTP para a régie sempre que muda."""
    global ultimo_slide_enviado
    import requests

    while True:
        try:
            if vigia_ativo:
                ip = entry_ip.get().strip()
                slide_atual = detetar_slide_keynote() if SISTEMA_MAC else detetar_slide_powerpoint()

                if slide_atual is not None and slide_atual != ultimo_slide_enviado:
                    ultimo_slide_enviado = slide_atual
                    try:
                        requests.get(f"http://{ip}:4545/api/cue/slide", params={"numero": slide_atual}, timeout=2)
                        root.after(0, lambda s=slide_atual: lbl_status.config(
                            text=f"Enviado à régie: slide {s}", fg="#50fa7b"))
                    except Exception:
                        root.after(0, lambda: lbl_status.config(
                            text=f"Falha a contactar a régie em {ip}:4545...", fg="#ff5555"))
                elif slide_atual is None and ultimo_slide_enviado is not None:
                    ultimo_slide_enviado = None
                    root.after(0, lambda: lbl_status.config(text="Sem apresentação ativa...", fg="#eab308"))
        except Exception as e:
            print(f"[Vigia Slides] Erro assíncrono isolado: {e}")
        time.sleep(0.4)


def toggle_vigia():
    global vigia_ativo, ultimo_slide_enviado
    vigia_ativo = not vigia_ativo
    ultimo_slide_enviado = None

    if vigia_ativo:
        ip = entry_ip.get().strip()
        if not ip:
            vigia_ativo = False
            lbl_status.config(text="Indica primeiro o IP da régie.", fg="#ff5555")
            return
        gravar_config(ip)
        btn_toggle.config(text="⏸ PARAR VIGIA", bg="#ff5555")
        entry_ip.config(state="disabled")
        nome_app = "Keynote" if SISTEMA_MAC else "PowerPoint"
        lbl_status.config(text=f"A vigiar o {nome_app}...", fg="#eab308")
    else:
        btn_toggle.config(text="▶ LIGAR VIGIA", bg="#22c55e")
        entry_ip.config(state="normal")
        lbl_status.config(text="Parado.", fg="#62657a")


root = Tk()
root.title("AVKtimer — Vigia de Slides v1.0.1")
root.configure(bg="#282a36")
root.geometry("420x260")
root.resizable(False, False)

try:
    if not SISTEMA_MAC:
        root.iconbitmap(os.path.join(caminho_base, "app.ico"))
except Exception:
    pass

Label(root, text="AVKtimer — Vigia de Slides", font=("Arial", 15, "bold"),
      bg="#282a36", fg="#f8f8f2").pack(pady=(18, 4))
Label(root, text="Corre no computador de quem apresenta e avisa\na régie sempre que o slide muda.",
      font=("Arial", 9), bg="#282a36", fg="#62657a", justify="center").pack(pady=(0, 16))

frame_ip = Frame(root, bg="#282a36")
frame_ip.pack(pady=(0, 10))
Label(frame_ip, text="IP da Régie (AVKtimer):", font=("Arial", 10, "bold"),
      bg="#282a36", fg="#f8f8f2").pack(anchor="w")
entry_ip = Entry(frame_ip, font=("Arial", 12), width=22, justify="center")
entry_ip.insert(0, carregar_config())
entry_ip.pack(pady=(4, 0))

btn_toggle = Button(root, text="▶ LIGAR VIGIA", bg="#22c55e", fg="white",
                     font=("Arial", 12, "bold"), bd=0, command=toggle_vigia)
btn_toggle.pack(fill="x", padx=30, pady=(6, 12), ipady=8)

lbl_status = Label(root, text="Parado.", font=("Arial", 9), bg="#282a36", fg="#62657a")
lbl_status.pack()

threading.Thread(target=loop_vigia, daemon=True).start()

root.mainloop()
