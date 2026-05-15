import os
import sys
import time
import json
import shutil
import requests
import re
from datetime import datetime
from typing import Optional, List
import base64

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import io
from PIL import Image

# ================= 配置区域 =================
class Config:
    api_key = os.getenv("YESCAPTCHA_KEY")
    base_url = "https://api.yescaptcha.com"
    # EUserv 账号
    EU_EMAIL = os.getenv("EUSERV_USERNAME")
    EU_PASSWORD = os.getenv("EUSERV_PASSWORD")
    
    # Mailparser (获取 PIN)
    MAILPARSER_URL = os.getenv("MAILPARSER_DOWNLOAD_URL_ID")
    
    # Telegram 推送配置
    TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
    TG_CHAT_ID = os.getenv("TG_USER_ID")
    TG_API_HOST = os.getenv("TG_API_HOST", "https://api.telegram.org") # 可选，默认官方接口
    
    # 运行参数
    WAITING_TIME_OF_PIN = 40
    MAX_RETRIES = 3
    RETRY_DELAY = 5
    ELEMENT_WAIT_TIMEOUT = 30
    
    # 运行时状态记录 (用于推送)
    run_status = "UNKNOWN"
    error_message = ""
    action_taken = "No action needed"

# ================= 工具函数 =================
def get_pin_from_mailparser(url_id: str) -> Optional[str]:
    if not url_id or "http" not in url_id:
        return None
    try:
        response = requests.get(url_id, timeout=10)
        response.raise_for_status()
        json_data = json.loads(response.text)
        if not json_data or not isinstance(json_data, list):
            return None
        
        raw_pin = str(json_data[0]["pin"]).strip()
        clean_pin = ""
        try:
            clean_pin = str(int(float(raw_pin)))
        except ValueError:
            clean_pin = re.sub(r'\D', '', raw_pin)
        return clean_pin if clean_pin else None
    except Exception:
        return None

def send_telegram_notification(status: str, details: str):
    """发送 Telegram 通知"""
    if not Config.TG_BOT_TOKEN or not Config.TG_CHAT_ID:
        print("⚠️ Telegram 配置缺失，跳过推送。")
        return

    emoji = "✅" if status == "SUCCESS" else "❌"
    title = "EUserv 续约成功" if status == "SUCCESS" else "EUserv 续约失败"
    
    # 构建消息内容
    message = (
        f"<b>{emoji} {title}</b>\n\n"
        f"<b>👤 账号:</b> <code>{Config.EU_EMAIL}</code>\n"
        f"<b>🕒 时间:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"<b>📝 状态:</b> {details}\n\n"
        f"<i>AutoEUServerless Bot</i>"
    )

    data = {
        "chat_id": Config.TG_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }

    try:
        url = f"{Config.TG_API_HOST}/bot{Config.TG_BOT_TOKEN}/sendMessage"
        response = requests.post(url, data=data, timeout=10)
        if response.status_code == 200:
            print("📬 Telegram 推送成功")
        else:
            print(f"⚠️ Telegram 推送失败: {response.text}")
    except Exception as e:
        print(f"⚠️ Telegram 请求异常: {e}")

