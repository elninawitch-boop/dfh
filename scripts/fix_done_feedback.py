# -*- coding: utf-8 -*-
"""修复完成后给足反馈

问题：修复完成后只有底部进度条变了，右上「当前文件」还是原文件信息，
     用户看不出修复成功。

改进：
  1. 右栏显示「修复完成」状态 + 输出文件名 + 前后体积对比
  2. 检测结果面板顶部显示绿色「已修复」横幅
  3. 拖放区变成「修复完成」状态
  4. 开始修复按钮变成「再修一次」
  5. 底部状态栏显示完整路径
"""
p = r'C:\Users\123\1\qt_ui\index.html'
s = open(p, encoding='utf-8').read()

# ---------- 1. 新增完成状态的 CSS ----------
old_css = """.hint {
  font-size:12.5px; opacity:.62; margin-top:16px;
}"""
new_css = """.hint {
  font-size:12.5px; opacity:.62; margin-top:16px;
}

/* ---- 修复完成状态 ---- */
.done-badge {
  display:inline-flex; align-items:center; gap:7px;
  padding:4px 12px; border-radius:999px;
  background:rgba(42,165,100,.16);
  border:1px solid rgba(42,165,100,.45);
  font-size:11.5px; font-weight:600; color:#1a7a4a;
  margin-left:10px;
}
body.dark .done-badge {
  background:rgba(42,165,100,.22);
  border-color:rgba(90,220,150,.5);
  color:#7ee0a8;
}
.done-banner {
  display:flex; align-items:center; gap:10px;
  padding:12px 16px; margin-bottom:12px;
  border-radius:12px;
  background:rgba(42,165,100,.12);
  border:1px solid rgba(42,165,100,.35);
}
body.dark .done-banner {
  background:rgba(42,165,100,.16);
  border-color:rgba(90,220,150,.35);
}
.done-banner-icon {
  width:22px; height:22px; border-radius:50%;
  background:#2aa564; color:#fff;
  display:flex; align-items:center; justify-content:center;
  font-size:14px; font-weight:700; flex:0 0 auto;
}
.done-banner-text { flex:1; font-size:12.5px; line-height:1.5; }
.done-banner-title { font-weight:600; }
.done-banner-sub { font-size:11.5px; opacity:.7; margin-top:2px; }

.out-file {
  font-size:14px; font-weight:600; color:#1a7a4a;
  margin-top:4px; word-break:break-all;
}
body.dark .out-file { color:#7ee0a8; }

.size-compare {
  display:flex; align-items:center; gap:8px;
  margin-top:14px; font-size:12.5px;
}
.size-before { opacity:.55; }
.size-arrow { opacity:.4; }
.size-after { font-weight:600; }
.size-save {
  font-size:11px; padding:1px 7px; border-radius:8px;
  background:rgba(42,165,100,.18); color:#1a7a4a;
  font-weight:600;
}
body.dark .size-save {
  background:rgba(42,165,100,.25); color:#7ee0a8;
}"""

if old_css in s:
    s = s.replace(old_css, new_css)
    print("[1] 已加完成状态样式")
else:
    print("[1] !! CSS 锚点未找到")

# ---------- 2. 重写 setDone ----------
old_done = """setDone(data) {
    S.busy = false;
    S.progress = 1;
    S.stage = data.hasIssues ? `完成 · ${data.count} 处提示` : '完成 · 校验通过';
    S.layers.forEach(L => { L.state = 'done'; L.frac = 1; L.detail = '完成'; });
    elFix.disabled = false;
    elOpen.disabled = false;
    setStatus(`${data.filename} · ${data.mb.toFixed(2)} MB`);
    renderProgList(); renderProgress();
  },"""

new_done = """setDone(data) {
    S.busy = false;
    S.progress = 1;
    S.outFile = data.filename;
    S.outMB = data.mb;
    S.doneCount = data.count;
    S.hasIssues = data.hasIssues;

    S.stage = data.hasIssues
      ? `完成 · ${data.count} 处提示`
      : '完成 · 结构校验通过';
    S.layers.forEach(L => { L.state = 'done'; L.frac = 1; L.detail = '完成'; });

    // 按钮：变成「再修一次」
    elFix.disabled = false;
    elFix.textContent = '再修一次';
    elOpen.disabled = false;

    // 拖放区改成完成态
    if (elDropMain) elDropMain.textContent = '✓ 修复完成';
    if (elDropSub) elDropSub.textContent = S.outFile;

    setStatus(`已保存 ${S.outFile} · ${data.mb.toFixed(2)} MB`);

    renderDiag();       // 加完成横幅
    renderRight();      // 右栏换成输出文件
    renderProgList();
    renderProgress();
  },"""

if old_done in s:
    s = s.replace(old_done, new_done)
    print("[2] 已重写 setDone")
else:
    print("[2] !! setDone 锚点未找到")

# ---------- 3. renderRight 支持完成态 ----------
old_right = """function renderRight() {
  if (!S.probe) {
    elRightBody.innerHTML = `
      <div class="hint">尚未载入文件</div>
      <div class="step"><span class="step-no">01</span><span>拖入 PSD 文件</span></div>
      <div class="step"><span class="step-no">02</span><span>自动检测结构问题</span></div>
      <div class="step"><span class="step-no">03</span><span>一键修复并导出</span></div>`;
    return;
  }"""

