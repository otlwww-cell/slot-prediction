import pandas as pd
import json
import re
from datetime import datetime
from io import StringIO
import requests

STORES = [
    {
        "name": "将軍葛西店",
        "csv_url": "https://docs.google.com/spreadsheets/d/e/2PACX-1vT_uca2oOds_D2Vx--UdZ7bnY2_9iZvcVRW-Pjls3kIytv8kzEnkViKZwlKBYXoaBU1f-TDzQLYSOQQ/pub?output=csv"
    },
]

def clean_number(val):
    if val is None:
        return None
    s = str(val).replace(",", "").replace(" ", "").strip()
    if s in ["#ERROR!", "#N/A", "-", "", "nan"]:
        return None
    try:
        return float(s)
    except:
        return None

def calc_score(games, diff, bb, rb):
    games = games or 0
    diff = diff or 0
    if games < 200:
        return 0
    diff_score = min(max(diff / 50, -20), 60)
    game_bonus = min(games / 100, 40)
    return round(max(diff_score + game_bonus, 0), 1)

def parse_anaslo_format(df_raw):
    results = []
    current_machine = None
    in_single_block = False

    SKIP_WORDS = {
        "データ表示", "グラフ表示", "設置機種一覧へ戻る",
        "末尾別データ一覧へ戻る", "平均", "スポンサーリンク",
        "詳細データ", "設置機種一覧", "末尾毎詳細データ",
        "機種名クリックで詳細データへジャンプ出来ます。",
        "台番号", "機種名"
    }

    def is_unit_row(v):
        return re.match(r"^\d{3,4}$", str(v).replace(",","").strip()) is not None

    def is_machine_name(v, next_v):
        s = str(v).strip()
        if not s or s in SKIP_WORDS or s == "nan":
            return False
        if re.match(r"^[\d,.\-/\s]+$", s):
            return False
        if re.match(r"^\d+位：", s):
            return False
        if re.match(r"^末尾", s):
            return False
        nv = str(next_v).strip()
        if nv in ["", "nan"] or not re.match(r"^\d", nv):
            return True
        return False

    for _, row in df_raw.iterrows():
        vals = [str(v).strip() for v in row.values]
        if all(v in ["", "nan"] for v in vals):
            continue

        first = vals[0]

        if "1台設置機種" in first:
            in_single_block = True
            current_machine = None
            continue

        if "末尾毎詳細データ" in first:
            break

        if first in SKIP_WORDS:
            continue

        if in_single_block:
            if first in SKIP_WORDS or first == "nan" or not first:
                continue
            try:
                unit_no = vals[1].replace(".0","")
                games = clean_number(vals[2])
                diff = clean_number(vals[3])
                bb = clean_number(vals[4])
                rb = clean_number(vals[5])
                if games and games > 0:
                    results.append({"機種名": first, "台番号": unit_no,
                                    "G数": games, "差枚": diff, "BB": bb, "RB": rb})
            except:
                continue
        else:
            if first == "台番号":
                continue
            next_val = vals[1] if len(vals) > 1 else ""
            if is_machine_name(first, next_val):
                current_machine = first
                continue
            if current_machine and is_unit_row(first):
                try:
                    games = clean_number(vals[1])
                    diff = clean_number(vals[2])
                    bb = clean_number(vals[3])
                    rb = clean_number(vals[4])
                    if games and games > 0:
                        results.append({"機種名": current_machine,
                                        "台番号": first.replace(".0",""),
                                        "G数": games, "差枚": diff, "BB": bb, "RB": rb})
                except:
                    continue
    return results

def parse_simple_format(df_raw):
    cols = [str(c).strip() for c in df_raw.columns]
    required = {"機種名", "台番号", "G数", "差枚", "BB", "RB"}
    if not required.issubset(set(cols)):
        return None
    results = []
    for _, row in df_raw.iterrows():
        machine = str(row.get("機種名","")).strip()
        if not machine or machine in ["nan","機種名",""]:
            continue
        games = clean_number(row.get("G数"))
        diff = clean_number(row.get("差枚"))
        bb = clean_number(row.get("BB"))
        rb = clean_number(row.get("RB"))
        unit_no = str(row.get("台番号","")).replace(".0","")
        if games and games > 0:
            results.append({"機種名": machine, "台番号": unit_no,
                            "G数": games, "差枚": diff, "BB": bb, "RB": rb})
    return results

def process_store(store):
    try:
        response = requests.get(store["csv_url"], timeout=30)
        response.encoding = "utf-8"
        df_raw = pd.read_csv(StringIO(response.text), header=0, dtype=str)
    except Exception as e:
        print(f"[ERROR] {store['name']} の読み込み失敗: {e}")
        return []

    simple = parse_simple_format(df_raw)
    if simple is not None:
        print(f"  シンプル形式で読み込み")
        raw_list = simple
    else:
        print(f"  あなすろ形式で読み込み")
        raw_list = parse_anaslo_format(df_raw)

    results = []
    for item in raw_list:
        games = item["G数"] or 0
        diff = item["差枚"]
        bb = item["BB"] or 0
        rb = item["RB"] or 0
        score = calc_score(games, diff, bb, rb)
        results.append({
            "店舗名": store["name"],
            "機種名": item["機種名"],
            "台番号": item["台番号"],
            "G数_num": games,
            "差枚_num": diff or 0,
            "BB_num": int(bb),
            "RB_num": int(rb),
            "G数": f"{int(games):,}",
            "差枚": f"{int(diff):+,}" if diff is not None else "#ERROR",
            "BB": int(bb),
            "RB": int(rb),
            "スコア": score,
        })
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
