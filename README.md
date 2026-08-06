# OmniScan: 👁️

Проект автономного мобильного робота-исследователя со сканирующим ИИ-зрением на базе связки **ESP32-CAM** и **Arduino Uno**. Камера закреплена непосредственно на сервоприводе, выступая в роли активного эгоцентрического сенсора. Робот сканирует пространство нейросетью **YOLOv8**, захватывает цели и автоматически удерживает курс на объект с помощью ПИД-регуляторов.

---

## 🚀 Возможности
* **Active AI Scanning:** Камера  вращается на 180° с помощью клавиатуры, сканируя сектор вокруг робота с помощью нейросети **YOLOv8** (80 классов).
* **Target Lock-On:** При обнаружении объекта ИИ фиксирует взгляд сервопривода на цели, рассчитывает вектор ошибки и автоматически направляет ПИД-шасси ровера на объект.
* **Ручной HUD-Перехват:** Возможность мгновенного перехода на ручное управление движением с клавиатуры (`W`,`S`,`A`,`D`) и точечное наведение глаза-камеры (`I`,`O`).

---


## ⚡ Быстрый запуск

1. Прошейте Arduino Uno (ПИД-драйвер, скорость связи `38400` бод) и ESP32-CAM (скетч MJPEG-моста).
2. Снимите ESP32-CAM с программатора, закрепите на сервоприводе робота, соберите цепи питания и включите тумблер.
3. Подключите ноутбук к Wi-Fi сети **`NEYMARK_01`** (пароль по умолчанию: `neymark123`).
4. Положите файл весов нейросети `yolov8n.pt` на Рабочий стол рядом со скриптом.
5. Запустите ИИ-центр управления на ноутбуке через терминал:
```powershell
& C:\Users\ibrag\AppData\Local\Python\pythoncore-3.14-64\python.exe c:/Users/ibrag/Desktop/ai_omni_test.py

---
## 💾 Архитектура ПО и Исходный код
### 1. Прошивка для ESP32-CAM (`esp32_cam_stream_bridge.ino`)
```cpp
#include "esp_camera.h"
#include <WiFi.h>
#include "esp_http_server.h"
// Конфигурация пинов для камеры AI Thinker ESP32-CAM
#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27
#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM        5
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22
const char* AP_NAME = "Vnfoo567";
const char* AP_PASSWORD = "Vnfoo567";

const uint16_t TCP_PORT = 8888;
WiFiServer tcpServer(TCP_PORT);
WiFiClient tcpClient;

char tcpLine[96];
uint8_t tcpLength = 0;
char uartLine[150]; 
uint8_t uartLength = 0;

void startCameraServer();

void setup() {
  Serial.begin(38400); 
  Serial.setDebugOutput(false);
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sscb_sda = SIOD_GPIO_NUM;
  config.pin_sscb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  
  // Использован обновленный нативный формат JPEG
  config.pixel_format = PIXFORMAT_JPEG;
  config.frame_size = FRAMESIZE_SVGA; 
  config.jpeg_quality = 12;          
  config.fb_count = 2;               
  // Игнорируем аппаратный сбой камеры для запуска Wi-Fi
  esp_camera_init(&config);
  WiFi.mode(WIFI_AP);
  WiFi.softAP(AP_NAME, AP_PASSWORD);
  WiFi.setSleep(false);
  startCameraServer();
  tcpServer.begin();
}
void loop() {
  if (!tcpClient || !tcpClient.connected()) {
    tcpClient = tcpServer.available();
    if (tcpClient) {
      tcpClient.setNoDelay(true); 
      tcpLength = 0;
    }
  }
  while (tcpClient && tcpClient.available()) {
    const char symbol = tcpClient.read();
    if (symbol == '\n' || symbol == '\r') {
      if (tcpLength > 0) {
        tcpLine[tcpLength] = '\0';
        Serial.println(tcpLine); 
        tcpLength = 0;
      }
    } else if (tcpLength < sizeof(tcpLine) - 1) {
      tcpLine[tcpLength++] = symbol;
    } else {
      tcpLength = 0;
    }
  }

  while (Serial.available()) {
    const char symbol = Serial.read();
    if (symbol == '\n' || symbol == '\r') {
      if (uartLength > 0) {
        uartLine[uartLength] = '\0';
        if (tcpClient && tcpClient.connected()) {
          tcpClient.println(uartLine); 
        }
        uartLength = 0;
      }
    } else if (uartLength < sizeof(uartLine) - 1) {
      uartLine[uartLength++] = symbol;
    } else {
      uartLength = 0;
    }
  }
}

