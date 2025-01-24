import re
import os


class Util:
    @staticmethod
    def is_phone(s: str):
        pattern = r'^[\+0-9]+$'
        return bool(re.match(pattern, s))

    @staticmethod
    def ensure_dir(dir: str):
        if not os.path.exists(dir):
            os.mkdir(dir)

    @staticmethod
    def is_login_code(code: str):
        pattern = r'^[0-9]+$'
        return len(code) == 5 and bool(re.match(pattern, code))

    @staticmethod
    def delete_file(file_path: str):
        os.remove(file_path)

    @staticmethod
    def try_to_correct_phone(phone: str):
        phone = phone.replace(" ", "")
        if len(phone) > 0 and phone[0] != "+":
            phone = "+" + phone
        return phone 