# 云端执行与周检

正式周检每周二北京时间 14:43 自动运行，不因同版本上次成功而跳过。手动运行可选择 `formal` 或 `debug`（默认）。push 使用 debug 且强制禁止云端调用。框架测试工作流仍独立运行。

## 配置

- Repository Secrets `DECKRENDER_API_KEY`：有额度的正常账号。
- Repository Secrets `DECKRENDER_API_KEY_2`：积分不足专用账号；没有 Secret 就阻塞，没有内置凭据。
- Repository Variables `REN_ALLOW_CLOUD=1`：授权正式周检和手动运行使用云端。push 不继承此授权。
- 手动 debug 的 `cloud_cases`：空格分隔的 case ID，只允许指定项使用云端；未选项仍在报告清单内。
- Repository Variables `REN_MAX_CLOUD_CALLS`、`REN_MAX_SOURCE_PAGES` 可设置周检预算上限。手动输入优先于变量。
- `max_cloud_calls`、`max_source_pages`：可选的更低上限。空值采用冻结清单计算的上界，不能用更大值突破计划。

源页提交预算是每次调用提交的源文件页数之和，不是输出页数、视频帧数或积分。页数不明会阻塞；当前实现无法承诺精确的积分上限。底层产品可能一次调用产生多个服务端任务。先用手动小集确认费用，再启用周检。

## 复用与熔断

五组检查在一个执行会话内顺序运行、分别输出证据，再独立聚合。不同接口、源哈希、格式、引擎、页面参数、图片编码、凭据场景或执行条件不共用调用；重复错误码稳定性实验不缓存。只有成功调用可被其他检查复用，原始命令和响应不改写，证据文件校验失败会阻塞复用。

每次执行都有 `executionRef`。各检查的 `cloud-execution.json` 与总报告 `cloudExecution.events` 记录调用／复用／阻塞映射。预算在调用前预留；超时不退款。普通账号首次出现支付或认证失败后熔断后续普通账号调用；第二账号的积分不足用例独立执行。不会从第二账号借用额度。

## 报告与历史

全量快照的 case 和断言仍是分母。预算耗尽、未知页数、未选中或账号不可用均记 BLOCKED，已有硬契约失败继续保留。debug 报告一律 `partial:debug`，不能 PASS、不能更新正式运行状态指纹。formal 报告包含完整清单，但 BLOCKED、REVIEW 或 FAIL 均不能放行。

报告分别显示断言计数、云端调用尝试、复用次数及源页提交量；调用数不冒充服务端任务或计费次数。模式和预算策略不兼容时，历史比较不得归因产品回归。

删除审计继续使用独立持久化账本和定时恢复工作流；无可验证接口时保持阻塞。Linux 隔离探针失败也保持阻塞；预算优化不绕过网络隔离和监控要求。

## Linux 隔离兼容性

CI 设置 `REN_ALLOW_SUDO_NETNS=1`。优先尝试映射当前用户的无特权网络命名空间；失败后可用 sudo 仅创建网络命名空间并启用 loopback，随后 setpriv 降至 runner 的 UID/GID、清除附加组并设置 no-new-privs，再执行 Python/Node。不会修改 AppArmor 或全局 sysctl。

探针必须证明目标身份不是 root、网络命名空间不同于宿主且仅有 loopback。凭据哨兵与网络 strace 负向校准仍在每个受保护 case 执行前进行。框架 CI 另有真实 Linux 集成测试，验证 loopback 可绑定、外部连接返回 ENETUNREACH 且被 strace 记录。任一必要探针失败仍阻塞验收。
