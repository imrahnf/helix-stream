package com.titancache.api;

// Metrics DTO
public record CacheMetrics(int hits, int misses, int evictions, double hitRadio) {

}
