from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import base64
import ddddocr  # 使用 ddddocr 进行验证码识别

# 初始化 OCR 识别器
ocr = ddddocr.DdddOcr()

# 设置 Selenium WebDriver 选项
chrome_options = Options()
# chrome_options.add_argument("--headless")  # 无头模式，提高速度
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--window-size=1920x1080")

# 启动 WebDriver
driver = webdriver.Chrome(options=chrome_options)
driver.implicitly_wait(10)  # 隐式等待，减少 sleep

# 访问网页
url = "https://ehall.seu.edu.cn/gsapp/sys/yddjzxxtjappseu/*default/index.do#/hdyy"
driver.get(url)

# **使用显式等待**，确保元素加载完毕
wait = WebDriverWait(driver, 10)

# **输入一卡通号和密码**
card_number = "230258294"
password = "194834"

wait.until(EC.presence_of_element_located((By.CLASS_NAME, "input-username-pc"))).find_element(By.TAG_NAME, "input").send_keys(card_number)
wait.until(EC.presence_of_element_located((By.CLASS_NAME, "input-password-pc"))).find_element(By.TAG_NAME, "input").send_keys(password)

# **点击登录按钮**
wait.until(EC.element_to_be_clickable((By.CLASS_NAME, "login-button-pc"))).click()

# **等待预约按钮出现并点击**
wait.until(EC.element_to_be_clickable((By.CLASS_NAME, "ydd-button-small.button-success"))).click()

# **等待验证码加载**
try:
    vcode_img = wait.until(EC.presence_of_element_located((By.ID, "vcodeImg")))
    src = vcode_img.get_attribute("src")

    if "base64," in src:
        # **直接解析 base64，无需保存文件**
        base64_data = src.split("base64,")[1]
        img_data = base64.b64decode(base64_data)

        # **识别验证码**
        captcha_text = ocr.classification(img_data)
        print(f"识别的验证码: {captcha_text}")

        # **输入验证码**
        vcode_input = wait.until(EC.presence_of_element_located((By.ID, "vcodeInput")))
        vcode_input.send_keys(captcha_text)

        # **点击确认按钮**
        wait.until(EC.element_to_be_clickable((By.ID, "jqalert_yes_btn"))).click()

        # **等待跳转**
        wait.until(EC.url_changes(url))
    else:
        print("未获取到验证码")
except Exception as e:
    print(f"错误发生：{e}")

# **关闭 WebDriver**
driver.quit()
print("验证码识别流程完成！")
