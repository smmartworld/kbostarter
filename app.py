import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import os
import calendar as cal_module
import time
from datetime import date, timedelta
from predictor import (
    predict_starter, get_active_rotation,
    get_pitcher_recent_stats, get_season_stats,
    get_recent_rotation_list, TEAM_COLORS
)

st.set_page_config(page_title="선발누구⚾", page_icon="⚾", layout="wide")

st.markdown("""
<style>
    header {visibility: hidden;}
    #MainMenu {visibility: hidden;}
    .block-container { padding-top: 1rem; padding-bottom: 0rem; max-width: 1200px; }
    .stApp { background: #ffffff; }
    
    .main-title { text-align: center; font-size: 2rem; font-weight: 900; color: #1a202c; margin-bottom: 12px; }
    
    .cal-wrap { background: #f7fafc; border: 1px solid #e2e8f0; border-radius: 16px; padding: 16px 20px; margin-bottom: 20px; }
    @media (max-width: 768px) {
        .block-container { padding-left: 0.2rem; padding-right: 0.2rem; }
        .cal-wrap { overflow-x: auto; padding: 10px; }
        /* 달력 너비와 버튼 크기를 모바일에 맞게 축소 */
        .cal-wrap [data-testid="stHorizontalBlock"] { flex-wrap: nowrap !important; min-width: 100% !important; }
        .cal-wrap div[data-testid="column"] { min-width: 45px !important; width: 14% !important; flex: 1 1 auto !important; }
        div[data-testid="stButton"] button { padding: 0.1rem 0 !important; font-size: 0.7rem; min-height: 40px !important; }
    }

    .cal-nav-title { text-align: center; font-size: 1.15rem; font-weight: 800; color: #2d3748; padding: 4px 0; }
    .cal-day-name { text-align: center; font-size: 0.78rem; font-weight: 700; color: #718096; padding: 8px 0 4px 0; }
    .cal-empty { height: 36px; }
    .cal-noGame { text-align: center; padding: 6px 0; font-size: 0.88rem; color: #cbd5e0; height: 36px; }
    
    .match-card { background: #f7fafc; border: 1.5px solid #e2e8f0; border-radius: 12px; padding: 12px 8px; text-align: center; margin-bottom: 4px; min-height: 100px; }
    .match-card.sel { background: #ebf8ff; border-color: #4299e1; }
    .mc-teams { font-size: 0.88rem; font-weight: 700; color: #2d3748; margin-top: 4px; }
    .mc-done { font-size: 0.78rem; color: #276749; font-weight: 600; }
    .mc-plan { font-size: 0.78rem; color: #c05621; font-weight: 600; }
    .mc-cancel { font-size: 0.78rem; color: #9b2c2c; }
    .mc-manual { font-size: 0.78rem; color: #3182ce; font-weight: 800; }
    
    .mc-logo-wrap { display: inline-flex; justify-content: center; align-items: center; width: 36px; height: 36px; border-radius: 50%; overflow: hidden; background-color: white; }
    .mc-logo-wrap img { width: 100%; height: 100%; object-fit: contain; }
    
    .team-panel { border-radius: 14px; padding: 18px 16px; height: 100%; width: 100% !important; box-sizing: border-box; }
    .team-name-big { font-size: 1.5rem; font-weight: 900; line-height: 1.2; }
    .team-label-small { font-size: 0.7rem; font-weight: 700; color: #a0aec0; }
    .sec-label { font-size: 0.72rem; font-weight: 800; color: #a0aec0; margin: 12px 0 5px 0; }
    .score-banner { background: #f0fff4; border: 1px solid #9ae6b4; border-radius: 10px; padding: 10px 20px; text-align: center; font-size: 1.35rem; font-weight: 800; color: #276749; margin: 8px 0 16px 0; }
    .score-banner.upcoming { background: #fffaf0; border-color: #fbd38d; color: #c05621; font-size: 0.95rem; }
    
    .stat-badge { display: inline-block; background: #edf2f7; border-radius: 6px; padding: 3px 10px; font-size: 0.78rem; color: #4a5568; margin: 2px 3px 2px 0; white-space: nowrap; }
    
    /* 🔥 새로 추가된 투수 스탯 그리드 & 보더 뱃지 스타일 */
    .pitcher-stat-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; width: 100%; box-sizing: border-box; }
    
    .border-badge {
        display: flex; flex-direction: column; justify-content: center;
        background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px;
        padding: 2px 8px; height: 38px; box-sizing: border-box;
        box-shadow: 0 1px 2px rgba(0,0,0,0.02);
    }
    .border-badge .bb-label { font-size: 0.68rem; font-weight: 700; color: #718096; margin-bottom: 1px; }
    .border-badge .bb-value { font-size: 0.82rem; font-weight: 800; color: #1a202c; }

    .border-gray   { border-left: 4px solid #cbd5e0; } /* 기본 정보 (회색) */
    .border-red    { border-left: 4px solid #f56565; } /* 실점 관련 (옅은 적색) */
    .border-blue   { border-left: 4px solid #4299e1; } /* 제구 관련 (옅은 청색) */
    .border-green  { border-left: 4px solid #48bb78; } /* 종합 체급 (옅은 초록색) */

    div[data-testid="stButton"] button { height: auto !important; min-height: 75px !important; padding: 6px 2px !important; }
    div[data-testid="stButton"] button p { white-space: pre-wrap !important; word-break: keep-all !important; line-height: 1.4 !important; font-size: 0.85rem !important; }
    .nav-button-container div[data-testid="stButton"] button { min-height: 40px !important; padding: 4px 8px !important; }
    
    .absence-badge { background: #fff5f5; border: 1px solid #fed7d7; color: #c53030; padding: 4px 10px; border-radius: 8px; font-size: 0.8rem; font-weight: 700; display: inline-block; margin-bottom: 8px;}
    .absence-badge-local { background: #ebf8ff; border: 1px solid #bee3f8; color: #2b6cb0; padding: 4px 10px; border-radius: 8px; font-size: 0.8rem; font-weight: 700; display: inline-block; margin-bottom: 8px;}
    .absence-badge-drop { background: #edf2f7; border: 1px solid #e2e8f0; color: #718096; padding: 4px 10px; border-radius: 8px; font-size: 0.8rem; font-weight: 700; display: inline-block; margin-bottom: 8px;}
    
    .admin-panel { background: #fffaf0; border: 2px solid #fbd38d; border-radius: 12px; padding: 15px 20px; margin-bottom: 20px; }
</style>
""", unsafe_allow_html=True)

