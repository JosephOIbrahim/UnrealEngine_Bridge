// ViewportPerceptionSubsystem.cpp

#include "ViewportPerceptionSubsystem.h"
#include "ViewportPerceptionModule.h"
#include "FrameProducer.h"
#include "PixelBus.h"
#include "MetadataCollector.h"
#include "PerceptionAdapter.h"
#include "PerceptionEndpoint.h"
#include "Editor.h"

void UViewportPerceptionSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
	Super::Initialize(Collection);

	Producer = MakeUnique<FFrameProducer>();
	Bus = MakeUnique<FPixelBus>();
	Collector = MakeUnique<FMetadataCollector>();
	Endpoint = MakeUnique<FPerceptionEndpoint>(this);

	// Register tick for metadata collection (~20Hz)
	TickDelegateHandle = FTSTicker::GetCoreTicker().AddTicker(
		FTickerDelegate::CreateLambda([this](float DeltaTime) -> bool
		{
			this->OnTick(DeltaTime);
			return true;
		}),
		0.05f
	);

	Endpoint->Start();

	UE_LOG(LogViewportPerception, Log, TEXT("Subsystem initialized"));
}

void UViewportPerceptionSubsystem::Deinitialize()
{
	StopCapture();

	if (Endpoint)
	{
		Endpoint->Stop();
	}

	FTSTicker::GetCoreTicker().RemoveTicker(TickDelegateHandle);

	Endpoint.Reset();
	Collector.Reset();
	Bus.Reset();
	Producer.Reset();

	UE_LOG(LogViewportPerception, Log, TEXT("Subsystem deinitialized"));

	Super::Deinitialize();
}

void UViewportPerceptionSubsystem::StartCapture(float MaxFPS, int32 Width, int32 Height)
{
	CaptureResolution = FIntPoint(FMath::Max(Width, 64), FMath::Max(Height, 64));

	if (Producer && Bus)
	{
		Producer->SetThrottleInterval(1.0 / FMath::Clamp(MaxFPS, 0.1f, 60.0f));
		Producer->Start(Bus.Get());
		bCapturing = true;
		UE_LOG(LogViewportPerception, Log, TEXT("Capture started: %dx%d @ %.1f fps"),
			CaptureResolution.X, CaptureResolution.Y, MaxFPS);
	}
}

void UViewportPerceptionSubsystem::StopCapture()
{
	if (Producer)
	{
		Producer->Stop();
	}
	bCapturing = false;
	bSingleFrameRequested = false;
}

void UViewportPerceptionSubsystem::RequestSingleFrame()
{
	if (!bCapturing)
	{
		// Temporarily start capture
		StartCapture(30.0f, CaptureResolution.X, CaptureResolution.Y);
		bSingleFrameRequested = true;
	}
}

void UViewportPerceptionSubsystem::SetCaptureResolution(int32 Width, int32 Height)
{
	CaptureResolution = FIntPoint(FMath::Max(Width, 64), FMath::Max(Height, 64));
}

void UViewportPerceptionSubsystem::SetMaxCaptureRate(float FPS)
{
	if (Producer)
	{
		Producer->SetThrottleInterval(1.0 / FMath::Clamp(FPS, 0.1f, 60.0f));
	}
}

void UViewportPerceptionSubsystem::SetImageFormat(EPerceptionImageFormat Format)
{
	ImageFormat = Format;
}

void UViewportPerceptionSubsystem::SetJPEGQuality(int32 Quality)
{
	JPEGQuality = FMath::Clamp(Quality, 1, 100);
}

FPerceptionPacket UViewportPerceptionSubsystem::GetLatestPacket()
{
	FPerceptionPacket Packet;

	if (!Bus)
	{
		return Packet;
	}

	TArray<FColor> RawPixels;
	FIntPoint RawSize;
	FPerceptionMetadata Meta;
	int64 FrameNum;
	double Timestamp;

	if (!Bus->ReadLatestWithMetadata(RawPixels, RawSize, Meta, FrameNum, Timestamp))
	{
		return Packet;
	}

	LastSeenFrame = FrameNum;

	// Resize if needed
	TArray<FColor> Pixels = (RawSize != CaptureResolution)
		? FPerceptionAdapter::Resize(RawPixels, RawSize, CaptureResolution)
		: MoveTemp(RawPixels);

	// Encode
	TArray<uint8> Encoded = FPerceptionAdapter::Encode(Pixels, CaptureResolution, ImageFormat, JPEGQuality);

	if (Encoded.Num() == 0)
	{
		return Packet;
	}

	Packet.ImageData = MoveTemp(Encoded);
	Packet.Width = CaptureResolution.X;
	Packet.Height = CaptureResolution.Y;
	Packet.Format = ImageFormat;
	Packet.FrameNumber = FrameNum;
	Packet.Timestamp = Timestamp;
	Packet.Metadata = Meta;
	Packet.bValid = true;

	return Packet;
}

bool UViewportPerceptionSubsystem::IsCapturing() const
{
	return bCapturing && Producer && Producer->IsActive();
}

bool UViewportPerceptionSubsystem::HasNewFrame() const
{
	return Bus && Bus->HasNewFrame(LastSeenFrame);
}

void UViewportPerceptionSubsystem::OnTick(float DeltaTime)
{
	if (!bCapturing || !Bus || !Collector)
	{
		return;
	}

	// Attach metadata to the latest frame
	if (Bus->HasNewFrame(LastSeenFrame))
	{
		FPerceptionMetadata Meta = Collector->Collect();
		Bus->AttachMetadata(Meta);
	}

	// Handle single-frame request
	if (bSingleFrameRequested && Bus->GetLatestFrameNumber() > 0)
	{
		// Frame captured, stop
		bSingleFrameRequested = false;
		// Don't stop here -- let the endpoint read it first
		// StopCapture will be called by the endpoint after reading
	}
}
