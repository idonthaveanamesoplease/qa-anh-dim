import streamlit as st
import pandas as pd
import re
import easyocr
from PIL import Image
import numpy as np

st.set_page_config(layout="wide")
st.title("QA Ảnh Dim")

@st.cache_resource
def load_ocr():
    # Chỉ dùng CPU, không tải GPU
    return easyocr.Reader(['en'], gpu=False)

try:
    reader = load_ocr()
    st.success("✅ OCR đã sẵn sàng")
except Exception as e:
    st.error(f"Lỗi tải OCR: {e}")
    st.stop()

excel_file = st.sidebar.file_uploader("Excel", type=["xlsx", "xls"])
image_files = st.sidebar.file_uploader("Ảnh", type=["jpg", "png", "jpeg"], accept_multiple_files=True)

if excel_file and image_files:
    df = pd.read_excel(excel_file)
    st.success(f"Đã upload {len(image_files)} ảnh")
    
    for img_file in image_files:
        st.subheader(img_file.name)
        img = Image.open(img_file)
        
        with st.spinner("Đang đọc ảnh..."):
            result = reader.readtext(np.array(img))
            numbers = []
            for (bbox, text, conf) in result:
                found = re.findall(r'\d+(?:\.\d+)?', text)
                if found and conf > 0.5:
                    numbers.extend(found)
        
        st.write(f"Số tìm thấy: {numbers}")
        st.image(img, width=300)
        st.divider()
