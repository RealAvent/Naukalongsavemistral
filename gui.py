import asyncio
import threading
import sys
import tkinter as tk
from tkinter import scrolledtext

from automation_module import main

# Przekierowanie printów do widgetu
class TextRedirector:
    def __init__(self, widget):
        self.widget = widget
    def write(self, text):
        self.widget.configure(state='normal')
        self.widget.insert(tk.END, text)
        self.widget.see(tk.END)
        self.widget.configure(state='disabled')
    def flush(self):
        pass

def run_gui():
    root = tk.Tk()
    root.title("Facebook Friend Adder")
    root.geometry("600x380")
    root.configure(bg="#23272f")
    root.resizable(False, False)

    # Nagłówek
    tk.Label(root, text="Facebook Friend Adder", font=("Segoe UI", 20, "bold"),
             bg="#23272f", fg="#00bfff").pack(pady=(15,5))

    # START
    def on_start():
        start_btn.config(state="disabled")
        def worker():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                # bez 'page' w GUI – po prostu uruchamiamy główną logikę
                loop.run_until_complete(main())
            except Exception as e:
                print(f"[BŁĄD] {e}")
            finally:
                loop.close()
        threading.Thread(target=worker, daemon=True).start()

    start_btn = tk.Button(root, text="START", font=("Segoe UI", 13, "bold"),
                          bg="#00bfff", fg="#23272f", bd=0, relief="flat",
                          activebackground="#0099cc", activeforeground="#ffffff",
                          cursor="hand2", command=on_start)
    start_btn.pack(pady=15, ipadx=30, ipady=8)

    # Logi
    log_frame = tk.Frame(root, bg="#181a20", highlightbackground="#00bfff", highlightthickness=2)
    log_frame.pack(fill="both", expand=True, padx=15, pady=(0,15))
    log_box = scrolledtext.ScrolledText(log_frame, bg="#181a20", fg="#00ff99",
                                        font=("Consolas",10), state='disabled', wrap='word')
    log_box.pack(fill="both", expand=True, padx=5, pady=5)

    # Przekierowanie stdout/stderr
    sys.stdout = TextRedirector(log_box)
    sys.stderr = TextRedirector(log_box)

    root.mainloop()

if __name__ == "__main__":
    # upewnij się, że asyncio loop jest już zainicjowane
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())
    run_gui()