#################################################################################################

import json  # TCP 소켓 통신 모듈 — 서버와 직접 연결하여 데이터를 주고받음
import os
import re  # 정규표현식 모듈 — 로그에서 온도/습도 수치를 패턴으로 추출할 때 사용
import socket  # TCP 소켓 통신 모듈 — 서버와 직접 연결하여 데이터를 주고받음
import sys# 시스템 종료, 인자 처리 등 파이썬 런타임 제어 모듈

import sys
sys.setrecursionlimit(2000)
import matplotlib
# 백엔드 설정은 항상 plot 관련 모듈보다 먼저 호출되어야 합니다.
matplotlib.use('Qt5Agg')

from PyQt5 import QtWidgets, uic, QtCore# GUI 위젯 클래스(버튼, 라벨 등)와 .ui 파일 로더 임포트

from datetime import datetime  # 날짜+시간 객체 생성 및 포맷 변환 — 로그 시간 필터링에 사용
from collections import deque

from PyQt5.QtCore import (
    QThread,
    pyqtSignal,
    QDate,
    QTime,
    QTimer
)  # 수정
from PyQt5.QtGui import QPixmap  # 이미지 파일을 불러와 라벨에 표시하기 위한 클래스

os.environ["QT_API"] = "pyqt5"

import matplotlib # 그래프 라이브러리 — 백엔드 설정을 위해 먼저 단독으로 임포트

matplotlib.use('Qt5Agg') #Matplotlib 렌더링 백엔드를 PyQt5 전용으로 설정 (반드시 plot 임포트 전에 해야 함)
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from log import log_manager

plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

##################################################################################################
# TCP/IP 통신 담당 클래스
# 서버 (mock_server.py)와 연결하여 온습도 데이터 수신, 새로고침 요청 전송, 실시간 데이터 전달을 담당
class NetworkWorker(QThread): # 클래스 선언, PyQt의 QThread를 상속받은 스레드
    data_received = pyqtSignal(int, int)
    refresh_received = pyqtSignal(int, int)

    def __init__(self, ip, port):
        super().__init__()
        self.server_ip = ip
        self.server_port = port
        self.client_socket = None
        self.is_running = True

    def force_refresh(self):
        if self.client_socket is None: return
        try:
            self.client_socket.sendall(b"REQ\n")
        except Exception as e:
            print(f"새로고침 명령 전송 오류: {e}")

    def run(self):
        try:
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.settimeout(5.0)
            self.client_socket.connect((self.server_ip, self.server_port))
            self.client_socket.settimeout(None)

            while self.is_running:
                raw_data = self.client_socket.recv(1024) #서버로부터 최대 1024바이트까지 데이터를 받아서 raw_data 변수에 저장
                if not raw_data: break #데이터가 없으면 반복문 종료

                QThread.msleep(100) # 잠시 대기 // 100ms(1초) 쉬기 -> cpu 과부하 방지를 위해서,,

                #raw_data를 UTF-8로 디코딩해서 문자열로 변환 후 decoded_lines에 저장
                decoded_lines = raw_data.decode('utf-8').strip().split('\n') # byte 형태 -> str 형태로 / 공백, 줄바꿈 제거/ 문자열 쪼갬
                for line in decoded_lines:# decoded_lines 안에 있는 데이터를 하나씩 꺼내서 line으로 넣는다.
                    line = line.strip() # line 앞뒤 공백 제거
                    if not line: continue # 빈줄이면 건너뛰고 계속 진행

                    #데이터 로직 처리 (조건문과 분기) / 새로고침인지 , 실시간 값인지 구분,,

                    if line.startswith("REQ_DATA:"): #line이 "REQ_DATA:" 로 시작하면 아래 코드 실행
                        try:
                            pure_data = line.replace("REQ_DATA:", "") #REQ_DATA: 부분을 제거-> 실제 데이터만 남긴다.
                            t_str, h_str = pure_data.split(",") # ,를 기준으로 문자열 나눔 -> 앞은 t_str, 뒤는 h_str에 저장

                            self.refresh_received.emit(int(t_str), int(h_str)) # 신호(Signal)를 발생 -> 데이터 전달
                        except ValueError: #값 변환 중 오류가 발생하면
                            continue # 이 줄은 버리고, 다음 줄 실행

                    #if line.startswith("REQ_DATA:")가 false 일때만 elif 검사 실시
                    elif "," in line and not line.startswith("REQ"): # , 가 포함되어 있고, REQ로 시작하지 않으면(둘 다 true이면)
                        try:
                            t_str, h_str = line.split(",")
                            self.data_received.emit(int(t_str), int(h_str)) #실시간 온습도 데이터를 UI에 전달
                            log_manager.log_server_data(f"DATA_REC_STREAM -> 온도: {t_str} °C, 습도: {h_str} %")#로그 남김
                        except ValueError:
                            continue
        except Exception: # 거의 모든 오류를 상속 받음
            print("오류")
            pass # 아무것도 하지 마라
        finally: # 반드시 close 해줘야 함. 이 부분에 작성된 코드는 무조건 실행됨.
            if self.client_socket: self.client_socket.close()

