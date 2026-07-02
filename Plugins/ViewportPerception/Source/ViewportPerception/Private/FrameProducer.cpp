// FrameProducer.cpp

#include "FrameProducer.h"
#include "PixelBus.h"
#include "ViewportPerceptionModule.h"
#include "RHICommandList.h"
#include "RenderingThread.h"
#include "Framework/Application/SlateApplication.h"
#include "RHISurfaceDataConversion.h"
#if ENGINE_MAJOR_VERSION == 5 && ENGINE_MINOR_VERSION >= 8
#include "Slate/SlateViewportProvider.h"
#endif

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

	// Make sure no in-flight render-thread callback is mid-readback before we
	// release the staging buffer.
	FlushRenderingCommands();
	Readback.Reset();
	bReadbackPending = false;

	UE_LOG(LogViewportPerception, Log, TEXT("FrameProducer stopped"));
}

void FFrameProducer::SetThrottleInterval(double Seconds)
{
	MinCaptureInterval = FMath::Max(Seconds, 0.01);  // Cap at 100fps
}

#if ENGINE_MAJOR_VERSION == 5 && ENGINE_MINOR_VERSION >= 8
void FFrameProducer::OnFrameBufferReady(SWindow& SlateWindow, ISlateViewportProvider& ViewportProvider)
{
	FRHITexture* FrameBuffer = ViewportProvider.GetBackBufferResource();
#else
void FFrameProducer::OnFrameBufferReady(SWindow& SlateWindow, const FTextureRHIRef& FrameBufferRef)
{
	FRHITexture* FrameBuffer = FrameBufferRef.GetReference();
#endif
	// Runs on the render thread. All readback state below is render-thread-only,
	// so no synchronization is needed for it. We NEVER block the render thread:
	// a copy is enqueued on one present and drained on a later one once the GPU
	// has finished, instead of a synchronous ReadSurfaceData stall.
	if (!PixelBus || !FrameBuffer)
	{
		return;
	}

	FRHICommandListImmediate& RHICmdList = FRHICommandListImmediate::Get();

	// 1) Drain a previously-enqueued readback if the GPU has finished it.
	if (bReadbackPending && Readback.IsValid() && Readback->IsReady())
	{
		int32 RowPitchInPixels = 0;
		void* Mapped = Readback->Lock(RowPitchInPixels);
		if (Mapped && PendingSize.X > 0 && PendingSize.Y > 0)
		{
			const int32 Pitch = (RowPitchInPixels > 0) ? RowPitchInPixels : PendingSize.X;
			TArray<FColor> Pixels;
			Pixels.SetNumUninitialized(PendingSize.X * PendingSize.Y);
			const FColor* Src = static_cast<const FColor*>(Mapped);
			for (int32 Y = 0; Y < PendingSize.Y; ++Y)
			{
				FMemory::Memcpy(
					Pixels.GetData() + Y * PendingSize.X,
					Src + Y * Pitch,
					PendingSize.X * sizeof(FColor));
			}
			Readback->Unlock();
			PixelBus->WriteFrame(MoveTemp(Pixels), PendingSize, PendingFrameNumber, PendingTimestamp);
		}
		else if (Mapped)
		{
			Readback->Unlock();
		}
		bReadbackPending = false;
	}

	// 2) Throttle gate: only enqueue a new capture every MinCaptureInterval.
	const double Now = FPlatformTime::Seconds();
	if ((Now - LastCaptureTime) < MinCaptureInterval)
	{
		return;
	}

	// 3) Enqueue a new async copy if one isn't already in flight.
	if (!bReadbackPending)
	{
		if (!Readback.IsValid())
		{
			Readback = MakeUnique<FRHIGPUTextureReadback>(TEXT("ViewportPerceptionReadback"));
		}

		LastCaptureTime = Now;
		const int64 CurrentFrame = FrameCounter.Load() + 1;
		FrameCounter.Store(CurrentFrame);

		PendingSize = FrameBuffer->GetSizeXY();
		PendingFrameNumber = CurrentFrame;
		PendingTimestamp = Now;

		Readback->EnqueueCopy(RHICmdList, FrameBuffer);
		bReadbackPending = true;
	}
}
