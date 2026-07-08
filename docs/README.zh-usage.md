# LLM Wiki Generator 使用文档

[Back to README](../README.md) | [Docs Index](index.md) | [中文首页介绍](README.zh-home.md)

`LLM Wiki Generator` 是一个对任何 AI agent、任何团队工作流、以及独立 CLI 使用都友好的工具。它既可以作为 skill 使用，也可以直接作为 Python CLI 运行。它的目标不是“直接把文档丢给模型问答”，而是先把知识转成结构化 wiki，再基于稳定知识进行检索和回答。

这份文档更偏实际操作，适合你准备开始导入资料、直接归档、生成知识页面和问答时使用。

## 1. 功能概览

这个项目提供这些核心能力：

- 文档转 Markdown：`convert`
- 宿主模型归档：`convert --as-json` + `apply-preview`
- 独立 CLI 直接归档：`archive`
- 可选预览：`show-updates`
- 只写入不重建索引：`apply`
- 构建检索索引：`index`
- 确定性召回：`search`
- 从 wiki 问答：`answer`

支持的输入格式：

- `PDF`
- `DOCX`
- `PPTX`
- `XLSX`
- `TXT`

## 2. 安装与准备

### 作为 skill 安装

如果你的宿主环境提供 `npx install skill` 这类统一安装入口，推荐先通过 skill 安装，再进入 CLI 使用阶段。

推荐说明写法可以是：

```bash
npx install skill llm-wiki-generator
```

推荐的安装后预检流程：

1. 检查是否存在 `Python 3`
2. 检查是否存在 `pip`
3. 检查 `requirements.txt` 中的依赖是否满足
4. 检查 `.env` 是否存在以及 wiki 路径是否已配置

如果不满足，skill 应明确提示用户还缺什么。例如：

- `Python 3 is not installed`
- `pip is not available`
- `Missing Python packages: typer, rich, pydantic, python-dotenv, openai, pyyaml`
- `Optional packages missing for extended document support: python-docx, python-pptx, openpyxl, reportlab`

然后在得到用户同意后，再安装全部依赖，再继续运行。

说明：这部分属于“推荐安装体验”。当前仓库真实提供的是 `requirements.txt` 和 `.env.example`，自动预检与自动安装更适合由 skill 安装器或宿主平台接管。

### 手动安装依赖

```bash
pip install -r requirements.txt
```

### 配置 `.env`

```bash
cp .env.example .env
```

常用配置如下：

```env
LLM_PROVIDER=openai_compatible
LLM_BASE_URL=
LLM_API_KEY=
LLM_MODEL=
LLM_TIMEOUT=60
WIKI_ROOT=runtime/vault
WIKI_INDEX_DB=runtime/index.sqlite3
WIKI_SCOPE=stable
```

说明：

- `WIKI_ROOT` 是知识库落盘目录
- `WIKI_INDEX_DB` 是本地 SQLite 索引文件
- `WIKI_SCOPE` 默认问答范围，默认是 `stable`
- 安装为 Claude Code、Codex、OpenCode skill 后，归档和回答默认使用宿主模型，不需要配置 `LLM_API_KEY`
- 只有独立 CLI/API 模式才需要配置 `LLM_PROVIDER`、`LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL`

## 3. 初始化知识库

首次使用前，推荐先检查当前知识库是否已经完成初始化：

```bash
python scripts/cli.py bootstrap-status --as-json
```

如果未初始化，推荐流程是：

1. 询问用户是否现在初始化
2. 询问 wiki 文件应创建在哪个路径
3. 重复路径并等待用户确认
4. 执行初始化并写回 `.env`
5. 初始化完成后立即询问用户是否现在提供第一份文档

对应的初始化命令是：

```bash
python scripts/cli.py bootstrap-init path/to/wiki-vault
```

它会自动：

- 写入 `WIKI_ROOT`
- 写入与 wiki 根目录同级的 `WIKI_INDEX_DB`
- 创建完整的 vault 结构

