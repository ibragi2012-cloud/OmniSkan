# OmniScan: 👁️

Проект автономного мобильного робота-исследователя со сканирующим ИИ-зрением на базе связки **ESP32-CAM** и **Arduino Uno**. Камера закреплена непосредственно на сервоприводе, выступая в роли активного эгоцентрического сенсора. Робот сканирует пространство нейросетью **YOLOv8**, захватывает цели и автоматически удерживает курс на объект с помощью ПИД-регуляторов.

---

## 🚀 Возможности
* **Active AI Scanning:** Камера непрерывно вращается на 180°, сканируя сектор вокруг робота с помощью нейросети **YOLOv8** (80 классов).
* **Target Lock-On:** При обнаружении объекта ИИ фиксирует взгляд сервопривода на цели, рассчитывает вектор ошибки и автоматически направляет ПИД-шасси ровера на объект.
* **Ручной HUD-Перехват:** Возможность мгновенного перехода на ручное управление движением с клавиатуры (`W`,`S`,`A`,`D`) и точечное наведение глаза-камеры (`I`,`O`).

---

## 🔌 Подключение компонентов

Все элементы соединяются напрямую без промежуточных плат расширения. Питание радиомодуля должно быть строго раздельным и мощным.

*   **ESP32-CAM 5V и GND** ➡️ К выходу **+5V** силового DC-DC преобразователя ровера. Запитка от платы Arduino **категорически запрещена** (риск циклической перезагрузки Brownout).
*   **Общая земля (GND):** Минус аккумулятора, GND преобразователя, GND Arduino Uno и GND ESP32-CAM соединены вместе в одну общую точку.
*   **Линия данных TX (Камера):** Пин `U0T` (GPIO 1) ESP32-CAM ➡️ Цифровой пин `A4` (RX) на Arduino Uno.
*   **Линия данных RX (Камера):** Пин `U0R` (GPIO 3) ESP32-CAM ➡️ Цифровой пин `A5` (TX) на Arduino Uno.
*   **Управление головой:** Сигнальный провод сервопривода (обычно оранжевый) ➡️ Пин `9` на Arduino Uno.

---

## ⚡ Быстрый запуск

1. Прошейте Arduino Uno (ПИД-драйвер, скорость связи `38400` бод) и ESP32-CAM (скетч MJPEG-моста).
2. Снимите ESP32-CAM с программатора, закрепите на сервоприводе робота, соберите цепи питания и включите тумблер.
3. Подключите ноутбук к Wi-Fi сети **`NEYMARK_01`** (пароль по умолчанию: `neymark123`).
4. Положите файл весов нейросети `yolov8n.pt` на Рабочий стол рядом со скриптом.
5. Запустите ИИ-центр управления на ноутбуке через терминал:
```powershell
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
  
  const char* AP_NAME = "ImyaSeti";
  const char* AP_PASSWORD = "ParolSeti";
  
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
6. Кликните мышкой по открывшемуся окну OpenCV и нажмите английскую клавишу **`W`**, чтобы запустить режим автономного ИИ-поиска объектов.

---

## 💾 Архитектура ПО и Исходный код

### 1. Прошивка для ESP32-CAM (`esp32_cam_stream_bridge.ino`)
```cpp
// [МЕСТО ДЛЯ ВСТАВКИ СKЕТЧА ESP32-CAM]
// Вставьте сюда C++ код для вашей платы ESP32-CAM, 
// который поднимает Wi-Fi точку доступа NEYMARK_01 и транслирует MJPEG-видеопоток.
```

**⚙️ Принцип работы:**
Плата инициализирует матрицу `OV2640` в ИИ-оптимальном разрешении 800x600 (`SVGA`). Она поднимает автономную Wi-Fi точку доступа и запускает HTTP-видеосервер на порту `80`, непрерывно отдавая JPEG-кадры методом покадрового сжатия видеопотока (`MJPEG`). Функции `btStop()` и `WIFI_POWER_2dBm` снижают общее энергопотребление, страхуя плату от просадок напряжения. В основном цикле `loop()` два независимых неблокирующих буфера пересылают приходящие от ПК пакеты `VEL` / `SERVO` в аппаратный UART к плате Arduino Uno и возвращают строки телеметрии `TEL` обратно в Wi-Fi сеть.

### 2. ПИД-прошивка для шасси ровера (`pid_rover_fixed.ino`)
```cpp
// [МЕСТО ДЛЯ ВСТАВКИ СKЕТЧА ARDUINO UNO]
// Вставьте сюда C++ код для платы Arduino Uno, 
// отвечающий за чтение энкодеров, расчет ПИД-скоростей и управление сервоприводом.
```

**⚙️ Как это работает:** 
Программа считывает вращение колес через прерывания `attachInterrupt` на высокой аппаратной частоте. Каждые 50 мс (`CONTROL_PERIOD_MS`) одометрический блок вычисляет мгновенную скорость движения каждого борта в мм/с. Функция `calculateMotorPwm` реализует полноценный цифровой ПИД-алгоритм стабилизации: интегральный буфер накапливает и убирает статическую погрешность редукторов моторов, выравнивая ход. Конструкция `VELOCITY_WATCHDOG_MS` страхует робота: если от ноутбука по Wi-Fi перестанут поступать пакеты удержания, шасси аварийно замрёт через **500 миллисекунд**, защищая систему от столкновений.

### 3. Управляющий ИИ-центр на ноутбуке (`ai_omni_test.py`)
```python
# [МЕСТО ДЛЯ ВСТАВКИ КОДА PYTHON]
# Вставьте сюда ваш главный ИИ-скрипт на Python, который подключается к ESP32-CAM,
# обрабатывает кадры через YOLOv8 и осуществляет автоматическое наведение на цель.
```

**⚙️ Принцип работы:** 
Скрипт побайтово вырезает JPEG-картинки из сетевого HTTP-канала по маркерам `\xff\xd8` и `\xff\xd9` в обход стандартных лагов видеодекодеров. Кадр анализируется весами YOLOv8. Если перед роботом пусто, он плавно крутится на ковре в режиме авто-разведки (`W`), качая камеру влево-вправо. Как только YOLOv8 обнаруживает объект, робот переходит в режим захвата (`Target Lock-On`). Скрипт оценивает положение центра масс объекта на матрице `1024x576`. Если объект уходит из центра кадров, ноутбук точечно корректирует угол сервопривода, удерживая объект строго во взгляде. Затем вычисляется физическая угловая ошибка между направлением «головы» и продольной осью робота: `err_servo = aservo - 90`. Полученное значение ошибки преобразуется в угловую скорость разворота колес `VEL`. Робот начинает автоматически доворачивать всем своим колесным корпусом вслед за взглядом своей поворотной камеры, центрируя курс на найденный предмет.

---

## 🛠️ Управление комментариями при отладке (Справка Python)

При локальном тестировании кода или его публикации на GitHub вы можете гибко отключать блоки логики с помощью синтаксических конструкций:

*   **Символ решетки (`#`):** Используется для однострочных комментариев. Если поставить его перед строкой, Python полностью ее пропустит:
    ```python
    # send_robot_command(current_cmd)  # Моторы временно заблокированы
    ```
*   **Тройные кавычки (`'''` или `"""`):** Используются для многострочного комментирования. Позволяют временно изолировать целые куски кода, например, для отключения приема телеметрии при тестировании чистого видео:
    ```python
    '''
    with data_lock:
        robot_data['servo_deg'] = int(parts[-1])
    '''
    ```
