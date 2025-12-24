package com.titancache.core;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class TitanCacheTest {

    private TitanCache<String, String> cache;

    @BeforeEach
    void setUp() {
        // create a tiny cache
        cache = new TitanCache<>(3, 100);
    }

    @Test
    void testPutAndGet() {
        cache.put("A", "1");
        assertEquals("1", cache.get("A"));
    }

    @Test
    void testUpdateValue() {
        cache.put("A", "1");
        cache.put("A", "2"); // update
        assertEquals("2", cache.get("A"));
    }

    @Test
    void testLruEviction() {
        // fill cache
        cache.put("A", "1");
        cache.put("B", "2");
        cache.put("C", "3");

        // oldest should be evicted.
        cache.put("D", "4");

        assertNull(cache.get("A"), "A should be evicted");
        assertNotNull(cache.get("B"));
        assertNotNull(cache.get("C"));
        assertNotNull(cache.get("D"));
    }

    @Test
    void testAccessResetsLru() {
        // Fill cache [A, B, C]
        cache.put("A", "1");
        cache.put("B", "2");
        cache.put("C", "3");

        // A is "fresh" Order is [B, C, A]
        cache.get("A");

        // add D, B  should be evicted, NOT A
        cache.put("D", "4");

        assertNotNull(cache.get("A"), "A should survive because it was accessed");
        assertNull(cache.get("B"), "B should be evicted");
    }
}