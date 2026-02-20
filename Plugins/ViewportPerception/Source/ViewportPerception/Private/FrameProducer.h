// FrameProducer.h
// Hooks the backbuffer presentation and performs GPU->CPU readback.
// Runs the readback on the render thread with a throttle gate.

#pragma once

#include "CoreMinimal.h"
#include "RHI.h"

class FPixelBus;

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
	/** Called on the render thread when the backbuffer is ready. */
	void OnFrameBufferReady(SWindow& SlateWindow, const FTextureRHIRef& FrameBuffer);

	FDelegateHandle DelegateHandle;
	FPixelBus* PixelBus = nullptr;

	double MinCaptureInterval = 0.2;  // 5 fps default
	double LastCaptureTime = 0.0;
	TAtomic<int64> FrameCounter;
	bool bActive = false;
};
