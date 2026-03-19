import streamlit as st
import pandas as pd
import plotly.express as px
import json
import gspread

# 1. 페이지 설정
st.set_page_config(page_title="최현규의 열공 대시보드", layout="wide")
st.title("🚀 최현규의 데이터 기반 학습 시스템")

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

# 데이터 불러오기 함수
def get_data():
    try:
        records = ws.get_all_records()
        if not records:
            return pd.DataFrame(columns=['날짜', '과목', '시간'])
        df = pd.DataFrame(records)
        if '시간' in df.columns:
            df['시간'] = pd.to_numeric(df['시간'])
        return df
    except gspread.exceptions.APIError:
        st.error("구글 시트 읽기 권한이 없습니다. 시트 공유 설정에서 서비스 계정을 추가해주세요.")
        st.stop()
    except Exception:
        return pd.DataFrame(columns=['날짜', '과목', '시간'])

# 데이터 업데이트 함수 
def update_data(updated_df):
    try:
        ws.clear()
        save_df = updated_df.copy()
        save_df['날짜'] = save_df['날짜'].astype(str)
        # 데이터 리스트 변환 후 저장
        data = [save_df.columns.values.tolist()] + save_df.values.tolist()
        ws.update(range_name='A1', values=data)
    except gspread.exceptions.APIError as e:
        st.error(f"구글 시트 쓰기(편집) 권한이 없습니다. 서비스 계정 이메일이 시트의 '편집자'로 등록되어 있는지 확인하세요. 상세 오류: {e}")
        st.stop()
    except Exception as e:
        st.error(f"데이터 업데이트 중 알 수 없는 오류가 발생했습니다: {e}")
        st.stop()

df = get_data()

# 데이터가 아예 비어있을 경우 초기화
if df.empty or '날짜' not in df.columns:
    df = pd.DataFrame(columns=['날짜', '과목', '시간'])

# 3. 사이드바: 데이터 입력 및 관리
with st.sidebar:
    # --- 신규: 주간 목표 설정 ---
    st.header("🎯 주간 목표 설정")
    weekly_goal = st.number_input("이번 주 목표 공부 시간 (h)", min_value=1.0, value=40.0, step=1.0)
    st.divider()

    st.header("📝 학습 기록")
    with st.form("input_form", clear_on_submit=True):
        date = st.date_input("날짜")
        subject = st.selectbox("과목", ["국어", "수학", "영어", "사회문화", "지구과학I", "한국사"])
        time = st.number_input("시간 (h)", min_value=0.0, step=0.5, value=0.0)
        submit = st.form_submit_button("구글 시트에 저장")
        
        if submit:
            if time > 0:
                new_row = pd.DataFrame([{"날짜": str(date), "과목": subject, "시간": time}])
                updated_df = pd.concat([df, new_row], ignore_index=True)
                update_data(updated_df)
                st.success("기록 완료!")
                st.rerun()
            else:
                st.warning("0시간 이상 입력해주세요.")

    st.divider()
    st.header("🗑️ 최근 기록 삭제")
    if not df.empty:
        delete_idx = st.selectbox("빠른 삭제할 기록을 선택하세요", df.index, format_func=lambda x: f"[{x}] {df.iloc[x]['날짜']} - {df.iloc[x]['과목']} ({df.iloc[x]['시간']}h)")
        if st.button("선택한 기록 삭제", type="primary"):
            updated_df = df.drop(delete_idx).reset_index(drop=True)
            update_data(updated_df)
            st.warning("기록이 삭제되었습니다.")
            st.rerun()

# 4. 메인 통계 화면
if df.empty:
    st.info("데이터가 없습니다. 왼쪽 사이드바에서 첫 공부 기록을 시작해보세요!")