##################################################################################################

class AnalysisWindow(QtWidgets.QDialog): # Class 생성 : Qt의 dialog창을 상속 받는다

    #1. UI 생성 : 온습도 뱐화 그래프 창 (로그 분석 창)
    def __init__(self, parent=None):# 생성자
        super().__init__(parent) # 부모창인 Qdialog를 먼저 생성하고 초기화
        self.setWindowTitle("📊 THM 온습도 이력 모니터") # 창의 제목 설절
        self.setFixedSize(960, 680) # 창의 크기 설정

        main_layout = QtWidgets.QVBoxLayout(self) # Vertical 방향으로 La  yout
        filter_layout = QtWidgets.QHBoxLayout() #Horizontal 방향으로 Layout

        lbl_date = QtWidgets.QLabel("📅 조회 날짜:")
        lbl_date.setStyleSheet("font-weight: bold; font-size: 11pt;")
        filter_layout.addWidget(lbl_date)

        self.start_date = QtWidgets.QDateEdit(self) # 날짜 선택 위젯 생성 후 저장
        self.start_date.setStyleSheet("font-size: 11pt; padding: 3px;")
        self.start_date.setCalendarPopup(True)
        self.start_date.setDate(QDate.currentDate())
        filter_layout.addWidget(self.start_date)

        lbl_time = QtWidgets.QLabel("⏰ 범위 설정:")
        lbl_time.setStyleSheet("font-weight: bold; font-size: 11pt;")
        filter_layout.addWidget(lbl_time)

        self.start_time = QtWidgets.QTimeEdit(self) #사용자가 선택한 시작 시간
        self.start_time.setStyleSheet("font-size: 11pt; padding: 3px;")
        self.start_time.setDisplayFormat("HH:mm")
        self.start_time.setTime(QTime(10, 30)) # 시작 시간 기본값 = 10:30
        filter_layout.addWidget(self.start_time) #시간 선택기를 화면에 표시

        filter_layout.addWidget(QtWidgets.QLabel("~")) # ~ 표시

        self.end_time = QtWidgets.QTimeEdit(self) # 사용자가 선택한 종료 시간
        self.end_time.setStyleSheet("font-size: 11pt; padding: 3px;")
        self.end_time.setDisplayFormat("HH:mm")
        self.end_time.setTime(QTime(18, 20)) # 종료 시간 기본 값 = 18:20
        filter_layout.addWidget(self.end_time) #시간 선택기를 화면에 표시
        main_layout.addLayout(filter_layout)

        self.fig = Figure(figsize=(9, 5), dpi=100) # figure 생성 (빈 도화지) 실제 크기 = 900*500
        self.canvas = FigureCanvas(self.fig) # fugure -> FigureCanvas -> QWidget
        self.canvas.setFixedSize(900, 500) #그래프 표시 영역 크기 고정
        main_layout.addWidget(self.canvas) # 그래프 캔버스를 메인 레이아웃에 추가

        self.btn_start_stream = QtWidgets.QPushButton("🔍 조건 범위 로그 분석 및 그래프 출력", self)
        self.btn_start_stream.setStyleSheet(
            "font-weight: bold; font-size: 12pt; background-color: #2C3E50; color: white;") # 버튼 디자인 설정
        self.btn_start_stream.setMinimumHeight(45) #버튼 크기 : 최소 높이 45픽셀
        self.btn_start_stream.clicked.connect(self.run_analysis) # clicked 신호 -> 연결 -> run_ananlysis 실행
        main_layout.addWidget(self.btn_start_stream) # 버튼을 메인 레이아웃에 추가

        # 로그 파일에서 읽어온 데이터를 저장할 공간을 미리 준비하는 코드 // Python에서 []는 빈 리스트(empty list)
        self.all_times = []
        self.all_temps = []
        self.all_humis = []
