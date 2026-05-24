"""
naver_stats.py
─────────────────────────────────────────────────────────────────────────────
KBO 투수 심화 스탯 수집기 (네이버 API 단독)

[데이터 소스]
  네이버 스포츠 API (단일 요청, BeautifulSoup 불필요)

[수집 스탯]
  WAR  : pitcherWar (네이버 제공)
  K%   : pitcherPaKkRate - PA 기준 삼진율
  BB%  : pitcherPaBbRate - PA 기준 볼넷율
  FIP  : 네이버 원시 데이터(HR/BB/HBP/K/IP)로 직접 계산
         → 스탯티즈 로그인 장벽 없이 동일한 값 산출 가능

[FIP 계산 방식]
  FIP = (13×HR + 3×(BB+HBP) - 2×SO) / IP + C_FIP
  C_FIP = 리그ERA - 리그FIP(상수 제외)  (전체 투수 데이터로 직접 산출)

[출력]
  pitcher_advanced_stats.csv
  컬럼: 선발투수, WAR, FIP, K%, BB%
─────────────────────────────────────────────────────────────────────────────
"""

import os
import re
import time
import requests
import pandas as pd
from datetime import datetime

MASTER_CSV = "로테이션_마스터데이터.csv"
OUTPUT_CSV = "pitcher_advanced_stats.csv"
SEASON     = 2026

NAVER_URL = (
    "https://api-gw.sports.naver.com/statistics/categories/kbo"
    "/seasons/{season}/players"
    "?sortField=pitcherEra&sortDirection=asc"
    "&playerType=PITCHER&gameType=REGULAR_SEASON"
    "&page=1&pageSize=200"
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://m.sports.naver.com/",
}


# ─── 이닝 파싱 ("63 2/3" → 63.667) ──────────────────────────────────────────

def parse_inning(inn_str: str) -> float:
    """'63 2/3', '51', '54 1/3' 같은 네이버 이닝 문자열 → float."""
    try:
        s = str(inn_str).strip()
        if not s or s in ('-', ''):
            return 0.0
        parts = s.split()
        if len(parts) == 2:
            whole = float(parts[0])
            num, den = parts[1].split('/')
            return whole + float(num) / float(den)
        return float(s)
    except Exception:
        return 0.0


# ─── FIP 계산 ─────────────────────────────────────────────────────────────────

def calculate_fip(players: list) -> dict[str, float]:
    """
    네이버 API 투수 리스트에서 FIP을 직접 계산.

    공식: FIP = (13×HR + 3×(BB+HBP) - 2×SO) / IP + C_FIP
    C_FIP: 리그 ERA - 리그 FIP(상수 제외) 로 자동 산출
    """
    # ── 리그 집계 (FIP 상수 계산용) ──────────────────────────────────────────
    lg_er  = sum(p.get('pitcherEr',  0) or 0 for p in players)
    lg_ip  = sum(parse_inning(p.get('pitcherInning', '0')) for p in players)
    lg_hr  = sum(p.get('pitcherHr',  0) or 0 for p in players)
    lg_bb  = sum(p.get('pitcherBb',  0) or 0 for p in players)
    lg_hp  = sum(p.get('pitcherHp',  0) or 0 for p in players)
    lg_k   = sum(p.get('pitcherKk',  0) or 0 for p in players)

    if lg_ip <= 0:
        print("   ⚠️  이닝 합계 0 — FIP 상수 계산 불가")
        return {}

    league_era = (lg_er * 9) / lg_ip
    fip_no_c   = (13 * lg_hr + 3 * (lg_bb + lg_hp) - 2 * lg_k) / lg_ip
    c_fip      = league_era - fip_no_c

    print(f"   📐 리그ERA: {league_era:.3f} | FIP상수(C): {c_fip:.3f}")

    # ── 개별 FIP 계산 ─────────────────────────────────────────────────────────
    result = {}
    for p in players:
        name = p.get('playerName', '').strip()
        ip   = parse_inning(p.get('pitcherInning', '0'))
        if ip <= 0:
            continue
        hr = p.get('pitcherHr', 0) or 0
        bb = p.get('pitcherBb', 0) or 0
        hp = p.get('pitcherHp', 0) or 0
        k  = p.get('pitcherKk', 0) or 0
        fip = (13 * hr + 3 * (bb + hp) - 2 * k) / ip + c_fip
        result[name] = round(fip, 2)

    print(f"   ✅ FIP 계산 완료: {len(result)}명")
    return result


# ─── 네이버 API 수집 ──────────────────────────────────────────────────────────

