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
        self.ship_x = 75
        self.ship_y = 40
        self.ship_tilt = 0
        self.last_ship_y = 40
        
        # 飛沫（パーティクル）管理
        self.particles = [] # {"x", "y", "vx", "vy", "life"}
        self.MAX_PARTICLES = 25
        
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
        wave1 = math.pow(abs(sine1), 0.55) * (14.0 if sine1 > 0 else -6.0)
        wave2 = math.sin(x * 0.18 + phase_fast) * 3
        return base_y + (wave1 + wave2) * amp_mod

    def update(self):
        self.frame_count += 1
        self.wave_phase += 0.1
        self.wave_phase_fast += 0.22
        self.amplitude_factor = 0.9 + math.sin(self.frame_count * 0.04) * 0.2
        
        # パーティクルの更新
        new_particles = []
        for p in self.particles:
            p["x"] += p["vx"]
            p["y"] += p["vy"]
            p["vy"] += 0.35
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

    def _spawn_spray(self, x, y, count=1):
        for _ in range(count):
            if len(self.particles) < self.MAX_PARTICLES:
                self.particles.append({
                    "x": x, "y": y,
                    "vx": random.uniform(-1.2, 1.2),
                    "vy": random.uniform(-2.2, -0.6),
                    "life": random.randint(6, 12)
                })

    def _draw_pure_crescent(self, draw, x, y, ox, oy):
        """ロゴを排除した、純粋で美しい三三日月の描画"""
        # 三日月の外円 (半径12)
        r_outer = 12
        draw.chord([x-r_outer+ox, y-r_outer+oy, x+r_outer+ox, y+r_outer+oy], 40, 320, fill=255)
        # 三日月の内側を削る円 (少し右にずらして鋭さを出す)
        r_inner = 11
        draw.chord([x-r_inner+ox+4, y-r_inner+oy, x+r_inner+ox+4, y+r_inner+oy], 0, 360, fill=0)

    def draw(self, draw: ImageDraw.Draw, font=None):
        if self.is_blackout: return
        ox, oy = self.burn_offset_x, self.burn_offset_y

        # 1. 星空
        for s in self.stars:
            if math.sin(s["p"] + self.frame_count * 0.03) > 0.5:
                draw.point((s["x"]+ox, s["y"]+oy), fill=255)

        # 2. 純粋なる三日月 (左上に孤高に輝く)
        self._draw_pure_crescent(draw, self.MOON_X, self.MOON_Y, ox, oy)

        # 3. 水面反射 (三日月の真下)
        reflect_x = self.MOON_X + ox
        for ry in range(48, self.height, 3):
            shift = math.sin(ry * 0.2 + self.wave_phase * 2) * 4
            sw = random.randint(1, 4)
            draw.line([reflect_x + shift - sw, ry+oy, reflect_x + shift + sw, ry+oy], fill=255)

        # 4. 波と船の高さ計算
        wave_points = []
        ship_current_y = 45
        ship_slope = 0
        for x in range(-5, self.width + 10, 3):
            y = self._generate_storm_wave(x, self.wave_phase, self.wave_phase_fast, self.amplitude_factor)
            wave_points.append((x+ox, y+oy))
            if abs(x - self.ship_x) < 3:
                ship_current_y = y
                y_next = self._generate_storm_wave(x + 3, self.wave_phase, self.wave_phase_fast, self.amplitude_factor)
                ship_slope = (y_next - y) / 3.0
            if y < 40 and random.random() < 0.12: # 波頂の飛沫
                self._spawn_spray(x+ox, y+oy, 1)

        if len(wave_points) > 1:
            draw.line(wave_points, fill=255, width=1)

        # 5. 大型帆船の描画 (主役は船体)
        target_y = ship_current_y - 2
        self.ship_y = self.ship_y * 0.5 + target_y * 0.5
        if target_y - self.last_ship_y > 4:
            self._spawn_spray(self.ship_x+ox, self.ship_y+oy, 3)
        self.last_ship_y = self.ship_y
        self.ship_tilt = math.atan(ship_slope) * 1.6

        def r(px, py):
            s, c = math.sin(self.ship_tilt), math.cos(self.ship_tilt)
            nx = (px - self.ship_x) * c - (py - self.ship_y) * s + self.ship_x
            ny = (px - self.ship_x) * s + (py - self.ship_y) * c + self.ship_y
            return nx + ox, ny + oy

        cx, cy = self.ship_x, self.ship_y
        # 船体
        hull = [r(cx-12, cy), r(cx+14, cy-1), r(cx+11, cy+5), r(cx-10, cy+5)]
        draw.polygon(hull, outline=255, fill=0)
        # 2本のマストと帆
        draw.line(r(cx-2, cy) + r(cx-2, cy-14), fill=255) 
        draw.line(r(cx+5, cy) + r(cx+5, cy-9), fill=255)
        draw.polygon([r(cx-1, cy-13), r(cx+6, cy-7), r(cx-1, cy-2)], outline=255)
        draw.polygon([r(cx+6, cy-8), r(cx+11, cy-5), r(cx+6, cy-2)], outline=255)
        # 航海灯
        if self.frame_count % 10 < 7: draw.point(r(cx-11, cy+1), fill=255)

        # 6. パーティクル
        for p in self.particles: draw.point((p["x"], p["y"]), fill=255)

        # 7. テキスト演出 (たまに右上に)
        if self.frame_count % 400 < 60:
            draw.text((80+ox, 6+oy), "Crypto Ark", fill=255)
            draw.text((85+ox, 16+oy), ":BCNOFNe", fill=255)
