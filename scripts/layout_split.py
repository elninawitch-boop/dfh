# -*- coding: utf-8 -*-
"""左右分栏布局：左侧主操作区，右侧信息面板"""

p = r'C:\Users\123\1\psd_repair_gui.py'
s = open(p, encoding='utf-8').read()

# 替换整个布局计算块
start = s.find('        # ---- 布局')
end = s.find('        self._draw_text(img)')
assert start > 0 and end > start

new_layout = '''        # ---- 布局：左右分栏
        head_h = 150
        top = head_h
        foot = 62
        gap = 14

        # 左栏宽度（主操作区）
        left_w = int((W - P * 2) * 0.62)
        left_x1 = P
        left_x2 = P + left_w
        right_x1 = left_x2 + 20
        right_x2 = W - P

        # 底部进度面板（横跨左侧）
        p2_col = 58
        p2_exp = int((H - top - foot) * 0.40)
        p2_h = int(p2_col + (p2_exp - p2_col) * self.expand)
        p2_bottom = H - foot
        p2_top = p2_bottom - p2_h

        # 左上：拖放区
        drop_h = 108
        self._drop_rect = (left_x1, top, left_x2, top + drop_h)

        # 操作栏
        bar_y = top + drop_h + 14
        bar_h = 36
        self._bar_rect = (left_x1, bar_y, left_x2, bar_y + bar_h)

        # 左下：检测结果
        self._panel1 = (left_x1, bar_y + bar_h + 16, left_x2,
                        p2_top - gap)
        # 底部：进度
        self._panel2 = (left_x1, p2_top, left_x2, p2_bottom)

        # 右栏：整块面板
        self._panel_right = (right_x1, top, right_x2, p2_bottom)

        # ---- 玻璃
        self._glass(img, frost, self._drop_rect, R_LG, white=0.20)
        self._glass(img, frost, self._panel1, R_LG, white=0.13)
        self._glass(img, frost, self._panel2, R_LG, white=0.13)
        self._glass(img, frost, self._panel_right, R_LG, white=0.16)

        # 主题按钮
        self._theme_btn = (W - P - 104, 40, W - P, 74)
        self._glass(img, frost, self._theme_btn, 17, white=0.26, shadow=False)

        # 按钮
        bw, bh = 112, bar_h
        self._btn_fix = (left_x2 - bw, bar_y, left_x2, bar_y + bh)
        ok = bool(self.probe)
        self._pill(img, self._btn_fix, BLUE if ok else (205, 214, 226), 240)
        x = left_x2 - bw - 10
        self._btn_dir = (x - bw, bar_y, x, bar_y + bh)
        self._glass(img, frost, self._btn_dir, 18, white=0.22, shadow=False)

        self._trim_rect = (left_x1, bar_y, left_x1 + 186, bar_y + bh)

        # 展开手柄
        hx = (left_x1 + left_x2) // 2
        self._handle = (hx - 30, p2_bottom - 16, hx + 30, p2_bottom - 2)

        self._row_area = (self._panel2[0] + 8, self._panel2[1] + 54,
                          self._panel2[2] - 8, self._panel2[3] - 20)

'''
s = s[:start] + new_layout + s[end:]

open(p, 'w', encoding='utf-8').write(s)
print("已改为左右分栏")
