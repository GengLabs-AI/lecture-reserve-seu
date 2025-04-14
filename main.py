"""
东南大学素质讲座预约抢票脚本
主要功能：自动登录系统、扫描符合要求的讲座并进行预约
"""

# ==================== 第三方库导入 ====================
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException
import time
import base64
import ddddocr
import re
from datetime import datetime

# ==================== 全局配置项 ====================
CONFIG = {
    # 登录凭证
    "card_number": "",  # 一卡通号
    "password": "",  # 登录密码

    # 讲座筛选条件

    # 讲座精准预约模式：
    # 1. 当列表非空时，仅尝试预约列表中指定的讲座（需完整匹配讲座标题）
    # 2. 本列表为空时，按分类/校区等其他条件筛选讲座
    # 格式示例：["【线下】【心理健康】研究生...精神卫生"、"【线下】【沙龙】解压魔方·聚力磁场"]
    "preferred_lectures": [],

    # 需要预约的讲座类别范围
    "required_categories": [
        "人文与科学素养系列讲座_心理健康",
        "人文与科学素养系列讲座_法律",
        "人文与科学素养系列讲座-艺术类",
        "人文与科学素养系列讲座_其他",
        '“SEU咖啡间”系列沙龙活动'
    ],
    "preferred_campus": ["九龙湖校区"],  # 优先选择的校区
    # 预约模式开关
    "enable_offline": False,  # 是否抢线下讲座
    "enable_online": True  # 是否抢线上讲座
}

# ==================== 全局工具初始化 ====================
ocr = ddddocr.DdddOcr()  # 验证码识别器

# 浏览器驱动配置
chrome_options = Options()
# chrome_options.add_argument("--headless")  # 无头模式
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--window-size=1920x1080")
driver = webdriver.Chrome(options=chrome_options)


# ==================== 核心功能函数 ====================
def login():
    """执行系统登录操作"""
    driver.get("https://ehall.seu.edu.cn/gsapp/sys/yddjzxxtjappseu/*default/index.do#/hdyy")
    time.sleep(1)

    # 输入账号密码
    driver.find_element(By.CSS_SELECTOR, ".input-username-pc input").send_keys(CONFIG["card_number"])
    driver.find_element(By.CSS_SELECTOR, ".input-password-pc input").send_keys(CONFIG["password"])

    # 点击登录按钮
    driver.find_element(By.CLASS_NAME, "login-button-pc").click()
    time.sleep(1)


def is_time_conflict(new_start, new_end):
    """
    检查新讲座时间是否与已预约讲座冲突

    Args:
        new_start: datetime 新讲座开始时间
        new_end: datetime 新讲座结束时间

    Returns:
        bool: True表示有时间冲突，False表示无冲突
    """
    try:
        # 获取所有已预约讲座
        booked_lectures = []
        for element in driver.find_elements(By.CLASS_NAME, "activity-container"):
            lecture = parse_lecture(element)
            if lecture and lecture["status"] == "取消预约":
                booked_lectures.append(lecture)

        # 检查时间重叠
        for lecture in booked_lectures:
            if (new_start <= lecture["end_time"]) and (new_end >= lecture["start_time"]):
                return True
        return False
    except Exception as e:
        print(f"‼ 时间冲突检查异常: {str(e)}")
        return False


def parse_lecture(element):
    """
    解析讲座元素信息

    Args:
        element: WebElement 讲座页面元素

    Returns:
        dict: 包含解析后的讲座信息，格式为：
            {
                "category": 讲座类别,
                "title": 讲座标题,
                "campus": 校区/线上,
                "start_time": 开始时间,
                "end_time": 结束时间,
                "element": 原始元素,
                "status": 预约状态
            }
    """
    try:
        # 解析基础信息
        category = element.find_element(By.CSS_SELECTOR, ".hdxq-hdlx .mint-text").text
        title = element.find_element(By.CSS_SELECTOR, ".activity-name .mint-text").text
        location = element.find_element(By.CSS_SELECTOR, "div[title='item.JZDD']").text

        # 解析时间信息
        time_text = element.find_elements(By.CSS_SELECTOR, ".activity-text .mint-text")[1].text
        time_matches = re.findall(r"\d{4}/\d{2}/\d{2}/\d{2}:\d{2}:\d{2}", time_text)
        start_time = datetime.strptime(time_matches[0], "%Y/%m/%d/%H:%M:%S")
        end_time = datetime.strptime(time_matches[1], "%Y/%m/%d/%H:%M:%S")

        return {
            "category": category,
            "title": title,
            "campus": _extract_campus(location),
            "start_time": start_time,
            "end_time": end_time,
            "element": element,
            "status": element.find_element(By.CSS_SELECTOR, "button").text.strip()
        }
    except Exception as e:
        print(f"❌ 讲座解析失败: {str(e)}")
        return None


def _extract_campus(location):
    """
    校区信息提取辅助函数

    Args:
        location: str 原始位置信息

    Returns:
        str: 提取后的校区/会议信息
    """
    campus_match = re.match(r'^(.+?校区)', location)
    return campus_match.group(1) if campus_match else location


