import streamlit as st
import pandas as pd
import plotly.express as px
import os

# 페이지 기본 설정
st.set_page_config(page_title="학습 대시보드", layout="wide")
st.title("📚 최현규님의 학습 통계 대시보드")

DATA_FILE = 'study_data.csv'

# 데이터 불러오기 함수
def load_data():
    if os.path.exists(DATA_FILE):
        df = pd.read_csv(DATA_FILE)
    else:
        df = pd.DataFrame(columns=['날짜', '과목', '시간'])
    return df

df = load_data()

# 1. 공부 시간 입력 폼 (항상 상단에 고정)
st.subheader("⏱️ 오늘 공부 시간 기록하기")
with st.form("record_form"):
    col1, col2, col3 = st.columns(3)
    
    with col1:
        input_date = st.date_input("날짜 선택")
    with col2:
        input_subject = st.selectbox("과목 선택", ["국어", "수학", "영어", "사회문화", "지구과학I", "한국사"])
    with col3:
        input_time = st.number_input("공부 시간 (시간 단위)", min_value=0.0, step=0.5, format="%.1f")
    
    submitted = st.form_submit_button("기록 저장")

    if submitted:
        if input_time > 0:
            new_data = pd.DataFrame({'날짜': [str(input_date)], '과목': [input_subject], '시간': [input_time]})
            df = pd.concat([df, new_data], ignore_index=True)
            df.to_csv(DATA_FILE, index=False)
            st.success(f"{input_date} / {input_subject} / {input_time}시간 기록이 완료되었습니다!")
            st.rerun()
        else:
            st.warning("공부 시간을 0시간보다 크게 입력해주세요.")

st.divider()

# 데이터 전처리 (분석을 위한 요일 변환 등)
if not df.empty:
    df['날짜'] = pd.to_datetime(df['날짜'])
    df['시간'] = pd.to_numeric(df['시간'])
    
    # 요일 데이터 추출 및 정렬 순서 지정
    days_map = {0: '월요일', 1: '화요일', 2: '수요일', 3: '목요일', 4: '금요일', 5: '토요일', 6: '일요일'}
    df['요일'] = df['날짜'].dt.dayofweek.map(days_map)
    day_order = ['월요일', '화요일', '수요일', '목요일', '금요일', '토요일', '일요일']
    df['요일'] = pd.Categorical(df['요일'], categories=day_order, ordered=True)

# 2. 통계 탭(Tab) 구성
tab1, tab2 = st.tabs(["📊 전체 누적 통계", "📅 요일별 세부 통계"])

# --- 탭 1: 기존 전체 누적 통계 ---
with tab1:
    if not df.empty:
        total_time = df['시간'].sum()
        # 고유한 날짜의 수로 나누어 정확한 일평균 계산
        unique_days_count = df['날짜'].nunique()
        daily_avg = total_time / unique_days_count if unique_days_count > 0 else 0
        
        metric1, metric2 = st.columns(2)
        metric1.metric("총 누적 공부 시간", f"{total_time:.1f}시간")
        metric2.metric("일평균 공부 시간", f"{daily_avg:.1f}시간")

        chart_col1, chart_col2 = st.columns(2)
        with chart_col1:
            daily_df = df.groupby('날짜', as_index=False)['시간'].sum()
            fig1 = px.bar(daily_df, x='날짜', y='시간', title="일자별 총 공부 시간", text_auto=True)
            st.plotly_chart(fig1, use_container_width=True)
            
        with chart_col2:
            subject_df = df.groupby('과목', as_index=False)['시간'].sum()
            fig2 = px.pie(subject_df, values='시간', names='과목', title="과목별 누적 공부 비중", hole=0.3)
            st.plotly_chart(fig2, use_container_width=True)

        with st.expander("📝 전체 기록 데이터 보기"):
            st.dataframe(df, use_container_width=True)
    else:
        st.info("기록된 데이터가 없습니다.")

# --- 탭 2: 신규 요일별 세부 통계 ---
with tab2:
    if not df.empty:
        # 요일별 평균 공부 시간 계산 (날짜별로 합산한 뒤, 요일별로 평균)
        daily_sum_for_weekday = df.groupby(['날짜', '요일'], observed=True)['시간'].sum().reset_index()
        weekday_avg = daily_sum_for_weekday.groupby('요일', observed=True)['시간'].mean().reset_index()
        
        st.subheader("전체 요일별 평균 학습 시간")
        fig_weekday_avg = px.bar(weekday_avg, x='요일', y='시간', title="어느 요일에 가장 많이 공부했을까?", text_auto='.1f', color='요일')
        st.plotly_chart(fig_weekday_avg, use_container_width=True)
        
        st.divider()
        
        # 특정 요일 선택 및 분석
        st.subheader("특정 요일 집중 분석")
        selected_day = st.selectbox("분석할 요일을 선택하세요", day_order)
        
        day_df = df[df['요일'] == selected_day]
        
        if day_df.empty:
            st.warning(f"아직 {selected_day}에 기록된 학습 데이터가 없습니다.")
        else:
            day_total_time = day_df['시간'].sum()
            day_unique_dates = day_df['날짜'].nunique()
            day_avg_time = day_total_time / day_unique_dates if day_unique_dates > 0 else 0
            
            col_a, col_b = st.columns(2)
            col_a.metric(f"{selected_day} 총 누적 공부 시간", f"{day_total_time:.1f}시간")
            col_b.metric(f"{selected_day} 평균 공부 시간", f"{day_avg_time:.1f}시간")
            
            # 해당 요일의 과목 비중 파이 차트
            day_subject_df = day_df.groupby('과목', as_index=False)['시간'].sum()
            fig_day_pie = px.pie(day_subject_df, values='시간', names='과목', title=f"{selected_day} 과목별 공부 비중")
            st.plotly_chart(fig_day_pie, use_container_width=True)
    else:
        st.info("기록된 데이터가 없습니다.")
