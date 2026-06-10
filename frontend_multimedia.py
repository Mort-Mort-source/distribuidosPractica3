import socket
import threading
import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import os
import time
import signal
import sys

BACKEND_HOST = "127.0.0.1"
BACKEND_PORT = 65436
BACKEND_BIN = "./backend"
BACKEND_SRC = "backend_cliente.cpp"
COMPILE_CMD = ["g++", "-std=c++17", "-pthread", BACKEND_SRC, "-o", "backend"]

class MultimediaClient:
    def __init__(self, root):
        self.root = root
        self.root.title("Cliente Multimedia Distribuido")
        self.root.geometry("700x500")

        self.backend_process = None
        self.backend_socket = None
        self.receive_thread = None
        self.downloading = False

        self.servers = {
            "video": {"ip": tk.StringVar(value="127.0.0.1"), "port": tk.StringVar(value="65433"), "connected": False},
            "audio": {"ip": tk.StringVar(value="127.0.0.1"), "port": tk.StringVar(value="65434"), "connected": False},
            "pdf":   {"ip": tk.StringVar(value="127.0.0.1"), "port": tk.StringVar(value="65435"), "connected": False}
        }
        self.active_server = tk.StringVar(value="video")

        self.progress_var = tk.IntVar()
        self.progress_bar = None

        self.start_backend()
        self.create_widgets()
        self.connect_to_backend()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def start_backend(self):
        if not os.path.exists(BACKEND_BIN):
            print("Compilando backend...")
            try:
                subprocess.run(COMPILE_CMD, check=True)
                print("Compilación exitosa.")
            except subprocess.CalledProcessError as e:
                messagebox.showerror("Error", f"No se pudo compilar el backend:\n{e}")
                sys.exit(1)

        try:
            self.backend_process = subprocess.Popen(
                [BACKEND_BIN],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid if os.name != 'nt' else None
            )
            time.sleep(0.5)
            threading.Thread(target=self.read_backend_output, daemon=True).start()
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo ejecutar el backend:\n{e}")
            sys.exit(1)

    def read_backend_output(self):
        for line in iter(self.backend_process.stdout.readline, b''):
            print(f"[Backend] {line.decode().strip()}")
        for line in iter(self.backend_process.stderr.readline, b''):
            print(f"[Backend ERROR] {line.decode().strip()}")

    def connect_to_backend(self):
        try:
            self.backend_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            for _ in range(10):
                try:
                    self.backend_socket.connect((BACKEND_HOST, BACKEND_PORT))
                    break
                except ConnectionRefusedError:
                    time.sleep(0.5)
            else:
                raise ConnectionRefusedError("Backend no respondió después de varios intentos")

            self.receive_thread = threading.Thread(target=self.receive_messages, daemon=True)
            self.receive_thread.start()
            self.status_label.config(text="Conectado al backend", fg="green")
        except Exception as e:
            self.status_label.config(text=f"Error conectando a backend: {e}", fg="red")
            messagebox.showerror("Error", f"No se pudo conectar al backend:\n{e}")
            self.on_closing()

    def receive_messages(self):
        buffer = ""
        while True:
            try:
                data = self.backend_socket.recv(1024).decode()
                if not data:
                    break
                buffer += data
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    self.process_backend_message(line)
            except:
                break

    def process_backend_message(self, msg):
        if msg.startswith("PROGRESS "):
            percent = int(msg.split()[1])
            self.progress_var.set(percent)
            self.progress_label.config(text=f"Descargando... {percent}%")
        elif msg.startswith("DOWNLOAD_COMPLETE"):
            self.progress_label.config(text="¡Descarga completada!")
            self.downloading = False
            self.download_btn.config(state="normal")
            messagebox.showinfo("Éxito", "Archivo descargado correctamente")
        elif msg.startswith("ERROR"):
            self.progress_label.config(text="Error en descarga")
            self.downloading = False
            self.download_btn.config(state="normal")
            messagebox.showerror("Error", msg)
        elif msg.startswith("SIZE "):
            pass
        else:
            if not self.downloading:
                self.file_listbox.delete(0, tk.END)
                for f in msg.splitlines():
                    if f.strip():
                        self.file_listbox.insert(tk.END, f)

    def send_command(self, cmd):
        try:
            self.backend_socket.sendall((cmd + "\n").encode())
        except:
            messagebox.showerror("Error", "Perdida conexión con backend")

    def create_widgets(self):
        config_frame = tk.LabelFrame(self.root, text="Configuración de servidores", padx=10, pady=5)
        config_frame.pack(fill="x", padx=10, pady=5)

        row = 0
        for tipo, info in self.servers.items():
            tk.Label(config_frame, text=f"{tipo.upper()}:", font=("Arial", 10, "bold")).grid(row=row, column=0, sticky="w")
            tk.Label(config_frame, text="IP:").grid(row=row, column=1)
            tk.Entry(config_frame, textvariable=info["ip"], width=15).grid(row=row, column=2, padx=2)
            tk.Label(config_frame, text="Puerto:").grid(row=row, column=3)
            tk.Entry(config_frame, textvariable=info["port"], width=6).grid(row=row, column=4, padx=2)
            btn = tk.Button(config_frame, text="Conectar", command=lambda t=tipo: self.toggle_connection(t))
            btn.grid(row=row, column=5, padx=5)
            info["btn"] = btn
            row += 1

        active_frame = tk.LabelFrame(self.root, text="Servidor activo", padx=10, pady=5)
        active_frame.pack(fill="x", padx=10, pady=5)
        for tipo in self.servers.keys():
            tk.Radiobutton(active_frame, text=tipo.upper(), variable=self.active_server,
                           value=tipo, command=self.refresh_list).pack(side="left", padx=10)

        list_frame = tk.Frame(self.root)
        list_frame.pack(fill="both", expand=True, padx=10, pady=5)
        tk.Label(list_frame, text="Archivos disponibles:").pack(anchor="w")
        self.file_listbox = tk.Listbox(list_frame, height=12)
        self.file_listbox.pack(side="left", fill="both", expand=True)
        scrollbar = tk.Scrollbar(list_frame, orient="vertical", command=self.file_listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self.file_listbox.config(yscrollcommand=scrollbar.set)

        btn_refresh = tk.Button(self.root, text="Refrescar lista", command=self.refresh_list)
        btn_refresh.pack(pady=5)

        download_frame = tk.Frame(self.root)
        download_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(download_frame, text="Nombre del archivo:").pack(side="left")
        self.filename_entry = tk.Entry(download_frame, width=30)
        self.filename_entry.pack(side="left", padx=5)
        self.download_btn = tk.Button(download_frame, text="Descargar", command=self.download_file)
        self.download_btn.pack(side="left", padx=5)

        self.progress_bar = ttk.Progressbar(self.root, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill="x", padx=10, pady=5)
        self.progress_label = tk.Label(self.root, text="")
        self.progress_label.pack()

        self.status_label = tk.Label(self.root, text="Conectando a backend...", fg="gray")
        self.status_label.pack(side="bottom", pady=5)

    def toggle_connection(self, tipo):
        info = self.servers[tipo]
        if not info["connected"]:
            ip = info["ip"].get().strip()
            port = info["port"].get().strip()
            if not ip or not port:
                messagebox.showerror("Error", "IP y puerto requeridos")
                return
            self.send_command(f"CONNECT {tipo} {ip} {port}")
            info["connected"] = True
            info["btn"].config(text="Desconectar", bg="lightcoral")
            self.status_label.config(text=f"Conectado a {tipo}", fg="blue")
        else:
            self.send_command(f"DISCONNECT {tipo}")
            info["connected"] = False
            # CORRECCIÓN: usar un color estándar que funcione en todos los sistemas
            info["btn"].config(text="Conectar", bg="lightgray")
            self.status_label.config(text=f"Desconectado de {tipo}", fg="gray")

    def refresh_list(self):
        tipo = self.active_server.get()
        if not self.servers[tipo]["connected"]:
            messagebox.showwarning("Aviso", f"El servidor {tipo} no está conectado")
            return
        self.send_command(f"LIST {tipo}")

    def download_file(self):
        if self.downloading:
            return
        tipo = self.active_server.get()
        if not self.servers[tipo]["connected"]:
            messagebox.showwarning("Aviso", f"El servidor {tipo} no está conectado")
            return
        filename = self.filename_entry.get().strip()
        if not filename:
            selection = self.file_listbox.curselection()
            if selection:
                filename = self.file_listbox.get(selection[0])
            else:
                messagebox.showwarning("Aviso", "Seleccione o escriba un nombre de archivo")
                return
        self.downloading = True
        self.download_btn.config(state="disabled")
        self.progress_var.set(0)
        self.progress_label.config(text="Solicitando descarga...")
        self.send_command(f"DOWNLOAD {tipo} {filename}")

    def on_closing(self):
        if self.backend_process:
            try:
                if os.name != 'nt':
                    os.killpg(os.getpgid(self.backend_process.pid), signal.SIGTERM)
                else:
                    self.backend_process.terminate()
            except:
                pass
            self.backend_process.terminate()
            self.backend_process.wait()
        if self.backend_socket:
            self.backend_socket.close()
        self.root.destroy()
        sys.exit(0)

if __name__ == "__main__":
    root = tk.Tk()
    app = MultimediaClient(root)
    root.mainloop()