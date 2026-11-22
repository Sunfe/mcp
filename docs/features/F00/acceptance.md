# F00 验收

- 最终结论：**工具阶段验收通过（PASS）**，2026-11-20，Chat1 A-01。独立 QA、R1/R2、冻结版本及父会话集成证据充分，未发现未解决的工具阻断缺陷。完整 F00 / M0 非 Done；约 20 GB 完整容量、真实标签及真实 holdout 为资料待就绪，剩余目标待确认。
- 范围版本：F00-scope-3（`feature.md`，2026-11-20）；纳入 R-01 及完整资料尚未整理的用户补充。
- 设计结论：D-01 批准 F00-design-1 的基线工具实现，须落实本文件 R1 / R2 两项明确补充；不必等待生产目标冻结或再次等待占位设计。
- 实现 / QA 版本：A-01 直接核对 `data/f00-qa/verified-versions.json` 的 14 份被测源码与 7 份 QA 源码、48 份原始证据及 17 份 QA / 集成报告的源码绑定，全部匹配当前文件；完整指纹及复核摘要见团队 `artifacts/chat1-final-tool-acceptance.md`。
- 验收人：F00 Chat1；已读取父会话最终集成记录及四份原始报告并核对版本。D-00 / D-01 / I-01 中的待 QA、未签通过为当时状态，当前以 A-01 为准。

## 已完成的只读核对

2026-11-20，在 `D:/repo/mcp` 阅读 README、项目方案、feature 模板、团队登记、现有生产源码及搜索 / MCP 测试。未改生产文件、索引、部署或用户原件。

| 检查 | 命令 / 方法 | 实际结果 | 结论边界 |
|---|---|---|---|
| 本地语料 | `find raw -type f ! -name .gitkeep`；`.venv/Scripts/python.exe` 使用 pathlib / fitz 只读统计 | 1 PDF，10,406,057 bytes，253 页 | 尚未测扫描比例 / 内嵌图片数；目录中无其他格式，不代表未来不存在 |
| 原件快照 | hashlib SHA-256；公开报告用匿名别名 `manual-1` | `ba2f84dff7483213799c6bc198ae1016f81a06073e30a3f58a817ba716f8def8` | 未复制原件或输出正文 |
| DB 元数据 | sqlite3 URI `Path("knowledge.db").resolve().as_uri()+"?mode=ro"`；只执行 count | 2,834,432 bytes；documents=1，chunks=324，FTS rows=324 | 未读取凭据；未断言这是运行服务使用的配置或正确索引版本 |
| 运行时 | `.venv/Scripts/python.exe` 的 `sys.version` | Python 3.11.9；命令 exit 0 | 不是新工具 / QA 测试通过 |
| 机器资源 | PowerShell `Get-CimInstance` 查询 CPU、OS 内存、D: 磁盘 | 各项报 `Access to a CIM resource was not available to the client.` | 不计通过；CPU / 内存 / 磁盘仍未知，可由 Chat2 用可用只读测量补充 |
| 现有搜索 | 阅读 `app/search.py` 与 `tests/test_search.py` | AND 字面查询；LIMIT；无 ORDER BY；测试覆盖参数标点与空查询 | 既有测试未在本次运行，不作为质量指标证据 |

## 已读源码指纹

以下为 Chat1 调研时的 SHA-256；它们是范围判断依据，不代替 Chat2 最终交付快照。共享目录有未提交改动可能，验收时须重新匹配实际版本。

| 路径 | SHA-256 |
|---|---|
| `app/search.py` | `0452830fb2c3b533daf4e783cb934eadde15f0f641a783730fb99f76656e7e48` |
| `app/db.py` | `4e50f31e89657a4dddf5279fc1e33d060381b80b2dcaa0ee3180a2d48a482799` |
| `app/parsers.py` | `60179ae239cd3c425379bd4df0615d5c5271a1dc71e8e78e9d547e6437b64adf` |
| `app/ingest.py` | `d4098b9e7bbb4f4703144d14ef200ac517bcecbc8afba49937b246a81c0bea3c` |
| `app/schemas.py` | `dc1690c7679456213f1edef32b42b3b7d1d7b61cef70e3a9c22644d4bfb24346` |
| `app/main.py` | `3a78a24128dc775e0170d64e58c5e6549e944724d0dc6208af7b4cc1aa42618a` |

