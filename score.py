import pandas as pd
import json
import re
from datetime import datetime
from io import StringIO
import requests

STORES = [
    {
        "name": "将軍葛西店",
        "csv_url": "https://docs.google.com/spreadsheets/d/e/2PACX-1vT_uca2oOds_D2Vx--UdZ7bnY2_9iZvcVRW-Pjls3kIytv8kzEnkViKZwlKBYXoaBU1f-TDzQLYSOQQ/pub?gid=1083792724&single=true&output=csv"
    },
]

def clean_num(val):
    s = str(val).replace(",", "").replace("+", "").replace(" ", "").replace("−","-").strip()
    if s in ["#ERROR!", "#N/A", "-", "", "nan", "ー", "−−"]:
        return None
    try:
        return float(s)
    except:
        return None

def parse_winrate(val):
    s = str(val).strip()
    m = re.match(r"([\d.]+)%\((\d+)/(\d+)\)", s)
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
            machine = m.group(2).strip()
            entry = {"rank": rank, "machine": machine,
                     "total_diff": None, "avg_diff": None,
                     "avg_games": None, "win_rate": None,
                     "win_count": None, "total_count": None}
            for j in range(i+1, min(i+8, len(lines))):
                vals = re.split(r"\t+", lines[j])
                if len(vals) < 2:
                    vals = re.split(r"\s{2,}", lines[j])
                # 勝率パターンを含む行を探す
                wr_str = ""
                for v in vals:
                    if re.search(r"\d+\.\d+%\(\d+/\d+\)", v):
                        wr_str = v
                        break
                if wr_str:
                    # A=機種別差枚 B=平均差枚 C=平均G数 D=勝率
                    entry["total_diff"] = clean_num(vals[0]) if len(vals) > 0 else None
                    entry["avg_diff"] = clean_num(vals[1]) if len(vals) > 1 else None
                    entry["avg_games"] = clean_num(vals[2]) if len(vals) > 2 else None
                    wr, wc, tc = parse_winrate(wr_str)
                    entry["win_rate"] = wr
                    entry["win_count"] = wc
                    entry["total_count"] = tc
                    break
            result["machine_ranking"].append(entry)

    # 末尾別データ：複数パターンに対応
    TAIL_KEYS = ["0","1","2","3","4","5","6","7","8","9","ゾロ目"]

    in_tail = False
    for i, line in enumerate(lines):
        if "末尾別データ" in line:
            in_tail = True
            continue
        if in_tail and "詳細データ" in line:
            break
        if not in_tail:
            continue

        # ヘッダー行スキップ
        if re.match(r"^末尾\t?末尾別", line) or line.strip() in ["末尾別データ","末尾\t末尾別差枚\t平均差枚\t平均G数\t勝率"]:
            continue

        # タブ区切りで分割
        vals = re.split(r"\t+", line.strip())

        # タブがない場合は末尾キーで始まる行を探す
        if len(vals) < 2:
            # 「0--818-」のような結合行を分割
            m = re.match(r"^([0-9]|ゾロ目)(.+)$", line)
            if m:
                tail = m.group(1)
                rest = m.group(2)
                # 数値・パーセントを抽出
                nums = re.findall(r"[+\-]?[\d,]+(?:\.\d+)?|#ERROR!|-{1,2}", rest)
                pct = re.search(r"([\d.]+)%\((\d+)/(\d+)\)", rest)
                entry = {
                    "tail": tail,
                    "total_diff": clean_num(nums[0]) if len(nums) > 0 else None,
                    "avg_diff": clean_num(nums[1]) if len(nums) > 1 else None,
                    "avg_games": clean_num(nums[2]) if len(nums) > 2 else None,
                    "win_rate": float(pct.group(1)) if pct else None,
                    "win_count": int(pct.group(2)) if pct else None,
                    "total_count": int(pct.group(3)) if pct else None,
                }
                result["tail_ranking"].append(entry)
            continue

        if vals[0] in TAIL_KEYS:
            td = clean_num(vals[1]) if len(vals) > 1 else None
            ad = clean_num(vals[2]) if len(vals) > 2 else None
            ag = clean_num(vals[3]) if len(vals) > 3 else None
            wr_str = vals[4] if len(vals) > 4 else ""
            wr, wc, tc = parse_winrate(wr_str)
            result["tail_ranking"].append({
                "tail": vals[0],
                "total_diff": td,
                "avg_diff": ad,
                "avg_games": ag,
                "win_rate": wr,
                "win_count": wc,
                "total_count": tc,
            })

    # 末尾データが取れなかった場合：全テキストから直接抽出
    if len(result["tail_ranking"]) == 0:
        full_text = text.replace("\r","")
        tail_section = re.search(r"末尾別データ(.+?)詳細データ", full_text, re.DOTALL)
        if tail_section:
            section = tail_section.group(1)
            for tail in TAIL_KEYS:
                pattern = re.escape(tail) + r"\t([^\t\n]*)\t([^\t\n]*)\t([^\t\n]*)\t([^\t\n]*)"
                m = re.search(pattern, section)
                if m:
                    td = clean_num(m.group(1))
                    ad = clean_num(m.group(2))
                    ag = clean_num(m.group(3))
                    wr, wc, tc = parse_winrate(m.group(4))
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
        response = requests.get(store["csv_url"], timeout=30)
        response.encoding = "utf-8"
        text = response.text
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
