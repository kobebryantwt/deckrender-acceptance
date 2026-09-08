# 当前版本范围与 GT 审查

审查日期：2026-09-08。结论：**尚不满足既定 CLI/SDK 发布验收范围，GT 也未达到可正式使用的状态。** 本次为审查，未修改实现、重建套件、批准答案或调用真实云端渲染。临时模拟探针不属于 DeckRender 产品证据。

## 当前事实

| 项目 | 当前值 |
|---|---|
| 套件 | 发布 43 案例 / 143 题；质量 29 案例 / 87 题 |
| 合计 | 72 案例 / 230 题，全部 draft |
| 当前矩阵分母 | 27 个格式/引擎/目标组合；接口维度已被删除 |
| 质量案例 | 15 个 CLI 成功组合 + 14 个困难样本定向组合 |
| 样本 | 16 份：13 份渲染样本、2 份拒绝样本、1 份 HTML 参考 |
| 当前 GT 清单 | 5 份有图，共 32 页；11 份 blocked；渲染样本为 5/13 有预览 |
| 已批准图像参考 | 0；所有源 facts.references 均为空 |
| 哈希验证 | 16 个源与当前清单的 32 个 PNG 均通过，清单绑定当前 corpus 哈希 |
| 自测 | 验收测试 70/70、Casework 21/21、Core 行为检查和两个 suite 结构校验通过 |
| 环境 | 发布包 doctor 可用；Linux 隔离不可用，云端未启用，未配置审计来源；当前可找到 soffice |

现有测试通过只说明已有测试所验证的行为通过，不足以证明本次合并和缩减没有漏测。下面的问题已通过代码追踪、现有材料和隔离的临时模拟验证。

## 需要优先修复

### 1. P1：R03 合并后没有执行隐私判定，独立 CI 分组为空

[catalog.py:191](/Users/tong/Project/deckrender-acceptance/benchmark/acceptance/catalog.py:191) 给本地 render 增加 `checkPrivacy` 和 R03 covers，但 [runner.py:52](/Users/tong/Project/deckrender-acceptance/benchmark/acceptance/runner.py:52) 的 render 分支只评估 outcome、artifacts、commonSchema；`privacy_evidence` 只在独立 privacy operation 下调用。

模拟返回合法响应后，三条断言 network/credentials/local 全部缺失，privacy evaluator 调用次数为 0。执行时这些断言成为 `Evaluator omitted assertion` blocked，而非实际隐私结果。

同时 [runner.py:130](/Users/tong/Project/deckrender-acceptance/benchmark/acceptance/runner.py:130) 仅按 `covers[0]` 分组。现在没有首项为 R03 的案例，`--group privacy` 选中 0 案例；现有 CI 仍要求 privacy 分组，聚合链无法完成。题目 featureId 也全部继承 R02，因此覆盖表出现 R03 有 4 案例、6 类规则，却有 0 条题目。

修复应同时处理调用、断言归属和 CI 分组去重，不能只补一处 covers。

### 2. P1：SDK 范围被两条 PPTX 图片对照替代

[catalog.py:197](/Users/tong/Project/deckrender-acceptance/benchmark/acceptance/catalog.py:197) 的矩阵、auto 和质量均仅生成 CLI。R07 只对本地/云端 PPTX→image 调用 SDK，不能覆盖 SDK 的 PDF、video、DOCX、PPT、Keynote、Pages/Numbers 和 auto 分支。

[coverage.py:8](/Users/tong/Project/deckrender-acceptance/benchmark/acceptance/coverage.py:8) 同时删除 interface 维度，将原来的 54 格缩成 27 格；因此 27/27 仅代表 CLI 范围内完整，不代表既定双接口范围完整。

可以共享规则、参考图与人工审核结果来降低成本，但需要保留接口执行映射；如需复用某次视觉判断，应先记录产物内容身份和等价证据，不能由两条接口 smoke test 推及所有组合。

### 3. P1：新增具体 GT 含猜测页数及错误产物数量

[catalog.py:111](/Users/tong/Project/deckrender-acceptance/benchmark/acceptance/catalog.py:111) 在没有独立 pages 时按文件 ID 猜测 55、3 等数字。当前 PPT、Keynote、DOCX 代表文件均有缺少独立页数事实的情况，却生成确定页数答案。

