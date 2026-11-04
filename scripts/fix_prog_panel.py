# -*- coding: utf-8 -*-
"""改进进度面板交互与空状态"""
p = r'C:\Users\123\1\qt_ui\index.html'
s = open(p, encoding='utf-8').read()

# 1) 空状态提示
old = """function renderProgList() {
  if (!S.layers.length) {
    elProgList.innerHTML = '';
    return;
  }"""
new = """function renderProgList() {
  if (!S.layers.length) {
    elProgList.innerHTML =
      '<div class="prog-empty">载入 PSD 后，这里显示每个图层的处理进度</div>';
    return;
  }"""
if old in s:
    s = s.replace(old, new)
    print("已加空状态提示")
else:
    print("!! 空状态锚点未找到")

# 2) 加空状态的样式
old_css = """#prog.open #prog-list {
  max-height:300px; opacity:1; margin-top:14px;
}"""
new_css = """#prog.open #prog-list {
  max-height:320px; opacity:1; margin-top:14px;
}
.prog-empty {
  font-size:12.5px; color:var(--ink); opacity:.55;
  padding:16px 4px; text-align:center;
}"""
if old_css in s:
    s = s.replace(old_css, new_css)
    print("已加空状态样式")
else:
    print("!! CSS 锚点未找到")

# 3) 点击整块面板都能展开（不只是标题栏）
old_click = """$('prog-head').onclick = () => elProg.classList.toggle('open');"""
new_click = """/* 整块面板可点击展开/收起 */
elProg.style.cursor = 'pointer';
elProg.onclick = function(e){
  // 忽略列表内部的滚动操作
  if (e.target.closest('#prog-list') && e.target.closest('.row')) return;
  elProg.classList.toggle('open');
};"""
if old_click in s:
    s = s.replace(old_click, new_click)
    print("已改为整块可点击")
else:
    print("!! 点击锚点未找到")

# 4) 载入文件后自动展开
old_probe = """    elFix.disabled = false;
    elOpen.disabled = true;"""
new_probe = """    elFix.disabled = false;
    elOpen.disabled = true;
    // 有图层时自动展开进度面板
    if (S.layers.length) elProg.classList.add('open');"""
if old_probe in s:
    s = s.replace(old_probe, new_probe)
    print("已改为载入后自动展开")
else:
    print("!! 自动展开锚点未找到")

open(p, 'w', encoding='utf-8').write(s)
print("\n完成，文件长度:", len(s))
