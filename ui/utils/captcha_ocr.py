# # -*- coding: utf-8 -*-
# """验证码 OCR 自动识别（数学算式验证码）
#
# 识别登录页的数学算式验证码（形如 "8/1=?"、"3+1=?"、"6-1=?"、"8*2=?"），
# 返回算式计算结果（答案）。
#
# 方案：深蓝像素提取 -> 列阈值断开细连接 -> 连通域分割 ->
#       数字1/运算符/数字2 定位 -> 运算符形态学判断 + 数字 OCR 识别 -> 计算答案。
# """
#
# """
# 管理端已全量更换企业微信扫码，所以这个模块无效了，但有存在价值
# """
# import io
# import math
# import re
# from collections import deque
#
# import ddddocr
# import numpy as np
# from PIL import Image
#
# from ui.utils.logger import logger
#
# # ddddocr 模型只初始化一次（加载较慢）
# _ocr = ddddocr.DdddOcr(show_ad=False)
#
# # ddddocr 对数字/符号的常见误读映射（用于多级回退）
# _NUM_MAPPING = {
#     "f": "1", "s": "5", "S": "5", "o": "0", "O": "0", "t": "7",
#     "l": "1", "i": "1", "I": "1", "g": "8", "b": "6", "z": "2", "Z": "2",
# }
#
#
# def _num_from_text(text):
#     """从文本提取第一个数字字符"""
#     nums = re.findall(r"\d", text)
#     return nums[0] if nums else None
#
#
# def solve(raw_bytes):
#     """识别数学算式验证码图片（bytes），返回答案字符串；失败返回 None"""
#     try:
#         img = Image.open(io.BytesIO(raw_bytes)).convert("RGB")
#     except Exception:
#         logger.error("验证码图片解码失败")
#         return None
#
#     arr = np.array(img)
#     r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
#     # 深蓝核心像素提取（3D 立体字，排除灰色阴影和背景）
#     mask = (b > 150) & (r < 100) & (g < 100)
#     m = mask.copy()
#     # 列阈值断开字符间的细连接（3D 阴影边缘）
#     colsum = m.sum(axis=0)
#     for x in range(m.shape[1]):
#         if colsum[x] < 3:
#             m[:, x] = False
#
#     H, W = m.shape
#     visited = np.zeros((H, W), dtype=bool)
#     comps = []
#     for y in range(H):
#         for x in range(W):
#             if m[y, x] and not visited[y, x]:
#                 q = deque([(x, y)])
#                 visited[y, x] = True
#                 xs, ys = [x], [y]
#                 while q:
#                     cx, cy = q.popleft()
#                     for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
#                         nx, ny = cx + dx, cy + dy
#                         if 0 <= nx < W and 0 <= ny < H and m[ny, nx] and not visited[ny, nx]:
#                             visited[ny, nx] = True
#                             q.append((nx, ny))
#                             xs.append(nx); ys.append(ny)
#                 if len(xs) >= 4:
#                     comps.append((min(xs), max(xs), min(ys), max(ys), len(xs), xs, ys))
#     comps.sort(key=lambda c: c[0])
#     if len(comps) < 3:
#         logger.warning(f"验证码字符分割失败（{len(comps)}块）")
#         return None
#
#     def crop_rec(x0, x1, y0, y1):
#         ex = 4
#         box = (max(0, x0 - ex), max(0, y0 - ex), min(W, x1 + 1 + ex), min(H, y1 + 1 + ex))
#         crop = img.crop(box)
#         crop = crop.resize((crop.width * 6, crop.height * 6), Image.LANCZOS)
#         buf = io.BytesIO()
#         crop.save(buf, format="PNG")
#         return _ocr.classification(buf.getvalue())
#
#     # 数字1 = 第 1 个连通域
#     c0 = comps[0]
#     d1 = _num_from_text(crop_rec(c0[0], c0[1], c0[2], c0[3]))
#
#     # 运算符 = 第 2 个连通域（形态学判断：宽高比 + 方向直方图）
#     c = comps[1]
#     x0, x1, y0, y1, n, xs, ys = c
#     w, h = x1 - x0 + 1, y1 - y0 + 1
#     ar = w / max(1, h)
#     cx, cy = np.mean(xs), np.mean(ys)
#     cnt = {"h": 0, "v": 0}
#     for x, y in zip(xs, ys):
#         ang = math.degrees(math.atan2(y - cy, x - cx)) % 180
#         if ang <= 22.5 or ang >= 157.5:
#             cnt["h"] += 1
#         elif 67.5 <= ang <= 112.5:
#             cnt["v"] += 1
#     hr, vr = cnt["h"] / n, cnt["v"] / n
#     if ar < 0.6:
#         op = "/"
#     elif ar > 1.3:
#         op = "-"
#     elif hr > 0.25 and vr > 0.25:
#         op = "+"
#     else:
#         op = "*"
#
#     # 数字2 = 第 3 个连通域（多级回退）
#     d2 = None
#     c2 = comps[2]
#     d2x0, d2x1, d2y0, d2y1 = c2[0], c2[1], c2[2], c2[3]
#     # 级别1：顶部笔画切分（数字有顶部，= 没有），去掉 = 粘连
#     in_seg = False
#     right_edge = d2x0
#     for x in range(d2x0, d2x1 + 1):
#         has_top = any(m[y, x] for y in range(d2y0, min(d2y0 + 6, H)))
#         if has_top:
#             in_seg = True
#             right_edge = x
#         elif in_seg:
#             break
#     if in_seg:
#         rx = min(right_edge + 4, d2x1)
#         d2 = _num_from_text(crop_rec(d2x0, rx, d2y0, d2y1))
#     # 级别2：整图识别 + 运算符后字符映射
#     if d2 is None:
#         t = _ocr.classification(raw_bytes)
#         for opc in "/+*-":
#             idx = t.find(opc)
#             if idx >= 0 and idx + 1 < len(t):
#                 nxt = t[idx + 1]
#                 if nxt.isdigit():
#                     d2 = nxt
#                 elif nxt.lower() in _NUM_MAPPING:
#                     d2 = _NUM_MAPPING[nxt.lower()]
#                 break
#         if d2 is None:
#             nums = re.findall(r"\d", t)
#             if len(nums) >= 2:
#                 d2 = nums[1]
#     # 级别3：连通域2 完整识别
#     if d2 is None:
#         d2 = _num_from_text(crop_rec(d2x0, d2x1, d2y0, d2y1))
#
#     if d1 is None or d2 is None:
#         logger.warning(f"验证码数字识别失败 d1={d1!r} d2={d2!r}")
#         return None
#
#     a, b = int(d1), int(d2)
#     if op == "/":
#         ans = a // b if b != 0 else 0
#     elif op == "*":
#         ans = a * b
#     elif op == "-":
#         ans = a - b
#     else:
#         ans = a + b
#     logger.info(f"验证码识别: {a}{op}{b}={ans}")
#     return str(ans)
