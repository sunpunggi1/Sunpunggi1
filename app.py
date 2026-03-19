import streamlit as st
import pandas as pd
import plotly.express as px
import json
import gspread
import calendar

# 1. 페이지 설정
st.set_page_config(page_title="최현규의 열공 대시보드", layout="wide")
st.title("🚀 최현규의 데이터 기반 학습 시스템")

# --- 탭 상태 및 달력 파라미터 보존 로직 ---
today = pd.Timestamp.now().date()
if 'selected_date' not in st.session_state:
    st.session_state['selected_date'] = today

if 'cal_view_date' not in st.session_state:
    st.session_state['cal_view_date'] = pd.to_datetime(today).replace(day=1).date()

if 'cal_goal' not in st.session_state:
    st.session_state['cal_goal'] = 5.0
if 'cal_c1' not in st.session_state:
    st.session_state['cal_c1'] = "#D4EDDA"
if 'cal_c2' not in st.session_state:
    st.session_state['cal_c2'] = "#FFF3CD"
if 'cal_c3' not in st.session_state:
    st.session_state['cal_c3'] = "#F8D7DA"

if 'active_tab' not in st.session_state:
    st.session_state['active_tab'] = "📊 요약 및 추이"

# 달력 클릭 시 URL 파라미터 감지 및 상태 강제 업데이트
if "date" in st.query_params:
    clicked_date_str = st.query_params["date"]
    if st.session_state.get('last_processed_date') != clicked_date_str:
        try:
            clicked_date = pd.to_datetime(clicked_date_str).date()
            st.session_state['selected_date'] = clicked_date
            st.session_state['cal_view_date'] = pd.to_datetime(clicked_date).replace(day=1).date()
            st.session_state['active_tab'] = "🗓️ 학습 캘린더 및 관리" 
            
            if "goal" in st.query_params: st.session_state['cal_goal'] = float(st.query_params["goal"])
            if "c1" in st.query_params: st.session_state['cal_c1'] = f"#{st.query_params['c1']}"
            if "c2" in st.query_params: st.session_state['cal_c2'] = f"#{st.query_params['c2']}"
            if "c3" in st.query_params: st.session_state['cal_c3'] = f"#{st.query_params['c3']}"
            
            st.session_state['last_processed_date'] = clicked_date_str
        except:
            pass

# 2. 구글 시트 직접 연결
@st.cache_resource
def init_connection():
    sa_data = st.secrets["connections"]["gsheets"]["service_account"]
    sa_dict = json.loads(sa_data) if isinstance(sa_data, str) else sa_data
    return gspread.service_account_from_dict(sa_dict)

try:
    gc = init_connection()
    sh = gc.open_by_url(st.secrets["public_gsheets_url"])
    ws = sh.sheet1
except Exception as e:
    st.error(f"구글 시트 연결에 실패했습니다. Secrets 설정을 확인해주세요. 상세오류: {e}")
    st.stop()

def get_data():
    try:
        records = ws.get_all_records()
        if not records:
            return pd.DataFrame(columns=['날짜', '과목', '시간', '사유'])
        df = pd.DataFrame(records)
        if '시간' in df.columns:
            df['시간'] = pd.to_numeric(df['시간'])
        if '사유' not in df.columns:
            df['사유'] = ''
        df['사유'] = df['사유'].fillna('').astype(str)
        return df
    except gspread.exceptions.APIError:
        st.error("구글 시트 읽기 권한이 없습니다. 시트 공유 설정에서 서비스 계정을 추가해주세요.")
        st.stop()
    except Exception:
        return pd.DataFrame(columns=['날짜', '과목', '시간', '사유'])

def update_data(updated_df):
    try:
        ws.clear()
        save_df = updated_df.copy()
        # 저장 전 모든 날짜를 완벽한 문자열 포맷으로 고정하여 오염 방지
        save_df['날짜'] = pd.to_datetime(save_df['날짜']).dt.strftime('%Y-%m-%d')
        save_df['사유'] = save_df['사유'].astype(str)
        
        # 보조용으로 추가된 열이 있다면 제거하고 저장
        cols_to_drop = ['날짜_date', '요일']
        save_df = save_df.drop(columns=[c for c in cols_to_drop if c in save_df.columns])
        
        data = [save_df.columns.values.tolist()] + save_df.values.tolist()
        ws.update(range_name='A1', values=data)
    except gspread.exceptions.APIError as e:
        st.error(f"구글 시트 쓰기 권한이 없습니다. 서비스 계정 이메일이 시트의 '편집자'인지 확인하세요.")
        st.stop()
    except Exception as e:
        st.error(f"데이터 업데이트 중 오류 발생: {e}")
        st.stop()

