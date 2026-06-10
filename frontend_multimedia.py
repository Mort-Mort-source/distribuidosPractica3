import socket
import threading
import tkinter as tk
from tkinter import ttk, messagebox

BACKEND_HOST = "127.0.0.1"
BACKEND_PORT = 65436

class MultimediaClient:
    def __init__(self, root):
        self.root = root
        self.root.title("Cliente Multimedia Distribuido")
        self.root.geometry("700x500")

        # Diccionario para almacenar configuración de servidores
        self.servers = {
            "video": {"ip": tk.StringVar(value="127.0.0.1"), "port": tk.StringVar(value="65433"), "connected": False},
            "audio": {"ip": tk.StringVar(value="127.0.0.1"), "port": tk.StringVar(value="65434"), "connected": False},
            "pdf":   {"ip": tk.StringVar(value="127.0.0.1"), "port": tk.StringVar(value="65435"), "connected": False}
        }
        self.active_server = tk.StringVar(value="video")

        self.backend_socket = None
        self.receive_thread = None
        self.downloading = False
        self.progress_var = tk.IntVar()
        self.progress_bar = None

        self.create_widgets()
        self.connect_to_backend()

    def create_widgets(self):
        # Marco superior: configuración de servidores
        config_frame = tk.LabelFrame(self.root, text="Configuración de servidores", padx=10, pady=5)
        config_frame.pack(fill="x", padx=10, pady=5)

        row = 0
        for tipo, info in self.servers.items():
            tk.Label(config_frame, text=f"{tipo.upper()}:", font=("Arial", 10, "bold")).grid(row=row, column=0, sticky="w")
            tk.Label(config_frame, text="IP:").grid(row=row, column=1)
            tk.Entry(config_frame, textvariable=info["ip"], width=15).grid(row=row, column=2, padx=2)
            tk.Label(config_frame, text="Puerto:").grid(row=row, column=3)
            tk.Entry(config_frame, textvariable=info["port"], width=6).grid(row=row, column=4, padx=2)
            btn_connect = tk.Button(config_frame, text="Conectar", command=lambda t=tipo: self.toggle_connection(t))
            btn_connect.grid(row=row, column=5, padx=5)
            info["btn"] = btn_connect
            row += 1

        # Marco de selección de servidor activo
        active_frame = tk.LabelFrame(self.root, text="Servidor activo", padx=10, pady=5)
        active_frame.pack(fill="x", padx=10, pady=5)
        for tipo in self.servers.keys():
            tk.Radiobutton(active_frame, text=tipo.upper(), variable=self.active_server,
                           value=tipo, command=self.refresh_list).pack(side="left", padx=10)

        # Lista de archivos y botón refrescar
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

        # Descarga
        download_frame = tk.Frame(self.root)
        download_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(download_frame, text="Nombre del archivo:").pack(side="left")
        self.filename_entry = tk.Entry(download_frame, width=30)
        self.filename_entry.pack(side="left", padx=5)
        self.download_btn = tk.Button(download_frame, text="Descargar", command=self.download_file)
        self.download_btn.pack(side="left", padx=5)

        # Barra de progreso
        self.progress_bar = ttk.Progressbar(self.root, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill="x", padx=10, pady=5)
        self.progress_label = tk.Label(self.root, text="")
        self.progress_label.pack()

        # Estado de conexión con backend
        self.status_label = tk.Label(self.root, text="Conectando a backend...", fg="gray")
        self.status_label.pack(side="bottom", pady=5)

    def connect_to_backend(self):
        """Conectar al backend local"""
        try:
            self.backend_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.backend_socket.connect((BACKEND_HOST, BACKEND_PORT))
            self.receive_thread = threading.Thread(target=self.receive_messages, daemon=True)
            self.receive_thread.start()
            self.status_label.config(text="Conectado al backend", fg="green")
        except Exception as e:
            self.status_label.config(text=f"Error conectando a backend: {e}", fg="red")
            messagebox.showerror("Error", f"No se pudo conectar al backend. ¿Está ejecutándose?\n{e}")

    def receive_messages(self):
        """Hilo para recibir mensajes del backend (respuestas a comandos y progreso)"""
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
        """Procesa líneas recibidas del backend"""
        if msg.startswith("SIZE "):
            # Inicio de descarga: se recibió el tamaño
            pass
        elif msg.startswith("PROGRESS "):
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
        elif msg.startswith("OK"):
            # Conexión exitosa a servidor remoto
            pass
        else:
            # Es la lista de archivos (una línea por archivo)
            if not self.downloading:
                self.file_listbox.delete(0, tk.END)
                for f in msg.splitlines():
                    if f.strip():
                        self.file_listbox.insert(tk.END, f)

    def send_command(self, cmd):
        """Enviar un comando al backend"""
        try:
            self.backend_socket.sendall((cmd + "\n").encode())
        except:
            messagebox.showerror("Error", "Perdida conexión con backend")

    def toggle_connection(self, tipo):
        """Conectar o desconectar un servidor remoto"""
        info = self.servers[tipo]
        if not info["connected"]:
            ip = info["ip"].get().strip()
            port = info["port"].get().strip()
            if not ip or not port:
                messagebox.showerror("Error", "IP y puerto requeridos")
                return
            cmd = f"CONNECT {tipo} {ip} {port}"
            self.send_command(cmd)
            # Esperar respuesta (asíncrona, pero simplificamos: asumimos que OK llega)
            info["connected"] = True
            info["btn"].config(text="Desconectar", bg="lightcoral")
            self.status_label.config(text=f"Conectado a {tipo}", fg="blue")
        else:
            cmd = f"DISCONNECT {tipo}"
            self.send_command(cmd)
            info["connected"] = False
            info["btn"].config(text="Conectar", bg="SystemButtonFace")
            self.status_label.config(text=f"Desconectado de {tipo}", fg="gray")

    def refresh_list(self):
        """Solicitar lista de archivos del servidor activo"""
        tipo = self.active_server.get()
        if not self.servers[tipo]["connected"]:
            messagebox.showwarning("Aviso", f"El servidor {tipo} no está conectado")
            return
        self.send_command(f"LIST {tipo}")

    def download_file(self):
        """Iniciar descarga del archivo seleccionado o ingresado"""
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

if __name__ == "__main__":
    root = tk.Tk()
    app = MultimediaClient(root)
    root.mainloop()