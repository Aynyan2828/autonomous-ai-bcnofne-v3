import random
import time
import math
from PIL import ImageDraw, ImageFont

class BCNOFNeScreenSaver:
    def __init__(self, width=128, height=64):
        self.width = width
        self.height = height
        self.frame_count = 0
        self.last_update_ts = time.time()
        
        # 月の状態 (軌道運行)
        self.moon_progress = 0.0
        # 1/4に減速 (0.45 -> 0.11)
        self.moon_orbit_speed = 0.11
        self.moon_radius = 10
        self.moon_x = -20
        self.moon_y = 50
        
        # 波の状態
        self.wave_phase = 0
        self.wave_phase_fast = 0
        self.amplitude_factor = 1.0
        self.HORIZON_Y = 46
        self.dt = 0.05 # 初期化
        
        # 船の状態
        self.ship_x = 64
        self.ship_y = 40
        self.ship_tilt = 0
        self.last_ship_y = 40
        
        # 飛沫管理
        self.particles = []
        self.MAX_PARTICLES = 60
        
        # 焼け防止
        self.burn_offset_x = 0
        self.burn_offset_y = 0
        self.last_offset_change = time.time()
        
        # 星空
        self.stars = [
            {"x": random.randint(0, width-1), "y": random.randint(0, 32), "p": random.random() * math.pi}
            for _ in range(15)
        ]
        
        # 暗転
        self.is_blackout = False
        self.last_blackout_ts = time.time()

    def update(self):
        now = time.time()
        dt = now - self.last_update_ts
        self.last_update_ts = now
        # 処理落ち等でdtが異常に大きくなるのを防ぐ
        dt = min(dt, 0.1)
        
        self.frame_count += 1
        
        # 1. 月の軌道更新 (1/4減速)
        self.dt = dt
        self.moon_progress += self.moon_orbit_speed * dt
        if self.moon_progress > 1.6:
            self.moon_progress = 0.0
            
        p = self.moon_progress
        if p <= 1.0:
            self.moon_x = -20 + (self.width + 40) * p
            self.moon_y = 10 + 152 * (p - 0.5)**2
        else:
            self.moon_y = 80
        
        # 2. 波と波の更新 (1/4減速)
        # 18.0 -> 4.5 / 37.5 -> 9.4
        self.wave_phase += 4.5 * dt
        self.wave_phase_fast += 9.4 * dt
        self.amplitude_factor = 0.9 + math.sin(now * 0.3) * 0.25
        
        # 3. パーティクル
        new_particles = []
        for p_obj in self.particles:
            p_obj["x"] += p_obj["vx"] * (dt * 30)
            p_obj["y"] += p_obj["vy"] * (dt * 30)
            p_obj["vy"] += 0.4 * (dt * 30)
            p_obj["life"] -= 1.0 * (dt * 30)
            if p_obj["life"] > 0 and 0 <= p_obj["x"] < self.width and 0 <= p_obj["y"] < self.height:
                new_particles.append(p_obj)
        self.particles = new_particles
        
        # 4. 焼け防止
        if now - self.last_offset_change > 15:
            self.burn_offset_x = random.randint(-4, 4)
            self.burn_offset_y = random.randint(-2, 2)
            self.last_offset_change = now
            
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
                    "vx": random.uniform(-1.5, 1.5),
                    "vy": random.uniform(-2.5, -0.8),
                    "life": random.uniform(6, 15)
                })

    def _draw_3d_moon_logic(self, draw, x, y, ox, oy):
        """3D回転 (1/4減速)"""
        r = self.moon_radius
        # 4.5 -> 1.12
        phi = time.time() * 1.12
        
        draw.ellipse([x-r+ox, y-r+oy, x+r+ox, y+r+oy], fill=255)
        shadow_w = math.sin(phi) * r * 2.2
        draw.ellipse([x+ox-r+shadow_w, y+oy-r-1, x+ox+r+shadow_w, y+oy+r+1], fill=0)

    def draw(self, draw: ImageDraw.Draw, font=None):
        if self.is_blackout: return
        ox, oy = self.burn_offset_x, self.burn_offset_y
        now = time.time()

        # LAYER 1: 星空
        for s in self.stars:
            if math.sin(s["p"] + now * 1.0) > 0.5:
                draw.point((s["x"]+ox, s["y"]+oy), fill=255)

        # LAYER 2: 軌道上の月
        if self.moon_y < self.height + 15:
            self._draw_3d_moon_logic(draw, self.moon_x, self.moon_y, ox, oy)

        # LAYER 3: 海のオクルージョン
        draw.rectangle([0, self.HORIZON_Y + oy, self.width, self.height], fill=0)

        # LAYER 4: 水面反射
        if self.moon_progress <= 1.0 and self.moon_y < self.HORIZON_Y:
            reflect_x = self.moon_x + ox
            for ry in range(self.HORIZON_Y + 2, self.height, 4):
                shift = math.sin(ry * 0.2 + self.wave_phase * 2) * 4
                sw = random.randint(1, 4)
                draw.line([reflect_x + shift - sw, ry+oy, reflect_x + shift + sw, ry+oy], fill=255)

        # LAYER 5: 波
        wave_points = []
        ship_current_y = 45
        ship_slope = 0
        for x in range(-10, self.width + 20, 3):
            sine1 = math.sin(x * 0.07 + self.wave_phase)
            wave1 = math.pow(abs(sine1), 0.55) * (15.0 if sine1 > 0 else -6.0)
            wave2 = math.sin(x * 0.18 + self.wave_phase_fast) * 4
            y = self.HORIZON_Y + (wave1 + wave2) * self.amplitude_factor
            
            wave_points.append((x+ox, y+oy))
            if abs(x - self.ship_x) < 3:
                ship_current_y = y
                s_n = math.sin((x+3) * 0.07 + self.wave_phase)
                w_n = math.pow(abs(s_n), 0.55) * (15.0 if s_n > 0 else -6.0)
                y_next = self.HORIZON_Y + (w_n + math.sin((x+3) * 0.18 + self.wave_phase_fast) * 4) * self.amplitude_factor
                ship_slope = (y_next - y) / 3.0
                
            if y < 40 and random.random() < 0.2: # 飛沫率アップ
                self._spawn_spray(x+ox, y+oy, 1)

        if len(wave_points) > 1:
            draw.line(wave_points, fill=255, width=1)

        # 6. 船 (波に深く沈ませ、左右にも揺らす)
        # 左右のドリフトを追加
        self.ship_x = 64 + math.sin(now * 0.4) * 10
        
        # 船の前後3点の平均高さを計算して、より安定して波に乗せる
        y_center = ship_current_y
        y_fore = self._generate_storm_wave(self.ship_x + 10, self.wave_phase, self.wave_phase_fast, self.amplitude_factor)
        y_aft = self._generate_storm_wave(self.ship_x - 10, self.wave_phase, self.wave_phase_fast, self.amplitude_factor)
        avg_wave_y = (y_center + y_fore + y_aft) / 3.0
        
        # 喫水線を下げて海に沈ませる (+2)
        target_y = avg_wave_y + 2
        
        # 補間
        dt_factor = min(self.dt * 8, 0.4)
        self.ship_y = self.ship_y * (1.0 - dt_factor) + target_y * dt_factor
        
        if target_y - self.last_ship_y > 4:
            self._spawn_spray(self.ship_x+ox, self.ship_y+oy, 4)
        self.last_ship_y = self.ship_y
        self.ship_tilt = math.atan(ship_slope) * 1.8

        def r(px, py):
            s, c = math.sin(self.ship_tilt), math.cos(self.ship_tilt)
            nx = (px - self.ship_x) * c - (py - self.ship_y) * s + self.ship_x
            ny = (px - self.ship_x) * s + (py - self.ship_y) * c + self.ship_y
            return nx + ox, ny + oy

        cx, cy = self.ship_x, self.ship_y
        hull = [r(cx-16, cy), r(cx+18, cy-1), r(cx+14, cy+7), r(cx-13, cy+7)]
        draw.polygon(hull, outline=255, fill=0)
        draw.line(r(cx, cy) + r(cx, cy-20), fill=255) 
        draw.polygon([r(cx+1, cy-19), r(cx+12, cy-11), r(cx+1, cy-3)], outline=255)
        # 航海灯
        if int(now * 5) % 2 == 0: draw.point(r(cx-15, cy+1), fill=255)

        # 飛沫描画
        for p in self.particles: draw.point((p["x"], p["y"]), fill=255)

        # テキスト
        if int(now / 15) % 2 == 0 and (now % 15) < 3: # 15秒おきに3秒表示
            draw.text((70+ox, 6+oy), "Crypto Ark", fill=255)
            draw.text((75+ox, 16+oy), ":BCNOFNe", fill=255)
    def _generate_storm_wave(self, x, phase, phase_fast, amplitude):
        """波の高さを計算する共通メソッド"""
        sine1 = math.sin(x * 0.07 + phase)
        wave1 = math.pow(abs(sine1), 0.55) * (15.0 if sine1 > 0 else -6.0)
        wave2 = math.sin(x * 0.18 + phase_fast) * 4
        return self.HORIZON_Y + (wave1 + wave2) * amplitude
