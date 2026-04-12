import random
import time
import math
from PIL import ImageDraw, ImageFont

class BCNOFNeScreenSaver:
    def __init__(self, width=128, height=64):
        self.width = width
        self.height = height
        self.frame_count = 0
        
        # 月の状態 (軌道運行)
        self.moon_progress = 0.0 # 0.0 to 1.0 (昇ってから沈むまで)
        self.moon_orbit_speed = 0.015 # 5倍速に変更 (0.003 -> 0.015)
        self.moon_radius = 10
        self.moon_x = -20
        self.moon_y = 50
        
        # 波の状態
        self.wave_phase = 0
        self.wave_phase_fast = 0
        self.amplitude_factor = 1.0
        self.HORIZON_Y = 46
        
        # 船の状態
        self.ship_x = 64
        self.ship_y = 40
        self.ship_tilt = 0
        self.last_ship_y = 40
        
        # 飛沫（パーティクル）管理
        self.particles = []
        self.MAX_PARTICLES = 50
        
        # 焼け防止用オフセット
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

    def update(self):
        self.frame_count += 1
        
        # 1. 月の軌道更新
        # 0.0〜1.0で空を横切り、しばらく間を置いてからリセット
        self.moon_progress += self.moon_orbit_speed
        if self.moon_progress > 1.6: # 1.0で沈み、0.6分だけ「夜」を維持
            self.moon_progress = 0.0
            
        # 軌道計算 (逆放物線)
        # x: -20 to 148
        # y: 46 (水平線) -> 10 (頂点) -> 46 (水平線)
        p = self.moon_progress
        if p <= 1.0:
            self.moon_x = -20 + (self.width + 40) * p
            # 2次関数: y = a(x - h)^2 + k
            # 頂点を (0.5, 10) 、端点を (0.0, 48), (1.0, 48) と仮定
            self.moon_y = 10 + 152 * (p - 0.5)**2
        else:
            self.moon_y = 80 # 画面外
        
        # 2. 波と波の更新 (5倍速に変更)
        self.wave_phase += 0.6     # 0.12 * 5
        self.wave_phase_fast += 1.25  # 0.25 * 5
        self.amplitude_factor = 0.9 + math.sin(self.frame_count * 0.2) * 0.25 # 周期を5倍に
        
        # 3. パーティクル
        new_particles = []
        for p_obj in self.particles:
            p_obj["x"] += p_obj["vx"]
            p_obj["y"] += p_obj["vy"]
            p_obj["vy"] += 0.4
            p_obj["life"] -= 1
            if p_obj["life"] > 0 and 0 <= p_obj["x"] < self.width and 0 <= p_obj["y"] < self.height:
                new_particles.append(p_obj)
        self.particles = new_particles
        
        # 4. 焼け防止
        now = time.time()
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
                    "life": random.randint(6, 15)
                })

    def _draw_3d_moon_logic(self, draw, x, y, ox, oy):
        """
        3D回転（満ち欠け）を表現しながら月の本体を描画
        """
        r = self.moon_radius
        # 回転スピードは前の3倍を維持
        phi = self.frame_count * 0.15
        
        # 1. 土台の白円
        draw.ellipse([x-r+ox, y-r+oy, x+r+ox, y+r+oy], fill=255)
        
        # 2. 満ち欠けの影
        shadow_w = math.sin(phi) * r * 2.2
        draw.ellipse([x+ox-r+shadow_w, y+oy-r-1, x+ox+r+shadow_w, y+oy+r+1], fill=0)

    def draw(self, draw: ImageDraw.Draw, font=None):
        if self.is_blackout: return
        ox, oy = self.burn_offset_x, self.burn_offset_y

        # LAYER 1: 星空
        for s in self.stars:
            if math.sin(s["p"] + self.frame_count * 0.03) > 0.5:
                draw.point((s["x"]+ox, s["y"]+oy), fill=255)

        # LAYER 2: 軌道上の月
        if self.moon_y < self.height + 15:
            self._draw_3d_moon_logic(draw, self.moon_x, self.moon_y, ox, oy)

        # LAYER 3: 海のオクルージョン (水平線より下を黒く塗りつぶす)
        # これにより月が海の下に隠れる
        draw.rectangle([0, self.HORIZON_Y + oy, self.width, self.height], fill=0)

        # LAYER 4: 水面反射 (月の位置に同期 & 水平線付近のみ)
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
        for x in range(-5, self.width + 10, 3):
            sine1 = math.sin(x * 0.07 + self.wave_phase)
            wave1 = math.pow(abs(sine1), 0.55) * (14.0 if sine1 > 0 else -6.0)
            wave2 = math.sin(x * 0.18 + self.wave_phase_fast) * 3
            y = self.HORIZON_Y + (wave1 + wave2) * self.amplitude_factor
            
            wave_points.append((x+ox, y+oy))
            if abs(x - self.ship_x) < 3:
                ship_current_y = y
                s_n = math.sin((x+3) * 0.07 + self.wave_phase)
                w_n = math.pow(abs(s_n), 0.55) * (14.0 if s_n > 0 else -6.0)
                y_next = self.HORIZON_Y + (w_n + math.sin((x+3) * 0.18 + self.wave_phase_fast) * 3) * self.amplitude_factor
                ship_slope = (y_next - y) / 3.0
                
            if y < 40 and random.random() < 0.1:
                self._spawn_spray(x+ox, y+oy, 1)

        if len(wave_points) > 1:
            draw.line(wave_points, fill=255, width=1)

        # LAYER 6: 船 (最前面)
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
        hull = [r(cx-14, cy), r(cx+16, cy-1), r(cx+13, cy+6), r(cx-12, cy+6)]
        draw.polygon(hull, outline=255, fill=0)
        draw.line(r(cx, cy) + r(cx, cy-18), fill=255) 
        draw.polygon([r(cx-1, cy-17), r(cx+7, cy-10), r(cx-1, cy-2)], outline=255)
        if self.frame_count % 10 < 7: draw.point(r(cx-13, cy+1), fill=255)

        # パーティクル
        for p in self.particles: draw.point((p["x"], p["y"]), fill=255)

        # テキスト (Crypto Ark)
        if self.frame_count % 400 < 60:
            draw.text((80+ox, 6+oy), "Crypto Ark", fill=255)
            draw.text((85+ox, 16+oy), ":BCNOFNe", fill=255)
