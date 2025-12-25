package com.titancache.networking;

import com.titancache.core.TitanCache;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import jakarta.annotation.PostConstruct;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;

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
                System.err.println("Server error: " + e.getMessage());
            }
        }).start();
    }
}

class ClientHandler implements Runnable {
    private final Socket socket;
    private final TitanCache<String, String> cache;

    public ClientHandler(Socket socket, TitanCache<String, String> cache) {
        this.socket = socket;
        this.cache = cache;
    }

    @Override
    public void run() {
        try (DataInputStream in = new DataInputStream(socket.getInputStream());
             DataOutputStream out = new DataOutputStream(socket.getOutputStream())) {

            while (true) {
                int length;
                try {
                    length = in.readInt();
                } catch (EOFException e) {
                    break; // Client closed connection normally
                }

                // Read exactly length bytes for the payload
                byte[] payload = new byte[length];
                in.readFully(payload);
                String message = new String(payload, StandardCharsets.UTF_8);
                System.out.println("Received: " + message);

                // Parse command using colon delimiter
                String[] parts = message.split(":", 3);
                String cmd = parts[0].toUpperCase();
                String responseText;

                switch (cmd) {
                    case "VERSION" -> responseText = "OK";
                    case "CHECK" -> {
                        String val = cache.get(parts[1]);
                        responseText = (val != null) ? "HIT:" + val : "MISS"; //
                    }
                    case "SET", "ENQUEUE" -> {
                        cache.put(parts[1], parts[2]);
                        responseText = "OK";
                    }
                    case "PING" -> responseText = "PONG";
                    default -> responseText = "ERR_UNKNOWN"; //
                }

                // Send length prefixed response
                byte[] responseBytes = responseText.getBytes(StandardCharsets.UTF_8);
                out.writeInt(responseBytes.length);
                out.write(responseBytes);
                out.flush();
            }
        } catch (IOException e) {
            System.err.println("Client handler error: " + e.getMessage());
        } finally {
            try { socket.close(); } catch (IOException ignored) {}
        }
    }
}