else:
    # 날짜 데이터 전처리
    df['날짜'] = pd.to_datetime(df['날짜'])
    days_map = {0:'월', 1:'화', 2:'수', 3:'목', 4:'금', 5:'토', 6:'일'}
    df['요일'] = df['날짜'].dt.dayofweek.map(days_map)
    day_order = ['월', '화', '수', '목', '금', '토', '일']
    df['요일'] = pd.Categorical(df['요일'], categories=day_order, ordered=True)

    # --- 신규: 연속 학습일(Streak) 계산 ---
    unique_dates = sorted(df['날짜'].dt.date.unique(), reverse=True)
    streak_count = 0
    today = pd.Timestamp.now().date()
    
    if unique_dates:
        # 오늘이나 어제 기록이 있다면 스트릭 활성화
        if unique_dates[0] == today or unique_dates[0] == today - pd.Timedelta(days=1):
            streak_count = 1
            curr_d = unique_dates[0]
            for d in unique_dates[1:]:
                if d == curr_d - pd.Timedelta(days=1):
                    streak_count += 1
                    curr_d = d
                else:
                    break

    # 이번 주 데이터 필터링 (월요일 기점)
    now_ts = pd.Timestamp.now().normalize()
    start_of_week = now_ts - pd.Timedelta(days=now_ts.dayofweek)
    this_week_df = df[df['날짜'] >= start_of_week]
    this_week_hours = this_week_df['시간'].sum()

    # 탭 3개로 확장
    tab1, tab2, tab3 = st.tabs(["📊 요약 및 추이", "📅 요일별 집중 분석", "🗓️ 날짜별 상세 관리"])

    with tab1:
        st.subheader("📊 기간별 학습 요약 및 달성도")
        
        # 상단 지표 (스트릭 추가)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("총 공부 시간", f"{df['시간'].sum():.1f}h")
        c2.metric("🔥 연속 학습일", f"{streak_count}일째!")
        c3.metric("기록 일수", f"{df['날짜'].nunique()}일")
        c4.metric("전체 일평균", f"{(df['시간'].sum()/df['날짜'].nunique() if df['날짜'].nunique() > 0 else 0):.1f}h")
        
        st.divider()

        # --- 신규: 주간 목표 달성 프로그레스 바 ---
        st.write(f"**이번 주 목표 달성률 ({this_week_hours:.1f}h / {weekly_goal:.1f}h)**")
        progress_pct = min(this_week_hours / weekly_goal, 1.0)
        st.progress(progress_pct)
        if progress_pct >= 1.0:
            st.success("🎉 이번 주 목표 시간을 달성했습니다! 훌륭합니다!")
        else:
            st.caption(f"목표 달성까지 {weekly_goal - this_week_hours:.1f}시간 남았습니다. 화이팅!")
        
        st.divider()

        # --- 신규: 주간 리포트 자동 생성 ---
        if not this_week_df.empty:
            top_subject = this_week_df.groupby('과목')['시간'].sum().idxmax()
            top_day = this_week_df.groupby('요일', observed=True)['시간'].sum().idxmax()
            st.info(f"📝 **최현규님의 주간 학습 리포트**\n\n이번 주 최애 과목은 **{top_subject}**이었고, 가장 열심히 공부한 요일은 **{top_day}요일**입니다. 훌륭한 페이스입니다!")
        
        st.divider()
        
        # 주간/월간 필터 추가
        filter_opt = st.radio("조회 기간 선택", ["전체 기간", "최근 7일 (주간)", "최근 30일 (월간)"], horizontal=True)
        filtered_df = df.copy()
        
        if filter_opt == "최근 7일 (주간)":
            filtered_df = filtered_df[filtered_df['날짜'] >= (now_ts - pd.Timedelta(days=6))]
        elif filter_opt == "최근 30일 (월간)":
            filtered_df = filtered_df[filtered_df['날짜'] >= (now_ts - pd.Timedelta(days=29))]

        if filtered_df.empty:
            st.warning("선택한 기간에 기록된 학습 데이터가 없습니다.")
        else:
            # 과목 밸런스(도넛 차트) & 누적 시간(영역 그래프)
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

    with tab2:
        st.subheader("요일별 학습 패턴 및 인사이트")
        col_left, col_right = st.columns(2)
        
        week_avg = df.groupby('요일', observed=True)['시간'].mean().reset_index()
        
        with col_left:
            fig_week = px.bar(week_avg, x='요일', y='시간', color='요일', title="요일별 평균 공부 시간")
            st.plotly_chart(fig_week, use_container_width=True)
            
        with col_right:
            # --- 신규: 요일별 슬럼프/집중도 인사이트 ---
            if not week_avg.empty and week_avg['시간'].sum() > 0:
                max_day = week_avg.loc[week_avg['시간'].idxmax(), '요일']
                min_day = week_avg.loc[week_avg['시간'].idxmin(), '요일']
                st.success(f"🔥 **{max_day}요일**에 가장 집중력이 좋으시군요! 이 페이스를 유지하세요.")
                st.warning(f"💡 데이터 객관화: **{min_day}요일**에는 유독 학습 시간이 짧아지는 패턴이 있습니다. {min_day}요일에는 무리한 계획보다는 가벼운 복습 위주로 슬럼프를 예방해 보세요.")
            
            st.divider()
            sel_day = st.radio("분석할 요일", day_order, horizontal=True)
            day_df = df[df['요일'] == sel_day]
            if not day_df.empty:
                fig_pie = px.pie(day_df, values='시간', names='과목', title=f"{sel_day}요일 과목 비중", hole=.4)
                st.plotly_chart(fig_pie, use_container_width=True)
            else:
                st.write(f"{sel_day}요일 데이터가 아직 없습니다.")

    with tab3:
        st.subheader("🗓️ 날짜별 기록 조회 및 관리")
        selected_date = st.date_input("조회 및 관리할 날짜를 선택하세요")
        target_df = df[df['날짜'].dt.date == selected_date]
        
        if target_df.empty:
            st.info(f"{selected_date}에 기록된 공부 데이터가 없습니다.")
        else:
            st.write(f"**{selected_date} 학습 기록**")
            st.dataframe(target_df[['과목', '시간']], use_container_width=True)
            
            st.divider()
            st.subheader("데이터 수정 및 삭제")
            
            target_idx = st.selectbox(
                "수정 또는 삭제할 과목 기록을 선택하세요", 
                target_df.index, 
                format_func=lambda x: f"{df.loc[x, '과목']} ({df.loc[x, '시간']}h)"
            )
            
            if target_idx is not None:
                new_time = st.number_input(
                    "새로운 공부 시간 (h)", 
                    min_value=0.0, 
                    step=0.5, 
                    value=float(df.loc[target_idx, '시간'])
                )
                
                col_btn1, col_btn2 = st.columns(2)
                
                with col_btn1:
                    if st.button("⏳ 시간 수정 저장", use_container_width=True):
                        if new_time > 0:
                            updated_df = df.copy()
                            updated_df.loc[target_idx, '시간'] = new_time
                            save_df = updated_df.drop(columns=['요일'], errors='ignore')
                            update_data(save_df)
                            st.success("공부 시간이 성공적으로 수정되었습니다.")
                            st.rerun()
                        else:
                            st.warning("0보다 큰 시간을 입력하세요.")
                
                with col_btn2:
                    if st.button("🗑️ 이 과목 기록 완전히 삭제", use_container_width=True, type="primary"):
                        updated_df = df.drop(target_idx).reset_index(drop=True)
                        save_df = updated_df.drop(columns=['요일'], errors='ignore')
                        update_data(save_df)
                        st.warning("해당 과목의 기록이 삭제되었습니다.")
                        st.rerun()

    with st.expander("📄 전체 데이터 테이블 확인"):
        st.write(df.sort_values('날짜', ascending=False))
