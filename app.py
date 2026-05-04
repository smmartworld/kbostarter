import streamlit as st
import pandas as pd
import calendar as cal_module
from datetime import date, timedelta
from predictor import (
    predict_starter, get_active_rotation,
    get_pitcher_recent_stats, get_season_stats,
    get_recent_rotation_list, TEAM_COLORS
)

st.set_page_config(page_title="KBO 선발 예측기", page_icon="⚾", layout="wide")

st.markdown("""
<style>
    header {visibility: hidden;}
    #MainMenu {visibility: hidden;}
    
    /* 🚨 1단계: 스트림릿의 반응형 레이아웃 억제 (강제 고정폭) */
    .block-container { 
        padding-top: 1rem; 
        padding-bottom: 0rem; 
        max-width: 1200px !important; 
        min-width: 800px !important; /* 모바일에서도 화면을 강제로 800px 넓이로 고정! */
    }
    
    /* 🚨 2단계: 화면 밖으로 튀어나간 건 좌우로 스크롤 가능하게 */
    .stApp { 
        background: #ffffff; 
        overflow-x: auto; /* 전체 화면 가로 스크롤 허용 */
    }
    
    .main-title { text-align: center; font-size: 2rem; font-weight: 900; color: #1a202c; margin-bottom: 2px; }
    
    /* 달력 강제 가로 유지 */
    .cal-wrap { background: #f7fafc; border: 1px solid #e2e8f0; border-radius: 16px; padding: 16px 20px; margin-bottom: 20px; min-width: 750px !important; }
    .cal-nav-title { text-align: center; font-size: 1.15rem; font-weight: 800; color: #2d3748; padding: 4px 0; }
    .cal-day-name { text-align: center; font-size: 0.78rem; font-weight: 700; color: #718096; padding: 8px 0 4px 0; }
    .cal-empty { height: 36px; }
    .cal-noGame { text-align: center; padding: 6px 0; font-size: 0.88rem; color: #cbd5e0; height: 36px; }
    
    /* 🚨 3단계: 스트림릿이 임의로 쪼개는 컬럼(Column)들을 강제로 한 줄에 묶기 */
    div[data-testid="column"] { 
        min-width: 0 !important; /* 컬럼 최소 넓이 해제 */
    }
    
    .match-card { background: #f7fafc; border: 1.5px solid #e2e8f0; border-radius: 12px; padding: 12px 8px; text-align: center; margin-bottom: 4px; min-height: 100px; }
    .match-card.sel { background: #ebf8ff; border-color: #4299e1; }
    .mc-teams { font-size: 0.88rem; font-weight: 700; color: #2d3748; margin-top: 4px; }
    .mc-done { font-size: 0.78rem; color: #276749; font-weight: 600; }
    .mc-plan { font-size: 0.78rem; color: #c05621; font-weight: 600; }
    .mc-cancel { font-size: 0.78rem; color: #9b2c2c; }
    .mc-manual { font-size: 0.78rem; color: #3182ce; font-weight: 800; }
    .team-panel { background: #fdfdfd; border: 1px solid #e2e8f0; border-radius: 14px; padding: 18px 16px; height: 100%; min-width: 350px !important; }
    .team-name-big { font-size: 1.5rem; font-weight: 900; line-height: 1.2; }
    .team-label-small { font-size: 0.7rem; font-weight: 700; color: #a0aec0; }
    .sec-label { font-size: 0.72rem; font-weight: 800; color: #a0aec0; margin: 12px 0 5px 0; }
    .score-banner { background: #f0fff4; border: 1px solid #9ae6b4; border-radius: 10px; padding: 10px 20px; text-align: center; font-size: 1.35rem; font-weight: 800; color: #276749; margin: 8px 0 16px 0; }
    .score-banner.upcoming { background: #fffaf0; border-color: #fbd38d; color: #c05621; font-size: 0.95rem; }
    
    .stat-badge { display: inline-block; background: #edf2f7; border-radius: 6px; padding: 3px 10px; font-size: 0.78rem; color: #4a5568; margin: 2px 3px 2px 0; white-space: nowrap; }
    .css-logo { width: 32px; height: 32px; border-radius: 50%; display: flex; align-items: center; justify-content: center; color: white; font-weight: 900; font-size: 0.75rem; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
    .css-logo-large { width: 50px; height: 50px; font-size: 1.1rem; }
</style>
""", unsafe_allow_html=True)

STADIUMS = {
    'LG': '잠실', '두산': '잠실', '키움': '고척', 'SSG': '문학', 
    'KT': '수원', '한화': '대전', '삼성': '대구', '롯데': '부산', 'NC': '창원', 'KIA': '광주'
}

@st.cache_data
def load_data():
    df = pd.read_csv('로테이션_마스터데이터.csv')
    df['날짜'] = pd.to_datetime(df['날짜'])
    return df

try:
    original_df = load_data()
except FileNotFoundError:
    st.error("❌ 데이터 파일 없음. data.py 먼저 실행 필요.")
    st.stop()

_defaults = {'cal_year': 2026, 'cal_month': 5, 'selected_date': date(2026, 5, 4), 'selected_game': None, 'pitcher_away': None, 'pitcher_home': None, 'my_team': '삼성', 'overrides': {}}
for k, v in _defaults.items():
    if k not in st.session_state: st.session_state[k] = v

st.markdown('<div class="main-title">⚾ KBO 선발 예측기</div>', unsafe_allow_html=True)

col_a, col_b, col_c = st.columns([1, 2, 1])
with col_b:
    st.session_state.my_team = st.selectbox("📣 나의 응원팀", list(TEAM_COLORS.keys()), index=list(TEAM_COLORS.keys()).index(st.session_state.my_team))

