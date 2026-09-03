import pandas as pd
from datetime import timedelta

TEAM_COLORS = {
    '삼성': '#074CA1', '두산': '#131230', 'LG': '#C30452', 'KT': '#000000', 'SSG': '#CE0E2D',
    '롯데': '#002955', '한화': '#FF6600', 'KIA': '#EA0029', 'NC': '#315288', '키움': '#570514'
}

# 로테이션 판정 기준
# - 주후보: 마지막 선발 이후 팀이 0~5경기 소화
# - 보조후보: 6~7경기 소화
# - 제외: 8경기 이상 소화
# 날짜 차이가 아니라 '실제로 치른 경기 수'를 보므로 장마/잔여경기/긴 휴식기에 덜 흔들린다.
PRIMARY_MAX_MISSED_GAMES = 5
BACKUP_MAX_MISSED_GAMES = 7
MIN_PRIMARY_PITCHERS = 3
MAX_ROTATION_CANDIDATES = 6
RECENT_START_WINDOW = 20


def get_active_rotation(df, team, target_date, excluded_pitchers=None):
    if excluded_pitchers is None:
        excluded_pitchers = []

    # 노게임도 실제 투구가 있었던 것으로 보고 최근 선발 후보 탐색에는 포함
    past_games = df[
        (df['팀'] == team) &
        (df['상태'].isin(['종료', '수동확정', '노게임'])) &
        (df['날짜'] < pd.to_datetime(target_date))
    ]
    if past_games.empty:
        return []

    recent_starters = (
        past_games
        .sort_values('날짜', ascending=False)
        .head(RECENT_START_WINDOW)['선발투수']
        .dropna()
        .unique()
    )
    return [p for p in recent_starters if p != '-' and p not in excluded_pitchers][:MAX_ROTATION_CANDIDATES]


