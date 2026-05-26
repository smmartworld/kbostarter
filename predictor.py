import pandas as pd
from datetime import timedelta

TEAM_COLORS = {
    '삼성': '#074CA1', '두산': '#131230', 'LG': '#C30452', 'KT': '#000000', 'SSG': '#CE0E2D',
    '롯데': '#002955', '한화': '#FF6600', 'KIA': '#EA0029', 'NC': '#315288', '키움': '#570514'
}

# 🔥 [NEW] 제외된 투수는 로테이션 후보군에서 아예 삭제!
def get_active_rotation(df, team, target_date, excluded_pitchers=None):
    if excluded_pitchers is None: excluded_pitchers = []
    past_games = df[(df['팀'] == team) & (df['상태'].isin(['종료', '수동확정', '노게임'])) & (df['날짜'] < pd.to_datetime(target_date))]
    if past_games.empty: return []
    recent_starters = past_games.sort_values('날짜', ascending=False).head(15)['선발투수'].dropna().unique()
    return [p for p in recent_starters if p != '-' and p not in excluded_pitchers][:6]

# 🔥 team_cancels 파라미터 추가!
def predict_starter(df, team, target_date, team_absences=None, excluded_pitchers=None, team_cancels=None):
    if team_absences is None: team_absences = {}
    if excluded_pitchers is None: excluded_pitchers = []
    if team_cancels is None: team_cancels = [] # 🔥 [NEW] 우취 날짜 리스트
    
    target_dt = pd.to_datetime(target_date)
    
    official_row = df[(df['날짜'] == target_dt) & (df['팀'] == team) & (df['상태'] == '예정') & (df['선발투수'] != '-')].copy()
    is_official = False
    if not official_row.empty:
        official_starter = str(official_row.iloc[0]['선발투수']).strip()
        if official_starter != 'nan' and official_starter != '':
            is_official = True
    else:
        official_starter = None

    # 🔥 실제로 던진 경기만 로테이션 소비로 인정
    known_games = df[
        (df['팀'] == team) &
        (df['상태'].isin(['종료', '노게임'])) &
        (df['선발투수'].notna()) &
        (df['선발투수'] != '-') &
        (df['날짜'] < target_dt)
    ].copy()

    # 🔥 [NEW] 우취된 날짜는 '기존에 던진 기록(known_games)'에서 아예 삭제!
    if team_cancels:
        cancel_dt_list = pd.to_datetime(team_cancels)
        known_games = known_games[~known_games['날짜'].isin(cancel_dt_list)]

    if known_games.empty: 
        return (official_starter if official_starter else "데이터 부족"), pd.DataFrame(), is_official

    recent_games = known_games.sort_values('날짜', ascending=False).head(15)
    rotation_pitchers = recent_games['선발투수'].dropna().unique()
    
    # 🔥 [NEW] 최근 던졌더라도 '완전 제외' 명단에 있으면 즉시 탈락!
    rotation_pitchers = [p for p in rotation_pitchers if p != '-' and p not in excluded_pitchers][:6] 

    rot_data = []
    last_known_team_game = known_games['날짜'].max() 

    simulated_last_pitched = {}

    for p in rotation_pitchers:
        p_games = known_games[known_games['선발투수'] == p].sort_values('날짜')
        if not p_games.empty:
            last_game_dt = p_games.iloc[-1]['날짜']
            simulated_last_pitched[p] = last_game_dt
            
            if pd.notna(last_known_team_game):
                days_since_last_appearance = (last_known_team_game - last_game_dt).days
                if days_since_last_appearance >= 9 and p != official_starter:
                    continue 
            
            rest_days = max(0, (target_dt - last_game_dt).days - 1)
            rot_data.append({'선발투수': p, '최근등판': last_game_dt, '휴식일': rest_days})
            
    if not rot_data: return (official_starter if official_starter else "예측 불가"), pd.DataFrame(), is_official
    
    rot_df = pd.DataFrame(rot_data)
    rot_df = rot_df.sort_values('최근등판', ascending=True).reset_index(drop=True)
    
    if is_official:
        predicted_pitcher = official_starter
    else:
        sim_date = last_known_team_game + timedelta(days=1)
        sim_rotation_queue = list(rot_df['선발투수'])
        
        while sim_date <= target_dt:
            # 🔥 [NEW] DB나 로컬에서 지정한 우취 날짜인지 먼저 확인!
            if team_cancels and sim_date.strftime("%Y-%m-%d") in team_cancels:
                has_game = False
            else:
                has_game = not df[(df['날짜'] == sim_date) & (df['팀'] == team) & (df['상태'] != '우천취소')].empty
            
                # 🔥 미래 오피셜 / DB 지정 선발 우선 반영
                fixed_row = df[
                    (df['날짜'] == sim_date) &
                    (df['팀'] == team) &
                    (df['선발투수'].notna()) &
                    (df['선발투수'] != '-')
                ]

                fixed_pitcher = None

                if not fixed_row.empty:
                    fixed_pitcher = fixed_row.iloc[0]['선발투수']


            if has_game:

                temp_queue = []
                available_pitcher = None

                # 🔥 미래에 이미 지정된 선발이 있으면 우선 사용
                if fixed_pitcher:
                    available_pitcher = fixed_pitcher

                    if fixed_pitcher in sim_rotation_queue:
                        sim_rotation_queue.remove(fixed_pitcher)

                else:

                    while sim_rotation_queue:
                        p = sim_rotation_queue.pop(0)
                        if p in team_absences and sim_date < pd.to_datetime(team_absences[p]):
                            temp_queue.append(p)
                        else:
                            available_pitcher = p
                            break
                
                if available_pitcher is None:
                    available_pitcher = temp_queue.pop(0) if temp_queue else "예측 불가"
                
                if sim_date == target_dt:
                    predicted_pitcher = available_pitcher
                    for idx, row in rot_df.iterrows():
                        p_name = row['선발투수']
                        if p_name in simulated_last_pitched:
                            last_d = simulated_last_pitched[p_name]
                            new_rest = max(0, (target_dt - last_d).days - 1)
                            rot_df.at[idx, '휴식일'] = new_rest
                    break
                
                if available_pitcher != "예측 불가":
                    simulated_last_pitched[available_pitcher] = sim_date

                sim_rotation_queue = temp_queue + sim_rotation_queue + [available_pitcher]
                
            sim_date += timedelta(days=1)
            
        if 'predicted_pitcher' not in locals():
            predicted_pitcher = rot_df.iloc[0]['선발투수']
        
    return predicted_pitcher, rot_df[['선발투수', '휴식일']], is_official

