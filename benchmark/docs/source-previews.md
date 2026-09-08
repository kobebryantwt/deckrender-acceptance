# 独立源文件逐页预览

审核页不以浏览器能否直接打开文件为界限。生成路径为：原文件 → 独立工具导出 PDF → 逐页图片 → 候选 GT 审核。此流程不调用 DeckRender。

- PDF：PyMuPDF 读取每页。
- PPTX、PPT、DOCX：独立 LibreOffice 转换，再读取每页。
- Keynote：macOS 使用 Keynote 原生导出，包含跳过的幻灯片，不把每步动画生成独立页面；缺少 Keynote 时尝试 LibreOffice。
- Pages、Numbers：当前是 planned/unsupported 拒绝测试样本，独立转换失败时明确保留不可预览状态，不伪造页面。
- 加密 Office、加密 PDF：缺少密码时明确拒绝生成完整页面。

`manage` 会在缺少预览或来源清单变化时自动准备，`dataset` 导入后也会准备。不要求用户自行逐份导出。可用 `gt prepare` 主动重建；转换缓存绑定源文件内容、工具版本和设置，校验导出 PDF 的哈希。工具操作独立副本，保留原件。LibreOffice 使用独立用户配置，设置宏安全级别及不更新链接，并在 macOS 显式加载系统字体；这不是 Linux 隐私验收证据。

预览记录工具版本、导出设置、输出 PDF 哈希和转换日志。LibreOffice 分页和字体可能与 Microsoft Office 不同，静态 PDF 也不能证明动画/音视频正确；因此它们只是可人工确认的候选，不是自动批准的渲染真值。原文件页数、导出预览页数和人工确认结果不能混用。

网页使用有内容哈希的图片文件，按需加载；只有一个候选时显示大图，不重复显示同一张图。不同参考和实际结果才并排比较。图片仍受本机 Host/Origin 检查及哈希校验保护。

2026-09-08 修复后：13/13 份渲染样本均有候选页图，共 156 页；另有 HTML 参考 1 页。多语言 PPTX 使用 Keynote 独立导出，其余 Office 文件优先 LibreOffice。Pages/Numbers 的拒绝测试不要求成功预览。16 个源文件未修改，所有候选均待人工确认。已发现的 LibreOffice 路径保存在本地 source-preview-tools.json，也可通过 REN_SOFFICE 显式指定。
