import json
import re
import os
from datetime import datetime, timedelta

# =============================================
# 設定：店舗ごとの入力ファイル
# =============================================
STORES = [
    {"name": "将軍葛西店",       "file": "data/shogun.txt",   "slug": "shogun"},
    {"name": "メッセ西葛西店",   "file": "data/messe.txt",    "slug": "messe"},
    {"name": "ウエスタン葛西店", "file": "data/western.txt",  "slug": "western"},
    {"name": "ウエスタン西葛西店","file": "data/western2.txt", "slug": "western2"},
    {"name": "ウエスタン環七南葛西店","file": "data/western3.txt","slug": "western3"},
    {"name": "パラッツォ葛西店", "file": "data/palazzo.txt",  "slug": "palazzo"},
    {"name": "アイオン西葛西店", "file": "data/aion.txt",     "slug": "aion"},
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
        "store": "", "date": "", "total": {},
        "machine_ranking": [], "tail_ranking": [],
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
                            "総差枚": d, "平均差枚": ad,
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
                    entry["avg_diff"]   = clean_num(vals[1]) if len(vals) > 1 else None
                    entry["avg_games"]  = clean_num(vals[2]) if len(vals) > 2 else None
                    wr, wc, tc = parse_winrate(wr_str)
                    entry["win_rate"] = wr
                    entry["win_count"] = wc
                    entry["total_count"] = tc
                    break
            result["machine_ranking"].append(entry)

    # 末尾別データ
    TAIL_KEYS = ["0","1","2","3","4","5","6","7","8","9","ゾロ目"]
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
            if "\t" in line:
                vals = line.split("\t")
            else:
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
                "tail": tail, "total_diff": td, "avg_diff": ad,
                "avg_games": ag, "win_rate": wr,
                "win_count": wc, "total_count": tc,
            })

    return result

def save_log(parsed, slug):
    """日付ごとにログを保存（既存があればスキップ）"""
    if not parsed["date"]:
        return False
    date_str = parsed["date"].replace("/", "-")
    log_dir = f"logs/{slug}"
    os.makedirs(log_dir, exist_ok=True)
    log_path = f"{log_dir}/{date_str}.json"
    if os.path.exists(log_path):
        print(f"  スキップ（既存）: {log_path}")
        return False
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(parsed, f, ensure_ascii=False, indent=2)
    print(f"  ログ保存: {log_path}")
    return True

def load_logs(slug):
    """全ログを読み込んで日付順に返す"""
    log_dir = f"logs/{slug}"
    if not os.path.exists(log_dir):
        return []
    logs = []
    for fname in sorted(os.listdir(log_dir)):
        if fname.endswith(".json"):
            with open(f"{log_dir}/{fname}", "r", encoding="utf-8") as f:
                logs.append(json.load(f))
    return logs

