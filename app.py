import streamlit as st
import pandas as pd
import plotly.express as px
import json
import gspread
import calendar
try:
    import holidays
    HAS_HOLIDAYS = True
except ImportError:
    HAS_HOLIDAYS = False

# 1. 페이지 설정
st.set_page_config(page_title="최현규의 열공 대시보드", layout="wide")
st.title("🚀 최현규의 데이터 기반 학습 시스템")

# 2. 구글 시트 직접 연결 (연결 및 시트 객체 자체를 캐싱하여 불필요한 통신 방지)
@st.cache_resource
def init_connection():
    sa_data = st.secrets["connections"]["gsheets"]["service_account"]
    sa_dict = json.loads(sa_data) if isinstance(sa_data, str) else sa_data
    gc = gspread.service_account_from_dict(sa_dict)
    sh = gc.open_by_url(st.secrets["public_gsheets_url"])
    return sh.sheet1

try:
    ws = init_connection()
except Exception as e:
    st.error(f"구글 시트 연결에 실패했습니다. Secrets 설정을 확인해주세요. 상세오류: {e}")
    st.stop()

# --- 데이터 로드 (캐싱을 통해 1분당 API 60회 제한 에러 완벽 방지) ---
@st.cache_data(ttl=600)
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

# --- 신규: 최적화된 CRUD 함수 분리 및 캐시 초기화 처리 ---
def _format_row(row_dict):
    date_val = row_dict.get('날짜', '')
    if hasattr(date_val, 'strftime'): date_val = date_val.strftime('%Y-%m-%d')
    else: date_val = str(date_val)
    return [
        date_val,
        str(row_dict.get('과목', '')),
        float(row_dict.get('시간', 0.0)),
        str(row_dict.get('사유', ''))
    ]

def append_data(row_dict):
    """새로운 행을 시트 맨 아래에 추가합니다."""
    try:
        row_values = _format_row(row_dict)
        ws.append_row(row_values)
        get_data.clear() # 추가 완료 시 데이터 캐시 초기화
    except Exception as e:
        st.error(f"데이터 추가 중 오류 발생: {e}")
        st.stop()

def edit_data(df_index, row_dict):
    """DataFrame 인덱스를 통해 시트의 특정 행 번호를 찾아 업데이트합니다."""
    try:
        sheet_row = df_index + 2 # 구글 시트는 1행이 헤더이므로 인덱스값에 +2를 해야 실제 행이 됨
        row_values = [_format_row(row_dict)]
        ws.update(range_name=f'A{sheet_row}:D{sheet_row}', values=row_values)
        get_data.clear() # 수정 완료 시 데이터 캐시 초기화
    except Exception as e:
        st.error(f"데이터 수정 중 오류 발생: {e}")
        st.stop()

def delete_data(df_index):
    """DataFrame 인덱스를 통해 시트의 특정 행 번호를 찾아 삭제합니다."""
    try:
        sheet_row = df_index + 2
        ws.delete_rows(sheet_row)
        get_data.clear() # 삭제 완료 시 데이터 캐시 초기화
    except Exception as e:
        st.error(f"데이터 삭제 중 오류 발생: {e}")
        st.stop()

def update_data(updated_df):
    """전체 덮어쓰기 로직 (설정 탭 등에서 필요 시 사용)"""
    try:
        ws.clear()
        save_df = updated_df.copy()
        save_df['날짜'] = pd.to_datetime(save_df['날짜']).dt.strftime('%Y-%m-%d')
        save_df['사유'] = save_df['사유'].astype(str)
        cols_to_drop = ['날짜_date', '요일']
        save_df = save_df.drop(columns=[c for c in cols_to_drop if c in save_df.columns])
        
        data = [save_df.columns.values.tolist()] + save_df.values.tolist()
        ws.update(range_name='A1', values=data)
        get_data.clear() # 덮어쓰기 완료 시 데이터 캐시 초기화
    except Exception as e:
        st.error(f"데이터 업데이트 중 오류 발생: {e}")
        st.stop()

