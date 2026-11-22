# F00 本地评测工具

完整入库流程及 Linux、MSYS2 / Git Bash、WSL 的解释器选择见根目录 [操作说明](../操作说明.md)。F00 最低要求 Python 3.11；本轮工具阶段已由 Chat1 验收通过，证据见 [验收记录](../docs/features/F00/acceptance.md)。该结论不包含 Linux / WSL 原生验收或完整约 20 GB 业务验收。

仅运行新增评测入口，不改生产索引/排序/解析。依赖使用项目已有 `.venv`；不需要下载模型或新增运行时包。业务约 20 GB 原件尚未整理，本轮只能验证工具和现有手册基线，不能证明 20 GB 性能。

## 直接复跑

在项目根目录 PowerShell / Git Bash 运行。每次使用新的输出文件名；已存在路径一律拒绝覆盖。

```powershell
.venv/Scripts/python.exe -m evaluation --help
.venv/Scripts/python.exe -m evaluation.prepare_demo --output-directory data/f00-demo-new
.venv/Scripts/python.exe -m evaluation score --queries data/f00-demo-new/queries.jsonl --results data/f00-demo-new/good.jsonl --split dev --k 2 --output data/f00-local/good-new.json
.venv/Scripts/python.exe -m evaluation score --queries data/f00-demo-new/queries.jsonl --results data/f00-demo-new/bad.jsonl --split dev --k 2 --output data/f00-local/bad-new.json
.venv/Scripts/python.exe -m evaluation benchmark --database data/f00-demo-new/demo.db --queries data/f00-demo-new/queries.jsonl --split dev --k 2 --warmup 5 --repeats 10 --concurrency 1 --output data/f00-local/demo-new.json
.venv/Scripts/python.exe -m evaluation inventory --root raw --database knowledge.db --output data/f00-local/inventory-new.json
.venv/Scripts/python.exe -m unittest evaluation.test_f00_self -v
```

prepare_demo 只向尚不存在的指定目录写原创合成数据库及题集，好/坏结果可独立评分：好结果四个有答案题 Recall/MRR 均为 1，无答案为空；坏结果四题均为 0，无答案为非空。合成示例有五类 dev 题及一个 holdout，不能计作真实五类覆盖。该辅助入口不能用于生产重建。

## 输入与版本绑定

每题为一行 UTF-8 JSON：`query_id`, `query`, `category`, `split`, `origin`, `corpus_id`, `answerable`, `relevant_chunk_ids`, `label_status`。类别是 parameter/chinese/table/similar_model/no_answer；split 是 dev/holdout；origin 是 synthetic/real。相关单位固定为 chunk。`answerable=true` 需非空相关 ID；false 需 complete 空集合；未知为 null、unjudged、空集合。原始完整题集文件的 SHA-256 是版本，连未选 split、题文与标签一起绑定。字段定义和取值验证见 `models.py`。

排名 JSONL 每行是 `query_id`, `corpus_id`, `query_set_sha256`, `ranked_chunk_ids`, `status`, `error_kind`。必须精确覆盖选定 split，一题一结果；其他 split 的结果不混入。R1：语料/题集指纹缺失或错配均报错，不能仅凭相同题号评分。score 输出的结果哈希来自同一份已解析字节，避免二次读文件改变证据。

benchmark 的 corpus_id 必须匹配实际 SQLite backup 产物 SHA-256。可先用 inventory 得到显式数据库的一致快照 ID，再人工创建标签文件；若源库改变，需要重新核对标签和快照。不能把当前搜索命中当相关真值。相关 ID 不存在时拒绝运行。无真实标签可用 answerable=null 的探针，只测性能，质量输出 null。

## 指标和错误

- 排名先稳定去重再截 K；Recall 是命中不同相关 chunk 数/已标相关 chunk 数，MRR 为首个相关名次倒数，宏平均。partial 只可解释为受限标签召回，报告按完整性、来源、类别、split 分组。
- 有答案 error 留分母且记 0。无答案的成功空/成功非空/error 分别报告，错误不计正确拒答。无适用题的指标为 null，并附原因；缺失类别组为 0 题而非质量通过。unjudged 单列且排除质量。
- R2：每题最小正式 submission_index 是质量样本；repeat_index 从 0 起，预热不参与。完成快慢和后续成功不改变首次 error。所有重复计入性能，另给排名稳定性。
- 请求 ms 仅包围实际 search_documents 调用，排队和报告解析在此计时之外；吞吐墙钟从首个任务提交前到全部完成，含排队/调度。P95 仅成功样本、nearest-rank ceil(0.95N)，原始请求记录可重算；错误数量/延迟、预热错误另列。
- tracemalloc peak 仅正式测量窗口内 Python 分配；Windows GetProcessMemoryInfo 是当前进程生命周期工作集峰值，含导入/副本/预热，无采样。其他 OS 当前进程峰值为 null + reason。两者不是系统内存，也不能互相替代。
- 无请求强制超时，`request_timeout=not_enforced`；本地线程测试不等于 API/MCP、多用户并发或生产 SLA。中断的运行不能作为完整基线。

CLI 输入/身份/路径错误退出 2，不输出原件正文、题文、凭据和异常详细消息。文件级损坏/不支持/加密产生 partial 清单，命令可成功退出；必须同时看报告 status 和逐文件状态。容量 total_bytes 是已知大小之和，unknown_size_file_count 单列，不把 stat 失败当 0。读取/解析失败保留已观测大小，哈希失败为 null；读取期间变化标 unstable，不声称稳定快照。

## 隔离与解释边界

数据库显式 `mode=ro`，使用 SQLite backup 包含 WAL，查询仅临时副本；不调用 init_db/ingest。只在评测进程临时替换现有 get_conn，每线程独立只读连接，异常时恢复，临时目录清理。生产模块导入可能触发现有 dotenv 加载，工具不打印配置或依赖其中 DB_PATH。测试仅用原创合成数据/隔离副本。

清单根目录不跟随符号链接或 Windows reparse point；公共报告使用匿名文件编号。PDF 的 <20 非空白字符页是扫描候选代理；图片统计是逐页引用次数，可能重复。DOCX 统计段落/表格/media，不造页码；DOC 结构、视频时长、GPU 未实现明确 unknown。目录不可访问报错，不伪装空目录。清单为 O(文件字节+PDF页数)，backup 需要额外一份 DB 磁盘空间。

真实题文、标签与结果都保存于被现有 `.gitignore` 排除的 `data/f00-local/`；不要把原件或正文复制进 evaluation。工具产物自带代码指纹、Python/依赖/SQLite/硬件、UTC 时间、K/split/负载及输入哈希。无 Git 提交或生产迁移；回滚为停用命令，仅清理由本次明确创建的输出。

## 当前验证缺口

完整约 20 GB 语料尚未整理；真实五类人工标签、真实 holdout、目标 P95/质量阈值、预算及恢复要求未冻结。一本手册和合成得分不代表这些目标通过。当前 basedpyright 未安装且工具提示用户此前已拒绝安装，不能声明类型检查通过；ruff 也未发现。自测、QA、静态规则审计分别记录；Chat1 A-01 已签署 Windows 工具阶段 PASS，完整业务验收仍待上述条件补齐。
