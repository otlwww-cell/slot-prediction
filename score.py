import pandas as pd
import json
from datetime import datetime

STORES = [
    {
        "name": "将軍葛西店",
        "csv_url": "https://docs.google.com/spreadsheets/d/e/2PACX-1vT_uca2oOds_D2Vx--UdZ7bnY2_9iZvcVRW-Pjls3kIytv8kzEnkViKZwlKBYXoaBU1f-TDzQLYSOQQ/pub?output=csv"
    }
]

def clean_number(val):
    if pd.isna(val):
        return 0
    s = str(val).replace(",", "").replace(" ", "")
    if s in ["#ERROR!", "#N/A", "-", ""]:
        return None
    try:
        return float(s)
    except:
        return None

def calc_score(row):
    diff = row.get("差枚_num", 0) or 0
    games = row.get("G数_num", 0) or 0
    if games < 200:
        return 0
    diff_score = min(max(diff / 50, -20), 60)
    game_bonus = min(games / 100, 40)
    score = diff_score + game_bonus
    return round(max(score, 0), 1)

def process_store(store):
    try:
        df = pd.read_csv(store["csv_url"])
    except Exception as e:
        print(f"[ERROR] {store['name']} の読み込み失敗: {e}")
        return []
    results = []
    for _, row in df.iterrows():
        row_dict = {str(k).strip(): v for k, v in row.items()}
        machine = str(row_dict.get("機種名", "")).strip()
        unit_no = row_dict.get("台番号", "")
        games_raw = row_dict.get("G数", 0)
        diff_raw = row_dict.get("差枚", 0)
        bb_raw = row_dict.get("BB", 0)
        rb_raw = row_dict.get("RB", 0)
        if not machine or machine in ["nan", "機種名", ""]:
            continue
        games = clean_number(games_raw)
        diff = clean_number(diff_raw)
        bb = clean_number(bb_raw)
        rb = clean_number(rb_raw)
        entry = {
            "店舗名": store["name"],
            "機種名": machine,
            "台番号": str(unit_no).replace(".0", ""),
            "G数_num": games or 0,
            "差枚_num": diff or 0,
            "BB_num": bb or 0,
            "RB_num": rb or 0,
            "G数": f"{int(games):,}" if games else "-",
            "差枚": f"{int(diff):+,}" if diff is not None else "#ERROR",
            "BB": int(bb) if bb else 0,
            "RB": int(rb) if rb else 0,
        }
        entry["スコア"] = calc_score(entry)
        results.append(entry)
    return results

def main():
    all_results = []
    for store in STORES:
        print(f"処理中: {store['name']}")
        results = process_store(store)
        all_results.extend(results)
        print(f"  → {len(results)} 台取得")
    all_results.sort(key=lambda x: x["スコア"], reverse=True)
    with open("docs/data.json", "w", encoding="utf-8") as f:
        json.dump({
            "updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "data": all_results
        }, f, ensure_ascii=False, indent=2)
    print(f"完了: 合計 {len(all_results)} 台 → docs/data.json に保存")

if __name__ == "__main__":
    main()
