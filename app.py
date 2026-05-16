import streamlit as st
import pandas as pd
import calendar as cal_module
import time
from datetime import date, timedelta
from predictor import (
    predict_starter, get_active_rotation,
    get_pitcher_recent_stats, get_season_stats,
    get_recent_rotation_list, TEAM_COLORS
)

st.set_page_config(page_title="⚾ KBO 선발 예측기", page_icon="⚾", layout="wide")

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
        .cal-wrap [data-testid="stHorizontalBlock"] { flex-wrap: nowrap !important; min-width: 550px !important; }
        .cal-wrap div[data-testid="column"] { min-width: 75px !important; width: 14% !important; flex: 1 1 auto !important; }
        div[data-testid="stButton"] button { padding: 0.2rem 0 !important; font-size: 0.75rem; }
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
    
    .team-panel { border-radius: 14px; padding: 18px 16px; height: 100%; min-width: 350px !important; }
    .team-name-big { font-size: 1.5rem; font-weight: 900; line-height: 1.2; }
    .team-label-small { font-size: 0.7rem; font-weight: 700; color: #a0aec0; }
    .sec-label { font-size: 0.72rem; font-weight: 800; color: #a0aec0; margin: 12px 0 5px 0; }
    .score-banner { background: #f0fff4; border: 1px solid #9ae6b4; border-radius: 10px; padding: 10px 20px; text-align: center; font-size: 1.35rem; font-weight: 800; color: #276749; margin: 8px 0 16px 0; }
    .score-banner.upcoming { background: #fffaf0; border-color: #fbd38d; color: #c05621; font-size: 0.95rem; }
    
    .stat-badge { display: inline-block; background: #edf2f7; border-radius: 6px; padding: 3px 10px; font-size: 0.78rem; color: #4a5568; margin: 2px 3px 2px 0; white-space: nowrap; }
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
db_excluded = set() # 🔥 [NEW] 로테이션 제외자 명단

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
        db_excluded.add((t, p)) # 🔥 [NEW] 제외 명단에 추가

_defaults = {'cal_year': 2026, 'cal_month': 5, 'selected_date': date(2026, 5, 4), 'selected_game': None, 'pitcher_away': None, 'pitcher_home': None, 'my_team': '삼성', 'overrides': {}, 'absences': {}, 'admin_unlocked': False}
for k, v in _defaults.items():
    if k not in st.session_state: st.session_state[k] = v

st.markdown('<div class="main-title">⚾ KBO 선발 예측기</div>', unsafe_allow_html=True)

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
        with c3:
            # 🔥 [NEW] 옵션 추가!
            m_type = st.radio("변동 유형", ["선발 지정", "휴식/말소", "로테이션 제외"], key="adm_type", horizontal=True)
            
        c4, c5 = st.columns([3, 1])
        with c4:
            if m_type == "선발 지정":
                m_date = st.date_input("선발 등판 확정일", value=date.today())
            elif m_type == "휴식/말소":
                m_date = st.date_input("복귀 예정일 (이 날부터 등판 가능)", value=date.today() + timedelta(days=10))
            else:
                # 🔥 [NEW] 완전 제외일 때는 날짜 필요 없음!
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
                icon = "🎯" if typ == "선발 지정" else ("🚑" if typ == "휴식/말소" else "🚫")
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

all_overrides = {**db_overrides, **st.session_state.overrides}

for (team, dt_str), pitcher in all_overrides.items():
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
            
            t_col1, t_col2 = st.columns(2)
            with t_col1:
                use_manual = st.toggle(f"🛠️ 수동 지정", value=(local_override_val is not None), key=f"man_{team}_{dt_str}")
            with t_col2:
                use_absence = st.toggle(f"🏥 휴식/말소", key=f"abs_tgl_{team}_{dt_str}")
            
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
            
            # 🔥 [NEW] 완전 제외자 명단을 추출해서 화면에도 회색 뱃지로 띄워줌!
            team_db_excluded = [p for t, p in db_excluded if t == team]
            
            if team_db_excluded:
                for p in team_db_excluded:
                    st.markdown(f'<div class="absence-badge-drop">🚫 [완전 제외] {p} (불펜/말소)</div>', unsafe_allow_html=True)
                    
            if team_db_absences:
                for p, d in team_db_absences.items():
                    st.markdown(f'<div class="absence-badge">🏢 [DB 공식] {p} ~ {d.strftime("%m/%d")} 복귀</div>', unsafe_allow_html=True)
                    
            if team_local_absences:
                for p, d in team_local_absences.items():
                    st.markdown(f"""
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 5px;">
                        <span class="absence-badge-local">🏠 [로컬] {p} ~ {d.strftime('%m/%d')} 복귀</span>
                    </div>
                    """, unsafe_allow_html=True)
                    if st.button(f"✖ {p} 로컬 해제", key=f"del_abs_{team}_{p}", use_container_width=True):
                        del st.session_state.absences[(team, p)]
                        st.rerun()

            # 🔥 [NEW] 시뮬레이터에 제외자 명단 던져주기!
            predicted, rotation_df, is_official = predict_starter(working_df, team, selected_dt, team_absences=combined_absences, excluded_pitchers=team_db_excluded)
            
            if rotation_df.empty: st.warning("데이터 부족"); return

            db_override_val = db_overrides.get((team, dt_str))
            final_override_p = local_override_val if local_override_val else db_override_val

            if st.session_state[pitcher_key] is None:
                st.session_state[pitcher_key] = final_override_p if final_override_p else predicted

            show_pitcher = st.session_state[pitcher_key]

            if show_pitcher and show_pitcher != "예측 불가" and show_pitcher != "-" and show_pitcher not in rotation_df['선발투수'].values:
                p_games = working_df[(working_df['팀'] == team) & 
                                     (working_df['상태'].isin(['종료', '수동확정'])) & 
                                     (working_df['선발투수'] == show_pitcher) & 
                                     (working_df['날짜'] < selected_dt)].sort_values('날짜')
                rest_days = max(0, (selected_dt - p_games.iloc[-1]['날짜']).days - 1) if not p_games.empty else "?"
                new_row = pd.DataFrame([{'선발투수': show_pitcher, '휴식일': rest_days}])
                rotation_df = pd.concat([rotation_df, new_row], ignore_index=True)

            if final_override_p:
                src_text = "로컬 적용" if local_override_val else "DB 공식"
                st.info(f"👉 지정됨 ({src_text}): 🎯 {show_pitcher}")
            else:
                st.markdown('<div class="sec-label">🎯 선발투수 선택</div>', unsafe_allow_html=True)
                btn_cols = st.columns(len(rotation_df))
                for j, rot_row in rotation_df.iterrows():
                    pname = rot_row['선발투수']
                    with btn_cols[j]:
                        is_active = (show_pitcher == pname)
                        
                        if pname == predicted:
                            if is_official:
                                btn_text = f"✅ 오피셜\n{pname}\n({rot_row['휴식일']}일)"
                            else:
                                btn_text = f"🎯 예상\n{pname}\n({rot_row['휴식일']}일)"
                        else:
                            btn_text = f"\n{pname}\n({rot_row['휴식일']}일)"
                            
                        if st.button(btn_text, key=f"btn_{pitcher_key}_{pname}", type="primary" if is_active else "secondary", use_container_width=True):
                            st.session_state[pitcher_key] = pname; st.rerun()

            if show_pitcher:
                s = get_season_stats(working_df, show_pitcher, selected_dt)
                st.markdown(f'<div style="margin:8px 0 2px 0;"><span class="stat-badge">등판 <b>{s["등판"]}회</b></span><span class="stat-badge">ERA <b>{s["ERA"]}</b></span></div>', unsafe_allow_html=True)
                if 'WHIP' in s:
                    st.markdown(f'<div style="margin:2px 0;"><span class="stat-badge" style="background:#eebfbb; color:#820024;">WHIP <b>{s["WHIP"]}</b></span><span class="stat-badge">이닝 <b>{s["총이닝"]}</b></span></div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div style="margin:2px 0;"><span class="stat-badge">이닝 <b>{s["총이닝"]}</b></span></div>', unsafe_allow_html=True)

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
                        "자책점": st.column_config.NumberColumn("자책점", format="%d", alignment="center"),
                        "피안타": st.column_config.NumberColumn("피안타", format="%d", alignment="center"),
                        "사사구": st.column_config.NumberColumn("사사구", format="%d", alignment="center"),
                        "투구수": st.column_config.NumberColumn("투구수", format="%d", alignment="center"),
                        "휴식일": st.column_config.NumberColumn("휴식일", format="%d", alignment="center")
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
                    "자책점": st.column_config.NumberColumn("자책점", format="%d", alignment="center"),
                    "투구수": 양의정수포맷팅,
                    "휴식일": st.column_config.NumberColumn("휴식일", format="%d", alignment="center")
                }
            )

render_team_panel(left_col, away_team, 'pitcher_away', is_away=True)
render_team_panel(right_col, home_team, 'pitcher_home', is_away=False)

st.divider()
st.markdown('<div style="text-align:center; color:#a0aec0; font-size:0.78rem;">⚾ KBO 선발 예측기 &nbsp;|&nbsp; 데이터: KBO 공식 / 네이버 스포츠</div>', unsafe_allow_html=True)