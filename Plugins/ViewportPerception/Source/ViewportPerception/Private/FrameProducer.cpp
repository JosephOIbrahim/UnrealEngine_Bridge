// FrameProducer.cpp

#include "FrameProducer.h"
#include "PixelBus.h"
#include "ViewportPerceptionModule.h"
#include "RHICommandList.h"
#include "RenderingThread.h"
#include "Framework/Application/SlateApplication.h"
#include "RHISurfaceDataConversion.h"

FFrameProducer::FFrameProducer()
	: FrameCounter(0)
{
}

FFrameProducer::~FFrameProducer()
{
	Stop();
}

void FFrameProducer::Start(FPixelBus* InPixelBus)
{
	if (bActive)
	{
		return;
	}

	check(InPixelBus);
	PixelBus = InPixelBus;

	if (FSlateApplication::IsInitialized())
	{
		DelegateHandle = FSlateApplication::Get().GetRenderer()->OnBackBufferReadyToPresent().AddRaw(
			this, &FFrameProducer::OnFrameBufferReady);

		bActive = true;
		UE_LOG(LogViewportPerception, Log, TEXT("FrameProducer started (interval=%.2fs)"), MinCaptureInterval);
	}
	else
	{
		UE_LOG(LogViewportPerception, Warning, TEXT("Slate not initialized, cannot hook backbuffer"));
	}
}

void FFrameProducer::Stop()
{
	if (!bActive)
	{
		return;
	}

	if (FSlateApplication::IsInitialized() && DelegateHandle.IsValid())
	{
		FSlateApplication::Get().GetRenderer()->OnBackBufferReadyToPresent().Remove(DelegateHandle);
		DelegateHandle.Reset();
	}

	bActive = false;
	PixelBus = nullptr;
	UE_LOG(LogViewportPerception, Log, TEXT("FrameProducer stopped"));
}

void FFrameProducer::SetThrottleInterval(double Seconds)
{
	MinCaptureInterval = FMath::Max(Seconds, 0.01);  // Cap at 100fps
}

void FFrameProducer::OnFrameBufferReady(SWindow& SlateWindow, const FTextureRHIRef& FrameBuffer)
{
	// This runs on the render thread -- must be fast when skipping

	// Throttle gate: skip if too soon since last capture
	const double Now = FPlatformTime::Seconds();
	if ((Now - LastCaptureTime) < MinCaptureInterval)
	{
		return;
	}

	if (!PixelBus || !FrameBuffer.IsValid())
	{
		return;
	}

	LastCaptureTime = Now;
	const int64 PrevFrame = FrameCounter.Load();
	const int64 CurrentFrame = PrevFrame + 1;
	FrameCounter.Store(CurrentFrame);

	// Read the backbuffer pixels
	const FIntPoint Size = FrameBuffer->GetSizeXY();
	TArray<FColor> Pixels;

	FReadSurfaceDataFlags ReadFlags(RCM_UNorm);
	ReadFlags.SetLinearToGamma(false);

	// ReadSurfaceData on the current RHI command list
	FRHICommandListImmediate& RHICmdList = FRHICommandListImmediate::Get();
	RHICmdList.ReadSurfaceData(
		FrameBuffer,
		FIntRect(0, 0, Size.X, Size.Y),
		Pixels,
		ReadFlags
	);

	if (Pixels.Num() > 0)
	{
		PixelBus->WriteFrame(MoveTemp(Pixels), Size, CurrentFrame, Now);
	}
}
