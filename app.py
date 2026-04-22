import streamlit as st
import pandas as pd
import re
import base64
import easyocr
from PIL import Image, ImageEnhance, ImageFilter
import numpy as np
import io

# Cấu hình trang
st.set_page_config(layout="wide", page_title="QA Ảnh Dim - Furniture")
st.title("🛋️ QA Ảnh Dim - Kiểm tra thông số nội thất")

# Khởi tạo EasyOCR
@st.cache_resource
def load_ocr():
    return easyocr.Reader(['en'])

reader = load_ocr()

def normalize_name(x):
    x = x.lower()
    x = re.sub(r'\.jpg|\.png|\.jpeg', '', x)
    x = re.sub(r'[_\-]', ' ', x)
    x = re.sub(r'[^a-z0-9 ]', '', x)
    x = re.sub(r'\s+', ' ', x)
    return x.strip()

def preprocess(img):
    img = img.convert("L")
    img = ImageEnhance.Contrast(img).enhance(3)
    img = ImageEnhance.Sharpness(img).enhance(2)
    img = img.filter(ImageFilter.MedianFilter())
    return img

def run_ocr_multi(image):
    scales = [1, 1.5, 2]
    nums = []
    for s in scales:
        resized = image.resize((int(image.width*s), int(image.height*s)))
        results = reader.readtext(np.array(resized))
        for (bbox, text, conf) in results:
            found = re.findall(r'(\d+(?:\.\d+)?)', text)
            if found:
                x = bbox[0][0] / s
                y = bbox[0][1] / s
                for f in found:
                    nums.append({"value": f, "x": x, "y": y})
    unique = []
    seen = set()
    for n in nums:
        key = (round(float(n["value"]),2), round(n["x"]/10), round(n["y"]/10))
        if key not in seen:
            seen.add(key)
            unique.append(n)
    return unique

def classify_dims(ocr):
    if len(ocr) < 3:
        return {}
    result = {}
    top = min(ocr, key=lambda x: x["y"])
    result["Height"] = top["value"]
    remain = [n for n in ocr if n != top]
    if len(ocr) >= 4:
        smallest = min(remain, key=lambda x: float(x["value"]))
        result["Leg Height"] = smallest["value"]
        remain = [n for n in remain if n != smallest]
    if len(remain) >= 2:
        remain = sorted(remain, key=lambda x: float(x["value"]), reverse=True)
        result["Width"] = remain[0]["value"]
        result["Depth"] = remain[1]["value"]
    return result

# Sidebar upload
with st.sidebar:
    st.header("📁 Upload dữ liệu")
    excel_file = st.file_uploader("File Excel", type=["xlsx", "xls"])
    image_files = st.file_uploader("Ảnh dim (chọn nhiều)", type=["jpg", "jpeg", "png"], accept_multiple_files=True)
    
    if excel_file and image_files:
        st.success(f"✅ Đã upload {len(image_files)} ảnh")

# Xử lý chính
if excel_file and image_files:
    df = pd.read_excel(excel_file)
    df.columns = [c.lower() for c in df.columns]
    
    for img_file in image_files:
        img = Image.open(img_file)
        img_processed = preprocess(img)
        
        # Tìm row trong Excel
        img_name = img_file.name
        clean_img = normalize_name(img_name)
        
        row = None
        for _, r in df.iterrows():
            excel_val = normalize_name(str(r.iloc[1]))
            if clean_img in excel_val or excel_val in clean_img:
                row = r
                break
        
        if row is None:
            st.error(f"❌ Không tìm thấy: {img_name}")
            continue
        
        # Lấy giá trị Excel
        excel_vals = {
            "Width": row.get("width", "N/A"),
            "Depth": row.get("depth", "N/A"),
            "Height": row.get("height", "N/A"),
            "Leg Height": row.get("leg height", "N/A")
        }
        
        # OCR
        ocr_raw = run_ocr_multi(img_processed)
        size_val = row.get("size")
        if pd.notna(size_val):
            size_num = re.sub(r'[^0-9.]', '', str(size_val))
            ocr_raw = [n for n in ocr_raw if n["value"] != size_num]
        
        ocr = classify_dims(ocr_raw)
        
        # Hiển thị kết quả
        col1, col2 = st.columns([1, 1.5])
        with col1:
            st.image(img, use_container_width=True)
            if pd.notna(size_val):
                st.caption(f"📏 Size: {size_val}")
        
        with col2:
            st.subheader(f"📊 {img_name}")
            
            # Tạo bảng
            data = []
            for k, v_ex in excel_vals.items():
                if pd.isna(v_ex):
                    continue
                v_ai = f'{ocr.get(k, "N/A")}"'
                n_ex = re.sub(r'[^0-9.]', '', str(v_ex))
                n_ai = re.sub(r'[^0-9.]', '', v_ai)
                status = "✅" if n_ex == n_ai else "❌"
                data.append({"Thông số": k, "Excel": v_ex, "AI Đọc": v_ai, "KQ": status})
            
            st.dataframe(data, use_container_width=True, hide_index=True)
        
        st.divider()
