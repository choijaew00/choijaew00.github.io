# 라이브러리 Import 영역
import sys
import os
import socket #TCP/IP 통신 담당
import configparser #config.ini 읽기
from errno import EWOULDBLOCK, EAGAIN
from PyQt5 import QtWidgets, uic
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import QThread, pyqtSignal

from log import log_manager #로그 저장(접속로그, 사용자 행동 로그, 오류 로그)

# ============================================================================
# [NetworkWorker 클래스]_1. UI 직원, 2. 통신 직원
# ============================================================================
class NetworkWorker(QThread):
    data_received = pyqtSignal(int, int) # signal 영역 (통신 thread -> UI)
    log_requested = pyqtSignal(str) # 통신 thread -> 로그창 -메시지 전달

    def __init__(self, ip, port): # TCP 서버 연결
        super().__init__()
        self.server_ip = ip
        self.server_port = port
        self.client_socket = None
        self.is_running = True

    def force_refresh(self): #수동 새로고침 기능
        """사용자가 새로고침을 누르면 서버에 신호를 보내고 즉시 받아옵니다."""
        if self.client_socket is None:
            return

        try:
            self.log_requested.emit("🔄 서버에 최신 데이터 즉시 요청 중 (REQ 발송)...")

            # 1. 서버에게 "나 지금 새로고침 눌렀으니 데이터 줘!" 하고 REQ 패킷을 던짐.
            self.client_socket.sendall(b"REQ\n")

            # 2. 서버가 응답을 바로 줄 테니 소켓 버퍼를 읽는다.
            # (잠시 논-블로킹으로 전환하여 안전하게 가로챔)
            self.client_socket.setblocking(False)
            raw_data = self.client_socket.recv(1024)
            self.client_socket.setblocking(True)

            if raw_data:
                decoded_string = raw_data.decode('utf-8')
                temp_str, humi_str = decoded_string.split(",")
                self.data_received.emit(int(temp_str), int(humi_str))
                self.log_requested.emit("🎯 수동 새로고침 즉시 반영 완료!")
            else:
                self.log_requested.emit("새로고침 실패: 서버 닫힘")

        except socket.error as e:
            if e.errno in (EWOULDBLOCK, EAGAIN):
                # 서버가 REQ를 받고 처리하는 수 밀리초의 찰나의 순간에 버퍼가 잠시 비었을 때의 예외 처리
                self.log_requested.emit("새로고침 요청 전송 완료. 서버의 즉시 응답을 대기합니다.")
            else:
                self.log_requested.emit(f"수동 새로고침 중 소켓 오류: {e}")
            if self.client_socket:
                self.client_socket.setblocking(True)
        except Exception as e:
            self.log_requested.emit(f"수동 새로고침 오류: {e}")
            if self.client_socket:
                self.client_socket.setblocking(True)

    def run(self):
        """10초 주기로 들어오는 자동 데이터 수신 루틴"""
        try:
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.settimeout(3.0)

            self.log_requested.emit(f"서버 접속 시도 중... ({self.server_ip}:{self.server_port})")
            self.client_socket.connect((self.server_ip, self.server_port))
            self.log_requested.emit("서버 연결 성공! 10초 주기 자동 수신 및 수동 새로고침 대기 시작.")

            self.client_socket.settimeout(None)

            while self.is_running:
                # 여기서 가만히 기다리다가 10초 주기로 오거나,
                # 내가 강제로 REQ 날려서 서버가 즉시 던져준 데이터를 받습니다.
                raw_data = self.client_socket.recv(1024)
                if not raw_data:
                    self.log_requested.emit("서버가 연결을 종료했습니다.")
                    break

                decoded_string = raw_data.decode('utf-8')
                temp_str, humi_str = decoded_string.split(",")
                self.data_received.emit(int(temp_str), int(humi_str))

        except Exception as e:
            self.log_requested.emit(f"통신 쓰레드 오류 발생: {e}")
        finally: # 프로그램 종료시 소켓 정리
            if self.client_socket:
                self.client_socket.close()
            self.log_requested.emit("통신 쓰레드가 안전하게 종료되었습니다.")


# ============================================================================
# [메인 UI 창 클래스] - 기존과 동일
# ============================================================================
class TempHumidityMonitor(QtWidgets.QMainWindow): # 메인 화면
    def __init__(self):
        super().__init__()
        uic.loadUi('main_window.ui', self) #ui 생성 -> Qt designer 로 만든 main_window.ui 불러오기

        self.config_file_path = os.path.join("config", "config.ini")
        config = configparser.ConfigParser()
        config.read(self.config_file_path, encoding="utf-8") # config읽기:설정파일 읽기
        self.server_ip = config.get("NETWORK", "SERVER_IP")
        self.server_port = config.getint("NETWORK", "SERVER_PORT")

        log_manager.log_server_data(f"ConfigParser 로드 완료 -> IP: {self.server_ip}, PORT: {self.server_port}")

        #이미지 로딩
        self.lbl_fan_img.setPixmap(QPixmap('fan.png').scaled(120, 120))
        self.lbl_heater_img.setPixmap(QPixmap('heater.png').scaled(120, 120))
        self.btn_refresh.clicked.connect(self.on_refresh_button_clicked) # 버튼 이벤트 연결 -> 버튼 클릭 시 함수 실행

        log_manager.log_server_data("시스템이 성공적으로 시작되었습니다.")

        self.worker = NetworkWorker(self.server_ip, self.server_port) # 통신 thread 생성
        self.worker.data_received.connect(self.process_received_data)
        self.worker.log_requested.connect(log_manager.log_server_data)
        self.worker.start()

    def process_received_data(self, temp, humi): # data 처리 영역
        self.lbl_temp.setText(f"온도: {temp} °C")
        self.lbl_humi.setText(f"습도: {humi} %")
        fan_status, heater_status = self.set_fan_heater(temp)
        log_message = f"데이터 적용 완료 ➡️ 온도: {temp}°C | 습도: {humi}%"
        log_manager.log_server_data(log_message)

    def set_fan_heater(self, temp): # 온도에 따라 상태 결정
        led_style_template = "background-color: {color}; border-radius: 5px; min-height: 20px;"
        if temp >= 26:
            fan_color, heater_color = "green", "red"
            fan_state, heater_state = "ON", "OFF"
        elif temp <= 10:
            fan_color, heater_color = "red", "green"
            fan_state, heater_state = "OFF", "ON"
        else:
            fan_color, heater_color = "blue", "blue"
            fan_state, heater_state = "OFF", "OFF"

        self.lbl_fan_led.setStyleSheet(led_style_template.format(color=fan_color))
        self.lbl_heater_led.setStyleSheet(led_style_template.format(color=heater_color))
        return fan_state, heater_state

    def on_refresh_button_clicked(self): # 사용자 이벤트 처리 영역 : 새로고침 버튼 처리 //
        log_manager.log_user_action("사용자가 [새로고침] 버튼을 클릭했습니다. 서버에 최신 데이터를 즉시 요구합니다.")
        self.worker.force_refresh()

    def closeEvent(self, event): # 종료 처리 영역 : 프로그램 종료 시 정리
        if self.worker.isRunning():
            self.worker.is_running = False
            self.worker.quit()
            self.worker.wait()
        event.accept()


# 프로그램 시작 영역
if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    monitor = TempHumidityMonitor()
    monitor.show()
    sys.exit(app.exec_())