// PixelBus.h
// Triple-buffered latest-frame latch. The producer (render thread) writes frames
// and the consumer (HTTP/game thread) reads the latest; all slot access is guarded
// by a mutex so a reader's pixel copy can't be torn by the producer reusing a slot.
// The latest-frame counter stays atomic for cheap lock-free "is there a new frame?".

#pragma once

#include "CoreMinimal.h"
#include "PerceptionTypes.h"

class FPixelBus
{
public:
	FPixelBus();

	/** Producer: write a completed frame into the next slot. Thread-safe. */
	void WriteFrame(TArray<FColor>&& Pixels, FIntPoint Size,
	                int64 FrameNumber, double Timestamp);

	/** Consumer: read the latest completed frame. Returns false if no frame available. */
	bool ReadLatest(TArray<FColor>& OutPixels, FIntPoint& OutSize,
	                int64& OutFrameNumber, double& OutTimestamp) const;

	/** Check if a new frame has arrived since the given frame number. */
	bool HasNewFrame(int64 LastSeenFrame) const;

	/** Get the latest frame number (0 if no frames written). */
	int64 GetLatestFrameNumber() const;

	/** Attach metadata to the most recently written frame. Call from game thread. */
	void AttachMetadata(const FPerceptionMetadata& Metadata);

	/** Read the latest frame as a full perception packet (before encode). */
	bool ReadLatestWithMetadata(TArray<FColor>& OutPixels, FIntPoint& OutSize,
	                            FPerceptionMetadata& OutMetadata,
	                            int64& OutFrameNumber, double& OutTimestamp) const;

private:
	struct FFrameSlot
	{
		TArray<FColor> Pixels;
		FIntPoint Size = FIntPoint::ZeroValue;
		FPerceptionMetadata Metadata;
		int64 FrameNumber = 0;
		double Timestamp = 0.0;
		FThreadSafeBool bReady;
	};

	static constexpr int32 NUM_SLOTS = 3;
	FFrameSlot Slots[NUM_SLOTS];

	TAtomic<int32> WriteIndex;
	TAtomic<int64> LatestFrame;

	// Guards all slot access across the render-thread producer and the consumer
	// thread (read + metadata attach), preventing torn pixel-array copies.
	mutable FCriticalSection BusLock;
};
