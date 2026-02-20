// PerceptionAdapter.h
// Resize and encode pixel data to JPEG/PNG.
// Designed to run on a worker thread to keep cost off render and game threads.

#pragma once

#include "CoreMinimal.h"
#include "PerceptionTypes.h"

class FPerceptionAdapter
{
public:
	/** Resize RGBA pixel array from source size to target size using bilinear filtering. */
	static TArray<FColor> Resize(const TArray<FColor>& Source,
	                              FIntPoint SourceSize, FIntPoint TargetSize);

	/** Encode RGBA pixels to JPEG or PNG bytes. Quality is 1-100 (JPEG only). */
	static TArray<uint8> Encode(const TArray<FColor>& Pixels, FIntPoint Size,
	                             EPerceptionImageFormat Format, int32 Quality = 85);
};
