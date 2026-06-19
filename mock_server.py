import socket
import time
import random


def run_mock_server():
    server_ip = "127.0.0.1"
    server_port = 5000

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        server_socket.bind((server_ip, server_port))
        server_socket.listen(1)
        print(f"📡 [THM SERVER] {server_ip}:{server_port} 에서 연동 대기 중...")
    except Exception as e:
        print(f"❌ 서버 바인딩 실패: {e}")
        return

    try:
        while True:
            client_socket, addr = server_socket.accept()
            print(f"✅ 클라이언트 접속 완료: {addr}")
            client_socket.setblocking(False)  # 비동기 넌블로킹 제어 활성화

            # 초기 가상 데이터 생성
            current_temp = random.randint(15, 28)
            current_humi = random.randint(40, 65)

            last_send_time = time.time()
            last_generate_time = time.time()

            try:
                while True:
                    current_time = time.time()

                    # 1️⃣ [규격 1] 1초에 한 번씩 새로운 가상의 온습도 값을 갱신 (내부 최신화)
                    if current_time - last_generate_time >= 1.0:
                        current_temp = random.randint(15, 28)
                        current_humi = random.randint(40, 65)
                        last_generate_time = current_time
                        print(f" 내부 계측 갱신 (기다리는 중...) -> 온도: {current_temp} °C, 습도: {current_humi} %")

                    # 2️⃣ [규격 3] 클라이언트가 새로고침 버튼을 누르면 '그 즉시' 최신값 반환
                    try:
                        data = client_socket.recv(1024)
                        if data:
                            request_str = data.decode('utf-8').strip()
                            if "REQ" in request_str:
                                # 1초 주기로 생성되고 있던 가장 최신의 데이터를 즉시 묶어서 송신
                                reply = f"REQ_DATA:{current_temp},{current_humi}\n"
                                client_socket.sendall(reply.encode('utf-8'))
                                print(f"⚡ [수동 새로고침 즉시 응답] -> 온도: {current_temp} °C, 습도: {current_humi} %")
                                # 수동 송신이 완료되었으므로, 정기 송신 타이머를 현재 시간으로 동기화
                                last_send_time = current_time
                    except BlockingIOError:
                        pass
                    except ConnectionResetError:
                        break

                    #  3 ️⃣ [규격 2] 10초에 한 번씩 주기적으로 메인화면에 자동 송신
                    if current_time - last_send_time >= 10.0:
                        packet = f"{current_temp},{current_humi}\n"
                        try:
                            client_socket.sendall(packet.encode('utf-8'))
                            print(f"⏳ [10초 주기 정기 송신] -> 온도: {current_temp} °C, 습도: {current_humi} %")
                        except (ConnectionResetError, ConnectionAbortedError):
                            break
                        last_send_time = current_time

                    # CPU 과점유 방지를 위한 미세 대기 루프 (0.05초 단위 초정밀 탐색)
                    time.sleep(0.05)

            except Exception as e:
                print(f"⚠️ 통신 세션 예외 발생: {e}")
            finally:
                client_socket.close()
                print("🔄 클라이언트 연결 종료, 차기 세션 대기.\n")

    except KeyboardInterrupt:
        print("\n🛑 서버가 사용자에 의해 안전하게 중단되었습니다.")
    finally:
        server_socket.close()


if __name__ == "__main__":
    run_mock_server()