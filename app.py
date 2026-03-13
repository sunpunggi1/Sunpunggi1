import streamlit as st
import pandas as pd
import plotly.express as px
import os
from datetime import datetime

# 페이지 설정
st.set_page_config(page_title="최현규의 열공 대시보드", layout="wide", initial_sidebar_state="expanded")

# 스타일 커스텀
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    </style>
    """, unsafe_allow_html=True)

st.title("🚀 최현규님의 학습 통계 시스템 v2.0")

DATA_FILE = 'study_data.csv'

def load_data():
    if os.path.exists(DATA_FILE):
        df = pd.read_csv(DATA_FILE)
        df['날짜'] = pd.to_datetime(df['날짜'])
        # 요일 데이터 생성
        days_map = {0: '월', 1: '화', 2: '수', 3: '목', 4: '금', 5: '토', 6: '일'}
        df['요일'] = df['날짜'].dt.dayofweek.map(days_map)
        day_order = ['월', '화', '수', '목', '금', '토', '일']
        df['요일'] = pd.Categorical(df['요일'], categories=day_order, ordered=True)
        return df
    return pd.DataFrame(columns=['날짜', '과목', '시간', '요일'])

df = load_data()

# 사이드바: 데이터 입력
with st.sidebar:
    st.header("📝 오늘의 기록")
    with st.form("input_form", clear_on_submit=True):
        date = st.date_input("날짜", datetime.now())
        subject = st.selectbox("과목", ["국어", "수학", "영어", "사회문화", "지구과학I", "한국사"])
        time = st.number_input("시간 (h)", min_value=0.1, max_value=24.0, value=1.0, step=0.5)
        submit = st.form_submit_button("기록하기")
        
        if submit:
            new_row = pd.DataFrame({'날짜': [pd.to_datetime(date)], '과목': [subject], '시간': [time]})
            df = pd.concat([df, new_row], ignore_index=True)
            df.to_csv(DATA_FILE, index=False)
            st.success("저장되었습니다!")
            st.rerun()

# 메인 화면 - 탭 구성
tab_main, tab_day, tab_subject = st.tabs(["🏠 전체 현황", "📅 요일별 분석", "📚 과목별 분석"])

if df.empty:
    st.info("데이터가 없습니다. 사이드바에서 오늘 공부한 시간을 입력해주세요!")
else:
    # --- 탭 1: 전체 현황 ---
    with tab_main:
        col1, col2, col3 = st.columns(3)
        total_h = df['시간'].sum()
        avg_h = total_h / df['날짜'].nunique()
        recent_h = df[df['날짜'] == df['날짜'].max()]['시간'].sum()
        
        col1.metric("총 공부 시간", f"{total_h:.1f}시간")
        col2.metric("일평균 시간", f"{avg_h:.1f}시간")
        col3.metric("최근 기록 시간", f"{recent_h:.1f}시간")
        
        st.divider()
        line_df = df.groupby('날짜')['시간'].sum().reset_index()
        fig_line = px.line(line_df, x='날짜', y='시간', title="📉 일자별 학습 추이", markers=True)
        fig_line.update_traces(line_color='#1f77b4')
        st.plotly_chart(fig_line, use_container_width=True)

    # --- 탭 2: 요일별 분석 (현규님 요청 사항) ---
    with tab_day:
        st.subheader("📅 요일별 집중도 분석")
        
        # 요일별 평균 계산
        weekday_stats = df.groupby('요일', observed=True)['시간'].agg(['mean', 'sum']).reset_index()
        
        c1, c2 = st.columns([2, 1])
        with c1:
            fig_bar = px.bar(weekday_stats, x='요일', y='mean', color='요일',
                             title="요일별 평균 공부 시간", labels={'mean':'평균 시간(h)'},
                             text_auto='.1f')
            st.plotly_chart(fig_bar, use_container_width=True)
        
        with c2:
            st.write("**💡 요일별 인사이트**")
            max_day = weekday_stats.loc[weekday_stats['mean'].idxmax(), '요일']
            min_day = weekday_stats.loc[weekday_stats['mean'].idxmin(), '요일']
            st.info(f"가장 열심히 하는 요일은 **{max_day}요일**입니다!")
            st.warning(f"**{min_day}요일**은 조금 더 집중이 필요해보여요.")

        st.divider()
        
        # 특정 요일 선택 시 해당 요일의 과목 비중
        sel_day = st.selectbox("상세 정보를 볼 요일을 선택하세요", ['월', '화', '수', '목', '금', '토', '일'])
        day_detail = df[df['요일'] == sel_day]
        
        if not day_detail.empty:
            day_sub_pie = px.pie(day_detail, values='시간', names='과목', 
                                 title=f"{sel_day}요일 과목별 학습 비중", hole=.4)
            st.plotly_chart(day_sub_pie, use_container_width=True)
        else:
            st.write(f"{sel_day}요일에 대한 데이터가 아직 없습니다.")

    # --- 탭 3: 과목별 분석 ---
    with tab_subject:
        st.subheader("📚 과목별 밸런스 확인")
        sub_df = df.groupby('과목')['시간'].sum().reset_index()
        
        col_a, col_b = st.columns(2)
        with col_a:
            fig_sub_bar = px.bar(sub_df, x='과목', y='시간', color='과목', title="과목별 총 투자 시간")
            st.plotly_chart(fig_sub_bar, use_container_width=True)
        with col_b:
            fig_sub_pie = px.pie(sub_df, values='시간', names='과목', title="전체 과목 비중")
            st.plotly_chart(fig_sub_pie, use_container_width=True)

# 데이터 관리 (필요 시 삭제 기능 등 추가 가능)
with st.expander("🛠️ 데이터 관리 (전체 데이터 확인)"):
    st.write(df.sort_values(by='날짜', ascending=False))
