// PixelBus.cpp

#include "PixelBus.h"

FPixelBus::FPixelBus()
	: WriteIndex(0)
	, LatestFrame(0)
{
}

void FPixelBus::WriteFrame(TArray<FColor>&& Pixels, FIntPoint Size,
                           int64 FrameNumber, double Timestamp)
{
	// Advance write index (wraps around NUM_SLOTS)
	const int32 SlotIndex = WriteIndex.Load() % NUM_SLOTS;

	FFrameSlot& Slot = Slots[SlotIndex];
	Slot.bReady = false;  // Mark slot as being written

	Slot.Pixels = MoveTemp(Pixels);
	Slot.Size = Size;
	Slot.FrameNumber = FrameNumber;
	Slot.Timestamp = Timestamp;

	Slot.bReady = true;  // Mark slot as readable

	// Update latest frame counter and advance write index
	LatestFrame.Store(FrameNumber);
	WriteIndex.Store(SlotIndex + 1);
}

bool FPixelBus::ReadLatest(TArray<FColor>& OutPixels, FIntPoint& OutSize,
                           int64& OutFrameNumber, double& OutTimestamp) const
{
	// Find the slot with the highest frame number that is ready
	int64 BestFrame = 0;
	int32 BestSlot = -1;

	for (int32 i = 0; i < NUM_SLOTS; ++i)
	{
		if (Slots[i].bReady && Slots[i].FrameNumber > BestFrame)
		{
			BestFrame = Slots[i].FrameNumber;
			BestSlot = i;
		}
	}

	if (BestSlot < 0)
	{
		return false;
	}

	const FFrameSlot& Slot = Slots[BestSlot];
	OutPixels = Slot.Pixels;  // Copy
	OutSize = Slot.Size;
	OutFrameNumber = Slot.FrameNumber;
	OutTimestamp = Slot.Timestamp;
	return true;
}

bool FPixelBus::HasNewFrame(int64 LastSeenFrame) const
{
	return LatestFrame.Load() > LastSeenFrame;
}

int64 FPixelBus::GetLatestFrameNumber() const
{
	return LatestFrame.Load();
}

void FPixelBus::AttachMetadata(const FPerceptionMetadata& Metadata)
{
	FScopeLock Lock(&MetadataLock);

	// Attach to the most recently written slot
	int64 BestFrame = 0;
	int32 BestSlot = -1;

	for (int32 i = 0; i < NUM_SLOTS; ++i)
	{
		if (Slots[i].bReady && Slots[i].FrameNumber > BestFrame)
		{
			BestFrame = Slots[i].FrameNumber;
			BestSlot = i;
		}
	}

	if (BestSlot >= 0)
	{
		Slots[BestSlot].Metadata = Metadata;
	}
}

bool FPixelBus::ReadLatestWithMetadata(TArray<FColor>& OutPixels, FIntPoint& OutSize,
                                       FPerceptionMetadata& OutMetadata,
                                       int64& OutFrameNumber, double& OutTimestamp) const
{
	FScopeLock Lock(&MetadataLock);

	int64 BestFrame = 0;
	int32 BestSlot = -1;

	for (int32 i = 0; i < NUM_SLOTS; ++i)
	{
		if (Slots[i].bReady && Slots[i].FrameNumber > BestFrame)
		{
			BestFrame = Slots[i].FrameNumber;
			BestSlot = i;
		}
	}

	if (BestSlot < 0)
	{
		return false;
	}

	const FFrameSlot& Slot = Slots[BestSlot];
	OutPixels = Slot.Pixels;
	OutSize = Slot.Size;
	OutMetadata = Slot.Metadata;
	OutFrameNumber = Slot.FrameNumber;
	OutTimestamp = Slot.Timestamp;
	return true;
}
