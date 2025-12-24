package com.titancache.core;

public class CacheNode<K, V> {
    // Keep K, V in node so that when we delete the last recently used node, the data deletes alongside it
    K key = null;
    V value = null;
    CacheNode<K, V> next = null;
    CacheNode<K, V> prev = null;

    // Initialize the node and set references immediately
    public CacheNode(K key, V value) {
        this.key = key;
        this.value = value;
    }
}
