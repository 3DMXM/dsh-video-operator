# 验证记录 · 2026-11-12

- 宿主版本：DSH 0.2.2-rc.2，Electron 44.7.0，当前桌面profile。
- 插件安装：`@local/dsh-video-operator`，`application: applied`，无warnings。
- 安装后实际调用：video_operator_guide、video_studio doctor、video_studio voice、video_platform_read account、video_platform_preview。
- B站独立账号状态：not_logged_in，错误如实返回；未尝试发布或回复。
- 抖音：官方OAuth旧版接口适配，mock验证上传后创建及错误传播；无凭证，在线发布/评论/统计未联调。
- v0.1.1 离线回归：20项通过，包括默认1080P、2K横竖屏、请求优先于项目JSON、非法分辨率和非60fps拒绝。
- v0.1.1 FFmpeg：实际合成1920×1080、2560×1440、1080×1920及1440×2560四种输出；`ffprobe` 的 `r_frame_rate` 与 `avg_frame_rate` 均为 `60/1`，封面尺寸与视频一致。测试使用本地产生的1秒测试音频。
- 历史v0.1.0曾验证1280×720和720×1280、25fps；新版本默认已升级，旧成片不会自动重编码。
- GPT-SoVITS：指定技能synthesize.py真实调用，本地现有七七v4配套模型；短句WAV 2.92秒；两分镜横屏MP4 8.301333秒，voice_engine=GPT-SoVITS。
- 试听/画面：模型不提供图像或音频感知，未试听、未检查画面视觉效果；仅校验音频PCM格式/时长、视频流与输出文件。
- 临时推理服务：本次管理的job在制片后停止；没有修改项目默认API配置。
- 分发检查：npm pack dry-run只包括源码、文档、示例、图标和测试，不包括环境、权重、凭证或产物。

## 使用流程复核

原计划分派独立审查，但当前会话子代理运行均在执行前失败；因此由主代理自行检查发现入口、主要流程和反馈。首次通过guide发现完整schema；制片返回可打开的绝对路径；未登录明确提示；发布前预览包含正文、平台、文件哈希及单次计划ID；结果不明会阻止重复投稿。使用DSH原生配置和工具卡片，无自定义客户端界面。

插件中文/英文metadata、exports及SVG XML结构已检查。当前没有可用的已连接浏览器控制，插件管理器中的实际图标、文案显示和两主题视觉效果仍未验收。没有用mock页面替代真实界面。
