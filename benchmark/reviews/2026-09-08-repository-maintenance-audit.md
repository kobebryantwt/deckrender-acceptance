# 全仓维护审查

审查日期：2026-09-08，基于上一轮修复后的当前文件。仓库业务文件目前均未纳入 Git 跟踪，本文不声称相对于某个提交的差异。本轮只新增审查记录，未修改实现、删除文件、批准 GT 或执行真实质量/云端实验。历史 scope-gt-audit 是修复前记录，不代表当前统计。

## 当前基础

- 128 案例、400 题、54 个双接口矩阵格，30 个成功格有对应质量案例；验证目的没有空值。
- GT：13 个渲染样本共 156 页，另有 HTML 参考 1 页；Pages/Numbers 为拒绝样本。全部候选待审，业务答案批准数为 0。
- 重新执行：验收测试 85 项、Casework 测试 21 项、Core 行为探针均通过。测试通过不等于产品通过，也没有覆盖下列全部发布闭环反例。

## 优先修复

### P1：聚合器不能证明测试集合完整

位置：`benchmark/acceptance/ci.py:10-25`。

只核对五个 group 名称、目标/evaluator/policy 相同以及 caseId 不重复，没有绑定共同 snapshot、预期 case/assertion 清单，也未验证每条记录归属正确分组。最后直接设置 scope=complete。

临时目录反例：五个组各包含一个不同 caseId，但所有断言都声称 REN-R01 并通过，真实 summarize_quality 仍返回 PASS、complete；只 mock 了最终报告落盘，没有 mock 裁决。此为框架反例，不是产品证据。

修复：冻结时输出共同 snapshotHash、完整 case/check 清单及分组清单；各组原样携带，聚合时核对集合完全相等、无缺失/额外断言、无跨组错配。补缺 case、缺 assertion、不同 snapshot 混合、错组和空组测试。

### P1：prepare 不刷新已经存在的套件

位置：`benchmark/acceptance/cli.py:5-25`。

import_sources 每次运行，但 catalog.build 仅在 release suite 文件不存在时执行。当前仓库自带 suite，因此更换 source 或冻结新版本后，该入口可以只更新 corpus/release，继续使用旧 case/契约。runner 的 commit 守卫会阻塞部分旧契约，但不会替用户完成新版本审核包生成。

隔离 mock 验证：在当前已有套件条件下，prepare 不调用 catalog.build。建议按源集合、冻结 release、选择策略、契约版本的语义摘要触发 build + refresh；保留不变答案审核记录，变化答案重新 draft；完全不变时不增历史。

### P1：多 home 并不隔离 suite，服务更新也未统一进入事务锁

位置：`benchmark/acceptance/maintenance.py:8-16,59-69,91-105`、`catalog.py:190-197`、`common.py:36-43`。

--home 隔离了 corpus/Casework/锁，但所有实例仍读写 REPO/benchmark/suites。不同 home 可覆盖同一套 questions/cases；manage 启动和 on_apply 的 sync 也没有使用 CLI 的 locked(home) 上下文。单文件原子替换无法保证多文件版本一致。

建议 suite revision 随 home 保存，运行仅消费不可变快照；仓库保留模板或显式导出的审核包。所有服务写操作和 CLI 共用锁及 revision 检查。补双 home、审核同步与 dataset 更新并发测试。

### P2：历史首页只索引本次输入的报告

位置：`benchmark/acceptance/reporting.py:73-84`、`.github/workflows/release-acceptance.yml:156-164`。

复现：依次发布 older、newer 两批，older/report.html 仍在，首页不再包含 older 链接。CI 每轮只下载当轮 aggregate，因而符合触发条件。

应扫描并校验目标历史目录生成全量索引；相同 runId 若摘要不同必须报冲突，不能静默沿用旧文件。增加两轮发布和 ID 冲突测试。

### P2：本地/CI 比较摘要算法不同，且摘要包含机器路径

位置：`runner.py:166`、`ci.py:25`、`reporting.py:58-63`、`snapshot.py:load`。

本地计算完整 definitions 列表摘要，CI 计算分组摘要列表的摘要。同一测试集合也不一致；facts 内 GT 路径又会被 snapshot.load 变成本机绝对路径，进一步阻止跨机器比较。当前是保守地拒绝归因，不是误报产品回归，但削弱历史比较功能。

应统一 canonical execution manifest：使用源/参考内容哈希、相对对象身份、按 ID 排序的业务定义，排除工作目录和仅用于运行的路径；CI 和本地从同一清单得到相同摘要。

### P2：NO_CHANGE 指纹和运行状态语义不统一

位置：`cli.py:27-33`、`scripts/ci_driver.py:10-15`、`.github/workflows/release-acceptance.yml:164`。

本地 check 与 CI 使用不同输入字段；代码摘要未包含实际执行的 Core/scripts，修改 dispatcher 或 ci_driver 可能未触发 CI 重跑。CI 不论最终 FAIL/INCOMPLETE 都可记录 processed fingerprint，而本地仅 PASS 的 verdict 写 last-completed。环境恢复、账号启用等也不是明确的变化因素。