## 设计评审记录

### D-00：设计尚未提交

- 被读版本：启动占位，内容为“待 Chat2 调研并填写，待 Chat1 评审。尚未批准实现”。
- 设计 SHA-256：`dad754911f21a496f5e64fc81d74d294a2cbbd3c12cc2f35b2e987f3e2070295`。随后通过 Windows FileSystemWatcher 有限等待 55 秒，无文件变更，命令 exit 0；本阶段以待设计交接，不制造设计通过。
- 决定：待设计，不作通过或退回判断。
- 接受所需材料：实际 CLI / 输入输出、只读 / 副本策略、质量标签与数据切分、指标算法、延迟 / 吞吐 / 内存测量边界、失败分类、运行成本范围、版本证据及 QA 场景。
- 可先进行：源码调研、非破坏性语料清单、设计与合成样例准备。实现前须有 Chat1 的具体设计决定。

### D-01：批准 F00-design-1 基线工具实现

- 评审日期：2026-11-20；对应范围 F00-scope-1 及 scope-2 的 R-01 需求澄清，工具实现范围未扩大。
- 被评设计：`design.md`，F00-design-1，124 行，SHA-256 `3b3d412b981d7586761bbd299d716f57ffa846ed386f3d95ed0b6e0bf7231fb4`。本记录替代 D-00 的待设计状态；D-00 保留为历史。
- 决定：批准 inventory / score / benchmark 的本地基线工具设计。Chat2 可立即在其所有权内实现，并将下列 R1 / R2 补充落实至自己的设计、实现与 QA 交接；这是具体实现约束，不是要求重新等待批准。若交付仍缺失补充，则相关验收退回。此批准不批准生产容量、性能或质量阈值，不代表实现、自测、QA 或 M0 已通过。

| 评审面 | 核对与理由 | 决定 |
|---|---|---|
| 指标数学 | 设计第 3 节固定 chunk 单位、稳定去重后截 K、逐题宏平均；partial / complete、真实 / 合成及 split 分列；0 分母 null；不强加 nDCG | 接受。保留现有返回顺序，不能将无 ORDER BY 解释成相关性排序 |
| 错误与无答案 | 有答案 error 留分母且计 0；无答案分成成功空 / 成功非空 / error 三项；unjudged 排除但报数量 | 接受。明确补充范围卡中的无答案 error rate，错误不得算正确拒答 |
| 生产源与副本 | 显式源路径、`mode=ro`、SQLite backup 一致副本、只读副本查询、无 init_db / ingest；不直接拷主文件漏 WAL | 接受。QA 必须在可控静止的测试源上验证不变及临时资源清理；外部并发修改不能归因为工具写入 |
| 快照身份 | benchmark 标签绑定备份产物 SHA-256，并核对相关 chunk 存在，优于源文件单次哈希 | 接受 benchmark 方向；离线 score 结果缺少相同绑定，须落实 R1 |
| 性能可解释性 | 原始逐请求时延、nearest-rank P95、成功吞吐含排队、请求时延不含排队、错误 / 预热分列；本地线程与 API/MCP 区分 | 接受。`request_timeout=not_enforced` 是明确限制，不伪称超时保障；首个正式样本按 R2 确定 |
| 内存 | tracemalloc 测量窗口 Python 分配峰值，与进程生命周期 PeakWorkingSetSize 分开；失败 null + reason | 接受，不将任何一种解释成系统总内存峰值 |
| 清单 / 资源 | PDF 文本稀少代理与图片引用口径、DOCX 不造页码、视频时长未实现明确未知；CIM 失败可用其他只读接口补充 | 接受探索范围。Chat2 新硬件数值属其调研记录，本次未独立复测，不计 AC-01 工具 / QA 通过 |
| 可实现性 / 版本 | 实际 `app.search` 在模块级使用 get_conn，限定评测进程临时替换可复用现有 SQL；本次只读核对 `.gitignore` 排除 data，并确认 Pydantic 2.9.2、typer 0.29.2、PyMuPDF 1.24.10、SQLite 3.45.1，命令 exit 0 | 接受无需新依赖的方向。替换仅限评测上下文，异常后恢复，每线程独立连接；这些是实现待验证项 |
| 独立 QA | 由 Chat2 创建，产品代码只读，单独报告及证据路径；冻结实现、文件哈希和失败复测历史 | 接受职责；当前 `qa-report.md` 仍 NOT RUN，不能代替实际执行 |

