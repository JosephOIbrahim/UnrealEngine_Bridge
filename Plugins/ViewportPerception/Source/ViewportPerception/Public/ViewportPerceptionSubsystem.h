// ViewportPerceptionSubsystem.h
// UEditorSubsystem that orchestrates the viewport perception pipeline:
// FrameProducer -> PixelBus -> MetadataCollector -> PerceptionAdapter -> PerceptionEndpoint

#pragma once

#include "CoreMinimal.h"
#include "EditorSubsystem.h"
#include "Containers/Ticker.h"
#include "PerceptionTypes.h"

// Full includes required — TUniquePtr needs complete types for destructor in UHT-generated code
#include "FrameProducer.h"
#include "PixelBus.h"
#include "MetadataCollector.h"
#include "PerceptionEndpoint.h"

#include "ViewportPerceptionSubsystem.generated.h"

UCLASS()
class VIEWPORTPERCEPTION_API UViewportPerceptionSubsystem : public UEditorSubsystem
{
	GENERATED_BODY()

public:
	// --- Lifecycle ---

	virtual void Initialize(FSubsystemCollectionBase& Collection) override;
	virtual void Deinitialize() override;

	// --- Control ---

	UFUNCTION(BlueprintCallable, Category = "ViewportPerception")
	void StartCapture(float MaxFPS = 5.0f, int32 Width = 1280, int32 Height = 720);

	UFUNCTION(BlueprintCallable, Category = "ViewportPerception")
	void StopCapture();

	UFUNCTION(BlueprintCallable, Category = "ViewportPerception")
	void RequestSingleFrame();

	// --- Configuration ---

	UFUNCTION(BlueprintCallable, Category = "ViewportPerception")
	void SetCaptureResolution(int32 Width, int32 Height);

	UFUNCTION(BlueprintCallable, Category = "ViewportPerception")
	void SetMaxCaptureRate(float FPS);

	UFUNCTION(BlueprintCallable, Category = "ViewportPerception")
	void SetImageFormat(EPerceptionImageFormat Format);

	UFUNCTION(BlueprintCallable, Category = "ViewportPerception")
	void SetJPEGQuality(int32 Quality);

	// --- Reading ---

	FPerceptionPacket GetLatestPacket();

	UFUNCTION(BlueprintCallable, Category = "ViewportPerception")
	bool IsCapturing() const;

	UFUNCTION(BlueprintCallable, Category = "ViewportPerception")
	bool HasNewFrame() const;

	FPerceptionEndpoint* GetEndpoint() const { return Endpoint.Get(); }

private:
	void OnTick(float DeltaTime);

	TUniquePtr<FFrameProducer> Producer;
	TUniquePtr<FPixelBus> Bus;
	TUniquePtr<FMetadataCollector> Collector;
	TUniquePtr<FPerceptionEndpoint> Endpoint;

	// Config
	FIntPoint CaptureResolution = FIntPoint(1280, 720);
	EPerceptionImageFormat ImageFormat = EPerceptionImageFormat::JPEG;
	int32 JPEGQuality = 85;

	// State
	int64 LastSeenFrame = 0;
	bool bSingleFrameRequested = false;
	bool bCapturing = false;

	FTSTicker::FDelegateHandle TickDelegateHandle;
};
