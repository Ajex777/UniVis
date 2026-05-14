# Phase 001: Viewer UI Polish

## Goal

在 Phase 00 fake `PolicyEpisode` viewer 的基础上打磨功能和视觉效果，让页面更接近真实数据审查工具。此阶段仍然使用 fake `PolicyEpisode`，但 UI 入口和交互要按真实工作流设计。

## Scope

- 增加 client 端本地目录选择入口。第一版只验证选择交互；后续真实数据接入必须走“目录文件上传到 server staging 后解析”，不能依赖浏览器提供绝对路径。
- 增加输入数据格式和输出数据格式下拉框，选项来自后端 registry API，后续与 adapter/exporter class 注册对应。
- 左侧 episode 列表支持滚动、折叠、点击切换 episode。
- episode item 用颜色表达转换状态：白色未转换，红色被拒绝，绿色转换完成，转换中用绿色占比表达进度。
- 增加自动播放，支持 pause、0.5x、1x、2x、3x。
- 修复右侧 annotation 状态按钮排版。
- 保持可变 camera slot 选择能力。

## Acceptance

- 页面顶部或左侧存在目录选择控件，选择目录后能显示目录名和文件数量。
- 输入/输出格式下拉框能显示后端注册的 adapter/exporter 名称。
- episode 列表区域可折叠，列表内容超出时可以上下滚动。
- fake episode 列表能展示 pending、rejected、converting、converted 等状态视觉。
- 自动播放在不同倍速下能推进时间轴，并能暂停。
- annotation 状态按钮不挤压、不错位。
- 所有新增源码文件仍保持单文件不超过 250 行。

## Tests

- 后端 smoke test：registry API 返回输入/输出格式。
- 前端手动验收：选择目录、切换格式、折叠 episode 列表、切换 episode、自动播放、保存 annotation。
- 文件行数检查：新增或修改文件不超过 250 行。

## Out Of Scope

- 不读取真实本地目录内容到 server。
- 不执行真实转换。
- 不接真实 adapter/exporter class。

## Follow-up Decision

真实数据源入口采用浏览器目录选择 + 文件上传。前端应上传文件内容和相对路径，server 在 staging workspace 重建目录结构并交给对应 adapter 扫描。`Server path` 仅可作为开发调试捷径，不作为正式用户路径。
