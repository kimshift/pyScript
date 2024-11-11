# -*- coding: utf-8 -*-
import subprocess
import psutil
import pyperclip
import pyautogui
import cv2
import numpy as np
import time
import keyboard
import json
import re
import os
from data import dict
pyautogui.FAILSAFE = True # 安全退出

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
    print(process_name, "-进程已关闭")

# 打开应用
def open_app(app_path):
    subprocess.Popen(app_path)
    pyautogui.sleep(1)

# 关闭应用
def close_app(app_name):
    close_running_process(app_name)

# 重启应用
def restart_app(app_path,process_name):
    # 检查应用是否已经在运行
    if is_process_running(process_name):
        print(f"{process_name}-已在运行，尝试重启...")
        # 杀死现有的应用进程
        close_app(process_name)
        # 重新启动应用
        print(f"重新启动{process_name}-应用...")
        open_app(app_path)
    else:
        print(f"{process_name}-未在运行，启动中...")
        open_app(app_path)

def location(img_path,position="center",width=8,height=8):
    try:
        # 截取当前屏幕截图
        screenshot = pyautogui.screenshot('screenshot.png')
        screenshot = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2GRAY)

        # 读取要查找的图片
        template = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
        w, h = template.shape[::-1]

        # 使用模板匹配在屏幕上查找图片
        result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result) # max_loc:矩形左上角
        # 设置匹配阈值
        threshold = 0.8
        coord = (None, None)
        if max_val >= threshold:
            # 获取图片中心点的坐标
            center_x, center_y = max_loc[0] + w // 2, max_loc[1] + h // 2
            left_x, right_x = max_loc[0] + width // 2, max_loc[0] + w - width // 2
            coords = {
                 "left": (left_x, center_y),
                 "right": (right_x, center_y),
                 "center": (center_x, center_y),
            }
            coord = coords[position]
        return coord
    except Exception as e:
        print(f"获取位置异常: {e}")
        return (None, None)
    

def v_location(img_path):
    # 截取屏幕截图
    screenshot = pyautogui.screenshot('screenshot.png')
    screenshot = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)

    # 加载模板图像
    template = cv2.imread(img_path, cv2.IMREAD_COLOR)
    template_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
    w, h = template_gray.shape[::-1]

    # 将屏幕截图转换为灰度图
    screenshot_gray = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)

    # 模板匹配
    res = cv2.matchTemplate(screenshot_gray, template_gray, cv2.TM_CCOEFF_NORMED)
    threshold = 0.8
    loc = np.where(res >= threshold)

    # 获取所有匹配的位置
    matches = []
    for pt in zip(*loc[::-1]):
        matches.append((pt[0], pt[1]))

    # 如果没有找到匹配项，退出程序
    if not matches:
        return (None, None)
    
    # 筛选垂直方向上最上面的那个按钮
    topmost_match = min(matches, key=lambda x: x[1])

    # 计算按钮的中心点
    center_x = topmost_match[0] + w // 2
    center_y = topmost_match[1] + h // 2
    return (center_x, center_y)

# 获取横向方位
def horizontal(btn,left_btn=None, right_btn=None,center_btn=None):
    left_btn = left_btn if left_btn else dict['left_btn']
    right_btn = right_btn if right_btn else dict['right_btn']
    center_btn = center_btn if center_btn else []

    position_map = {param: 'left' for param in left_btn} # 将左侧按钮的键值对添加到字典中
    position_map.update({param: 'right' for param in right_btn}) # 将右侧按钮的键值对添加到字典中
    position_map.update({param: 'center' for param in center_btn}) # 将右侧按钮的键值对添加到字典中
    # 使用get方法获取键对应的值，如果键不存在则返回默认值'center'
    position = position_map.get(btn, 'center')
    return position

# 提示框
def alert(value):
    pyautogui.alert(str(value))

# 确认提示框
def confirm(title="标题", text="内容",buttons=['取消','确认']):
    result = pyautogui.confirm(title=title,text=text,buttons=buttons)
    return result == buttons[1]

# 点击坐标
def click(coord, number=1, interval=0.5):
    if isinstance(coord, str):
        coord = coord.split(',')
    if coord[0] is None:
        print("未找到坐标=>无法点击")
        res = confirm('提示','未找到坐标，无法点击。是否关闭进程？',['否','是'])
        exit() if res else None
        return False
    for i in range(number):
        pyautogui.click(int(coord[0]), int(coord[1]))
        if(i < number - 1):
            pyautogui.sleep(interval)
    return True

# 双击坐标
def doubleClick(coord, interval=0.5):
    if coord[0] is None:
        print("未找到坐标=>无法点击")
        return False
    pyautogui.moveTo(coord[0], coord[1])   
    pyautogui.doubleClick(interval)
    return True

# 监听点击
def wait_click(path,config={}):
    number = config.get('number', 1)
    interval = config.get('interval', 0.5)
    position = config.get('position', 'center')
    width = config.get('width', 8)
    try :
        count = 0
        while True:
            if keyboard.is_pressed('f8'):  # 长按F8停止
                print("F8终止监听.")
                break  # 跳出循环
            coord = location(path, position, width)
            if coord[0] is not None:
                count += 1
                click(coord)
                print("点击目标:", coord)
            if count == number:
                print(f"监听点击完毕{count}次")
                break
            sleep(interval)
    except :
        print('终止监听.')

