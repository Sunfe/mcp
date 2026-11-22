# F00 独立 QA 报告

2026-11-20，执行身份 `/root/f00_independent_qa`，由 Chat2 创建的独立 QA 子会话。工作目录 `D:/repo/mcp`；Python 3.11.9、Windows 10.0.26300、SQLite 3.45.1、PyMuPDF 1.24.10、Pydantic 2.9.2、Typer 0.29.2。环境原始记录见 `data/f00-qa/attempt-1/environment.json` 和各报告 provenance。

**工具阶段结论：PASS。** 本次独立执行 34 个矩阵场景，未发现需产品修复的缺陷。结论覆盖新增 inventory / score / benchmark 的已批准工具契约、R1/R2、隔离与错误边界；不代表完整 F00 或真实业务验收通过。完整矩阵含场景、精确命令、预期、结果及 48 个非空证据引用：`data/f00-qa/f00-manual-qa.md`；机器可读版：`data/f00-qa/manualQa.json`。

## 方法与边界

本报告直接读取并运行产品代码，对照 feature、acceptance、design 和 README。自行构造评分真值、SQLite WAL 数据库、PDF/DOCX/其他文件；未复用实现者的好坏答案作为独立数学依据。真实检索调用现有 `app.search.search_documents`。故障注入只在 QA 进程既有 Python 边界发生，不修改产品源码或新增产品测试接口。

写入仅限 `evaluation/qa/`、`data/f00-qa/` 和本报告。没有读取或输出 `.env`/凭据，没有改生产数据库、原件、排序、索引或配置，没有 commit/push。约 20 GB 原件尚未整理；既有真实手册报告只做元数据与算术复核，没有重新复制或扫描原件。

`omo-agent-toolkit ulw-loop status --json` 返回 127（命令不存在），且调用方未提供 ulw-loop 计划，故使用调用方指定 `data/f00-qa/`。CLI 行为使用真实子进程、完整 argv、cwd、exit、stdout/stderr 与 JSON 报告；不存在 UI/HTTP 改动，浏览器与 HTTP 场景 not_applicable。

## 实际执行结果

| 验收引用 | 独立场景与观察 | 结论及关键证据 |
|---|---|---|
| AC-01 | 9 个混合文件；损坏非空 PDF/DOCX、零字节 PDF、非法 UTF-8、未知格式；容量按已知大小求和，失败文件保留 hash/bytes；空目录 complete，缺失目录退出 2 | PASS：`attempt-1/inventory-mixed.json`、`inventory-oracle.json`、`inventory-empty.json`、`inventory-missing-invocation.json` |
| AC-01 | 合成两页 PDF，1 页 sparse，比例 0.5；DOCX 两段落、1 表格、1 media，页数 null；视频时长 null、GPU unknown；共享图片逐页引用次数 2 | PASS：`attempt-1/inventory-mixed.json`、`edges-1/inventory-edge.json` |
| AC-01 | Windows CreateFileW 独占读锁使 CLI 真正遇到 PermissionError；保留 24 bytes，hash null；另外定点 stat 故障使 unknown_size=1、bytes null | PASS：`attempt-1/inventory-os-locked.json`、`inventory-stat-fault.json` |
| AC-01 | AES256 加密 PDF 保留 bytes/hash 且 encrypted；真实 Windows junction 跳过；读取间修改文件标 unstable 且清除 hash；拒绝覆盖既有报告且原报告 hash 不变 | PASS：`edges-1/inventory-edge.json`、`inventory-unstable.json`、`overwrite-invocation.json`、`junction-creation.json` |
| AC-02 | 相关集 {11,13,17} 与排名 [97,11,11,13,17] 在 K=3 下先去重；与单相关全中、首样本 error 联合宏平均，独立手算 Recall=5/9、MRR=1/2。全错对照为 0 | PASS：`attempt-1/score-hand-oracle.json`、`score-oracle.json`、`score-all-miss.json` |
| AC-02 | 无答案成功空、成功非空、error 各 1/3，错误不伪装拒答；未判题不进质量，空类别和全部 unjudged 输出 null；空题集、K=0、空 split 拒绝 | PASS：`attempt-1/score-oracle.json`、`edges-1/score-unjudged.json` 及对应 invocation |
| R1 / AC-04 | 正确绑定成功；语料/hash 错配、缺 binding、重复/漏/额外结果、同 ID 改题文/标签/未选 holdout 题文均退出 2 且未产生报告 | PASS：`attempt-1/r1-*-invocation.json`；九个失败路径均是预期拒绝 |
| AC-04 holdout | 真正调用 `score --split holdout`，只评 1 个合成 holdout，Recall=1、MRR=0.5；无该 split 时退出 2。没有真实 holdout 标签，不宣称真实 holdout 合格 | PASS（工具选择）：`attempt-1/score-explicit-holdout-invocation.json`、`score-explicit-holdout.json`；`edges-1/score-empty-split-invocation.json` |
| AC-03 | 独立 SQLite WAL 源库含 2 个 chunk，未 checkpoint WAL 65,952 bytes；CLI 预热3、重复11、并发2，正式22次均成功，质量1；主库/WAL哈希前后相同 | PASS：`benchmark-1/benchmark-concurrent.json`、`benchmark-independent-oracle.json` |
| AC-03 | 从22条原始时延独立取第21条：P95=3.9762 ms；22/正式窗口=515.4349333683205 queries/s；Python分配峰值与 Windows 进程生命周期工作集峰值分别输出 | PASS（算法/口径）：同上。数值仅这次微型合成运行，不是容量或 SLA 证明 |
| R2 | 单题 warmup=2、repeats=4、concurrency=2；事件控制使调用3成功先于调用2失败完成。调用2是首正式 submission_index=0，质量保留 error 和0分；后续3次成功仍计性能；预热1错独立统计 | PASS：`benchmark-1/benchmark-r2-control.json`、`benchmark-r2-concurrency.json` |
| AC-03 | 六次在真实快照连接上尝试写入均被 SQLite 拒绝；正常与 RuntimeError 退出后 get_conn 恢复，snapshot 文件消失；异常后 tracemalloc 停止；源库哈希不变。全部请求错误时 P95 null、吞吐0；错 corpus/缺相关 chunk 拒绝 | PASS：`benchmark-1/benchmark-r2-control.json`、`benchmark-exception-cleanup.json`、`benchmark-all-errors.json` 及对应 invocation |
| AC-04 / AC-05 | 初末14个产品/既有自测源码哈希一致；13个原始成功报告的 provenance 逐项与实际源码比对相同；完整题集原字节绑定及 synthetic 来源保留 | PASS：`data/f00-qa/verified-versions.json`、`attempt-1/source-manifest-start.json`、`source-manifest-end.json` |

