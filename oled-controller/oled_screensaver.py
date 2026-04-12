import random
import time
import math
from PIL import ImageDraw, ImageFont

class BCNOFNeScreenSaver:
    def __init__(self, width=128, height=64):
        self.width = width
        self.height = height
        self.frame_count = 0
        
        # 月の状態 (3D回転 & 自由移動)
        self.moon_x = random.randint(20, width - 20)
        self.moon_y = random.randint(10, 30)
        self.moon_vx = random.uniform(0.2, 0.5) * random.choice([1, -1])
        self.moon_vy = random.uniform(0.1, 0.3) * random.choice([1, -1])
        self.moon_phi = random.random() * 2 * math.pi # 回転角 (満ち欠け)
        self.moon_radius = 10
        
        # 波の状態
        self.wave_phase = 0
        self.wave_phase_fast = 0
        self.amplitude_factor = 1.0
        
        # 船の状態
        self.ship_x = 64
        self.ship_y = 40
        self.ship_tilt = 0
        self.last_ship_y = 40
        
        # 飛沫（パーティクル）管理
        self.particles = [] # {"x", "y", "vx", "vy", "life"}
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
        
        # 1. 月の物理移動
        self.moon_x += self.moon_vx
        self.moon_y += self.moon_vy
        # 壁との衝突判定 (マージンを持たせる)
        if self.moon_x < 15 or self.moon_x > self.width - 15:
            self.moon_vx *= -1
        if self.moon_y < 10 or self.moon_y > self.height - 20:
            self.moon_vy *= -1
            
        # 2. 月の3D回転 (満ち欠け)
        self.moon_phi += 0.03
        
        # 3. 波とパーティクル
        self.wave_phase += 0.12
        self.wave_phase_fast += 0.25
        self.amplitude_factor = 0.9 + math.sin(self.frame_count * 0.04) * 0.25
        
        new_particles = []
        for p in self.particles:
            p["x"] += p["vx"]
            p["y"] += p["vy"]
            p["vy"] += 0.4
            p["life"] -= 1
            if p["life"] > 0 and 0 <= p["x"] < self.width and 0 <= p["y"] < self.height:
                new_particles.append(p)
        self.particles = new_particles
        
        # 4. 焼け防止
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
                    "vx": random.uniform(-1.5, 1.5),
                    "vy": random.uniform(-2.5, -0.8),
                    "life": random.randint(6, 15)
                })

    def _draw_3d_moon(self, draw, x, y, ox, oy):
        """
        円と楕円の影を組み合わせて3D回転（満ち欠け）を表現する。
        """
        r = self.moon_radius
        phi = self.moon_phi % (2 * math.pi)
        
        # 基本の白円 (月本体)
        draw.ellipse([x-r+ox, y-r+oy, x+r+ox, y+r+oy], fill=255)
        
        # 位相に応じた影の描画
        # cos(phi) で影の幅を決定
        w_factor = math.cos(phi)
        abs_w = abs(w_factor) * r
        
        if 0 <= phi < math.pi:
            # 満月 -> 新月 (右から影が迫る)
            if w_factor > 0:
                # 三日月 (左側が明るい)
                draw.ellipse([x-abs_w+ox, y-r+oy, x+abs_w+ox, y+r+oy], fill=0)
                # 左半分を削るなどして調整が必要だが、中心をずらした楕円で代用
                draw.ellipse([x-r+ox+ (r - abs_w), y-r+oy, x+r+ox + (r - abs_w), y+r+oy], fill=0)
            else:
                # 逆三日月 (右側が明るい)
                draw.ellipse([x-r+ox - (r - abs_w), y-r+oy, x+r+ox - (r - abs_w), y+r+oy], fill=0)
        else:
            # 新月 -> 満月
            if w_factor < 0:
                draw.ellipse([x-r+ox - (r - abs_w), y-r+oy, x+r+ox - (r - abs_w), y+r+oy], fill=0)
            else:
                draw.ellipse([x-r+ox + (r - abs_w), y-r+oy, x+r+ox + (r - abs_w), y+r+oy], fill=0)

    def _draw_pure_crescent_logic(self, draw, x, y, ox, oy):
        """
        よりシンプルな3D回転ロジック:
        白い円の上に黒い楕円を重ねて満ち欠けを表現。
        """
        r = self.moon_radius
        phi = self.frame_count * 0.05
        
        # 1. 土台の白円
        draw.ellipse([x-r+ox, y-r+oy, x+r+ox, y+r+oy], fill=255)
        
        # 2. 影のパラメータ
        # 影の幅を -2r から 2r まで変化させる
        shadow_w = math.sin(phi) * r * 2.2
        
        # 影の楕円を描画 (中心を少しずらして三日月を形作る)
        # shadow_w が正なら右から、負なら左から影
        draw.ellipse([x+ox-r+shadow_w, y+oy-r-1, x+ox+r+shadow_w, y+oy+r+1], fill=0)

    def draw(self, draw: ImageDraw.Draw, font=None):
        if self.is_blackout: return
        ox, oy = self.burn_offset_x, self.burn_offset_y

        # 1. 星空
        for s in self.stars:
            if math.sin(s["p"] + self.frame_count * 0.03) > 0.5:
                draw.point((s["x"]+ox, s["y"]+oy), fill=255)

        # 2. 3D回転月 (自由移動)
        self._draw_pure_crescent_logic(draw, self.moon_x, self.moon_y, ox, oy)

        # 3. 水面反射 (月の位置に同期)
        if self.moon_y < 45: # 地平線より上にある時のみ反射
            reflect_x = self.moon_x + ox
            for ry in range(48, self.height, 4):
                shift = math.sin(ry * 0.2 + self.wave_phase * 2) * 4
                sw = random.randint(1, 4)
                draw.line([reflect_x + shift - sw, ry+oy, reflect_x + shift + sw, ry+oy], fill=255)

        # 4. 波と船
        wave_points = []
        ship_current_y = 45
        ship_slope = 0
        for x in range(-5, self.width + 10, 3):
            # 前回のStorm波生成ロジックを流用 (簡易化)
            sine1 = math.sin(x * 0.07 + self.wave_phase)
            wave1 = math.pow(abs(sine1), 0.55) * (14.0 if sine1 > 0 else -6.0)
            wave2 = math.sin(x * 0.18 + self.wave_phase_fast) * 3
            y = 46 + (wave1 + wave2) * self.amplitude_factor
            
            wave_points.append((x+ox, y+oy))
            if abs(x - self.ship_x) < 3:
                ship_current_y = y
                # 勾配計算
                s_n = math.sin((x+3) * 0.07 + self.wave_phase)
                w_n = math.pow(abs(s_n), 0.55) * (14.0 if s_n > 0 else -6.0)
                y_next = 46 + (w_n + math.sin((x+3) * 0.18 + self.wave_phase_fast) * 3) * self.amplitude_factor
                ship_slope = (y_next - y) / 3.0
                
            if y < 40 and random.random() < 0.1:
                self._spawn_spray(x+ox, y+oy, 1)

        if len(wave_points) > 1:
            draw.line(wave_points, fill=255, width=1)

        # 5. 大型帆船
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

        # 6. パーティクル
        for p in self.particles: draw.point((p["x"], p["y"]), fill=255)

        # 7. テキスト (たまに右上に)
        if self.frame_count % 400 < 60:
            draw.text((80+ox, 6+oy), "Crypto Ark", fill=255)
            draw.text((85+ox, 16+oy), ":BCNOFNe", fill=255)
