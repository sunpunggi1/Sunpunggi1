import streamlit as st
import pandas as pd
import plotly.express as px
import os

# 페이지 기본 설정
st.set_page_config(page_title="학습 대시보드", layout="wide")
st.title("📚 최현규님의 학습 통계 대시보드")

DATA_FILE = 'study_data.csv'

# 데이터 불러오기 함수 (파일이 없으면 빈 데이터프레임 생성)
def load_data():
    if os.path.exists(DATA_FILE):
        df = pd.read_csv(DATA_FILE)
    else:
        df = pd.DataFrame(columns=['날짜', '과목', '시간'])
    return df

df = load_data()

# 1. 공부 시간 입력 폼
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
            # 새로운 데이터를 기존 데이터에 추가
            new_data = pd.DataFrame({'날짜': [str(input_date)], '과목': [input_subject], '시간': [input_time]})
            df = pd.concat([df, new_data], ignore_index=True)
            
            # CSV 파일로 저장
            df.to_csv(DATA_FILE, index=False)
            st.success(f"{input_date} / {input_subject} / {input_time}시간 기록이 완료되었습니다!")
            # 화면 강제 새로고침을 통해 즉시 그래프 반영
            st.rerun()
        else:
            st.warning("공부 시간을 0시간보다 크게 입력해주세요.")

st.divider()

# 2. 통계 및 그래프 표시
st.subheader("📊 누적 학습 통계")

if not df.empty:
    df['시간'] = pd.to_numeric(df['시간'])
    
    # 상단 요약 지표
    total_time = df['시간'].sum()
    daily_avg = df.groupby('날짜')['시간'].sum().mean()
    
    metric1, metric2 = st.columns(2)
    metric1.metric("총 누적 공부 시간", f"{total_time:.1f}시간")
    metric2.metric("일평균 공부 시간", f"{daily_avg:.1f}시간")

    # 그래프 영역 (일자별 총합 & 과목별 비중)
    chart_col1, chart_col2 = st.columns(2)
    
    with chart_col1:
        # 일자별 총 공부 시간 막대 그래프
        daily_df = df.groupby('날짜', as_index=False)['시간'].sum()
        fig1 = px.bar(daily_df, x='날짜', y='시간', title="📅 일자별 총 공부 시간", text_auto=True)
        st.plotly_chart(fig1, use_container_width=True)
        
    with chart_col2:
        # 과목별 누적 공부 시간 파이 차트
        subject_df = df.groupby('과목', as_index=False)['시간'].sum()
        fig2 = px.pie(subject_df, values='시간', names='과목', title="🎯 과목별 누적 공부 비중", hole=0.3)
        st.plotly_chart(fig2, use_container_width=True)

    # 전체 데이터 표 확인
    with st.expander("📝 전체 기록 데이터 보기"):
        st.dataframe(df, use_container_width=True)
else:
    st.info("아직 기록된 데이터가 없습니다. 위의 폼에서 첫 공부 시간을 입력해보세요.")