#### R1：离线 score 必须核对结果的快照与题集身份

设计第 2 节结果 JSONL 当前只有 query_id / 排名 / status；同名题号可来自其他库或已更改题文，单在最终报告记录两个文件的哈希不能检测这种错配。结果输入须携带并校验 corpus_id 与所用题集版本指纹，允许逐行字段或单独的版本化元数据封装，具体格式由 Chat2 落实。score 必须与实际被评题集比对，不符或缺失时非零退出；合成 fixtures 同样适用，不为其静默绕过。benchmark 输出的绑定须来自实际备份与被读取题集，不从待验证结果反向赋值。

QA 至少验证：正确绑定可评分；题号相同但 corpus 不同、题号相同但 query 文本 / 标签版本变化、绑定缺失，均拒绝。指纹可使用完整题集文件 SHA-256；若只绑定所选 split，须定义包含 query_id、题文、标签与 split 的确定性序列化及哈希。不得公开真实题文。

#### R2：并发重复的首个正式结果按提交序号定义

设计第 4 节的“每题首个正式测量结果”明确为固定请求序列中该题的首个正式提交序号，不能按线程最先完成的请求挑选。预热不进入质量样本，后续成功不能替换首个样本错误；所有重复仍参与性能 / 错误统计，排名稳定性另报。正式请求记录 query_id、重复序号 / 提交序号、status 与时延，使 QA 可重算并验证乱序完成不改变质量样本选择。

#### 保留缺口

真实五类题集、人工标签、留出题集未参与调优的记录及真实基线尚未具备；视频时长 / GPU 可保持明确未知；一本手册不能证明生产代表性。AC-02 至 AC-05 仍待实现和独立 QA，AC-06 继续因剩余目标 / 阈值与集成证据缺失而阻塞。父会话负责把 D-01 及 R1 / R2 传给 Chat2；本次不跨聊天发送消息。

### R-01：已确认需求及设计影响

直接用户确认已写入项目总台账 `docs/knowledge-platform-project.md` 的“需求确认 R-01（2026-11-20）”，本次已直接读取该记录。

| 已确认内容 | 本阶段采用口径 | 不得推导的结论 |
|---|---|---|
| 预计总量约 20G | 暂按约 20 GB 原始资料规划；GB / GiB 精度未确认 | 不能换算文件数 / 页数；不等于索引、备份和临时副本总预算；现有 10 MB 手册不能证明达标 |
| 日增量少，可忽略 | 低增量作为规划输入 | 不取消 F02 可靠更新、删除和恢复，也不新增分布式设施 |
| 暂定单人使用 | F00 默认串行探索基线仍合理，后续实测负载另记 | 单人不等于已确认请求并发 1、P95 或可用性目标 |
| 预留多人接口 | F01 主体 / 资料域契约，F06 调用上下文；真实权限隔离归 F10 | 预留字段不是身份验证或权限实现；F00 不增加多用户产品代码 |

影响决定：R-01 不推翻 D-01 的基线工具批准，不要求为未知 SLA / 质量目标重复等待。Chat2 应在自己的设计与报告中引用更新需求。实际格式构成、首版图片 / 视频、SLA / 质量阈值、预算及离线 / 恢复要求仍待确认；约 20 GB 容量验收须有对应规模与代表性证据，不能外推为通过。

## 验收证据账本

