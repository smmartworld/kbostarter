import requests
import re
import csv
import time

def master_collector_v7():
    team_codes = {
        'KT': 'KT', 'KIA': 'HT', '롯데': 'LT', 'SSG': 'SK', 'LG': 'LG',
        'NC': 'NC', '두산': 'OB', '키움': 'WO', '삼성': 'SS', '한화': 'HH'
    }

    print("🚀 [V7] KBO 선발투수 데이터 & 사진 URL 수집 시작!")

    with open('로테이션_마스터데이터.csv', 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        # 💡 사진 URL을 통째로 저장할 컬럼 추가!
        writer.writerow(['날짜', '팀', '상대팀', '구장', '상태', '득점', '실점', '선발투수', '이닝', '투구수', '피안타', '사사구', '자책점', '선발투수사진'])

        for month in [f"{i:02d}" for i in range(3, 11)]:
            kbo_url = "https://www.koreabaseball.com/ws/Schedule.asmx/GetScheduleList"
            payload = {'leId': '1', 'srIdList': '0,9', 'seasonId': '2026', 'gameMonth': month, 'teamId': ''}
            
            kbo_res = requests.post(kbo_url, data=payload)
            if kbo_res.status_code != 200: continue
            kbo_data = kbo_res.json()
            
            rows = kbo_data.get('rows', [])
            current_date_str = ""

            for row_info in rows:
                cells = row_info.get('row', [])
                if len(cells) < 3: continue 

                date_text = cells[0].get('Text', '')
                if "(" in date_text:
                    month_day = date_text.split('(')[0].replace('.', '-') 
                    current_date_str = f"2026-{month_day}" 
                
                play_text = next((c.get('Text', '') for c in cells if c.get('Class') == 'play'), "")
                clean_text = re.sub(r'<[^>]+>', ' ', play_text)
                teams = re.findall(r'<span>(.*?)</span>', play_text)
                
                if len(teams) >= 2 and current_date_str: 
                    away_team = teams[0].strip()
                    home_team = teams[-1].strip()

                    status = '예정'
                    away_score, home_score = '-', '-'
                    nums = re.findall(r'\d+', clean_text)
                    
                    if "취소" in play_text: status = '우천취소'
                    elif len(nums) >= 2: 
                        status = '종료'
                        away_score = nums[0]
                        home_score = nums[-1]

                    if status in ['예정', '우천취소']:
                        # 사진 데이터(마지막 컬럼)를 '-' 로 빈칸 처리
                        writer.writerow([current_date_str, away_team, home_team, '원정', status, away_score, home_score, '-', '-', '-', '-', '-', '-', '-'])
                        writer.writerow([current_date_str, home_team, away_team, '홈', status, home_score, away_score, '-', '-', '-', '-', '-', '-', '-'])
                        print(f"📅 {current_date_str} | {away_team} vs {home_team} [{status}] 스케줄 저장")
                        continue

                    date_id = current_date_str.replace('-', '')
                    away_c = team_codes.get(away_team)
                    home_c = team_codes.get(home_team)
                    is_saved = False 

                    if away_c and home_c:
                        game_id = f"{date_id}{away_c}{home_c}02026"
                        record_url = f"https://api-gw.sports.naver.com/schedule/games/{game_id}/record"
                        headers = {'User-Agent': 'Mozilla/5.0'}
                        
                        try:
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
                                            
                                            # 🔥 성우의 완벽한 아이디어! pcode 추출해서 바로 URL로 만들기
                                            pcode = p.get('pcode', '') 
                                            img_url = f"https://sports-phinf.pstatic.net/player/kbo/default/{pcode}.png" if pcode else "-"
                                            
                                            return name, inn, np, hit, sasa, er, img_url

                                        a_name, a_inn, a_np, a_hit, a_sasa, a_er, a_img = get_stats(pitchers['away'][0])
                                        h_name, h_inn, h_np, h_hit, h_sasa, h_er, h_img = get_stats(pitchers['home'][0])
                                        
                                        # 💡 완벽한 이미지 URL(a_img, h_img)을 함께 저장!
                                        writer.writerow([current_date_str, away_team, home_team, '원정', status, away_score, home_score, a_name, a_inn, a_np, a_hit, a_sasa, a_er, a_img])
                                        writer.writerow([current_date_str, home_team, away_team, '홈', status, home_score, away_score, h_name, h_inn, h_np, h_hit, h_sasa, h_er, h_img])
                                        
                                        print(f"📸 {current_date_str} | {a_name}({away_team}) & {h_name}({home_team}) 사진 URL 저장 완료!")
                                        is_saved = True
                        except requests.exceptions.RequestException:
                            pass 
                        
                    if not is_saved:
                        writer.writerow([current_date_str, away_team, home_team, '원정', status, away_score, home_score, '-', '-', '-', '-', '-', '-', '-'])
                        writer.writerow([current_date_str, home_team, away_team, '홈', status, home_score, away_score, '-', '-', '-', '-', '-', '-', '-'])

                    time.sleep(0.2)

    print("\n🎉 V7 데이터 수집 완료! CSV 파일을 확인해 보세요!")

master_collector_v7()
