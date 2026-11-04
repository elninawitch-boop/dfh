# -*- coding: utf-8 -*-
"""在 _compose 末尾调用 GPU 渲染"""

p = r'C:\Users\123\1\psd_repair_gui.py'
s = open(p, encoding='utf-8').read()

# 1) 清空登记 + 绘制后 GPU 渲染
s = s.replace(
    '''    def _compose(self, base):
        img = base.copy()
        frost = img.filter(ImageFilter.GaussianBlur(1.5))
        W, H, P = self.W, self.H, PAD''',
    '''    def _compose(self, base):
        img = base.copy()
        frost = img.filter(ImageFilter.GaussianBlur(1.5))
        W, H, P = self.W, self.H, PAD
        self._glass_boxes = []''')

# 2) 在 _draw_text 调用之后、return img 之前插入 GPU 渲染
s = s.replace(
    '''        self._draw_text(img)
        return img''',
    '''        # ---- GPU 玻璃渲染
        img = self._render_glass_gpu(img)
        self._draw_text(img)
        return img

    def _render_glass_gpu(self, img):
        """用 GPU 渲染所有登记的面板；失败则退回简单绘制"""
        if not self._glass_boxes:
            return img
        W, H = img.size
        if HAS_GL:
            try:
                if self.gl is None:
                    self.gl = GLG.GlassGL(W, H)
                elif (self.gl.width, self.gl.height) != (W, H):
                    self.gl.resize(W, H)
                self.gl.set_artwork(img)
                ptr = (int(W * 0.5 + self.mx * W * 0.3),
                       int(H * 0.5 + self.my * H * 0.3))
                out = self.gl.render(self._glass_boxes, time=self.anim_t,
                                     pointer=ptr, brightness=1.0,
                                     animate=1.0)
                return out
            except Exception:
                pass
        return self._glass_fallback(img)

    def _glass_fallback(self, img):
        """GPU 不可用时的降级：极淡白 + 细边"""
        d = ImageDraw.Draw(img, "RGBA")
        for b in self._glass_boxes:
            x1, y1, x2, y2 = b["x1"], b["y1"], b["x2"], b["y2"]
            r = b["radius"]
            d.rounded_rectangle([x1, y1, x2 - 1, y2 - 1], radius=r,
                                outline=(255, 255, 255, 170), width=1)
        return img''')

open(p, 'w', encoding='utf-8').write(s)
print("GPU 渲染已接入")
