import os  # 컴퓨터 운영체제(폴더 생성 등)를 제어
import logging  # 파이썬에서 제공하는 실무용 전문 로그 관리 모듈
from datetime import datetime  # 실시간으로 현재 날짜와 시간을 측정하기 위한 도구


# ============================================================================
# [로그 통합 관리 클래스]
# ============================================================================
class LogManager:
    def __init__(self):
        """프로그램이 켜질 때 '딱 한 번' 자동으로 실행되는 초기화 함수(생성자)"""
        self.base_log_folder = "log"  # 모든 로그가 모일 최상위 대문 폴더 이름을 지정
        self.current_date_str = ""  # 마지막으로 로그를 기록한 날짜를 기억하는 상자(날짜 변경 감지)
        self.server_logger = None  # 서버/데이터 로그를 담당
        self.user_logger = None  # 사용자 행동 로그를 담당

        # 프로그램이 켜지자마자 오늘 날짜에 맞는 폴더를 생성하라고 지시
        self._check_and_update_rotation()

    def _get_current_date(self):
        """현재 시스템의 오늘 날짜를 문자열로 받아오는 함수"""
        return datetime.now().strftime("%Y-%m-%d")

    def _check_and_update_rotation(self):
        """마지막 로그 날짜와 오늘 날짜를 비교하여 폴더를 전환(Rotation)하는 함수"""
        #(_): 내부 함수라는 뜻
        today_str = self._get_current_date()  # 1. 현재 날짜와 마지막 log 날짜 비교

        # 2. 만약 기억하고 있던 날짜(current_date_str)와 오늘 날짜가 서로 다르다면 (날짜가 바뀌었거나 프로그램이 처음 켜졌다면)
        if self.current_date_str != today_str:
            self.current_date_str = today_str  # 오늘 날짜로 최신화

            self.daily_folder_path = os.path.join(self.base_log_folder, self.current_date_str)

            #3.하드디스크를 검사해서 해당 날짜 폴더가 없다면 생성
            if not os.path.exists(self.daily_folder_path):
                os.makedirs(self.daily_folder_path)

            self._setup_loggers()

    def _setup_loggers(self):
        """서버용/사용자용 독립된(Logger)들을 생성하고 각각의 텍스트 파일과 매핑하는 환경 설정 함수"""
        formatter = logging.Formatter('[%(asctime)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

        # --------------------------------------------------------------------
        # [1번 서버/데이터 전담 일꾼(Logger) 세팅]
        # --------------------------------------------------------------------
        self.server_logger = logging.getLogger("ServerLogger")  # ServerLogger라는 함수 소환
        self.server_logger.setLevel(logging.INFO)

        if self.server_logger.handlers:
            self.server_logger.handlers.clear()


        server_file = os.path.join(self.daily_folder_path, "server_log.txt")

        server_handler = logging.FileHandler(server_file, encoding="utf-8") #한글 깨짐 방지 위해 UTF-8 인코딩 적용
        server_handler.setFormatter(formatter)
        self.server_logger.addHandler(server_handler)  # 이 전담 일꾼이 텍스트 파일에 글을 쓸 수 있도록 최종 승인합니다.


        # --------------------------------------------------------------------
        self.user_logger = logging.getLogger("UserLogger")
        self.user_logger.setLevel(logging.INFO)

        if self.user_logger.handlers:
            self.user_logger.handlers.clear()  # 예전 날짜 파일 핸들러 중복 제거

        # 새로 바뀐 날짜 폴더 안에 담길 최종 텍스트 파일 경로 지정 (log/날짜/user_log.txt)
        user_file = os.path.join(self.daily_folder_path, "user_log.txt")
        user_handler = logging.FileHandler(user_file, encoding="utf-8")
        user_handler.setFormatter(formatter)
        self.user_logger.addHandler(user_handler)

    # ============================================================================
    def log_server_data(self, message):
        """main.py에서 '온습도 데이터나 장비 제어 상태'를 기록하고 싶을 때 호출하는 대문 창구"""
        self._check_and_update_rotation()  # 글을 쓰기 직전에 '혹시 밤 12시 자정이 지나 날짜가 바뀌었는지' 체크
        self.server_logger.info(message)  # 1번(server_log.txt)에 안전하게 누적하여 저장.

    def log_user_action(self, message):
        """main.py에서 '사용자가 버튼을 클릭하는 등의 행동 이력'을 기록하고 싶을 때 호출하는 대문 창구"""
        self._check_and_update_rotation()  # 로그가 기록되는 바로 그 순간의 날짜 검사 수행
        self.user_logger.info(message)  # 2번(user_log.txt)에 안전하게 글을 누적하여 저장


# ============================================================================
log_manager = LogManager()