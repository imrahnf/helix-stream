package com.titancache.api;

public class CacheRequest {
    String key;
    String value;

    // Getters and setters
    public String getKey() { return key; }
    public void setKey(String key) { this.key = key; }
    public String getValue() { return value; }
    public void setValue(String value) { this.value = value; }

    public CacheRequest() {

    }
}
