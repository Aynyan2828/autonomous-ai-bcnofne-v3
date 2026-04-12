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
        self.ship_y_offset = 0
        self.ship_dir = 1
        self.wave_phase = 0
        
        # 焼け防止用オフセット
        self.burn_offset_x = 0
        self.burn_offset_y = 0
        self.last_offset_change = time.time()
        
        # 星空の状態 (x, y, brightness_phase)
        self.stars = [
            [random.randint(0, width-1), random.randint(0, 30), random.random() * math.pi]
            for _ in range(12)
        ]
        
        # テキスト表示状態
        self.overlay_text = ""
        self.text_timer = 0
        self.messages = ["BCNOFNe", "DEST: SAIL", "AYN ONLINE", "IDLE DRIFT", "SIGNAL OK"]
        
        # 暗転管理
        self.is_blackout = False
        self.last_blackout_ts = time.time()

    def update(self):
        """内部状態を更新する"""
        self.frame_count += 1
        
        # 波の位相 (ダイナミックに動かす)
        self.wave_phase += 0.15
        
        # 星の点滅
        for i in range(len(self.stars)):
            self.stars[i][2] += 0.05
            
        # 焼け防止オフセット
        now = time.time()
        if now - self.last_offset_change > 15:
            self.burn_offset_x = random.randint(-4, 4)
            self.burn_offset_y = random.randint(-2, 2)
            self.last_offset_change = now
            
        # 低頻度テキストの更新
        if self.text_timer > 0:
            self.text_timer -= 1
        elif random.random() < 0.02: # 稀に表示
            self.overlay_text = random.choice(self.messages)
            self.text_timer = 30 # 約10-15秒（ループ間欠に依存）
        else:
            self.overlay_text = ""

        # 暗転管理
        cycle_time = now - self.last_blackout_ts
        if cycle_time > 45:
            self.is_blackout = True
            if cycle_time > 46.5:
                self.is_blackout = False
                self.last_blackout_ts = now

    def draw(self, draw: ImageDraw.Draw, font=None):
        """北斎風の大波と帆船を描画するバイ"""
        if self.is_blackout:
            return

        ox = self.burn_offset_x
        oy = self.burn_offset_y

        # 1. 星空
        for x, y, phase in self.stars:
            if math.sin(phase) > 0.3:
                draw.point((x + ox, y + oy), fill=255)

        # 2. 北斎風の大波を描画
        wave_points = []
        ship_x = 50 + math.sin(self.wave_phase * 0.5) * 15 # 船のX位置もゆったり動く
        ship_wave_y = 0

        for x in range(-10, self.width + 10, 2):
            # 複数のサイン波を組み合わせて「うねり」を表現
            # 大きなうねり + 細かい波
            y_base = 48
            wave1 = math.sin(x * 0.05 + self.wave_phase) * 8
            wave2 = math.sin(x * 0.12 + self.wave_phase * 2) * 3
            y = y_base + wave1 + wave2
            
            wave_points.append((x + ox, y + oy))
            
            # 船の位置の波の高さを記憶
            if abs(x - ship_x) < 2:
                ship_wave_y = y

        # 波の描画 (塗りつぶし風に線を重ねるか、ポリゴンで描く)
        if len(wave_points) > 1:
            draw.line(wave_points, fill=255, width=1)
            # 波の下を少しだけ埋める（奥行き感）
            fill_points = wave_points + [(self.width+10+ox, self.height+oy), (-10+ox, self.height+oy)]
            # 線の密度で表現（点描風）
            for i in range(len(wave_points)-1):
                px, py = wave_points[i]
                if i % 4 == 0:
                    draw.line((px, py, px, py + 3), fill=255)

        # 3. かっこいい帆船シルエット
        # 船は波の高さに合わせて上下し、少し傾ける
        ship_y = ship_wave_y - 2 # 波の少し上に配置
        tilt = math.cos(ship_x * 0.05 + self.wave_phase) * 0.2
        
        def rotate_point(px, py, cx, cy, angle):
            s, c = math.sin(angle), math.cos(angle)
            nx = (px - cx) * c - (py - cy) * s + cx
            ny = (px - cx) * s + (py - cy) * c + cy
            return nx + ox, ny + oy

        cx, cy = ship_x, ship_y
        # 船体 (大きめの帆船)
        hull = [
            rotate_point(ship_x - 12, ship_y, cx, cy, tilt),
            rotate_point(ship_x + 14, ship_y - 2, cx, cy, tilt),
            rotate_point(ship_x + 10, ship_y + 6, cx, cy, tilt),
            rotate_point(ship_x - 10, ship_y + 6, cx, cy, tilt)
        ]
        draw.polygon(hull, outline=255, fill=0)
        
        # メインマストと大きな帆
        draw.line(rotate_point(ship_x, ship_y, cx, cy, tilt) + 
                  rotate_point(ship_x, ship_y - 18, cx, cy, tilt), fill=255)
        sail1 = [
            rotate_point(ship_x + 1, ship_y - 17, cx, cy, tilt),
            rotate_point(ship_x + 12, ship_y - 10, cx, cy, tilt),
            rotate_point(ship_x + 1, ship_y - 3, cx, cy, tilt)
        ]
        draw.polygon(sail1, outline=255, fill=0)

        # 前方のマストと帆
        draw.line(rotate_point(ship_x - 6, ship_y, cx, cy, tilt) + 
                  rotate_point(ship_x - 6, ship_y - 12, cx, cy, tilt), fill=255)
        sail2 = [
            rotate_point(ship_x - 5, ship_y - 11, cx, cy, tilt),
            rotate_point(ship_x + 2, ship_y - 8, cx, cy, tilt),
            rotate_point(ship_x - 5, ship_y - 4, cx, cy, tilt)
        ]
        draw.polygon(sail2, outline=255, fill=0)

        # 4. オーバーレイテキスト
        if self.overlay_text:
            text_x = 40 + random.randint(-5, 5) # テキストも位置を揺らす
            text_y = 15 + random.randint(-2, 2)
            if font:
                draw.text((text_x + ox, text_y + oy), self.overlay_text, font=font, fill=255)
            else:
                draw.text((text_x + ox, text_y + oy), self.overlay_text, fill=255)
