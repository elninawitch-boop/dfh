# -*- coding: utf-8 -*-
"""修复两个问题：
1. 主题切换只换文字色，背景光晕不变 -> 每个主题给独立配色
2. 按钮禁用态没有视觉区分 -> 明显灰化
"""
p = r'C:\Users\123\1\qt_ui\index.html'
s = open(p, encoding='utf-8').read()

# ---------- 1. 主题配色 ----------
old_theme = """const THEMES = ['冰蓝青', '紫蓝粉', '红黑', '石墨'];
const DARK = { '红黑': true };"""

new_theme = """const THEMES = ['冰蓝青', '紫蓝粉', '红黑', '石墨'];

/* 每个主题一套完整配色：底色 + 三个光斑色 */
const THEME_COLORS = {
  '冰蓝青': {
    base: '#f2f5fa',
    b1: '#5c7cf0',   // 主光斑：蓝
    b2: '#8f74ee',   // 副光斑：紫
    b3: '#7ba7f5',   // 第三光斑：浅蓝
    dark: false
  },
  '紫蓝粉': {
    base: '#faf5fc',
    b1: '#a06ef0',   // 紫
    b2: '#e868c8',   // 粉
    b3: '#6b8ef5',   // 蓝
    dark: false
  },
  '红黑': {
    base: '#150b0b',
    b1: '#b8302a',   // 深红
    b2: '#7d1a16',   // 暗红
    b3: '#5a1210',   // 极暗红
    dark: true
  },
  '石墨': {
    base: '#eef0f4',
    b1: '#8b9ab8',   // 冷灰蓝
    b2: '#a8b4c8',   // 浅灰
    b3: '#6e7d99',   // 深灰
    dark: false
  }
};"""
if old_theme in s:
    s = s.replace(old_theme, new_theme)
    print("已加入主题配色表")
else:
    print("!! 主题表锚点未找到")

# ---------- 2. setTheme 实现 ----------
old_set = """function setTheme(name) {
  S.theme = name;
  $('theme-label').textContent = name;
  const dark = !!DARK[name];
  document.body.classList.toggle('dark', dark);
}"""

new_set = """function setTheme(name) {
  const c = THEME_COLORS[name] || THEME_COLORS['冰蓝青'];
  S.theme = name;
  $('theme-label').textContent = name;

  // 文字颜色：深色背景用白，浅色用黑
  document.body.classList.toggle('dark', c.dark);

  // 背景底色
  const aurora = document.getElementById('aurora');
  aurora.style.setProperty('--bg-base', c.base);

  // 三个光斑颜色
  document.querySelector('.b1').style.background = c.b1;
  document.querySelector('.b2').style.background = c.b2;
  document.querySelector('.b3').style.background = c.b3;

  // 深色主题时光斑要更暗一些，避免刺眼
  const blobs = document.querySelectorAll('.blob');
  blobs.forEach(function(b){
    b.style.opacity = c.dark ? '0.55' : '0.85';
  });

  console.log('[theme] 切换到', name, c);
}"""

if old_set in s:
    s = s.replace(old_set, new_set)
    print("已重写 setTheme")
else:
    print("!! setTheme 锚点未找到，尝试正则")
    import re
    s = re.sub(
        r'function setTheme\(name\) \{.*?\n\}',
        new_set, s, count=1, flags=re.S)
    print("  已用正则替换")

# ---------- 3. 按钮禁用态明显灰化 ----------
old_btn = """.btn:disabled { opacity:.45; cursor:default; transform:none; }"""
new_btn = """.btn:disabled {
  opacity:.40;
  cursor:not-allowed;
  transform:none !important;
  background:rgba(200,210,225,.45) !important;
  border-color:rgba(180,195,215,.5) !important;
  box-shadow:none !important;
  backdrop-filter:blur(8px);
  color:rgba(0,0,0,.45) !important;
}
body.dark .btn:disabled {
  background:rgba(255,255,255,.10) !important;
  border-color:rgba(255,255,255,.14) !important;
  color:rgba(255,255,255,.40) !important;
}"""
if old_btn in s:
    s = s.replace(old_btn, new_btn)
    print("已强化禁用态样式")
else:
    print("!! 按钮样式锚点未找到")

open(p, 'w', encoding='utf-8').write(s)
print("\n完成，文件长度:", len(s))