| 验收项 | 当前证据 | 判定 | 补齐条件 |
|---|---|---|---|
| AC-01 | 独立 QA 的清单边界与父会话真实手册 inventory 均通过，原始证据匹配 | PASS（工具） | 完整约 20 GB 容量资料待就绪 |
| AC-02 | 独立手算真值、多相关 / 去重 / 全错、无答案三项各 1/3、unjudged / 空分组 null | PASS（工具） | 真实五类 gold 与质量目标待就绪 |
| AC-03 | WAL CLI 22 次成功、原始时延重算、运行时 R2、只读拒写、正常 / 异常清理、全部错误统计 | PASS（工具） | 约 20 GB 压测资料及 SLA 目标待就绪 |
| AC-04 | R1 九项负输入、实际合成 holdout CLI、13 份 QA 加 4 份集成报告各 14 项源码绑定匹配 | PASS（工具） | 真实代表性及真实 holdout 资料待就绪；旧 demo-benchmark-r1 不用于最终验收 |
| AC-05 | Chat2 内 `/root/f00_independent_qa` 的 34 场景全部 PASS；14 份被测源码、7 份 QA 源码、48 份证据校验匹配 | PASS（工具） | 已满足本轮工具出口，无产品阻断缺陷 |
| AC-06 | A-01 正式签收；父会话 10 项既有回归、7 项工具自测及三个 CLI 集成通过 | PASS（工具）；完整 F00 / M0 未完成 | 完整容量 / 真实质量资料待就绪，SLA / 质量 / 预算 / 恢复及首版多媒体等目标待确认 |

## I-01：实现 / 文档提前复核（2026-11-20）

以下保留提前复核的实际历史；其中独立 QA、运行时 R2、实际 holdout CLI 与最终集成待补项已由 A-01 关闭，“当前暂不签通过”不再代表最终状态。

本次只读产品文件，不创建代理、不发跨聊天消息、不改 Chat2 / QA 文件。CLI 运行仅向 TemporaryDirectory 写本次报告，结束自动清理；真实库显式只读，在前后检查中 SHA-256 相同。未使用完整 20 GB 资料，未宣称生产验收。

### 发现与处置

1. **已消除的复跑文档问题**：初读 `design.md` 的第 6 节指向不存在的 `evaluation/fixtures/`。照抄 score 命令实际退出 2，`ERROR FileNotFoundError`，未生成输出。审查期间 Chat2 自行更新为 prepare_demo + `data/f00-demo-new/` 完整链路；最终只读版本 SHA-256 `9656031b7d17e95e914dec553b486148a0a3e80b588c90e1e0d1dc2a56bbf7f0` 已不含该断链。记录为 RESOLVED，不再作为未修缺陷。
2. **证据版本限制**：`data/f00-local/demo-benchmark-r1.json` 内 `evaluation/{__main__,benchmark,inventory,models,resources}.py` 共 5 项指纹与本次实现不同，旧产物不能作为当前最终验收证据。当前 inventory-v2 / good-v2 / bad-v2 / manual-unjudged-v2 的已记录源码指纹全部匹配。最终独立 QA 应提供本次冻结版本的基线和精确指纹，不用旧产物的 PASS 覆盖新实现。
3. **保留验证缺口**：现有 7 项自测中 R2 用乱序构造的 Request 保护最小提交序号，不是完整运行时并发乱序 / 首错后成的端到端证据；holdout 命名测试实际未执行 holdout CLI。独立 QA 应直接覆盖这两个已批准契约。本次未做代码修改或变异测试，不将阅读判断代作 QA 通过。当前提前检查未发现新的产品阻断缺陷，但不能以此证明未测路径无缺陷。

### R1 / R2 与副本核对

