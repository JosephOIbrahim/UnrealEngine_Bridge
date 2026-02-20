// PerceptionEndpoint.cpp

#include "PerceptionEndpoint.h"
#include "ViewportPerceptionSubsystem.h"
#include "ViewportPerceptionModule.h"
#include "HttpServerModule.h"
#include "IHttpRouter.h"
#include "HttpServerRequest.h"
#include "HttpServerResponse.h"
#include "Misc/Base64.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
#include "Serialization/JsonReader.h"

FPerceptionEndpoint::FPerceptionEndpoint(UViewportPerceptionSubsystem* InSubsystem)
	: Subsystem(InSubsystem)
{
}

FPerceptionEndpoint::~FPerceptionEndpoint()
{
	Stop();
}

void FPerceptionEndpoint::Start()
{
	if (bRunning)
	{
		return;
	}

	FHttpServerModule& HttpModule = FHttpServerModule::Get();
	TSharedPtr<IHttpRouter> Router = HttpModule.GetHttpRouter(PERCEPTION_PORT);

	if (!Router.IsValid())
	{
		UE_LOG(LogViewportPerception, Warning, TEXT("Failed to get HTTP router on port %d"), PERCEPTION_PORT);
		return;
	}

	// GET /perception/frame
	RouteHandles.Add(Router->BindRoute(
		FHttpPath(TEXT("/perception/frame")),
		EHttpServerRequestVerbs::VERB_GET,
		FHttpRequestHandler::CreateRaw(this, &FPerceptionEndpoint::HandleFrame)
	));

	// GET /perception/status
	RouteHandles.Add(Router->BindRoute(
		FHttpPath(TEXT("/perception/status")),
		EHttpServerRequestVerbs::VERB_GET,
		FHttpRequestHandler::CreateRaw(this, &FPerceptionEndpoint::HandleStatus)
	));

	// PUT /perception/config
	RouteHandles.Add(Router->BindRoute(
		FHttpPath(TEXT("/perception/config")),
		EHttpServerRequestVerbs::VERB_PUT,
		FHttpRequestHandler::CreateRaw(this, &FPerceptionEndpoint::HandleConfig)
	));

	// PUT /perception/start
	RouteHandles.Add(Router->BindRoute(
		FHttpPath(TEXT("/perception/start")),
		EHttpServerRequestVerbs::VERB_PUT,
		FHttpRequestHandler::CreateRaw(this, &FPerceptionEndpoint::HandleStart)
	));

	// PUT /perception/stop
	RouteHandles.Add(Router->BindRoute(
		FHttpPath(TEXT("/perception/stop")),
		EHttpServerRequestVerbs::VERB_PUT,
		FHttpRequestHandler::CreateRaw(this, &FPerceptionEndpoint::HandleStop)
	));

	// GET /perception/single
	RouteHandles.Add(Router->BindRoute(
		FHttpPath(TEXT("/perception/single")),
		EHttpServerRequestVerbs::VERB_GET,
		FHttpRequestHandler::CreateRaw(this, &FPerceptionEndpoint::HandleSingle)
	));

	// PUT /perception/single
	RouteHandles.Add(Router->BindRoute(
		FHttpPath(TEXT("/perception/single")),
		EHttpServerRequestVerbs::VERB_PUT,
		FHttpRequestHandler::CreateRaw(this, &FPerceptionEndpoint::HandleSingle)
	));

	HttpModule.StartAllListeners();
	bRunning = true;

	UE_LOG(LogViewportPerception, Log, TEXT("HTTP endpoint started on port %d"), PERCEPTION_PORT);
}

void FPerceptionEndpoint::Stop()
{
	if (!bRunning)
	{
		return;
	}

	FHttpServerModule& HttpModule = FHttpServerModule::Get();
	TSharedPtr<IHttpRouter> Router = HttpModule.GetHttpRouter(PERCEPTION_PORT);

	if (Router.IsValid())
	{
		for (const FHttpRouteHandle& Handle : RouteHandles)
		{
			Router->UnbindRoute(Handle);
		}
	}

	RouteHandles.Empty();
	bRunning = false;

	UE_LOG(LogViewportPerception, Log, TEXT("HTTP endpoint stopped"));
}

