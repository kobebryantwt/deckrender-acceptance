# DeckRender GitHub 最终发版验收手册

## 目标

验证 `@deckflow/deckrender` release 对“文档到视觉资产渲染层”的当前声明。验收重点是路线正确性、隐私边界、格式矩阵、结构化结果和可重复质量证据；不验收像素级或全格式保证。

## 固定输入

- Git tag、npm artifact、MIT LICENSE、release notes、源→目标→引擎矩阵。
- PPTX、PPT、PDF、Keynote、DOCX 样例；本地 PPTX/PDF 样例；Pages/Numbers 负向样例；字体、图表、特殊元素、密集页面困难集。
- 独立网络监控、云端测试账号与可查询任务删除日志。

## 一票否决项

- `local` 发生文档上传、读取云端凭据，或静默回退云端。
- Pages/Numbers 或 HTML/URL/Markdown 在公开 API 中被宣传为当前支持，且状态与矩阵不符。
- cloud route 未返回实际 engine/route/artifact/caveat，或保留期不符合已发布设置。

## 验收用例

| ID | 声明 | 步骤 | 通过证据 |
|---|---|---|---|
| REN-R01 | 可追溯 MIT release | 干净安装、核对 tag/包/changelog/LICENSE | 版本、commit、包内容和 LICENSE 一致 |
| REN-R02 | 本地 PPTX/PDF | 在断网环境分别请求 image/PDF 的已声明 route | 仅生成矩阵允许的产物；无网络连接；依赖缺失有可操作错误 |
| REN-R03 | 严格 local 边界 | 带 cloud key 和网络监控重复 REN-R02 | 文档字节不离机、不读 key、不发生 cloud fallback；结果标记 local |
| REN-R04 | 云端格式矩阵 | 对 PPTX、PPT、PDF、Keynote、DOCX 逐项按矩阵渲染 | 每对输出、页序和 caveat 符合矩阵；不可用对被拒绝而非伪成功 |
| REN-R05 | Pages/Numbers 规划状态 | 提交 Pages/Numbers 并核对 docs/help | 返回明确 planned/unsupported；不产生虚假成功 |
| REN-R06 | `auto` 可审计 | 对同时存在本地/云端候选路线运行 auto | local-first 符合规则；需云端时先警告；结果记录最终 route 和上传状态 |
| REN-R07 | 结构化结果契约 | 校验 CLI/SDK JSON 的 engine、route、ordered artifacts、caveat、lifecycle 字段 | Schema、页码排序、退出码与文档一致；错误具稳定 machine code |
| REN-R08 | 云端删除 | 分别设 1、默认 1、99 小时；检查任务、输入、中间产物、输出 | 在设定时间后共同删除；删除日志/审计证据可查；不用于训练的政策与实现一致 |
| REN-R09 | 质量基准 | 运行困难集的 local/cloud 受支持路线 | 发布基准含环境、分辨率、字体、样例与人工结论；不以无数据“高保真”发布 |
| REN-R10 | 弃用范围 | 扫描 README、docs、CLI help、SDK schema | 通用 HTML/URL/Markdown 未作为公共能力；如尚存 v0.3.1 路线，有弃用和移除版本说明 |
| REN-R11 | 支持与商业边界 | 核对 Issue、安全流程、点数/企业条款 | 不存在的 SLA、认证、地域、价格不会被承诺；机密样例提交指引可用 |

## 签核规则

本地隐私、删除、矩阵和结构化结果为 P0。质量基准首次可用可记录为 P1，但 release 必须明确其覆盖与未覆盖范围。