def predict_starter(df, team, target_date, team_absences=None, excluded_pitchers=None, team_cancels=None):
    """
    선발 예측 + 후보 목록 반환.

    후보 분류 기준은 '마지막 선발 이후 팀이 실제로 몇 경기를 치렀는지'다.
      - 주후보: 0~5경기
      - 보조:   6~7경기 (화면에는 표시하지만 기본 예측 큐에는 넣지 않음)
      - 제외:   8경기 이상

    주후보가 3명 미만이면 보조후보 중 최근성이 높은 투수를 자동 승격한다.
    공식 선발은 위 기준과 무관하게 우선한다.
    """
    if team_absences is None:
        team_absences = {}
    if excluded_pitchers is None:
        excluded_pitchers = []
    if team_cancels is None:
        team_cancels = []

    target_dt = pd.to_datetime(target_date)

    official_row = df[
        (df['날짜'] == target_dt) &
        (df['팀'] == team) &
        (df['상태'] == '예정') &
        (df['선발투수'] != '-')
    ].copy()

    is_official = False
    official_starter = None
    if not official_row.empty:
        official_starter = str(official_row.iloc[0]['선발투수']).strip()
        if official_starter not in ('nan', ''):
            is_official = True

    # 종료/노게임만 실제로 소화한 팀 경기로 본다.
    # 우천취소와 미래 '예정'은 로테이션 탈락 판정에 포함하지 않는다.
    known_games = df[
        (df['팀'] == team) &
        (df['상태'].isin(['종료', '노게임'])) &
        (df['선발투수'].notna()) &
        (df['선발투수'] != '-') &
        (df['날짜'] < target_dt)
    ].copy()

    # 로컬/DB 우취 처리 날짜는 실제 경기 수에서도 제외
    if team_cancels:
        cancel_dt_list = pd.to_datetime(team_cancels)
        known_games = known_games[~known_games['날짜'].isin(cancel_dt_list)]

    if known_games.empty:
        return (
            official_starter if official_starter else '데이터 부족',
            pd.DataFrame(),
            is_official,
        )

    recent_games = known_games.sort_values('날짜', ascending=False).head(RECENT_START_WINDOW)
    rotation_pitchers = recent_games['선발투수'].dropna().unique()
    rotation_pitchers = [
        p for p in rotation_pitchers
        if p != '-' and p not in excluded_pitchers
    ][:MAX_ROTATION_CANDIDATES]

    last_known_team_game = known_games['날짜'].max()
    simulated_last_pitched = {}
    candidate_rows = []

    for p in rotation_pitchers:
        p_games = known_games[known_games['선발투수'] == p].sort_values('날짜')
        if p_games.empty:
            continue

        last_game_dt = p_games.iloc[-1]['날짜']
        simulated_last_pitched[p] = last_game_dt

        # 핵심 변경: 날짜 차이가 아니라 마지막 등판 뒤 실제 팀 경기 수를 센다.
        games_since_last_start = known_games[
            (known_games['날짜'] > last_game_dt) &
            (known_games['날짜'] <= last_known_team_game)
        ]['날짜'].nunique()

        # 공식 선발은 장기 미등판이어도 후보에 복귀시킨다.
        if p == official_starter:
            rotation_status = '주후보'
        elif games_since_last_start <= PRIMARY_MAX_MISSED_GAMES:
            rotation_status = '주후보'
        elif games_since_last_start <= BACKUP_MAX_MISSED_GAMES:
            rotation_status = '보조'
        else:
            continue

        rest_days = max(0, (target_dt - last_game_dt).days - 1)
        candidate_rows.append({
            '선발투수': p,
            '최근등판': last_game_dt,
            '휴식일': rest_days,
            '미등판경기': int(games_since_last_start),
            '구분': rotation_status,
        })

    if not candidate_rows:
        return (
            official_starter if official_starter else '예측 불가',
            pd.DataFrame(),
            is_official,
        )

    rot_df = pd.DataFrame(candidate_rows)
    rot_df = rot_df.sort_values('최근등판', ascending=True).reset_index(drop=True)

    # 주후보가 지나치게 줄었을 때만 보조후보를 예측 큐에 승격한다.
    primary_count = int((rot_df['구분'] == '주후보').sum())
    if primary_count < MIN_PRIMARY_PITCHERS:
        need = MIN_PRIMARY_PITCHERS - primary_count
        backup_indices = (
            rot_df[rot_df['구분'] == '보조']
            .sort_values(['미등판경기', '최근등판'], ascending=[True, False])
            .index
            .tolist()
        )
        for idx in backup_indices[:need]:
            rot_df.at[idx, '구분'] = '승격'

    if is_official:
        predicted_pitcher = official_starter
    else:
        # 기본 예측은 주후보 + 필요한 경우 승격된 후보만 사용한다.
        active_mask = rot_df['구분'].isin(['주후보', '승격'])
        active_df = rot_df[active_mask].copy()
        backup_df = rot_df[rot_df['구분'] == '보조'].copy()

        if active_df.empty:
            # 방어 로직: 주후보가 0명인 극단 상황에서는 보조후보를 사용
            active_df = backup_df.copy()
            backup_df = backup_df.iloc[0:0]

        sim_date = last_known_team_game + timedelta(days=1)
        sim_rotation_queue = list(active_df['선발투수'])
        backup_queue = list(backup_df['선발투수'])

        predicted_pitcher = None

        while sim_date <= target_dt:
            fixed_pitcher = None

            if team_cancels and sim_date.strftime('%Y-%m-%d') in team_cancels:
                has_game = False
            else:
                has_game = not df[
                    (df['날짜'] == sim_date) &
                    (df['팀'] == team) &
                    (df['상태'] != '우천취소')
                ].empty

                fixed_row = df[
                    (df['날짜'] == sim_date) &
                    (df['팀'] == team) &
                    (df['선발투수'].notna()) &
                    (df['선발투수'] != '-')
                ]
                if not fixed_row.empty:
                    fixed_pitcher = fixed_row.iloc[0]['선발투수']

            if has_game:
                temp_queue = []
                available_pitcher = None
                used_backup = False

                if fixed_pitcher:
                    available_pitcher = fixed_pitcher
                    if fixed_pitcher in sim_rotation_queue:
                        sim_rotation_queue.remove(fixed_pitcher)
                    if fixed_pitcher in backup_queue:
                        backup_queue.remove(fixed_pitcher)
                else:
                    # 1) 주후보 큐에서 복귀 전 투수를 건너뛰며 선택
                    while sim_rotation_queue:
                        p = sim_rotation_queue.pop(0)
                        if p in team_absences and sim_date < pd.to_datetime(team_absences[p]):
                            temp_queue.append(p)
                        else:
                            available_pitcher = p
                            break

                    # 2) 주후보가 모두 unavailable이면 보조후보를 비상 사용
                    if available_pitcher is None:
                        for p in list(backup_queue):
                            if p in team_absences and sim_date < pd.to_datetime(team_absences[p]):
                                continue
                            available_pitcher = p
                            backup_queue.remove(p)
                            used_backup = True
                            break

                if available_pitcher is None:
                    available_pitcher = '예측 불가'

                if sim_date == target_dt:
                    predicted_pitcher = available_pitcher
                    for idx, row in rot_df.iterrows():
                        p_name = row['선발투수']
                        if p_name in simulated_last_pitched:
                            last_d = simulated_last_pitched[p_name]
                            new_rest = max(0, (target_dt - last_d).days - 1)
                            rot_df.at[idx, '휴식일'] = new_rest
                    break

                if available_pitcher != '예측 불가':
                    simulated_last_pitched[available_pitcher] = sim_date

                # 건너뛴 부재 투수는 앞쪽에 유지하고, 실제 등판자는 맨 뒤로 보낸다.
                if available_pitcher != '예측 불가' and not used_backup:
                    sim_rotation_queue = temp_queue + sim_rotation_queue + [available_pitcher]
                else:
                    sim_rotation_queue = temp_queue + sim_rotation_queue
                    if used_backup and available_pitcher != '예측 불가':
                        # 비상 투입된 보조후보는 이후 연속 선택되지 않도록 보조 큐 뒤로 돌린다.
                        backup_queue.append(available_pitcher)

            sim_date += timedelta(days=1)

        if predicted_pitcher is None:
            # 타깃 날짜가 팀 경기일이 아닌 등 예외 상황에서 가장 오래 쉰 주후보를 반환
            fallback_df = rot_df[rot_df['구분'].isin(['주후보', '승격'])]
            if fallback_df.empty:
                fallback_df = rot_df
            predicted_pitcher = fallback_df.iloc[0]['선발투수']

    return predicted_pitcher, rot_df[['선발투수', '휴식일', '미등판경기', '구분']], is_official


