import requests
import re
import csv
import time
from datetime import datetime

def master_collector_v11():
    team_codes = {
        'KT': 'KT', 'KIA': 'HT', '롯데': 'LT', 'SSG': 'SK', 'LG': 'LG',
        'NC': 'NC', '두산': 'OB', '키움': 'WO', '삼성': 'SS', '한화': 'HH'
    }

    print("🚀 [V11] KBO 예고 선발 & 우취 판독기 완벽 가동! (사진 컬럼 삭제)")

    with open('로테이션_마스터데이터.csv', 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        # 💡 성우의 요청대로 '선발투수사진' 컬럼을 깔끔하게 지웠어!
        writer.writerow(['날짜', '팀', '상대팀', '구장', '상태', '득점', '실점', '선발투수', '이닝', '투구수', '피안타', '사사구', '자책점'])

        current_month = datetime.now().month
        months_to_check = [f"{m:02d}" for m in range(max(3, current_month-1), min(12, current_month+2))]

        for month in months_to_check:
            print(f"\n🔍 2026년 {month}월 KBO 스케줄 분석 중...")
            kbo_url = "https://www.koreabaseball.com/ws/Schedule.asmx/GetScheduleList"
            payload = {'leId': '1', 'srIdList': '0,9', 'seasonId': '2026', 'gameMonth': month, 'teamId': ''}
            
            try:
                kbo_res = requests.post(kbo_url, data=payload, timeout=10)
                if kbo_res.status_code != 200: continue
                kbo_data = kbo_res.json()
            except:
                continue
            
            rows = kbo_data.get('rows', [])
            current_date_str = ""

            for idx, row_info in enumerate(rows):
                cells = row_info.get('row', [])
                if not cells: continue

                date_cell_text = cells[0].get('Text', '').strip()
                if date_cell_text and "(" in date_cell_text:
                    month_day = date_cell_text.split('(')[0].replace('.', '-') 
                    current_date_str = f"2026-{month_day}" 
                
                if not current_date_str: continue 

                play_text = next((c.get('Text', '') for c in cells if c.get('Class') == 'play'), "")
                if not play_text: continue 

                clean_text = re.sub(r'<[^>]+>', ' ', play_text)
                teams = re.findall(r'<span>(.*?)</span>', play_text)
                
                if len(teams) >= 2: 
                    away_team = teams[0].strip()
                    home_team = teams[-1].strip()

                    status = '예정'
                    away_score, home_score = '-', '-'
                    nums = re.findall(r'\d+', clean_text)
                    
                    # 1차 판독 (KBO 공홈 기준)
                    if "취소" in play_text: status = '우천취소'
                    elif len(nums) >= 2: 
                        status = '종료'
                        away_score = nums[0]
                        home_score = nums[-1]

                    date_id = current_date_str.replace('-', '')
                    away_c = team_codes.get(away_team)
                    home_c = team_codes.get(home_team)
                    is_saved = False 

                    if away_c and home_c:
                        game_id = f"{date_id}{away_c}{home_c}02026"
                        headers = {'User-Agent': 'Mozilla/5.0'}
                        
                        try:
                            time.sleep(0.3) # 네이버 차단 방지
                            
                            # 💡 1단계: 네이버 기본 정보 찌르기 (우취 및 예고 선발 확인용)
                            base_url = f"https://api-gw.sports.naver.com/schedule/games/{game_id}"
                            base_res = requests.get(base_url, headers=headers, timeout=5)
                            
                            if base_res.status_code == 200:
                                base_data = base_res.json()
                                game_info = base_data.get('result', {}).get('game', {})
                                game_status = game_info.get('statusCode', '')

                                # 💡 네이버 교차 검증: KBO보다 네이버가 우취를 먼저 띄웠다면 업데이트!
                                if game_status == 'CANCEL':
                                    status = '우천취소'

                                a_name, h_name = '-', '-'
                                a_inn, a_np, a_hit, a_sasa, a_er = '-', '-', '-', '-', '-'
                                h_inn, h_np, h_hit, h_sasa, h_er = '-', '-', '-', '-', '-'

                                # 💡 2단계: 경기 종료(RESULT)면 기록(record) 찌르기
                                if status == '종료' or game_status == 'RESULT':
                                    record_url = f"https://api-gw.sports.naver.com/schedule/games/{game_id}/record"
                                    rec_res = requests.get(record_url, headers=headers, timeout=5)
                                    if rec_res.status_code == 200:
                                        rec_data = rec_res.json()
                                        recordData = rec_data.get('result', {}).get('recordData') or {}
                                        if 'pitchersBoxscore' in recordData:
                                            pitchers = recordData['pitchersBoxscore']
                                            if pitchers.get('away') and pitchers.get('home'):
                                                def get_stats(p):
                                                    name = p.get('name', '')
                                                    inn = p.get('inn', '0')
                                                    np = p.get('bf', '0') 
                                                    hit = p.get('hit', '0')
                                                    sasa = str(int(p.get('bb', 0)) + int(p.get('hp', 0))) 
                                                    er = p.get('er', '0')
                                                    return name, inn, np, hit, sasa, er

                                                a_name, a_inn, a_np, a_hit, a_sasa, a_er = get_stats(pitchers['away'][0])
                                                h_name, h_inn, h_np, h_hit, h_sasa, h_er = get_stats(pitchers['home'][0])
                                                # 종료된 경기는 스코어도 네이버 기준으로 최신화
                                                away_score = game_info.get('awayTeamScore', away_score)
                                                home_score = game_info.get('homeTeamScore', home_score)
                                                status = '종료'

                                # 💡 3단계: 경기 전(BEFORE)이면 기본 정보에서 이름만 쏙!
                                elif status == '예정' or game_status == 'BEFORE':
                                    a_name = game_info.get('awayStarterName', '-')
                                    h_name = game_info.get('homeStarterName', '-')
                                    if not a_name: a_name = '-'
                                    if not h_name: h_name = '-'

                                # 이름이 하나라도 긁혔으면 무조건 저장!
                                if a_name != '-' and h_name != '-':
                                    writer.writerow([current_date_str, away_team, home_team, '원정', status, away_score, home_score, a_name, a_inn, a_np, a_hit, a_sasa, a_er])
                                    writer.writerow([current_date_str, home_team, away_team, '홈', status, home_score, away_score, h_name, h_inn, h_np, h_hit, h_sasa, h_er])
                                    print(f"   ⚾ {current_date_str} | {away_team}({a_name}) vs {home_team}({h_name}) [저장: {status}]")
                                    is_saved = True

                        except Exception as e:
                            print(f"   ⚠️ 에러 ({game_id}): {e}")
                            pass 
                        
                    # 우천취소이거나 정보를 못 찾았을 때 빈 줄 저장
                    if not is_saved:
                        writer.writerow([current_date_str, away_team, home_team, '원정', status, away_score, home_score, '-', '-', '-', '-', '-', '-'])
                        writer.writerow([current_date_str, home_team, away_team, '홈', status, home_score, away_score, '-', '-', '-', '-', '-', '-'])
                        print(f"   ⚪ {current_date_str} | {away_team} vs {home_team} [상태: {status}]")

    print("\n🎉 V11 데이터 수집 완료! 내일 예고선발과 우천취소 판단이 완벽해졌습니다!")

master_collector_v11()