STADIUMS = {
    'LG': '잠실', '두산': '잠실', '키움': '고척', 'SSG': '문학', 
    'KT': '수원', '한화': '대전', '삼성': '대구', '롯데': '부산', 'NC': '창원', 'KIA': '광주'
}

from streamlit_gsheets import GSheetsConnection
conn = st.connection("gsheets", type=GSheetsConnection)
SHEET_URL = "https://docs.google.com/spreadsheets/d/183uhIBmpzZ76B4S-4Y-_1B54cF6NThycuGYDKtQUhx8/edit?usp=sharing"

@st.cache_data(ttl=1800)
def load_data():
    df = pd.read_csv('로테이션_마스터데이터.csv')
    df['날짜'] = pd.to_datetime(df['날짜'])
    return df

try:
    original_df = load_data()
except FileNotFoundError:
    st.error("❌ 데이터 파일 없음. data.py 먼저 실행 필요.")
    st.stop()

# ── 스탯티즈 심화 스탯 로드 (없어도 앱은 정상 동작) ──────────────────────────
@st.cache_data(ttl=3600)
def load_advanced_stats() -> pd.DataFrame:
    """pitcher_advanced_stats.csv 로드. 없으면 빈 DataFrame 반환."""
    # 구버전 statiz_stats.csv도 fallback으로 읽음 (마이그레이션 대응)
    for fname in ['pitcher_advanced_stats.csv', 'statiz_stats.csv']:
        if not os.path.exists(fname):
            continue
        try:
            df = pd.read_csv(fname)
            for col in ['WAR', 'FIP', 'K%', 'BB%']:
                if col not in df.columns:
                    df[col] = None
            return df
        except Exception:
            continue
    return pd.DataFrame(columns=['선발투수', 'WAR', 'FIP', 'K%', 'BB%'])

adv_stats_df = load_advanced_stats()

def get_advanced_stats(pitcher_name: str) -> dict:
    """투수 심화 스탯 조회. 없으면 '-' 반환."""
    empty = {'WAR': '-', 'FIP': '-', 'K%': '-', 'BB%': '-'}
    if adv_stats_df.empty:
        return empty
    row = adv_stats_df[adv_stats_df['선발투수'] == pitcher_name]
    if row.empty:
        return empty
    r = row.iloc[0]
    def fmt(val, decimals=2):
        try:
            return f"{float(val):.{decimals}f}" if pd.notna(val) else '-'
        except (ValueError, TypeError):
            return '-'
    return {
        'WAR': fmt(r.get('WAR'), 2),
        'FIP': fmt(r.get('FIP'), 2),
        'K%':  fmt(r.get('K%'),  1),
        'BB%': fmt(r.get('BB%'), 1),
    }

def load_manager_data():
    try:
        db_df = conn.read(spreadsheet=SHEET_URL, usecols=[0,1,2,3], ttl=0)
        db_df = db_df.dropna(how="all")
        return db_df
    except Exception as e:
        return pd.DataFrame(columns=['팀', '선수', '타입', '날짜'])

db_df = load_manager_data()

db_overrides = {}
db_absences = {}
db_excluded = set()
db_cancels = set() # 🔥 [NEW] DB 우취 명단

for _, row in db_df.iterrows():
    if pd.isna(row.get('팀')) or pd.isna(row.get('선수')): continue
    t = str(row['팀']).strip()
    p = str(row['선수']).strip()
    m_type = str(row['타입']).strip()
    d_str = str(row['날짜']).strip()
    
    if m_type == "선발 지정":
        db_overrides[(t, d_str)] = p
    elif m_type == "휴식/말소":
        db_absences[(t, p)] = pd.to_datetime(d_str).date()
    elif m_type == "로테이션 제외":
        db_excluded.add((t, p))
    elif m_type == "우천취소": # 🔥 [NEW] 우취 파싱
        db_cancels.add((t, d_str))

_defaults = {'cal_year': 2026, 'cal_month': 5, 'selected_date': date(2026, 5, 4), 'selected_game': None, 'pitcher_away': None, 'pitcher_home': None, 'my_team': '삼성', 'overrides': {}, 'absences': {}, 'cancels': set(), 'admin_unlocked': False}
for k, v in _defaults.items():
    if k not in st.session_state: st.session_state[k] = v

st.markdown('<div class="main-title">⚾선발누구⚾</div>', unsafe_allow_html=True)

col_a, col_b, col_c = st.columns([1, 2, 1])

with col_a:
    st.markdown("<div style='margin-top: 32px;'></div>", unsafe_allow_html=True)
    show_admin = st.toggle("🛠️ 관리자 모드")

with col_b:
    st.session_state.my_team = st.selectbox("📣 나의 응원팀", list(TEAM_COLORS.keys()), index=list(TEAM_COLORS.keys()).index(st.session_state.my_team), label_visibility="collapsed")

