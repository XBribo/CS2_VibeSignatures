# bump_download 自动登记设计

## 背景

仓库已有 `download.yaml` 作为 depot manifest 的配置来源，`download_depot.py` 会按 Git tag 精确匹配其中的 `downloads[].tag` 并下载对应 depot。现有 `build-on-self-runner.yml` 则在 tag push 后执行下载、分析、gamedata 更新、测试和 release。

当前缺口是上游发现流程仍需人工维护：当 CS2 默认公开分支更新时，需要手动查询 depot manifest、读取 `steam.inf` 的 `PatchVersion`、更新 `download.yaml`、提交并创建新 tag。本设计新增一个 self-hosted runner 上定时执行的 bump 流程，把这部分自动化。

## 目标

- 新增 `bump_download.py`，自动发现 CS2 默认公开分支的新版本或同版本 manifest 变体。
- 自动追加 `download.yaml` 条目，并尽量保留已有注释、引号、顺序和未改动条目的格式。
- 有新条目时，本地创建 commit 和 tag；脚本不执行 push。
- 新增 GitHub Actions workflow，每 6 小时运行一次，并支持手动触发。
- workflow 负责把脚本创建的本地 commit 推回 `main`，并推送新 tag。
- 新 tag push 后复用现有 `build-on-self-runner.yml` 完成后续构建和 release。

## 非目标

- 不监控或自动更新 `animgraph_2_beta` 等非默认分支。
- 不替换现有 `download_depot.py` 的按 tag 下载逻辑。
- 不修改现有 release workflow 的核心构建、IDA 分析或打包流程。
- 不尝试修复 `download.yaml` 中历史条目的注释内容、旧 manifest 值或人工标记。
- 不在脚本内 push commit 或 tag。

## 总体方案

采用一个自包含的 `bump_download.py` 作为核心入口。脚本负责网络查询、版本判定、YAML 追加、本地 commit 和本地 tag；GitHub Actions workflow 只负责调度、传入凭据、读取脚本 output，并在有更新时 push。

这个方案让本地手动运行和 CI 定时运行使用同一套逻辑，也避免把 tag 决策散落到 PowerShell workflow 中。

## 脚本数据流

`bump_download.py` 的主流程如下：

1. 调用 `DepotDownloader -app 730 -depot 2347770 -os all-platform -dir <depotdir> -manifest-only` 获取默认公开分支 depot `2347770` 的 manifest 文件。
2. 从生成的 `manifest_2347770_<manifest_id>.txt` 文件名中解析 `2347770` 的 manifest id。
3. 创建临时 filelist 文件，内容只包含 `game\csgo\steam.inf`；随后调用 `DepotDownloader -app 730 -depot 2347770 -os all-platform -dir <depotdir> -manifest <2347770_manifest_id> -filelist <filelist_path>`，只下载 `steam.inf`。
4. 从 `steam.inf` 读取 `PatchVersion`，例如 `1.41.6.1`。
5. 分别调用 `DepotDownloader -app 730 -depot 2347771 -os all-platform -dir <depotdir> -manifest-only` 和 `2347773`，解析两个二进制 depot 的 manifest id。
6. 将 `PatchVersion` 转为基础 tag，例如 `1.41.6.1 -> 14161`。
7. 读取并校验 `download.yaml`。
8. 根据已有条目决定是否追加新条目。
9. 有新条目时写回 `download.yaml`，执行本地 `git add`、`git commit`、`git tag`。
10. 写入 GitHub Actions output，告知 workflow 是否需要 push。

## Tag 规则

基础 tag 由 `PatchVersion` 去掉点号得到：

```text
1.41.6.1 -> 14161
```

新增条目规则：

- 如果 `download.yaml` 中不存在 `name: 1.41.6.1` 的默认分支条目，新增 `tag: "14161"`。
- 如果同一 `name` 已存在，但 `2347771` 或 `2347773` 的 manifest 组合从未出现，新增下一个后缀 tag。
- 后缀从 `b` 开始递增：`14161b`、`14161c`、`14161d`。
- 如果同一 `name` 下已经存在完全相同的 `2347771` 和 `2347773` manifest 组合，视为无更新。
- 已有 `branch` 字段的条目不作为默认分支的等价记录参与 manifest 去重；它们只保留为历史或 beta 记录。

