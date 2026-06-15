import socket #TCP/IP 통신 기능
import time
import random #랜덤값 생성
import threading #멀티스레드

# 전역 변수로 최신 온습도 저장 (센서가 1초마다 여기 업데이트함)
# 전역 변수 = 어디서든 접근 가능한 변수
current_temp = 25
current_humi = 50


def virtual_sensor(): # 가상 센서 함수
    """실제 장비 대신 실제 센서 하드웨어처럼 1초에 한 번씩 온습도를 측정해서 저장하는 쓰레드"""
    global current_temp, current_humi
    while True: # 계속 측정 (무한 반복)
        current_temp = random.randint(15, 30) # 온도 생성
        current_humi = random.randint(40, 70) # 습도 센서
        # 프린트 로그는 1초마다 너무 많이 찍히므로 생략하거나 주석 처리합니다.
        time.sleep(1.0) # 1초 대기 = 1초 마다 반복


# 가상 센서 가동
sensor_thread = threading.Thread(target=virtual_sensor, daemon=True)
sensor_thread.start() #센서 시작

# 소켓 서버 시작
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # TCP 서버 생성
server_socket.bind(('127.0.0.1', 5000)) # 서버 주소 설정
server_socket.listen(1) # 연결 대기

print("🏢 [가상 장비 서버] 클라이언트 연결 대기 중 (127.0.0.1:5000)...") # 콘솔 출력

# (accept: 누가 접속할 때 까지 대기) -> main.py실행 -> 127.0.0.1, 5000연결 -> accept 성공
while True: # 서버 메인 루프
    client_socket, addr = server_socket.accept() #클라이언트 대기(= 통신용 소켓)
    print(f"🤝 클라이언트 접속 완료: {addr}") #(addr : 접속한 상대 정보)

    # 클라이언트가 읽어갈 수 있도록 논-블로킹 설정 (요청이 들어왔는지 수시로 확인하기 위함)
    client_socket.setblocking(False)

    last_sent_time = time.time() # 마지막 전송 시간 (현재 시간 저장)

    try:
        while True: # 클라이언트 연결 유지
            current_time = time.time()

            # 클라이언트가 "REQ"(새로고침) 신호를 보냈는지 체크 // req : 지금 데이터 보내달라는 요청 (새로고침)
            try:
                data = client_socket.recv(1024) # 클라이언트 메시지 읽기
                if data:
                    request_msg = data.decode('utf-8').strip()
                    if request_msg == "REQ": # 새로고침 요청
                        print("⚡ [수동 요청 수신] 클라이언트가 새로고침을 눌렀습니다! 즉시 전송합니다.")
                        data_message = f"{current_temp},{current_humi}" # 데이터 생성
                        client_socket.sendall(data_message.encode('utf-8')) # 전송
                        last_sent_time = current_time  # 10초 타이머 초기화
                        continue
                else:
                    # 데이터가 없는데 연결이 끊긴 경우
                    print("클라이언트 연결 종료")
                    break # 통신 종료
            except BlockingIOError:
                # 클라이언트가 아무 명령도 안 보냈으면 그냥 통과 (정상 상태)
                pass

            #  수동 요청이 없더라도 10초가 지나면 자동으로 전송
            if current_time - last_sent_time >= 10.0:
                print("⏰ [정기 자동 송신] 10초 주기 도달. 데이터를 전송합니다.")
                data_message = f"{current_temp},{current_humi}"
                client_socket.sendall(data_message.encode('utf-8'))
                last_sent_time = current_time

            # CPU 과부하 방지를 위한 쉬는 시간
            time.sleep(0.1)

    except Exception as e:
        print(f"서버 루프 오류: {e}")
    finally:
        client_socket.close()
        print("클라이언트 소켓 닫힘. 다음 접속 대기...")

