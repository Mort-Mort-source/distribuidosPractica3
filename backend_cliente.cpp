#include <iostream>
#include <string>
#include <cstring>
#include <sstream>
#include <thread>
#include <vector>
#include <map>
#include <fstream>
#include <filesystem>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <unistd.h>
#include <netdb.h>

#define BACKEND_PORT 65436
#define BUFFER_SIZE 8192
#define TIMEOUT_SEC 10

namespace fs = std::filesystem;

struct ServerConn {
    std::string tipo;
    std::string ip;
    int puerto;
    int socket_fd;
    bool conectado;
};

std::map<std::string, ServerConn> servidores = {
    {"video", {"video", "", 0, -1, false}},
    {"audio", {"audio", "", 0, -1, false}},
    {"pdf",   {"pdf",   "", 0, -1, false}}
};

bool conectar_remoto(const std::string& tipo, const std::string& ip, int puerto) {
    if (servidores[tipo].conectado) {
        close(servidores[tipo].socket_fd);
        servidores[tipo].conectado = false;
    }

    int sock = socket(AF_INET, SOCK_STREAM, 0);
    if (sock < 0) return false;

    struct sockaddr_in addr;
    addr.sin_family = AF_INET;
    addr.sin_port = htons(puerto);
    inet_pton(AF_INET, ip.c_str(), &addr.sin_addr);

    if (connect(sock, (struct sockaddr*)&addr, sizeof(addr)) < 0) {
        close(sock);
        return false;
    }

    servidores[tipo].socket_fd = sock;
    servidores[tipo].ip = ip;
    servidores[tipo].puerto = puerto;
    servidores[tipo].conectado = true;
    return true;
}

void desconectar_remoto(const std::string& tipo) {
    if (servidores[tipo].conectado) {
        close(servidores[tipo].socket_fd);
        servidores[tipo].conectado = false;
    }
}

std::string enviar_comando(const std::string& tipo, const std::string& cmd) {
    if (!servidores[tipo].conectado) return "ERROR: Servidor no conectado";
    send(servidores[tipo].socket_fd, cmd.c_str(), cmd.size(), 0);
    char buffer[BUFFER_SIZE];
    std::string respuesta;
    while (true) {
        memset(buffer, 0, BUFFER_SIZE);
        int bytes = recv(servidores[tipo].socket_fd, buffer, BUFFER_SIZE - 1, 0);
        if (bytes <= 0) break;
        respuesta += buffer;
        if (respuesta.find('\n') != std::string::npos) break;
    }
    return respuesta;
}

void descargar_archivo(int frontend_fd, const std::string& tipo, const std::string& filename) {
    if (!servidores[tipo].conectado) {
        send(frontend_fd, "ERROR: Servidor no conectado\n", 30, 0);
        return;
    }

    std::string cmd = "DOWNLOAD " + filename + "\n";
    send(servidores[tipo].socket_fd, cmd.c_str(), cmd.size(), 0);

    char buffer[BUFFER_SIZE];
    memset(buffer, 0, BUFFER_SIZE);
    int bytes = recv(servidores[tipo].socket_fd, buffer, BUFFER_SIZE - 1, 0);
    if (bytes <= 0) {
        send(frontend_fd, "ERROR: Servidor no responde\n", 28, 0);
        return;
    }
    std::string respuesta(buffer);
    if (respuesta.rfind("SIZE ", 0) != 0) {
        send(frontend_fd, respuesta.c_str(), respuesta.size(), 0);
        return;
    }
    size_t size = std::stoull(respuesta.substr(5));
    send(frontend_fd, ("SIZE " + std::to_string(size) + "\n").c_str(), 0, 0);

    fs::create_directory("descargas");
    std::string path = "descargas/" + filename;
    std::ofstream outfile(path, std::ios::binary);
    if (!outfile.is_open()) {
        send(frontend_fd, "ERROR: No se pudo crear archivo local\n", 38, 0);
        return;
    }

    size_t recibidos = 0;
    int last_progress = -1;
    while (recibidos < size) {
        memset(buffer, 0, BUFFER_SIZE);
        int chunk = recv(servidores[tipo].socket_fd, buffer, BUFFER_SIZE, 0);
        if (chunk <= 0) break;
        outfile.write(buffer, chunk);
        recibidos += chunk;
        int progress = (int)((recibidos * 100) / size);
        if (progress != last_progress) {
            std::string progMsg = "PROGRESS " + std::to_string(progress) + "\n";
            send(frontend_fd, progMsg.c_str(), progMsg.size(), 0);
            last_progress = progress;
        }
    }
    outfile.close();

    if (recibidos == size) {
        send(frontend_fd, "DOWNLOAD_COMPLETE\n", 19, 0);
        std::cout << "[Backend] Archivo descargado: " << filename << " (" << size << " bytes)" << std::endl;
    } else {
        send(frontend_fd, "ERROR: Descarga incompleta\n", 27, 0);
    }
}

void atender_frontend(int frontend_fd) {
    char buffer[BUFFER_SIZE];
    while (true) {
        memset(buffer, 0, BUFFER_SIZE);
        int bytes = recv(frontend_fd, buffer, BUFFER_SIZE - 1, 0);
        if (bytes <= 0) break;
        std::string cmd(buffer);

        std::istringstream iss(cmd);
        std::string comando;
        iss >> comando;

        if (comando == "CONNECT") {
            std::string tipo, ip;
            int puerto;
            iss >> tipo >> ip >> puerto;
            if (conectar_remoto(tipo, ip, puerto)) {
                send(frontend_fd, "OK Conectado\n", 13, 0);
            } else {
                send(frontend_fd, "ERROR No se pudo conectar\n", 26, 0);
            }
        }
        else if (comando == "DISCONNECT") {
            std::string tipo;
            iss >> tipo;
            desconectar_remoto(tipo);
            send(frontend_fd, "OK Desconectado\n", 16, 0);
        }
        else if (comando == "LIST") {
            std::string tipo;
            iss >> tipo;
            std::string lista = enviar_comando(tipo, "LIST\n");
            send(frontend_fd, lista.c_str(), lista.size(), 0);
        }
        else if (comando == "DOWNLOAD") {
            std::string tipo, filename;
            iss >> tipo >> filename;
            descargar_archivo(frontend_fd, tipo, filename);
        }
        else {
            send(frontend_fd, "ERROR Comando desconocido\n", 26, 0);
        }
    }
    close(frontend_fd);
}

int main() {
    int server_fd, client_fd;
    struct sockaddr_in address;
    int opt = 1;
    socklen_t addrlen = sizeof(address);

    server_fd = socket(AF_INET, SOCK_STREAM, 0);
    setsockopt(server_fd, SOL_SOCKET, SO_REUSEADDR | SO_REUSEPORT, &opt, sizeof(opt));

    address.sin_family = AF_INET;
    address.sin_addr.s_addr = inet_addr("127.0.0.1");
    address.sin_port = htons(BACKEND_PORT);

    bind(server_fd, (struct sockaddr*)&address, sizeof(address));
    listen(server_fd, 5);

    std::cout << "Backend cliente escuchando en puerto " << BACKEND_PORT << " (localhost)" << std::endl;

    while (true) {
        client_fd = accept(server_fd, (struct sockaddr*)&address, &addrlen);
        std::thread(atender_frontend, client_fd).detach();
    }
    close(server_fd);
    return 0;
}