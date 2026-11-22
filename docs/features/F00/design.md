# F00 设计：容量清单与隔离评测

- 设计版本：F00-design-1 + D-01 R1/R2，2026-11-20，Chat2。
- 状态：Chat1 已通过 D-01 批准实现；本次补齐 R1/R2，无需再次等待批准。最终验收由 Chat1 决定。
- 对应范围：F00-scope-2，AC-01 至 AC-06。R-01 规划输入为约 20 GB 原始资料、低增量、单人首版；多人接口由 F01/F06 预留，真实授权隔离归 F10；本阶段不扩产品范围。
- 所有权：本文件、`evaluation/`、独立命名的自测；不修改 `app/`、部署、生产数据库、原件或 Chat1 的文件。

## 1. 已核对事实和容量边界

已读 README、项目方案、feature 模板、团队 guide / team.json、F00 feature / acceptance 及 `app/{search,db,parsers,ingest,config}.py`、`tests/test_search.py`。在项目树及上级检索未发现 AGENTS.md。Git Bash 中内置 rg 无法执行，文件发现退回 find；没有执行 Git 写操作。

现有查询是空白分词后逐词转义的 FTS5 AND；结果有 LIMIT，无 ORDER BY。评测必须保留实际返回顺序，不能把当前行为描述成相关性排序。文档/片段数字 ID 只在固定数据库快照内有意义。当前分块没有页码映射，因此不从 chunk_index 编造页码。

| 项目 | 已知值 / 来源 | 边界 |
|---|---|---|
| 本地原件 | Chat2 独立复核：1 PDF，10,406,057 bytes，253 页；文本稀少（非空白字符 <20）页 0；图片引用 79 次、涉及 33 页 | 全部页只读；代理比例 0 不是人工扫描判定；一本手册不是未来目标规模 |
| 本地 DB | Chat2 只读复核：2,834,432 bytes，1 document、324 chunks、324 FTS 行；PRAGMA quick_check=ok | 显式路径 `knowledge.db`；未声称是运行服务实际配置或原件内容正确 |
| Python | `.venv/Scripts/python.exe`，3.11.9，64 bit | 本次命令 exit 0 |
| CPU | Intel Core i7-10510U @ 1.80GHz；8 logical processors | 注册表 ProcessorNameString / Environment.ProcessorCount，只读命令 exit 0；不是保证可用核数 |
| OS | Microsoft Windows 10.0.26300 | RuntimeInformation.OSDescription |
| D: 磁盘 | 总 785,004,883,968 bytes；可用 460,979,740,672 bytes | DriveInfo 瞬时值，非存储性能；非部署服务器资源 |
| 已装工具 | fitz、pydantic、typer 可用；pytest、psutil、ruff、basedpyright 模块未发现 | 不为实现擅自安装依赖；既有项目以 unittest 运行测试 |
| 物理内存 | GlobalMemoryStatusEx 成功：总 34,133,594,112 bytes；瞬时可用 10,463,145,984 bytes | PowerShell Add-Type 调用 kernel32，只读，exit 0；瞬时可用值非资源承诺 |
| GPU | 未测，unknown | CIM 已被 Chat1 证实不可访问，不能把失败当 0 |
| 规划规模 / 增量 | R-01：约 20 GB 原件，日增量可忽略；用户确认完整资料尚未整理 | 不从现有一本手册外推容量验收 |
| 用户 / 业务并发 / 预算 / SLA | 首版单人；实际请求并发、预算、SLA 未冻结 | 多人接口由 F01/F06 预留，真实权限归 F10 |

原件匿名快照 manual-1 的 SHA-256 为 `ba2f84dff7483213799c6bc198ae1016f81a06073e30a3f58a817ba716f8def8`；读取前后 size/mtime_ns 相同；未加密。非空白提取字符合计 169,674；独立图片文件 0、视频文件 0。没有复制原件、保存正文或把提取文本当质量真值。

只读调研曾有一次 sqlite3 URI 打开失败：调用遗漏 `uri=True`，exit 1；补齐后 `sqlite3.connect(path.as_uri()+"?mode=ro", uri=True)` 完整执行，exit 0。这是调研调用错误，保留在交接证据中，不计工具测试失败或 QA 通过。此段为设计初期调查；后续实现状态见第 9 节。真实标签仍未创建。

## 2. 交付入口与输入输出

