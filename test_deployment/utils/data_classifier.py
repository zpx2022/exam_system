"""
数据分类工具
识别敏感数据和非敏感数据，实现分层加密
借鉴前端data-classifier.js实现
"""

# 敏感数据字段列表（基于实际前端代码验证）
SENSITIVE_FIELDS = [
    # 密码相关（实际使用）
    'password', 'old_password', 'new_password', 'confirm_password',
    
    # 用户个人信息（实际使用）
    'real_name', 'phone',
    
    # 题库管理相关（实际使用）
    'content', 'options', 'answer', 'analysis',
    
    # 考试答题相关（实际使用）
    'answers', 'student_answer', 'student_answers',
    'final_answers', 'user_answers',
    
    # 评分相关（实际使用）
    'score',
    
    # 认证令牌相关（安全敏感）
    'token',
    
    # 注意：description字段（班级/课程描述）已移除，因为不需要加密
]


def classify_data(data):
    """
    提取敏感数据和非敏感数据
    @param {dict} data - 原始数据对象
    @returns {dict} { sensitive: dict, non_sensitive: dict }
    """
    if not data or not isinstance(data, dict):
        return {'sensitive': {}, 'non_sensitive': {}}

    sensitive = {}
    non_sensitive = {}

    for key, value in data.items():
        # 检查是否为敏感字段且值不为空
        if key in SENSITIVE_FIELDS and value is not None and value != '':
            sensitive[key] = value
        else:
            non_sensitive[key] = value

    return {'sensitive': sensitive, 'non_sensitive': non_sensitive}


def has_sensitive_data(data):
    """
    检查是否包含敏感数据
    @param {dict} data - 数据对象
    @returns {bool}
    """
    result = classify_data(data)
    return len(result['sensitive']) > 0


def get_sensitive_fields():
    """
    获取所有敏感字段名
    @returns {list}
    """
    return SENSITIVE_FIELDS.copy()


def add_sensitive_fields(fields):
    """
    添加自定义敏感字段
    @param {str|list} fields - 要添加的字段名
    """
    if isinstance(fields, str):
        fields = [fields]
    
    for field in fields:
        if field not in SENSITIVE_FIELDS:
            SENSITIVE_FIELDS.append(field)


def merge_encrypted_data(original_data, decrypted_data):
    """
    合并原始数据和解密后的敏感数据
    处理批量数据导入的特殊情况
    
    @param {dict} original_data - 原始非敏感数据
    @param {dict} decrypted_data - 解密后的敏感数据
    @returns {dict} 合并后的数据
    """
    merged_data = original_data.copy()
    
    # 特殊处理：批量用户导入
    if 'users' in merged_data and 'sensitive_users' in decrypted_data:
        encrypted_users = merged_data.pop('users')
        sensitive_users = decrypted_data.get('sensitive_users', [])
        
        merged_users = []
        for i, user in enumerate(encrypted_users):
            if i < len(sensitive_users):
                merged_user = user.copy()
                merged_user.update(sensitive_users[i])
                merged_users.append(merged_user)
            else:
                merged_users.append(user)
        
        merged_data['users'] = merged_users
    # 特殊处理：批量题目导入
    elif 'questions' in merged_data and 'sensitive_questions' in decrypted_data:
        encrypted_questions = merged_data.pop('questions')
        sensitive_questions = decrypted_data.get('sensitive_questions', [])
        
        merged_questions = []
        for i, question in enumerate(encrypted_questions):
            if i < len(sensitive_questions):
                merged_question = question.copy()
                merged_question.update(sensitive_questions[i])
                merged_questions.append(merged_question)
            else:
                merged_questions.append(question)
        
        merged_data['questions'] = merged_questions
    else:
        # 直接合并解密的数据
        merged_data.update(decrypted_data)
    
    return merged_data
