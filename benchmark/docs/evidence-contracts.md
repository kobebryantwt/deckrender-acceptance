# 证据与判断契约

## 运行边界

`prepare --online` 访问 GitHub/npm、冻结正式 tag 和 npm SRI、安装依赖并捕获公开帮助。`run` 不执行安装，也不自动补齐缺失资料。准备失败的 staging 保留诊断，不能替代已冻结目标。

本地隐私实验在 Linux network namespace 内运行，strace 跟踪进程树，使用假凭据和 Node 环境变量读取探针。每轮先进行负向校准：连接保留测试地址、读取假凭据文件和环境变量，确认监控确实捕获违规操作。校准或权限缺失均 BLOCKED。Node 探针不声称能观测原生程序直接读取进程环境内存；证据中保留该边界。下载/安装阶段不计入运行时断网实验。

R02 和 R03 的 local 执行采用隔离监控。PDF→PDF 的 `passthrough` 即使无上传，也不会被改写成 `local`；附件与发布契约的该差异如实呈现。图片完整性不是视觉保真：没有独立页数/页序答案时，结构检查保持 REVIEW。

## 云端账号与删除

`REN_ALLOW_CLOUD=1` 是明确启用真实云测试的开关；还需配置 `DECKRENDER_API_KEY` 或所支持的其他测试账号变量。仅批准公开的源可上传。缺账号时不降级为 guest 实验。

v0.3.1 发布的类型未暴露保留期设置和完整生命周期返回，因此不能伪造一个保留期参数或删除 API。框架提供下列**证据适配协议**；它不宣称上游已实现这些端点。没有经验证的服务接口时，R08 配置检查按契约判断，真实删除检查保持 BLOCKED。提供后端实际接口后应实现并审核对应适配器，不能把客户端 404 当作服务器删除证明。

`REN_LIFECYCLE_COMMAND` 和 `REN_AUDIT_COMMAND` 是 JSON argv 数组。框架将一个请求 JSON 文件的绝对路径作为最后一个参数传入，要求 stdout 为 JSON、成功退出码为 0；不经过 shell。这是供已有审计服务接入的扩展点，不要求审核人编写评测器。

生命周期请求：

```json
{"action":"submit","idempotencyKey":"...","input":{"uri":"...","sha256":"..."},"requestedHours":null}
```

`null` 表示不传保留期、验证默认值。另两组显式传 1 和 99。服务响应必须包含：

```json
{
  "taskId":"task-id",
  "sourceSha256":"source-sha256",
  "requestedHours":null,
  "effectiveHours":1,
  "createdAt":"2026-09-08T00:00:00+00:00",
  "expiresAt":"2026-09-08T01:00:00+00:00",
  "objects":[
    {"kind":"task","id":"task-id"},
    {"kind":"input","id":"input-id"},
    {"kind":"intermediate","id":"intermediate-id"},
    {"kind":"output","id":"output-id"}
  ]
}
```

请求同时携带冻结的 target（tag、commit、npmTarballSha256），响应必须原样绑定该实际发布身份。必须列出实际所有对象，不应填占位 ID。提交前持久化 intent；结果不确定时不重提。后续 `collect` 通过 `{"action":"lookup","idempotencyKey":"..."}` 查询既有任务。确定未提交的配置阻塞允许在环境补齐后再次提交。

审计请求为 `{"action":"collect","experiment":{...}}`。响应包含 taskId、sourceSha256、authority、auditId、checkedAt 和对象列表。每个对象需 kind、id、state、deletedAt、deletionLogId；列表必须与提交清单完全一致，时间需带时区且可比较。

- 到期前：等待，BLOCKED。
- 到期后对象仍保留，或删除晚于声明期限：FAILED。
- 所有对象有服务端日志且按期删除：PASSED。
- 只看到 URL 失效、404、对象列表缺失、身份不符或审计不可用：BLOCKED。

审计文件也可使用 `cloud collect --evidence /path/audit.json` 导入。声明“不用于训练”需另外提交政策及实施审计，不能从任务删除推导。

## 人工证据

`apply-reviews` 仅处理指定的语义/视觉待审项（以及缺少不用于训练证据的阻塞项）。不能覆盖 schema、许可证、已证实的隐私泄露等确定性失败。

```json
{
  "runSha256":"sha256-of-run-json",
  "actor":"审核人",
  "reviewedAt":"2026-09-08T12:00:00+08:00",
  "reviews":[{
    "caseId":"REN-R09-quality-...",
    "assertionId":"visual",
    "status":"passed",
    "conclusion":"已逐页对照独立参考并核实可读性",
    "rubric":{"text":"passed","clipping":"passed","overlap":"passed","charts":"passed","hierarchy":"passed","legibility":"passed"},
    "evidence":[{"path":"reference-and-review.pdf","sha256":"..."}]
  }]
}
```

视觉报告在具体运行后生成 `visual-review-template.json`，列出实际图片哈希。每个渲染结果的标准答案来自源事实、独立参考或人工审核；不能把目标本次输出保存为黄金答案来消除差异。人工复核附件尚未经公开授权时，新报告保持本地私有。

## 审核与兼容性

批准绑定当前答案摘要、源文件身份、检查定义和请求选项。改检查、事实或源内容会使旧批准失效。Casework 记录操作者和历史；它是单机审核工具，不提供多用户身份认证。READY 是完整性和批准状态凭证，不是密码学签名或不可伪造的第三方认证。

比较要求 evaluator 代码哈希、策略哈希、执行定义以及 case/source SHA 集合一致；不一致仍可查看差异，但不归因产品回归。报告中原始命令保留供复现，不自动运行报告里的命令。
