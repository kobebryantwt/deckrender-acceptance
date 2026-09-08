# DeckRender 独立发布验收框架

基于 [《DeckRender GitHub 最终发版验收手册》](deckrender-github-release-acceptance.md) 构建的独立黑盒验收框架。直接针对 **已发布** 的 `@deckflow/deckrender` npm 包进行严格验证，不修改产品源码，不使用 `main` 分支或本地开发构建替代正式发布包。

- 🌐 **在线验收报告总览 (GitHub Pages)**：[https://kobebryantwt.github.io/deckrender-acceptance/](https://kobebryantwt.github.io/deckrender-acceptance/)
- 📦 **开源仓库**：[https://github.com/kobebryantwt/deckrender-acceptance](https://github.com/kobebryantwt/deckrender-acceptance)
- ⏰ **定时周检**：每周二下午 14:34 (北京时间，UTC 06:34) 自动触发流水线并归档至 `acceptance-results` 分支。

---

## 核心定位与设计理念

1. **规范与契约驱动（Spec-Driven）**：
   - 坚决杜绝“拿产品自己的运行结果反写成标准答案”（避免自圆其说的虚假放行）；
   - **裁判与考生严格解耦**：由第三方独立工具（如 `python-pptx`, `pypdf`, `Pillow`, Linux `strace`）提取客观物理事实（真实页数、文件尺寸、进程外连数）；拿提取出的客观真值去断言产品返回的业务 JSON 字段（`ok`, `engine`, `route`, `pages`, `outputs`, `error.code`）。
2. **全格式状态机矩阵覆盖（54 格双向防护）**：
   - **已支持路线（✅）**：必须执行成功、返回 `ok=true`、产物有效解码、页码递增；
   - **规划中路线（🕓）**：必须在客户端/云端明确拦截，返回稳定错误码 `not_implemented`，禁止伪造产物；**若产品已实现但文档未更新，框架立刻报警文档漂移（Documentation Drift）**；
   - **不支持路线（—）**：必须立即拒绝并返回 `unsupported_format`。
3. **真实执行透明度（Execution Transparency）**：
   - 每一个用例在题面、审核后台以及验收报告中，均全量回显 **待测 CLI 完整执行命令** 与 **等价 Node.js SDK 调用代码**，彻底告别黑盒盲区。
4. **自包含测试集与四大困难集**：
   - 在 `benchmark/corpus/` 下自包含维护 16 份高质量开源文档（CC0-1.0 / CC-BY-4.0 / Apache-2.0，严禁外部绝对路径依赖）；
   - 100% 覆盖**字体集（中英简繁/日文/RTL阿拉伯语/符号）、图表集（多系列原生图表）、特殊元素（64个OMML公式与转场时序）、密集排版（单页上百节点与长表格）**四大困难维度。

---

## 快速上手与操作流程

### 1. 环境准备

- **运行时**：Python 3.9+、Node.js 22、npm。
- **推荐工具**：
  - macOS 本地自测建议安装：`brew install tesseract ffmpeg`
  - 正式 Linux CI（Ubuntu 24.04）环境具备 `unshare`, `strace`, `tesseract`, `ffmpeg`, `fonts-liberation`, `fonts-noto-cjk`。

```sh
python3 -m pip install -r benchmark/acceptance/requirements.txt
```

### 2. 准备与环境自检

```sh
# 冻结并下载最新正式版（或通过 --tag v0.3.1 指定版本）
python3 benchmark/scripts/release_acceptance.py prepare --online

# 环境医生检查（检查可执行工具、字体、隔离能力）
python3 benchmark/scripts/release_acceptance.py doctor

# 扫描四大困难集结构并构建最新题库
python3 benchmark/scripts/release_acceptance.py difficulty

# 校验 Core 2.1 规范与套件定义
python3 benchmark/scripts/check_core.py benchmark/scripts/deck_benchmark.py
python3 benchmark/scripts/deck_benchmark.py validate --suite deckrender-release
python3 benchmark/scripts/deck_benchmark.py validate --suite deckrender-quality
```

### 3. 本地可视化审核后台（双工作台）

启动本地可视化管理服务：
```sh
python3 benchmark/scripts/release_acceptance.py manage --port 8768
```

启动后可在浏览器中访问：
- **`http://127.0.0.1:8768/` 或 `/gt`** —— **Visual Workbench（图像与 GT 候选工作台）**：
  - 双栏并排对照源文件独立预览与候选/渲染结果；
  - 自动展示宽高比、分辨率与非全白/全黑预检徽标；
  - 提供快捷键 `1`（本页标记符合）、`← / →` 翻页、以及「当前可见页标记符合」批量操作（仅当前文件当前筛选内的页面）；
  - 标记跨文件累积，自动保存在当前浏览器、当前地址；顶部显示已提交、已标记未提交与待完善页数。填写审核人后，点击「提交全部已完成审核」一次提交全部已完成页，无需逐页导出。
  - 「导出全部草稿备份」用于备份或换浏览器/端口；「导入草稿备份」可合并旧 JSON，导入后仍需提交。源文件或图像哈希变化的记录会隔离，不自动批准。也可用 `gt apply --file <path>` 导入完整审核。
  - 图像 GT 提交不会代替 Casework 问题与预期答案审批。
- **`http://127.0.0.1:8768/casework/`** —— **Casework 契约事实审核后台**：
  - 查看每个用例的【待测 CLI/SDK 执行代码】与【具体量化的预期 JSON】；
  - 点击「一键审核全部场景」并点击「同步到验收」。
- **`http://127.0.0.1:8768/coverage`** —— **矩阵范围与覆盖率全景图**。

### 4. 执行验收运行与导出

```sh
# 执行本地用例组自验（可指定 --group local / release / cloud / quality / all）
python3 benchmark/scripts/release_acceptance.py run --group release --run-id my-release-run

# 注入云端 Token 执行真实云端自测（可选）
export REN_ALLOW_CLOUD=1
export DECKRENDER_API_KEY="你的云端Token"
python3 benchmark/scripts/release_acceptance.py run --group cloud --run-id my-cloud-run

# 导出自包含 CI 快照（生成 READY 凭证）
python3 benchmark/scripts/release_acceptance.py snapshot export --output ci-input/current
python3 benchmark/scripts/release_acceptance.py snapshot validate --snapshot ci-input/current
```

---

## GitHub Actions 自动化周检

工作流文件位于 `.github/workflows/release-acceptance.yml`：

- **调度时机**：
  - **定时周检**：`cron: '34 6 * * 2'`（**每周二下午 14:34 北京时间** / UTC 06:34 自动触发）；
  - **主干提交触发**：`push: branches: [main]`；
  - **手动重跑**：`workflow_dispatch` 支持手动输入发布 tag 或勾选 `force` 强制重跑。
- **并行执行矩阵**：
  - `release`：校验包元数据、开源协议、版本一致性；
  - `local`：本地 PPTX/PDF 格式矩阵与依赖错误流；
  - `privacy`：Linux 命名空间与 strace 全进程树零网络、零凭据泄露验证；
  - `cloud`：云端 30 路线状态机矩阵及智能选路；
  - `quality`：困难集渲染产物多页质检。
- **仓库配置要求**：
  1. **Secrets**：添加 `DECKRENDER_API_KEY`（填入云端测试 Token）；
  2. **Variables**：添加 `REN_ALLOW_CLOUD`，值设为 `1`；
  3. **Pages**：Settings → Pages 的 Source 选择 **GitHub Actions**（历史报告自动归档并在 Pages 在线展示）。

---

## Git 提交安全指引（哪些文件不应上传）

在执行 `git add` 和 `git commit` 前，请务必严格遵守以下文件提交边界：

### ❌ 严禁上传到 Git 的文件清单（已配置 `.gitignore` 保护）

1. **`benchmark/artifacts/` 目录下的所有内容**：
   - `releases/`：本地下载并解压的 `@deckflow/deckrender` npm tarball 原始包与 node_modules（体积巨大）；
   - `runtimes/`：本地构建的临时 node_modules 运行环境；
   - `casework/`：本地 SQLite 数据库（`casework.sqlite3`）与本地样本临时缓存；
   - `runs/`：本地测试运行的中间输出、临时图片产物与调试日志；
   - `private/`：本地运行留存的未脱敏原始数据（可能包含系统绝对路径或敏感信息）；
   - `source-previews/`, `gt/`, `gt-assets/`, `font-cache/`：本地生成的临时栅格化图片缓存。
2. **密钥与本地环境文件**：
   - `.env`, `.env.*`（严禁提交任何明文 API 密钥，Token 只能配置在 GitHub Secrets 中）；
   - `*.pem`, `*.id_rsa`, `*.id_ed25519` 等私钥凭据。
3. **系统与编辑器临时文件**：
   - `.DS_Store`, `.idea/`, `.vscode/`, `__pycache__/`, `*.pyc`, `*.log`。
4. **未审核通过的草案快照**：
   - 未获得批准或缺少 `READY` 凭证的临时快照目录，绝不能作为 `ci-input/current` 提交到 Git。

### ✅ 应当提交到 Git 的文件清单

1. **框架源代码与适配器**：
   - `benchmark/acceptance/`（全部 Python 调度与契约代码）；
   - `benchmark/adapters/`（SDK 适配器与探针）；
   - `benchmark/evaluators/`（版本化评估器）；
   - `benchmark/scripts/`（CLI 驱动入口）；
   - `casework/`（轻量审核后台源码，不含 sqlite 缓存数据）。
2. **用例定义与配置文件**：
   - `benchmark/config/`（包含 `case-selection.json` 出题策略与版本契约）；
   - `benchmark/suites/`（包含两个套件的 `cases.jsonl`, `questions.jsonl`, `suite.json`）。
3. **自包含合法开源测试集**：
   - `benchmark/corpus/`（14 份经过清理、具备合法开源许可且无加密的样本及 `manifest.tsv` 清单）；
   - `benchmark/fixtures/`（自建的 2 份带页码独立标记的 markers 文件）。
4. **CI/CD 工作流与规范文档**：
   - `.github/workflows/`（全部 GitHub Actions 工作流）；
   - `deckrender-github-release-acceptance.md`（验收手册）；
   - `ci-input/current/`（仅在完成正式审批、成功导出并附带 `READY` 签名凭证后提交）。

---

## 框架自验证与测试

在提交代码或变更出题规则后，运行以下测试确保框架自身健康度：

```sh
# 1. 运行 85 项框架单元与防作弊回归测试（含 R03、SDK 对称性、GT 完整性、JSON 契约值匹配）
python3 -m unittest discover -s benchmark/acceptance/tests -v

# 2. 运行 21 项 Casework 事实与状态机测试
python3 -m unittest discover -s casework/tests -v

# 3. 校验 Core 2.1 契约指纹一致性
python3 benchmark/scripts/check_core.py benchmark/scripts/deck_benchmark.py
```

当前全套 106 项测试均处于 **100% 通过 (OK)** 状态。
