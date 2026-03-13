import streamlit as st
import pandas as pd
import plotly.express as px

st.title("📚 최현규님의 학습 통계 대시보드")

# 데이터 불러오기
try:
    df = pd.read_csv('study_data.csv')
    df['날짜'] = pd.to_datetime(df['날짜'])
    
    # 통계 요약
    total_time = df['시간'].sum()
    avg_time = df['시간'].mean()
    
    col1, col2 = st.columns(2)
    col1.metric("총 공부 시간", f"{total_time}시간")
    col2.metric("일평균 공부 시간", f"{avg_time:.1f}시간")

    # 그래프 생성
    fig = px.bar(df, x='날짜', y='시간', title='일자별 공부 시간', color='시간')
    st.plotly_chart(fig)

except FileNotFoundError:
    st.error("study_data.csv 파일을 찾을 수 없습니다. 데이터를 먼저 작성해 주세요.")