def fetch_naver_stats() -> tuple[pd.DataFrame | None, list]:
    """네이버 API 단일 요청. (DataFrame, 원시 players 리스트) 반환."""
    print("\n📡 [네이버] 투수 시즌 스탯 수집 중...")

    url = NAVER_URL.format(season=SEASON)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"   ❌ 네이버 API 실패: {e}")
        return None, []

    if not data.get("success"):
        print("   ❌ success=false")
        return None, []

    players = data.get("result", {}).get("seasonPlayerStats", [])
    if not players:
        print("   ❌ 선수 데이터 없음")
        return None, []

    rows = []
    for p in players:
        name = p.get("playerName", "").strip()
        if not name:
            continue
        rows.append({
            "선발투수": name,
            "WAR": p.get("pitcherWar"),
            "K%":  p.get("pitcherPaKkRate"),
            "BB%": p.get("pitcherPaBbRate"),
        })

    df = pd.DataFrame(rows).drop_duplicates(subset="선발투수", keep="first")
    print(f"   ✅ 네이버 수집 완료: {len(df)}명 (단일 요청)")
    return df, players


# ─── 마스터 투수 명단 ─────────────────────────────────────────────────────────

def load_master_pitchers() -> list[str]:
    if not os.path.exists(MASTER_CSV):
        print(f"❌ {MASTER_CSV} 없음")
        return []
    try:
        df = pd.read_csv(MASTER_CSV)
        pitchers = [
            p for p in df["선발투수"].dropna().unique()
            if str(p) not in ("-", "nan", "예측 불가", "팀전체", "")
        ]
        print(f"📋 마스터 투수: {len(pitchers)}명")
        return pitchers
    except Exception as e:
        print(f"❌ 마스터 파일 읽기 실패: {e}")
        return []


# ─── 안전 저장 ────────────────────────────────────────────────────────────────

def save_safely(new_df: pd.DataFrame) -> bool:
    if new_df.empty:
        print("⚠️  저장 데이터 없음 → 기존 파일 보존")
        return False

    if os.path.exists(OUTPUT_CSV):
        try:
            old_df = pd.read_csv(OUTPUT_CSV).set_index("선발투수")
            merged = new_df.set_index("선발투수").combine_first(old_df)
            final_df = merged.reset_index().rename(columns={"index": "선발투수"})
        except Exception:
            final_df = new_df
    else:
        final_df = new_df

    final_df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")
    print(f"💾 저장: {OUTPUT_CSV} ({len(final_df)}명)")
    return True


# ─── 메인 ─────────────────────────────────────────────────────────────────────

def run():
    print("=" * 60)
    print(f"🚀 투수 심화 스탯 수집기 [{datetime.now().strftime('%Y-%m-%d %H:%M')}]")
    print(f"   Naver API: WAR / K% / BB% / FIP(자체계산)")
    print("=" * 60)

    master_pitchers = load_master_pitchers()
    if not master_pitchers:
        return

    naver_df, raw_players = fetch_naver_stats()
    if naver_df is None:
        print("\n❌ 네이버 실패. 기존 파일 유지.")
        return

    # FIP 직접 계산 (네이버 원시 데이터 활용)
    fip_dict = calculate_fip(raw_players)

    # FIP을 naver_df에 합치기
    naver_df["FIP"] = naver_df["선발투수"].map(fip_dict)

    # 마스터 투수 기준으로 필터 & 정렬
    naver_lookup = naver_df.set_index("선발투수").to_dict(orient="index")

    rows = []
    matched = 0
    for p in master_pitchers:
        n = naver_lookup.get(p, {})
        if n:
            matched += 1
        rows.append({
            "선발투수": p,
            "WAR": round(n["WAR"],  2) if n.get("WAR")  is not None else None,
            "FIP": round(n["FIP"],  2) if n.get("FIP")  is not None else None,
            "K%":  round(n["K%"],   1) if n.get("K%")   is not None else None,
            "BB%": round(n["BB%"],  1) if n.get("BB%")  is not None else None,
        })

    result_df = pd.DataFrame(rows)
    unmatched = [p for p in master_pitchers if p not in naver_lookup]

    print(f"\n📊 매칭: {matched}/{len(master_pitchers)}명")
    if unmatched:
        print(f"   ⚠️  미매칭 {len(unmatched)}명: {unmatched}")

    save_safely(result_df)

    # 샘플 출력 (FIP 확인용)
    sample = result_df.dropna(subset=["FIP"]).head(8)
    if not sample.empty:
        print("\n📋 FIP 계산 샘플 (상위 8명):") 
        print(sample.to_string(index=False))

    print(f"\n🎉 완료!")


if __name__ == "__main__":
    run()
