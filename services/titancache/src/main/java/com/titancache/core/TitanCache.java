package com.titancache.core;

import java.util.concurrent.locks.ReentrantReadWriteLock;
import java.util.HashMap;
import java.util.Map;

public class TitanCache<K, V> {
    private final int capacity;
    private final int maxEntrySizeBytes;
    private final Map<K, CacheNode<K, V>> map;
    private final ReentrantReadWriteLock lock = new ReentrantReadWriteLock();
    private final CacheNode<K, V> head;
    private final CacheNode<K, V> tail;

    public TitanCache(int capacity, int maxEntrySizeBytes) {
        this.capacity = capacity;
        this.maxEntrySizeBytes = maxEntrySizeBytes;
        this.map = new HashMap<>();
        this.head = new CacheNode<>(null, null);
        this.tail = new CacheNode<>(null, null);
        head.next = tail;
        tail.prev = head;
    }

    public void clear() {
        lock.writeLock().lock();
        try {
            map.clear();
            head.next = tail;
            tail.prev = head;
        } finally {
            lock.writeLock().unlock();
        }
    }

    public V get(K key) {
        lock.writeLock().lock();
        try {
            if (map.containsKey(key)) {
                CacheNode<K, V> temp = removeNode(map.get(key));
                addNode(temp);
                return temp.value;
            }
            return null;
        } finally {
            lock.writeLock().unlock();
        }
    }

    public void put(K key, V value) {
        lock.writeLock().lock();
        try {
            if (value.toString().length() > maxEntrySizeBytes) return;

            if (map.containsKey(key)) {
                CacheNode<K, V> node = map.get(key);
                node.value = value;
                removeNode(node);
                addNode(node);
                return;
            }

            if (map.size() == capacity) {
                CacheNode<K, V> lru = tail.prev;
                removeNode(lru);
                map.remove(lru.key);
            }

            CacheNode<K, V> node = new CacheNode<>(key, value);
            addNode(node);
            map.put(key, node);
        } finally {
            lock.writeLock().unlock();
        }
    }

    private void addNode(CacheNode<K, V> node) {
        CacheNode<K, V> oldNext = head.next;
        node.prev = head;
        node.next = oldNext;
        head.next = node;
        oldNext.prev = node;
    }

    private CacheNode<K, V> removeNode(CacheNode<K, V> node) {
        node.prev.next = node.next;
        node.next.prev = node.prev;
        return node;
    }
}