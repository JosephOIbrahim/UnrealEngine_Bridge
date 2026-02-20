// PerceptionEndpoint.h
// Lightweight HTTP server serving perception packets on port 30011.
// Routes:
//   GET  /perception/frame   -> latest perception packet (JSON + base64 image)
//   GET  /perception/status  -> capture state, fps, buffer stats
//   PUT  /perception/config  -> set resolution, format, rate
//   PUT  /perception/start   -> begin capturing
//   PUT  /perception/stop    -> stop capturing
//   PUT  /perception/single  -> one-shot capture

#pragma once

#include "CoreMinimal.h"
#include "HttpServerModule.h"
#include "IHttpRouter.h"
#include "HttpRouteHandle.h"

class UViewportPerceptionSubsystem;

class FPerceptionEndpoint
{
public:
	explicit FPerceptionEndpoint(UViewportPerceptionSubsystem* InSubsystem);
	~FPerceptionEndpoint();

	/** Start the HTTP server and register routes. */
	void Start();

	/** Stop the HTTP server. */
	void Stop();

private:
	// Route handlers
	bool HandleFrame(const FHttpServerRequest& Request, const FHttpResultCallback& OnComplete);
	bool HandleStatus(const FHttpServerRequest& Request, const FHttpResultCallback& OnComplete);
	bool HandleConfig(const FHttpServerRequest& Request, const FHttpResultCallback& OnComplete);
	bool HandleStart(const FHttpServerRequest& Request, const FHttpResultCallback& OnComplete);
	bool HandleStop(const FHttpServerRequest& Request, const FHttpResultCallback& OnComplete);
	bool HandleSingle(const FHttpServerRequest& Request, const FHttpResultCallback& OnComplete);

	/** Build a JSON response and send it. */
	void SendJsonResponse(const FHttpResultCallback& OnComplete, const FString& JsonBody, int32 StatusCode = 200);

	UViewportPerceptionSubsystem* Subsystem = nullptr;

	TArray<FHttpRouteHandle> RouteHandles;
	static constexpr int32 PERCEPTION_PORT = 30011;
	bool bRunning = false;
};