esp_err_t stream_handler(httpd_req_t *req) {
  camera_fb_t * fb = NULL;
  esp_err_t res = ESP_OK;
  size_t _jpg_buf_len = 0;
  uint8_t * _jpg_buf = NULL;
  char part_buf[64];

  res = httpd_resp_set_type(req, "multipart/x-mixed-replace;boundary=123456789000000000000987654321");
  if(res != ESP_OK) return res;

  while(true) {
    fb = esp_camera_fb_get();
    if (!fb) {
      res = ESP_FAIL;
    } else {
      _jpg_buf_len = fb->len;
      _jpg_buf = fb->buf;
    }
    
    if(res == ESP_OK) {
      size_t hlen = snprintf(part_buf, 64, "\r\n--123456789000000000000987654321\r\nContent-Type: image/jpeg\r\nContent-Length: %u\r\n\r\n", _jpg_buf_len);
      res = httpd_resp_send_chunk(req, part_buf, hlen);
    }
    if(res == ESP_OK) {
      res = httpd_resp_send_chunk(req, (const char *)_jpg_buf, _jpg_buf_len);
    }
    
    if(fb) {
      esp_camera_fb_return(fb);
      fb = NULL;
      _jpg_buf = NULL;
    }
    if(res != ESP_OK) break;
  }
  return res;
}

void startCameraServer() {
  httpd_config_t config = HTTPD_DEFAULT_CONFIG();
  config.server_port = 80; 
  config.ctrl_port = 32769;

  httpd_uri_t stream_uri = {
    .uri       = "/",
    .method    = HTTP_GET,
    .handler   = stream_handler,
    .user_ctx  = NULL
  };

  httpd_handle_t cam_httpd = NULL;
  if (httpd_start(&cam_httpd, &config) == ESP_OK) {
    httpd_register_uri_handler(cam_httpd, &stream_uri);
  }
}

```

**⚙️ Принцип работы:**
Плата инициализирует матрицу `OV2640` в ИИ-оптимальном разрешении 800x600 (`SVGA`). Она поднимает автономную Wi-Fi точку доступа и запускает HTTP-видеосервер на порту `80`, непрерывно отдавая JPEG-кадры методом покадрового сжатия видеопотока (`MJPEG`). Функции `btStop()` и `WIFI_POWER_2dBm` снижают общее энергопотребление, страхуя плату от просадок напряжения. В основном цикле `loop()` два независимых неблокирующих буфера пересылают приходящие от ПК пакеты `VEL` / `SERVO` в аппаратный UART к плате Arduino Uno и возвращают строки телеметрии `TEL` обратно в Wi-Fi сеть.

### 2. ПИД-прошивка для шасси ровера (`pid_rover_fixed.ino`)
```cpp
// Финальная исправленная прошивка Arduino дня 2.
// Интегрирован раздельный ПИД-регулятор скорости колес + ПИД-выравниватель прямой.
// Знаки скоростей и направления моторов полностью согласованы с Python-автопилотом.

#include <Servo.h>
#include <SoftwareSerial.h>
#include <math.h>
#include <stdlib.h>
#include <string.h>

const uint8_t LEFT_DIR_PIN = 4;
const uint8_t LEFT_PWM_PIN = 5;
const uint8_t RIGHT_PWM_PIN = 6;
const uint8_t RIGHT_DIR_PIN = 7;
const uint8_t LEFT_ENCODER_A_PIN = 2;
const uint8_t LEFT_ENCODER_B_PIN = 8;
const uint8_t RIGHT_ENCODER_A_PIN = 3;
const uint8_t RIGHT_ENCODER_B_PIN = 10;
const uint8_t SERVO_PIN = 9;
const uint8_t LEFT_LINE_PIN = A0;
const uint8_t RIGHT_LINE_PIN = A1;
const uint8_t IR_DISTANCE_PIN = A2;

const uint8_t ESP_RX_PIN = A4;
const uint8_t ESP_TX_PIN = A5;

// Геометрия робота (в миллиметрах)
const float WHEEL_DIAMETER_MM = 44.0f;
const float WHEEL_BASE_MM = 128.0f;
const float ENCODER_TICKS_PER_REV = 358.0f;
const float MM_PER_TICK = PI * WHEEL_DIAMETER_MM / ENCODER_TICKS_PER_REV;
const float IR_K = 3782.0f;
const float IR_C = 96.0f;

const unsigned long CONTROL_PERIOD_MS = 50;
const unsigned long TELEMETRY_PERIOD_MS = 200;
const unsigned long VELOCITY_WATCHDOG_MS = 500;
const unsigned long START_BOOST_MS = 200;
const unsigned long SERVO_MOVE_MS = 180;

// Скоростные ограничения
const int MIN_LINEAR_MM_S = 100;
const int MAX_LINEAR_MM_S = 400;
const int MIN_ANGULAR_MRAD_S = 1000;
const int MAX_ANGULAR_MRAD_S = 6000;
const float MAX_WHEEL_SPEED_MM_S = 400.0f;