如果你已经在 `.env` 里提前确定了路径，也可以继续使用原来的初始化命令。

首次使用直接初始化 vault：

```bash
python scripts/cli.py init
```

会创建：

```text
10-raw/
  business_fact/
  industry_practice/
  team_history/
  feedback/
20-wiki/
  sources/
  entities/
  concepts/
  synthesis/
  conflicts/
  prd-patterns/
  index.md
  log.md
```

其中：

- `10-raw/` 保存原始输入文件副本
- `20-wiki/` 保存结构化知识页面
- `index.md` 记录 wiki 入口
- `log.md` 记录归档日志

## 4. 命令详解

### `convert`

把源文件转换成 Markdown，但不进入归档流程。

```bash
python scripts/cli.py convert path/to/file.pdf
```

适用场景：

- 只想看当前文档解析结果是否符合预期
- 先验证源文件内容是否可被正常抽取
- 调试导入前的原始文本质量

### 宿主模型归档

安装为 skill 后，推荐由 Claude Code、Codex 或 OpenCode 的当前模型负责抽取知识，CLI 只做转换、校验、写入和建索引。

```bash
python scripts/cli.py convert path/to/file.docx --as-json
```

宿主模型读取返回的 Markdown 后，生成符合 `ArchivePreview` schema 的 JSON，并写入临时文件，例如 `/tmp/archive-preview.json`。然后执行：

```bash
python scripts/cli.py apply-preview path/to/file.docx --preview-file /tmp/archive-preview.json
```

执行后会发生这些事：

1. 把原文件复制到 `10-raw/<source_type>/`
2. 把结构化页面写入 `20-wiki/`
3. 如果页面已存在，则合并 metadata，并把新内容追加为更新块
4. 更新 `20-wiki/index.md`
5. 追加 `20-wiki/log.md`
6. 重建 SQLite 检索索引，方便后续 `answer` 召回

如果你准备批量导入很多文件，可以先跳过自动索引：

```bash
python scripts/cli.py apply-preview path/to/file.docx --preview-file /tmp/archive-preview.json --no-index
```

然后在一批文件结束后手动执行 `index`。

### `archive`

独立 CLI/API 模式下，可以让 Python CLI 自己调用 OpenAI-compatible API 完成抽取和归档：

```bash
python scripts/cli.py archive path/to/file.docx --source-type team_history
```

这个模式需要在 `.env` 中配置 `LLM_PROVIDER`、`LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL`。

### `show-updates`

预览归档结果，不写入任何 wiki 页面。

```bash
python scripts/cli.py show-updates path/to/file.docx --source-type team_history
```

它会输出一个 `ArchivePreview`，里面包含：

- 会创建或更新哪些页面
- 页面类型是什么
- 状态是 `stable`、`draft` 还是 `conflict`
- 置信度
- 证据片段
- 归档理由

这是可选审计步骤，适合你想看 LLM 会生成什么页面但暂时不写入时使用。
这一步必须配置 OpenAI-compatible LLM。如果模型配置缺失，或者模型返回内容无法解析，命令会直接失败，不会写入归档文件。

### `apply`

经过 LLM 抽取后写入知识库，但不自动重建检索索引。

```bash
python scripts/cli.py apply path/to/file.docx --source-type team_history
```

执行后会发生这些事：

1. 把原文件复制到 `10-raw/<source_type>/`
2. 把结构化页面写入 `20-wiki/`
3. 如果页面已存在，则合并 metadata，并把新内容追加为更新块
4. 更新 `20-wiki/index.md`
5. 追加 `20-wiki/log.md`

如果你希望归档后立即用于召回，skill 模式优先使用 `apply-preview`，独立 CLI/API 模式优先使用 `archive`。

### `index`

构建本地检索索引：

```bash
python scripts/cli.py index
```

