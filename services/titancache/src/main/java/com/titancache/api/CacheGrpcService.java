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
    private final TitanCache cache;

    public CacheGrpcService(TitanCache cache) {
        this.cache = cache;
    }

    @Override
    public void submitTask(KeyRequest request, StreamObserver<EmptyResponse> responseObserver) {
        // Enforce Model ID presence
        if (request.getModelId().isEmpty()) {
            logger.warn("Rejected SubmitTask: missing model_id");
            responseObserver.onError(new IllegalArgumentException("model_id is required"));
            return;
        }

        cache.submitTask(request.getKey(), request.getModelId());
        responseObserver.onNext(EmptyResponse.newBuilder().setMessage("Queued").build());
        responseObserver.onCompleted();
    }

    @Override
    public void get(KeyRequest request, StreamObserver<ValueResponse> responseObserver) {
        String val = cache.get(request.getKey(), request.getModelId());

        ValueResponse.Builder builder = ValueResponse.newBuilder()
                .setFound(val != null)
                .setModelId(request.getModelId());

        if (val != null) {
            builder.setValue(val);
        }

        responseObserver.onNext(builder.build());
        responseObserver.onCompleted();
    }

    @Override
    public void put(CacheEntry request, StreamObserver<EmptyResponse> responseObserver) {
        cache.put(request.getKey(), request.getModelId(), request.getValue());
        responseObserver.onNext(EmptyResponse.newBuilder().setMessage("Stored").build());
        responseObserver.onCompleted();
    }

    @Override
    public void leaseTasks(LeaseRequest request, StreamObserver<LeaseResponse> responseObserver) {
        var keys = cache.leaseTasks(request.getMaxBatchSize(), request.getTargetModelId());

        // Wwe return the composites "hash:model_id"
        responseObserver.onNext(LeaseResponse.newBuilder().addAllKeys(keys).build());
        responseObserver.onCompleted();
    }

    @Override
    public void submitBatch(BatchResult request, StreamObserver<EmptyResponse> responseObserver) {
        String modelId = request.getModelId();
        for (var entry : request.getResultsList()) {
            // The key here is gonna be likely the RAW hash from the worker
            cache.put(entry.getKey(), modelId, entry.getEmbeddingJson());
            cache.resolveTask(entry.getKey(), modelId);
        }
        responseObserver.onNext(EmptyResponse.newBuilder().setMessage("Batch Processed").build());
        responseObserver.onCompleted();
    }

    @Override
    public void clear(EmptyRequest request, StreamObserver<EmptyResponse> responseObserver) {
        cache.clear();
        responseObserver.onNext(EmptyResponse.newBuilder().setMessage("Cleared").build());
        responseObserver.onCompleted();
    }
}