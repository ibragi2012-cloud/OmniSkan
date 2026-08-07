import cv2
import numpy as np
import math
import time
import socket
import threading
import os
from datetime import datetime
from ultralytics import YOLO, settings

# === ГЛОБАЛЬНЫЕ ТАКТИЧЕСКИЕ ПЕРЕМЕННЫЕ ===
current_servo_angle = 90  # Стартовый угол сервопривода
current_cmd = "STOP"      # Текущая команда движения для Arduino
ai_detected_object = "NOTHING SPECIAL"
screenshot_alert_until = 0.0  # Таймер вывода плашки о сохранении кадра

# Автоматическое создание папки для скриншотов на Рабочем столе
DESKTOP_PATH = r"C:\Users\ibrag\Desktop"
SAVE_DIR = os.path.join(DESKTOP_PATH, "OmniScan_Screenshots")
if not os.path.exists(SAVE_DIR):
    os.makedirs(SAVE_DIR)

# Скоростные константы под вашу ПИД-прошивку Arduino Uno
TARGET_LINEAR_SPEED = 350   # Чуть меньше максимума (максимум 400 мм/с)
TARGET_ANGULAR_SPEED = 4500 # Скорость разворота на месте в мрад/с

ROBOT_IP = "192.168.4.1"
TCP_PORT = 8888

# Отключаем онлайн-синхронизацию весов для мгновенного старта YOLOv8 в оффлайне
settings.update({'sync': False, 'uuid': 'offline'}) 
print("[SYSTEM]: Загрузка продвинутой обученной ИИ-модели YOLOv8n.pt...")
model = YOLO('yolov8n.pt', task='detect')

# Переменные для обмена данными между видео и ИИ-потоком
latest_frame = None
processed_frame = None
frame_lock = threading.Lock()
global_tcp_socket = None

# --- 1. ВЫСОКОСКОРОСТНОЙ ПОСТОЯННЫЙ СОКЕТ-ПОТОК (ОТКЛИК < 5 МС) ---
def tcp_sender_loop():
    global current_cmd, current_servo_angle, global_tcp_socket
    print("[+] Высокоскоростной постоянный TCP-канал запущен.")
    
    while True:
        try:
            if global_tcp_socket is None:
                global_tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                global_tcp_socket.settimeout(0.5)
                global_tcp_socket.connect((ROBOT_IP, TCP_PORT))
                global_tcp_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                print("[+] Железобетонное Wi-Fi соединение с ESP32-C3 установлено!")
            
            cmd_string = f"SERVO {int(current_servo_angle)}\n{current_cmd}\n"
            global_tcp_socket.sendall(cmd_string.encode('utf-8'))
        except Exception:
            if global_tcp_socket:
                try: global_tcp_socket.close()
                except: pass
                global_tcp_socket = None
            time.sleep(0.3)
        time.sleep(0.04)

