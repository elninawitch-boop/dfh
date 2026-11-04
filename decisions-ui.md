# PSD 修复工具 · 界面改动决策记录

> 用途：记录对 UI 的每次改动「改了什么 + 为什么」，避免以后改回去。
> 项目本体：`E:\workbuddy-en\111\psd-tool\`
> 工作区镜像：`E:\大肥鱼工作区\psd-tool\`（改这里 → 写回项目）

---

## 2026-11-03 · 去 AI 味第一批：删两处文字

### 背景
用户发来两张截图，指出「检测并修复 AI 生成 PSD 的结构问题」和「01/02/03 步骤列表」这两处 AI 味重，要求删掉。

### 改动清单

| # | 位置 | 改动 | 理由 |
|---|---|---|---|
| 1 | L817 顶栏品牌区 | 删除 `<div class="brand-cn">检测并修复 AI 生成 PSD 的结构问题</div>` 整行 | 与上方 `PSD REPAIR` + `DETECT · FIX · EXPORT` 完全重复，是典型的「标题+副标题+小字」三层堆叠 AI 味。删掉不少任何信息 |
| 2 | CSS L174-177 | 删除 `.brand-cn` 样式块 | 节点删了样式留着就是死代码 |
| 3 | L889-891 右栏空状态 | 删除 `01 拖入 PSD 文件 / 02 自动检测结构问题 / 03 一键修复并导出` 三行 | **「01 / 02 / 03」章节编号是 de-slop 清单里点名的 AI 套路**（另一批：紫蓝渐变+小火箭、奶油色背景+斜体衬线大标题）。而且上面的「尚未载入文件」已经说明状态，三步说明属于解释性冗余 |
| 4 | L1066-1068 `renderRight()` | 同步删除 JS 里的三行步骤（渲染时会重新塞回来，只删 HTML 等于白删） | 同上 |
| 5 | CSS L564-571 | 删除 `.step` / `.step-no` 样式 | 死代码 |

### 明确保留（用户点名不要删）

| 位置 | 内容 | 理由 |
|---|---|---|
| L816 `#drop-main` | 「拖入 PSD 文件」 | **这是唯一的操作引导**。右栏的三步说明删掉之后，如果这里也删，用户完全不知道能拖文件。drag 热区还在但没有任何文字提示 |

### 未动
- 顶栏其余：`PSD REPAIR`（品牌名）、`DETECT · FIX · EXPORT`（一行英文短语，不重复正文）
- 面板标题的英文小字：`DIAGNOSIS` / `PROGRESS` / `FILE` —— 是视觉层次的一部分，不是解释性文字
- 拖放区下方 `OR CLICK TO SELECT` 保留

### 验证
- HTML 结构校验：标签全平衡，0 多余闭合、0 不匹配
- 关键节点存在性：`#drop` `#drop-main` `#right-body` `#diag` `#prog` `renderRight` `elRightBody` 全部 OK
- 26539 → 48545 字节（UTF-8），减少 2452 字节
- 真 Chrome 渲染截图对比通过（`_preview_before.png` / `_preview_after.png`）

### 回滚
原文件备份在：`qt_ui\index.html.bak-deslop-20261103`（50997 B）

---

## 用户审美偏好（持续累积）

从 `交接文档.md` 第六节 + 本次互动提炼，**这些是用户明确说过「不要」的**：

1. 文字纯黑 `#000`（深色主题纯白），**不要灰**。看不清就加大加粗。
2. 玻璃要通透：极淡白 4-6% + 四边高光 + 内阴影，**不要 62% 的重色板**。
3. 图标入场**不要从 opacity:0 淡入**（会「背景先到、图标后到」）。
4. 图层行**不要改回实心绿条**（要矩形靠 `background-position` 来回滑）。
5. 卡片/说明文字**能删就删**（本次新增）：标题下的副标题、章节编号、一行能说完却写三行的，都是 AI 味。

---

## 2026-11-03 · 第二批：右栏「最近文件列表」