# 长按坐标
def long_press(coord, button='left'):
    if isinstance(coord, str):
        coord = coord.split(',')
        coord = (int(coord[0]), int(coord[1]))
    if coord[0] is None:
        print("未找到坐标=>无法长按")
        res = confirm('提示','未找到坐标，无法长按。是否关闭进程？',['否','是'])
        exit() if res else None
        return False
    # 按下鼠标右键 
    pyautogui.mouseDown(int(coord[0]), int(coord[1]), button=button)
    

def drag(start, end, button='left', duration=0.5):
    if isinstance(end, str):
        end = end.split(',')
        end = (int(end[0]), int(end[1]))
    long_press(start, button)
    sleep(1)
    if end[0] is None:
        # 按下鼠标右键 
        print("未找到坐标=>无法拖动")
        res = confirm('提示','未找到坐标，无法拖动。是否关闭进程？',['否','是'])
        exit() if res else None
        return False
    pyautogui.moveTo(end[0],end[1],duration=duration)  # duration 参数控制移动速度 
    pyautogui.mouseUp()
    
    

# 点击键盘
def click_key(key):
    # pyautogui.keyDown(key)
    # pyautogui.keyUp(key)
    pyautogui.press(key)

# 等待
def sleep(second):
    pyautogui.sleep(second)

# 清楚输入框
def clear():
    pyautogui.hotkey('ctrl','a')
    pyautogui.sleep(0.1)
    pyautogui.hotkey('backspace')

# 输入文本
def write(value):
    if contains_chinese(value):
        paste(value)
    else:
        pyautogui.typewrite(str(value))

# 粘贴文本
def paste(value):
    pyperclip.copy(value)
    pyautogui.hotkey('ctrl','v')

# 读取json文件
def read_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

# 写入json文件
def write_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# 判断是否包含中文以及中文标点符号
def contains_chinese(text):
    # 定义一个匹配中文字符和中文标点符号的正则表达式模式
    pattern = re.compile(r'[\u4e00-\u9fff]|[\u3000-\u303f\uff00-\uffef]')
    # 搜索文本中是否有匹配的模式
    match = pattern.search(text)
    return match is not None

# 打开电脑文件夹
def open_file(path):
    os.startfile(path)

class Buttons:
    def __init__(self, prefix=None, suffix=None):
        config = read_json("config.json") 
        self.root = config['image_path']
        self.common = config['image_prefix'] # 按钮图片公共目录
        self.prefix = prefix if prefix else self.common # 按钮图片目录前缀
        suffix = suffix if suffix else config['image_type'] # 按钮图片后缀
        self.suffix =f".{suffix}"
        self.path = '' # 按钮图片路径
        self.btn = ''  # 按钮名称
        self.coord = {
            '批量操作': (None, None),    # 操作
            '批量新增': (None, None),    # 创建
            '全选': (None, None),        # 全选
            '批量设置': (None, None),    # 设置
            '批量启动': (None, None),    # 启动
            '其他设置': (None, None),
            '分辨率': (None, None),     
            '内存': (None, None),     
            '退出选项': (None, None),     
            '保存设置': (None, None),     
            '确定': (None, None),     
        }
        print("初始化Buttons类:", self.prefix)    

    def 通用(self, num, position):
        coord = (None, None)
        if self.btn in self.coord:
            coord = self.coord[self.btn]
            if coord[0] is None:
                coord = location(self.path,position)[:2]
                self.coord[self.btn] = coord
        coord = location(self.path,position)[:2]
        print(f'点击->{self.btn}按钮:',coord)
        return click(coord, num)
    
    def 监听点击(self, num, position):
        config = {'position':position, 'num':num }
        wait_click(self.path, config)
        print(f'监听->{self.btn}点击按钮完成')

    def default(self, btn, num, listen):
        current_dict = dict[self.prefix]
        if btn in dict['global']:
            self.btn = btn
            prefix = self.prefix if btn in current_dict else self.common
            self.path = self.root + prefix + '/' + dict['global'][btn] + self.suffix
            position = horizontal(btn)
            if listen:
               return self.监听点击(num, position)
            return self.通用(num, position)
        print(f'************Error:{btn}按钮获取失败************')
        return False

    def find(self, btn, listen=False):
        try :
            coord = (None, None)
            if btn not in dict['global']:
                return coord
            current_dict = dict[self.prefix]
            prefix = self.prefix if btn in current_dict else self.common
            path = self.root + prefix + '/' + dict['global'][btn] + self.suffix
            position = horizontal(btn)
            while True:
                if keyboard.is_pressed('f8'):  # 长按F8停止
                    print("F8终止查找.")
                    break  # 跳出循环
                coord = location(path, position)
                if coord[0]:
                    print(f'{btn}-坐标：', coord)
                    listen = False
                if listen == False:
                    break
                sleep(1)
            return coord        
        except :
            print('终止查找.')
            return (None, None)

    def click(self, btn, num=1, listen=False):
        """
          btn:按钮名称
          num:点击次数 
          listen:是否持续监听;为True时,num为监听点击次数
        """
        button = getattr(self, btn, self.default)
        return button(btn, num, listen) 
            


