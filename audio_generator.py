"""Synthesize dual-speaker podcast audio from script using Edge TTS + ffmpeg."""

import asyncio
import os
import subprocess
import tempfile
from pathlib import Path

import edge_tts

VOICES = {
    "晓晓": "zh-CN-XiaoxiaoNeural",
    "云扬": "zh-CN-YunyangNeural",
}


async def _tts_single(text: str, voice: str, output_path: str) -> None:
    communicate = edge_tts.Communicate(
        text=text,
        voice=voice,
        rate="+5%",
        pitch="-2Hz",
    )
    await communicate.save(output_path)


async def _generate_turn_audio(turn: dict, turn_idx: int, tmpdir: str) -> str:
    speaker = turn.get("speaker", "晓晓")
    text = turn.get("text", "").strip()
    voice = VOICES.get(speaker, "zh-CN-XiaoxiaoNeural")

    output_file = os.path.join(tmpdir, f"turn_{turn_idx:03d}_{speaker}.mp3")
    await _tts_single(text, voice, output_file)
    return output_file


def _generate_silence(duration_sec: float, output_path: str) -> None:
    """Generate a silent MP3 segment using ffmpeg."""
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi",
        "-i", f"anullsrc=r=24000:cl=mono",
        "-t", str(duration_sec),
        "-b:a", "128k",
        output_path,
    ], capture_output=True, check=True)


def _concat_with_silence(
    track_files: list[str],
    script: list[dict],
    tmpdir: str,
    output_path: str,
) -> str:
    """
    Concatenate audio tracks with appropriate silence gaps between turns using ffmpeg.
    Returns the final audio duration in seconds.
    """
    # Build a concat file list with silence segments interleaved
    concat_file = os.path.join(tmpdir, "concat_list.txt")
    lines = []

    last_speaker = None
    for i, track_file in enumerate(track_files):
        if i == 0:
            # 0.4s intro silence
            silence_path = os.path.join(tmpdir, f"silence_{i:03d}_intro.mp3")
            _generate_silence(0.4, silence_path)
            lines.append(f"file '{silence_path}'")

        else:
            # Silence gap between turns
            pause = 0.3 if script[i].get("speaker") != last_speaker else 0.6
            silence_path = os.path.join(tmpdir, f"silence_{i:03d}.mp3")
            _generate_silence(pause, silence_path)
            lines.append(f"file '{silence_path}'")

        lines.append(f"file '{track_file}'")
        last_speaker = script[i].get("speaker")

    with open(concat_file, "w") as f:
        f.write("\n".join(lines))

    # Use concat demuxer (requires same codec/bitrate)
    subprocess.run([
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", concat_file,
        "-c", "copy",
        output_path,
    ], capture_output=True, check=True)

    # Get duration
    result = subprocess.run([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        output_path,
    ], capture_output=True, text=True, check=True)
    return float(result.stdout.strip())


def _apply_fade_out(input_path: str, output_path: str, fade_duration: float = 1.5) -> None:
    """Apply fade-out effect to the final audio."""
    # Get total duration first
    result = subprocess.run([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        input_path,
    ], capture_output=True, text=True, check=True)
    total_dur = float(result.stdout.strip())
    fade_start = total_dur - fade_duration

    subprocess.run([
        "ffmpeg", "-y",
        "-i", input_path,
        "-af", f"afade=t=out:st={fade_start}:d={fade_duration}",
        "-b:a", "128k",
        output_path,
    ], capture_output=True, check=True)


async def generate_audio(
    script: list[dict],
    output_path: str,
    bg_music_path: str | None = None,
) -> str:
    if not script:
        raise ValueError("Script is empty")

    tmpdir = tempfile.mkdtemp(prefix="podcast_")
    track_files = []

    try:
        # Step 1: Generate TTS for each turn in parallel
        tasks = [_generate_turn_audio(turn, i, tmpdir) for i, turn in enumerate(script)]
        track_files = await asyncio.gather(*tasks)

        # Step 2: Concatenate with silence gaps
        merged_path = os.path.join(tmpdir, "merged.mp3")
        total_dur = _concat_with_silence(track_files, script, tmpdir, merged_path)

        # Step 3: Apply fade out
        faded_path = os.path.join(tmpdir, "faded.mp3")
        _apply_fade_out(merged_path, faded_path)

        # Step 4: Export to final location
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        if bg_music_path and os.path.exists(bg_music_path):
            # Mix with background music
            subprocess.run([
                "ffmpeg", "-y",
                "-i", faded_path,
                "-i", bg_music_path,
                "-filter_complex",
                f"[1:a]volume=-18dB,aloop=loop=-1:size=2e9[bg];[0:a][bg]amix=inputs=2:duration=first:dropout_transition=0",
                "-b:a", "128k",
                output_path,
            ], capture_output=True, check=True)
        else:
            os.rename(faded_path, output_path)

        minutes = int(total_dur // 60)
        seconds = int(total_dur % 60)
        print(f"  ✓ 播客生成完成: {output_path}")
        print(f"  ✓ 时长: {minutes}分{seconds}秒")
        print(f"  ✓ 对话轮次: {len(script)}")

        return output_path

    finally:
        for f in track_files:
            try:
                os.remove(f)
            except OSError:
                pass
        try:
            for f in os.listdir(tmpdir):
                os.remove(os.path.join(tmpdir, f))
            os.rmdir(tmpdir)
        except OSError:
            pass


def generate_audio_sync(script: list[dict], output_path: str, bg_music_path: str | None = None) -> str:
    return asyncio.run(generate_audio(script, output_path, bg_music_path))


if __name__ == "__main__":
    test_script = [
        {"speaker": "晓晓", "text": "欢迎收听每日AI新闻播客，我是晓晓。"},
        {"speaker": "云扬", "text": "大家好我是云扬。今天AI圈又有大新闻，我们一起来看看。"},
    ]
    output = asyncio.run(generate_audio(test_script, "output/test_podcast.mp3"))
    print(f"测试完成: {output}")
