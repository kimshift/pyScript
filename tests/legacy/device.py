# -*- coding: utf-8 -*-
import subprocess
import psutil
import pyperclip
import pyautogui
import cv2

# 检查是否有指定名称的进程正在运行
def is_process_running(process_name):
    for proc in psutil.process_iter(['pid', 'name']):
        if process_name.lower() in proc.info['name'].lower():
            return True
    return False

# 关闭指定名称的进程
def close_running_process(process_name):
    for proc in psutil.process_iter(['pid', 'name']):
        if process_name.lower() in proc.info['name'].lower():
            proc.kill()
    # 等待进程完全关闭
    while is_process_running(process_name):
        pass
    print(process_name, "进程已关闭")

# 打开雷电多开应用
def open_emulator(path="D:\\Program Files\\LDPlayer9\\dnmultiplayer.exe"):
    subprocess.Popen(path)
    pyautogui.sleep(1)

# 关闭雷电多开应用
def close_emulator(name="dnmultiplayer.exe"):
    close_running_process(name)

# 启动雷电模拟器
def start_emulator(emulator_path,process_name):
    # 检查雷电模拟器是否已经在运行
    if is_process_running(process_name):
        print("雷电模拟器已在运行，尝试重启...")
        # 杀死现有的雷电模拟器进程
        close_emulator(process_name)
        # 重新启动雷电模拟器
        print("重新启动雷电模拟器...")
        open_emulator(emulator_path)
    else:
        print("雷电模拟器未在运行，启动中...")
        open_emulator(emulator_path)

# 获取坐标
def location(img_path):
    """
    匹配位置信息
    :param img_path: 图片路径
    :return: (x, y, tl, br, w, h) => (x, y)为中心坐标，(tl, br)为左上角和右下角坐标，(w, h)为宽高
    """
    try:
        # 将屏幕截图保存
        pyautogui.screenshot('image/screenshot.png')
        # 载入截图
        screenshot = cv2.imread('image/screenshot.png')
        # 载入模板图片
        img_path = img_path.encode('utf-8').decode('utf-8')
        print(img_path)
        template = cv2.imread(img_path)
        # 读取模板图片的宽高
        h, w = template.shape[:2]
        # 在截图中进行模板匹配
        result = cv2.matchTemplate(screenshot, template, cv2.TM_SQDIFF_NORMED)
        # 解析出匹配区域的左上角坐标
        tl = cv2.minMaxLoc(result)[2]
        # 计算匹配区域右下角坐标
        br = (tl[0] + w, tl[1] + h)
        # 计算出匹配区域的中心坐标
        x=int((tl[0] + br[0]) / 2)
        y=int((tl[1] + br[1]) / 2)
        return (x, y, tl, br, w, h)
    except Exception as e:
        print("获取坐标异常: ",e)
        return (None, None, None, None, None, None)
    
def get_xy(img_path):
   return location(img_path)[:2]
    
# 点击坐标
def click(location):
    if location[0] is None:
        print("未找到坐标，无法点击")
        return
    pyautogui.click(location[0], location[1])

# 等待
def sleep(second):
    pyautogui.sleep(second)

# 输入文本
def write(value):
    pyautogui.typewrite(str(value))

# 粘贴文本
def paste(value):
    pyperclip.copy(value)
    pyautogui.hotkey('ctrl','v')

# 搜索
def search(value=''):
    # 清除焦点
    select = location("image/emulator/select.png")
    select = select[:2]
    click(select) 

    # 点击搜索
    search_btn = location("image/emulator/search.png")
    search_btn = search_btn[:2]
    print('搜索按钮坐标:',search_btn)
    click(search_btn) # 点击搜索按钮
    pyautogui.sleep(0.1)

    # 清空搜索框
    pyautogui.hotkey('ctrl','a')
    pyautogui.sleep(0.1)
    pyautogui.hotkey('backspace')

    # 输入内容
    write(value)
    print('搜索内容:',value)

    
if __name__ == "__main__":
    print("设备模块测试")
    emulator_path = "D:\\Program Files\\LDPlayer9\\dnmultiplayer.exe"
    process_name = "dnmultiplayer.exe"
    # 打开雷电模拟器
    # start_emulator(emulator_path,process_name)
   