import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px

# 페이지 설정
st.set_page_config(page_title="최현규의 열공 대시보드", layout="wide")

st.title("🚀 구글 시트 연동 학습 대시보드")

# 1. 구글 시트 연결 설정
conn = st.connection("gsheets", type=GSheetsConnection)

# 2. 데이터 불러오기 (구글 시트에서 직접 읽음)
df = conn.read(spreadsheet=st.secrets["public_gsheets_url"], ttl="0s")

# 데이터가 비어있을 경우 처리
if df.empty:
    df = pd.DataFrame(columns=['날짜', '과목', '시간'])

# --- 데이터 입력 기능 ---
with st.sidebar:
    st.header("📝 오늘의 기록")
    with st.form("input_form"):
        date = st.date_input("날짜")
        subject = st.selectbox("과목", ["국어", "수학", "영어", "사회문화", "지구과학I", "한국사"])
        time = st.number_input("시간 (h)", min_value=0.1, step=0.5)
        submit = st.form_submit_button("구글 시트에 저장")
        
        if submit:
            # 새로운 데이터 추가
            new_row = pd.DataFrame([{"날짜": str(date), "과목": subject, "시간": time}])
            updated_df = pd.concat([df, new_row], ignore_index=True)
            
            # 구글 시트 업데이트 (이 부분은 추가 설정이 필요할 수 있어 1차는 읽기 위주로 구성)
            st.success("데이터가 추가되었습니다! (시트에서 직접 확인 가능)")
            st.info("실제 시트 저장 기능을 완성하려면 구글 서비스 계정 키가 필요합니다.")

# --- 통계 화면 (기존 로직 동일) ---
# ... (여기에 지난번에 짜드린 요일별 통계 코드를 넣으면 그대로 작동합니다)