bool FPerceptionEndpoint::HandleFrame(const FHttpServerRequest& Request,
                                       const FHttpResultCallback& OnComplete)
{
	if (!Subsystem)
	{
		SendJsonResponse(OnComplete, TEXT("{\"error\":\"Subsystem not available\"}"), 503);
		return true;
	}

	FPerceptionPacket Packet = Subsystem->GetLatestPacket();

	if (!Packet.bValid)
	{
		SendJsonResponse(OnComplete, TEXT("{\"error\":\"No frame available\"}"), 404);
		return true;
	}

	// Build JSON response
	TSharedRef<FJsonObject> Root = MakeShared<FJsonObject>();

	// Base64 encode the image
	FString ImageBase64 = FBase64::Encode(Packet.ImageData.GetData(), Packet.ImageData.Num());
	Root->SetStringField(TEXT("image"), ImageBase64);
	Root->SetNumberField(TEXT("width"), Packet.Width);
	Root->SetNumberField(TEXT("height"), Packet.Height);
	Root->SetStringField(TEXT("format"),
		Packet.Format == EPerceptionImageFormat::PNG ? TEXT("png") : TEXT("jpeg"));
	Root->SetNumberField(TEXT("frame_number"), static_cast<double>(Packet.FrameNumber));
	Root->SetNumberField(TEXT("timestamp"), Packet.Timestamp);

	// Camera
	TSharedRef<FJsonObject> CameraObj = MakeShared<FJsonObject>();
	TArray<TSharedPtr<FJsonValue>> LocArr;
	LocArr.Add(MakeShared<FJsonValueNumber>(Packet.Metadata.Camera.Location.X));
	LocArr.Add(MakeShared<FJsonValueNumber>(Packet.Metadata.Camera.Location.Y));
	LocArr.Add(MakeShared<FJsonValueNumber>(Packet.Metadata.Camera.Location.Z));
	CameraObj->SetArrayField(TEXT("location"), LocArr);

	TArray<TSharedPtr<FJsonValue>> RotArr;
	RotArr.Add(MakeShared<FJsonValueNumber>(Packet.Metadata.Camera.Rotation.Pitch));
	RotArr.Add(MakeShared<FJsonValueNumber>(Packet.Metadata.Camera.Rotation.Yaw));
	RotArr.Add(MakeShared<FJsonValueNumber>(Packet.Metadata.Camera.Rotation.Roll));
	CameraObj->SetArrayField(TEXT("rotation"), RotArr);
	CameraObj->SetNumberField(TEXT("fov"), Packet.Metadata.Camera.FOV);
	Root->SetObjectField(TEXT("camera"), CameraObj);

	// Viewport
	TSharedRef<FJsonObject> ViewportObj = MakeShared<FJsonObject>();
	TArray<TSharedPtr<FJsonValue>> SizeArr;
	SizeArr.Add(MakeShared<FJsonValueNumber>(Packet.Metadata.ViewportSize.X));
	SizeArr.Add(MakeShared<FJsonValueNumber>(Packet.Metadata.ViewportSize.Y));
	ViewportObj->SetArrayField(TEXT("size"), SizeArr);
	ViewportObj->SetStringField(TEXT("type"), Packet.Metadata.ViewportType);
	Root->SetObjectField(TEXT("viewport"), ViewportObj);

	// Selection
	TArray<TSharedPtr<FJsonValue>> SelArr;
	for (const FString& Name : Packet.Metadata.SelectedActors)
	{
		SelArr.Add(MakeShared<FJsonValueString>(Name));
	}
	Root->SetArrayField(TEXT("selection"), SelArr);

	// Scene
	TSharedRef<FJsonObject> SceneObj = MakeShared<FJsonObject>();
	SceneObj->SetStringField(TEXT("map"), Packet.Metadata.MapName);
	SceneObj->SetNumberField(TEXT("actor_count"), Packet.Metadata.ActorCount);
	Root->SetObjectField(TEXT("scene"), SceneObj);

	// Timing
	TSharedRef<FJsonObject> TimingObj = MakeShared<FJsonObject>();
	TimingObj->SetNumberField(TEXT("delta_time"), Packet.Metadata.DeltaTime);
	TimingObj->SetNumberField(TEXT("fps"), Packet.Metadata.FPS);
	Root->SetObjectField(TEXT("timing"), TimingObj);

	// Serialize
	FString JsonBody;
	TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&JsonBody);
	FJsonSerializer::Serialize(Root, Writer);

	SendJsonResponse(OnComplete, JsonBody);
	return true;
}

