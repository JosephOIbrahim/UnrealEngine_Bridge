// MetadataCollector.h
// Gathers scene context (camera, selection, viewport state) on the game thread.

#pragma once

#include "CoreMinimal.h"
#include "PerceptionTypes.h"

class FMetadataCollector
{
public:
	/** Collect current scene metadata. Must be called on the game thread. */
	FPerceptionMetadata Collect();
};
