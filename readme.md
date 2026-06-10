# Manual de usuario: Sistema multimedia distribuido
Este documento explica cómo levantar los servidores (video, audio, PDF) en una PC servidor y el cliente (backend C++ + frontend Python) en otra PC cliente, dentro de la misma red local.
## 1. Requisitos previos en ambas PC
Sistema operativo: Linux (Ubuntu/Debian recomendado).

Compilador C++17 con soporte para pthreads: g++ (instalar con sudo apt install g++).

Python 3 con tkinter: sudo apt install python3-tk.

Permisos de firewall para los puertos que usen los servidores.

# PC servidor 

## 1. Compilar el servidor
compila el servidor con:

```bash
g++ -std=c++17 -pthread servidor_multimedia.cpp -o servidor
```

## 2. Ejecutar los tres servidores (en terminales separadas)

```bash 
# Servidor de videos (puerto 65433)
./servidor 65433 videos/

# Servidor de audios (puerto 65434)
./servidor 65434 audios/

# Servidor de PDFs (puerto 65435)
./servidor 65435 pdfs/
```

# PC CLIENTE

## Compilar el backend del cliente con: 

```bash

g++ -std=c++17 -pthread backend_cliente.cpp -o backend
```

## Ejecutar frontend
```bash
python3 frontend_multimedia.py
```

