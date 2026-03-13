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

# 데이터 업데이트 함수 (권한 에러 예외 처리 추가)
def update_data(updated_df):
    try:
        ws.clear()
        save_df = updated_df.copy()
        save_df['날짜'] = save_df['날짜'].astype(str)
        # 데이터 리스트 변환 후 저장
        data = [save_df.columns.values.tolist()] + save_df.values.tolist()
        ws.update(values=data)
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

    # 탭 3개로 확장
    tab1, tab2, tab3 = st.tabs(["📊 요약 및 추이", "📅 요일별 집중 분석", "🗓️ 날짜별 상세 관리"])

    with tab1:
        c1, c2, c3 = st.columns(3)
        c1.metric("총 시간", f"{df['시간'].sum():.1f}h")
        c2.metric("기록 일수", f"{df['날짜'].nunique()}일")
        c3.metric("일평균", f"{(df['시간'].sum()/df['날짜'].nunique()):.1f}h")

        line_df = df.groupby('날짜', as_index=False)['시간'].sum()
        fig_line = px.line(line_df, x='날짜', y='시간', title="학습 시간 변화 추이", markers=True)
        st.plotly_chart(fig_line, use_container_width=True)

    with tab2:
        st.subheader("요일별 학습 패턴")
        col_left, col_right = st.columns(2)
        
        with col_left:
            week_avg = df.groupby('요일', observed=True)['시간'].mean().reset_index()
            fig_week = px.bar(week_avg, x='요일', y='시간', color='요일', title="요일별 평균 공부 시간")
            st.plotly_chart(fig_week, use_container_width=True)
            
        with col_right:
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