使用现有 `.venv/Scripts/python.exe -m evaluation --help`。CLI 采用已安装 typer，输入边界采用现有 Pydantic v2；不新增运行时依赖。实际模块为 __main__、models、metrics、inventory、database、benchmark、resources、artifacts；prepare_demo 仅生成原创合成样例。入口与字段由以下契约落实，实际复跑见 `evaluation/README.md`。

| 命令 | 显式输入 | 输出 |
|---|---|---|
| `inventory --root raw --database knowledge.db --output data/f00-local/inventory.json` | 原件根目录、可选 DB；不读 `.env` 取得路径 | 匿名文件 ID、扩展名、bytes、SHA-256、页数、文本稀少页代理数、图片引用次数、格式/失败状态；数据库计数与一致快照哈希；硬件、依赖与源文件指纹 |
| `score --queries evaluation/fixtures/queries.jsonl --results evaluation/fixtures/good.jsonl --k 5 --output data/f00-local/good.json` | 人工标签 JSONL、已有排序 JSONL、K、明确 split | 逐题、分组、总指标；分母、排除项与失败原因；输入及实现 SHA-256 |
| `benchmark --database <副本或显式源路径> --queries <JSONL> --split dev --k 5 --warmup 5 --repeats 10 --concurrency 1 --output data/f00-local/run.json` | 数据库、题集、负载参数；DB 路径无默认值 | 固定 DB 副本上的实际 search_documents 结果 ID、逐请求 ms / 错误、汇总质量、P95 / 吞吐 / 内存、执行环境与哈希 |

所有输出路径显式指定；输出已存在时拒绝覆盖，输入输出同路径拒绝。输出父目录须存在或只在指定输出父目录内创建。根目录缺失/不是目录、DB 缺失、输入损坏、K/负载非法是 CLI 错误，非零退出。业务标签和 query 文本不默认回显，异常只报告错误类别/安全错误码，不打印 SQL、正文、配置对象或绝对原件路径。输出模型拒绝 NaN/Inf，`provenance.schema_version` 标识版本。

### 题集 JSONL（每行一个对象）

字段：`query_id`（唯一非空字符串）、`query`（非空字符串）、`category`（parameter / chinese / table / similar_model / no_answer）、`split`（dev / holdout）、`origin`（synthetic / real）、`corpus_id`（语料快照标识）、`answerable`（bool 或 null）、`relevant_chunk_ids`（去重正整数数组）、`label_status`（complete / partial / unjudged）。

`answerable=true` 必须有相关 ID；false 必须空集合且 complete；null 只可 unjudged 且不计质量。partial 的召回明确命名“受限标签召回”。单位固定 chunk，不混入 document ID。页/章节等人工定位可放在本地标注说明文件，不由本阶段工具推造。所有题属于同一 corpus_id；benchmark corpus_id 为所用 DB 快照 SHA-256，显式不符时报错，避免不同版本数字 ID 错配。

结果 JSONL：`query_id`、`corpus_id`、`query_set_sha256`、`ranked_chunk_ids`（正整数数组）、`status`（ok / error）、可选 `error_kind`。R1：每行均必须绑定实际完整题集原始 UTF-8 文件 bytes 的 SHA-256 和语料快照 SHA-256；score 对照读入的完整题集指纹与 corpus_id，缺失或错配非零退出，合成 fixtures 也不绕过。所选 split 必须一题一结果，不接受未知题、漏题或重复题；error 不能携带成功排名。重复命中按首次出现保留，再取前 K，防止重复片段灌高指标。未知 chunk ID 可以作为不相关结果参与 score，但 benchmark 会核对标签中的相关 ID 是否实际存在。

合成 fixtures 完全原创，不复制用户手册；包含多相关项、乱序、重复、零命中和无答案。真实标签保存在 `data/f00-local/`（既有 .gitignore 排除 `/data/**`），不进入版本化目录。五类真实覆盖分别报告数量、来源、有效标签数、dev/holdout 数，不用合成题填补真实覆盖。

## 3. 指标算法与分母