def validate_lecture(lecture):
    """
    验证讲座是否符合预约条件

    Args:
        lecture: dict 讲座信息字典

    Returns:
        bool: True表示符合条件，False表示不符合
    """
    # 基础状态检查
    if lecture["status"] != "预约":
        return False

    # 优先检查用户是否指定讲座名称
    if CONFIG["preferred_lectures"]:
        if lecture["title"] not in CONFIG["preferred_lectures"]:
            # print(f"❌ 指定讲座不存在: {lecture['title']}")
            return False
        else:
            # print(f"✅ 命中指定讲座: {lecture['title']}")
            return True  # 直接跳过其他条件

    # 类别检查
    if lecture["category"] not in CONFIG["required_categories"]:
        return False

    # 校区检查
    if lecture["campus"] not in CONFIG["preferred_campus"] and "线上" not in lecture["title"]:
        return False

    # 类型检查（线上/线下）
    is_online = "线上" in lecture["title"]
    if (is_online and not CONFIG["enable_online"]) or \
            (not is_online and not CONFIG["enable_offline"]):
        return False

    # 时间冲突检查
    if is_time_conflict(lecture["start_time"], lecture["end_time"]):
        print(f"‼ 时间冲突: {lecture['title']}")
        return False

    return True


def reserve_lecture(lecture):
    """
    执行讲座预约操作

    Args:
        lecture: dict 包含讲座信息的字典

    Returns:
        bool: True表示预约成功，False表示失败
    """
    try:
        # 点击预约按钮
        button = WebDriverWait(lecture["element"], 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button")))
        button.click()
        # print("已点击预约按钮...")

        # 处理验证码
        wait = WebDriverWait(driver, 5)
        vcode_img = wait.until(EC.presence_of_element_located((By.ID, "vcodeImg")))
        img_data = base64.b64decode(vcode_img.get_attribute("src").split("base64,")[1])

        # OCR识别
        captcha_text = ocr.classification(img_data)
        # print(f"验证码识别结果: {captcha_text}")

        # # 输入并提交验证码
        wait.until(EC.presence_of_element_located((By.ID, "vcodeInput"))).send_keys(captcha_text)
        wait.until(EC.element_to_be_clickable((By.ID, "jqalert_yes_btn"))).click()

        try:
            # 检测验证码错误弹窗（最多等待3秒）
            WebDriverWait(driver, 1).until(
                EC.presence_of_element_located(
                    (By.XPATH, "//div[contains(@class, 'mint-msgbox-message') and contains(text(), '验证码错误')]")
                )
            )
            # 如果检测到错误提示则不打印成功信息
        except TimeoutException:
            # 未检测到错误弹窗则执行成功逻辑
            print(f"✅ 预约成功！ {lecture['title']}")
            return True
    except Exception as e:
        print(f"❌ 预约失败: {str(e)}")
        return False


def lecture_scanner():
    """
    扫描并筛选可预约讲座

    Returns:
        list: 按优先级排序后的可预约讲座列表
    """
    driver.refresh()
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "activity-container")))
    except:
        return []

    # 解析和筛选讲座
    valid_lectures = []
    for element in driver.find_elements(By.CLASS_NAME, "activity-container"):
        lecture = parse_lecture(element)
        if lecture and validate_lecture(lecture):
            valid_lectures.append(lecture)

    # 按优先级排序
    return sorted(valid_lectures, key=_sort_priority)


def _sort_priority(lecture):
    """
    讲座排序优先级规则（升序排列）
    1. 必需类别优先
    2. 优先校区/线上优先
    3. 时间最近优先
    """
    required_priority = 0 if lecture["category"] in CONFIG["required_categories"] else 1
    is_online = "线上" in lecture["title"]
    campus_priority = 0 if (is_online or lecture["campus"] == CONFIG["preferred_campus"]) else 1
    return (required_priority, campus_priority, lecture["start_time"])


# ==================== 主流程控制 ====================
def main_process():
    """主控制流程（支持多预约）"""
    no_lecture_reported = False  # 添加状态跟踪变量
    wait_dots = ['.  ', '.. ', '...']  # 等待动画符号
    wait_dot_index = 0

    while True:
        try:
            # 获取最新讲座列表
            lectures = lecture_scanner()
            if lectures:
                # 如果发现讲座且有等待提示，先换行
                if no_lecture_reported:
                    print("\n", end="")
                    no_lecture_reported = False

                # 尝试预约优先级最高的讲座
                reserve_lecture(lectures[0])

            else:
                # 只在第一次未找到时显示完整提示
                if not no_lecture_reported:
                    print("⏳ 未发现新讲座，持续扫描中", end="", flush=True)
                    no_lecture_reported = True
                else:
                    # 显示动态等待符号
                    print(f"\r⏳ 未发现新讲座，持续扫描中 {wait_dots[wait_dot_index]}", end="", flush=True)
                    wait_dot_index = (wait_dot_index + 1) % len(wait_dots)


        except Exception as e:
            # 异常时重置状态
            no_lecture_reported = False
            print(f"\n‼ 发生异常: {str(e)}")
            driver.refresh()
            time.sleep(1)

# ==================== 程序入口 ====================
if __name__ == "__main__":
    login()  # 执行登录
    main_process()  # 启动主流程
    driver.quit()  # 退出浏览器
