import pandas as pd

TEAM_COLORS = {
    'KIA': '#EA0029', 'LG':  '#C30452', 'KT':   '#000000',
    'NC':  '#315288', 'SSG': '#CE0E2D', '두산': '#131230',
    '롯데':'#041E42', '삼성':'#0038A8', '키움': '#820024', '한화':'#FF6600',
}

def parse_innings(inn):
    if pd.isna(inn) or str(inn).strip() in ['-', '']: return 0.0
    s = str(inn).strip().replace('⅓', '.33').replace('⅔', '.67')
    parts = s.split()
    try: return sum(float(p) for p in parts)
    except: return 0.0

# 💡 '수동확정' 상태도 실제 던진 경기처럼 취급해서 로테이션에 포함!
def get_active_rotation(df, team, target_date, n_recent=8):
    team_df = df[(df['팀'] == team) & 
                 (df['상태'].isin(['종료', '수동확정'])) & 
                 (df['선발투수'] != '-') & 
                 (df['날짜'] < pd.to_datetime(target_date))].copy().sort_values('날짜')
                 
    if team_df.empty: return pd.DataFrame(columns=['선발투수', '마지막등판일', '휴식일'])

    recent_games = team_df.tail(n_recent)
    active_pitchers = recent_games['선발투수'].unique().tolist()

    last_dates = team_df[team_df['선발투수'].isin(active_pitchers)].groupby('선발투수')['날짜'].max().reset_index().rename(columns={'날짜': '마지막등판일'}).sort_values('마지막등판일')
    target_dt = pd.to_datetime(target_date)
    last_dates['휴식일'] = (target_dt - last_dates['마지막등판일']).dt.days
    return last_dates.reset_index(drop=True)

def predict_starter(df, team, target_date):
    rotation_df = get_active_rotation(df, team, target_date)
    if rotation_df.empty: return None, rotation_df
    
    # 💡 '수동확정'도 past_games로 카운트!
    past_games = df[(df['팀'] == team) & (df['상태'].isin(['종료', '수동확정'])) & (df['날짜'] < pd.to_datetime(target_date))]
    if past_games.empty: return rotation_df.iloc[0]['선발투수'], rotation_df
        
    last_played_date = past_games['날짜'].max()
    future_games = df[(df['팀'] == team) & (df['날짜'] > last_played_date) & (df['날짜'] <= pd.to_datetime(target_date)) & (df['상태'] == '예정')]
    games_to_play = len(future_games)
    
    if games_to_play > 0 and len(rotation_df) > 0:
        pred_idx = (games_to_play - 1) % len(rotation_df)
        predicted = rotation_df.iloc[pred_idx]['선발투수']
    else:
        predicted = rotation_df.iloc[0]['선발투수']
        
    return predicted, rotation_df

def get_pitcher_recent_stats(df, pitcher_name, target_date, n=5): # n=5 로 변경
    pitcher_df = df[(df['선발투수'] == pitcher_name) & (df['상태'] == '종료') & (df['날짜'] < pd.to_datetime(target_date))].copy().sort_values('날짜')
    if pitcher_df.empty: return pd.DataFrame()

    pitcher_df['휴식일'] = pitcher_df['날짜'].diff().dt.days.fillna(0).astype(int)
    recent = pitcher_df.tail(n).copy()
    recent['날짜'] = recent['날짜'].dt.strftime('%m/%d')
    
    for col in ['투구수', '피안타', '사사구', '자책점']:
        recent[col] = pd.to_numeric(recent[col], errors='coerce').fillna(0).astype(int)

    # 🔥 순서 변경: 이닝 -> 자책점 -> 투구수
    return recent[['날짜', '상대팀', '이닝', '자책점', '투구수', '피안타', '사사구', '휴식일']].reset_index(drop=True)

def get_season_stats(df, pitcher_name, target_date):
    pitcher_df = df[(df['선발투수'] == pitcher_name) & (df['상태'] == '종료') & (df['날짜'] < pd.to_datetime(target_date))].copy()
    if pitcher_df.empty: return {'등판': 0, 'ERA': '-', 'WHIP': '-', '총이닝': 0} # WHIP 빈값 추가

    games = len(pitcher_df)
    total_inn = pitcher_df['이닝'].apply(parse_innings).sum()
    total_er = pd.to_numeric(pitcher_df['자책점'], errors='coerce').fillna(0).sum()
    
    # 🔥 WHIP 계산 추가!
    total_hit = pd.to_numeric(pitcher_df['피안타'], errors='coerce').fillna(0).sum()
    total_sasa = pd.to_numeric(pitcher_df['사사구'], errors='coerce').fillna(0).sum()
    
    era = round(total_er / total_inn * 9, 2) if total_inn > 0 else '-'
    whip = round((total_hit + total_sasa) / total_inn, 2) if total_inn > 0 else '-'
    
    return {'등판': games, 'ERA': era, 'WHIP': whip, '총이닝': round(total_inn, 1)}

def get_recent_rotation_list(df, team, target_date, n=10):
    team_df = df[(df['팀'] == team) & (df['상태'].isin(['종료', '수동확정'])) & (df['선발투수'] != '-') & (df['날짜'] < pd.to_datetime(target_date))].copy().sort_values('날짜', ascending=False)
    recent = team_df.head(n).copy()
    if recent.empty: return pd.DataFrame()

    recent = recent.sort_values('날짜', ascending=True)
    recent['날짜'] = recent['날짜'].dt.strftime('%m/%d')
    for c in ['투구수', '자책점']:
        recent[c] = pd.to_numeric(recent[c], errors='coerce').fillna(0).astype(int)

    # 🔥 순서 변경: 이닝 -> 자책점 -> 투구수
    return recent[['날짜', '상대팀', '선발투수', '이닝', '자책점', '투구수']].reset_index(drop=True)
