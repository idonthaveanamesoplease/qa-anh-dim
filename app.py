import streamlit as st
import pandas as pd
import re
import easyocr
from PIL import Image, ImageEnhance, ImageFilter
import tempfile
import os

# Khởi tạo EasyOCR
@st.cache_resource
def load_ocr():
    return easyocr.Reader(['en'])

reader = load_ocr()

# Tiền xử lý ảnh dim
def preprocess_image(image):
    enhancer = ImageEnhance.Contrast(image)
    image = enhancer.enhance(2.0)
    enhancer = ImageEnhance.Sharpness(image)
    image = enhancer.enhance(2.0)
    image = image.convert('L')
    image = image.filter(ImageFilter.MedianFilter(size=3))
    return image

# Xử lý OCR
def extract_dimensions_from_image(image):
    processed = preprocess_image(image)
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
        temp_path = tmp.name
        processed.save(temp_path)
    
    result = reader.readtext(temp_path)
    os.unlink(temp_path)
    
    all_text = [detection[1] for detection in result]
    full_text = " ".join(all_text)
    
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
        "raw_text": full_text[:200],
        "numbers": unique_numbers,
        "formatted": " x ".join([f"{n}\"" for n in unique_numbers[:3]])
    }

def parse_excel_dimension(dim_str):
    if pd.isna(dim_str):
        return []
    return re.findall(r'(\d+(?:\.\d+)?)', str(dim_str))

def find_row_by_filename(df, filename):
    for idx, row in df.iterrows():
        if pd.notna(row.iloc[1]) and filename.lower() in str(row.iloc[1]).lower():
            return idx, row
    return None, None

def compare_numbers(excel_nums, ocr_nums):
    if not excel_nums or not ocr_nums:
        return False, "Missing data"
    all_pass = True
    results = []
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
    image_files = st.file_uploader("Ảnh dim cần QA (chọn nhiều ảnh)", type=["jpg", "jpeg", "png"], accept_multiple_files=True)
    
    if excel_file and image_files:
        st.success(f"✅ Đã upload {len(image_files)} ảnh")
        df = pd.read_excel(excel_file, engine='openpyxl')
        st.write("**Preview Excel:**")
        st.dataframe(df.head(3))

if excel_file and image_files:
    results_list = []
    
    for idx, image_file in enumerate(image_files):
        with st.status(f"Đang xử lý ảnh {idx+1}/{len(image_files)}: {image_file.name}") as status:
            image = Image.open(image_file)
            filename = image_file.name
            
            idx_row, row = find_row_by_filename(df, filename)
            
            if idx_row is not None:
                product_name = row.iloc[0] if pd.notna(row.iloc[0]) else "N/A"
                dim_columns = df.columns[3:]
                excel_dimensions = {}
                for col in dim_columns:
                    if pd.notna(row[col]):
                        excel_dimensions[col] = str(row[col])
                
                ocr_result = extract_dimensions_from_image(image)
                
                first_dim_name = list(excel_dimensions.keys())[0] if excel_dimensions else None
                if first_dim_name and excel_dimensions[first_dim_name]:
                    excel_nums = parse_excel_dimension(excel_dimensions[first_dim_name])
                    is_pass, comparison = compare_numbers(excel_nums, ocr_result['numbers'])
                    result_status = "✅ PASS" if is_pass else "❌ FAIL"
                else:
                    result_status = "⚠️ No dimension"
                    comparison = "No dimension in Excel"
                
                results_list.append({
                    "STT": idx+1,
                    "Filename": filename,
                    "Sản phẩm": product_name,
                    "Kết quả": result_status,
                    "Chi tiết": comparison,
                    "Excel số": str(excel_nums) if first_dim_name else "N/A",
                    "OCR số": str(ocr_result['numbers']),
                    "OCR text": ocr_result['raw_text']
                })
                status.update(label=f"✅ Xong: {image_file.name} - {result_status}", state="complete")
            else:
                results_list.append({
                    "STT": idx+1,
                    "Filename": filename,
                    "Sản phẩm": "N/A",
                    "Kết quả": "❌ NOT FOUND",
                    "Chi tiết": "Không tìm thấy trong Excel",
                    "Excel số": "N/A",
                    "OCR số": "N/A",
                    "OCR text": "N/A"
                })
                status.update(label=f"❌ Không tìm thấy: {image_file.name}", state="error")
    
    # Hiển thị kết quả tổng hợp
    st.subheader("📊 Bảng kết quả tổng hợp")
    result_df = pd.DataFrame(results_list)
    st.dataframe(result_df, use_container_width=True)
    
    # Thống kê
    pass_count = sum(1 for r in results_list if "PASS" in r["Kết quả"])
    fail_count = sum(1 for r in results_list if "FAIL" in r["Kết quả"])
    not_found = sum(1 for r in results_list if "NOT FOUND" in r["Kết quả"])
    
    st.markdown(f"""
    ### 📈 Thống kê
    - ✅ PASS: {pass_count}
    - ❌ FAIL: {fail_count}
    - 🔍 Không tìm thấy: {not_found}
    - 📊 Tổng số: {len(results_list)}
    """)
    
    # Download kết quả
    csv = result_df.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Tải kết quả (CSV)", data=csv, file_name="ket_qua_qa.csv", mime="text/csv")

else:
    st.info("👈 Vui lòng upload file Excel và ảnh dim ở sidebar để bắt đầu QA")

st.markdown("---")
st.caption("QA Ảnh Dim v1.0 - Hỗ trợ nhiều ảnh")
