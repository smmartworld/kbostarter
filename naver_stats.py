"""
naver_stats.py
─────────────────────────────────────────────────────────────────────────────
KBO 투수 심화 스탯 통합 수집기

[데이터 소스]
 ① 네이버 스포츠 API  → WAR, K%, BB%  (JSON API, 안정적)
 ② 스탯티즈           → FIP 전용       (BeautifulSoup, FIP은 네이버에 없음)

[출력]
 pitcher_advanced_stats.csv
 컬럼: 선발투수, WAR, FIP, K%, BB%

[안전 설계]
 - 로테이션_마스터데이터.csv 절대 수정 안 함
 - 네이버/스탯티즈 어느 쪽이 실패해도 기존 파일 보존
 - 앱에서 파일 없어도 '-' 처리로 절대 안 뻗음
─────────────────────────────────────────────────────────────────────────────
"""

import os
import re
import time
import requests
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime

# ─── 상수 ────────────────────────────────────────────────────────────────────
MASTER_CSV  = "로테이션_마스터데이터.csv"
OUTPUT_CSV  = "pitcher_advanced_stats.csv"
SEASON      = 2026

# 네이버 스포츠 API
# pageSize=200: KBO 시즌 전체 투수 ~150명 이하, 루프 없이 한 번에 가져옴
NAVER_URL = (
    "https://api-gw.sports.naver.com/statistics/categories/kbo"
    "/seasons/{season}/players"
    "?sortField=pitcherEra&sortDirection=asc"
    "&playerType=PITCHER&gameType=REGULAR_SEASON"
    "&page=1&pageSize=200"
)

# 스탯티즈 투수 스탯 (FIP 전용)
STATIZ_URL = (
    "https://statiz.co.kr/stat.php"
    "?opt=1&sopt=0&re=0"
    f"&ys={SEASON}&ye={SEASON}"
    "&gp=0&pos=SP&si=&di=&li=&ti=&ki="
)

NAVER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://m.sports.naver.com/",
}
STATIZ_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Referer": "https://statiz.co.kr/",
}

# 스탯티즈 FIP 컬럼 인덱스 폴백
# 순위(0) 이름(1) 팀(2) G(3) GS(4) IP(5) W(6) L(7) SV(8) HLD(9)
# ERA(10) RA9(11) FIP(12) ...
STATIZ_FIP_IDX  = 12
STATIZ_NAME_IDX = 1


# ─── 1. 네이버 API: WAR / K% / BB% ───────────────────────────────────────────

def fetch_naver_stats() -> pd.DataFrame | None:
    """네이버 스포츠 API에서 전체 투수 시즌 스탯 수집 (단일 요청)."""
    print("\n📡 [네이버] 투수 시즌 스탯 수집 중...")

    url = NAVER_URL.format(season=SEASON)
    try:
        resp = requests.get(url, headers=NAVER_HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"   ❌ 네이버 API 요청 실패: {e}")
        return None

    if not data.get("success"):
        print(f"   ❌ 네이버 API success=false")
        return None

    players = data.get("result", {}).get("seasonPlayerStats", [])
    if not players:
        print("   ❌ 선수 데이터 없음")
        return None

    rows = []
    for p in players:
        name = p.get("playerName", "").strip()
        if not name:
            continue
        rows.append({
            "선발투수": name,
            "K%":  p.get("pitcherPaKkRate"),   # PA 기준 삼진율 (예: 17.6)
            "BB%": p.get("pitcherPaBbRate"),    # PA 기준 볼넷율 (예: 3.8)
            "WAR": p.get("pitcherWar"),
            "WPA": p.get("pitcherWpa"),         # 보관용 (선발엔 노이즈 있음)
        })

    df = pd.DataFrame(rows)
    df = df.drop_duplicates(subset="선발투수", keep="first")
    print(f"   ✅ 네이버 수집 완료: {len(df)}명 (단일 요청)")
    return df


# ─── 2. 스탯티즈: FIP 전용 ────────────────────────────────────────────────────

def _parse_fip_from_table(soup: BeautifulSoup) -> dict[str, float]:
    """스탯티즈 HTML 테이블에서 {투수이름: FIP} 딕셔너리 반환."""
    result = {}
    if soup is None:
        return result

    table = soup.find("table")
    if not table:
        return result

    # 헤더에서 FIP 컬럼 인덱스 확인 (없으면 폴백 인덱스 사용)
    fip_idx  = STATIZ_FIP_IDX
    name_idx = STATIZ_NAME_IDX

    thead = table.find("thead")
    if thead:
        headers = [th.get_text(strip=True) for th in thead.find_all(["th", "td"])]
        for i, h in enumerate(headers):
            if h == "FIP":
                fip_idx = i
            if h in ("이름", "Name"):
                name_idx = i

    tbody = table.find("tbody") or table
    for row in tbody.find_all("tr"):
        cells = [td.get_text(strip=True) for td in row.find_all(["td", "th"])]
        if len(cells) <= max(fip_idx, name_idx):
            continue
        name = cells[name_idx].strip()
        fip_raw = cells[fip_idx].strip()
        if not name or name in ("이름", "Name", ""):
            continue
        try:
            fip_val = float(fip_raw)
            result[name] = fip_val
        except ValueError:
            continue

    return result


