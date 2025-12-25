package com.titancache.core;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.BlockingQueue;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.LinkedBlockingQueue;
import java.util.concurrent.locks.ReentrantReadWriteLock;

public class TitanCache<K, V> {
    private static final Logger logger = LoggerFactory.getLogger(TitanCache.class);

    private final int capacity;
    private final int maxEntrySizeBytes;
    private final Map<K, CacheNode<K, V>> map;
    private final ReentrantReadWriteLock lock = new ReentrantReadWriteLock();
    private final CacheNode<K, V> head;
    private final CacheNode<K, V> tail;

    private final BlockingQueue<String> taskQueue = new LinkedBlockingQueue<>();
    private final Map<String, Long> activeLeases = new ConcurrentHashMap<>();

    public TitanCache(int capacity, int maxEntrySizeBytes) {
        this.capacity = capacity;
        this.maxEntrySizeBytes = maxEntrySizeBytes;
        this.map = new HashMap<>();
        this.head = new CacheNode<>(null, null);
        this.tail = new CacheNode<>(null, null);
        head.next = tail;
        tail.prev = head;
    }

    public void submitTask(String key) {
        // 1. Check L1 Cache
        if (map.containsKey((K)key)) {
            logger.debug("⏭️ Skipping Task: {} already exists in L1 Cache", key);
            return;
        }

        // 2. Check Active Leases (currently being processed)
        if (activeLeases.containsKey(key)) {
            logger.debug("⏳ Skipping Task: {} is currently leased by a worker", key);
            return;
        }

        // 3. Deduplication Check for Queue
        if (!taskQueue.contains(key)) {
            taskQueue.offer(key);
            logger.info("🆕 Task Queued: {}. Current Queue Size: {}", key, taskQueue.size());
        } else {
            logger.warn("🛑 Duplicate Task Blocked: {} is already in the queue", key);
        }
    }

    public List<String> leaseTasks(int count) {
        List<String> batch = new ArrayList<>();
        taskQueue.drainTo(batch, count);
        for (String key : batch) {
            activeLeases.put(key, System.currentTimeMillis());
        }
        if (!batch.isEmpty()) {
            logger.info("📡 Leased {} tasks to worker. Active leases: {}", batch.size(), activeLeases.size());
        }
        return batch;
    }

    public void resolveTask(String key) {
        if (activeLeases.remove(key) != null) {
            logger.info("✅ Task Resolved: {}", key);
        }
    }

    public void clear() {
        lock.writeLock().lock();
        try {
            map.clear();
            taskQueue.clear();
            activeLeases.clear();
            head.next = tail;
            tail.prev = head;
            logger.info("🧹 Cache and Task Queue cleared.");
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
                logger.debug("🎯 L1 Hit: {}", key);
                return temp.value;
            }
            logger.debug("💨 L1 Miss: {}", key);
            return null;
        } finally {
            lock.writeLock().unlock();
        }
    }

    public void put(K key, V value) {
        lock.writeLock().lock();
        try {
            if (value.toString().length() > maxEntrySizeBytes) {
                logger.error("❌ Entry size exceeds limit for key: {}", key);
                return;
            }

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
                logger.info("♻️ LRU Eviction: {}", lru.key);
            }

            CacheNode<K, V> node = new CacheNode<>(key, value);
            addNode(node);
            map.put(key, node);
            logger.info("💾 Stored in L1: {}", key);
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