# ================= 核心逻辑 =================
class EUservBot:
    def __init__(self):
        self.driver = None
        self.wait = None

    def init_driver(self):
        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        driver_path = shutil.which("chromedriver") or "/usr/bin/chromedriver"
        try:
            service = Service(executable_path=driver_path) if os.path.exists(driver_path) else None
            self.driver = webdriver.Chrome(service=service, options=options)
            self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                'source': 'Object.defineProperty(navigator, "webdriver", {get: () => undefined})'
            })
            self.wait = WebDriverWait(self.driver, Config.ELEMENT_WAIT_TIMEOUT)
            return True
        except Exception as e:
            Config.error_message = f"Driver init failed: {str(e)}"
            return False

    def login(self) -> bool:
        try:
            self.driver.get("https://support.euserv.com/index.iphp")
            if "Logout" in self.driver.page_source:
                return True

            self.wait.until(EC.presence_of_element_located((By.NAME, "email"))).send_keys(Config.EU_EMAIL)
            self.driver.find_element(By.NAME, "password").send_keys(Config.EU_PASSWORD)
            
            try:
                self.driver.find_element(By.XPATH, "//input[@type='submit' and contains(@value, 'Login')]").click()
            except:
                self.driver.find_element(By.TAG_NAME, "form").submit()
            
            self.wait.until(lambda d: "Logout" in d.page_source)
            if "captcha" in self.driver.page_source.lower():
                captcha_img = self.driver.find_element(By.ID, "captcha")
                img_bytes = self.crop_captcha_image(captcha_img)
                assa = self.solve_captcha(img_bytes)
                print(f"解析结果：{str(assa)}")
                self.driver.find_element(By.NAME, "captcha_code").send_keys(assa)
                try:
                    self.driver.find_element(By.XPATH, "//input[@type='submit' and contains(@value, 'Login')]").click()
                except:
                    self.driver.find_element(By.TAG_NAME, "form").submit()
            
            self.wait.until(EC.presence_of_element_located((By.ID, "kc2_content")))

            try:
                # 直接查找元素，不等待
                self.driver.find_element(By.ID, "kc2_content_core")
                try:
                    self.driver.find_element(By.XPATH, "//input[@type='submit' and contains(@value, 'Save')]").click()
                except:
                    self.driver.find_element(By.TAG_NAME, "form").submit()
                self.wait.until(EC.presence_of_element_located((By.ID, "kc2_default_box_title_minus")))
            except NoSuchElementException:
                self.wait.until(EC.presence_of_element_located((By.ID, "kc2_default_box_title_minus")))
            return True
            
        except Exception as e:
            Config.error_message = f"Login failed: {str(e)}"
            return False

    def process_single_contract(self) -> bool:
        try:
            self.wait.until(EC.presence_of_element_located((By.ID, "kc2_order_customer_orders_tab_1")))
            self.driver.find_element(By.ID, "kc2_order_customer_orders_tab_1").click()
            try:
                extend_submit = self.driver.find_element(By.XPATH, "//input[@type='submit' and contains(@value, 'Extend contract')]")
                extend_submit.click()
            except NoSuchElementException:
                Config.action_taken = "无需续约 (所有合同正常)"
                return True
            
            try:
                WebDriverWait(self.driver, 20).until(EC.presence_of_element_located((By.ID, "kc2_customer_contract_details_change_plan_dialog_content")))
            except TimeoutException:
                pass
            
            if not self._click_extend():
                Config.error_message = "Failed to click Extend button"
                return False
            loading_modal_xpath = "//div[contains(@class, 'modal') and .//div[contains(@class, 'progress')]]"
            try:
                modal = WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.XPATH, loading_modal_xpath)))
                WebDriverWait(self.driver, 30).until_not(EC.visibility_of(modal))
            except TimeoutException:
                pass
            if not self._handle_pin():
                Config.error_message = "PIN verification failed"
                return False
            self._final_confirm()
            Config.action_taken = "续约成功"
            return True

        except Exception as e:
            Config.error_message = f"Process error: {str(e)}"
            return False

    def _click_extend(self) -> bool:
        try:
            btn = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//input[@value='Extend' and contains(@onclick, 'kc2_customer_contract_details_extend_contract_confirmation_dialog_show')]"))
            )
            self.driver.execute_script("arguments[0].click();", btn)
            return True
        except Exception:
            return False

    def _handle_pin(self) -> bool:
        modal_xpath = "//div[contains(@class, 'modal') and .//h5[contains(text(), 'Security check')]]"
        loading_xpath = "//div[contains(@class, 'modal') and .//div[contains(@class, 'progress')]]"
        
        try:
            modal = WebDriverWait(self.driver, 5).until(EC.presence_of_element_located((By.XPATH, modal_xpath)))
        except TimeoutException:
            return True

        time.sleep(Config.WAITING_TIME_OF_PIN)

        pin = get_pin_from_mailparser(Config.MAILPARSER_URL)
        if not pin:
            Config.error_message = "Failed to retrieve PIN"
            return False
        
        try:
            self.driver.find_element(By.XPATH, "//input[@name='auth']").send_keys(pin)
            btn = WebDriverWait(self.driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Continue')]"))
            )
            btn.click()
            
            try:
                load_modal = WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.XPATH, loading_xpath)))
                WebDriverWait(self.driver, 20).until_not(EC.visibility_of(load_modal))
            except TimeoutException:
                pass
            
            WebDriverWait(self.driver, 10).until_not(EC.visibility_of(modal))
            return True
        except Exception as e:
            Config.error_message = f"PIN error: {str(e)}"
            return False

    def _final_confirm(self):
        try:
            for text in ["OK", "Confirm"]:
                try:
                    btn = WebDriverWait(self.driver, 2).until(
                        EC.element_to_be_clickable((By.XPATH, f"//button[contains(text(), '{text}')]"))
                    )
                    if btn.is_displayed():
                        btn.click()
                        break
                except: continue
        except: pass

    def cleanup(self):
        if self.driver:
            try:
                self.driver.quit()
            except:
                os.system("pkill -f chrome >/dev/null 2>&1")

    def run(self) -> bool:
        if not self.init_driver(): return False
        try:
            if not self.login(): return False
            return self.process_single_contract()
        finally:
            self.cleanup()
    
    def solve_captcha(self, image_data, website_url="", page_action=""):
        """
        使用 yescaptcha API 解析 Securimage 验证码
        :param image_data: 图片数据（bytes 或 base64 编码）
        :param website_url: 目标网站 URL
        :param page_action: 页面动作描述
        :return: 验证码识别结果
        """
        if not Config.api_key:
            print("⚠️ 出现人机验证， captcha 配置缺失。")
            return ""
        print("🔍 开始处理验证码识别...")
        try:
                
            # 准备任务数据
            task_data = {
                "clientKey": Config.api_key,
                "task": {
                    "type": "ImageToTextTaskOcrBase",
                    "body": base64.b64encode(image_data).decode('utf-8'),  # 确保这里传入的是字节数据
                }
            }
            
            if website_url:
                task_data["websiteURL"] = website_url
                
            if page_action:
                task_data["pageAction"] = page_action
            
            print(f"📤 发送验证码识别请求...")
            # 发送任务请求
            response = requests.post(
                f"{Config.base_url}/createTask",
                json=task_data,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            if response.status_code != 200:
                print(f"❌ API 请求失败: {response.status_code}, {response.text}")
                return ""
                
            result = response.json()
            if result.get("errorId") != 0:
                print(f"❌ 创建任务失败: {result.get('errorCode')}, {result.get('errorDescription')}")
                return ""
                
            task_id = result["taskId"]
            print(f"✅ 验证码任务已提交，任务ID: {task_id}")
            
            # 轮询结果
            max_attempts = 30
            for attempt in range(max_attempts):
                time.sleep(2)
                print(f"⏳ 查询识别结果... ({attempt + 1}/{max_attempts})")
                
                check_response = requests.post(
                    f"{Config.base_url}/getTaskResult",
                    json={
                        "clientKey": Config.api_key,
                        "taskId": task_id
                    },
                    headers={"Content-Type": "application/json"},
                    timeout=30
                )
                
                if check_response.status_code != 200:
                    print(f"❌ 查询结果请求失败: {check_response.status_code}, {check_response.text}")
                    continue
                    
                check_result = check_response.json()
                
                if check_result.get("errorId") != 0:
                    print(f"❌ 查询结果失败: {check_result.get('errorCode')}")
                    return ""
                    
                status = check_result.get("status")
                if status == "ready":
                    solution = check_result.get("solution", {}).get("text", "")
                    print(f"🎉 验证码识别成功: {solution}")
                    # 解析数学表达式并计算结果
                    calculated_result = self.calculate_math_expression(solution)
                    if calculated_result is not None:
                        print(f"🧮 计算结果: {calculated_result}")
                        return str(calculated_result)
                    else:
                        print(f"⚠️ 未检测到数学表达式，返回原始结果: {solution.strip()}")
                        return solution.strip()
                elif status == "processing":
                    print(f"⏳ 验证码识别中... ({attempt + 1}/{max_attempts})")
                    continue
                else:
                    print(f"⚠️ 未知状态: {status}")
                    return ""
                    
            print("⏰ 验证码识别超时")
            return ""
            
        except Exception as e:
            print(f"❌ 验证码识别失败: {str(e)}")
            return ""

        
    def crop_captcha_image(self, captcha_element):
        """裁剪验证码图片（最简版）"""
        try:
            # 获取位置和大小
            loc = captcha_element.location
            size = captcha_element.size
            
            # 截图并裁剪
            screenshot = self.driver.get_screenshot_as_png()
            img = Image.open(io.BytesIO(screenshot))
            cropped = img.crop((
                loc['x'], 
                loc['y'], 
                loc['x'] + size['width'], 
                loc['y'] + size['height']
            ))
            
            # 直接返回 PNG 格式的字节数据
            output = io.BytesIO()
            cropped.save(output, format='PNG')
            return output.getvalue()
        except Exception as e:
            print(f"裁剪验证码图片失败: {str(e)}")
            return None
    
    def calculate_math_expression(self, text):
        """
        解析并计算数学表达式（数字 运算符 数字）
        :param text: 验证码识别结果文本
        :return: 计算结果，如果无法解析则返回None
        """
        import re
        
        # 先处理重复模式：如 "9x3x9" -> "9x3"
        # 查找形如 "数字x数字x数字" 且第一个和第三个数字相同的模式
        repeated_pattern = r'(\d+)([x*×])(\d+)\2(\1)'
        repeated_match = re.search(repeated_pattern, text)
        
        if repeated_match:
            num1 = int(repeated_match.group(1))  # 第一个数字
            operator = repeated_match.group(2)   # 第一个运算符
            num2 = int(repeated_match.group(3))  # 中间的数字
            
            print(f"🔄 检测到重复模式，简化表达式: {num1}{operator}{num2}")
            
            # 使用简化后的表达式进行计算
            try:
                if operator in ['x', '*', '×']:
                    result = num1 * num2
                else:
                    print(f"⚠️ 不支持的运算符: {operator}")
                    return None
                
                print(f"✅ 计算完成: {num1}{operator}{num2} = {result}")
                return result
            except Exception as e:
                print(f"❌ 计算错误: {str(e)}")
                return None
        
        # 如果没有匹配到重复模式，则按常规方式匹配数学表达式
        # 匹配数字 运算符 数字的模式
        pattern = r'(\d+)\s*([+\-*/x×])\s*(\d+)'
        match = re.search(pattern, text)
        
        if match:
            num1 = int(match.group(1))  # 第一个数字
            operator = match.group(2)   # 运算符
            num2 = int(match.group(3))  # 第二个数字
            
            print(f"🔢 解析到数学表达式: {num1}{operator}{num2}")
            
            try:
                if operator in ['+', '＋']:
                    result = num1 + num2
                elif operator in ['-', '－']:
                    result = num1 - num2
                elif operator in ['*', 'x', '×']:
                    result = num1 * num2
                elif operator in ['/', '÷']:
                    if num2 == 0:
                        print("⚠️ 除零错误，无法计算")
                        return None
                    result = int(num1 / num2)  # 取整数部分
                else:
                    print(f"⚠️ 不支持的运算符: {operator}")
                    return None
                
                print(f"✅ 计算完成: {num1}{operator}{num2} = {result}")
                return result
            except Exception as e:
                print(f"❌ 计算错误: {str(e)}")
                return None
        else:
            print("ℹ️ 未找到数学表达式模式，尝试返回原值")
            return None

# ================= 主入口 =================
def main():
    # 基础校验
    if not Config.EU_EMAIL or not Config.EU_PASSWORD or not Config.MAILPARSER_URL:
        msg = "Missing environment variables (EU_USER, EU_PASS, MAILPARSER_URL)"
        print(f"❌ {msg}")
        send_telegram_notification("FAILED", msg)
        sys.exit(1)

    print("="*40)
    print("🚀 EUserv Auto-Renew + Telegram")
    print(f"👤 User: {Config.EU_EMAIL}")
    print("="*40)

    success = False
    final_msg = ""

    for i in range(1, Config.MAX_RETRIES + 1):
        print(f"🔄 Attempt {i}/{Config.MAX_RETRIES}...")
        if EUservBot().run():
            success = True
            final_msg = Config.action_taken
            print(f"✨ Success: {final_msg}")
            break
        
        print(f"⚠️ Attempt {i} failed.")
        if i < Config.MAX_RETRIES:
            time.sleep(Config.RETRY_DELAY)
    
    if success:
        # 如果是因为"无需续约"而成功，可以选择是否推送。这里设定为：只有真正执行了续约或出错才推送，或者全部推送。
        # 为了保险起见，我们只要运行完成就推送，但区分状态。
        # 如果你只想在"真正续约了"或者"出错"时才收到通知，可以取消下面这行的注释：
        # if Config.action_taken == "无需续约 (所有合同正常)": return 
        
        send_telegram_notification("SUCCESS", final_msg)
        sys.exit(0)
    else:
        error_detail = Config.error_message if Config.error_message else "Unknown error after all retries"
        send_telegram_notification("FAILED", error_detail)
        print("❌ All attempts failed.")
        sys.exit(1)

if __name__ == "__main__":
    main()
