import os
import cv2
import imageio_ffmpeg
from moviepy.video.io.VideoFileClip import VideoFileClip
from ultralytics import YOLO
from typing import List, Dict, Tuple, Union
from moviepy import concatenate_videoclips
# --- Moviepy 配置 ---
# 通过代码直接修改 moviepy 的配置，确保在任何 moviepy 函数调用前执行
# 这在打包或虚拟环境中尤其有用，可以确保 moviepy 找到正确的 ffmpeg 执行文件
# This is the NEW way for moviepy v2.0+
import moviepy.config as mpy_config
import imageio_ffmpeg

try:
    mpy_config.FFMPEG_BINARY = imageio_ffmpeg.get_ffmpeg_exe()
    print("Moviepy FFMPEG_BINARY set successfully.")
except Exception as e:
    print(f"Could not set FFMPEG_BINARY for moviepy: {e}")


def extract_audio(video_path: str, output_audio_path: str = "temp_audio.wav") -> Union[str, None]:
    """
    从视频中提取音频并保存为 wav 文件。
    (使用 with 语句确保资源被正确释放)

    :param video_path: 视频文件路径
    :param output_audio_path: 输出的音频文件路径
    :return: 成功则返回音频文件路径，否则返回 None
    """
    try:
        # 使用 with 语句可以自动关闭 video_clip，无需手动调用 .close()
        with VideoFileClip(video_path) as video_clip:
            if video_clip.audio is None:
                print(f"视频 '{video_path}' 中没有音频轨道。")
                return None
            
            # 提取音频并写入文件
            audio_clip = video_clip.audio
            audio_clip.write_audiofile(output_audio_path, codec='pcm_s16le', logger='bar')
        
        print(f"音频成功提取并保存至: {output_audio_path}")
        return output_audio_path
        
    except Exception as e:
        print(f"提取音频时出错: {e}")
        # 如果文件已创建但过程失败，则清理
        if os.path.exists(output_audio_path):
            os.remove(output_audio_path)
        return None


def cut_video_by_segments(video_path: str, segments: List[Union[Dict[str, float], Tuple[float, float]]], output_path: str, keep_segments: bool = True) -> None:
    """
    根据时间段列表对视频进行剪辑。
    (使用 with 语句确保资源被正确释放)

    :param video_path: 原始视频路径
    :param segments: (开始, 结束) 时间段列表, 可以是 {'start': s, 'end': e} 或 (s, e)
    :param output_path: 输出视频路径
    :param keep_segments: True 则保留列表中的片段，False 则移除列表中的片段
    """
    try:
        with VideoFileClip(video_path) as video_clip:
            duration = video_clip.duration

            # 检查并转换 segments 格式，使其统一为元组列表
            if segments and isinstance(segments[0], dict):
                proc_segments = [(s['start'], s['end']) for s in segments]
            else:
                proc_segments = segments

            # 对时间戳进行排序和边界检查
            proc_segments = sorted([(max(0, s), min(duration, e)) for s, e in proc_segments])

            target_segments = []
            if keep_segments:
                target_segments = proc_segments
            else:
                # 反转时间段，生成需要保留的片段
                last_end = 0
                for start, end in proc_segments:
                    if start > last_end:
                        target_segments.append((last_end, start))
                    last_end = max(last_end, end)
                if last_end < duration:
                    target_segments.append((last_end, duration))
            
            if not target_segments:
                print("没有可用于拼接的视频片段。")
                return

            print(f"将要拼接 {len(target_segments)} 个片段...")
            # 创建子剪辑列表
            final_clips = [video_clip.subclipped(start, end) for start, end in target_segments]
            
            # 拼接所有剪辑，并使用 with 语句确保拼接后的视频资源也被正确管理
            with concatenate_videoclips(final_clips) as final_video:
                # 写入最终文件，logger='bar' 会显示进度条
                final_video.write_videofile(
                    output_path, 
                    codec="libx264", 
                    audio_codec="aac",
                    threads=4, # 可以指定多线程以加快速度
                    preset='medium', # 速度与质量的权衡: ultrafast, superfast, veryfast, faster, fast, medium, slow, slower, veryslow
                    logger='bar'
                )
        
        print(f"视频已成功剪辑并保存至: {output_path}")

    except Exception as e:
        print(f"剪辑视频时出错: {e}")