- 默认 K=5。先对 ranked_chunk_ids 稳定去重，再取 K。每题 Recall@K = 命中的不同相关 chunk 数 / 全部已标相关 chunk 数；MRR@K = 首个相关项名次倒数，未命中为 0。按题宏平均，并分别给类别、split、origin、label_status；partial 与 complete 不混称全库召回。
- error 的有答案题保留在质量分母内，Recall/MRR 计 0，并单列错误数；不以删除失败请求美化质量。unjudged 不参与质量，并明确数量。
- 已确认无答案题不进 Recall/MRR。empty-result rate = 成功且空结果数 / 全部已确认无答案题数；false-positive rate = 成功且非空结果数 / 全部已确认无答案题数；另列无答案 error rate，三者合计 1。错误不能当正确拒答。它们仅评价检索，非生成幻觉率。
- 没有适用题时该指标 null，给出 `no_eligible_queries`；不输出假 0/100%。空题集报输入错误；过滤后无该 split 也报错。
- 不实现 nDCG，本阶段使用 MRR。K、去重规则、分母、标签完整性和错误处理写入输出版本，后续改算法必须升级 schema/version。

手算对照：相关 {1,2}，K=2；好结果 [1,2] 为 Recall=1、MRR=1；坏结果 [9,1] 为 Recall=0.5、MRR=0.5；全错 [9,8] 均为 0；重复 [1,1,2] 去重后同好结果。无答案空、非空、error 各自按独立三分项报告。QA 使用独立构造的数字和边界验证，不能只复制此算例。

## 4. 检索、压测和内存边界

benchmark 不调用 init_db / run_ingest。源 DB 以 SQLite URI `mode=ro` 连接，在临时目录使用 SQLite backup API 建立一致副本；之后所有查询仅访问副本，临时目录随运行清理。快照哈希、documents/chunks/FTS 行数、完整性检查和开始/结束状态写入结果。不能仅复制主 DB 忽略 WAL。源库即使只读也可能被外部更新，因此版本绑定到备份产物，不将源文件运行前单次哈希当一致快照。

适配器直接调用现有 `app.search.search_documents`，在评测进程中限定其已有 get_conn 入口为副本的只读连接；不修改生产源码或调用 API。导入生产模块可能触发其现有配置加载，但不打印任何配置/凭据，不依赖其中的 DB_PATH。补丁只在评测上下文有效；并发线程每次建独立只读连接。返回值只留 chunk_id，不把正文保存到公共产物。

输入序列按 query_id 固定顺序循环 repeats 次；warmup 为正式测量前的请求数，不计正式样本。R2：每请求记录 submission_index、repeat_index、query_id，质量只取该题最小正式 submission_index 的结果，与线程完成顺序无关；后续成功不替换首个 error。所有重复仍计性能/错误，另报告每题各重复的排名是否一致。默认 concurrency=1；较大并发明确为本地线程并发，不等价 API/MCP、多用户或跨机能力。明确记录 Python/SQLite/GIL、K 和无 ORDER BY 的排序局限；不做生产调优。

每请求用 perf_counter_ns 从实际调用前至返回/异常结束计时；ms 原始值保留。P95 为成功样本升序第 ceil(0.95N) 个（nearest-rank）；0 成功则 null。错误延迟另外保存。无超时机制不伪称 timeout=0：字段 `request_timeout=not_enforced`。CLI 单次总耗时不是请求时延；当前本地同步调用不能硬取消卡住的线程，因此用户可用外部进程超时终止，已中断运行不作为完整基线。

吞吐 = 成功请求数 / 正式测量窗口墙钟秒数；窗口从提交首个测量任务前到所有测量任务完成后，包含线程排队/调度。请求时延不含池内排队，两种边界分别声明。总请求数、成功/错误数、错误率、warmup 错误数和窗口秒数均保留，失败不静默丢弃。

内存：tracemalloc 从正式测量前启动，报告测量窗口 Python allocated peak bytes；它不包含 SQLite / fitz 原生内存。Windows 通过 GetProcessMemoryInfo 读 process PeakWorkingSetSize，明确为当前评测进程自启动以来 OS 工作集峰值，包含导入、备份、预热，非测量窗口增量；不使用采样，不宣称整个系统或子进程 RSS。不能获得则 null + reason。当前其他系统进程峰值尚未实现，输出 null + platform_not_implemented；不借 Python 分配值替代进程峰值。

## 5. 清单测量口径和失败分类

只扫描显式 root，跳过 .gitkeep，不跟随目录/文件符号链接或 Windows reparse point，输出跳过计数。按排序后的相对路径给匿名 file-0001 等 ID，公共输出不含路径/文件名。hash 读取二进制流，记录检查前后 size/mtime；变化时标 unstable，不计作稳定版本。单文件不可读/解析失败保留记录与错误类别，整体报告 partial，不能显示 complete。可读损坏格式保留 bytes/hash；无法 stat 的 bytes=null，unknown_size_file_count 单列；total_bytes 只表示已知大小之和，不把未知当 0。

