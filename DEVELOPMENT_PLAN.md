# AutoClip v2 - 增强预览与交互计划

## 1. 目标
构建一个带有视频播放器、时间轴和字幕编辑区的交互式界面，允许用户在播放视频的同时，实时预览字幕样式的修改效果。

---

## 2. GUI 布局方案 (Mermaid)
我们将把界面重构成一个经典的三栏布局：

```mermaid
graph TD
    subgraph "主窗口 (MainWindow)"
        direction LR
        subgraph "左侧面板 (功能与样式)"
            direction TB
            A[剪辑功能区]
            B[字幕样式调整区]
        end
        subgraph "中心面板 (预览与时间轴)"
            direction TB
            C[视频预览区 (QVideoWidget)]
            D[播放控制条 (播放/暂停按钮, 时间轴 QSlider)]
        end
        subgraph "右侧面板 (字幕列表)"
            direction TB
            E[字幕文本列表 (QTableWidget)]
        end
    end
```

---
## 3. 核心功能实现方案

**A. 视频播放与时间轴同步**
1.  **引入 `QtMultimedia`**: 我们将在 `gui/main_window.py` 中导入 `QMediaPlayer` 和 `QVideoWidget`。
2.  **加载视频**: 导入视频后，创建一个 `QMediaPlayer` 实例，将其输出设置到 `QVideoWidget` 上，并加载视频媒体。
3.  **双向同步**:
    *   当视频播放时，定时更新 `QSlider` (时间轴) 的位置。
    *   当用户拖动 `QSlider` 时，调用 `player.setPosition()` 来跳转到视频的相应位置。

**B. 字幕列表与编辑**
1.  **使用 `QTableWidget`**: 生成字幕后，我们将每个字幕段落（时间、文本）填充到一个 `QTableWidget` 中。
2.  **高亮当前字幕**: 当视频播放时，根据当前时间戳，自动高亮显示 `QTableWidget` 中对应的字幕行。
3.  **可编辑字幕**: 用户可以直接在表格中**双击修改字幕文本**。

**C. 实时字幕样式预览 (关键功能)**
这是一个挑战，直接在播放的视频上层层叠加动态文本很难做到流畅。我建议采用一个非常高效且可行的方案：
1.  **创建 `SubtitlePreviewLabel`**: 在 `QVideoWidget` 上层，我们放置一个透明背景的 `QLabel`。这个 `QLabel` 的大小与视频帧完全一致。
2.  **样式更新触发**: 当用户在左侧面板调整任何样式（如字号、颜色）时，触发一个 `update_preview` 函数。
3.  **`update_preview` 逻辑**:
    *   获取当前播放器的时间戳。
    *   在字幕列表中找到此刻应该显示的字幕文本。
    *   如果找到了文本，就使用用户选择的新样式，通过 `QLabel` 的富文本功能 (HTML/CSS) 或者 `QPainter`，将这段带样式的字幕绘制出来，并设置到 `SubtitlePreviewLabel` 上。
    *   如果此刻没有字幕，则清空 `SubtitlePreviewLabel`。
4.  **时间轴拖动触发**: 拖动时间轴滑块时，同样触发 `update_preview`。

**这个方案的优势是**：我们避免了为每一帧视频都重新进行耗时的 `moviepy` 视频合成，而是利用轻量级的 `QLabel` 实现了“所见即所得”的实时样式预览。最终的“烧录”步骤只在用户点击“导出”时执行一次。

---

## 4. 实施步骤
1.  **修复 `TextClip` Bug**: 首先修正 `core/subtitle_processing.py` 中的参数错误。
2.  **重构GUI**: 在 `gui/main_window.py` 中搭建新的三栏式布局。
3.  **实现播放器与时间轴**。
4.  **实现字幕列表**。
5.  **实现 `SubtitlePreviewLabel` 实时预览机制**。
6.  **整合与测试**。