它会扫描 `20-wiki/` 下的 Markdown 页面，写入 SQLite 和 FTS 索引，用于后续 `answer` 检索。

### `search`

确定性检索本地 wiki，不调用任何模型，适合让 Claude Code、Codex 或 OpenCode 基于召回结果回答：

```bash
python scripts/cli.py search "团队历史里提到的设计思路有哪些？" --scope stable-draft --as-json
```

返回结果包含页面标题、状态、页面类型、来源类型、路径和摘录。宿主模型回答时应只基于这些结果，并引用页面标题。

### `answer`

从 wiki 中检索并回答问题：

```bash
python scripts/cli.py answer "当前已知的业务约束是什么？"
```

默认只查 `stable` 内容。你也可以扩大范围：

```bash
python scripts/cli.py answer "团队历史里提到的设计思路有哪些？" --scope stable-draft
```

支持的 `scope`：

- `stable`
- `stable-draft`
- `all`

## 5. `source_type` 怎么选

### `business_fact`

适合：

- 业务规则
- 客户约束
- 已确认事实

特点：

- 证据足够强时可以沉淀为稳定知识

### `industry_practice`

适合：

- 行业案例
- 通用方法论
- 最佳实践

特点：

- 更适合沉淀为 `source`、`synthesis`、`prd_pattern`
- 不应直接被当作客户事实

### `team_history`

适合：

- 设计演变记录
- 历史方案
- 过去的讨论结果

特点：

- 默认进入 `draft`
- 也可以从历史 PRD、团队决策、需求结构、评审流程和可复用产品判断中提取 `prd_pattern`

### `feedback`

适合：

- 用户反馈
- 内部意见
- 访谈摘录

特点：

- 默认进入 `draft`

## 6. 一个完整示例

假设你有一个团队历史文档 `docs/team-retro.docx`：

```bash
python scripts/cli.py init
python scripts/cli.py convert docs/team-retro.docx --as-json
# Claude Code / Codex / OpenCode 生成 ArchivePreview JSON 到 /tmp/archive-preview.json
python scripts/cli.py apply-preview docs/team-retro.docx --preview-file /tmp/archive-preview.json
python scripts/cli.py search "团队过去在架构上有哪些反复出现的思路？" --scope stable-draft --as-json
```

建议习惯：

- 安装为 skill 后，日常优先使用宿主模型归档流程
- 独立 CLI/API 使用者再使用 `archive`
- 批量归档时可以使用 `apply-preview --no-index`，最后统一执行一次 `index`
- 第一次初始化完成后，立即决定是否现在导入第一份文档，避免初始化后流程中断

## 7. 模型要求

Skill 宿主模型模式：

- Claude Code、Codex、OpenCode 当前会话模型负责生成 `ArchivePreview` 和综合回答
- CLI 不需要 `LLM_API_KEY`
- `apply-preview` 只负责校验和写入，坏 JSON 会直接失败且不写入 raw/wiki

独立 CLI/API 模式：

- `archive`、`show-updates` 和 `apply` 需要 OpenAI-compatible 配置
- `answer` 在无模型时仍可退化为摘录式回答

也就是说，skill 模式使用宿主模型；CLI-only 模式可以选择配置外部 API。

## 8. 总结

如果你想把“原始资料 -> 结构化知识 -> 可检索问答”做成一个可控、可持续更新的流程，这个项目的推荐使用方式就是：

1. `init`
2. `convert --as-json`
3. 宿主模型生成 `ArchivePreview`
4. `apply-preview`
5. `search --as-json`
6. 宿主模型回答

最重要的心智模型是：

- `convert` 是抽取
- `apply-preview` 是宿主模型归档结果的确定性写入入口
- `archive` 是独立 CLI/API 的一步式入口
- `show-updates` 是可选审阅
- `apply` 是只归档、不自动建索引
- `index` 是检索准备
- `search` 是确定性召回
- `answer` 是 CLI-only 的问答入口；skill 模式优先由宿主模型回答
