import random
import time
import math
from PIL import ImageDraw, ImageFont

class BCNOFNeScreenSaver:
    def __init__(self, width=128, height=64):
        self.width = width
        self.height = height
        self.frame_count = 0
        
        # 固有レイアウト定数
        self.HORIZON_Y = 40
        self.LOGO_X = 24
        self.LOGO_Y = 20
        
        # 状態
        self.wave_phase = 0
        self.ship_x = 90
        
        # 焼け防止
        self.burn_offset_x = 0
        self.burn_offset_y = 0
        self.last_offset_change = time.time()
        
        # 星 (空 0-38)
        self.stars = [
            {"x": random.randint(0, width-1), "y": random.randint(0, 35), "p": random.random() * math.pi}
            for _ in range(20)
        ]
        
        # 粒子 (ロゴ周辺)
        self.particles = [
            {"x": 0, "y": 0, "angle": random.random() * 2 * math.pi, "dist": random.randint(12, 22), "speed": random.uniform(0.02, 0.05)}
            for _ in range(6)
        ]
        
        self.mode = 0 # 0:NORMAL, 1:SILENCE, 2:BLACKOUT
        self.last_mode_change = time.time()
        self.is_blackout = False

    def update(self):
        self.frame_count += 1
        self.wave_phase += 0.07
        
        # 星の点滅
        for s in self.stars:
            s["p"] += 0.04
            
        # 粒子の回転移動
        for p in self.particles:
            p["angle"] += p["speed"]
            
        # 演出サイクル 
        now = time.time()
        cycle = now - self.last_mode_change
        if self.mode == 0 and cycle > 40:
            self.mode = 1
            self.last_mode_change = now
        elif self.mode == 1 and cycle > 15:
            self.mode = 2
            self.is_blackout = True
            self.last_mode_change = now
        elif self.mode == 2 and cycle > 2:
            self.mode = 0
            self.is_blackout = False
            self.last_mode_change = now
            self.burn_offset_x = random.randint(-5, 5)
            self.burn_offset_y = random.randint(-3, 3)

    def _draw_sharp_logo(self, draw, x, y, ox, oy):
        """より大きく鋭い三日月型ロゴを描画"""
        # 三日月 (外弧)
        draw.arc([x-14+ox, y-14+oy, x+14+ox, y+14+oy], 30, 330, fill=255, width=1)
        # 三日月 (内弧 - 鋭くするために少しずらす)
        draw.arc([x-10+ox, y-14+oy, x+16+ox, y+14+oy], 60, 300, fill=0, width=2)
        
        # 方舟シンボル (ロゴ内部)
        draw.line([x-3+ox, y+1+oy, x+5+ox, y+1+oy], fill=255)
        draw.line([x+ox, y+1+oy, x+ox, y-6+oy], fill=255)
        draw.polygon([ (x+ox, y-6+oy), (x+5+ox, y-1+oy), (x+ox, y-1+oy) ], outline=255)

    def draw(self, draw: ImageDraw.Draw, font=None):
        if self.is_blackout:
            return

        ox, oy = self.burn_offset_x, self.burn_offset_y
        
        # --- 1. 空の描画 (Stars & Particles) ---
        for s in self.stars:
            if math.sin(s["p"]) > 0.4:
                draw.point((s["x"]+ox, s["y"]+oy), fill=255)
                
        # ロゴ周辺の粒子
        for p in self.particles:
            px = self.LOGO_X + math.cos(p["angle"]) * p["dist"]
            py = self.LOGO_Y + math.sin(p["angle"]) * p["dist"]
            if random.random() > 0.2:
                draw.point((px+ox, py+oy), fill=255)

        # --- 2. ロゴの描画 ---
        self._draw_sharp_logo(draw, self.LOGO_X, self.LOGO_Y, ox, oy)

        # --- 3. 水平線の描画 ---
        draw.line([0+ox, self.HORIZON_Y+oy, self.width+ox, self.HORIZON_Y+oy], fill=255)

        # --- 4. 水面反射 (シマー効果) ---
        # ロゴの真下から垂直に伸びる光の筋
        if self.mode in [0, 1]:
            reflect_x = self.LOGO_X + ox
            for ry in range(self.HORIZON_Y + 1, self.height, 2):
                # 波の位相で横に揺らす
                shimmer_w = random.randint(2, 6)
                shimmer_x = reflect_x + math.sin(ry * 0.2 + self.wave_phase * 2) * 3
                # 遠くほど細く、近くほど少し太く
                draw.line([shimmer_x - shimmer_w//2, ry+oy, shimmer_x + shimmer_w//2, ry+oy], fill=255)

        # --- 5. 海の描画 (Waves & Sea) ---
        if self.mode == 0:
            # 波の線
            wave_points = []
            ship_wave_y = self.HORIZON_Y + 8
            for x in range(-5, self.width + 5, 3):
                yw = self.HORIZON_Y + 6 + math.sin(x * 0.1 + self.wave_phase) * 4
                wave_points.append((x+ox, yw+oy))
                if abs(x - self.ship_x) < 3:
                    ship_wave_y = yw
            
            if len(wave_points) > 1:
                draw.line(wave_points, fill=255, width=1)
                
            # 船の描画 (右側・波に同期)
            sx, sy = self.ship_x + ox, ship_wave_y - 2 + oy
            draw.polygon([(sx-6, sy), (sx+8, sy-1), (sx+6, sy+3), (sx-4, sy+3)], outline=255, fill=0)
            draw.line([(sx, sy), (sx, sy-8)], fill=255) # Mast
            draw.line([(sx, sy-8), (sx+5, sy-3)], fill=255) # Sail
            if self.frame_count % 8 < 5:
                draw.point((sx-6, sy+1), fill=255) # Stern light

        # --- 6. テキストの配置 (作品名とタイトル) ---
        if self.mode == 0:
            # 下部の深い海の部分に配置
            draw.text((65+ox, 48+oy), "Crypto Ark", fill=255)
            draw.text((70+ox, 56+oy), "BCNOFNe", fill=255)
        elif self.mode == 1:
            # 静寂フェーズ：メッセージを中央に
            draw.text((45+ox, 25+oy), "Celestial Voyage", fill=255)
            draw.text((55+ox, 35+oy), ". . . .", fill=255)