- PDF：fitz 只读、上下文管理。真实页数；每页非空白文本字符数小于 20 的页数作为 `text_sparse_pages` / 总页数，明确是扫描候选代理，不能称人工确认扫描比例。图片为各页 get_images(full=True) 的引用次数，可能重复引用/未使用，不等于独立照片数。
- DOCX：zip / XML 只读统计段落、表格及 word/media 条目；页数 null（无可靠渲染分页）。TXT 统计 bytes 与可解码状态；DOC 不调用 antiword 来执行未知外部程序，统计容量，结构未知。
- 图片：按扩展名计文件数；内嵌图片与独立图片分列。视频：按扩展名计文件数；本阶段不带入转码/转写依赖，duration_hours=null + `duration_probe_not_implemented`，无视频时 observed_video_files=0，不能推断未来无视频需求。
- 不支持格式、损坏、加密、权限失败和不稳定文件都有明确状态。空目录是成功的 0 文件清单，指标分母为 0 的比率 null；目录不可访问是错误。
- 系统资源使用只读 OS 接口；物理内存可用 GlobalMemoryStatusEx；GPU 不能稳定读取则 unknown。不采集用户名、机器名、IP、环境变量或凭据。日增量、未来量和预算标 unknown，不从本地快照推导。

## 6. 版本、保护、成本和复跑

每个产物包含 UTC 采集时间、schema / tool version、Python/平台/依赖版本、显式非敏感参数、输入 SHA-256、`app/search.py` / `db.py` / `config.py` 和 evaluation 源文件 SHA-256。共享目录未提交状态不以单一 commit 代表；文件指纹是被测版本，QA 交接前冻结自己实现文件并重新核对。源码版本读取不执行 Git 操作，不输出 `.env`、原件正文或秘密。

清单为 O(全部文件 bytes + PDF 页数) 的本地只读工作；score 为 O(题数 × 排名长度)；benchmark 要求临时磁盘至少一份 DB 副本及 SQLite 开销，内存含当前查询结果。默认不发网络请求，不下载模型，不付费。大文件/大库需要实际预算后再压测；一本手册不支持容量预测。

复跑示例（每次使用新的输出名；完整实际入口见 evaluation/README.md）：

```powershell
.venv/Scripts/python.exe -m evaluation --help
.venv/Scripts/python.exe -m evaluation inventory --root raw --database knowledge.db --output data/f00-local/inventory.json
.venv/Scripts/python.exe -m evaluation.prepare_demo --output-directory data/f00-demo-new
.venv/Scripts/python.exe -m evaluation score --queries data/f00-demo-new/queries.jsonl --results data/f00-demo-new/good.jsonl --k 5 --split dev --output data/f00-local/good-new.json
.venv/Scripts/python.exe -m evaluation score --queries data/f00-demo-new/queries.jsonl --results data/f00-demo-new/bad.jsonl --k 5 --split dev --output data/f00-local/bad-new.json
.venv/Scripts/python.exe -m evaluation benchmark --database data/f00-demo-new/demo.db --queries data/f00-demo-new/queries.jsonl --split dev --k 5 --warmup 5 --repeats 10 --concurrency 1 --output data/f00-local/baseline-new.json
```

demo.db 和其题集由 prepare_demo 生成；真实题集由人工标注和冻结，不能从检索当前命中反推真值。首次真实基线若无标签，仅清单与结构/性能探索可做，真实质量明确 NOT RUN。默认不运行 holdout；验收冻结后由 QA 显式 `--split holdout`，记录未参与调参（本阶段不调优）。合成 holdout 仅演示分组入口，不是独立真实留出验证。

新增文件无迁移。回滚是停用新增命令；只清理本次确知的评测输出/临时目录，绝不批量清理 data、raw 或用户备份。没有生产配置变化。

## 7. 自测与独立 QA 交接

自测保护的独立行为是指标数学、输入拒绝、清单失败/未知口径和真实 search 函数副本隔离；现有 tests 只覆盖搜索/MCP，不含这些契约。先从现有测试风格扩展独立命名文件，不为了测试修改生产接口。好/坏结果必须区分，零分母/无答案/重复须独立可手算；错误输入必须经 CLI 观察非零退出。测试使用 TemporaryDirectory 与合成内容，不改用户资料。

