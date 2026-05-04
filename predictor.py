import pandas as pd
from datetime import timedelta

TEAM_COLORS = {
    'KIA': '#EA0029', '삼성': '#074CA1', 'LG': '#C30452', '두산': '#131230', 
    'KT': '#000000', 'SSG': '#CE0E2D', '롯데': '#002955', '한화': '#FF6600', 
    'NC': '#315288', '키움': '#570514'
}

def get_active_rotation(df, team, target_date):
    past_games = df[(df['팀'] == team) & (df['상태'].isin(['종료', '수동확정'])) & (df['날짜'] < pd.to_datetime(target_date))]
    if past_games.empty: return []
    recent_starters = past_games.sort_values('날짜', ascending=False).head(15)['선발투수'].dropna().unique()
    return [p for p in recent_starters if p != '-'][:6]

def predict_starter(df, team, target_date):
    target_dt = pd.to_datetime(target_date)
    
    # 💡 1. 오피셜 선발 감지 (최우선)
    official_row = df[(df['날짜'] == target_dt) & (df['팀'] == team) & (df['상태'] == '예정') & (df['선발투수'] != '-')].copy()
    is_official = False
    if not official_row.empty:
        official_starter = official_row.iloc[0]['선발투수']
        is_official = True
    else:
        official_starter = None

    past_df = df[(df['팀'] == team) & (df['상태'].isin(['종료', '수동확정'])) & (df['날짜'] < target_dt)].copy()
    if past_df.empty: 
        return (official_starter if official_starter else "데이터 부족"), pd.DataFrame(), is_official

    # 💡 2. 최근 15경기를 통해 현재 '진짜' 로테이션 멤버 5~6명 추출
    recent_games = past_df.sort_values('날짜', ascending=False).head(15)
    recent_pitchers_raw = recent_games['선발투수'].dropna().unique()
    
    active_rotation = []
    last_team_game = past_df['날짜'].max()

    # 🔥 9일 룰: 최근 9일 이상 등판 기록이 없는 선수는 로테이션에서 배제 (오피셜 예외)
    for p in recent_pitchers_raw:
        if p == '-': continue
        p_last_game = past_df[past_df['선발투수'] == p]['날짜'].max()
        if pd.notna(last_team_game) and pd.notna(p_last_game):
            if (last_team_game - p_last_game).days >= 9 and p != official_starter:
                continue 
        active_rotation.append(p)
        if len(active_rotation) == 6: break # 최대 6선발까지만 관리

    if not active_rotation: 
        return (official_starter if official_starter else "예측 불가"), pd.DataFrame(), is_official

    # 💡 3. 로테이션 멤버들의 휴식일 및 기본 정보 세팅 (UI에 뿌려줄 표 만들기 용도)
    rot_data = []
    for p in active_rotation:
        p_games = past_df[past_df['선발투수'] == p].sort_values('날짜')
        if not p_games.empty:
            last_game_dt = p_games.iloc[-1]['날짜']
            rest_days = max(0, (target_dt - last_game_dt).days - 1)
            rot_data.append({'선발투수': p, '최근등판': last_game_dt, '휴식일': rest_days})
            
    rot_df = pd.DataFrame(rot_data)
    rot_df = rot_df.sort_values('최근등판', ascending=True).reset_index(drop=True)

    # 💡 4. 대망의 예측 시뮬레이션 복구! (1-2-3-4-5 순서대로 돌리기)
    # 만약 오피셜이 떴다면 시뮬레이션 무시하고 오피셜 리턴!
    if is_official:
        predicted_pitcher = official_starter
    else:
        # 마지막 경기 날짜부터 타겟 날짜까지 팀의 스케줄을 하나씩 짚어가며 로테이션을 돌려본다.
        sim_date = last_team_game + timedelta(days=1)
        sim_rotation_queue = list(rot_df['선발투수']) # [가장 오래 쉰 투수, 두번째..., 최근 던진 투수]
        
        # 만약 스케줄상 팀의 경기가 있는 날이면, 큐의 첫 번째 투수가 등판하고 맨 뒤로 이동!
        while sim_date <= target_dt:
            # 팀이 그 날짜에 경기가 있는지 확인 (과거 결측치, 미래 스케줄 포함)
            has_game = not df[(df['날짜'] == sim_date) & (df['팀'] == team) & (df['상태'] != '우천취소')].empty
            
            if has_game:
                current_pitcher = sim_rotation_queue.pop(0) # 오늘 던질 투수 꺼냄
                if sim_date == target_dt:
                    predicted_pitcher = current_pitcher
                    break
                sim_rotation_queue.append(current_pitcher) # 던졌으니 맨 뒤로 줄 섬
            
            sim_date += timedelta(days=1)
            
        # 만약 루프를 다 돌았는데도 할당이 안 됐다면(예외), 가장 오래 쉰 투수 배정
        if 'predicted_pitcher' not in locals():
            predicted_pitcher = rot_df.iloc[0]['선발투수']

    return predicted_pitcher, rot_df[['선발투수', '휴식일']], is_official