def get_pitcher_recent_stats(df, pitcher_name, target_date, n=5):
    # 공식 기록(종료)만 테이블에 표시 — 노게임은 성적 집계 X, 휴식일 계산에만 반영
    target_dt = pd.to_datetime(target_date)
    pitcher_df = df[
        (df['선발투수'] == pitcher_name) &
        (df['상태'] == '종료') &
        (df['날짜'] < target_dt)
    ].copy().sort_values('날짜')
    if pitcher_df.empty:
        return pd.DataFrame()

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
    pitcher_df = df[
        (df['선발투수'] == pitcher_name) &
        (df['상태'] == '종료') &
        (df['날짜'] < target_dt)
    ].copy()
    if pitcher_df.empty:
        return {'등판': 0, '총이닝': '0', 'ERA': '-', 'WHIP': '-'}

    games = len(pitcher_df)

    def parse_inning(inn_str):
        try:
            inn_str = str(inn_str).strip()
            if not inn_str or inn_str == '-':
                return 0.0
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
                if rem == 0.1:
                    return whole + 1 / 3
                elif rem == 0.2:
                    return whole + 2 / 3
                return val
        except Exception:
            return 0.0

    total_innings_float = sum(pitcher_df['이닝'].apply(parse_inning))
    total_er = pd.to_numeric(pitcher_df['자책점'], errors='coerce').sum()
    total_hits = pd.to_numeric(pitcher_df['피안타'], errors='coerce').sum()
    total_walks = pd.to_numeric(pitcher_df['사사구'], errors='coerce').sum()

    whole_innings = int(total_innings_float)
    remainder = total_innings_float - whole_innings

    if remainder > 0.6:
        frac_str = ' ⅔'
    elif remainder > 0.3:
        frac_str = ' ⅓'
    else:
        frac_str = ''
    display_innings = f'{whole_innings}{frac_str}'

    era = (total_er * 9) / total_innings_float if total_innings_float > 0 else 0
    whip = (total_hits + total_walks) / total_innings_float if total_innings_float > 0 else 0

    return {
        '등판': games,
        '총이닝': display_innings,
        'ERA': f'{era:.2f}',
        'WHIP': f'{whip:.2f}',
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
    if recent.empty:
        return pd.DataFrame()

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
