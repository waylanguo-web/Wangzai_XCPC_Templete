# Wangzai_XCPC_Templete

Wangzai 的 XCPC 算法竞赛模板仓库。

## 目录结构

- `正文/`：模板正文章节
- `tools/template_tests/`：模板编译与样例运行测试工具
- `scripts/`：辅助脚本，例如安装 `pre-push` hook
- `.githooks/`：仓库内置 Git hook 模板
- `run-template-tests.ps1`：Windows 下的一键测试入口

## 模板测试

当前已经接入自动化测试的章节：

- `正文/03A - 图论.md`
- `正文/03B - 图论常见结论及例题.md`

测试脚本会从 Markdown 中抽取对应代码块，自动生成最小编译单元，完成编译与样例运行校验。

## 一键运行

在仓库根目录执行：

```powershell
.\run-template-tests.ps1
```

默认行为是只测试当前改动涉及到、且已经接入测试的章节。

## 常用命令

测试全部已接入章节：

```powershell
.\run-template-tests.ps1 -All
```

只测试当前改动涉及的章节：

```powershell
.\run-template-tests.ps1 -Changed
```

只测试指定文件：

```powershell
.\run-template-tests.ps1 -Files "正文\03A - 图论.md"
```

也可以直接调用 Python 主脚本：

```powershell
python .\tools\template_tests\run.py --all
python .\tools\template_tests\run.py --changed
python .\tools\template_tests\run.py --files "正文\03A - 图论.md"
python .\tools\template_tests\run.py --list
```

## Push 前自动测试

安装 `pre-push` hook：

```powershell
.\scripts\install-pre-push.ps1
```

安装完成后，每次执行 `git push` 前都会自动运行当前改动涉及的模板测试；如果测试失败，push 会被拦下。

## PR / MR 前的 CI

仓库已经接入 GitHub Actions 工作流：

`/.github/workflows/template-tests.yml`

它会在以下时机自动运行：

- 向 `main` 发起 Pull Request 时
- 代码直接 push 到 `main` 时

CI 中会执行：

```bash
python tools/template_tests/run.py --all
```

也就是说，只要当前已经接入测试的章节有问题，PR 就会直接红掉。

如果你希望“PR 未通过测试就绝对不能合并”，还需要在 GitHub 仓库里打开分支保护：

1. 进入仓库 `Settings`
2. 打开 `Branches`
3. 给 `main` 新建或编辑保护规则
4. 勾选 `Require a pull request before merging`
5. 勾选 `Require status checks to pass before merging`
6. 把 `template-tests` 加进必需检查

这样之后你的流程就是：

1. 从 `main` 拉新分支
2. 在分支上修改
3. 提交 Pull Request
4. GitHub 自动跑 `template-tests`
5. 只有测试通过，PR 才允许合并

如果你平时口头上习惯叫 MR，也可以把这里理解成同一件事；这个仓库实际平台是 GitHub，所以对应名称是 PR。

## 测试产物

测试中间产物与结果位于：

`tools/template_tests/.generated`

目前的处理方式如下：

- `.cpp` / `.exe` 中间文件会在测试开始前清理，并在每个用例结束后自动删除
- `.generated/` 已加入 `.gitignore`
- `results.json` 会保留，用于查看最近一次测试汇总结果

## 说明

如果你后续继续给其他章节接入测试，只需要在 `tools/template_tests/run.py` 里补充对应章节内容和最小样例即可，整套入口和 Git hook 流程可以直接复用。
