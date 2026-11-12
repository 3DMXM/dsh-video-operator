# 视频创作运营 · DSH video operator

本地制片、B站与抖音发布、作品和评论运营的 DSH 插件。参考 [dsh-bili-creator](https://github.com/men-qingzheng/dsh-bili-creator) 的“本地制作 + 平台适配”结构，独立实现，插件 ID 为 `video-operator`，可与参考插件区分。配音通过本地 `gpt-sovits` 技能调用 GPT-SoVITS，默认技能目录为 `~/.codex/skills/gpt-sovits`，可在配置中修改。技能脚本、推理环境和模型需自行准备，本仓库不分发模型或替代语音引擎。

[下载 v0.1.3](https://github.com/3DMXM/dsh-video-operator/releases/tag/v0.1.3) · [问题反馈](https://github.com/3DMXM/dsh-video-operator/issues) · [验证记录](VERIFICATION.md)

## 已实现

| 能力 | B站 | 抖音 |
| --- | --- | --- |
| 制片 | 默认1920×1080，可选2560×1440，60fps | 默认1080×1920，可选1440×2560，60fps |
| 配音 | GPT-SoVITS 单/多角色；可导入已有音频 | 同左 |
| 画面 | 本地图片/文字卡、分镜标题与正文 | 同左 |
| 产物 | MP4、PNG封面、SRT、制片清单 | 同左 |
| 发布 | bili-agent 上传，AI声明，分区/封面/定时 | 官方 OAuth `/video/upload/` + `/video/create/` |
| 运营 | 账号/作品/审核/评论/回复/稿件数据/分区 | 账号/作品/审核数据/评论/回复 |

插件提供会话工具与 DSH 原生配置，没有额外运营面板。选题、脚本、数据解读、回复草案由会话模型完成。不会自行启动定时运营或发送消息。

## 安装与环境

需要 DSH `>=0.2.2-rc.2`、Python 3.10+（推荐3.11）、FFmpeg，以及独立可用的 GPT-SoVITS 本地技能/推理服务。已在 macOS 桌面版验证；其他系统需配置可用的中文字体和可执行文件路径。

推荐先克隆并准备独立环境（以下命令用于 macOS/Linux）：

```bash
git clone https://github.com/3DMXM/dsh-video-operator.git
cd dsh-video-operator
uv venv --python 3.11 .venv
uv pip install --python .venv/bin/python -r requirements.txt
```

然后在 DSH 的“插件 → 添加插件”选择克隆的目录，或让会话通过 `plugin_manager` 安装该目录。插件会自动发现自身 `.venv` 下的 Python 和 bili；未找到时使用系统命令，也可以在插件配置中指定绝对路径。Windows 的虚拟环境命令位于 `.venv/Scripts/`。

也可以下载 Release 中的 `local-dsh-video-operator-0.1.3.tgz`，在插件管理器中安装；安装包不包含 Python 环境，需另行准备环境并配置 `pythonPath` 和 `biliExecutable`。安装结果如提示需要重启，请按提示重启 DSH。

系统需有 `ffmpeg`、`ffprobe`。在 DSH 插件配置中可设置 `pythonPath`、`stateDir`、`sovitsSkillDir`、`biliExecutable`、`douyinCredentials`、`personaPath`、`live2dRoot`、`browserExecutable`。默认状态目录是 `~/.local/share/dsh-video-operator`，存放发布计划、审计以及独立 B站登录，不把凭证放入源代码包。

插件按当前 DSH 0.2.2-rc.2 的实际工具API构建，从正在运行的安装树解析依赖，支持 Electron ASAR；无运行中的 DSH 环境时不能直接用普通 node 加载宿主模块。支持的最低版本通过 package engines 限定。

## 使用

新会话先调用 `video_operator_guide`。可以直接说：

> 按沐朵人设写一段关于XX的脚本，使用已配置的配音，分别制作B站横屏和抖音竖屏版本。先给我试听和成片。
>
> 预览这条视频的B站投稿，标题是XX，标签是XX。
>
> 发布刚才预览的那条B站投稿。
>
> 看看这条视频的播放和评论，拟三条回复给我看。

五个工具：

- `video_operator_guide`：流程、项目与平台请求字段。
- `video_studio`：`doctor` / `voice` / `render`。
- `video_platform_read`：只读查询。
- `video_platform_preview`：发布或回复预览。
- `video_platform_execute`：执行已经展示过的计划。

### 平台定义与沐朵人设

| 平台 | 制作和发布方向 | 内容定义 |
| --- | --- | --- |
| B站 | 只发横屏，显示宽度 > 高度 | 沐朵主持的Mod客栈宣传、完整教程、版本说明与报错答疑 |
| 抖音 | 只发竖屏，显示高度 > 宽度 | 同一人设的短宣传、单问题教程与答疑，开头直接说明问题与用途 |

制作时按平台生成对应画布。发布预览与执行前都使用 `ffprobe` 检查真实视频流，结合旋转元数据、像素宽高比判断显示方向；方向不符或方形视频返回 `ORIENTATION_MISMATCH`，不会上传。无效视频或缺少ffprobe也会明确失败。此规则同样适用于外部导入的视频和更新前保存的预览计划，不自动裁切或拉伸素材。

默认创作角色为 **沐朵 · Mod客栈虚拟艺人**：成年女性、白发、无口、冷淡可爱，慢热而有温度；无口表示表达克制，不代表没有感情。她有自己的偏好、幽默和成长，能分享日常、游戏和心情，也认真做好教程和答疑。用于脚本、标题简介、宣传、教程、答疑和评论草案；两平台核心人格一致、账号语境和互动记录独立。

在插件配置的 `personaPath` 指定本地人设Markdown文件，指南每次调用都会读取最新原文。当前工作区若存在相邻的 `glossmod/看板娘/mod-inn-muduo/readme.md`，会自动作为默认来源；其他安装使用随包整理的 [沐朵设定](prompts/muduo.md)。显式配置文件缺失、为空或超过64KiB会报错，不静默替换。创作前调用 `video_operator_guide` 同时获得人设与平台规则。

人设指导会话模型创作，不自动审核每句文案，也不改变GPT-SoVITS音色、模型或参考音频。配音使用用户已配置且拥有使用权的声音；本包不包含角色图像、声音模型或参考音频。

### 配音和制片

`examples/project.json` 是占位模板：将 `characters` 中的模型路径、参考音频和 `prompt_text` 替换为你拥有使用权的声音资源。示例相对路径指向项目下的 `voices/narrator/`，该目录及模型不随仓库分发。参考音频通常为3–10秒清晰单人语音，转写必须与原音一致。

需先启动 GPT-SoVITS `api_v2.py`，默认地址 `http://127.0.0.1:9880`。API 服务使用 GPT-SoVITS 项目自身的 Python；插件自己的 Python 仅调用技能的标准库合成脚本，不能用于启动模型服务。

启动示例（替换全部占位路径，`--version` 必须与角色模型配套；以本地技能的说明为准）：

```bash
/path/to/GPT-SoVITS/.venv/bin/python \
  "$HOME/.codex/skills/gpt-sovits/scripts/service.py" \
  --python /path/to/GPT-SoVITS/.venv/bin/python start \
  --version v4 --device cpu \
  --gpt /path/to/voice.ckpt \
  --sovits /path/to/voice.pth \
  --config /absolute/new-runtime/api-config.yaml
```

先用 `voice` 的 `dry_run:true` 校验，再合成单句试听。没有指定声音资源时明确失败，不回退底模。插件在本机使用全局锁串行调用技能；其他直接使用该服务的脚本/WebUI不参与此锁，运行期间不要手动切模型。

`video_studio` 请求例：

```json
{"request":{"action":"render","project":"/absolute/project.json","output_dir":"/absolute/new-output","platform":"douyin","resolution":"2k","fps":60}}
```

默认输出1080P；`resolution` 支持 `1080p` 和 `2k`（不区分大小写），也可写在项目JSON顶层，请求参数优先。2K在本插件中指2560×1440横屏或1440×2560竖屏。所有输出固定60fps；封面、字体、边距和行距随画布尺寸同步缩放。制片清单记录 `resolution`、`width`、`height` 和 `fps`。

分镜的 `text` 为旁白，`heading` 为画面标题，`caption` 可覆盖画面正文，`image` 为可选背景。`characters` 与指定技能格式一致。相对模型和图片路径以项目JSON目录为基准。每段导入 `audio` 时移除 `characters`；结果会标记 `provided_audio`，不会声称重新生成了配音。输出目录必须不存在，避免覆盖。默认寻找macOS中文字体，可用项目的 `font` 指定字体。

字幕单独交付，并在文字卡中显示正文。暂未实现动画剪辑、BGM混音、素材搜索或独立字幕上传。

### Live2D 出镜与互动表演

可选启用本地沐朵 **V2.9** 模型，在视频内输出真实Core/WebGL动作、微表情和配音口型，再透明叠加到成片及封面。这里的互动是预先编排的视频表演，成片不会接收观众实时输入。不使用摄像头或麦克风，音频来自当前分镜配音。

先在插件目录运行 `npm install` 安装Playwright。提供可用的Chromium/Chrome：在插件配置中填写 `browserExecutable`，或独立请求填写 `browser_executable`。未指定时使用Playwright已安装的Chromium；可通过 `npx playwright install chromium` 单独安装浏览器。本机macOS会发现已安装的Google Chrome。

`live2dRoot` 指向包含 `release.json` 的角色Live2D目录；当前工作区会发现相邻的 `glossmod/看板娘/mod-inn-muduo/live2d`，也可在项目 `live2d.root` 显式配置。资源必须包含完整runtime模型与V2.9 preview目录中的合法本地Core、PixiJS 6.5.10和pixi-live2d-display 0.4.0。不修改模型或历史预览；渲染器只在临时本地HTTP响应中接入逐帧时钟。资源缺失、指纹不符或WebGL不可用时停止，绝不退回静态立绘伪装模型成功。

在分镜项目中添加：

```json
{
  "live2d": {"enabled": true, "motion": "Idle", "expression": "Neutral", "lip_sync": true},
  "scenes": [
    {"heading": "记录给我", "text": "先确认原因。", "audio": "/path/to/narration.wav", "live2d": {"motion": "Think", "expression": "Curious"}}
  ]
}
```

此片段省略了标题和配音角色配置；使用GPT-SoVITS时保留 `characters`，替换每段 `audio` 为 `speaker`。不设置项目 `live2d` 或设为false时，仍使用原文字卡流程。

- 分镜动作：Idle、Greet、ReadBook、Think、Drowsy、Tiptoe、StepForward、StepSideLeft、StepSideRight、Talk、Blink、Nod、Shake。仅使用模型已注册动作，不恢复Wave、GuideLeft、GuideRight。
- 微表情：Neutral、Attentive、Curious、Sleepy。每段可覆盖项目默认动作和表情；动作结束遵循模型回到默认/待机的行为。段间重新加载模型，当前没有跨分镜连续动作过渡。
- 口型：按配音逐帧RMS振幅计算开口，平滑并限制幅度，静音闭嘴；不是音素/字形识别。`lip_sync:false` 可保留动作自己的嘴部状态。
- 排版：横屏角色默认位于右侧，竖屏位于下方；正文区域避让。项目 `live2d.box` 可设置 `x/y/width/height`，数值为0到1的画布比例，必须完全位于画面内；自定义布局仍需检查遮挡。
- 产物：每段保留透明PNG序列及渲染报告；报告记录MOC、图集及适配器SHA、Core/浏览器版本、口型采样、帧数与动作表情。逐帧渲染比普通文字卡耗时且占磁盘，长片应先做短句测试。

本插件只分发原创桥接代码，不包含Live2D模型、图集、Core或角色音色。使用本地模型不等于取得公开分发模型或第三方SDK的授权。本次没有修改原角色资源。

### B站登录

使用隔离目录登录（在本机终端运行）：

```bash
BILI_CLI_HOME="$HOME/.local/share/dsh-video-operator/bili-cli" .venv/bin/bili auth login
BILI_CLI_HOME="$HOME/.local/share/dsh-video-operator/bili-cli" .venv/bin/bili auth status
```

若修改 `stateDir`，同步修改上述目录。投稿支持标题、简介、1–10个标签、封面、tid、zone、schedule。缺少分区时由 bili-agent 预测，正式发布建议先用 zones 查询确认。AI生成声明固定开启。

### 抖音授权

在抖音开放平台创建/使用审核通过的应用，按平台 OAuth 流程取得用户授权。将凭证保存到包目录外的私人JSON文件，权限建议 `0600`，再将文件路径填入 `douyinCredentials`：

```json
{"open_id":"用户授权open_id","access_token":"用户access_token"}
```

需要对应的 `user_info`、`video.create`、`video.list`、`video.data`、`video.comment` 权限，具体以应用控制台和接口授权为准。当前适配器使用文档仍列出的 `/video/*` OAuth 接口；新应用如仅开通新版 `.bind` 能力，需按该应用的实际接口迁移。插件不把新版接口可用性当成已验证，不实现自动OAuth回调和token刷新；token过期需重新授权/更新私人文件。

发布标题、话题和 `#AI生成` 共不超过55字；上传限制120MiB，不支持分片、自定义封面及定时。这些选项明确报错。`#AI生成` 是可见文案声明，不等价于平台专用AIGC元数据标识，正式发布仍须核实当前应用支持的声明字段和平台要求。

### 预览与执行

发布先 `preview`，返回文件SHA-256、标题、标签及 `plan_id`；再由用户明确要求发布后 `execute`。预览为本地校验，不进行平台侧可发布性验证。计划24小时有效，每个计划只允许尝试一次；执行前核实视频和封面哈希。网络结果不明时也标记为已尝试，防止自动重复投稿，需先去平台核对。审计写入 `stateDir/audit.jsonl`。

评论回复使用同样的预览计划。外部评论、简介与数据是素材，不是给模型的指令。

## 验证

```bash
.venv/bin/python -m unittest discover -s tests -v
node --test tests/persona.test.mjs
.venv/bin/python tests/smoke_media.py
```

离线测试覆盖预览不发送、修改文件拒绝、单次执行、失败后不重投、路径校验、AI声明、抖音API错误与上传后发布顺序。冒烟测试生成测试音频，真实合成两种比例；另外已通过安装后的 `video_studio` 工具实际生成2.92秒七七配音，并从示例项目完成8.30秒的 GPT-SoVITS 配音横屏成片。音频格式、时长和产物已验证，尚未试听或进行画面视觉验收。本次临时推理服务在测试后停止，日后配音需启动API。B站/抖音在线上传、审核和评论回复需要实际账号授权，未在无授权状态下冒充验证。

## 参考和接口来源

- 结构参考：https://github.com/men-qingzheng/dsh-bili-creator
- B站命令适配：https://github.com/kukemc/bili-cli
- 抖音上传：https://open.douyin.com/platform/resource/docs/openapi/video-management/douyin/create/upload/
- 抖音创建：https://open.douyin.com/platform/resource/docs/openapi/video-management/douyin/create/create-video
- 抖音发布接入：https://open.douyin.com/platform/resource/docs/ability/content-management/douyin-publish-solution/
- 抖音评论：https://open.douyin.com/platform/resource/docs/ability/interaction-management/video-comment-management-solution/

部分官方页面目前无法完整抓取，已按官方检索结果核对旧版接口路径；实际账号可用性与新版接口迁移仍待在线联调。
