import re
from flask import Flask, request, jsonify, render_template

app = Flask(__name__)


def parse_pdf_text_by_toc(toc_text, full_text):
    """
    根据目录条目解析完整的PDF文本并提取内容。

    Args:
        toc_text (str): 包含目录信息的文本。
        full_text (str): 完整的PDF文本内容。

    Returns:
        list: 包含解析结果的字典列表，每个字典代表一个条目。
    """
    # 1. 文本预处理：移除不必要的换行符和空格
    # 修复像 "ID\n.IM" 这样的格式
    full_text = re.sub(r'\s*\n\s*\.\s*', '.', full_text)
    # 修复像 "ID\n-" 这样的格式
    full_text = re.sub(r'-\s*\n\s*', '', full_text)
    # 将所有换行符替换为单个空格
    full_text = re.sub(r'\s*\n\s*', ' ', full_text)
    # 移除多余的空格
    full_text = re.sub(r'\s+', ' ', full_text).strip()

    # 2. 解析目录，获取所有条目的编号和描述
    toc_entries = []
    # 匹配 "1.1.1.1 Ensure..." 这种格式的行
    # Updated regex to be more flexible, matching numbers with one or more dots.
    toc_lines = re.findall(r'•\s*(\d+(?:\.\d+)+)\s+([^\n]+?)\s*\.{3,}\s*\d+', toc_text, re.IGNORECASE | re.DOTALL)
    if not toc_lines:
        # Fallback for lines without a bullet point
        toc_lines = re.findall(r'(\d+(?:\.\d+)+)\s+([^\n]+?)\s*\.{3,}\s*\d+', toc_text, re.IGNORECASE | re.DOTALL)

    for number, description in toc_lines:
        # 清理描述中的页码
        clean_description = re.sub(r'\.{3,}\s*\d+', '', description).strip()
        toc_entries.append({'number': number.strip(), 'description': clean_description})

    data = []

    # 3. 遍历目录，以目录条目作为锚点来提取内容
    for i in range(len(toc_entries)):
        current_entry = toc_entries[i]

        # 构造当前条目在PDF文本中的唯一标识
        start_string = f"{current_entry['number']} {current_entry['description']}"
        start_index = full_text.find(start_string)

        # 如果找不到该条目，则跳过
        if start_index == -1:
            print(f"警告：无法在PDF文本中找到条目：{start_string}")
            continue

        # 确定当前条目内容的结束位置，即下一个条目的起始位置
        end_index = len(full_text)
        if i + 1 < len(toc_entries):
            next_entry = toc_entries[i + 1]
            next_start_string = f"{next_entry['number']} {next_entry['description']}"
            next_index = full_text.find(next_start_string, start_index + len(start_string))
            if next_index != -1:
                end_index = next_index

        # 提取当前条目的完整内容部分
        section_content = full_text[start_index:end_index]

        # 4. 从提取出的内容中解析各个字段

        # 提取类型 (FAILED, PASSED, SKIPPED)
        status_match = re.search(r'\*\* (FAILED|PASSED|SKIPPED) \*\*', section_content)
        if not status_match:
            status_match = re.search(r'Policy Value\s*\n\s*(FAILED|PASSED|SKIPPED)', section_content, re.IGNORECASE)
        type_ = status_match.group(1).upper() if status_match else 'N/A'

        # 使用正则表达式和捕获组来提取 Info, Solution, References, Audit File, Policy Value
        info_match = re.search(r'Info\s*(.*?)(?=\s*Solution|\s*$)', section_content, re.DOTALL)
        solution_match = re.search(r'Solution\s*(.*?)(?=\s*See Also|\s*References|\s*$)', section_content, re.DOTALL)
        references_match = re.search(r'References\s*(.*?)(?=\s*Audit File|\s*$)', section_content, re.DOTALL)
        audit_file_match = re.search(r'Audit File\s*(.*?)(?=\s*Policy Value|\s*$)', section_content, re.DOTALL)
        # Updated regex to correctly capture multi-line policy values that are followed by "Hosts"
        policy_value_match = re.search(r'Policy Value\s*(.*?)(?=\s*Hosts|\s*$)', section_content, re.DOTALL)

        data.append({
            'number': current_entry['number'],
            'description': current_entry['description'],
            'type': type_,
            'info': info_match.group(1).strip() if info_match else 'N/A',
            'solution': solution_match.group(1).strip() if solution_match else 'N/A',
            'references': references_match.group(1).strip().split('\n') if references_match else ['N/A'],
            'auditFile': audit_file_match.group(1).strip() if audit_file_match else 'N/A',
            'policyValue': policy_value_match.group(1).strip() if policy_value_match else 'N/A',
        })

    return data


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/process_pdf', methods=['POST'])
def process_pdf():
    try:
        data = request.get_json()
        toc_text = data.get('toc_text', '')
        pdf_text = data.get('pdf_text', '')

        if not toc_text or not pdf_text:
            return jsonify({'error': '目录和PDF文本都不能为空'}), 400

        results = parse_pdf_text_by_toc(toc_text, pdf_text)
        return jsonify({'results': results})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True)