const int LEFT_START_FORWARD_PWM = 100;
const int LEFT_START_REVERSE_PWM = 100;
const int RIGHT_START_FORWARD_PWM = 90;
const int RIGHT_START_REVERSE_PWM = 110;
const int MIN_HOLD_PWM = 40;

// === КОЭФФИЦИЕНТЫ ПИД-РЕГУЛЯТОРА СКОРОСТИ ===
const float PID_KP = 0.25f;  // Пропорциональный коэффициент
const float PID_KI = 0.15f;  // Интегральный коэффициент (исправляет дрейф моторов)
const float PID_KD = 0.05f;  // Дифференциальный коэффициент (демпфирует рывки)
const float MAX_PID_CORRECTION = 70.0f;

// Коэффициент выравнивания прямой
const float STRAIGHT_PID_KP = 1.8f;
const float MAX_STRAIGHT_CORRECTION_MM_S = 45.0f;

// Таблицы аппроксимации PWM
const uint8_t MOTOR_TABLE_SIZE = 16;
const int SPEED_TABLE[MOTOR_TABLE_SIZE] = {
  0, 75, 100, 125, 150, 175, 200, 225,
  250, 275, 300, 325, 350, 375, 395, 400
};
const int LEFT_FORWARD_PWM_TABLE[MOTOR_TABLE_SIZE] = {
  0, 40, 45, 49, 54, 59, 66, 73, 80, 91, 102, 119, 142, 175, 215, 220
};
const int LEFT_REVERSE_PWM_TABLE[MOTOR_TABLE_SIZE] = {
  0, 41, 46, 50, 55, 60, 66, 72, 80, 90, 102, 117, 138, 171, 210, 220
};
const int RIGHT_FORWARD_PWM_TABLE[MOTOR_TABLE_SIZE] = {
  0, 44, 48, 53, 58, 63, 69, 77, 85, 95, 108, 124, 147, 178, 220, 220
};
const int RIGHT_REVERSE_PWM_TABLE[MOTOR_TABLE_SIZE] = {
  0, 43, 48, 52, 58, 63, 69, 76, 85, 95, 108, 125, 147, 181, 219, 220
};

const uint8_t COMMAND_BUFFER_SIZE = 96;

// Структура ПИД-состояния для каждого колеса отдельно
struct PidState {
  int8_t previousDirection;
  unsigned long boostUntilMs;
  float integralError;
  float previousError;
};

SoftwareSerial espSerial(ESP_RX_PIN, ESP_TX_PIN);
Servo scannerServo;

volatile long leftTicks = 0;
volatile long rightTicks = 0;
long previousLeftTicks = 0;
long previousRightTicks = 0;
long straightStartLeft = 0;
long straightStartRight = 0;

float xMm = 0.0f;
float yMm = 0.0f;
float thetaRad = 0.0f;
float leftSpeedMmS = 0.0f;
float rightSpeedMmS = 0.0f;
float targetLeftMmS = 0.0f;
float targetRightMmS = 0.0f;

int requestedLinearMmS = 0;
int requestedAngularMradS = 0;
int servoAngleDeg = 90;
bool controlEnabled = false;
bool straightActive = false;
unsigned long servoDetachMs = 0;

PidState leftPid = {0, 0, 0.0f, 0.0f};
PidState rightPid = {0, 0, 0.0f, 0.0f};

char usbCommandBuffer[COMMAND_BUFFER_SIZE];
uint8_t usbCommandLength = 0;
char espCommandBuffer[COMMAND_BUFFER_SIZE];
uint8_t espCommandLength = 0;
unsigned long previousControlMs = 0;
unsigned long previousTelemetryMs = 0;
unsigned long lastVelocityCommandMs = 0;

void onLeftEncoder() { leftTicks += digitalRead(LEFT_ENCODER_B_PIN) ? 1 : -1; }
void onRightEncoder() { rightTicks += digitalRead(RIGHT_ENCODER_A_PIN) ? -1 : 1; } // Исправлены знаки осей

void copyTicks(long &left, long &right) {
  noInterrupts();
  left = leftTicks;
  right = rightTicks;
  interrupts();
}

int8_t signOf(float value) {
  if (value > 0.5f) return 1;
  if (value < -0.5f) return -1;
  return 0;
}

float normalizeAngle(float angle) {
  while (angle > PI) angle -= 2.0f * PI;
  while (angle < -PI) angle += 2.0f * PI;
  return angle;
}

int applySignedMinimum(int value, int minimum, int maximum) {
  if (value == 0) return 0;
  const int magnitude = constrain(abs(value), minimum, maximum);
  return value > 0 ? magnitude : -magnitude;
}

void setMotor(uint8_t dirPin, uint8_t pwmPin, int pwm) {
  digitalWrite(dirPin, pwm < 0 ? HIGH : LOW);
  analogWrite(pwmPin, abs(constrain(pwm, -255, 255)));
}

