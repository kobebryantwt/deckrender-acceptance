# 精选参考候选与样本来源

用户不需要提供基准页。本轮准备 5 份文件、8 页优先候选，保持 draft；工作台默认展示这些页，可切换“全部渲染样本与页面”。每页有验证目的、具体核对内容、参考来源及已知疑点。精选只安排审核顺序，不批准 GT，也不降低正式快照的完整参考要求。

| 文件 | 精选页 | 检查对象 | 参考依据与限制 |
|---|---|---|---|
| pptx_paired_collaboration | 1、2、3（原稿 2、11、16） | 列表与页脚、双栏截图、气泡与遮挡关系 | 作者同记录配套 PDF；配对仍待人工确认 |
| pptx_math_formulas | 15 | 分式、根号、求和及上下标 | LibreOffice 候选；边框接近页面边缘，需核对原生效果 |
| pptx_multilingual_fonts | 1、2 | 中日韩/阿拉伯文、希腊字母及特殊符号 | Keynote 转换候选；字体/RTL/标题换行需核对 |
| docx_business_report | 2 | 表格边框、单元格换行与层级 | LibreOffice 候选；页内产品描述是样本内容，不作为契约依据 |
| pdf_academic_paper | 2 | 正文、小字图注、上下标、多条曲线 | 源 PDF 直接栅格化；不验证内容学术真实性 |

暂缓优先展示：图表样本第 5 页存在明显重叠；86 页规划报告分页尚未确认且审核成本高；OmniDoc 页本身低清；简单 Keynote 和页码标识继续用于格式/边界，静态视频样本不代表动画真值。上述样本保留，缺口继续披露，不删除历史。

## 新来源与派生

先检查 Hugging Face Forceless/Zenodo10K 的公开索引和八个原始记录；检查到的八个记录仅提供 PPTX，不能提供现成的同稿 PDF 参考。没有批量下载这些文件。

另从 Zenodo 找到 Robert Haase 的 [Collaborative Working and Version Control with git[hub]](https://zenodo.org/records/14623257)，同一发布提供 PPTX 与 PDF，记录许可为 CC BY 4.0。下载约 42.7 MB，校验发布记录的 MD5，并保存 SHA-256、元数据快照、作者和许可。不能仅靠同名/同页数认定视觉真值。

原件均为 86 页。派生 PPTX 仅调整 presentation.xml 的幻灯片清单，选原页 2/11/16；未重绘页面，其余 ZIP 部件原字节保留（因此文件体积未大幅减少）。配套 PDF 提取同三页。LibreOffice 独立打开派生 PPTX 后得到 3 页；这只验证可打开及页数，不是产品渲染证据，也不是参考批准。

源文件为 benchmark/corpus/pptx_paired_collaboration.pptx，参考与完整来源链在 benchmark/references/paired-collaboration.pdf、paired-collaboration.json、paired-collaboration-upstream.json。重建脚本 benchmark/scripts/prepare_paired_candidate.py 在缺少原件时从记录下载，严格核对已冻结的 SHA-256。

## 同步修复

- 作者参考 PDF 显式绑定源 SHA、PDF SHA 和 provenance SHA；任一变化即拒绝静默复用。
- PPTX 结构扫描按 presentation.xml 活动页清单计数，不将保留但未列出的幻灯片或图表计入覆盖。
- 学术论文质量路线由 PDF→PDF passthrough 改成实际 PDF→image；本地/云端均有题。
- 新样本展开两条图片质量案例，所有新增或实质变化问题保持 draft。
- 优先队列绑定源与候选图 SHA；重新导出后旧精选标记失效。原 GT 批准和正式 READY 守卫保持不变。
- 批量按钮只作用于当前可见页；默认精选不会导致隐藏页被顺带确认。参数测试区默认折叠，优先展示图片。
- 图像预检去掉“画面正常”的暗示，只报告尺寸等基础观察。

111 项 Python 测试通过，新增测试覆盖精选失效、非批准语义、活动页计数、配套参考直读与篡改拒绝。JavaScript DOM 模拟检查覆盖默认页、前后翻页、可见页批量草稿、完整页切换和空搜索。Core 行为及两个 suite 校验通过。页面 HTTP 与脚本语法检查通过；浏览器自动化服务未能启动，本轮没有真实浏览器布局复核。

本轮未运行真实产品质量或云端验收。deck-benchmark/SKILL.md 要求 “Stop before the quality run until the user approves or edits the draft.” 当前 8 页是已准备的审核候选，不是已批准基准。剩余源的参考可靠性、完整 GT、字体和真实视频时序仍需继续补齐。
