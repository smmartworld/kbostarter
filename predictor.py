import pandas as pd
from datetime import timedelta

TEAM_COLORS = {
    '삼성': '#074CA1', '두산': '#131230', 'LG': '#C30452', 'KT': '#000000', 'SSG': '#CE0E2D',
    '롯데': '#002955', '한화': '#FF6600', 'KIA': '#EA0029', 'NC': '#315288', '키움': '#570514'
}

def get_active_rotation(df, team, target_date, excluded_pitchers=None):
    if excluded_pitchers is None: excluded_pitchers = []
    # 🔥 [NEW] 노게임도 로테이션 소비로 인정
    past_games = df[(df['팀'] == team) & (df['상태'].isin(['종료', '수동확정', '노게임'])) & (df['날짜'] < pd.to_datetime(target_date))]
    if past_games.empty: return []
    recent_starters = past_games.sort_values('날짜', ascending=False).head(21)['선발투수'].dropna().unique()
    return [p for p in recent_starters if p != '-' and p not in excluded_pitchers][:8]

def predict_starter(df, team, target_date, team_absences=None, excluded_pitchers=None, team_cancels=None):
    if team_absences is None: team_absences = {}
    if excluded_pitchers is None: excluded_pitchers = []
    if team_cancels is None: team_cancels = []
    
    target_dt = pd.to_datetime(target_date)
    
    official_row = df[(df['날짜'] == target_dt) & (df['팀'] == team) & (df['상태'] == '예정') & (df['선발투수'] != '-')].copy()
    is_official = False
    if not official_row.empty:
        official_starter = str(official_row.iloc[0]['선발투수']).strip()
        if official_starter != 'nan' and official_starter != '':
            is_official = True
    else:
        official_starter = None

    # 🔥 [NEW] 노게임도 실제로 던진 것으로 인정 → 로테이션 소비에 포함
    known_games = df[
        (df['팀'] == team) &
        (df['상태'].isin(['종료', '노게임'])) &
        (df['선발투수'].notna()) &
        (df['선발투수'] != '-') &
        (df['날짜'] < target_dt)
    ].copy()

    if team_cancels:
        cancel_dt_list = pd.to_datetime(team_cancels)
        known_games = known_games[~known_games['날짜'].isin(cancel_dt_list)]

    if known_games.empty: 
        return (official_starter if official_starter else "데이터 부족"), pd.DataFrame(), is_official

    # 6선발 + 대체/복귀 선발이 겹치는 구간까지 후보군에 담을 수 있게 범위를 넓힌다.
    recent_games = known_games.sort_values('날짜', ascending=False).head(21)
    rotation_pitchers = [
        p for p in recent_games['선발투수'].dropna().unique()
        if p != '-' and p not in excluded_pitchers
    ]

    # 복귀일이 된 기존 선발은 최근 21경기 밖이더라도 후보로 다시 올린다.
    for p, return_date in team_absences.items():
        is_returned = target_dt.normalize() >= pd.to_datetime(return_date).normalize()
        has_team_history = not known_games[known_games['선발투수'] == p].empty
        if is_returned and has_team_history and p not in excluded_pitchers and p not in rotation_pitchers:
            rotation_pitchers.append(p)

    rot_data = []
    last_known_team_game = known_games['날짜'].max() 

    simulated_last_pitched = {}

    for p in rotation_pitchers:
        p_games = known_games[known_games['선발투수'] == p].sort_values('날짜')
        if not p_games.empty:
            last_game_dt = p_games.iloc[-1]['날짜']
            simulated_last_pitched[p] = last_game_dt
            is_returning_from_absence = (
                p in team_absences and
                target_dt.normalize() >= pd.to_datetime(team_absences[p]).normalize()
            )
            
            if pd.notna(last_known_team_game):
                # 올스타 브레이크나 연속 우취는 날짜만 흐르므로,
                # 달력상 간격 대신 해당 투수 등판 후 팀이 실제 소화한 경기 수로 이탈을 판정한다.
                team_games_since_appearance = len(
                    known_games[
                        (known_games['날짜'] > last_game_dt) &
                        (known_games['날짜'] <= last_known_team_game)
                    ]
                )
                if (
                    team_games_since_appearance >= 7 and
                    not is_returning_from_absence and
                    p != official_starter
                ):
                    continue 
            
            rest_days = max(0, (target_dt - last_game_dt).days - 1)
            rot_data.append({
                '선발투수': p,
                '최근등판': last_game_dt,
                '휴식일': rest_days,
                '후보보호': is_returning_from_absence or p == official_starter,
            })
            
    if not rot_data: return (official_starter if official_starter else "예측 불가"), pd.DataFrame(), is_official
    
    rot_df = pd.DataFrame(rot_data)
    rot_df = rot_df.sort_values('최근등판', ascending=True).reset_index(drop=True)
    # 화면이 과도하게 넓어지지 않도록 활성 후보는 최대 8명까지 표시한다.
    if len(rot_df) > 8:
        rot_df = (
            rot_df.sort_values(['후보보호', '최근등판'], ascending=[False, False])
            .head(8)
            .sort_values('최근등판', ascending=True)
            .reset_index(drop=True)
        )
    
    if is_official:
        predicted_pitcher = official_starter
    else:
        sim_date = last_known_team_game + timedelta(days=1)
        today_kst = pd.Timestamp.now(tz='Asia/Seoul').tz_localize(None).normalize()
        sim_rotation_queue = list(rot_df['선발투수'])
        rainout_carryover_pitcher = None
        
        while sim_date <= target_dt:
            sim_rows = df[(df['날짜'] == sim_date) & (df['팀'] == team)]
            fixed_row = sim_rows[
                (sim_rows['선발투수'].notna()) &
                (sim_rows['선발투수'] != '-')
            ]
            announced_pitcher = None if fixed_row.empty else fixed_row.iloc[0]['선발투수']
            is_manual_cancel = team_cancels and sim_date.strftime("%Y-%m-%d") in team_cancels
            is_data_cancel = not sim_rows[sim_rows['상태'] == '우천취소'].empty

            if is_manual_cancel or is_data_cancel:
                # 우취 당일 발표됐던 선발이 있으면 다음 실제 경기의 1순위 예상으로 이월한다.
                if announced_pitcher:
                    rainout_carryover_pitcher = announced_pitcher
                has_game = False
            else:
                # 오늘보다 이전인데도 '예정'으로 남은 행은 유령 경기로 보고
                # 로테이션을 소비하지 않는다. 종료/노게임은 known_games에 이미 반영된다.
                if sim_date < today_kst:
                    has_game = False
                else:
                    has_game = not sim_rows[
                        ~sim_rows['상태'].isin(['우천취소', '과거미확인'])
                    ].empty

            if has_game:

                temp_queue = []
                available_pitcher = None

                if announced_pitcher:
                    available_pitcher = announced_pitcher
                    rainout_carryover_pitcher = None

                    if announced_pitcher in sim_rotation_queue:
                        sim_rotation_queue.remove(announced_pitcher)

                elif rainout_carryover_pitcher:
                    carryover_return_date = team_absences.get(rainout_carryover_pitcher)
                    carryover_is_absent = (
                        carryover_return_date is not None and
                        sim_date < pd.to_datetime(carryover_return_date)
                    )
                    if not carryover_is_absent:
                        available_pitcher = rainout_carryover_pitcher
                        if available_pitcher in sim_rotation_queue:
                            sim_rotation_queue.remove(available_pitcher)
                    rainout_carryover_pitcher = None

                if available_pitcher is None:

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
    # 공식 기록(종료)만 테이블에 표시 — 노게임은 성적 집계 X, 휴식일 계산에만 반영
    target_dt = pd.to_datetime(target_date)
    pitcher_df = df[
        (df['선발투수'] == pitcher_name) &
        (df['상태'] == '종료') &
        (df['날짜'] < target_dt)
    ].copy().sort_values('날짜')
    if pitcher_df.empty: return pd.DataFrame()

    # 휴식일은 노게임 포함한 실제 최근 등판 기준으로 계산
    all_pitching = df[
        (df['선발투수'] == pitcher_name) &
        (df['상태'].isin(['종료', '노게임'])) &
        (df['날짜'] < target_dt)
    ].sort_values('날짜')

    rest_days_list = []
    for _, row in pitcher_df.iterrows():
        prev = all_pitching[all_pitching['날짜'] < row['날짜']]
        rest = max(0, (row['날짜'] - prev.iloc[-1]['날짜']).days - 1) if not prev.empty else 0
        rest_days_list.append(rest)
    pitcher_df['휴식일'] = rest_days_list

    recent = pitcher_df.tail(n).copy()
    recent['날짜'] = recent['날짜'].dt.strftime('%m/%d')

    for col in ['투구수', '피안타', '사사구', '자책점']:
        recent[col] = pd.to_numeric(recent[col], errors='coerce').fillna(0).astype(int)

    recent = recent[['날짜', '상대팀', '이닝', '자책점', '피안타', '사사구', '투구수', '휴식일']].reset_index(drop=True)

    while len(recent) < n:
        recent.loc[len(recent)] = ['', '', '', '', '', '', '', '']

    return recent

def get_season_stats(df, pitcher_name, target_date):
    target_dt = pd.to_datetime(target_date)
    # 시즌 스탯은 공식 기록인 '종료'만 집계 (노게임은 기록 무효)
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
    # 공식 기록(종료)만 로테이션 테이블에 표시
    team_df = df[
        (df['팀'] == team) &
        (df['상태'] == '종료') &
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
        # 휴식일은 노게임 포함해서 계산 (실제로 던진 날 기준)
        prev_games = df[
            (df['선발투수'] == p_name) &
            (df['상태'].isin(['종료', '노게임'])) &
            (df['날짜'] < p_date)
        ].sort_values('날짜')
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