# --- YOLOv8 模型加载与人物检测 ---
# 这部分代码与 moviepy 版本无关，保持原样即可

try:
    model = YOLO('yolov8n.pt')  # 使用 nano 版本，速度快
    print("YOLOv8 模型加载成功。")
except Exception as e:
    print(f"加载 YOLOv8 模型失败: {e}")
    model = None

def get_person_segments(video_path: str, confidence_threshold: float = 0.5, process_every_n_frames: int = 1) -> List[Dict[str, float]]:
    """
    分析视频，返回包含人物的片段列表。

    :param video_path: 视频文件路径
    :param confidence_threshold: 人物检测的置信度阈值
    :param process_every_n_frames: 每隔 n 帧处理一次，以提高性能。1 表示处理每一帧。
    :return: 包含人物的 {'start': start_time, 'end': end_time} 字典列表
    """
    if not model:
        print("YOLO 模型不可用，无法进行人物检测。")
        return []

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"无法打开视频文件: {video_path}")
        return []

    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps == 0:
        print(f"无法获取视频 '{video_path}' 的帧率。")
        cap.release()
        return []

    segments = []
    in_person_segment = False
    start_time = 0
    frame_index = 0

    while cap.isOpened():
        # 如果设置了 process_every_n_frames > 1，则跳帧
        if process_every_n_frames > 1 and frame_index > 0:
            frame_index += process_every_n_frames - 1
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)

        ret, frame = cap.read()
        if not ret:
            break

        current_time = frame_index / fps
        
        # 使用 YOLO 模型进行预测
        # verbose=False 可以让输出更干净
        results = model(frame, classes=[0], conf=confidence_threshold, verbose=False) # classes=[0] 表示只检测 'person'
        
        person_detected = len(results[0].boxes) > 0

        if person_detected and not in_person_segment:
            in_person_segment = True
            start_time = current_time
        elif not person_detected and in_person_segment:
            in_person_segment = False
            segments.append({'start': start_time, 'end': current_time})

        frame_index += 1

    # 循环结束后，如果仍在人物片段中，则添加最后一个片段
    if in_person_segment:
        end_time = cap.get(cv2.CAP_PROP_FRAME_COUNT) / fps
        segments.append({'start': start_time, 'end': end_time})

    cap.release()
    print(f"在 '{os.path.basename(video_path)}' 中检测到 {len(segments)} 个人物片段。")
    return segments


# --- 示例用法 ---
if __name__ == '__main__':
    # 创建一个虚拟的视频文件用于测试，如果你有自己的视频，请替换路径
    # from moviepy.editor import ColorClip
    # test_video_path = "test_video.mp4"
    # if not os.path.exists(test_video_path):
    #     ColorClip(size=(640, 480), color=(0, 0, 0), duration=10).write_videofile(test_video_path, fps=30)
    
    # 请将下面的路径替换为你的视频文件路径
    video_file_path = "path/to/your/video.mp4" 
    
    if not os.path.exists(video_file_path):
        print(f"错误：视频文件 '{video_file_path}' 不存在。请修改 'video_file_path' 变量。")
    else:
        # 1. 提取音频
        # extract_audio(video_file_path, "output_audio.wav")

        # 2. 获取包含人物的视频片段
        # process_every_n_frames=30 表示大约每秒检测一次，可以极大提高速度
        person_segments = get_person_segments(video_file_path, process_every_n_frames=30)

        # 3. 根据检测到的片段进行剪辑
        if person_segments:
            # 示例 1: 只保留有人物的片段
            output_with_person = "output_only_person.mp4"
            print(f"\n开始创建只包含人物的视频...")
            cut_video_by_segments(video_file_path, person_segments, output_with_person, keep_segments=True)

            # 示例 2: 移除所有人物片段
            output_without_person = "output_no_person.mp4"
            print(f"\n开始创建移除了人物的视频...")
            cut_video_by_segments(video_file_path, person_segments, output_without_person, keep_segments=False)
        else:
            print("未检测到任何人物片段，不进行剪辑。")