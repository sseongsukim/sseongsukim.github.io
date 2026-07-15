"""Halve videos by keeping frames 0, 2, 4, ... at the original FPS."""

from fractions import Fraction
from pathlib import Path

import av


VIDEO_DIRECTORY = Path("videos")
EXCLUDED_NAMES = {"visuo-tactile-video.mp4"}
FRAME_STEP = 2


def downsample_in_place(path: Path) -> tuple[int, int, float]:
    temporary_path = path.with_name(f".{path.stem}.downsampling.mp4")
    temporary_path.unlink(missing_ok=True)

    input_container = av.open(str(path))
    input_stream = input_container.streams.video[0]
    input_fps = input_stream.average_rate
    if input_fps is None or input_fps <= 0:
        input_container.close()
        raise RuntimeError(f"{path} has invalid FPS metadata")

    output_container = av.open(
        str(temporary_path), mode="w", options={"movflags": "+faststart"}
    )
    output_stream = output_container.add_stream(
        "libx264", rate=Fraction(input_fps)
    )
    output_stream.width = input_stream.codec_context.width
    output_stream.height = input_stream.codec_context.height
    output_stream.pix_fmt = "yuv420p"
    output_stream.options = {"crf": "23", "preset": "medium"}

    input_frames = 0
    output_frames = 0

    try:
        for frame in input_container.decode(input_stream):
            if input_frames % FRAME_STEP == 0:
                frame.pts = output_frames
                frame.time_base = Fraction(input_fps.denominator, input_fps.numerator)
                for packet in output_stream.encode(frame):
                    output_container.mux(packet)
                output_frames += 1

            input_frames += 1

        for packet in output_stream.encode():
            output_container.mux(packet)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise
    finally:
        input_container.close()
        output_container.close()

    temporary_path.replace(path)
    return input_frames, output_frames, float(input_fps)


def main() -> None:
    paths = [
        path
        for path in sorted(VIDEO_DIRECTORY.glob("*.mp4"))
        if path.name not in EXCLUDED_NAMES
    ]

    for path in paths:
        original_size = path.stat().st_size
        input_frames, output_frames, fps = downsample_in_place(path)
        output_size = path.stat().st_size
        reduction = (1 - output_size / original_size) * 100
        print(
            f"{path}: {input_frames} -> {output_frames} frames, "
            f"{fps:.6f} FPS, {original_size} -> {output_size} bytes "
            f"({reduction:.2f}% smaller)"
        )


if __name__ == "__main__":
    main()
