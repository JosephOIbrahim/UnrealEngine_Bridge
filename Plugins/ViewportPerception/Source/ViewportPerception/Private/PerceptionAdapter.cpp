// PerceptionAdapter.cpp

#include "PerceptionAdapter.h"
#include "ViewportPerceptionModule.h"
#include "IImageWrapper.h"
#include "IImageWrapperModule.h"
#include "Modules/ModuleManager.h"

TArray<FColor> FPerceptionAdapter::Resize(const TArray<FColor>& Source,
                                           FIntPoint SourceSize, FIntPoint TargetSize)
{
	if (SourceSize == TargetSize || Source.Num() == 0)
	{
		return Source;  // No resize needed
	}

	const int32 SrcW = SourceSize.X;
	const int32 SrcH = SourceSize.Y;
	const int32 DstW = TargetSize.X;
	const int32 DstH = TargetSize.Y;

	TArray<FColor> Result;
	Result.SetNumUninitialized(DstW * DstH);

	// Bilinear interpolation
	const float ScaleX = static_cast<float>(SrcW) / static_cast<float>(DstW);
	const float ScaleY = static_cast<float>(SrcH) / static_cast<float>(DstH);

	for (int32 Y = 0; Y < DstH; ++Y)
	{
		const float SrcY = (Y + 0.5f) * ScaleY - 0.5f;
		const int32 Y0 = FMath::Clamp(FMath::FloorToInt32(SrcY), 0, SrcH - 1);
		const int32 Y1 = FMath::Clamp(Y0 + 1, 0, SrcH - 1);
		const float FracY = SrcY - Y0;

		for (int32 X = 0; X < DstW; ++X)
		{
			const float SrcX = (X + 0.5f) * ScaleX - 0.5f;
			const int32 X0 = FMath::Clamp(FMath::FloorToInt32(SrcX), 0, SrcW - 1);
			const int32 X1 = FMath::Clamp(X0 + 1, 0, SrcW - 1);
			const float FracX = SrcX - X0;

			// Sample 4 neighbors
			const FColor& C00 = Source[Y0 * SrcW + X0];
			const FColor& C10 = Source[Y0 * SrcW + X1];
			const FColor& C01 = Source[Y1 * SrcW + X0];
			const FColor& C11 = Source[Y1 * SrcW + X1];

			// Bilinear blend
			const float OneMinusFX = 1.0f - FracX;
			const float OneMinusFY = 1.0f - FracY;

			const uint8 R = static_cast<uint8>(FMath::Clamp(
				C00.R * OneMinusFX * OneMinusFY + C10.R * FracX * OneMinusFY +
				C01.R * OneMinusFX * FracY + C11.R * FracX * FracY, 0.0f, 255.0f));
			const uint8 G = static_cast<uint8>(FMath::Clamp(
				C00.G * OneMinusFX * OneMinusFY + C10.G * FracX * OneMinusFY +
				C01.G * OneMinusFX * FracY + C11.G * FracX * FracY, 0.0f, 255.0f));
			const uint8 B = static_cast<uint8>(FMath::Clamp(
				C00.B * OneMinusFX * OneMinusFY + C10.B * FracX * OneMinusFY +
				C01.B * OneMinusFX * FracY + C11.B * FracX * FracY, 0.0f, 255.0f));
			const uint8 A = 255;

			Result[Y * DstW + X] = FColor(R, G, B, A);
		}
	}

	return Result;
}

TArray<uint8> FPerceptionAdapter::Encode(const TArray<FColor>& Pixels, FIntPoint Size,
                                          EPerceptionImageFormat Format, int32 Quality)
{
	TArray<uint8> Result;

	if (Pixels.Num() == 0 || Size.X <= 0 || Size.Y <= 0)
	{
		return Result;
	}

	IImageWrapperModule& ImageWrapperModule = FModuleManager::LoadModuleChecked<IImageWrapperModule>("ImageWrapper");

	const EImageFormat ImageFormat = (Format == EPerceptionImageFormat::PNG) ? EImageFormat::PNG : EImageFormat::JPEG;
	TSharedPtr<IImageWrapper> ImageWrapper = ImageWrapperModule.CreateImageWrapper(ImageFormat);

	if (!ImageWrapper.IsValid())
	{
		UE_LOG(LogViewportPerception, Warning, TEXT("Failed to create image wrapper"));
		return Result;
	}

	// Set raw pixel data
	const TArray<uint8>* RawData = reinterpret_cast<const TArray<uint8>*>(&Pixels);
	if (ImageWrapper->SetRaw(
		Pixels.GetData(),
		Pixels.Num() * sizeof(FColor),
		Size.X,
		Size.Y,
		ERGBFormat::BGRA,
		8))
	{
		// Compress
		const int32 CompressQuality = (Format == EPerceptionImageFormat::JPEG) ? FMath::Clamp(Quality, 1, 100) : 0;
		Result = ImageWrapper->GetCompressed(CompressQuality);
	}
	else
	{
		UE_LOG(LogViewportPerception, Warning, TEXT("Failed to set raw image data for encoding"));
	}

	return Result;
}