###################추가
        # Playback 관련

        self.current_index = 0

        # 화면에 표시할 데이터 개수
        self.window_size = 30

        self.play_timer = QTimer(self)

        self.play_timer.timeout.connect(
            self.update_playback
        )

    #2. 로그 로딩 및 파싱 -> 그래프를 그릴 수 있도록 리스트에 저장
    def load_and_parse_log_files(self):
        # 사용자가 화면에서 선택한 날짜, 시간, 을 가져옴
        target_date_str = self.start_date.date().toPyDate().strftime("%Y-%m-%d") #Qt 날짜 -> python 날짜로 변환 -> 날짜를 문자열로 전환 -> 최종 결과 저장
        s_time = self.start_time.time().toPyTime()
        e_time = self.end_time.time().toPyTime()

        start_filter = datetime.combine(self.start_date.date().toPyDate(), s_time) #datetime.combine: 날짜와 시간 결합 -> ex) 2026-06-19 10:30:00
        end_filter = datetime.combine(self.start_date.date().toPyDate(), e_time)

        # 이전 데이터가 섞이지 않도록 clear(완전 초기화)
        self.all_times.clear()
        self.all_temps.clear()
        self.all_humis.clear()

        # 로그 파일 경로 생성
        log_file_path = os.path.join("log", target_date_str, "server_log.txt")

        if not os.path.exists(log_file_path): # 파일이 존재 하는지.
            QtWidgets.QMessageBox.warning(self, "오류", f"해당 날짜({target_date_str})의 server_log.txt 파일이 없습니다.")
            return # 함수 실행 종료

        try:
            with open(log_file_path, "r", encoding="utf-8") as f:
                lines = f.readlines() # 파일에 모든 내용을 읽어서 리스트 형태로 변환하여 line 변수에 저장 한다.
        except Exception:
            with open(log_file_path, "r", encoding="cp949") as f:
                lines = f.readlines()

        log_pattern = re.compile(r"(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}).*?온도.*?(\d+).*?습도.*?(\d+)")

        for line in lines:
            match = log_pattern.search(line)
            if match:
                log_time = datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S") #match.group(1)을 datetime 객체로 변환
                if start_filter <= log_time <= end_filter: #필터링
                    self.all_times.append(log_time)
                    self.all_temps.append(float(match.group(2))) # 온도 / 실수형으로 변환
                    self.all_humis.append(float(match.group(3))) # 습도

    #3. 그래프 생성(분석 버튼 누르면 -> 실행)
    #교체
    # 사용자가 "그래프 출력"을 눌렀을 때 즉시 실행되는 함수
    def run_analysis(self):

        self.load_and_parse_log_files() #로그 파일 읽기

        if not self.all_temps: #온도 데이터가 비어있는가? = 데이터 없음
            QtWidgets.QMessageBox.information(
                self,
                "알림",
                "선택한 시간 범위에 데이터가 없습니다."
            )

            return

        try:

            self.play_timer.stop() # 기존 애니매이션 중지

            self.current_index = 0 #그래프 재생 위치 초기화

            self.fig.clear() # Figure 전체 초기화

            # 온도 그래프
            self.ax1 = self.fig.add_subplot(
                2,
                1,
                1
            )

            # 습도 그래프
            self.ax2 = self.fig.add_subplot(
                2,
                1,
                2
            )

            #온도 그래프 생성
            self.ax1.plot(
                self.all_times,
                self.all_temps,
                color='red',
                linewidth=2,
                alpha=0.4 #투명도
            )

            #습도 그래프 생성
            self.ax2.plot(
                self.all_times,
                self.all_humis,
                color='blue',
                linewidth=2,
                alpha=0.4
            )

            self.ax1.xaxis.set_major_formatter(
                mdates.DateFormatter('%H:%M') # 시간 표시 형식 2026-06-18 10:30:00-> 10:30
            )

            self.ax2.xaxis.set_major_formatter(
                mdates.DateFormatter('%H:%M')
            )

            # 보통 matplitlib은 위 그래프의 X축을 숨김-> 그래서 강제로 표시
            self.ax1.tick_params(
                axis='x',
                labelbottom=True
            )

            self.ax2.tick_params(
                axis='x',
                labelbottom=True
            )

            # ///// self.fig.autofmt_xdate() //////

            # 그래프를 따라 움직이는 빈 점.
            self.temp_dot, = self.ax1.plot(
                [],
                [],
                'ro',
                markersize=10
            )

            self.humi_dot, = self.ax2.plot(
                [],
                [],
                'bo',
                markersize=10
            )

            self.ax1.set_title(
                "온도 변화 추이"
            )

            self.ax2.set_title(
                "습도 변화 추이"
            )

            # 격자
            self.ax1.grid(True)
            self.ax2.grid(True)

            self.ax1.set_ylabel(
                "온도 (°C)"
            )

            self.ax2.set_ylabel(
                "습도 (%)"
            )

            self.ax2.set_xlabel(
                "시간"
            )

            # y축의 범위
            self.ax1.set_ylim(
                min(self.all_temps) - 2,
                max(self.all_temps) + 2
            )

            self.ax2.set_ylim(
                min(self.all_humis) - 2,
                max(self.all_humis) + 2
            )

            # 초기 화면 크기
            right = min(
                self.window_size,
                len(self.all_times) - 1
            )

            # X축 범위
            self.ax1.set_xlim(
                self.all_times[0],
                self.all_times[right]
            )

            self.ax2.set_xlim(
                self.all_times[0],
                self.all_times[right]
            )

            self.ax1.tick_params(
                axis='x',
                labelbottom=True
            )

            self.ax2.tick_params(
                axis='x',
                labelbottom=True
            )

            for label in self.ax1.get_xticklabels():
                label.set_visible(True)

            self.fig.tight_layout()

            #실제 화면에 그림 출력
            self.canvas.draw()

            self.play_timer.start(
                1000
            ) # 1000ms = 1초 ,, 마다 update_playback() 실행

        except Exception as e:

            QtWidgets.QMessageBox.critical(
                self,
                "분석 에러",
                str(e)
            )

    # 애니메이션 엔진
    def update_playback(self):

        try:

            # 종료 조건 : 모든 데이터의 재생이 끝났는가??
            if self.current_index >= len(
                    self.all_temps # 전체 온도데이터 리스트의 길이
            ):
                self.play_timer.stop() # 조건이 참이면, QTimer 중지

                return # 함수 즉시 종료

            # 현재 프레임의 데이터 가져오기
            # 현재 온도 가져오기
            temp = self.all_temps[
                self.current_index # 현재 재생 위치
            ]

            ## 현재 습도 가져오기
            humi = self.all_humis[
                self.current_index
            ]

            #현재 시간 가져오기
            current_time = self.all_times[self.current_index]

            #시간과 온도 1:1 대응 시켜 점 이 시간에 흐름에 따라 이동
            self.temp_dot.set_data(
                [current_time],
                [temp]
            )

            #시간과 습도 1:1 대응 시켜 점 이 시간에 흐름에 따라 이동
            self.humi_dot.set_data(
                [current_time],
                [humi]
            )

            # 그래프의 보이는 구간 계산
            # 왼쪽 범위 계산 : 왼쪽이 0보다 작아지지 않도록
            # max= 가장 큰 값 반환
            left = max(
                0,
                self.current_index - self.window_size
            )

            #오른쪽 범위 계산 : 리스트의 마지막 인덱스를 넘지 않도록
            #min = 작은 값 반환
            right = min(
                len(self.all_times) - 1,
                self.current_index + self.window_size
            )

            #계산된 인덱스 = 실제 시간 값으로 변환 -> X축 표시
            left_time = self.all_times[left]
            right_time = self.all_times[right]

            # X축 이동
            self.ax1.set_xlim(
                left_time,
                right_time
            )

            self.ax2.set_xlim(
                left_time,
                right_time
            )

            self.canvas.draw_idle() #.draw_idle(): 캔버스를 다시 그리도록 요청하는 메서드

            self.current_index += 1 #QTimer가 이 함수를 반복 호출할 때마다 그래프가 한 칸씩 전진

        except Exception as e:

            print(
                f"Playback Error : {e}"
            )

            self.play_timer.stop()