应区分 lastAttempted、lastCompleted、lastPassed，共用指纹构造函数，纳入 Core/编排版本及非敏感环境能力策略摘要；对 blocked 明确强制重跑/环境变化重跑策略，不能让 NO_CHANGE 被理解为已经验收通过。

### P2：周检时间与已给定计划不一致

位置：`.github/workflows/release-acceptance.yml:15`。

当前为北京时间周二 14:34，原计划为周一 10:00。若不是后来有意变更，应恢复并同步文档；本轮没有擅自修改调度。

## 需要补充的覆盖与 GT 工作

1. R03 现有隔离实验均注入伪凭据；普通 render 并非同一监控条件下的无凭据对照。补同输入/发布包/监控环境下无凭据与伪凭据两次运行，并比较路由、结果、网络与读取证据。
2. R07 边界目前重点是不存在的文件。补损坏文件、零字节、扩展名与内容不符、加密输入、无效页面范围、不可写输出目录、超时；错误预期先绑定发布契约，不能先猜错误码。
3. JPEG/WebP、页面筛选、真实动画/音视频保真仍未专项覆盖，已在 case-selection limits 披露。按冻结版本的公开能力决定必测项；image 大类不能代表全部编码。CLI 当前未转发 options.pages，增加对应题时必须同时补适配器。
4. 视频五个时间点可以做抽样内容审核，不能证明每一页都在视频中出现，更不能代表动画保真。需独立页时间区间或每页关键帧映射，加全页出现性检查；不需要像素阈值。
5. 86 页 Word 占渲染 GT 页数约 55%。保留作为长文档压力层；日常审核按页特征索引优先处理新增/变更页面，并保留完整逐页可审能力。不能为减少审核量把抽查改称全页通过。
6. 先补真实媒体/动画、明确 RTL/缺字等特征证据与页定位，再决定是否引入 Hugging Face。不要只按文件名增加“困难”标签；外部数据需来源许可、内容哈希和独立 GT 来源。
7. 现有图片候选和目的描述已经补齐；当前缺的是人工确认及部分独立视频映射。第三方导出继续作为候选预制工具，无需强制第三方闭环。

## 冗余与清理判断

| 内容 | 判断与处理 |
|---|---|
| `**/__pycache__/`，约 0.35 MiB | 可直接再生；可删除，不影响业务证据。 |
| `.playwright-cli/` 约 264 KiB、`output/` 约 1.3 MiB | 调试会话/截图候选；确认没有需要保留的人工反馈附件后删除。不是生产证据目录。 |
| `benchmark/artifacts/acceptance/runtimes/` 约 136 MiB | 冻结运行环境，占体积大头；可按保留策略回收旧版本，但重建依赖安装，不能与无成本缓存同等处理。当前版本建议保留。 |
| `font-cache/` 约 4.7 MiB | 可再生工具缓存；清理后要确认字体解析/环境记录仍一致。 |
| `gt/` 约 32 MiB、`gt-assets/` 约 27 MiB、`source-previews/` 约 12 MiB | 源预览、GT、离线网页资源有用途不同的图像副本；先做按内容哈希的引用图，再清无人引用对象，不能整目录删。 |
| `suite-history/` 约 14 MiB、`casework/` 约 25 MiB | 审核历史和样本对象，不是普通缓存。优化无变化时不写新 revision，保留历史可追溯性。 |
| release evaluator v1/v2 | **仍是活代码**：v3 → v2 → v1；禁止按版本老旧删除。 |
| 六个 evaluator `evaluate.py` | 有两组内容完全相同，但各 evaluator.json 使用自己的入口路径；属于薄包装，不值得以破坏版本入口为代价删除。 |
| quality v1/v2 与历史入口 | 兼容/历史候选，当前执行用 v3；归档前检查历史运行/evaluator 引用，并先定义历史重建支持范围。不能直接宣称死代码。 |
| CLI/SDK target descriptors、adapter | README 明确提供单次 Core 调用，均有入口用途；不要删除。 |
| HTML 参考样本 | 当前只用于范围参考，不参与成功渲染。可考虑从默认 GT 列表移入参考专区；删除价值很小，且会影响清单与映射。 |
| 原验收附件、PROVENANCE、历史审查 | 标准、来源和审查证据，保留。旧审查在索引标注“修复前”，避免被误读成现状。 |

没有发现足以支持立即整块删除的业务模块。主要空间来自有用途的数据和运行环境，不是大量无人调用代码。不要使用 git clean：当前业务目录也都未跟踪。

## 维护成本优化顺序

先修聚合、刷新与状态隔离，再统一比较/指纹并补跨进程发布测试；之后做引用驱动的缓存清理。为清理命令提供默认 dry-run、逐项原因、活跃 run/snapshot/GT/history 引用保护。

将格式矩阵的生成和覆盖分母从共同的版本化 scope manifest 派生，避免 catalog/coverage 各维护一套循环。把大型内联工作台拆成模板、脚本和样式，保留离线打包出口；将业务模块的星号导入和多语句单行逐步展开，提高审查与异常定位能力。Core 通用分支先保持兼容，不为追求文件短而裁剪。

最终验收仍需审核批准后的真实运行。本轮没有把测试 mock、GT 预览成功或覆盖题数当作产品通过证据。
