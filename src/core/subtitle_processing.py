import whisper
import os
import subprocess
from typing import List, Dict, Any
import imageio_ffmpeg

def _write_srt_file(subtitles: List[Dict[str, Any]], srt_path: str):
    """将字幕数据写入临时的 SRT 文件"""
    def _format_time(seconds):
        millis = int((seconds - int(seconds)) * 1000)
        seconds = int(seconds)
        minutes = seconds // 60
        hours = minutes // 60
        seconds %= 60
        minutes %= 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"

    with open(srt_path, 'w', encoding='utf-8') as f:
        for i, segment in enumerate(subtitles):
            start_time = _format_time(segment['start'])
            end_time = _format_time(segment['end'])
            text = segment['text'].strip()
            f.write(f"{i + 1}\n")
            f.write(f"{start_time} --> {end_time}\n")
            f.write(f"{text}\n\n")

def generate_subtitles(audio_path: str, model_name: str = "base") -> List[Dict[str, Any]]:
    """
    使用 Whisper 模型生成字幕
    """
    if not os.path.exists(audio_path):
        print(f"错误: 音频文件未找到 at {audio_path}")
        return None

    try:
        model = whisper.load_model(model_name)
        result = model.transcribe(audio_path, fp16=False) # fp16=False can improve compatibility
        return result["segments"]
    except Exception as e:
        print(f"生成字幕时出错: {e}")
        return None

def burn_subtitles_to_video(video_path: str, subtitles: List[Dict[str, Any]], output_path: str, style_options: Dict[str, Any]):
    """
    使用 ffmpeg 将字幕烧录到视频中。
    """
    srt_path = "temp_subtitle.srt"
    try:
        # 1. 创建临时的 SRT 文件
        _write_srt_file(subtitles, srt_path)

        # 2. 构建 ffmpeg 的 force_style 字符串
        # 注意：ffmpeg 的颜色格式是 &HBBGGRR
        font_color = style_options.get('color', '#FFFFFF')[1:] # 去掉 '#'
        font_color_ffmpeg = f"&H{font_color[4:6]}{font_color[2:4]}{font_color[0:2]}"
        
        style_params = [
            f"FontName={style_options.get('font', 'Arial')}",
            f"FontSize={style_options.get('fontsize', 24)}",
            f"PrimaryColour={font_color_ffmpeg}",
            # Add more style mappings here if needed (e.g., border, shadow)
        ]
        
        # ffmpeg -vf subtitles filter needs path with escaped backslashes for Windows
        escaped_srt_path = srt_path.replace('\\', '\\\\').replace(':', '\\:')
        
        video_filter = f"subtitles={escaped_srt_path}:force_style='{','.join(style_params)}'"

        # 3. 构建并执行 ffmpeg 命令
        ffmpeg_executable = imageio_ffmpeg.get_ffmpeg_exe()
        command = [
            ffmpeg_executable,
            '-y',  # Overwrite output file if it exists
            '-i', video_path,
            '-vf', video_filter,
            '-c:a', 'copy', # Copy audio stream without re-encoding
            output_path
        ]
        
        print(f"正在执行 ffmpeg 命令: {' '.join(command)}")
        
        # 使用 subprocess.PIPE 来捕获输出，可以更好地进行调试
        process = subprocess.run(command, check=True, capture_output=True, text=True)
        print("ffmpeg process completed.")
        print("STDOUT:", process.stdout)
        print("STDERR:", process.stderr)

        print(f"字幕已成功烧录到视频并保存至: {output_path}")

    except subprocess.CalledProcessError as e:
        print("ffmpeg 执行失败！")
        print(f"返回码: {e.returncode}")
        print(f"输出: {e.stdout}")
        print(f"错误: {e.stderr}")
        raise e # Re-raise the exception to be caught by the GUI
    except Exception as e:
        print(f"烧录字幕时发生未知错误: {e}")
        raise e
    finally:
        # 4. 清理临时的 SRT 文件
        if os.path.exists(srt_path):
            os.remove(srt_path)