###################################################################################################

class TempHumidityMonitor(QtWidgets.QMainWindow): # 온습도 프로그램의 메인 창
    def __init__(self):
        super().__init__()
        self.ui = uic.loadUi('main_window.ui', self) # Qt designer 로 만든 파일을 읽는다.
        ##################################
        # 큐 초기화 (모두 동일하게 20개 유지)
        self.temp_queue = deque(maxlen=20)
        self.humi_queue = deque(maxlen=20)
        self.time_queue = deque(maxlen=20)  # 밖으로 뺌

        container = self.findChild(QtWidgets.QWidget, 'graph_container')
        if container:
            layout = QtWidgets.QVBoxLayout(container)
            layout.setContentsMargins(0, 0, 0, 0)
            self.fig = Figure(figsize=(5, 2), dpi=100)
            self.canvas = FigureCanvas(self.fig)
            layout.addWidget(self.canvas)
            self.ax = self.fig.add_subplot(111)
            self.line1, = self.ax.plot([], [], 'r-o', label='온도')
            self.line2, = self.ax.plot([], [], 'b-o', label='습도')
            self.ax.legend(loc='upper left', fontsize='small')
            self.ax.grid(True)
            container.setLayout(layout)

        ####################################
        # JSON 방식 설정 파일 읽기
        self.config_file_path = os.path.join("config", "config.json")
        try:
            with open(self.config_file_path, "r", encoding="utf-8") as f: # 설정 파일을 읽기 모드로 연다
                config = json.load(f) #일 객체(f)를 읽어와서 파이썬의 딕셔너리(Dictionary) 형태로 변환
                self.server_ip = config["NETWORK"]["SERVER_IP"]
                self.server_port = int(config["NETWORK"]["SERVER_PORT"]) #포트 번호를 가져와서 정수(int)로 변환
        except (FileNotFoundError, KeyError, json.JSONDecodeError) as e:
            print(f"설정 파일 로드 실패: {e}")
            # 필요시 기본값 설정 또는 프로그램 종료 처리
            self.server_ip = "127.0.0.1"
            self.server_port = 5000

        self.lbl_fan_img.setPixmap(QPixmap(os.path.join('images', 'fan.png')).scaled(120, 120))
        self.lbl_heater_img.setPixmap(QPixmap(os.path.join('images', 'heater.png')).scaled(120, 120))

        self.btn_analysis.setEnabled(True) #버튼 활성화: 분석 버튼 사용 가능

        self.btn_refresh.clicked.connect(self.on_refresh_button_clicked) #btn_refresh를 클릭->on_refresh_button_clicked 함수 호출 (서버 데이터 새로고침)
        self.btn_analysis.clicked.connect(self.on_analysis_button_clicked) #btn_analysis를 클릭->on_analysis_button_clicked 함수 호출 (분석창 열기)

        self.worker = NetworkWorker(self.server_ip, self.server_port) #TCP 통신 전담
        self.worker.data_received.connect(self.process_received_data) #10초마다 데이터 받음
        self.worker.refresh_received.connect(self.process_refresh_data) # 새로고침 버튼 누르면 그 즉시 최신 데이터 받음
        self.worker.start()

        self.statusBar().showMessage("✅ THM 모니터링 시스템 준비 완료 (10초 주기)")

    def process_received_data(self, temp, humi):

        ##############################
        # 1. 데이터 저장
        self.temp_queue.append(temp)
        self.humi_queue.append(humi)
        self.time_queue.append(datetime.now())

        # 2. UI 갱신
        self.lbl_temp.setText(f"온도: {temp} °C")
        self.lbl_humi.setText(f"습도: {humi} %")
        self.set_fan_heater(temp)
        self.statusBar().showMessage(f"⏳ 정기 업데이트 완료 (자동 수신: {temp}°C / {humi}%)")

        # 3. 그래프 갱신
        self.update_graph()

    def update_graph(self):

        if len(self.time_queue) < 2:
            return

        try:
            self.ax.cla()  # 기존 축을 지우고 새로 그림 (훨씬 안전함)
            self.ax.plot(list(self.time_queue), list(self.temp_queue), 'r-o', label='온도')
            self.ax.plot(list(self.time_queue), list(self.humi_queue), 'b-o', label='습도')
            self.ax.legend(loc='upper left', fontsize='small')
            self.ax.grid(True)
            self.ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))

            self.canvas.draw_idle()
        except Exception as e:
            print(f"그래프 렌더링 오류: {e}")
        ##############################

    def process_refresh_data(self, temp, humi):
        # 1. 수동 새로고침 시에도 큐에 데이터를 넣어 그래프에 반영
        self.temp_queue.append(temp)
        self.humi_queue.append(humi)
        self.time_queue.append(datetime.now())

        # 2. UI 갱신 (라벨)
        self.lbl_temp.setText(f"온도: {temp} °C")
        self.lbl_humi.setText(f"습도: {humi} %")

        # 3. 제어 상태 업데이트
        self.set_fan_heater(temp)

        # 4. 그래프 즉시 갱신
        self.update_graph()

        # 5. 상태바 알림
        self.statusBar().showMessage(f"⚡ [즉시 동기화] 최신 계측값 반영됨 ({temp}°C / {humi}%)")
    def set_fan_heater(self, temp):
        led_style_template = "background-color: {color}; border-radius: 5px; min-height: 20px;"
        if temp >= 26:
            fan_color, heater_color = "green", "red"
        elif temp <= 10:
            fan_color, heater_color = "red", "green"
        else:
            fan_color, heater_color = "blue", "blue"
        self.lbl_fan_led.setStyleSheet(led_style_template.format(color=fan_color))
        self.lbl_heater_led.setStyleSheet(led_style_template.format(color=heater_color))

    def on_refresh_button_clicked(self):
        self.statusBar().showMessage("🔄 즉시 동기화 요청 중...")
        self.worker.force_refresh()

    def on_analysis_button_clicked(self):
        if hasattr(self, "analysis_dialog"):
            if self.analysis_dialog.isVisible():
                self.analysis_dialog.raise_()
                self.analysis_dialog.activateWindow() # 키도드 입력 받는 창
                return

        self.analysis_dialog = AnalysisWindow(self) # 위 조건 통과 실패시 새로운 AnalysisWindow 생성
        self.analysis_dialog.show()

    def closeEvent(self, event):
        if self.worker.isRunning(): #만약 worker가 실행 중이라면
            self.worker.is_running = False
            self.worker.quit() #스레드를 멈춰라
            self.worker.wait() #스레드가 완전히 끝날 때까지 기다림
        event.accept() #종료 허용

###############################################################################################
# 메인 실행부
if __name__ == '__main__':
    # GPU 렌더링 관련 충돌 방지 (그래픽 드라이버 호환성 해결)
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_ShareOpenGLContexts)
    app = QtWidgets.QApplication(sys.argv) #
    monitor = TempHumidityMonitor() #
    monitor.show() #
    sys.exit(app.exec_()) #