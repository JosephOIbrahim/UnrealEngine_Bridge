// FrameProducer.h
// Hooks the backbuffer presentation and performs GPU->CPU readback.
// Runs the readback on the render thread with a throttle gate.

#pragma once

#include "CoreMinimal.h"
#include "RHI.h"
#include "RHIGPUReadback.h"
#include "Runtime/Launch/Resources/Version.h"

class FPixelBus;
#if ENGINE_MAJOR_VERSION == 5 && ENGINE_MINOR_VERSION >= 8
class ISlateViewportProvider;
#endif

class FFrameProducer
{
public:
	FFrameProducer();
	~FFrameProducer();

	/** Begin capturing frames. Hooks OnBackBufferReadyToPresent. */
	void Start(FPixelBus* InPixelBus);

	/** Stop capturing and unhook the delegate. */
	void Stop();

	/** Set minimum interval between captures (1/MaxFPS). */
	void SetThrottleInterval(double Seconds);

	/** True if currently hooked and capturing. */
	bool IsActive() const { return bActive; }

private:
	/** Called on the render thread when the backbuffer is ready.
	 *  5.8 changed OnBackBufferReadyToPresent's second param from the raw
	 *  texture to an ISlateViewportProvider — both signatures are kept so the
	 *  plugin compiles against 5.7 and 5.8 from the same source. */
#if ENGINE_MAJOR_VERSION == 5 && ENGINE_MINOR_VERSION >= 8
	void OnFrameBufferReady(SWindow& SlateWindow, ISlateViewportProvider& ViewportProvider);
#else
	void OnFrameBufferReady(SWindow& SlateWindow, const FTextureRHIRef& FrameBufferRef);
#endif

	FDelegateHandle DelegateHandle;
	FPixelBus* PixelBus = nullptr;

	double MinCaptureInterval = 0.2;  // 5 fps default
	double LastCaptureTime = 0.0;
	TAtomic<int64> FrameCounter;
	bool bActive = false;

	// Asynchronous GPU->CPU readback (render thread only). We enqueue a copy on
	// one present and drain the completed result on a later present, so the render
	// thread never blocks on a synchronous ReadSurfaceData.
	TUniquePtr<FRHIGPUTextureReadback> Readback;
	bool bReadbackPending = false;
	FIntPoint PendingSize = FIntPoint::ZeroValue;
	int64 PendingFrameNumber = 0;
	double PendingTimestamp = 0.0;
};
