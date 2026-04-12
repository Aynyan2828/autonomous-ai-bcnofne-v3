import random
import time
import math
from PIL import ImageDraw, ImageFont

class BCNOFNeScreenSaver:
    def __init__(self, width=128, height=64):
        self.width = width
        self.height = height
        self.frame_count = 0
        
        # 定数
        self.MOON_X = 24
        self.MOON_Y = 18
        
        # 波の状態
        self.wave_phase = 0
        self.wave_phase_fast = 0
        self.amplitude_factor = 1.0
        
        # 船の状態
        self.ship_x = 64 # 中央付近へ
        self.ship_y = 40
        self.ship_tilt = 0
        self.last_ship_y = 40
        
        # 飛沫（パーティクル）管理
        self.particles = [] # {"x", "y", "vx", "vy", "life"}
        self.MAX_PARTICLES = 60 # 増量！幅広く飛沫を飛ばす
        
        # 焼け防止
        self.burn_offset_x = 0
        self.burn_offset_y = 0
        self.last_offset_change = time.time()
        
        # 星空
        self.stars = [
            {"x": random.randint(0, width-1), "y": random.randint(0, 32), "p": random.random() * math.pi}
            for _ in range(15)
        ]
        
        # 暗転管理
        self.is_blackout = False
        self.last_blackout_ts = time.time()

    def _generate_storm_wave(self, x, phase, phase_fast, amp_mod):
        """北斎風の鋭い波形生成"""
        base_y = 46
        sine1 = math.sin(x * 0.07 + phase)
        # 山を鋭く、谷を浅く
        wave1 = math.pow(abs(sine1), 0.55) * (15.0 if sine1 > 0 else -6.0)
        wave2 = math.sin(x * 0.18 + phase_fast) * 4
        return base_y + (wave1 + wave2) * amp_mod

    def update(self):
        self.frame_count += 1
        self.wave_phase += 0.13
        self.wave_phase_fast += 0.28
        self.amplitude_factor = 1.0 + math.sin(self.frame_count * 0.05) * 0.3
        
        # パーティクルの更新
        new_particles = []
        for p in self.particles:
            p["x"] += p["vx"]
            p["y"] += p["vy"]
            p["vy"] += 0.45 # 少し重力を強めに
            p["life"] -= 1
            if p["life"] > 0 and 0 <= p["x"] < self.width and 0 <= p["y"] < self.height:
                new_particles.append(p)
        self.particles = new_particles
        
        # 焼け防止
        now = time.time()
        if now - self.last_offset_change > 15:
            self.burn_offset_x = random.randint(-4, 4)
            self.burn_offset_y = random.randint(-2, 2)
            self.last_offset_change = now
            
        # 暗転
        if now - self.last_blackout_ts > 50:
            self.is_blackout = True
            if now - self.last_blackout_ts > 51.5:
                self.is_blackout = False
                self.last_blackout_ts = now

    def _spawn_spray(self, x, y, count=1, heavy=False):
        for _ in range(count):
            if len(self.particles) < self.MAX_PARTICLES:
                vx = random.uniform(-2.0, 2.0) if heavy else random.uniform(-1.0, 1.0)
                vy = random.uniform(-4.0, -1.0) if heavy else random.uniform(-2.0, -0.5)
                self.particles.append({
                    "x": x, "y": y,
                    "vx": vx,
                    "vy": vy,
                    "life": random.randint(8, 20)
                })

    def _draw_pure_crescent(self, draw, x, y, ox, oy):
        """ピュアな三日月"""
        r_outer = 13
        draw.chord([x-r_outer+ox, y-r_outer+oy, x+r_outer+ox, y+r_outer+oy], 40, 320, fill=255)
        r_inner = 12
        draw.chord([x-r_inner+ox+5, y-r_inner+oy, x+r_inner+ox+5, y+r_inner+oy], 0, 360, fill=0)

    def draw(self, draw: ImageDraw.Draw, font=None):
        if self.is_blackout: return
        ox, oy = self.burn_offset_x, self.burn_offset_y

        # 1. 星空
        for s in self.stars:
            if math.sin(s["p"] + self.frame_count * 0.04) > 0.4:
                draw.point((s["x"]+ox, s["y"]+oy), fill=255)

        # 2. 三日月 (左上)
        self._draw_pure_crescent(draw, self.MOON_X, self.MOON_Y, ox, oy)

        # 3. 水面反射 (シマー)
        reflect_x = self.MOON_X + ox
        for ry in range(48, self.height, 3):
            shift = math.sin(ry * 0.2 + self.wave_phase * 2) * 5
            sw = random.randint(1, 5)
            draw.line([reflect_x + shift - sw, ry+oy, reflect_x + shift + sw, ry+oy], fill=255)

        # 4. 波と船の高さ計算
        wave_points = []
        ship_current_y = 45
        ship_slope = 0
        for x in range(-10, self.width + 10, 3):
            y = self._generate_storm_wave(x, self.wave_phase, self.wave_phase_fast, self.amplitude_factor)
            wave_points.append((x+ox, y+oy))
            if abs(x - self.ship_x) < 3:
                ship_current_y = y
                y_next = self._generate_storm_wave(x + 3, self.wave_phase, self.wave_phase_fast, self.amplitude_factor)
                ship_slope = (y_next - y) / 3.0
            
            # 激しい波頭の飛沫
            if y < 38 and random.random() < 0.25:
                self._spawn_spray(x+ox, y+oy, 1, heavy=True)

        if len(wave_points) > 1:
            draw.line(wave_points, fill=255, width=1)

        # 5. 特大帆船の描画 (存在感アップ)
        target_y = ship_current_y - 2
        self.ship_y = self.ship_y * 0.4 + target_y * 0.6
        if target_y - self.last_ship_y > 3: # 衝撃検知
            self._spawn_spray(self.ship_x+ox, self.ship_y+oy, 5, heavy=True)
        self.last_ship_y = self.ship_y
        self.ship_tilt = math.atan(ship_slope) * 1.8 # 傾斜も強調

        def r(px, py):
            s, c = math.sin(self.ship_tilt), math.cos(self.ship_tilt)
            nx = (px - self.ship_x) * c - (py - self.ship_y) * s + self.ship_x
            ny = (px - self.ship_x) * s + (py - self.ship_y) * c + self.ship_y
            return nx + ox, ny + oy

        cx, cy = self.ship_x, self.ship_y
        # 巨大船体 (スケールアップ)
        hull = [r(cx-16, cy), r(cx+18, cy-1), r(cx+14, cy+7), r(cx-13, cy+7)]
        draw.polygon(hull, outline=255, fill=0)
        
        # バランスよい帆とマスト
        # メインマスト (中央)
        draw.line(r(cx, cy) + r(cx, cy-18), fill=255)
        draw.polygon([r(cx+1, cy-17), r(cx+10, cy-10), r(cx+1, cy-3)], outline=255)
        # 前方マスト
        draw.line(r(cx-7, cy) + r(cx-7, cy-12), fill=255)
        draw.polygon([r(cx-6, cy-11), r(cx, cy-7), r(cx-6, cy-3)], outline=255)
        
        # 航海灯
        if self.frame_count % 10 < 7: draw.point(r(cx-15, cy+1), fill=255)

        # 6. 飛沫パーティクルの描画
        for p in self.particles: 
            draw.point((p["x"], p["y"]), fill=255)
            # 少し軌跡を描いて躍動感を出す
            if random.random() > 0.5:
                draw.point((p["x"]-p["vx"]*0.5, p["y"]-p["vy"]*0.5), fill=255)

        # 7. テキスト演出 (見切れないように内側へ配置)
        if self.frame_count % 400 < 80:
            text_x = 48 + ox # 80から48へ大幅に左へシフト
            draw.text((text_x, 6+oy), "Crypto Ark", fill=255)
            draw.text((text_x + 5, 16+oy), ":BCNOFNe", fill=255)