表内子路径相对 `data/f00-qa/`；矩阵中每项列出完整路径和 SHA-256。`benchmark-r2-control.json` 记录实际完成序列 `[1,3,2,5,4]`，因此不是仅构造 Request 元组或检查 helper 的替代证明。预热调用0的错误在专用 warmup_errors 中，未进入正式质量样本。

## 复跑入口与原始日志

使用未存在的运行目录名；以下为本次真实执行命令，当前证据目录已存在，原样重跑会被 QA harness 拒绝覆盖。需要复跑时将末尾目录名改为新的编号。

```powershell
.venv/Scripts/python.exe -m evaluation.qa.run_manual attempt-1
.venv/Scripts/python.exe -m evaluation.qa.benchmark_scenarios benchmark-1
.venv/Scripts/python.exe -m evaluation.qa.edge_scenarios edges-1
.venv/Scripts/python.exe -m evaluation.qa.finalize_evidence
```

前三项退出 0，原始日志分别是 `data/f00-qa/run-attempt-1.log`、`run-benchmark-1.log`、`run-edges-1.log`。每个真实 CLI 在执行前打印 surface 和完整命令；对应 `*-invocation.json` 保留退出码与输出。holdout 完整命令为：

```powershell
D:\repo\mcp\.venv\Scripts\python.exe -m evaluation score --queries D:\repo\mcp\data\f00-qa\attempt-1\qa-queries.jsonl --results D:\repo\mcp\data\f00-qa\attempt-1\held-rank.jsonl --split holdout --output D:\repo\mcp\data\f00-qa\attempt-1\score-explicit-holdout.json
```

## 缺陷与尝试历史

无产品缺陷、无产品补丁、无产品修复后复测项。三个场景运行批次均首轮通过。保留的 harness/执行准备问题不算产品失败：首次日志重定向时 `data/f00-qa` 尚不存在，shell 退出1，尚未运行产品；创建指定证据目录后正式运行成功。最终证据汇总第一次因 Windows 反斜杠与 provenance 正斜杠的键格式不同而失败，见 `data/f00-qa/finalize.log`；只将 QA 汇总的路径键标准化，再次成功，见 `finalize-v2.log`。产品源码初末一致。

QA 源码不执行破坏产品文件的 mutation 测试；用户给 QA 的权限为产品源码只读。数学好/坏对照、R1 负输入、真实文件锁、实际写入拒绝、事件乱序和错误/清理场景提供行为上的区分能力。编写期间 basedpyright 不存在，LSP 提示用户此前已拒绝安装，故未安装、未声称静态类型检查通过；本次也未运行 ruff。测试结果限定为实际运行的 Python/Windows 环境。

关键冻结指纹（完整14项见 verified-versions.json）：

| 文件 | 初始 = 最终 SHA-256 |
|---|---|
| evaluation/benchmark.py | a3fd5f67016ba79ad1f6856acf2984a8c15afaad9ff9b9608b71f7acfd4bda73 |
| evaluation/inventory.py | 06e02423ce60770b3e2859cba203952237b8d06e1b20f988e57af98d38ab0855 |
| evaluation/models.py | 7277b5fc1440a4d11c7b5129d94535fd19d8f7a7c01ee7686f87f32040b58dbf |
| app/search.py | 0452830fb2c3b533daf4e783cb934eadde15f0f641a783730fb99f76656e7e48 |

## 真实资料与最终验收状态

既有 `inventory-v2.json`（SHA256 `6a5449de2c6b3c5d3e9f8f172b45c46c3e02ae7f37fb47307716303e8c2861c7`）读到 1 个文件、10,406,057 bytes、253页。既有 `manual-unjudged-v2.json`（SHA256 `c2b81f66a979847cba9465c9a6552ff0e83ece665279d6287f96f889cdef38d0`）90条成功时延重算 P95=1.5426 ms、吞吐437.5978213463135/s，3个 unjudged 探针质量 null。该项仅证明现有产物内部一致；不把实现者报告替代本次原件复测，证据见 `edges-1/existing-artifacts-audit.json`。

| 后续条件 | 当前状态 / 缺失前提 |
|---|---|
| 完整约20 GB代表性容量与性能 | NOT RUN：用户确认原件尚未整理；一本手册和微型合成库不可外推 |
| 五类真实人工相关性标签和独立真实holdout | NOT RUN：缺人工冻结 gold；合成 holdout CLI 通过只证明工具行为 |
| 真实质量阈值、P95/SLA、预算与恢复目标 | NOT RUN：目标未冻结，不能判断达标 |
| 最终项目集成与 M0/F00 完成签署 | 本子会话不签最终完成；由 Chat1/父会话结合项目集成证据验收 |

这些是后续业务验收前提，不将已完成工具 QA 标为失败或将整体 F00 标为 Done。