if show_admin:
    st.markdown('<div class="admin-panel">', unsafe_allow_html=True)
    if not st.session_state.admin_unlocked:
        st.markdown("**🔒 관리자 모드 잠금 해제**")
        pw_c1, pw_c2 = st.columns([3, 1])
        with pw_c1:
            pw = st.text_input("비밀번호", type="password", placeholder="비밀번호를 입력하세요", label_visibility="collapsed")
        with pw_c2:
            if st.button("해제", use_container_width=True):
                if pw == "password12":
                    st.session_state.admin_unlocked = True
                    st.rerun()
                else:
                    st.error("비밀번호 오류!")
    else:
        lock_c1, lock_c2 = st.columns([4, 1])
        with lock_c1:
            st.markdown("### 🔓 DB 관리 패널")
        with lock_c2:
            if st.button("🔒 닫기", use_container_width=True):
                st.session_state.admin_unlocked = False
                st.rerun()
                
        c1, c2, c3 = st.columns([2, 2, 4]) # 🔥 라디오 버튼이 길어져서 비율 조정!
        with c1:
            m_team = st.selectbox("구단", list(TEAM_COLORS.keys()), key="adm_t")
        with c2:
            active_p = get_active_rotation(original_df, m_team, date.today() + timedelta(days=7))
            if not active_p: active_p = ["선발 기록 없음"]
            m_player = st.selectbox("선수", active_p, key="adm_p")
            custom_player = st.text_input("직접 입력 (콜업 등)", placeholder="예: 양창섭")
            final_player = custom_player if custom_player else m_player
        # 수정 후
        with c3:
            # 🔥 우천취소 옵션 추가!
            m_type = st.radio("변동 유형", ["선발 지정", "휴식/말소", "로테이션 제외", "우천취소"], key="adm_type", horizontal=True)
            
        c4, c5 = st.columns([3, 1])
        with c4:
            if m_type == "선발 지정":
                m_date = st.date_input("선발 등판 확정일", value=date.today())
            elif m_type == "휴식/말소":
                m_date = st.date_input("복귀 예정일 (이 날부터 등판 가능)", value=date.today() + timedelta(days=10))
            elif m_type == "우천취소": # 🔥 [NEW] 우취 UI
                st.info("☔ 해당 날짜의 경기를 우천취소 처리하여 로테이션을 하루 밉니다.")
                m_date = st.date_input("우천취소 날짜", value=date.today())
                final_player = "팀전체" # 선수가 특정되지 않으므로 팀전체로 넣음
            else:
                st.info("🚫 해당 투수를 선발 로테이션 계산에서 즉시 제외합니다.")
                m_date = date.today()
                
        with c5:
            st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
            if st.button("💾 DB 저장", type="primary", use_container_width=True):
                if final_player and final_player != "선발 기록 없음":
                    new_row = pd.DataFrame([{'팀': m_team, '선수': final_player, '타입': m_type, '날짜': m_date.strftime("%Y-%m-%d")}])
                    updated_df = pd.concat([db_df, new_row], ignore_index=True)
                    try:
                        conn.update(spreadsheet=SHEET_URL, data=updated_df)
                        st.success("✅ 시트에 저장됨!")
                        time.sleep(0.5)
                        st.rerun()
                    except Exception as e:
                        st.error(f"저장 실패! 에러 로그: {e}")
                        
        if not db_df.empty:
            st.divider()
            st.markdown("**📋 현재 DB 등록 현황**")
            for i, row in db_df.iterrows():
                t, p, typ, d = row['팀'], row['선수'], row['타입'], row['날짜']
                # 🔥 [NEW] 뱃지 아이콘 분기
                icon = "🎯" if typ == "선발 지정" else ("⏸️" if typ == "휴식/말소" else "🚫")
                dc1, dc2 = st.columns([4, 1])
                with dc1:
                    if typ == "로테이션 제외":
                        st.markdown(f"**{t}** | {icon} {p} (완전 제외)")
                    else:
                        st.markdown(f"**{t}** | {icon} {p} ({d})")
                with dc2:
                    if st.button("✖ 삭제", key=f"del_{i}", use_container_width=True):
                        updated_df = db_df.drop(index=i)
                        conn.update(spreadsheet=SHEET_URL, data=updated_df)
                        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)


working_df = original_df.copy()

# 🔥 [NEW] 우취 명단 자동 확장 로직
# db_cancels와 session_state.cancels를 합친 뒤, 상대팀도 찾아서 같이 넣어줌!
all_cancels = set(db_cancels) | st.session_state.cancels
expanded_cancels = set()

for t, d_str in all_cancels:
    expanded_cancels.add((t, d_str))
    # 해당 날짜, 해당 팀의 데이터 찾아서 상대팀 알아내기
    mask = (working_df['팀'] == t) & (working_df['날짜'] == pd.to_datetime(d_str))
    if not working_df[mask].empty:
        opp = working_df[mask].iloc[0]['상대팀']
        expanded_cancels.add((opp, d_str))

# 🔥 [NEW] 1단계: 구글 시트 DB 강제 지정 적용 (오피셜이 없을 때만 백엔드 데이터에 반영!)
for (team, dt_str), pitcher in db_overrides.items():
    dt_pd = pd.to_datetime(dt_str)
    mask = (working_df['팀'] == team) & (working_df['날짜'] == dt_pd)
    if mask.any():

        current_status = working_df.loc[mask, '상태'].values[0]

        # 🔥 종료 경기면 실제 데이터 우선
        if current_status == '종료':
            continue
        current_pitcher = working_df.loc[mask, '선발투수'].values[0]
        
        # 이미 현실 KBO 오피셜 선발투수가 나온 상태('예정'이면서 투수가 있는 경우)라면 DB 지정을 패스!
        if current_status == '예정' and pd.notna(current_pitcher) and current_pitcher != '-':
            continue
            
        working_df.loc[mask, '선발투수'] = pitcher
        working_df.loc[mask, '상태'] = '수동확정' 

