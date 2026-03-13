import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
import json

# 1. 페이지 설정
st.set_page_config(page_title="최현규의 열공 대시보드", layout="wide")
st.title("🚀 최현규의 데이터 기반 학습 시스템")

# 2. 구글 시트 연결 (JSON 키 파싱 오류 해결)
try:
    # Secrets에 문자열로 저장된 JSON 데이터를 파싱하여 명시적으로 권한 부여
    sa_info = json.loads(st.secrets["connections"]["gsheets"]["service_account"])
    conn = st.connection("gsheets", type=GSheetsConnection, service_account_info=sa_info)
except Exception:
    # 파싱 실패 시 기본 연결 (읽기 전용 모드로 빠질 수 있음)
    conn = st.connection("gsheets", type=GSheetsConnection)

# 데이터 불러오기 함수 (실시간 반영을 위해 TTL=0)
def get_data():
    return conn.read(spreadsheet=st.secrets["public_gsheets_url"], ttl="0s")

df = get_data()

# 데이터가 아예 비어있을 경우 초기화
if df.empty or '날짜' not in df.columns:
    df = pd.DataFrame(columns=['날짜', '과목', '시간'])

# 3. 사이드바: 데이터 입력 및 관리
with st.sidebar:
    st.header("📝 학습 기록")
    with st.form("input_form", clear_on_submit=True):
        date = st.date_input("날짜")
        subject = st.selectbox("과목", ["국어", "수학", "영어", "사회문화", "지구과학I", "한국사"])
        # 시작점을 0.0으로 수정
        time = st.number_input("시간 (h)", min_value=0.0, step=0.5, value=0.0)
        submit = st.form_submit_button("구글 시트에 저장")
        
        if submit:
            if time > 0:
                new_row = pd.DataFrame([{"날짜": str(date), "과목": subject, "시간": time}])
                updated_df = pd.concat([df, new_row], ignore_index=True)
                conn.update(spreadsheet=st.secrets["public_gsheets_url"], data=updated_df)
                st.success("기록 완료!")
                st.rerun()
            else:
                st.warning("0시간 이상 입력해주세요.")

    st.divider()
    st.header("🗑️ 최근 기록 삭제")
    if not df.empty:
        # 가장 최근 데이터 순으로 보여주며 삭제 선택
        delete_idx = st.selectbox("빠른 삭제할 기록을 선택하세요", df.index, format_func=lambda x: f"[{x}] {df.iloc[x]['날짜']} - {df.iloc[x]['과목']} ({df.iloc[x]['시간']}h)")
        if st.button("선택한 기록 삭제", font_variant="primary"):
            updated_df = df.drop(delete_idx)
            conn.update(spreadsheet=st.secrets["public_gsheets_url"], data=updated_df)
            st.warning("기록이 삭제되었습니다.")
            st.rerun()

# 4. 메인 통계 화면
if df.empty:
    st.info("데이터가 없습니다. 왼쪽 사이드바에서 첫 공부 기록을 시작해보세요!")
