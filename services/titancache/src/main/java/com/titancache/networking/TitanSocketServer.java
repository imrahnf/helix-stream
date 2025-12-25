package com.titancache.networking;

import com.titancache.core.TitanCache;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import jakarta.annotation.PostConstruct;
import java.io.*;
import java.net.*;

@Component
public class TitanSocketServer {
    private final TitanCache<String, String> cache;

    @Value("${titan.tcp.port:6379}")
    private int port;

    public TitanSocketServer(TitanCache<String, String> cache) {
        this.cache = cache;
    }

    @PostConstruct
    public void start() {
        new Thread(() -> {
            try (ServerSocket serverSocket = new ServerSocket(port)) {
                System.out.println("Titan TCP Server listening on port " + port);
                while (true) {
                    Socket clientSocket = serverSocket.accept();
                    new Thread(new ClientHandler(clientSocket, cache)).start();
                }
            } catch (IOException e) {
                e.printStackTrace();
            }
        }).start();
    }
}

class ClientHandler implements Runnable {
    private Socket socket;
    private TitanCache<String, String> cache;

    public ClientHandler(Socket socket, TitanCache<String, String> cache) {
        this.socket = socket;
        this.cache = cache;
    }

    @Override
    public void run() {
        try (BufferedReader in = new BufferedReader(new InputStreamReader(socket.getInputStream()));
             PrintWriter out = new PrintWriter(socket.getOutputStream(), true)) {

            String line;
            while ((line = in.readLine()) != null) {
                System.out.println("Received Command: " + line);

                String[] parts = line.split(" ", 3);
                String cmd = parts[0].toUpperCase();

                switch (cmd) {
                    case "GET" -> out.println(cache.get(parts[1]));
                    case "SET" -> {
                        cache.put(parts[1], parts[2]);
                        out.println("OK");
                    }
                    default -> out.println("ERROR: UNKNOWN COMMAND");
                }
            }
        } catch (IOException e) {
            System.err.println("Client disconnected.");
        }
    }
}