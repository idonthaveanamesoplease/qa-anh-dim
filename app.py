import streamlit as st
import pandas as pd
import cv2
import numpy as np
import re
import easyocr
from PIL import Image

# Khởi tạo EasyOCR
@st.cache_resource
def load_ocr():
    return easyocr.Reader(['en'])

reader = load_ocr()

# Tiền xử lý ảnh dim
def preprocess_image(image):
    img = np.array(image)
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    enhanced = clahe.apply(gray)
    
    denoised = cv2.fastNlMeansDenoising(enhanced, h=30)
    
    kernel_sharpen = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
    sharpened = cv2.filter2D(denoised, -1, kernel_sharpen)
    
    return sharpened

# Xử lý OCR và trích xuất số
def extract_dimensions_from_image(image):
    processed = preprocess_image(image)
    
    # Lưu tạm
    temp_path = "temp_processed.png"
    cv2.imwrite(temp_path, processed)
    
    # OCR bằng EasyOCR
    result = reader.readtext(temp_path)
    
    # Gom text
    all_text = []
    for detection in result:
        text = detection[1]
        all_text.append(text)
    
    full_text = " ".join(all_text)
    
    # Trích xuất số
    patterns = [
        r'(\d+(?:\.\d+)?)\s*["\']',
        r'(\d+(?:\.\d+)?)\s*in',
        r'(\d+(?:\.\d+)?)\s*"',
        r'(\d+(?:\.\d+)?)\s*(?:W|H|D|x)'
    ]
    
    numbers = []
    for pattern in patterns:
        matches = re.findall(pattern, full_text, re.IGNORECASE)
        numbers.extend(matches)
    
    unique_numbers = list(dict.fromkeys(numbers))
    
    return {
        "raw_text": full_text,
        "numbers": unique_numbers,
        "formatted": " x ".join([f"{n}\"" for n in unique_numbers[:3]])
    }

def parse_excel_dimension(dim_str):
    if pd.isna(dim_str):
        return []
    dim_str = str(dim_str)
    numbers = re.findall(r'(\d+(?:\.\d+)?)', dim_str)
    return numbers

def find_row_by_filename(df, filename):
    for idx, row in df.iterrows():
        if pd.notna(row.iloc[1]) and filename.lower() in str(row.iloc[1]).lower():
            return idx, row
    return None, None

def compare_numbers(excel_nums, ocr_nums):
    if not excel_nums or not ocr_nums:
        return False, "Missing data"
    
    results = []
    all_pass = True
    for i, excel_num in enumerate(excel_nums):
        if i < len(ocr_nums):
            if excel_num == ocr_nums[i]:
                results.append(f"{excel_num} == {ocr_nums[i]} ✓")
            else:
                results.append(f"{excel_num} != {ocr_nums[i]} ✗")
                all_pass = False
        else:
            results.append(f"{excel_num} not found ✗")
            all_pass = False
    
    return all_pass, " | ".join(results)

# Giao diện
st.set_page_config(layout="wide", page_title="QA Ảnh Dim - Furniture")
st.title("🛋️ QA Ảnh Dim - Kiểm tra thông số nội thất")

with st.sidebar:
    st.header("📁 Upload dữ liệu")
    excel_file = st.file_uploader("File Excel (data gốc)", type=["xlsx", "xls"])
    image_file = st.file_uploader("Ảnh dim cần QA", type=["jpg", "jpeg", "png"])
    
    if excel_file and image_file:
        st.success("✅ Đã upload xong")
        df = pd.read_excel(excel_file)
        st.write("**Preview Excel:**")
        st.dataframe(df.head(3))

if excel_file and image_file:
    image = Image.open(image_file)
    filename = image_file.name
    
    idx, row = find_row_by_filename(df, filename)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📷 Ảnh dim")
        st.image(image, use_container_width=True)
        st.caption(f"Filename: {filename}")
    
    with col2:
        st.subheader("📊 Kết quả QA")
        
        if idx is not None:
            product_name = row.iloc[0] if pd.notna(row.iloc[0]) else "N/A"
            file_col_b = row.iloc[1] if pd.notna(row.iloc[1]) else "N/A"
            
            dim_columns = df.columns[3:]
            excel_dimensions = {}
            
            for col in dim_columns:
                if pd.notna(row[col]):
                    excel_dimensions[col] = str(row[col])
            
            st.markdown("### 📋 Data từ file Excel")
            st.write(f"**Sản phẩm:** {product_name}")
            st.write(f"**Filename:** {file_col_b}")
            st.write("**Dimensions:**")
            for dim_name, dim_value in excel_dimensions.items():
                st.write(f"- {dim_name}: {dim_value}")
            
            with st.spinner("🔍 Đang quét ảnh..."):
                ocr_result = extract_dimensions_from_image(image)
            
            st.markdown("### 🤖 AI quét được từ ảnh")
            st.write(f"**Raw text:** {ocr_result['raw_text'][:200]}...")
            st.write(f"**Số tìm thấy:** {', '.join(ocr_result['numbers']) if ocr_result['numbers'] else 'Không tìm thấy'}")
            st.write(f"**Format gợi ý:** {ocr_result['formatted']}")
            
            st.markdown("### ✅ So sánh PASS/FAIL")
            
            first_dim_name = list(excel_dimensions.keys())[0] if excel_dimensions else None
            if first_dim_name and excel_dimensions[first_dim_name]:
                excel_nums = parse_excel_dimension(excel_dimensions[first_dim_name])
                is_pass, comparison = compare_numbers(excel_nums, ocr_result['numbers'])
                
                if is_pass:
                    st.success(f"✅ PASS - {comparison}")
                else:
                    st.error(f"❌ FAIL - {comparison}")
                
                st.write(f"**Excel:** {excel_dimensions[first_dim_name]} → số: {excel_nums}")
                st.write(f"**OCR:** {ocr_result['formatted']} → số: {ocr_result['numbers']}")
            else:
                st.warning("⚠️ Không tìm thấy dimension trong Excel để so sánh")
        else:
            st.error(f"❌ Không tìm thấy filename '{filename}' trong file Excel")

else:
    st.info("👈 Vui lòng upload file Excel và ảnh dim ở sidebar để bắt đầu QA")

st.markdown("---")
st.caption("QA Ảnh Dim v1.0 - So sánh số từ ảnh với dữ liệu Excel")
