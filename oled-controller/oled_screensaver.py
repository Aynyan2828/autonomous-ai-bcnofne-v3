import random
import time
import math
from PIL import ImageDraw, ImageFont

class BCNOFNeScreenSaver:
    def __init__(self, width=128, height=64):
        self.width = width
        self.height = height
        self.frame_count = 0
        
        # 固有状態
        self.wave_phase = 0
        self.wave_phase2 = 0
        self.ship_x = 80
        self.ship_y = 0
        self.ship_tilt = 0
        
        # 焼け防止用オフセット
        self.burn_offset_x = 0
        self.burn_offset_y = 0
        self.last_offset_change = time.time()
        
        # 星空の状態 (x, y, type: 0=small, 1=twinkle)
        self.stars = [
            {"x": random.randint(0, width-1), "y": random.randint(0, 40), "type": random.randint(0, 1), "p": random.random() * math.pi}
            for _ in range(15)
        ]
        
        # ロゴ周辺の粒子
        self.particles = [
            {"x": 20 + random.randint(-15, 15), "y": 15 + random.randint(-10, 10), "vx": random.uniform(-0.5, 0.5), "vy": random.uniform(-0.5, 0.5)}
            for _ in range(8)
        ]
        
        # 演出状態: 0=NORMAL, 1=SILENCE (Logo only), 2=BLACKOUT
        self.mode = 0
        self.last_mode_change = time.time()
        self.is_blackout = False

    def update(self):
        """内部状態を更新する"""
        self.frame_count += 1
        
        # 波の位相
        self.wave_phase += 0.08
        self.wave_phase2 += 0.12
        
        # 星の点滅
        for s in self.stars:
            s["p"] += 0.05
            
        # 粒子の移動
        for p in self.particles:
            p["x"] += p["vx"]
            p["y"] += p["vy"]
            if abs(p["x"] - 20) > 20: p["vx"] *= -1
            if abs(p["y"] - 15) > 15: p["vy"] *= -1
            
        # 船の移動
        self.ship_x = 80 + math.sin(self.wave_phase * 0.4) * 10
            
        # 演出フェーズの切り替え
        now = time.time()
        cycle_time = now - self.last_mode_change
        
        if self.mode == 0: # NORMAL (45s)
            if cycle_time > 45:
                self.mode = 1
                self.last_mode_change = now
        elif self.mode == 1: # SILENCE (Logo only) (10s)
            if cycle_time > 10:
                self.mode = 2
                self.is_blackout = True
                self.last_mode_change = now
        elif self.mode == 2: # BLACKOUT (2s)
            if cycle_time > 2:
                self.mode = 0
                self.is_blackout = False
                self.last_mode_change = now
                # 暗転明けにオフセット変更
                self.burn_offset_x = random.randint(-4, 4)
                self.burn_offset_y = random.randint(-2, 2)

    def _draw_celestial_logo(self, draw, x, y, ox, oy, scale=1.0):
        """月と船が融合した幻想的なロゴを描画"""
        # 月 (三日月)
        draw.arc([x-10+ox, y-10+oy, x+10+ox, y+10+oy], 40, 320, fill=255, width=1)
        # ロゴ内の小さな船のシルエット
        draw.line([x-2+ox, y+2+oy, x+6+ox, y+2+oy], fill=255) # 船体
        draw.line([x+ox, y+2+oy, x+ox, y-4+oy], fill=255) # マスト
        draw.line([x+ox, y-4+oy, x+4+ox, y+oy], fill=255) # 帆

    def draw(self, draw: ImageDraw.Draw, font=None):
        """Celestial Voyage Mode を描画するバイ"""
        if self.is_blackout:
            return

        ox = self.burn_offset_x
        oy = self.burn_offset_y
        
        logo_center_x, logo_center_y = 20, 15

        # 1. 星空 (NORMAL / SILENCE)
        for s in self.stars:
            if s["type"] == 0:
                if math.sin(s["p"]) > 0: draw.point((s["x"] + ox, s["y"] + oy), fill=255)
            else:
                sz = 1 if math.sin(s["p"]) > 0.5 else 0
                if sz > 0: draw.point((s["x"] + ox, s["y"] + oy), fill=255)

        # 2. 粒子の演出 (Logo周辺)
        for p in self.particles:
            if random.random() > 0.3:
                draw.point((p["x"] + ox, p["y"] + oy), fill=255)

        # 3. 波の描画 (NORMAL時のみ)
        ship_wave_y = 52
        if self.mode == 0:
            # 遠景の波
            for x in range(0, self.width, 4):
                yw = 48 + math.sin(x * 0.1 + self.wave_phase) * 3
                draw.point((x + ox, yw + oy), fill=255)
            
            # 近景の波
            wave_points = []
            for x in range(-5, self.width + 5, 2):
                yw = 54 + math.sin(x * 0.08 + self.wave_phase2) * 5
                wave_points.append((x+ox, yw+oy))
                if abs(x - self.ship_x) < 2:
                    ship_wave_y = yw
            
            if len(wave_points) > 1:
                draw.line(wave_points, fill=255, width=1)
                # 水面反射の歪み用領域
                for i in range(0, len(wave_points)-1, 4):
                    px, py = wave_points[i]
                    draw.point((px, py+2), fill=255)

        # 4. 水面反射 (ロゴの真下に)
        reflection_y_base = 56
        if self.mode in [0, 1]:
            # 波のゆらぎに応じて反射を左右にずらす
            reflect_offset = math.sin(self.wave_phase2) * 2
            # 反射された月 (間引いて描画して透け感を出す)
            ry = reflection_y_base
            draw.arc([logo_center_x-8+ox+reflect_offset, ry+oy, logo_center_x+8+ox+reflect_offset, ry+12+oy], 180, 0, fill=255)
            if self.frame_count % 2 == 0:
                draw.line([logo_center_x-5+ox+reflect_offset, ry+5+oy, logo_center_x+5+ox+reflect_offset, ry+5+oy], fill=255)

        # 5. セレスティアル・ロゴ
        self._draw_celestial_logo(draw, logo_center_x, logo_center_y, ox, oy)

        # 6. 船 (NORMAL時のみ)
        if self.mode == 0:
            sx, sy = self.ship_x, ship_wave_y - 2
            tilt = math.sin(self.wave_phase2) * 0.15
            
            def rot(px, py, cx, cy, angle):
                s, c = math.sin(angle), math.cos(angle)
                nx = (px - cx) * c - (py - cy) * s + cx
                ny = (px - cx) * s + (py - cy) * c + cy
                return nx + ox, ny + oy

            # 船体
            hull = [
                rot(sx-8, sy, sx, sy, tilt),
                rot(sx+10, sy-1, sx, sy, tilt),
                rot(sx+7, sy+4, sx, sy, tilt),
                rot(sx-6, sy+4, sx, sy, tilt)
            ]
            draw.polygon(hull, outline=255, fill=0)
            # マスト
            draw.line(rot(sx, sy, sx, sy, tilt) + rot(sx, sy-10, sx, sy, tilt), fill=255)
            # 帆
            draw.polygon([rot(sx+1, sy-9, sx, sy, tilt), rot(sx+8, sy-5, sx, sy, tilt), rot(sx+1, sy-2, sx, sy, tilt)], outline=255)
            # 船尾灯 (小さな点明滅)
            if self.frame_count % 10 < 7:
                draw.point(rot(sx-8, sy+1, sx, sy, tilt), fill=255)

        # 7. テキスト演出 (画像と同じ Crypto Ark : BCNOFNe)
        if self.mode == 0:
            # 遠くの水平線付近に薄っすら表示
            draw.text((35+ox, 35+oy), "Crypto Ark : BCNOFNe", fill=255)
        elif self.mode == 1:
            # 静寂フェーズでは中央に
            draw.text((32+ox, 30+oy), "Celestial Voyage", fill=255)
            draw.text((35+ox, 40+oy), "BCNOFNe", fill=255)