def get_pitcher_recent_stats(df, pitcher_name, target_date, n=5):
    pitcher_df = df[(df['선발투수'] == pitcher_name) & (df['상태'].isin(['종료', '노게임'])) & (df['날짜'] < pd.to_datetime(target_date))].copy().sort_values('날짜')
    if pitcher_df.empty: return pd.DataFrame()

    pitcher_df['휴식일'] = (pitcher_df['날짜'].diff().dt.days - 1).fillna(0).astype(int)
    pitcher_df.loc[pitcher_df['휴식일'] < 0, '휴식일'] = 0
    
    recent = pitcher_df.tail(n).copy()
    recent['날짜'] = recent['날짜'].dt.strftime('%m/%d')
    
    for col in ['투구수', '피안타', '사사구', '자책점']:
        recent[col] = pd.to_numeric(recent[col], errors='coerce').fillna(0).astype(int)

    recent = recent[['날짜', '상대팀', '이닝', '자책점', '피안타', '사사구', '투구수', '휴식일']].reset_index(drop=True)

    # 🔥 최근 5경기 줄 수 고정
    while len(recent) < n:
        recent.loc[len(recent)] = ['', '', '', '', '', '', '', '']

    return recent

def get_season_stats(df, pitcher_name, target_date):
    target_dt = pd.to_datetime(target_date)
    pitcher_df = df[(df['선발투수'] == pitcher_name) & (df['상태'] == '종료') & (df['날짜'] < target_dt)].copy()
    if pitcher_df.empty: return {"등판": 0, "총이닝": "0", "ERA": "-", "WHIP": "-"}

    games = len(pitcher_df)
    
    def parse_inning(inn_str):
        try:
            inn_str = str(inn_str).strip()
            if not inn_str or inn_str == '-': return 0.0
            inn_str = inn_str.replace('⅓', ' 1/3').replace('⅔', ' 2/3').strip()
            parts = inn_str.split()
            if len(parts) == 2:
                whole = float(parts[0])
                num, den = parts[1].split('/')
                return whole + (float(num) / float(den))
            elif '/' in inn_str:
                num, den = inn_str.split('/')
                return float(num) / float(den)
            else:
                val = float(inn_str)
                whole = int(val)
                rem = round(val - whole, 2)
                if rem == 0.1: return whole + 1/3
                elif rem == 0.2: return whole + 2/3
                return val
        except:
            return 0.0

    total_innings_float = sum(pitcher_df['이닝'].apply(parse_inning))
    total_er = pd.to_numeric(pitcher_df['자책점'], errors='coerce').sum()
    total_hits = pd.to_numeric(pitcher_df['피안타'], errors='coerce').sum()
    total_walks = pd.to_numeric(pitcher_df['사사구'], errors='coerce').sum()

    whole_innings = int(total_innings_float)
    remainder = total_innings_float - whole_innings
    
    if remainder > 0.6: frac_str = " ⅔"
    elif remainder > 0.3: frac_str = " ⅓"
    else: frac_str = ""
    display_innings = f"{whole_innings}{frac_str}"

    era = (total_er * 9) / total_innings_float if total_innings_float > 0 else 0
    whip = (total_hits + total_walks) / total_innings_float if total_innings_float > 0 else 0

    return {
        "등판": games,
        "총이닝": display_innings,
        "ERA": f"{era:.2f}",
        "WHIP": f"{whip:.2f}"
    }

def get_recent_rotation_list(df, team, target_date, n=10):
    team_df = df[
        (df['팀'] == team) &
        (df['상태'].isin(['종료', '노게임'])) &
        (df['선발투수'] != '-') &
        (df['날짜'] < pd.to_datetime(target_date))
    ].copy().sort_values('날짜', ascending=False)
    recent = team_df.head(n).copy()
    if recent.empty: return pd.DataFrame()

    recent = recent.sort_values('날짜', ascending=True)

    rest_days_list = []
    for _, row in recent.iterrows():
        p_name = row['선발투수']
        p_date = row['날짜']
        prev_games = df[(df['선발투수'] == p_name) & (df['상태'].isin(['종료', '노게임'])) & (df['날짜'] < p_date)].sort_values('날짜')
        if not prev_games.empty:
            rest_days = max(0, (p_date - prev_games.iloc[-1]['날짜']).days - 1)
            rest_days_list.append(rest_days)
        else:
            rest_days_list.append(0) 

    recent['휴식일'] = rest_days_list
    recent['날짜'] = recent['날짜'].dt.strftime('%m/%d')

    for c in ['투구수', '자책점']:
        recent[c] = pd.to_numeric(recent[c], errors='coerce').fillna(0).astype(int)

    recent = recent[['날짜', '상대팀', '선발투수', '이닝', '자책점', '투구수', '휴식일']].reset_index(drop=True)

    while len(recent) < n:
        recent.loc[len(recent)] = ['', '', '', '', '', '', '']

    return recent