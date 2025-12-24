package com.titancache.config;

import com.titancache.core.TitanCache;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class CacheConfig {
    // Inject values
    @Value("${titan.cache.capacity}")
    private int capacity;

    @Value("${titan.cache.max-entry-size-bytes}")
    private int maxEntrySizeBytes;

    @Bean
    public TitanCache<String, String> titanCache() {
        System.out.println("TitanCache Starting >>> Capacity: " + capacity + " | Max Item Size: " + maxEntrySizeBytes + " bytes");
        return new TitanCache<>(capacity, maxEntrySizeBytes);
    }
}