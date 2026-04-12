import random
import time
import math
from PIL import ImageDraw, ImageFont

class BCNOFNeScreenSaver:
    def __init__(self, width=128, height=64):
        self.width = width
        self.height = height
        self.frame_count = 0
        
        # 波の状態
        self.wave_phase = 0
        self.wave_phase_fast = 0
        self.amplitude_factor = 1.0 # 時間で変動させる
        
        # 船の状態
        self.ship_x = 55
        self.ship_y = 40
        self.ship_tilt = 0
        self.last_ship_y = 40
        
        # 飛沫（パーティクル）管理
        self.particles = [] # {"x", "y", "vx", "vy", "life"}
        self.MAX_PARTICLES = 30
        
        # 焼け防止用オフセット
        self.burn_offset_x = 0
        self.burn_offset_y = 0
        self.last_offset_change = time.time()
        
        # 星空 (背景は静かに)
        self.stars = [
            {"x": random.randint(0, width-1), "y": random.randint(0, 30), "p": random.random() * math.pi}
            for _ in range(12)
        ]
        
        # 暗転管理
        self.is_blackout = False
        self.last_blackout_ts = time.time()

    def _generate_storm_wave(self, x, phase, phase_fast, amp_mod):
        """
        北斎風の非対称で尖った波を生成するロジック。
        複数の波を合成し、累乗を使って頂点を鋭くする。
        """
        # 大きなうねり (低周波)
        base_y = 45
        
        # 第一波 (主波): 累乗で頂点を尖らせる
        sine1 = math.sin(x * 0.06 + phase)
        peak_sharpness = 0.6 # 1.0未満で鋭くなる
        wave1 = math.pow(abs(sine1), peak_sharpness) * (1.0 if sine1 > 0 else -0.7) # 谷は浅く、山は高く
        
        # 第二波 (高波): 非対称な動き
        wave2 = math.sin(x * 0.15 + phase_fast) * 3
        
        # ノイズと微細な揺れ
        wave3 = math.sin(x * 0.3 + phase * 2) * 1.5
        
        total_y = base_y + (wave1 * 12 + wave2 + wave3) * amp_mod
        return total_y

    def update(self):
        """内部状態を更新する"""
        self.frame_count += 1
        
        # 波の位相更新 (時化を表現するために速め)
        self.wave_phase += 0.12
        self.wave_phase_fast += 0.25
        
        # 波の振幅をゆっくり変動させる (定常状態を避ける)
        self.amplitude_factor = 0.8 + math.sin(self.frame_count * 0.05) * 0.3
        
        # パーティクルの更新
        new_particles = []
        for p in self.particles:
            p["x"] += p["vx"]
            p["y"] += p["vy"]
            p["vy"] += 0.4 # 重力
            p["life"] -= 1
            if p["life"] > 0 and 0 <= p["x"] < self.width and 0 <= p["y"] < self.height:
                new_particles.append(p)
        self.particles = new_particles
        
        # 焼け防止オフセット
        now = time.time()
        if now - self.last_offset_change > 15:
            self.burn_offset_x = random.randint(-4, 4)
            self.burn_offset_y = random.randint(-2, 2)
            self.last_offset_change = now
            
        # 暗転管理 (45秒ごとに1秒)
        if now - self.last_blackout_ts > 45:
            self.is_blackout = True
            if now - self.last_blackout_ts > 46:
                self.is_blackout = False
                self.last_blackout_ts = now

    def _spawn_spray(self, x, y, count=1):
        """波の頂点や衝突時に飛沫を発生させる"""
        for _ in range(count):
            if len(self.particles) < self.MAX_PARTICLES:
                self.particles.append({
                    "x": x,
                    "y": y,
                    "vx": random.uniform(-1.5, 1.5),
                    "vy": random.uniform(-2.5, -0.5), # 上に飛ばす
                    "life": random.randint(5, 12)
                })

    def draw(self, draw: ImageDraw.Draw, font=None):
        """Storm Mode を描画するバイ"""
        if self.is_blackout:
            return

        ox = self.burn_offset_x
        oy = self.burn_offset_y

        # 1. 背後の星空 (静止)
        for s in self.stars:
            if math.sin(s["p"] + self.frame_count * 0.02) > 0.6:
                draw.point((s["x"] + ox, s["y"] + oy), fill=255)

        # 2. 波の描画と船の高さ計算
        wave_points = []
        ship_current_y = 0
        ship_slope = 0
        
        for x in range(-5, self.width + 5, 2):
            y = self._generate_storm_wave(x, self.wave_phase, self.wave_phase_fast, self.amplitude_factor)
            wave_points.append((x + ox, y + oy))
            
            # 船の位置(ship_x)での高さと傾斜を取得
            if abs(x - self.ship_x) < 2:
                ship_current_y = y
                # 傾斜を計算（少し先の点との比較）
                y_next = self._generate_storm_wave(x + 2, self.wave_phase, self.wave_phase_fast, self.amplitude_factor)
                ship_slope = (y_next - y) / 2.0
            
            # 波の頂点での飛沫発生 (yが十分に高いとき)
            if y < 38 and random.random() < 0.1:
                self._spawn_spray(x + ox, y + oy, 1)

        # 波を描画 (線)
        if len(wave_points) > 1:
            draw.line(wave_points, fill=255, width=1)
            # 波しぶき感（点々を追加）
            for i in range(0, len(wave_points), 4):
                px, py = wave_points[i]
                if py < 45: # 頂点付近
                    draw.point((px, py + 1), fill=255)

        # 3. 船の描画 (荒波対応)
        # 船の高さ更新 (ガクッと動かすための処理)
        target_y = ship_current_y - 2
        # なめらか補間をあえて弱くし、波に即座に反応させる
        self.ship_y = self.ship_y * 0.4 + target_y * 0.6
        
        # 急落判定 (大きな落差があるとき飛沫)
        if target_y - self.last_ship_y > 4:
            self._spawn_spray(self.ship_x + ox, self.ship_y + oy, 3)
        self.last_ship_y = self.ship_y

        # 傾斜 (波の勾配に同期)
        self.ship_tilt = math.atan(ship_slope) * 1.5 # 傾斜を強調

        def rot(px, py, cx, cy, angle):
            s, c = math.sin(angle), math.cos(angle)
            nx = (px - cx) * c - (py - cy) * s + cx
            ny = (px - cx) * s + (py - cy) * c + cy
            return nx + ox, ny + oy

        # 船体を描画
        cx, cy = self.ship_x, self.ship_y
        hull = [
            rot(cx - 10, cy, cx, cy, self.ship_tilt),
            rot(cx + 12, cy - 1, cx, cy, self.ship_tilt),
            rot(cx + 8, cy + 5, cx, cy, self.ship_tilt),
            rot(cx - 8, cy + 5, cx, cy, self.ship_tilt)
        ]
        draw.polygon(hull, outline=255, fill=0)
        
        # マスト (波の衝撃で揺れる)
        m_top = rot(cx, cy - 10, cx, cy, self.ship_tilt + math.sin(self.frame_count * 0.2) * 0.1)
        draw.line(rot(cx, cy, cx, cy, self.ship_tilt) + m_top, fill=255)

        # 4. パーティクルの描画
        for p in self.particles:
            draw.point((p["x"], p["y"]), fill=255)

        # 5. テキスト演出 (時化の緊迫感)
        if random.random() < 0.05 and self.frame_count % 50 < 10:
            draw.text((10+ox, 10+oy), "STORM ALERT", fill=255)