bool FPerceptionEndpoint::HandleStatus(const FHttpServerRequest& Request,
                                        const FHttpResultCallback& OnComplete)
{
	TSharedRef<FJsonObject> Root = MakeShared<FJsonObject>();

	Root->SetBoolField(TEXT("capturing"), Subsystem ? Subsystem->IsCapturing() : false);
	Root->SetBoolField(TEXT("has_new_frame"), Subsystem ? Subsystem->HasNewFrame() : false);
	Root->SetNumberField(TEXT("port"), PERCEPTION_PORT);
	Root->SetBoolField(TEXT("running"), bRunning);

	FString JsonBody;
	TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&JsonBody);
	FJsonSerializer::Serialize(Root, Writer);

	SendJsonResponse(OnComplete, JsonBody);
	return true;
}

bool FPerceptionEndpoint::HandleConfig(const FHttpServerRequest& Request,
                                        const FHttpResultCallback& OnComplete)
{
	if (!Subsystem)
	{
		SendJsonResponse(OnComplete, TEXT("{\"error\":\"Subsystem not available\"}"), 503);
		return true;
	}

	// Parse request body as JSON
	if (Request.Body.Num() == 0)
	{
		SendJsonResponse(OnComplete, TEXT("{\"status\":\"no changes\"}"));
		return true;
	}

	FString BodyStr = UTF8_TO_TCHAR(reinterpret_cast<const char*>(Request.Body.GetData()));
	TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(BodyStr);
	TSharedPtr<FJsonObject> Body;

	if (FJsonSerializer::Deserialize(Reader, Body) && Body.IsValid())
	{
		double MaxFPS;
		if (Body->TryGetNumberField(TEXT("max_fps"), MaxFPS))
		{
			Subsystem->SetMaxCaptureRate(static_cast<float>(MaxFPS));
		}

		int32 Width = 0, Height = 0;
		if (Body->TryGetNumberField(TEXT("width"), Width) &&
		    Body->TryGetNumberField(TEXT("height"), Height))
		{
			Subsystem->SetCaptureResolution(Width, Height);
		}

		FString Format;
		if (Body->TryGetStringField(TEXT("format"), Format))
		{
			Subsystem->SetImageFormat(
				Format.Equals(TEXT("png"), ESearchCase::IgnoreCase)
					? EPerceptionImageFormat::PNG
					: EPerceptionImageFormat::JPEG
			);
		}

		int32 Quality;
		if (Body->TryGetNumberField(TEXT("quality"), Quality))
		{
			Subsystem->SetJPEGQuality(Quality);
		}
	}

	SendJsonResponse(OnComplete, TEXT("{\"status\":\"configured\"}"));
	return true;
}

bool FPerceptionEndpoint::HandleStart(const FHttpServerRequest& Request,
                                       const FHttpResultCallback& OnComplete)
{
	if (!Subsystem)
	{
		SendJsonResponse(OnComplete, TEXT("{\"error\":\"Subsystem not available\"}"), 503);
		return true;
	}

	// Parse optional params from body (defaults used if body is empty)
	float FPS = 5.0f;
	int32 Width = 1280, Height = 720;

	if (Request.Body.Num() > 0)
	{
		FString BodyStr = UTF8_TO_TCHAR(reinterpret_cast<const char*>(Request.Body.GetData()));
		TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(BodyStr);
		TSharedPtr<FJsonObject> Body;

		if (FJsonSerializer::Deserialize(Reader, Body) && Body.IsValid())
		{
			double V;
			if (Body->TryGetNumberField(TEXT("fps"), V)) FPS = static_cast<float>(V);
			Body->TryGetNumberField(TEXT("width"), Width);
			Body->TryGetNumberField(TEXT("height"), Height);
		}
	}

	Subsystem->StartCapture(FPS, Width, Height);
	SendJsonResponse(OnComplete, TEXT("{\"status\":\"capturing\"}"));
	return true;
}

bool FPerceptionEndpoint::HandleStop(const FHttpServerRequest& Request,
                                      const FHttpResultCallback& OnComplete)
{
	if (Subsystem)
	{
		Subsystem->StopCapture();
	}

	SendJsonResponse(OnComplete, TEXT("{\"status\":\"stopped\"}"));
	return true;
}

