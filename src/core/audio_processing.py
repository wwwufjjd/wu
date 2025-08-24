import torch
import os
import torchaudio

# 【最终正确版 - V2 恢复】
# 在干净的环境下，这是最标准、最高效的实现方式。

try:
    # force_reload=False 确保在干净的环境下，优先使用本地缓存，避免网络问题。
    model, utils = torch.hub.load(repo_or_dir='snakers4/silero-vad',
                                  model='silero_vad',
                                  force_reload=False,
                                  onnx=True)
    
    (get_speech_timestamps, _, read_audio, _, _) = utils
    print("Silero VAD 模型已从本地 pip 包成功加载。")

except Exception as e:
    print(f"加载 Silero VAD 模型失败。错误: {e}")
    model, get_speech_timestamps, read_audio = None, None, None

def get_voice_segments(audio_path, 
                       threshold=0.5, 
                       min_speech_duration_ms=250, 
                       min_silence_duration_ms=100):
    """
    使用高阶函数 get_speech_timestamps 分析音频，返回所有人声片段。
    """
    if not all([model, read_audio, get_speech_timestamps]):
        print("Silero VAD 模型或工具函数不可用，无法处理音频。")
        return []

    try:
        wav, sample_rate = torchaudio.load(audio_path)
        if wav.shape[0] > 1:
            wav = torch.mean(wav, dim=0, keepdim=True)
        if sample_rate != 16000:
            resampler = torchaudio.transforms.Resample(orig_freq=sample_rate, new_freq=16000)
            wav = resampler(wav)
        
        speech_timestamps = get_speech_timestamps(wav, model, 
                                                  sampling_rate=16000,
                                                  threshold=threshold,
                                                  min_speech_duration_ms=min_speech_duration_ms,
                                                  min_silence_duration_ms=min_silence_duration_ms,
                                                  return_seconds=True)
        
        print(f"在 '{os.path.basename(audio_path)}' 中检测到 {len(speech_timestamps)} 个人声片段。")
        return speech_timestamps

    except Exception as e:
        print(f"处理音频时出错: {e}")
        return []

if __name__ == '__main__':
    test_file = 'test.wav'
    if os.path.exists(test_file):
        segments = get_voice_segments(test_file)
        if segments:
            print("检测到的人声片段 (秒):")
            for i, seg in enumerate(segments):
                print(f"  片段 {i+1}: {seg['start']:.2f} - {seg['end']:.2f}")
        else:
            print(f"在 '{test_file}' 中未检测到人声片段。")
    else:
        print(f"请提供一个 '{test_file}' 文件来运行测试。")