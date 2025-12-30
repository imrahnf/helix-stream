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

public class TitanCache {
    private static final Logger logger = LoggerFactory.getLogger(TitanCache.class);

    // K is now the Composite Key (hash:model_id)
    private final int capacity;
    private final int maxEntrySizeBytes;
    private final Map<String, CacheNode<String, String>> map;
    private final ReentrantReadWriteLock lock = new ReentrantReadWriteLock();
    private final CacheNode<String, String> head;
    private final CacheNode<String, String> tail;

    // Queue is model specific
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

    // Helperfor consistency
    private String compositeKey(String hash, String modelId) {
        return hash + ":" + modelId;
    }

    public void submitTask(String hash, String modelId) {
        String composite = compositeKey(hash, modelId);

        // Check L1 Cache
        if (map.containsKey(composite)) {
            logger.debug("Skipping Task: {} already exists for model {}", hash, modelId);
            return;
        }

        // Check Active
        if (activeLeases.containsKey(composite)) {
            logger.debug("Skipping Task: {} is currently leased", composite);
            return;
        }

        // Queue
        if (!taskQueue.contains(composite)) {
            taskQueue.offer(composite);
            logger.info("Task Queued: {}", composite);
        }
    }

    // Ffilter by model_id if needed or just lease raw comp keys
    public List<String> leaseTasks(int count, String targetModelId) {
        List<String> batch = new ArrayList<>();
        taskQueue.drainTo(batch, count);

        for (String composite : batch) {
            activeLeases.put(composite, System.currentTimeMillis());
        }
        return batch;
    }

    public void resolveTask(String hash, String modelId) {
        String composite = compositeKey(hash, modelId);
        if (activeLeases.remove(composite) != null) {
            logger.info("Task Resolved: {}", composite);
        }
    }

    public void put(String hash, String modelId, String value) {
        String composite = compositeKey(hash, modelId);
        lock.writeLock().lock();
        try {
            if (map.containsKey(composite)) {
                // Update existing
                CacheNode<String, String> node = map.get(composite);
                node.value = value;
                removeNode(node);
                addNode(node);
                return;
            }

            if (map.size() == capacity) {
                CacheNode<String, String> lru = tail.prev;
                removeNode(lru);
                map.remove(lru.key);
            }

            CacheNode<String, String> node = new CacheNode<>(composite, value);
            addNode(node);
            map.put(composite, node);
            logger.info("Stored L1: {} (Model: {})", hash, modelId);
        } finally {
            lock.writeLock().unlock();
        }
    }

    public String get(String hash, String modelId) {
        String composite = compositeKey(hash, modelId);
        lock.writeLock().lock();
        try {
            if (map.containsKey(composite)) {
                CacheNode<String, String> node = map.get(composite);
                removeNode(node);
                addNode(node);
                return node.value;
            }
            return null;
        } finally {
            lock.writeLock().unlock();
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
        } finally {
            lock.writeLock().unlock();
        }
    }

    private void addNode(CacheNode<String, String> node) {
        CacheNode<String, String> oldNext = head.next;
        node.prev = head;
        node.next = oldNext;
        head.next = node;
        oldNext.prev = node;
    }

    private CacheNode<String, String> removeNode(CacheNode<String, String> node) {
        node.prev.next = node.next;
        node.next.prev = node.prev;
        return node;
    }
}