# 🔥 [NEW] 2단계: 로컬 샌드박스 수동 지정 적용 (유저의 What-if 테스트를 위해 백엔드 데이터에 반영!)
for (team, dt_str), pitcher in st.session_state.overrides.items():
    dt_pd = pd.to_datetime(dt_str)
    mask = (working_df['팀'] == team) & (working_df['날짜'] == dt_pd)
    if mask.any():
        working_df.loc[mask, '선발투수'] = pitcher
        working_df.loc[mask, '상태'] = '수동확정'

year, month = st.session_state.cal_year, st.session_state.cal_month
month_df = working_df[(working_df['날짜'].dt.year == year) & (working_df['날짜'].dt.month == month)]
game_days = set(month_df['날짜'].dt.day.unique())

st.markdown('<div class="cal-wrap">', unsafe_allow_html=True)
nav1, nav2, nav3 = st.columns([1, 6, 1])
with nav1:
    if st.button("◀", use_container_width=True, key="prev_month"):
        st.session_state.cal_year -= 1 if month == 1 else 0
        st.session_state.cal_month = 12 if month == 1 else month - 1
        st.rerun()
with nav2: st.markdown(f'<div class="cal-nav-title">{year}년 {month}월</div>', unsafe_allow_html=True)
with nav3:
    if st.button("▶", use_container_width=True, key="next_month"):
        st.session_state.cal_year += 1 if month == 12 else 0
        st.session_state.cal_month = 1 if month == 12 else month + 1
        st.rerun()

day_names = ['월', '화', '수', '목', '금', '토', '일']
hcols = st.columns(7)
for i, d in enumerate(day_names): hcols[i].markdown(f'<div class="cal-day-name">{d}</div>', unsafe_allow_html=True)

my_all_games = working_df[((working_df['팀'] == st.session_state.my_team) | (working_df['상대팀'] == st.session_state.my_team)) & (working_df['구장'] == '원정')].copy()
my_all_games = my_all_games.sort_values('날짜')