实现自测后，在本 Chat2 通过 spawn_agent 创建独立 QA。QA 产品源码只读，只拥有 `docs/features/F00/qa-report.md`、`evaluation/qa/` 与 `data/f00-qa/`；Chat2 实现和自测文件在 QA 时冻结。交付给 QA：本设计和完整 AC-01..06 矩阵、实际命令/退出码、实现/DB/题集哈希、机器环境、好坏对照和已知缺口。QA 自选算例和故障输入，不能把 Chat2 自报当通过；缺陷由 Chat2 修复后 QA 复测并保留历史。

| 验收项 | 设计落实 | QA 重点 / 不能替代的缺口 |
|---|---|---|
| AC-01 | inventory、真实手册只读复核、资源 unknown 原因 | 空/缺失/损坏/不支持；代理扫描率与真实扫描区别；视频时长未实现明确 PARTIAL |
| AC-02 | score、固定 chunk 单位、宏平均、去重、错误和 null | CLI 手算好坏、多相关、重复、无答案、空分组、错配/漏题拒绝 |
| AC-03 | benchmark、原始计数/时延、明确窗口、两种峰值 | 本地串行与线程并发；源 DB 前后不变；P95 从原始样本重算；错误分开 |
| AC-04 | SHA-256、真实/合成分列、显式 split、原件不版本化 | 数据/代码变化能识别；真实题量和五类覆盖不足不伪造；holdout 未调参 |
| AC-05 | 本 Chat2 独立 QA 与隔离写路径 | QA 真命令、身份、版本及 FAIL / 修复 / 复测留存 |
| AC-06 | 仅工具/探索基线交付 | 工具实现与独立 QA 已交付，待 Chat1 工具验收；完整资料与剩余目标待就绪，Chat2 不签最终验收 |

## 8. 实现决定与保留缺口

Chat1 D-01 已批准本设计及 R1/R2 的具体约束，立即实现并自测、委派本 Chat2 内独立 QA。工具正确性、真实基线、生产代表性及 M0 目标冻结分别判定；约 20 GB 代表性数据、五类真实人工标签、质量/SLA/恢复阈值仍缺失，不阻止工具实现与 QA，也不将当前一本手册基线外推为通过。

## 9. 实现与基线交付记录

2026-11-20：三个入口及合成样例生成器已实现。自测 `.venv/Scripts/python.exe -m unittest evaluation.test_f00_self -v` 共 7 项通过，raw log 在 `data/f00-local/selftest-v2.log`；Python safety 审计 11 文件无违规，compileall exit 0。LSP 明确 basedpyright 未安装且用户之前拒绝安装；ruff 未发现，不宣称二者通过。

真实清单 `data/f00-local/inventory-v2.json`：1 PDF、10,406,057 bytes、253 页，79 图片引用分布于 33 页，文本稀少页 0，DB 快照 1 文档/324 片段，quick_check=ok。独立原件仍未复制或版本化。

`data/f00-local/manual-unjudged-v2.json` 为三个人工选择、无标注的合成探针在现有真实 DB 副本上的性能探索：K=5、warmup=5、repeats=30、concurrency=1，90 请求成功、0 错误，P95=1.5426 ms，吞吐=437.5978 successful queries/s；Python allocated peak=299,364 bytes，进程生命周期 PeakWorkingSetSize=71,032,832 bytes。这只是一次本机短负载观测；题目均 unjudged，Recall/MRR/no-answer 指标全部 null，未从命中反推标签。完整 20 GB 尚未准备好，不进行猜测目录扫描或容量外推。

本 Chat2 通过 spawn_agent 创建的独立 QA `/root/f00_independent_qa` 已交付 qa-report.md：工具阶段 PASS，34 个实际场景，无产品缺陷或产品补丁。R1 完整题集绑定、实际 holdout CLI、R2 事件控制的运行时乱序首错后成、WAL 隔离和异常清理均有原始证据。14 个产品/既有自测源码初末一致，13 个成功报告 provenance 与源码匹配；Chat2 交接前再次核对当前 14 个源码及 48 个证据引用，均无指纹变化。完整矩阵见 data/f00-qa/f00-manual-qa.md，精确版本见 verified-versions.json。源码保持冻结，Chat2 不代签 Chat1 验收；完整约 20 GB、真实标签/留出集和剩余目标仍待就绪。实现命令、最终报告哈希及项目层 CLI 集成记录另交团队 artifacts/chat2-implementation-handoff.md。
