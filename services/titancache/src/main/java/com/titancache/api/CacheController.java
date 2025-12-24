package com.titancache.api;

import com.titancache.core.TitanCache;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/cache")
public class CacheController {
    private final TitanCache<String, String> cache;

    public CacheController(TitanCache<String, String> cache) {
        this.cache = cache;
    }

    @PostMapping("/store")
    public ResponseEntity<String> store(@RequestBody CacheRequest request) {
        cache.put(request.getKey(), request.getValue());
        return ResponseEntity.ok("Stored value: " + request.getValue());
    }

    @GetMapping("/retrieve/{key}")
    public ResponseEntity<String> retrieve(@PathVariable String key) {
        String value = cache.get(key);
        if (value == null) {
            return ResponseEntity.notFound().build(); // return 404 not found
        }
        return ResponseEntity.ok(value);
    }

    @GetMapping("/metrics")
    public ResponseEntity<CacheMetrics> getMetrics() {
        return ResponseEntity.ok(cache.getMetrics());
    }

    // Simply return status whether the application is running or not
    @GetMapping("/status")
    public ResponseEntity<String> status() {
        return ResponseEntity.ok("TitanCache is running.");
    }

    @DeleteMapping("/clear")
    public ResponseEntity<String> clearCache() {
        cache.clear();
        return ResponseEntity.ok("Cache cleared and metrics reset.");
    }
}
