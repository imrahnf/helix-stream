package com.titancache.api;

import com.titancache.core.TitanCache;
import com.titancache.grpc.*; // Generated from proto
import io.grpc.stub.StreamObserver;
import net.devh.boot.grpc.server.service.GrpcService;

@GrpcService
public class CacheGrpcService extends CacheServiceGrpc.CacheServiceImplBase {

    private final TitanCache<String, String> cache;

    public CacheGrpcService(TitanCache<String, String> cache) {
        this.cache = cache;
    }

    @Override
    public void put(CacheEntry request, StreamObserver<EmptyResponse> responseObserver) {
        cache.put(request.getKey(), request.getValue());
        responseObserver.onNext(EmptyResponse.newBuilder().setMessage("Stored").build());
        responseObserver.onCompleted();
    }

    @Override
    public void get(KeyRequest request, StreamObserver<ValueResponse> responseObserver) {
        String val = cache.get(request.getKey());
        ValueResponse response = ValueResponse.newBuilder()
                .setValue(val != null ? val : "")
                .setFound(val != null)
                .build();
        responseObserver.onNext(response);
        responseObserver.onCompleted();
    }

    @Override
    public void clear(EmptyRequest request, StreamObserver<EmptyResponse> responseObserver) {
        cache.clear();
        responseObserver.onNext(EmptyResponse.newBuilder().setMessage("Cleared").build());
        responseObserver.onCompleted();
    }
}