bool FPerceptionEndpoint::HandleSingle(const FHttpServerRequest& Request,
                                        const FHttpResultCallback& OnComplete)
{
	if (!Subsystem)
	{
		SendJsonResponse(OnComplete, TEXT("{\"error\":\"Subsystem not available\"}"), 503);
		return true;
	}

	// If not capturing, start a temporary capture
	const bool WasCapturing = Subsystem->IsCapturing();
	if (!WasCapturing)
	{
		Subsystem->RequestSingleFrame();
	}

	// Give the frame a moment to arrive, then try to read
	// We schedule a delayed response via async
	AsyncTask(ENamedThreads::GameThread, [this, OnComplete, WasCapturing]()
	{
		if (!Subsystem)
		{
			SendJsonResponse(OnComplete, TEXT("{\"error\":\"Subsystem destroyed\"}"), 500);
			return;
		}

		// Try to get a frame with a brief spin (up to 500ms)
		FPerceptionPacket Packet;
		constexpr float MaxWait = 0.5f;
		constexpr float PollInterval = 0.05f;
		float Waited = 0.0f;

		while (Waited < MaxWait)
		{
			Packet = Subsystem->GetLatestPacket();
			if (Packet.bValid)
			{
				break;
			}
			FPlatformProcess::Sleep(PollInterval);
			Waited += PollInterval;
		}

		// Stop if we started it
		if (!WasCapturing)
		{
			Subsystem->StopCapture();
		}

		if (!Packet.bValid)
		{
			SendJsonResponse(OnComplete, TEXT("{\"error\":\"Capture timed out\"}"), 408);
			return;
		}

		// Build the same JSON response as HandleFrame
		TSharedRef<FJsonObject> Root = MakeShared<FJsonObject>();
		FString ImageBase64 = FBase64::Encode(Packet.ImageData.GetData(), Packet.ImageData.Num());
		Root->SetStringField(TEXT("image"), ImageBase64);
		Root->SetNumberField(TEXT("width"), Packet.Width);
		Root->SetNumberField(TEXT("height"), Packet.Height);
		Root->SetStringField(TEXT("format"),
			Packet.Format == EPerceptionImageFormat::PNG ? TEXT("png") : TEXT("jpeg"));
		Root->SetNumberField(TEXT("frame_number"), static_cast<double>(Packet.FrameNumber));
		Root->SetNumberField(TEXT("timestamp"), Packet.Timestamp);

		TSharedRef<FJsonObject> CameraObj = MakeShared<FJsonObject>();
		TArray<TSharedPtr<FJsonValue>> LocArr;
		LocArr.Add(MakeShared<FJsonValueNumber>(Packet.Metadata.Camera.Location.X));
		LocArr.Add(MakeShared<FJsonValueNumber>(Packet.Metadata.Camera.Location.Y));
		LocArr.Add(MakeShared<FJsonValueNumber>(Packet.Metadata.Camera.Location.Z));
		CameraObj->SetArrayField(TEXT("location"), LocArr);
		TArray<TSharedPtr<FJsonValue>> RotArr;
		RotArr.Add(MakeShared<FJsonValueNumber>(Packet.Metadata.Camera.Rotation.Pitch));
		RotArr.Add(MakeShared<FJsonValueNumber>(Packet.Metadata.Camera.Rotation.Yaw));
		RotArr.Add(MakeShared<FJsonValueNumber>(Packet.Metadata.Camera.Rotation.Roll));
		CameraObj->SetArrayField(TEXT("rotation"), RotArr);
		CameraObj->SetNumberField(TEXT("fov"), Packet.Metadata.Camera.FOV);
		Root->SetObjectField(TEXT("camera"), CameraObj);

		TSharedRef<FJsonObject> SceneObj = MakeShared<FJsonObject>();
		SceneObj->SetStringField(TEXT("map"), Packet.Metadata.MapName);
		SceneObj->SetNumberField(TEXT("actor_count"), Packet.Metadata.ActorCount);
		Root->SetObjectField(TEXT("scene"), SceneObj);

		TArray<TSharedPtr<FJsonValue>> SelArr;
		for (const FString& Name : Packet.Metadata.SelectedActors)
		{
			SelArr.Add(MakeShared<FJsonValueString>(Name));
		}
		Root->SetArrayField(TEXT("selection"), SelArr);

		FString JsonBody;
		TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&JsonBody);
		FJsonSerializer::Serialize(Root, Writer);

		SendJsonResponse(OnComplete, JsonBody);
	});

	return true;  // We'll respond asynchronously
}

void FPerceptionEndpoint::SendJsonResponse(const FHttpResultCallback& OnComplete,
                                            const FString& JsonBody, int32 StatusCode)
{
	auto Response = FHttpServerResponse::Create(JsonBody, TEXT("application/json"));
	OnComplete(MoveTemp(Response));
}