def get_pitcher_recent_stats(df, pitcher_name, target_date, n=5):
    pitcher_df = df[(df['선발투수'] == pitcher_name) & (df['상태'] == '종료') & (df['날짜'] < pd.to_datetime(target_date))].copy().sort_values('날짜')
    if pitcher_df.empty: return pd.DataFrame()

    pitcher_df['휴식일'] = (pitcher_df['날짜'].diff().dt.days - 1).fillna(0).astype(int)
    pitcher_df.loc[pitcher_df['휴식일'] < 0, '휴식일'] = 0 
    
    recent = pitcher_df.tail(n).copy()
    recent['날짜'] = recent['날짜'].dt.strftime('%m/%d')
    
    for col in ['투구수', '피안타', '사사구', '자책점']:
        recent[col] = pd.to_numeric(recent[col], errors='coerce').fillna(0).astype(int)

    return recent[['날짜', '상대팀', '이닝', '자책점', '피안타', '사사구', '투구수', '휴식일']].reset_index(drop=True)

def get_season_stats(df, pitcher_name, target_date):
    target_dt = pd.to_datetime(target_date)
    pitcher_df = df[(df['선발투수'] == pitcher_name) & (df['상태'] == '종료') & (df['날짜'] < target_dt)].copy()
    if pitcher_df.empty: return {"등판": 0, "총이닝": "0", "ERA": "-", "WHIP": "-"}

    games = len(pitcher_df)
    
    def parse_inning(inn_str):
        try:
            inn_str = str(inn_str).strip()
            if ' ' in inn_str:
                whole, frac = inn_str.split(' ')
                num, den = frac.split('/')
                return float(whole) + (float(num) / float(den))
            elif '/' in inn_str:
                num, den = inn_str.split('/')
                return float(num) / float(den)
            else:
                return float(inn_str)
        except:
            return 0.0

    total_innings_float = sum(pitcher_df['이닝'].apply(parse_inning))
    total_er = pd.to_numeric(pitcher_df['자책점'], errors='coerce').sum()
    total_hits = pd.to_numeric(pitcher_df['피안타'], errors='coerce').sum()
    total_walks = pd.to_numeric(pitcher_df['사사구'], errors='coerce').sum()

    whole_innings = int(total_innings_float)
    remainder = total_innings_float - whole_innings
    if remainder > 0.6: frac_str = " 2/3"
    elif remainder > 0.3: frac_str = " 1/3"
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
    team_df = df[(df['팀'] == team) & (df['상태'].isin(['종료', '수동확정'])) & (df['선발투수'] != '-') & (df['날짜'] < pd.to_datetime(target_date))].copy().sort_values('날짜', ascending=False)
    recent = team_df.head(n).copy()
    if recent.empty: return pd.DataFrame()

    recent = recent.sort_values('날짜', ascending=True)

    rest_days_list = []
    for _, row in recent.iterrows():
        p_name = row['선발투수']
        p_date = row['날짜']
        prev_games = df[(df['선발투수'] == p_name) & (df['상태'] == '종료') & (df['날짜'] < p_date)].sort_values('날짜')
        if not prev_games.empty:
            rest_days = max(0, (p_date - prev_games.iloc[-1]['날짜']).days - 1)
            rest_days_list.append(rest_days)
        else:
            rest_days_list.append(0) 

    recent['휴식일'] = rest_days_list
    recent['날짜'] = recent['날짜'].dt.strftime('%m/%d')
    
    for c in ['투구수', '자책점']:
        recent[c] = pd.to_numeric(recent[c], errors='coerce').fillna(0).astype(int)

    return recent[['날짜', '상대팀', '선발투수', '이닝', '자책점', '투구수', '휴식일']].reset_index(drop=True)