# --- 2. АСИНХРОННЫЙ ПОТОК НЕЙРОСЕТИ С ЖЕСТКИМ ИСПРАВЛЕНИЕМ ИНДЕКСА [0] ---
def ai_processing_loop():
    global latest_frame, processed_frame, ai_detected_object
    print("[+] Асинхронное ИИ-ядро успешно заведено в фоне.")
    
    while True:
        frame_to_process = None
        with frame_lock:
            if latest_frame is not None:
                frame_to_process = latest_frame.copy()
        
        if frame_to_process is not None:
            yolo_results = model(frame_to_process, imgsz=256, verbose=False) 
            found_target = "NOTHING SPECIAL"

            # ЖЕСТКОЕ ИСПРАВЛЕНИЕ: Добавлен индекс [0] для работы со списком детекции Ultralytics
            if len(yolo_results) > 0 and len(yolo_results[0].boxes) > 0:
                top_box = yolo_results[0].boxes[0] # Берем первый найденный объект на первом кадре
                conf = float(top_box.conf[0])
                cls_id = int(top_box.cls[0])
                label = model.names[cls_id]

                if conf > 0.45 and label != 'floor':
                    found_target = f"{label.upper()} ({int(conf*100)}%)"
                    
                    box_coords = top_box.xyxy.cpu().numpy()[0].astype(int)
                    x1, y1, x2, y2 = box_coords[0], box_coords[1], box_coords[2], box_coords[3]
                    
                    # --- КРАСИВАЯ ДИЗАЙНЕРСКАЯ ОТРИСОВКА ЗАХВАТА ЦЕЛИ ---
                    color = (0, 255, 0) # Ярко-зеленый неоновый цвет
                    thickness = 2
                    length = 20 # Длина угловых засечек прицела
                    
                    cv2.line(frame_to_process, (x1, y1), (x1 + length, y1), color, thickness)
                    cv2.line(frame_to_process, (x1, y1), (x1, y1 + length), color, thickness)
                    cv2.line(frame_to_process, (x2, y1), (x2 - length, y1), color, thickness)
                    cv2.line(frame_to_process, (x2, y1), (x2, y1 + length), color, thickness)
                    cv2.line(frame_to_process, (x1, y2), (x1 + length, y2), color, thickness)
                    cv2.line(frame_to_process, (x1, y2), (x1, y2 - length), color, thickness)
                    cv2.line(frame_to_process, (x2, y2), (x2 - length, y2), color, thickness)
                    cv2.line(frame_to_process, (x2, y2), (x2, y2 - length), color, thickness)
                    
                    label_str = f" TARGET: {label.upper()} [{int(conf*100)}%]"
                    cv2.rectangle(frame_to_process, (x1, max(y1 - 25, 5)), (x1 + len(label_str)*9, max(y1, 30)), (0, 0, 0), -1)
                    cv2.putText(frame_to_process, label_str, (x1, max(y1 - 7, 22)), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1, cv2.LINE_AA)

            ai_detected_object = found_target
            with frame_lock:
                processed_frame = frame_to_process
        
        time.sleep(0.05)

