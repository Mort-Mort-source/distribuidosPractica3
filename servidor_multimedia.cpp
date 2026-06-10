#include <iostream>
#include <fstream>
#include <string>
#include <cstring>
#include <sstream>
#include <thread>
#include <vector>
#include <filesystem>
#include <netinet/in.h>
#include <sys/socket.h>
#include <unistd.h>
#include <arpa/inet.h>

#define BUFFER_SIZE 8192

namespace fs = std::filesystem;

void atender_cliente(int client_fd, const std::string& directorio) {
    char buffer[BUFFER_SIZE];
    std::string comando;

    // Obtener IP y puerto del cliente
    struct sockaddr_in addr;
    socklen_t addr_len = sizeof(addr);
    getpeername(client_fd, (struct sockaddr*)&addr, &addr_len);
    std::string ip = inet_ntoa(addr.sin_addr);
    int puerto = ntohs(addr.sin_port);
    std::cout << "[Servidor " << directorio << "] Cliente conectado desde " << ip << ":" << puerto << std::endl;

    while (true) {
        memset(buffer, 0, BUFFER_SIZE);
        int bytes = recv(client_fd, buffer, BUFFER_SIZE - 1, 0);
        if (bytes <= 0) {
            std::cout << "[Servidor " << directorio << "] Cliente " << ip << ":" << puerto << " desconectado" << std::endl;
            break;
        }

        comando = buffer;
        if (comando.rfind("LIST", 0) == 0) {
            std::string lista;
            for (const auto& entry : fs::directory_iterator(directorio)) {
                if (entry.is_regular_file()) {
                    lista += entry.path().filename().string() + "\n";
                }
            }
            send(client_fd, lista.c_str(), lista.size(), 0);
        }
        else if (comando.rfind("DOWNLOAD ", 0) == 0) {
            std::string filename = comando.substr(9);
            filename.erase(filename.find_last_not_of("\n\r") + 1);
            std::string path = directorio + "/" + filename;

            std::ifstream file(path, std::ios::binary | std::ios::ate);
            if (!file.is_open()) {
                std::string error = "ERROR: Archivo no encontrado\n";
                send(client_fd, error.c_str(), error.size(), 0);
                continue;
            }

            size_t size = file.tellg();
            file.seekg(0, std::ios::beg);

            std::cout << "[Servidor " << directorio << "] Enviando: " << filename << " (" << size << " bytes) a " << ip << ":" << puerto << std::endl;

            std::string sizeMsg = "SIZE " + std::to_string(size) + "\n";
            send(client_fd, sizeMsg.c_str(), sizeMsg.size(), 0);

            char fileBuffer[BUFFER_SIZE];
            while (!file.eof()) {
                file.read(fileBuffer, BUFFER_SIZE);
                std::streamsize bytesRead = file.gcount();
                if (bytesRead > 0) {
                    send(client_fd, fileBuffer, bytesRead, 0);
                }
            }
            file.close();
            std::cout << "[Servidor " << directorio << "] Enviado: " << filename << " (" << size << " bytes) a " << ip << ":" << puerto << std::endl;
        }
        else {
            std::string error = "ERROR: Comando desconocido\n";
            send(client_fd, error.c_str(), error.size(), 0);
        }
    }
    close(client_fd);
}

int main(int argc, char* argv[]) {
    if (argc != 3) {
        std::cerr << "Uso: " << argv[0] << " <puerto> <directorio>" << std::endl;
        return 1;
    }

    int port = std::stoi(argv[1]);
    std::string directorio = argv[2];

    if (!fs::exists(directorio) || !fs::is_directory(directorio)) {
        std::cerr << "Error: el directorio '" << directorio << "' no existe o no es válido." << std::endl;
        return 1;
    }

    int server_fd, client_fd;
    struct sockaddr_in address;
    int opt = 1;
    socklen_t addrlen = sizeof(address);

    server_fd = socket(AF_INET, SOCK_STREAM, 0);
    setsockopt(server_fd, SOL_SOCKET, SO_REUSEADDR | SO_REUSEPORT, &opt, sizeof(opt));

    address.sin_family = AF_INET;
    address.sin_addr.s_addr = INADDR_ANY;
    address.sin_port = htons(port);

    bind(server_fd, (struct sockaddr*)&address, sizeof(address));
    listen(server_fd, 5);

    std::cout << "Servidor multimedia escuchando en puerto " << port << " (directorio: " << directorio << ")" << std::endl;

    while (true) {
        client_fd = accept(server_fd, (struct sockaddr*)&address, &addrlen);
        std::thread(atender_cliente, client_fd, directorio).detach();
    }
    close(server_fd);
    return 0;
}