working_df = original_df.copy()
for (team, dt_str), pitcher in st.session_state.overrides.items():
    dt_pd = pd.to_datetime(dt_str)
    mask = (working_df['팀'] == team) & (working_df['날짜'] == dt_pd)
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
                    elif g_status == '우천취소': btn_label = f"{day} ⚪"
                    
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
            st.markdown(f"""
            <div class="{card_cls}">
                <div style="display:flex;justify-content:center;align-items:center;gap:6px;">
                    <div class="css-logo" style="background:{c_away};">{row['원정팀']}</div>
                    <span style="color:#a0aec0;font-size:0.75rem;">vs</span>
                    <div class="css-logo" style="background:{c_home};">{row['홈팀']}</div>
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
if status == '종료':
    st.markdown(f'<div class="score-banner">{away_team} &nbsp; {g["away_score"]} : {g["home_score"]} &nbsp; {home_team}</div>', unsafe_allow_html=True)
elif status == '우천취소':
    st.error(f"☔ {away_team} vs {home_team} — 우천취소된 경기입니다."); st.stop()
else:
    st.markdown(f'<div class="score-banner upcoming">⏰ {away_team} vs {home_team} — 선발 예측 모드</div>', unsafe_allow_html=True)

left_col, right_col = st.columns(2)

def render_team_panel(col, team: str, pitcher_key: str, is_away: bool):
    with col:
        color = TEAM_COLORS.get(team, '#4299e1')
        st.markdown(f"""
        <div class="team-panel" style="border-top:4px solid {color};">
            <div style="display:flex;align-items:center;gap:14px;margin-bottom:10px;">
                <div class="css-logo css-logo-large" style="background:{color};">{team}</div>
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
            st.markdown(f'<div class="sec-label">실제 선발 투수</div><div style="font-size:1.4rem;font-weight:900;">{r["선발투수"]}</div>', unsafe_allow_html=True)
            st.markdown(f'<span class="stat-badge">이닝 <b>{r["이닝"]}</b></span><span class="stat-badge">투구수 <b>{r["투구수"]}</b></span><span class="stat-badge">자책점 <b>{r["자책점"]}</b></span>', unsafe_allow_html=True)
        else:
            dt_str = selected_dt.strftime('%Y-%m-%d')
            is_overridden = (team, dt_str) in st.session_state.overrides
            
            use_manual = st.toggle(f"🛠️ 관리자: 오피셜 수동 확정", value=is_overridden, key=f"man_{team}_{dt_str}")
            
            if use_manual:
                current_val = st.session_state.overrides.get((team, dt_str), "")
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
                        if is_overridden:
                            del st.session_state.overrides[(team, dt_str)]
                            st.session_state[pitcher_key] = None
                            st.rerun()
            else:
                if is_overridden:
                    del st.session_state.overrides[(team, dt_str)]
                    st.session_state[pitcher_key] = None
                    st.rerun()

            predicted, rotation_df = predict_starter(working_df, team, selected_dt)
            if rotation_df.empty: st.warning("데이터 부족"); return

            if st.session_state[pitcher_key] is None:
                st.session_state[pitcher_key] = st.session_state.overrides.get((team, dt_str), predicted)

            show_pitcher = st.session_state[pitcher_key]

            if is_overridden:
                st.info(f"👉 관리자 강제 지정됨: 🎯 {show_pitcher}")
            else:
                st.markdown('<div class="sec-label">🎯 로테이션 멤버 선택</div>', unsafe_allow_html=True)
                btn_cols = st.columns(len(rotation_df))
                for j, rot_row in rotation_df.iterrows():
                    pname = rot_row['선발투수']
                    with btn_cols[j]:
                        is_active = (show_pitcher == pname)
                        if st.button(f"{'🎯 ' if pname == predicted else ''}{pname}\n({rot_row['휴식일']}일)", key=f"btn_{pitcher_key}_{pname}", type="primary" if is_active else "secondary", use_container_width=True):
                            st.session_state[pitcher_key] = pname; st.rerun()

            if show_pitcher:
                s = get_season_stats(working_df, show_pitcher, selected_dt)
                st.markdown(f'<div style="margin:6px 0 4px 0;"><span class="stat-badge">등판 <b>{s["등판"]}회</b></span><span class="stat-badge">ERA <b>{s["ERA"]}</b></span><span class="stat-badge">총이닝 <b>{s["총이닝"]}</b></span></div>', unsafe_allow_html=True)

        st.divider()
        if 'show_pitcher' in locals() and show_pitcher and show_pitcher != '-':
            st.markdown(f"**📊 {show_pitcher} 최근 3경기 성적**")
            recent = get_pitcher_recent_stats(working_df, show_pitcher, selected_dt, n=3)
            if not recent.empty: st.dataframe(recent, hide_index=True, use_container_width=True)
            else: st.caption("최근 경기 기록 없음")

        st.divider()
        st.markdown(f"**🔄 {team} 최근 로테이션 흐름 (수동확정 포함)**")
        rot_list = get_recent_rotation_list(working_df, team, selected_dt, n=10)
        if not rot_list.empty: st.dataframe(rot_list, hide_index=True, use_container_width=True)

# 모바일에서는 양팀 패널이 위아래로 쌓이도록 (기본 Streamlit 동작 유지)
render_team_panel(left_col, away_team, 'pitcher_away', is_away=True)
render_team_panel(right_col, home_team, 'pitcher_home', is_away=False)

st.divider()
st.markdown('<div style="text-align:center; color:#a0aec0; font-size:0.78rem;">⚾ KBO 선발 예측기 &nbsp;|&nbsp; 데이터: KBO 공식 / 네이버 스포츠</div>', unsafe_allow_html=True)