# --- 3. ОСНОВНОЙ ВЫЧИСЛИТЕЛЬНЫЙ ЦИКЛ ОБРАБОТКИ ВИДЕО И КЛАВИАТУРЫ ---
def main():
    global current_cmd, current_servo_angle, ai_detected_object, latest_frame, processed_frame, screenshot_alert_until
    
    threading.Thread(target=tcp_sender_loop, daemon=True).start()
    threading.Thread(target=ai_processing_loop, daemon=True).start()

    camera_index = 1
    cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
    
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1) 
    
    if not cap.isOpened():
        print(f"[-] КРИТИЧЕСКАЯ ОШИБКА: Нет доступа к камере под индексом {camera_index}")
        return

    print("[+] Высокоскоростной USB-видеопоток успешно запущен!")
    cv2.namedWindow("OMNISCAN: INSTANT HUD CENTER")

    print("\n" + "="*50)
    print("[УПРАВЛЕНИЕ MOTORS]: W, S, A, D - Движение (Удержание)")
    print("[УГЛЫ ГОЛОВЫ СЕРВО]: I - Прямо(90) | O - Вбок(20) | P - Прямо(90)")
    print("[ФОТОФИКСАЦИЯ ИИ  ]: Клавиша 'C' - Сделать СКРИНШОТ с ИИ-разметкой на ноутбук")
    print("[ВЫХОД ИЗ КЛИЕНТА ]: Клавиша 'ESC' - Закрыть софт")
    print("="*50 + "\n")

    try:
        while True:
            ret, frame = cap.read()
            if not ret or frame is None:
                continue

            with frame_lock:
                latest_frame = frame
                display_frame = processed_frame.copy() if processed_frame is not None else frame.copy()

            display_frame = cv2.resize(display_frame, (1024, 576))

            # --- ГРАФИЧЕСКИЙ ИНТЕРФЕЙС HUD РАДАРА ВНИЗУ ЭКРАНА ---
            radar_center_x, radar_center_y = 512, 540
            cv2.ellipse(display_frame, (radar_center_x, radar_center_y), (120, 120), 0, 180, 360, (60, 60, 60), 2, cv2.LINE_AA)
            
            angle_rad = math.radians(current_servo_angle)
            beam_len = 100
            bx = int(radar_center_x - beam_len * math.cos(angle_rad))
            by = int(radar_center_y - beam_len * math.sin(angle_rad))
            
            cv2.line(display_frame, (radar_center_x, radar_center_y), (bx, by), (0, 255, 255), 2, cv2.LINE_AA)
            cv2.circle(display_frame, (bx, by), 4, (0, 255, 255), -1)

            # Вывод тактической HUD-панели управления поверх кадра
            cv2.rectangle(display_frame, (10, 10), (560, 95), (0, 0, 0), -1)
            cv2.putText(display_frame, "OMNISCAN INSTANT AI HUB : ONLINE", (20, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1, cv2.LINE_AA)
            cv2.putText(display_frame, f"CURRENT TELEMETRY CMD     : {current_cmd}", (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1, cv2.LINE_AA)
            cv2.putText(display_frame, f"SEMANTIC OBJECT TARGET    : {ai_detected_object}", (20, 72), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 100) if ai_detected_object != "NOTHING SPECIAL" else (140, 140, 140), 1, cv2.LINE_AA)
            
            cv2.rectangle(display_frame, (830, 10), (1014, 38), (0, 0, 0), -1)
            cv2.putText(display_frame, f"SERVO: {int(current_servo_angle)} DEG", (845, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1, cv2.LINE_AA)

            # ВСПЛЫВАЮЩИЙ ИНДИКАТОР УСПЕШНОГО СОХРАНЕНИЯ СНИМКА
            if time.time() < screenshot_alert_until:
                cv2.rectangle(display_frame, (390, 20), (634, 55), (0, 0, 0), -1)
                cv2.rectangle(display_frame, (390, 20), (634, 55), (0, 255, 0), 1)
                cv2.putText(display_frame, "[ SCREENSHOT SAVED ]", (420, 42), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1, cv2.LINE_AA)

            # Отрисовка прицельной сетки
            cv2.drawMarker(display_frame, (512, 288), (0, 165, 255), cv2.MARKER_CROSS, 20, 1, cv2.LINE_AA)

            cv2.imshow("OMNISCAN: INSTANT HUD CENTER", display_frame)
            
            # --- МГНОВЕННАЯ ИМПУЛЬСНАЯ ОТПРАВКА КОМАНД С КЛАВИАТУРЫ ---
            is_any_key_pressed = False
            key = cv2.waitKey(1) & 0xFF
            
            if key == 27: 
                break
            
            # ФУНКЦИЯ ФОТОФИКСАЦИИ ЦЕЛИ (КЛАВИША С)
            elif key == ord('c'):
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"capture_{timestamp}.jpg"
                full_path = os.path.join(SAVE_DIR, filename)
                cv2.imwrite(full_path, display_frame)
                print(f"[+] Снимок успешно сохранен: {full_path}")
                screenshot_alert_until = time.time() + 0.6  
                
            elif key == ord('w'): 
                is_any_key_pressed = True
                current_cmd = f"VEL {TARGET_LINEAR_SPEED} 0" 
            elif key == ord('s'): 
                is_any_key_pressed = True
                current_cmd = f"VEL -{TARGET_LINEAR_SPEED} 0"
            
            # ИСПРАВЛЕНО: Точное соответствие знаков угловой скорости прошивке Arduino Uno
            elif key == ord('a'): 
                is_any_key_pressed = True
                current_cmd = f"VEL 0 {TARGET_ANGULAR_SPEED}"   # Поворот налево (A)
            elif key == ord('d'): 
                is_any_key_pressed = True
                current_cmd = f"VEL 0 -{TARGET_ANGULAR_SPEED}"  # Поворот направо (D)
            
            # Тактическое мгновенное переключение углов головы по вашим 3 кнопкам
            elif key == ord('i'): current_servo_angle = 0
            elif key == ord('o'): current_servo_angle = 120 
            elif key == ord('p'): current_servo_angle = 180  
            
            if not is_any_key_pressed:
                current_cmd = "STOP"
                
    finally:
        if global_tcp_socket: global_tcp_socket.close()
        cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
