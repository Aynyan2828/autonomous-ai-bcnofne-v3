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
        """内部状態を更新する（描画前に呼ぶ）"""
        self.frame_count += 1
        
        # 船の揺れ (少し大きめに揺らす)
        self.ship_y_offset = math.sin(self.frame_count * 0.3) * 3
        
        # 波の位相 (バシャバシャ動くように速くする)
        self.wave_phase += 1.2
        
        # 星の点滅
        for i in range(len(self.stars)):
            self.stars[i][2] += 0.1
            
        # 焼け防止オフセットの変更 (15秒ごと)
        now = time.time()
        if now - self.last_offset_change > 15:
            self.burn_offset_x = random.randint(-2, 2)
            self.burn_offset_y = random.randint(-1, 1)
            self.last_offset_change = now
            
        # 低頻度テキストの更新
        if self.text_timer > 0:
            self.text_timer -= 1
        elif random.random() < 0.02: # 稀に表示
            self.overlay_text = random.choice(self.messages)
            self.text_timer = 30 # 約10-15秒（ループ間欠に依存）
        else:
            self.overlay_text = ""

        # 暗転フラグの更新 (45秒ごとに1.5秒程度)
        cycle_time = now - self.last_blackout_ts
        if cycle_time > 45:
            self.is_blackout = True
            if cycle_time > 47:
                self.is_blackout = False
                self.last_blackout_ts = now

    def draw(self, draw: ImageDraw.Draw, font=None):
        """提供されたImageDrawオブジェクトにスクリーンセーバーを描画する"""
        if self.is_blackout:
            return # 何も描画しない（黒）

        ox = self.burn_offset_x
        oy = self.burn_offset_y

        # 1. 星空を描画
        for x, y, phase in self.stars:
            # 点滅演出：位相が0以上の時だけ描画
            if math.sin(phase) > 0.5:
                draw.point((x + ox, y + oy), fill=255)

        # 2. 波を描画 (下部 - バシャバシャ感を出すために振幅と周波数を調整)
        wave_y_base = 56
        points = []
        for x in range(0, self.width, 2): # より細かく描画
            # 激しい波の表現：複数のサイン波を重ねて尖った動きに
            y = wave_y_base + math.sin(x * 0.2 + self.wave_phase) * 3
            y += math.sin(x * 0.4 + self.wave_phase * 1.5) * 2
            points.append((x + ox, y + oy))
        
        if len(points) > 1:
            draw.line(points, fill=255, width=1)

        # 3. 船のシルエットを描画 (中央付近)
        ship_x = 55 + math.cos(self.frame_count * 0.05) * 10 # 左右にも少し漂う
        ship_y = 35 + self.ship_y_offset
        
        # 船体 (台形)
        draw.polygon([
            (ship_x + ox, ship_y + oy),
            (ship_x + 20 + ox, ship_y + oy),
            (ship_x + 16 + ox, ship_y + 5 + oy),
            (ship_x + 4 + ox, ship_y + 5 + oy)
        ], outline=255, fill=0)
        
        # マスト
        draw.line((ship_x + 10 + ox, ship_y + oy, ship_x + 10 + ox, ship_y - 8 + oy), fill=255)
        # 帆
        draw.line((ship_x + 10 + ox, ship_y - 8 + oy, ship_x + 16 + ox, ship_y - 2 + oy), fill=255)
        draw.line((ship_x + 10 + ox, ship_y - 2 + oy, ship_x + 16 + ox, ship_y - 2 + oy), fill=255)

        # 4. オーバーレイテキスト
        if self.overlay_text:
            text_x = 40 + random.randint(-5, 5) # テキストも位置を揺らす
            text_y = 15 + random.randint(-2, 2)
            if font:
                draw.text((text_x + ox, text_y + oy), self.overlay_text, font=font, fill=255)
            else:
                draw.text((text_x + ox, text_y + oy), self.overlay_text, fill=255)
