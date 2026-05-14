import requests
import re
import csv
import time
from datetime import datetime, timedelta
import pandas as pd
import os

def master_collector_v16():
    team_codes = {
        'KT': 'KT', 'KIA': 'HT', '롯데': 'LT', 'SSG': 'SK', 'LG': 'LG',
        'NC': 'NC', '두산': 'OB', '키움': 'WO', '삼성': 'SS', '한화': 'HH'
    }

    now_kst = datetime.utcnow() + timedelta(hours=9)
    today_obj = now_kst.date()
    start_date = today_obj - timedelta(days=3)
    end_date = today_obj + timedelta(days=7)

    print(f"🚀 [V16] 심플 모드 가동! (진행중 경기는 '예정'으로 간주) 타겟 기간: {start_date} ~ {end_date}")

    months_to_check = list(set([f"{start_date.month:02d}", f"{end_date.month:02d}"]))
    months_to_check.sort()

    new_data = []

    for month in months_to_check:
        print(f"\n🔍 2026년 {month}월 KBO 스케줄 추출 중...")
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

            game_date_obj = datetime.strptime(current_date_str, "%Y-%m-%d").date()
            if not (start_date <= game_date_obj <= end_date):
                continue

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
                
                # 1차 KBO 텍스트 판독 (나중에 네이버 API로 덮어씀)
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
                        time.sleep(0.1) 
                        base_url = f"https://api-gw.sports.naver.com/schedule/games/{game_id}"
                        base_res = requests.get(base_url, headers=headers, timeout=5)
                        
                        if base_res.status_code == 200:
                            base_data = base_res.json()
                            game_info = base_data.get('result', {}).get('game', {})
                            game_status = game_info.get('statusCode', '')

                            # 🔥 [핵심 로직] 네이버 API 상태값을 최우선으로 믿기!
                            if game_status == 'CANCEL':
                                status = '우천취소'
                            elif game_status == 'RESULT':
                                status = '종료'
                            elif game_status in ['BEFORE', 'PLAYING']:
                                status = '예정' # 진행 중이어도 무조건 '예정'으로 묶어버림!

                            if status == '예정' and game_date_obj < today_obj:
                                status = '우천취소'

                            a_name, h_name = '-', '-'
                            a_inn, a_np, a_hit, a_sasa, a_er = '-', '-', '-', '-', '-'
                            h_inn, h_np, h_hit, h_sasa, h_er = '-', '-', '-', '-', '-'

                            if status == '우천취소':
                                new_data.append([current_date_str, away_team, home_team, '원정', status, '-', '-', '-', '-', '-', '-', '-', '-'])
                                new_data.append([current_date_str, home_team, away_team, '홈', status, '-', '-', '-', '-', '-', '-', '-', '-'])
                                print(f"   ☔ {current_date_str} | {away_team} vs {home_team} [저장: 우천취소]")
                                is_saved = True

                            elif status == '종료':
                                record_url = f"https://api-gw.sports.naver.com/schedule/games/{game_id}/record"
                                rec_res = requests.get(record_url, headers=headers, timeout=5)
                                if rec_res.status_code == 200:
                                    rec_data = rec_res.json()
                                    recordData = rec_data.get('result', {}).get('recordData') or {}
                                    if 'pitchersBoxscore' in recordData:
                                        pitchers = recordData['pitchersBoxscore']
                                        if pitchers.get('away') and pitchers.get('home') and len(pitchers['away']) > 0 and len(pitchers['home']) > 0:
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
                                            
                                            away_score = game_info.get('awayTeamScore', away_score)
                                            home_score = game_info.get('homeTeamScore', home_score)
                                            
                                            new_data.append([current_date_str, away_team, home_team, '원정', status, away_score, home_score, a_name, a_inn, a_np, a_hit, a_sasa, a_er])
                                            new_data.append([current_date_str, home_team, away_team, '홈', status, home_score, away_score, h_name, h_inn, h_np, h_hit, h_sasa, h_er])
                                            print(f"   ⚾ {current_date_str} | {away_team}({a_name}) vs {home_team}({h_name}) [저장: {status}]")
                                            is_saved = True

                            elif status == '예정':
                                a_name = game_info.get('awayStarterName', '-')
                                h_name = game_info.get('homeStarterName', '-')
                                if not a_name: a_name = '-'
                                if not h_name: h_name = '-'

                                if a_name != '-' and h_name != '-':
                                    # 진행 중이더라도 점수 표시 안 하고 '예정' 상태로 저장!
                                    new_data.append([current_date_str, away_team, home_team, '원정', status, '-', '-', a_name, a_inn, a_np, a_hit, a_sasa, a_er])
                                    new_data.append([current_date_str, home_team, away_team, '홈', status, '-', '-', h_name, h_inn, h_np, h_hit, h_sasa, h_er])
                                    
                                    p_status = "🔥 진행중(예정처리)" if game_status == 'PLAYING' else "⏰ 예정"
                                    print(f"   {p_status} | {away_team}({a_name}) vs {home_team}({h_name}) [저장: {status}]")
                                    is_saved = True

                    except Exception as e:
                        print(f"   ⚠️ 에러 ({game_id}): {e}")
                        pass 
                    
                if not is_saved:
                    if status == '예정' and game_date_obj < today_obj:
                        status = '우천취소'
                        print(f"   ☔ {current_date_str} | {away_team} vs {home_team} [저장: 우천취소 (강제변환)]")

                    new_data.append([current_date_str, away_team, home_team, '원정', status, away_score, home_score, '-', '-', '-', '-', '-', '-'])
                    new_data.append([current_date_str, home_team, away_team, '홈', status, home_score, away_score, '-', '-', '-', '-', '-', '-'])
                    if status != '우천취소':
                        print(f"   ⚪ {current_date_str} | {away_team} vs {home_team} [저장: 정보 부족]")

    print("\n💾 데이터 병합(Upsert) 작업 시작...")
    columns = ['날짜', '팀', '상대팀', '구장', '상태', '득점', '실점', '선발투수', '이닝', '투구수', '피안타', '사사구', '자책점']
    new_df = pd.DataFrame(new_data, columns=columns)
    new_df['날짜'] = pd.to_datetime(new_df['날짜'])
    
    file_name = '로테이션_마스터데이터.csv'
    if os.path.exists(file_name):
        try:
            existing_df = pd.read_csv(file_name)
            existing_df['날짜'] = pd.to_datetime(existing_df['날짜'])
            mask = (existing_df['날짜'].dt.date >= start_date) & (existing_df['날짜'].dt.date <= end_date)
            existing_df = existing_df[~mask]
            final_df = pd.concat([existing_df, new_df], ignore_index=True)
            print("   ✔️ 기존 데이터 도려내고 새 데이터 끼워넣기 성공!")
        except Exception as e:
            print(f"   ⚠️ 기존 파일 읽기 실패, 덮어씁니다: {e}")
            final_df = new_df
    else:
        print("   ✔️ 마스터 파일이 없어 새로 생성합니다.")
        final_df = new_df
        
    final_df = final_df.sort_values(by=['날짜', '팀'])
    final_df['날짜'] = final_df['날짜'].dt.strftime('%Y-%m-%d')
    final_df.to_csv(file_name, index=False, encoding='utf-8-sig')
    
    print(f"\n🎉 V16 심플 업데이트 완료! (크롤링 구간: {start_date} ~ {end_date})")

master_collector_v16()