### 背景
第一批删掉 01/02/03 三步之后，右栏只剩一行「尚未载入文件」，**480px 高的玻璃面板全空**，看着像坏了。用户选方案 B：放最近打开的文件列表。

### 关键决策：为什么不用 localStorage
Qt WebEngine **拿不到完整文件路径**（拖放由 Qt 层 `DropCatcher` 取值，`load_path` 只把 basename 传给 JS）。要做到「点一下就重新打开」，必须有完整路径 → 只能在 Python 侧存。
另外 `net_guard.configure_profile()` 把 `HttpCacheType` 设成了 `MemoryHttpCache`，localStorage 是否落盘不可靠。

**结论：新建 `recent_store.py`，存到 `%LOCALAPPDATA%\PSD修复工具\recent.json`。**
不写程序目录（打包后 `_internal` 只读），不写文档目录（不污染用户文件）。

### 改动清单

| 文件 | 改动 |
|---|---|
| `recent_store.py` | **新增**。`RecentStore` 类：`touch / list / path_at / remove_at`，上限 5 条，倒序，原子写入（tmp + os.replace） |
| `psd_repair_qt.py` | import + `Bridge.recent` 实例；`load_path` 里 `touch` 并推列表；新增 `open_recent / remove_recent / push_recent`；`_start_bridge` 注册两个新 handler，桥就绪后 `QTimer.singleShot(150, push_recent)` |
| `qt_ui/index.html` | `S.recent` 状态；`renderRight()` 空状态改为「有记录就列、没有才显示 hint」；`fmtSize / fmtAgo`；`APP.setRecent`；`elRightBody.onclick` 事件委托处理打开/删除 |

### 交互样式来源（全部取自 `E:\大肥鱼工作区\动画视觉素材\`）

| 效果 | 来源 | 原值 |
|---|---|---|
| **× 平时是空环，悬停整块填充 + 反色** | `doytsujin/css/base.css` L316-331 | `box-shadow: inset 0 0 0 3px var(--color-link)` → `background: var(--color-link)` + 反色 |
| **× 浮现：淡入 + 位移 10px** | `loaders-css/demo.css` L63-113 的 `.tooltip` | `opacity 0→1` + `translate3d` 位移，`transition: all 200ms ease` |
| **按下反馈** | 项目自有 | `.recent-del:active { transform:scale(.92) }` + `--spring-snap` |

按用户要求「显隐用库里、按压用项目」，所以悬停 200ms ease、按下用项目弹簧，不冲突。

**尺寸调整（库里原值直接搬会不合适）**：原 3px 内描边在 18px 的 × 上太粗，缩到 **1.5px**；`scale(1.0156)` 在小元素上等于没动，改成 **scale(.92) 按压**。

### 已验证
- HTML 结构：标签全平衡，10 个关键 JS 钩子全部存在
- 视觉：真 Chrome 渲染，列表 4 条正常显示，失效条目显示划线
- `RecentStore` 单测：上限 5 ✓、去重置顶 ✓、持久化重载 ✓、越界删除返回 False ✓、已删文件 `exists=false` ✓
- `Bridge` 集成测试（offscreen，不启 GUI）：越界下标不触发 ✓、`push_recent` 推列表 ✓、`open_recent` 走 `setRecent`+`setLoading` ✓、`remove_recent` 2→1 ✓
- 核心冒烟：`PsdProbe` 输出 `2000 2000 7 0`，**与交接文档 §10 的期望值完全一致**（核心未被动）

### 回滚
- `qt_ui\index.html.bak-recent-20261103`
- `psd_repair_qt.py.bak-recent-20261103`
- `recent_store.py` 是新增文件，直接删即可

---

## 待确认

- **两批改动都还没打包进 exe**。成品 `_internal\qt_ui\index.html` 仍是 11-02 21:15 那版。
- 打包时程序**不能在运行**（上一轮检测到 PID 36692 在跑）。
- 用户选了「打包由我全包」，需要先关程序。
