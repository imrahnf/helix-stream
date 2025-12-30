package com.titancache.config;

import com.titancache.core.TitanCache;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class CacheConfig {

    @Value("${titan.cache.capacity:1000}")
    private int capacity;

    @Value("${titan.cache.max-entry-size-bytes:1048576}")
    private int maxEntrySizeBytes;

    @Bean
    public TitanCache titanCache() {
        return new TitanCache(capacity, maxEntrySizeBytes);
    }
}