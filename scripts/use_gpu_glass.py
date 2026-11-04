# -*- coding: utf-8 -*-
"""把 GPU 玻璃接入界面（替换 numpy 版）

性能：3.4ms/帧，可跑 30-60fps，所以不需要缓存了。
"""

p = r'C:\Users\123\1\psd_repair_gui.py'
s = open(p, encoding='utf-8').read()

# 1) 引入 GL 模块（带降级）
s = s.replace(
    "import glass_render as gr",
    """try:
    import gl_glass as GLG
    HAS_GL = True
except Exception:
    HAS_GL = False
    GLG = None
try:
    import glass_render as gr
    HAS_CPU_GLASS = True
except Exception:
    HAS_CPU_GLASS = False
    gr = None""")

# 2) __init__ 里创建 GL 上下文
s = s.replace(
    """        # 玻璃缓存：每 GLASS_EVERY 帧重算一次，其余帧复用
        self._glass_cache = None
        self._glass_frame = -1
        self._frame_no = 0
        self._last_box_key = None""",
    """        # GPU 玻璃渲染器
        self.gl = None
        self._glass_boxes = []
        self._frame_no = 0""")

# 3) 替换 _glass 方法：改为记录面板，最后统一 GPU 渲染
start = s.find("    # 玻璃重算间隔（帧）。背景在动，玻璃不必每帧重算")
end = s.find("    def _pill(self, img, box, color, alpha=235):")
assert start > 0 and end > start

new_glass = '''    def _glass(self, img, frost, box, radius, white=0.12, shadow=True,
               material=None):
        """真玻璃（GPU）。这里只登记面板，最后统一在 _compose 末尾渲染。"""
        x1, y1, x2, y2 = [int(round(v)) for v in box]
        W, H = img.size
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(W, x2), min(H, y2)
        if x2 - x1 < 12 or y2 - y1 < 12:
            return
        kind = material or "panel"
        tint_map = {"panel": 0.10, "dock": 0.075, "small": 0.09,
                    "button": 0.14, "accent": 0.30}
        self._glass_boxes.append({
            "x1": x1, "y1": y1, "x2": x2, "y2": y2,
            "radius": int(radius),
            "tint": tint_map.get(kind, 0.10),
            "refraction": 0.90 if kind != "button" else 0.55,
            "blur": 0.20,
            "dispersion": 0.60 if kind != "button" else 0.35,
            "opacity": 1.0,
        })

'''
s = s[:start] + new_glass + s[end:]

open(p, 'w', encoding='utf-8').write(s)
print("_glass 已改为 GPU 登记")