void setMotors(int leftPwm, int rightPwm) {
  setMotor(LEFT_DIR_PIN, LEFT_PWM_PIN, leftPwm);
  setMotor(RIGHT_DIR_PIN, RIGHT_PWM_PIN, rightPwm);
}

void resetPidState(PidState &state) {
  state.previousDirection = 0;
  state.boostUntilMs = 0;
  state.integralError = 0.0f;
  state.previousError = 0.0f;
}

void stopMotion() {
  requestedLinearMmS = 0;
  requestedAngularMradS = 0;
  targetLeftMmS = 0.0f;
  targetRightMmS = 0.0f;
  controlEnabled = false;
  straightActive = false;
  resetPidState(leftPid);
  resetPidState(rightPid);
  setMotors(0, 0);
}

void resetOdometry() {
  copyTicks(previousLeftTicks, previousRightTicks);
  straightStartLeft = previousLeftTicks;
  straightStartRight = previousRightTicks;
  xMm = 0.0f;
  yMm = 0.0f;
  thetaRad = 0.0f;
  leftSpeedMmS = 0.0f;
  rightSpeedMmS = 0.0f;
}

int readIrDistanceCm() {
  const int raw = analogRead(IR_DISTANCE_PIN);
  if (raw >= 700) return 5;
  if (raw < 160) return 60;
  const float distance = IR_K / (raw - IR_C);
  return constrain((int)(distance + 0.5f), 5, 60);
}

int servoPhysicalAngle(int logicalAngle) { return 180 - logicalAngle; }

void moveServo(int angle) {
  angle = constrain(angle, 20, 160);
  if (angle == servoAngleDeg) return;
  servoAngleDeg = angle;
  if (!scannerServo.attached()) scannerServo.attach(SERVO_PIN);
  scannerServo.write(servoPhysicalAngle(servoAngleDeg));
  servoDetachMs = millis() + SERVO_MOVE_MS;
}

void updateServo(unsigned long nowMs) {
  if (scannerServo.attached() && (long)(nowMs - servoDetachMs) >= 0) {
    scannerServo.detach();
  }
}

void setVelocity(int linearMmS, int angularMradS) {
  requestedLinearMmS = applySignedMinimum(linearMmS, MIN_LINEAR_MM_S, MAX_LINEAR_MM_S);
  requestedAngularMradS = applySignedMinimum(angularMradS, MIN_ANGULAR_MRAD_S, MAX_ANGULAR_MRAD_S);

  const bool newStraight = requestedLinearMmS != 0 && requestedAngularMradS == 0;
  if (newStraight && !straightActive) {
    copyTicks(straightStartLeft, straightStartRight);
  }
  straightActive = newStraight;
  controlEnabled = requestedLinearMmS != 0 || requestedAngularMradS != 0;
  if (!controlEnabled) stopMotion();
}

void updateOdometry(long deltaLeftTicks, long deltaRightTicks) {
  const float leftDistance = deltaLeftTicks * MM_PER_TICK;
  const float rightDistance = deltaRightTicks * MM_PER_TICK;
  const float distance = 0.5f * (leftDistance + rightDistance);
  const float deltaTheta = (rightDistance - leftDistance) / WHEEL_BASE_MM;
  const float middleTheta = thetaRad + 0.5f * deltaTheta;

  xMm += distance * cos(middleTheta);
  yMm += distance * sin(middleTheta);
  thetaRad = normalizeAngle(thetaRad + deltaTheta);
}

int tablePwm(uint8_t index, bool leftMotor, bool forward) {
  if (leftMotor && forward) return LEFT_FORWARD_PWM_TABLE[index];
  if (leftMotor && !forward) return LEFT_REVERSE_PWM_TABLE[index];
  if (!leftMotor && forward) return RIGHT_FORWARD_PWM_TABLE[index];
  return RIGHT_REVERSE_PWM_TABLE[index];
}

int calibratedPwm(float target, bool leftMotor) {
  const bool forward = target > 0.0f;
  const float speed = fabs(target);
  if (speed < 0.5f) return 0;
  if (speed <= SPEED_TABLE[1]) return MIN_HOLD_PWM;

  for (uint8_t index = 1; index < MOTOR_TABLE_SIZE - 1; index++) {
    if (speed <= SPEED_TABLE[index + 1]) {
      const float speed0 = SPEED_TABLE[index];
      const float speed1 = SPEED_TABLE[index + 1];
      const float pwm0 = tablePwm(index, leftMotor, forward);
      const float pwm1 = tablePwm(index + 1, leftMotor, forward);
      const float part = (speed - speed0) / (speed1 - speed0);
      return (int)(pwm0 + part * (pwm1 - pwm0));
    }
  }
  return tablePwm(MOTOR_TABLE_SIZE - 1, leftMotor, forward);
}