# 데이터 로드 및 전처리 (캐시된 함수 호출)
df = get_data()

# --- 설정 데이터(물리적 저장) 불러오기 ---
default_settings = {
    'cal_goal': 3.0, 'cal_c1': "#D4EDDA", 'cal_c2': "#FFF3CD", 'cal_c3': "#FFFFFF",
    'subj_colors': {
        "국어": "#ef553b", "수학": "#636efa", "영어": "#00cc96", 
        "사회문화": "#ab63fa", "지구과학I": "#ffa15a", "한국사": "#19d3f3"
    }
}

if not df.empty and '과목' in df.columns:
    settings_rows = df[df['과목'] == '설정']
    if not settings_rows.empty:
        try:
            loaded_settings = json.loads(settings_rows.iloc[-1]['사유'])
            default_settings.update(loaded_settings)
        except: pass

# 세션 스테이트 초기화 (설정값 적용)
today = pd.Timestamp.now().date()
if 'selected_date' not in st.session_state: st.session_state['selected_date'] = today
if 'cal_view_date' not in st.session_state: st.session_state['cal_view_date'] = pd.to_datetime(today).replace(day=1).date()
if 'active_tab' not in st.session_state: st.session_state['active_tab'] = "📊 요약 및 추이"

for k, v in default_settings.items():
    if k not in st.session_state:
        st.session_state[k] = v

if "date" in st.query_params:
    clicked_date_str = st.query_params["date"]
    if st.session_state.get('last_processed_date') != clicked_date_str:
        try:
            clicked_date = pd.to_datetime(clicked_date_str).date()
            st.session_state['selected_date'] = clicked_date
            st.session_state['cal_view_date'] = pd.to_datetime(clicked_date).replace(day=1).date()
            st.session_state['active_tab'] = "🗓️ 학습 캘린더 및 관리" 
            st.session_state['last_processed_date'] = clicked_date_str
        except: pass

# 데이터 정리 (원본 인덱스 유지를 위해 필터링 전에 날짜형 변환)
if not df.empty and '날짜' in df.columns:
    df['날짜'] = pd.to_datetime(df['날짜'].astype(str).str.strip(), errors='coerce')
    # copy()는 기존 인덱스를 유지함 (sheet_row 매칭에 필수)
    df = df.dropna(subset=['날짜']).copy() 
    df['날짜_date'] = df['날짜'].dt.date
    
    days_map = {0:'월', 1:'화', 2:'수', 3:'목', 4:'금', 5:'토', 6:'일'}
    df['요일'] = df['날짜'].dt.dayofweek.map(days_map)
    day_order = ['월', '화', '수', '목', '금', '토', '일']
    df['요일'] = pd.Categorical(df['요일'], categories=day_order, ordered=True)
else:
    df = pd.DataFrame(columns=['날짜', '과목', '시간', '사유', '날짜_date', '요일'])

# 무지개색 매핑
rainbow_colors = {'월': '#FF4B4B', '화': '#FF9F36', '수': '#FFD025', '목': '#00C250', '금': '#00A3FF', '토': '#4B0082', '일': '#8A2BE2'}

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
                append_data({"날짜": date_input, "과목": subject, "시간": time, "사유": ""})
                st.success("기록 완료!")
                st.rerun()
            else:
                st.warning("0시간 이상 입력해주세요.")

    st.divider()
    st.header("🗑️ 최근 기록 삭제")
    if not df.empty:
        del_df = df[df['과목'] != '설정']
        reversed_idx = list(reversed(del_df.index))
        def format_delete_item(x):
            row = df.loc[x]
            date_str = row['날짜'].strftime('%Y-%m-%d')
            if row['과목'] == '인정결석': return f"[{x}] {date_str} - 🚫 인정결석 ({row['사유']})"
            elif row['과목'] == '메모': return f"[{x}] {date_str} - 📝 메모 ({row['사유']})"
            return f"[{x}] {date_str} - {row['과목']} ({row['시간']}h)"
            
        delete_idx = st.selectbox("빠른 삭제할 기록을 선택하세요 (최신순)", reversed_idx, format_func=format_delete_item)
        if st.button("선택한 기록 삭제", type="primary"):
            delete_data(delete_idx)
            st.warning("기록이 삭제되었습니다.")
            st.rerun()

