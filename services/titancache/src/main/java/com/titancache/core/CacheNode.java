package com.titancache.core;

public class CacheNode<K, V> {
    K key;
    V value;
    CacheNode<K, V> next;
    CacheNode<K, V> prev;

    public CacheNode(K key, V value) {
        this.key = key;
        this.value = value;
    }
}