# --- 핵심 수정: 데이터를 불러오자마자 전역으로 날짜 변환 및 정리 ---
df = get_data()

if not df.empty and '날짜' in df.columns:
    df['날짜'] = pd.to_datetime(df['날짜'].astype(str).str.strip(), errors='coerce')
    df = df.dropna(subset=['날짜']).copy()
    df['날짜_date'] = df['날짜'].dt.date
    
    days_map = {0:'월', 1:'화', 2:'수', 3:'목', 4:'금', 5:'토', 6:'일'}
    df['요일'] = df['날짜'].dt.dayofweek.map(days_map)
    day_order = ['월', '화', '수', '목', '금', '토', '일']
    df['요일'] = pd.Categorical(df['요일'], categories=day_order, ordered=True)
else:
    df = pd.DataFrame(columns=['날짜', '과목', '시간', '사유', '날짜_date', '요일'])

# 3. 사이드바: 데이터 입력 및 관리
with st.sidebar:
    st.header("🎯 주간 목표 설정")
    weekly_goal = st.number_input("이번 주 목표 공부 시간 (h)", min_value=1.0, value=40.0, step=1.0)
    st.divider()

    st.header("📝 학습 기록")
    with st.form("input_form", clear_on_submit=True):
        date_input = st.date_input("날짜", value=st.session_state['selected_date'])
        subject = st.selectbox("과목", ["국어", "수학", "영어", "사회문화", "지구과학I", "한국사"])
        time = st.number_input("시간 (h)", min_value=0.0, step=0.5, value=0.0)
        submit = st.form_submit_button("구글 시트에 저장")
        
        if submit:
            if time > 0:
                new_row = pd.DataFrame([{"날짜": pd.to_datetime(date_input), "과목": subject, "시간": time, "사유": ""}])
                updated_df = pd.concat([df, new_row], ignore_index=True)
                update_data(updated_df)
                st.success("기록 완료!")
                st.rerun()
            else:
                st.warning("0시간 이상 입력해주세요.")

    st.divider()
    st.header("🗑️ 최근 기록 삭제")
    if not df.empty:
        reversed_idx = list(reversed(df.index))
        def format_delete_item(x):
            row = df.loc[x]
            date_str = row['날짜'].strftime('%Y-%m-%d')
            if row['과목'] == '인정결석':
                return f"[{x}] {date_str} - 🚫 인정결석 ({row['사유']})"
            return f"[{x}] {date_str} - {row['과목']} ({row['시간']}h)"
            
        delete_idx = st.selectbox("빠른 삭제할 기록을 선택하세요 (최신순)", reversed_idx, format_func=format_delete_item)
        if st.button("선택한 기록 삭제", type="primary"):
            updated_df = df.drop(delete_idx).reset_index(drop=True)
            update_data(updated_df)
            st.warning("기록이 삭제되었습니다.")
            st.rerun()

# 4. 메인 통계 화면
if df.empty:
    st.info("데이터가 없습니다. 왼쪽 사이드바에서 첫 공부 기록을 시작해보세요!")