def calc_prediction(logs, store_name):
    """
    過去ログから予測スコアを計算
    - 機種ごとの設定6投入率（差枚+・勝率が高い日の頻度）
    - 末尾ごとの勝率傾向
    - 曜日ごとの傾向
    """
    if not logs:
        return {"machine_scores": [], "tail_scores": [], "log_count": 0}

    from collections import defaultdict

    machine_stats = defaultdict(lambda: {"days": 0, "hot_days": 0, "total_diff": 0})
    tail_stats = defaultdict(lambda: {"days": 0, "win_days": 0, "win_rates": []})
    weekday_stats = defaultdict(lambda: {"days": 0, "total_diff": 0})

    for log in logs:
        date = log.get("date", "")
        try:
            dt = datetime.strptime(date, "%Y/%m/%d")
            wd = dt.weekday()  # 0=月曜
        except:
            wd = -1

        # 機種別
        for m in log.get("machine_ranking", []):
            name = m["machine"]
            machine_stats[name]["days"] += 1
            td = m.get("total_diff") or 0
            machine_stats[name]["total_diff"] += td
            wr = m.get("win_rate") or 0
            if td > 0 and wr >= 50:
                machine_stats[name]["hot_days"] += 1

        # 末尾別
        for t in log.get("tail_ranking", []):
            tail = t["tail"]
            tail_stats[tail]["days"] += 1
            wr = t.get("win_rate")
            if wr is not None:
                tail_stats[tail]["win_rates"].append(wr)
                if wr >= 50:
                    tail_stats[tail]["win_days"] += 1

        # 曜日別
        if wd >= 0:
            total = log.get("total", {})
            td = total.get("総差枚") or 0
            weekday_stats[wd]["days"] += 1
            weekday_stats[wd]["total_diff"] += td

    # 機種スコア計算
    machine_scores = []
    for name, stats in machine_stats.items():
        if stats["days"] < 2:
            continue
        hot_rate = stats["hot_days"] / stats["days"]
        avg_diff = stats["total_diff"] / stats["days"]
        score = round(hot_rate * 60 + min(avg_diff / 500, 40), 1)
        machine_scores.append({
            "machine": name,
            "score": score,
            "hot_rate": round(hot_rate * 100, 1),
            "avg_diff": round(avg_diff),
            "days": stats["days"],
        })
    machine_scores.sort(key=lambda x: x["score"], reverse=True)

    # 末尾スコア計算
    tail_scores = []
    for tail, stats in tail_stats.items():
        if not stats["win_rates"]:
            continue
        avg_wr = sum(stats["win_rates"]) / len(stats["win_rates"])
        tail_scores.append({
            "tail": tail,
            "avg_win_rate": round(avg_wr, 1),
            "days": stats["days"],
        })
    tail_scores.sort(key=lambda x: x["avg_win_rate"], reverse=True)

    # 曜日スコア
    wd_names = ["月","火","水","木","金","土","日"]
    weekday_scores = []
    for wd, stats in weekday_stats.items():
        if stats["days"] < 1:
            continue
        avg = stats["total_diff"] / stats["days"]
        weekday_scores.append({
            "weekday": wd_names[wd],
            "avg_total_diff": round(avg),
            "days": stats["days"],
        })
    weekday_scores.sort(key=lambda x: x["avg_total_diff"], reverse=True)

    return {
        "machine_scores": machine_scores[:15],
        "tail_scores": tail_scores,
        "weekday_scores": weekday_scores,
        "log_count": len(logs),
    }

def process_store(store):
    try:
        with open(store["file"], "r", encoding="utf-8") as f:
            text = f.read()
    except:
        return None

    parsed = parse_anaslo(text)
    if not parsed["store"]:
        parsed["store"] = store["name"]

    # ログ保存
    save_log(parsed, store["slug"])

    # 全ログ読み込み
    logs = load_logs(store["slug"])
    print(f"  日付: {parsed['date']} / ログ蓄積: {len(logs)}日分")
    print(f"  機種ランキング: {len(parsed['machine_ranking'])}件")
    print(f"  末尾データ: {len(parsed['tail_ranking'])}件")

    # 予測計算
    prediction = calc_prediction(logs, store["name"])

    return {
        "store": parsed["store"],
        "date": parsed["date"],
        "total": parsed["total"],
        "today": {
            "machine_ranking": parsed["machine_ranking"],
            "tail_ranking": parsed["tail_ranking"],
        },
        "prediction": prediction,
    }

def main():
    all_stores = []
    for store in STORES:
        if not os.path.exists(store["file"]):
            continue
        print(f"処理中: {store['name']}")
        data = process_store(store)
        if data:
            all_stores.append(data)

    os.makedirs("docs", exist_ok=True)
    with open("docs/data.json", "w", encoding="utf-8") as f:
        json.dump({
            "updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "stores": all_stores
        }, f, ensure_ascii=False, indent=2)

    print(f"\n完了: {len(all_stores)}店舗 → docs/data.json に保存")

if __name__ == "__main__":
    main()
