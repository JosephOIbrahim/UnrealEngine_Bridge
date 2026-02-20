// PixelBus.h
// Lock-free ring buffer with latest-frame latch semantics.
// Producer (render thread) writes frames, consumer (HTTP handler) reads the latest.

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

	// Critical section for metadata attachment (game thread only)
	mutable FCriticalSection MetadataLock;
};
