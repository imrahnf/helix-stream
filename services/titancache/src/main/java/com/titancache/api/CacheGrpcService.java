package com.titancache.api;

import com.titancache.core.TitanCache;
import com.titancache.grpc.*;
import io.grpc.stub.StreamObserver;
import net.devh.boot.grpc.server.service.GrpcService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

@GrpcService
public class CacheGrpcService extends CacheServiceGrpc.CacheServiceImplBase {
    private static final Logger logger = LoggerFactory.getLogger(CacheGrpcService.class);
    private final TitanCache<String, String> cache;

    public CacheGrpcService(TitanCache<String, String> cache) {
        this.cache = cache;
    }

    @Override
    public void submitTask(KeyRequest request, StreamObserver<EmptyResponse> responseObserver) {
        logger.debug("📥 gRPC SUBMIT_TASK: {}", request.getKey());
        cache.submitTask(request.getKey());
        responseObserver.onNext(EmptyResponse.newBuilder().setMessage("Queued").build());
        responseObserver.onCompleted();
    }

    @Override
    public void put(CacheEntry request, StreamObserver<EmptyResponse> responseObserver) {
        logger.debug("📥 gRPC PUT: {}", request.getKey());
        cache.put(request.getKey(), request.getValue());
        responseObserver.onNext(EmptyResponse.newBuilder().setMessage("Stored").build());
        responseObserver.onCompleted();
    }

    @Override
    public void get(KeyRequest request, StreamObserver<ValueResponse> responseObserver) {
        logger.debug("📥 gRPC GET: {}", request.getKey());
        String val = cache.get(request.getKey());
        ValueResponse response = ValueResponse.newBuilder()
                .setValue(val != null ? val : "")
                .setFound(val != null)
                .build();
        responseObserver.onNext(response);
        responseObserver.onCompleted();
    }

    @Override
    public void leaseTasks(LeaseRequest request, StreamObserver<LeaseResponse> responseObserver) {
        logger.debug("📥 gRPC LEASE_TASKS: count={}", request.getMaxBatchSize());
        var keys = cache.leaseTasks(request.getMaxBatchSize());
        responseObserver.onNext(LeaseResponse.newBuilder().addAllKeys(keys).build());
        responseObserver.onCompleted();
    }

    @Override
    public void submitBatch(BatchResult request, StreamObserver<EmptyResponse> responseObserver) {
        logger.info("📥 gRPC SUBMIT_BATCH: size={}", request.getResultsCount());
        for (var entry : request.getResultsList()) {
            cache.put(entry.getKey(), entry.getEmbeddingJson());
            cache.resolveTask(entry.getKey());
        }
        responseObserver.onNext(EmptyResponse.newBuilder().setMessage("Batch Processed").build());
        responseObserver.onCompleted();
    }

    @Override
    public void clear(EmptyRequest request, StreamObserver<EmptyResponse> responseObserver) {
        logger.info("📥 gRPC CLEAR");
        cache.clear();
        responseObserver.onNext(EmptyResponse.newBuilder().setMessage("Cleared").build());
        responseObserver.onCompleted();
    }
}