同处将 pages 直接写成 `outputs` 元素数量。当前三页 PDF→PDF 的题面要求三个输出文件；冻结发布的 [renderer.ts:157](/Users/tong/Project/deckrender-acceptance/benchmark/artifacts/acceptance/releases/v0.3.1/source/src/core/renderer.ts:157) 明确 passthrough 只产生一个 artifact，并报告 engine=passthrough。附件对 local 标记的要求应作为独立差异判断，不能与文件数量/JSON pages/物理 PDF 页数混为一个 GT。

未知页数应保留 unknown/review；分别定义源页面数、输出文件数、文件内页面数、JSON pages 的版本语义，并注明独立证据。

### 4. P1：题面具体 JSON 预期没有被执行器落实

题面写出了准确的 route、engine、错误码和质量条件，但 [runner.py:51](/Users/tong/Project/deckrender-acceptance/benchmark/acceptance/runner.py:51) 调用的通用检查并不消费这些文本预期。

临时探针得到：

- `route=['wrong-but-nonempty']` 仍通过 commonSchema。这作为结构检查本身合理，但现在题面声称精确路线已被检查，缺少对应的语义断言。
- planned 题面要求 not_implemented，执行器传入 `False` 后，unsupported_format 也通过 outcome。
- 质量 integrity 题面宣称 channelStddev>0.5、分辨率符合规范，实际 integrity 仍是 artifact_checks。预检另外生成观察值，不等于这条题面已被验证。

应将需要判定的值作为版本化结构化 expectation 传给 evaluator；通用 schema 与业务语义分开。视觉预检不能替代逐页视觉真值，也不应未经校准成为像素放行阈值。

### 5. P1：READY 不证明视觉 GT 就绪

[snapshot.py:21](/Users/tong/Project/deckrender-acceptance/benchmark/acceptance/snapshot.py:21) 只检查已有 references，空集合直接跳过。临时模拟一条已审核、公开的 quality case，令 facts 为空，正式 snapshot export/validate 仍通过并生成 READY。

这不是当前真实答案已被批准，而是就绪检查存在语义缺口：仅审核文本问题即可进入质量执行，不能保证存在完整的已审核图像参考。应增加逐页 GT 就绪条件，或明确区分“可采集证据”和“可按 GT 完成质量判定”的状态；缺少参考/页映射时保持未完成。

### 6. P1：R08 将已确定的不支持与缺少环境统一为 blocked

[runner.py:39](/Users/tong/Project/deckrender-acceptance/benchmark/acceptance/runner.py:39) 在找不到保留期选项时固定返回 blocked，甚至直接写“产品当前未实现”。这混淆了两种情况：无法取得审计来源应 blocked；充分证据已证明无法满足明确保留期契约，应 failed。

另外，仅搜索 retentionHours/retainHours 两个名字不足以证明所有 API 都不支持；需要冻结公开契约映射和实际设置/拒绝证据。不能一边声称已证实产品不支持，一边仅记录环境阻塞。

## GT 范围与质量

当前有预览的只有 3 份 PDF 和 2 份 Keynote。全部 PPTX、DOCX、PPT 的当前清单均 blocked，因而图表、公式、多语言和长文档困难集虽然有题，尚无完整可审核图像 GT。现有 32 页哈希有效；抽查的 Keynote 页面可读，但这不能批准全部页面的内容正确性。

当前阻塞理由全部仍为“需要 LibreOffice”，而本次 doctor 能找到 soffice。应检查预览生成进程的 PATH/工具发现并恢复源哈希匹配的独立候选，而不是将目录中可能存在的旧缓存直接统计为当前已就绪。

困难集结构标签不能当视觉真值：special-elements 仍只有一份来源经结构扫描证实；视频切换样本没有转场/媒体结构。Keynote 的 charts 标签也不能由截图中存在图形推定为原生图表保真。视频目前只取五个时间点且 sourcePage=null，仍缺人工可提交的时间戳→源页映射；第三方预制 GT 不需要模仿产品 schema，但这一对应关系必须可审计。

JPG/WebP、页面筛选、更多异常输入、真实动画/音视频保真仍未专门覆盖。若首版允许缩小这些范围，应在验收范围中明确，而不能称为全部发布能力覆盖。

## 处理顺序

先恢复 R03 执行/CI 和双接口范围，再清除猜测答案并落实结构化业务期望；然后补 GT 就绪守卫和当前缺失的候选页面，逐页审核。更新测试，使其能发现这些失败场景，最后更新 VALIDATION.md 中仍保留的上一版数量与预览结论。

本次没有进行真实质量验收，也没有自动批准任何 GT。