- R1：`models.py:98` 从同一份题集 bytes 解析并哈希；`:120` 对结果文件每行同时比对 corpus_id 和 query_set_sha256，再核对精确题号覆盖。benchmark 实际副本哈希必须等于题集 corpus，排名绑定来自该已验证题集。自测中的 corpus 变化、题文变化、标签变化、缺失绑定四种真实 score CLI 均退出 2。
- R2：`benchmark.py:75` 排序 submission_index 后逐题取首次；`:126` 构造固定 query 顺序 × repeats，再以枚举索引标记请求；所有重复留在性能统计中。Chat1 合成运行质量索引为 c=0、m=1、n=2、p=3、t=4，正式请求 10 个，0 error；预热不进入请求与质量记录。
- 副本：`database.py` 以 mode=ro + query_only 读源，backup 写临时副本；查询上下文替换实际 app.search.get_conn，连接逐请求创建，退出恢复。未运行 init_db / ingest。自测核对源哈希与连接恢复；本次真实库前后哈希相同，合成副本起止哈希相同。
- 文档 / 模块：inventory / score / benchmark 三入口、prepare_demo 与 README 实际存在；`--help` 可显示。基线 source 明示 function / not_API_or_MCP，未混称生产端到端。

### 已实际复跑

均使用 `.venv/Scripts/python.exe`，项目根 `D:/repo/mcp`。CLI 参数的输出在本次临时目录；输入来自 `data/f00-demo-r1/` 或明确的 raw / knowledge.db。

| 场景 | 实际结果 |
|---|---|
| `-m evaluation --help` | exit 0，列 inventory / score / benchmark |
| `-m unittest evaluation.test_f00_self -v` | 7 tests，OK，exit 0；6.308 秒 |
| score good / bad，dev，K=2 | 均 exit 0；4 个有答案题 Recall/MRR 分别 1 / 0；无答案成功空比例分别 1 / 0，假阳性 0 / 1 |
| benchmark 合成库，K=2，warmup=1，repeats=2，concurrency=2 | exit 0；10 正式请求、0 error，Recall/MRR=1，首样本索引确定，副本哈希起止相同 |
| inventory，root=raw，database=knowledge.db | exit 0；1 文件、10,406,057 bytes；生产源库前后哈希相同 |
| score，K=0 | exit 2，未生成报告 |
| 旧设计中不存在的 fixtures 输入 | exit 2，未生成报告；最终设计已修正 |

手册现有 `manual-unjudged-v2.json` 为 3 题 unjudged、90 成功请求、0 error：P95=1.5426 ms、吞吐=437.5978213463135 successful queries/s、Python allocated peak=299,364 bytes、进程生命周期工作集峰值=71,032,832 bytes。这是读取 Chat2 当前指纹一致产物得到的本机短测记录，非本次独立重跑该性能数字；Recall/MRR 与无答案指标全部 null。它不证明真实质量或约 20 GB 性能。父会话原 10 项回归已直接读取 `artifacts/parent-integration-check.md`：OK、exit 0，使用测试 DB 与 MockTransport，非真实客户端端到端。

### 本轮出口与资料就绪后的出口

本轮可以完成工具阶段验收，不因完整资料尚未整理而继续等待：独立 QA 报告交付后，Chat1 直接匹配其身份、冻结文件指纹、实际命令、失败 / 修复 / 复测和当前版本集成证据，再签工具结论。当前暂不签通过。完整容量清单、真实五类标签、真实 holdout、约 20 GB 实测统一列为“资料待就绪”，SLA / 质量等剩余目标另列待确认。约 20 GB、低增量、单人已知，不得重新标为全部未知。

## A-01：工具阶段正式验收（2026-11-20）

验收人 F00 Chat1；范围 F00-scope-3。结论 **PASS（工具阶段）**。直接读取独立 QA 报告、矩阵、原始 invocation / JSON、事件控制 harness 及父会话集成记录，并使用 `.venv/Scripts/python.exe -c` 只读重算 SHA-256、文件大小、报告绑定、P95 和吞吐。校验命令均 exit 0。本轮未重复运行已通过的完整测试，也未以阅读报告冒充本轮重跑测试。

