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
    public void submitTask(Task request, StreamObserver<EmptyResponse> responseObserver) {
        cache.submitTask(request.getHash(), request.getSequence(), request.getModelId());
        responseObserver.onNext(EmptyResponse.newBuilder().setMessage("Queued").build());
        responseObserver.onCompleted();
    }

    @Override
    public void leaseTasks(LeaseRequest request, StreamObserver<LeaseResponse> responseObserver) {
        var entries = cache.leaseTasks(request.getMaxBatchSize(), request.getTargetModelId());
        LeaseResponse.Builder responseBuilder = LeaseResponse.newBuilder();
        for (var entry : entries) {
            responseBuilder.addTasks(Task.newBuilder()
                    .setHash(entry.hash())
                    .setSequence(entry.sequence())
                    .setModelId(entry.modelId())
                    .build());
        }
        responseObserver.onNext(responseBuilder.build());
        responseObserver.onCompleted();
    }

    @Override
    public void get(KeyRequest request, StreamObserver<ValueResponse> responseObserver) {
        var storedVal = cache.get(request.getKey(), request.getModelId());

        ValueResponse.Builder builder = ValueResponse.newBuilder()
                .setFound(storedVal != null)
                .setModelId(request.getModelId());

        if (storedVal != null) {
            builder.setValue(storedVal.json());
            builder.setConfidenceScore(storedVal.confidence());
        }

        responseObserver.onNext(builder.build());
        responseObserver.onCompleted();
    }

    @Override
    public void put(CacheEntry request, StreamObserver<EmptyResponse> responseObserver) {
        cache.put(request.getKey(), request.getModelId(), request.getValue(), request.getConfidenceScore());
        responseObserver.onNext(EmptyResponse.newBuilder().setMessage("Stored").build());
        responseObserver.onCompleted();
    }

    @Override
    public void submitBatch(BatchResult request, StreamObserver<EmptyResponse> responseObserver) {
        String modelId = request.getModelId();
        for (var entry : request.getResultsList()) {
            cache.put(entry.getKey(), modelId, entry.getEmbeddingJson(), entry.getConfidenceScore());
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