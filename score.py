import json
import re
import csv
from datetime import datetime
from io import StringIO

# =============================================
# 設定：店舗ごとの入力ファイル
# =============================================
STORES = [
    {"name": "将軍葛西店", "file": "data/shogun.txt"},
    # 他店舗を追加する場合はここに追記
    # {"name": "メッセ西葛西店", "file": "data/messe.txt"},
]

def clean_num(val):
    s = str(val).replace(",", "").replace("+", "").replace(" ", "").strip()
    if s in ["#ERROR!", "#N/A", "-", "", "nan", "−"]:
        return None
    try:
        return float(s)
    except:
        return None

def parse_winrate(val):
    m = re.match(r"([\d.]+)%\((\d+)/(\d+)\)", str(val).strip())
    if m:
        return float(m.group(1)), int(m.group(2)), int(m.group(3))
    return None, None, None

def parse_anaslo(text):
    result = {
        "store": "",
        "date": "",
        "total": {},
        "machine_ranking": [],
        "tail_ranking": [],
    }

    lines = [l.strip() for l in text.splitlines()]
    lines = [l for l in lines if l]

    # 店舗名・日付
    for line in lines[:15]:
        m = re.match(r"(\d{4}/\d{2}/\d{2})\s+(.+?)\s+データまとめ", line)
        if m:
            result["date"] = m.group(1)
            result["store"] = m.group(2)
            break

    # 全体データ
    for i, line in enumerate(lines):
        if line in ["全体データ", "全データ一覧"]:
            for j in range(i+1, min(i+6, len(lines))):
                vals = re.split(r"\t+", lines[j])
                if len(vals) < 3:
                    vals = re.split(r"\s{2,}", lines[j])
                if len(vals) >= 3:
                    d = clean_num(vals[0])
                    ad = clean_num(vals[1])
                    if d is not None or ad is not None:
                        result["total"] = {
                            "総差枚": d,
                            "平均差枚": ad,
                            "勝率": vals[3] if len(vals) > 3 else ""
                        }
                        break
            break

    # 機種別ランキング
    for i, line in enumerate(lines):
        m = re.match(r"(\d+)位：(.+)", line)
        if m:
            rank = int(m.group(1))
            machine = m.group(2).strip().rstrip(",").strip()
            entry = {"rank": rank, "machine": machine,
                     "total_diff": None, "avg_diff": None,
                     "avg_games": None, "win_rate": None,
                     "win_count": None, "total_count": None}
            for j in range(i+1, min(i+8, len(lines))):
                vals = re.split(r"[\t,]+", lines[j])
                wr_str = ""
                for v in vals:
                    if re.search(r"\d+\.\d+%\(\d+/\d+\)", v):
                        wr_str = v
                        break
                if wr_str:
                    entry["total_diff"] = clean_num(vals[0]) if len(vals) > 0 else None
                    entry["avg_diff"] = clean_num(vals[1]) if len(vals) > 1 else None
                    entry["avg_games"] = clean_num(vals[2]) if len(vals) > 2 else None
                    wr, wc, tc = parse_winrate(wr_str)
                    entry["win_rate"] = wr
                    entry["win_count"] = wc
                    entry["total_count"] = tc
                    break
            result["machine_ranking"].append(entry)

    # 末尾別データ：テキストから直接正規表現で抽出
    TAIL_KEYS = ["0","1","2","3","4","5","6","7","8","9","ゾロ目"]

    # 末尾セクションを切り出す
    tail_start = -1
    tail_end = -1
    for i, line in enumerate(lines):
        if "末尾別データ" in line and tail_start == -1:
            tail_start = i
        if tail_start > 0 and "詳細データ" in line:
            tail_end = i
            break

    if tail_start > 0:
        tail_lines = lines[tail_start:tail_end if tail_end > 0 else tail_start+20]
        for line in tail_lines:
            if "平均G数" in line or "末尾別差枚" in line or "末尾別データ" in line:
                continue

            # タブ区切りで分割を試みる
            if "\t" in line:
                vals = line.split("\t")
            else:
                # スペース区切りで分割
                vals = re.split(r"\s{2,}", line)

            if not vals or vals[0].strip() not in TAIL_KEYS:
                continue

            tail = vals[0].strip()
            td = clean_num(vals[1]) if len(vals) > 1 else None
            ad = clean_num(vals[2]) if len(vals) > 2 else None
            ag = clean_num(vals[3]) if len(vals) > 3 else None
            wr_str = vals[4] if len(vals) > 4 else ""
            wr, wc, tc = parse_winrate(wr_str)

            result["tail_ranking"].append({
                "tail": tail,
                "total_diff": td,
                "avg_diff": ad,
                "avg_games": ag,
                "win_rate": wr,
                "win_count": wc,
                "total_count": tc,
            })

    return result

def process_store(store):
    try:
        with open(store["file"], "r", encoding="utf-8") as f:
            text = f.read()
    except Exception as e:
        print(f"[ERROR] {store['name']} の読み込み失敗: {e}")
        return None

    parsed = parse_anaslo(text)
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
