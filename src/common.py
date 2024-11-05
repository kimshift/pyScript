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
from dict import data as dict, ld_left_btn, ld_right_btn

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
    # 读取要查找的图片
    template = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
    w, h = template.shape[::-1]
    
    # 截取当前屏幕截图
    screenshot = pyautogui.screenshot('image/screenshot.png')
    screenshot = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2GRAY)

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

# 点击坐标
def click(coord, number=1, interval=0.5):
    if coord[0] is None:
        print("未找到坐标，无法点击")
        return 
    for i in range(number):
        pyautogui.click(coord[0], coord[1])
        if(i < number - 1):
            pyautogui.sleep(interval)    

# 双击坐标
def doubleClick(coord, interval=0.5):
    if coord[0] is None:
        print("未找到坐标，无法点击")
        return 
    pyautogui.moveTo(coord[0], coord[1])   
    pyautogui.doubleClick(interval)

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

class Buttons:
    def __init__(self,prefix):
        self.prefix = prefix # 按钮图片路径前缀
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
        print("初始化按钮坐标:", self.coord)    

    def 通用(self, num, position):
        coord = (None, None)
        if self.btn in self.coord:
            coord = self.coord[self.btn]
            if coord[0] is None:
                coord = location(self.path,position)[:2]
                self.coord[self.btn] = coord
        coord = location(self.path,position)[:2]
        print(f'点击->{self.btn}按钮:',coord)
        click(coord, num)
    
    def 监听点击(self, num, position):
        config = {'position':position, 'num':num }
        wait_click(self.path, config)
        print(f'监听->{self.btn}点击按钮完成')

    def default(self, btn, num, listen):
        if btn in dict:
            self.btn = btn
            self.path = self.prefix + dict[btn] + ".png"
            position_map = {param: 'left' for param in ld_left_btn}
            position_map.update({param: 'right' for param in ld_right_btn})
            position = position_map.get(btn, 'center')
            if listen:
                self.监听点击(num, position)
            else:
                self.通用(num, position)
        else:
            print(f'************Error:{btn}按钮获取失败************')

    def click(self, btn, num=1, listen=False):
        """
          btn:按钮名称
          num:点击次数 
          listen:是否持续监听;为True时,num为监听点击次数
        """
        button = getattr(self, btn, self.default)
        button(btn, num, listen) 
            


