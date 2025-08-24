import os
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QFileDialog, QMessageBox, QGroupBox, QGridLayout, QLabel,
                             QFontComboBox, QSpinBox, QComboBox, QCheckBox, QColorDialog,
                             QSlider, QStyle, QTableWidget, QTableWidgetItem, QAbstractItemView,
                             QStackedLayout)
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtMultimediaWidgets import QVideoWidget
from PyQt5.QtGui import QColor, QFont, QPalette
from PyQt5.QtCore import Qt, QUrl

from core.audio_processing import get_voice_segments
from core.video_processing import extract_audio, cut_video_by_segments, get_person_segments
from core.subtitle_processing import generate_subtitles, burn_subtitles_to_video

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AutoClip v2 - 自动化剪辑工具")
        self.setGeometry(100, 100, 1600, 900)

        self.video_paths = []
        self.subtitles = None
        self.media_player = None
        self.current_subtitle_index = -1

        self._init_ui()
        self._connect_signals()

    def _init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # --- Left Panel ---
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_panel.setMinimumWidth(300)
        left_panel.setMaximumWidth(400)
        
        self.btn_import = QPushButton("导入视频")
        left_layout.addWidget(self.btn_import)

        clip_group = QGroupBox("剪辑功能")
        clip_layout = QVBoxLayout(clip_group)
        self.btn_keep_voice = QPushButton("只保留有人声的片段")
        self.btn_smart_remove = QPushButton("智能去除 (人声+人物)")
        clip_layout.addWidget(self.btn_keep_voice)
        clip_layout.addWidget(self.btn_smart_remove)
        left_layout.addWidget(clip_group)

        self.subtitle_style_group = QGroupBox("字幕功能与样式")
        self._create_subtitle_style_controls(self.subtitle_style_group)
        left_layout.addWidget(self.subtitle_style_group)
        
        left_layout.addStretch()
        main_layout.addWidget(left_panel)

        # --- Center Panel ---
        center_panel = QWidget()
        center_layout = QVBoxLayout(center_panel)
        center_panel.setMinimumWidth(600) # Set a minimum width for the center panel
        
        self.preview_stack = QStackedLayout()
        self.video_widget = QVideoWidget()
        self.subtitle_preview_label = QLabel()
        self.subtitle_preview_label.setAlignment(Qt.AlignCenter)
        self.subtitle_preview_label.setAttribute(Qt.WA_TranslucentBackground)
        self.preview_stack.addWidget(self.video_widget)
        self.preview_stack.addWidget(self.subtitle_preview_label)
        center_layout.addLayout(self.preview_stack)

        self.timeline_slider = QSlider(Qt.Horizontal)
        self.timeline_slider.setRange(0, 0)
        center_layout.addWidget(self.timeline_slider)
        
        self._create_player_controls(center_layout)
        main_layout.addWidget(center_panel)
        
        # --- Right Panel ---
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_panel.setMinimumWidth(350)
        right_panel.setMaximumWidth(500)
        
        self.subtitle_table = QTableWidget()
        self.subtitle_table.setColumnCount(3)
        self.subtitle_table.setHorizontalHeaderLabels(["开始", "结束", "字幕文本"])
        self.subtitle_table.setEditTriggers(QAbstractItemView.DoubleClicked)
        right_layout.addWidget(self.subtitle_table)

        main_layout.addWidget(right_panel)

    def _create_subtitle_style_controls(self, group):
        layout = QGridLayout(group)
        
        layout.addWidget(QLabel("识别模型:"), 0, 0)
        self.model_combo = QComboBox()
        self.model_combo.addItems(["base", "small", "medium", "large"])
        layout.addWidget(self.model_combo, 0, 1)

        self.btn_auto_subtitle = QPushButton("1. 生成字幕")
        layout.addWidget(self.btn_auto_subtitle, 1, 0, 1, 2)

        layout.addWidget(QLabel("字体:"), 2, 0)
        self.font_combo = QFontComboBox()
        layout.addWidget(self.font_combo, 2, 1)

        layout.addWidget(QLabel("字号:"), 3, 0)
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 128)
        self.font_size_spin.setValue(48)
        layout.addWidget(self.font_size_spin, 3, 1)
        
        layout.addWidget(QLabel("颜色:"), 4, 0)
        self.font_color_btn = QPushButton("选择颜色")
        self.font_color = QColor("white")
        layout.addWidget(self.font_color_btn, 4, 1)

        layout.addWidget(QLabel("位置:"), 5, 0)
        self.pos_combo = QComboBox()
        self.pos_combo.addItems(["底部", "顶部", "中部"])
        layout.addWidget(self.pos_combo, 5, 1)

        self.bg_checkbox = QCheckBox("启用背景框")
        layout.addWidget(self.bg_checkbox, 6, 0)
        self.bg_color_btn = QPushButton("背景颜色")
        self.bg_color_btn.setEnabled(False)
        self.bg_color = QColor(0,0,0,128)
        layout.addWidget(self.bg_color_btn, 6, 1)

        self.stroke_checkbox = QCheckBox("启用描边")
        layout.addWidget(self.stroke_checkbox, 7, 0)
        self.stroke_color_btn = QPushButton("描边颜色")
        self.stroke_color_btn.setEnabled(False)
        self.stroke_color = QColor("black")
        layout.addWidget(self.stroke_color_btn, 7, 1)
        
        self.btn_burn_subtitles = QPushButton("2. 将字幕烧录到视频")
        self.btn_burn_subtitles.setEnabled(False)
        layout.addWidget(self.btn_burn_subtitles, 8, 0, 1, 2)

    def _create_player_controls(self, parent_layout):
        controls_widget = QWidget()
        controls_layout = QHBoxLayout(controls_widget)
        controls_layout.setContentsMargins(0, 0, 0, 0)

        self.play_btn = QPushButton()
        self.play_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.play_btn.setEnabled(False)
        controls_layout.addWidget(self.play_btn)

        self.time_label = QLabel("00:00 / 00:00")
        controls_layout.addWidget(self.time_label)
        
        parent_layout.addWidget(controls_widget)

    def _connect_signals(self):
        self.btn_import.clicked.connect(self.import_video)
        self.play_btn.clicked.connect(self.toggle_play)
        self.timeline_slider.sliderMoved.connect(self.set_position)
        
        self.btn_keep_voice.clicked.connect(self.auto_keep_voice)
        self.btn_smart_remove.clicked.connect(self.smart_remove)

        self.btn_auto_subtitle.clicked.connect(self.auto_generate_subtitles)
        self.btn_burn_subtitles.clicked.connect(self.burn_subtitles)

        style_controls = [self.font_combo, self.font_size_spin, self.pos_combo, self.bg_checkbox, self.stroke_checkbox]
        for control in style_controls:
            if isinstance(control, QComboBox) or isinstance(control, QFontComboBox):
                control.currentIndexChanged.connect(self.update_subtitle_preview)
            elif isinstance(control, QSpinBox):
                control.valueChanged.connect(self.update_subtitle_preview)
            elif isinstance(control, QCheckBox):
                control.toggled.connect(self.update_subtitle_preview)
        
        self.font_color_btn.clicked.connect(lambda: self.select_color('font'))
        self.bg_checkbox.toggled.connect(self.bg_color_btn.setEnabled)
        self.bg_color_btn.clicked.connect(lambda: self.select_color('bg'))
        self.stroke_checkbox.toggled.connect(self.stroke_color_btn.setEnabled)
        self.stroke_color_btn.clicked.connect(lambda: self.select_color('stroke'))

    def import_video(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "选择一个或多个视频文件", "", "视频文件 (*.mp4 *.avi *.mov)")
        if paths:
            self.video_paths = paths
            
            preview_path = self.video_paths[0]
            if self.media_player is None:
                self.media_player = QMediaPlayer(None, QMediaPlayer.VideoSurface)
                self.media_player.setVideoOutput(self.video_widget)
                self.media_player.positionChanged.connect(self.position_changed)
                self.media_player.durationChanged.connect(self.duration_changed)
                self.media_player.stateChanged.connect(self.media_state_changed)

            self.media_player.setMedia(QMediaContent(QUrl.fromLocalFile(preview_path)))
            self.play_btn.setEnabled(True)
            
            self.subtitles = None
            self.subtitle_table.setRowCount(0)
            self.btn_burn_subtitles.setEnabled(False)
            
            if len(self.video_paths) == 1:
                QMessageBox.information(self, "成功", f"已导入视频: {os.path.basename(preview_path)}")
            else:
                QMessageBox.information(self, "成功", f"已导入 {len(self.video_paths)} 个视频。\n预览窗口将显示第一个视频。")

    def toggle_play(self):
        if self.media_player.state() == QMediaPlayer.PlayingState:
            self.media_player.pause()
        else:
            self.media_player.play()

    def media_state_changed(self, state):
        if state == QMediaPlayer.PlayingState:
            self.play_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))
        else:
            self.play_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))

    def position_changed(self, position):
        self.timeline_slider.setValue(position)
        self.update_time_label(position, self.media_player.duration())
        self.update_subtitle_preview()

    def duration_changed(self, duration):
        self.timeline_slider.setRange(0, duration)
        self.update_time_label(self.media_player.position(), duration)

    def set_position(self, position):
        self.media_player.setPosition(position)

    def update_time_label(self, position, duration):
        if duration == 0: return
        pos_seconds = position / 1000
        dur_seconds = duration / 1000
        self.time_label.setText(f"{int(pos_seconds//60):02d}:{int(pos_seconds%60):02d} / {int(dur_seconds//60):02d}:{int(dur_seconds%60):02d}")
    
    def select_color(self, target):
        initial_color = {'font': self.font_color, 'bg': self.bg_color, 'stroke': self.stroke_color}.get(target, QColor("white"))
        color = QColorDialog.getColor(initial_color, self, "选择颜色")
        if color.isValid():
            button = {'font': self.font_color_btn, 'bg': self.bg_color_btn, 'stroke': self.stroke_color_btn}[target]
            if target == 'font': self.font_color = color
            elif target == 'bg': self.bg_color = color
            else: self.stroke_color = color
            button.setStyleSheet(f"background-color: {color.name()};")
            self.update_subtitle_preview()

    def update_subtitle_preview(self):
        if not self.subtitles or not self.media_player:
            return

        current_time = self.media_player.position() / 1000.0
        
        found_segment = None
        found_index = -1
        for i, seg in enumerate(self.subtitles):
            if seg['start'] <= current_time < seg['end']:
                found_segment = seg
                found_index = i
                break
        
        if self.current_subtitle_index != found_index:
            if self.current_subtitle_index != -1:
                self.subtitle_table.item(self.current_subtitle_index, 2).setBackground(QColor('white'))
            if found_index != -1:
                self.subtitle_table.item(found_index, 2).setBackground(QColor('lightblue'))
                self.subtitle_table.scrollToItem(self.subtitle_table.item(found_index, 0))
            self.current_subtitle_index = found_index

        if found_segment:
            text = self.subtitle_table.item(found_index, 2).text()
            font = self.font_combo.currentFont()
            font.setPointSize(self.font_size_spin.value())
            
            style = f"font-family:'{font.family()}'; font-size:{font.pointSize()}pt; color:{self.font_color.name()};"
            if self.bg_checkbox.isChecked():
                style += f" background-color:rgba({self.bg_color.red()},{self.bg_color.green()},{self.bg_color.blue()},{self.bg_color.alpha()});"
            
            pos_map = {"顶部": "top", "中部": "center", "底部": "bottom"}
            v_align = pos_map.get(self.pos_combo.currentText(), "bottom")
            
            self.subtitle_preview_label.setText(f"<div style='{style}'>{text}</div>")
            self.subtitle_preview_label.setAlignment({"top": Qt.AlignTop | Qt.AlignHCenter, "center": Qt.AlignCenter, "bottom": Qt.AlignBottom | Qt.AlignHCenter}[v_align])
            self.subtitle_preview_label.show()
        else:
            self.subtitle_preview_label.clear()
            self.subtitle_preview_label.hide()

    def auto_keep_voice(self):
        self._batch_process("keep_voice")

    def _process_voice_cut(self, keep_segments, input_path, output_path, silent=False):
        if not input_path: return False
        
        if not silent:
            QMessageBox.information(self, "提示", "正在处理人声，请稍候...")
        temp_audio_path = f"temp_audio_{os.path.basename(input_path)}.wav"
        audio_file = extract_audio(input_path, temp_audio_path)
        if not audio_file:
            if not silent: QMessageBox.critical(self, "错误", "提取音频失败！")
            return False

        voice_segments = get_voice_segments(audio_file, threshold=0.35, min_silence_duration_ms=500)
        if os.path.exists(audio_file): os.remove(audio_file)

        if not voice_segments:
            if not silent: QMessageBox.warning(self, "警告", "未检测到任何人声片段。")
            import shutil
            shutil.copy(input_path, output_path)
            return True

        cut_video_by_segments(input_path, voice_segments, output_path, keep_segments=keep_segments)
        if not silent: QMessageBox.information(self, "完成", f"人声处理完成！文件保存在: {output_path}")
        return True

    def _process_person_cut(self, input_path, output_path, silent=False):
        if not input_path: return False
        
        if not silent: QMessageBox.information(self, "提示", "正在进行人物检测，请稍候...")
        person_segments = get_person_segments(input_path)
        
        if not person_segments:
            if not silent: QMessageBox.warning(self, "警告", "未检测到任何人物片段。")
            import shutil
            shutil.copy(input_path, output_path)
            return True
            
        cut_video_by_segments(input_path, person_segments, output_path, keep_segments=False)
        if not silent: QMessageBox.information(self, "完成", f"人物处理完成！视频已保存至: {output_path}")
        return True

    def smart_remove(self):
        self._batch_process("smart_remove")

    def _batch_process(self, operation_name):
        if not self.video_paths:
            return QMessageBox.warning(self, "警告", "请先导入一个或多个视频文件！")

        # For single file, just run the old logic with prompts
        if len(self.video_paths) == 1:
            if operation_name == 'smart_remove':
                self.smart_remove_single()
            elif operation_name == 'keep_voice':
                self._process_voice_cut(True, self.video_paths[0], None, silent=False)
            return

        output_dir = QFileDialog.getExistingDirectory(self, "选择一个文件夹来保存所有处理后的视频")
        if not output_dir:
            return

        QMessageBox.information(self, "开始处理", f"将对 {len(self.video_paths)} 个视频进行批量处理，请稍候...")

        total_files = len(self.video_paths)
        for i, video_path in enumerate(self.video_paths):
            base_name = os.path.basename(video_path)
            name, ext = os.path.splitext(base_name)
            
            self.statusBar().showMessage(f"正在处理第 {i+1}/{total_files} 个文件: {base_name}")

            if operation_name == "smart_remove":
                output_path = os.path.join(output_dir, f"{name}_smart_removed{ext}")
                temp_path = os.path.join(output_dir, f"temp_{name}{ext}")
                
                voice_ok = self._process_voice_cut(False, video_path, temp_path, silent=True)
                if voice_ok:
                    self._process_person_cut(temp_path, output_path, silent=True)
                if os.path.exists(temp_path): os.remove(temp_path)

            elif operation_name == "keep_voice":
                output_path = os.path.join(output_dir, f"{name}_voice_kept{ext}")
                self._process_voice_cut(True, video_path, output_path, silent=True)
        
        self.statusBar().showMessage(f"批量处理完成！", 5000)
        QMessageBox.information(self, "全部完成", f"所有视频已处理完毕并保存至:\n{output_dir}")

    def smart_remove_single(self):
        if not self.video_paths: return QMessageBox.warning(self, "警告", "请先导入一个视频文件！")
        output_path, _ = QFileDialog.getSaveFileName(self, "保存(智能去除后)视频", "", "MP4 (*.mp4)")
        if not output_path: return
        
        temp_path = os.path.join(os.path.dirname(output_path), "temp_" + os.path.basename(output_path))
        voice_removed_ok = self._process_voice_cut(False, self.video_paths[0], temp_path, silent=False)
        
        if not voice_removed_ok:
            if os.path.exists(temp_path): os.remove(temp_path)
            return

        person_removed_ok = self._process_person_cut(temp_path, output_path, silent=False)
        if os.path.exists(temp_path): os.remove(temp_path)
        
        if person_removed_ok:
            QMessageBox.information(self, "全部完成", f"智能去除处理完成！\n最终视频已保存至: {output_path}")

    def auto_generate_subtitles(self):
        if not self.video_path: return QMessageBox.warning(self, "警告", "请先导入一个视频文件！")
        
        selected_model = self.model_combo.currentText()
        QMessageBox.information(self, "提示", f"正在使用 '{selected_model}' 模型生成字幕，请稍候...\n更大的模型需要更长时间，并可能需要下载。")
        
        temp_audio_path = "temp_audio.wav"
        audio_file = extract_audio(self.video_path, temp_audio_path)
        if not audio_file: return QMessageBox.critical(self, "错误", "提取音频失败！")
        
        self.subtitles = generate_subtitles(audio_file, model_name=selected_model)
        if os.path.exists(audio_file): os.remove(audio_file)

        if not self.subtitles:
            return QMessageBox.warning(self, "警告", "未能生成字幕。")
        
        self.populate_subtitle_table()
        self.btn_burn_subtitles.setEnabled(True)
        QMessageBox.information(self, "完成", "字幕已生成并显示在右侧列表中。")

    def populate_subtitle_table(self):
        self.subtitle_table.setRowCount(0)
        if not self.subtitles: return
        self.subtitle_table.setRowCount(len(self.subtitles))
        for i, seg in enumerate(self.subtitles):
            self.subtitle_table.setItem(i, 0, QTableWidgetItem(f"{seg['start']:.2f}"))
            self.subtitle_table.setItem(i, 1, QTableWidgetItem(f"{seg['end']:.2f}"))
            self.subtitle_table.setItem(i, 2, QTableWidgetItem(seg['text']))

    def burn_subtitles(self):
        if not self.video_path or not self.subtitles: return QMessageBox.warning(self, "警告", "请先导入视频并生成字幕！")
        output_path, _ = QFileDialog.getSaveFileName(self, "保存带字幕的视频", "", "MP4 (*.mp4)")
        if not output_path: return
        
        pos_map = {"底部": ('center', 'bottom'), "顶部": ('center', 'top'), "中部": ('center', 'center')}
        style_options = {
            'font': self.font_combo.currentFont().family(),
            'fontsize': self.font_size_spin.value(),
            'color': self.font_color.name(),
            'position': pos_map.get(self.pos_combo.currentText()),
            'bg_color': self.bg_color.name(QColor.HexArgb) if self.bg_checkbox.isChecked() else 'transparent',
            'stroke_color': self.stroke_color.name() if self.stroke_checkbox.isChecked() else None,
            'stroke_width': 1 if self.stroke_checkbox.isChecked() else 0,
        }
        
        QMessageBox.information(self, "提示", "正在烧录字幕，请稍候...")
        try:
            for i in range(self.subtitle_table.rowCount()):
                self.subtitles[i]['text'] = self.subtitle_table.item(i, 2).text()
            
            burn_subtitles_to_video(self.video_path, self.subtitles, output_path, style_options)
            QMessageBox.information(self, "完成", f"带字幕的视频已保存至: {output_path}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"烧录字幕时发生错误: {e}")