## YAML 保留策略

`download.yaml` 当前包含行内注释，因此脚本使用 `ruamel.yaml` 读写配置，尽量保留已有注释、引号、顺序和未改动条目的结构。

新增依赖：

```toml
ruamel.yaml
```

写回原则：

- 只追加新的 `downloads` 条目。
- 不重排已有条目。
- 不主动重写已有注释。
- 不主动修复旧条目的缩进或历史 manifest 值。
- 新条目使用稳定结构：

```yaml
- tag: "14161"
  name: 1.41.6.1
  manifests:
    "2347771": "6999933698852825529"
    "2347773": "1005161166845732962"
```

如果后续实现发现 `ruamel.yaml` 仍会对部分空白做轻微规范化，应以“尽量保留未改动内容”为目标，不要求 byte-for-byte 完全不变。

## CLI 设计

建议参数：

```text
uv run bump_download.py
  -config download.yaml
  -depotdir cs2_depot
  -app 730
  -os all-platform
  -username <steam username>
  -password <steam password>
  -remember-password
  -github-output <path>
  -dry-run
```

参数说明：

- `-config`：下载配置文件，默认 `download.yaml`。
- `-depotdir`：DepotDownloader 输出目录，默认 `cs2_depot`。
- `-app`：Steam app id，默认 `730`。
- `-os`：DepotDownloader `-os` 参数，默认 `all-platform`。
- `-username`、`-password`、`-remember-password`：透传给 DepotDownloader。
- `-github-output`：可选。传入后写入 `updated` 和 `tag` 等 workflow output。
- `-dry-run`：只打印将要新增的条目，不写文件、不执行 git。

## Git 行为

脚本只执行本地 Git 操作：

```text
git add download.yaml
git commit -m "chore(download): 更新 1.41.6.1 下载清单"
git tag 14161
```

约束：

- 有更新时，提交前要求工作区没有无关未提交变更。
- 无更新时不要求工作区干净，因为脚本不会写入或提交。
- 创建 tag 前检查本地 tag 和远端 tag，避免覆盖历史。
- 如果 commit 或 tag 失败，脚本返回失败。
- 如果 `download.yaml` 已经存在完全匹配的新版本条目，但对应 tag 在远端缺失，脚本进入 tag 修复模式：不修改 `download.yaml`，只在本地创建或复用同名 tag，并输出需要 push tag。这样可以恢复“main push 成功但 tag push 失败”的中间状态。

## GitHub Actions 设计

新增 `.github/workflows/bump-download.yml`：

```yaml
name: Bump Download

on:
  schedule:
    - cron: "0 */6 * * *"
  workflow_dispatch:

permissions:
  contents: write

jobs:
  bump:
    if: github.repository == 'HLND2T/CS2_VibeSignatures' || github.repository == 'hzqst/CS2_VibeSignatures'
    environment: win64
    runs-on: [self-hosted, windows, x64]
    env:
      STEAM_USERNAME: ${{ secrets.STEAM_USERNAME }}
      STEAM_PASSWORD: ${{ secrets.STEAM_PASSWORD }}
    steps:
      - uses: actions/checkout@v4
        with:
          ref: main
          fetch-depth: 0

      - name: Configure git
        shell: pwsh
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"

      - name: Bump download config
        id: bump
        shell: pwsh
        run: |
          uv run bump_download.py -config download.yaml -depotdir cs2_depot -username "$env:STEAM_USERNAME" -password "$env:STEAM_PASSWORD" -remember-password -github-output "$env:GITHUB_OUTPUT"

      - name: Push bump branch
        if: steps.bump.outputs.updated == 'true'
        shell: pwsh
        run: |
          git push origin "HEAD:refs/heads/bump-download/${{ steps.bump.outputs.tag }}"

      - name: Create or update bump pull request
        if: steps.bump.outputs.updated == 'true'
        uses: actions/github-script@v7
```

workflow 使用 `main` 作为固定目标分支，但不直接 push protected branch。新下载条目先进入 `bump-download/<tag>` 临时分支并创建 PR。PR 合并后，post-merge workflow 在合并后的 main commit 上创建 tag，并通过 `repository_dispatch` 触发 `build-on-self-runner`。