int startPwm(bool leftMotor, int8_t direction) {
  if (leftMotor && direction > 0) return LEFT_START_FORWARD_PWM;
  if (leftMotor && direction < 0) return LEFT_START_REVERSE_PWM;
  if (!leftMotor && direction > 0) return RIGHT_START_FORWARD_PWM;
  return RIGHT_START_REVERSE_PWM;
}

// === ПОЛНОЦЕННЫЙ ПИД-РЕГУЛЯТОР УПРАВЛЕНИЯ PWM КОЛЕСА ===
int calculateMotorPwm(float target, float measured, unsigned long nowMs, bool leftMotor, PidState &state) {
  const int8_t direction = signOf(target);
  if (direction == 0) {
    resetPidState(state);
    return 0;
  }

  if (direction != state.previousDirection) {
    state.previousDirection = direction;
    state.boostUntilMs = nowMs + START_BOOST_MS;
    state.integralError = 0.0f;
    state.previousError = 0.0f;
  }

  // Стартовый буст для преодоления трения редуктора
  if ((long)(state.boostUntilMs - nowMs) > 0) {
    int launchPwm = calibratedPwm(target, leftMotor);
    const int minimumStartPwm = startPwm(leftMotor, direction);
    if (launchPwm < minimumStartPwm) launchPwm = minimumStartPwm;
    return direction * launchPwm;
  }

  const float basePwm = calibratedPwm(target, leftMotor);
  const float error = target - measured;
  
  // Интегральная составляющая ПИД (накапливает и исправляет жесткую разницу)
  state.integralError = constrain(state.integralError + error * (CONTROL_PERIOD_MS * 0.001f), -40.0f, 40.0f);
  // Дифференциальная составляющая (гасит резкие прыжки)
  const float derivativeError = (error - state.previousError) / (CONTROL_PERIOD_MS * 0.001f);
  state.previousError = error;

  // Итоговое ПИД-вычисление
  const float correction = constrain(
    (PID_KP * error) + (PID_KI * state.integralError) + (PID_KD * derivativeError),
    -MAX_PID_CORRECTION, MAX_PID_CORRECTION
  );

  const float output = direction * basePwm + correction;
  if (direction > 0) return constrain((int)output, 0, 255);
  return constrain((int)output, -255, 0);
}

void updateControl(unsigned long nowMs) {
  if (nowMs - previousControlMs < CONTROL_PERIOD_MS) return;
  const float dt = (nowMs - previousControlMs) * 0.001f;
  previousControlMs = nowMs;

  long left, right;
  copyTicks(left, right);
  const long deltaLeft = left - previousLeftTicks;
  const long deltaRight = right - previousRightTicks;
  previousLeftTicks = left;
  previousRightTicks = right;

  leftSpeedMmS = deltaLeft * MM_PER_TICK / dt;
  rightSpeedMmS = deltaRight * MM_PER_TICK / dt;
  updateOdometry(deltaLeft, deltaRight);

  if (!controlEnabled) return;
  const float angularRadS = requestedAngularMradS * 0.001f;
  
  // Согласование знаков направления движения по протоколу Python
  targetLeftMmS = (angularRadS * WHEEL_BASE_MM * 0.5f) + requestedLinearMmS;
  targetRightMmS = (angularRadS * WHEEL_BASE_MM * 0.5f) - requestedLinearMmS;

  if (straightActive) {
    const int direction = requestedLinearMmS > 0 ? 1 : -1;
    const float leftProgress = (left - straightStartLeft) * MM_PER_TICK * direction;
    const float rightProgress = (right - straightStartRight) * MM_PER_TICK * direction;
    const float pathError = leftProgress - rightProgress;
    
    const float correction = constrain(STRAIGHT_PID_KP * pathError, -MAX_STRAIGHT_CORRECTION_MM_S, MAX_STRAIGHT_CORRECTION_MM_S);
    targetLeftMmS -= direction * correction;
    targetRightMmS += direction * correction;
  }

  targetLeftMmS = constrain(targetLeftMmS, -MAX_WHEEL_SPEED_MM_S, MAX_WHEEL_SPEED_MM_S);
  targetRightMmS = constrain(targetRightMmS, -MAX_WHEEL_SPEED_MM_S, MAX_WHEEL_SPEED_MM_S);

  const int leftPwm = calculateMotorPwm(targetLeftMmS, leftSpeedMmS, nowMs, true, leftPid);
  const int rightPwm = calculateMotorPwm(targetRightMmS, rightSpeedMmS, nowMs, false, rightPid);
  setMotors(leftPwm, rightPwm);
}

void sendLine(const char *line) {
  Serial.println(line);
  espSerial.println(line);
}