# 4. 메인 화면
if df.empty:
    st.info("데이터가 없습니다. 왼쪽 사이드바에서 첫 공부 기록을 시작해보세요!")
else:
    # 데이터 분류
    study_df = df[(df['과목'] != '인정결석') & (df['과목'] != '메모') & (df['과목'] != '설정')]
    absence_df = df[df['과목'] == '인정결석']

    active_dates_A = set(df[((df['시간'] > 0) | (df['과목'] == '인정결석')) & (df['과목'] != '설정')]['날짜_date'])
    active_dates_B = set(df[(df['시간'] > 0) & (df['과목'] != '설정') & (df['과목'] != '인정결석') & (df['과목'] != '메모')]['날짜_date'])
    
    def calc_longest_break(active_set):
        if not active_set: return 0, None, None
        first_d = sorted(list(active_set))[0]
        full_range = pd.date_range(start=first_d, end=today).date
        mb, cb = 0, 0
        cs, ms, me = None, None, None
        for d in full_range:
            if d not in active_set:
                if cb == 0: cs = d
                cb += 1
                if cb > mb:
                    mb = cb
                    ms = cs
                    me = d
            else:
                cb = 0
        return mb, ms, me

    max_break_A, start_A, end_A = calc_longest_break(active_dates_A)
    max_break_B, start_B, end_B = calc_longest_break(active_dates_B)

    streak_count = 0
    total_rest_days = 0
    total_rest_days_B = 0
    if active_dates_A:
        active_dates_desc = sorted(list(active_dates_A), reverse=True)
        if active_dates_desc[0] == today or active_dates_desc[0] == today - pd.Timedelta(days=1):
            streak_count = 1
            curr_d = active_dates_desc[0]
            for d in active_dates_desc[1:]:
                if d == curr_d - pd.Timedelta(days=1):
                    streak_count += 1
                    curr_d = d
                else: break
        
        first_date = sorted(list(active_dates_A))[0]
        full_date_range = pd.date_range(start=first_date, end=today).date
        total_rest_days = len([d for d in full_date_range if d not in active_dates_A])
        total_rest_days_B = len([d for d in full_date_range if d not in active_dates_B])

    now_ts = pd.Timestamp.now().normalize()
    start_of_week = now_ts - pd.Timedelta(days=now_ts.dayofweek)
    this_week_df = study_df[study_df['날짜'] >= start_of_week]
    this_week_hours = this_week_df['시간'].sum()

    tabs = ["📊 요약 및 추이", "📅 요일별 집중 분석", "🗓️ 학습 캘린더 및 관리", "⚙️ 설정"]
    selected_tab = st.radio("메뉴 이동", tabs, horizontal=True, label_visibility="collapsed", key="active_tab")
    st.write("---")

    if selected_tab == "📊 요약 및 추이":
        st.subheader("📊 기간별 학습 요약 및 달성도")
        
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("총 공부 시간", f"{study_df['시간'].sum():.1f}h")
        c2.metric("🔥 연속 활동일", f"{streak_count}일")
        c3.metric("순수 학습일", f"{study_df[study_df['시간']>0]['날짜_date'].nunique()}일")
        c4.metric("총 쉰 날 (공식)", f"{total_rest_days}일")
        c5.metric("총 쉰 날 (인정결석 포함)", f"{total_rest_days_B}일")

        c6, c7, c8 = st.columns(3)
        c6.metric("최장 휴식기 (공식)", f"{max_break_A}일")
        if max_break_A > 0: c6.caption(f"기간: {start_A.strftime('%y.%m.%d.')} - {end_A.strftime('%y.%m.%d.')}")
        else: c6.caption("꾸준히 기록 중입니다!")

        c7.metric("최장 휴식기 (인정결석 포함)", f"{max_break_B}일")
        if max_break_B > 0: c7.caption(f"기간: {start_B.strftime('%y.%m.%d.')} - {end_B.strftime('%y.%m.%d.')}")
        else: c7.caption("꾸준히 기록 중입니다!")
        
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
        
        if filter_opt == "최근 7일 (주간)": filtered_df = filtered_df[filtered_df['날짜'] >= (now_ts - pd.Timedelta(days=6))]
        elif filter_opt == "최근 30일 (월간)": filtered_df = filtered_df[filtered_df['날짜'] >= (now_ts - pd.Timedelta(days=29))]

        if filtered_df.empty:
            st.warning("선택한 기간에 기록된 학습 데이터가 없습니다.")
        else:
            col_chart1, col_chart2 = st.columns(2)
            with col_chart1:
                sub_sum = filtered_df.groupby('과목', as_index=False)['시간'].sum()
                fig_donut = px.pie(sub_sum, values='시간', names='과목', title=f"🎯 {filter_opt} 과목별 학습 밸런스", hole=0.4, color='과목', color_discrete_map=st.session_state['subj_colors'])
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
        col_title, col_check = st.columns([3, 1])
        with col_title:
            st.subheader("요일별 학습 패턴 및 인사이트")
        with col_check:
            exclude_red_days = st.checkbox("🎈 빨간 날(공휴일/일요일) 제외", value=False)
            exclude_saturdays = st.checkbox("🌊 토요일 제외", value=False)
            
        avg_method = st.radio("📊 평균 계산 기준", ["공부한 날만 포함", "쉬었던 날 포함(인정결석 제외)", "전체 날짜 포함 (모든 휴일/결석/기록 없는 날 포함)"], horizontal=True)
        
        target_study_df = study_df.copy()
        target_dates_desc = active_dates_desc.copy()
        
        cal_year = today.year
        kr_holidays = holidays.KR(years=range(cal_year-2, cal_year+2)) if HAS_HOLIDAYS else {}

        def is_excluded(d):
            if exclude_red_days and (d.weekday() == 6 or (HAS_HOLIDAYS and d in kr_holidays)): return True
            if exclude_saturdays and d.weekday() == 5: return True
            return False

        if exclude_red_days or exclude_saturdays:
            target_study_df = target_study_df[~target_study_df['날짜_date'].apply(is_excluded)]
        
        # 총 시간 및 기준 일수 계산 로직
        total_time = target_study_df['시간'].sum()
        total_days = 0
        
        daily_sum_df = target_study_df.groupby(['날짜_date', '요일'], observed=True)['시간'].sum().reset_index()
        
        if avg_method == "공부한 날만 포함":
            week_avg = daily_sum_df[daily_sum_df['시간'] > 0].groupby('요일', observed=True)['시간'].mean().reset_index()
            total_days = len(daily_sum_df[daily_sum_df['시간'] > 0]['날짜_date'].unique())
        else:
            if target_dates_desc:
                first_d = sorted(list(target_dates_desc))[0]
                full_dates = pd.date_range(start=first_d, end=today)
                full_df = pd.DataFrame({'날짜_date': full_dates.date})
                
                if exclude_red_days or exclude_saturdays:
                    full_df = full_df[~full_df['날짜_date'].apply(is_excluded)]
                
                full_df['요일'] = full_df['날짜_date'].apply(lambda d: {0:'월', 1:'화', 2:'수', 3:'목', 4:'금', 5:'토', 6:'일'}[d.weekday()])
                full_df['요일'] = pd.Categorical(full_df['요일'], categories=['월', '화', '수', '목', '금', '토', '일'], ordered=True)
                
                absence_date_list = absence_df['날짜_date'].unique()
                if avg_method == "쉬었던 날 포함(인정결석 제외)":
                    full_df = full_df[~full_df['날짜_date'].isin(absence_date_list)]
                
                total_days = len(full_df['날짜_date'].unique())
                
                merged_df = pd.merge(full_df, daily_sum_df[['날짜_date', '시간']], on='날짜_date', how='left').fillna({'시간': 0})
                week_avg = merged_df.groupby('요일', observed=True)['시간'].mean().reset_index()
            else:
                week_avg = pd.DataFrame({'요일': ['월', '화', '수', '목', '금', '토', '일'], '시간': [0]*7})
                total_days = 0
        
        overall_avg = (total_time / total_days) if total_days > 0 else 0.0
        
        st.metric("💡 해당 조건 일 평균 순공시간", f"{overall_avg:.1f}h", delta=f"총 {total_time:.1f}h / {total_days}일 기준", delta_color="off")
        st.write("---")

        col_left, col_right = st.columns(2)

        with col_left:
            fig_week = px.bar(week_avg, x='요일', y='시간', color='요일', title="요일별 평균 공부 시간", color_discrete_map=rainbow_colors)
            st.plotly_chart(fig_week, use_container_width=True)
            
        with col_right:
            if not week_avg.empty and week_avg['시간'].sum() > 0:
                max_day = week_avg.loc[week_avg['시간'].idxmax(), '요일']
                min_day = week_avg.loc[week_avg['시간'].idxmin(), '요일']
                st.success(f"🔥 **{max_day}요일**에 가장 집중력이 좋으시군요! 이 페이스를 유지하세요.")
                st.warning(f"💡 데이터 객관화: **{min_day}요일**에는 유독 학습 시간이 짧아지는 패턴이 있습니다.")
            
            st.divider()
            
            day_options = ['월', '화', '수', '목', '금', '토', '일']
            if exclude_saturdays: day_options.remove('토')
            if exclude_red_days: day_options.remove('일')
            
            if day_options:
                sel_day = st.radio("분석할 요일", day_options, horizontal=True)
                day_df = target_study_df[target_study_df['요일'] == sel_day]
                if not day_df.empty:
                    fig_pie = px.pie(day_df, values='시간', names='과목', title=f"{sel_day}요일 과목 비중", hole=.4, color='과목', color_discrete_map=st.session_state['subj_colors'])
                    st.plotly_chart(fig_pie, use_container_width=True)
                else:
                    st.write(f"{sel_day}요일에 학습한 데이터가 아직 없습니다.")
            else:
                st.write("선택할 수 있는 요일이 없습니다.")

    elif selected_tab == "🗓️ 학습 캘린더 및 관리":
        st.subheader("🗓️ 학습 캘린더 및 상세 관리")

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

        cal = calendar.Calendar(firstweekday=6)
        month_days = cal.monthdatescalendar(cal_year, cal_month)
        
        if HAS_HOLIDAYS: kr_holidays = holidays.KR(years=[cal_year])
        else: kr_holidays = {}
        
        daily_stats = {}
        for week in month_days:
            for d in week:
                if d.month == cal_month:
                    target_df = df[df['날짜_date'] == d]
                    abs_data = target_df[target_df['과목'] == '인정결석']
                    is_absence = not abs_data.empty
                    reason = abs_data.iloc[0]['사유'] if is_absence else ""
                    
                    memo_data = target_df[target_df['과목'] == '메모']
                    memo_text = ", ".join(memo_data['사유'].tolist()) if not memo_data.empty else ""
                    
                    total_h = target_df[(target_df['과목'] != '인정결석') & (target_df['과목'] != '메모') & (target_df['과목'] != '설정')]['시간'].sum()
                    daily_stats[d] = {'hours': total_h, 'is_absence': is_absence, 'reason': reason, 'memo': memo_text}

        html = "<style>"
        html += ".cal-container { display: grid; grid-template-columns: repeat(7, 1fr); gap: 8px; margin-bottom: 20px; }"
        html += ".cal-header { text-align: center; font-weight: bold; color: #555; padding: 5px 0; }"
        
        # 기본 PC 화면에서의 캘린더 셀 CSS
        html += ".cal-cell { height: 110px; padding: 6px; border-radius: 8px; border: 1px solid #ddd; display: flex; flex-direction: column; justify-content: space-between; color: #333; box-shadow: 1px 1px 3px rgba(0,0,0,0.05); transition: all 0.2s ease; overflow: hidden; }"
        html += ".cal-cell:hover { transform: translateY(-3px); box-shadow: 2px 4px 8px rgba(0,0,0,0.15); border-color: #999; cursor: pointer; }"
        html += ".cal-top { display: flex; flex-direction: column; align-items: flex-start; line-height: 1.1; }"
        html += ".cal-bottom { display: flex; flex-direction: column; align-items: flex-end; width: 100%; }"
        html += ".cal-day-num { font-weight: bold; font-size: 1.1em; margin-bottom: 2px; }"
        html += ".cal-holiday { font-size: 0.7em; color: #dc3545; font-weight: bold; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 100%; }"
        html += ".cal-memo { font-size: 0.75em; color: #495057; background: rgba(255,255,255,0.6); padding: 1px 4px; border-radius: 4px; border: 1px solid #dee2e6; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 100%; align-self: flex-start; margin-bottom: 2px; }"
        html += ".cal-hours { font-size: 0.95em; font-weight: bold; }"
        html += ".cal-reason { font-size: 0.8em; color: #dc3545; font-weight: bold; line-height: 1.2; text-align: right; width: 100%; }"
        html += ".cal-reason-text { font-weight: normal; color: #555; font-size: 0.9em; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; display: block; }"
        html += ".cal-empty { background-color: transparent; border: none; box-shadow: none; }"
        
        # 모바일 화면을 위한 미디어 쿼리 추가 (화면 너비 768px 이하일 때 적용)
        html += "@media (max-width: 768px) {"
        html += ".cal-container { gap: 4px; }"
        html += ".cal-cell { height: auto; aspect-ratio: 1 / 1.15; padding: 4px; }"
        html += ".cal-day-num { font-size: 0.85em; margin-bottom: 1px; }"
        html += ".cal-hours { font-size: 0.75em; }"
        html += ".cal-holiday { font-size: 0.6em; }"
        html += ".cal-memo { font-size: 0.6em; padding: 1px; margin-bottom: 1px; }"
        html += ".cal-reason { font-size: 0.7em; }"
        html += ".cal-reason-text { display: none; }" # 모바일에서는 사유 텍스트 숨김 처리하여 공간 확보
        html += "}"
        html += "</style><div class='cal-container'>"
        
        for day_name in ["일", "월", "화", "수", "목", "금", "토"]:
            color_style = "color: #dc3545;" if day_name == "일" else ("color: #007bff;" if day_name == "토" else "")
            html += f"<div class='cal-header' style='{color_style}'>{day_name}</div>"

        first_d = sorted(list(active_dates_A))[0] if active_dates_A else today
        
        n_hours = st.session_state['cal_goal']
        color1 = st.session_state['cal_c1']
        color2 = st.session_state['cal_c2']
        color3 = st.session_state['cal_c3']

        for week in month_days:
            for d in week:
                if d.month != cal_month:
                    html += "<div class='cal-empty'></div>"
                else:
                    stats = daily_stats[d]
                    h = stats['hours']
                    is_abs = stats['is_absence']
                    reason = stats['reason']
                    memo = stats['memo']

                    stripe_css = ""
                    if d > today or d < first_d:
                        bg_color = "#FFFFFF"
                        opacity = "0.6"
                        bottom_content = ""
                    elif is_abs:
                        bg_color = "#e9ecef"
                        opacity = "0.85"
                        stripe_css = "background-image: repeating-linear-gradient(45deg, transparent, transparent 10px, rgba(0,0,0,0.08) 10px, rgba(0,0,0,0.08) 20px);"
                        memo_html = f"<div class='cal-memo'>📝 {memo}</div>" if memo else ""
                        bottom_content = f"{memo_html}<div class='cal-reason'>🚫 인정결석<div class='cal-reason-text'>{reason}</div></div>"
                    else:
                        opacity = "1"
                        if h >= n_hours: bg_color = color1
                        elif h > 0: bg_color = color2
                        else: bg_color = color3
                        
                        memo_html = f"<div class='cal-memo'>📝 {memo}</div>" if memo else ""
                        bottom_content = f"{memo_html}<span class='cal-hours'>{h:.1f} h</span>"

                    holiday_name_text = kr_holidays.get(d)
                    is_holiday = bool(holiday_name_text)
                    is_sunday = d.weekday() == 6
                    is_saturday = d.weekday() == 5
                    
                    if is_holiday or is_sunday: day_color = "#dc3545"
                    elif is_saturday: day_color = "#007bff"
                    else: day_color = "inherit"
                        
                    holiday_html = f"<div class='cal-holiday'>{holiday_name_text}</div>" if is_holiday else ""

                    href = f"?date={d}"
                    html += f"<a href='{href}' target='_self' style='text-decoration: none; color: inherit;'>"
                    html += f"<div class='cal-cell' style='background-color: {bg_color}; opacity: {opacity}; {stripe_css}'>"
                    html += f"<div class='cal-top'><span class='cal-day-num' style='color: {day_color};'>{d.day}</span>{holiday_html}</div>"
                    html += f"<div class='cal-bottom'>{bottom_content}</div>"
                    html += "</div></a>"
                    
        html += "</div>"
        st.markdown(html, unsafe_allow_html=True)

        st.divider()
        st.subheader("🛠️ 특정 날짜 상세 관리 및 결석 처리")
        
        selected_date = st.date_input("조회 및 관리할 날짜 (달력 칸 클릭 시 연동)", value=st.session_state['selected_date'])
        st.session_state['selected_date'] = selected_date
        
        target_df = df[df['날짜_date'] == selected_date]
        
        if target_df.empty:
            st.info(f"{selected_date}에 기록된 공부 데이터가 없습니다.")
        else:
            st.write(f"**{selected_date} 기록 목록**")
            disp_df = target_df[target_df['과목'] != '설정']
            st.dataframe(disp_df[['과목', '시간', '사유']], use_container_width=True)
            
            target_idx_list = list(reversed(disp_df.index))
            def format_edit_item(x):
                r = df.loc[x]
                if r['과목'] == '인정결석': return f"🚫 인정결석 ({r['사유']})"
                elif r['과목'] == '메모': return f"📝 메모 ({r['사유']})"
                else: return f"{r['과목']} ({r['시간']}h)"
                
            target_idx = st.selectbox("수정 또는 삭제할 기록을 선택하세요 (최신순)", target_idx_list, format_func=format_edit_item)
            
            if target_idx is not None:
                is_selected_abs = (df.loc[target_idx, '과목'] == '인정결석')
                is_selected_memo = (df.loc[target_idx, '과목'] == '메모')
                
                if is_selected_abs or is_selected_memo:
                    new_reason = st.text_input("수정할 내용", value=df.loc[target_idx, '사유'])
                else:
                    new_time = st.number_input("새로운 공부 시간 (h)", min_value=0.0, step=0.5, value=float(df.loc[target_idx, '시간']))
                
                col_btn1, col_btn2 = st.columns(2)
                
                with col_btn1:
                    if st.button("⏳ 수정 저장", use_container_width=True):
                        row_dict = df.loc[target_idx].to_dict()
                        if is_selected_abs or is_selected_memo: 
                            row_dict['사유'] = new_reason
                        else:
                            if new_time > 0: row_dict['시간'] = new_time
                            else: st.warning("0보다 큰 시간을 입력하세요."); st.stop()
                        edit_data(target_idx, row_dict)
                        st.success("성공적으로 수정되었습니다.")
                        st.rerun()
                
                with col_btn2:
                    if st.button("🗑️ 이 기록 완전히 삭제", use_container_width=True, type="primary"):
                        delete_data(target_idx)
                        st.warning("기록이 삭제되었습니다.")
                        st.rerun()

        st.write("---")
        col_form1, col_form2 = st.columns(2)
        
        with col_form1:
            st.write(f"**📌 {selected_date} 메모 등록**")
            with st.form("memo_form", clear_on_submit=True):
                memo_reason = st.text_input("일정이나 특이사항을 작게 메모하세요")
                submit_memo = st.form_submit_button("메모 남기기")
                if submit_memo:
                    if memo_reason.strip() == "": st.warning("메모 내용을 입력해주세요.")
                    else:
                        append_data({"날짜": selected_date, "과목": "메모", "시간": 0.0, "사유": memo_reason})
                        st.success("메모가 달력에 등록되었습니다.")
                        st.rerun()

        with col_form2:
            st.write(f"**📌 {selected_date} 인정결석 등록**")
            with st.form("absence_form", clear_on_submit=True):
                absence_reason = st.text_input("결석 사유를 입력하세요 (예: 감기몸살)")
                submit_abs = st.form_submit_button("인정결석 처리하기")
                if submit_abs:
                    if absence_reason.strip() == "": st.warning("사유를 반드시 입력해주세요.")
                    else:
                        append_data({"날짜": selected_date, "과목": "인정결석", "시간": 0.0, "사유": absence_reason})
                        st.success(f"{selected_date}이(가) 인정결석으로 처리되었습니다.")
                        st.rerun()

    elif selected_tab == "⚙️ 설정":
        st.subheader("⚙️ 대시보드 및 캘린더 설정")
        st.info("이곳에서 설정한 값들은 구글 시트 데이터베이스에 안전하게 영구 저장되어 다른 기기에서도 유지됩니다.")
        
        with st.form("settings_form"):
            st.write("**1. 🎨 캘린더 색상 및 목표 기준 설정**")
            n_hours = st.number_input("목표 달성 기준 시간 (n시간)", min_value=0.1, value=st.session_state['cal_goal'], step=0.5)
            
            cc1, cc2, cc3 = st.columns(3)
            with cc1: color1 = st.color_picker(f"목표 달성 ({n_hours}h 이상)", st.session_state['cal_c1'])
            with cc2: color2 = st.color_picker(f"부분 달성 ({n_hours}h 미만)", st.session_state['cal_c2'])
            with cc3: color3 = st.color_picker("공부 안 한 날 (0h)", st.session_state['cal_c3'])
            
            st.divider()
            st.write("**2. 📚 과목별 통계 그래프 색상 설정**")
            sc1, sc2, sc3 = st.columns(3)
            new_colors = {}
            subj_list = ["국어", "수학", "영어", "사회문화", "지구과학I", "한국사"]
            for i, subj in enumerate(subj_list):
                col = [sc1, sc2, sc3][i % 3]
                with col:
                    new_colors[subj] = st.color_picker(subj, st.session_state['subj_colors'].get(subj, "#000000"))
            
            st.divider()
            submit_settings = st.form_submit_button("설정 저장하기", type="primary")
            
            if submit_settings:
                save_dict = {
                    'cal_goal': n_hours, 'cal_c1': color1, 'cal_c2': color2, 'cal_c3': color3,
                    'subj_colors': new_colors
                }
                settings_json = json.dumps(save_dict)
                
                # 기존 설정 행 삭제 (아래에서부터 지워야 인덱스 밀림 방지)
                setting_indices = df[df['과목'] == '설정'].index.tolist()
                for idx in reversed(setting_indices):
                    delete_data(idx)
                
                # 새 설정 추가
                append_data({"날짜": today, "과목": "설정", "시간": 0.0, "사유": settings_json})
                
                st.success("설정이 데이터베이스에 안전하게 저장되었습니다!")
                st.rerun()

    with st.expander("📄 전체 데이터 테이블 확인"):
        display_df = df.drop(columns=['날짜_date', '요일'], errors='ignore')
        display_df = display_df[display_df['과목'] != '설정']
        st.write(display_df.sort_values('날짜', ascending=False))