如果配置已在 `main` 但远端 tag 缺失，脚本进入 tag 修复模式并写出 `repair_tag=true`。workflow 此时不创建 PR，而是补推缺失 tag，并通过 `repository_dispatch` 触发 `build-on-self-runner`。

## Output 与退出码

退出码：

- `0`：脚本执行成功，包括“无更新”和“有更新”。
- `1`：真实失败，例如配置错误、DepotDownloader 失败、Git 失败。

GitHub Actions output：

无更新：

```text
updated=false
```

有更新：

```text
updated=true
tag=14161
```

tag 修复模式同样写入 `updated=true` 和 `tag=<missing_tag>`，并额外写入 `repair_tag=true`，让 workflow 走补 tag 与 dispatch 构建路径。

## 错误处理

以下情况应失败退出：

- DepotDownloader 不存在。
- DepotDownloader 返回非 0。
- `-manifest-only` 后未找到预期 manifest 文件。
- `steam.inf` 找不到或缺少 `PatchVersion`。
- `PatchVersion` 不是四段数字版本。
- `download.yaml` 不存在、YAML 非法或 `downloads` 不是列表。
- 已有条目缺少 `tag`、`name` 或 `manifests`，导致无法可靠判定。
- 已有 tag 重复。
- 即将创建的 tag 已存在于本地或远端。
- 有更新时工作区已有无关未提交变更。
- `git add`、`git commit` 或 `git tag` 失败。
- tag 修复模式下，本地已有同名 tag 但指向的 commit 与当前 `download.yaml` 条目不一致。

无更新时脚本应清晰打印当前 `PatchVersion`、manifest 组合和“no update”结论。

## 测试策略

新增 `tests/test_bump_download.py`，使用 mock 覆盖逻辑，不真实访问 Steam。

建议测试：

- `PatchVersion -> base tag`：`1.41.6.1 -> 14161`。
- 全新默认分支版本生成无后缀 tag。
- 同版本不同 manifest 生成 `b`、`c` 后缀。
- 同版本同 manifest 判定无更新。
- 带 `branch` 的 beta 条目不作为默认分支去重依据。
- manifest 文件名解析正确。
- `steam.inf` 中 `PatchVersion` 解析正确。
- 下载 `steam.inf` 时使用 `2347770` 的 manifest id 和只包含 `game\csgo\steam.inf` 的 filelist。
- `-dry-run` 不写文件、不执行 git。
- 有更新时 Git 命令顺序为 `add -> commit -> tag`。
- 配置已在 main 但 tag 缺失时，脚本进入 tag 修复模式并输出需要补推的 tag。
- `-github-output` 正确写入 `updated=false`、`updated=true/tag=...`，以及 tag 修复时的 `repair_tag=true`。
- `ruamel.yaml` 写回后保留既有条目的行内注释。

按仓库偏好，本任务属于有行为影响的新自动化功能，建议至少执行定向单测：

```text
uv run python -m unittest tests.test_bump_download tests.test_download_depot
```

## 风险与权衡

- `ruamel.yaml` 能显著降低注释丢失风险，但不保证完全保持原始字节布局。
- DepotDownloader 输出文件名是脚本解析 manifest id 的关键依据，需要用明确的 glob 和 depot id 校验减少误判。
- 工作区干净检查会让脚本在 runner 残留修改时失败，但这比误提交无关文件更安全。
- 定时 workflow 推送 tag 会触发现有 build workflow，因此 bump workflow 只负责登记，不负责构建结果判断。
- tag 修复模式只覆盖“main 已包含条目但 tag 缺失”的情况；如果远端 tag 已存在但 main 推送失败，现有构建仍可通过 tag 中的提交运行，main 同步问题需要人工处理或重新推送分支。

## 验收标准

- 运行 bump workflow 时，如果 CS2 默认公开分支没有新 manifest 组合，则不修改 `download.yaml`，不创建 commit，不创建 tag。
- 如果发现新 PatchVersion，则追加无后缀 tag 条目，提交并创建同名 tag。
- 如果发现同 PatchVersion 的新 manifest 组合，则追加递增后缀 tag 条目，提交并创建同名 tag。
- 新增条目不包含 `branch` 字段。
- `download.yaml` 中已有注释尽量保留。
- workflow 每 6 小时运行一次，也可手动触发。
- workflow 只在脚本 output `updated=true` 时 push `main` 和新 tag。