else:
    study_df = df[df['과목'] != '인정결석']
    absence_df = df[df['과목'] == '인정결석']

    active_dates = set(df[(df['시간'] > 0) | (df['과목'] == '인정결석')]['날짜_date'])
    active_dates_desc = sorted(list(active_dates), reverse=True)
    
    streak_count = 0
    total_rest_days = 0
    max_break = 0

    if active_dates_desc:
        if active_dates_desc[0] == today or active_dates_desc[0] == today - pd.Timedelta(days=1):
            streak_count = 1
            curr_d = active_dates_desc[0]
            for d in active_dates_desc[1:]:
                if d == curr_d - pd.Timedelta(days=1):
                    streak_count += 1
                    curr_d = d
                else:
                    break
        
        first_date = sorted(list(active_dates))[0]
        full_date_range = pd.date_range(start=first_date, end=today).date
        total_rest_days = len([d for d in full_date_range if d not in active_dates])
        
        current_break = 0
        for d in full_date_range:
            if d not in active_dates:
                current_break += 1
                if current_break > max_break:
                    max_break = current_break
            else:
                current_break = 0

    now_ts = pd.Timestamp.now().normalize()
    start_of_week = now_ts - pd.Timedelta(days=now_ts.dayofweek)
    this_week_df = study_df[study_df['날짜'] >= start_of_week]
    this_week_hours = this_week_df['시간'].sum()

    tabs = ["📊 요약 및 추이", "📅 요일별 집중 분석", "🗓️ 학습 캘린더 및 관리"]
    selected_tab = st.radio("메뉴 이동", tabs, horizontal=True, label_visibility="collapsed", key="active_tab")
    st.write("---")

    if selected_tab == "📊 요약 및 추이":
        st.subheader("📊 기간별 학습 요약 및 달성도")
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("총 공부 시간", f"{study_df['시간'].sum():.1f}h")
        c2.metric("🔥 연속 활동일", f"{streak_count}일")
        c3.metric("순수 학습일", f"{study_df[study_df['시간']>0]['날짜_date'].nunique()}일")
        c4.metric("총 쉰 날", f"{total_rest_days}일")
        c5.metric("최장 휴식기", f"{max_break}일")
        
        st.divider()

        st.write(f"**이번 주 목표 달성률 ({this_week_hours:.1f}h / {weekly_goal:.1f}h)**")
        progress_pct = min(this_week_hours / weekly_goal, 1.0)
        st.progress(progress_pct)
        if progress_pct >= 1.0:
            st.success("🎉 이번 주 목표 시간을 달성했습니다! 훌륭합니다!")
        else:
            st.caption(f"목표 달성까지 {weekly_goal - this_week_hours:.1f}시간 남았습니다. 화이팅!")
        
        st.divider()

        if not this_week_df.empty:
            top_subject = this_week_df.groupby('과목')['시간'].sum().idxmax()
            top_day = this_week_df.groupby('요일', observed=True)['시간'].sum().idxmax()
            st.info(f"📝 **최현규님의 주간 학습 리포트**\n\n이번 주 최애 과목은 **{top_subject}**이었고, 가장 열심히 공부한 요일은 **{top_day}요일**입니다. 훌륭한 페이스입니다!")
        
        st.divider()
        
        filter_opt = st.radio("조회 기간 선택", ["전체 기간", "최근 7일 (주간)", "최근 30일 (월간)"], horizontal=True)
        filtered_df = study_df.copy()
        
        if filter_opt == "최근 7일 (주간)":
            filtered_df = filtered_df[filtered_df['날짜'] >= (now_ts - pd.Timedelta(days=6))]
        elif filter_opt == "최근 30일 (월간)":
            filtered_df = filtered_df[filtered_df['날짜'] >= (now_ts - pd.Timedelta(days=29))]

        if filtered_df.empty:
            st.warning("선택한 기간에 기록된 학습 데이터가 없습니다.")
        else:
            col_chart1, col_chart2 = st.columns(2)
            with col_chart1:
                sub_sum = filtered_df.groupby('과목', as_index=False)['시간'].sum()
                fig_donut = px.pie(sub_sum, values='시간', names='과목', title=f"🎯 {filter_opt} 과목별 학습 밸런스", hole=0.4)
                st.plotly_chart(fig_donut, use_container_width=True)

            with col_chart2:
                daily_sum = filtered_df.groupby('날짜', as_index=False)['시간'].sum().sort_values('날짜')
                daily_sum['누적시간'] = daily_sum['시간'].cumsum()
                fig_cum = px.area(daily_sum, x='날짜', y='누적시간', title=f"📈 {filter_opt} 누적 학습 성취도", markers=True)
                fig_cum.update_traces(line_color='#2ca02c', fillcolor='rgba(44, 160, 44, 0.2)')
                st.plotly_chart(fig_cum, use_container_width=True)
            
            fig_daily = px.bar(daily_sum, x='날짜', y='시간', title=f"📅 {filter_opt} 일자별 공부 시간", text_auto=True)
            st.plotly_chart(fig_daily, use_container_width=True)

    elif selected_tab == "📅 요일별 집중 분석":
        st.subheader("요일별 학습 패턴 및 인사이트")
        avg_method = st.radio("📊 평균 계산 기준", ["공부한 날만 포함", "쉬었던 날 포함(인정결석 제외)", "쉬었던 날(0시간) 포함"], horizontal=True)
        
        col_left, col_right = st.columns(2)
        daily_sum_df = study_df.groupby(['날짜_date', '요일'], observed=True)['시간'].sum().reset_index()
        
        if avg_method == "공부한 날만 포함":
            week_avg = daily_sum_df[daily_sum_df['시간'] > 0].groupby('요일', observed=True)['시간'].mean().reset_index()
        else:
            if active_dates_desc:
                first_d = sorted(list(active_dates))[0]
                full_dates = pd.date_range(start=first_d, end=today)
                full_df = pd.DataFrame({'날짜_date': full_dates.date})
                full_df['요일'] = full_dates.dayofweek.map({0:'월', 1:'화', 2:'수', 3:'목', 4:'금', 5:'토', 6:'일'})
                full_df['요일'] = pd.Categorical(full_df['요일'], categories=['월', '화', '수', '목', '금', '토', '일'], ordered=True)
                
                absence_date_list = absence_df['날짜_date'].unique()
                if avg_method == "쉬었던 날 포함(인정결석 제외)":
                    full_df = full_df[~full_df['날짜_date'].isin(absence_date_list)]
                
                merged_df = pd.merge(full_df, daily_sum_df[['날짜_date', '시간']], on='날짜_date', how='left').fillna({'시간': 0})
                week_avg = merged_df.groupby('요일', observed=True)['시간'].mean().reset_index()
            else:
                week_avg = pd.DataFrame({'요일': ['월', '화', '수', '목', '금', '토', '일'], '시간': [0]*7})
        
        with col_left:
            fig_week = px.bar(week_avg, x='요일', y='시간', color='요일', title="요일별 평균 공부 시간")
            st.plotly_chart(fig_week, use_container_width=True)
            
        with col_right:
            if not week_avg.empty and week_avg['시간'].sum() > 0:
                max_day = week_avg.loc[week_avg['시간'].idxmax(), '요일']
                min_day = week_avg.loc[week_avg['시간'].idxmin(), '요일']
                st.success(f"🔥 **{max_day}요일**에 가장 집중력이 좋으시군요! 이 페이스를 유지하세요.")
                st.warning(f"💡 데이터 객관화: **{min_day}요일**에는 유독 학습 시간이 짧아지는 패턴이 있습니다.")
            
            st.divider()
            sel_day = st.radio("분석할 요일", ['월', '화', '수', '목', '금', '토', '일'], horizontal=True)
            day_df = study_df[study_df['요일'] == sel_day]
            if not day_df.empty:
                fig_pie = px.pie(day_df, values='시간', names='과목', title=f"{sel_day}요일 과목 비중", hole=.4)
                st.plotly_chart(fig_pie, use_container_width=True)
            else:
                st.write(f"{sel_day}요일에 학습한 데이터가 아직 없습니다.")

    elif selected_tab == "🗓️ 학습 캘린더 및 관리":
        st.subheader("🗓️ 학습 캘린더 및 상세 관리")
        
        with st.expander("🎨 캘린더 색상 및 목표 기준 설정"):
            n_hours = st.number_input("목표 달성 기준 시간 (n시간)", min_value=0.1, value=st.session_state['cal_goal'], step=0.5)
            st.session_state['cal_goal'] = n_hours
            
            cc1, cc2, cc3 = st.columns(3)
            with cc1:
                color1 = st.color_picker(f"목표 달성 ({n_hours}h 이상)", st.session_state['cal_c1'])
                st.session_state['cal_c1'] = color1
            with cc2:
                color2 = st.color_picker(f"부분 달성 ({n_hours}h 미만)", st.session_state['cal_c2'])
                st.session_state['cal_c2'] = color2
            with cc3:
                color3 = st.color_picker("공부 안 한 날 (0h)", st.session_state['cal_c3'])
                st.session_state['cal_c3'] = color3

        curr_view_dt = pd.to_datetime(st.session_state['cal_view_date'])
        
        col_btn_l, col_text, col_btn_r = st.columns([1, 4, 1])
        with col_btn_l:
            if st.button("◀ 이전 달", use_container_width=True):
                st.session_state['cal_view_date'] = (curr_view_dt - pd.DateOffset(months=1)).date()
                st.rerun()
        with col_text:
            st.markdown(f"<h3 style='text-align: center; margin-top: 0;'>{st.session_state['cal_view_date'].year}년 {st.session_state['cal_view_date'].month}월</h3>", unsafe_allow_html=True)
        with col_btn_r:
            if st.button("다음 달 ▶", use_container_width=True):
                st.session_state['cal_view_date'] = (curr_view_dt + pd.DateOffset(months=1)).date()
                st.rerun()

        cal_year = st.session_state['cal_view_date'].year
        cal_month = st.session_state['cal_view_date'].month

        # --- 핵심 수정: 한 주의 시작을 일요일(6)로 변경 ---
        cal = calendar.Calendar(firstweekday=6)
        month_days = cal.monthdatescalendar(cal_year, cal_month)
        
        daily_stats = {}
        for week in month_days:
            for d in week:
                if d.month == cal_month:
                    target_df = df[df['날짜_date'] == d]
                    abs_data = target_df[target_df['과목'] == '인정결석']
                    is_absence = not abs_data.empty
                    reason = abs_data.iloc[0]['사유'] if is_absence else ""
                    total_h = target_df[target_df['과목'] != '인정결석']['시간'].sum()
                    daily_stats[d] = {'hours': total_h, 'is_absence': is_absence, 'reason': reason}

        html = "<style>"
        html += ".cal-container { display: grid; grid-template-columns: repeat(7, 1fr); gap: 8px; margin-bottom: 20px; }"
        html += ".cal-header { text-align: center; font-weight: bold; color: #555; padding: 5px 0; }"
        html += ".cal-cell { min-height: 80px; padding: 8px; border-radius: 8px; border: 1px solid #ddd; display: flex; flex-direction: column; justify-content: space-between; color: #333; box-shadow: 1px 1px 3px rgba(0,0,0,0.05); transition: all 0.2s ease; }"
        html += ".cal-cell:hover { transform: translateY(-3px); box-shadow: 2px 4px 8px rgba(0,0,0,0.15); border-color: #999; cursor: pointer; }"
        html += ".cal-day-num { font-weight: bold; font-size: 1.1em; margin-bottom: 5px; }"
        html += ".cal-hours { font-size: 0.95em; align-self: flex-end; font-weight: bold; }"
        html += ".cal-reason { font-size: 0.85em; color: #dc3545; font-weight: bold; line-height: 1.2; margin-top: 5px; }"
        html += ".cal-empty { background-color: transparent; border: none; box-shadow: none; }"
        html += "</style><div class='cal-container'>"
        
        # 헤더 순서 일요일부터 시작하도록 변경
        for day_name in ["일", "월", "화", "수", "목", "금", "토"]:
            # 일요일, 토요일 색상 구별 추가
            color_style = "color: #dc3545;" if day_name == "일" else ("color: #007bff;" if day_name == "토" else "")
            html += f"<div class='cal-header' style='{color_style}'>{day_name}</div>"

        first_d = sorted(list(active_dates))[0] if active_dates else today
        
        q_goal = st.session_state['cal_goal']
        q_c1 = st.session_state['cal_c1'].replace('#', '')
        q_c2 = st.session_state['cal_c2'].replace('#', '')
        q_c3 = st.session_state['cal_c3'].replace('#', '')

        for week in month_days:
            for d in week:
                if d.month != cal_month:
                    html += "<div class='cal-empty'></div>"
                else:
                    stats = daily_stats[d]
                    h = stats['hours']
                    is_abs = stats['is_absence']
                    reason = stats['reason']

                    stripe_css = ""
                    if d > today or d < first_d:
                        bg_color = "#FFFFFF"
                        opacity = "0.6"
                        text = ""
                    elif is_abs:
                        # 인정결석 시각화 개선: 더 어둡게, 빗금 촘촘하게, 텍스트 눈에 띄게
                        bg_color = "#e9ecef"
                        opacity = "0.85"
                        stripe_css = "background-image: repeating-linear-gradient(45deg, transparent, transparent 10px, rgba(0,0,0,0.08) 10px, rgba(0,0,0,0.08) 20px);"
                        text = f"<span class='cal-reason'>🚫 인정결석<br><span style='font-weight: normal; color: #555;'>{reason}</span></span>"
                    else:
                        opacity = "1"
                        if h >= n_hours:
                            bg_color = color1
                        elif h > 0:
                            bg_color = color2
                        else:
                            bg_color = color3
                        text = f"<span class='cal-hours'>{h:.1f} h</span>"

                    href = f"?date={d}&goal={q_goal}&c1={q_c1}&c2={q_c2}&c3={q_c3}"
                    html += f"<a href='{href}' target='_self' style='text-decoration: none; color: inherit;'>"
                    html += f"<div class='cal-cell' style='background-color: {bg_color}; opacity: {opacity}; {stripe_css}'>"
                    html += f"<span class='cal-day-num'>{d.day}</span>{text}"
                    html += "</div></a>"
                    
        html += "</div>"
        st.markdown(html, unsafe_allow_html=True)

        st.divider()
        st.subheader("🛠️ 특정 날짜 상세 관리 및 결석 처리")
        
        selected_date = st.date_input(
            "조회 및 관리할 날짜 (위의 달력 칸을 클릭하면 바로 이동합니다)", 
            value=st.session_state['selected_date']
        )
        st.session_state['selected_date'] = selected_date
        
        target_df = df[df['날짜_date'] == selected_date]
        
        if target_df.empty:
            st.info(f"{selected_date}에 기록된 공부 데이터가 없습니다.")
        else:
            st.write(f"**{selected_date} 기록 목록**")
            st.dataframe(target_df[['과목', '시간', '사유']], use_container_width=True)
            
            target_idx_list = list(reversed(target_df.index))
            def format_edit_item(x):
                r = df.loc[x]
                return f"🚫 인정결석 ({r['사유']})" if r['과목'] == '인정결석' else f"{r['과목']} ({r['시간']}h)"
                
            target_idx = st.selectbox(
                "수정 또는 삭제할 기록을 선택하세요 (최신순)", 
                target_idx_list, 
                format_func=format_edit_item
            )
            
            if target_idx is not None:
                is_selected_abs = (df.loc[target_idx, '과목'] == '인정결석')
                
                if not is_selected_abs:
                    new_time = st.number_input("새로운 공부 시간 (h)", min_value=0.0, step=0.5, value=float(df.loc[target_idx, '시간']))
                else:
                    new_reason = st.text_input("새로운 사유", value=df.loc[target_idx, '사유'])
                
                col_btn1, col_btn2 = st.columns(2)
                
                with col_btn1:
                    if st.button("⏳ 수정 저장", use_container_width=True):
                        updated_df = df.copy()
                        if not is_selected_abs:
                            if new_time > 0:
                                updated_df.loc[target_idx, '시간'] = new_time
                            else:
                                st.warning("0보다 큰 시간을 입력하세요.")
                                st.stop()
                        else:
                            updated_df.loc[target_idx, '사유'] = new_reason
                            
                        update_data(updated_df)
                        st.success("성공적으로 수정되었습니다.")
                        st.rerun()
                
                with col_btn2:
                    if st.button("🗑️ 이 기록 완전히 삭제", use_container_width=True, type="primary"):
                        updated_df = df.drop(target_idx).reset_index(drop=True)
                        update_data(updated_df)
                        st.warning("기록이 삭제되었습니다.")
                        st.rerun()

        st.write("---")
        st.write(f"**📌 {selected_date} 인정결석 등록**")
        with st.form("absence_form", clear_on_submit=True):
            absence_reason = st.text_input("결석 사유를 입력하세요 (예: 심한 감기몸살, 가족 행사)")
            submit_abs = st.form_submit_button("인정결석 처리하기")
            
            if submit_abs:
                if absence_reason.strip() == "":
                    st.warning("사유를 반드시 입력해주세요.")
                else:
                    new_abs_row = pd.DataFrame([{"날짜": pd.to_datetime(selected_date), "과목": "인정결석", "시간": 0.0, "사유": absence_reason}])
                    updated_df = pd.concat([df, new_abs_row], ignore_index=True)
                    update_data(updated_df)
                    st.success(f"{selected_date}이(가) 인정결석으로 처리되었습니다.")
                    st.rerun()

    with st.expander("📄 전체 데이터 테이블 확인"):
        # 불필요한 보조 열 숨기고 출력
        display_df = df.drop(columns=['날짜_date', '요일'], errors='ignore')
        st.write(display_df.sort_values('날짜', ascending=False))
