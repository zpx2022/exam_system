"""
Redis客户端封装
处理考试倒计时 & 临时进度缓存
"""
import redis
from django.conf import settings
import time
import json


class RedisClient:
    def __init__(self):
        self.client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            password=settings.REDIS_PASSWORD,
            decode_responses=False  # 返回字节串
        )

    # ---------- 通用JSON缓存 ----------
    def set_json(self, key: str, obj, ttl: int | None = None):
        data = json.dumps(obj, ensure_ascii=False).encode()
        if ttl:
            self.client.setex(key, ttl, data)
        else:
            self.client.set(key, data)

    def get_json(self, key: str):
        data = self.client.get(key)
        if data is None:
            return None
        return json.loads(data.decode())

    # ---------- 考试倒计时 ----------
    def set_exam_timer(self, record_id, duration_seconds):
        """
        设置考试倒计时
        :param record_id: 考试记录ID
        :param duration_seconds: 考试时长（秒）
        :return: 强制结束时间戳
        """
        force_end_time = int(time.time()) + duration_seconds
        ttl = duration_seconds + 300  # 增加5分钟缓冲
        self.client.setex(f"exam_timer:{record_id}", ttl, force_end_time)
        return force_end_time

    def get_exam_remaining_time(self, record_id):
        val = self.client.get(f"exam_timer:{record_id}")
        if val is None:
            return 0
        remaining = int(val) - int(time.time())
        return max(0, remaining)

    def delete_exam_timer(self, record_id):
        self.client.delete(f"exam_timer:{record_id}")

    def exam_expired(self, record_id):
        return self.get_exam_remaining_time(record_id) == 0

    # ---------- 学生答案缓存 ----------
    def cache_student_answers(self, record_id, answers: dict, ttl: int = 7200):
        """缓存学生答案2小时"""
        self.set_json(f"student_answers:{record_id}", answers, ttl=ttl)

    def get_student_answers(self, record_id):
        return self.get_json(f"student_answers:{record_id}")

    def delete_student_answers(self, record_id):
        self.client.delete(f"student_answers:{record_id}")

    def update_student_answer(self, record_id, question_id: int, answer, ttl: int = 7200):
        """更新单个答案"""
        key = f"student_answers:{record_id}"
        answers = self.get_student_answers(record_id) or {}
        answers[str(question_id)] = answer
        self.set_json(key, answers, ttl=ttl)

    def get_student_answer(self, record_id, question_id: int):
        """获取单个答案"""
        answers = self.get_student_answers(record_id)
        if answers:
            return answers.get(str(question_id))
        return None

    # ---------- 修改密码验证码 ----------
    def set_password_change_code(self, user_id, code, ttl=300):
        """设置修改密码验证码，有效期5分钟"""
        self.client.setex(f"pwd_change_code:{user_id}", ttl, code)

    def get_password_change_code(self, user_id):
        code = self.client.get(f"pwd_change_code:{user_id}")
        return code.decode() if code else None

    def delete_password_change_code(self, user_id):
        self.client.delete(f"pwd_change_code:{user_id}")

    def set_password_change_cooldown(self, user_id, ttl=60):
        """设置修改密码验证码发送冷却，60秒"""
        self.client.setex(f"pwd_change_cd:{user_id}", ttl, 1)

    def check_password_change_cooldown(self, user_id):
        """检查是否在冷却中"""
        return self.client.exists(f"pwd_change_cd:{user_id}")

    # ---------- 忘记密码验证码 ----------
    def set_forgot_password_code(self, user_id, code, ttl=300):
        """设置忘记密码验证码，有效期5分钟"""
        self.client.setex(f"forgot_pwd_code:{user_id}", ttl, code)

    def get_forgot_password_code(self, user_id):
        code = self.client.get(f"forgot_pwd_code:{user_id}")
        return code.decode() if code else None

    def delete_forgot_password_code(self, user_id):
        self.client.delete(f"forgot_pwd_code:{user_id}")

    def set_forgot_password_cooldown(self, user_id, ttl=60):
        """设置忘记密码验证码发送冷却，60秒"""
        self.client.setex(f"forgot_pwd_cd:{user_id}", ttl, 1)

    def check_forgot_password_cooldown(self, user_id):
        """检查是否在冷却中"""
        return self.client.exists(f"forgot_pwd_cd:{user_id}")


redis_client = RedisClient()