def fetch_statiz_fip() -> dict[str, float]:
    """스탯티즈에서 {투수이름: FIP} 수집. 실패 시 빈 딕셔너리."""
    print("\n📡 [스탯티즈] FIP 수집 중...")
    session = requests.Session()
    session.headers.update(STATIZ_HEADERS)

    # 홈 방문으로 쿠키 확보
    try:
        session.get("https://statiz.co.kr/", timeout=10)
        time.sleep(0.8)
    except Exception:
        pass

    fip_dict = {}

    for label, url in [("SP", STATIZ_URL),
                        ("전체", STATIZ_URL.replace("pos=SP", "pos="))]:
        try:
            resp = session.get(url, timeout=15)
            resp.raise_for_status()
            resp.encoding = resp.apparent_encoding or "utf-8"
            soup = BeautifulSoup(resp.text, "lxml")
            fip_dict.update(_parse_fip_from_table(soup))
            print(f"   ✅ {label}: {len(fip_dict)}명 FIP 파싱")

            # 페이지네이션 체크
            for link in soup.select("a.page-link, .pagination a"):
                href = link.get("href", "")
                m = re.search(r"[?&]page=(\d+)", href)
                if m and int(m.group(1)) > 1:
                    pg_resp = session.get(url + f"&page={m.group(1)}", timeout=15)
                    pg_soup = BeautifulSoup(pg_resp.text, "lxml")
                    fip_dict.update(_parse_fip_from_table(pg_soup))
            time.sleep(0.8)
        except Exception as e:
            print(f"   ⚠️ 스탯티즈 {label} 수집 실패: {e}")

    print(f"   📊 최종 FIP 보유: {len(fip_dict)}명")
    return fip_dict


# ─── 3. 마스터 투수 명단 추출 ─────────────────────────────────────────────────

def load_master_pitchers() -> list[str]:
    if not os.path.exists(MASTER_CSV):
        print(f"❌ {MASTER_CSV} 없음")
        return []
    try:
        df = pd.read_csv(MASTER_CSV)
        pitchers = [
            p for p in df["선발투수"].dropna().unique()
            if p not in ("-", "nan", "예측 불가", "팀전체", "")
        ]
        print(f"📋 마스터 투수 명단: {len(pitchers)}명")
        return pitchers
    except Exception as e:
        print(f"❌ 마스터 파일 읽기 실패: {e}")
        return []


# ─── 4. 안전 저장 ─────────────────────────────────────────────────────────────

def save_safely(new_df: pd.DataFrame) -> bool:
    """새 데이터가 비었으면 기존 파일 보존. 부분 실패면 기존값으로 보완."""
    if new_df.empty:
        print("⚠️  저장할 데이터 없음 → 기존 파일 보존")
        return False

    if os.path.exists(OUTPUT_CSV):
        try:
            old_df = pd.read_csv(OUTPUT_CSV).set_index("선발투수")
            merged = new_df.set_index("선발투수").combine_first(old_df)
            final_df = merged.reset_index().rename(columns={"index": "선발투수"})
            print("   🔀 기존 파일과 병합 완료 (결측치는 기존값으로 보완)")
        except Exception as e:
            print(f"   ⚠️ 기존 파일 병합 실패, 새 데이터만 저장: {e}")
            final_df = new_df
    else:
        final_df = new_df

    final_df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")
    print(f"💾 저장 완료: {OUTPUT_CSV} ({len(final_df)}명)")
    return True


# ─── 메인 ─────────────────────────────────────────────────────────────────────

def run():
    print("=" * 60)
    print(f"🚀 투수 심화 스탯 수집기 [{datetime.now().strftime('%Y-%m-%d %H:%M')}]")
    print(f"   Naver: WAR / K% / BB%  |  Statiz: FIP")
    print("=" * 60)

    master_pitchers = load_master_pitchers()
    if not master_pitchers:
        return

    # ── 네이버 API 수집 ──────────────────────────────────────────────────────
    naver_df = fetch_naver_stats()

    # ── 스탯티즈 FIP 수집 ────────────────────────────────────────────────────
    fip_dict = fetch_statiz_fip()

    # ── 데이터 없으면 중단 ────────────────────────────────────────────────────
    if naver_df is None and not fip_dict:
        print("\n❌ 네이버/스탯티즈 모두 실패. 기존 파일 유지.")
        return

    # ── 마스터 투수 기준으로 병합 ─────────────────────────────────────────────
    naver_lookup = (
        naver_df.set_index("선발투수").to_dict(orient="index")
        if naver_df is not None else {}
    )

    rows = []
    matched_naver, matched_fip = 0, 0

    for p in master_pitchers:
        n = naver_lookup.get(p, {})
        f = fip_dict.get(p)

        if n:
            matched_naver += 1
        if f is not None:
            matched_fip += 1

        rows.append({
            "선발투수": p,
            "WAR":  round(n["WAR"],  2) if n.get("WAR")  is not None else None,
            "FIP":  round(f,          2) if f             is not None else None,
            "K%":   round(n["K%"],   1) if n.get("K%")   is not None else None,
            "BB%":  round(n["BB%"],  1) if n.get("BB%")  is not None else None,
        })

    result_df = pd.DataFrame(rows)

    print(f"\n📊 매칭 결과:")
    print(f"   Naver(WAR/K%/BB%): {matched_naver}/{len(master_pitchers)}명")
    print(f"   Statiz(FIP):       {matched_fip}/{len(master_pitchers)}명")

    unmatched = [p for p in master_pitchers if p not in naver_lookup and p not in fip_dict]
    if unmatched:
        print(f"   ⚠️  미매칭: {unmatched}")

    save_safely(result_df)
    print(f"\n🎉 완료!")

    # 샘플 출력
    sample = result_df.dropna(subset=["WAR"]).head(5)
    if not sample.empty:
        print("\n📋 상위 5명 샘플:")
        print(sample.to_string(index=False))


if __name__ == "__main__":
    run()