| 复核面 | 实际核对结果 | 判定 |
|---|---|---|
| 独立性与矩阵 | QA 身份 `/root/f00_independent_qa`，由 Chat2 创建；34 个 surfaceEvidence 均 PASS；29 个适用 adversarialCases 均 PASS，浏览器 / HTTP 场景 1 项 not_applicable。实际场景引用均有效；该不适用项无证据引用符合其边界 | PASS |
| 版本与证据完整性 | `verified-versions.json` 中 14 份被测源码、7 份 QA 源码逐项匹配当前文件；48 份 artifactRefs 的 SHA-256 与 bytes 全部匹配；13 份 QA 加 4 份父会话报告各自 14 项 provenance 均与当前源码一致 | PASS |
| R1 | 九份 `r1-*-invocation.json` 均 exit 2；包括同 ID 修改题文、标签与未选 holdout，缺失 / 错配绑定、重复 / 漏 / 多余结果。完整题集字节绑定有效 | PASS |
| 实际 holdout CLI | `score-explicit-holdout-invocation.json` 明确 `--split holdout`、exit 0；输出仅 1 个合成题，Recall=1、MRR=0.5；题集和排名文件 SHA 与报告匹配 | PASS（工具选择） |
| R2 运行时 | 直接阅读事件控制 harness：后续真实 search 成功后释放首正式请求错误；完成序列 `[1,3,2,5,4]`，正式 submission_index=0 的 error 被保留，质量 Recall/MRR=0；后续 3 次成功计入性能，2 次预热中的 1 错单列 | PASS；关闭 I-01 缺口 |
| 性能与隔离 | 22 成功请求的原始时延第 21 位重算 P95=3.9762 ms；成功数 / 正式窗口=515.4349333683205 queries/s，与报告一致。WAL 65,952 bytes 的静止测试源前后不变；6 次真实快照连接拒写，正常 / 异常后恢复连接、清理快照并停止异常路径 tracemalloc；全错时 P95 null / 吞吐 0 | PASS（算法与边界） |
| 项目集成 | 父会话记录既有 10 项、自测 7 项均通过；prepare_demo、good / bad score、benchmark 25 成功请求、真实 inventory 均 exit 0；四份报告版本匹配 | PASS；并行运行的性能数值不作隔离 SLA 证据 |

冻结证据 SHA-256：

| 文件 | SHA-256 |
|---|---|
| `docs/features/F00/qa-report.md` | `b6224b3a1118777881703afff1f174da09a2b34983b0cf56328dff4012328360` |
| `data/f00-qa/f00-manual-qa.md` | `378c37c476a6cd9ceb3ebda7eeee33fe73d54cb995f5fee82514fdb2f4e20efc` |
| `data/f00-qa/manualQa.json` | `c36dcd91dfc855d1eedc0620f6025adf6eefde98fef02c56ef558db6da4484fa` |
| `data/f00-qa/verified-versions.json` | `dd7e634db0737c2c2ea5c1365f85eaf6d5db114db356d504200e10595e937b75` |

I-01 的两个行为验证缺口已关闭；旧 `demo-benchmark-r1.json` 继续排除，由以上当前 QA / 集成产物承担正式证据。QA 无产品缺陷、无产品修复后复测项；日志目录准备与证据路径标准化问题仅属 QA harness，历史保留在 QA 报告。basedpyright 未安装且此前拒绝安装，ruff 未运行，均未计为通过；本结论限定于实际 Python 3.11.9 / Windows 环境。

约 20 GB 原始资料、真实五类人工标签、真实 holdout 及规模压测为“资料待就绪”；质量阈值、P95/SLA、资源预算、恢复目标及首版图片 / 视频范围仍待确认。现有手册与合成题不能替代这些完整出口，本次不签完整 F00 / M0 Done。

## 下游影响与解除条件

F00 基线工具已由 Chat1 A-01 正式验收通过，可作为后续资料到位后的清单、评分与本地检索压测入口。父会话可据此登记工具阶段完成并安排后续设计；M0 完整出口仍待资料与剩余目标就绪，未经实测的容量、选型或性能不作承诺。

待确认 / 资料待就绪的内容和负责人见 `feature.md`。工具阶段无需继续等待或重复全量测试；产品源码若后续变化须重新核对版本并针对变化补测。完整资料、真实标签与目标就绪后再开启完整容量 / 真实质量验收，当前完整 F00 / M0 保持未完成。