else:
    # 날짜 데이터 전처리 (모든 탭에서 공통으로 사용하기 위해 상단 배치)
    df['날짜'] = pd.to_datetime(df['날짜'])
    days_map = {0:'월', 1:'화', 2:'수', 3:'목', 4:'금', 5:'토', 6:'일'}
    df['요일'] = df['날짜'].dt.dayofweek.map(days_map)
    day_order = ['월', '화', '수', '목', '금', '토', '일']
    df['요일'] = pd.Categorical(df['요일'], categories=day_order, ordered=True)

    # 탭 3개로 확장
    tab1, tab2, tab3 = st.tabs(["📊 요약 및 추이", "📅 요일별 집중 분석", "🗓️ 날짜별 상세 관리"])

    with tab1:
        # 지표 표시
        c1, c2, c3 = st.columns(3)
        c1.metric("총 시간", f"{df['시간'].sum():.1f}h")
        c2.metric("기록 일수", f"{df['날짜'].nunique()}일")
        c3.metric("일평균", f"{(df['시간'].sum()/df['날짜'].nunique()):.1f}h")

        # 추이 그래프
        line_df = df.groupby('날짜')['시간'].sum().reset_index()
        fig_line = px.line(line_df, x='날짜', y='시간', title="학습 시간 변화 추이", markers=True)
        st.plotly_chart(fig_line, use_container_width=True)

    with tab2:
        st.subheader("요일별 학습 패턴")
        col_left, col_right = st.columns(2)
        
        with col_left:
            # 요일별 평균 시간
            week_avg = df.groupby('요일', observed=True)['시간'].mean().reset_index()
            fig_week = px.bar(week_avg, x='요일', y='시간', color='요일', title="요일별 평균 공부 시간")
            st.plotly_chart(fig_week, use_container_width=True)
            
        with col_right:
            # 선택한 요일의 과목 비중
            sel_day = st.radio("분석할 요일", day_order, horizontal=True)
            day_df = df[df['요일'] == sel_day]
            if not day_df.empty:
                fig_pie = px.pie(day_df, values='시간', names='과목', title=f"{sel_day}요일 과목 비중", hole=.4)
                st.plotly_chart(fig_pie, use_container_width=True)
            else:
                st.write(f"{sel_day}요일 데이터가 아직 없습니다.")

    # 날짜별 상세 관리 탭
    with tab3:
        st.subheader("🗓️ 날짜별 기록 조회 및 관리")
        
        # 날짜 선택
        selected_date = st.date_input("조회 및 관리할 날짜를 선택하세요")
        
        # 선택한 날짜의 데이터 필터링
        target_df = df[df['날짜'].dt.date == selected_date]
        
        if target_df.empty:
            st.info(f"{selected_date}에 기록된 공부 데이터가 없습니다.")
        else:
            st.write(f"**{selected_date} 학습 기록**")
            # 보기 편하도록 표 형태로 출력
            st.dataframe(target_df[['과목', '시간']], use_container_width=True)
            
            st.divider()
            st.subheader("데이터 수정 및 삭제")
            
            # 관리할 특정 기록 선택
            target_idx = st.selectbox(
                "수정 또는 삭제할 과목 기록을 선택하세요", 
                target_df.index, 
                format_func=lambda x: f"{df.loc[x, '과목']} ({df.loc[x, '시간']}h)"
            )
            
            if target_idx is not None:
                # 새로운 시간 입력 (시작점 0.0 수정)
                new_time = st.number_input(
                    "새로운 공부 시간 (h)", 
                    min_value=0.0, 
                    step=0.5, 
                    value=float(df.loc[target_idx, '시간'])
                )
                
                col_btn1, col_btn2 = st.columns(2)
                
                # 시간 수정 버튼
                with col_btn1:
                    if st.button("⏳ 시간 수정 저장", use_container_width=True):
                        if new_time > 0:
                            updated_df = df.copy()
                            updated_df.loc[target_idx, '시간'] = new_time
                            conn.update(spreadsheet=st.secrets["public_gsheets_url"], data=updated_df)
                            st.success("공부 시간이 성공적으로 수정되었습니다.")
                            st.rerun()
                        else:
                            st.warning("0보다 큰 시간을 입력하세요.")
                
                # 기록 삭제 버튼
                with col_btn2:
                    if st.button("🗑️ 이 과목 기록 완전히 삭제", use_container_width=True):
                        updated_df = df.drop(target_idx)
                        conn.update(spreadsheet=st.secrets["public_gsheets_url"], data=updated_df)
                        st.warning("해당 과목의 기록이 삭제되었습니다.")
                        st.rerun()

    with st.expander("📄 전체 데이터 테이블 확인"):
        st.write(df.sort_values('날짜', ascending=False))
