import sys
import random
from PyQt5 import QtWidgets, uic
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import QTimer

# [사수분 피드백 반영] 우리가 만든 log.py 모듈에서 로깅 매니저를 가져옵니다.
from log import log_manager


class TempHumidityMonitor(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        uic.loadUi('main_window.ui', self)

        # ------------------------------------------------------------------------
        # [변수 초기화 단락]
        # ------------------------------------------------------------------------
        self.current_temp = 0
        self.current_humi = 0

        # ------------------------------------------------------------------------
        # [UI 및 이미지 세팅 단락]
        # ------------------------------------------------------------------------
        self.lbl_fan_img.setPixmap(QPixmap('fan.png').scaled(120, 120))
        self.lbl_heater_img.setPixmap(QPixmap('heater.png').scaled(120, 120))

        # ------------------------------------------------------------------------
        # [이벤트 바인딩 및 타이머 세팅 단락]
        # ------------------------------------------------------------------------
        # 새로고침 버튼을 누르면 수동 갱신 함수 실행
        self.btn_refresh.clicked.connect(self.on_refresh_button_clicked)

        # 5초 자동 타이머 세팅
        self.timer = QTimer(self)
        self.timer.setInterval(5000)  # 5초
        self.timer.timeout.connect(self.on_timer_timeout)
        self.timer.start()

        # 프로그램 실행 시 최초 1회 화면 자동 갱신
        self.refresh_data()
        log_manager.log_server_data("시스템이 성공적으로 시작되었습니다.")

    # ============================================================================
    # [이벤트 핸들러 기능]
    # ============================================================================
    def on_refresh_button_clicked(self):
        """사용자가 새로고침 버튼을 누르는 '행동'을 했을 때 발생하는 이벤트 함수"""
        # [사용자 로그 분리 기록] 사용자가 수동으로 버튼을 눌렀음을 따로 남깁니다.
        log_manager.log_user_action("사용자가 [새로고침] 버튼을 클릭하여 수동 갱신을 요청했습니다.")
        self.refresh_data()

    def on_timer_timeout(self):
        """5초 자동 타이머 주기가 완료되었을 때 발생하는 이벤트 함수"""
        # 자동 타이머는 사용자가 누른 게 아니므로 사용자 로그를 남기지 않고 데이터만 갱신합니다.
        self.refresh_data()

    # ============================================================================
    # [데이터 수집 관련 기능]
    # ============================================================================
    def get_randdata(self):
        """가상의 온습도 데이터를 생성하는 함수"""
        temp = random.randint(0, 35)
        humi = random.randint(30, 80)
        return temp, humi

    # ============================================================================
    # [화면 표시 및 출력 제어 관련 기능]
    # ============================================================================
    def update_condition_label(self, temp, humi):
        """UI 라벨의 텍스트를 최신 데이터로 업데이트하는 함수"""
        self.lbl_temp.setText(f"온도: {temp} °C")
        self.lbl_humi.setText(f"습도: {humi} %")

    def set_fan_heater(self, temp):
        """온도 값에 따라 선풍기와 히터의 LED 색상을 제어하고 현재 상태를 반환하는 함수"""
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

    # ============================================================================
    # [메인 컨트롤 로직]
    # ============================================================================
    def refresh_data(self):
        """온습도 데이터를 갱신하고 상태를 파악하여 서버 로그로 전송하는 메인 핵심 함수"""
        # 1. 데이터를 수집
        self.current_temp, self.current_humi = self.get_randdata()

        # 2. 화면 글자를 업데이트
        self.update_condition_label(self.current_temp, self.current_humi)

        # 3. 온도 기반으로 LED 장치 출력 제어 및 현재 상태 변수 받기
        fan_status, heater_status = self.set_fan_heater(self.current_temp)

        # 4. [서버 로그 분리 기록] 수집된 순수 데이터와 장비 제어 상태는 서버 로그 파일에만 보냅니다.
        log_message = f"데이터 수신 결과 -> 온도: {self.current_temp}°C | 습도: {self.current_humi}% | 선풍기: {fan_status} | 히터: {heater_status}"
        log_manager.log_server_data(log_message)


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    monitor = TempHumidityMonitor()
    monitor.show()
    sys.exit(app.exec_())