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

    private final int capacity;
    private final int maxEntrySizeBytes;
    private final Map<String, CacheNode<String, StoredValue>> map;
    private final ReentrantReadWriteLock lock = new ReentrantReadWriteLock();
    private final CacheNode<String, StoredValue> head;
    private final CacheNode<String, StoredValue> tail;
    private final BlockingQueue<TaskEntry> taskQueue = new LinkedBlockingQueue<>();
    private final Map<String, Long> activeLeases = new ConcurrentHashMap<>();

    public record StoredValue(String json, float confidence) {}
    public record TaskEntry(String hash, String sequence, String modelId) {}

    public TitanCache(int capacity, int maxEntrySizeBytes) {
        this.capacity = capacity;
        this.maxEntrySizeBytes = maxEntrySizeBytes;
        this.map = new HashMap<>();
        this.head = new CacheNode<>(null, null);
        this.tail = new CacheNode<>(null, null);
        head.next = tail;
        tail.prev = head;
    }

    private String compositeKey(String hash, String modelId) {
        return hash + ":" + modelId;
    }

    public void submitTask(String hash, String sequence, String modelId) {
        String composite = compositeKey(hash, modelId);
        System.out.println("DEBUG: submitTask for key [" + composite + "]");
        if (map.containsKey(composite) || activeLeases.containsKey(composite)) return;
        TaskEntry entry = new TaskEntry(hash, sequence, modelId);
        if (!taskQueue.contains(entry)) {
            taskQueue.offer(entry);
            logger.info("Task Queued: {}", hash);
        }
    }

    public List<TaskEntry> leaseTasks(int count, String targetModelId) {
        List<TaskEntry> batch = new ArrayList<>();
        taskQueue.drainTo(batch, count);
        for (TaskEntry entry : batch) {
            activeLeases.put(compositeKey(entry.hash(), entry.modelId()), System.currentTimeMillis());
        }
        return batch;
    }

    public void resolveTask(String hash, String modelId) {
        String composite = compositeKey(hash, modelId);
        if (activeLeases.remove(composite) != null) {
            logger.info("Task Resolved: {}", composite);
        }
    }

    public void put(String hash, String modelId, String valueJson, float confidence) {
        String composite = compositeKey(hash, modelId);
        StoredValue storedVal = new StoredValue(valueJson, confidence);

        System.out.println("DEBUG PUT -> CompositeKey: [" + composite + "]");

        lock.writeLock().lock();
        try {
            if (map.containsKey(composite)) {
                CacheNode<String, StoredValue> node = map.get(composite);
                node.value = storedVal;
                removeNode(node);
                addNode(node);
                return;
            }
            if (map.size() == capacity) {
                CacheNode<String, StoredValue> lru = tail.prev;
                removeNode(lru);
                map.remove(lru.key);
            }
            CacheNode<String, StoredValue> node = new CacheNode<>(composite, storedVal);
            addNode(node);
            map.put(composite, node);
            logger.info("Stored L1: {} (Conf: {})", hash, confidence);
        } finally {
            lock.writeLock().unlock();
        }
    }

    public StoredValue get(String hash, String modelId) {
        String composite = compositeKey(hash, modelId);

        System.out.println("DEBUG GET -> Looking for Key: [" + composite + "]");
        System.out.println("DEBUG GET -> Keys currently in Map: " + map.keySet());

        lock.writeLock().lock();
        try {
            if (map.containsKey(composite)) {
                System.out.println("DEBUG GET -> HIT FOUND!");
                CacheNode<String, StoredValue> node = map.get(composite);
                removeNode(node);
                addNode(node);
                return node.value;
            }
            System.out.println("DEBUG GET -> MISS");
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

    private void addNode(CacheNode<String, StoredValue> node) {
        CacheNode<String, StoredValue> oldNext = head.next;
        node.prev = head;
        node.next = oldNext;
        head.next = node;
        oldNext.prev = node;
    }

    private CacheNode<String, StoredValue> removeNode(CacheNode<String, StoredValue> node) {
        node.prev.next = node.next;
        node.next.prev = node.prev;
        return node;
    }
}