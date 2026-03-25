# Feature 007 - 配置管理基础设施 - 人工测试指导

## 功能概述

**功能名称**: 配置管理基础设施
**版本**: v0.1.0
**测试日期**: [待填写]
**测试人员**: [待填写]

**功能描述**:
实现配置加载工厂函数 `build_config()`，支持 CLI 参数、环境变量和默认值的优先级链（CLI > 环境变量 > 默认值）。新增 `NOTEEDITOR_DPI` 环境变量支持和 `--verbose` CLI 标志。

---

## 测试环境

### 前置条件
- Python 3.12+ 已安装
- 项目依赖已安装: `uv sync --all-extras`
- CLI 可用: `uv run noteeditor --help`
- 准备一个测试 PDF 文件（任意有效 PDF 即可）

### 终端要求
- 操作系统: Windows 10/11
- 终端: PowerShell / CMD / Git Bash

---

## 测试用例

### TC-001: 默认配置 - 无参数使用

**优先级**: 高
**类型**: 正向测试

**前置条件**:
- 存在测试 PDF 文件

**测试步骤**:
1. 执行 `uv run noteeditor test.pdf`
2. 观察输出中的 DPI 值

**预期效果**:
- [ ] 终端显示 `DPI: 300`（默认值）
- [ ] 命令正常完成，生成 PPTX 文件

**实际结果**: [待填写]
**是否通过**: [ ] Pass / [ ] Fail

---

### TC-002: CLI DPI 参数覆盖默认值

**优先级**: 高
**类型**: 正向测试

**测试步骤**:
1. 执行 `uv run noteeditor test.pdf --dpi 150`
2. 观察输出中的 DPI 值

**预期效果**:
- [ ] 终端显示 `DPI: 150`
- [ ] 命令正常完成

**实际结果**: [待填写]
**是否通过**: [ ] Pass / [ ] Fail

---

### TC-003: 环境变量 NOTEEDITOR_DPI 生效

**优先级**: 高
**类型**: 正向测试

**测试步骤**:
1. 设置环境变量:
   - PowerShell: `$env:NOTEEDITOR_DPI = "200"`
   - CMD: `set NOTEEDITOR_DPI=200`
   - Git Bash: `export NOTEEDITOR_DPI=200`
2. 执行 `uv run noteeditor test.pdf`（不指定 --dpi）
3. 观察输出中的 DPI 值
4. 清除环境变量

**预期效果**:
- [ ] 终端显示 `DPI: 200`（来自环境变量，非默认 300）
- [ ] 命令正常完成

**实际结果**: [待填写]
**是否通过**: [ ] Pass / [ ] Fail

---

### TC-004: CLI 参数优先于环境变量

**优先级**: 高
**类型**: 正向测试

**测试步骤**:
1. 设置环境变量: `NOTEEDITOR_DPI=200`
2. 执行 `uv run noteeditor test.pdf --dpi 150`
3. 观察输出中的 DPI 值
4. 清除环境变量

**预期效果**:
- [ ] 终端显示 `DPI: 150`（CLI 参数优先）
- [ ] 环境变量的 200 被忽略

**实际结果**: [待填写]
**是否通过**: [ ] Pass / [ ] Fail

---

### TC-005: --verbose 标志

**优先级**: 中
**类型**: 正向测试

**测试步骤**:
1. 执行 `uv run noteeditor test.pdf --verbose`
2. 观察输出

**预期效果**:
- [ ] 命令正常完成，无报错
- [ ] `--verbose` 参数被接受（不会报 "no such option" 错误）

**实际结果**: [待填写]
**是否通过**: [ ] Pass / [ ] Fail

---

### TC-006: --verbose 短选项 -v

**优先级**: 中
**类型**: 正向测试

**测试步骤**:
1. 执行 `uv run noteeditor test.pdf -v`

**预期效果**:
- [ ] 命令正常完成，无报错

**实际结果**: [待填写]
**是否通过**: [ ] Pass / [ ] Fail

---

## 负向测试

### TC-N01: 环境变量 NOTEEDITOR_DPI 为非数字

**优先级**: 高
**类型**: 负向测试

**测试步骤**:
1. 设置环境变量: `NOTEEDITOR_DPI=abc`
2. 执行 `uv run noteeditor test.pdf`（不指定 --dpi）
3. 清除环境变量

**预期效果**:
- [ ] 退出码为 1
- [ ] 终端显示错误信息，包含 "invalid DPI"

**实际结果**: [待填写]
**是否通过**: [ ] Pass / [ ] Fail

---

### TC-N02: 环境变量 NOTEEDITOR_DPI 超出范围

**优先级**: 高
**类型**: 负向测试

**测试步骤**:
1. 设置环境变量: `NOTEEDITOR_DPI=10`
2. 执行 `uv run noteeditor test.pdf`（不指定 --dpi）
3. 清除环境变量

**预期效果**:
- [ ] 退出码为 1
- [ ] 终端显示错误信息，包含 "DPI must be between"

**实际结果**: [待填写]
**是否通过**: [ ] Pass / [ ] Fail

---

### TC-N03: 环境变量 NOTEEDITOR_DPI 超出范围（过高）

**优先级**: 中
**类型**: 负向测试

**测试步骤**:
1. 设置环境变量: `NOTEEDITOR_DPI=9999`
2. 执行 `uv run noteeditor test.pdf`（不指定 --dpi）
3. 清除环境变量

**预期效果**:
- [ ] 退出码为 1
- [ ] 终端显示错误信息，包含 "DPI must be between"

**实际结果**: [待填写]
**是否通过**: [ ] Pass / [ ] Fail

---

## 边界用例

### BC-001: 环境变量设置为边界值

- `NOTEEDITOR_DPI=72`（最小值）: 应成功，DPI 显示 72
- `NOTEEDITOR_DPI=1200`（最大值）: 应成功，DPI 显示 1200

### BC-002: CLI 和环境变量都为边界值

- `NOTEEDITOR_DPI=72` + `--dpi 1200`: 应使用 CLI 的 1200
- `NOTEEDITOR_DPI=1200` + `--dpi 72`: 应使用 CLI 的 72

---

## 测试总结

| 用例数 | 通过 | 失败 | 阻塞 |
|--------|------|------|------|
| 9 | - | - | - |

**测试结论**: [待填写]

**发现的问题**: [如有问题请在此记录]

---

*测试指导生成时间: 2026-03-24*
*Feature ID: 007*
*Version: v0.1.0*
