import pandas as pd
import json
import re
from datetime import datetime
from io import StringIO
import requests

# =============================================
# 設定：店舗ごとのスプレッドシートCSV URL
# =============================================
STORES = [
    {
        "name": "将軍葛西店",
        "csv_url": "https://docs.google.com/spreadsheets/d/e/2PACX-1vT_uca2oOds_D2Vx--UdZ7bnY2_9iZvcVRW-Pjls3kIytv8kzEnkViKZwlKBYXoaBU1f-TDzQLYSOQQ/pub?gid=1083792724&single=true&output=csv"
    },
    # 他店舗を追加する場合はここに追記
    # {"name": "メッセ西葛西店", "csv_url": "..."},
]

def clean_num(val):
    """+1,234 や -567 などを数値に変換"""
    s = str(val).replace(",", "").replace("+", "").replace(" ", "").strip()
    if s in ["#ERROR!", "#N/A", "-", "", "nan", "−"]:
        return None
    try:
        return float(s)
    except:
        return None

def parse_winrate(val):
    """66.7%(2/3) → (66.7, 2, 3)"""
    s = str(val).strip()
    m = re.match(r"([\d.]+)%\((\d+)/(\d+)\)", s)
    if m:
        return float(m.group(1)), int(m.group(2)), int(m.group(3))
    return None, None, None

def parse_anaslo(text):
    """
    あなすろのコピペテキストから以下を抽出：
    - 店舗名・日付
    - 全体データ（総差枚・平均差枚・勝率）
    - 機種別ランキング（最大20位）
    - 末尾別データ
    """
    lines = [l.strip() for l in text.splitlines()]
    lines = [l for l in lines if l]

    result = {
        "store": "",
        "date": "",
        "total": {},
        "machine_ranking": [],
        "tail_ranking": [],
    }

    # 店舗名・日付を検出
    for line in lines[:10]:
        m = re.match(r"(\d{4}/\d{2}/\d{2})\s+(.+?)\s+データまとめ", line)
        if m:
            result["date"] = m.group(1)
            result["store"] = m.group(2)
            break

    # 全体データを検出
    i = 0
    while i < len(lines):
        if lines[i] == "全体データ" or lines[i] == "全データ一覧":
            # 次の行に 総差枚・平均差枚・平均G数・勝率 のヘッダー
            if i+2 < len(lines):
                vals = lines[i+2].split("\t") if "\t" in lines[i+2] else lines[i+2].split()
                if len(vals) >= 4:
                    result["total"] = {
                        "総差枚": clean_num(vals[0]),
                        "平均差枚": clean_num(vals[1]),
                        "勝率": vals[3] if len(vals) > 3 else ""
                    }
            break
        i += 1

    # 機種別ランキングを検出
    i = 0
    while i < len(lines):
        m = re.match(r"(\d+)位：(.+)", lines[i])
        if m:
            rank = int(m.group(1))
            machine = m.group(2).strip()
            # 次の数行からデータを取得
            entry = {"rank": rank, "machine": machine,
                     "total_diff": None, "avg_diff": None,
                     "avg_games": None, "win_rate": None,
                     "win_count": None, "total_count": None}
            for j in range(i+1, min(i+5, len(lines))):
                vals = lines[j].split("\t") if "\t" in lines[j] else re.split(r"\s{2,}", lines[j])
                if len(vals) >= 3:
                    d = clean_num(vals[0])
                    ad = clean_num(vals[1])
                    ag = clean_num(vals[2])
                    wr_str = vals[3] if len(vals) > 3 else ""
                    if d is not None and ag is not None:
                        entry["total_diff"] = d
                        entry["avg_diff"] = ad
                        entry["avg_games"] = ag
                        wr, wc, tc = parse_winrate(wr_str)
                        entry["win_rate"] = wr
                        entry["win_count"] = wc
                        entry["total_count"] = tc
                        break
            result["machine_ranking"].append(entry)
        i += 1

    # 末尾別データを検出
    i = 0
    in_tail = False
    while i < len(lines):
        if "末尾別データ" in lines[i]:
            in_tail = True
            i += 1
            continue
        if in_tail and "詳細データ" in lines[i]:
            break
        if in_tail:
            # 末尾ヘッダー行スキップ
            if lines[i].startswith("末尾\t") or lines[i] == "末尾":
                i += 1
                continue
            vals = lines[i].split("\t") if "\t" in lines[i] else re.split(r"\s{2,}", lines[i])
            if len(vals) >= 4:
                tail = vals[0].strip()
                if tail in ["0","1","2","3","4","5","6","7","8","9","ゾロ目"]:
                    td = clean_num(vals[1])
                    ad = clean_num(vals[2])
                    ag = clean_num(vals[3])
                    wr_str = vals[4] if len(vals) > 4 else ""
                    wr, wc, tc = parse_winrate(wr_str)
                    result["tail_ranking"].append({
                        "tail": tail,
                        "total_diff": td,
                        "avg_diff": ad,
                        "avg_games": ag,
                        "win_rate": wr,
                        "win_count": wc,
                        "total_count": tc
                    })
        i += 1

    return result

def process_store(store):
    """CSVを取得してあなすろ形式を解析"""
    try:
        response = requests.get(store["csv_url"], timeout=30)
        response.encoding = "utf-8"
        # CSVの全テキストを結合して1つのテキストとして解析
        text = response.text
    except Exception as e:
        print(f"[ERROR] {store['name']} の読み込み失敗: {e}")
        return None

    parsed = parse_anaslo(text)

    # 店舗名が取得できなかった場合はstore設定から補完
    if not parsed["store"]:
        parsed["store"] = store["name"]

    print(f"  日付: {parsed['date']}")
    print(f"  機種ランキング: {len(parsed['machine_ranking'])}件")
    print(f"  末尾データ: {len(parsed['tail_ranking'])}件")

    return parsed

def main():
    all_stores = []

    for store in STORES:
        print(f"処理中: {store['name']}")
        data = process_store(store)
        if data:
            all_stores.append(data)

    with open("docs/data.json", "w", encoding="utf-8") as f:
        json.dump({
            "updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "stores": all_stores
        }, f, ensure_ascii=False, indent=2)

    print(f"\n完了: {len(all_stores)}店舗 → docs/data.json に保存")

if __name__ == "__main__":
    main()