new_right = """function renderRight() {
  if (!S.probe) {
    elRightBody.innerHTML = `
      <div class="hint">尚未载入文件</div>
      <div class="step"><span class="step-no">01</span><span>拖入 PSD 文件</span></div>
      <div class="step"><span class="step-no">02</span><span>自动检测结构问题</span></div>
      <div class="step"><span class="step-no">03</span><span>一键修复并导出</span></div>`;
    return;
  }

  // ---- 修复完成后，右栏显示输出文件 ----
  if (S.outFile) {
    const before = (S.probe.size / 1024 / 1024);
    const after = S.outMB;
    const savePct = before > 0
      ? Math.round((1 - after / before) * 100) : 0;
    let html = `
      <div class="kv" style="margin-top:0">
        <span class="k">状态</span>
        <span class="v" style="color:#1a7a4a;font-weight:700">✓ 已修复</span>
      </div>
      <div class="out-file">${esc(S.outFile)}</div>
      <div class="size-compare">
        <span class="size-before">${before.toFixed(2)} MB</span>
        <span class="size-arrow">→</span>
        <span class="size-after">${after.toFixed(2)} MB</span>
        ${savePct > 0 ? `<span class="size-save">省 ${savePct}%</span>` : ''}
      </div>
      <div class="divider"></div>
      <div class="kv"><span class="k">原文件</span>
        <span class="v" style="font-size:11.5px;opacity:.7">${esc(S.probe.filename || '')}</span></div>
      <div class="kv"><span class="k">画布</span>
        <span class="v">${S.probe.width} × ${S.probe.height}</span></div>
      <div class="kv"><span class="k">图层</span>
        <span class="v">${S.layers.length} 个</span></div>
      <div class="kv"><span class="k">复核</span>
        <span class="v">${S.hasIssues ? S.doneCount + ' 处提示' : '全部通过'}</span></div>
      <div class="divider"></div>
      <div class="sect-title">图层结构</div>`;
    S.layers.slice(0, 8).forEach((L, i) => {
      html += `<div class="layer-row">
        <span class="layer-idx">${String(i + 1).padStart(2, '0')}</span>
        <span class="layer-name">${esc(L.name)}</span>
      </div>`;
    });
    elRightBody.innerHTML = html;
    return;
  }"""

if old_right in s:
    s = s.replace(old_right, new_right)
    print("[3] 已改造 renderRight")
else:
    print("[3] !! renderRight 锚点未找到")

# ---------- 4. renderDiag 加完成横幅 ----------
old_diag = """  const errs = S.issues.filter(i => i.sev === 'error').length;
  const warns = S.issues.length - errs;

  if (!S.issues.length) {"""

new_diag = """  const errs = S.issues.filter(i => i.sev === 'error').length;
  const warns = S.issues.length - errs;

  // 修复完成后显示横幅
  const banner = S.outFile ? `
    <div class="done-banner">
      <div class="done-banner-icon">✓</div>
      <div class="done-banner-text">
        <div class="done-banner-title">修复完成</div>
        <div class="done-banner-sub">
          已导出 ${esc(S.outFile)}（${S.outMB.toFixed(2)} MB）
          ${S.hasIssues ? '· 复核剩 ' + S.doneCount + ' 处提示' : '· 结构校验通过'}
        </div>
      </div>
    </div>` : '';

  if (!S.issues.length) {"""

if old_diag in s:
    s = s.replace(old_diag, new_diag)
    print("[4] 已加完成横幅变量")

# 把 banner 插入到 innerHTML
old_body = """    elDiagBody.innerHTML = '<div class="issue"><span class="issue-text">未发现结构问题，文件健康</span></div>';
    elDiagSum.textContent = '结构健康';
    return;
  }
  elDiagSum.textContent = `${S.issues.length} 个问题 · ${errs} 错误 / ${warns} 警告`;
  elDiagBody.innerHTML = S.issues.map((it, i) => `"""

new_body = """    elDiagBody.innerHTML = banner +
      '<div class="issue"><span class="issue-text">未发现结构问题，文件健康</span></div>';
    elDiagSum.textContent = '结构健康';
    return;
  }
  elDiagSum.textContent = S.outFile
    ? `已修复 · 原 ${S.issues.length} 个问题`
    : `${S.issues.length} 个问题 · ${errs} 错误 / ${warns} 警告`;
  elDiagBody.innerHTML = banner + S.issues.map((it, i) => `"""

if old_body in s:
    s = s.replace(old_body, new_body)
    print("[5] 已把横幅插入渲染")
else:
    print("[5] !! 渲染锚点未找到")

# ---------- 5. 新增状态字段与重置 ----------
old_state = """  busy: false,
};"""
new_state = """  busy: false,
  outFile: null,     // 修复后的文件名
  outMB: 0,          // 修复后的大小
  doneCount: 0,      // 复核剩余问题数
  hasIssues: false,
};"""
if old_state in s:
    s = s.replace(old_state, new_state)
    print("[6] 已加状态字段")

# load 时重置
old_load = """  setLoading(file) {
    S.file = file;
    S.probe = null; S.issues = []; S.layers = [];"""
new_load = """  setLoading(file) {
    S.file = file;
    S.outFile = null; S.outMB = 0; S.doneCount = 0; S.hasIssues = false;
    elFix.textContent = '开始修复';
    S.probe = null; S.issues = []; S.layers = [];"""
if old_load in s:
    s = s.replace(old_load, new_load)
    print("[7] 已加重置逻辑")

open(p, 'w', encoding='utf-8').write(s)
print()
print("完成，文件长度:", len(s))