sel_date = st.session_state.selected_date
for week in cal_module.monthcalendar(year, month):
    row_cols = st.columns(7)
    for i, day in enumerate(week):
        with row_cols[i]:
            if day == 0: 
                st.markdown('<div class="cal-empty"></div>', unsafe_allow_html=True)
            elif day in game_days:
                is_sel = (sel_date == date(year, month, day))
                day_pd = pd.to_datetime(date(year, month, day))
                
                my_day_game = my_all_games[my_all_games['날짜'] == day_pd]
                btn_label = str(day)
                
                if not my_day_game.empty:
                    r = my_day_game.iloc[0]
                    is_away = (r['팀'] == st.session_state.my_team)
                    g_status = r['상태']
                    opp_team = r['상대팀'] if is_away else r['팀']
                    
                    if g_status == '종료':
                        try:
                            my_s = int(r['득점']) if is_away else int(r['실점'])
                            opp_s = int(r['실점']) if is_away else int(r['득점'])
                            if my_s > opp_s: btn_label = f"{day} 🔵" 
                            elif my_s < opp_s: btn_label = f"{day} 🔴" 
                            else: btn_label = f"{day} 🟢" 
                        except: btn_label = f"{day} ✅"
                    elif g_status == '우천취소': 
                        btn_label = f"{day} ⚪"
                    elif str(r['선발투수']) != '-':
                        btn_label = f"{day} ✅"
                    
                    yesterday_pd = day_pd - timedelta(days=1)
                    yesterday_game = my_all_games[my_all_games['날짜'] == yesterday_pd]
                    
                    is_new_series = False
                    if yesterday_game.empty: is_new_series = True
                    else:
                        y_r = yesterday_game.iloc[0]
                        y_is_away = (y_r['팀'] == st.session_state.my_team)
                        y_opp_team = y_r['상대팀'] if y_is_away else y_r['팀']
                        if (y_opp_team != opp_team) or (y_is_away != is_away): is_new_series = True
                    
                    if is_new_series:
                        stadium = STADIUMS.get(opp_team) if is_away else STADIUMS.get(st.session_state.my_team)
                        stadium_str = stadium if stadium else "?"
                        btn_label += f"\n(원정,{stadium_str})" if is_away else f"\n(홈,{stadium_str})"

                if st.button(btn_label, key=f"cd_{year}_{month}_{day}", type="primary" if is_sel else "secondary", use_container_width=True):
                    st.session_state.selected_date = date(year, month, day)
                    st.session_state.pitcher_away = None 
                    st.session_state.pitcher_home = None 
                    if not my_day_game.empty:
                        r = my_day_game.iloc[0]
                        st.session_state.selected_game = {'away': r['팀'], 'home': r['상대팀'], 'status': r['상태'], 'away_score': r['득점'], 'home_score': r['실점']}
                    else:
                        st.session_state.selected_game = None
                    st.rerun()
            else: 
                st.markdown(f'<div class="cal-noGame">{day} ⚪</div>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

selected_dt = pd.to_datetime(st.session_state.selected_date)
day_df = working_df[working_df['날짜'] == selected_dt]
matchups = day_df[day_df['구장'] == '원정'][['팀', '상대팀', '상태', '득점', '실점']].copy()
matchups.columns = ['원정팀', '홈팀', '상태', '원정점수', '홈점수']

if not matchups.empty:
    mcols = st.columns(min(len(matchups), 5))
    for i, (_, row) in enumerate(matchups.reset_index().iterrows()):
        with mcols[i % 5]:
            is_sel = (st.session_state.selected_game and st.session_state.selected_game['away'] == row['원정팀'])
            card_cls = "match-card sel" if is_sel else "match-card"
            
            if row['상태'] == '종료': status_html = f'<div class="mc-done">✅ {row["원정점수"]}:{row["홈점수"]}</div>'
            elif row['상태'] == '우천취소': status_html = '<div class="mc-cancel">☔ 우천취소</div>'
            elif row['상태'] == '수동확정': status_html = '<div class="mc-manual">🛠️ 수동확정</div>'
            else: status_html = '<div class="mc-plan">⏰ 예정</div>'
            
            c_away, c_home = TEAM_COLORS.get(row['원정팀'], '#000'), TEAM_COLORS.get(row['홈팀'], '#000')
            
            away_logo = f"https://raw.githubusercontent.com/smmartworld/kbostarter/main/images/{row['원정팀']}.png"
            home_logo = f"https://raw.githubusercontent.com/smmartworld/kbostarter/main/images/{row['홈팀']}.png"
            fallback_logo = "https://sports-phinf.pstatic.net/player/kbo/default/empty_player.png"

            st.markdown(f"""
            <div class="{card_cls}">
                <div style="display:flex;justify-content:center;align-items:center;gap:6px;">
                    <div class="mc-logo-wrap">
                        <img src="{away_logo}" onerror="this.onerror=null; this.src='{fallback_logo}'">
                    </div>
                    <span style="color:#a0aec0;font-size:0.75rem;">vs</span>
                    <div class="mc-logo-wrap">
                        <img src="{home_logo}" onerror="this.onerror=null; this.src='{fallback_logo}'">
                    </div>
                </div>
                <div class="mc-teams">{row['원정팀']} vs {row['홈팀']}</div>
                {status_html}
            </div>
            """, unsafe_allow_html=True)

            if st.button("✔ 보는 중" if is_sel else "경기 보기", key=f"gm_{i}_{row['원정팀']}", use_container_width=True):
                st.session_state.selected_game = {'away': row['원정팀'], 'home': row['홈팀'], 'status': row['상태'], 'away_score': row['원정점수'], 'home_score': row['홈점수']}
                st.session_state.pitcher_away = None 
                st.session_state.pitcher_home = None 
                st.rerun()

if not st.session_state.selected_game: st.stop()

g = st.session_state.selected_game
away_team, home_team, status = g['away'], g['home'], g['status']

st.divider()

prev_game_date = None
next_game_date = None

my_team_real_games = my_all_games[my_all_games['상태'] != '우천취소']

if not my_team_real_games.empty:
    past_games = my_team_real_games[my_team_real_games['날짜'] < selected_dt]
    if not past_games.empty:
        prev_game_date = past_games.iloc[-1]['날짜'].date()
        
    future_games = my_team_real_games[my_team_real_games['날짜'] > selected_dt]
    if not future_games.empty:
        next_game_date = future_games.iloc[0]['날짜'].date()

st.markdown('<div class="nav-button-container">', unsafe_allow_html=True)
nav_col1, nav_col2, nav_col3 = st.columns([1, 4, 1])

with nav_col1:
    if prev_game_date:
        if st.button(f"⏪ {prev_game_date.strftime('%m/%d')} 경기", use_container_width=True):
            st.session_state.selected_date = prev_game_date
            st.session_state.cal_year = prev_game_date.year
            st.session_state.cal_month = prev_game_date.month
            
            prev_pd = pd.to_datetime(prev_game_date)
            p_game = my_all_games[my_all_games['날짜'] == prev_pd].iloc[0]
            st.session_state.selected_game = {'away': p_game['팀'], 'home': p_game['상대팀'], 'status': p_game['상태'], 'away_score': p_game['득점'], 'home_score': p_game['실점']}
            st.session_state.pitcher_away = None 
            st.session_state.pitcher_home = None 
            st.rerun()

with nav_col2:
    if status == '종료':
        st.markdown(f'<div class="score-banner">{away_team} &nbsp; {g["away_score"]} : {g["home_score"]} &nbsp; {home_team}</div>', unsafe_allow_html=True)
    elif status == '우천취소':
        st.error(f"☔ {away_team} vs {home_team} — 우천취소된 경기입니다."); st.stop()
    else:
        st.markdown(f'<div class="score-banner upcoming">⏰ {away_team} vs {home_team} — 선발 투수 프리뷰</div>', unsafe_allow_html=True)

with nav_col3:
    if next_game_date:
        if st.button(f"{next_game_date.strftime('%m/%d')} 경기 ⏩", use_container_width=True):
            st.session_state.selected_date = next_game_date
            st.session_state.cal_year = next_game_date.year
            st.session_state.cal_month = next_game_date.month
            
            n_pd = pd.to_datetime(next_game_date)
            n_game = my_all_games[my_all_games['날짜'] == n_pd].iloc[0]
            st.session_state.selected_game = {'away': n_game['팀'], 'home': n_game['상대팀'], 'status': n_game['상태'], 'away_score': n_game['득점'], 'home_score': n_game['실점']}
            st.session_state.pitcher_away = None 
            st.session_state.pitcher_home = None 
            st.rerun()
st.markdown('</div>', unsafe_allow_html=True)

left_col, right_col = st.columns(2)

def render_team_panel(col, team: str, pitcher_key: str, is_away: bool):
    with col:
        color = TEAM_COLORS.get(team, '#4299e1')
        
        st.markdown(f"""
        <div class="team-panel" style="background-color: {color}1a; border: 2px solid {color};">
            <div style="display:flex;align-items:center;gap:14px;margin-bottom:10px;">
                <img src="https://raw.githubusercontent.com/smmartworld/kbostarter/main/images/{team}.png" width="55" style="border-radius: 50%;" onerror="this.style.display='none'">
                <div>
                    <div class="team-label-small">{"원정팀" if is_away else "홈팀"}</div>
                    <div class="team-name-big" style="color:{color};">{team}</div>
                </div>
            </div>
        """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        if status == '종료':
            actual_row = working_df[(working_df['날짜'] == selected_dt) & (working_df['팀'] == team) & (working_df['상태'] == '종료')]
            if actual_row.empty: st.warning("선발 기록 없음"); return
            r = actual_row.iloc[0]
            show_pitcher = r["선발투수"]
            
            st.markdown(f'<div class="sec-label">실제 선발 투수</div><div style="font-size:1.4rem;font-weight:900;">{show_pitcher}</div>', unsafe_allow_html=True)
            st.markdown(f'<span class="stat-badge">당일 이닝 <b>{r["이닝"]}</b></span><span class="stat-badge">당일 자책 <b>{r["자책점"]}</b></span><span class="stat-badge">당일 투구 <b>{r["투구수"]}</b></span>', unsafe_allow_html=True)
            
            s = get_season_stats(working_df, show_pitcher, selected_dt)
            st.markdown(f'<div style="margin:8px 0 2px 0;"><span class="stat-badge">시즌 등판 <b>{s["등판"]}회</b></span><span class="stat-badge">시즌 ERA <b>{s["ERA"]}</b></span></div>', unsafe_allow_html=True)
        else:
            dt_str = selected_dt.strftime('%Y-%m-%d')
            local_override_val = st.session_state.overrides.get((team, dt_str))
            
            t_col1, t_col2, t_col3 = st.columns(3)
            with t_col1:
                use_manual = st.toggle(f"🛠️ 수동 지정", value=(local_override_val is not None), key=f"man_{team}_{dt_str}")
            with t_col2:
                use_absence = st.toggle(f"⏸️ 휴식/말소", key=f"abs_tgl_{team}_{dt_str}")
            with t_col3:
                # 🔥 expanded_cancels를 확인해서 상대팀이 우취됐어도 토글이 같이 켜지게 만듦!
                is_cancelled = (team, dt_str) in expanded_cancels
                use_cancel = st.toggle(f"☔ 우취 처리", value=is_cancelled, key=f"can_tgl_{team}_{dt_str}")

            # 상태가 바뀌었을 때만 로직 실행 (무한 로딩 방지)
            if use_cancel != is_cancelled:
                if use_cancel:
                    st.session_state.cancels.add((team, dt_str))
                else:
                    st.session_state.cancels.discard((team, dt_str))
                    # 우취 끌 때는 상대팀 우취 기록도 같이 꺼주기!
                    opp_team = home_team if is_away else away_team
                    st.session_state.cancels.discard((opp_team, dt_str))
                st.rerun()
            
            if use_manual:
                current_val = local_override_val if local_override_val else ""
                c1, c2, c3 = st.columns([5, 2, 2])
                with c1:
                    manual_p = st.text_input("투수 이름", value=current_val, key=f"inp_{team}_{dt_str}", label_visibility="collapsed")
                with c2:
                    if st.button("적용", key=f"apply_{team}_{dt_str}", use_container_width=True):
                        if manual_p:
                            st.session_state.overrides[(team, dt_str)] = manual_p.strip()
                            st.session_state[pitcher_key] = manual_p.strip() 
                            st.rerun()
                with c3:
                    if st.button("초기화", key=f"clear_{team}_{dt_str}", use_container_width=True):
                        if (team, dt_str) in st.session_state.overrides:
                            del st.session_state.overrides[(team, dt_str)]
                            st.session_state[pitcher_key] = None
                            st.rerun()
            else:
                if (team, dt_str) in st.session_state.overrides:
                    del st.session_state.overrides[(team, dt_str)]
                    st.session_state[pitcher_key] = None
                    st.rerun()

            if use_absence:
                # 🔥 [NEW] 완전 제외자 명단 넘겨주기
                team_db_excl = [p for t, p in db_excluded if t == team]
                active_pitchers = get_active_rotation(working_df, team, selected_dt, excluded_pitchers=team_db_excl)
                if active_pitchers:
                    st.markdown('<div style="background:#f7fafc; padding:8px 10px; border-radius:8px; margin-bottom:10px;">', unsafe_allow_html=True)
                    a_col1, a_col2, a_col3 = st.columns([4, 4, 2])
                    with a_col1:
                        absent_p = st.selectbox("선수 선택", active_pitchers, key=f"abs_p_{team}_{dt_str}", label_visibility="collapsed")
                    with a_col2:
                        return_d = st.date_input("복귀일", value=selected_dt + timedelta(days=10), key=f"abs_d_{team}_{dt_str}", label_visibility="collapsed")
                    with a_col3:
                        if st.button("등록", key=f"abs_btn_{team}_{dt_str}", use_container_width=True):
                            st.session_state.absences[(team, absent_p)] = return_d
                            st.rerun()
                    st.markdown('</div>', unsafe_allow_html=True)

            team_db_absences = {p: d for (t, p), d in db_absences.items() if t == team}
            team_local_absences = {p: d for (t, p), d in st.session_state.absences.items() if t == team}
            combined_absences = {**team_db_absences, **team_local_absences}
            combined_cancels = [d for t, d in expanded_cancels if t == team]

            team_db_excluded = [p for t, p in db_excluded if t == team]

            predicted, rotation_df, is_official = predict_starter(working_df, team, selected_dt, team_absences=combined_absences, excluded_pitchers=team_db_excluded, team_cancels=combined_cancels)
            
            if rotation_df.empty: st.warning("데이터 부족"); return

            db_override_val = db_overrides.get((team, dt_str))

            if local_override_val:
                final_pitcher = local_override_val
                pitcher_source = "로컬 적용"
            elif is_official:
                final_pitcher = predicted
                pitcher_source = "오피셜"
            elif db_override_val:
                final_pitcher = db_override_val
                pitcher_source = "DB 공식"
            else:
                final_pitcher = predicted
                pitcher_source = "자동 예측"

            # 🔥 현재 세션에 선택된 투수가 없거나, 우선순위가 바뀌면 자동 갱신
            current_pitcher = st.session_state.get(pitcher_key)
            if current_pitcher != final_pitcher:
                st.session_state[pitcher_key] = final_pitcher

            show_pitcher = st.session_state[pitcher_key]

            if show_pitcher and show_pitcher != "예측 불가" and show_pitcher != "-" and show_pitcher not in rotation_df['선발투수'].values:
                p_games = working_df[(working_df['팀'] == team) & 
                                     (working_df['상태'].isin(['종료', '수동확정'])) & 
                                     (working_df['선발투수'] == show_pitcher) & 
                                     (working_df['날짜'] < selected_dt)].sort_values('날짜')
                rest_days = max(0, (selected_dt - p_games.iloc[-1]['날짜']).days - 1) if not p_games.empty else "?"
                new_row = pd.DataFrame([{'선발투수': show_pitcher, '휴식일': rest_days}])
                rotation_df = pd.concat([rotation_df, new_row], ignore_index=True)
            # ----------------------------------------------------
            # ⚾ 대시보드 상태 패널
            # ----------------------------------------------------

            team_color = TEAM_COLORS.get(team, "#4a5568")

            if pitcher_source == "로컬 적용":
                s_icon, s_text, s_color = "🧪", f"로컬: {show_pitcher}", "#2b6cb0"

            elif pitcher_source == "DB 공식":
                s_icon, s_text, s_color = "📌", f"DB: {show_pitcher}", "#c05621"

            elif pitcher_source == "오피셜":
                s_icon, s_text, s_color = "✅", f"오피셜: {show_pitcher}", "#2f855a"

            else:
                s_icon, s_text, s_color = "🤖", f"자동 예측: {show_pitcher}", "#4a5568"

            info_badges = []

            if dt_str in combined_cancels:
                info_badges.append(
                    "<span style='color:#e53e3e; font-weight:700;'>☔ 우천취소</span>"
                )

            team_pitchers = working_df[
                working_df['팀'] == team
            ]['선발투수'].dropna().unique()

            for p in team_pitchers:

                if p in combined_absences:
                    ret_dt = pd.to_datetime(combined_absences[p]).date()

                    if selected_dt.date() < ret_dt:
                        info_badges.append(
                            f"<span style='color:#d69e2e; font-weight:700;'>⏸️ {p}(~{ret_dt.strftime('%m/%d')})</span>"
                        )

                if p in team_db_excluded:
                    info_badges.append(
                        f"<span style='color:#e53e3e; font-weight:700;'>🚫 {p}(제외)</span>"
                    )

            if info_badges:
                info_html = " <span style='color:#cbd5e0; margin: 0 10px;'>/</span> ".join(info_badges)

            else:
                info_html = "<span style='color:#a0aec0;'>특이사항 없음</span>"

            scoreboard_html = f"""
            <div style="
                background: #f8fafc;
                border: 1px solid #e2e8f0;
                border-left: 6px solid {team_color};
                border-radius: 8px;
                padding: 0 16px;
                margin-bottom: 12px;
                height: 48px;
                box-shadow: 0 1px 3px rgba(0,0,0,0.04);
                font-family: 'Malgun Gothic', sans-serif;
            ">

                <div style="
                    display:flex;
                    align-items:center;
                    width:100%;
                    height:100%;
                    overflow-x:auto;
                    white-space:nowrap;
                    scrollbar-width:none;
                    -ms-overflow-style:none;
                ">

                    <div style="
                        font-weight:800;
                        font-size:0.95rem;
                        color:{s_color};
                        flex-shrink:0;
                    ">
                        {s_icon} {s_text}
                    </div>

                    <div style="
                        width:2px;
                        height:16px;
                        background:#e2e8f0;
                        flex-shrink:0;
                        margin:0 16px;
                    "></div>

                    <div style="
                        font-size:0.85rem;
                        font-weight:600;
                        flex-shrink:0;
                        display:flex;
                        align-items:center;
                    ">
                        {info_html}
                    </div>

                </div>
            </div>
            """

            components.html(scoreboard_html, height=60)

            btn_cols = st.columns(len(rotation_df))
            for j, rot_row in rotation_df.iterrows():
                pname = rot_row['선발투수']
                with btn_cols[j]:
                    is_active = (show_pitcher == pname)
                    
                    # 🔥 [NEW] 선택된 날짜 기준으로 이 투수가 현재 휴식/말소 상태인지 판별!
                    is_absent = False
                    if pname in combined_absences and selected_dt.date() < combined_absences[pname]:
                        is_absent = True
                    
                    if is_absent:
                        # 휴식 중이면 텍스트를 바꾸고, 아래 st.button에서 disabled 처리
                        return_date_str = combined_absences[pname].strftime('%m/%d')
                        btn_text = f"{pname}\n({return_date_str} 복귀)"
                    elif pname == predicted:
                        if is_official:
                            btn_text = f"✅ 오피셜\n{pname}\n({rot_row['휴식일']}일)"
                        else:
                            btn_text = f"🎯 예상\n{pname}\n({rot_row['휴식일']}일)"
                    else:
                        btn_text = f"\n{pname}\n({rot_row['휴식일']}일)"
                        
                    if st.button(btn_text, key=f"btn_{pitcher_key}_{pname}", type="primary" if is_active else "secondary", use_container_width=True, disabled=is_absent):
                        st.session_state[pitcher_key] = pname; st.rerun()

            if show_pitcher:
                s = get_season_stats(working_df, show_pitcher, selected_dt)
                adv = get_advanced_stats(show_pitcher)

                whip_val = s["WHIP"] if 'WHIP' in s else "-"
                
                # ── 1행: 기본 스탯 (등판, ERA, 이닝, WHIP) ──────────────────────
                row1_html = (
                    f'<div class="border-badge border-gray"><div class="bb-label">등판</div><div class="bb-value">{s["등판"]}회</div></div>'
                    f'<div class="border-badge border-red"><div class="bb-label">ERA</div><div class="bb-value">{s["ERA"]}</div></div>'
                    f'<div class="border-badge border-gray"><div class="bb-label">이닝</div><div class="bb-value">{s["총이닝"]}</div></div>'
                    f'<div class="border-badge border-blue"><div class="bb-label">WHIP</div><div class="bb-value">{whip_val}</div></div>'
                )

                # ── 2행: 심화 스탯 (WAR, FIP, K%, BB%) ─────────────────────────
                has_adv = (adv['WAR'] != '-') or (adv['K%'] != '-' and adv['BB%'] != '-')
                if has_adv:
                    k_val = f'{adv["K%"]}%' if adv["K%"] != '-' else '-'
                    bb_val = f'{adv["BB%"]}%' if adv["BB%"] != '-' else '-'
                    
                    row2_html = (
                        f'<div class="border-badge border-green"><div class="bb-label">WAR</div><div class="bb-value">{adv["WAR"]}</div></div>'
                        f'<div class="border-badge border-red"><div class="bb-label">FIP</div><div class="bb-value">{adv["FIP"]}</div></div>'
                        f'<div class="border-badge border-blue"><div class="bb-label">K%</div><div class="bb-value">{k_val}</div></div>'
                        f'<div class="border-badge border-blue"><div class="bb-label">BB%</div><div class="bb-value">{bb_val}</div></div>'
                    )
                    st.markdown(
                        f'<div class="pitcher-stat-grid" style="margin: 8px 0 4px 0;">{row1_html}{row2_html}</div>'
                        f'<div style="font-size:0.68rem;color:#a0aec0;margin-left:4px;margin-bottom:6px;">WAR·K%·BB% via Naver / FIP via Statiz</div>', 
                        unsafe_allow_html=True
                    )
                else:
                    st.markdown(
                        f'<div class="pitcher-stat-grid" style="margin: 8px 0 4px 0;">{row1_html}{row2_html}</div>', 
                        unsafe_allow_html=True
                    )

        st.divider()
        if 'show_pitcher' in locals() and show_pitcher and show_pitcher != '-':
            st.markdown(f"**📊 {show_pitcher} 최근 5경기 상세 성적**") 
            recent = get_pitcher_recent_stats(working_df, show_pitcher, selected_dt, n=5)
            
            if not recent.empty: 
                st.dataframe(
                    recent, 
                    hide_index=True, 
                    use_container_width=True,
                    column_config={
                        "날짜": st.column_config.TextColumn("날짜", alignment="center"),
                        "상대팀": st.column_config.TextColumn("상대팀", alignment="center"),
                        "이닝": st.column_config.TextColumn("이닝", alignment="center"),
                        "자책점": st.column_config.TextColumn("자책점", alignment="center"),
                        "피안타": st.column_config.TextColumn("피안타", alignment="center"),
                        "사사구": st.column_config.TextColumn("사사구", alignment="center"),
                        "투구수": st.column_config.TextColumn("투구수", alignment="center"),
                        "휴식일": st.column_config.TextColumn("휴식일", alignment="center")
                    }
                )
            else: 
                st.caption("최근 경기 기록 없음")

        st.divider()
        st.markdown(f"**🔄 {team} 최근 선발로테 2바퀴**")
        rot_list = get_recent_rotation_list(working_df, team, selected_dt, n=10)
        
        if not rot_list.empty: 
            st.dataframe(
                rot_list, 
                hide_index=True, 
                use_container_width=True,
                column_config={
                    "날짜": st.column_config.TextColumn("날짜", alignment="center"),
                    "상대팀": st.column_config.TextColumn("상대팀", alignment="center"),
                    "선발투수": st.column_config.TextColumn("선발투수", alignment="center"),
                    "이닝": st.column_config.TextColumn("이닝", alignment="center"),
                    "자책점": st.column_config.TextColumn("자책점", alignment="center"),
                    "투구수": st.column_config.TextColumn("투구수", alignment="center"),
                    "휴식일": st.column_config.TextColumn("휴식일", alignment="center")
                }
            )

render_team_panel(left_col, away_team, 'pitcher_away', is_away=True)
render_team_panel(right_col, home_team, 'pitcher_home', is_away=False)

st.divider()
st.markdown('<div style="text-align:center; color:#a0aec0; font-size:0.78rem;">⚾선발누구⚾ &nbsp;|&nbsp; 데이터: KBO 공식 / 네이버 스포츠</div>', unsafe_allow_html=True)