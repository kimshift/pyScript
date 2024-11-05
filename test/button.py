# -*- coding: utf-8 -*-
import pyautogui
import cv2
from dictionaries import dict

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
    
# 获取全选坐标
def check_all(img_path):
    info= location(img_path)
    if info[0] is None:
        return (None, None)
    center_x, center_y, tl, br, width, height = info
    x=int(tl[0] + 8) 
    return (x,center_y)

# 点击坐标
def auto_click(location):
    if location[0] is None:
        print("未找到坐标，无法点击")
        return    
    pyautogui.click(location[0], location[1])

class Buttons:
    def __init__(self):
        self.prefix = "image/emulator/" # 按钮图片路径前缀
        self.coord = {
            '批量操作': (None, None),    # 操作
            '批量新增': (None, None),    # 创建
            '全选': (None, None),        # 全选
            '批量设置': (None, None),    # 设置
            '批量启动': (None, None),    # 启动
        }    

    def 通用(self, btn):
        path = self.prefix + dict[btn] + ".png"
        coord = self.coord[btn]
        if coord[0] is None:
            coord = location(path)[:2]
            self.coord[btn] = coord
        print(f'点击{btn}按钮:',coord)    
        auto_click(coord)
    
    def 全选(self, btn):
        coord = self.coord[btn]
        if coord[0] is None:
            path = self.prefix + dict[btn] + ".png"
            coord = check_all(path)
        print(f'点击{btn}按钮:',coord)    
        auto_click(coord)
    
    def default(self, btn):
        if btn in self.coord:
            return self.通用(btn)
        print(f'************Error:{btn}按钮获取失败************')

    def click(self, btn):
        button = getattr(self, btn, self.default)
        button(btn)
   