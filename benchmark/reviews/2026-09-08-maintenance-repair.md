# 发布闭环修复记录

针对 repository-maintenance-audit 的七项优先问题实施修复，保留当前用户新增的 CLI/SDK executionSnippet 字段和审核页面展示。

| 问题 | 实施 |
|---|---|
| 聚合完整性 | 必须提供审核 snapshot，核对 manifest、snapshotHash、group case 全集、assertion 全集、定义和 source SHA；不再按组名齐全推断 complete。 |
| prepare 陈旧套件 | 以 corpus、冻结 release 内容、生成代码和配置摘要判断刷新；刷新后 reconciliation 保留未变化审核，变更继续 draft。 |
| home/服务互相覆盖 | 非默认 home 使用自己的 suites；服务的写请求及同步共用 CLI 锁，启动预览准备同样加锁。默认 home 的仓库 suite 继续兼容 Core。 |
| 历史首页 | 从发布目标中的全部已封存报告生成索引；runId 内容冲突拒绝。 |
| 比较摘要 | 本地及聚合使用同一全量 execution manifest；内容已识别对象的 uri/path 不参与摘要。 |
| NO_CHANGE | 共用 state 模块，纳入 Core/scripts/config/Casework 和非敏感能力开关；区分尝试、完成、通过；不完整与待审可重试。 |
| 调度 | 恢复北京时间周一 10:00。 |
| 清理 | 新增 dry-run 默认清理入口，仅允许 Python 字节码缓存；不删除数据、GT、历史或旧 evaluator。 |

验证：验收测试 100 项、Casework 21 项通过（最终复核见 VALIDATION）；新增 15 项测试覆盖缺 case/check、错组、混用快照、断言定义篡改、重复断言、跨目录内容身份、连续发布/冲突、home 隔离、prepare 无变化、未完成重试及保守清理。

实际本地 prepare 连续两次：第一轮刷新，第二轮审核 revision 保持 3；16 个源、128 案例、400 题不变，批准数仍为 0。没有执行真实质量/云端实验。

本轮处理发布闭环与维护缺陷。审查中的范围扩展仍在 backlog：R03 同监控条件双凭据对照、更多异常输入、JPEG/WebP/页面筛选、真实动画样本和逐页视频时序覆盖；不得以现有五点视频抽样或题数代表这些能力已经覆盖。GT/业务答案仍需人工审核。工作台拆文件、矩阵单一声明源和大体积缓存引用回收也尚未实施；当前不删除有引用用途的业务文件。
