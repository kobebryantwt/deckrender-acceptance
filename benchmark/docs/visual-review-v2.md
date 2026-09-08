# 图像审核与公共契约 v2

本版本不使用像素相等、MAE 或 SSIM 作为放行条件。人工审核检查文字、裁切、重叠、图表、层级和可读性。

## 审核入口

`python3 benchmark/scripts/release_acceptance.py gt prepare` 生成独立 GT 候选。`manage` 首页展示图像工作台，顶部链接进入契约答案审核。PDF 候选直接采用源 PDF 的独立栅格化预览，因此左右可能是同一图；界面明确标注，不暗示经过两个渲染器验证。

结果保留 canonical `report.html`、`agent-report.json`、`run.json`，新增主报告可进入的 `visual.html`。每个输出的图片、PDF 全部页面或视频采样帧保留源 SHA、case ID、输出序号、原始产物 SHA、预览 SHA、参考 SHA 和页码/时间戳。视频固定采样 5%、25%、50%、75%、95% 时刻，只覆盖五帧，不将帧序号当作源页码。

支持筛选、缩略图、切页、缩放、逐页 rubric 和备注。浏览器导出默认为草稿，不自动批准答案。GT 确认后用 `gt apply --file <导出文件>` 导入；结果结论用 `apply-visual --run <原运行目录> --file <导出文件> --output <新目录>`。后者要求运行哈希匹配、覆盖选中案例全部记录页/帧、逐页完整 rubric、备注和审核人，生成新报告，不能覆盖确定性失败。修改 GT 后关联业务答案需要重新审核。

## 可选独立参考

第三方工具只帮助预制 GT，不是强制交叉验证关卡，不要求输出 DeckRender Schema：

```sh
python3 benchmark/scripts/release_acceptance.py gt attach --source-id <corpus中的ID> --file <独立导出的PDF或图片> --provenance '工具、版本、源文件和导出设置'
```

导入文件按内容哈希绑定源文件，保持 draft、非公开。缺失参考不能推定质量通过。上传授权和公开许可不因导入而获得。自动预览已覆盖 PDF、PPTX、PPT、DOCX、Keynote；转换与缓存详见 [源文件预览](source-previews.md)。第三方无须提供目标特有的生命周期或上传字段，这些继续检查目标实际输出和独立审计。

## 覆盖与映射

R09 覆盖支持矩阵内的 image/PDF/video，分别测试 local/cloud、CLI/SDK。矩阵案例的 `qualityCaseId` 按源 SHA、engine、target、interface 关联质量案例。每次渲染挂 `commonSchema` gate，分别校验成功与错误分支。R07 保留错误码稳定性、文档退出码、CLI/SDK 公共语义一致性及不存在输入的边界测试。生命周期任务 ID/时间戳比较结构；输出路径和耗时不要求跨调用相等。

公共 Schema 依据冻结发布 `src/types.ts` 和附件：ok/input/format/engine/route/pages/outputs/durationMs、可选输出尺寸/字节数，以及附件要求的显式 caveat/lifecycle。lifecycle 目前强制 object，没有臆造发布未定义的子字段；上传/删除语义由 R06/R08 验证。

`difficulty` 收集字体、图表、特殊元素、密集内容的 XML 部件或 PDF 页码证据。DOCX 表格总量仅是候选，不证明单页视觉密度；文件名页数不作真值。旧格式与 Apple 格式没有扫描器时明确未刻画。现有语料四类均有结构证据，因此本次未新增 Hugging Face 下载；来源许可未自动批准。

当前（evaluator v3）：84 个发布案例、44 个质量案例、400 个草稿问题。13 份渲染样本共 156 页独立候选，另有 1 页 HTML 参考。Pages/Numbers 两份样本用于拒绝测试。正式质量执行要求完整、已审核、源哈希匹配的逐页 GT；视频还需要五个采样比例位置的独立源页映射，在工作台填写后随草稿导入。未审核参考、未知分页或缺失映射均保持 blocked，不能生成正式 READY。真实质量验收和云端调用均未执行。