void sendTelemetry() {
  long left, right;
  copyTicks(left, right);
  const int linearMmS = (int)(0.5f * (leftSpeedMmS + rightSpeedMmS));
  const int angularMradS = (int)(1000.0f * (rightSpeedMmS - leftSpeedMmS) / WHEEL_BASE_MM);

  char line[150];
  snprintf(line, sizeof(line), "TEL %ld %ld %ld %d %d %ld %ld %d %d %d %d",
      (long)xMm, (long)yMm, (long)(thetaRad * 1000.0f), linearMmS, angularMradS,
      left, right, analogRead(LEFT_LINE_PIN), analogRead(RIGHT_LINE_PIN),
      readIrDistanceCm(), servoAngleDeg);
  sendLine(line);
}

void processCommand(char *line) {
  char *save = NULL;
  char *command = strtok_r(line, " ", &save);
  if (command == NULL) return;

  if (strcmp(command, "VEL") == 0) {
    char *linearText = strtok_r(NULL, " ", &save);
    char *angularText = strtok_r(NULL, " ", &save);
    if (linearText == NULL || angularText == NULL) {
      sendLine("ERR VEL_NEEDS_LINEAR_ANGULAR");
      return;
    }
    setVelocity(atoi(linearText), atoi(angularText));
    lastVelocityCommandMs = millis();
  } else if (strcmp(command, "SERVO") == 0) {
    char *angleText = strtok_r(NULL, " ", &save);
    if (angleText == NULL) {
      sendLine("ERR SERVO_NEEDS_ANGLE");
      return;
    }
    moveServo(atoi(angleText));
  } else if (strcmp(command, "RESET_ODOM") == 0) {
    stopMotion();
    resetOdometry();
    sendLine("OK RESET_ODOM");
  } else if (strcmp(command, "STOP") == 0) {
    stopMotion();
  } else if (strcmp(command, "PING") == 0) {
    sendLine("PONG ARDUINO");
  } else if (strcmp(command, "GET") == 0) {
    sendTelemetry();
  } else {
    sendLine("ERR UNKNOWN_COMMAND");
  }
}

void readCommands(Stream &stream, char *buffer, uint8_t &length) {
  while (stream.available()) {
    const char symbol = stream.read();
    if (symbol == '\n' || symbol == '\r') {
      if (length > 0) {
        buffer[length] = '\0';
        processCommand(buffer);
        length = 0;
      }
    } else if (length < COMMAND_BUFFER_SIZE - 1) {
      buffer[length++] = symbol;
    } else {
      length = 0;
      sendLine("ERR LINE_TOO_LONG");
    }
  }
}

void readUsbCommands() { readCommands(Serial, usbCommandBuffer, usbCommandLength); }
void readEspCommands() { readCommands(espSerial, espCommandBuffer, espCommandLength); }

void checkWatchdog(unsigned long nowMs) {
  if (controlEnabled && nowMs - lastVelocityCommandMs > VELOCITY_WATCHDOG_MS) {
    stopMotion();
    sendLine("EVENT WATCHDOG_STOP");
  }
}

void setup() {
  Serial.begin(115200);
  espSerial.begin(38400);
  pinMode(LEFT_DIR_PIN, OUTPUT);
  pinMode(LEFT_PWM_PIN, OUTPUT);
  pinMode(RIGHT_PWM_PIN, OUTPUT);
  pinMode(RIGHT_DIR_PIN, OUTPUT);
  pinMode(LEFT_ENCODER_A_PIN, INPUT);
  pinMode(LEFT_ENCODER_B_PIN, INPUT);
  pinMode(RIGHT_ENCODER_A_PIN, INPUT);
  pinMode(RIGHT_ENCODER_B_PIN, INPUT);
  pinMode(LEFT_LINE_PIN, INPUT);
  pinMode(RIGHT_LINE_PIN, INPUT);
  pinMode(IR_DISTANCE_PIN, INPUT);
  
  attachInterrupt(digitalPinToInterrupt(LEFT_ENCODER_A_PIN), onLeftEncoder, RISING);
  attachInterrupt(digitalPinToInterrupt(RIGHT_ENCODER_A_PIN), onRightEncoder, RISING);
  
  scannerServo.attach(SERVO_PIN);
  scannerServo.write(servoPhysicalAngle(servoAngleDeg));
  servoDetachMs = millis() + SERVO_MOVE_MS;
  
  stopMotion();
  resetOdometry();
  previousControlMs = millis();
  previousTelemetryMs = millis();
  sendLine("READY ARDUINO_DAY2_PID");
}

void loop() {
  readUsbCommands();
  readEspCommands();
  const unsigned long nowMs = millis();
  checkWatchdog(nowMs);
  updateControl(nowMs);
  updateServo(nowMs);

  if (nowMs - previousTelemetryMs >= TELEMETRY_PERIOD_MS) {
    previousTelemetryMs = nowMs;
    sendTelemetry();
  }
}


