import pandas as pd
from datetime import timedelta

PREDICTOR_VERSION = "V4.1-sim-rest-20260903"

TEAM_COLORS = {
    '삼성': '#074CA1', '두산': '#131230', 'LG': '#C30452', 'KT': '#000000', 'SSG': '#CE0E2D',
    '롯데': '#002955', '한화': '#FF6600', 'KIA': '#EA0029', 'NC': '#315288', '키움': '#570514'
}

# 로테이션 판정 기준
# - 주후보: 마지막 선발 이후 팀이 0~5경기 소화
# - 보조후보: 6~10경기 소화
# - 제외: 11경기 이상 소화
#
# 미래 예측은 매 경기의 '예측 선발'을 실제 등판한 것으로 가정해 누적한다.
# 선택 우선순위:
#   1) 주후보 중 5일 이상 휴식
#   2) 보조후보 중 5일 이상 휴식
#   3) 주후보 중 4일 이상 휴식
#   4) 보조후보 중 4일 이상 휴식
# 3일 이하 휴식은 자동 예측하지 않는다.
PRIMARY_MAX_MISSED_GAMES = 5
BACKUP_MAX_MISSED_GAMES = 10
MAX_ROTATION_CANDIDATES = 6
RECENT_START_WINDOW = 24

PREFERRED_REST_DAYS = 5
MIN_ALLOWED_REST_DAYS = 4


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

    핵심:
    1) 후보 탈락은 날짜 차이가 아니라 마지막 선발 이후 '팀이 실제로 치른 경기 수'로 판단한다.
       - 주후보: 0~5경기
       - 보조:   6~10경기
       - 제외:   11경기 이상
    2) 미래의 각 경기에서 예측된 선발을 실제로 등판했다고 가정하고
       simulated_last_pitched에 누적한다.
    3) 다음 경기 선발 선택 때 그 '가상 최근등판일'로 휴식일을 다시 계산한다.
       - 주후보 5일+ → 보조 5일+ → 주후보 4일+ → 보조 4일+
       - 3일 이하 휴식은 자동 예측하지 않는다.
    4) 미래에 공식/수동 선발이 지정돼 있으면 그 날짜에는 해당 선발을 우선하고,
       이후 시뮬레이션에서도 그 등판을 실제 등판처럼 누적한다.
    """
    if team_absences is None:
        team_absences = {}
    if excluded_pitchers is None:
        excluded_pitchers = []
    if team_cancels is None:
        team_cancels = []

    target_dt = pd.to_datetime(target_date)

    # 타깃 날짜의 네이버/KBO 오피셜 선발
    official_row = df[
        (df['날짜'] == target_dt) &
        (df['팀'] == team) &
        (df['상태'] == '예정') &
        (df['선발투수'].notna()) &
        (df['선발투수'] != '-')
    ].copy()

    is_official = False
    official_starter = None
    if not official_row.empty:
        official_starter = str(official_row.iloc[0]['선발투수']).strip()
        if official_starter not in ('nan', ''):
            is_official = True

    # 실제로 소화된 선발 기록만 기준점으로 사용
    # 노게임은 기록은 무효지만 실제 투구/휴식에는 영향을 줬으므로 포함
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
        return (
            official_starter if official_starter else '데이터 부족',
            pd.DataFrame(),
            is_official,
        )

    last_known_team_game = known_games['날짜'].max()

    # 최근 실제 선발들에서 최대 6명 후보를 구성
    recent_games = known_games.sort_values('날짜', ascending=False).head(RECENT_START_WINDOW)
    rotation_pitchers = recent_games['선발투수'].dropna().unique()
    rotation_pitchers = [
        p for p in rotation_pitchers
        if p != '-' and p not in excluded_pitchers
    ][:MAX_ROTATION_CANDIDATES]

    simulated_last_pitched = {}
    candidate_roles = {}
    candidate_missed = {}

    for p in rotation_pitchers:
        p_games = known_games[known_games['선발투수'] == p].sort_values('날짜')
        if p_games.empty:
            continue

        last_game_dt = p_games.iloc[-1]['날짜']

        games_since_last_start = known_games[
            (known_games['날짜'] > last_game_dt) &
            (known_games['날짜'] <= last_known_team_game)
        ]['날짜'].nunique()

        if p == official_starter:
            role = '주후보'
        elif games_since_last_start <= PRIMARY_MAX_MISSED_GAMES:
            role = '주후보'
        elif games_since_last_start <= BACKUP_MAX_MISSED_GAMES:
            role = '보조'
        else:
            continue

        simulated_last_pitched[p] = last_game_dt
        candidate_roles[p] = role
        candidate_missed[p] = int(games_since_last_start)

    # 후보가 모두 잘렸더라도 타깃 오피셜 선발은 표시/예측 가능
    if not candidate_roles and not official_starter:
        return '예측 불가', pd.DataFrame(), is_official

    # 팀 휴식/말소 여부
    def is_absent(pitcher, sim_date):
        if pitcher not in team_absences:
            return False
        try:
            return sim_date < pd.to_datetime(team_absences[pitcher])
        except Exception:
            return False

    # 현재 시뮬레이션 기준 휴식일
    def calc_rest_days(pitcher, sim_date):
        last_dt = simulated_last_pitched.get(pitcher)
        if last_dt is None or pd.isna(last_dt):
            return 999
        return max(0, (sim_date - pd.to_datetime(last_dt)).days - 1)

    # 후보 집단에서 가장 오래 쉰 투수 선택
    def choose_oldest_eligible(pitchers, sim_date, min_rest):
        eligible = []
        for p in pitchers:
            if is_absent(p, sim_date):
                continue
            rest = calc_rest_days(p, sim_date)
            if rest >= min_rest:
                last_dt = simulated_last_pitched.get(p)
                # 오래 쉰 순 → 실제 최근등판이 오래된 순
                sort_dt = pd.Timestamp.min if last_dt is None or pd.isna(last_dt) else pd.to_datetime(last_dt)
                eligible.append((p, rest, sort_dt))

        if not eligible:
            return None

        eligible.sort(key=lambda x: (-x[1], x[2], x[0]))
        return eligible[0][0]

    def choose_predicted_pitcher(sim_date):
        primary = [
            p for p, role in candidate_roles.items()
            if role in ('주후보', '가상승격')
        ]
        backup = [
            p for p, role in candidate_roles.items()
            if role == '보조'
        ]

        # 일반적인 KBO 잔여경기 흐름:
        # 충분히 쉰 기존 로테 → 충분히 쉰 보조 → 4일 휴식 기존 → 4일 휴식 보조
        choice = choose_oldest_eligible(primary, sim_date, PREFERRED_REST_DAYS)
        if choice:
            return choice

        choice = choose_oldest_eligible(backup, sim_date, PREFERRED_REST_DAYS)
        if choice:
            return choice

        choice = choose_oldest_eligible(primary, sim_date, MIN_ALLOWED_REST_DAYS)
        if choice:
            return choice

        choice = choose_oldest_eligible(backup, sim_date, MIN_ALLOWED_REST_DAYS)
        if choice:
            return choice

        return None

    predicted_pitcher = None
    target_rest_snapshot = {}

    # 마지막 실제 경기 다음날부터 타깃까지 날짜별로 시뮬레이션
    sim_date = last_known_team_game + timedelta(days=1)

    while sim_date <= target_dt:
        sim_date_str = sim_date.strftime('%Y-%m-%d')

        # 사용자/DB 우취
        if team_cancels and sim_date_str in team_cancels:
            has_game = False
        else:
            # 마스터데이터에 실제 편성된 경기만 시뮬레이션
            game_rows = df[
                (df['날짜'] == sim_date) &
                (df['팀'] == team) &
                (df['상태'] != '우천취소')
            ]
            has_game = not game_rows.empty

        if not has_game:
            sim_date += timedelta(days=1)
            continue

        # 해당 날짜에 이미 선발이 지정돼 있으면 자동 예측보다 우선
        fixed_row = df[
            (df['날짜'] == sim_date) &
            (df['팀'] == team) &
            (df['상태'] != '우천취소') &
            (df['선발투수'].notna()) &
            (df['선발투수'] != '-')
        ]

        fixed_pitcher = None
        if not fixed_row.empty:
            fixed_pitcher = str(fixed_row.iloc[0]['선발투수']).strip()
            if fixed_pitcher in ('', 'nan'):
                fixed_pitcher = None

        if fixed_pitcher:
            available_pitcher = fixed_pitcher

            # 새 콜업/보조 선발이라도 한 번 실제/공식 선발로 잡히면
            # 이후 미래 예측에서는 로테이션 구성원으로 취급
            if available_pitcher not in candidate_roles:
                candidate_roles[available_pitcher] = '주후보'
                candidate_missed[available_pitcher] = 0
        else:
            available_pitcher = choose_predicted_pitcher(sim_date)

        if available_pitcher is None:
            available_pitcher = '예측 불가'

        # 타깃 날짜에 표시할 휴식일은 "그날 등판하기 직전" 기준
        if sim_date == target_dt:
            all_display_pitchers = set(candidate_roles.keys())
            if available_pitcher != '예측 불가':
                all_display_pitchers.add(available_pitcher)

            for p in all_display_pitchers:
                target_rest_snapshot[p] = calc_rest_days(p, target_dt)

            predicted_pitcher = available_pitcher
            break

        # 앞선 날짜의 예측/확정 선발은 실제 등판한 것으로 가정해서 누적
        if available_pitcher != '예측 불가':
            simulated_last_pitched[available_pitcher] = sim_date

            # 보조후보가 한 번 미래 선발로 투입되면
            # 이후에는 그 예측을 전제로 정상 로테이션에 편입
            if candidate_roles.get(available_pitcher) == '보조':
                candidate_roles[available_pitcher] = '가상승격'
                candidate_missed[available_pitcher] = 0

        sim_date += timedelta(days=1)

    if predicted_pitcher is None:
        # 타깃 날짜가 경기일이 아닌 예외 상황
        predicted_pitcher = choose_predicted_pitcher(target_dt)
        if predicted_pitcher is None:
            predicted_pitcher = official_starter if official_starter else '예측 불가'

        for p in candidate_roles:
            target_rest_snapshot[p] = calc_rest_days(p, target_dt)

    # 타깃 오피셜이 후보 명단 밖에 있더라도 버튼/정보 표시는 가능하게 추가
    if official_starter and official_starter not in candidate_roles:
        candidate_roles[official_starter] = '주후보'
        candidate_missed[official_starter] = 0
        target_rest_snapshot.setdefault(
            official_starter,
            calc_rest_days(official_starter, target_dt)
        )

    # 화면용 후보 표 생성
    rot_rows = []
    for p, role in candidate_roles.items():
        rest = target_rest_snapshot.get(p, calc_rest_days(p, target_dt))
        rot_rows.append({
            '선발투수': p,
            '휴식일': '?' if rest == 999 else int(rest),
            '미등판경기': int(candidate_missed.get(p, 0)),
            '구분': role,
            '_last': simulated_last_pitched.get(p, pd.NaT),
        })

    rot_df = pd.DataFrame(rot_rows)
    if not rot_df.empty:
        # 화면 정렬: 타깃 기준 오래 쉰 순
        rot_df['_rest_sort'] = pd.to_numeric(rot_df['휴식일'], errors='coerce').fillna(999)
        rot_df = (
            rot_df
            .sort_values(['_rest_sort', '_last'], ascending=[False, True], na_position='first')
            .drop(columns=['_rest_sort', '_last'])
            .reset_index(drop=True)
        )

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
