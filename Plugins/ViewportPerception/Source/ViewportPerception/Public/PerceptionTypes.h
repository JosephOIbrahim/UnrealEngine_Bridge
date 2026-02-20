// PerceptionTypes.h
// Shared types for the Viewport Perception system.

#pragma once

#include "CoreMinimal.h"
#include "PerceptionTypes.generated.h"

/** Image format for perception output. */
UENUM(BlueprintType)
enum class EPerceptionImageFormat : uint8
{
	JPEG UMETA(DisplayName = "JPEG"),
	PNG  UMETA(DisplayName = "PNG")
};

/** Camera state at the moment of capture. */
USTRUCT(BlueprintType)
struct FPerceptionCamera
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly)
	FVector Location = FVector::ZeroVector;

	UPROPERTY(BlueprintReadOnly)
	FRotator Rotation = FRotator::ZeroRotator;

	UPROPERTY(BlueprintReadOnly)
	float FOV = 90.0f;
};

/** Scene context at the moment of capture. */
USTRUCT(BlueprintType)
struct FPerceptionMetadata
{
	GENERATED_BODY()

	// Camera
	UPROPERTY(BlueprintReadOnly)
	FPerceptionCamera Camera;

	// Viewport
	UPROPERTY(BlueprintReadOnly)
	FIntPoint ViewportSize = FIntPoint::ZeroValue;

	UPROPERTY(BlueprintReadOnly)
	FString ViewportType;

	// Scene context
	UPROPERTY(BlueprintReadOnly)
	TArray<FString> SelectedActors;

	UPROPERTY(BlueprintReadOnly)
	FString MapName;

	UPROPERTY(BlueprintReadOnly)
	int32 ActorCount = 0;

	// Timing
	UPROPERTY(BlueprintReadOnly)
	float DeltaTime = 0.0f;

	UPROPERTY(BlueprintReadOnly)
	float FPS = 0.0f;
};

/** A complete perception packet: pixels + metadata. */
USTRUCT(BlueprintType)
struct FPerceptionPacket
{
	GENERATED_BODY()

	/** Encoded image bytes (JPEG or PNG). */
	UPROPERTY()
	TArray<uint8> ImageData;

	/** Image dimensions after resize/encode. */
	UPROPERTY(BlueprintReadOnly)
	int32 Width = 0;

	UPROPERTY(BlueprintReadOnly)
	int32 Height = 0;

	/** Format used for encoding. */
	UPROPERTY(BlueprintReadOnly)
	EPerceptionImageFormat Format = EPerceptionImageFormat::JPEG;

	/** Monotonically increasing frame counter. */
	UPROPERTY(BlueprintReadOnly)
	int64 FrameNumber = 0;

	/** Platform time at capture. */
	UPROPERTY(BlueprintReadOnly)
	double Timestamp = 0.0;

	/** Scene metadata collected at capture time. */
	UPROPERTY(BlueprintReadOnly)
	FPerceptionMetadata Metadata;

	/** True if this packet contains valid data. */
	UPROPERTY(BlueprintReadOnly)
	bool bValid = false;
};