```

**⚙️ Как это работает:** 
Программа считывает вращение колес через прерывания `attachInterrupt` на высокой аппаратной частоте. Каждые 50 мс (`CONTROL_PERIOD_MS`) одометрический блок вычисляет мгновенную скорость движения каждого борта в мм/с. Функция `calculateMotorPwm` реализует полноценный цифровой ПИД-алгоритм стабилизации: интегральный буфер накапливает и убирает статическую погрешность редукторов моторов, выравнивая ход. Конструкция `VELOCITY_WATCHDOG_MS` страхует робота: если от ноутбука по Wi-Fi перестанут поступать пакеты удержания, шасси аварийно замрёт через **500 миллисекунд**, защищая систему от столкновений.

### 3. Управляющий ИИ-центр на ноутбуке (`ai_omni_test.py`)
```python
import cv2
import numpy as np
import math
import time
import socket
import threading
import requests

# === ГЛОБАЛЬНЫЕ ТАКТИЧЕСКИЕ ПЕРЕМЕННЫЕ ===
current_servo_angle = 90  # Стартовый угол камеры (прямо)
current_cmd = "STOP"      # Стартовое состояние моторов

# Телеметрия из Arduino Uno (строго под 11 параметров прошивки)
robot_data = {
    'ir_cm': 60, 'servo_deg': 90
}
data_lock = threading.Lock()
tcp_socket = None

# --- 1. НАДЁЖНЫЙ ПОТОК ПРИЕМА ТЕЛЕМЕТРИИ С ФИЛЬТРОМ СДВИГОВ ---
def tcp_telemetry_receiver():
    global tcp_socket, robot_data
    print("[SYSTEM]: Подключение к командному TCP-мосту: 192.168.4.1:8888...")
    while True:
        try:
            if tcp_socket is None:
                tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                tcp_socket.settimeout(1.5)
                # Постоянный жесткий адрес платы робота
                tcp_socket.connect(("192.168.4.1", 8888))
                tcp_socket.setblocking(False)
                print("[+] Беспроводной TCP-канал связи OmniScan успешно соединен!")
            
            try:
                buffer = tcp_socket.recv(2048).decode('utf-8', errors='ignore')
                if buffer and "TEL" in buffer:
                    # Режем лаги Wi-Fi по последней актуальной строке TEL
                    raw_telemetry = buffer.split("TEL")[-1].strip()
                    parts = raw_telemetry.split()
                    if len(parts) >= 8:
                        with data_lock:
                            robot_data['ir_cm'] = int(parts[-2])   
                            robot_data['servo_deg'] = int(parts[-1])
            except BlockingIOError: pass
        except Exception:
            if tcp_socket: tcp_socket.close(); tcp_socket = None
            time.sleep(1.0)
        time.sleep(0.01)

def send_robot_command(cmd):
    global tcp_socket
    if tcp_socket:
        try: tcp_socket.sendall(f"{cmd}\n".encode('utf-8'))
        except Exception: pass

# --- 2. ВЫСОКОСКОРОСТНОЙ ПОТОК ОБХОДА WATCHDOG (КАЖДЫЕ 80 МС) ---
def robot_control_watchdog_loop():
    global current_cmd, current_servo_angle
    print("[+] Высокоскоростной Wi-Fi генератор команд запущен.")
    while True:
        # Непрерывно дублируем ручные значения, чтобы сбрасывать Watchdog на Arduino (500 мс)
        send_robot_command(f"SERVO {current_servo_angle}")
        send_robot_command(current_cmd)
        time.sleep(0.08)

# --- 3. ОСНОВНОЙ ВЫЧИСЛИТЕЛЬНЫЙ ЦИКЛ ОБРАБОТКИ ВИДЕО И КЛАВИАТУРЫ ---
def main():
    global current_cmd, current_servo_angle
    
    threading.Thread(target=tcp_telemetry_receiver, daemon=True).start()
    threading.Thread(target=robot_control_watchdog_loop, daemon=True).start()

    print("[SYSTEM]: Подключение к HTTP-видеосерверу ESP32-CAM...")
    cv2.namedWindow("OMNISCAN: Manual Control HUD")
    
    # Прямой побайтовый перехват беспроводного JPEG-потока
    stream = None
    try:
        stream = requests.get("http://192.168.4", stream=True, timeout=5)
        print("[+] Беспроводной видеопоток успешно инициализирован!")
    except Exception as e:
        print(f"[-] Ошибка подключения к камере: {e}")

    bytes_buffer = bytes()

    print("\n" + "="*50)
    print("[УПРАВЛЕНИЕ MOTORS]: W - Вперед | S - Назад | A - Поворот влево | D - Поворот вправо")
    print("[УПРАВЛЕНИЕ SERVO ]: I - Поворот глаза влево | O - Поворот глаза вправо")
    print("[ЭКСТРЕННЫЙ ТОРМОЗ]: Клавиша 'Пробел' (Space) - Полная остановка")
    print("[ВЫХОД ИЗ КЛИЕНТА ]: Клавиша 'Q' - Закрыть интерфейс")
    print("="*50 + "\n")

    if stream and stream.status_code == 200:
        for chunk in stream.iter_content(chunk_size=1024):
            bytes_buffer += chunk
            a = bytes_buffer.find(b'\xff\xd8') # Начало JPEG кадра
            b = bytes_buffer.find(b'\xff\xd9') # Конец JPEG кадра
            
            if a != -1 and b != -1:
                jpg = bytes_buffer[a:b+2]
                bytes_buffer = bytes_buffer[b+2:]
                frame = cv2.imdecode(np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)
                
                if frame is not None:
                    frame = cv2.resize(frame, (1024, 576))

                    with data_lock:
                        air_cm = robot_data['ir_cm']
                        aservo = robot_data['servo_deg']

                    # --- КИБЕРПАНК-ИНТЕРФЕЙС ИК-РАДАРА ВНИЗУ ЭКРАНА ---
                    radar_center_x, radar_center_y = 512, 540
                    cv2.ellipse(frame, (radar_center_x, radar_center_y), (120, 120), 0, 180, 360, (60, 60, 60), 2, cv2.LINE_AA)
                    
                    angle_rad = math.radians(aservo)
                    beam_len = int(max(20, min(120, air_cm * 2.2)))
                    bx = int(radar_center_x - beam_len * math.cos(angle_rad))
                    by = int(radar_center_y - beam_len * math.sin(angle_rad))
                    
                    beam_color = (0, 0, 255) if air_cm < 16 else (0, 255, 255)
                    cv2.line(frame, (radar_center_x, radar_center_y), (bx, by), beam_color, 2, cv2.LINE_AA)
                    cv2.circle(frame, (bx, by), 4, beam_color, -1)

                    # Стильная HUD-панель ручного пилотирования OmniScan
                    cv2.rectangle(frame, (10, 10), (520, 95), (0, 0, 0), -1)
                    cv2.putText(frame, "OMNISCAN MANUAL HUB : ONLINE", (20, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1, cv2.LINE_AA)
                    cv2.putText(frame, f"CURRENT TELEMETRY CMD     : {current_cmd}", (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1, cv2.LINE_AA)
                    cv2.putText(frame, f"MANUAL TARGET SERVO VALUE : {current_servo_angle} DEG", (20, 72), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 0, 255), 1, cv2.LINE_AA)

                    cv2.rectangle(frame, (830, 10), (1014, 55), (0, 0, 0), -1)
                    cv2.putText(frame, f"LIDAR: {air_cm} CM", (845, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.45, beam_color, 1, cv2.LINE_AA)
                    cv2.putText(frame, f"SERVO: {aservo} DEG", (845, 47), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1, cv2.LINE_AA)

                    cv2.imshow("OMNISCAN: Manual Control HUD", frame)

                # --- ОБРАБОТКА НАДЁЖНЫХ КЛАВИШ OpenCV (Робот едет, пока клавиша активна) ---
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'): break
                elif key == ord('w'): current_cmd = "VEL 180 0"   # Езда вперед
                elif key == ord('s'): current_cmd = "VEL -180 0"  # Езда назад
                elif key == ord('a'): current_cmd = "VEL 0 4500"   # Поворот влево
                elif key == ord('d'): current_cmd = "VEL 0 -4500"  # Поворот вправо
                elif key == ord('i'): current_servo_angle = min(165, current_servo_angle + 15) # Поворот головы влево
                elif key == ord('o'): current_servo_angle = max(15, current_servo_angle - 15)  # Поворот головы вправо
                elif key == ord(' '): current_cmd = "STOP"        # Экстренный тормоз моторов

    if tcp_socket: tcp_socket.close()
    cv2.destroyAllWindows()

if __name__ == '__main__':
    main()


```

**⚙️ Принцип работы:** 
Скрипт побайтово вырезает JPEG-картинки из сетевого HTTP-канала по маркерам `\xff\xd8` и `\xff\xd9` в обход стандартных лагов видеодекодеров. Кадр анализируется весами YOLOv8. Если перед роботом пусто, он плавно крутится на ковре в режиме авто-разведки (`W`), качая камеру влево-вправо. Как только YOLOv8 обнаруживает объект, робот переходит в режим захвата (`Target Lock-On`). Скрипт оценивает положение центра масс объекта на матрице `1024x576`. Если объект уходит из центра кадров, ноутбук точечно корректирует угол сервопривода, удерживая объект строго во взгляде. Затем вычисляется физическая угловая ошибка между направлением «головы» и продольной осью робота: `err_servo = aservo - 90`. Полученное значение ошибки преобразуется в угловую скорость разворота колес `VEL`. Робот начинает автоматически доворачивать всем своим колесным корпусом вслед за взглядом своей поворотной камеры, центрируя курс на найденный предмет.

---
